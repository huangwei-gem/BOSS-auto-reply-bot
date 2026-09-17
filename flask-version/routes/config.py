"""
配置与日志 API
- 查看/修改配置
- 查看日志文件
"""
import logging
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint('config', __name__)
logger = logging.getLogger("bot")


@bp.route("/api/config")
def api_config():
    """获取配置"""
    import config
    return jsonify({
        "success": True,
        "data": {
            "check_interval": config.CHECK_INTERVAL,
            "max_replies_per_hour": config.MAX_REPLIES_PER_HOUR,
            "rules_count": len(config.REPLY_RULES),
            "rules": {k: (v if v != "send_resume" else "发送简历") for k, v in config.REPLY_RULES.items()}
        }
    })


@bp.route("/api/prompts", methods=["GET"])
def api_prompts_get():
    """获取所有可调节的提示词和配置"""
    import boss_bot.config as config
    from boss_bot.prompts import _SYSTEM_RULES, USER_PROMPT_TEMPLATE

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


@bp.route("/api/prompts", methods=["POST"])
def api_prompts_save():
    """保存修改的提示词和配置"""
    from flask import current_app
    project_root = current_app.config["PROJECT_ROOT"]
    data = request.get_json(silent=True) or {}
    saved = []

    overrides_path = project_root / "config_overrides.json"
    overrides = {}
    if overrides_path.exists():
        try:
            import json
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
        try:
            import json
            with open(project_root / "user_profile.json", "w", encoding="utf-8") as f:
                json.dump(data["user_profile"], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 user_profile.json 失败: {e}")
        saved.append("user_profile")

    try:
        import json
        with open(overrides_path, "w", encoding="utf-8") as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2)
        logger.info(f"配置已保存: {saved}")
        return jsonify({"success": True, "message": f"已保存: {', '.join(saved)}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# ===================== 日志文件 API =====================

@bp.route("/api/logfiles")
def api_logfiles():
    """获取日志文件列表"""
    from flask import current_app
    log_dir = current_app.config["LOG_DIR"]
    log_dir.mkdir(exist_ok=True)
    files = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        result.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify({"success": True, "data": result})


@bp.route("/api/logfile/<path:filename>")
def api_logfile(filename):
    """获取指定日志文件内容"""
    from flask import current_app
    log_dir = current_app.config["LOG_DIR"]

    # 安全校验：防止目录遍历
    if "/" in filename or "\\" in filename or ".." in filename:
        return jsonify({"success": False, "message": "Invalid filename"})
    log_file = log_dir / filename
    if not log_file.exists():
        return jsonify({"success": False, "message": "File not found"})
    try:
        content = log_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        if len(lines) > 1000:
            lines = lines[-1000:]
        return jsonify({"success": True, "data": "\n".join(lines)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
