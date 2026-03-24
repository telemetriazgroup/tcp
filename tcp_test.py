import argparse
import signal
import socket
import threading
import datetime
import time
import os
import sys

HOST = "0.0.0.0"

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
COMANDO_ARCHIVO = os.path.join(DIR_BASE, "comando_test.txt")
REGISTRO_ENVIADOS = os.path.join(DIR_BASE, "comando_enviado")
CHAT_DIR = os.path.join(DIR_BASE, "chats")
CONEXIONES_LOG = os.path.join(DIR_BASE, "dispositivos_conexiones.txt")

# Lista de conexiones activas (conn, addr) para broadcast
conexiones_activas = []
lock_conexiones = threading.Lock()
lock_archivos_chat = threading.Lock()

shutdown_event = threading.Event()
server_socket_global = None
server_socket_lock = threading.Lock()


def ruta_chat_dispositivo(ip: str, port: int) -> str:
    """Archivo de chat por dispositivo: chats/IP_con_puntos_sustituidos_por_guiones_puerto.txt"""
    ip_safe = ip.replace(".", "_")
    os.makedirs(CHAT_DIR, exist_ok=True)
    return os.path.join(CHAT_DIR, f"{ip_safe}_{port}.txt")


def registrar_conexion_evento(ip: str, port: int, evento: str):
    """Guarda en dispositivos_conexiones.txt: CONECTADO / DESCONECTADO."""
    ts = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linea = f"[{ts}] {evento} {ip}:{port}\n"
    with lock_archivos_chat:
        with open(CONEXIONES_LOG, "a", encoding="utf-8") as f:
            f.write(linea)


def guardar_linea_chat(ip: str, port: int, origen: str, texto: str):
    """
    origen: 'dispositivo' (respuesta del cliente) o 'servidor' (comando u hora enviada).
    Formato legible para la interfaz tipo chat.
    """
    ts = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    texto_limpio = texto.replace("\r", " ").replace("\n", " ").strip()
    linea = f"[{ts}] {origen}> {texto_limpio}\n"
    ruta = ruta_chat_dispositivo(ip, port)
    with lock_archivos_chat:
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(linea)


def guardar_comando_enviado(texto, ip_dispositivo, puerto, timestamp):
    """Guarda en archivo global: texto enviado, hora, IP y puerto."""
    fecha_actual = timestamp.strftime("%d_%m_%Y")
    nombre_archivo = os.path.join(DIR_BASE, f"{os.path.basename(REGISTRO_ENVIADOS)}_{fecha_actual}.txt")
    hora = timestamp.strftime("%H:%M:%S")
    linea = f"[{hora}] IP: {ip_dispositivo}:{puerto} | Texto: {texto}\n"

    with open(nombre_archivo, "a", encoding="utf-8") as archivo:
        archivo.write(linea)


def procesar_comandos_cada_5_segundos():
    """Lee comando_test.txt y envía primera línea (200 chars) a dispositivos."""
    while not shutdown_event.is_set():
        time.sleep(1)

        if not os.path.exists(COMANDO_ARCHIVO):
            continue

        try:
            with open(COMANDO_ARCHIVO, "r", encoding="utf-8") as f:
                lineas = f.readlines()
        except (IOError, OSError):
            continue

        if not lineas:
            continue

        primera_linea = lineas[0].strip()
        if not primera_linea:
            lineas.pop(0)
            with open(COMANDO_ARCHIVO, "w", encoding="utf-8") as f:
                f.writelines(lineas)
            continue

        texto_a_enviar = primera_linea[:200]
        lineas_restantes = lineas[1:]

        with open(COMANDO_ARCHIVO, "w", encoding="utf-8") as f:
            f.writelines(lineas_restantes)

        with lock_conexiones:
            conexiones = list(conexiones_activas)

        if not conexiones:
            continue

        timestamp = datetime.datetime.now()
        desconectados = []

        for conn, addr in conexiones:
            client_ip, client_port = addr[0], addr[1]
            try:
                conn.sendall(texto_a_enviar.encode("utf-8"))
                guardar_comando_enviado(texto_a_enviar, client_ip, client_port, timestamp)
                guardar_linea_chat(client_ip, client_port, "servidor", texto_a_enviar)
                print(f"📤 [COMANDO ENVIADO a {client_ip}:{client_port}] {texto_a_enviar[:50]}...")
            except (BrokenPipeError, ConnectionResetError, OSError):
                desconectados.append((conn, addr))

        with lock_conexiones:
            for item in desconectados:
                if item in conexiones_activas:
                    conexiones_activas.remove(item)


