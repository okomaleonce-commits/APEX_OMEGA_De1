# ═══════════════════════════════════════════════════════
#  APEX-OMEGA De1 Bot — Dockerfile
#  Base : Python 3.11-slim
# ═══════════════════════════════════════════════════════
FROM python:3.11-slim

# Metadata
LABEL maintainer="APEX-OMEGA Bundesliga Bot"
LABEL version="1.4.0"

# Variables d'environnement runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    PORT=10000

# Dossier de travail
WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

# Volume persistant pour les données
VOLUME ["/data"]

# Création des sous-dossiers /data au build
RUN mkdir -p /data/signals /data/outcomes /data/calibration /data/logs

# Exposition du port health check
EXPOSE 10000

# Point d'entrée
CMD ["python", "main.py"]
