#!/bin/bash
# ================================================
#   Vinted AutoBot — Script de démarrage
# ================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
DATA_DIR="$SCRIPT_DIR/data"
LOG_FILE="$SCRIPT_DIR/bot.log"
PID_FILE="$SCRIPT_DIR/bot.pid"

case "${1:-start}" in

  start)
    # Vérifie si déjà lancé
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "[!] Bot déjà en cours (PID $(cat "$PID_FILE"))"
      echo "    → http://localhost:8000"
      exit 0
    fi

    mkdir -p "$DATA_DIR"
    cd "$BACKEND_DIR"

    # Installe les dépendances si nécessaire
    if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
      echo "[*] Installation des dépendances..."
      pip3 install -r requirements.txt -q
    fi

    # Lance en arrière-plan
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 \
      > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    sleep 3

    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "[OK] Bot démarré (PID $(cat "$PID_FILE"))"
      # Affiche l'IP locale
      IP=$(hostname -I 2>/dev/null | awk '{print $1}')
      echo ""
      echo "  Accès local   : http://localhost:8000"
      [ -n "$IP" ] && echo "  Accès réseau  : http://$IP:8000"
      echo ""
      echo "  Logs : tail -f $LOG_FILE"
      echo "  Stop : bash $0 stop"
    else
      echo "[ERREUR] Le bot n'a pas démarré. Logs :"
      tail -20 "$LOG_FILE"
      exit 1
    fi
    ;;

  stop)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      kill "$(cat "$PID_FILE")"
      rm -f "$PID_FILE"
      echo "[OK] Bot arrêté."
    else
      rm -f "$PID_FILE"
      echo "[!] Bot non actif."
    fi
    ;;

  restart)
    bash "$0" stop
    sleep 1
    bash "$0" start
    ;;

  status)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "[OK] Bot en cours — PID $(cat "$PID_FILE") — http://localhost:8000"
    else
      echo "[--] Bot arrêté."
    fi
    ;;

  logs)
    tail -f "$LOG_FILE"
    ;;

  *)
    echo "Usage: bash start.sh [start|stop|restart|status|logs]"
    ;;
esac
