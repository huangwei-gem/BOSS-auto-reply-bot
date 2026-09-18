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
| **通用** | `python main.py`= | 需要自行安装依赖 |

首次运行脚本会自动：
- 检测 Python 3.8+
- 创建虚拟环境 `venv/`
- 安装依赖（DrissionPage、openai、flask）
- 检测 Chrome 浏览器
- 启动机器人

#### 3. 首次使用
1. 启动后浏览器窗口会自动打开
2. 手动登录 BOSS 直聘
3. 登录后 Cookie 自动保存（通过 CDP `Storage.getCookies` 捕获完整 Cookie，含 HttpOnly）
4. 后续启动自动登录，无需重复操作

**有头模式安全验证**：如果 BOSS 直聘检测到自动化并弹出安全验证页面，机器人会暂停等待你在浏览器窗口中手动完成验证（滑块/验证码），完成后自动保存 Cookie 并继续运行。

#### 4. 配置个人画像
编辑 `user_profile.json`，填入你的求职信息：
```json
{
  "name": "张三",
  "education": "本科学历",
  "position":E "数据分析",
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
| **Windows** | `start_bot.bat` | 系统 Chrome |
| **macOS** | `./start_bot.sh` | `/Applications/Google Chrome.app` |
| **Linux** | `./start_bot.sh` | `google-chrome` / `chromium` |

## 项目结构

```
sturgeon/
├── .env.example                 # 环境变量模板
├── .gitignore                   # 排除敏感文件
├── DEPLOY.md                    # 免费线上部署指南
├── TUNNEL_GUIDE.md              # 内网穿透使用教程（Cloudflare Tunnel）
├── Dockerfile                   # Docker 镜像（ARM/x86 双架构）
├── docker-compose.yml           # Docker Compose 编排
├── config.py                    # 配置文件（画像加载、话术渲染、规则、意图、通知等）
├── main.py                      # 主入口（命令行版）
├── page_handler.py              # 浏览器操作封装（跨平台、健康检查、安全验证处理）
├── reply_engine.py              # 回复引擎（规则 → 意图 → AI → 兜底，四级决策）
├── rules.py                     # 关键词规则引擎
├── intent.py                    # 意图分类（8 种意图正则识别）
├── prompts.py                   # AI 提示词（画像驱动 + 多轮对话历史）
├── state_store.py               # 会话状态持久化（去重、简历记录、暂停）
├── stats.py                     # 统计数据持久化
├── notify.py                    # 通知模块（重要事件检测 + Webhook 推送）
├── message_store.py             # 消息存储（JSON 持久化 + TTL 内存缓存）
├── self_optimizer.py            # 自进化引擎（人工 vs 机器对比学习）
├── ai_client.py                 # AI 客户端工厂（多候选轮换 + 代理支持）
├── account_manager.py           # 多账号管理（独立 Cookie/状态/配置）
├── browser_launcher.py          # 跨平台浏览器启动器（Chromium API）
├── user_profile.json            # 个人画像配置
├── mock_zhipin.html             # 端到端测试用 mock 聊天页
├── requirements.txt             # Python 依赖
├── start_bot.bat                # Windows 一键启动
├── start_bot.sh                 # macOS/Linux 一键启动
├── start_tunnel.bat             # Windows 一键内网穿透
├── start_tunnel.sh              # macOS/Linux 一键内网穿透
├── test_full_run.py             # 端到端集成测试（27 项）
├── test_real.py                 # 真机实测脚本（连接真实 BOSS）
├── tests/test_unit.py           # 单元测试套件（46 项）
├── README.md                    # 本文档
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
├── messages/                    # 真实消息记录
├── messages_test/               # 测试消息记录（TEST_MODE 隔离）
├── cookie_backups/              # Cookie 备份
└── logs/                        # 运行日志
```

## 核心功能

### 自动回复机器人

持续监控 BOSS 直聘聊天页面的未读消息，自动回复。

**四级回复决策：**

| 层级 | 说明 | 示例 |
|------|------|------|
| 1. 关键词规则 | `REPLY_RULES` 精确命中，最高优先级 | "简历" → 发简历；"薪资" → 画像话术 |
| 2. 意图识别 | `intent.py` 正则模式识别 ) 种意图 | "预算范围多少" → ask_salary |
| 3. AI 生成 | OpenAI 兼容 API，带入多轮对话历史 + 画像 | 规则/意图均未命中时，AI 接续话题 |
| 4. 兜底 | `AI_FAIL_ACTION` 配置：`skip` 或 `default` | AI 全挂时宁可不回复 |

**重要事件与转人工：**
- 面试邀约 / offer / 入职等关键词命中 → 自动通知 + 暂停转人工
- 通知写入 `notifications.json`，可选 Webhook 推送
- 暂停后机器人仅监控不回复，通过 Flask `/api/resume` 恢复

**防重复与防滥用：**
- 已处理消息哈希去重（重启不重复回复）
- 简历每会话只发一次
- 每小时回复上限 30 条
- 随机 2-5 秒人类操作延迟

**安全验证处理：**
- 有头模式：检测到安全验证页面时暂停，等待用户手动完成验证后自动继续
- 无头模式：检测到安全验证时通知用户，需在有头模式下完成验证

### 自进化功能（类似 Hermes）

机器人会自动分析人工回复与机器回复的差异，从中学习优化。

**工作原理：**
1. **数据收集**：区分人工回复（`is_mine: true` 但无 `source: "bot"`）和机器回复
2. **对比分析**：AI 从 5 个维度对比分析（语气、针对性、行动导向、信息密度、称呼使用）
3. **建议清洗**：自动清洗硬编码人名（防过拟合）、白名单校验、防规则堆积
4. **自动应用**：将建议写入 `config_overrides.json`（系统提示词规则、话术模板、回复规则）
5. **定时自动进化**：Flask 启动时自动启动后台线程（默认每 1 小时迭代一次）

### Flask Web 管理界面

```bash
python flask-version/app.py
# 打开 http://127.0.0.1:5001
```

功能：实时状态监控、消息查看、一键启停、配置编辑、多账号管理、自进化控制。

## 配置 AI 回复

### .env 文件（推荐）
```bash
cp .env.example .env
# 编辑 .env 填入 API Key
```

### 环境变量
| 变量 | 说明 |
|------|------|
| `AI_API_KEY_1` | AI API Key |
| `AI_BASE_URL` | API 地址（默认 `https://apihub.agnes-ai.com/v1`） |
| `AI_HTTP_PROXY` | HTTP 代理（可选，解决 TLS 超时） |

