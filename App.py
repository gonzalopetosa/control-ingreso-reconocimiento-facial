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

app = Flask(__name__)
app.secret_key = "supersecretkey"  # necesario para sesiones

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "data")
ROSTROS_DIR = os.path.join(BASE_DIR, "rostros")
os.makedirs(SAVE_DIR, exist_ok=True)

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
        return "❌ No se detectó rostro en la imagen"

    # Buscar en todos los usuarios registrados
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, rostro_path FROM usuarios WHERE rostro_path IS NOT NULL")
    rostros = c.fetchall()
    for username, rostro_filename in rostros:
        path = os.path.join(ROSTROS_DIR, rostro_filename)
        if os.path.exists(path):
            known_image = face_recognition.load_image_file(path)
            known_encodings = face_recognition.face_encodings(known_image)
            if known_encodings and face_recognition.compare_faces([known_encodings[0]], face_encodings[0])[0]:
                session["user"] = username     
                conn.close()
                return redirect(url_for("dashboard")) and f"✅ Bienvenido {username} (login con rostro)"
            
    conn.close()
    return "❌ Rostro no coincide"

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

        if password != confirm_password:
            error = "❌ Las contraseñas no coinciden"
            return render_template("register.html", error=error)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO usuarios (username, password, email) VALUES (?, ?, ?)",
                      (username, password, email))
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
def dashboard():
    username = session.get("user", "Usuario")
    return render_template("dashboard.html", username=username)

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
            rostro_path TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

if __name__ == "__main__":
    app.run(port=int(os.environ.get("FLASK_PORT", 5000)), debug=True)