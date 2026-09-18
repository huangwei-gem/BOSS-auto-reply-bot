# BOSS Auto-Reply Bot

BOSS直聘自动化机器人 — 跨平台通用版本，支持 Windows / macOS / Linux。

> **一键启动**：脚本会自动检测 Python、创建虚拟环境、安装依赖，无需手动配置！

## 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/huangwei-gem/BOSS-auto-reply-bot.git
cd BOSS-auto-reply-bot
```

### 2. 配置 AI（可选）
```bash
cp .env.example .env
# 编辑 .env 填入你的 AI API Key
```

### 3. 运行启动脚本

| 平台 | 命令 | 说明 |
|------|------|------|
| **Windows** | `start_bot.bat` | 双击即可运行 |
| **macOS / Linux** | `./start_bot.sh` | 自动完成所有配置 |
| **通用** | `python -m boss_bot` | 需要自行安装依赖 |

首次运行脚本会自动：
- 检测 Python 3.8+
- 创建虚拟环境 `venv/`
- 安装依赖（DrissionPage、openai、flask）
- 检测 Chrome 浏览器
- 启动机器人

### 4. 首次使用
1. 启动后浏览器窗口会自动打开
2. 手动登录 BOSS 直聘
3. 登录后 Cookie 自动保存到 `zhipin_cookies.json`（通过 CDP `Storage.getCookies` 捕获完整 Cookie，含 HttpOnly）
4. 后续启动自动登录，无需重复操作

### 5. 配置个人画像
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

**方式一：CloakBrowser（推荐，带反检测）**
- GitHub：https://github.com/CloakHQ/CloakBrowser
- Windows x64：https://github.com/CloakHQ/CloakBrowser/releases/download/chromium-v145.0.7632.109.2/cloakbrowser-windows-x64.zip
- macOS ARM64：https://github.com/CloakHQ/CloakBrowser/releases/download/chromium-v145.0.7632.109.2/cloakbrowser-darwin-arm64.tar.gz

**方式二：Chrome-for-Testing（Google 官方）**
- 下载地址：https://github.com/GoogleChromeLabs/chrome-for-testing
- 选择 `chrome-win64` 版本下载

**方式三：自行打包**
- 安装 Chrome 后，复制安装目录到 `cloakbrowser-windows-x64/`

### 安装步骤

1. 下载便携版 Chrome
2. 解压到项目根目录：
   ```
   BOSS-auto-reply-bot/
   └── cloakbrowser-windows-x64/
       ├── chrome.exe
       ├── chrome.dll
       └── ...
   ```
3. 启动脚本会自动检测并使用便携版 Chrome

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
curl -X POST http://127.0.0.1:5001/api/browser/select \
  -H "Content-Type: application/json" \
  -d '{"browser":"portable"}'

# 切换到系统 Chrome
curl -X POST http://127.0.0.1:5001/api/browser/select \
  -H "Content-Type: application/json" \
  -d '{"browser":"chrome"}'
```

## 项目结构

