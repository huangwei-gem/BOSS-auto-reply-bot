"""
BOSS 自动回复机器人 - 配置文件
"""

import os
import json
from pathlib import Path

# 项目根目录（boss_bot/ 的上一级）
BASE_DIR = Path(__file__).parent.parent

# 加载 .env 文件（如果存在）
_env_path = BASE_DIR / ".env"
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

# 测试模式：配合 test_full_run.py 使用本地 mock 页面，不访问真实站点
TEST_MODE = os.environ.get("BOSS_BOT_TEST_MODE", "") == "1"
TEST_PAGE = os.environ.get("BOSS_BOT_TEST_PAGE", "")

# 无头模式：不显示浏览器窗口，节省资源（服务器部署推荐开启）
HEADLESS = os.environ.get("BOSS_BOT_HEADLESS", "") == "1"

# ===================== 基础配置 =====================

# 检查未读消息的间隔（秒），实际等待会加上随机抖动避免固定节奏被检测
CHECK_INTERVAL = 20

# 每次操作后的随机延迟范围（秒），模拟人类操作节奏
MIN_DELAY = 3
MAX_DELAY = 8

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

# ===================== 配置覆盖 =====================

OVERRIDES_FILE = BASE_DIR / "config_overrides.json"

def _load_overrides() -> dict:
    # 测试隔离：BOSS_BOT_NO_OVERRIDES=1 时跳过自进化产物，使用纯净默认配置
    if os.environ.get("BOSS_BOT_NO_OVERRIDES", "") == "1":
        return {}
    try:
        if OVERRIDES_FILE.exists():
            with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

_OVERRIDES = _load_overrides()

# 应用覆盖：话术模板
if "reply_templates" in _OVERRIDES:
    _rt = _OVERRIDES["reply_templates"]
    if "SALARY_REPLY" in _rt: globals()["SALARY_REPLY"] = render_template(_rt["SALARY_REPLY"], USER_PROFILE)
    if "INTERVIEW_TIME_REPLY" in _rt: globals()["INTERVIEW_TIME_REPLY"] = render_template(_rt["INTERVIEW_TIME_REPLY"], USER_PROFILE)
    if "JOB_CONTENT_REPLY" in _rt: globals()["JOB_CONTENT_REPLY"] = render_template(_rt["JOB_CONTENT_REPLY"], USER_PROFILE)
    if "GREETING_REPLY" in _rt: globals()["GREETING_REPLY"] = render_template(_rt["GREETING_REPLY"], USER_PROFILE)
    if "DEFAULT_REPLY" in _rt: globals()["DEFAULT_REPLY"] = _rt["DEFAULT_REPLY"]
    if "RESUME_DUPLICATE_REPLY" in _rt: globals()["RESUME_DUPLICATE_REPLY"] = _rt["RESUME_DUPLICATE_REPLY"]
    if "RESUME_UNAVAILABLE_REPLY" in _rt: globals()["RESUME_UNAVAILABLE_REPLY"] = _rt["RESUME_UNAVAILABLE_REPLY"]

# 应用覆盖：重要事件关键词
if "importance_keywords" in _OVERRIDES:
    IMPORTANCE_KEYWORDS_OVERRIDE = _OVERRIDES["importance_keywords"]

# ===================== AI 配置 =====================

# 是否启用 AI 回复（规则未匹配时）
ENABLE_AI = os.environ.get("ENABLE_AI", "false").lower() == "true"

# AI 模型池配置
# 每个模型一个 (api_key, model_name, base_url) 元组
# 调用时随机选择一个，失败时自动切换到下一个
# 配置方式：AI_PROVIDERS_1=key|model|url, AI_PROVIDERS_2=key|model|url, ...
def _parse_ai_providers(env_prefix: str = "AI_PROVIDERS") -> list:
    """解析 AI 提供商配置，支持多模型自动切换

    环境变量格式：AI_PROVIDERS_1=api_key|model_name|base_url
    示例：
        AI_PROVIDERS_1=sk-xxx|agnes-2.5-flash|https://apihub.agnes-ai.com/v1
        AI_PROVIDERS_2=sk-yyy|deepseek-v4-flash|https://token.sensenova.cn/v1
        AI_PROVIDERS_3=sk-zzz|deepseek-v4-flash|https://token.sensenova.cn/v1
    """
    providers = []
    for i in range(1, 20):  # 最多支持 20 个配置
        value = os.environ.get(f"{env_prefix}_{i}", "")
        if not value:
            continue
        parts = value.split("|")
        if len(parts) >= 2:
            key = parts[0].strip()
            model = parts[1].strip()
            url = parts[2].strip() if len(parts) >= 3 else "https://apihub.agnes-ai.com/v1"
            if key and model:
                providers.append({"key": key, "model": model, "url": url})
    return providers

