# ClawShell

> **一云多端云边协同分布式神经系统** — v1.12.0

---

## 安装方案

```
┌─────────────────────────────────────────────────────────┐
│  云枢 (Cloud Hub)               端脑 (Edge Brain)        │
│  安装一次, 部署于ECS            每台机器安装一次          │
│                                                         │
│  clawshell-cloud install        clawshell install        │
│  ├─ 系统检测                    ├─ 系统检测               │
│  ├─ 克隆代码                    ├─ 框架发现(Hermes/Wukong)│
│  ├─ LLM/OSS API Keys            ├─ 云枢URL配置            │
│  ├─ systemd + cron              ├─ MemPalace + MemOS      │
│  └─ 验证12引擎                   └─ MCP注入 + Adapter      │
│                                                         │
│  幂等: 重复运行仅更新           幂等: 重复运行不破坏配置   │
└─────────────────────────────────────────────────────────┘
```

### 云枢安装 (ECS, 仅一次)

```bash
git clone https://github.com/jorinyang/ClawShell.git /opt/clawshell
python3 /opt/clawshell/bin/clawshell-cloud install
```

需要提供: DeepSeek API Key (必填), Aliyun AK (可选,启用OSS)

### 端脑安装 (每台本地机器)

```bash
git clone https://github.com/jorinyang/ClawShell.git ~/.clawshell
python3 ~/.clawshell/bin/clawshell install
```

需要提供: CloudHub URL (默认 `http://47.239.71.174`), MemOS Cloud Key (可选)

| 信息 | 云枢 | 端脑 | 必填 |
|------|:--:|:--:|:--:|
| DeepSeek API Key | ✅ | — | 云枢必填 |
| Aliyun AccessKey | ✅ | — | OSS可选 |
| CloudHub URL | — | ✅ | 有默认值 |
| MemOS Cloud Key | — | 可选 | 可选 |
| 注入框架选择 | — | ✅ | 自动发现 |

### 命令

```bash
# 云枢
clawshell-cloud install          交互式安装
clawshell-cloud status           状态检查
clawshell-cloud update           更新(幂等)

# 端脑
clawshell install                交互式安装
clawshell install --quick        静默安装
clawshell status                 状态检查
```

---

## 架构

```
☁️ Cloud Hub (ECS)                     🖥️ Edge Brain (WSL/macOS)
12 Engines: EventBus TaskBoard         MCP STDIO (18 tools)
SkillMarket BrainLLM Swarm             MemPalace · MemOS Bridge
OSS Vault · Cron · N8N                 Adapters: Hermes/Wukong
```

---

## 文档

- [安装最佳实践](docs/INSTALL_BEST_PRACTICES.md)
- [Wukong MCP集成](docs/WUKONG_INTEGRATION.md)
- [Release Notes](RELEASE_v1.12.0.md)

MIT
