"""
BOSS 自动回复机器人 - 结构化事件日志

按天追加 JSONL 文件（logs/events_YYYYMMDD.jsonl），每行一个 JSON 事件。
方便日后用 pandas / jq 做统计分析，例如：

    # 各意图分布
    jq -r 'select(.kind=="reply") | .intent' events_*.jsonl | sort | uniq -c

    # AI 失败率
    jq -r 'select(.kind=="ai_call") | .ok' events_*.jsonl | sort | uniq -c
"""

import json
import threading
from datetime import datetime, date
from pathlib import Path


class EventLogger:
    """结构化事件记录器（线程安全，按天分文件）"""

    def __init__(self, log_dir=None, enabled=None):
        import config
        self.log_dir = Path(log_dir) if log_dir else Path(config.LOG_DIR)
        self.enabled = config.EVENT_LOG_ENABLED if enabled is None else enabled
        self._lock = threading.Lock()
        self._date = None
        self._file = None

    def _get_file(self):
        today = date.today()
        if self._file is None or self._date != today:
            self._date = today
            self.log_dir.mkdir(parents=True, exist_ok=True)
            path = self.log_dir / f"events_{today.strftime('%Y%m%d')}.jsonl"
            self._file = open(path, "a", encoding="utf-8")
        return self._file

    def event(self, kind: str, **fields):
        """记录一个事件。kind: reply/ai_call/send/skip/error/notice/session"""
        if not self.enabled:
            return
        record = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "kind": kind}
        record.update(fields)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            try:
                f = self._get_file()
                f.write(line + "\n")
                f.flush()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"事件日志写入失败: {e}")

    def close(self):
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None


# 模块级单例（各组件共享）
_instance = None
_instance_lock = threading.Lock()


def get_event_logger() -> EventLogger:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EventLogger()
    return _instance