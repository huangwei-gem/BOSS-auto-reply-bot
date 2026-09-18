"""
BOSS 自动回复机器人 - Flask Web 管理界面

提供 Web 界面管理机器人：
- 实时状态监控（含暂停/人工接管状态）
- 未读消息列表
- 实时操作日志 + 日志文件查看
- 一键启动/停止
- 配置和规则查看 + 提示词在线编辑
- 通知列表查看
- 统计数据查看
- 暂停/恢复控制
- Cookie 管理（状态查看、手动保存、清除）
- 浏览器选择
- 多账号管理（创建、切换、删除、Cookie 上传）
- 自进化控制（手动触发、状态查看、历史记录）
"""
import os
import sys
import logging
import warnings
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, jsonify

# 抑制 urllib3 LibreSSL 警告
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

# 关闭 Flask 默认请求日志
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boss_bot.log_manager import setup_logging, cleanup_old_logs
setup_logging()

from boss_bot.event_logger import get_event_logger


# ===================== 日志缓冲区（供前端实时显示） =====================

MAX_LOGS = 500
log_buffer = []


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


# 配置 Web 日志流
web_handler = WebLogHandler()
web_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(web_handler)
logging.getLogger().setLevel(logging.INFO)


# ===================== Flask 应用工厂 =====================

def create_app():
    """创建并配置 Flask 应用"""
    app = Flask(__name__)

    # 项目路径
    project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app.config["PROJECT_ROOT"] = project_root
    app.config["LOG_DIR"] = project_root / "logs"

    # 共享状态（蓝图通过 app.config 访问）
    import os as _os
    app.config["BOT_STATE"] = {
        "running": False,
        "logged_in": False,
        "needs_login": False,
        "headless": _os.environ.get("BOSS_BOT_HEADLESS", "") == "1",
        "total_replies": 0,
        "total_resumes": 0,
        "last_check": None,
        "current_chat": None,
        "last_unread_chats": [],
    }
    app.config["BOT_THREAD"] = None
    app.config["_BOT_HANDLER"] = None
    app.config["LOG_BUFFER"] = log_buffer

    # 注册蓝图
    from routes import register_blueprints
    register_blueprints(app)

    # 主页路由
    @app.route("/")
    def index():
        return render_template("index.html")

    return app


def main():
    """启动 Flask 应用"""
    # 启动定时自动进化后台线程
    from boss_bot.self_optimizer import start_auto_evolve
    start_auto_evolve()

    app = create_app()
    app.run(host="127.0.0.1", port=5001, debug=False)


if __name__ == "__main__":
    main()
