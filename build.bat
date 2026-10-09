@echo off
REM Reproducible local build: same PyInstaller flags as GitHub Windows CI.
REM UnRAR is never bundled; users can install it or set KANTAN_UNRAR.
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed --name KantanKaiko app.py
if errorlevel 1 exit /b 1
echo.
echo Done: dist\KantanKaiko.exe
