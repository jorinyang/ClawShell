<div align="center">
  <h1>🦀 ClawShell</h1>
  <p><strong>一云多端云边协同分布式神经系统</strong></p>
  <p>Cloud-Edge Collaborative Distributed Neural System</p>

  <p>
    <a href="https://clawshell.club"><img src="https://img.shields.io/badge/website-clawshell.club-22d3ee?style=flat-square" alt="Website"></a>
    <a href="https://github.com/jorinyang/ClawShell/releases"><img src="https://img.shields.io/badge/release-v2.2.0-6366f1?style=flat-square" alt="Version"></a>
    <a href="#"><img src="https://img.shields.io/badge/tests-586%2F586%20passed-34d399?style=flat-square" alt="Tests"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-fbbf24?style=flat-square" alt="License"></a>
    <a href="#"><img src="https://img.shields.io/badge/lines-~42K-f472b6?style=flat-square" alt="Lines"></a>
  </p>
</div>

---

## 这是什么

ClawShell 是一个**增强型外骨骼功能插件**，为类 OpenClaw 架构的 AI Agent 提供云边协同基础设施。

```
你的 AI Agent (Hermes / Wukong / Claude Code / ...)
              ↓ 接入 ClawShell
  ☁️  19 引擎云端调度 + 跨设备记忆同步
  🖥️  4 层外骨骼自感知/自适应/自组织/集群协作
  🔌  MCP 协议自动注入，零配置即插即用
```

> **一句话安装**：复制下面这句话发给任意 AI Agent，它自动完成全部部署。
> ```
> 请帮我完成安装与配置：https://github.com/jorinyang/clawshell
> ```

---

## 快速开始

```bash
# 🤖 Agent 模式（推荐）
# 对 Claude Code / Hermes / Codex 说：
请帮我完成安装与配置：https://github.com/jorinyang/clawshell

# 📦 CLI 模式
curl -fsSL https://clawshell.club/install.sh | bash

# 🪟 Windows
iwr https://clawshell.club/install.ps1 | iex
```

Agent 会自动检测环境、安装依赖、注入 MCP 配置并生成自检报告。**人类只提供 2 个 API Key。**

---

## 架构全景

| 图表 | |
|------|------|
| 🗺️ **系统架构全景** | [官网](https://clawshell.club/#architecture) · [独立页](https://clawshell.club/architecture.html) — 19 Engines + 35 Edge Components |
| 📊 **业务架构图** | [官网](https://clawshell.club/#biz-arch) · [独立页](https://clawshell.club/ClawShell_Business_Architecture.html) — 4 层业务模型 |
| 🔗 **数据关系图** | [官网](https://clawshell.club/#data-rel) · [独立页](https://clawshell.club/ClawShell_Data_Relationship.html) — 数据源→存储→消费 |

---

## 能力矩阵

### ☁️ CloudHub 云枢 — 19 引擎

| 引擎 | 职责 |
|------|------|
| `EventBus` `TaskBoard` `SkillMarket` | 事件流 · 任务分发 · 技能发布 |
| `CapRegistry` `SwarmCoord` `Scheduler` | 节点管理 · 集群协调 · Cron 调度 |
| `Evolution` `Review` `Broadcast` | 系统进化 · 深度复盘 · 广播通知 |
| `Workflow` `Optimizer` `DeepThink` | 工作流编排 · 成本优化 · 深度推理 |
| `Insight` `Topology` `Brain` | 系统洞察 · 拓扑分析 · LLM 智能 |
| `KnowledgeGraph` `PubSub` | 知识图谱 · 发布订阅 |
| 🆕 `CloudCronSupervisor` | 5 规则健康监测 + 自动修复派发 |
| 🆕 `DispatchRouter` | 3 层分流: EventBus→TaskBoard→MCP→Manual |

### 🖥️ Edge Brain 端脑 — 35 组件

| 层级 | 能力 |
|------|------|
| **L1 自感知** | 27 项健康检测 |
| **L2 自适应** | SelfRepairEngine (4 策略) · PI 控制器 · AdaptiveTuner |
| **L3 自组织** | EdgeEventBus · TaskOrganizer (DAG) · 🆕 CronReporter |
| **L4 集群** | SwarmManager · TrustEvaluator · EcologyMatcher |
| 🆕 **Installer** | Agent-First · 10 Agent + 8 IDE 自动发现 · MCP 注入 |
| 🔌 **MCP** | 19 tools (edge + memory) · STDIO · 自动激活 |

### 🔄 数据同步

| 通道 | 说明 |
|------|------|
| **REST API** | 76+ 端点 · JWT 鉴权 · AES-256-GCM 加密 |
| **WebSocket** | 实时事件推送 · Dashboard 动态更新 |
| **MCP Protocol** | 19 工具 STDIO · Agent 自动注入 |
| **SyncDaemon** | 5 秒云边同步 · 9 步协议 · 离线持久化 |

---

## 技术规格

| 指标 | 数据 |
|------|------|
| 云引擎 | 19 (Python 3.10+, stdlib-only, RLock thread-safe) |
| 边缘组件 | 35 (L1-L4 外骨骼 + MCP + Installer + Gateway + IDE Bridge) |
| API 端点 | 76+ (REST + WebSocket + MCP) |
| 测试覆盖 | **586/586 passed** (10 维度 × 10 边界) |
| 代码规模 | ~42,000 lines (Python 39K + Scripts + Config) |
| Agent 检测 | 10 (Hermes/Wukong/OpenClaw/QClaw/CoPaw/HiClaw/EasyClaw/WorkBuddy/Cline/Cursor) |
| IDE 检测 | 8 (Codex/Claude/Kimi/DeepSeek/Copilot/Windsurf/Orchestrator/Sandbox) |
| LLM 支持 | DeepSeek V4 Pro · MiniMax M2.7 · OpenAI · Anthropic |
| 部署 | ECS HK · Docker · Nginx SSL · Cloud Assistant |

---

## 设计原则

> **Engineering Cybernetics** — 信息反馈 · 动态调控 · 系统整体思维

**异构同效** · **无侵入** · **Agent-First** · **高内聚 · 低耦合** · **幂等性** · **端-云解耦**

---

## 许可证

MIT © [智询工作室](https://clawshell.club)
