@echo off
setlocal

echo ================================================================
echo           LocalOps AI -- System Launcher
echo ================================================================
echo.

cd /d "%~dp0"

REM Check for virtual environment
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Using Python interpreter: %PYTHON_EXE%
echo Starting LocalOps AI full stack...
echo.

"%PYTHON_EXE%" scripts/run_all.py %*

endlocal
