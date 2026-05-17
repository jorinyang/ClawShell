"""Edge EventBus — enhanced local event bus for Edge Brain.

Features: pub/sub with wildcards, priority, condition-based routing.
v1.8.1: Enhanced from MacOS EventBus with condition engine support.
v1.10.0: Wired ConditionEngine, DeadLetterQueue, EventTracer into publish flow.
"""

from __future__ import annotations
import threading, time, uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

try:
    from shared.hooks.registry import trigger_hook
    from shared.hooks.manager import HookEvent
except ImportError:
    trigger_hook = None
    HookEvent = None

try:
    from edge.eventbus.condition_engine import ConditionEngine
    from edge.eventbus.dead_letter import EdgeDeadLetterQueue, DLQReason
    from edge.eventbus.tracer import EdgeEventTracer
except ImportError:
    ConditionEngine = None
    EdgeDeadLetterQueue = None
    DLQReason = None
    EdgeEventTracer = None

class EdgeEventBus:
    """Enhanced local event bus with pub/sub, condition routing, DLQ, and tracing."""

    def __init__(self, max_history: int = 1000):
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[dict] = []
        self._max_history = max_history
        self._running = True

        # Sub-module instances (wired in v1.10.0)
        self._condition_engine = ConditionEngine() if ConditionEngine else None
        self._dlq = EdgeDeadLetterQueue() if EdgeDeadLetterQueue else None
        self._tracer = EdgeEventTracer() if EdgeEventTracer else None

    @property
    def condition_engine(self):
        """Access the ConditionEngine for adding conditions."""
        return self._condition_engine

    @property
    def dlq(self):
        """Access the DeadLetterQueue."""
        return self._dlq

    @property
    def tracer(self):
        """Access the EventTracer."""
        return self._tracer

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

        # ── Condition Engine: check if event should be blocked ──
        if self._condition_engine is not None:
            allowed, blocked_by = self._condition_engine.evaluate(event)
            if not allowed:
                # Log to DLQ as condition-blocked
                if self._dlq is not None:
                    self._dlq.enqueue(
                        event_type=event_type,
                        data=data,
                        reason=DLQReason.HANDLER_ERROR,
                        error_message=f"Blocked by conditions: {blocked_by}",
                    )
                event["_blocked"] = True
                event["_blocked_by"] = blocked_by
                return event

        # ── Tracer: start span ──
        span = None
        if self._tracer is not None:
            span = self._tracer.start_span(event_type)

        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            subscribers = list(self._subscribers.get(event_type, []))
            for sub in self._subscribers.get("*", []):
                if sub not in subscribers:
                    subscribers.append(sub)

        # ── Deliver to subscribers ──
        delivery_errors = []
        for callback in subscribers:
            try:
                callback(event)
            except Exception as exc:
                delivery_errors.append((callback, str(exc)))
                # Log subscriber failure to DLQ
                if self._dlq is not None:
                    self._dlq.enqueue(
                        event_type=event_type,
                        data=data,
                        reason=DLQReason.HANDLER_ERROR,
                        error_message=f"Subscriber {callback!r} failed: {exc}",
                    )

        # ── Tracer: end span ──
        if span is not None and self._tracer is not None:
            status = "error" if delivery_errors else "success"
            self._tracer.complete_span(span.span_id, status=status)

        # Bridge to hook system
        if trigger_hook is not None:
            try:
                trigger_hook(
                    HookEvent.POST_EVENT,
                    {"event_type": event_type, "event": event},
                    source=source or "eventbus",
                )
            except Exception:
                pass

        return event

    # ── Sub-module accessors ────────────────────────────

    def get_dlq_items(self, limit: int = 50) -> List:
        """Get pending dead letter queue items."""
        if self._dlq is not None:
            return self._dlq.get_pending(limit=limit)
        return []

    def get_trace(self, trace_id: str):
        """Get trace result for a given trace_id."""
        if self._tracer is not None:
            return self._tracer.get_trace(trace_id)
        return None

    def get_condition_stats(self) -> Dict[str, Any]:
        """Get condition engine statistics."""
        if self._condition_engine is not None:
            return self._condition_engine.get_stats()
        return {}

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
            base = {
                "total_events": len(self._history),
                "subscriber_count": sum(len(v) for v in self._subscribers.values()),
                "by_type": dict(types),
            }
            if self._dlq is not None:
                base["dlq"] = self._dlq.get_stats()
            if self._tracer is not None:
                base["tracer"] = self._tracer.get_stats()
            if self._condition_engine is not None:
                base["conditions"] = self._condition_engine.get_stats()
            return base

    def shutdown(self) -> None:
        self._running = False
