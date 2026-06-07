#!/bin/bash
# ============================================
# TokenForge Build Script for macOS/Linux
# ============================================

set -e

echo ""
echo "=== TokenForge Build Script ==="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    exit 1
fi
echo "[OK] Python3 found"

if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js is not installed."
    exit 1
fi
echo "[OK] Node.js found"

echo ""
echo "[1/4] Installing Python dependencies..."
python3 -m pip install -r requirements.txt
echo "[OK] Python dependencies installed"

echo ""
echo "[2/4] Installing Node dependencies..."
npm install
echo "[OK] Node dependencies installed"

echo ""
echo "[3/4] Building Electron application..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    npx electron-builder --mac --x64
elif [[ "$OSTYPE" == "linux"* ]]; then
    npx electron-builder --linux --x64
else
    npx electron-builder
fi

echo "[OK] Electron application built!"

echo ""
echo "=== Build complete! ==="
echo "Distribution package is in the 'dist' folder."
echo ""
