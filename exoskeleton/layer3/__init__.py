"""Exoskeleton Layer 3 — Self-Organization (自组织).

Core: Local EventBus (pub/sub/priority/dead-letter), Task organizer (DAG),
Task market (capability matching), Context manager.
"""

import os
import json
import time
import fnmatch
import threading
import hashlib
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict


class LocalEventBus:
    """Local event bus with pub/sub, priority queue, and dead letter queue."""

    def __init__(self, data_dir: str = "~/.clawshell-edge/eventbus"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_history: List[dict] = []
        self._dead_letter: List[dict] = []

    def publish(self, event_type: str, payload: dict, priority: int = 0,
                ttl: int = 3600) -> str:
        """Publish an event. Returns event_id."""
        import uuid
        eid = str(uuid.uuid4())
        event = {
            "event_id": eid,
            "event_type": event_type,
            "payload": payload,
            "priority": priority,
            "ttl": ttl,
            "timestamp": time.time(),
        }

        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > 1000:
                self._event_history = self._event_history[-500:]

        # Notify subscribers
        for pattern, handlers in list(self._subscribers.items()):
            if fnmatch.fnmatch(event_type, pattern):
                for handler in handlers:
                    try:
                        handler(event)
                    except Exception:
                        self._dead_letter.append({"event": event, "error": "handler_failed",
                                                  "timestamp": time.time()})

        return eid

    def subscribe(self, event_pattern: str, handler: Callable):
        """Subscribe to events matching a pattern."""
        with self._lock:
            self._subscribers[event_pattern].append(handler)

    def unsubscribe(self, event_pattern: str, handler: Callable):
        with self._lock:
            if handler in self._subscribers.get(event_pattern, []):
                self._subscribers[event_pattern].remove(handler)

    def query(self, event_type: str = "*", limit: int = 100) -> List[dict]:
        with self._lock:
            events = [
                e for e in self._event_history
                if fnmatch.fnmatch(e["event_type"], event_type)
            ]
            return events[-limit:]

    def get_dead_letters(self) -> List[dict]:
        return self._dead_letter[-50:]

    def get_stats(self) -> dict:
        with self._lock:
            by_type = defaultdict(int)
            for e in self._event_history:
                by_type[e["event_type"]] += 1
            return {
                "total_events": len(self._event_history),
                "subscribers": len(self._subscribers),
                "dead_letters": len(self._dead_letter),
                "event_types": dict(by_type),
            }


class TaskOrganizer:
    """Task organizer with DAG dependency management."""

    def __init__(self):
        self._lock = threading.RLock()
        self._tasks: Dict[str, dict] = {}
        self._dependencies: Dict[str, List[str]] = defaultdict(list)
        self._dependents: Dict[str, List[str]] = defaultdict(list)

    def add_task(self, task_id: str, task: dict,
                 depends_on: Optional[List[str]] = None,
                 required_by: Optional[List[str]] = None):
        with self._lock:
            self._tasks[task_id] = task
            if depends_on:
                self._dependencies[task_id] = list(depends_on)
                # Auto-populate dependents
                for dep_id in depends_on:
                    if task_id not in self._dependents.get(dep_id, []):
                        self._dependents[dep_id].append(task_id)
            if required_by:
                for req_id in required_by:
                    if req_id not in self._dependents.get(task_id, []):
                        self._dependents[task_id].append(req_id)

    def can_execute(self, task_id: str) -> bool:
        """Check if all dependencies are satisfied."""
        with self._lock:
            deps = self._dependencies.get(task_id, [])
            return all(
                self._tasks.get(d, {}).get("status") == "completed"
                for d in deps
            )

    def get_executable_tasks(self) -> List[str]:
        """Get all tasks ready for execution (deps satisfied)."""
        with self._lock:
            return [
                tid for tid in self._tasks
                if self._tasks[tid].get("status", "pending") == "pending"
                and self.can_execute(tid)
            ]

    def get_topology(self) -> List[str]:
        """Get topological task order (Kahn's algorithm)."""
        with self._lock:
            in_degree = {tid: len(self._dependencies.get(tid, []))
                        for tid in self._tasks}
            queue = [tid for tid, deg in in_degree.items() if deg == 0]
            order = []

            while queue:
                tid = queue.pop(0)
                order.append(tid)
                for dep_tid in self._dependents.get(tid, []):
                    if dep_tid in in_degree:
                        in_degree[dep_tid] -= 1
                        if in_degree[dep_tid] == 0:
                            queue.append(dep_tid)

            return order

    def get_task(self, task_id: str) -> Optional[dict]:
        return self._tasks.get(task_id)


class ContextManager:
    """Global state manager for cross-module context sharing."""

    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = {}
        self._version = 0
        self._load()

    def set(self, key: str, value: Any):
        with self._lock:
            self._state[key] = value
            self._version += 1
            self._save()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._state.get(key, default)

    def get_all(self) -> dict:
        with self._lock:
            return dict(self._state)

    def snapshot(self) -> dict:
        with self._lock:
            return {"state": dict(self._state), "version": self._version}

    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "context.json"), "w") as f:
                json.dump({"state": self._state, "version": self._version}, f, default=str)
        except Exception:
            pass

    def _load(self):
        path = os.path.join(self._data_dir, "context.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                self._state = data.get("state", {})
                self._version = data.get("version", 0)
            except Exception:
                pass
