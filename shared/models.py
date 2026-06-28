"""ClawShell Pydantic v2 data models.

Design inspired by ClawShell-DEEP shared/models.py.
Provides type-safe models for new engine code while maintaining
backward compatibility with existing @dataclass types in types.py.

All models use Pydantic v2 (pydantic>=2.5.0).
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional, Union
from pydantic import BaseModel, Field

# ── Enums (also available in types.py for backward compat) ─────────

class Strategy(str):
    """Runtime strategy modes."""
    DEFAULT = "default"
    EMERGENCY = "emergency"
    ECONOMY = "economy"
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"

class HealthStatus(str):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

class TrustLevel(str):
    UNTRUSTED = "untrusted"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FULL = "full"

class EventCategory(str):
    """Event categories matching cloud/edge event patterns."""
    TASK = "task"
    NODE = "node"
    INSIGHT = "insight"
    STRATEGY = "strategy"
    ERROR = "error"
    SYSTEM = "system"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"

class EventPriority:
    """Event priority levels (int-based, higher = more urgent)."""
    LOW = 0
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100

class TaskStatusClass:
    """Task status constants (matches old types.py TaskStatus Enum)."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

TaskStatus = TaskStatusClass  # Alias for backward compat

class RepairLayer(str):
    SELF_HEALING = "self_healing"
    AUTO_REPAIR = "auto_repair"
    MANUAL = "manual"

class CapabilityDomain(str):
    SKILL = "skill"
    TOOL = "tool"
    API = "api"
    MODEL = "model"
    SERVICE = "service"

class PerceptionDimension(str):
    SYSTEM = "system"
    NETWORK = "network"
    CLOUD = "cloud"
    INTERNET = "internet"

class OpenClawVariant(str):
    OPENCLAW = "openclaw"
    HERMES = "hermes"
    WORK_BUDDY = "work_buddy"
    EASYCLAW = "easyclaw"
    QCLAW = "qclaw"
    COPAW = "copaw"
    HICLAW = "hiclaw"
    WUKONG = "wukong"
    UNKNOWN = "unknown"

# Type aliases
NodeID = str
TaskID = str
PluginID = str
EventID = str

# ── Node / Core Models ──────────────────────────────────────────────

class NodeInfo(BaseModel):
    """Edge node registration info."""
    node_id: NodeID
    node_type: str = "ganglion"  # "cortex" or "ganglion"
    variant: str = "unknown"
    hostname: str = ""
    os: str = ""
    arch: str = ""
    ip_address: str = ""
    status: str = "offline"
    capabilities: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_legacy_dict(self) -> dict[str, Any]:
        """Backward-compatible dict for legacy dataclass consumers."""
        return self.model_dump(mode="json")


class NodeHeartbeat(BaseModel):
    """Heartbeat metrics from edge to cloud."""
    node_id: NodeID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "online"
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    active_tasks: int = 0


class CortexInfo(BaseModel):
    """Cortex (Cloud Hub) self-info."""
    node_id: NodeID = "cortex-01"
    node_type: str = "cortex"
    version: str = "1.9.0"
    status: str = "online"
    connected_edges: int = 0
    uptime_seconds: float = 0.0


# ── Task Models ──────────────────────────────────────────────────────

class Task(BaseModel):
    """Task with full lifecycle tracking."""
    task_id: TaskID
    title: str
    description: str = ""
    status: str = "pending"
    priority: int = 50  # 0=LOW, 50=NORMAL, 80=HIGH, 100=CRITICAL
    assigned_to: Optional[NodeID] = None
    created_by: Optional[NodeID] = None
    tags: list[str] = Field(default_factory=list)
    dependencies: list[TaskID] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: int = 300

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class TaskResult(BaseModel):
    """Task completion result."""
    task_id: TaskID
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    duration_ms: float = 0.0
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Event / Message Models ───────────────────────────────────────────

class EventMessage(BaseModel):
    """Standard event message for CloudEventBus / Neural Bus."""
    event_id: str = ""
    category: str = ""  # task, node, insight, strategy, error, system
    event_type: str = ""  # e.g., "task.created", "node.online"
    source: NodeID = ""
    target: Optional[NodeID] = None
    priority: int = 50  # 0=LOW, 50=NORMAL, 80=HIGH, 100=CRITICAL
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    ttl_seconds: int = 60  # 0 = no expiry

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ── Insight / Knowledge / Memory ─────────────────────────────────────