```
BOSS-auto-reply-bot/
├── boss_bot/                    # 核心代码包
│   ├── __init__.py              # 包初始化（自动加载日志）
│   ├── __main__.py              # python -m boss_bot 入口
│   ├── config.py                # 全局配置（画像、话术、规则、AI 模型池）
│   ├── main.py                  # CLI 主入口
│   ├── page_handler.py          # 浏览器操作封装（健康检查、送达验证）
│   ├── browser_launcher.py      # 跨平台浏览器启动器（便携版优先）
│   ├── reply_engine.py          # 回复引擎（规则 → 意图 → AI → 兜底）
│   ├── rules.py                 # 关键词规则引擎
│   ├── intent.py                # 意图分类（8 种意图正则识别）
│   ├── prompts.py               # AI 提示词（画像驱动 + 多轮对话历史）
│   ├── state_store.py           # 会话状态持久化（去重、简历记录）
│   ├── stats.py                 # 统计数据持久化（按天、来源分布）
│   ├── notify.py                # 通知模块（重要事件 + Webhook）
│   ├── message_store.py         # 消息存储（JSON + TTL 缓存）
│   ├── self_optimizer.py        # 自进化引擎（AI 分析 + 定时迭代）
│   ├── account_manager.py       # 多账号管理（独立 Cookie/状态）
│   ├── event_logger.py          # 结构化事件日志（JSONL）
│   ├── log_manager.py           # 日志管理器（分组件 + 错误聚合）
│   └── diagnose.py              # 诊断工具
│
├── flask-version/               # Web 管理界面
│   ├── app.py                   # Flask 应用（工厂模式）
│   ├── bot_loop.py              # 机器人主循环
│   ├── routes/                  # API 蓝图
│   │   ├── status.py            # 状态/控制/日志 API
│   │   ├── messages.py          # 消息 API
│   │   ├── config.py            # 配置 API
│   │   ├── accounts.py          # 账号管理 API
│   │   └── optimize.py          # 自进化 API
│   └── templates/index.html     # 前端页面
│
├── tests/                       # 测试套件
│   └── test_unit.py             # 47 个单元测试
│
├── docs/                        # 文档
│   ├── DEPLOY.md                # 线上部署指南
│   └── TUNNEL_GUIDE.md          # 内网穿透教程
│
├── .env.example                 # 环境变量模板（AI 模型池配置）
├── .gitignore                   # Git 排除规则
├── user_profile.json            # 个人画像配置
├── mock_zhipin.html             # 测试用 mock 页面
├── requirements.txt             # Python 依赖
├── Dockerfile                   # Docker 镜像
├── docker-compose.yml           # Docker 编排
├── render.yaml                  # Render 部署配置
├── start_bot.bat                # Windows 一键启动
├── start_bot.sh                 # macOS/Linux 一键启动
├── start_tunnel.bat             # Windows 内网穿透
├── start_tunnel.sh              # macOS/Linux 内网穿透
└── README.md                    # 本文档
```

## 核心功能

### 自动回复机器人

持续监控 BOSS 直聘聊天页面的未读消息，自动回复。

**四级回复决策：**

| 层级 | 说明 | 示例 |
|------|------|------|
| 1. 关键词规则 | `REPLY_RULES` 精确命中，最高优先级 | "简历" → 发简历；"薪资" → 画像话术 |
| 2. 意图识别 | `intent.py` 正则模式识别 8 种意图 | "预算范围多少" → ask_salary |
| 3. AI 生成 | 多模型池，自动切换，带多轮对话历史 | 规则/意图均未命中时，AI 接续话题 |
| 4. 兜底 | `AI_FAIL_ACTION` 配置：`skip` 或 `default` | AI 全挂时宁可不回复 |

**意图分类：**

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
- 暂停后机器人仅监控不回复，通过 Web UI 或删除 `bot_state.json` 恢复

**防重复与防滥用：**
- 已处理消息哈希去重（重启不重复回复同一条消息）
- 简历每会话只发一次（重复索要降级为文字提醒）
- 每小时回复上限 30 条（可配置）
- 随机 2-5 秒人类操作延迟

### 自进化功能

机器人会自动分析回复效果并持续优化提示词和规则。

**工作原理：**
1. **数据收集**：分析 `messages/` 中所有会话的交互数据
2. **规则分析**：基于阈值的启发式建议
3. **AI 分析**：用 AI 智能分析效果差/好的回复，生成精准优化建议
4. **自动应用**：将建议写入 `config_overrides.json`
5. **效果追踪**：每次优化后记录日志，形成正向反馈循环

**定时自动进化：**
- Flask 启动时自动启动后台线程（默认每 1 小时迭代一次）
- API：`POST /api/evolve`（手动触发）、`GET /api/evolve/status`（查看状态）

### Flask Web 管理界面

提供 Web 界面管理机器人，访问 http://127.0.0.1:5001

**功能：**
- 实时状态监控（含暂停/人工接管状态）
- 未读消息列表
- 实时操作日志 + 日志文件查看
- 一键启动/停止
- 配置和规则查看 + 提示词在线编辑
- 通知列表、统计数据查看
- 暂停/恢复控制
- Cookie 管理
- 浏览器选择
- 多账号管理
- 自进化控制

### 日志系统

