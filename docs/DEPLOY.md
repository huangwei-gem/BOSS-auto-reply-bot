# 免费线上部署指南

本项目支持三种免费部署方式，按推荐程度排序：

| 方案 | 适合场景 | 是否需要公网 IP | 持续运行 |
|------|---------|----------------|---------|
| **Oracle Cloud 免费 VPS**（最推荐） | 7×24 时刻后台运行 | ✅ 自带公网 IP | ✅ 24/7 |
| **本机 + Cloudflare Tunnel** | 用自己电脑跑，外网可访问管理界面 | ❌ 无需公网 IP | ⚠️ 依赖本机开机 |
| **Render.com / Hugging Face Spaces** | 仅 Web 管理界面（浏览器自动化受限） | ✅ 平台提供 | ⚠️ 免费版会休眠 |

> **重要说明**：本项目需要真实浏览器（Chrome/Chromium）运行自动化，最理想的免费方案是
> **Oracle Cloud Always Free VPS**（ARM 4核24G，永久免费，可 24/7 运行无头浏览器）。

---

## 方案一：Oracle Cloud 免费 VPS（最推荐）

### 免费额度（Always Free，永久免费，不是试用期）

- **AMD 实例**：2 台 `VM.Standard.E2.1.Micro`（1核 1G 内存 / 每台）
- **ARM 实例**：最高 4 核 24GB 内存（`VM.Standard.A1.Flex`，可拆成 1台 4核 或 4台 1核）
- **存储**：200GB 总量块存储
- **流量**：每月 10TB 出站流量（完全够用）
- **配置要求**：注册需一张信用卡（仅验证身份，免费套餐不扣费）

### 注册条件

1. 年满 18 岁，一张支持外币的信用卡（Visa/MasterCard）
2. 一个手机号（验证用）
3. 电子邮箱
4. 选择"Home Region"（注册后不可更改，建议选 `ap-osaka-1` / `ap-seoul-1` / `us-ashburn-1`，国内访问延迟较低可选首尔/大阪）

### 申请步骤

1. 访问 https://www.oracle.com/cloud/free/ → 点击 **Start for free**
2. 填写邮箱、国家 → 验证邮箱
3. 填写姓名、地址（与信用卡账单地址一致）→ 绑定信用卡验证（会预扣 1 美元再退回）
4. 选择 Home Region → 提交注册
5. 注册成功后登录 https://cloud.oracle.com

### 创建免费 VM 实例

1. 控制台左侧菜单 → **Compute** → **Instances** → **Create Instance**
2. 配置：
   - **Image**: Ubuntu 22.04（或 24.04）
   - **Shape**: `VM.Standard.A1.Flex`（ARM，免费额度内选 4 OCPU + 24GB 内存最佳）
   - **SSH Key**: 上传你的公钥或下载生成的私钥
3. 创建后记录公网 IP

### 部署本项目（ARM Ubuntu）

```bash
# 1. SSH 连接（首次用下载的私钥）
ssh -i <私钥路径> ubuntu@<公网IP>

# 2. 安装基础环境
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv git chromium-browser fonts-noto-cjk
# 字体必须装，否则页面中文乱码导致选择器失效

# 3. 克隆项目
git clone <你的仓库地址>
cd sturgeon

# 4. 创建虚拟环境并安装依赖
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install browser-use playwright flask
playwright install chromium

# 5. 配置环境变量
cp .env.example .env
nano .env   # 填入 AI_API_KEY_1 等

# 6. Docker 方式（推荐，隔离环境更干净）
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu
docker compose up -d --build
```

### 开放端口

控制台 → **Networking** → **Virtual Cloud Networks** → 你的 VCN →
**Security Lists** → Default Security List → **Add Ingress Rule**：
- Source CIDR: `0.0.0.0/0`
- IP Protocol: `TCP`
- Destination Port Range: `5001`

```bash
# 同时在系统防火墙放行
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5001 -j ACCEPT
sudo netfilter-persistent save
```

