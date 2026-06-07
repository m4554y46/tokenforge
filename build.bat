@echo off
REM ============================================
REM TokenForge Build Script for Windows
REM ============================================

echo.
echo === TokenForge Build Script ===
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python 3.11+.
    pause
    exit /b 1
)
echo [OK] Python found

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed. Please install Node.js 18+.
    pause
    exit /b 1
)
echo [OK] Node.js found

REM Install Python dependencies
echo.
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)
echo [OK] Python dependencies installed

REM Install Node dependencies
echo.
echo [2/4] Installing Node dependencies...
call npm install
if errorlevel 1 (
    echo [ERROR] Failed to install Node dependencies.
    pause
    exit /b 1
)
echo [OK] Node dependencies installed

REM Build Python backend with PyInstaller (optional)
echo.
echo [3/4] Building Python backend...
REM Uncomment below to build a standalone Python executable
REM pip install pyinstaller
REM pyinstaller --onefile --name tokenforge-backend backend/app.py
REM echo [OK] Backend built

REM Build Electron app
echo.
echo [4/4] Building Electron application...
call npx electron-builder --win --x64
if errorlevel 1 (
    echo [ERROR] Failed to build Electron application.
    pause
    exit /b 1
)
echo [OK] Electron application built!

echo.
echo === Build complete! ===
echo Distribution package is in the "dist" folder.
echo.

pause
