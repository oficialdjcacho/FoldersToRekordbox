#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

pyinstaller --noconfirm --clean --windowed \
  --name "Folders to Rekordbox" \
  --icon rekordbox.ico \
  --add-data "rekordbox.ico:." \
  --add-data "rekordbox.webp:." \
  folders_to_rekordbox_app.py
