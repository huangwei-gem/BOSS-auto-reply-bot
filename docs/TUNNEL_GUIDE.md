# 内网穿透使用教程（Cloudflare Tunnel）

通过 Cloudflare Tunnel，将本机运行的 BOSS 机器人 Web 管理界面暴露到公网，
让你在任何设备（手机、其他电脑）上都能远程访问和管理机器人。

> **原理**：cloudflared 在本机和 Cloudflare 之间建立一条加密隧道，
> 外部访问 `xxx.trycloudflare.com` 时，流量通过隧道转发到本机 `localhost:5001`。
> 无需公网 IP、无需路由器端口映射、无需防火墙配置。

---

## 一、安装 cloudflared

### macOS

```bash
# 方式 1：Homebrew（推荐，如果网络通畅）
brew install cloudflared

# 方式 2：手动下载（如果 brew 超时，用代理下载）
# 设置代理（将 7897 替换为你的代理端口）
export https_proxy=http://127.0.0.1:7897

# 下载 macOS ARM 版（M1/M2/M3 芯片）
curl -L -o /tmp/cloudflared.tgz \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz"

# 下载 macOS Intel 版（老款 Mac）
curl -L -o /tmp/cloudflared.tgz \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"

# 解压并安装
tar -xzf /tmp/cloudflared.tgz -C /tmp/
sudo cp /tmp/cloudflared /usr/local/bin/cloudflared
cloudflared --version  # 验证安装
```

### Windows

```powershell
# 方式 1：Winget（Windows 10/11 自带）
winget install --id Cloudflare.cloudflared

# 方式 2：手动下载
# 用浏览器打开以下地址下载（如需代理，在浏览器中设置代理）：
# ARM 版（Surface Pro X 等）：https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-arm64.exe
# 64 位版（绝大多数 Windows）：https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

# 下载后放到项目目录或任意 PATH 路径下，重命名为 cloudflared.exe
# 验证安装：
cloudflared.exe --version
```

### Linux（Ubuntu/Debian）

```bash
# 方式 1：apt 安装
sudo apt install -y cloudflared

# 方式 2：手动下载
curl -L -o /tmp/cloudflared \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
# 或 x86 版：
curl -L -o /tmp/cloudflared \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"

sudo cp /tmp/cloudflared /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared
cloudflared --version
```

---

## 二、快速模式（临时 URL，无需账号域名）

最简单的用法，一条命令即可获得公网地址。适合临时使用或测试。

### 启动步骤

1. **先启动 BOSS 机器人**（确保 `http://localhost:5001` 可访问）
2. **再启动隧道**：

```bash
# macOS / Linux
cloudflared tunnel --url http://localhost:5001

# Windows
cloudflared.exe tunnel --url http://localhost:5001
```

3. **获取公网 URL**：命令输出中会显示类似：

```
+--------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:            |
|  https://xxxx-yyyy-zzzz.trycloudflare.com                    |
+--------------------------------------------------------------+
```

4. **访问**：在任意设备的浏览器中打开该 URL，即可看到 BOSS 机器人管理界面。

### 一键启动脚本

项目已提供一键脚本，自动启动机器人 + 隧道：

| 平台 | 脚本 |
|------|------|
| macOS / Linux | `./start_tunnel.sh` |
| Windows | `start_tunnel.bat` |

### 注意事项

- 临时 URL **每次重启 cloudflared 都会变**，不固定
- 临时隧道 **无 SLA 保证**，Cloudflare 可能随时断开
- 适合临时调试和演示，不适合长期稳定使用
- 如需固定地址，请使用下方"正式模式"

---

## 三、正式模式（绑定域名，固定地址）

适合长期使用。需要一个 Cloudflare 账号和一个域名（域名需托管在 Cloudflare）。

### 前提条件

- 注册 Cloudflare 账号（免费）：https://dash.cloudflare.com/sign-up
- 一个域名，且 DNS 托管在 Cloudflare（在 Cloudflare Dashboard 添加域名即可）

### 配置步骤

