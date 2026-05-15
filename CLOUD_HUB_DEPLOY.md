# ClawShell Cloud Hub 部署指南

> 从零到上线，完整云枢部署流程

---

## 前置准备清单

| 项目 | 说明 | 获取方式 |
|------|------|---------|
| ☑ 阿里云账号 | 实名认证 | https://aliyun.com |
| ☑ DeepSeek API Key | Brain LLM分析 | https://platform.deepseek.com/api_keys |
| ☑ 域名(可选) | 如 clawshell.your-domain.com | 任意域名注册商 |
| ☑ SSH 客户端 | 连接ECS | 系统自带 |

---

## 第一步：购买 ECS

### 推荐配置

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **地域** | 香港 / 新加坡 | 低延迟，无需备案 |
| **实例规格** | ecs.c6.large (2C4G) | 12引擎+LLM分析足够了 |
| **系统盘** | 40GB ESSD | 代码+日志+事件数据 |
| **操作系统** | Ubuntu 22.04 LTS | 长期支持 |
| **带宽** | 按量 100Mbps | 峰值弹性 |
| **月费用** | ≈¥120-150/月 | 香港2C4G参考价 |

### 购买步骤

1. 登录 [阿里云ECS控制台](https://ecs.console.aliyun.com)
2. 点击 **创建实例**
3. 地域选 **中国香港** 或 **新加坡**
4. 镜像选 **Ubuntu 22.04**
5. 规格选 **2 vCPU 4 GiB** (ecs.c6.large)
6. 系统盘 40GB，勾选 **随实例释放**
7. **登录凭证** → 选择 **密钥对** → 新建密钥对并下载 .pem
8. 带宽勾选 **分配公网IPv4**，计费方式 **按使用流量**
9. 安全组：开放 **22** (SSH), **80** (HTTP), **443** (HTTPS)
10. 确认订单，支付

### 安全组规则

| 端口 | 协议 | 来源 | 用途 |
|------|------|------|------|
| 22 | TCP | 你的IP/0.0.0.0 | SSH |
| 80 | TCP | 0.0.0.0 | HTTP/API |
| 443 | TCP | 0.0.0.0 | HTTPS (可选) |

---

## 第二步：连接 ECS

```bash
# 设置密钥权限
chmod 400 ~/Downloads/your-key.pem

# 连接到 ECS (替换为你的公网IP)
ssh -i ~/Downloads/your-key.pem root@<你的ECS公网IP>
```

首次连接确认指纹，输入 `yes`。

---

## 第三步：安装 ClawShell Cloud Hub

```bash
# 1. 克隆仓库
git clone https://github.com/jorinyang/ClawShell.git /opt/clawshell

# 2. 安装必要系统包
apt update && apt install -y python3 python3-pip git nginx curl

# 3. 运行安装向导
python3 /opt/clawshell/bin/clawshell-cloud install
```

安装向导会依次询问：

```
Step 1/5: 系统检测 → 自动验证 Python/git/systemd/root
Step 2/5: 克隆代码 → 自动
Step 3/5: 配置信息 → 需要你输入 API Keys
Step 4/5: 安装服务 → 自动配置 systemd + cron + OSS
Step 5/5: 验证健康 → 自动检查 12 引擎
```

### 需要输入的信息

| 提示 | 输入 | 示例 |
|------|------|------|
| `DeepSeek API Key` | DeepSeek 平台生成的 key | `sk-xxxxxxxxxxxxxxxx` |
| `Aliyun AccessKey ID` | OSS访问密钥 (可跳过) | `LTAI5t...` |
| `JWT Secret` | 按回车使用随机生成的 | (回车) |

---

## 第四步：验证

```bash
# 服务状态
systemctl status clawshell-cloud

# 健康检查
curl http://localhost:8000/health

# 应返回 12 engines active:
# {"status":"healthy","engines":{"eventbus":"active",...}}
```

---

## 第五步：配置 Nginx (可选)

```bash
cat > /etc/nginx/sites-available/clawshell << 'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/clawshell /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

之后可通过 `http://<公网IP>/health` 访问。

---

## 第六步：连接端脑

在本地机器上：

```bash
git clone https://github.com/jorinyang/ClawShell.git ~/.clawshell
python3 ~/.clawshell/bin/clawshell install
```

提示 CloudHub URL 时输入 ECS 公网 IP: `http://<你的ECS公网IP>`

---

## FAQ

### Q: 必须要阿里云 ECS 吗？
任何支持 Ubuntu 22.04、有公网 IP 的服务器都可以。AWS EC2、腾讯云 CVM、DigitalOcean 均可，只需改安全组规则。

### Q: 可以不用 DeepSeek 吗？
Brain LLM 分析依赖 DeepSeek API。可以用其他 OpenAI 兼容 API，编辑 `/opt/clawshell/.env` 中的 `LLM_BASE_URL` 和 `LLM_MODEL`。

### Q: 安装后如何升级？
```bash
clawshell-cloud update
```
自动 git pull + 重启服务，幂等操作，不覆盖 .env 配置。

### Q: 如何查看日志？
```bash
journalctl -u clawshell-cloud -f       # 实时
journalctl -u clawshell-cloud -n 50    # 最近50行
cat /opt/clawshell/logs/cron/cron.log  # 定时任务
```

### Q: OSS Vault 是什么？跳过有影响吗？
OSS Vault 是 Obsidian 知识库的云存储。跳过不影响核心功能（事件、任务、记忆、分析），仅 vault_search/sync 不可用。

### Q: 安全组怎么配？
阿里云控制台 → ECS → 安全组 → 配置规则 → 入方向：
- 22端口建议仅允许你的IP (`curl ifconfig.me` 查看)
- 80/443 可允许 0.0.0.0/0

### Q: 费用预估？
- 香港 ECS 2C4G: ≈¥120-150/月
- 流量费: ≈¥0.5/GB (按量)
- DeepSeek API: 按 token 计费，日常分析 ≈$1-5/月
- 总计: ≈¥150-200/月

### Q: 安装失败怎么办？
1. 确认是 root 用户: `whoami`
2. 检查系统版本: `lsb_release -a`
3. 查看服务日志: `journalctl -u clawshell-cloud -n 50`
4. 手动测试: `cd /opt/clawshell && python3 cloud/main.py`
