"""
消息相关 API
- 未读消息列表
- 会话消息详情
"""
import logging

from flask import Blueprint, jsonify

from boss_bot.message_store import MessageStore
from boss_bot.page_handler import BossChatHandler

bp = Blueprint('messages', __name__)
logger = logging.getLogger("bot")


@bp.route("/api/unread")
def api_unread():
    """获取未读消息列表（复用全局浏览器实例，避免重复启动浏览器）"""
    from flask import current_app
    bot_state = current_app.config["BOT_STATE"]
    _bot_handler = current_app.config.get("_BOT_HANDLER")

    try:
        if _bot_handler is not None and bot_state["running"]:
            handler, owned = _bot_handler, False
        else:
            handler, owned = BossChatHandler(), True

        try:
            handler.go_to_chat()
            unread = handler.get_unread_chats()
        finally:
            if owned:
                handler.close()

        return jsonify({
            "success": True,
            "data": [{"name": c["name"], "preview": c["preview"][:100], "count": c["unread_count"]} for c in unread]
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
