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
- 检测 Python 3.8+
- 创建虚拟环境 `venv/`
- 安装依赖（DrissionPage、openai、flask）
- 检测 Chrome 浏览器
- 启动机器人

#### 3. 首次使用
1. 启动后浏览器窗口会自动打开
2. 手动登录 BOSS 直聘
3. 登录后 Cookie 自动保存到 `zhipin_cookies.json`（通过 CDP `Storage.getCookies` 捕获完整 Cookie，含 HttpOnly）
4. 后续启动自动登录，无需重复操作

#### 4. 配置个人画像
编辑 `user_profile.json`，填入你的求职信息：
```json
{
  "name": "张三",
  "education": "本科学历",
  "position": "数据分析",
  "skills": ["Excel", "SQL", "Python 基础"],
  "experience": "有数据分析相关实习经验",
  "salary_expectation": "8-10K",
  "available_interview_time": "这周周一到周五下午",
  "contact": "",
  "highlights": ["学习能力强", "沟通顺畅"]
}
```
话术模板中的 `{salary}`、`{position}`、`{skills}` 等占位符会自动替换为画像内容。

## 跨平台支持

| 平台 | 启动脚本 | Chrome 自动检测 |
|------|----------|-----------------|
| **Windows** | `start_bot.bat` | 便携版 → 系统 Chrome |
| **macOS** | `./start_bot.sh` | `/Applications/Google Chrome.app` |
| **Linux** | `./start_bot.sh` | `google-chrome` / `chromium` |

## 便携版 Chrome（Windows）

项目默认使用 `cloakbrowser-windows-x64/` 目录下的便携版 Chrome（无需安装，开箱即用）。

由于文件较大（~537MB），便携版 Chrome 未包含在 Git 仓库中。首次使用请下载：

### 下载方式

1. **下载便携版 Chrome**：

   **方式一：CloakBrowser（推荐，带反检测）**
   - GitHub：https://github.com/CloakHQ/CloakBrowser
   - Windows x64 下载：https://github.com/CloakHQ/CloakBrowser/releases/download/chromium-v145.0.7632.109.2/cloakbrowser-windows-x64.zip
   - macOS ARM64 下载：https://github.com/CloakHQ/CloakBrowser/releases/download/chromium-v145.0.7632.109.2/cloakbrowser-darwin-arm64.tar.gz

   **方式二：Chrome-for-Testing（Google 官方）**
   - 下载地址：https://github.com/GoogleChromeLabs/chrome-for-testing
   - 选择 `chrome-win64` 版本下载

   **方式三：自行打包**
   - 安装 Chrome 后，复制安装目录到 `cloakbrowser-windows-x64/`

2. **解压到项目根目录**：
   ```
   BOSS-auto-reply-bot/
   └── cloakbrowser-windows-x64/
       ├── chrome.exe
       ├── chrome.dll
       └── ...
   ```

3. **启动脚本会自动检测并使用便携版 Chrome**

> 如果没有便携版 Chrome，脚本会自动检测系统安装的 Google Chrome 或 Microsoft Edge。

### 浏览器选择

Web 管理界面（http://127.0.0.1:5001）支持在线切换浏览器：
- 便携版 Chrome（默认）
- 系统 Google Chrome
- Microsoft Edge

也可以通过 API 切换：
```bash
# 查看可用浏览器
curl http://127.0.0.1:5001/api/browser/detect

# 切换到便携版
curl -X POST http://127.0.0.1:5001/api/browser/select -H "Content-Type: application/json" -d '{"browser":"portable"}'

# 切换到系统 Chrome
curl -X POST http://127.0.0.1:5001/api/browser/select -H "Content-Type: application/json" -d '{"browser":"chrome"}'
```

## 项目结构

