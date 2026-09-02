#!/usr/bin/env bash
# ============================================================
#  BOSS Auto-Reply Bot - macOS / Linux 一键启动
#  自动完成: 检测 Python → 创建虚拟环境 → 安装依赖 → 启动
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================================="
echo "  BOSS Auto-Reply Bot - 一键启动"
echo "==================================================="
echo ""

# ========== 1. 检查 Python ==========
echo "[1/4] 检查 Python..."

find_python() {
    # 优先 python3，其次 python
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            # 检查版本 >= 3.8
            version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 8 ] 2>/dev/null; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python)

if [ -z "$PYTHON" ]; then
    echo "  [ERROR] 未找到 Python 3.8+"
    echo ""
    echo "  请安装 Python:"
    echo "    macOS:  brew install python3"
    echo "    Linux:  sudo apt install python3 python3-venv"
    echo "    或访问: https://www.python.org/downloads/"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

PYTHON_FULL=$("$PYTHON" -c "import sys; print(sys.executable)")
PYTHON_VERSION=$("$PYTHON" --version 2>&1)
echo "  [OK] $PYTHON_VERSION ($PYTHON_FULL)"

# ========== 2. 创建/激活虚拟环境 ==========
echo "[2/4] 检查虚拟环境..."

VENV_DIR="$SCRIPT_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "  [INFO] 虚拟环境不存在，正在创建..."
    "$PYTHON" -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "  [ERROR] 创建虚拟环境失败"
        echo "  尝试安装 venv 模块: sudo apt install python3-venv"
        read -p "按回车键退出..."
        exit 1
    fi
    echo "  [OK] 虚拟环境创建成功"
else
    echo "  [OK] 虚拟环境已存在"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
echo "  [OK] 虚拟环境已激活: $VIRTUAL_ENV"

# ========== 3. 安装依赖 ==========
echo "[3/4] 检查依赖..."

# 检查关键依赖是否已安装
check_dep() {
    python -c "import $1" 2>/dev/null
}

MISSING_DEPS=""

if ! check_dep "DrissionPage"; then
    MISSING_DEPS="$MISSING_DEPS DrissionPage"
fi

if ! check_dep "openai"; then
    MISSING_DEPS="$MISSING_DEPS openai"
fi

if [ -n "$MISSING_DEPS" ]; then
    echo "  [INFO] 缺少依赖:$MISSING_DEPS"
    echo "  [INFO] 正在安装依赖 (首次需要几分钟)..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "  [ERROR] 依赖安装失败"
        read -p "按回车键退出..."
        exit 1
    fi
    echo "  [OK] 依赖安装完成"
else
    echo "  [OK] 所有依赖已安装"
fi

# ========== 4. 检查 Chrome ==========
echo "[4/4] 检查 Chrome 浏览器..."

CHROME_FOUND=""

# macOS
if [ -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    CHROME_FOUND="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
fi

# Linux
if [ -z "$CHROME_FOUND" ]; then
    for cmd in google-chrome chromium-browser chromium; do
        if command -v "$cmd" &>/dev/null; then
            CHROME_FOUND="$cmd"
            break
        fi
    done
fi

if [ -n "$CHROME_FOUND" ]; then
    echo "  [OK] Chrome: $CHROME_FOUND"
else
    echo "  [WARN] 未检测到 Chrome 浏览器"
    echo "  请安装 Google Chrome: https://www.google.com/chrome/"
    echo ""
fi

# ========== 启动机器人 ==========
echo ""
echo "==================================================="
echo "  启动机器人... 按 Ctrl+C 停止"
echo "==================================================="
echo ""

# 检查 Cookie
if [ -f "$SCRIPT_DIR/zhipin_cookies.json" ]; then
    echo "  [INFO] 发现已保存的 Cookie，将尝试自动登录"
else
    echo "  [INFO] 首次使用需要手动登录"
    echo "  [INFO] 启动后浏览器窗口会弹出，请在 BOSS 直聘登录"
fi
echo ""

# 启动
python main.py

echo ""
echo "==================================================="
echo "  机器人已停止"
echo "==================================================="
echo ""
read -p "按回车键退出..."
