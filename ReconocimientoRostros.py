import cv2

# Cargar el clasificador pre-entrenado de rostros (Haar Cascade)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml") #permite detectar rostros sin nesecidad de entrenar un modelo.

# Iniciar la cámara
cap = cv2.VideoCapture(0)

while True:
    # Capturar frame por frame
    ret, frame = cap.read()
    if not ret:
        break

    # Convertir a escala de grises (mejora la detección)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detectar rostros
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    # Dibujar rectángulos alrededor de los rostros detectados
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # Mostrar el video en una ventana
    cv2.imshow("Detección de Rostros - OpenCV", frame)

    # Presionar 'q' para salir
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Liberar cámara y cerrar ventanas
cap.release()
cv2.destroyAllWindows()

