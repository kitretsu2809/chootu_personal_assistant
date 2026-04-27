# Chotu Voice Assistant

A voice assistant that listens for wake words ("chhotu", "chotu") and executes commands via OpenCLAW.

## Features

- Wake word detection using speech recognition
- Voice and typing input modes
- Tkinter-based popup UI
- Keyboard shortcut: Hold Alt for 1+ seconds to invoke
- Autostart support for Linux

## Prerequisites

- Python 3.12+
- OpenCLAW binary at `~/.nvm/versions/node/v24.14.0/bin/openclaw`
- ALSA audio libraries (Linux)

## Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the assistant
python voice_assistant.py
```

## Autostart (Linux)

```bash
# Install autostart entry
./install_autostart.sh
```

## Usage

- Say "chhotu" or "chotu" followed by your command
- Or hold Alt key for 1+ seconds to invoke typing mode