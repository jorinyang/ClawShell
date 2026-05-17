# ClawShell v2.1.0 — "Neural Genesis" 实施计划

> **灵感来源:** Ruflo (claude-flow) v3.7.0 的核心架构
> **目标:** 将 Ruflo 最有价值的 5 个能力模块移植到 ClawShell 的 Python 生态中
> **预计新增:** ~3,500 行 Python 代码，6 个新模块

---

## 1. 背景与动机

### 1.1 Ruflo 是什么

Ruflo 是一个面向 Claude Code 的多代理 AI 编排框架，核心能力包括：
- **HNSW 向量记忆** — 150x-12,500x 加速语义检索
- **行为信任评分** — 0.4×success + 0.2×uptime + 0.2×(1-threat) + 0.2×integrity
- **Swarm 拓扑管理** — mesh/hierarchical/centralized/hybrid 四种拓扑
- **Hook 事件系统** — 17 种 hook 事件 + 12 个后台 worker
- **插件生命周期** — 完整的插件发现/加载/注册/卸载框架

### 1.2 为什么要借鉴

ClawShell v2.0.0 的核心差距：

| 维度 | ClawShell v2.0 | Ruflo v3.7 | 差距 |
|------|---------------|------------|------|
| 向量搜索 | TF-IDF only | HNSW 索引 | 🔴 大 |
| 节点信任 | 静态配置 | 动态评分 | 🔴 大 |
| 记忆管理 | 5 层无统一 | 统一 API | 🟡 中 |
| Swarm 协作 | 基础管理 | 拓扑+共识 | 🟡 中 |
| 插件系统 | YAML 发现 | 完整生命周期 | 🟡 中 |
| Hook 系统 | 无 | 17 种事件 | 🟡 中 |

### 1.3 借鉴原则

1. **Python 原生** — 不引入 Node.js 依赖，使用 Python 生态 (hnswlib, numpy)
2. **渐进增强** — 新模块独立，不破坏 v2.0 现有功能
3. **接口兼容** — 通过适配器模式集成到现有引擎
4. **测试先行** — 每个模块配套完整单元测试

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│  ClawShell v2.1.0 — "Neural Genesis"                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ HNSW Memory │  │   Trust     │  │  Topology   │              │
│  │   Engine    │  │  Evaluator  │  │  Manager    │  ← NEW       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐              │
│  │  Unified    │  │    Hook     │  │  Plugin     │              │
│  │  Memory Mgr │  │   Manager   │  │  Lifecycle  │  ← NEW       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│  ═══════╪════════════════╪════════════════╪═════════════════     │
│         │      Existing v2.0 Layer        │                      │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐              │
│  │ CloudHub    │  │  EdgeBrain  │  │  SyncDaemon │              │
│  │ (12 engines)│  │  (L1-L4)    │  │  (5s loop)  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 模块详细设计

### 3.1 P0: HNSW 向量记忆引擎

**灵感来源:** `ruflo/v3/@claude-flow/memory/src/hnsw-index.ts`
**目标:** 替代 TF-IDF，提供 100x+ 加速的语义向量检索

**文件:**
- `shared/memory/hnsw_engine.py` (新建)
- `shared/memory/__init__.py` (新建)
- `tests/test_hnsw_engine.py` (新建)

**依赖:** `hnswlib` (纯 Python/C++ 绑定，无 GPU 要求)

**核心接口:**
```python
class HNSWEngine:
    """HNSW 向量索引引擎"""
    
    def __init__(self, dim: int = 384, max_elements: int = 100_000,
                 ef_construction: int = 200, M: int = 16,
                 space: str = "cosine"):
        ...
    
    def add(self, id: str, vector: np.ndarray, metadata: dict = None) -> None:
        """添加向量"""
    
    def search(self, query: np.ndarray, k: int = 10,
               filter_fn: Callable = None) -> list[SearchResult]:
        """搜索最近邻"""
    
    def delete(self, id: str) -> None:
        """删除向量"""
    
    def save(self, path: str) -> None:
        """持久化索引"""
    
    def load(self, path: str) -> None:
        """加载索引"""
```

**数据类型:**
```python
@dataclass
class SearchResult:
    id: str
    distance: float
    score: float  # 1 - distance (相似度)
    metadata: dict
```

**优化点 (参考 Ruflo):**
- 预归一化向量 → O(1) 余弦相似度
- BinaryMinHeap 用于候选集管理 (Python heapq 实现)
- 分层持久化 (索引文件 + 元数据 JSON)

---

### 3.2 P0: 行为信任评分系统

**灵感来源:** `ruflo/v3/@claude-flow/plugin-agent-federation/src/application/trust-evaluator.ts`
**目标:** 为 Edge 节点提供动态行为信任评分

**文件:**
- `shared/trust/evaluator.py` (新建)
- `shared/trust/__init__.py` (新建)
- `tests/test_trust_evaluator.py` (新建)

