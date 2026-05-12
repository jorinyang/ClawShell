"""Event Tracer — causal chain tracking for event-driven debugging.

Tracks event spans through the system: event published → processed → 
resulting events. Builds causal chains for root cause analysis.

Design: stdlib-only, in-memory trace buffer with optional JSON export.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class EventSpan:
    """A traced span representing one event processing step.

    Spans form a tree via parent_span_id. A span starts when an event
    is received and completes when processing finishes.
    """
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""              # All spans in a causal chain share this
    parent_span_id: Optional[str] = None
    event_id: str = ""             # The event being processed
    event_topic: str = ""
    source: str = ""               # Component that processed this event
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "started"        # started / success / error / timeout
    result_events: List[str] = field(default_factory=list)  # IDs of events produced
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def duration_ms(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceResult:
    """Complete trace with all spans in a causal chain."""
    trace_id: str = ""
    root_event_id: str = ""
    spans: List[EventSpan] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    total_spans: int = 0
    error_spans: int = 0

    def duration_ms(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_event_id": self.root_event_id,
            "spans": [s.to_dict() for s in self.spans],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_spans": self.total_spans,
            "error_spans": self.error_spans,
            "duration_ms": self.duration_ms(),
        }


class EventTracer:
    """Lightweight event tracer for causal chain analysis.

    Maintains in-memory span buffer. Not persistent — designed for
    real-time debugging and recent-history analysis.

    Thread-safe via RLock.
    """

    MAX_SPANS = 10000
    MAX_TRACES = 1000

    def __init__(self):
        self._lock = threading.RLock()
        self._spans: Dict[str, EventSpan] = {}      # span_id → span
        self._traces: Dict[str, List[str]] = {}      # trace_id → [span_ids]
        self._active_traces: Dict[str, str] = {}     # event_id → trace_id mapping

    def start_span(self, event_id: str, event_topic: str,
                   source: str = "", parent_span_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> EventSpan:
        """Start tracing an event processing step.

        If parent_span_id is provided, inherits trace_id from parent.
        Otherwise, starts a new trace.
        """
        with self._lock:
            self._trim_if_needed()

            # Determine trace_id
            if parent_span_id and parent_span_id in self._spans:
                trace_id = self._spans[parent_span_id].trace_id
            elif event_id in self._active_traces:
                trace_id = self._active_traces[event_id]
            else:
                trace_id = str(uuid.uuid4())

            span = EventSpan(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                event_id=event_id,
                event_topic=event_topic,
                source=source,
                metadata=metadata or {},
            )

            self._spans[span.span_id] = span
            if trace_id not in self._traces:
                self._traces[trace_id] = []
            self._traces[trace_id].append(span.span_id)
            self._active_traces[event_id] = trace_id

            return span

    def complete_span(self, span_id: str, status: str = "success",
                      result_events: Optional[List[str]] = None,
                      error_message: Optional[str] = None) -> Optional[EventSpan]:
        """Complete a span with final status."""
        with self._lock:
            if span_id not in self._spans:
                return None
            span = self._spans[span_id]
            span.completed_at = time.time()
            span.status = status
            span.error_message = error_message
            if result_events:
                span.result_events = result_events
                # Link result events to this trace
                for ev_id in result_events:
                    self._active_traces[ev_id] = span.trace_id
            return span

    def get_trace(self, trace_id: str) -> Optional[TraceResult]:
        """Get complete trace with all spans."""
        with self._lock:
            if trace_id not in self._traces:
                return None
            span_ids = self._traces[trace_id]
            spans = [self._spans[sid] for sid in span_ids if sid in self._spans]
            if not spans:
                return None

            root_event_id = self._find_root_event(spans) or spans[0].event_id
            error_count = sum(1 for s in spans if s.status == "error")
            all_completed = all(s.completed_at for s in spans)
            latest = max((s.completed_at or s.started_at) for s in spans)

            return TraceResult(
                trace_id=trace_id,
                root_event_id=root_event_id,
                spans=sorted(spans, key=lambda s: s.started_at),
                started_at=min(s.started_at for s in spans),
                completed_at=latest if all_completed else None,
                total_spans=len(spans),
                error_spans=error_count,
            )

    def get_recent_traces(self, limit: int = 20) -> List[TraceResult]:
        """Get most recent traces."""
        with self._lock:
            trace_ids = list(self._traces.keys())[-limit:]
            results = []
            for tid in trace_ids:
                tr = self.get_trace(tid)
                if tr:
                    results.append(tr)
            return sorted(results, key=lambda t: t.started_at, reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get tracer statistics."""
        with self._lock:
            active = sum(1 for s in self._spans.values() if s.completed_at is None)
            error = sum(1 for s in self._spans.values() if s.status == "error")
            return {
                "total_spans": len(self._spans),
                "total_traces": len(self._traces),
                "active_spans": active,
                "error_spans": error,
            }

    def _find_root_event(self, spans: List[EventSpan]) -> Optional[str]:
        """Find the root event (span with no parent)."""
        for s in spans:
            if s.parent_span_id is None:
                return s.event_id
        return None

    def _trim_if_needed(self) -> None:
        """Trim old spans if buffer is full."""
        if len(self._spans) >= self.MAX_SPANS:
            # Remove oldest 20%
            to_remove = int(self.MAX_SPANS * 0.2)
            sorted_spans = sorted(self._spans.items(), key=lambda x: x[1].started_at)
            for sid, span in sorted_spans[:to_remove]:
                del self._spans[sid]
                if span.trace_id in self._traces:
                    self._traces[span.trace_id] = [
                        s for s in self._traces[span.trace_id] if s != sid
                    ]
                    if not self._traces[span.trace_id]:
                        del self._traces[span.trace_id]

    def shutdown(self) -> None:
        """Clear all traces (clean shutdown)."""
        with self._lock:
            self._spans.clear()
            self._traces.clear()
            self._active_traces.clear()
