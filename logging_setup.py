"""
BOSS 自动回复机器人 - 日志初始化

三路输出：
1. 控制台：简洁格式（时间 级别 消息）
2. 文件 logs/bot_YYYYMMDD.log：详细格式（含模块/函数/行号，方便事后定位）
3. 自动清理超过保留天数的旧日志
"""

import logging
import time
from datetime import datetime
from pathlib import Path


def setup_logging(level: str = None, retention_days: int = None) -> logging.Logger:
    """初始化根日志器，返回根 logger"""
    from config import LOG_DIR, LOG_RETENTION_DAYS

    root = logging.getLogger()
    if getattr(root, "_boss_bot_configured", False):
        return root

    level = (level or __import__("config").LOG_LEVEL).upper()
    retention = retention_days or LOG_RETENTION_DAYS

    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # 控制台：简洁
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    root.addHandler(console)

    # 文件：详细（含模块/函数/行号）
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s"))
    root.addHandler(file_handler)

    # 清理旧日志
    cleanup_old_logs(retention)

    root._boss_bot_configured = True
    return root


def cleanup_old_logs(retention_days: int = None):
    """清理超过保留天数的日志文件（*.log 与 *.jsonl）"""
    from config import LOG_DIR

    retention = retention_days or __import__("config").LOG_RETENTION_DAYS
    if not Path(LOG_DIR).exists():
        return
    now = time.time()
    max_age = retention * 24 * 3600
    removed = 0
    for f in Path(LOG_DIR).glob("*"):
        if f.suffix in (".log", ".jsonl") and now - f.stat().st_mtime > max_age:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        logging.getLogger(__name__).info(f"已清理 {removed} 个过期日志文件")