```
sturgeon/
├── .skills/drissionpage/        # DrissionPage skill 文档（4.1.x API 速查 + 58页完整文档）
├── .env.example                 # 环境变量模板
├── .gitignore                   # 排除敏感文件
├── DEPLOY.md                    # 免费线上部署指南（Oracle Cloud / Cloudflare Tunnel）
├── TUNNEL_GUIDE.md              # 内网穿透使用教程（跨平台，Cloudflare Tunnel）
├── Dockerfile                   # Docker 镜像（ARM/x86 双架构，Oracle Cloud 部署用）
├── docker-compose.yml           # Docker Compose 编排
├── config.py                    # 配置文件（画像加载、话术渲染、规则、意图、通知等）
├── main.py                      # 主入口
├── page_handler.py              # 浏览器操作封装（跨平台、健康检查、送达验证）
├── reply_engine.py              # 回复引擎（规则 → 意图 → AI → 兜底，四级决策）
├── rules.py                     # 关键词规则引擎
├── intent.py                    # 意图分类（8 种意图正则识别）
├── prompts.py                   # AI 提示词（画像驱动 + 多轮对话历史）
├── state_store.py               # 会话状态持久化（去重、简历记录、暂停）
├── stats.py                     # 统计数据持久化（按天、来源/动作分布）
├── notify.py                    # 通知模块（重要事件检测 + Webhook 推送）
├── message_store.py             # 消息存储（JSON 持久化 + TTL 内存缓存）
├── self_optimizer.py            # 自进化引擎（规则分析 + AI 分析 + 定时自动迭代）
├── account_manager.py           # 多账号管理（独立 Cookie/状态/配置）
├── browser_launcher.py          # 跨平台浏览器启动器（统一使用 Chromium API）
├── user_profile.json            # 个人画像配置
├── mock_zhipin.html             # 端到端测试用 mock 聊天页
├── requirements.txt             # Python 依赖
├── start_bot.bat                # Windows 一键启动
├── start_bot.sh                 # macOS/Linux 一键启动
├── start_tunnel.bat             # Windows 一键内网穿透
├── start_tunnel.sh              # macOS/Linux 一键内网穿透
├── test_full_run.py             # 端到端集成测试（真实浏览器）
├── tests/test_unit.py           # 单元测试套件
├── README.md                    # 本文档
│
├── browser-use-version/         # browser-use 版本（一键投递，Playwright 引擎）
│   ├── auto_apply.py            # 自动投递主逻辑
│   ├── config.py                # 投递配置
│   ├── .venv/                   # Python 3.12 虚拟环境（browser-use + Playwright）
│   └── .pw-browsers/            # Playwright Chromium 浏览器缓存
│
├── flask-version/               # Flask Web 管理界面
│   ├── app.py                   # Flask 应用（含自进化 API、多账号管理 API）
│   └── templates/index.html     # 前端页面
│
├── accounts/                    # 多账号数据目录
│   ├── index.json               # 账号索引
│   └── {account_id}/            # 每个账号独立目录
│       ├── cookies.json         # 账号 Cookie
│       ├── messages/            # 账号消息记录
│       └── bot_state.json       # 账号状态
│
├── messages/                    # 真实消息记录（前端展示用）
├── messages_test/               # 测试消息记录（TEST_MODE 隔离，不污染前端）
├── cookie_backups/              # Cookie 备份
└── logs/                        # 运行日志
```

## 核心功能

### 自动回复机器人（DrissionPage 版本）

持续监控 BOSS 直聘聊天页面的未读消息，自动回复。

**四级回复决策：**

| 层级 | 说明 | 示例 |
|------|------|------|
| 1. 关键词规则 | `REPLY_RULES` 精确命中，最高优先级 | "简历" → 发简历；"薪资" → 画像话术 |
| 2. 意图识别 | `intent.py` 正则模式识别 8 种意图，语义更精准 | "预算范围多少" → ask_salary（区分"问薪资"与"报薪资"） |
| 3. AI 生成 | OpenAI 兼容 API，带入多轮对话历史 + 画像 | 规则/意图均未命中时，AI 接续话题 |
| 4. 兜底 | `AI_FAIL_ACTION` 配置：`skip`（跳过）或 `default`（默认话术） | AI 全挂时宁可不回复，不发驴唇不对马嘴的话 |

**意图分类（`intent.py`）：**

| 意图 | 说明 | 回复动作 |
|------|------|---------|
| `invite_interview` | 面试邀约（重要事件） | 文字：可面试时间 |
| `ask_salary` | 对方询问薪资 | 文字：期望薪资话术 |
| `ask_resume` | 对方要简历 | 发简历 |
| `ask_interview` | 询问面试时间 | 文字：可面试时间 |
| `ask_job_content` | 询问工作内容 | 文字：岗位理解话术 |
| `contact_request` | 要联系方式 | 文字：引导平台沟通 |
| `tell_salary` | 对方报薪资 | 文字：感谢报价 |
| `greeting` | 打招呼 | 文字：问候话术 |

**重要事件与转人工：**
- 面试邀约 / offer / 入职等关键词命中 → 自动通知 + 暂停转人工
- 通知写入 `notifications.json`，可选 Webhook 推送（企业微信/飞书/钉钉）
- 暂停后机器人仅监控不回复，通过 Flask `/api/resume` 或删除 `bot_state.json` 恢复

