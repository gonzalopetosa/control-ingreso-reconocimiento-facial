FROM python:3.10-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gfortran \
    libblas-dev \
    liblapack-dev \
    libopenblas-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-all-dev \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir dlib==19.24.0

# INSTALAR face_recognition_models PRIMERO
RUN pip install --no-cache-dir git+https://github.com/ageitgey/face_recognition_models

# Ahora instalar los requirements
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "App:app", "--bind", "0.0.0.0:5000", "--workers", "2"]