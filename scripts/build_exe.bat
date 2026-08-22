@echo off
REM PDF Unlocker - build a standalone Windows executable.
setlocal
cd /d "%~dp0.."

echo ========================================
echo PDF Unlocker - Build
echo ========================================
echo.

python -c "import PyInstaller" 2>NUL
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    echo.
)

echo Running the test suite before building...
python -m pytest -q
if errorlevel 1 (
    echo.
    echo ========================================
    echo Tests FAILED - build aborted
    echo ========================================
    pause
    exit /b 1
)
echo.

echo Building executable...
echo.

REM tkinterdnd2 ships a Tcl package (tkdnd) that PyInstaller cannot infer, so
REM collect its data files explicitly or drag-and-drop dies in the build.
pyinstaller --onefile ^
    --noconsole ^
    --name "PDF Unlocker" ^
    --collect-all tkinterdnd2 ^
    --collect-data customtkinter ^
    --hidden-import="keyring.backends.Windows" ^
    entry_point.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo Build FAILED
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build complete
echo ========================================
echo.
echo Executable: dist\PDF Unlocker.exe
echo.
pause
