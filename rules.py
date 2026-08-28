"""
BOSS 自动回复机器人 - 关键词规则模块

定义关键词到回复内容的匹配规则。
规则引擎会按优先级匹配，第一个命中的规则生效。
"""

import re
from typing import Callable, Optional, Tuple
from config import REPLY_RULES


class RuleEngine:
    """关键词规则引擎"""

    def __init__(self, rules: dict = None):
        self.rules = rules or REPLY_RULES
        # 编译正则，提高匹配效率
        self._compiled = {
            keyword: re.compile(re.escape(keyword), re.IGNORECASE)
            for keyword in self.rules
        }

    def match(self, message: str) -> Optional[Tuple[str, str]]:
        """
        匹配消息内容，返回 (动作类型, 回复内容)
        动作类型: 'text' 表示直接发文字, 'resume' 表示发送简历
        未匹配返回 None
        """
        for keyword, response in self.rules.items():
            if self._compiled[keyword].search(message):
                if response == "send_resume":
                    return ("resume", None)
                else:
                    return ("text", response)
        return None

    def add_rule(self, keyword: str, response):
        """动态添加规则"""
        self.rules[keyword] = response
        self._compiled[keyword] = re.compile(re.escape(keyword), re.IGNORECASE)

    def remove_rule(self, keyword: str):
        """移除规则"""
        self.rules.pop(keyword, None)
        self._compiled.pop(keyword, None)
