#!/bin/bash
# ================================================
#   VintedBot — Gestion des releases
# ================================================
# Usage:
#   bash release.sh prepare    → basculer sur develop pour coder
#   bash release.sh publish    → publier develop → main (release)
#   bash release.sh hotfix     → corriger un bug directement sur main
#   bash release.sh status     → voir l'état des branches
# ================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

case "${1}" in

  prepare)
    echo "[*] Basculement sur la branche develop..."
    git fetch origin 2>/dev/null
    git checkout develop 2>/dev/null || git checkout -b develop
    git pull origin develop 2>/dev/null || true
    echo ""
    echo "[OK] Tu es sur 'develop'. Code tes nouvelles fonctionnalités."
    echo "     Quand tu veux publier : bash release.sh publish"
    ;;

  publish)
    VERSION="${2:-$(date +%Y.%m.%d)}"
    echo "[*] Publication de la version $VERSION..."

    # S'assurer qu'on est à jour
    git checkout develop
    git pull origin develop 2>/dev/null || true

    # Merge develop → main
    git checkout main
    git pull origin main 2>/dev/null || true
    git merge develop --no-ff -m "release: version $VERSION"

    # Tag de version
    git tag -a "v$VERSION" -m "Version $VERSION"

    # Push
    git push origin main
    git push origin "v$VERSION"

    echo ""
    echo "[OK] Version $VERSION publiée sur main !"
    echo "     Redémarre le bot : bash start.sh restart"
    ;;

  hotfix)
    echo "[*] Mode hotfix — correction directe sur main..."
    git checkout main
    git pull origin main 2>/dev/null || true
    echo ""
    echo "[OK] Tu es sur 'main'. Corrige le bug, puis :"
    echo "     git add . && git commit -m 'hotfix: description'"
    echo "     git push origin main"
    echo "     bash start.sh restart"
    ;;

  status)
    echo "=== Branches ==="
    git branch -a 2>/dev/null
    echo ""
    echo "=== Dernières versions ==="
    git tag --sort=-version:refname 2>/dev/null | head -5
    echo ""
    echo "=== Branche actuelle ==="
    git branch --show-current
    ;;

  *)
    echo "Usage: bash release.sh [prepare|publish|hotfix|status]"
    echo ""
    echo "  prepare          → Aller sur develop pour coder de nouvelles fonctionnalités"
    echo "  publish [v1.0]   → Publier develop sur main (mise en production)"
    echo "  hotfix           → Corriger un bug urgent directement sur main"
    echo "  status           → Voir l'état des branches et versions"
    ;;
esac
