# BOSS Auto-Reply Bot

BOSS直聘自动化机器人 — 三个版本，一键投递 + 自动回复 + Web管理。

## 项目结构

```
BOSS-auto-reply-bot/
├── drissionpage-version/          # DrissionPage 版本（自动回复）
│   ├── main.py                    # 主入口
│   ├── page_handler.py            # 浏览器操作封装
│   ├── reply_engine.py            # 回复引擎（规则 + AI）
│   ├── rules.py                   # 关键词规则
│   ├── prompts.py                 # AI 提示词
│   └── config.py                  # 配置文件
│
├── browser-skill-version/         # browser-skill 版本（一键投递）
│   ├── auto_apply.py              # 一键投递主逻辑
│   └── config.py                  # 投递配置
│
├── flask-version/                 # Flask Web 管理界面
│   ├── app.py                     # Flask 应用
│   └── templates/index.html       # 前端页面
│
├── cloakbrowser-windows-x64/      # 便携版 Chrome（自带 BrowserSkill 扩展）
├── browser-skill-extension/       # BrowserSkill 扩展文件
├── start_bot.bat                  # DrissionPage 版本一键启动
└── requirements.txt               # Python 依赖
```

## 版本说明

### 1. DrissionPage 版本（自动回复）

持续监控 BOSS 直聘聊天页面的未读消息，自动回复。

**特点：**
- 使用项目根目录的便携 Chrome（无需安装 Chrome）
- 内置 BrowserSkill 扩展
- 混合回复策略：关键词规则优先，AI 兜底
- 支持自动发送简历
- Cookie 自动保存，首次登录后无需重复登录

**使用方法：**

```bash
# 安装依赖
pip install -r requirements.txt

# 双击运行
start_bot.bat
```

或命令行：
```bash
python main.py
```

**首次使用：**
1. 启动后浏览器窗口会自动打开
2. 手动登录 BOSS 直聘
3. 登录后 Cookie 自动保存到 `zhipin_cookies.json`
4. 后续启动自动登录，无需重复操作

**配置 AI 回复：**
```bash
# Windows
set AI_API_KEY_1=your_api_key_here
set AI_BASE_URL=https://apihub.agnes-ai.com/v1
```

### 2. browser-skill 版本（一键投递）

使用 bsk CLI（浏览器插件）实现一键自动投递。

**特点：**
- 搜索岗位 → 浏览列表 → 逐个点击"立即沟通" → 发送消息
- 自动检测已投递岗位，避免重复
- 发送失败自动重试

**使用方法：**
```bash
# 安装 bsk CLI（全局）
# 已包含在 Claude Code 安装中，或从 https://github.com/Tencent/BrowserSkill 获取

# 启动会话
bsk session start --browser <your_browser_id>

# 运行投递
python browser-skill-version/auto_apply.py --session <session_id> --max 10
```

### 3. Flask Web 管理界面

提供 Web 界面管理机器人。

**功能：**
- 实时状态监控
- 未读消息列表
- 实时操作日志
- 一键启动/停止
- 配置和规则查看

**使用方法：**
```bash
cd flask-version
python app.py
# 打开 http://127.0.0.1:5000
```

## 配置说明

### config.py（DrissionPage 版本）

```python
CHECK_INTERVAL = 8              # 检查间隔（秒）
MAX_REPLIES_PER_HOUR = 30       # 每小时最大回复数
ENABLE_AI = True                # 是否启用 AI 回复

# AI API 配置（从环境变量读取）
AI_API_KEYS = [os.environ.get("AI_API_KEY_1", ""), ...]
AI_MODELS = ["agnes-2.5-flash", ...]
AI_BASE_URL = "https://apihub.agnes-ai.com/v1"

# 回复规则
REPLY_RULES = {
    "简历": "send_resume",
    "面试": "我这周周一到周五下午都可以安排面试...",
    "薪资": "我的期望薪资是 8-10K...",
    ...
}
```

### browser-skill-version/config.py

```python
CITY = "上海"                   # 目标城市
JOB_KEYWORD = "数据分析"         # 岗位关键词
MAX_APPLIES = 10                # 单次最大投递数
APPLY_MESSAGE = "您好..."       # 投递自我介绍
```

## 便携浏览器

DrissionPage 版本使用项目根目录的便携 Chrome (`cloakbrowser-windows-x64`)，无需安装 Chrome 即可运行。

**首次使用需要准备便携浏览器：**

1. 下载 Chrome 便携版（或 Chrome for Testing）
2. 解压到项目根目录，命名为 `cloakbrowser-windows-x64`
3. 确保 `cloakbrowser-windows-x64/chrome.exe` 存在

> 注意：便携浏览器体积约 500MB，未包含在 Git 仓库中。请自行准备。

**目录结构要求：**
```
BOSS-auto-reply-bot/
├── cloakbrowser-windows-x64/      # 便携 Chrome（自行准备）
│   ├── chrome.exe
│   └── ...
├── browser-skill-extension/       # BrowserSkill 扩展（已包含）
├── main.py
└── start_bot.bat
```

## 安全说明

- API Key 通过环境变量读取，不存储在代码中
- `.gitignore` 已排除 `.env`、`zhipin_cookies.json` 等敏感文件
- Cookie 文件请妥善保管，不要上传到公开仓库

## 依赖

```
DrissionPage>=4.0.0
openai>=1.0.0
flask>=3.0.0
```

## License

MIT
