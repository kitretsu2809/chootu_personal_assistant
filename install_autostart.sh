#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC="$SCRIPT_DIR/chotu.desktop"
DEST="$HOME/.config/autostart/chotu.desktop"

mkdir -p "$HOME/.config/autostart"
cp "$SRC" "$DEST"
chmod +x "$DEST" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/run_chotu.sh" 2>/dev/null || true

echo "Installed autostart entry to: $DEST"