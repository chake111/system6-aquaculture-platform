@echo off
echo ========================================
echo   Aquaculture Platform - Demo Launcher
echo ========================================
echo.

echo [0/3] Killing old processes on ports 8000 and 4173...
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":4173 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1

echo [1/3] Cleaning old database...
if exist "%~dp0backend\aquaculture.db" del /f /q "%~dp0backend\aquaculture.db"

echo [2/3] Starting backend (port 8000)...
set SEED_DATA=true
start "Backend" /D "%~dp0backend" cmd /k uv run uvicorn aquaculture_api.main:app --app-dir src --host 127.0.0.1 --port 8000
timeout /t 3 /nobreak >nul

echo [3/3] Starting frontend (port 4173)...
start "Frontend" /D "%~dp0frontend" cmd /k npx vite --host=127.0.0.1 --port=4173 --strictPort
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Done! Visit: http://127.0.0.1:4173/
echo ========================================
echo.
echo Demo accounts:
echo   Farmer:     13800000001 / demo-246810
echo   Technician: 13800000002 / demo-246810
echo   Admin:      13800000003 / demo-246810
echo.
pause
