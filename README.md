# ClawShell 2.0

> **一云多端云边协同分布式神经系统**
>
> Version 1.2.0 | Cloud Hub (云枢) + Edge Brain (端脑) | Engineering Cybernetics | 智询工作室

---

## 架构全景

```
┌──────────────────────────────────────────────────────────────────────────────┐
│            ClawShell 2.0 — 一云多端云边协同分布式神经系统                      │
│     Version 1.2.0 | Cloud Hub + Edge Brain | Engineering Cybernetics        │
└──────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────┐  ┌───────────────────────────────────────────┐
│   ☁️ CLOUD HUB (云枢)         │  │   🖥️ EDGE BRAIN (端脑)                    │
│   Alibaba Cloud ECS           │  │   User Terminal                           │
│                               │  │                                           │
│ ┌─ API Gateway :8000 ───────┐ │  │ ┌─ L4 多Agent集群 ────────────────────┐  │
│ │ REST /api/v1/* (14 ep)    │ │  │ │ SwarmManager+Discovery              │  │
│ │ WebSocket /ws/events      │ │  │ │ TrustEvaluator+Manager              │  │
│ │ MCP WSS /mcp/ws :8443     │ │↕ │ │ EcologyMatcher·CollaborationProtocol│  │
│ │ Auth(JWT+Token+RateLimit) │ │D │ └────────────────────────────────────┘  │
│ └────────────────────────────┘ │A │                                           │
│                               │T │ ┌─ L3 自组织 ─────────────────────────┐  │
│ ┌─ 12 Core Engines ─────────┐ │A │ │ EdgeEventBus(Condition+DLQ+Tracer)  │  │
│ │ EventBus · TaskBoard      │ │  │ │ TaskOrganizer(DAG)·ContextManager   │  │
│ │ SkillMarket · CapRegistry │ │F │ │ N8N Workflow                        │  │
│ │ SwarmCoord · CronSched    │ │L │ └────────────────────────────────────┘  │
│ │ Evolution · ReviewEngine  │ │O │                                           │
│ │ Broadcast · N8NBridge     │ │W │ ┌─ L2 自适应 ─────────────────────────┐  │
│ │ 🆕 Workflow · 🆕 Optimizer│ │  │ │ SelfRepair(Backup+Checkpoint)        │  │
│ │ 🆕 DeepThinkEngine        │ │  │ │ FeedbackControlLoop·AdaptiveTuner   │  │
│ └────────────────────────────┘ │  │ │ Strategy·AdaptiveController          │  │
│                               │  │ └────────────────────────────────────┘  │
│ ┌─ 🆕 Event Sourcing (9) ───┐ │  │                                           │
│ │ Store·Tracer·DeadLetterQ  │ │  │ ┌─ L1 自感知 ─────────────────────────┐  │
│ │ PriorityQ·Aggregator      │ │  │ │ System·Disk·Process·Network          │  │
│ │ Metrics·PatternMiner      │ │  │ │ Service·Agent·Gateway                │  │
│ │ MLEngine·QualityEvaluator │ │  │ │ HealthChecker(27 items)              │  │
│ └────────────────────────────┘ │  │ └────────────────────────────────────┘  │
│                               │  │                                           │
│ ┌─ 🆕 MCP Protocol Layer ───┐ │  │ ┌─ 🆕 Edge Gateway ───────────────────┐  │
│ │ MCPHub·JWT Auth            │ │  │ │ NetworkDiscovery·DeviceMonitor       │  │
│ │ 7-Domain Router            │ │  │ │ KnowledgePuller·SelfHealing          │  │
│ └────────────────────────────┘ │  │ └────────────────────────────────────┘  │
│                               │  │                                           │
│ ┌─ Cloud Services ──────────┐ │  │ ┌─ Core Components ───────────────────┐  │
│ │ VaultAPI·OSS Sync·MemOS   │ │  │ │ EnvDetector (8 frameworks)           │  │
│ │ 🆕 KnowledgeGraph          │ │  │ │ IDEBridge (6 CLI agents)             │  │
│ └────────────────────────────┘ │  │ │ Ecosystem Installer (10 comp)        │  │
│                               │  │ │ ConfigWizard·Edge CLI                │  │
│ ┌─ Deployment ──────────────┐ │  │ │ SyncDaemon(5s)·SyncEngine(Delta)     │  │
│ │ Terraform·Docker·install  │ │  │ │ AdapterManager                       │  │
│ └────────────────────────────┘ │  │ └────────────────────────────────────┘  │
└───────────────────────────────┘  │                                           │
                                    │ Frameworks: Hermes·OpenClaw·Wukong       │
                                    │ QClaw·CoPaw·HiClaw·EasyClaw·WorkBuddy    │
                                    │ IDEs: Codex·Claude·Kimi·DeepSeek·Copilot │
                                    │ Eco: psutil·ws·chromadb·MemPalace·N8N    │
                                    │ MemOS·Watchdog·BrowserRT·ONNX·Obsidian   │
                                    └───────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  🔄 DATA FLOW                                                                 │
│  Cloud→Edge: REST(:8000) WSS(:8443) Tasks Events Skills Insight              │
│  Edge→Cloud: Health Events Register Claim Discover Sync                      │
│  SyncDaemon: scan→enqueue→flush→pull→health (5s loop)                        │
├──────────────────────────────────────────────────────────────────────────────┤
│  🧬 PERSISTENCE: Genome · MemOS Cloud · MemPalace · Obsidian · KnowledgeGraph│
│  EventStore(JSON) · WorkflowState · TaskBoard · SkillMarket · Review          │
├──────────────────────────────────────────────────────────────────────────────┤
│  ☁️ EXTERNAL: Alibaba ECS+OSS · GitHub · N8N · Docker · Claude+OpenAI API    │
│  ChromaDB · MemOS Cloud API · Browser Runtime · psutil · websockets           │
└──────────────────────────────────────────────────────────────────────────────┘
```

