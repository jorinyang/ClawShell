# ClawShell 2.0

> **一云多端云边协同分布式神经系统**
>
> 版本: 1.8.1 | 架构: 云枢 + 端脑 | 指导思想: 工程控制论

---

## 架构全景图

👉 **[查看完整交互式架构图](docs/architecture-diagram.html)** — 在浏览器中打开查看 SVG 全景架构

![ClawShell 2.0 Architecture](docs/architecture-diagram.html)

```
☁️ CLOUD HUB (云枢) — 阿里云 ECS              🖥️ EDGE BRAIN (端脑) — 用户终端
┌────────────────────────────────┐    ┌─────────────────────────────────┐
│ FastAPI :8000 + MCP WSS :8443  │    │ L4 多Agent集群                    │
│ ├ 12 Cloud Engines              │    │ ├ SwarmDiscovery + Trust 🆕       │
│ ├ CloudEventBus / TaskBoard     │    │ ├ EcologyMatcher + Protocol       │
│ ├ SkillMarket / CapRegistry     │◄──►│ L3 自组织                         │
│ ├ SwarmCoordinator / Scheduler  │WSS │ ├ EventBus(Condition+DLQ+Tracer)🆕│
│ ├ EvolutionEngine / Review      │MCP │ ├ TaskOrganizer + ContextManager  │
│ ├ BroadcastEngine / N8NBridge   │    │ L2 自适应                         │
│ ├ WorkflowEngine(Saga) 🆕        │    │ ├ SelfRepair(Backup+Checkpoint)🆕 │
│ ├ GlobalOptimizer 🆕             │    │ ├ FeedbackControlLoop + Tuner     │
│ ├ DeepThinkEngine 🆕             │    │ L1 自感知 (7 Monitors)            │
│ ├ EventStore/Tracer/DLQ/ML 🆕    │    │ Gateway 🆕                        │
│ ├ KnowledgeGraph 🆕              │    │ ├ NetworkDiscovery / DeviceMon    │
│ ├ MCP Hub + JWT Auth 🆕          │    │ ├ KnowledgePuller / SelfHealing   │
│ └ VaultAPI / OSS Sync / MemOS   │    │ IDEBridge (6 CLI agents)          │
└────────────────────────────────┘    │ Ecosystem Installer (10 components)│
                                       │ SyncDaemon (5s loop)               │
         🧬 Persistence                 │ AdapterManager 🆕                  │
    Genome · MemOS · MemPalace         └─────────────────────────────────┘
    Obsidian Vault · KnowledgeGraph 🆕
    
    ☁️ 阿里云 ECS/OSS · GitHub · N8N · Docker
```

---

## 概述

ClawShell 是一个适用于类 OpenClaw 架构的增强型外骨骼功能插件，以工程控制论为指导思想，
核心是信息反馈、动态调控和系统整体思维。

2.0 版本采用**一云多端云边协同分布式神经架构**，由 1 个云枢（Cloud Hub）和 N 个端脑（Edge Brain）组成：

- **☁️ 云枢**: 部署于阿里云 ECS，负责全局架构规划、深度思考、洞察分析、复盘总结、成果广播、终端管理。
  共识信息及复用能力部署到云端（ECS/OSS/GitHub/MemOS Cloud），保持自我成长及迭代高可用性。
- **🖥️ 端脑**: 安装于用户终端，自适应不同的类 OpenClaw 架构，
  负责环境检测、插件管理、IDE 桥接、任务执行和离线自治。
  端脑可独立运行，链接云枢后实现信息同步及进化增强。

### v1.8.1 跨仓库融合新增 (from ClawShell-MacOS)

| 模块 | 来源 | 说明 |
|------|------|------|
| Event Sourcing (8 modules) | MacOS EventStore | EventStore/Tracer/DeadLetter/Priority/Aggregator/Metrics/Pattern/ML/Quality |
| WorkflowEngine | MacOS WorkflowDomain | Saga补偿 + StepType + 内置工作流 |
| GlobalOptimizer | MacOS GlobalOptimizer | 跨端资源优化 (COST/LATENCY/THROUGHPUT/BALANCED) |
| DeepThinkEngine | MacOS DeepThink | Decompose→Analyze→Synthesize→Recommend |
| KnowledgeGraph | MacOS KnowledgeGraph | 知识图谱 + 语义搜索 + 关系引擎 |
| MCP Protocol | MacOS Cloud Hub | WebSocket Hub + JWT HS256 + 7-Domain Router |
| Edge Gateway | MacOS Edge Gateway | NetworkDiscovery/DeviceMonitor/KnowledgePuller/SelfHealing |
| ConditionEngine | MacOS EventBus | 条件评估 + 死信队列 + 事件追踪 |

## 核心原则

| 原则 | 说明 |
|------|------|
| 异构同效 | 不同架构/技术栈模块在同一机制下发挥同等效能 |
| 无侵入 | 不修改任何已部署框架核心代码 |
| 低耦合 | 模块间通过文件协议和 EventBus 通信 |
| 高鲁棒 | 多层级错误恢复、守护进程保活、自动降级 |
| 高泛用 | 感知层抽象、适配器模式、标准化接口 |
| 高协同 | EventBus + ContextManager + TaskMarket + Swarm |
| 可移植 | 支持 macOS/Linux/WSL，端侧跨平台 |
| 幂等性 | 重复安装不对已有配置产生副作用 |
| 端-云版本解耦 | Cloud Hub 升级不影响 Edge Brain |

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
├── cloud/              # ☁️ Cloud Hub (12 engines + 3 services + Eventing + MCP)
│   ├── engines/        #   CloudEventBus, TaskBoard, SkillMarket, Workflow🆕, etc.
│   ├── eventing/       #   EventStore, Tracer, DLQ, ML, Quality🆕 (8 modules)
│   ├── mcp/            #   MCPHub, JWT Auth, Domain Router🆕 (3 modules)
│   └── services/       #   VaultAPI, OSSSync, MemOSCloud, KnowledgeGraph🆕
├── edge/               # 🖥️ Edge Brain
│   ├── eventbus/       #   ConditionEngine + DLQ + Tracer🆕
│   ├── gateway/        #   NetworkDiscovery, DeviceMonitor, KnowledgePuller🆕
│   ├── adapters/       #   Hermes/Wukong/OpenClaw + AdapterManager🆕
│   ├── detector/       #   8 framework detectors
│   ├── ide_bridge/     #   6 IDE CLI bridges
│   ├── ecosystem/      #   10 component installer
│   └── sync/           #   SyncDaemon (5s loop)
├── exoskeleton/        # 🦴 四层外骨骼 (L1-L4)
├── shared/             # 🔄 共享类型与协议 (MCP Types🆕)
├── deploy/             # 🚀 部署配置 (Terraform + Docker)
├── tests/              # 🧪 测试 (412 comprehensive, 0 failures)
└── docs/               # 📚 文档 + 架构图
```

## 文档

- [架构全景图](docs/architecture-diagram.html) — 交互式 SVG 完整架构图
- [架构文档](docs/ARCHITECTURE.md) — 一云多端完整架构
- [核心定义](docs/CORE_DEFINITION.md) — 设计哲学与工程控制论
- [更新日志](docs/CHANGELOG.md)
- [安装指南](docs/INSTALL.md)

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
