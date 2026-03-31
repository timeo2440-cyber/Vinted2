#!/bin/bash
# Démarre automatiquement le serveur dans GitHub Codespaces
mkdir -p /workspaces/Vinted2/data
cd /workspaces/Vinted2/backend
echo "🚀 Démarrage de Vinted AutoBot..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
echo "✅ Serveur démarré — port 8000 public"
