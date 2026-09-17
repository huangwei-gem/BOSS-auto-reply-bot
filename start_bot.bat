@echo off
setlocal

title BOSS Auto-Reply Bot
cd /d "%~dp0"

echo ===================================================
echo   BOSS Auto-Reply Bot
echo ===================================================
echo.

REM === 1. Check Python ===
echo [1/4] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Install from: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version') do echo [OK] Python %%v

REM === 2. Virtual Environment ===
echo [2/4] Checking virtual environment...
if not exist venv (
    echo [INFO] Creating venv...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo [OK] venv activated

REM === 3. Dependencies ===
echo [3/4] Checking dependencies...
python -c "import DrissionPage" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] pip install failed
        pause
        exit /b 1
    )
)
echo [OK] Dependencies OK

REM === 4. Chrome ===
echo [4/4] Checking Chrome...
set CHROME_OK=0
if exist "cloakbrowser-windows-x64\chrome.exe" set CHROME_OK=1
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set CHROME_OK=1
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set CHROME_OK=1
if "%CHROME_OK%"=="1" (
    echo [OK] Chrome found
) else (
    echo [WARN] Chrome not found
)

REM === Select Mode ===
echo.
echo Select mode:
echo   1) With browser window
echo   2) Headless
set /p MODE="Enter [1/2] (default 1): "
set HEADLESS=
if "%MODE%"=="2" set HEADLESS=--headless

echo.
echo Starting bot...
echo.

python -m boss_bot %HEADLESS%

echo.
echo Bot stopped. Press any key to exit.
pause >nul
