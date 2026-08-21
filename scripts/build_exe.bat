@echo off
echo ========================================
echo PDF Unlocker Pro - Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>NUL
if errorlevel 1 (
    echo PyInstaller is not installed.
    echo Installing PyInstaller...
    pip install pyinstaller
    echo.
)

echo Building executable...
echo.

REM Build the executable
pyinstaller --onefile ^
    --noconsole ^
    --name "PDF Unlocker Pro" ^
    --add-data "core;core" ^
    --add-data "ui;ui" ^
    --hidden-import="pikepdf" ^
    --hidden-import="keyring" ^
    --hidden-import="platformdirs" ^
    --hidden-import="tkinterdnd2" ^
    --hidden-import="keyring.backends" ^
    --hidden-import="keyring.backends.Windows" ^
    pdf_unlocker.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo Build FAILED!
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build complete!
echo ========================================
echo.
echo Executable location: dist\PDF Unlocker Pro.exe
echo.
echo You can now distribute the .exe file.
echo No Python installation required on target machines.
echo.
pause
