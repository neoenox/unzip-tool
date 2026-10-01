@echo off
REM Build KantanKaiko.exe (requires Python 3.11+)
REM Usage: build.bat
REM If tools\UnRAR.exe exists, it is bundled so rar works standalone.
setlocal
cd /d "%~dp0"
pip install -r requirements.txt
pip install -r requirements-build.txt
set ADD_BIN=
if exist "tools\UnRAR.exe" set ADD_BIN=--add-binary "tools\UnRAR.exe;tools"
pyinstaller --noconfirm --clean --onefile --windowed --name KantanKaiko %ADD_BIN% app.py
echo.
echo Done: dist\KantanKaiko.exe
