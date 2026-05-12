# ClawShell 2.0 Clean-Room Rebuild Plan

> 版本: v2.0.0-plan
> 日期: 2026-05-12
> 目标仓库: https://github.com/jorinyang/ClawShell
> 当前仓库状态: 1.0.0 (v0.9 插件封装版, 28核心模块, 94单元测试)
> 参考代码: ClawShell-Windows v1.1.8 (C:\Users\Aorus\.ClawShell)

---

## 零、指导思想与核心原则 (不变)

### 指导思想
架构设计以**工程控制论**为指导思想，核心是**信息反馈、动态调控和系统整体思维**。

### 核心定义
ClawShell 本质上是一个适用于类 OpenClaw 架构的增强型外骨骼功能插件；
具备的自感知、自适应、自组织能力是以插件形式加强类 OpenClaw 架构的底层能力。

### 设计原则 (10条)
| 原则 | 2.0 新增 | 说明 |
|------|----------|------|
| 异构同效 | - | 不同架构/技术栈模块在同一机制下发挥同等效能 |
| 无侵入 | - | 不修改任何已部署框架核心代码 |
| 低耦合 | - | 模块间通过文件协议和 EventBus 通信 |
| 高鲁棒 | - | 多层级错误恢复、守护进程保活、自动降级 |
| 高泛用 | - | 感知层抽象、适配器模式、标准化接口 |
| 高协同 | - | EventBus + ContextManager + TaskMarket + Swarm |
| 可移植 | ✅ | 支持 macOS/Linux/WSL，端侧跨平台 |
| 幂等性 | ✅ | 重复安装不对已有配置产生副作用 |
| 端-云版本解耦 | ✅ | Cloud Hub 升级不影响 Edge Brain，反之亦然 |

### 核心能力 (4项)
- **自感知 (自发现)**: 设备/网络/云端/互联网环境 + 能力边界
- **自适应 (自修复)**: 环境改造 (优先) + 自我改造 (降级)
- **自组织 (自协同)**: 任务驱动的动态协作 + 最优路径
- **集群协作 (生态位匹配)**: 信任机制 + 协作协议 + 共识 + 接口标准化

---

## 一、2.0 架构全景

### 一云多端云边协同分布式神经系统

```
┌─────────────────────────────────────────────────────────────────┐
│                     ☁️ CLOUD HUB (云枢)                          │
│                     阿里云 ECS + OSS                              │
│                                                                  │
│  FastAPI Server (:8000)                                          │
│  ├── CloudEventBus (持久化/去重/广播/过期)                       │
│  ├── GlobalTaskBoard (跨Edge共享任务看板)                        │
│  ├── SkillMarket (技能发布→索引→发现→跨Edge同步)                │
│  ├── CapabilityRegistry (Edge注册+能力声明+调度)                 │
│  ├── SwarmCoordinator (节点管理/心跳/负载均衡)                   │
│  ├── CronScheduler (全局定时任务)                                │
│  ├── EvolutionEngine (洞察聚合→模式挖掘→自动技能发布)            │
│  ├── UnifiedReviewEngine (日/周/月复盘→ActionPlan)              │
│  ├── BroadcastEngine (成果广播+最佳实践注册)                     │
│  ├── VaultAPI (Obsidian OSS CRUD+搜索)                           │
│  ├── N8NBridge (工作流自动化触发)                                │
│  └── WSS /ws/events (实时事件推送)                               │
│                                                                  │
│  持久化: MemOS Cloud (记忆) + OSS (知识库) + GitHub (代码)       │
│  Nginx (:80/:443)                                                │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTPS/WebSocket
         ┌─────────────┼─────────────┐
         │             │             │
┌────────▼───┐  ┌─────▼──────┐  ┌───▼──────────┐
│ Edge A     │  │ Edge B     │  │ Edge C       │
│ (WSL/Win)  │  │ (macOS)    │  │ (Linux)      │
│            │  │            │  │              │
│ 端脑核心:   │  │ 端脑核心:   │  │ 端脑核心:    │
│ ├EnvDetect │  │ ├EnvDetect │  │ ├EnvDetect  │
│ ├Ecosystem │  │ ├Ecosystem │  │ ├Ecosystem  │
│ ├SyncDaemon│  │ ├SyncDaemon│  │ ├SyncDaemon │
│ ├IDEBridge │  │ ├IDEBridge │  │ ├IDEBridge  │
│ ├MCPBridge │  │ ├MCPBridge │  │ ├MCPBridge  │
│ ├Exoskelet │  │ ├Exoskelet │  │ ├Exoskelet  │
│ │ L1-L4    │  │ │ L1-L4    │  │ │ L1-L4     │
│ └Plugins   │  │ └Plugins   │  │ └Plugins    │
│            │  │            │  │              │
│ 类OpenClaw │  │ 类OpenClaw  │  │ 类OpenClaw   │
│ Wukong     │  │ Hermes     │  │ OpenClaw    │
│ Hermes     │  │            │  │ EasyClaw    │
│            │  │            │  │              │
│ Agent CLI  │  │ Agent CLI  │  │ Agent CLI   │
│ Codex      │  │ Claude Code│  │ Kimi Code   │
│ Claude Code│  │ Kimi Code  │  │ DeepSeek TUI│
│ DeepSeek   │  │            │  │              │
└────────────┘  └────────────┘  └──────────────┘
```

