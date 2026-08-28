"""
BOSS 自动回复机器人 - 回复引擎

混合模式：规则优先，规则未匹配时调用 AI 生成回复。
使用 OpenAI 兼容 API。
"""

import random
import time
import logging
from typing import Optional, Tuple

from config import (
    ENABLE_AI,
    AI_API_KEYS, AI_MODELS, AI_BASE_URL,
    AI_BACKUP_API_KEYS, AI_BACKUP_MODELS, AI_BACKUP_BASE_URL,
    AI_MAX_TOKENS, DEFAULT_REPLY, MIN_DELAY, MAX_DELAY
)
from rules import RuleEngine
from prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class ReplyEngine:
    """回复引擎：规则 + AI 混合模式"""

    def __init__(self):
        self.rule_engine = RuleEngine()
        self._reply_count = 0
        self._hour_start = time.time()

    def get_reply(self, message: str, boss_name: str = "", job_name: str = "") -> Tuple[str, str]:
        """
        根据消息内容决定回复。
        返回: (动作类型, 回复内容)
        动作类型: 'text' | 'resume' | 'none'
        """
        # 1. 先尝试规则匹配
        result = self.rule_engine.match(message)
        if result:
            action, content = result
            logger.info(f"[规则匹配] 命中规则 -> 动作={action}")
            return result

        # 2. 规则未匹配，尝试 AI
        if ENABLE_AI and AI_API_KEYS:
            logger.info("[AI回复] 规则未匹配，调用 AI 生成回复...")
            ai_reply = self._ask_ai(message, boss_name, job_name)
            if ai_reply:
                return ("text", ai_reply)

        # 3. 都未命中，返回默认回复
        logger.info("[默认回复] 无规则匹配且 AI 未响应")
        return ("text", DEFAULT_REPLY)

    def _ask_ai(self, message: str, boss_name: str, job_name: str) -> Optional[str]:
        """调用 AI API 生成回复（OpenAI 兼容格式）"""
        try:
            from openai import OpenAI

            # 随机选择一个 key
            idx = random.randint(0, len(AI_API_KEYS) - 1)
            api_key = AI_API_KEYS[idx]
            model = AI_MODELS[idx]

            client = OpenAI(
                api_key=api_key,
                base_url=AI_BASE_URL
            )

            user_prompt = build_user_prompt(boss_name, job_name, message)

            response = client.chat.completions.create(
                model=model,
                max_tokens=AI_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            )

            reply = response.choices[0].message.content.strip()
            logger.info(f"[AI回复生成] {reply}")
            return reply

        except ImportError:
            logger.warning("未安装 openai 库，无法使用 AI 回复。运行: pip install openai")
            return None
        except Exception as e:
            logger.error(f"主 API 调用失败: {e}，尝试备用 API...")
            return self._ask_ai_backup(message, boss_name, job_name)

    def _ask_ai_backup(self, message: str, boss_name: str, job_name: str) -> Optional[str]:
        """备用 AI API"""
        try:
            from openai import OpenAI

            idx = random.randint(0, len(AI_BACKUP_API_KEYS) - 1)
            api_key = AI_BACKUP_API_KEYS[idx]
            model = AI_BACKUP_MODELS[idx]

            client = OpenAI(
                api_key=api_key,
                base_url=AI_BACKUP_BASE_URL
            )

            user_prompt = build_user_prompt(boss_name, job_name, message)

            response = client.chat.completions.create(
                model=model,
                max_tokens=AI_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            )

            reply = response.choices[0].message.content.strip()
            logger.info(f"[备用AI回复生成] {reply}")
            return reply

        except Exception as e:
            logger.error(f"备用 API 也失败: {e}")
            return None

    def wait_human_delay(self):
        """模拟人类操作延迟"""
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        logger.debug(f"等待 {delay:.1f} 秒...")
        time.sleep(delay)

    def can_reply(self) -> bool:
        """检查是否超过每小时回复限制"""
        now = time.time()
        # 重置计数器（超过1小时）
        if now - self._hour_start > 3600:
            self._reply_count = 0
            self._hour_start = now
        return self._reply_count < 30  # MAX_REPLIES_PER_HOUR

    def record_reply(self):
        """记录一次回复"""
        self._reply_count += 1
