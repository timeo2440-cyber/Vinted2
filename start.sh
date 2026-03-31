#!/bin/bash
# ================================================
#   Vinted AutoBot — Script de démarrage
# ================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
DATA_DIR="$SCRIPT_DIR/data"
VENV_DIR="$SCRIPT_DIR/venv"
LOG_FILE="$SCRIPT_DIR/bot.log"
PID_FILE="$SCRIPT_DIR/bot.pid"

PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"

# ── Helpers ──────────────────────────────────────────────────────────────────

_ensure_venv() {
  if [ ! -f "$PYTHON" ]; then
    echo "[*] Création de l'environnement virtuel..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
      echo "[ERREUR] Impossible de créer le venv. Vérifiez que python3-venv est installé :"
      echo "         sudo apt-get install python3-venv"
      exit 1
    fi
  fi
}

_ensure_deps() {
  if ! "$PYTHON" -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "[*] Installation des dépendances (peut prendre 1-2 minutes)..."
    "$PIP" install --upgrade pip -q
    "$PIP" install -r "$BACKEND_DIR/requirements.txt" -q
    if [ $? -ne 0 ]; then
      echo "[ERREUR] Échec de l'installation des dépendances."
      exit 1
    fi
    echo "[OK] Dépendances installées."
  fi
}

_show_urls() {
  IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  echo ""
  echo "  ┌─────────────────────────────────────────┐"
  echo "  │  Vinted AutoBot — accès                 │"
  echo "  │                                         │"
  echo "  │  Local   : http://localhost:8000        │"
  if [ -n "$IP" ]; then
  printf "  │  Réseau  : http://%-21s │\n" "$IP:8000"
  fi
  echo "  └─────────────────────────────────────────┘"
  echo ""
  echo "  Logs : tail -f $LOG_FILE"
  echo "  Stop : bash $0 stop"
  echo ""
}

# ── Commandes ────────────────────────────────────────────────────────────────

case "${1:-start}" in

  start)
    # Déjà en cours ?
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "[!] Bot déjà en cours (PID $(cat "$PID_FILE"))"
      _show_urls
      exit 0
    fi

    mkdir -p "$DATA_DIR"
    _ensure_venv
    _ensure_deps

    cd "$BACKEND_DIR"

    # Lance en arrière-plan
    nohup "$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port 8000 \
      > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    sleep 3

    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "[OK] Bot démarré (PID $(cat "$PID_FILE"))"
      _show_urls
    else
      echo "[ERREUR] Le bot n'a pas démarré. Logs :"
      tail -30 "$LOG_FILE"
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
      echo "[OK] Bot en cours — PID $(cat "$PID_FILE")"
      _show_urls
    else
      echo "[--] Bot arrêté."
    fi
    ;;

  logs)
    tail -f "$LOG_FILE"
    ;;

  install)
    echo "[*] Réinstallation forcée de l'environnement..."
    rm -rf "$VENV_DIR"
    _ensure_venv
    _ensure_deps
    echo "[OK] Installation terminée. Lancez : bash $0 start"
    ;;

  *)
    echo "Usage: bash start.sh [start|stop|restart|status|logs|install]"
    echo ""
    echo "  start    — Démarrer le bot"
    echo "  stop     — Arrêter le bot"
    echo "  restart  — Redémarrer le bot"
    echo "  status   — Vérifier l'état"
    echo "  logs     — Voir les logs en direct"
    echo "  install  — Réinstaller les dépendances"
    ;;
esac
