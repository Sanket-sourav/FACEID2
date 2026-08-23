#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.12}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Could not find $PYTHON_BIN. Install it with: brew install python@3.12"
  exit 1
fi

if [ ! -d "venv" ]; then
  echo "Creating virtualenv with $PYTHON_BIN..."
  "$PYTHON_BIN" -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete. Activate with:  source venv/bin/activate"
