#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export KUGOU_SIGNER_HOME="$ROOT_DIR"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "Python interpreter not found. Install Python 3.10+ or create .venv first."
  exit 1
fi

exec "$PYTHON_BIN" bootstrap_env.py "$@"
