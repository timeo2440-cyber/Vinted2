#!/bin/bash
set -e

LOG=/workspaces/Vinted2/server.log
mkdir -p /workspaces/Vinted2/data
cd /workspaces/Vinted2/backend

echo "🚀 Démarrage de Vinted AutoBot..." | tee -a "$LOG"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload >> "$LOG" 2>&1 &
echo $! > /tmp/vinted_pid
echo "✅ Serveur démarré (PID $(cat /tmp/vinted_pid)) — port 8000"
echo "📋 Logs : $LOG"
