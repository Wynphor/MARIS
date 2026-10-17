@echo off
REM MathModel-Engine 启动脚本
REM 使用系统 Python 3.13，不依赖 venv

set PYTHON=D:\Program Files\Python\Python313\python.exe
set PROJECT_DIR=%~dp0

echo === MathModel-Engine ===
echo Python: %PYTHON%

REM 启动后端
echo Starting backend on http://127.0.0.1:8000 ...
"%PYTHON%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
