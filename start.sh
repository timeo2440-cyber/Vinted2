#!/bin/bash
set -e

echo "================================"
echo "   Vinted AutoBot - Démarrage   "
echo "================================"

# Se placer dans le dossier backend
cd "$(dirname "$0")/backend"

# Créer le dossier data si absent
mkdir -p ../data

# Installer les dépendances si nécessaire
if ! python -c "import fastapi" 2>/dev/null; then
  echo "[*] Installation des dépendances..."
  pip install -r requirements.txt -q
fi

echo "[*] Serveur lancé sur http://0.0.0.0:8000"
echo "[*] Accès local  : http://localhost:8000"
echo "[*] Ctrl+C pour arrêter"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
