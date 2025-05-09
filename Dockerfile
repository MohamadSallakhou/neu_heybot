# 1. Base Image mit Python & Dependencies
FROM python:3.11-slim

# 2. Arbeitsverzeichnis
WORKDIR /app

# 3. Copy requirements und install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy Quellcode
COPY . .

# 5. Env-Defaults (können in K8s-Deployment überschrieben werden)
ENV OLLAMA_HOST="http://ollama-service:11434" \
    DISCORD_WEBHOOK_URL="" \
    MODEL_HUMOR_PATH="model_humor.txt"

# 6. Port (falls du einen HTTP-Server betreibst, sonst optional)
# EXPOSE 8080

# 7. EntryPoint
CMD ["python", "app/main.py"]
