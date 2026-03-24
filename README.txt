INTERFAZ WEB (recomendado)
==========================
Para gestionar comandos sin usar la terminal:

1. Instalar dependencias:
   pip install -r requirements.txt

2. Iniciar la interfaz web:
   python web_app.py

3. Abrir en el navegador: http://localhost:5000

4. Desde la web puedes:
   - Ver y editar la cola de comandos (comando_test.txt)
   - Añadir comandos rápidos con un solo clic
   - Ver los últimos comandos enviados (general, a todos)
   - Ver registro de conexiones (dispositivos_conexiones.txt)
   - Ver chat por dispositivo (archivos en chats/IP_en_guiones_puerto.txt)
   - Arrancar o detener el servidor TCP y alternar entre puerto 9990 y 9991

Control del servidor TCP desde la web:
   - "Activar 9990" o "Activar 9991": detiene el proceso actual, libera ambos puertos
     (fuser -k, lsof + kill -9) y arranca tcp_test.py en el puerto elegido.
   - "Detener servidor TCP": termina el proceso y vuelve a intentar liberar 9990/9991.
   - Los clientes no cambian de puerto solos: deben reconectar al puerto activo.
     Tras el cambio, revisa dispositivos_conexiones.txt (nuevas líneas CONECTADO).

Arranque manual por terminal (opcional):
   python tcp_test.py --port 9990
   python tcp_test.py --port 9991

El servidor TCP (tcp_test.py) escribe:
   - dispositivos_conexiones.txt: CONECTADO / DESCONECTADO con fecha
   - chats/192_168_1_5_50234.txt (ejemplo): líneas [fecha] dispositivo> o servidor>


COMANDOS UBUNTU PARA ESCRIBIR EN ARCHIVOS
=========================================

Añadir al final del archivo (append):
-------------------------------------
echo "texto a añadir" >> comando_test.txt

Sobrescribir el archivo (reemplaza todo el contenido):
------------------------------------------------------
echo "nuevo contenido" > comando_test.txt

Añadir varias líneas (una por comando):
--------------------------------------
echo "COMANDO_1" >> comando_test.txt
echo "COMANDO_2" >> comando_test.txt

Añadir línea vacía:
------------------
echo "" >> comando_test.txt

Usar tee (muestra en pantalla y escribe al archivo):
---------------------------------------------------
echo "comando de prueba" | tee -a comando_test.txt
  (-a = append, sin -a sobrescribe)

Usar editor de texto:
---------------------
nano comando_test.txt     # editor sencillo en terminal
gedit comando_test.txt    # editor gráfico (si está instalado)

Ejemplo para el proyecto TCP:
-----------------------------
# Añadir un comando a la cola (para que se envíe al dispositivo):
echo "ENVIAR_ALERTA" >> comando_test.txt

# Ver el contenido actual:
cat comando_test.txt

# Vaciar el archivo:
> comando_test.txt