class Insight(BaseModel):
    """Cortex-generated insight from event analysis."""
    insight_id: str
    title: str
    content: str
    category: str = "general"  # alert, summary, pattern, optimization
    severity: int = 50  # EventPriority
    source_node: Optional[NodeID] = None
    tags: list[str] = Field(default_factory=list)
    actionable: bool = False
    action: Optional[dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Knowledge(BaseModel):
    """Knowledge entry for KnowledgeStore."""
    knowledge_id: str
    title: str
    content: str
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    source: str = "hub"
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Memory(BaseModel):
    """Memory entry with time-decay scoring."""
    memory_id: str
    content: str
    importance: float = 0.5  # 0.0 to 1.0
    decay_factor: float = 0.95  # per-day decay
    category: str = "session"
    tags: list[str] = Field(default_factory=list)
    source_node: Optional[NodeID] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    ttl_seconds: int = 0  # 0 = no expiry

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ── Plugin Models ────────────────────────────────────────────────────

class Plugin(BaseModel):
    """Plugin registration info."""
    plugin_id: PluginID
    name: str
    version: str = "0.1.0"
    description: str = ""
    domain: str = "tool"  # skill, tool, api, model, service
    provider: str = ""
    endpoint: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)
    health_status: str = "unknown"
    enabled: bool = True
    last_checked: Optional[datetime] = None

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PluginRegistry(BaseModel):
    """Registry of all plugins on a node."""
    node_id: NodeID
    plugins: list[Plugin] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Health / Repair ──────────────────────────────────────────────────

class HealthReport(BaseModel):
    """System health report."""
    node_id: NodeID = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    overall: str = "unknown"  # healthy, warning, critical, unknown
    components: dict[str, str] = Field(default_factory=dict)
    issues: list[dict[str, Any]] = Field(default_factory=list)

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class RepairAction(BaseModel):
    """Repair action with escalation tracking."""
    action_id: str
    component: str = ""
    layer: str = "self_healing"  # self_healing, auto_repair, manual
    action: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    triggered_by: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: Optional[dict[str, Any]] = None

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ── Perception Models ────────────────────────────────────────────────

class SystemPerception(BaseModel):
    """System-level perception snapshot."""
    cpu_percent: float = 0.0
    cpu_count: int = 1
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_percent: float = 0.0
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_percent: float = 0.0
    processes: list[dict[str, Any]] = Field(default_factory=list)


class NetworkPerception(BaseModel):
    """Network-level perception snapshot."""
    hostname: str = ""
    ip_address: str = ""
    mac_address: str = ""
    open_ports: list[int] = Field(default_factory=list)
    services: list[dict[str, Any]] = Field(default_factory=list)
    internet_access: bool = False


class PerceptionResult(BaseModel):
    """Full perception result for one dimension."""
    dimension: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)
    health: str = "unknown"


# ── Swarm / Cluster Models ───────────────────────────────────────────

class SwarmNode(BaseModel):
    """Node in the swarm with trust score."""
    node_id: NodeID
    version: str = ""
    status: str = "offline"
    capabilities: list[str] = Field(default_factory=list)
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trust_score: float = 1.0


# ── Config Models ────────────────────────────────────────────────────

class CortexConfig(BaseModel):
    """Cortex (Cloud Hub) configuration."""
    node_id: NodeID = "cortex-01"
    host: str = "0.0.0.0"
    port: int = 8000
    strategy: str = "default"
    heartbeat_interval: int = 30
    max_edges: int = 100
    insight_broadcast_interval: int = 300
    knowledge_sync_interval: int = 600


class DispatchLayer(str):
    """Three-layer dispatch channels."""
    EVENTBUS = "eventbus"    # Push: EventBus publish
    TASKBOARD = "taskboard"  # Pull: GlobalTaskBoard
    MCP_DIRECT = "mcp_direct"  # RPC: MCP direct call


