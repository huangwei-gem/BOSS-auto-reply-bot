"""
BOSS 自动回复机器人 - 日志管理器

分组件日志系统，方便快速定位问题：
- logs/browser.log    : 浏览器操作（启动、页面、点击）
- logs/ai.log         : AI API 调用（请求、响应、失败）
- logs/reply.log      : 回复决策（规则/意图/AI 命中）
- logs/web.log        : Web 界面（API 请求、用户操作）
- logs/errors.log     : 错误聚合（所有 ERROR 级别）
- logs/bot.log        : 主日志（其他所有）
- events_*.jsonl       : 结构化事件（供分析）

快速诊断：
    python -m boss_bot.diagnose
"""
import json
import logging
import time
import threading
from datetime import datetime, date
from pathlib import Path

# ===================== 日志格式 =====================

# 控制台格式（简洁）
CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
CONSOLE_DATEFMT = "%H:%M:%S"

# 文件格式（详细，含模块/行号）
FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s"
FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"

# 错误格式（带上下文）
ERROR_FORMAT = """%(asctime)s [ERROR] %(name)s.%(funcName)s:%(lineno)d
  Message: %(message)s
  Module: %(module)s
  Path: %(pathname)s:%(lineno)d
"""


class ErrorAggregator(logging.Handler):
    """错误聚合器 - 收集所有 ERROR 级别日志到 errors.json"""

    def __init__(self, log_dir: Path, max_errors: int = 100):
        super().__init__(level=logging.ERROR)
        self.log_dir = log_dir
        self.max_errors = max_errors
        self._lock = threading.Lock()
        self._errors = []
        self._load_existing()

    def _load_existing(self):
        """加载已有的错误记录"""
        error_file = self.log_dir / "errors.json"
        if error_file.exists():
            try:
                with open(error_file, "r", encoding="utf-8") as f:
                    self._errors = json.load(f)
            except Exception:
                self._errors = []

    def emit(self, record: logging.LogRecord):
        """收集错误记录"""
        error_entry = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        # 如果有异常信息，加上
        if record.exc_info and record.exc_info[1]:
            error_entry["exception"] = str(record.exc_info[1])

        with self._lock:
            self._errors.append(error_entry)
            # 只保留最近的 N 条
            if len(self._errors) > self.max_errors:
                self._errors = self._errors[-self.max_errors:]
            self._save()

    def _save(self):
        """保存到 errors.json"""
        error_file = self.log_dir / "errors.json"
        try:
            with open(error_file, "w", encoding="utf-8") as f:
                json.dump(self._errors, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_recent(self, count: int = 20) -> list:
        """获取最近的错误"""
        with self._lock:
            return self._errors[-count:]

    def get_summary(self) -> dict:
        """获取错误摘要"""
        with self._lock:
            # 按类型分组
            by_module = {}
            for e in self._errors[-100:]:
                mod = e.get("module", "unknown")
                by_module[mod] = by_module.get(mod, 0) + 1

            return {
                "total": len(self._errors),
                "recent_24h": len([
                    e for e in self._errors
                    if (time.time() - _parse_ts(e["ts"])) < 86400
                ]),
                "by_module": by_module,
            }

    def clear(self):
        """清除所有错误记录"""
        with self._lock:
            self._errors = []
            self._save()


def _parse_ts(ts_str: str) -> float:
    """解析时间字符串为时间戳"""
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return dt.timestamp()
    except Exception:
        return 0


# ===================== 组件日志过滤器 =====================

class ComponentFilter(logging.Filter):
    """只允许指定模块前缀的日志通过"""

    def __init__(self, allowed_prefixes):
        super().__init__()
        self.allowed_prefixes = allowed_prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        for prefix in self.allowed_prefixes:
            if record.name.startswith(prefix):
                return True
        return False


class ExcludeComponentFilter(logging.Filter):
    """排除指定模块前缀的日志"""

    def __init__(self, excluded_prefixes):
        super().__init__()
        self.excluded_prefixes = excluded_prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        for prefix in self.excluded_prefixes:
            if record.name.startswith(prefix):
                return False
        return True


# ===================== 日志初始化 =====================

_loggers_configured = False
_error_aggregator = None


def setup_logging(level: str = None, retention_days: int = None):
    """
    初始化日志系统

    输出目标：
    1. 控制台 - 简洁格式，INFO 级别
    2. logs/bot.log - 主日志，DEBUG 级别
    3. logs/browser.log - 浏览器相关
    4. logs/ai.log - AI API 调用
    5. logs/reply.log - 回复决策
    6. logs/web.log - Web 界面
    7. logs/errors.log - 错误专用
    8. logs/errors.json - 错误聚合（供诊断）
    """
    global _loggers_configured, _error_aggregator

    from boss_bot.config import LOG_DIR, LOG_LEVEL, LOG_RETENTION_DAYS

    root = logging.getLogger()

    # 避免重复配置
    if _loggers_configured and getattr(root, "_boss_bot_configured", False):
        return root

    level = (level or LOG_LEVEL).upper()
    retention = retention_days or LOG_RETENTION_DAYS

    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    log_dir = Path(LOG_DIR)
    log_dir.mkdir(exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")

    # ---- 1. 控制台输出 ----
    console = logging.StreamHandler()
    console.setLevel(getattr(logging, level, logging.INFO))
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATEFMT))
    # 设置控制台输出编码为 UTF-8
    if hasattr(console.stream, 'reconfigure'):
        console.stream.reconfigure(encoding='utf-8', errors='replace')
    root.addHandler(console)

    # ---- 2. 主日志文件（所有日志）----
    main_file = logging.FileHandler(
        log_dir / f"bot_{today}.log", encoding="utf-8"
    )
    main_file.setLevel(logging.DEBUG)
    main_file.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=FILE_DATEFMT))
    root.addHandler(main_file)

    # ---- 3. 组件日志文件 ----
    _add_component_log(root, log_dir, today, "browser", ["boss_bot.browser_launcher", "boss_bot.page_handler"])
    _add_component_log(root, log_dir, today, "ai", ["boss_bot.reply_engine"])
    _add_component_log(root, log_dir, today, "reply", ["boss_bot.rules", "boss_bot.intent", "boss_bot.prompts"])
    _add_component_log(root, log_dir, today, "web", ["boss_bot.flask", "routes", "werkzeug", "flask_version"])

    # ---- 4. 错误日志 ----
    error_file = logging.FileHandler(
        log_dir / f"errors_{today}.log", encoding="utf-8"
    )
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(logging.Formatter(ERROR_FORMAT, datefmt=FILE_DATEFMT))
    root.addHandler(error_file)

    # ---- 5. 错误聚合器 ----
    _error_aggregator = ErrorAggregator(log_dir)
    root.addHandler(_error_aggregator)

    # 清理旧日志
    cleanup_old_logs(retention)

    _loggers_configured = True
    root._boss_bot_configured = True

    return root


