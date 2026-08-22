@echo off
REM PDF Unlocker - launcher. Installs dependencies on first run.
setlocal
cd /d "%~dp0.."

echo ========================================
echo PDF Unlocker
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo Install Python 3.9+ from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM customtkinter is the newest requirement, so it is the one worth probing.
python -c "import pikepdf, customtkinter" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies, this may take a minute...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies.
        echo.
        pause
        exit /b 1
    )
    echo.
)

echo Starting PDF Unlocker...
echo.
python -m pdf_unlocker

if errorlevel 1 (
    echo.
    echo ========================================
    echo Application exited with an error
    echo Check the log directory named in the README
    echo ========================================
    echo.
    pause
)