> **完整交互式 SVG 架构图**: [docs/architecture-diagram.html](docs/architecture-diagram.html) (下载后在浏览器中打开)

---

## 概述

ClawShell 是一个适用于类 OpenClaw 架构的增强型外骨骼功能插件，以工程控制论为指导思想，
核心是信息反馈、动态调控和系统整体思维。

采用**一云多端云边协同分布式神经架构**，由 1 个云枢（Cloud Hub）和 N 个端脑（Edge Brain）组成：

- **☁️ 云枢**: 部署于阿里云 ECS，负责全局架构规划、深度思考、洞察分析、复盘总结、成果广播、终端管理
- **🖥️ 端脑**: 安装于用户终端，自适应不同类 OpenClaw 架构，负责环境检测、IDE 桥接、任务执行和离线自治

---

## 云枢 (Cloud Hub) — 12 Engines

| 引擎 | 功能 |
|------|------|
| `CloudEventBus` | Persist + SHA256 Dedup + Wildcard Query + 30d Expiry |
| `GlobalTaskBoard` | CRUD + State Machine (PENDING→IN_PROGRESS→COMPLETED/FAILED/CANCELLED/COMPENSATING) |
| `SkillMarket` | Publish/Discover/Sync + Version History |
| `CapabilityRegistry` | Edge Registration + Heartbeat + Load-Balanced Scheduling |
| `SwarmCoordinator` | Multi-Node Management + Load Balance + Offline Detection |
| `CronScheduler` | 5-field Cron Parser + 60s Check Loop |
| `EvolutionEngine` | InsightAggregator → PatternMiner → AutoSkillPublisher |
| `UnifiedReviewEngine` | Daily/Weekly/Monthly Review → ActionPlan + Metrics |
| `BroadcastEngine` | Cloud Announcement + BestPracticeRegistry + CrossEdgeLearning |
| `N8NBridge` | Event → N8N Workflow Routing |
| `WorkflowEngine` 🆕 | Built-in Saga Compensation + StepType(TASK/PARALLEL/CONDITION/SAGA/WAIT) |
| `GlobalOptimizer` 🆕 | Resource Quota + Cost Model + Balanced Allocation |

### 🆕 Event Sourcing (9 modules)

| 模块 | 功能 |
|------|------|
| EventStore | Append-only persistent storage + Sequence-based replay |
| EventTracer | Causal chain tracking + Span/Trace analysis |
| DeadLetterQueue | Failed event replay + Configurable retry |
| PriorityQueue | Heap-based CRITICAL/HIGH/MEDIUM/LOW ordering |
| EventAggregator | Time-window aggregation + Flush to JSON |
| EventMetrics | Per-topic statistics + Latency + Error rate + Moving average |
| PatternMiner | Sequential + Co-occurrence pattern detection |
| MLEngine | Z-score anomaly detection + Linear trend analysis |
| QualityEvaluator | 4-dim scoring (Completeness/Timeliness/Correctness/Consistency) |

### 🆕 MCP Protocol Layer

| 模块 | 功能 |
|------|------|
| MCPHub | WebSocket MCP Router + Client lifecycle |
| JWT Auth | HS256 token generation/verification (stdlib-only) |
| Domain Router | 7 domains: vault/skill/kanban/memory/node/workflow/genome |

---

