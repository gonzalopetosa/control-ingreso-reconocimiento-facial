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
import json

app = Flask(__name__)
app.secret_key = "supersecretkey"  # necesario para sesiones

# Registrar el blueprint en una ruta base (ej: "/dashboard")
app.register_blueprint(visualizacion_bp, url_prefix="/visualizacion")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "Data")
ROSTROS_DIR = os.path.join(BASE_DIR, "rostros")
os.makedirs(SAVE_DIR, exist_ok=True)


DB_PATH = os.path.join(BASE_DIR, "Data", "usuarios.db")

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
        role TEXT NOT NULL DEFAULT 'operador',
        encoding TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_empleado INTEGER,
        username TEXT NOT NULL,
        fecha TEXT NOT NULL,
        hora_ingreso TEXT,
        hora_egreso TEXT,
        area TEXT,
        FOREIGN KEY (id_empleado) REFERENCES usuarios(id)
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

    # Si hay un rostro detectado, debe coincidir con este usuario
    pending_user = session.get("pending_face_user")
    if pending_user and username != pending_user:
        error = "❌ El usuario no coincide con el rostro detectado"
        return render_template("login.html", error=error)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()

    if user:
        session["user"] = username
        session["role"] = user[5]

        # Registrar ingreso automático
        registrar_ingreso_automatico(username)

        # Si venía de login facial...
        if session.get("pending_face_user"):
            session["authenticated"] = True
            session.pop("pending_face_user", None)

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

    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    face_encodings = face_recognition.face_encodings(frame)
    if not face_encodings:
        return jsonify({"success": False, "message": "❌ No se detectó rostro en la imagen"})
    input_encoding = face_encodings[0]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, encoding, role FROM usuarios WHERE encoding IS NOT NULL")
    rostros = c.fetchall()
    conn.close()

    usuario_identificado = None

    for username, encoding_json, role in rostros:
        if encoding_json:
            known_encoding = np.array(json.loads(encoding_json))
            match = face_recognition.compare_faces([known_encoding], input_encoding, tolerance=0.6)
            if match[0]:
                usuario_identificado = username
                break

    if usuario_identificado:
        session["pending_face_user"] = usuario_identificado
        return jsonify({
            "success": True,
            "message": f"✅ Rostro identificado. Por favor, ingrese su usuario y contraseña.",
            "username": usuario_identificado
        })

    return jsonify({"success": False, "message": "❌ Rostro no coincide con ningún usuario registrado"})

# Función para registrar ingreso automático
def registrar_ingreso_automatico(username):
    ahora = datetime.now()
    fecha_actual = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Buscar usuario
    c.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
    usuario = c.fetchone()
    if not usuario:
        conn.close()
        print(f"❌ Usuario {username} no encontrado en la base de datos")
        return False

    user_id = usuario[0]

    # Verificar si ya existe un ingreso sin egreso hoy
    c.execute("""
        SELECT id FROM registros
        WHERE id_empleado=? AND fecha=? AND hora_ingreso IS NOT NULL 
        AND (hora_egreso IS NULL OR hora_egreso='')
    """, (user_id, fecha_actual))
    existe = c.fetchone()

    if existe:
        conn.close()
        print(f"ℹ️ {username} ya tiene un ingreso registrado hoy sin egreso")
        return False

    # Insertar nuevo ingreso
    c.execute("""
        INSERT INTO registros (id_empleado, username, fecha, hora_ingreso, area)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, fecha_actual, hora_actual, "Sistema"))
    conn.commit()
    conn.close()

    print(f"✅ Ingreso registrado automáticamente para {username} a las {hora_actual}")
    return True

# Agregar esta función para registrar egreso
def registrar_egreso_automatico(username):
    ahora = datetime.now()
    fecha_actual = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Buscar el último ingreso del día sin egreso
    print(f"🔍 Buscando ingreso sin egreso para {username} en {fecha_actual}")
    c.execute("""
        SELECT id FROM registros
        WHERE username=? AND fecha=? AND hora_ingreso IS NOT NULL 
        AND (hora_egreso IS NULL OR hora_egreso='')
        ORDER BY id DESC LIMIT 1
    """, (username, fecha_actual))
    registro = c.fetchone()
    print(f"Resultado de búsqueda: {registro}")

    if not registro:
        conn.close()
        print(f"⚠️ No se encontró ingreso pendiente de egreso para {username}")
        return False

    # Actualizar con hora de egreso
    c.execute("UPDATE registros SET hora_egreso=? WHERE id=?", (hora_actual, registro[0]))
    conn.commit()
    conn.close()

    print(f"✅ Egreso registrado automáticamente para {username} a las {hora_actual}")
    return True

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

    # Guardar encoding como JSON en DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE usuarios SET encoding=? WHERE username=?", (json.dumps(new_encoding.tolist()), username))
    conn.commit()
    conn.close()

    return jsonify({
    "success": "✅ Te registraste correctamente.",
    "redirect": url_for("index")  # index() ya renderiza login.html
})

@app.route("/register_face_reject", methods=["POST"])
def register_face_reject():
    username = session.get("user", None)
    if username:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM usuarios WHERE username=?", (username,))
        conn.commit()
        conn.close()
        session.pop("user", None)
    return render_template("register.html", rejected=True)

@app.route("/dashboard")
@facial_auth_required
def dashboard():
    username = session.get("user", "Usuario")
    role = session.get("role", "operador")  # valor por defecto

    if role == "ADMIN":
        return render_template("dashboard_admin.html", username=username)
    else:
        return render_template("dashboard_operador.html", username=username)



if __name__ == "__main__":
     app.run(port=int(os.environ.get("FLASK_PORT", 5000)))