### 云枢四大核心职责
1. **架构规划**: 全局洞察分析, 跨Edge模式挖掘
2. **成果广播**: 一端成长, 多端共进 (insight/best-practice/skill 广播)
3. **终端管理**: 心跳监控, 能力注册, 负载均衡调度
4. **版本统一**: 代码 (GitHub) + 知识 (OSS) + 记忆 (MemOS Cloud) 统一管理

### 端脑六大核心职责
1. **自发现接入**: 嗅探类OpenClaw架构 → 自动配置 → 向云枢注册
2. **插件管理 + IDE桥接**: 模块化接入 N8N/MemPalace/MemOS/ComfyUI 等三方能力；桥接 Agent CLI IDE (Codex/Claude Code/Kimi Code/DeepSeek TUI) 完成代码开发 (Harness Engineering 方法论)
3. **多Agent协同调度**: 单设备 EventBus 消息传递与解耦
4. **行动前参考**: 每次行动前主动拉取云端 insight/broadcast/best-practice
5. **离线自治**: 云枢离线/无法获取信息时, 端脑独立自主执行
6. **多IDE协同开发**: 根据任务类型匹配最优IDE (生态位匹配), 多IDE并行协作, 结果汇总与质量评估

---

## 二、目录结构设计

```
ClawShell/                          # GitHub: jorinyang/ClawShell
│
├── cloud/                          # ☁️ Cloud Hub 完整实现
│   ├── __init__.py                 # 统一 re-export
│   ├── main.py                     # FastAPI 入口 (所有路由注册)
│   ├── engines/                    # 12 个云引擎模块
│   │   ├── __init__.py
│   │   ├── eventbus.py             # CloudEventBus — 持久化+去重+查询+广播+过期
│   │   ├── task_board.py           # GlobalTaskBoard — 跨Edge任务共享看板
│   │   ├── skill_market.py         # SkillMarket — 技能发布/发现/同步/版本管理
│   │   ├── capability_registry.py  # CapabilityRegistry — Edge注册+能力声明+调度
│   │   ├── swarm_coordinator.py    # SwarmCoordinator — 心跳(30s)+离线检测+负载均衡
│   │   ├── scheduler.py            # CronScheduler — 5-field cron + 执行日志
│   │   ├── evolution.py            # EvolutionEngine — 洞察聚合→模式挖掘→自动发布
│   │   ├── review.py               # UnifiedReviewEngine — 日/周/月复盘
│   │   ├── broadcast.py            # BroadcastEngine — 广播+最佳实践+跨Edge学习
│   │   └── n8n_bridge.py           # N8NBridge — 事件→工作流映射+webhook触发
│   ├── services/                   # 云服务集成
│   │   ├── __init__.py
│   │   ├── vault_api.py            # Obsidian OSS CRUD + 全文搜索 API
│   │   ├── oss_sync.py             # OSS 双向同步引擎 (ossutil wrapper)
│   │   └── memos_cloud.py          # MemOS Cloud API 客户端
│   ├── routers/                    # FastAPI 路由模块
│   │   ├── events.py               # /api/v1/events/*
│   │   ├── tasks.py                # /api/v1/tasks/*
│   │   ├── skills.py               # /api/v1/skills/*
│   │   ├── nodes.py                # /api/v1/nodes/* + /api/v1/health/*
│   │   ├── insights.py             # /api/v1/insights/*
│   │   ├── broadcasts.py           # /api/v1/broadcasts/*
│   │   ├── reviews.py              # /api/v1/reviews/*
│   │   ├── evolution.py            # /api/v1/evolution/*
│   │   └── vault.py                # /api/v1/vault/*
│   ├── websocket.py                # WebSocket /ws/events 管理器
│   ├── middleware.py               # Auth/CORS/RateLimit 中间件
│   └── config.py                   # Cloud 配置管理
│
├── edge/                           # 🖥️ Edge Brain 完整实现
│   ├── __init__.py
│   ├── detector/                   # 环境检测器 (10+ 种框架)
│   │   ├── __init__.py
│   │   ├── base.py                 # 抽象检测器基类
│   │   ├── wukong.py               # 悟空 (Wukong) 检测
│   │   ├── hermes.py               # Hermes Agent 检测
│   │   ├── openclaw.py             # OpenClaw 检测
│   │   ├── qclaw.py                # QClaw 检测
│   │   ├── copaw.py                # CoPaw 检测
│   │   ├── hiclaw.py               # HiClaw 检测
│   │   ├── easyclaw.py             # EasyClaw 检测
│   │   ├── workbuddy.py            # Work Buddy 检测
│   │   └── system.py               # 系统信息 (OS/CPU/Memory/Disk/Network)
│   ├── ecosystem/                  # 生态组件管理
│   │   ├── __init__.py
│   │   ├── installer.py            # 10 组件: MemPalace/ChromaDB/N8N/MemOS/Watchdog/BrowserRT/ONNX/psutil/websockets/Obsidian+OSS
│   │   ├── manager.py              # 组件启停/状态/升级
│   │   └── components/             # 各组件安装器
│   │       ├── __init__.py
│   │       ├── mempalace.py
│   │       ├── chromadb.py
│   │       ├── n8n.py
│   │       ├── memos.py
│   │       ├── watchdog.py
│   │       ├── browser_runtime.py
│   │       ├── onnx.py
│   │       └── obsidian_oss.py
│   ├── sync/                       # Edge↔Cloud 同步守护进程
│   │   ├── __init__.py
│   │   ├── daemon.py               # 主循环: scan→enqueue→flush→pull→health (5s)
│   │   ├── client.py               # 云 HTTP 客户端 (stdlib urllib, 零外部依赖)
│   │   ├── queue.py                # 离线队列 (JSON file, 500 max/300 trim)
│   │   ├── scanner.py              # 本地 EventBus 事件扫描 (mtime-based)
│   │   └── health.py               # 健康报告 (psutil metrics + port checks)
│   ├── adapters/                   # 框架适配器 (向目标框架注入 ClawShell)
│   │   ├── __init__.py
│   │   ├── base.py                 # 抽象适配器基类
│   │   ├── wukong_adapter.py       # 悟空适配: MCP config + cron tasks + workspace
│   │   ├── hermes_adapter.py       # Hermes适配: skill + config.yaml + .env
│   │   ├── openclaw_adapter.py     # OpenClaw适配: eventbus hook + skills loader
│   │   └── action_reference.py     # 行动前参考注入 (cloud_insights → workspace)
│   ├── ide_bridge/                 # Agent CLI IDE 桥接 (Harness Engineering)
│   │   ├── __init__.py
│   │   ├── base.py                 # 抽象IDE桥接器 (invoke/task/result/status)
│   │   ├── codex.py                # OpenAI Codex CLI (codex exec/acp)
│   │   ├── claude_code.py          # Claude Code CLI (claude --print)
│   │   ├── kimi_code.py            # Kimi Code (kimi agent)
│   │   ├── deepseek_tui.py         # DeepSeek TUI CLI
│   │   ├── copilot.py              # GitHub Copilot CLI (--acp)
│   │   ├── orchestrator.py         # 多IDE编排器: 任务匹配 → 并行调度 → 结果汇总
│   │   └── sandbox.py              # IDE沙箱: 隔离执行 + 超时控制 + 资源限制
│   ├── wizard/                     # 配置向导
│   │   ├── __init__.py
│   │   └── config_wizard.py        # 交互式 Cloud URL/Token/NodeID 配置+连接测试
│   └── cli.py                      # Edge CLI: install/start/stop/status/config
│
├── exoskeleton/                    # 🦴 四层外骨骼层 (1.0 核心能力迁移)
│   ├── __init__.py
│   ├── layer1/                     # 自感知 (L1)
│   │   ├── __init__.py
│   │   ├── health_check.py         # 27项健康检测
│   │   ├── system_mon.py           # CPU/内存/网络监控
│   │   ├── disk_mon.py             # 磁盘空间/IO监控
│   │   ├── process_mon.py          # 进程存活监控
│   │   ├── agent_mon.py            # Agent会话状态监控
│   │   ├── gateway_mon.py          # 网关运行状态监控
│   │   └── service_mon.py          # 外部服务可用性监控
│   ├── layer2/                     # 自适应 (L2)
│   │   ├── __init__.py
│   │   ├── self_repair.py          # 自修复引擎 (20+修复动作)
│   │   ├── discovery.py            # 自发现引擎 (能力/服务/接口)
│   │   ├── ml_engine.py            # AI/ML分析引擎
│   │   ├── condition.py            # 条件触发引擎
│   │   ├── strategy.py             # 策略选择与评估
│   │   ├── control_loop.py         # 工程控制论反馈闭环
│   │   ├── adaptive_tuner.py       # 自适应参数调优
│   │   ├── robust_controller.py    # 鲁棒控制器 (摄动容忍)
│   │   └── sense.py                # 感知融合
│   ├── layer3/                     # 自组织 (L3)
│   │   ├── __init__.py
│   │   ├── eventbus.py             # 本地 EventBus (pub/sub/priority/dead-letter)
│   │   ├── organizer.py            # 任务编排 (DAG)
│   │   ├── task_market.py          # 本地任务市场 (能力匹配分发)
│   │   ├── scheduler.py            # 本地 Cron 调度
│   │   ├── context_manager.py      # 全局状态管理器
│   │   └── ecology.py              # 生态位协调
│   ├── layer4/                     # 多Agent集群 (L4)
│   │   ├── __init__.py
│   │   ├── swarm.py                # 集群发现与管理
│   │   ├── trust.py                # 信任评估 (已知+陌生节点)
│   │   ├── ecology.py              # 生态位匹配
│   │   ├── protocol.py             # 协作协议
│   │   ├── node_registry.py        # 节点注册
│   │   └── metrics_collector.py    # 指标收集
│   └── genome/                     # 知识传承
│       ├── __init__.py
│       ├── heritage.py             # 知识版本管理
│       ├── cache_manager.py        # 缓存管理
│       └── evolution_tracker.py    # 进化追踪
│
├── shared/                         # 🔄 Cloud↔Edge 共享类型定义
│   ├── __init__.py
│   ├── types.py                    # Event/Task/Skill/Node/Broadcast/Insight 数据类
│   ├── protocol.py                 # 通信协议定义 (JSON-RPC 2.0 + REST)
│   ├── constants.py                # 共享常量 (端口/路径/超时/exopiry)
│   └── utils.py                    # 工具函数 (hash/validate/serialize)
│
├── deploy/                         # 🚀 部署配置
│   ├── cloud/                      # 云端部署
│   │   ├── terraform/              # 阿里云 ECS IaC
│   │   │   ├── main.tf             # VPC + ECS + Security Group + EIP
│   │   │   ├── variables.tf        # Region/Zone/Instance/Spec
│   │   │   ├── outputs.tf          # ECS IP/API URL/N8N URL/SSH
│   │   │   └── user_data.sh        # Bootstrap: docker + git + docker-compose up
│   │   ├── docker-compose.yml      # API + N8N + MemOS Cloud Proxy + Nginx
│   │   ├── nginx.conf              # Reverse Proxy (SSL termination)
│   │   └── Dockerfile              # Python API 镜像
│   └── edge/                       # 端侧安装
│       ├── install.sh              # Linux/macOS 一键安装
│       └── install.ps1             # Windows PowerShell 一键安装
│
├── tests/                          # 🧪 测试
│   ├── __init__.py
│   ├── test_cloud/                 # Cloud 引擎测试
│   │   ├── test_eventbus.py
│   │   ├── test_task_board.py
│   │   ├── test_skill_market.py
│   │   ├── test_capability_registry.py
│   │   └── test_swarm_coordinator.py
│   ├── test_edge/                  # Edge 组件测试
│   │   ├── test_detector.py
│   │   ├── test_ide_bridge.py      # IDE桥接器测试
│   │   ├── test_sync_daemon.py
│   │   └── test_adapters.py
│   ├── test_exoskeleton/           # 外骨骼层测试
│   │   ├── test_layer1.py
│   │   └── test_layer2.py
│   └── test_integration/           # 集成测试
│       └── test_cloud_edge_sync.py
│
├── docs/                           # 📚 文档
│   ├── ARCHITECTURE.md             # ★ 2.0 一云多端架构全景文档
│   ├── CORE_DEFINITION.md          # ★ 核心定义与设计哲学
│   ├── ENGINEERING_CYBERNETICS.md  # ★ 工程控制论理论依据与实现映射
│   ├── INSTALL.md                  # 安装指南 (Cloud + Edge)
│   ├── USER_GUIDE.md               # 用户指南
│   ├── DEVELOPER_GUIDE.md          # 开发者指南
│   ├── API_REFERENCE.md            # Cloud API 参考
│   └── CHANGELOG.md                # 版本变更日志
│
├── README.md                       # ★ 项目入口 (2.0 云边协同介绍)
├── MANIFEST.json                   # ★ 能力清单 (cloud/edge/exoskeleton 三层)
├── CLAWSHELL_VERSION               # 版本号: 2.0.0-dev
├── .gitignore
├── requirements.txt                # Python 依赖
├── requirements-cloud.txt          # Cloud 额外依赖 (fastapi/uvicorn/websockets)
├── pyproject.toml                  # 项目元数据 (PEP 621)
└── LICENSE                         # MIT
```

