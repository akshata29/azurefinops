@echo off
REM ---------------------------------------------------------------------------
REM run_frontend.bat - install deps (first run), start Vite dev server (:5173)
REM ---------------------------------------------------------------------------
cd /d %~dp0frontend

if not exist node_modules (
  echo Installing frontend dependencies...
  call npm install
)

echo Starting dashboard on http://localhost:5174  (proxies /api -> :8081)
call npm run dev
