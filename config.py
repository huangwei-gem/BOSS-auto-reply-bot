"""
BOSS 自动回复机器人 - 配置文件
"""

import os
import json
from pathlib import Path

# 加载 .env 文件（如果存在）
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and not os.environ.get(key):
                    os.environ[key] = value

BASE_DIR = Path(__file__).parent

# 测试模式：配合 test_full_run.py 使用本地 mock 页面，不访问真实站点
TEST_MODE = os.environ.get("BOSS_BOT_TEST_MODE", "") == "1"
TEST_PAGE = os.environ.get("BOSS_BOT_TEST_PAGE", "")

# ===================== 基础配置 =====================

# 检查未读消息的间隔（秒）
CHECK_INTERVAL = 8

# 每次操作后的随机延迟范围（秒），模拟人类操作节奏
MIN_DELAY = 2
MAX_DELAY = 5

# 每小时最大回复数，防止被平台检测
MAX_REPLIES_PER_HOUR = 30

# 读取聊天消息的条数（用于多轮上下文）
CONTEXT_MESSAGE_COUNT = 10

# BOSS 聊天页面
CHAT_URL = "https://www.zhipin.com/web/geek/chat"

# ===================== 登录配置 =====================

# Cookie 保存路径
COOKIE_FILE = "zhipin_cookies.json"

# ===================== 个人画像配置 =====================

PROFILE_FILE = BASE_DIR / "user_profile.json"

# 话术模板占位符渲染
_TEMPLATE_MAP = {
    "{salary}": "salary_expectation",
    "{interview_time}": "available_interview_time",
    "{position}": "position",
    "{skills}": "skills",          # 特殊处理：列表拼接
    "{experience}": "experience",
    "{name}": "name",
    "{contact}": "contact",
}


def load_user_profile() -> dict:
    """加载个人画像配置，缺失时返回默认值"""
    default = {
        "name": "求职者",
        "education": "本科学历",
        "position": "数据分析",
        "skills": [],
        "experience": "",
        "salary_expectation": "面议",
        "available_interview_time": "工作日下午",
        "contact": "",
        "highlights": [],
    }
    try:
        if PROFILE_FILE.exists():
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            default.update({k: v for k, v in data.items() if v is not None})
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"加载个人画像失败，使用默认值: {e}")
    return default


def render_template(text: str, profile: dict) -> str:
    """将话术模板中的 {salary} 等占位符替换为画像字段"""
    if not text or not isinstance(text, str):
        return text
    for ph, key in _TEMPLATE_MAP.items():
        if ph in text:
            val = profile.get(key, "")
            if isinstance(val, list):
                val = "、".join(str(x) for x in val)
            text = text.replace(ph, str(val))
    return text


USER_PROFILE = load_user_profile()

# ===================== AI 配置 =====================

# 是否启用 AI 回复（规则未匹配时）
ENABLE_AI = os.environ.get("ENABLE_AI", "false").lower() == "true"

# AI API 配置（OpenAI 兼容格式）
# 从环境变量读取 API Key，避免明文存储
# 复制 .env.example 为 .env 并填入你的 API Key
AI_API_KEYS = [
    os.environ.get("AI_API_KEY_1", ""),
    os.environ.get("AI_API_KEY_2", ""),
    os.environ.get("AI_API_KEY_3", ""),
]
AI_MODELS = [
    os.environ.get("AI_MODEL_1", "agnes-2.5-flash"),
    os.environ.get("AI_MODEL_2", "deepseek-v4-flash"),
    os.environ.get("AI_MODEL_3", "deepseek-v4-flash"),
]
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://apihub.agnes-ai.com/v1")

# 备用 API
AI_BACKUP_API_KEYS = [
    os.environ.get("AI_BACKUP_KEY_1", ""),
    os.environ.get("AI_BACKUP_KEY_2", ""),
]
AI_BACKUP_MODELS = [
    os.environ.get("AI_BACKUP_MODEL_1", "deepseek-v4-flash"),
    os.environ.get("AI_BACKUP_MODEL_2", "deepseek-v4-flash"),
]
AI_BACKUP_BASE_URL = os.environ.get("AI_BACKUP_BASE_URL", "https://token.sensenova.cn/v1")

# AI 回复的最大 token 数
AI_MAX_TOKENS = 200