**防重复与防滥用：**
- 已处理消息哈希去重（重启不重复回复同一条消息）
- 简历每会话只发一次（重复索要降级为文字提醒）
- 每小时回复上限 30 条（可配置）
- 随机 2-5 秒人类操作延迟

**健康检查：**
- 登录失效检测（被踢下线 → 通知 + 等待重新登录）
- 验证码/安全验证检测（暂停 + 通知人工处理）
- 简历送达验证（弹窗关闭 + 消息列表出现简历项）

### browser-use 版本（一键投递）

使用 Playwright（browser-use 的底层引擎）实现一键自动投递。

**为什么用 browser-use 替代 browser-skill？**
- browser-use 基于 Playwright，社区活跃、文档完善、API 稳定
- browser-skill 依赖 bsk CLI 浏览器插件，维护停滞、兼容性差
- browser-use 支持 AI Agent 模式（`browser_use.Agent`），未来可扩展智能操作
- Playwright 原生 API 直接操控 DOM，比 bsk CLI 更灵活可靠

**特点：**
- 搜索岗位 → 浏览列表 → 逐个点击"立即沟通" → 发送消息
- Cookie 通过 Playwright `context.add_cookies` 注入（含 HttpOnly）
- 自动保存 Cookie 到账号目录（退出时 `context.cookies()` 保存）
- 支持 `--headless` 无头模式（服务器部署用）
- 支持 `--account` 指定账号

**使用方法：**
```bash
cd browser-use-version
# 首次需创建 Python 3.12 虚拟环境（browser-use 要求 >=3.11）
python3.12 -m venv .venv
.venv/bin/pip install browser-use playwright
PLAYWRIGHT_BROWSERS_PATH=.pw-browsers .venv/bin/playwright install chromium

# 运行
PLAYWRIGHT_BROWSERS_PATH=.pw-browsers .venv/bin/python auto_apply.py --headless
```

### 自进化功能（类似 Hermes）

机器人会自动分析回复效果并持续优化提示词和规则，无需人工干预。

**工作原理：**
1. **数据收集**：分析 `messages/` 中所有会话的交互数据（对方是否在机器人回复后继续聊）
2. **规则分析**：基于阈值的启发式建议（回复有效率低 → 优化话术；默认回复占比高 → 扩展规则覆盖）
3. **AI 分析**：用 DeepSeek API 智能分析效果差/好的回复，生成精准优化建议
4. **自动应用**：将建议写入 `config_overrides.json`（系统提示词规则、话术模板、AI 启用策略）
5. **效果追踪**：每次优化后记录日志，后续迭代对比效果变化，形成正向反馈循环

**定时自动进化：**
- Flask 启动时自动启动后台线程（默认每 1 小时迭代一次）
- 环境变量 `AUTO_EVOLVE_INTERVAL` 可调整间隔
- API：`POST /api/evolve`（手动触发）、`GET /api/evolve/status`（查看状态）

### Flask Web 管理界面

提供 Web 界面管理机器人。

**功能：**
- 实时状态监控（含暂停/人工接管状态）
- 未读消息列表（复用全局浏览器实例，避免重复启动）
- 消息明细查看（`/api/messages`、`/api/messages/<chat_name>`）
- 实时操作日志 + 日志文件查看
- 一键启动/停止
- 配置和规则查看 + 提示词在线编辑
- 通知列表查看（`/api/notifications`）
- 统计数据查看（`/api/stats`）
- 暂停/恢复控制（`/api/pause`、`/api/resume`）
- Cookie 管理（状态查看、手动保存、清除）
- 浏览器选择
- 多账号管理（创建、切换、删除、Cookie 上传）
- 自进化控制（手动触发、状态查看、历史记录）

**使用方法：**
```bash
python flask-version/app.py
# 打开 http://127.0.0.1:5001
```

### 缓存优化

- **消息缓存**：`MessageStore` 内置 30 秒 TTL 内存缓存，减少重复磁盘 IO
- **浏览器实例复用**：`/api/unread` 复用全局 handler 的浏览器实例，避免每次请求都启动新浏览器
- **测试数据隔离**：`TEST_MODE` 下消息写入 `messages_test/` 目录，不污染前端真实消息列表

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

## 配置说明

### 个人画像（`user_profile.json`）

所有话术模板中的占位符会从画像自动渲染：

