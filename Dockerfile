# Usa una imagen base de Python 3.10
FROM python:3.10-slim

# Evita problemas de memoria al instalar paquetes
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Instala dependencias del sistema necesarias para dlib y OpenCV
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Crea el directorio de la app
WORKDIR /app

# Copia tu archivo de requerimientos
COPY requirements.txt .

# Instala todas las dependencias de Python
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el código de tu proyecto
COPY . .

# Expone el puerto que usará Flask
EXPOSE 5000

# Comando para correr la app
CMD ["gunicorn", "App:app", "--bind", "0.0.0.0:5000", "--workers", "2"]
