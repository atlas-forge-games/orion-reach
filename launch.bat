@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if errorlevel 1 (
        python -m venv .venv
    ) else (
        py -3 -m venv .venv
    )
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import pygame" >nul 2>nul
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Could not start Orion Reach. Install Python 3.10 or newer.
echo The first launch also needs internet access to install pygame-ce.
echo See README.md for manual setup and troubleshooting.
pause
exit /b 1
