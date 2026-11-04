@echo off
echo ========================================================
echo  Starting ProjectMind AI React/Vite Frontend (Port 5173)
echo ========================================================
cd /d "%~dp0frontend"
npm run dev -- --host 127.0.0.1 --port 5173
pause
