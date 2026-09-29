#!/usr/bin/env bash
# run_dev.sh - EdiPro Developer Gateway Launcher for Linux/macOS
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$SCRIPT_DIR/venv/bin/python"

if [ ! -f "$VENV_PY" ]; then
    echo "[*] Creating Python virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
    "$VENV_PY" -m pip install --upgrade pip
    "$VENV_PY" -m pip install -r "$SCRIPT_DIR/src/backend/requirements.txt"
fi

echo "[+] Launching FastAPI gateway on http://localhost:8000 ..."
echo "[+] Operator Dashboard: http://localhost:8000/"
echo "[i] Press Ctrl+C to terminate."
cd "$SCRIPT_DIR/src/backend"
exec "$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
