# Windows Build Guide

## Requirements
- Python 3.9+
- PyInstaller

## Install Dependencies
```bash
pip install pyinstaller PyQt6 requests python-vlc
```

## Build .exe
```bash
cd clients/windows
pyinstaller --onefile --windowed --name "X87Player" main.py
```

## Output
Built `.exe` will be at `dist/X87Player.exe`
Copy to `releases/windows/X87Player-vX.X.X.exe`
