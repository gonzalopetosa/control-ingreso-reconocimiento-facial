from flask import Flask, render_template, request, jsonify, Response, session
import os
import cv2
import numpy as np
import base64
import re
from datetime import datetime
import face_recognition
import sqlite3
from flask import redirect, url_for
from decorators import facial_auth_required, role_required
from visualizacion import visualizacion_bp
import csv


app = Flask(__name__)
app.secret_key = "supersecretkey"  # necesario para sesiones

# Registrar el blueprint en una ruta base (ej: "/dashboard")
app.register_blueprint(visualizacion_bp, url_prefix="/visualizacion")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "data")
ROSTROS_DIR = os.path.join(BASE_DIR, "rostros")
os.makedirs(SAVE_DIR, exist_ok=True)


DB_PATH = os.path.join(BASE_DIR, "data", "usuarios.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT NOT NULL,
        rostro_path TEXT,
        role TEXT NOT NULL DEFAULT 'operador'
    )
""")
    conn.commit()
    conn.close()

init_db()

# ====== RUTA PRINCIPAL ======
@app.route("/")
def index():
    return render_template("login.html")

# ====== LOGIN NORMAL (usuario/contraseña) ======
@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    error = None

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()

    if user:
        session["user"] = username
        return redirect(url_for("dashboard"))
    else:
        error = "❌ Usuario o contraseña incorrectos"
        return render_template("login.html", error=error)

# ====== LOGIN CON RECONOCIMIENTO FACIAL ======
@app.route("/login_face", methods=["POST"])
def login_face():
    data = request.get_json()
    image_data = re.sub('^data:image/.+;base64,', '', data['image'])
    image_bytes = base64.b64decode(image_data)

    # Convertir a imagen OpenCV
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Buscar rostros en la imagen recibida
    face_encodings = face_recognition.face_encodings(frame)
    if not face_encodings:
        return jsonify({
            "success": False,
            "message": "❌ No se detectó rostro en la imagen"
        })

    # Buscar en todos los usuarios registrados
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, rostro_path, role FROM usuarios WHERE rostro_path IS NOT NULL")
    rostros = c.fetchall()
    conn.close()

    print("DEBUG -> filas recibidas de la DB:", rostros)  # 👈 para depuración

    usuario_identificado = None
    rol_identificado = None

    # 👇 recorremos correctamente las 3 columnas
    for username, rostro_filename, role in rostros:
        path = os.path.join(ROSTROS_DIR, rostro_filename)
        if os.path.exists(path):
            known_image = face_recognition.load_image_file(path)
            known_encodings = face_recognition.face_encodings(known_image)
            if known_encodings and face_recognition.compare_faces([known_encodings[0]], face_encodings[0])[0]:
                usuario_identificado = username
                rol_identificado = role
                break

    if usuario_identificado:
        session["user"] = usuario_identificado
        session["role"] = rol_identificado   # ✅ ahora guarda el rol
        session["authenticated"] = True
        registrar_ingreso_automatico(usuario_identificado)

        return jsonify({
            "success": True,
            "message": f"✅ Bienvenido {usuario_identificado}",
            "username": usuario_identificado,
            "role": rol_identificado
        })

    return jsonify({
        "success": False,
        "message": "❌ Rostro no coincide con ningún usuario registrado"
    })

# Función para registrar ingreso automático
def registrar_ingreso_automatico(username):
    ahora = datetime.now()
    fecha_actual = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")

    # Obtener información del usuario desde la base de datos
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username FROM usuarios WHERE username = ?", (username,))
    usuario = c.fetchone()
    conn.close()

    if usuario:
        user_id, username = usuario

        # Leer el archivo CSV existente
        csv_path = os.path.join(SAVE_DIR, "ingresos_egresos.csv")
        registros = []
        fieldnames = ['id_registro', 'id_empleado', 'nombre', 'apellido',
                     'fecha', 'hora_ingreso', 'hora_egreso', 'area']

        # Verificar si el archivo existe y leerlo
        file_exists = os.path.exists(csv_path)

        if file_exists:
            try:
                with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    # Verificar que el archivo tenga el formato correcto
                    if reader.fieldnames == fieldnames:
                        registros = list(reader)
                    else:
                        # Si el formato no coincide, empezar desde cero
                        registros = []
            except Exception as e:
                print(f"❌ Error leyendo el archivo CSV: {e}")
                registros = []

        # Verificar si ya existe un registro de ingreso hoy sin egreso
        tiene_ingreso_sin_egreso = False
        for registro in registros:
            if (registro.get('nombre') == username and
                registro.get('fecha') == fecha_actual and
                registro.get('hora_ingreso', '') != '' and
                registro.get('hora_egreso', '') == ''):
                tiene_ingreso_sin_egreso = True
                break

        if not tiene_ingreso_sin_egreso:
            # Crear nuevo registro
            nuevo_id = len(registros) + 1 if registros else 1

            nuevo_registro = {
                'id_registro': str(nuevo_id),
                'id_empleado': str(user_id),
                'nombre': username,
                'apellido': '',
                'fecha': fecha_actual,
                'hora_ingreso': hora_actual,
                'hora_egreso': '',
                'area': 'Sistema'
            }

            registros.append(nuevo_registro)

            # Escribir todos los registros al CSV
            try:
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(registros)

                print(f"✅ Ingreso registrado automáticamente para {username} a las {hora_actual}")
                return True
            except Exception as e:
                print(f"❌ Error escribiendo en el archivo CSV: {e}")
                return False
        else:
            print(f"ℹ️ {username} ya tiene un ingreso registrado hoy sin egreso")
            return False
    else:
        print(f"❌ Usuario {username} no encontrado en la base de datos")
        return False

# Agregar esta función para registrar egreso
def registrar_egreso_automatico(username):
    ahora = datetime.now()
    fecha_actual = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")

    # Leer el archivo CSV
    csv_path = os.path.join(SAVE_DIR, "ingresos_egresos.csv")
    fieldnames = ['id_registro', 'id_empleado', 'nombre', 'apellido',
                 'fecha', 'hora_ingreso', 'hora_egreso', 'area']

    if not os.path.exists(csv_path):
        print("❌ No hay registros de ingreso para registrar egreso")
        return False

    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            # Verificar que el archivo tenga el formato correcto
            if reader.fieldnames != fieldnames:
                print("❌ Formato incorrecto del archivo CSV")
                return False
            registros = list(reader)
    except Exception as e:
        print(f"❌ Error leyendo el archivo CSV: {e}")
        return False

    # Buscar el último registro del usuario para hoy sin egreso
    registro_actualizado = False
    for registro in registros:
        if (registro.get('nombre') == username and
            registro.get('fecha') == fecha_actual and
            registro.get('hora_ingreso', '') != '' and
            registro.get('hora_egreso', '') == ''):

            registro['hora_egreso'] = hora_actual
            registro_actualizado = True
            break

    if registro_actualizado:
        # Escribir los registros actualizados
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(registros)

            print(f"✅ Egreso registrado automáticamente para {username} a las {hora_actual}")
            return True
        except Exception as e:
            print(f"❌ Error escribiendo en el archivo CSV: {e}")
            return False
    else:
        print(f"⚠️ No se encontró ingreso pendiente de egreso para {username}")
        return False

# Modificar la ruta de logout
@app.route("/logout")
def logout():
    if "user" in session:
        username = session["user"]
        # Registrar egreso automáticamente
        egreso_registrado = registrar_egreso_automatico(username)

        if egreso_registrado:
            mensaje = "✅ Egreso registrado correctamente. Sesión cerrada."
        else:
            mensaje = "ℹ️ Sesión cerrada (sin registro de egreso)"
    else:
        mensaje = "ℹ️ Sesión cerrada"

    # Limpiar sesión
    session.pop("user", None)
    session.pop("authenticated", None)

    # Redirigir al login con mensaje
    return redirect(url_for("index", mensaje=mensaje))

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    success = None
    require_face = False
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        email = request.form["email"]
        role = request.form.get("role", "operador")  # 👈 por defecto operador

        if password != confirm_password:
            error = "❌ Las contraseñas no coinciden"
            return render_template("register.html", error=error)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO usuarios (username, password, email, role) VALUES (?, ?, ?, ?)",
                      (username, password, email, role))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            error = "❌ El usuario ya existe"
            return render_template("register.html", error=error)
        conn.close()
        # Guardar el usuario en sesión temporal para el registro facial
        session["user"] = username
        require_face = True
        return render_template("register.html", require_face=require_face, success="Usuario preliminarmente registrado. Por favor, registra tu rostro para finalizar.")
    return render_template("register.html")

@app.route("/register_face", methods=["POST"])
def register_face():
    data = request.get_json()
    image_data = re.sub('^data:image/.+;base64,', '', data['image'])
    image_bytes = base64.b64decode(image_data)

    username = session.get("user", None)
    if not username:
        return jsonify({"error": "No se pudo registrar el rostro del usuario"}), 400

    # Convertir a imagen OpenCV
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Obtener encoding del rostro capturado
    new_encodings = face_recognition.face_encodings(frame)
    if not new_encodings:
        return jsonify({"error": "No se detectó rostro en la imagen"}), 400
    new_encoding = new_encodings[0]

    # Buscar si el rostro ya está registrado
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, rostro_path FROM usuarios WHERE rostro_path IS NOT NULL")
    rostros = c.fetchall()
    for user, path in rostros:
        if os.path.exists(path):
            known_image = face_recognition.load_image_file(path)
            known_encodings = face_recognition.face_encodings(known_image)
            if known_encodings and face_recognition.compare_faces([known_encodings[0]], new_encoding)[0]:
                # Eliminar usuario temporal
                c2 = sqlite3.connect(DB_PATH)
                c2.execute("DELETE FROM usuarios WHERE username=?", (username,))
                c2.commit()
                c2.close()
                session.pop("user", None)
                conn.close()
                return jsonify({"error": "❌ No se pudo registrar el usuario porque el rostro ya está registrado"}), 400

    # Guardar imagen en disco
    rostro_filename = f"{username}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    rostro_path = os.path.join(ROSTROS_DIR, rostro_filename)
    with open(rostro_path, "wb") as f:
        f.write(image_bytes)

    # Guarda solo el nombre en la base de datos
    c.execute("UPDATE usuarios SET rostro_path=? WHERE username=?", (rostro_filename, username))
    conn.commit()
    conn.close()

    return jsonify({
        "success": "✅ Te registraste correctamente.",
        "show_login": True
    })

@app.route("/register_face_reject", methods=["POST"])
def register_face_reject():
    error = "❌ No se pudo registrar el rostro del usuario"
    # Elimina el usuario temporal si lo deseas
    username = session.get("user", None)
    if username:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM usuarios WHERE username=?", (username,))
        conn.commit()
        conn.close()
        session.pop("user", None)
    return render_template("register.html", error=error)

@app.route("/dashboard")
@facial_auth_required
def dashboard():
    username = session.get("user", "Usuario")
    return render_template("dashboard.html", username=username)


if __name__ == "__main__":
     app.run(port=int(os.environ.get("FLASK_PORT", 5000)))