# AI 主备 API 全部失败时的行为:
#   skip    - 跳过不回复（推荐，避免驴唇不对马嘴）
#   default - 发送默认兜底话术
AI_FAIL_ACTION = os.environ.get("AI_FAIL_ACTION", "skip").lower()

# ===================== 回复内容配置 =====================

# 期望薪资回复
SALARY_REPLY = "我的期望薪资是 {salary}，具体可以面谈，更看重发展机会和团队氛围。"

# 可面试时间
INTERVIEW_TIME_REPLY = "{interview_time}都可以安排面试，您看哪个时间段方便？"

# 岗位理解回复
JOB_CONTENT_REPLY = "我了解这个岗位主要负责{position}相关工作，我{experience}，相信能快速上手。"

# 打招呼回复
GREETING_REPLY = "您好！我对这个岗位很感兴趣，方便了解一下具体情况吗？"

# 默认兜底回复（规则和 AI 都未命中时）
DEFAULT_REPLY = "好的，感谢您的消息，我会尽快回复您。"

# 简历已发过时收到再次要简历请求的降级回复
RESUME_DUPLICATE_REPLY = "您好，简历刚刚已经发您了，您看一下，有任何问题随时沟通~"

# 用画像渲染话术模板
REPLY_TEMPLATE_RAW = {
    "SALARY_REPLY": SALARY_REPLY,
    "INTERVIEW_TIME_REPLY": INTERVIEW_TIME_REPLY,
    "JOB_CONTENT_REPLY": JOB_CONTENT_REPLY,
    "GREETING_REPLY": GREETING_REPLY,
    "DEFAULT_REPLY": DEFAULT_REPLY,
    "RESUME_DUPLICATE_REPLY": RESUME_DUPLICATE_REPLY,
}
for _k, _v in REPLY_TEMPLATE_RAW.items():
    globals()[_k] = render_template(_v, USER_PROFILE)

# ===================== 规则配置 =====================

# 关键词规则：关键词 -> 回复内容或动作（最高优先级，直接命中）
REPLY_RULES = {
    "简历": "send_resume",
    "发简历": "send_resume",
    "看看简历": "send_resume",
    "面试": INTERVIEW_TIME_REPLY,
    "约面试": INTERVIEW_TIME_REPLY,
    "时间安排": INTERVIEW_TIME_REPLY,
    "薪资": SALARY_REPLY,
    "待遇": SALARY_REPLY,
    "工资": SALARY_REPLY,
    "多少钱": SALARY_REPLY,
    "您好": GREETING_REPLY,
    "你好": GREETING_REPLY,
    "在吗": GREETING_REPLY,
    "在不在": GREETING_REPLY,
    "工作内容": JOB_CONTENT_REPLY,
    "岗位职责": JOB_CONTENT_REPLY,
    "做什么": JOB_CONTENT_REPLY,
}

# ===================== 意图识别与重要事件 =====================

# 重要事件关键词（命中即通知并可选暂停转人工）
IMPORTANCE_KEYWORDS = [
    "offer", "入职", "录取", "录用", "欢迎加入", "报到",
    "面试邀请", "邀约", "来公司", "到岗",
]

# 检测到重要事件后是否自动暂停（转人工模式）
PAUSE_ON_IMPORTANT = os.environ.get("PAUSE_ON_IMPORTANT", "true").lower() == "true"

# 同一会话是否只发一次简历
RESUME_SEND_ONCE = os.environ.get("RESUME_SEND_ONCE", "true").lower() == "true"

# ===================== 状态与数据文件 =====================

# 已处理会话状态（防重复回复）
STATE_FILE = BASE_DIR / "bot_state.json"

# 统计数据
STATS_FILE = BASE_DIR / "bot_stats.json"

# 通知记录
NOTIFY_FILE = BASE_DIR / "notifications.json"

# ===================== 通知配置 =====================

# 是否启用通知（重要事件：面试邀约/offer 等）
NOTIFY_ENABLED = os.environ.get("NOTIFY_ENABLED", "true").lower() == "true"

# Webhook 地址（可选：企业微信/飞书/钉钉机器人等，POST JSON）
NOTIFY_WEBHOOK_URL = os.environ.get("NOTIFY_WEBHOOK_URL", "")