---

## 三、实施阶段

### Phase 1: 项目骨架 + 共享层 + Cloud 基础设施
**预计文件数**: ~30

| Task | 模块 | 说明 |
|------|------|------|
| P1.1 | 项目骨架 | README, MANIFEST, pyproject.toml, CLAWSHELL_VERSION, .gitignore, LICENSE |
| P1.2 | `shared/` | types.protocol/constants/utils (Event/Task/Skill/Node/Insight/Broadcast 数据模型) |
| P1.3 | `cloud/config.py`, `cloud/middleware.py`, `cloud/main.py` | FastAPI 骨架 + 健康检查 |
| P1.4 | `cloud/engines/eventbus.py` | CloudEventBus: 持久化 + SHA256去重 + 通配符查询 + 30天过期 + stats |
| P1.5 | `cloud/engines/capability_registry.py` | Edge注册 + 能力声明 + 心跳 + least-loaded调度 |
| P1.6 | `cloud/engines/scheduler.py` | CronScheduler: 5-field cron parser + 60s loop + execution logging |
| P1.7 | `cloud/routers/events.py` + `cloud/routers/nodes.py` | REST API: 事件推送/查询, 节点注册/心跳 |
| P1.8 | `cloud/websocket.py` | WebSocket 管理器 (实时事件推送) |
| P1.9 | P1.4~P1.8 测试 | Cloud引擎基础测试 (4个测试文件) |

