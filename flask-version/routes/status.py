"""
状态与控制 API
- 启动/停止机器人
- 查看运行状态
- 暂停/恢复
- 日志查看
- Cookie 管理
- 浏览器选择
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request

from boss_bot.state_store import StateStore
from boss_bot.notify import Notifier
from boss_bot.stats import Stats
from boss_bot.config import COOKIE_FILE

bp = Blueprint('status', __name__)
logger = logging.getLogger("bot")


@bp.route("/api/status")
def api_status():
    """获取当前状态"""
    from flask import current_app
    bot_state = current_app.config["BOT_STATE"]
    data = dict(bot_state)
    data["headless"] = bot_state.get("headless", False)
    try:
        state = StateStore()
        data["paused"] = state.is_paused()
        if state.is_paused():
            data["pause_info"] = state.pause_info()
    except Exception:
        data["paused"] = False
    return jsonify({"success": True, "data": data})


@bp.route("/api/start", methods=["POST"])
def api_start():
    """启动机器人"""
    from flask import current_app
    bot_state = current_app.config["BOT_STATE"]
    bot_thread = current_app.config["BOT_THREAD"]

    if bot_state["running"]:
        return jsonify({"success": False, "message": "机器人已在运行"})

    data = request.get_json(silent=True) or {}
    bot_state["headless"] = data.get("headless", False)

    bot_state["running"] = True
    import threading
    from bot_loop import run_bot_loop
    t = threading.Thread(target=run_bot_loop, daemon=True)
    current_app.config["BOT_THREAD"] = t
    t.start()

    mode_label = "无头模式" if bot_state["headless"] else "有头模式"
    logger.info(f"机器人已启动 ({mode_label})")
    return jsonify({"success": True, "message": f"机器人已启动 ({mode_label})"})


@bp.route("/api/stop", methods=["POST"])
def api_stop():
    """停止机器人"""
    from flask import current_app
    bot_state = current_app.config["BOT_STATE"]

    if not bot_state["running"]:
        return jsonify({"success": False, "message": "机器人未在运行"})

    bot_state["running"] = False
    logger.info("机器人停止中...")
    return jsonify({"success": True, "message": "机器人正在停止"})


@bp.route("/api/pause", methods=["POST"])
def api_pause():
    """切换为人工接管模式（暂停自动回复）"""
    data = request.get_json(silent=True) or {}
    StateStore().pause(reason=data.get("reason", "手动暂停"))
    logger.info("已切换为人工接管模式")
    return jsonify({"success": True, "message": "已暂停自动回复（人工接管模式）"})


@bp.route("/api/resume", methods=["POST"])
def api_resume():
    """恢复自动回复"""
    resumed = StateStore().resume()
    msg = "已恢复自动回复" if resumed else "当前未处于暂停状态"
    logger.info(msg)
    return jsonify({"success": True, "message": msg})


@bp.route("/api/stats")
def api_stats():
    """获取统计数据"""
    return jsonify({"success": True, "data": Stats().summary()})


@bp.route("/api/notifications")
def api_notifications():
    """获取通知列表"""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"success": True, "data": Notifier().records(limit)})


@bp.route("/api/logs")
def api_logs():
    """获取实时日志（内存缓冲区）"""
    from flask import current_app
    log_buffer = current_app.config.get("LOG_BUFFER", [])
    limit = request.args.get("limit", 100, type=int)
    return jsonify({"success": True, "data": log_buffer[-limit:]})


@bp.route("/api/logs/file/<name>")
def api_log_file(name):
    """获取指定日志文件内容

    可选: bot, browser, ai, reply, web, errors
    """
    from flask import current_app
    from datetime import date

    # 安全校验
    valid_names = ("bot", "browser", "ai", "reply", "web", "errors")
    if name not in valid_names:
        return jsonify({"success": False, "message": f"无效名称，可选: {valid_names}"})

    log_dir = current_app.config["LOG_DIR"]
    today = date.today().strftime("%Y%m%d")
    log_file = log_dir / f"{name}_{today}.log"

    if not log_file.exists():
        return jsonify({"success": True, "data": [], "message": "今日暂无日志"})

    try:
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        limit = request.args.get("limit", 200, type=int)
        return jsonify({
            "success": True,
            "data": lines[-limit:],
            "total": len(lines),
            "file": log_file.name,
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@bp.route("/api/logs/errors")
def api_log_errors():
    """获取错误记录"""
    from boss_bot.log_manager import get_error_aggregator
    aggregator = get_error_aggregator()
    if aggregator:
        limit = request.args.get("limit", 50, type=int)
        return jsonify({"success": True, "data": aggregator.get_recent(limit)})
    return jsonify({"success": True, "data": []})


@bp.route("/api/logs/diagnose")
def api_log_diagnose():
    """获取诊断摘要"""
    from boss_bot.log_manager import get_diagnostic_summary
    return jsonify({"success": True, "data": get_diagnostic_summary()})


# ===================== Cookie & 浏览器 =====================

@bp.route("/api/cookie/status")
def api_cookie_status():
    """获取 Cookie 状态"""
    from flask import current_app
    project_root = current_app.config["PROJECT_ROOT"]
    cookie_path = project_root / COOKIE_FILE
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
                "modified": __import__("datetime").datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "path": COOKIE_FILE
            }
        })
    return jsonify({"success": True, "data": {"exists": False}})


@bp.route("/api/cookie/save", methods=["POST"])
def api_cookie_save():
    """用户点击「我已登录」按钮 — 保存 Cookie 并通知机器人继续"""
    from flask import current_app
    bot_state = current_app.config["BOT_STATE"]
    _bot_handler = current_app.config.get("_BOT_HANDLER")

    if _bot_handler is None:
        return jsonify({"success": False, "message": "浏览器未启动，请先启动机器人"})

    try:
        success = _bot_handler.confirm_and_save()
        if success:
            bot_state["needs_login"] = False
            bot_state["logged_in"] = True
            return jsonify({"success": True, "message": "Cookie 已保存，登录成功！"})
        else:
            return jsonify({"success": False, "message": "保存失败，请确认已在浏览器中完成登录"})
    except Exception as e:
        logger.error(f"confirm_and_save 异常: {e}")
        return jsonify({"success": False, "message": f"保存失败: {e}"})


@bp.route("/api/cookie/clear", methods=["POST"])
def api_cookie_clear():
    """清除已保存的 Cookie"""
    from flask import current_app
    project_root = current_app.config["PROJECT_ROOT"]
    cookie_path = project_root / COOKIE_FILE
    if cookie_path.exists():
        try:
            cookie_path.unlink()
            return jsonify({"success": True, "message": "Cookie 已清除"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    return jsonify({"success": False, "message": "没有已保存的 Cookie"})


@bp.route("/api/browser/detect")
def api_browser_detect():
    """检测可用浏览器列表"""
    from boss_bot.browser_launcher import detect_available_browsers, _preferred_browser, _get_portable_chrome_path
    browsers = detect_available_browsers()
    portable = _get_portable_chrome_path()

    # 如果有便携版 Chrome，添加到可用列表
    if portable and "portable" not in browsers:
        browsers["portable"] = portable

    # 当前选中的浏览器
    selected = _preferred_browser or ("portable" if portable else next(iter(browsers), ""))

    return jsonify({
        "success": True,
        "data": {
            "available": browsers,
            "selected": selected,
            "default": "portable" if portable else next(iter(browsers), ""),
            "portable_exists": bool(portable)
        }
    })


@bp.route("/api/browser/select", methods=["POST"])
def api_browser_select():
    """用户选择浏览器"""
    from boss_bot.browser_launcher import set_preferred_browser, _get_portable_chrome_path
    data = request.get_json()
    name = data.get("browser", "")
    valid_names = ("chrome", "edge", "chromium", "portable")
    if name not in valid_names:
        return jsonify({"success": False, "message": "无效的浏览器类型"})
    # 检查便携版是否真实存在
    if name == "portable" and not _get_portable_chrome_path():
        return jsonify({"success": False, "message": "便携版 Chrome 不存在"})
    set_preferred_browser(name)
    logger.info(f"用户选择浏览器: {name}")
    return jsonify({"success": True, "message": f"已选择 {name}"})


@bp.route("/api/test", methods=["POST"])
def api_test():
    """运行浏览器测试"""
    from flask import current_app
    project_root = current_app.config["PROJECT_ROOT"]
    try:
        result = subprocess.run(
            [sys.executable, str(project_root / "test_full_run.py")],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(project_root)
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
