#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec >/dev/null 2>&1
exec "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/voice_assistant.py"