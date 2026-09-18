# 免费线上部署指南（无需信用卡）

本项目支持两种免费部署方式，**均不需要信用卡**：

| 方案 | 适合场景 | 是否需要信用卡 | 持续运行 |
|------|---------|---------------|---------|
| **本机 + Cloudflare Tunnel**（推荐） | 用自己电脑跑，外网可访问管理界面 | ❌ 不需要 | ⚠️ 依赖本机开机 |
| **Hugging Face Spaces** | 免费 Docker 容器，24/7 运行 | ❌ 不需要 | ✅ 24/7（有资源限制） |

---

## 方案一：本机 + Cloudflare Tunnel（推荐，5 分钟搞定）

**原理**：在你自己的电脑上运行机器人，通过 Cloudflare Tunnel 把 Flask 管理界面暴露到公网，任何人都可以通过浏览器访问。

**优点**：
- 完全免费，不需要信用卡
- 不需要公网 IP
- 不需要域名（临时 URL 即可用）
- 你的电脑能跑 Chrome，浏览器自动化无障碍
- Cookie 安全存在本机，不上传到任何服务器

**缺点**：
- 电脑关机/休眠后机器人停止运行
- 临时 URL 每次重启会变（绑定域名后可固定）

### 步骤 1：安装 cloudflared

| 平台 | 命令 |
|------|------|
| **macOS** | `brew install cloudflared` |
| **Linux** | `wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x cloudflared-linux-amd64 && sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared` |
| **Windows** | 从 [GitHub Releases](https://github.com/cloudflare/cloudflared/releases) 下载 `cloudflared-windows-amd64.exe` |

### 步骤 2：启动机器人

```bash
./start_bot.sh    # macOS / Linux
start_bot.bat     # Windows
```

### 步骤 3：启动 Cloudflare Tunnel

**快速模式（无需域名，临时 URL）**：

```bash
./start_tunnel.sh    # macOS / Linux
start_tunnel.bat     # Windows
```

或者手动执行：
```bash
cloudflared tunnel --url http://localhost:5001
```

输出示例：
```
+--------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:            |
|  https://xxxx-yyyy-zzzz.trycloudflare.com                    |
+--------------------------------------------------------------+
```

打开该地址即可从任何地方访问你的 Flask 管理界面。

**正式模式（绑定自己的域名，地址固定）**：

1. 注册 Cloudflare 账号（免费）：https://dash.cloudflare.com/sign-up
2. 将你的域名托管到 Cloudflare（免费 DNS）
3. 执行以下命令：

```bash
# 登录
cloudflared tunnel login

# 创建命名隧道
cloudflared tunnel create boss-bot

# 配置隧道
cat > ~/.cloudflared/config.yml <<EOF
tunnel: <隧道UUID>
credentials-file: ~/.cloudflared/<隧道UUID>.json
ingress:
  - hostname: bot.yourdomain.com
    service: http://localhost:5001
  - service: http_status:404
EOF

# 添加 DNS 记录
cloudflared tunnel route dns boss-bot bot.yourdomain.com

# 启动
cloudflared tunnel run boss-bot

# 安装为系统服务（开机自启）
sudo cloudflared service install
```

### 安全提醒

公网暴露 Web 管理界面有风险，建议：
1. Cloudflare Dashboard 开启 **Zero Trust Access**（给访问加一层邮箱验证码，免费）
2. 或保持 `host="127.0.0.1"` 仅本地访问，通过 SSH 隧道远程访问

---

## 方案二：Hugging Face Spaces（免费 Docker 容器）

**原理**：Hugging Face 提供免费的 Docker 容器运行环境，可以 24/7 运行你的机器人。

**优点**：
- 完全免费，不需要信用卡
- 24/7 运行，不依赖你的电脑
- 自带公网 URL

**缺点**：
- 免费版资源有限（16GB RAM、2 vCPU）
- 需要适配无头 Chrome 环境
- BOSS 直聘可能对数据中心 IP 风控更严格
- 不支持持久化磁盘（重启后数据丢失，需用外部存储）

### 步骤 1：注册 Hugging Face 账号

访问 https://huggingface.co/join 注册（免费，不需要信用卡）

### 步骤 2：创建 Space

1. 访问 https://huggingface.co/new-space
2. **Owner**: 你的用户名
3. **Space name**: `boss-bot`
4. **SDK**: 选择 **Docker**
5. **Visibility**: Private（推荐，不公开你的代码）
6. 点击 **Create Space**

### 步骤 3：上传项目文件

将项目文件上传到 Space 的文件管理器，或用 Git 推送：

```bash
# 克隆你的 Space（注意用你的用户名替换）
git clone https://huggingface.co/spaces/你的用户名/boss-bot
cd boss-bot

# 复制项目文件（排除 venv、.git 等）
cp -r /path/to/sturgeon/* .
cp -r /path/to/sturgeon/.env.example .

# 推送
git add .
git commit -m "Deploy BOSS bot"
git push
```

### 步骤 4：配置环境变量

在 Space 的 **Settings → Repository secrets** 中添加：

| Key | Value |
|-----|-------|
| `AI_API_KEY_1` | 你的 AI API Key |
| `AI_BASE_URL` | `https://apihub.agnes-ai.com/v1` |
| `BOSS_BOT_HEADLESS` | `1` |

### 步骤 5：修改 Dockerfile 适配 Hugging Face

Hugging Face Spaces 要求：
- 应用监听 `0.0.0.0:7860`（不是 5001）
- Dockerfile 中不能有 `USER` 指令（以 root 运行）

修改 `flask-version/app.py` 最后的启动代码：
```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
```

修改 `Dockerfile`：
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver fonts-noto-cjk fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/chromium /usr/bin/google-chrome

ENV PYTHONUNBUFFERED=1 CHROME_PATH=/usr/bin/chromium TZ=Asia/Shanghai

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p messages logs accounts cookie_backups

EXPOSE 7860
CMD ["python", "flask-version/app.py"]
```

### 注意事项

- **Cookie 持久化**：Hugging Face Spaces 重启后磁盘数据会丢失。需要将 Cookie 保存到外部存储（如 GitHub Gist、Hugging Face Dataset）或每次重启后重新上传 Cookie。
- **安全验证**：数据中心 IP 更容易触发 BOSS 直聘的安全验证。建议先在本机有头模式下完成验证，获取 Cookie 后上传到 Space。
- **资源限制**：免费版 16GB RAM 足够运行 Chrome + Flask，但如果有多个账号同时运行可能会紧张。

---

## 部署后检查清单

- [ ] `curl http://localhost:5001/api/status` 返回正常 JSON
- [ ] Web 界面能看到 Cookie 状态
- [ ] 上传/保存 Cookie 后 `accounts/<账号>/cookies.json` 存在且非空
- [ ] 启动机器人后日志无报错
- [ ] 自进化状态 `curl http://localhost:5001/api/evolve/status` 返回 `running: true`
- [ ] Cloudflare Tunnel 公网 URL 可正常访问

---

## 方案对比总结

| 维度 | 本机 + Cloudflare Tunnel | Hugging Face Spaces |
|------|--------------------------|---------------------|
| **费用** | 免费 | 免费 |
| **信用卡** | 不需要 | 不需要 |
| **24/7 运行** | ❌ 依赖电脑开机 | ✅ |
| **Chrome 自动化** | ✅ 本机 Chrome | ✅ 容器内 Chromium |
| **Cookie 持久化** | ✅ 本机磁盘 | ❌ 重启丢失 |
| **BOSS 风控** | ✅ 家庭 IP | ⚠️ 数据中心 IP |
| **安全验证** | ✅ 有头模式可手动过 | ❌ 无头模式无法手动 |
| **配置难度** | ⭐ 极简 | ⭐⭐ 中等 |

**推荐**：先用 **本机 + Cloudflare Tunnel** 方案快速上线，如果需要 24/7 运行再考虑 Hugging Face Spaces。
