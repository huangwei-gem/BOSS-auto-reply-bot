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
import warnings
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file

# 抑制 urllib3 LibreSSL 警告（macOS 自带 Python 使用 LibreSSL 而非 OpenSSL）
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

# 关闭 Flask 默认的请求日志（那些 GET /api/... 200 的废话）
logging.getLogger('werkzeug').setLevel(logging.ERROR)

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
    "needs_login": False,
    "total_replies": 0,
    "total_resumes": 0,
    "last_check": None,
    "current_chat": None,
}

# 全局 handler 引用（用于手动保存 cookie）
_bot_handler = None

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



# 配置日志：控制台/文件走 logging_setup（详细格式），Web 流走 WebLogHandler
from logging_setup import setup_logging, cleanup_old_logs
setup_logging()

web_handler = WebLogHandler()
web_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(web_handler)
logging.getLogger().setLevel(logging.INFO)

from event_logger import get_event_logger


def run_bot_loop():
    """机器人主循环（在后台线程运行）"""
    from page_handler import BossChatHandler
    from reply_engine import ReplyEngine
    from state_store import StateStore
    from stats import Stats
    from notify import Notifier
    from config import CHECK_INTERVAL, CONTEXT_MESSAGE_COUNT, PAUSE_ON_IMPORTANT, RESUME_SEND_ONCE

    global bot_state, _bot_handler

    logger = logging.getLogger("bot")
    events = get_event_logger()
    handler = BossChatHandler()
    _bot_handler = handler
    engine = ReplyEngine()
    state = StateStore()
    stats = Stats()
    notifier = Notifier()

    try:
        # 登录
        logger.info("正在检查登录状态...")
        logged_in = handler.login()
        if logged_in:
            bot_state["logged_in"] = True
            bot_state["needs_login"] = False
            logger.info("登录成功")
        else:
            # 需要手动登录 — 通知前端显示按钮
            bot_state["needs_login"] = True
            bot_state["logged_in"] = False
            logger.info("等待用户在浏览器登录后点击「我已登录」按钮...")
            # 等待用户点击按钮（confirm_and_save 会设置 _login_event）
            if not handler.wait_for_login_confirm(timeout=300):
                logger.error("登录超时")
                bot_state["running"] = False
                return
            bot_state["needs_login"] = False
            bot_state["logged_in"] = True
            logger.info("用户已确认登录，Cookie 已保存")

        while bot_state["running"]:
            try:
                # 健康检查：登录失效 / 验证码
                health = handler.check_health()
                if health == "need_login":
                    logger.error("登录已失效，请重新登录！")
                    notifier.send_notification("登录失效", "BOSS 直聘登录已失效，请重新登录。", "error")
                    bot_state["logged_in"] = False
                    bot_state["needs_login"] = True
                    time.sleep(30)
                    continue
                if health == "captcha":
                    logger.warning("检测到安全验证/验证码，暂停 60 秒...")
                    notifier.send_notification("安全验证", "检测到安全验证/验证码，请人工处理！", "warning")
                    time.sleep(60)
                    continue

                # 频率限制
                if not engine.can_reply():
                    logger.warning("已达到每小时回复上限，等待...")
                    time.sleep(60)
                    continue

                # 人工接管模式提示
                if state.is_paused():
                    info = state.pause_info()
                    logger.info(f"人工接管模式中（{info.get('reason', '')}），仅监控不回复...")

                # 获取未读聊天
                handler.go_to_chat()
                unread_chats = handler.get_unread_chats()
                bot_state["last_check"] = datetime.now().strftime("%H:%M:%S")

                if unread_chats:
                    logger.info(f"发现 {len(unread_chats)} 个未读会话")
                else:
                    pass

                    for chat_info in unread_chats:
                        if not bot_state["running"]:
                            break

                        name = chat_info["name"]
                        bot_state["current_chat"] = name

                        # 人工接管模式：不自动回复
                        if state.is_paused():
                            logger.info("人工接管模式中，跳过自动回复")
                            events.event("skip", chat=name, reason="paused")
                            break

                        logger.info(f"处理与 [{name}] 的聊天")

                        # 进入聊天（带切换校验）
                        if not handler.enter_chat(chat_info):
                            logger.warning(f"会话 [{name}] 切换校验失败，本次跳过")
                            events.event("skip", chat=name, reason="switch_verify_failed")
                            continue

                        # 读取消息（多轮上下文）
                        messages = handler.read_latest_messages(CONTEXT_MESSAGE_COUNT)
                        if not messages:
                            logger.info("未读取到消息，跳过")
                            events.event("skip", chat=name, reason="no_messages")
                        else:
                            # 找最后一条对方发的消息（is_mine=False 表示对方）
                            latest = None
                            for msg in reversed(messages):
                                if not msg.get("is_mine"):
                                    latest = msg.get("text", "")
                                    break

                            if not latest:
                                logger.info("最新消息是自己发的，无需回复")
                                events.event("skip", chat=name, reason="latest_is_mine")
                            else:
                                logger.info(f"对方消息: {latest[:50]}...")

                                # 去重检查
                                if state.was_handled(name, latest):
                                    logger.info("该消息已处理过，跳过")
                                    stats.record_skip()
                                    events.event("skip", chat=name, reason="duplicate",
                                                 message=latest[:120])
                                    continue

                                boss_name = handler.get_boss_name()
                                job_name = handler.get_job_name()

                                # 获取回复
                                action, content, meta = engine.get_reply(
                                    messages, boss_name, job_name, chat_name=name)

                                # 重要事件：通知 + 可选转人工
                                if notifier.notify_if_important(
                                        latest, chat_name=name, job_name=job_name,
                                        intent=meta.get("intent", "")):
                                    stats.record_important()
                                    if PAUSE_ON_IMPORTANT:
                                        state.pause(reason=f"收到重要消息: {latest[:50]}", chat_name=name)
                                        notifier.send_notification(
                                            "机器人已暂停，转人工模式",
                                            "检测到重要消息，自动回复已暂停。",
                                            "info")
                                        logger.warning("已切换为人工接管模式")

                                # 简历去重降级
                                if action == "resume" and RESUME_SEND_ONCE and state.resume_sent(name):
                                    from config import RESUME_DUPLICATE_REPLY
                                    logger.info("该会话已发送过简历，降级为文字提醒")
                                    action, content = "text", RESUME_DUPLICATE_REPLY
                                    meta["source"] = "intent"

                                # 执行回复
                                if action == "resume":
                                    engine.wait_human_delay()
                                    if handler.send_resume():
                                        state.mark_resume_sent(name)
                                        stats.record_reply(source=meta.get("source", "rule"), action="resume")
                                        bot_state["total_resumes"] += 1
                                        events.event("send", chat=name, type="resume", ok=True)
                                        logger.info("已发送简历")
                                    else:
                                        # 简历发送失败：降级为文字告知 + 通知
                                        from config import RESUME_UNAVAILABLE_REPLY
                                        logger.warning("简历发送失败，降级为文字告知")
                                        engine.wait_human_delay()
                                        handler.send_text(RESUME_UNAVAILABLE_REPLY)
                                        notifier.send_notification(
                                            "简历发送失败",
                                            f"[{name}]（{job_name or '未知岗位'}）请求简历但发送失败，请检查 BOSS 账号的简历设置。",
                                            "warning")
                                        stats.record_reply(source=meta.get("source", "rule"), action="skip")
                                        events.event("send", chat=name, type="resume", ok=False,
                                                     fallback="text", message=latest[:120])
                                elif action == "text" and content:
                                    engine.wait_human_delay()
                                    if handler.send_text(content):
                                        stats.record_reply(source=meta.get("source", "rule"), action="text")
                                        bot_state["total_replies"] += 1
                                        events.event("send", chat=name, type="text", ok=True,
                                                     reply=content[:120], source=meta.get("source", ""))
                                        logger.info(f"已回复: {content[:30]}...")
                                    else:
                                        stats.record_reply(source=meta.get("source", "rule"), action="skip")
                                        events.event("send", chat=name, type="text", ok=False,
                                                     reply=content[:120])
                                else:
                                    logger.info("无合适回复，跳过")
                                    stats.record_reply(source=meta.get("source", "default"), action="skip")
                                    events.event("skip", chat=name, reason="no_action",
                                                 message=latest[:120])

                                # 记录已处理
                                state.mark_handled(name, latest, action or "none")
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
    from state_store import StateStore
    data = dict(bot_state)
    try:
        state = StateStore()
        data["paused"] = state.is_paused()
        if state.is_paused():
            data["pause_info"] = state.pause_info()
    except Exception:
        data["paused"] = False
    return jsonify({"success": True, "data": data})


