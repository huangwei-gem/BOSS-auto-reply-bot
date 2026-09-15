@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

title BOSS Auto-Reply Bot - 内网穿透启动

cd /d "%~dp0"

echo ===================================================
echo   BOSS Auto-Reply Bot - 内网穿透启动
echo ===================================================
echo.

REM ========== 1. 检查 cloudflared ==========
set "CLOUDFLARED_CMD="

REM 检查 PATH 中的 cloudflared
where cloudflared >nul 2>&1
if !errorlevel! equ 0 (
    set "CLOUDFLARED_CMD=cloudflared"
) else (
    REM 检查项目目录下的 cloudflared.exe
    if exist "%~dp0cloudflared.exe" (
        set "CLOUDFLARED_CMD=%~dp0cloudflared.exe"
    ) else (
        REM 检查常见安装路径
        if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
            set "CLOUDFLARED_CMD=C:\Program Files (x86)\cloudflared\cloudflared.exe"
        ) else if exist "C:\Program Files\cloudflared\cloudflared.exe" (
            set "CLOUDFLARED_CMD=C:\Program Files\cloudflared\cloudflared.exe"
        )
    )
)

if "!CLOUDFLARED_CMD!"=="" (
    echo   [ERROR] 未找到 cloudflared
    echo.
    echo   安装方式：
    echo     1. winget install --id Cloudflare.cloudflared
    echo     2. 或从 GitHub 下载 cloudflared-windows-amd64.exe
    echo     3. 参考 TUNNEL_GUIDE.md 详细教程
    echo.
    pause
    exit /b 1
)

echo   [OK] cloudflared 已检测到
echo.

REM ========== 2. 检查 Flask 是否在运行 ==========
set "FLASK_RUNNING=0"

curl -s -o nul -w "%%{http_code}" http://localhost:5001/api/status --connect-timeout 2 >nul 2>&1
if !errorlevel! equ 0 (
    REM 检查返回是否为 200
    for /f %%c in ('curl -s -o nul -w "%%{http_code}" http://localhost:5001/api/status --connect-timeout 2 2^>nul') do (
        if "%%c"=="200" set "FLASK_RUNNING=1"
    )
)

if "!FLASK_RUNNING!"=="1" (
    echo   [OK] Flask 已在运行 (http://localhost:5001)
) else (
    echo   [INFO] Flask 未运行，正在启动...
    
    REM 激活虚拟环境
    if exist "%~dp0venv\Scripts\activate.bat" (
        call "%~dp0venv\Scripts\activate.bat"
    )
    
    REM 选择运行模式
    echo.
    echo   请选择运行模式：
    echo     1) 有头模式（显示浏览器窗口）
    echo     2) 无头模式（不显示浏览器窗口，节省资源）
    set /p MODE_CHOICE=请输入选项 [1/2]（默认 2）:
    
    set "HEADLESS_FLAG=--headless"
    if "!MODE_CHOICE!"=="1" set "HEADLESS_FLAG="
    
    REM 启动 Flask（后台）
    echo   [INFO] 正在启动 Flask...
    start /b python flask-version\app.py !HEADLESS_FLAG!
    
    REM 等待 Flask 就绪
    set "WAIT_COUNT=0"
    :wait_flask
    set /a WAIT_COUNT+=1
    if !WAIT_COUNT! gtr 15 (
        echo   [ERROR] Flask 启动超时
        pause
        exit /b 1
    )
    timeout /t 1 /nobreak >nul
    for /f %%c in ('curl -s -o nul -w "%%{http_code}" http://localhost:5001/api/status --connect-timeout 1 2^>nul') do (
        if "%%c"=="200" (
            echo   [OK] Flask 启动成功
            set "FLASK_RUNNING=1"
            goto :flask_ready
        )
    )
    goto :wait_flask
)

:flask_ready
echo.

REM ========== 3. 选择隧道模式 ==========
echo   请选择隧道模式：
echo     1) 快速模式（临时 URL，无需域名，地址每次重启会变）
echo     2) 正式模式（绑定域名，固定地址，需要 Cloudflare 账号）
set /p TUNNEL_CHOICE=请输入选项 [1/2]（默认 1）:

echo.
echo ===================================================

if "!TUNNEL_CHOICE!"=="2" (
    echo   正式模式启动中...
    echo   确保 %%USERPROFILE%%\.cloudflared\config.yml 已配置
    echo ===================================================
    echo.
    "!CLOUDFLARED_CMD!" tunnel run boss-bot
) else (
    echo   快速模式启动中...
    echo ===================================================
    echo.
    "!CLOUDFLARED_CMD!" tunnel --url http://localhost:5001
)

echo.
echo ===================================================
echo   隧道已关闭
echo ===================================================
pause