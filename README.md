# ClawShell 2.0

> **一云多端云边协同分布式神经系统**
>
> 版本: 1.8 | 架构: 云枢 + 端脑 | 指导思想: 工程控制论

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

## 架构全景

```
☁️ CLOUD HUB (云枢)                     🖥️ EDGE BRAIN (端脑)
┌──────────────────────┐         ┌──────────────────────┐
│ FastAPI Server       │  HTTPS  │ EnvDetector          │
│ ├ CloudEventBus      │◄───────►│ ├ Wukong/Hermes/...  │
│ ├ GlobalTaskBoard    │   WSS   │ IDEBridge            │
│ ├ SkillMarket        │         │ ├ Codex/Claude Code  │
│ ├ CapabilityRegistry │         │ ├ Kimi/DeepSeek      │
│ ├ SwarmCoordinator   │         │ ├ Copilot            │
│ ├ EvolutionEngine    │         │ Ecosystem            │
│ ├ ReviewEngine       │         │ ├ MemPalace/N8N/...  │
│ └ BroadcastEngine    │         │ SyncDaemon (5s)      │
└──────────────────────┘         │ Exoskeleton L1-L4    │
                                 └──────────────────────┘
```

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
├── cloud/              # ☁️ Cloud Hub
├── edge/               # 🖥️ Edge Brain
├── exoskeleton/        # 🦴 四层外骨骼 (L1-L4)
├── shared/             # 🔄 共享类型与协议
├── deploy/             # 🚀 部署配置
├── tests/              # 🧪 测试
└── docs/               # 📚 文档
```

## 文档

- [架构全景](docs/ARCHITECTURE.md) — 一云多端完整架构
- [核心定义](docs/CORE_DEFINITION.md) — 设计哲学与工程控制论
- [安装指南](docs/INSTALL.md)
- [API 参考](docs/API_REFERENCE.md)

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
