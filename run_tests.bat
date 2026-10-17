@echo off
REM MathModel-Engine 测试运行脚本
REM 使用系统 Python 3.13

set PYTHON=D:\Program Files\Python\Python313\python.exe
set PROJECT_DIR=%~dp0

echo === MathModel-Engine Test Suite ===

echo.
echo [1/3] Fast unit tests (test_api + test_services)...
"%PYTHON%" -m pytest backend/tests/test_api.py backend/tests/test_services.py -q
if %ERRORLEVEL% NEQ 0 (echo FAILED && exit /b 1)

echo.
echo [2/3] Fast E2E tests (no LLM, < 30s)...
"%PYTHON%" -m pytest backend/tests/test_e2e_fast.py -q
if %ERRORLEVEL% NEQ 0 (echo FAILED && exit /b 1)

echo.
echo [3/3] Full unit tests (88 tests)...
"%PYTHON%" -m pytest backend/tests/test_api.py backend/tests/test_services.py backend/tests/test_ux.py backend/tests/test_perf.py -q
if %ERRORLEVEL% NEQ 0 (echo FAILED && exit /b 1)

echo.
echo === All tests passed ===
