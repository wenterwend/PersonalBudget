@echo off
title Build Standalone Windows Executable
echo ====================================================================
echo       Building Budget Application Single-File Executable (.exe)
echo ====================================================================
echo.

:: 1. Build frontend static files
echo [Step 1/3] Building SvelteKit frontend static distribution...
cd src\frontend
call npm install
call npm run build
cd ..\..
if not exist "src\frontend\build\index.html" (
    echo Error: Frontend build failed!
    pause
    exit /b 1
)

:: 2. Ensure PyInstaller is installed
echo [Step 2/3] Checking dependencies...
python -m pip install pyinstaller -r requirements.txt

:: 3. Build single-file executable
echo [Step 3/3] Compiling single-file executable with PyInstaller...
pyinstaller --noconfirm --clean --onefile ^
  --add-data "src\frontend\build;frontend_build" ^
  --hidden-import "uvicorn.logging" ^
  --hidden-import "uvicorn.loops" ^
  --hidden-import "uvicorn.loops.auto" ^
  --hidden-import "uvicorn.protocols" ^
  --hidden-import "uvicorn.protocols.http" ^
  --hidden-import "uvicorn.protocols.http.auto" ^
  --hidden-import "uvicorn.protocols.websockets" ^
  --hidden-import "uvicorn.protocols.websockets.auto" ^
  --hidden-import "uvicorn.lifespan" ^
  --hidden-import "uvicorn.lifespan.on" ^
  --name BudgetApp ^
  run_app.py

echo.
echo ====================================================================
echo Build completed successfully!
echo Executable location: dist\BudgetApp.exe
echo ====================================================================
pause