### Phase 2: Cloud Hub 完整引擎
**预计文件数**: ~20

| Task | 模块 | 说明 |
|------|------|------|
| P2.1 | `cloud/engines/task_board.py` | GlobalTaskBoard: 跨Edge任务CRUD + 状态机 (pending→in_progress→completed/failed/cancelled) + 优先级队列 + 认领 |
| P2.2 | `cloud/engines/skill_market.py` | SkillMarket: 发布→索引→发现→跨Edge同步 + 版本管理 |
| P2.3 | `cloud/engines/swarm_coordinator.py` | SwarmCoordinator: 节点管理 + 心跳30s + 离线检测 + 负载均衡 |
| P2.4 | `cloud/engines/evolution.py` | EvolutionEngine: InsightAggregator → PatternMiner → AutoSkillPublisher → EvolutionTracker (300s循环) |
| P2.5 | `cloud/engines/review.py` | UnifiedReviewEngine: 日/周/月复盘 → ActionPlan → SkillMarket发布 |
| P2.6 | `cloud/engines/broadcast.py` | BroadcastEngine: 广播 + BestPracticeRegistry + CrossEdgeLearning |
| P2.7 | `cloud/engines/n8n_bridge.py` | N8NBridge: 事件→workflow映射 + webhook触发 + 通配符 |
| P2.8 | `cloud/services/vault_api.py` + `cloud/services/oss_sync.py` | OSS Vault CRUD + 全文搜索 + 双向同步 (ossutil wrapper) |
| P2.9 | `cloud/services/memos_cloud.py` | MemOS Cloud API 客户端 |
| P2.10 | All `cloud/routers/` | REST API 补全: tasks/skills/insights/broadcasts/reviews/evolution/vault |
| P2.11 | P2.1~P2.10 测试 | Cloud引擎全量测试 (8个引擎 + 路由) |