class DispatchResult(str):
    """Dispatch outcome."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    NO_CLAIM = "no_claim"    # TaskBoard无人认领
    UNREACHABLE = "unreachable"  # Edge不在线/不可达


class ProblemType(str):
    """Cloud-wide problem types detected by CronSupervisor."""
    EDGE_OFFLINE = "edge_offline"       # Edge失联
    CRON_STARVED = "cron_starved"       # Cron长期未执行
    CHRONIC_FAILURE = "chronic_failure"  # 慢性故障(连续失败)
    GLOBAL_ANOMALY = "global_anomaly"   # 全局异常(所有Edge同时异常)
    SYNC_LAG = "sync_lag"               # 同步延迟过长
    ENGINE_DEGRADED = "engine_degraded" # 云端引擎降级


class GanglionConfig(BaseModel):
    """Ganglion (Edge Brain) configuration."""
    node_id: NodeID = ""
    cortex_host: str = "localhost"
    cortex_port: int = 8000
    variant: str = "unknown"
    strategy: str = "default"
    heartbeat_interval: int = 30
    perception_interval: int = 60
    auto_register: bool = True
    offline_mode: bool = False
    plugins_dir: str = "plugins"


# ── CronSupervisor Models ─────────────────────────────────────────────────

class CronReport(BaseModel):
    """Standardized report from any Cron execution (cloud or edge).

    Every Cron task on every node generates this report after execution.
    The CloudCronSupervisor aggregates all reports to detect patterns.
    """
    report_id: str = ""
    source: str = ""          # "cloud:scheduler:evolution" | "edge:local_scheduler:node-xxx"
    task_id: str = ""        # "cloud.evolution.cycle" | "edge.cleanup"
    scheduled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "success"  # "success" | "failed" | "skipped" | "timeout"
    error: Optional[str] = None
    duration_ms: float = 0.0
    cpu_avg: float = 0.0
    memory_mb: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Problem(BaseModel):
    """A detected problem from report analysis."""
    problem_id: str = ""
    problem_type: str = ""   # ProblemType.*
    source: str = ""         # cloud | edge:node-xxx
    severity: int = 50      # EventPriority
    title: str = ""
    description: str = ""
    affected_tasks: list[str] = Field(default_factory=list)  # related CronReport.report_id
    repair_action: Optional[str] = None  # recommended action
    dispatch_layer: str = ""  # DispatchLayer.*
    dispatch_status: str = "pending"  # pending | dispatched | confirmed | failed | escalated
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DispatchRecord(BaseModel):
    """Record of one dispatch attempt across layers."""
    dispatch_id: str = ""
    problem_id: str = ""
    layer: str = ""          # DispatchLayer.*
    target: str = ""         # edge:node-xxx | cloud
    action: str = ""
    result: str = "pending"  # DispatchResult.*
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    next_layer: Optional[str] = None  # next fallback layer

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class RepairPlan(BaseModel):
    """Complete repair plan generated by RepairOrchestrator."""
    plan_id: str = ""
    problem: Problem
    action: str = ""
    target: str = ""         # edge:node-xxx | cloud | all
    dispatch_layer: str = ""  # DispatchLayer.*
    priority: int = 50
    estimated_duration_ms: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ── v3.0: Agent / Injection / Repo Models ───────────────────────────

class InjectionStatus(BaseModel):
    """Five injection method status."""
    mcp: bool = False
    hook: bool = False
    config: bool = False
    loop_skill: bool = False
    skill: bool = False

    def all_injected(self) -> bool:
        return all([self.mcp, self.hook, self.config, self.loop_skill, self.skill])

    def missing(self) -> list[str]:
        items = []
        if not self.mcp: items.append("mcp")
        if not self.hook: items.append("hook")
        if not self.config: items.append("config")
        if not self.loop_skill: items.append("loop_skill")
        if not self.skill: items.append("skill")
        return items

    def injected_count(self) -> int:
        return sum([self.mcp, self.hook, self.config, self.loop_skill, self.skill])


class AgentProfileModel(BaseModel):
    """Agent instance — Pydantic v2 model."""
    agent_id: str = ""                          # "hermes:dev-agent-01"
    framework: str = ""                         # "hermes" | "wukong" | "claude_code"
    agent_type: str = "framework"               # "framework" | "ide" | "bridge"
    display_name: str = ""
    config_path: str = ""
    capabilities: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    injection_status: InjectionStatus = Field(default_factory=InjectionStatus)
    status: str = "offline"
    node_id: str = ""
    user_id: str = ""
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AgentMeshEntry(BaseModel):
    """AgentMesh registration entry."""
    agent_id: str = ""
    node_id: str = ""
    user_id: str = ""
    framework: str = ""
    capabilities: list[str] = Field(default_factory=list)
    status: str = "offline"
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_task_id: str = ""

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SkillRepoModel(BaseModel):
    """GitHub skill repository."""
    repo_name: str = ""
    user_id: str = ""
    pinyin_prefix: str = ""
    git_url: str = ""
    clone_path: str = ""
    skills_count: int = 0
    skills: list[str] = Field(default_factory=list)

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class KnowledgeRepoModel(BaseModel):
    """GitHub knowledge repository."""
    repo_name: str = ""
    user_id: str = ""
    pinyin_prefix: str = ""
    git_url: str = ""
    clone_path: str = ""
    entries_count: int = 0
    categories: list[str] = Field(default_factory=list)

    def to_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
