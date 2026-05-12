"""Edge Event Tracer — local event causal chain tracking."""

import threading, time, uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class EventSpan:
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    event_type: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "started"

@dataclass
class TraceResult:
    trace_id: str = ""
    spans: List[EventSpan] = field(default_factory=list)
    total_spans: int = 0
    error_spans: int = 0

class EdgeEventTracer:
    def __init__(self):
        self._lock = threading.RLock()
        self._spans: Dict[str, EventSpan] = {}
        self._traces: Dict[str, List[str]] = {}

    def start_span(self, event_type: str, trace_id: Optional[str] = None) -> EventSpan:
        with self._lock:
            tid = trace_id or str(uuid.uuid4())
            span = EventSpan(trace_id=tid, event_type=event_type)
            self._spans[span.span_id] = span
            self._traces.setdefault(tid, []).append(span.span_id)
            return span

    def complete_span(self, span_id: str, status: str = "success") -> Optional[EventSpan]:
        with self._lock:
            if span_id in self._spans:
                self._spans[span_id].completed_at = time.time()
                self._spans[span_id].status = status
                return self._spans[span_id]
            return None

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"total_spans": len(self._spans), "total_traces": len(self._traces)}