def guardar_en_archivo(mensaje, timestamp):
    fecha_actual = timestamp.strftime("%d_%m_%Y")
    nombre_archivo = os.path.join(DIR_BASE, f"1_tcp_datos_{fecha_actual}.txt")
    hora = timestamp.strftime("%H:%M:%S")
    linea = f"[{hora}] {mensaje}\n"

    with open(nombre_archivo, "a", encoding="utf-8") as archivo:
        archivo.write(linea)


def enviar_hora_periodicamente(conn, addr):
    client_ip, client_port = addr
    ultimo_segundo = -1

    while not shutdown_event.is_set():
        now = datetime.datetime.now()
        segundos = now.second

        if segundos != ultimo_segundo and segundos % 10 == 0:
            hora_str = now.strftime("%H:%M:%S")
            msg = f"HORA: {hora_str}"
            try:
                conn.sendall(msg.encode("utf-8"))
                print(f"⏰ [HORA ENVIADA a {client_ip}:{client_port}] {msg}")
            except (BrokenPipeError, ConnectionResetError, OSError):
                print(f"❌ Cliente desconectado ({client_ip}:{client_port}) al enviar hora")
                remover_conexion(conn, addr)
                break

        ultimo_segundo = segundos
        time.sleep(0.2)


def remover_conexion(conn, addr):
    with lock_conexiones:
        try:
            conexiones_activas.remove((conn, addr))
        except ValueError:
            pass


def recibir_datos(conn, addr):
    client_ip, client_port = addr
    conn.settimeout(1.0)

    try:
        while not shutdown_event.is_set():
            try:
                data = conn.recv(1024)
            except socket.timeout:
                continue
            if not data:
                print(f"🔌 Cliente desconectado: {client_ip}:{client_port}")
                break

            message = data.decode("utf-8")
            timestamp = datetime.datetime.now()

            print(f"📩 [DATA] {client_ip}:{client_port}: {message}")
            guardar_en_archivo(message, timestamp)
            guardar_linea_chat(client_ip, client_port, "dispositivo", message)

            ack = f"RECIBIDO ({len(message)} bytes)"
            conn.sendall(ack.encode("utf-8"))

    except Exception:
        print(f"⚠️ Error con el cliente {client_ip}:{client_port}")
    finally:
        registrar_conexion_evento(client_ip, client_port, "DESCONECTADO")
        remover_conexion(conn, addr)
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()


def handle_client(conn, addr):
    ip, puerto = addr[0], addr[1]
    print(f"✅ Nueva conexión: {ip}:{puerto}")
    registrar_conexion_evento(ip, puerto, "CONECTADO")
    ruta = ruta_chat_dispositivo(ip, puerto)
    with lock_archivos_chat:
        if not os.path.exists(ruta):
            open(ruta, "a", encoding="utf-8").close()

    with lock_conexiones:
        conexiones_activas.append((conn, addr))

    thread_recv = threading.Thread(target=recibir_datos, args=(conn, addr), daemon=True)
    thread_recv.start()


def _cerrar_socket_servidor():
    global server_socket_global
    with server_socket_lock:
        s = server_socket_global
        server_socket_global = None
    if s is not None:
        try:
            s.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            s.close()
        except OSError:
            pass


def request_shutdown(signum=None, frame=None):
    shutdown_event.set()
    _cerrar_socket_servidor()


def start_server(port: int):
    global server_socket_global

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    srv.bind((HOST, port))
    srv.listen(20)
    srv.settimeout(1.0)

    with server_socket_lock:
        server_socket_global = srv

    print(f"🚀 Servidor escuchando en {HOST}:{port} (SO_REUSEADDR activo)")

    while not shutdown_event.is_set():
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        if shutdown_event.is_set():
            try:
                conn.close()
            except OSError:
                pass
            break

        hilo_cliente = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        hilo_cliente.start()
        print(f"👥 Clientes activos: {threading.active_count() - 1}")

    try:
        srv.close()
    except OSError:
        pass
    print(f"🛑 Servidor en puerto {port} detenido.")


def main():
    parser = argparse.ArgumentParser(description="Servidor TCP para comandos y chat.")
    parser.add_argument("--port", "-p", type=int, default=9990, help="Puerto de escucha (default 9990)")
    args = parser.parse_args()

    os.makedirs(CHAT_DIR, exist_ok=True)
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    thread_comandos = threading.Thread(target=procesar_comandos_cada_5_segundos, daemon=True)
    thread_comandos.start()
    print(f"📋 Procesador de comandos (archivo: {COMANDO_ARCHIVO})")
    print(f"💬 Chats por dispositivo en: {CHAT_DIR}")

    try:
        start_server(args.port)
    finally:
        shutdown_event.set()
        _cerrar_socket_servidor()

    return 0


if __name__ == "__main__":
    sys.exit(main())
