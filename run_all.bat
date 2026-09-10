@echo off
REM ---------------------------------------------------------------------------
REM run_all.bat - launch backend and frontend in separate windows
REM ---------------------------------------------------------------------------
start "Affiliate FinOps - Backend" cmd /k "%~dp0run_backend.bat"
start "Affiliate FinOps - Frontend" cmd /k "%~dp0run_frontend.bat"
echo Launched backend (:8081) and frontend (:5174) in separate windows.
