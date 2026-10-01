@echo off
REM かんたん解凍のexeビルド (要 Python 3.11+)
REM 使い方: build.bat
setlocal
cd /d "%~dp0"
pip install -r requirements-build.txt
pyinstaller --noconfirm --clean --onefile --windowed --name KantanKaiko app.py
echo.
echo 完成: dist\KantanKaiko.exe
