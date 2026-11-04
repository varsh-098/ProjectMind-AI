@echo off
echo ========================================================
echo  Starting ProjectMind AI FastAPI Backend (Port 8081)
echo ========================================================
cd /d "%~dp0"
echo Launching Uvicorn backend server...
".\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8081
pause