### Phase 3: Edge Brain 核心组件
**预计文件数**: ~35

| Task | 模块 | 说明 |
|------|------|------|
| P3.1 | `edge/detector/base.py` + `edge/detector/system.py` | 抽象检测器基类 + 系统信息收集 (OS/CPU/MEM/Disk/Network) |
| P3.2 | `edge/detector/wukong.py` | 悟空检测: ~/.real/路径, dingtalk-rewind, MCP配置, cron_tasks |
| P3.3 | `edge/detector/hermes.py` | Hermes检测: ~/.hermes/路径, config.yaml, skills/目录 |
| P3.4 | `edge/detector/openclaw.py` + 6个其他检测器 | OpenClaw/QClaw/CoPaw/HiClaw/EasyClaw/WorkBuddy 自动嗅探 |
| P3.5 | `edge/ide_bridge/base.py` | ★ 抽象IDE桥接器: invoke/task/result/status 标准接口 |
| P3.6 | `edge/ide_bridge/codex.py` | OpenAI Codex CLI 桥接 (codex exec --acp) |
| P3.7 | `edge/ide_bridge/claude_code.py` | Claude Code CLI 桥接 (claude --print --output-format json) |
| P3.8 | `edge/ide_bridge/kimi_code.py` | Kimi Code 桥接 (kimi agent) |
| P3.9 | `edge/ide_bridge/deepseek_tui.py` + `copilot.py` | DeepSeek TUI + GitHub Copilot CLI (--acp) |
| P3.10 | `edge/ide_bridge/orchestrator.py` | ★ 多IDE编排器: 任务类型→IDE生态位匹配 → 并行调度 → 结果汇总 |
| P3.11 | `edge/ide_bridge/sandbox.py` | IDE沙箱: 隔离执行 + 超时控制 + 资源限制 |
| P3.12 | `edge/ecosystem/installer.py` + components/* | 10生态组件: MemPalace/ChromaDB/N8N/MemOS/Watchdog/BrowserRT/ONNX/psutil/websockets/Obsidian+OSS |
| P3.13 | `edge/ecosystem/manager.py` | 组件启停/状态检查/升级管理 |
| P3.14 | `edge/sync/client.py` | Cloud HTTP Client (stdlib urllib only, 零外部依赖) |
| P3.15 | `edge/sync/queue.py` | 离线队列 (JSON file, 500 max / 300 trim, 断网持久化) |
| P3.16 | `edge/sync/scanner.py` + `edge/sync/health.py` | 本地 EventBus 事件扫描 + 健康报告 |
| P3.17 | `edge/sync/daemon.py` | 核心守护进程: scan→enqueue→flush→pull→discover→health (5s循环) |
| P3.18 | P3.1~P3.17 测试 | Edge组件测试 (detector + ide_bridge + sync + ecosystem) |

### Phase 4: 端脑适配器 + 外骨骼层迁移
**预计文件数**: ~45

| Task | 模块 | 说明 |
|------|------|------|
| P4.1 | `edge/adapters/base.py` | 抽象适配器基类: register/detect/inject/verify |
| P4.2 | `edge/adapters/wukong_adapter.py` | 悟空适配: MCP注册 + cron注入 + workspace创建 + action_reference注入 |
| P4.3 | `edge/adapters/hermes_adapter.py` | Hermes适配: skill安装 + config.yaml更新 + .env注入 + action_reference注入 |
| P4.4 | `edge/adapters/openclaw_adapter.py` | OpenClaw适配: eventbus hook注册 + skills loader配置 |
| P4.5 | `edge/adapters/action_reference.py` | 行动前参考注入: 从Cloud拉取insight → 写入目标Agent工作空间 (cloud离线时写入autonomous模式标记) |
| P4.6 | `edge/wizard/config_wizard.py` | 交互式配置: Cloud URL + Token + NodeID + 连接测试 |
| P4.7 | `edge/cli.py` | Edge CLI: install/start/stop/status/config |
| P4.8~P4.14 | `exoskeleton/layer1/` (7 modules) | 自感知层: health_check, system_mon, disk_mon, process_mon, agent_mon, gateway_mon, service_mon |
| P4.15~P4.23 | `exoskeleton/layer2/` (9 modules) | 自适应层: self_repair, discovery, ml_engine, condition, strategy, control_loop, adaptive_tuner, robust_controller, sense |
| P4.24~P4.29 | `exoskeleton/layer3/` (6 modules) | 自组织层: eventbus, organizer, task_market, scheduler, context_manager, ecology |
| P4.30~P4.36 | `exoskeleton/layer4/` (7 modules) | 多Agent集群层: swarm, trust, ecology, protocol, node_registry, metrics_collector, failure_detector |
| P4.37~P4.40 | `exoskeleton/genome/` (4 modules) | 知识传承: heritage, cache_manager, evolution_tracker, enterprise_knowledge |
| P4.41 | 外骨骼层测试 | L1/L2/L3/L4 关键模块的 smoke test |

### Phase 5: 集成、部署、测试
**预计文件数**: ~35

| Task | 模块 | 说明 |
|------|------|------|
| P5.1 | `tests/test_integration/test_cloud_edge_sync.py` | 端到端集成测试: Cloud EventBus ↔ Edge Sync Daemon |
| P5.2 | `tests/test_cloud/*` (8 test files) | Cloud引擎完整单元测试 (100%核心路径覆盖) |
| P5.3 | `tests/test_edge/*` (4 test files) | Edge组件测试 (detector/sync/adapters/ecosystem) |
| P5.4 | `tests/test_exoskeleton/*` (4 test files) | 外骨骼层smoke test (每层关键路径) |
| P5.5 | `deploy/cloud/terraform/main.tf` | 阿里云ECS IaC: VPC + vSwitch + Security Group + ECS (ecs.c6.large, Ubuntu 22.04) + EIP + OSS Bucket |
| P5.6 | `deploy/cloud/terraform/variables.tf` | Region/Zone/InstanceType/Disk/Bandwidth 变量 |
| P5.7 | `deploy/cloud/terraform/outputs.tf` | ECS IP/API URL (:8000)/N8N URL (:5678)/SSH命令 |
| P5.8 | `deploy/cloud/terraform/user_data.sh` | Bootstrap: apt install docker/nginx/git → git clone → docker compose up → health check |
| P5.9 | `deploy/cloud/docker-compose.yml` | Docker stack: ClawShell API + PostgreSQL + N8N + Nginx |
| P5.10 | `deploy/cloud/Dockerfile` | Python API镜像: FastAPI + uvicorn + cloud engines |
| P5.11 | `deploy/cloud/nginx.conf` | Reverse Proxy: SSL termination + /api/v1/ → API + /ws/ → WebSocket |
| P5.12 | `deploy/edge/install.sh` | Linux/macOS一键安装: detect → ecosystem → config → start |
| P5.13 | `deploy/edge/install.ps1` | Windows PowerShell一键安装 |
| P5.14 | `MANIFEST.json` 更新 | 完整能力清单: cloud/edge/exoskeleton 三层 + 数据流图 |

### Phase 6: 文档 + GitHub 发布
**预计文件数**: ~10

| Task | 文件 | 说明 |
|------|------|------|
| P6.1 | `docs/ARCHITECTURE.md` | ★ 2.0 一云多端全景架构文档 (ASCII图 + 模块清单 + 数据流) |
| P6.2 | `docs/CORE_DEFINITION.md` | ★ 核心定义 + 设计哲学 + 10原则 + 工程控制论体系 |
| P6.3 | `docs/ENGINEERING_CYBERNETICS.md` | ★ 工程控制论理论依据: 反馈闭环/鲁棒性/综合集成 + ClawShell实现映射 |
| P6.4 | `docs/INSTALL.md` | 安装指南: Cloud部署 + Edge安装 + 配置 |
| P6.5 | `docs/USER_GUIDE.md` | 用户指南: 端脑CLI使用 + Cloud API使用 + 场景示例 |
| P6.6 | `docs/DEVELOPER_GUIDE.md` | 开发者指南: 模块开发 + 测试 + 贡献规范 |
| P6.7 | `docs/API_REFERENCE.md` | Cloud API参考: 全部REST端点 + WebSocket协议 |
| P6.8 | `docs/CHANGELOG.md` | 版本变更日志: 1.0→2.0 完整变更记录 |
| P6.9 | `README.md` 重写 | ★ 项目入口: 2.0云边协同概述 + 快速开始 + 架构图 |
| P6.10 | GitHub Release | v2.0.0-dev annotated tag + Release notes |

---

## 四、关键技术决策

### 1. RLock 铁律 (继承自 v1.1)
所有使用 threading 锁的模块必须用 `threading.RLock()`，不能用 `Lock()`。
原因: `_save()`/`_load()` 私有方法可能被其他已持有锁的方法调用，非重入锁导致死锁。

### 2. 通信协议 (三通道冗余)
- **主通道**: REST API (HTTPS) — Edge → Cloud 事件推送/任务拉取
- **实时通道**: WebSocket — Cloud → Edge 实时广播推送
- **备用通道**: Filesystem EventBus — JSON文件协议, 通道故障自动切换

### 3. 记忆边界 (不可妥协的铁律)
- **MemPalace** (SQLite + ChromaDB): 本地 ONLY — 永不上云
- **MemOS Local** (Node/Bun): 本地 ONLY 
- **MemOS Cloud** (API): 云端 ONLY — 跨设备同步
- **Obsidian Vault**: 本地编辑 + OSS 云端存储 (双向同步)

### 4. 引擎零外部依赖原则
- Cloud engines (eventbus/task_board/skill_market/capability_registry/swarm_coordinator/scheduler): 纯 stdlib，零外部依赖
- Edge sync client: 纯 urllib，零外部依赖
- 仅在 FastAPI layer 引入 uvicorn/websockets

### 5. 版本规则 (严恪语义化)
- **PATCH bump** (2.0.0→2.0.1): Bug修复/文档/版本修正
- **MINOR bump** (2.0→2.1): 新引擎/API/功能 (未部署验证)
- **MAJOR bump** (2.x→3.0): 仅云-端完全分离部署 + 生产验证后

### 6. 守护进程 5s chunk 规则
所有 daemon thread 的 sleep 必须用 5s chunks + `self._running` 检查:
```python
for _ in range(int(self.INTERVAL / 5)):
    if not self._running: break
    time.sleep(5)
```
永不使用裸 `time.sleep(N)` 在 daemon threads 中 — 会阻塞 shutdown。

### 7. 代码生成 ≠ 部署
- Terraform/Docker Compose 文件为代码生成蓝图 — 不实际 terraform apply
- 实际部署需用户手动执行
- 版本号基于部署验证后的能力，非生成代码量

---

## 五、从 1.0/1.1 到 2.0 的关键演变

| 方面 | 1.0 (ClawShell repo) | 1.1 (ClawShell-Windows) | 2.0 (ClawShell clean-room) |
|------|---------------------|------------------------|---------------------------|
| 仓库 | jorinyang/ClawShell (tag 1.0.0) | jorinyang/ClawShell-Windows (v1.1.8) | jorinyang/ClawShell (clean restart) |
| 架构 | 本地四层外骨骼 | 本地+Cloud初探 (cloud/ + edge/) | 云枢中枢 + 端脑执行 (完全分离) |
| 适配 | 硬编码 Wukong/Hermes | 硬编码 Wukong/Hermes | 10+ 框架自动检测 + 6 IDE CLI 桥接 |
| 通信 | EventBus (文件) | MCP Bridge (:17655) | REST + WSS + Filesystem 三通道 |
| IDE | 无IDE调用能力 | 无IDE调用能力 | Agent CLI IDE Bridge: Codex/Claude Code/Kimi Code/DeepSeek TUI/Copilot 多IDE编排 |
| 记忆 | 模糊 (MemOS混用) | 明确但未强制执行 | 三层铁律 (MemPalace本地/MemOS Local本地/MemOS Cloud云端) |
| 端侧平台 | 仅 Windows/WSL | 仅 WSL + Windows | macOS / Linux / WSL 全平台 |
| 安装方式 | 手动 copy 到 .openclaw | install.sh/install.ps1 | 一键安装 + 交互式配置向导 |
| 代码组织 | 散乱 (lib/ + scripts/) | 改进 (cloud/ + edge/ + lib/) | 清晰四域: cloud/ edge/ exoskeleton/ shared/ |
| 命名 | 无正式名称 | 章鱼式 (用户明确否决) | 一云多端云边协同分布式神经系统 |
| 版本 | 1.0.0 | 1.1.8 (锁定) | 2.0.0-dev (clean start) |
| 云引擎 | 无 | 8引擎 (已实现但未部署) | 12引擎 (完整重写, 从零构建) |
| 测试 | 94单元测试 | 部分集成测试 | 完整分层测试 (cloud/edge/exoskeleton/integration) |

---

## 六、风险与对策

| 风险 | 影响等级 | 概率 | 对策 |
|------|---------|------|------|
| 云引擎12个过多, 内存/启动压力 | 中 | 中 | 惰性加载 (lazy init), 按需初始化; 每个引擎 <500 行 |
| 框架检测误判 (假阳性/假阴性) | 高 | 中 | 多维度交叉验证 (路径+进程+配置文件+端口), 置信度评分 |
| Cloud 离线时 Edge 失连 | 高 | 低 | 端脑离线自治 + 离线队列持久化 + 恢复后批量同步 (幂等) |
| 跨Edge事件冲突/重复 | 中 | 中 | SHA256 内容去重 + event.source 标记 + 30天过期 |
| 外骨骼层迁移遗漏功能 | 中 | 低 | 对照 v1.1 MANIFEST.json 交叉验证, 每层smoke test |
| RLock死锁 (v1.1核心教训) | 高 | 极低 | 全量 RLock 铁律 + 测试覆盖 (嵌套锁场景) |
| ChromaDB二进制泄露到git | 中 | 中 | .gitignore 预配置 storage/ + __pycache__/ |

---

## 七、凭证配置

| 凭证 | 值 | 用途 |
|------|-----|------|
| GitHub Token | `<CLAWSHELL_GITHUB_TOKEN>` | Push to jorinyang/ClawShell |
| 阿里云 AK ID | `<CLAWSHELL_ALIYUN_AK_ID>` | OSS/ECS (deploy configs) |
| 阿里云 AK Secret | `<CLAWSHELL_ALIYUN_AK_SECRET>` | OSS/ECS (deploy configs) |
| MemOS Cloud | `<CLAWSHELL_MEMOS_API_KEY>` | Cloud memory sync |

**安全规则**: 凭证绝不硬编码在代码中，仅通过环境变量 (`CLAWSHELL_*`) 注入到部署配置。
代码中的配置引用形式: `os.environ.get("CLAWSHELL_ALIYUN_AK_ID")`

---

*本计划基于以下文档综合制定:*
- *《CLAWSHELL_CORE_DEFINITION.md》— ClawShell 核心定义 v1.0*
- *《00-SYSTEM_ARCHITECTURE.md》— 系统架构全景 v2.0.0*
- *《04-工程控制论研究报告.md》— 工程控制论理论依据*
- *《04-多Agent集群.md》— L4 多Agent集群设计*
- *ClawShell-Windows v1.1.8 代码库* (C:\Users\Aorus\.ClawShell)
- *用户 2.0 愿景: 一云多端云边协同分布式神经系统*
