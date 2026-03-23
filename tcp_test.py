import socket
import threading
import datetime
import time
import os

HOST = '0.0.0.0'
PORT = 9990
COMANDO_ARCHIVO = "comando_test.txt"
REGISTRO_ENVIADOS = "comando_enviado"

# Lista de conexiones activas (conn, addr) para broadcast
conexiones_activas = []
lock_conexiones = threading.Lock()

def guardar_comando_enviado(texto, ip_dispositivo, timestamp):
    """Guarda en archivo: texto enviado, hora e IP del dispositivo."""
    fecha_actual = timestamp.strftime("%d_%m_%Y")
    nombre_archivo = f"{REGISTRO_ENVIADOS}_{fecha_actual}.txt"
    hora = timestamp.strftime("%H:%M:%S")
    linea = f"[{hora}] IP: {ip_dispositivo} | Texto: {texto}\n"

    with open(nombre_archivo, "a", encoding="utf-8") as archivo:
        archivo.write(linea)

def procesar_comandos_cada_5_segundos():
    """Cada 5 segundos lee comando_test.txt, envía primera línea (200 chars) a dispositivos y la elimina."""
    while True:
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
            client_ip = addr[0]
            try:
                conn.sendall(texto_a_enviar.encode('utf-8'))
                guardar_comando_enviado(texto_a_enviar, client_ip, timestamp)
                print(f"📤 [COMANDO ENVIADO a {client_ip}] {texto_a_enviar[:50]}...")
            except (BrokenPipeError, ConnectionResetError, OSError):
                desconectados.append((conn, addr))

        with lock_conexiones:
            for item in desconectados:
                if item in conexiones_activas:
                    conexiones_activas.remove(item)

def guardar_en_archivo(mensaje, timestamp):
    fecha_actual = timestamp.strftime("%d_%m_%Y")
    nombre_archivo = f"1_tcp_datos_{fecha_actual}.txt"
    hora = timestamp.strftime("%H:%M:%S")
    linea = f"[{hora}] {mensaje}\n"

    with open(nombre_archivo, "a", encoding="utf-8") as archivo:
        archivo.write(linea)

def enviar_hora_periodicamente(conn, addr):
    client_ip, client_port = addr
    ultimo_segundo = -1

    while True:
        now = datetime.datetime.now()
        segundos = now.second

        # Enviar cuando el segundo cambia Y es múltiplo de 10
        if segundos != ultimo_segundo and segundos % 10 == 0:
            hora_str = now.strftime("%H:%M:%S")
            msg = f"HORA: {hora_str}"
            try:
                conn.sendall(msg.encode('utf-8'))
                print(f"⏰ [HORA ENVIADA a {client_ip}:{client_port}] {msg}")
            except (BrokenPipeError, ConnectionResetError, OSError):
                print(f"❌ Cliente desconectado ({client_ip}:{client_port}) al enviar hora")
                remover_conexion(conn, addr)
                break

        ultimo_segundo = segundos
        time.sleep(0.2)  # precisión sin sobrecargar CPU


def remover_conexion(conn, addr):
    """Quita una conexión de la lista de activas."""
    with lock_conexiones:
        try:
            conexiones_activas.remove((conn, addr))
        except ValueError:
            pass

def recibir_datos(conn, addr):
    client_ip, client_port = addr

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                print(f"🔌 Cliente desconectado: {client_ip}:{client_port}")
                break

            message = data.decode('utf-8')
            timestamp = datetime.datetime.now()

            print(f"📩 [DATA] {client_ip}:{client_port}: {message}")
            guardar_en_archivo(message, timestamp)

            ack = f"RECIBIDO ({len(message)} bytes)"
            conn.sendall(ack.encode('utf-8'))

    except Exception:
        print(f"⚠️ Error con el cliente {client_ip}:{client_port}")
    finally:
        remover_conexion(conn, addr)
        conn.close()

def handle_client(conn, addr):
    print(f"✅ Nueva conexión: {addr[0]}:{addr[1]}")

    with lock_conexiones:
        conexiones_activas.append((conn, addr))

    # Hilo para recibir datos
    thread_recv = threading.Thread(target=recibir_datos, args=(conn, addr), daemon=True)
    thread_recv.start()

    # Hilo para enviar la hora siempre
    # thread_time = threading.Thread(target=enviar_hora_periodicamente, args=(conn, addr), daemon=True)
    #thread_time.start()

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(20)

    print(f"🚀 Servidor escuchando en {HOST}:{PORT}")

    while True:
        conn, addr = server_socket.accept()
        hilo_cliente = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        hilo_cliente.start()
        print(f"👥 Clientes activos: {threading.active_count() - 1}")

if __name__ == "__main__":
    thread_comandos = threading.Thread(
        target=procesar_comandos_cada_5_segundos,
        daemon=True
    )
    thread_comandos.start()
    print(f"📋 Procesador de comandos iniciado (cada 5 s, archivo: {COMANDO_ARCHIVO})")
    start_server()
