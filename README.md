# ClawShell

> **一云多端云边协同分布式神经系统**
>
> Version 1.12.0 | Cloud Hub (云枢) + Edge Brain (端脑) | Engineering Cybernetics

---

## 快速安装

```bash
git clone https://github.com/jorinyang/ClawShell.git ~/.clawshell
python3 ~/.clawshell/bin/clawshell install
```

交互式向导会引导你完成全部配置：

```
╔══════════════════════════════════════╗
║     ClawShell v1.12.0 Installer     ║
╚══════════════════════════════════════╝

Step 1/5  系统检测 → OS/WSL/Python 自动识别
Step 2/5  框架发现 → Hermes / Wukong / OpenClaw 自动发现
Step 3/5  云枢连接 → CloudHub URL + 连通性测试
Step 4/5  记忆系统 → MemPalace + MemOS Cloud Key(可选)
Step 5/5  框架注入 → MCP配置 + Adapter 自动注入
```

### 安装需要提供的信息

| 信息 | 必填 | 默认值 | 说明 |
|------|:--:|------|------|
| CloudHub URL | 否 | `http://47.239.71.174` | 云枢地址 |
| Edge节点名称 | 否 | 自动检测主机名 | 在云枢中的标识 |
| MemOS Cloud API Key | 否 | (跳过) | 云端记忆同步(可选) |
| 注入目标框架 | — | 全部已发现 | Hermes/Wukong/OpenClaw |
| 启动MemOS Local | 否 | Yes | 本地记忆桥接(端口18800) |

### 快速安装（非交互）

```bash
python3 ~/.clawshell/bin/clawshell install --quick
```

### 安装后

```bash
clawshell status    # Edge + CloudHub 状态
```

**Wukong**: 重启后对话中直接调用 `clawshell_*` 工具  
**Hermes**: 对话中自动加载 clawshell skill

---

## 架构

```
┌──────────────────────────┐     ┌──────────────────────────────┐
│   ☁️ Cloud Hub (云枢)     │     │   🖥️ Edge Brain (端脑)        │
│   阿里云 ECS Hong Kong    │     │   WSL / macOS                │
│                          │     │                              │
│  12 Engines:             │     │  MCP STDIO Server (18 tools) │
│  EventBus · TaskBoard    │←───→│  MemPalace · MemOS Bridge    │
│  SkillMarket · Brain LLM │     │  Adapters: Hermes/Wukong     │
│  Swarm · Evolution       │     │  Detectors: 3 frameworks     │
│  OSS Vault · Cron        │     │  IDE Bridge: 5 agents        │
└──────────────────────────┘     └──────────────────────────────┘
```

### 云枢 12 引擎

| 引擎 | 功能 |
|------|------|
| `CloudEventBus` | 事件持久化 + SHA256去重 + 通配符查询 |
| `GlobalTaskBoard` | 任务CRUD + 状态机 |
| `SkillMarket` | 技能发布/发现/同步 |
| `CapabilityRegistry` | 节点注册 + 心跳 + 负载调度 |
| `SwarmCoordinator` | 多节点管理 |
| `CronScheduler` | 定时任务调度 |
| `EvolutionEngine` | 洞察聚合 → 模式挖掘 |
| `ReviewEngine` | 日/周/月复盘 |
| `BroadcastEngine` | 云端公告 + 最佳实践 |
| `N8NBridge` | 事件 → N8N 工作流路由 |
| `InsightEngine` | 实时洞察生成 |
| `CloudBrain` 🆕 | LLM根因分析 + 趋势判断 + 架构规划 + 记忆复盘 |

### 端脑核心组件

| 组件 | 功能 |
|------|------|
| `edge/mcp/edge_server.py` | MCP STDIO服务器 (15 tools) |
| `edge/mcp/memory_server.py` | 三层记忆系统 (3 tools) |
| `edge/mcp/memos_local_bridge.py` | MemOS本地桥接 (:18800) |
| `edge/adapters/` | Hermes/Wukong/OpenClaw适配器 |
| `edge/detector/` | 框架自动检测 |
| `bin/clawshell` | 交互式安装向导 |

---

## 命令

```bash
clawshell install           # 交互式安装
clawshell install --quick   # 静默安装
clawshell install --dry-run # 预览
clawshell status            # 状态检查
```

## 文档

- [安装最佳实践](docs/INSTALL_BEST_PRACTICES.md)
- [Wukong MCP集成](docs/WUKONG_INTEGRATION.md)
- [仓库对比分析](docs/REPO_COMPARISON_ANALYSIS.md)

## 许可证

MIT
