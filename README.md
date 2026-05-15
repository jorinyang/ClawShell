# ClawShell

> **一云多端云边协同分布式神经系统** — v1.12.0

---

## 5 分钟上手

### 云枢部署 (ECS服务器)

**前置**: 阿里云账号 + DeepSeek API Key

1. 购买 ECS: 香港/新加坡, 2C4G, Ubuntu 22.04 → [详细指引](docs/CLOUD_HUB_DEPLOY.md)
2. SSH 登录后一键安装:

```bash
git clone https://github.com/jorinyang/ClawShell.git /opt/clawshell
python3 /opt/clawshell/bin/clawshell-cloud install
```

3. 根据提示输入 DeepSeek API Key，3分钟内完成

### 端脑部署 (本地机器)

```bash
git clone https://github.com/jorinyang/ClawShell.git ~/.clawshell
python3 ~/.clawshell/bin/clawshell install
```

自动发现 Hermes / Wukong，一键注入。

---

## 安装信息速查

| 需要的信息 | 云枢 | 端脑 | 获取方式 |
|-----------|:--:|:--:|------|
| DeepSeek API Key | ✅ 必填 | — | platform.deepseek.com/api_keys |
| Aliyun AccessKey | 可选 | — | ram.console.aliyun.com |
| CloudHub URL | — | 自动 | ECS公网IP |
| MemOS Cloud Key | — | 可选 | memos-dashboard.openmem.net |
| 框架选择 | — | 自动发现 | Hermes/Wukong/OpenClaw |

---

## 命令

```bash
# 云枢 (ECS)
clawshell-cloud install    交互式安装
clawshell-cloud status     健康检查
clawshell-cloud update     升级(幂等)

# 端脑 (本地)
clawshell install          交互式安装
clawshell install --quick  静默安装
clawshell status           状态检查
```

---

## 架构

```
☁️ Cloud Hub (ECS)                  🖥️ Edge Brain (WSL/macOS)
12 Engines active                   MCP STDIO (18 tools)
Brain LLM · EventBus · OSS Vault    MemPalace · MemOS Bridge
Cron (insight/review/optimize)      Adapters: Hermes/Wukong
```

---

## 文档

| 文档 | 内容 |
|------|------|
| [Cloud Hub 部署指南](docs/CLOUD_HUB_DEPLOY.md) | ECS购买+安装+Nginx+FAQ |
| [安装最佳实践](docs/INSTALL_BEST_PRACTICES.md) | 端脑安装+验证+排错 |
| [Wukong MCP 集成](docs/WUKONG_INTEGRATION.md) | MCP配置参考 |
| [Release v1.12.0](RELEASE_v1.12.0.md) | 完整变更记录 |
| [仓库对比分析](docs/REPO_COMPARISON_ANALYSIS.md) | ClawShell vs ClawShell-MacOS |

MIT