```bash
# 1. 登录 Cloudflare（浏览器会弹出授权页面）
cloudflared tunnel login

# 2. 创建命名隧道
cloudflared tunnel create boss-bot

# 3. 记录输出中的隧道 UUID 和 credentials-file 路径
# 输出示例：
# Created tunnel boss-bot with id <UUID>
# Your tunnel's credentials are stored at /Users/<你>/.cloudflared/<UUID>.json

# 4. 创建配置文件
# macOS / Linux：
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml <<EOF
tunnel: <替换为隧道UUID>
credentials-file: /Users/<你的用户名>/.cloudflared/<替换为隧道UUID>.json
ingress:
  - hostname: bot.yourdomain.com
    service: http://localhost:5001
  - service: http_status:404
EOF

# Windows（PowerShell）：
mkdir "$env:USERPROFILE\.cloudflared" -Force
# 手动创建 config.yml 文件，内容同上，注意 credentials-file 路径改为：
# C:\Users\<你的用户名>\.cloudflared\<UUID>.json

# 5. 添加 DNS 记录（将 bot.yourdomain.com 指向隧道）
cloudflared tunnel route dns boss-bot bot.yourdomain.com

# 6. 启动隧道
cloudflared tunnel run boss-bot
```

### 设为系统服务（开机自启）

```bash
# macOS / Linux
sudo cloudflared service install
# 启动/停止/查看状态：
sudo launchctl start cloudflared   # macOS
sudo systemctl start cloudflared   # Linux
sudo systemctl status cloudflared  # Linux

# Windows（管理员权限运行）
cloudflared.exe service install
# 在"服务"管理器中查看和启动 cloudflared 服务
```

### 安全加固

公网暴露管理界面有风险，强烈建议至少做一项：

1. **Cloudflare Zero Trust Access**（推荐）：在 Cloudflare Dashboard → Zero Trust → Access，
   给 `bot.yourdomain.com` 添加访问策略（如邮箱验证码），只有授权的人才能访问。

2. **SSH 隧道**（更安全）：不暴露公网，改为：
   ```bash
   # 在远程电脑上执行：
   ssh -L 5001:localhost:5001 <用户名>@<本机IP>
   # 然后本地浏览器访问 http://localhost:5001
   ```

---

## 四、常见问题

### Q: cloudflared 下载超时怎么办？

设置代理后重试：
```bash
# macOS / Linux
export https_proxy=http://127.0.0.1:7897  # 替换为你的代理端口
curl -L -o /tmp/cloudflared.tgz "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz"

# Windows（PowerShell）
$env:HTTPS_PROXY = "http://127.0.0.1:7897"
Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile "cloudflared.exe"
```

### Q: 启动隧道后 URL 访问不了？

- DNS 传播需要几秒钟，等待 5-10 秒后重试
- 确认本机 `http://localhost:5001` 能正常访问（先启动 Flask 应用）
- 检查 cloudflared 输出日志中是否有错误

### Q: 隧道断开了怎么办？

- 临时模式：重新运行 `cloudflared tunnel --url http://localhost:5001`，获取新 URL
- 正式模式：cloudflared 会自动重连，无需手动干预
- 系统服务模式：`sudo systemctl restart cloudflared`（Linux）或重启电脑

### Q: 能否同时穿透多个端口？

可以，在 `config.yml` 中添加多条 ingress 规则：
```yaml
ingress:
  - hostname: bot.yourdomain.com
    service: http://localhost:5001
  - hostname: api.yourdomain.com
    service: http://localhost:8080
  - service: http_status:404
```

### Q: 手机上能访问吗？

可以。只要手机有网络，在浏览器中打开隧道 URL 即可。
BOSS 机器人的 Web 管理界面已适配移动端布局。

---

## 五、快速验证清单

- [ ] `cloudflared --version` 能正常输出版本号
- [ ] 本机 `http://localhost:5001/api/status` 返回 JSON
- [ ] 隧道启动后输出中包含 `trycloudflare.com` URL
- [ ] 在另一台设备上访问该 URL，能看到管理界面
- [ ] `/api/status` 通过公网 URL 返回 200