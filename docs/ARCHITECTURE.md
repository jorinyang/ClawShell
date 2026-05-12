# ClawShell 2.0 — 一云多端云边协同分布式神经系统

> **Architecture Document** | Version 1.8.1 | 2026-05-12
>
> 指导思想：工程控制论 (Cybernetics) — 信息反馈 · 动态调控 · 系统整体思维

---

## 架构全景

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                         ClawShell 2.0 v1.8.1 — 一云多端云边协同分布式神经系统              │
└──────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────┐     ┌─────────────────────────────────────────┐
│     ☁️ CLOUD HUB (云枢)             │     │      🖥️ EDGE BRAIN (端脑)                │
│     Alibaba Cloud ECS               │◄───►│      User Terminal                      │
│                                     │     │                                         │
│  ┌───────────────────────────────┐  │ D A │  ┌─────────────────────────────────┐   │
│  │ API Gateway :8000             │  │ A T │  │ L4 多Agent集群                    │   │
│  │ ├ REST API /api/v1/*          │  │ T A │  │ ├ SwarmManager + Discovery 🆕     │   │
│  │ ├ WebSocket /ws/events        │  │ A   │  │ ├ TrustEvaluator + Manager 🆕     │   │
│  │ ├ MCP WSS /mcp/ws :8443 🆕     │  │   │  │ ├ EcologyMatcher                  │   │
│  │ └ Auth(JWT+Token+RateLimit)   │  │ F │  │ └ CollaborationProtocol           │   │
│  └───────────────────────────────┘  │ L │  └─────────────────────────────────┘   │
│                                     │ O │                                         │
│  ┌───────────────────────────────┐  │ W │  ┌─────────────────────────────────┐   │
│  │ 12 Core Engines                │  │   │  │ L3 自组织                         │   │
│  │ ┌──────────┐ ┌──────────┐     │  │   │  │ ├ 🆕 EdgeEventBus(Cond+DLQ+Trace) │   │
│  │ │EventBus  │ │TaskBoard │     │  │ ↔ │  │ ├ TaskOrganizer (DAG)             │   │
│  │ │SkillMkt  │ │CapReg    │     │  │   │  │ ├ ContextManager                  │   │
│  │ │SwarmCoord│ │Scheduler │     │  │   │  │ └ N8N Workflow                    │   │
│  │ │Evolution │ │Review    │     │  │   │  └─────────────────────────────────┘   │
│  │ │Broadcast │ │N8NBridge │     │  │   │                                         │
│  │ │🆕Workflow│ │🆕Optimizr│     │  │   │  ┌─────────────────────────────────┐   │
│  │ └──────────┘ └──────────┘     │  │   │  │ L2 自适应                         │   │
│  └───────────────────────────────┘  │   │  │ ├ 🆕 SelfRepair(Backup+Checkpoint) │   │
│                                     │   │  │ ├ FeedbackControlLoop             │   │
│  ┌───────────────────────────────┐  │   │  │ ├ AdaptiveParameterTuner          │   │
│  │ 🆕 Event Sourcing (9 modules)  │  │   │  │ └ Strategy + 🆕 AdaptiveCtrl      │   │
│  │ Store·Tracer·DLQ·PriorityQ    │  │   │  └─────────────────────────────────┘   │
│  │ Aggregator·Metrics·Pattern     │  │   │                                         │
│  │ MLEngine·Quality               │  │   │  ┌─────────────────────────────────┐   │
│  └───────────────────────────────┘  │   │  │ L1 自感知 (7 Monitors)            │   │
│                                     │   │  │ System·Disk·Process·Network       │   │
│  ┌───────────────────────────────┐  │   │  │ Service·Agent·Gateway             │   │
│  │ 🆕 MCP Protocol Layer           │  │   │  │ HealthChecker (27 items)          │   │
│  │ Hub·JWT·7-Domain Router        │  │   │  └─────────────────────────────────┘   │
│  └───────────────────────────────┘  │   │                                         │
│                                     │   │  ┌─────────────────────────────────┐   │
│  ┌───────────────────────────────┐  │   │  │ 🆕 Edge Gateway                   │   │
│  │ Cloud Services                 │  │   │  │ NetworkDiscovery·DeviceMonitor   │   │
│  │ VaultAPI·OSS Sync·MemOSClient │  │   │  │ KnowledgePuller·SelfHealing       │   │
│  │ 🆕 KnowledgeGraph·DeepThink    │  │   │  └─────────────────────────────────┘   │
│  └───────────────────────────────┘  │   │                                         │
│                                     │   │  ┌─────────────────────────────────┐   │
│  ┌───────────────────────────────┐  │   │  │ Core Components                  │   │
│  │ Deployment                     │  │   │  │ EnvDetector (8 frameworks)        │   │
│  │ Terraform·Docker·install.sh   │  │   │  │ IDEBridge (6 CLI agents)          │   │
│  └───────────────────────────────┘  │   │  │ Ecosystem Installer (10 comp.)    │   │
└─────────────────────────────────────┘   │  │ ConfigWizard·Edge CLI            │   │
                                           │  │ SyncDaemon (5s)·🆕 Delta Sync     │   │
                                           │  │ 🆕 AdapterManager                 │   │
                                           │  └─────────────────────────────────┘   │
                                           │                                         │
                                           │  Adapters: Hermes·OpenClaw·Wukong       │
                                           │  QClaw·CoPaw·HiClaw·EasyClaw·WorkBuddy  │
                                           │  IDEs: Codex·Claude·Kimi·DeepSeek·Copilot│
                                           │  Eco: psutil·ws·chromadb·MemPalace·N8N  │
                                           │  MemOS·Watchdog·BrowserRT·ONNX·Obsidian │
                                           └─────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────┐
│  🔄 Data Flow: Cloud↔Edge                                                             │
│  Cloud→Edge: HTTPS REST(:8000)·WSS/MCP(:8443)·Event Push·Broadcast·Task·Insight       │
│  Edge→Cloud: Event Batch·Health Report·Node Register·Task Claim·Skill Discover        │
│  SyncDaemon 5s loop: scan→enqueue→flush→pull→health                                   │
└──────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────┐
│  🧬 Persistence Layer (持久层)                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │  Genome  │ │MemOS Cloud│ │MemPalace │ │ Obsidian │ │🆕 Knowl-  │ │Event Store│     │
│  │ 知识传承 │ │ 记忆云   │ │记忆宫殿  │ │  Vault   │ │ edgeGraph │ │ JSON Seq  │     │
│  │Versioning│ │跨端同步  │ │SQLite+   │ │OSS双向   │ │Entity+    │ │YYYY-MM-DD │     │
│  │Heritage  │ │向量化    │ │ChromaDB  │ │同步 .md  │ │Relation   │ │/seq.json  │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│  TaskBoard(data/tasks.json)·SkillMarket(data/skills.json)·Review(data/reviews.json)    │
│  Workflow State(data/workflows/)·Dead Letters(data/dead_letters/)                      │
└──────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────┐
│  ☁️ External Services & Infrastructure                                                  │
│  Alibaba ECS·OSS│GitHub│N8N│Docker│Claude API│OpenAI API│ChromaDB│BrowserRT│MemOS API│
└──────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────┐
│  🎯 Design Philosophy                                                                  │
│  工程控制论: 信息反馈 · 动态调控 · 系统整体思维                                            │
│  九大原则: 异构同效·无侵入·低耦合·高鲁棒·高泛用·高协同·可移植·幂等性·端-云版本解耦         │
│  核心定义: 适用于类OpenClaw架构的增强型外骨骼功能插件 · 自感知→自适应→自组织→多Agent集群    │
│  v1.8.1 · 30+ new modules · 412 tests (0 failures) · ~17,000 LOC · 65+ Python modules   │
│  GitHub: jorinyang/ClawShell · MIT License                                              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 云枢 (Cloud Hub) — 详细组件

### API Gateway
| 组件 | 端口 | 说明 |
|------|------|------|
| FastAPI Server | :8000 | REST API (14 endpoints) |
| WebSocket | :8000 | Real-time event push |
| MCP WSS 🆕 | :8443 | JSON-RPC 2.0 MCP protocol |
| Auth Middleware | — | JWT HS256 + Edge Token + RateLimit |

### 12 Cloud Engines (stdlib-only, RLock thread-safe)

| 引擎 | 文件 | 核心功能 |
|------|------|----------|
| `CloudEventBus` | `cloud/engines/eventbus.py` | Persist + SHA256 Dedup + Wildcard Query + 30d Expiry |
| `GlobalTaskBoard` | `cloud/engines/task_board.py` | CRUD + State Machine + Priority + COMPENSATING 🆕 |
| `SkillMarket` | `cloud/engines/skill_market.py` | Publish/Discover/Sync + Version History 🆕 |
| `CapabilityRegistry` | `cloud/engines/capability_registry.py` | Edge Register + Heartbeat + Least-Loaded Schedule |
| `SwarmCoordinator` | `cloud/engines/swarm_coordinator.py` | Node Mgmt + Load Balance + Offline Detect |
| `CronScheduler` | `cloud/engines/scheduler.py` | 5-field Cron Parser + 60s Loop |
| `EvolutionEngine` | `cloud/engines/evolution.py` | InsightAggregator → PatternMiner → AutoSkillPublisher |
| `UnifiedReviewEngine` | `cloud/engines/review.py` | Daily/Weekly/Monthly → ActionPlan + Metrics 🆕 |
| `BroadcastEngine` | `cloud/engines/broadcast.py` | Announcement + BestPracticeRegistry + CrossEdgeLearning |
| `N8NBridge` | `cloud/engines/n8n_bridge.py` | Event → N8N Workflow Routing |
| `WorkflowEngine` 🆕 | `cloud/engines/workflow.py` | Built-in Saga Compensation + StepType (TASK/PARALLEL/CONDITION/SAGA/WAIT) |
| `GlobalOptimizer` 🆕 | `cloud/engines/optimizer.py` | Resource Quota + Cost Model + Balanced Allocation |

### 🆕 Event Sourcing Infrastructure (v1.8.1 from ClawShell-MacOS)

| 模块 | 文件 | 功能 |
|------|------|------|
| `EventStore` | `cloud/eventing/store.py` | Append-only persistent storage + Sequence-based replay |
| `EventTracer` | `cloud/eventing/tracer.py` | Causal chain tracking + Span/Trace analysis |
| `DeadLetterQueue` | `cloud/eventing/dead_letter.py` | Failed event replay + Configurable retry (3x, 60s) |
| `PriorityQueue` | `cloud/eventing/priority_queue.py` | Heap-based CRITICAL/HIGH/MEDIUM/LOW ordering |
| `EventAggregator` | `cloud/eventing/aggregator.py` | Time-window aggregation + Flush to JSON |
| `EventMetrics` | `cloud/eventing/metrics.py` | Per-topic stats + Latency + Error rate + Moving avg |
| `PatternMiner` | `cloud/eventing/pattern_miner.py` | Sequential/Co-occurrence pattern detection |
| `MLEngine` | `cloud/eventing/ml_engine.py` | Z-score anomaly detection + Linear trend analysis |
| `QualityEvaluator` | `cloud/eventing/quality.py` | 4-dim scoring: Completeness/Timeliness/Correctness/Consistency |

### 🆕 MCP Protocol Layer

| 模块 | 功能 |
|------|------|
| `MCPHub` | WebSocket MCP Router + Client lifecycle management |
| JWT Auth | HS256 token generation/verification (stdlib-only) |
| Domain Router | 7 domains: vault, skill, kanban, memory, node, workflow, genome |

### Cloud Services

| 服务 | 功能 |
|------|------|
| `VaultAPI` | Obsidian Vault CRUD (7 endpoints) |
| `OSSVaultSync` | Alibaba OSS bidirectional sync |
| `MemOSCloudClient` | Cross-device memory synchronization |
| `KnowledgeGraph` 🆕 | Entity-Relation graph + TF-IDF Semantic Search + BFS Traversal |
| `DeepThinkEngine` 🆕 | Decompose→Analyze→Synthesize→Recommend pipeline |

---

## 端脑 (Edge Brain) — 详细组件

### 四层外骨骼 (L1-L4)

| 层级 | 名称 | 核心组件 |
|------|------|----------|
| **L4** | 多Agent集群 | SwarmManager + TrustEvaluator + EcologyMatcher + CollaborationProtocol + SwarmDiscovery 🆕 + TrustManager 🆕 |
| **L3** | 自组织 | 🆕 EdgeEventBus(ConditionEngine+DLQ+Tracer) + TaskOrganizer(DAG) + ContextManager + N8N |
| **L2** | 自适应 | 🆕 SelfRepairEngine(Backup+Checkpoint) + FeedbackControlLoop + AdaptiveTuner + Strategy + AdaptiveController 🆕 |
| **L1** | 自感知 | SystemMon + DiskMon + ProcessMon + NetworkMon + ServiceMon + HealthChecker(27 items) |

### 🆕 Edge Gateway (v1.8.1)

| 组件 | 功能 |
|------|------|
| `NetworkDiscovery` | LAN UDP broadcast device discovery (:17660) |
| `DeviceMonitor` | Real-time CPU/Mem/Disk/Net health monitoring |
| `KnowledgePuller` | Cloud insight/broadcast local cache management |
| `EdgeSelfHealing` | Autonomous Diagnose→Heal→Verify pipeline |

### Core Components

| 组件 | 功能 |
|------|------|
| `EnvDetector` | 8 framework auto-detection (Wukong/Hermes/OpenClaw/QClaw/CoPaw/HiClaw/EasyClaw/WorkBuddy) |
| `IDEBridge` | 6 Agent CLI bridges (Codex/Claude Code/Kimi Code/DeepSeek TUI/Copilot + Orchestrator + Sandbox) |
| `EcosystemInstaller` | 10 component one-click install (psutil/websockets/chromadb/MemPalace/N8N/MemOS/Watchdog/BrowserRT/ONNX/Obsidian+OSS) |
| `SyncDaemon` | 5s loop: scan→enqueue→flush→pull tasks→pull insights→pull broadcasts→health |
| `ActionReference` | Pre-action cloud insight injection (autonomous mode on disconnect) |
| `ConfigWizard` | Interactive Cloud URL/Token/NodeID setup |
| `Edge CLI` | install/start/stop/status/config commands |
| `AdapterManager` 🆕 | Unified Hermes/OpenClaw/Wukong adapter lifecycle management |

---

## Data Flow (数据流)

```
Cloud→Edge (Push):
  HTTPS REST :8000   → Event Push, Task Assign, Broadcast
  WSS/MCP :8443      → Real-time notification, Skill sync
  
Edge→Cloud (Pull/Report):
  Event Batch        → Local events → CloudEventBus
  Health Report      → CPU/Mem/Disk metrics every 10 cycles (~50s)
  Node Register      → Capability declaration + heartbeat
  Task Claim         → Pull + claim matching tasks
  Skill Discover     → Search + download from SkillMarket

SyncDaemon 5s Loop:
  1. Scan local EventBus (mtime-based)
  2. Enqueue new events → OfflineQueue (500 max)
  3. Batch-flush to Cloud
  4. Pull tasks from GlobalTaskBoard
  5. Pull insights → cloud_insights.json
  6. Pull broadcasts → cloud_broadcasts.json
  7. Discover new skills from SkillMarket
  8. Health report (every 10 cycles)

Protocol Stack:
  Primary:   REST API (HTTPS JSON)
  Realtime:  WebSocket JSON frames  
  MCP:       MCP over WebSocket (JSON-RPC 2.0) 🆕
  Fallback:  Filesystem EventBus (JSON files)
```

---

## Persistence Layer (持久层)

| 存储 | 位置 | 类型 | 说明 |
|------|------|------|------|
| **Genome** | Cloud | Knowledge | 知识传承体系: Versioning, Heritage, Evolution records |
| **MemOS Cloud** | Cloud | Memory | 跨端同步记忆存储，向量化语义搜索 |
| **MemPalace** | Local | Memory | SQLite + ChromaDB 本地语义记忆 |
| **Obsidian Vault** | OSS | Knowledge | Markdown 知识库，OSS 双向同步 |
| **KnowledgeGraph** 🆕 | Cloud | Graph | Entity-Relation 知识图谱 + TF-IDF 语义搜索 |
| **Event Store** | Cloud | Events | YYYY-MM-DD/seq.json 追加式事件存储 |
| **TaskBoard** | Cloud | State | data/tasks.json 任务持久化 |
| **SkillMarket** | Cloud | Registry | data/skills.json 技能注册表 |
| **Review** | Cloud | Reports | data/reviews.json 复盘报告 |
| **Workflow** 🆕 | Cloud | State | data/workflows/ 工作流定义 + 执行状态 |

---

## External Services

| 服务 | 用途 |
|------|------|
| Alibaba ECS | Cloud Hub 计算实例 (Terraform IaC 部署) |
| Alibaba OSS | Obsidian Vault 对象存储 |
| GitHub | 代码托管 + Release 管理 |
| N8N | 外部工作流自动化编排 |
| Docker | 容器化部署 (API + N8N + Nginx) |
| Claude / OpenAI API | AI 推理能力 |
| ChromaDB | 向量数据库 (本地 + 云端) |
| MemOS Cloud API | 跨设备记忆同步 |
| Browser Runtime | Chromium CDP 浏览器自动化 |

---

## 设计原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | **异构同效** | 不同架构/技术栈模块在同一机制下发挥同等效能 |
| 2 | **无侵入** | 不修改任何已部署框架核心代码 |
| 3 | **低耦合** | 模块间通过文件协议和 EventBus 通信 |
| 4 | **高鲁棒** | 多层级错误恢复、守护进程保活、自动降级 |
| 5 | **高泛用** | 感知层抽象、适配器模式、标准化接口 |
| 6 | **高协同** | EventBus + ContextManager + TaskMarket + Swarm |
| 7 | **可移植** | 支持 macOS/Linux/WSL，端侧跨平台 |
| 8 | **幂等性** | 重复安装不对已有配置产生副作用 |
| 9 | **端-云版本解耦** | Cloud Hub 升级不影响 Edge Brain |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **v1.8.1** | 2026-05-12 | 跨仓库融合: 30+ new modules, Event Sourcing, MCP Protocol, Workflow/Optimizer/DeepThink/KnowledgeGraph, Edge Gateway, 412 tests |
| v1.8 | 2026-05-12 | Clean-room rebuild: 12 engines, 4-layer exoskeleton, Terraform deployment |
| v1.1 | 2026-05-11 | EventBus + TaskMarket + Swarm + Self-evolution pipeline |
| v1.0 | 2026-05-10 | Initial 2.0 architecture: Cloud-Edge split |

---

## 测试覆盖

| Phase | 类别 | 测试数 | 结果 |
|-------|------|:---:|:---:|
| P1 | Shared types + protocol | 49 | ✅ |
| P2 | Cloud Eventing (9 modules) | 56 | ✅ |
| P3 | New Engines (4 modules) | 26 | ✅ |
| P4 | Engine Merges (5 engines) | 11 | ✅ |
| P5 | MCP Protocol Layer | 12 | ✅ |
| P6+P7 | Edge EventBus + Gateway | 17 | ✅ |
| Comprehensive | All modules | 412 | ✅ |

---

*架构文档版本: 1.8.1 | 生成于 2026-05-12 | GitHub: jorinyang/ClawShell*