访问 `http://<公网IP>:5001` 即可打开 Web 管理界面。

### 开机自启（时刻后台运行）

用 systemd 创建服务：

```bash
sudo tee /etc/systemd/system/boss-bot.service > /dev/null <<EOF
[Unit]
Description=BOSS Auto Reply Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/sturgeon
Environment=PATH=/home/ubuntu/sturgeon/venv/bin:/usr/bin
ExecStart=/home/ubuntu/sturgeon/venv/bin/python flask-version/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now boss-bot
sudo systemctl status boss-bot   # 查看状态
journalctl -u boss-bot -f        # 看实时日志
```

---

## 方案二：本机 + Cloudflare Tunnel（内网穿透，5 分钟）

适合：不想买服务器、想让别人访问你本机上的 Web 管理界面。

### 前提

- 一个 Cloudflare 账号（免费注册 https://dash.cloudflare.com/sign-up）
- 一个已托管在 Cloudflare 的域名（没有域名也可用临时 URL，见下方"快速模式"）

### 快速模式（无需域名，临时 URL）

```bash
# macOS
brew install cloudflared

# 一条命令启动临时隧道（会随机生成 trycloudflare.com 临时地址）
cloudflared tunnel --url http://localhost:5001
```

输出示例：
```
+--------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:            |
|  https://xxxx-yyyy-zzzz.trycloudflare.com                    |
+--------------------------------------------------------------+
```

打开该地址即可从任何地方访问本机的 Flask 管理界面。
**注意**：快速模式的地址每次重启会变，仅供临时使用。

### 正式模式（绑定自己的域名，地址固定）

```bash
# 1. 登录
cloudflared tunnel login

# 2. 创建命名隧道
cloudflared tunnel create boss-bot

# 3. 配置隧道（创建 ~/.cloudflared/config.yml）
cat > ~/.cloudflared/config.yml <<EOF
tunnel: <隧道UUID>
credentials-file: /Users/<你>/.cloudflared/<隧道UUID>.json
ingress:
  - hostname: bot.yourdomain.com
    service: http://localhost:5001
  - service: http_status:404
EOF

# 4. 添加 DNS 记录
cloudflared tunnel route dns boss-bot bot.yourdomain.com

# 5. 启动
cloudflared tunnel run boss-bot

# 6. 安装为系统服务（开机自启）
sudo cloudflared service install
```

### 安全提醒

公网暴露 Web 管理界面有风险，建议：
1. Cloudflare Dashboard 开启 **Zero Trust Access**（给访问加一层邮箱验证码）
2. 或者修改 `flask-version/app.py` 中 `main()` 的 `host="127.0.0.1"` 保持仅本地，
   再通过 SSH 隧道访问：`ssh -L 5001:localhost:5001 ubuntu@<服务器IP>`

---

## 方案三：Render.com / Hugging Face Spaces（仅 Web 界面）

免费 Tier 提供 750 小时/月（Render），但 15 分钟无请求会休眠，且**不支持持久化
磁盘和真实 Chrome 自动化**（服务器无显示器浏览器可用 headless Chromium，但
BOSS 直聘对数据中心 IP 风控严格，容易触发验证码）。

- 本项目根目录已含 `render.yaml`，可一键部署 Web 界面
- 适合展示/管理，不适合跑真正的自动回复
- **结论：仅当没有 VPS 时的临时方案**

---

## 部署后检查清单

- [ ] `curl http://localhost:5001/api/status` 返回正常 JSON
- [ ] Web 界面能看到 Cookie 状态（`/api/cookie/status`）
- [ ] 上传/保存 Cookie 后 `accounts/<账号>/cookies.json` 存在且非空
- [ ] 启动机器人后 `journalctl -u boss-bot -f`（或本地 logs/）无报错
- [ ] 自动进化状态 `curl http://localhost:5001/api/evolve/status` 返回 `running: true`
- [ ] 重启服务器后服务自动拉起（`systemctl is-enabled boss-bot`）