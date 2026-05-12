# ClawShell 2.0 — 核心定义与设计哲学

> 版本: 2.0.0-dev | 2026-05-12

---

## 核心定义

**ClawShell 本质上是一个适用于类 OpenClaw 架构的增强型外骨骼功能插件；
具备的自感知、自适应、自组织能力是以插件形式加强类 OpenClaw 架构的底层能力，
使其能够更快了解环境、适应环境、动态协作。**

## 指导思想：工程控制论

架构设计以**工程控制论**为指导思想，核心是**信息反馈、动态调控和系统整体思维**。

| 控制论概念 | ClawShell 实现 |
|-----------|---------------|
| 系统整体思维 | 全局任务调度 (GlobalTaskBoard + SwarmCoordinator) |
| 信息反馈机制 | EventBus + ContextManager + Comparator |
| 动态调控 | FeedbackControlLoop + AdaptiveParameterTuner |
| 鲁棒性设计 | SelfRepairEngine + RobustController |
| 层次化建模 | L1-L4 四层架构 |
| 综合集成 | Hermes/Wukong 适配器 + IDE Bridge (人机协同) |

## 四层架构

| 层级 | 名称 | 核心能力 |
|------|------|----------|
| **L1** | 自感知 (Self-Sensing) | 系统/网络/进程/磁盘健康检测，环境信息采集 |
| **L2** | 自适应 (Self-Adaptation) | 自修复引擎、工程控制论反馈闭环、参数自适应调优 |
| **L3** | 自组织 (Self-Organization) | EventBus事件总线、DAG任务编排、ContextManager全局状态 |
| **L4** | 多Agent集群 (Multi-Agent Swarm) | 集群发现、信任评估、生态位匹配、协作协议 |

## 设计原则 (10条)

1. **异构同效** — 不同架构/技术栈模块在同一机制下发挥同等效能
2. **无侵入** — 不修改已部署框架核心代码
3. **低耦合** — 模块间通过文件协议和EventBus通信
4. **高鲁棒** — 多层级错误恢复、守护进程保活、自动降级
5. **高泛用** — 感知层抽象、适配器模式、标准化接口
6. **高协同** — EventBus + ContextManager + TaskMarket + Swarm
7. **可移植** — macOS/Linux/WSL全平台
8. **幂等性** — 重复安装无副作用
9. **端-云版本解耦** — Cloud Hub升级不影响Edge Brain

## 2.0 核心创新

1. **一云多端架构** — 1个云枢 + N个端脑，分布式神经协同
2. **Harness Engineering** — IDE Bridge 多Agent CLI协同开发
3. **行动前参考** — 每次行动前主动拉取云端insight作为上下文
4. **离线自治** — Cloud离线时端脑独立自主执行
5. **跨Edge进化** — 一端成长，多端共进 (insight/skill广播)
