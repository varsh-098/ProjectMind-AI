@echo off
echo ========================================================
echo  Launching ProjectMind AI (Backend + Frontend)
echo ========================================================
cd /d "%~dp0"

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8081 ...
start "ProjectMind AI - Backend (Port 8081)" "%~dp0run_backend.bat"

timeout /t 2 /nobreak >nul

echo [2/2] Starting Vite Frontend on http://127.0.0.1:5173 ...
start "ProjectMind AI - Frontend (Port 5173)" "%~dp0run_frontend.bat"

echo.
echo ========================================================
echo  All services started!
echo  Open your web browser at: http://localhost:5173
echo ========================================================
echo.
pause