分组件日志，方便快速定位问题：

```bash
# 查看诊断报告
python -m boss_bot.diagnose

# 查看今日事件统计
python -m boss_bot.diagnose --today

# 查看错误记录
python -m boss_bot.diagnose --errors

# 实时监控日志
python -m boss_bot.diagnose --watch bot
```

日志文件：
- `logs/bot_YYYYMMDD.log` - 主日志
- `logs/browser_YYYYMMDD.log` - 浏览器操作
- `logs/ai_YYYYMMDD.log` - AI API 调用
- `logs/errors_YYYYMMDD.log` - 错误专用

## 配置 AI 回复

### .env 文件（推荐）
```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### AI 模型池配置

支持多模型自动切换，一个失败自动试下一个：

```bash
# .env 格式
ENABLE_AI=true

# 模型池：AI_PROVIDERS_N=api_key|model_name|base_url
AI_PROVIDERS_1=sk-xxx|agnes-2.5-flash|https://apihub.agnes-ai.com/v1
AI_PROVIDERS_2=sk-yyy|deepseek-v4-flash|https://token.sensenova.cn/v1
AI_PROVIDERS_3=sk-zzz|deepseek-v4-flash|https://token.sensenova.cn/v1

# AI 失败时的行为: skip（跳过）或 default（兜底话术）
AI_FAIL_ACTION=skip
```

### 可用 AI 模型

| 平台 | 模型 | 说明 |
|------|------|------|
| Agnes | `agnes-2.5-flash` | 快速模型 |
| 商汤 Sensenova | `deepseek-v4-flash` | DeepSeek 快速版 |
| 商汤 Sensenova | `deepseek-v4-pro` | DeepSeek 专业版 |
| 商汤 Sensenova | `SenseChat-5` | 商汤自研模型 |
| DeepSeek 官方 | `deepseek-flash` | 最稳定 |

## 配置说明

### 个人画像（`user_profile.json`）

| 占位符 | 字段 | 说明 |
|--------|------|------|
| `{salary}` | `salary_expectation` | 期望薪资 |
| `{interview_time}` | `available_interview_time` | 可面试时间 |
| `{position}` | `position` | 求职方向 |
| `{skills}` | `skills` | 技能列表（自动拼接） |
| `{experience}` | `experience` | 经历描述 |
| `{contact}` | `contact` | 联系方式 |

### 主要配置

```python
CHECK_INTERVAL = 8              # 检查间隔（秒）
CONTEXT_MESSAGE_COUNT = 10      # 读取聊天消息条数（多轮上下文）
MAX_REPLIES_PER_HOUR = 30       # 每小时最大回复数
ENABLE_AI = True                # 是否启用 AI 回复
AI_FAIL_ACTION = "skip"         # AI 全挂时：skip 或 default
PAUSE_ON_IMPORTANT = True       # 重要事件自动暂停转人工
RESUME_SEND_ONCE = True         # 简历每会话只发一次
NOTIFY_ENABLED = True           # 是否启用通知
```

## 免费线上部署

详见 **[DEPLOY.md](docs/DEPLOY.md)**，三种方案：

| 方案 | 适合场景 | 持续运行 |
|------|---------|---------|
| **Oracle Cloud 免费 VPS**（最推荐） | 7×24 后台运行 | ✅ 24/7 |
| **本机 + Cloudflare Tunnel** | 外网访问 | ⚠️ 依赖本机开机 |
| **Render.com** | 仅 Web 管理界面 | ⚠️ 免费版会休眠 |

## 运行测试

```bash
# 单元测试（47 项，无需浏览器）
python -m pytest tests/ -v

# 端到端测试（真实浏览器 + mock 聊天页）
python test_full_run.py
```

## 安全说明

- API Key 通过环境变量读取，不存储在代码中
- `.gitignore` 已排除所有敏感文件
- Cookie 文件请妥善保管，不要上传到公开仓库

## 依赖

```
DrissionPage>=4.1.0,<5.0.0  # 浏览器自动化
openai>=1.0.0          # OpenAI 兼容 API
flask>=3.0.0           # Web 管理界面
```

## License

MIT
