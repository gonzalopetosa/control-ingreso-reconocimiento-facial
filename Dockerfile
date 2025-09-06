FROM python:3.10-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar TODAS las dependencias necesarias incluyendo git
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gfortran \
    git \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements primero para mejor caching
COPY requirements.txt .

RUN pip install --upgrade pip

# Instalar todo en un solo paso para mejor caching
RUN pip install --no-cache-dir \
    dlib==19.24.0 \
    git+https://github.com/ageitgey/face_recognition_models \
    -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "App:app", "--bind", "0.0.0.0:5000", "--workers", "2"]