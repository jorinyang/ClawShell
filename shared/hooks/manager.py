"""
ClawShell Hook Event System v2.1
Interceptors that run in priority order and can modify/block actions.
Unlike EventBus pub/sub, hooks form a pipeline where each can transform data.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HookEvent(Enum):
    """All hookable events in ClawShell."""
    PRE_TASK = "pre_task"
    POST_TASK = "post_task"
    TASK_PROGRESS = "task_progress"
    PRE_EVENT = "pre_event"
    POST_EVENT = "post_event"
    NODE_JOIN = "node_join"
    NODE_LEAVE = "node_leave"
    NODE_HEARTBEAT = "node_heartbeat"
    PRE_SYNC = "pre_sync"
    POST_SYNC = "post_sync"
    PATTERN_LEARNED = "pattern_learned"
    THREAT_DETECTED = "threat_detected"
    TRUST_CHANGED = "trust_changed"


class HookPriority(IntEnum):
    """Priority levels – highest value runs first."""
    CRITICAL = 1000
    HIGH = 100
    NORMAL = 50
    LOW = 10
    BACKGROUND = 1


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class HookContext:
    """Mutable context passed through the hook chain."""
    event: HookEvent
    data: Dict[str, Any]
    source: str
    timestamp: float = field(default_factory=time.time)
    cancelled: bool = False
    modified_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.modified_data:
            self.modified_data = dict(self.data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.modified_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.modified_data[key] = value

    def cancel(self) -> None:
        self.cancelled = True


@dataclass
class HookEntry:
    """Internal bookkeeping for a registered hook."""
    hook_id: str
    event: HookEvent
    handler: Callable[[HookContext], None]
    priority: HookPriority
    name: str


# ---------------------------------------------------------------------------
# HookManager
# ---------------------------------------------------------------------------

class HookManager:
    """Thread-safe hook registration and execution engine."""

    def __init__(self) -> None:
        self._hooks: Dict[str, HookEntry] = {}
        self._event_index: Dict[HookEvent, List[str]] = {e: [] for e in HookEvent}
        self._lock = threading.Lock()

    # -- registration -------------------------------------------------------

    def register(
        self,
        event: HookEvent,
        handler: Callable[[HookContext], None],
        priority: HookPriority = HookPriority.NORMAL,
        name: str = "",
    ) -> str:
        """Register a hook handler. Returns a unique hook_id."""
        hook_id = uuid.uuid4().hex
        entry = HookEntry(
            hook_id=hook_id,
            event=event,
            handler=handler,
            priority=priority,
            name=name or hook_id[:8],
        )
        with self._lock:
            self._hooks[hook_id] = entry
            # Insert maintaining descending priority order
            index = self._event_index[event]
            inserted = False
            for i, hid in enumerate(index):
                if priority > self._hooks[hid].priority:
                    index.insert(i, hook_id)
                    inserted = True
                    break
            if not inserted:
                index.append(hook_id)
        logger.debug("Hook %s registered for %s (priority=%s)", hook_id, event.name, priority.name)
        return hook_id

    def unregister(self, hook_id: str) -> bool:
        """Remove a hook by id. Returns True if found."""
        with self._lock:
            entry = self._hooks.pop(hook_id, None)
            if entry is None:
                return False
            self._event_index[entry.event].remove(hook_id)
        logger.debug("Hook %s unregistered", hook_id)
        return True

    # -- execution ----------------------------------------------------------

    def trigger(
        self,
        event: HookEvent,
        data: Dict[str, Any] | None = None,
        source: str = "system",
    ) -> HookContext:
        """Run all hooks for *event* in priority order.

        Each hook receives the same ``HookContext`` so it can:
        - modify data via ``ctx.set(key, value)``
        - cancel the chain via ``ctx.cancel()``
        Exceptions are logged but do **not** break the chain.
        """
        ctx = HookContext(event=event, data=data or {}, source=source)

        with self._lock:
            hook_ids = list(self._event_index.get(event, []))

        for hid in hook_ids:
            if ctx.cancelled:
                logger.debug("Hook chain cancelled before %s", hid)
                break
            entry = self._hooks.get(hid)
            if entry is None:
                continue
            try:
                entry.handler(ctx)
            except Exception:
                logger.exception("Hook %s (%s) raised – skipping", entry.name, hid)

        return ctx

    # -- introspection ------------------------------------------------------

    def list_hooks(self, event: Optional[HookEvent] = None) -> List[HookEntry]:
        """Return registered hooks, optionally filtered by event."""
        with self._lock:
            if event is not None:
                return [self._hooks[hid] for hid in self._event_index.get(event, []) if hid in self._hooks]
            return list(self._hooks.values())

    def clear(self) -> None:
        """Remove all hooks."""
        with self._lock:
            self._hooks.clear()
            for key in self._event_index:
                self._event_index[key] = []
