@echo off
chcp 65001 >nul 2>&1

title BOSS Auto-Reply Bot

cd /d "%~dp0"

echo ===================================================
echo   BOSS Auto-Reply Bot - Quick Start
echo ===================================================
echo.

REM ========== 1. Check Python ==========
echo [1/4] Checking Python...

set "PYTHON_CMD="
set "PYTHON_VERSION="

where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do (
        set "PYTHON_CMD=python"
        set "PYTHON_VERSION=%%v"
    )
)

if "%PYTHON_CMD%"=="" (
    where python3 >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=2" %%v in ('python3 --version 2^>^&1') do (
            set "PYTHON_CMD=python3"
            set "PYTHON_VERSION=%%v"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo   [ERROR] Python not found!
    echo.
    echo   Please install Python 3.8+ from:
    echo   https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo   [OK] Python %PYTHON_VERSION%

REM ========== 2. Check Virtual Environment ==========
echo [2/4] Checking virtual environment...

set "VENV_DIR=%~dp0venv"

if not exist "%VENV_DIR%" (
    echo   [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo   [ERROR] Failed to create venv
        pause
        exit /b 1
    )
    echo   [OK] Virtual environment created
) else (
    echo   [OK] Virtual environment exists
)

REM Activate venv
call "%VENV_DIR%\Scripts\activate.bat"
echo   [OK] Virtual environment activated

REM ========== 3. Install Dependencies ==========
echo [3/4] Checking dependencies...

python -c "import DrissionPage" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] Installing dependencies (first time may take minutes)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo   [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    echo   [OK] Dependencies installed
) else (
    echo   [OK] All dependencies installed
)

REM ========== 4. Check Chrome ==========
echo [4/4] Checking Chrome browser...

set "CHROME_FOUND="

REM Check portable Chrome
if exist "%~dp0cloakbrowser-windows-x64\chrome.exe" (
    for %%A in ("%~dp0cloakbrowser-windows-x64\chrome.exe") do (
        if %%~zA gtr 1000 set "CHROME_FOUND=1"
    )
)

REM Check system Chrome
if not defined CHROME_FOUND (
    if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
)
if not defined CHROME_FOUND (
    if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
)

if defined CHROME_FOUND (
    echo   [OK] Chrome detected
) else (
    echo   [WARN] Chrome not found
    echo   Install from: https://www.google.com/chrome/
    echo.
)

REM ========== Select Mode ==========
echo.
echo ===================================================
echo   Select Mode:
echo     1) With Browser (visible window)
echo     2) Headless (no window, save resources)
echo ===================================================
set /p MODE_CHOICE=Enter [1/2] (default 1):

set "HEADLESS_FLAG="
set "MODE_LABEL=With Browser"

if "%MODE_CHOICE%"=="2" (
    set "HEADLESS_FLAG=--headless"
    set "MODE_LABEL=Headless"
)

echo   Selected: %MODE_LABEL%
echo.

REM ========== Start Bot ==========
echo ===================================================
echo   Starting Bot (%MODE_LABEL%)... Press Ctrl+C to stop
echo ===================================================
echo.

if exist "%~dp0zhipin_cookies.json" (
    echo   [INFO] Found saved cookies, will auto-login
) else (
    echo   [INFO] First time use - manual login required
    echo   [INFO] Browser will open, please login to BOSS Zhipin
)
echo.

python -m boss_bot %HEADLESS_FLAG%

REM ========== Exit ==========
echo.
echo ===================================================
echo   Bot stopped
echo ===================================================
echo.
echo Press any key to exit...
pause >nul
