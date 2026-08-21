#!/usr/bin/env bash
# ==============================================================================
#  bootstrap.sh — Initialisation Bulletproof pour Sandbox & Conteneurs Linux
#  - Installe les dépendances Python dans .venv
#  - Installe UNIQUEMENT Chromium (pas WebKit ni Firefox)
#  - Installe uniquement les bibliothèques runtime minimales (zéro police CJK OOM)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

echo "🚀 [Bootstrap] Initialisation de l'environnement..."

# 1. Création et activation du venv Python
if [ ! -d ".venv" ]; then
    echo "📦 Création de l'environnement virtuel .venv..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# 2. Installation des dépendances Python
echo "📥 Installation des dépendances Python..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# 3. Installation de Chromium Playwright (ciblé)
echo "🌐 Installation du binaire Chromium Playwright..."
playwright install chromium

# 4. Installation des bibliothèques système Linux minimales (sans polices CJK géantes)
if [ "$(uname -s)" = "Linux" ]; then
    MINIMAL_DEPS=(
        libnspr4
        libnss3
        libatk1.0-0
        libatk-bridge2.0-0
        libcups2
        libdrm2
        libxkbcommon0
        libxcomposite1
        libxdamage1
        libxfixes3
        libxrandr2
        libgbm1
        libpango-1.0-0
        libcairo2
        libasound2
        fonts-liberation
        ca-certificates
    )

    if [ "$(id -u)" -eq 0 ] && command -v apt-get >/dev/null 2>&1; then
        echo "🔧 Installation des bibliothèques Chromium légères (Debian/Ubuntu)..."
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq || true
        apt-get install -y --no-install-recommends "${MINIMAL_DEPS[@]}" >/dev/null 2>&1 || true
    elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
        echo "🔧 Installation des bibliothèques via sudo apt-get..."
        sudo apt-get update -qq || true
        sudo apt-get install -y --no-install-recommends "${MINIMAL_DEPS[@]}" >/dev/null 2>&1 || true
    else
        echo "ℹ️  Environnement non-root ou sans apt-get. Utilisation des bibliothèques système existantes."
    fi
fi

echo "✅ [Bootstrap] Environnement prêt ! Tu peux lancer : python run.py"
