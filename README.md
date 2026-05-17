# ClawShell 2.0 — 多账户云边协同管理平台

> **一云多端云边协同分布式神经系统** | Multi-Account · Cloud Dashboard · Credential Sync
>
> Version 2.0.0 | CloudHub (云枢) + Edge Brain (端脑) + Dashboard (控制台) | Engineering Cybernetics | 智询工作室

---

## 架构全景

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│              ClawShell 2.0 — 多账户云边协同管理平台                                    │
│    CloudHub + Edge Brain + Dashboard | Engineering Cybernetics                       │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐  ┌──────────────────────────────────────┐  ┌──────────────────────┐
│  ☁️ CLOUDHUB (云枢)           │  │  🖥️ EDGE BRAIN (端脑)                │  │  📊 DASHBOARD (控制台)│
│  Alibaba Cloud ECS            │  │  User Terminal                       │  │  Next.js 16           │
│                               │  │                                      │  │                       │
│  ┌─ API Gateway :8000 ─────┐ │  │  ┌─ L4 多Agent集群 ─────────────┐  │  │  ┌─ Features ───────┐ │
│  │ REST /api/v1/* (76 ep)  │ │  │  │ SwarmManager + Discovery     │  │  │  │ 多账户管理       │ │
│  │ WebSocket /ws/events    │ │  │  │ TrustEvaluator + Manager     │  │  │  │ 节点拓扑图       │ │
│  │ MCP WSS /mcp/ws :8443   │ │↕ │  │ EcologyMatcher               │  │  │  │ 凭证管理         │ │
│  │ Auth(JWT+RBAC+RateLimit)│ │D │  └──────────────────────────────┘  │  │  │ 审计日志         │ │
│  └─────────────────────────┘ │A │                                      │  │  │ 中/English       │ │
│                               │T │  ┌─ L3 自组织 ─────────────────┐  │  │  └──────────────────┘ │
│  ┌─ 15 Core Engines ───────┐ │A │  │ EdgeEventBus(Cond+DLQ+Trace)│  │  │                       │
│  │ EventBus · TaskBoard     │ │  │  │ TaskOrganizer(DAG)          │  │  │  HTTPS (clawshell.club│
│  │ SkillMarket · CapRegistry│ │F │  │ ContextManager · N8N        │  │  │  Let's Encrypt SSL    │
│  │ SwarmCoord · CronSched   │ │L │  └──────────────────────────────┘  │  │                       │
│  │ Evolution · ReviewEngine │ │O │                                      │  └──────────────────────┘
│  │ Broadcast · N8NBridge    │ │W │  ┌─ L2 自适应 ─────────────────┐  │
│  │ Workflow · Optimizer      │ │  │  │ SelfRepair(Backup+Checkpoint)│  │
│  │ DeepThink · CredentialMgr│ │  │  │ FeedbackLoop · AdaptiveTuner │  │
│  │ 🆕 AuditEngine           │ │  │  │ Strategy · AdaptiveController│  │
│  └──────────────────────────┘ │  │  └──────────────────────────────┘  │
│                               │  │                                      │
│  ┌─ Event Sourcing (9) ─────┐│  │  ┌─ L1 自感知 ─────────────────┐  │
│  │ Store·Tracer·DeadLetterQ ││  │  │ System·Disk·Process·Network  │  │
│  │ PriorityQ·Aggregator     ││  │  │ Service·Agent·Gateway        │  │
│  │ Metrics·PatternMiner     ││  │  │ HealthChecker(27 items)      │  │
│  │ MLEngine·QualityEval     ││  │  └──────────────────────────────┘  │
│  └──────────────────────────┘│  │                                      │
│                               │  │  ┌─ Core Components ─────────────┐  │
│  ┌─ MCP Protocol ───────────┐│  │  │ EnvDetector (8 frameworks)    │  │
│  │ MCPHub · JWT Auth         ││  │  │ IDEBridge (6 CLI agents)      │  │
│  │ 7-Domain Router           ││  │  │ SyncDaemon(5s) · SyncEngine   │  │
│  └──────────────────────────┘│  │  │ AdapterManager · ConfigWizard │  │
│                               │  │  └──────────────────────────────────┘  │
│  ┌─ Services (6) ───────────┐│  │                                      │
│  │ VaultAPI · OSS · MemOS   ││  │  Frameworks: Hermes·OpenClaw·Wukong  │
│  │ KnowledgeGraph            ││  │  QClaw·CoPaw·HiClaw·EasyClaw        │
│  │ 🆕 CredentialSync        ││  │  IDEs: Codex·Claude·Kimi·DeepSeek   │
│  │ 🆕 AccountService        ││  │  Copilot·Windsurf                    │
│  └──────────────────────────┘│  │                                      │
└──────────────────────────────┘  └──────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│  🔄 DATA FLOW: CloudHub ↔ Edge Brain (REST/WSS/MCP)                                │
│  🔄 Credential Sync: AES-256-GCM → auto-push → edge decrypt                        │
│  🔄 SyncDaemon: scan→enqueue→flush→pull→health (5s loop)                           │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## v2.0 核心特性

| 特性 | 说明 |
|------|------|
| **多账户系统** | 三级角色: `core_admin` (超级管理员) / `admin` (管理员) / `user` (普通用户)，RBAC 权限矩阵 |
| **云管理控制台** | Next.js 16 全功能 Dashboard，中/English 双语，节点拓扑可视化 |
| **凭证管理** | AES-256-GCM 加密存储，CloudHub→Edge 自动同步，WebSocket 实时推送 |
| **一键端侧安装** | `curl\|bash` 一键安装 + 交互式配置向导，自动注册到 CloudHub |
| **SSL/HTTPS** | clawshell.club 域名，Let's Encrypt 自动证书，全链路 HTTPS |
| **节点拓扑** | user→node→framework/IDE 三级拓扑关系，Dashboard 实时可视化 |
| **审计日志** | 全操作审计记录，按用户/时间/操作类型筛选 |
| **事件溯源增强** | 9 模块完整 Event Sourcing 体系 + DeepThink 深度推理引擎 |
| **MCP 协议层** | 7 域路由 + JWT 鉴权 + WebSocket MCP |

---

## 快速开始

### 云侧部署 (CloudHub + Dashboard)

```bash
git clone https://github.com/jorinyang/ClawShell.git
cd ClawShell
docker compose up -d
# CloudHub API: http://localhost:8000
# Dashboard:    http://localhost:3000
# 默认管理员: core_admin / clawshell
```

### 端侧安装 (Edge Brain)

```bash
curl -fsSL https://clawshell.club/install.sh | bash
# 交互式引导: 选择框架 → 配置 CloudHub 地址 → 自动注册
```

### 本地开发

```bash
git clone https://github.com/jorinyang/ClawShell.git
cd ClawShell
pip install -e ".[cloud,edge]"
cd dashboard && npm install && npm run dev
```

---

## 架构总览

### CloudHub (云枢)

| 模块 | 数量 | 说明 |
|------|------|------|
| Core Engines | **15** | EventBus · TaskBoard · SkillMarket · CapRegistry · SwarmCoord · CronSched · Evolution · Review · Broadcast · N8N · Workflow · Optimizer · DeepThink · **CredentialMgr** · **AuditEngine** |
| Event Sourcing | **9** | Store · Tracer · DeadLetterQ · PriorityQ · Aggregator · Metrics · PatternMiner · MLEngine · QualityEvaluator |
| MCP Protocol | 3 | MCPHub · JWT Auth · 7-Domain Router |
| Services | **6** | VaultAPI · OSSSync · MemOS · KnowledgeGraph · **CredentialSync** · **AccountService** |

### Edge Brain (端脑)

| 模块 | 数量 | 说明 |
|------|------|------|
| L1-L4 外骨骼 | 4 层 | 自感知 → 自适应 → 自组织 → 多Agent集群 |
| 健康检测器 | **8** | System · Disk · Process · Network · Service · Agent · Gateway · Framework |
| IDE 桥接器 | **6** | Codex · Claude · Kimi · DeepSeek · Copilot · Windsurf |
| Sync Daemon | 1 | 5s 循环: scan→enqueue→flush→pull→health |
| Edge Gateway | 4 | NetworkDiscovery · DeviceMonitor · KnowledgePuller · SelfHealing |

---

## API 参考 (76 Endpoints)

| 类别 | 端点数 | 说明 |
|------|--------|------|
| 认证 & 账户 | 12 | 登录/注册/刷新Token/用户CRUD/角色管理 |
| 凭证管理 | 8 | CRUD/加密/同步/推送/轮换 |
| 任务管理 | 10 | 创建/查询/状态机流转/分配/补偿 |
| 技能市场 | 6 | 发布/发现/同步/版本管理 |
| 节点管理 | 8 | 注册/心跳/拓扑/负载均衡/离线检测 |
| 事件系统 | 10 | 发布/查询/溯源/聚合/重放 |
| 工作流 | 8 | 创建/执行/Saga补偿/状态查询 |
| MCP 协议 | 6 | WebSocket连接/域路由/JWT认证 |
| 审计日志 | 4 | 查询/导出/筛选/统计 |
| 系统 | 4 | 健康检查/配置/版本/指标 |
| **合计** | **76** | 48 (v1.x) + 28 (v2.0新增) |

---

## 权限矩阵

| 资源/操作 | core_admin | admin | user |
|-----------|:----------:|:-----:|:----:|
| 用户管理 (CRUD) | ✅ | ✅ (本组织) | ❌ |
| 角色分配 | ✅ | ❌ | ❌ |
| 节点管理 | ✅ | ✅ | ✅ (自己的) |
| 凭证管理 | ✅ | ✅ | ✅ (只读) |
| 任务管理 | ✅ | ✅ | ✅ (自己的) |
| 技能市场 | ✅ | ✅ | ✅ (只读) |
| 审计日志 | ✅ | ✅ (本组织) | ❌ |
| 系统配置 | ✅ | ❌ | ❌ |
| 工作流管理 | ✅ | ✅ | ❌ |

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
| 7 | 可移植 | 支持 macOS / Linux / WSL |
| 8 | 幂等性 | 重复安装不对已有配置产生副作用 |
| 9 | 端-云版本解耦 | CloudHub 升级不影响 Edge Brain |

---

## 项目结构

```
ClawShell/
├── cloud/                # ☁️ CloudHub
│   ├── engines/          #   15 engines (含 CredentialMgr · AuditEngine)
│   ├── eventing/         #   Event Sourcing (9 modules)
│   ├── mcp/              #   MCP Protocol (Hub · JWT · Router)
│   └── services/         #   6 services (含 CredentialSync · AccountService)
├── edge/                 # 🖥️ Edge Brain
│   ├── eventbus/         #   ConditionEngine + DLQ + Tracer
│   ├── gateway/          #   NetworkDiscovery · DeviceMonitor · SelfHealing
│   ├── adapters/         #   Hermes · Wukong · OpenClaw + AdapterManager
│   ├── detector/         #   8 framework detectors
│   ├── ide_bridge/       #   6 IDE CLI bridges
│   ├── ecosystem/        #   10 component installer
│   └── sync/             #   SyncDaemon (5s loop) + Delta Sync
├── dashboard/            # 📊 云管理控制台 (Next.js 16)
│   ├── app/              #   Pages: auth · nodes · credentials · audit · topology
│   ├── components/       #   UI 组件 (中/English)
│   └── lib/              #   API client · Auth · i18n
├── exoskeleton/          # 🦴 L1-L4 外骨骼
├── shared/               # 🔄 共享类型 · 协议 · MCP Types
├── deploy/               # 🚀 Docker Compose · Terraform · install.sh
├── tests/                # 🧪 测试套件
└── docs/                 # 📚 文档 + SVG 架构图
```

---

## 版本历史

| 版本 | 日期 | 关键变更 |
|------|------|----------|
| **v2.0** | 2026-05 | 多账户系统 · 云管理控制台 · 凭证管理 · 节点拓扑 · 审计日志 · SSL/HTTPS · 76 API |
| v1.12 | 2026-03 | Event Sourcing (9模块) · MCP Protocol Layer · Edge Gateway · Workflow · Optimizer · DeepThink |
| v1.0 | 2025-12 | 初始发布: CloudHub (12 engines) · Edge Brain (L1-L4外骨骼) · 8 检测器 · 6 IDE桥接 · SyncDaemon |

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
