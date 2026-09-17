"""
Flask 蓝图注册中心
"""
from .status import bp as bp_status
from .messages import bp as bp_messages
from .config import bp as bp_config
from .accounts import bp as bp_accounts
from .optimize import bp as bp_optimize


def register_blueprints(app):
    """注册所有蓝图"""
    app.register_blueprint(bp_status)
    app.register_blueprint(bp_messages)
    app.register_blueprint(bp_config)
    app.register_blueprint(bp_accounts)
    app.register_blueprint(bp_optimize)
