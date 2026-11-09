FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema requeridas para visión artificial y ONNX Runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copia e instalación de requerimientos del backend, visión y orquestación con LangChain
COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements-vision.txt /app/backend/requirements-vision.txt
RUN pip install --no-cache-dir \
    -r /app/backend/requirements.txt \
    -r /app/backend/requirements-vision.txt

# Copia de la lógica del backend y la configuración normativa inicial
COPY backend /app/backend
COPY config_normativo /app/config_normativo

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
