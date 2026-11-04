@echo off
echo ========================================================
echo  Starting ProjectMind AI FastAPI Backend (Port 8081)
echo ========================================================
cd /d "%~dp0"
call .venv\Scripts\activate.bat
uvicorn backend.main:app --host 127.0.0.1 --port 8081 --reload
pause
