# 1. Official Python Base Image
FROM python:3.11-slim

# 2. Arbeitsverzeichnis setzen
WORKDIR /app

# 3. System-Dependencies installieren (für Curl, Compiler-Tools o. Ä.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Python-Dependencies installieren
#    Zuerst nur requirements kopieren, damit Docker-Cache greift
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 5. Applikationscode kopieren
COPY ./app /app

# 6. ENV-Defaults (können in Deinem K8s-Deployment per envFrom überschrieben werden)
ENV OLLAMA_API_URL="http://ollama-svc.default.svc.cluster.local:11434" \
    DISCORD_WEBHOOK_URL="" \
    MODEL_HUMOR_PATH="model_humor.txt" \
    PROJECT_CONTEXT_INFO="Keine weiteren Informationen"

# 7. Port freigeben (wie in Deinem Deployment: containerPort 7861)
EXPOSE 7861

# 8. Startup-Command
#    Main-Skript liegt im Projekt-Root als main.py
CMD ["python", "main.py"]
