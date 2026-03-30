#!/bin/bash
# ============================================
#   Vinted AutoBot — Installation Mac
#   AUCUN GIT REQUIS — télécharge un ZIP
# ============================================

ZIPURL="https://github.com/timeo2440-cyber/Vinted2/archive/refs/heads/main.zip"
INSTALL_DIR="$HOME/Desktop/VintedBot"
PORT=8000

G='\033[0;32m'; R='\033[0;31m'; B='\033[0;34m'; Y='\033[1;33m'; N='\033[0m'

echo ""
echo "  ╔══════════════════════════════╗"
echo "  ║     Vinted AutoBot Setup     ║"
echo "  ╚══════════════════════════════╝"
echo ""

# ── 1. Python 3 ─────────────────────────────────────────────
echo -e "${B}[1/5]${N} Vérification de Python 3..."
if ! command -v python3 &>/dev/null; then
  echo -e "${R}[!] Python 3 non trouvé.${N}"
  echo ""
  echo "  Installe-le d'abord :"
  echo "  1. Va sur https://www.python.org/downloads/"
  echo "  2. Clique 'Download Python 3'"
  echo "  3. Installe-le"
  echo "  4. Relance ce script"
  echo ""
  exit 1
fi
echo -e "${G}  OK — $(python3 --version)${N}"

# ── 2. Téléchargement ZIP ────────────────────────────────────
echo -e "${B}[2/5]${N} Téléchargement du bot..."
rm -rf "$INSTALL_DIR" /tmp/vinted_bot.zip /tmp/Vinted2-main 2>/dev/null

curl -L -o /tmp/vinted_bot.zip "$ZIPURL" --progress-bar || {
  echo -e "${R}[!] Téléchargement échoué. Vérifie ta connexion internet.${N}"
  exit 1
}

echo "       Extraction..."
cd /tmp
unzip -q vinted_bot.zip || {
  echo -e "${R}[!] Extraction échouée.${N}"
  exit 1
}
mv Vinted2-main "$INSTALL_DIR"
rm -f vinted_bot.zip
echo -e "${G}  OK — Dossier : $INSTALL_DIR${N}"

# ── 3. Dépendances Python ────────────────────────────────────
echo -e "${B}[3/5]${N} Installation des dépendances (1-3 min)..."
cd "$INSTALL_DIR"
mkdir -p data

python3 -m pip install --user --upgrade pip -q 2>/dev/null
python3 -m pip install --user -r backend/requirements.txt 2>&1 | while IFS= read -r line; do
  case "$line" in
    *Installing*|*Collecting*|*Successfully*|*ERROR*|*error*|*Downloading*)
      echo "     $line"
      ;;
  esac
done
echo -e "${G}  OK — Tout est installé${N}"

# ── 4. Libère le port ────────────────────────────────────────
echo -e "${B}[4/5]${N} Préparation..."
lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
echo -e "${G}  OK${N}"

# ── 5. Lancement ─────────────────────────────────────────────
echo -e "${B}[5/5]${N} Démarrage..."
echo ""
echo -e "${G}  ┌─────────────────────────────────────────┐${N}"
echo -e "${G}  │                                         │${N}"
echo -e "${G}  │   BOT PRÊT !                            │${N}"
echo -e "${G}  │                                         │${N}"
echo -e "${G}  │   Ouvre Chrome :                        │${N}"
echo -e "${G}  │   → http://localhost:8000               │${N}"
echo -e "${G}  │                                         │${N}"
echo -e "${G}  │   Ctrl+C pour arrêter                   │${N}"
echo -e "${G}  │                                         │${N}"
echo -e "${G}  └─────────────────────────────────────────┘${N}"
echo ""

# Ouvre Chrome
(sleep 3 && open "http://localhost:$PORT" 2>/dev/null) &

cd "$INSTALL_DIR/backend"
python3 -m uvicorn main:app --host 127.0.0.1 --port $PORT
