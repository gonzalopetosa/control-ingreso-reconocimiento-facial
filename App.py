from flask import request, Flask, jsonify, render_template, session, redirect, url_for, Response
import os
from flask_cors import CORS
from dotenv import load_dotenv
import cv2
from datetime import datetime

app = Flask(__name__)

SAVE_DIR = r"C:\Users\gonza\Desktop\TP-Inicial\Data"
os.makedirs(SAVE_DIR, exist_ok=True)

# Cargar el clasificador HaarCascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

@app.route("/capture_face", methods=["GET"])
def capture_face():
    # Abrir la cámara (0 = cámara por defecto)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return jsonify({"error": "No se pudo abrir la cámara"}), 500

    # Capturar varios frames para asegurar enfoque
    for _ in range(15):
        ret, frame = cap.read()
    cap.release()

    if not ret:
        return jsonify({"error": "No se pudo capturar la imagen"}), 500

    # Redimensionar para mejorar detección
    frame = cv2.resize(frame, (640, 480))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detectar rostros
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=3,
        minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE
    )

    # Dibujar rectángulos sobre los rostros
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    if len(faces) > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(SAVE_DIR, f"face_{timestamp}.jpg")
        cv2.imwrite(filename, frame)

    # Codificar imagen a JPEG para devolverla
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return jsonify({"error": "No se pudo procesar la imagen"}), 500

    # Responder con la imagen
    return Response(buffer.tobytes(), mimetype='image/jpeg')

if __name__== '__main__':
    app.run(port=int(os.environ.get("FLASK_PORT", 5000)))