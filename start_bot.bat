@echo off
chcp 65001 >nul
title BOSS Auto-Reply Bot - DrissionPage Version

echo ===================================================
echo   BOSS Auto-Reply Bot - DrissionPage Version
echo ===================================================
echo.

REM === Check Python ===
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)
echo [OK] Python detected.

REM === Check dependencies ===
echo Checking dependencies...
python -c "import DrissionPage" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] Installing DrissionPage...
    pip install DrissionPage
)
python -c "import openai" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] Installing openai...
    pip install openai
)
echo [OK] Dependencies ready.
echo.

REM === Check API Key ===
if "%AI_API_KEY_1%"=="" (
    echo [WARN] AI_API_KEY_1 is not set. AI fallback replies will be disabled.
    echo        To enable AI replies, set the environment variable:
    echo        set AI_API_KEY_1=your_api_key
    echo.
)

REM === Check cookies ===
if exist "zhipin_cookies.json" (
    echo [OK] Saved cookies found. Auto-login will be attempted.
) else (
    echo [INFO] No saved cookies. Manual login required on first run.
    echo        A browser window will open — please log in to BOSS.
)
echo.

REM === Start the bot ==================================
echo Starting bot... Press Ctrl+C to stop.
echo ---------------------------------------------------
echo.

python main.py

echo.
echo ---------------------------------------------------
echo Bot stopped.
pause
