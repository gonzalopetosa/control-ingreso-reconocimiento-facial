from flask import request, Flask, jsonify, render_template, session, redirect, url_for, Response
import os
from flask_cors import CORS
from dotenv import load_dotenv
import cv2
from datetime import datetime
import numpy as np
import pickle
import json
import insightface
from insightface.app import FaceAnalysis

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "data")
EMPLOYEES_DIR = os.path.join(BASE_DIR, "EMPLEADOS")
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(EMPLOYEES_DIR, exist_ok=True)

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Inicializar InsightFace
app_face = FaceAnalysis(name='buffalo_l')
app_face.prepare(ctx_id=0, det_size=(640, 640))

# Base de datos de empleados
EMPLOYEES_DB = {
    "empleado_001": {
        "id": "empleado_001",
        "nombre": "Gonzalo Petosa",
        "puesto": "Operario de Producción",
        "foto_path": os.path.join(EMPLOYEES_DIR, "petosa.jpg"),
        "embedding": None
    }
}

# Cargar embeddings de empleados
def load_employee_embeddings():
    """Cargar embeddings de empleados"""
    embeddings_file = os.path.join(EMPLOYEES_DIR, "embeddings.pkl")
    if os.path.exists(embeddings_file):
        with open(embeddings_file, 'rb') as f:
            return pickle.load(f)
    return {}

def save_employee_embeddings(embeddings_dict):
    """Guardar embeddings de empleados"""
    embeddings_file = os.path.join(EMPLOYEES_DIR, "embeddings.pkl")
    with open(embeddings_file, 'wb') as f:
        pickle.dump(embeddings_dict, f)

employee_embeddings = load_employee_embeddings()

def register_employee_face(employee_id, image_path):
    """Registrar el rostro de un empleado"""
    try:
        if not os.path.exists(image_path):
            return False

        img = cv2.imread(image_path)
        if img is None:
            return False

        faces = app_face.get(img)
        if len(faces) > 0:
            employee_embeddings[employee_id] = faces[0].embedding
            save_employee_embeddings(employee_embeddings)
            return True
        return False
    except Exception as e:
        print(f"Error registrando empleado: {e}")
        return False

def recognize_face(frame):
    """Reconocer un rostro en el frame"""
    try:
        faces = app_face.get(frame)
        recognized_employees = []

        for face in faces:
            for emp_id, emp_embedding in employee_embeddings.items():
                # Calcular similitud coseno
                similarity = np.dot(face.embedding, emp_embedding) / (
                    np.linalg.norm(face.embedding) * np.linalg.norm(emp_embedding)
                )

                if similarity > 0.6:  # Umbral de similitud
                    employee = EMPLOYEES_DB.get(emp_id, {})
                    recognized_employees.append({
                        "employee": employee,
                        "similarity": float(similarity),
                        "confidence": float(similarity * 100)
                    })

        return recognized_employees
    except Exception as e:
        print(f"Error en reconocimiento facial: {e}")
        return []

@app.route('/')
def index():
    return render_template('capturar_imagen.html')

@app.route('/admin')
def admin():
    """Panel de administración"""
    return render_template('admin.html', employees=EMPLOYEES_DB)

@app.route('/register_employee', methods=['POST'])
def register_employee():
    """Registrar nuevo empleado"""
    try:
        employee_id = request.form.get('employee_id')
        if not employee_id or employee_id not in EMPLOYEES_DB:
            return jsonify({"error": "ID de empleado inválido"}), 400

        # Capturar imagen
        cap = cv2.VideoCapture(0)
        best_frame = None
        for _ in range(10):
            ret, frame = cap.read()
            if ret:
                best_frame = frame.copy()
        cap.release()

        if best_frame is None:
            return jsonify({"error": "No se pudo capturar la imagen"}), 500

        # Guardar imagen temporal
        temp_path = os.path.join(EMPLOYEES_DIR, f"temp_{employee_id}.jpg")
        cv2.imwrite(temp_path, best_frame)

        # Registrar rostro
        success = register_employee_face(employee_id, temp_path)

        # Limpiar
        if os.path.exists(temp_path):
            os.remove(temp_path)

        if success:
            return jsonify({
                "success": True,
                "message": f"Empleado {EMPLOYEES_DB[employee_id]['nombre']} registrado"
            })
        else:
            return jsonify({"error": "No se detectó un rostro claro"}), 400

    except Exception as e:
        return jsonify({"error": f"Error en registro: {str(e)}"}), 500