**核心公式 (直接移植 Ruflo):**
```
trust_score = 0.4 × success_rate
            + 0.2 × uptime_ratio
            + 0.2 × (1 - threat_penalty)
            + 0.2 × data_integrity_score
```

**信任等级:**
```python
class TrustLevel(Enum):
    UNTRUSTED = 0    # score < 0.2
    LOW = 1          # 0.2 <= score < 0.4
    STANDARD = 2     # 0.4 <= score < 0.6
    HIGH = 3         # 0.6 <= score < 0.8
    PRIVILEGED = 4   # score >= 0.8
```

**核心接口:**
```python
class TrustEvaluator:
    """行为信任评分器"""
    
    def compute_score(self, metrics: NodeMetrics) -> TrustScore:
        """计算信任分数"""
    
    def evaluate_transition(self, node_id: str, metrics: NodeMetrics) -> TrustTransition | None:
        """评估信任等级变更"""
    
    def record_threat(self, node_id: str) -> bool:
        """记录威胁检测，返回是否触发降级"""
    
    def immediate_downgrade(self, node_id: str, reason: str) -> TrustTransition:
        """立即降级（安全事件）"""
```

**数据类型:**
```python
@dataclass
class NodeMetrics:
    messages_sent: int = 0
    messages_received: int = 0
    hmac_failures: int = 0
    threat_detections: int = 0
    uptime_seconds: float = 0
    total_seconds: float = 0
    tasks_completed: int = 0
    tasks_failed: int = 0

@dataclass
class TrustScore:
    score: float  # 0.0 - 1.0
    level: TrustLevel
    components: dict  # success_rate, uptime, threat_penalty, integrity

@dataclass
class TrustTransition:
    node_id: str
    previous_level: TrustLevel
    new_level: TrustLevel
    score: float
    reason: str
    timestamp: float
```

**集成点:**
- `CapabilityRegistry` 在心跳时更新 metrics → `TrustEvaluator`
- `SwarmCoordinator` 根据 trust_score 调度任务
- `SyncDaemon` 上报 metrics 到 CloudHub

---

### 3.3 P1: 统一记忆管理器

**灵感来源:** `ruflo/v3/@claude-flow/memory/src/` 的统一内存架构
**目标:** 统一 ClawShell 的 5 层记忆系统为单一 API

**文件:**
- `shared/memory/unified_manager.py` (新建)

**核心接口:**
```python
class UnifiedMemoryManager:
    """统一记忆管理器 — 5 层合一"""
    
    def __init__(self, config: MemoryConfig):
        self.hnsw = HNSWEngine(...)           # 向量层
        self.knowledge_graph = KnowledgeGraph  # 知识图谱层
        self.memory_store = MemoryStore        # 时间衰减层
        self.mempalace = MemPalaceBridge       # MemPalace 层
        self.memos = MemOSBridge               # MemOS 云层
    
    def store(self, key: str, content: str, memory_type: MemoryType,
              namespace: str = "default", tags: list[str] = None,
              access_level: AccessLevel = AccessLevel.PRIVATE) -> str:
        """存储记忆，自动路由到合适的层"""
    
    def search(self, query: str, k: int = 10,
               memory_types: list[MemoryType] = None,
               namespace: str = None,
               access_level: AccessLevel = None) -> list[MemoryResult]:
        """跨层语义搜索"""
    
    def consolidate(self) -> ConsolidationReport:
        """记忆整合 — 去重、合并、清理过期"""
```

**记忆类型 (参考 Ruflo):**
```python
class MemoryType(Enum):
    EPISODIC = "episodic"      # 时间序列事件
    SEMANTIC = "semantic"      # 知识/概念
    PROCEDURAL = "procedural"  # 技能/操作
    WORKING = "working"        # 短期工作记忆
    CACHE = "cache"            # 临时缓存
```

---

### 3.4 P1: Swarm 拓扑管理器

**灵感来源:** `ruflo/v3/@claude-flow/swarm/src/types.ts`
**目标:** 为 CloudHub SwarmCoordinator 引入拓扑感知

**文件:**
- `cloud/engines/topology_manager.py` (新建)
- `tests/test_topology_manager.py` (新建)

**拓扑类型:**
```python
class TopologyType(Enum):
    MESH = "mesh"              # 全互联（同级协作）
    HIERARCHICAL = "hierarchical"  # 云枢为 Queen，端脑为 Worker
    CENTRALIZED = "centralized"    # 单一中心节点
    HYBRID = "hybrid"          # 混合模式
```

