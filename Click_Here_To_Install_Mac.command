#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
echo "Preparing JurisAtlas Setup Window..."
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv package runner..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

PY_BIN="$(uv python find 3.12 2>/dev/null || true)"
if [ -z "$PY_BIN" ]; then
    echo "Preparing Python 3.12 runtime..."
    uv python install 3.12
    PY_BIN="$(uv python find 3.12)"
fi

exec "$PY_BIN" "$SCRIPT_DIR/gui_installer_mac.py" "$@"
