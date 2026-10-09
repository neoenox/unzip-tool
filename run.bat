@echo off
REM Run KantanKaiko from source. Missing pip deps are installed automatically.
setlocal
cd /d "%~dp0"
python -c "import rarfile, py7zr" 2>nul
if errorlevel 1 (
  echo Installing dependencies...
  pip install -r requirements.txt
)
python "%~dp0app.py" %*
