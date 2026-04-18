# APEX_OMEGA_De1 · Dockerfile
# Python 3.11-slim — Render compatible

FROM python:3.11-slim

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Répertoire persistant (Render Disk mountPath: /data)
RUN mkdir -p /data/signals /data/outcomes /data/calibration
VOLUME ["/data"]

EXPOSE 10000

CMD ["python", "main.py"]
