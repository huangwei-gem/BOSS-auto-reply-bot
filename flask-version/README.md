# BOSS 自动回复机器人 - Flask Web 管理界面

## 快速启动

```bash
# 确保已安装依赖
pip install flask DrissionPage openai

# 启动 Web 界面
python flask-version/app.py
```

浏览器打开: http://127.0.0.1:5001

## 项目结构

```
flask-version/
├── app.py              # Flask 应用入口（工厂模式）
├── bot_loop.py         # 机器人主循环（与 main.py 共享逻辑）
├── routes/             # API 蓝图模块
│   ├── __init__.py     # 蓝图注册中心
│   ├── status.py       # 状态/控制/日志/Cookie/浏览器 API
│   ├── messages.py     # 消息/未读 API
│   ├── config.py       # 配置/提示词/日志文件 API
│   ├── accounts.py     # 多账号管理 API
│   └── optimize.py     # 自进化 API
├── templates/
│   └── index.html      # 前端单页应用
└── README.md           # 本文档
```

## API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | / | 主页（Web 界面） |
| **状态控制** | | |
| GET | /api/status | 运行状态 |
| POST | /api/start | 启动机器人 |
| POST | /api/stop | 停止机器人 |
| POST | /api/pause | 暂停（人工接管） |
| POST | /api/resume | 恢复自动回复 |
| GET | /api/stats | 统计数据 |
| GET | /api/notifications | 通知列表 |
| GET | /api/logs | 实时日志 |
| **消息** | | |
| GET | /api/unread | 未读消息列表 |
| GET | /api/messages | 所有会话列表 |
| GET | /api/messages/<name> | 会话详情 |
| **配置** | | |
| GET | /api/config | 基础配置 |
| GET | /api/prompts | 提示词与完整配置 |
| POST | /api/prompts | 保存配置修改 |
| GET | /api/logfiles | 日志文件列表 |
| GET | /api/logfile/<name> | 日志文件内容 |
| **账号** | | |
| GET | /api/accounts | 账号列表 |
| POST | /api/accounts | 创建账号 |
| DELETE | /api/accounts/<id> | 删除账号 |
| POST | /api/accounts/<id>/switch | 切换账号 |
| **优化** | | |
| POST | /api/optimize | 触发优化 |
| POST | /api/evolve | 触发 AI 进化 |
| GET | /api/evolve/status | 进化状态 |

## 功能

- 实时状态监控（运行状态、回复数、简历数）
- 未读消息列表查看
- 实时操作日志
- 一键启动/停止机器人
- 配置和规则查看 + 在线编辑
- 多账号管理
- 自进化控制
