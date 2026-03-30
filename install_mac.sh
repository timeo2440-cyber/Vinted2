#!/bin/bash
# ============================================
#   Vinted AutoBot — Installation Mac
#   Usage: bash install_mac.sh
# ============================================
set -e

REPO="https://github.com/timeo2440-cyber/Vinted2.git"
BRANCH="claude/vinted-autobot-interface-sCXVq"
INSTALL_DIR="$HOME/Desktop/VintedBot"
PORT=8000

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
info() { echo -e "${BLUE}[..]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[ERREUR]${NC} $1"; exit 1; }

echo ""
echo "  ╔══════════════════════════════╗"
echo "  ║     Vinted AutoBot Setup     ║"
echo "  ╚══════════════════════════════╝"
echo ""

# ── 1. Python 3 ────────────────────────────────────────────────────────────
info "Vérification de Python 3..."
if ! command -v python3 &>/dev/null; then
  warn "Python 3 non trouvé. Installation via Homebrew..."
  if ! command -v brew &>/dev/null; then
    info "Installation de Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi
  brew install python3
fi
PY=$(python3 --version)
ok "Python trouvé : $PY"

# ── 2. Git ──────────────────────────────────────────────────────────────────
info "Vérification de git..."
if ! command -v git &>/dev/null; then
  warn "Git non trouvé. Installation..."
  brew install git || xcode-select --install
fi
ok "Git OK"

# ── 3. Cloner le repo ───────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
  info "Dossier existant détecté — mise à jour..."
  cd "$INSTALL_DIR"
  git pull origin "$BRANCH" --quiet
else
  info "Téléchargement du bot..."
  git clone --branch "$BRANCH" --depth 1 "$REPO" "$INSTALL_DIR" --quiet
  cd "$INSTALL_DIR"
fi
ok "Code téléchargé dans : $INSTALL_DIR"

# ── 4. Environnement virtuel Python ─────────────────────────────────────────
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
  info "Création de l'environnement Python..."
  python3 -m venv venv
fi
source venv/bin/activate
ok "Environnement virtuel activé"

# ── 5. Dépendances ──────────────────────────────────────────────────────────
info "Installation des dépendances Python..."
pip install -r backend/requirements.txt -q
ok "Dépendances installées"

# ── 6. Dossier data ─────────────────────────────────────────────────────────
mkdir -p data
ok "Dossier data prêt"

# ── 7. Lancer le serveur ─────────────────────────────────────────────────────
echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │  Bot démarré !                          │"
echo "  │                                         │"
echo "  │  Ouvre Chrome et va sur :               │"
echo "  │  → http://localhost:$PORT               │"
echo "  │                                         │"
echo "  │  Ctrl+C pour arrêter                    │"
echo "  └─────────────────────────────────────────┘"
echo ""

# Ouvre automatiquement Chrome
sleep 2 && open -a "Google Chrome" "http://localhost:$PORT" &

cd "$INSTALL_DIR/backend"
python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT
