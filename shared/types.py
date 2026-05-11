"""Core data types shared between Cloud Hub and Edge Brain."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum
import time
import uuid
import hashlib
import json


# ── Enums ────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class EventCategory(str, Enum):
    TASK = "task"
    NODE = "node"
    SKILL = "skill"
    INSIGHT = "insight"
    BROADCAST = "broadcast"
    HEALTH = "health"
    SYSTEM = "system"
    ERROR = "error"


# ── Data Classes ─────────────────────────────────────

@dataclass
class ClawShellEvent:
    """Universal event type for EventBus communication."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    category: EventCategory = EventCategory.SYSTEM
    source: str = ""          # edge_id or "cloud"
    target: str = "*"          # edge_id or "*" for broadcast
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0          # 0-100, higher = more urgent
    ttl: int = 2592000  # 30 days in seconds

    def __post_init__(self):
        if isinstance(self.category, str):
            try:
                self.category = EventCategory(self.category)
            except ValueError:
                self.category = EventCategory.SYSTEM

    def content_hash(self) -> str:
        """SHA256 hash of event content for deduplication."""
        content = json.dumps({
            "event_type": self.event_type,
            "source": self.source,
            "payload": self.payload
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, EventCategory) else self.category
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ClawShellEvent":
        d = d.copy()
        if isinstance(d.get("category"), str):
            try:
                d["category"] = EventCategory(d["category"])
            except ValueError:
                d["category"] = EventCategory.SYSTEM
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Task:
    """Task definition for GlobalTaskBoard."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    task_type: str = "general"
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    required_capabilities: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None    # edge_id
    claimed_by: Optional[str] = None     # edge_id
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    deadline: Optional[float] = None
    parent_task_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = TaskStatus(self.status)
            except ValueError:
                self.status = TaskStatus.PENDING
        if isinstance(self.priority, str):
            try:
                self.priority = TaskPriority(self.priority)
            except ValueError:
                self.priority = TaskPriority.MEDIUM

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, TaskStatus) else self.status
        d["priority"] = self.priority.value if isinstance(self.priority, TaskPriority) else self.priority
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Task":
        d = d.copy()
        for key, enum_cls in [("status", TaskStatus), ("priority", TaskPriority)]:
            if isinstance(d.get(key), str):
                try:
                    d[key] = enum_cls(d[key])
                except ValueError:
                    d[key] = list(enum_cls)[0]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Skill:
    """Skill definition for SkillMarket."""
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    category: str = "general"
    author: str = ""
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    content: str = ""              # Skill body (markdown or code)
    published_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    download_count: int = 0
    rating: float = 0.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Skill":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class EdgeNode:
    """Edge node registration info."""
    node_id: str = ""
    node_name: str = ""
    hostname: str = ""
    os_type: str = ""              # linux / macos / windows / wsl
    os_version: str = ""
    python_version: str = ""
    cpu_count: int = 0
    memory_total_mb: float = 0.0
    disk_free_gb: float = 0.0
    frameworks: List[str] = field(default_factory=list)   # Detected OpenClaw-class frameworks
    ide_tools: List[str] = field(default_factory=list)    # Detected Agent CLI IDEs
    capabilities: List[str] = field(default_factory=list)  # Declared capabilities
    status: NodeStatus = NodeStatus.UNKNOWN
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    ip_address: str = ""
    labels: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = NodeStatus(self.status)
            except ValueError:
                self.status = NodeStatus.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, NodeStatus) else self.status
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EdgeNode":
        d = d.copy()
        if isinstance(d.get("status"), str):
            try:
                d["status"] = NodeStatus(d["status"])
            except ValueError:
                d["status"] = NodeStatus.UNKNOWN
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Insight:
    """Cloud-generated insight for Edge pre-action reference."""
    insight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    category: str = "general"       # best_practice / warning / optimization / pattern
    source_edges: List[str] = field(default_factory=list)
    confidence: float = 0.0         # 0.0 - 1.0
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    action_suggestion: str = ""     # Suggested action for Edge

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Insight":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Broadcast:
    """Cloud broadcast message to all/specific edges."""
    broadcast_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    broadcast_type: str = "announcement"  # announcement / skill_update / config_change / alert
    target_edges: List[str] = field(default_factory=lambda: ["*"])
    created_at: float = field(default_factory=time.time)
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Broadcast":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