## 端脑 (Edge Brain) — 四层外骨骼

| 层 | 名称 | 组件 |
|----|------|------|
| **L4** | 多Agent集群 | SwarmManager+Discovery · TrustEvaluator+Manager · EcologyMatcher · CollaborationProtocol |
| **L3** | 自组织 | EdgeEventBus(Condition+DLQ+Tracer) · TaskOrganizer(DAG) · ContextManager · N8N |
| **L2** | 自适应 | SelfRepair(Backup+Checkpoint) · FeedbackControlLoop · AdaptiveParameterTuner · Strategy |
| **L1** | 自感知 | SystemMon · DiskMon · ProcessMon · NetworkMon · ServiceMon · HealthChecker(27 items) |

### 🆕 Edge Gateway + Core Components

| 组件 | 功能 |
|------|------|
| NetworkDiscovery | LAN UDP broadcast device discovery (:17660) |
| DeviceMonitor | Real-time CPU/Mem/Disk/Net health monitoring |
| KnowledgePuller | Cloud insight/broadcast local cache |
| EdgeSelfHealing | Diagnose→Heal→Verify pipeline |
| EnvDetector | 8 framework auto-detection |
| IDEBridge | 6 Agent CLI bridges (Codex/Claude/Kimi/DeepSeek/Copilot + Orchestrator + Sandbox) |
| EcosystemInstaller | 10 component one-click install |
| AdapterManager | Unified Hermes/OpenClaw/Wukong adapter management |
| SyncDaemon | 5s loop: scan→enqueue→flush→pull→health |

---

## Data Flow

```
Cloud→Edge (Push):  REST API(:8000) · WSS/MCP(:8443) · Event Push · Broadcast · Task Assign · Insight
Edge→Cloud (Report): Event Batch · Health Report · Node Register · Task Claim · Skill Discover
SyncDaemon 5s:       scan→enqueue→flush→pull tasks→pull insights→pull broadcasts→health
```

---

## 设计原则

> **指导思想**: Engineering Cybernetics — 信息反馈 · 动态调控 · 系统整体思维

| # | 原则 | 说明 |
|---|------|------|
| 1 | 异构同效 | 不同架构/技术栈模块在同一机制下发挥同等效能 |
| 2 | 无侵入 | 不修改任何已部署框架核心代码 |
| 3 | 低耦合 | 模块间通过文件协议和 EventBus 通信 |
| 4 | 高鲁棒 | 多层级错误恢复、守护进程保活、自动降级 |
| 5 | 高泛用 | 感知层抽象、适配器模式、标准化接口 |
| 6 | 高协同 | EventBus + ContextManager + TaskMarket + Swarm |
| 7 | 可移植 | 支持 macOS/Linux/WSL |
| 8 | 幂等性 | 重复安装不对已有配置产生副作用 |
| 9 | 端-云版本解耦 | Cloud Hub 升级不影响 Edge Brain |

---

## 快速开始

```bash
# 端侧安装 (一键)
curl -fsSL https://raw.githubusercontent.com/jorinyang/ClawShell/main/deploy/edge/install.sh | bash

# 云侧部署 (Terraform)
cd deploy/cloud/terraform
terraform init && terraform apply

# 本地开发
git clone https://github.com/jorinyang/ClawShell.git
cd ClawShell
pip install -e ".[cloud,edge]"
```

## 项目结构

```
ClawShell/
├── cloud/              # ☁️ Cloud Hub
│   ├── engines/        #   12 engines + Workflow · Optimizer · DeepThink
│   ├── eventing/       #   Event Sourcing (9 modules)
│   ├── mcp/            #   MCP Protocol (Hub · JWT · Router)
│   └── services/       #   VaultAPI · OSSSync · MemOS · KnowledgeGraph
├── edge/               # 🖥️ Edge Brain
│   ├── eventbus/       #   ConditionEngine + DLQ + Tracer
│   ├── gateway/        #   NetworkDiscovery · DeviceMonitor · KnowledgePuller · SelfHealing
│   ├── adapters/       #   Hermes · Wukong · OpenClaw + AdapterManager
│   ├── detector/       #   8 framework detectors
│   ├── ide_bridge/     #   6 IDE CLI bridges
│   ├── ecosystem/      #   10 component installer
│   └── sync/           #   SyncDaemon (5s loop) + Delta Sync
├── exoskeleton/        # 🦴 L1-L4 外骨骼
├── shared/             # 🔄 共享类型 · 协议 · MCP Types
├── deploy/             # 🚀 Terraform + Docker
├── tests/              # 🧪 412 comprehensive tests
└── docs/               # 📚 文档 + SVG 架构图
```

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