| 占位符 | 字段 | 说明 |
|--------|------|------|
| `{salary}` | `salary_expectation` | 期望薪资 |
| `{interview_time}` | `available_interview_time` | 可面试时间 |
| `{position}` | `position` | 求职方向 |
| `{skills}` | `skills` | 技能列表（自动拼接） |
| `{experience}` | `experience` | 经历描述 |
| `{contact}` | `contact` | 联系方式 |

### config.py 主要配置

```python
CHECK_INTERVAL = 8              # 检查间隔（秒）
CONTEXT_MESSAGE_COUNT = 10      # 读取聊天消息条数（多轮上下文）
MAX_REPLIES_PER_HOUR = 30       # 每小时最大回复数
ENABLE_AI = True                # 是否启用 AI 回复
AI_FAIL_ACTION = "skip"         # AI 全挂时：skip（跳过）或 default（兜底话术）
PAUSE_ON_IMPORTANT = True       # 重要事件自动暂停转人工
RESUME_SEND_ONCE = True         # 简历每会话只发一次
NOTIFY_ENABLED = True           # 是否启用通知
NOTIFY_WEBHOOK_URL = ""         # Webhook 推送地址（可选）
```

### 数据文件

| 文件 | 说明 |
|------|------|
| `zhipin_cookies.json` | 登录 Cookie（CDP 完整捕获，含 HttpOnly） |
| `bot_state.json` | 会话处理状态（去重、简历记录、暂停） |
| `bot_stats.json` | 统计数据（按天、来源/动作分布） |
| `notifications.json` | 通知记录（最近 100 条） |
| `config_overrides.json` | 配置覆盖（自进化写入的优化规则/话术） |
| `accounts/{id}/cookies.json` | 多账号 Cookie（每个账号独立） |

## 免费线上部署

详见 **[DEPLOY.md](DEPLOY.md)**，三种方案：

| 方案 | 适合场景 | 持续运行 |
|------|---------|---------|
| **Oracle Cloud 免费 VPS**（最推荐） | 7×24 时刻后台运行 | ✅ 24/7 |
| **本机 + Cloudflare Tunnel** | 用自己电脑跑，外网可访问 | ⚠️ 依赖本机开机 |
| **Render.com** | 仅 Web 管理界面 | ⚠️ 免费版会休眠 |

**Oracle Cloud Always Free** 提供 ARM 4核24G 内存 VPS（永久免费），是运行无头浏览器自动化的最佳免费方案。

**Cloudflare Tunnel** 可 5 分钟内让本机 Flask 界面从外网访问，无需公网 IP。详见 **[TUNNEL_GUIDE.md](TUNNEL_GUIDE.md)**，项目内置一键启动脚本：

| 平台 | 命令 |
|------|------|
| **macOS / Linux** | `./start_tunnel.sh` |
| **Windows** | `start_tunnel.bat` |

## 运行测试

```bash
# 单元测试（46 项，无需浏览器）
python -m unittest discover tests -v

# 端到端测试（27 项，真实浏览器 + mock 聊天页）
python test_full_run.py

# browser-use 版冒烟测试
cd browser-use-version
PLAYWRIGHT_BROWSERS_PATH=.pw-browsers .venv/bin/python test_smoke.py
```

端到端测试覆盖：
- 规则直通 → 发简历 + 送达验证
- 意图识别 → 画像话术渲染
- 简历去重降级
- 面试邀约 → 通知 + 转人工暂停
- 人工接管模式跳过
- 重复消息去重
- 数据文件落盘验证
- 引擎决策验证

> 测试数据自动隔离到 `messages_test/` 目录，不会污染前端真实消息显示。

## 安全说明

- API Key 通过环境变量读取，不存储在代码中（所有 API Key 均从 `.env` 或环境变量读取，无硬编码）
- `.gitignore` 已排除 `.env`、`zhipin_cookies.json`、`bot_state.json`、`bot_stats.json`、`notifications.json` 等敏感文件
- Cookie 文件请妥善保管，不要上传到公开仓库
- Cookie 通过 CDP `Storage.getCookies` 完整捕获（含 HttpOnly），加载时用 `Storage.setCookies` 恢复

## 依赖

```
DrissionPage>=4.1.0,<5.0.0  # 浏览器自动化（命令行版）
openai>=1.0.0          # OpenAI 兼容 API
flask>=3.0.0           # Web 管理界面
browser-use>=0.13      # browser-use 版（需 Python >=3.11）
playwright>=1.60       # Playwright（browser-use 版底层引擎）
```

## License

MIT
