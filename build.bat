@echo off
REM Build KantanKaiko.exe (requires Python 3.11+)
REM Usage: build.bat
REM If tools\UnRAR.exe exists, it is bundled so rar works standalone.
setlocal
cd /d "%~dp0"
pip install -r requirements.txt
pip install -r requirements-build.txt
REM UnRAR.exe が無ければ自動取得を試みる (失敗してもビルドは続行)。
if not exist "tools\UnRAR.exe" (
  python scripts\fetch_unrar.py
  if errorlevel 1 echo WARN: UnRAR auto-fetch failed. RAR needs manual setup or in-app fetch.
)
set ADD_BIN=
if exist "tools\UnRAR.exe" set ADD_BIN=--add-binary "tools\UnRAR.exe;tools"
pyinstaller --noconfirm --clean --onefile --windowed --name KantanKaiko %ADD_BIN% app.py
echo.
echo Done: dist\KantanKaiko.exe