@app.route("/capture_face", methods=["GET"])
def capture_face():
    """Capturar y verificar identidad"""
    try:
        cap = cv2.VideoCapture(0)
        best_frame = None
        for _ in range(15):
            ret, frame = cap.read()
            if ret:
                best_frame = frame.copy()
        cap.release()

        if best_frame is None:
            return jsonify({"error": "No se pudo capturar imagen"}), 500

        frame = cv2.resize(best_frame, (640, 480))

        # Detectar rostros
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces_haar = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )

        # Reconocer empleados
        recognized_employees = recognize_face(frame)

        # Dibujar resultados
        for (x, y, w, h) in faces_haar:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        for i, recognition in enumerate(recognized_employees):
            emp = recognition["employee"]
            confidence = recognition["confidence"]
            text = f"{emp['nombre']} ({confidence:.1f}%)"
            cv2.putText(frame, text, (10, 30 + i*30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Guardar imagen
        if len(faces_haar) > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(SAVE_DIR, f"face_{timestamp}.jpg")
            cv2.imwrite(filename, frame)

        # Preparar respuesta
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            return jsonify({"error": "Error procesando imagen"}), 500

        response_data = {
            "recognized": len(recognized_employees) > 0,
            "employees": [
                {
                    "id": rec["employee"]["id"],
                    "nombre": rec["employee"]["nombre"],
                    "puesto": rec["employee"]["puesto"],
                    "confidence": rec["confidence"]
                } for rec in recognized_employees
            ]
        }

        # Guardar log
        log_file = os.path.join(SAVE_DIR, "access_log.json")
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "access_granted" if recognized_employees else "access_denied",
            "employees": response_data["employees"]
        }

        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        return Response(buffer.tobytes(), mimetype='image/jpeg')

    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"}), 500

@app.route("/verify_identity", methods=["POST"])
def verify_identity():
    """Verificación de identidad"""
    try:
        cap = cv2.VideoCapture(0)
        best_frame = None
        for _ in range(10):
            ret, frame = cap.read()
            if ret:
                best_frame = frame.copy()
        cap.release()

        if best_frame is None:
            return jsonify({"error": "No se pudo capturar imagen"}), 400

        frame = cv2.resize(best_frame, (640, 480))
        recognized_employees = recognize_face(frame)

        if recognized_employees:
            recognized_employees.sort(key=lambda x: x['confidence'], reverse=True)
            best_match = recognized_employees[0]

            return jsonify({
                "success": True,
                "employee": {
                    "id": best_match["employee"]["id"],
                    "nombre": best_match["employee"]["nombre"],
                    "puesto": best_match["employee"]["puesto"]
                },
                "confidence": best_match["confidence"]
            })
        else:
            return jsonify({
                "success": False,
                "message": "No se reconoció a ningún empleado"
            }), 401

    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"}), 500

@app.route("/access_logs", methods=["GET"])
def get_access_logs():
    """Obtener logs de acceso"""
    try:
        log_file = os.path.join(SAVE_DIR, "access_log.json")
        logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line.strip()))
        return jsonify({"logs": logs[-50:]})
    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    # Registrar empleados automáticamente si tienen fotos
    for emp_id, emp_data in EMPLOYEES_DB.items():
        if os.path.exists(emp_data["foto_path"]):
            register_employee_face(emp_id, emp_data["foto_path"])

    app.run(port=int(os.environ.get("FLASK_PORT", 5000)))