@app.route("/api/notifications")
def api_notifications():
    """获取通知列表"""
    from notify import Notifier
    notifier = Notifier()
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"success": True, "data": notifier.records(limit)})


@app.route("/api/stats")
def api_stats():
    """获取统计数据"""
    from stats import Stats
    return jsonify({"success": True, "data": Stats().summary()})


@app.route("/api/pause", methods=["POST"])
def api_pause():
    """切换为人工接管模式（暂停自动回复）"""
    from state_store import StateStore
    data = request.get_json(silent=True) or {}
    StateStore().pause(reason=data.get("reason", "手动暂停"))
    logging.getLogger("bot").info("已切换为人工接管模式")
    return jsonify({"success": True, "message": "已暂停自动回复（人工接管模式）"})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    """恢复自动回复"""
    from state_store import StateStore
    resumed = StateStore().resume()
    msg = "已恢复自动回复" if resumed else "当前未处于暂停状态"
    logging.getLogger("bot").info(msg)
    return jsonify({"success": True, "message": msg})


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


@app.route("/api/cookie/status")
def api_cookie_status():
    """获取 Cookie 状态"""
    from config import COOKIE_FILE
    cookie_path = PROJECT_ROOT / COOKIE_FILE
    if cookie_path.exists():
        stat = cookie_path.stat()
        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            count = len(cookies)
        except Exception:
            count = 0
        return jsonify({
            "success": True,
            "data": {
                "exists": True,
                "count": count,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "path": COOKIE_FILE
            }
        })
    return jsonify({"success": True, "data": {"exists": False}})


