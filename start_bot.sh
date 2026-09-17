#!/usr/bin/env bash
# ============================================================
#  BOSS Auto-Reply Bot - macOS / Linux Quick Start
# ============================================================

cd "$(dirname "$0")"

echo "==================================================="
echo "  BOSS Auto-Reply Bot - Quick Start"
echo "==================================================="
echo ""

# === 1. Check Python ===
echo "[1/4] Checking Python..."

if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "  [ERROR] Python not found!"
    echo "  Install from: https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)
echo "  [OK] $PY_VERSION"

# === 2. Virtual Environment ===
echo "[2/4] Checking virtual environment..."

if [ ! -d "venv" ]; then
    echo "  [INFO] Creating virtual environment..."
    $PYTHON -m venv venv
    if [ $? -ne 0 ]; then
        echo "  [ERROR] Failed to create venv"
        exit 1
    fi
    echo "  [OK] Virtual environment created"
else
    echo "  [OK] Virtual environment exists"
fi

source venv/bin/activate
echo "  [OK] Virtual environment activated"

# === 3. Dependencies ===
echo "[3/4] Checking dependencies..."

python -c "import DrissionPage" &>/dev/null
if [ $? -ne 0 ]; then
    echo "  [INFO] Installing dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "  [ERROR] pip install failed"
        exit 1
    fi
    echo "  [OK] Dependencies installed"
else
    echo "  [OK] All dependencies installed"
fi

# === 4. Chrome ===
echo "[4/4] Checking Chrome..."

CHROME_OK=0
if command -v google-chrome &>/dev/null; then
    CHROME_OK=1
elif command -v chromium &>/dev/null; then
    CHROME_OK=1
elif [ -d "/Applications/Google Chrome.app" ]; then
    CHROME_OK=1
fi

if [ "$CHROME_OK" -eq 1 ]; then
    echo "  [OK] Chrome found"
else
    echo "  [WARN] Chrome not found"
    echo "  Install from: https://www.google.com/chrome/"
fi

# === Select Mode ===
echo ""
echo "Select mode:"
echo "  1) With browser window"
echo "  2) Headless"
read -p "Enter [1/2] (default 1): " MODE_CHOICE

HEADLESS_FLAG=""
case "$MODE_CHOICE" in
    2) HEADLESS_FLAG="--headless" ;;
esac

echo ""
echo "Starting bot..."
echo ""

python -m boss_bot $HEADLESS_FLAG

echo ""
echo Bot stopped.
