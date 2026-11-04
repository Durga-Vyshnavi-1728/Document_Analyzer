@echo off
cd /d "%~dp0"
echo Setting up Document Analyzer...
if not exist .venv (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
call .venv\\Scripts\\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Setup complete. Add your Gemini key to .env, then run run.bat.
pause
