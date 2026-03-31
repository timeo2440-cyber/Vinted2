FROM python:3.11-slim

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les fichiers
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Répertoire pour la base de données
RUN mkdir -p /app/data

# Variables d'environnement par défaut
ENV DATABASE_URL="sqlite+aiosqlite:////app/data/vinted_bot.db"
ENV FRONTEND_DIR="/app/frontend"
ENV PORT=8000

EXPOSE 8000

# Lancement
CMD sh -c "cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
