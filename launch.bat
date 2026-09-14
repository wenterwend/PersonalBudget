@echo off
title Personal Finance & Budget App
echo Starting FastAPI Backend (Port 8000)...
start "Budget Backend" /b .venv\Scripts\uvicorn.exe src.backend.main:app --port 8000

echo Starting SvelteKit Frontend (Port 5173)...
cd src\frontend
start "Budget Frontend" /b npm run dev

echo Waiting for servers to initialize...
timeout /t 3 /nobreak > nul

echo Opening browser at http://localhost:5173...
start http://localhost:5173

echo.
echo Application is running. Close this window to stop servers when finished.
pause
