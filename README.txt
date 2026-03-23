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
   - Ver los últimos comandos enviados a dispositivos


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
