"""
Interfaz web para gestionar comando_test.txt, comandos enviados y chat por dispositivo.
"""
import os
import re
import glob
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.urandom(24)

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
COMANDO_ARCHIVO = os.path.join(DIR_BASE, "comando_test.txt")
REGISTRO_ENVIADOS = os.path.join(DIR_BASE, "comando_enviado")
CHAT_DIR = os.path.join(DIR_BASE, "chats")
CONEXIONES_LOG = os.path.join(DIR_BASE, "dispositivos_conexiones.txt")

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
    return render_template(
        "index.html",
        comandos=comandos,
        enviados=enviados,
        dispositivos=dispositivos,
        conexiones=conexiones,
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