def _add_component_log(root: logging.Logger, log_dir: Path, date_str: str,
                       name: str, module_prefixes: list):
    """添加组件专用日志文件"""
    handler = logging.FileHandler(
        log_dir / f"{name}_{date_str}.log", encoding="utf-8"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=FILE_DATEFMT))
    handler.addFilter(ComponentFilter(module_prefixes))
    root.addHandler(handler)


def get_error_aggregator() -> ErrorAggregator:
    """获取错误聚合器"""
    return _error_aggregator


def cleanup_old_logs(retention_days: int = None):
    """清理超过保留天数的日志文件"""
    from boss_bot.config import LOG_DIR, LOG_RETENTION_DAYS

    retention = retention_days or LOG_RETENTION_DAYS
    log_dir = Path(LOG_DIR)
    if not log_dir.exists():
        return

    now = time.time()
    max_age = retention * 24 * 3600
    removed = 0
    for f in log_dir.glob("*"):
        if f.suffix in (".log", ".jsonl") and now - f.stat().st_mtime > max_age:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        logging.getLogger(__name__).info(f"已清理 {removed} 个过期日志文件")


# ===================== 便捷函数 =====================

def get_logger(name: str) -> logging.Logger:
    """获取命名 logger（自动添加 boss_bot 前缀）"""
    if not name.startswith("boss_bot.") and name != "boss_bot":
        name = f"boss_bot.{name}"
    return logging.getLogger(name)


def get_diagnostic_summary() -> dict:
    """获取诊断摘要（供 diagnose 命令使用）"""
    from boss_bot.config import LOG_DIR

    log_dir = Path(LOG_DIR)
    today = date.today().strftime("%Y%m%d")

    summary = {
        "date": date.today().isoformat(),
        "log_dir": str(log_dir),
        "log_files": {},
        "errors": {},
        "recent_errors": [],
    }

    # 检查各日志文件大小
    for name in ["bot", "browser", "ai", "reply", "web", "errors"]:
        log_file = log_dir / f"{name}_{today}.log"
        if log_file.exists():
            size = log_file.stat().st_size
            summary["log_files"][name] = {
                "size_kb": round(size / 1024, 1),
                "path": str(log_file),
            }

    # 错误摘要
    if _error_aggregator:
        summary["errors"] = _error_aggregator.get_summary()
        summary["recent_errors"] = _error_aggregator.get_recent(10)

    return summary


def print_diagnostic_report():
    """打印诊断报告到控制台"""
    summary = get_diagnostic_summary()

    print("=" * 60)
    print("BOSS Auto-Reply Bot - 诊断报告")
    print("=" * 60)
    print(f"日期: {summary['date']}")
    print(f"日志目录: {summary['log_dir']}")
    print()

    # 日志文件
    print("--- 今日日志文件 ---")
    for name, info in summary["log_files"].items():
        print(f"  {name:10s} : {info['size_kb']:>8.1f} KB  ({info['path']})")

    if not summary["log_files"]:
        print("  （今日暂无日志）")

    print()

    # 错误摘要
    errors = summary.get("errors", {})
    print("--- 错误统计 ---")
    print(f"  总计: {errors.get('total', 0)} 条")
    print(f"  最近24h: {errors.get('recent_24h', 0)} 条")

    if errors.get("by_module"):
        print("  按模块分布:")
        for mod, count in sorted(errors["by_module"].items(), key=lambda x: -x[1]):
            print(f"    {mod}: {count}")

    print()

    # 最近错误
    recent = summary.get("recent_errors", [])
    if recent:
        print("--- 最近 10 条错误 ---")
        for e in recent[-10:]:
            print(f"  [{e['ts']}] {e['logger']}.{e['func']}:{e['line']}")
            print(f"    {e['message'][:100]}")
    else:
        print("--- 无错误记录 ---")

    print()
    print("=" * 60)
    print("提示: 查看详细日志: cat logs/bot_YYYYMMDD.log")
    print("     查看错误日志: cat logs/errors_YYYYMMDD.log")
    print("     查看事件日志: cat logs/events_YYYYMMDD.jsonl")
    print("=" * 60)
