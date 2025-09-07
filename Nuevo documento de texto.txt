FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependencias necesarias
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gfortran \
    git \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip

# ✅ Instalar wheel precompilado de dlib para Python 3.11 + Linux
RUN pip install --no-cache-dir \
    https://github.com/alvinregin/dlib-wheels/releases/download/v20.0.0/dlib-20.0.0-cp311-cp311-linux_x86_64.whl

# Instalar face_recognition_models y el resto de requirements
RUN pip install --no-cache-dir \
    git+https://github.com/ageitgey/face_recognition_models \
    -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "App:app", "--bind", "0.0.0.0:5000", "--workers", "1", "--preload", "--timeout", "120"]


