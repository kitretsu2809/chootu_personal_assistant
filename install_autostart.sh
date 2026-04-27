#!/bin/bash
set -euo pipefail

SRC="/home/kitretsu/Desktop/PROJECTS/PERSONAL/ASSISTANT/chotu.desktop"
DEST="$HOME/.config/autostart/chotu.desktop"

mkdir -p "$HOME/.config/autostart"
cp "$SRC" "$DEST"
chmod +x "$DEST" 2>/dev/null || true
chmod +x /home/kitretsu/Desktop/PROJECTS/PERSONAL/ASSISTANT/run_chotu.sh 2>/dev/null || true

echo "Installed autostart entry to: $DEST"
