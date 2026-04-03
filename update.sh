#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "[1/4] Arrêt du bot..."
bash start.sh stop 2>/dev/null

echo "[2/4] Récupération du dernier code..."
git pull origin claude/vinted-autobot-interface-k84pq

echo "[3/4] Mise à jour des dépendances..."
rm -rf venv
bash start.sh install

echo "[4/4] Démarrage..."
bash start.sh start