**核心接口:**
```python
class TopologyManager:
    """Swarm 拓扑管理器"""
    
    def __init__(self, topology_type: TopologyType = TopologyType.HIERARCHICAL):
        self.nodes: dict[str, TopologyNode] = {}
        self.edges: list[TopologyEdge] = []
        self.partitions: dict[str, TopologyPartition] = {}
    
    def add_node(self, node_id: str, role: NodeRole, capabilities: dict) -> None:
        """添加节点到拓扑"""
    
    def remove_node(self, node_id: str) -> None:
        """移除节点并重新平衡"""
    
    def elect_leader(self, partition_id: str = None) -> str:
        """选举 leader（基于 trust_score + capability）"""
    
    def rebalance(self) -> RebalanceResult:
        """重新分配任务和连接"""
    
    def get_route(self, from_node: str, to_node: str) -> list[str]:
        """获取路由路径"""
    
    def get_topology_state(self) -> TopologyState:
        """获取当前拓扑状态快照"""
```

---

### 3.5 P2: Hook 事件系统

**灵感来源:** `ruflo/v3/@claude-flow/hooks/src/types.ts`
**目标:** 为引擎和端脑提供事件钩子机制

**文件:**
- `shared/hooks/manager.py` (新建)
- `shared/hooks/__init__.py` (新建)
- `tests/test_hook_manager.py` (新建)

**Hook 事件类型:**
```python
class HookEvent(Enum):
    # 任务生命周期
    PRE_TASK = "pre-task"
    POST_TASK = "post-task"
    TASK_PROGRESS = "task-progress"
    
    # 事件处理
    PRE_EVENT = "pre-event"
    POST_EVENT = "post-event"
    
    # 节点生命周期
    NODE_JOIN = "node-join"
    NODE_LEAVE = "node-leave"
    NODE_HEARTBEAT = "node-heartbeat"
    
    # 同步
    PRE_SYNC = "pre-sync"
    POST_SYNC = "post-sync"
    
    # 学习
    PATTERN_LEARNED = "pattern-learned"
    
    # 安全
    THREAT_DETECTED = "threat-detected"
    TRUST_CHANGED = "trust-changed"
```

**优先级:**
```python
class HookPriority(IntEnum):
    CRITICAL = 1000  # 安全/验证 — 最先执行
    HIGH = 100       # 预处理
    NORMAL = 50      # 标准
    LOW = 10         # 日志/指标
    BACKGROUND = 1   # 异步 — 最后执行
```

---

### 3.6 P2: 插件生命周期框架

**灵感来源:** `ruflo/v3/@claude-flow/plugins/src/` 的插件 SDK
**目标:** 将现有 PluginManager 升级为完整生命周期框架

**文件:**
- `edge/ecosystem/plugin_lifecycle.py` (新建)
- `tests/test_plugin_lifecycle.py` (新建)

**插件状态机:**
```python
class PluginState(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    SHUTTING_DOWN = "shutting-down"
    SHUTDOWN = "shutdown"
    ERROR = "error"
```

**核心接口:**
```python
class IPlugin(Protocol):
    """插件接口"""
    metadata: PluginMetadata
    state: PluginState
    
    async def initialize(self, context: PluginContext) -> None: ...
    async def shutdown(self) -> None: ...
    async def health_check(self) -> HealthCheckResult: ...

class PluginLifecycleManager:
    """插件生命周期管理器"""
    
    def register(self, plugin: IPlugin) -> None: ...
    async def initialize_all(self) -> None: ...
    async def shutdown_all(self) -> None: ...
    def get_state(self, name: str) -> PluginState: ...
    async def health_check_all(self) -> dict[str, HealthCheckResult]: ...
```

---

## 4. 实施顺序

| Phase | 模块 | 预计工时 | 依赖 |
|-------|------|---------|------|
| P0-A | HNSW 向量记忆引擎 | 30 min | 无 |
| P0-B | 行为信任评分系统 | 20 min | 无 |
| P1-A | 统一记忆管理器 | 25 min | P0-A |
| P1-B | Swarm 拓扑管理器 | 25 min | P0-B |
| P2-A | Hook 事件系统 | 20 min | 无 |
| P2-B | 插件生命周期框架 | 20 min | P2-A |
| Final | 版本更新 + Release | 15 min | 全部 |

---

## 5. 测试策略

每个模块必须包含：
1. **单元测试** — 核心接口全覆盖
2. **集成测试** — 与现有引擎的交互
3. **性能基准** — HNSW vs TF-IDF 对比

```bash
# 运行所有 v2.1 测试
cd /home/aorus/.clawshell && python -m pytest tests/test_hnsw_engine.py tests/test_trust_evaluator.py tests/test_topology_manager.py tests/test_hook_manager.py tests/test_plugin_lifecycle.py -v
```

---

## 6. 版本发布

- **版本号:** v2.1.0 (MINOR — 新增功能，不破坏兼容)
- **Release Notes:** 详细列出每个新模块、每个 API、每个改进
- **GitHub:** 推送到 jorinyang/ClawShell，创建 v2.1.0 tag + release

---

*Plan generated: 2026-05-17 | ClawShell v2.1.0 "Neural Genesis"*
