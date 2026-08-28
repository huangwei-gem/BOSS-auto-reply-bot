"""
BOSS 自动回复机器人 - 配置文件
"""

import os

# ===================== 基础配置 =====================

# 检查未读消息的间隔（秒）
CHECK_INTERVAL = 8

# 每次操作后的随机延迟范围（秒），模拟人类操作节奏
MIN_DELAY = 2
MAX_DELAY = 5

# 每小时最大回复数，防止被平台检测
MAX_REPLIES_PER_HOUR = 30

# BOSS 聊天页面
CHAT_URL = "https://www.zhipin.com/web/geek/chat"

# ===================== 登录配置 =====================

# Cookie 保存路径
COOKIE_FILE = "zhipin_cookies.json"

# ===================== AI 配置 =====================

# 是否启用 AI 回复（规则未匹配时）
ENABLE_AI = True

# AI API 配置（OpenAI 兼容格式）
# 从环境变量读取 API Key，避免明文存储
# 设置环境变量: set AI_API_KEY_1=your_key_here
AI_API_KEYS = [
    os.environ.get("AI_API_KEY_1", ""),
    os.environ.get("AI_API_KEY_2", ""),
]
AI_MODELS = [
    os.environ.get("AI_MODEL_1", "agnes-2.5-flash"),
    os.environ.get("AI_MODEL_2", "agnes-2.5-flash"),
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

# ===================== 回复内容配置 =====================

# 期望薪资回复
SALARY_REPLY = "我的期望薪资是 8-10K，具体可以面谈，更看重发展机会和团队氛围。"

# 可面试时间
INTERVIEW_TIME_REPLY = "我这周周一到周五下午都可以安排面试，您看哪个时间段方便？"

# 岗位理解回复
JOB_CONTENT_REPLY = "我了解这个岗位主要负责数据分析和业务支持工作，我之前有相关实习经验，相信能快速上手。"

# 打招呼回复
GREETING_REPLY = "您好！我对这个岗位很感兴趣，方便了解一下具体情况吗？"

# 默认兜底回复（规则和 AI 都未命中时）
DEFAULT_REPLY = "好的，感谢您的消息，我会尽快回复您。"

# ===================== 规则配置 =====================

# 关键词规则：关键词 -> 回复内容或动作
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
