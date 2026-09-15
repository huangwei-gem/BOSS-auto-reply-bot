#!/usr/bin/env bash
# ============================================================
#  BOSS Auto-Reply Bot - 内网穿透一键启动 (macOS / Linux)
#  自动完成: 启动 Flask → 启动 cloudflared → 输出公网 URL
# ============================================================

cd "$(dirname "$0")"

echo "==================================================="
echo "  BOSS Auto-Reply Bot - 内网穿透启动"
echo "==================================================="
echo ""

# ── 检查 cloudflared ──
CLOUDFLARED=""
for path in "$(command -v cloudflared 2>/dev/null)" "/usr/local/bin/cloudflared" "$HOME/.local/bin/cloudflared"; do
    if [ -x "$path" ] && "$path" --version >/dev/null 2>&1; then
        CLOUDFLARED="$path"
        break
    fi
done

if [ -z "$CLOUDFLARED" ]; then
    echo "  [ERROR] 未找到 cloudflared"
    echo ""
    echo "  安装方式："
    echo "    macOS:  brew install cloudflared"
    echo "    Linux:  sudo apt install cloudflared"
    echo "    手动:   参考项目目录下 TUNNEL_GUIDE.md"
    echo ""
    exit 1
fi

echo "  cloudflared: $($CLOUDFLARED --version 2>&1)"
echo ""

# ── 检查 Flask 是否已在运行 ──
FLASK_RUNNING=false
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/api/status --connect-timeout 2 | grep -q "200"; then
    FLASK_RUNNING=true
    echo "  Flask 已在运行 (http://localhost:5001)"
else
    echo "  Flask 未运行，正在启动..."
    
    # 激活虚拟环境
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    
    # 选择运行模式
    echo ""
    echo "  请选择运行模式："
    echo "    1) 有头模式（显示浏览器窗口）"
    echo "    2) 无头模式（不显示浏览器窗口，节省资源）"
    echo ""
    read -p "  请输入选项 [1/2]（默认 2）: " MODE_CHOICE
    
    case "$MODE_CHOICE" in
        1) HEADLESS_FLAG="" ;;
        *) HEADLESS_FLAG="--headless" ;;
    esac
    
    # 启动 Flask
    python flask-version/app.py $HEADLESS_FLAG &
    FLASK_PID=$!
    
    # 等待 Flask 就绪
    echo -n "  等待 Flask 启动"
    for i in $(seq 1 15); do
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/api/status --connect-timeout 1 | grep -q "200"; then
            echo " OK"
            FLASK_RUNNING=true
            break
        fi
        echo -n "."
        sleep 1
    done
    echo ""
    
    if [ "$FLASK_RUNNING" = false ]; then
        echo "  [ERROR] Flask 启动失败"
        kill $FLASK_PID 2>/dev/null
        exit 1
    fi
fi

echo ""

# ── 选择隧道模式 ──
echo "  请选择隧道模式："
echo "    1) 快速模式（临时 URL，无需域名，地址每次重启会变）"
echo "    2) 正式模式（绑定域名，固定地址，需要 Cloudflare 账号）"
echo ""
read -p "  请输入选项 [1/2]（默认 1）: " TUNNEL_CHOICE

echo ""
echo "  ========================================"

case "$TUNNEL_CHOICE" in
    2)
        echo "  正式模式启动中..."
        echo "  确保 ~/.cloudflared/config.yml 已配置"
        echo "  ========================================"
        echo ""
        $CLOUDFLARED tunnel run boss-bot
        ;;
    *)
        echo "  快速模式启动中..."
        echo "  ========================================"
        echo ""
        # 启动隧道，捕获输出中的 URL
        $CLOUDFLARED tunnel --url http://localhost:5001 2>&1 | while IFS= read -r line; do
            echo "$line"
            # 检测到 URL 行后额外提示
            if echo "$line" | grep -q "trycloudflare.com"; then
                echo ""
                echo "  ========================================"
                echo "  公网地址已生成！在任意设备浏览器中打开上述 URL"
                echo "  按 Ctrl+C 停止隧道和机器人"
                echo "  ========================================"
            fi
        done
        ;;
esac

# 清理
echo ""
echo "  正在关闭..."
if [ -n "$FLASK_PID" ]; then
    kill $FLASK_PID 2>/dev/null
fi
echo "  已停止"