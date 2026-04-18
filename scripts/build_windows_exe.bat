@echo off
setlocal

cd /d "%~dp0\.."

if not exist .venv (
  py -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --onefile --name VidIQLocalLauncher app\desktop_launcher.py

echo.
echo Build complete.
echo Please double-click: dist\VidIQLocalLauncher.exe
pause
