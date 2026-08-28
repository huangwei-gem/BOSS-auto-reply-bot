"""
BOSS 自动回复机器人 - Flask Web 管理界面

提供 Web 界面管理机器人：
- 查看登录状态
- 查看未读消息列表
- 手动触发回复
- 查看操作日志
- 配置管理
"""

import os
import sys
import json
import logging
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

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


# 配置日志
web_handler = WebLogHandler()
web_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(web_handler)


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


def main():
    """启动 Flask 应用"""
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
