"""
多账号管理 API
- 创建/删除/切换账号
- Cookie 上传/查看
"""
import logging

from flask import Blueprint, jsonify, request

from boss_bot.account_manager import AccountManager

bp = Blueprint('accounts', __name__)
logger = logging.getLogger("bot")


@bp.route("/api/accounts")
def api_accounts_list():
    """获取所有账号列表"""
    mgr = AccountManager()
    return jsonify({"success": True, "data": mgr.list_accounts()})


@bp.route("/api/accounts", methods=["POST"])
def api_accounts_create():
    """创建新账号"""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    if not name:
        return jsonify({"success": False, "message": "请输入账号名称"})
    mgr = AccountManager()
    result = mgr.create_account(name, data.get("id"))
    return jsonify(result)


@bp.route("/api/accounts/<account_id>", methods=["DELETE"])
def api_accounts_delete(account_id):
    """删除账号"""
    mgr = AccountManager()
    result = mgr.delete_account(account_id)
    return jsonify(result)


@bp.route("/api/accounts/<account_id>/default", methods=["POST"])
def api_accounts_set_default(account_id):
    """设置默认账号"""
    mgr = AccountManager()
    result = mgr.switch_account(account_id)
    return jsonify(result)


@bp.route("/api/accounts/<account_id>/switch", methods=["POST"])
def api_accounts_switch(account_id):
    """切换到指定账号"""
    mgr = AccountManager()
    result = mgr.switch_account(account_id)
    return jsonify(result)


@bp.route("/api/accounts/active")
def api_accounts_active():
    """获取当前活跃账号"""
    mgr = AccountManager()
    active = mgr.get_default_account()
    accounts = mgr.list_accounts()
    for a in accounts:
        a["is_active"] = a["id"] == active
    return jsonify({"success": True, "data": {"active_id": active, "accounts": accounts}})


@bp.route("/api/accounts/<account_id>/cookie", methods=["POST"])
def api_accounts_upload_cookie(account_id):
    """上传账号的 cookie 数据"""
    data = request.get_json(silent=True) or {}
    cookies = data.get("cookies", [])
    if not cookies:
        return jsonify({"success": False, "message": "没有 cookie 数据"})
    mgr = AccountManager()
    result = mgr.save_cookie(account_id, cookies)
    return jsonify(result)


@bp.route("/api/accounts/<account_id>/cookie", methods=["GET"])
def api_accounts_get_cookie_status(account_id):
    """获取账号 cookie 状态"""
    mgr = AccountManager()
    result = mgr.get_cookie_status(account_id)
    return jsonify({"success": True, "data": result})