# AI 请求代理（可选）：部分网络环境直连 API 的 TLS 握手会间歇超时，需走代理
# 示例：AI_HTTP_PROXY=http://127.0.0.1:7897，留空则直连
AI_HTTP_PROXY = os.environ.get("AI_HTTP_PROXY", "")

AI_PROVIDERS = _parse_ai_providers("AI_PROVIDERS")

# 兼容旧配置格式（向后兼容）
def _build_providers_from_legacy() -> list:
    """从旧格式配置构建 providers 列表"""
    providers = []

    # 主 API（Agnes）
    main_keys = [
        os.environ.get("AI_API_KEY_1", ""),
        os.environ.get("AI_API_KEY_2", ""),
        os.environ.get("AI_API_KEY_3", ""),
    ]
    main_models = [
        os.environ.get("AI_MODEL_1", "agnes-2.5-flash"),
        os.environ.get("AI_MODEL_2", "agnes-2.5-flash"),
        os.environ.get("AI_MODEL_3", "agnes-2.5-flash"),
    ]
    main_url = os.environ.get("AI_BASE_URL", "https://apihub.agnes-ai.com/v1")
    for key, model in zip(main_keys, main_models):
        if key:
            providers.append({"key": key, "model": model, "url": main_url})

    # 备用 API（商汤 Sensenova）
    backup_keys = [
        os.environ.get("AI_BACKUP_KEY_1", ""),
        os.environ.get("AI_BACKUP_KEY_2", ""),
    ]
    backup_models = [
        os.environ.get("AI_BACKUP_MODEL_1", "deepseek-v4-flash"),
        os.environ.get("AI_BACKUP_MODEL_2", "deepseek-v4-flash"),
    ]
    backup_url = os.environ.get("AI_BACKUP_BASE_URL", "https://token.sensenova.cn/v1")
    for key, model in zip(backup_keys, backup_models):
        if key:
            providers.append({"key": key, "model": model, "url": backup_url})

    # 兜底 API（DeepSeek 官方）
    fallback_key = os.environ.get("AI_FALLBACK_KEY", "")
    fallback_model = os.environ.get("AI_FALLBACK_MODEL", "deepseek-flash")
    fallback_url = os.environ.get("AI_FALLBACK_BASE_URL", "https://api.deepseek.com")
    if fallback_key:
        providers.append({"key": fallback_key, "model": fallback_model, "url": fallback_url})

    return providers


# 如果没有新的 PROVIDERS 配置，使用旧格式
if not AI_PROVIDERS:
    AI_PROVIDERS = _build_providers_from_legacy()

# 快捷访问属性（兼容旧代码）
AI_API_KEYS = [p["key"] for p in AI_PROVIDERS]
AI_MODELS = [p["model"] for p in AI_PROVIDERS]
AI_BASE_URL = AI_PROVIDERS[0]["url"] if AI_PROVIDERS else ""

# AI 回复的最大 token 数
AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "200"))

# AI 全部失败时的行为:
#   skip    - 跳过不回复（推荐，避免驴唇不对马嘴）
#   default - 发送默认兜底话术
AI_FAIL_ACTION = os.environ.get("AI_FAIL_ACTION", "skip").lower()

# API 限流（429）时等待重试的秒数
AI_RATE_LIMIT_WAIT = int(os.environ.get("AI_RATE_LIMIT_WAIT", "30"))

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

# 应用覆盖：关键词规则（自进化新增；value 必须是 "send_resume" 或可发送的回复文本）
if "reply_rules" in _OVERRIDES:
    for _rk, _rv in _OVERRIDES["reply_rules"].items():
        if not isinstance(_rk, str) or not _rk.strip():
            continue
        if _rv == "send_resume" or (isinstance(_rv, str) and 0 < len(_rv.strip()) <= 200):
            REPLY_RULES[_rk.strip()] = _rv

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

# 简历发送失败时的降级话术
RESUME_UNAVAILABLE_REPLY = "不好意思，简历文件暂时不在我这边，稍后我补发给您，可以先看看我主页的在线简历~"

# ===================== 日志配置 =====================

LOG_DIR = BASE_DIR / "logs"

# 日志级别：DEBUG / INFO / WARNING（环境变量可覆盖）
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# 日志保留天数（文本日志 + 事件日志统一清理）
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "14"))

# 是否启用结构化事件日志（logs/events_YYYYMMDD.jsonl，方便程序分析）
EVENT_LOG_ENABLED = os.environ.get("EVENT_LOG", "true").lower() == "true"

# ===================== AI 容错配置 =====================

# API 限流（429）时等待重试的秒数
AI_RATE_LIMIT_WAIT = int(os.environ.get("AI_RATE_LIMIT_WAIT", "30"))
