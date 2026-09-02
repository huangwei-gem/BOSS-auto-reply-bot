# BOSS Auto-Reply Bot

BOSS直聘自动化机器人 — 跨平台通用版本，支持 Windows / macOS / Linux。

> **一键启动**：脚本会自动检测 Python、创建虚拟环境、安装依赖，无需手动配置！

## 快速开始

### 只需要两步：

#### 1. 克隆项目
```bash
git clone <repo-url>
cd sturgeon
```

#### 2. 运行启动脚本

| 平台 | 命令 | 说明 |
|------|------|------|
| **macOS / Linux** | `./start_bot.sh` | 自动完成所有配置 |
| **Windows** | `start_bot.bat` | 双击即可运行 |
| **通用** | `python main.py` | 需要自行安装依赖 |

首次运行脚本会自动：
- ✅ 检测 Python 3.8+
- ✅ 创建虚拟环境 `venv/`
- ✅ 安装依赖（DrissionPage、openai、flask）
- ✅ 检测 Chrome 浏览器
- ✅ 启动机器人

#### 3. 首次使用
1. 启动后浏览器窗口会自动打开
2. 手动登录 BOSS 直聘
3. 登录后 Cookie 自动保存到 `zhipin_cookies.json`
4. 后续启动自动登录，无需重复操作

## 跨平台支持

| 平台 | 启动脚本 | Chrome 自动检测 |
|------|----------|-----------------|
| **Windows** | `start_bot.bat` | 便携版 → 系统 Chrome |
| **macOS** | `./start_bot.sh` | `/Applications/Google Chrome.app` |
| **Linux** | `./start_bot.sh` | `google-chrome` / `chromium` |

## 项目结构

```
sturgeon/
├── .env.example                 # 环境变量模板
├── .gitignore                   # 排除敏感文件
├── config.py                    # 配置文件
├── main.py                      # 主入口
├── page_handler.py              # 浏览器操作封装（跨平台）
├── reply_engine.py              # 回复引擎（规则 + AI）
├── rules.py                     # 关键词规则
├── prompts.py                   # AI 提示词
├── requirements.txt             # Python 依赖
├── start_bot.bat                # Windows 一键启动
├── start_bot.sh                 # macOS/Linux 一键启动
├── test_full_run.py             # 跨平台集成测试
├── README.md                    # 本文档
├── browser-skill-extension/     # 浏览器扩展
├── cloakbrowser-windows-x64/    # 便携版 Chrome（Windows，可选）
│
├── browser-skill-version/       # browser-skill 版本（一键投递）
│   ├── auto_apply.py
│   └── config.py
│
└── flask-version/               # Flask Web 管理界面
    ├── app.py
    └── templates/index.html
```

## 配置 AI 回复

### 方式一：环境变量

#### Windows (cmd):
```cmd
set AI_API_KEY_1=your_api_key_here
set AI_BASE_URL=https://apihub.agnes-ai.com/v1
```

#### macOS / Linux (bash):
```bash
export AI_API_KEY_1=your_api_key_here
export AI_BASE_URL=https://apihub.agnes-ai.com/v1
```

### 方式二：.env 文件（推荐）
```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

## 功能说明

### DrissionPage 版本（自动回复）

持续监控 BOSS 直聘聊天页面的未读消息，自动回复。

**特点：**
- 跨平台自动检测系统 Chrome
- 混合回复策略：关键词规则优先，AI 兜底
- 支持自动发送简历
- Cookie 自动保存，首次登录后无需重复登录
- 模拟人类操作延迟，降低被检测风险

### browser-skill 版本（一键投递）

使用 bsk CLI（浏览器插件）实现一键自动投递。

**特点：**
- 搜索岗位 → 浏览列表 → 逐个点击"立即沟通" → 发送消息
- 自动检测已投递岗位，避免重复
- 发送失败自动重试

### Flask Web 管理界面

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

### config.py

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

## 运行测试

```bash
# 跨平台集成测试
python test_full_run.py
```

## 安全说明

- API Key 通过环境变量读取，不存储在代码中
- `.gitignore` 已排除 `.env`、`zhipin_cookies.json` 等敏感文件
- Cookie 文件请妥善保管，不要上传到公开仓库

## 依赖

```
DrissionPage>=4.0.0    # 浏览器自动化
openai>=1.0.0          # OpenAI 兼容 API
flask>=3.0.0           # Web 管理界面
```

## License

MIT
