@echo off
REM PDF Unlocker Pro - Launcher Script
REM This script installs dependencies and runs the application

echo ========================================
echo PDF Unlocker Pro - Launcher
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM Check if dependencies are installed
python -c "import pikepdf" 2>NUL
if errorlevel 1 (
    echo Installing dependencies...
    echo This may take a minute...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Dependencies installed successfully!
    echo.
)

echo Starting PDF Unlocker Pro...
echo.

REM Run the application
python pdf_unlocker.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo Application exited with an error
    echo ========================================
    echo.
    pause
)