## 免费线上部署

详见 **[DEPLOY.md](DEPLOY.md)**，两种方案：

| 方案 | 适合场景 | 持续运行 |
|------|---------|---------|
| **本机 + Cloudflare Tunnel** | 用自己电脑跑，外网可访问 | ⚠️ 依赖本机开机 |
| **Hugging Face Spaces** | 免费 Docker 容器 | ⚠️ 有资源限制 |

**Cloudflare Tunnel** 可 5 分钟内让本机 Flask 界面从外网访问，无需公网 IP。详见 **[TUNNEL_GUIDE.md](TUNNEL_GUIDE.md)**。

## 运行测试

```bash
# 单元测试（46 项，无需浏览器）
python -m pytest tests/test_unit.py -v

# 端到端测试（27 项，真实浏览器 + mock 聊天页）
python test_full_run.py

# 真机实测（连接真实 BOSS 直聘）
python test_real.py --headless     # 无头模式
python test_real.py                # 有头模式
python test_real.py --send         # 实际发送回复
```

## 安全说明

- API Key 通过环境变量读取，不存储在代码中
- `.gitignore` 已排除 `.env`、`zhipin_cookies.json` 等敏感文件
- Cookie 文件请妥善保管，不要上传到公开仓库

## 依赖

```
DrissionPage>=4.1.0,<5.0.0  # 浏览器自动化
openai>=1.0.0                # OpenAI 兼容 API
flask>=3.0.0                 # Web 管理界面
```

## License

MIT
