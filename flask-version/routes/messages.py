"""
消息相关 API
- 未读消息列表
- 会话消息详情
"""
import logging

from flask import Blueprint, jsonify

from boss_bot.message_store import MessageStore


bp = Blueprint('messages', __name__)
logger = logging.getLogger("bot")


@bp.route("/api/unread")
def api_unread():
    """获取未读消息列表（从 bot_state 缓存读取，不触发浏览器操作，避免频繁刷新触发风控）"""
    from flask import current_app
    bot_state = current_app.config["BOT_STATE"]

    try:
        cached = bot_state.get("last_unread_chats", [])
        return jsonify({
            "success": True,
            "data": [{"name": c["name"], "preview": c.get("preview", "")[:100], "count": c.get("unread_count", 1)} for c in cached]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@bp.route("/api/messages")
def api_messages():
    """获取所有会话消息列表"""
    store = MessageStore()
    return jsonify({"success": True, "data": store.get_chat_list()})


@bp.route("/api/messages/<path:chat_name>")
def api_message_detail(chat_name):
    """获取某个会话的完整消息记录"""
    store = MessageStore()
    return jsonify({"success": True, "data": store.get_chat_detail(chat_name)})
