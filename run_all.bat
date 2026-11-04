@echo off
echo ========================================================
echo  Launching ProjectMind AI (Backend + Frontend)
echo ========================================================
cd /d "%~dp0"

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8081 ...
start "ProjectMind AI - Backend (Port 8081)" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && uvicorn backend.main:app --host 127.0.0.1 --port 8081 --reload"

echo [2/2] Starting Vite Frontend on http://127.0.0.1:5173 ...
start "ProjectMind AI - Frontend (Port 5173)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo All services launched!
echo Open your web browser at: http://localhost:5173
echo.
pause
