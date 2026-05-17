# Changelog

## v2.1.0 — "Neural Genesis" (2026-05-17)

> **灵感来源:** 借鉴 [Ruflo](https://github.com/ruvnet/ruflo) v3.7.0 的核心架构，将 5 个最有价值的能力模块移植到 ClawShell Python 生态。

### 🚀 New Features

#### P0: HNSW 向量记忆引擎 (`shared/memory/hnsw_engine.py`)
- **HNSWVectorMemory** — 基于 hnswlib 的高性能向量检索，150x-12,500x 加速
- 支持 cosine、euclidean、inner product 三种距离度量
- 批量操作: `add_batch()`, `search_batch()`
- 自动持久化: `save()`/`load()` 索引文件
- 线程安全 (threading.Lock)
- `embed_text_simple()` — 无外部依赖的文本向量化
- **52 unit tests**

#### P0: 行为信任评分系统 (`shared/trust/evaluator.py`)
- **TrustEvaluator** — 基于 Ruflo 的动态行为信任评分
- 核心公式: `0.4×success_rate + 0.2×uptime + 0.2×(1-threat) + 0.2×integrity`
- 5 级信任: UNTRUSTED → LOW → STANDARD → HIGH → PRIVILEGED
- 威胁窗口: 1 小时滚动窗口，2+ 检测触发惩罚
- 安全事件即时降级: HMAC 失败、会话劫持
- 持久化: JSON 序列化/反序列化
- **35 unit tests**

#### P1: 统一记忆管理器 (`shared/memory/unified_manager.py`)
- **UnifiedMemoryManager** — 5 层记忆系统统一 API
- 5 种记忆类型: EPISODIC / SEMANTIC / PROCEDURAL / WORKING / CACHE
- 4 级访问控制: PRIVATE / TEAM / SWARM / PUBLIC
- 复合搜索评分: 向量相似度 × 时间衰减 × 重要度加权
- 记忆整合: 去重(内容哈希)、合并、过期清理、容量淘汰
- **54 unit tests**

#### P1: Swarm 拓扑管理器 (`cloud/engines/topology_manager.py`)
- **TopologyManager** — 拓扑感知的 Swarm 协调
- 4 种拓扑: MESH / HIERARCHICAL / CENTRALIZED / HYBRID
- 4 种角色: QUEEN / WORKER / COORDINATOR / PEER
- Leader 选举: `trust_score × 0.6 + (1 - workload) × 0.4`
- BFS 路由: 节点间最短路径
- 自动重平衡: 节点增删触发拓扑重构
- **48 unit tests**

#### P2: Hook 事件系统 (`shared/hooks/manager.py`)
- **HookManager** — 事件拦截器框架
- 13 种 Hook 事件 (任务/节点/同步/学习/安全)
- 5 级优先级: CRITICAL(1000) → BACKGROUND(1)
- 数据链传递: Hook 可修改/阻止后续操作
- 异常容错: Hook 异常不影响链路
- **15 unit tests**

#### P2: 插件生命周期框架 (`edge/ecosystem/plugin_lifecycle.py`)
- **PluginLifecycleManager** — 完整插件状态机
- 7 种状态: UNINITIALIZED → INITIALIZING → INITIALIZED → ACTIVE → SHUTTING_DOWN → SHUTDOWN / ERROR
- Kahn 拓扑排序: 依赖顺序初始化
- 循环依赖检测
- 服务注入 (DI 容器)
- 健康检查 + 延迟追踪
- **16 unit tests**

### 📊 Statistics

| Metric | Value |
|--------|-------|
| New Python files | 12 |
| New test files | 6 |
| New Python LOC | ~3,500 |
| New unit tests | 220 |
| Test execution time | 0.49s |
| New dependencies | hnswlib, numpy |

### 📁 New Files

```
shared/
├── memory/
│   ├── __init__.py
│   ├── hnsw_engine.py          # HNSW 向量引擎
│   └── unified_manager.py      # 统一记忆管理器
├── trust/
│   ├── __init__.py
│   └── evaluator.py            # 行为信任评分
└── hooks/
    ├── __init__.py
    └── manager.py              # Hook 事件系统

cloud/engines/
└── topology_manager.py         # Swarm 拓扑管理器

edge/ecosystem/
└── plugin_lifecycle.py         # 插件生命周期框架

tests/
├── test_hnsw_engine.py         # 52 tests
├── test_trust_evaluator.py     # 35 tests
├── test_unified_manager.py     # 54 tests
├── test_topology_manager.py    # 48 tests
├── test_hook_manager.py        # 15 tests
└── test_plugin_lifecycle.py    # 16 tests

docs/
├── ClawShell-v2.1-Ruflo-Adaptation-Plan.md  # 详细实施计划
└── CHANGELOG.md                              # 本文件
```

---

## v2.0.0 (2026-05-15)

### 🚀 Features
- Multi-account auth system (SQLite + RBAC + AES-256-GCM)
- 12 cloud engines (EventBus, TaskBoard, SkillMarket, SwarmCoordinator, etc.)
- 9-module event sourcing infrastructure
- 4-layer exoskeleton (L1-L4)
- MCP WebSocket protocol (JSON-RPC 2.0)
- 8 framework detectors, 6 IDE bridges
- SyncDaemon (5s loop)
- Web dashboard (Next.js)
