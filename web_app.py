"""
Interfaz web para gestionar comando_test.txt y enviar comandos al servidor TCP.
"""
import os
import glob
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.urandom(24)

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
COMANDO_ARCHIVO = os.path.join(DIR_BASE, "comando_test.txt")
REGISTRO_ENVIADOS = os.path.join(DIR_BASE, "comando_enviado")


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
    """Lee los archivos comando_enviado_*.txt más recientes."""
    patron = os.path.join(DIR_BASE, "comando_enviado_*.txt")
    archivos = sorted(glob.glob(patron), reverse=True)[:5]
    lineas = []
    for ruta in archivos:
        with open(ruta, "r", encoding="utf-8") as f:
            lineas.extend(f.readlines()[-20:])  # últimas 20 por archivo
    return lineas[-50:]  # últimas 50 líneas total


@app.route("/")
def index():
    comandos = leer_comandos()
    enviados = leer_registro_enviados()
    return render_template("index.html", comandos=comandos, enviados=enviados)


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
