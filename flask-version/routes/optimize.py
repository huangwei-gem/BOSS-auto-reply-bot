"""
自进化 API
- 触发优化/进化
- 查看进化状态和历史
"""
import logging

from flask import Blueprint, jsonify

from boss_bot.self_optimizer import SelfOptimizer, get_auto_evolve_status

bp = Blueprint('optimize', __name__)
logger = logging.getLogger("bot")


@bp.route("/api/optimize", methods=["POST"])
def api_optimize():
    """触发自我优化迭代"""
    opt = SelfOptimizer()
    result = opt.analyze_and_optimize()
    return jsonify({"success": True, "data": result})


@bp.route("/api/evolve", methods=["POST"])
def api_evolve():
    """触发自进化（AI 驱动的提示词优化）"""
    opt = SelfOptimizer()
    result = opt.evolve()
    return jsonify({"success": True, "data": result})


@bp.route("/api/optimize/history")
def api_optimize_history():
    """获取优化历史"""
    opt = SelfOptimizer()
    return jsonify({"success": True, "data": opt.get_optimization_history()})


@bp.route("/api/evolve/status")
def api_evolve_status():
    """获取自动进化后台状态"""
    return jsonify({"success": True, "data": get_auto_evolve_status()})