@app.route("/api/cookie/save", methods=["POST"])
def api_cookie_save():
    """用户点击「我已登录」按钮 — 保存 Cookie 并通知机器人继续"""
    global bot_state, _bot_handler

    if _bot_handler is None:
        return jsonify({"success": False, "message": "浏览器未启动，请先启动机器人"})

    try:
        # 调用 confirm_and_save：导航到站 → 保存 Cookie → 触发事件唤醒机器人线程
        success = _bot_handler.confirm_and_save()
        if success:
            bot_state["needs_login"] = False
            bot_state["logged_in"] = True
            return jsonify({"success": True, "message": "Cookie 已保存，登录成功！"})
        else:
            return jsonify({"success": False, "message": "保存失败，请确认已在浏览器中完成登录"})
    except Exception as e:
        logging.getLogger("bot").error(f"confirm_and_save 异常: {e}")
        return jsonify({"success": False, "message": f"保存失败: {e}"})


@app.route("/api/cookie/clear", methods=["POST"])
def api_cookie_clear():
    """清除已保存的 Cookie"""
    from config import COOKIE_FILE
    cookie_path = PROJECT_ROOT / COOKIE_FILE
    if cookie_path.exists():
        try:
            cookie_path.unlink()
            return jsonify({"success": True, "message": "Cookie 已清除"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    return jsonify({"success": False, "message": "没有已保存的 Cookie"})


@app.route("/api/browser/detect")
def api_browser_detect():
    """检测可用浏览器列表"""
    from browser_launcher import detect_available_browsers, _preferred_browser
    browsers = detect_available_browsers()
    return jsonify({
        "success": True,
        "data": {
            "available": browsers,
            "selected": _preferred_browser or "",
            "default": next(iter(browsers), "")  # 按优先级第一个
        }
    })


@app.route("/api/browser/select", methods=["POST"])
def api_browser_select():
    """用户选择浏览器"""
    from browser_launcher import set_preferred_browser
    data = request.get_json()
    name = data.get("browser", "")
    if name not in ("chrome", "edge", "chromium"):
        return jsonify({"success": False, "message": "无效的浏览器类型"})
    set_preferred_browser(name)
    logging.getLogger("bot").info(f"用户选择浏览器: {name}")
    return jsonify({"success": True, "message": f"已选择 {name}"})


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


# ===================== 消息列表 API =====================

@app.route("/api/messages")
def api_messages():
    """获取所有会话消息列表"""
    from message_store import MessageStore
    store = MessageStore()
    return jsonify({"success": True, "data": store.get_chat_list()})


@app.route("/api/messages/<path:chat_name>")
def api_message_detail(chat_name):
    """获取某个会话的完整消息记录"""
    from message_store import MessageStore
    store = MessageStore()
    return jsonify({"success": True, "data": store.get_chat_detail(chat_name)})


# ===================== 提示词 & 配置可调 API =====================

@app.route("/api/prompts", methods=["GET"])
def api_prompts_get():
    """获取所有可调节的提示词和配置"""
    import config
    from prompts import _SYSTEM_RULES, USER_PROMPT_TEMPLATE

    return jsonify({
        "success": True,
        "data": {
            "system_rules": _SYSTEM_RULES,
            "user_prompt_template": USER_PROMPT_TEMPLATE,
            "reply_templates": {
                "SALARY_REPLY": config.SALARY_REPLY,
                "INTERVIEW_TIME_REPLY": config.INTERVIEW_TIME_REPLY,
                "JOB_CONTENT_REPLY": config.JOB_CONTENT_REPLY,
                "GREETING_REPLY": config.GREETING_REPLY,
                "DEFAULT_REPLY": config.DEFAULT_REPLY,
                "RESUME_DUPLICATE_REPLY": config.RESUME_DUPLICATE_REPLY,
                "RESUME_UNAVAILABLE_REPLY": config.RESUME_UNAVAILABLE_REPLY,
            },
            "reply_rules": config.REPLY_RULES,
            "importance_keywords": config.IMPORTANCE_KEYWORDS,
            "user_profile": config.USER_PROFILE,
            "ai_config": {
                "enable_ai": config.ENABLE_AI,
                "ai_models": config.AI_MODELS,
                "ai_base_url": config.AI_BASE_URL,
                "ai_backup_models": config.AI_BACKUP_MODELS,
                "ai_backup_base_url": config.AI_BACKUP_BASE_URL,
                "ai_fallback_model": config.AI_FALLBACK_MODEL,
                "ai_fallback_base_url": config.AI_FALLBACK_BASE_URL,
                "ai_max_tokens": config.AI_MAX_TOKENS,
                "ai_fail_action": config.AI_FAIL_ACTION,
            },
            "behavior_config": {
                "check_interval": config.CHECK_INTERVAL,
                "max_replies_per_hour": config.MAX_REPLIES_PER_HOUR,
                "context_message_count": config.CONTEXT_MESSAGE_COUNT,
                "pause_on_important": config.PAUSE_ON_IMPORTANT,
                "resume_send_once": config.RESUME_SEND_ONCE,
            },
        }
    })


@app.route("/api/prompts", methods=["POST"])
def api_prompts_save():
    """保存修改的提示词和配置"""
    data = request.get_json(silent=True) or {}
    saved = []

    # 保存话术模板到 config.py 的覆盖文件
    overrides_path = PROJECT_ROOT / "config_overrides.json"
    overrides = {}
    if overrides_path.exists():
        try:
            with open(overrides_path, "r", encoding="utf-8") as f:
                overrides = json.load(f)
        except Exception:
            pass

    if "reply_templates" in data:
        overrides["reply_templates"] = data["reply_templates"]
        saved.append("reply_templates")
    if "system_rules" in data:
        overrides["system_rules"] = data["system_rules"]
        saved.append("system_rules")
    if "user_prompt_template" in data:
        overrides["user_prompt_template"] = data["user_prompt_template"]
        saved.append("user_prompt_template")
    if "importance_keywords" in data:
        overrides["importance_keywords"] = data["importance_keywords"]
        saved.append("importance_keywords")
    if "user_profile" in data:
        overrides["user_profile"] = data["user_profile"]
        # 同步保存到 user_profile.json
        try:
            with open(PROJECT_ROOT / "user_profile.json", "w", encoding="utf-8") as f:
                json.dump(data["user_profile"], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.getLogger("bot").error(f"保存 user_profile.json 失败: {e}")
        saved.append("user_profile")

    try:
        with open(overrides_path, "w", encoding="utf-8") as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2)
        logging.getLogger("bot").info(f"配置已保存: {saved}")
        return jsonify({"success": True, "message": f"已保存: {', '.join(saved)}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# ===================== 自我优化 API =====================

@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    """触发自我优化迭代"""
    from self_optimizer import SelfOptimizer
    opt = SelfOptimizer()
    result = opt.analyze_and_optimize()
    return jsonify({"success": True, "data": result})


@app.route("/api/optimize/history")
def api_optimize_history():
    """获取优化历史"""
    from self_optimizer import SelfOptimizer
    opt = SelfOptimizer()
    return jsonify({"success": True, "data": opt.get_optimization_history()})


# ===================== 多账号管理 API =====================

@app.route("/api/accounts")
def api_accounts_list():
    """获取所有账号列表"""
    from account_manager import AccountManager
    mgr = AccountManager()
    return jsonify({"success": True, "data": mgr.list_accounts()})


@app.route("/api/accounts", methods=["POST"])
def api_accounts_create():
    """创建新账号"""
    from account_manager import AccountManager
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    if not name:
        return jsonify({"success": False, "message": "请输入账号名称"})
    mgr = AccountManager()
    result = mgr.create_account(name, data.get("id"))
    return jsonify(result)


@app.route("/api/accounts/<account_id>", methods=["DELETE"])
def api_accounts_delete(account_id):
    """删除账号"""
    from account_manager import AccountManager
    mgr = AccountManager()
    result = mgr.delete_account(account_id)
    return jsonify(result)


@app.route("/api/accounts/<account_id>/default", methods=["POST"])
def api_accounts_set_default(account_id):
    """设置默认账号（切换当前活跃账号）"""
    from account_manager import AccountManager
    mgr = AccountManager()
    result = mgr.switch_account(account_id)
    return jsonify(result)


@app.route("/api/accounts/<account_id>/cookie", methods=["POST"])
def api_accounts_upload_cookie(account_id):
    """上传账号的 cookie 数据"""
    from account_manager import AccountManager
    mgr = AccountManager()
    data = request.get_json(silent=True) or {}
    cookies = data.get("cookies", [])
    if not cookies:
        return jsonify({"success": False, "message": "没有 cookie 数据"})
    result = mgr.save_cookie(account_id, cookies)
    return jsonify(result)


@app.route("/api/accounts/<account_id>/cookie", methods=["GET"])
def api_accounts_get_cookie_status(account_id):
    """获取账号 cookie 状态"""
    from account_manager import AccountManager
    mgr = AccountManager()
    result = mgr.get_cookie_status(account_id)
    return jsonify({"success": True, "data": result})


@app.route("/api/accounts/active")
def api_accounts_active():
    """获取当前活跃账号"""
    from account_manager import AccountManager
    mgr = AccountManager()
    active = mgr.get_default_account()
    accounts = mgr.list_accounts()
    for a in accounts:
        a["is_active"] = a["id"] == active
    return jsonify({"success": True, "data": {"active_id": active, "accounts": accounts}})


@app.route("/api/accounts/<account_id>/switch", methods=["POST"])
def api_accounts_switch(account_id):
    """切换到指定账号"""
    from account_manager import AccountManager
    mgr = AccountManager()
    result = mgr.switch_account(account_id)
    return jsonify(result)


def main():
    """启动 Flask 应用"""
    app.run(host="127.0.0.1", port=5001, debug=False)


if __name__ == "__main__":
    main()
