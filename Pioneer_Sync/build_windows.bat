@echo off
setlocal
cd /d "%~dp0"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

pyinstaller --noconfirm --clean --onefile --windowed ^
  --name "Folders to Rekordbox" ^
  --icon rekordbox.ico ^
  --add-data "rekordbox.ico;." ^
  --add-data "rekordbox.webp;." ^
  folders_to_rekordbox_app.py

endlocal
