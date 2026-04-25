@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo Starting zTrade from %CD%
"%PYTHON_EXE%" -m ztrade.cli desktop

if errorlevel 1 (
    echo.
    echo zTrade exited with an error. Press any key to close this window.
    pause > nul
)
