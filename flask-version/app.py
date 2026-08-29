"""
BOSS 自动回复机器人 - Flask Web 管理界面

提供 Web 界面管理机器人：
- 实时状态监控
- 未读消息列表
- 实时操作日志 + 日志文件查看
- 一键启动/停止
- 配置和规则查看
- 浏览器测试报告
"""

import os
import sys
import json
import logging
import threading
import time
import glob
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

# 项目根目录
PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = PROJECT_ROOT / "logs"

# 全局状态
bot_state = {
    "running": False,
    "logged_in": False,
    "total_replies": 0,
    "total_resumes": 0,
    "last_check": None,
    "current_chat": None,
}

# 日志存储
log_buffer = []
MAX_LOGS = 500

# 机器人线程
bot_thread = None


class WebLogHandler(logging.Handler):
    """将日志写入内存缓冲区，供前端显示"""

    def emit(self, record):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage()
        }
        log_buffer.append(entry)
        if len(log_buffer) > MAX_LOGS:
            log_buffer.pop(0)


# 同时写入日志文件
def setup_file_logger():
    """设置日志文件输出，带自动清理"""
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    file_handler.setFormatter(formatter)

    # 自动清理：只保留最近7天的日志
    cleanup_old_logs()

    return file_handler


def cleanup_old_logs():
    """清理7天前的日志文件"""
    if not LOG_DIR.exists():
        return
    now = time.time()
    max_age = 7 * 24 * 3600  # 7天
    for log_file in LOG_DIR.glob("*.log"):
        if now - log_file.stat().st_mtime > max_age:
            try:
                log_file.unlink()
            except:
                pass


# 配置日志
web_handler = WebLogHandler()
web_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(web_handler)
logging.getLogger().addHandler(setup_file_logger())
logging.getLogger().setLevel(logging.INFO)


def run_bot_loop():
    """机器人主循环（在后台线程运行）"""
    from page_handler import BossChatHandler
    from reply_engine import ReplyEngine
    from config import CHECK_INTERVAL

    global bot_state

    logger = logging.getLogger("bot")
    handler = BossChatHandler()
    engine = ReplyEngine()

    try:
        # 登录
        logger.info("正在检查登录状态...")
        handler.login()
        bot_state["logged_in"] = True
        logger.info("登录成功")

        while bot_state["running"]:
            try:
                # 获取未读聊天
                handler.go_to_chat()
                unread_chats = handler.get_unread_chats()
                bot_state["last_check"] = datetime.now().strftime("%H:%M:%S")

                if unread_chats:
                    logger.info(f"发现 {len(unread_chats)} 个未读会话")

                    for chat_info in unread_chats:
                        if not bot_state["running"]:
                            break

                        name = chat_info["name"]
                        bot_state["current_chat"] = name
                        logger.info(f"处理与 [{name}] 的聊天")

                        # 进入聊天
                        handler.enter_chat(chat_info)

                        # 读取消息
                        messages = handler.read_latest_messages(5)
                        if messages:
                            # 找最后一条对方发的消息
                            latest = None
                            for msg in reversed(messages):
                                if not msg["is_mine"]:
                                    latest = msg["text"]
                                    break

                            if latest:
                                logger.info(f"对方消息: {latest[:50]}...")

                                # 获取回复
                                action, content = engine.get_reply(latest)

                                if action == "resume":
                                    handler.send_resume()
                                    bot_state["total_resumes"] += 1
                                    logger.info("已发送简历")
                                elif action == "text" and content:
                                    handler.send_text(content)
                                    bot_state["total_replies"] += 1
                                    logger.info(f"已回复: {content[:30]}...")

                                engine.record_reply()

                        engine.wait_human_delay()

                bot_state["current_chat"] = None

            except Exception as e:
                logger.error(f"运行时错误: {e}")

            time.sleep(CHECK_INTERVAL)

    except Exception as e:
        logger.error(f"机器人异常: {e}")
    finally:
        handler.close()
        bot_state["running"] = False
        logger.info("机器人已停止")


# ===================== API 路由 =====================

@app.route("/")
def index():
    """主页"""
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """获取当前状态"""
    return jsonify({
        "success": True,
        "data": bot_state
    })


@app.route("/api/logs")
def api_logs():
    """获取日志"""
    limit = request.args.get("limit", 100, type=int)
    return jsonify({
        "success": True,
        "data": log_buffer[-limit:]
    })


@app.route("/api/start", methods=["POST"])
def api_start():
    """启动机器人"""
    global bot_thread, bot_state

    if bot_state["running"]:
        return jsonify({"success": False, "message": "机器人已在运行"})

    bot_state["running"] = True
    bot_thread = threading.Thread(target=run_bot_loop, daemon=True)
    bot_thread.start()

    logging.getLogger("bot").info("机器人已启动")
    return jsonify({"success": True, "message": "机器人已启动"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    """停止机器人"""
    global bot_state

    if not bot_state["running"]:
        return jsonify({"success": False, "message": "机器人未在运行"})

    bot_state["running"] = False
    logging.getLogger("bot").info("机器人停止中...")
    return jsonify({"success": True, "message": "机器人正在停止"})


@app.route("/api/unread")
def api_unread():
    """获取未读消息列表"""
    from page_handler import BossChatHandler

    try:
        handler = BossChatHandler()
        handler.go_to_chat()
        unread = handler.get_unread_chats()
        handler.close()

        return jsonify({
            "success": True,
            "data": [{"name": c["name"], "preview": c["preview"][:100], "count": c["unread_count"]} for c in unread]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/config", methods=["GET"])
def api_config():
    """获取配置"""
    from config import CHECK_INTERVAL, MAX_REPLIES_PER_HOUR, REPLY_RULES

    return jsonify({
        "success": True,
        "data": {
            "check_interval": CHECK_INTERVAL,
            "max_replies_per_hour": MAX_REPLIES_PER_HOUR,
            "rules_count": len(REPLY_RULES),
            "rules": {k: (v if v != "send_resume" else "发送简历") for k, v in REPLY_RULES.items()}
        }
    })


@app.route("/api/logfiles")
def api_logfiles():
    """获取日志文件列表"""
    LOG_DIR.mkdir(exist_ok=True)
    files = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        result.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify({"success": True, "data": result})


@app.route("/api/logfile/<path:filename>")
def api_logfile(filename):
    """获取指定日志文件内容"""
    # 安全校验：防止目录遍历
    if "/" in filename or "\\" in filename or ".." in filename:
        return jsonify({"success": False, "message": "Invalid filename"})
    log_file = LOG_DIR / filename
    if not log_file.exists():
        return jsonify({"success": False, "message": "File not found"})
    try:
        content = log_file.read_text(encoding="utf-8")
        # 只返回最后1000行
        lines = content.split("\n")
        if len(lines) > 1000:
            lines = lines[-1000:]
        return jsonify({"success": True, "data": "\n".join(lines)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/test", methods=["POST"])
def api_test():
    """运行浏览器测试"""
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "test_full_run.py")],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(PROJECT_ROOT)
        )
        return jsonify({
            "success": result.returncode == 0,
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "message": "Test timed out (120s)"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


def main():
    """启动 Flask 应用"""
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
