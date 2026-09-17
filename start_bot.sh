#!/usr/bin/env bash
# ============================================================
#  BOSS Auto-Reply Bot - macOS / Linux 一键启动
#  自动完成: 检测 Python → 创建虚拟环境 → 安装依赖 → 启动
# ============================================================

cd "$(dirname "$0")"

echo "==================================================="
echo "  BOSS Auto-Reply Bot - 一键启动"
echo "==================================================="
echo ""

# ── 检查 Python ──
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "  [ERROR] 未找到 Python，请先安装 Python 3.8+"
    echo "  下载地址: https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)
echo "  Python: $PY_VERSION"

# ── 创建虚拟环境 ──
if [ ! -d "venv" ]; then
    echo "  创建虚拟环境..."
    if ! $PYTHON -m venv venv 2>/dev/null; then
        echo "  [ERROR] 创建虚拟环境失败"
        exit 1
    fi
    echo "  ✅ 虚拟环境创建完成"
fi

# ── 激活虚拟环境 ──
source venv/bin/activate

# ── 安装依赖 ──
echo "  安装依赖..."
pip install -r requirements.txt -q 2>/dev/null
echo "  ✅ 依赖安装完成"

# ── 选择运行模式 ──
echo ""
echo "  请选择运行模式："
echo "    1) 有头模式（显示浏览器窗口，可手动操作）"
echo "    2) 无头模式（不显示浏览器窗口，节省资源）"
echo ""
read -p "  请输入选项 [1/2]（默认 1）: " MODE_CHOICE

case "$MODE_CHOICE" in
    2)
        HEADLESS_FLAG="--headless"
        MODE_LABEL="无头模式"
        ;;
    *)
        HEADLESS_FLAG=""
        MODE_LABEL="有头模式"
        ;;
esac

echo "  已选择: $MODE_LABEL"
echo ""

# ── 启动 ──
echo "  ========================================"
echo "  🚀 启动地址: http://127.0.0.1:5001"
echo "  📋 运行模式: $MODE_LABEL"
echo "  ========================================"

python -m flask_version.app &
SERVER_PID=$!

# Ctrl+C 时终止后台服务
trap "kill $SERVER_PID 2>/dev/null; exit" INT TERM

# 等待服务就绪
sleep 2

# 自动打开浏览器（有头模式才打开管理界面）
if [ "$MODE_LABEL" = "有头模式" ]; then
    echo "  🌐 正在打开浏览器..."
    open "http://127.0.0.1:5001" 2>/dev/null || xdg-open "http://127.0.0.1:5001" 2>/dev/null || true
fi

# 等待服务端退出
wait $SERVER_PID
