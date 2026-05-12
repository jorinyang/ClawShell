"""Edge EventBus — enhanced local event bus for Edge Brain.

Features: pub/sub with wildcards, priority, condition-based routing.
v1.8.1: Enhanced from MacOS EventBus with condition engine support.
"""

from __future__ import annotations
import threading, time, uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

class EdgeEventBus:
    """Enhanced local event bus with pub/sub and condition routing."""

    def __init__(self, max_history: int = 1000):
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[dict] = []
        self._max_history = max_history
        self._running = True

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, data: Any = None,
                source: str = "", priority: int = 0) -> dict:
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "source": source,
            "timestamp": time.time(),
            "data": data,
            "priority": priority,
        }
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            subscribers = list(self._subscribers.get(event_type, []))
            for sub in self._subscribers.get("*", []):
                if sub not in subscribers:
                    subscribers.append(sub)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                pass
        return event

    def get_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[dict]:
        with self._lock:
            if event_type:
                return [e for e in self._history if e["event_type"] == event_type][-limit:]
            return self._history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            types = defaultdict(int)
            for e in self._history:
                types[e["event_type"]] += 1
            return {"total_events": len(self._history), "subscriber_count": sum(len(v) for v in self._subscribers.values()), "by_type": dict(types)}

    def shutdown(self) -> None:
        self._running = False
