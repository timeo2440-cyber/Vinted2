#!/bin/bash
# ============================================
#   Vinted AutoBot — Installation Mac
#   Colle cette commande dans le Terminal :
#   bash <(curl -fsSL https://raw.githubusercontent.com/timeo2440-cyber/Vinted2/claude/vinted-autobot-interface-sCXVq/install_mac.sh)
# ============================================

REPO="https://github.com/timeo2440-cyber/Vinted2.git"
BRANCH="claude/vinted-autobot-interface-sCXVq"
INSTALL_DIR="$HOME/Desktop/VintedBot"
PORT=8000

G='\033[0;32m'; R='\033[0;31m'; B='\033[0;34m'; Y='\033[1;33m'; N='\033[0m'

echo ""
echo "  ╔══════════════════════════════╗"
echo "  ║     Vinted AutoBot Setup     ║"
echo "  ╚══════════════════════════════╝"
echo ""

# ── 1. Python 3 ─────────────────────────────────────────────
echo -e "${B}[1/6]${N} Vérification de Python 3..."
if ! command -v python3 &>/dev/null; then
  echo -e "${Y}Python 3 non trouvé. Installation...${N}"
  if command -v brew &>/dev/null; then
    brew install python3
  else
    echo -e "${R}[!] Installe d'abord Homebrew :${N}"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo "Puis relance ce script."
    exit 1
  fi
fi
echo -e "${G}  ✓ $(python3 --version)${N}"

# ── 2. Téléchargement du code ────────────────────────────────
echo -e "${B}[2/6]${N} Téléchargement du bot..."
if [ -d "$INSTALL_DIR/.git" ]; then
  cd "$INSTALL_DIR"
  git pull origin "$BRANCH" --quiet 2>/dev/null || true
else
  rm -rf "$INSTALL_DIR" 2>/dev/null
  git clone --branch "$BRANCH" --depth 1 "$REPO" "$INSTALL_DIR" 2>&1 || {
    echo -e "${R}[!] Impossible de télécharger. Vérifiez votre connexion internet.${N}"
    exit 1
  }
fi
cd "$INSTALL_DIR"
echo -e "${G}  ✓ Code dans : $INSTALL_DIR${N}"

# ── 3. Environnement Python ──────────────────────────────────
echo -e "${B}[3/6]${N} Création environnement Python..."
if [ ! -d "venv" ]; then
  python3 -m venv venv 2>&1 || {
    echo -e "${Y}venv a échoué, essai avec pip direct...${N}"
  }
fi

if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
  PIP="venv/bin/pip"
else
  PIP="pip3"
fi
echo -e "${G}  ✓ Environnement prêt${N}"

# ── 4. Dépendances ───────────────────────────────────────────
echo -e "${B}[4/6]${N} Installation des dépendances (peut prendre 1-3 min)..."
$PIP install --upgrade pip -q 2>/dev/null
$PIP install -r backend/requirements.txt 2>&1 | while IFS= read -r line; do
  # Affiche seulement les lignes importantes
  case "$line" in
    *Installing*|*Collecting*|*Successfully*|*ERROR*|*error*)
      echo "     $line"
      ;;
  esac
done
echo -e "${G}  ✓ Dépendances installées${N}"

# ── 5. Préparation ───────────────────────────────────────────
echo -e "${B}[5/6]${N} Préparation..."
mkdir -p data

# Libère le port si déjà pris
lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
echo -e "${G}  ✓ Port $PORT libre${N}"

# ── 6. Lancement ─────────────────────────────────────────────
echo -e "${B}[6/6]${N} Démarrage du serveur..."
echo ""
echo -e "${G}  ┌─────────────────────────────────────────┐${N}"
echo -e "${G}  │                                         │${N}"
echo -e "${G}  │   Bot démarré !                         │${N}"
echo -e "${G}  │                                         │${N}"
echo -e "${G}  │   Chrome va s'ouvrir sur :              │${N}"
echo -e "${G}  │   → http://localhost:$PORT              │${N}"
echo -e "${G}  │                                         │${N}"
echo -e "${G}  │   Ctrl+C pour arrêter le bot            │${N}"
echo -e "${G}  │                                         │${N}"
echo -e "${G}  └─────────────────────────────────────────┘${N}"
echo ""

# Ouvre Chrome après un court délai
(sleep 3 && open "http://localhost:$PORT" 2>/dev/null) &

cd "$INSTALL_DIR/backend"

# Lance uvicorn (le process principal)
if [ -f "$INSTALL_DIR/venv/bin/uvicorn" ]; then
  "$INSTALL_DIR/venv/bin/uvicorn" main:app --host 127.0.0.1 --port $PORT
else
  python3 -m uvicorn main:app --host 127.0.0.1 --port $PORT
fi
