"""
BOSS 自动回复机器人 - 回复引擎

四级决策：
1. 关键词规则直通（REPLY_RULES）
2. 意图识别回复（intent.py，比关键词更精准）
3. AI 生成回复（带多轮对话历史，OpenAI 兼容 API，主备切换）
4. 兜底（AI 失败时可配置 skip / default）

返回 (动作类型, 回复内容, 元信息)：
- 动作类型: 'text' | 'resume' | 'none'
- 元信息: {"source": rule/intent/ai/default, "intent": ..., "important": bool}
"""

import random
import time
import logging
from typing import Optional, Tuple

import config
from config import (
    MIN_DELAY, MAX_DELAY,
    SALARY_REPLY, INTERVIEW_TIME_REPLY, JOB_CONTENT_REPLY,
    GREETING_REPLY,
    USER_PROFILE, render_template,
)
from rules import RuleEngine
from intent import classify
from prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

# 意图 -> 动作/话术模板（从个人画像渲染占位符）
INTENT_REPLIES = {
    "ask_salary": ("text", SALARY_REPLY),
    "ask_resume": ("resume", None),
    "ask_interview": ("text", INTERVIEW_TIME_REPLY),
    "invite_interview": ("text", INTERVIEW_TIME_REPLY),
    "ask_job_content": ("text", JOB_CONTENT_REPLY),
    "greeting": ("text", GREETING_REPLY),
    "contact_request": ("text", "方便的话您可以直接在平台上和我沟通，看到消息我会尽快回复您~"),
    "tell_salary": ("text", "感谢您的报价，我这边综合考虑一下，有进一步消息会及时回复您。"),
}


class ReplyEngine:
    """回复引擎：规则 + 意图 + AI 混合模式"""

    def __init__(self):
        self.rule_engine = RuleEngine()
        self._reply_count = 0
        self._hour_start = time.time()

    # ---------- 决策入口 ----------

    def get_reply(self, messages, boss_name: str = "", job_name: str = "",
                  chat_name: str = "") -> Tuple[str, Optional[str], dict]:
        """
        根据消息决定回复。
        Args:
            messages: 消息列表 [{"text","is_mine"/"isFriend","time"}]，
                      也兼容直接传最新消息字符串
        Returns:
            (动作类型, 回复内容, 元信息)
        """
        latest, history = self._split_messages(messages)

        meta = {"source": "", "intent": "", "important": False}

        if latest:
            meta["intent"] = classify(latest)

        # 1. 关键词规则直通（最高优先级）
        if latest:
            result = self.rule_engine.match(latest)
            if result:
                action, content = result
                logger.info(f"[规则匹配] 命中规则 -> 动作={action}")
                meta["source"] = "rule"
                return action, content, meta

        # 2. 意图识别回复
        if meta["intent"] in INTENT_REPLIES:
            action, template = INTENT_REPLIES[meta["intent"]]
            content = render_template(template, USER_PROFILE) if template else None
            logger.info(f"[意图匹配] intent={meta['intent']} -> 动作={action}")
            meta["source"] = "intent"
            return action, content, meta

        # 3. AI 生成回复（带多轮历史）
        if config.ENABLE_AI and any(config.AI_API_KEYS):
            logger.info("[AI回复] 规则/意图未命中，调用 AI 生成回复...")
            ai_reply = self._ask_ai(latest, boss_name, job_name, history)
            if ai_reply:
                meta["source"] = "ai"
                return ("text", ai_reply, meta)
            logger.warning("[AI回复] 主备 API 均失败")

        # 4. 兜底
        if config.AI_FAIL_ACTION == "default":
            logger.info("[默认回复] 使用兜底话术")
            meta["source"] = "default"
            return ("text", config.DEFAULT_REPLY, meta)

        # skip：宁可不回复，不发驴唇不对马嘴的话
        logger.info("[跳过回复] 无规则/意图命中且 AI 未响应，跳过")
        meta["source"] = "default"
        return ("none", None, meta)

    @staticmethod
    def _split_messages(messages):
        """拆出最新对方消息和历史列表，兼容直接传字符串"""
        if isinstance(messages, str):
            return messages, []
        if not messages:
            return "", []
        latest = ""
        for msg in reversed(messages):
            if not msg.get("is_mine"):
                latest = (msg.get("text") or "").strip()
                break
        return latest, messages

    # ---------- AI ----------

    def _ask_ai(self, message: str, boss_name: str, job_name: str,
                history: list = None) -> Optional[str]:
        """调用 AI API 生成回复（OpenAI 兼容格式），失败自动切备用"""
        if message == "" and not history:
            return None
        try:
            from openai import OpenAI

            idx = random.randint(0, len(config.AI_API_KEYS) - 1)
            api_key = config.AI_API_KEYS[idx]
            model = config.AI_MODELS[idx]

            client = OpenAI(api_key=api_key, base_url=config.AI_BASE_URL)
            reply = self._call_chat(client, model, message, boss_name, job_name, history)
            logger.info(f"[AI回复生成] {reply}")
            return reply
        except ImportError:
            logger.warning("未安装 openai 库，无法使用 AI 回复。运行: pip install openai")
            return None
        except Exception as e:
            logger.error(f"主 API 调用失败: {e}，尝试备用 API...")
            return self._ask_ai_backup(message, boss_name, job_name, history)

    def _ask_ai_backup(self, message: str, boss_name: str, job_name: str,
                       history: list = None) -> Optional[str]:
        """备用 AI API"""
        try:
            from openai import OpenAI

            idx = random.randint(0, len(config.AI_BACKUP_API_KEYS) - 1)
            api_key = config.AI_BACKUP_API_KEYS[idx]
            model = config.AI_BACKUP_MODELS[idx]

            client = OpenAI(api_key=api_key, base_url=config.AI_BACKUP_BASE_URL)
            reply = self._call_chat(client, model, message, boss_name, job_name, history)
            logger.info(f"[备用AI回复生成] {reply}")
            return reply
        except Exception as e:
            logger.error(f"备用 API 也失败: {e}")
            return None

    @staticmethod
    def _call_chat(client, model, message, boss_name, job_name, history):
        user_prompt = build_user_prompt(boss_name, job_name, message, history)
        response = client.chat.completions.create(
            model=model,
            max_tokens=config.AI_MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    # ---------- 频控与延迟 ----------

    def wait_human_delay(self):
        """模拟人类操作延迟"""
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        logger.debug(f"等待 {delay:.1f} 秒...")
        time.sleep(delay)

    def can_reply(self) -> bool:
        """检查是否超过每小时回复限制"""
        now = time.time()
        if now - self._hour_start > 3600:
            self._reply_count = 0
            self._hour_start = now
        return self._reply_count < config.MAX_REPLIES_PER_HOUR

    def record_reply(self):
        """记录一次回复"""
        self._reply_count += 1
