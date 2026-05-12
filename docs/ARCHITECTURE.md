# ClawShell 2.0 — 一云多端云边协同分布式神经系统

> **Architecture Document** | Version 1.8 | 2026-05-12

---

## 架构全景

ClawShell 2.0 采用**一云多端云边协同分布式神经架构**：

```
☁️ CLOUD HUB (云枢)                     🖥️ EDGE BRAIN (端脑)
┌──────────────────────────┐         ┌──────────────────────────┐
│ FastAPI Server (:8000)   │  HTTPS  │ EnvDetector              │
│ ├ CloudEventBus          │◄───────►│ ├ 10+ 框架自动检测        │
│ ├ GlobalTaskBoard        │   WSS   │ IDEBridge                │
│ ├ SkillMarket            │         │ ├ Codex/Claude/Kimi/     │
│ ├ CapabilityRegistry     │         │ │ DeepSeek/Copilot       │
│ ├ SwarmCoordinator       │         │ ├ Orchestrator+Sandbox   │
│ ├ EvolutionEngine        │         │ Ecosystem (10组件)        │
│ ├ ReviewEngine           │         │ SyncDaemon (5s loop)     │
│ ├ BroadcastEngine        │         │ Exoskeleton L1-L4        │
│ ├ VaultAPI + OSS Sync    │         │ ActionReference          │
│ ├ MemOS Cloud Client     │         │ ConfigWizard + CLI       │
│ └ N8NBridge              │         └──────────────────────────┘
└──────────────────────────┘
```

## 云枢 (Cloud Hub)

部署于阿里云 ECS，负责全局架构规划、洞察分析、复盘总结、成果广播、终端管理。

| 引擎 | 功能 |
|------|------|
| CloudEventBus | 持久化 + SHA256去重 + 通配符查询 + 30天过期 |
| GlobalTaskBoard | 跨Edge任务CRUD + 状态机 + 优先级队列 |
| SkillMarket | 技能发布/发现/同步 + 版本管理 |
| CapabilityRegistry | Edge注册 + 能力声明 + 心跳监控 |
| SwarmCoordinator | 节点管理 + 负载均衡 + 离线检测 |
| CronScheduler | 5-field cron + 执行日志 |
| EvolutionEngine | 洞察聚合 → 模式挖掘 → 自动技能发布 |
| UnifiedReviewEngine | 日/周/月复盘 → ActionPlan |
| BroadcastEngine | 公告广播 + 最佳实践注册 + 跨Edge学习 |
| N8NBridge | 事件 → N8N工作流映射 |

## 端脑 (Edge Brain)

安装于用户终端，自适应不同类OpenClaw架构。

| 组件 | 功能 |
|------|------|
| EnvDetector | 10+ 框架自动检测 (Wukong/Hermes/OpenClaw/QClaw/CoPaw/HiClaw/EasyClaw/WorkBuddy) |
| IDEBridge | 6 Agent CLI IDE桥接 (Codex/Claude Code/Kimi Code/DeepSeek TUI/Copilot) |
| Ecosystem | 10 可选组件安装器 |
| SyncDaemon | 5s周期 Cloud↔Edge 同步 |
| Adapters | 框架适配器 + 行动前参考注入 |
| Exoskeleton L1 | 自感知 — 系统/磁盘/进程/网络健康检测 |
| Exoskeleton L2 | 自适应 — 自修复 + 控制论反馈闭环 + 参数自调优 |
| Exoskeleton L3 | 自组织 — EventBus + DAG任务编排 + ContextManager |
| Exoskeleton L4 | 多Agent集群 — Swarm + 信任评估 + 生态位匹配 + 协作协议 |

## 设计原则

| 原则 | 说明 |
|------|------|
| 异构同效 | 不同架构/技术栈模块在同一机制下发挥同等效能 |
| 无侵入 | 不修改已部署框架核心代码 |
| 低耦合 | 模块间通过文件协议和EventBus通信 |
| 高鲁棒 | 多层级错误恢复、守护进程保活、自动降级 |
| 高泛用 | 感知层抽象、适配器模式、标准化接口 |
| 高协同 | EventBus + ContextManager + TaskMarket + Swarm |
| 可移植 | macOS/Linux/WSL全平台 |
| 幂等性 | 重复安装无副作用 |
| 端-云版本解耦 | Cloud升级不影响Edge |

## 指导思想

**工程控制论** — 信息反馈、动态调控、系统整体思维

## 技术栈

- **Cloud**: Python 3.8+ / FastAPI / Uvicorn / WebSocket / Docker / Nginx
- **Edge**: Python 3.8+ / stdlib HTTP / psutil
- **Deploy**: Terraform (阿里云ECS) / Docker Compose
- **Storage**: MemOS Cloud (记忆) / OSS (知识库) / GitHub (代码)

## 快速开始

```bash
# Edge 安装
curl -fsSL https://raw.githubusercontent.com/jorinyang/ClawShell/main/deploy/edge/install.sh | bash

# Cloud 部署
cd deploy/cloud/terraform
terraform init && terraform apply

# 本地开发
git clone https://github.com/jorinyang/ClawShell.git
cd ClawShell
pip install -e ".[cloud,edge]"
```
