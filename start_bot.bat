@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

title BOSS Auto-Reply Bot - 一键启动

cd /d "%~dp0"

echo ===================================================
echo   BOSS Auto-Reply Bot - 一键启动
echo ===================================================
echo.

REM ========== 1. 检查 Python ==========
echo [1/4] 检查 Python...

set "PYTHON_CMD="
set "PYTHON_VERSION="

REM 检查 python
for %%P in (python3 python py) do (
    %%P --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2" %%v in ('%%P --version 2^>^&1') do (
            set "VER=%%v"
            REM 检查版本 >= 3.8
            for /f "tokens=1,2 delims=." %%a in ("%%v") do (
                if %%a geq 3 (
                    if %%b geq 8 (
                        set "PYTHON_CMD=%%P"
                        set "PYTHON_VERSION=%%v"
                        goto :python_found
                    )
                )
            )
        )
    )
)

:python_found
if "%PYTHON_CMD%"=="" (
    echo   [ERROR] 未找到 Python 3.8+
    echo.
    echo   请安装 Python:
    echo     访问: https://www.python.org/downloads/
    echo     安装时勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo   [OK] Python %PYTHON_VERSION%

REM ========== 2. 创建/激活虚拟环境 ==========
echo [2/4] 检查虚拟环境...

set "VENV_DIR=%~dp0venv"

if not exist "%VENV_DIR%" (
    echo   [INFO] 虚拟环境不存在，正在创建...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo   [ERROR] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo   [OK] 虚拟环境创建成功
) else (
    echo   [OK] 虚拟环境已存在
)

REM 激活虚拟环境
call "%VENV_DIR%\Scripts\activate.bat"
echo   [OK] 虚拟环境已激活

REM ========== 3. 安装依赖 ==========
echo [3/4] 检查依赖...

python -c "import DrissionPage" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] 正在安装依赖 (首次需要几分钟)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo   [ERROR] 依赖安装失败
        pause
        exit /b 1
    )
    echo   [OK] 依赖安装完成
) else (
    echo   [OK] 所有依赖已安装
)

REM ========== 4. 检查 Chrome ==========
echo [4/4] 检查 Chrome 浏览器...

set "CHROME_FOUND="

REM 检查便携版
if exist "%~dp0cloakbrowser-windows-x64\chrome.exe" (
    for %%A in ("%~dp0cloakbrowser-windows-x64\chrome.exe") do (
        if %%~zA gtr 1000 set "CHROME_FOUND=1"
    )
)

REM 检查系统 Chrome
if not defined CHROME_FOUND (
    if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
)
if not defined CHROME_FOUND (
    if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
)

if defined CHROME_FOUND (
    echo   [OK] Chrome 已检测到
) else (
    echo   [WARN] 未检测到 Chrome 浏览器
    echo   请安装 Google Chrome: https://www.google.com/chrome/
    echo.
)

REM ========== 启动机器人 ==========
echo.
echo ===================================================
echo   启动机器人... 按 Ctrl+C 停止
echo ===================================================
echo.

if exist "%~dp0zhipin_cookies.json" (
    echo   [INFO] 发现已保存的 Cookie，将尝试自动登录
) else (
    echo   [INFO] 首次使用需要手动登录
    echo   [INFO] 启动后浏览器窗口会弹出，请在 BOSS 直聘登录
)
echo.

python main.py

echo.
echo ===================================================
echo   机器人已停止
echo ===================================================
echo.
pause
