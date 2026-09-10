@echo off
REM ---------------------------------------------------------------------------
REM run_backend.bat - create venv (first run), install deps, start FastAPI (:8000)
REM ---------------------------------------------------------------------------
cd /d %~dp0backend

if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

if not exist .env copy .env.example .env >nul

echo Starting backend on http://localhost:8081  (Swagger: /docs)
uvicorn app.main:app --reload --port 8081
