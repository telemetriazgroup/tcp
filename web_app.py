"""
Interfaz web para gestionar comando_test.txt, comandos enviados, chat por dispositivo
y arranque/parada del servidor TCP en 9990 / 9991.
"""
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.urandom(24)

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
COMANDO_ARCHIVO = os.path.join(DIR_BASE, "comando_test.txt")
REGISTRO_ENVIADOS = os.path.join(DIR_BASE, "comando_enviado")
CHAT_DIR = os.path.join(DIR_BASE, "chats")
CONEXIONES_LOG = os.path.join(DIR_BASE, "dispositivos_conexiones.txt")

TCP_SCRIPT = os.path.join(DIR_BASE, "tcp_test.py")
TCP_STATE_FILE = os.path.join(DIR_BASE, "tcp_server_state.json")
PUERTO_TCP_A = 9990
PUERTO_TCP_B = 9991

tcp_lock = threading.Lock()
tcp_child = None
tcp_port_running = None


def _pid_vivo(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _leer_estado_archivo():
    if not os.path.exists(TCP_STATE_FILE):
        return None
    try:
        with open(TCP_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _guardar_estado_tcp(puerto: int, pid: int):
    with open(TCP_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"puerto": puerto, "pid": pid}, f)


def _borrar_estado_tcp():
    try:
        os.remove(TCP_STATE_FILE)
    except OSError:
        pass


def obtener_estado_tcp():
    """Estado del proceso tcp_test.py (gestionado por la web u otro arranque)."""
    global tcp_child, tcp_port_running
    with tcp_lock:
        if tcp_child is not None and tcp_child.poll() is None:
            return {
                "activo": True,
                "puerto": tcp_port_running,
                "pid": tcp_child.pid,
                "web": True,
            }
        if tcp_child is not None:
            tcp_child = None
            tcp_port_running = None

    st = _leer_estado_archivo()
    if st and st.get("pid") and _pid_vivo(int(st["pid"])):
        return {
            "activo": True,
            "puerto": st.get("puerto"),
            "pid": int(st["pid"]),
            "web": False,
        }
    if st:
        _borrar_estado_tcp()
    return {"activo": False, "puerto": None, "pid": None, "web": False}


def _detener_subproceso(p: subprocess.Popen | None, timeout: float = 5.0):
    if p is None or p.poll() is not None:
        return
    p.terminate()
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


def _detener_por_pid(pid: int):
    if not _pid_vivo(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(30):
        if not _pid_vivo(pid):
            return
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def liberar_puertos_tcp() -> list[str]:
    """
    Varios intentos para liberar 9990 y 9991 (proceso colgado, TIME_WAIT, etc.).
    Linux/WSL: fuser -k y lsof + kill -9.
    """
    log = []
    for puerto in (PUERTO_TCP_A, PUERTO_TCP_B):
        fuser = shutil.which("fuser")
        if fuser:
            try:
                r = subprocess.run(
                    [fuser, "-k", f"{puerto}/tcp"],
                    capture_output=True,
                    text=True,
                    timeout=12,
                )
                log.append(f"fuser -k {puerto}/tcp → código {r.returncode}")
            except (subprocess.TimeoutExpired, OSError) as e:
                log.append(f"fuser {puerto}: {e}")
        lsof = shutil.which("lsof")
        if lsof:
            try:
                r = subprocess.run(
                    [lsof, "-ti", f":{puerto}"],
                    capture_output=True,
                    text=True,
                    timeout=6,
                )
                for pid in r.stdout.strip().split():
                    if not pid.isdigit():
                        continue
                    try:
                        subprocess.run(
                            ["kill", "-9", pid],
                            capture_output=True,
                            timeout=4,
                        )
                        log.append(f"kill -9 {pid} (puerto {puerto})")
                    except OSError as e:
                        log.append(f"kill {pid}: {e}")
            except (subprocess.TimeoutExpired, OSError) as e:
                log.append(f"lsof {puerto}: {e}")
    time.sleep(1.2)
    return log


def detener_servidor_tcp() -> tuple[bool, str]:
    global tcp_child, tcp_port_running
    partes = []
    with tcp_lock:
        st = _leer_estado_archivo()
        pid_arch = int(st["pid"]) if st and st.get("pid") else None

        if tcp_child is not None:
            _detener_subproceso(tcp_child)
            tcp_child = None
            tcp_port_running = None
            partes.append("Proceso iniciado desde la web terminado.")

        if pid_arch and _pid_vivo(pid_arch):
            _detener_por_pid(pid_arch)
            partes.append(f"Señal SIGTERM/SIGKILL a PID {pid_arch}.")

        _borrar_estado_tcp()

    partes.extend(liberar_puertos_tcp())
    return True, " · ".join(partes[:10])


def iniciar_servidor_tcp(puerto: int) -> tuple[bool, str]:
    global tcp_child, tcp_port_running
    if puerto not in (PUERTO_TCP_A, PUERTO_TCP_B):
        return False, "Puerto no permitido (solo 9990 o 9991)."

    detener_servidor_tcp()

    with tcp_lock:
        tcp_child = subprocess.Popen(
            [sys.executable, TCP_SCRIPT, "--port", str(puerto)],
            cwd=DIR_BASE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        tcp_port_running = puerto
        _guardar_estado_tcp(puerto, tcp_child.pid)

    time.sleep(0.4)
    if tcp_child.poll() is not None:
        rc = tcp_child.returncode
        with tcp_lock:
            tcp_child = None
            tcp_port_running = None
        _borrar_estado_tcp()
        liberar_puertos_tcp()
        return (
            False,
            f"El servidor salió al arrancar (código {rc}). Comprueba que el puerto esté libre.",
        )
    return True, f"Servidor TCP activo en puerto {puerto} (PID {tcp_child.pid})."

LINE_CHAT = re.compile(
    r"^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\] (dispositivo|servidor)> (.*)$"
)


def parse_nombre_chat(filename: str):
    """chats/192_168_1_5_50234.txt -> (192.168.1.5, 50234, id '192_168_1_5_50234')"""
    base = os.path.basename(filename)
    if not base.endswith(".txt"):
        return None
    stem = base[:-4]
    parts = stem.split("_")
    if len(parts) < 2:
        return None
    try:
        port = int(parts[-1])
    except ValueError:
        return None
    ip = ".".join(parts[:-1])
    return {"id": stem, "ip": ip, "port": port, "ruta": filename}


def leer_mensajes_chat(ruta: str, limite: int = 200):
    mensajes = []
    if not os.path.exists(ruta):
        return mensajes
    with open(ruta, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = LINE_CHAT.match(line)
            if m:
                mensajes.append(
                    {
                        "fecha": m.group(1),
                        "rol": m.group(2),
                        "texto": m.group(3),
                    }
                )
            elif line.strip():
                mensajes.append(
                    {"fecha": "", "rol": "dispositivo", "texto": line}
                )
    return mensajes[-limite:]


def listar_dispositivos_chats():
    os.makedirs(CHAT_DIR, exist_ok=True)
    patron = os.path.join(CHAT_DIR, "*.txt")
    archivos = glob.glob(patron)
    dispositivos = []
    for ruta in archivos:
        info = parse_nombre_chat(ruta)
        if not info:
            continue
        info["mensajes"] = leer_mensajes_chat(ruta)
        try:
            info["mtime"] = os.path.getmtime(ruta)
        except OSError:
            info["mtime"] = 0
        dispositivos.append(info)
    dispositivos.sort(key=lambda x: x["mtime"], reverse=True)
    return dispositivos


def leer_log_conexiones(max_lineas: int = 60):
    if not os.path.exists(CONEXIONES_LOG):
        return []
    with open(CONEXIONES_LOG, "r", encoding="utf-8") as f:
        lineas = f.readlines()
    return [ln.rstrip("\n") for ln in lineas[-max_lineas:]]


def leer_comandos():
    if os.path.exists(COMANDO_ARCHIVO):
        with open(COMANDO_ARCHIVO, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def guardar_comandos(texto):
    with open(COMANDO_ARCHIVO, "w", encoding="utf-8") as f:
        f.write(texto)


def agregar_comando(comando):
    with open(COMANDO_ARCHIVO, "a", encoding="utf-8") as f:
        f.write(comando.strip() + "\n")


def leer_registro_enviados():
    patron = os.path.join(DIR_BASE, "comando_enviado_*.txt")
    archivos = sorted(glob.glob(patron), reverse=True)[:5]
    lineas = []
    for ruta in archivos:
        with open(ruta, "r", encoding="utf-8") as f:
            lineas.extend(f.readlines()[-20:])
    return lineas[-50:]


@app.route("/")
def index():
    comandos = leer_comandos()
    enviados = leer_registro_enviados()
    dispositivos = listar_dispositivos_chats()
    conexiones = leer_log_conexiones()
    estado_tcp = obtener_estado_tcp()
    return render_template(
        "index.html",
        comandos=comandos,
        enviados=enviados,
        dispositivos=dispositivos,
        conexiones=conexiones,
        estado_tcp=estado_tcp,
        puerto_a=PUERTO_TCP_A,
        puerto_b=PUERTO_TCP_B,
    )


@app.route("/guardar", methods=["POST"])
def guardar():
    texto = request.form.get("comandos", "").replace("\r\n", "\n").replace("\r", "\n")
    guardar_comandos(texto)
    flash("Archivo guardado correctamente.")
    return redirect(url_for("index"))


@app.route("/agregar", methods=["POST"])
def agregar():
    comando = request.form.get("comando", "").strip()
    if comando:
        agregar_comando(comando)
        msg = comando[:50] + "..." if len(comando) > 50 else comando
        flash(f'Comando "{msg}" añadido a la cola.')
    else:
        flash("Escribe un comando antes de enviar.", "warning")
    return redirect(url_for("index"))


@app.route("/tcp/control", methods=["POST"])
def tcp_control():
    accion = request.form.get("accion", "").strip()
    if accion == "detener":
        _, msg = detener_servidor_tcp()
        flash(msg, "success")
    elif accion == f"puerto_{PUERTO_TCP_A}":
        ok, msg = iniciar_servidor_tcp(PUERTO_TCP_A)
        flash(msg, "success" if ok else "warning")
    elif accion == f"puerto_{PUERTO_TCP_B}":
        ok, msg = iniciar_servidor_tcp(PUERTO_TCP_B)
        flash(msg, "success" if ok else "warning")
    else:
        flash("Acción TCP no reconocida.", "warning")
    return redirect(url_for("index"))


if __name__ == "__main__":
    # use_reloader=False evita duplicar el proceso hijo TCP al recargar Flask
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
