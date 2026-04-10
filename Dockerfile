FROM python:3.11-slim

# System deps for curl_cffi + Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libssl-dev \
    ca-certificates \
    gcc \
    # Chromium system dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-xcb1 \
    libxcb-dri3-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser
RUN playwright install chromium

# Copy app code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Persistent data directory
RUN mkdir -p /app/data

# Environment defaults
ENV DATABASE_URL="sqlite+aiosqlite:////app/data/vinted_bot.db"
ENV FRONTEND_DIR="/app/frontend"
ENV PORT=8000
ENV SECRET_KEY="change-me-in-production"

EXPOSE 8000

CMD sh -c "cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
