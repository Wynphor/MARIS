@echo off
chcp 65001 >nul 2>&1
echo.
echo  ========================================
echo   MathModel-Engine 启动
echo  ========================================
echo.

cd /d "%~dp0backend"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

:: Check dependencies
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
)

:: Check .env
if not exist "..\.env" (
    if exist "..\.env.example" (
        echo [WARNING] No .env file found. Copying from .env.example...
        copy "..\.env.example" "..\.env" >nul
        echo [WARNING] Please edit .env and add your API keys before using AI features.
        echo.
    )
)

:: Start server
echo Starting server at http://localhost:8000
echo API docs at http://localhost:8000/docs
echo Press Ctrl+C to stop.
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
