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
