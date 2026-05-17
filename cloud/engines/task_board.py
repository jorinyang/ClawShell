"""GlobalTaskBoard — Cross-Edge shared task management board.

Features:
- Full CRUD with state machine: pending → in_progress → completed/failed/cancelled
- Transition guards: invalid state changes raise ValueError
- Priority queue: CRITICAL > HIGH > MEDIUM > LOW
- Task claiming by edge nodes
- Capability-based task assignment
- Thread-safe via threading.RLock()
- Persistent storage (data/tasks.json)
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, List, Optional, Any
from enum import Enum

try:
    from shared.hooks.registry import trigger_hook
    from shared.hooks.manager import HookEvent
except ImportError:
    trigger_hook = None
    HookEvent = None


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"  # v1.8.1: Saga compensation in progress


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def _normalize_priority(p):
    """Normalize priority value — handles legacy int values."""
    if isinstance(p, (int, float)):
        return "critical" if p >= 90 else "high" if p >= 70 else "medium" if p >= 40 else "low"
    try:
        TaskPriority(p)
        return p
    except ValueError:
        return "low"


# State transition map
VALID_TRANSITIONS = {
    TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
    TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.COMPENSATING],
    TaskStatus.COMPLETED: [],  # Terminal
    TaskStatus.FAILED: [TaskStatus.PENDING],  # Can retry
    TaskStatus.CANCELLED: [],  # Terminal
    TaskStatus.COMPENSATING: [TaskStatus.COMPLETED, TaskStatus.FAILED],  # v1.8.1
}

PRIORITY_ORDER = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
}


class GlobalTaskBoard:
    """Cross-edge shared task management board."""

    def __init__(self, data_dir: str = "data"):
        self._data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._tasks_file = os.path.join(data_dir, "tasks.json")

        self._lock = threading.RLock()
        self._tasks: Dict[str, dict] = {}

        self._load()

    # ── CRUD ──────────────────────────────────────

    def create_task(self, task: dict) -> str:
        """Create a new task. Returns task_id."""
        task_id = task.get("task_id", "")
        if not task_id:
            import uuid
            task_id = str(uuid.uuid4())
            task["task_id"] = task_id

        with self._lock:
            task.setdefault("status", TaskStatus.PENDING.value)
            task.setdefault("priority", TaskPriority.MEDIUM.value)
            task.setdefault("created_at", time.time())
            task.setdefault("updated_at", time.time())
            task.setdefault("assigned_to", None)
            task.setdefault("claimed_by", None)
            task.setdefault("required_capabilities", [])
            task.setdefault("tags", [])

            self._tasks[task_id] = task
            self._save()

        # Pre-task hook
        if trigger_hook is not None:
            try:
                trigger_hook(
                    HookEvent.PRE_TASK,
                    {"task_id": task_id, "task": dict(task)},
                    source="taskboard",
                )
            except Exception:
                pass

        return task_id

    def get_task(self, task_id: str) -> Optional[dict]:
        """Get a task by ID."""
        with self._lock:
            return dict(self._tasks.get(task_id, {})) or None

    def list_tasks(self, status: Optional[str] = None,
                   priority: Optional[str] = None,
                   claimed_by: Optional[str] = None,
                   limit: int = 100, offset: int = 0) -> List[dict]:
        """List tasks with optional filters."""
        with self._lock:
            tasks = list(self._tasks.values())

            if status:
                tasks = [t for t in tasks if t.get("status") == status]
            if priority:
                tasks = [t for t in tasks if t.get("priority") == priority]
            if claimed_by:
                tasks = [t for t in tasks if t.get("claimed_by") == claimed_by]

            # Sort by priority DESC
            tasks.sort(key=lambda t: PRIORITY_ORDER.get(
                TaskPriority(_normalize_priority(t.get("priority", "low"))), 99
            ))
            return [dict(t) for t in tasks[offset:offset + limit]]

    def update_task(self, task_id: str, updates: dict) -> Optional[dict]:
        """Update task fields."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            # Validate status transition
            new_status = updates.get("status")
            if new_status:
                current = TaskStatus(task.get("status", "pending"))
                try:
                    target = TaskStatus(new_status)
                except ValueError:
                    raise ValueError(f"Invalid status: {new_status}")

                if target not in VALID_TRANSITIONS.get(current, []):
                    raise ValueError(
                        f"Invalid transition: {current.value} → {target.value}"
                    )

            task.update(updates)
            task["updated_at"] = time.time()
            self._save()
            return dict(task)

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._save()
                return True
            return False

    # ── Task Lifecycle ────────────────────────────

    def claim(self, task_id: str, edge_id: str) -> Optional[dict]:
        """Claim a task for execution."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            current = TaskStatus(task.get("status", "pending"))
            if current != TaskStatus.PENDING:
                raise ValueError(f"Task {task_id} is not pending (status: {current.value})")

            if task.get("claimed_by") and task["claimed_by"] != edge_id:
                raise ValueError(f"Task {task_id} already claimed by {task['claimed_by']}")

            task["status"] = TaskStatus.IN_PROGRESS.value
            task["claimed_by"] = edge_id
            task["updated_at"] = time.time()
            self._save()
            return dict(task)

    def complete(self, task_id: str, result: Optional[dict] = None) -> Optional[dict]:
        """Mark a task as completed."""
        return self._transition(task_id, TaskStatus.COMPLETED, result)

    def fail(self, task_id: str, error: Optional[str] = None) -> Optional[dict]:
        """Mark a task as failed."""
        result = {"error": error} if error else None
        return self._transition(task_id, TaskStatus.FAILED, result)

    def cancel(self, task_id: str, reason: Optional[str] = None) -> Optional[dict]:
        """Cancel a task."""
        result = {"reason": reason} if reason else None
        return self._transition(task_id, TaskStatus.CANCELLED, result)

    def _transition(self, task_id: str, target: TaskStatus,
                    result: Optional[dict] = None) -> Optional[dict]:
        """Internal state transition."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            current = TaskStatus(task.get("status", "pending"))
            if target not in VALID_TRANSITIONS.get(current, []):
                raise ValueError(
                    f"Invalid transition: {current.value} → {target.value}"
                )

            task["status"] = target.value
            task["updated_at"] = time.time()
            if target in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task["completed_at"] = time.time()
            if result:
                task.setdefault("results", []).append({
                    "timestamp": time.time(),
                    "status": target.value,
                    "data": result,
                })
            self._save()
            task_snapshot = dict(task)

        # Post-task hook (for completed/failed tasks)
        if trigger_hook is not None and target in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            try:
                trigger_hook(
                    HookEvent.POST_TASK,
                    {"task_id": task_id, "task": task_snapshot, "target_status": target.value},
                    source="taskboard",
                )
            except Exception:
                pass

        return task_snapshot

    # ── Smart Dispatch ────────────────────────────

    def get_next_pending(self, capability: Optional[List[str]] = None,
                         exclude_claimed: bool = True) -> Optional[dict]:
        """Get next highest-priority pending task, optionally matching capabilities."""
        with self._lock:
            candidates = [
                t for t in self._tasks.values()
                if t.get("status") == "pending"
            ]
            if exclude_claimed:
                candidates = [t for t in candidates if not t.get("claimed_by")]
            if capability:
                required = set(capability)
                candidates = [
                    t for t in candidates
                    if not t.get("required_capabilities")
                    or required.issuperset(set(t.get("required_capabilities", [])))
                ]

            if not candidates:
                return None

            candidates.sort(key=lambda t: PRIORITY_ORDER.get(
                TaskPriority(t.get("priority", "low")), 99
            ))
            return dict(candidates[0])

    def assign_to_edge(self, task_id: str, edge_id: str) -> Optional[dict]:
        """Assign a task to a specific edge."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task["assigned_to"] = edge_id
            task["updated_at"] = time.time()
            self._save()
            return dict(task)

    # ── Stats ─────────────────────────────────────

    def get_stats(self) -> dict:
        """Get task board statistics."""
        with self._lock:
            by_status = {}
            by_priority = {}
            for t in self._tasks.values():
                s = t.get("status", "unknown")
                p = t.get("priority", "unknown")
                by_status[s] = by_status.get(s, 0) + 1
                by_priority[p] = by_priority.get(p, 0) + 1

            return {
                "total": len(self._tasks),
                "by_status": by_status,
                "by_priority": by_priority,
            }

    # ── Persistence ───────────────────────────────

    def _save(self):
        try:
            with open(self._tasks_file, "w", encoding="utf-8") as f:
                json.dump(list(self._tasks.values()), f, ensure_ascii=False, default=str)
        except OSError:
            pass

    def _load(self):
        if not os.path.exists(self._tasks_file):
            return
        try:
            with open(self._tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            for t in tasks:
                tid = t.get("task_id")
                if tid:
                    self._tasks[tid] = t
        except (json.JSONDecodeError, OSError):
            pass
