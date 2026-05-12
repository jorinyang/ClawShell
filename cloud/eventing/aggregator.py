"""Event Aggregator — time-window event aggregation for pattern detection.

Aggregates events into time-windowed buckets, producing aggregated
summaries for downstream pattern mining and insight generation.

Design: stdlib-only, in-memory with optional flush to JSON.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AggregatedEvent:
    """Aggregated summary of events in a time window."""
    window_start: float = 0.0
    window_end: float = 0.0
    window_seconds: int = 60
    total_events: int = 0
    by_topic: Dict[str, int] = field(default_factory=dict)
    by_source: Dict[str, int] = field(default_factory=dict)
    topics: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    sample_payloads: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregationRule:
    """Rule for aggregating specific event types."""
    topic_pattern: str = "*"           # fnmatch wildcard
    window_seconds: int = 60
    max_samples: int = 100
    enabled: bool = True


class EventAggregator:
    """Time-window event aggregator.

    Maintains sliding time windows. Events are bucketed by their timestamp.
    When a window is complete (window_end < current_time), it's flushed
    to the aggregation output.

    Thread-safe via RLock.
    """

    def __init__(self, rule: Optional[AggregationRule] = None,
                 output_dir: Optional[str] = None):
        self._rule = rule or AggregationRule()
        self._output_dir = Path(output_dir) if output_dir else None
        self._lock = threading.RLock()
        self._current_window: Optional[AggregatedEvent] = None
        self._completed_windows: List[AggregatedEvent] = []
        self._max_completed = 1000  # Keep last 1000 completed windows

    def ingest(self, topic: str, source: str = "",
               timestamp: Optional[float] = None,
               payload: Optional[Dict[str, Any]] = None) -> None:
        """Ingest an event for aggregation."""
        if not self._rule.enabled:
            return

        with self._lock:
            ts = timestamp or time.time()
            window_start = (int(ts) // self._rule.window_seconds) * self._rule.window_seconds

            # Check if this event falls in current window
            if self._current_window and self._current_window.window_start == window_start:
                self._add_to_window(self._current_window, topic, source, payload)
            else:
                # Flush current window if exists
                if self._current_window:
                    self._flush_window(self._current_window)

                # Start new window
                self._current_window = AggregatedEvent(
                    window_start=window_start,
                    window_end=window_start + self._rule.window_seconds,
                    window_seconds=self._rule.window_seconds,
                )
                self._add_to_window(self._current_window, topic, source, payload)

    def _add_to_window(self, window: AggregatedEvent, topic: str,
                       source: str, payload: Optional[Dict[str, Any]]) -> None:
        """Add event data to a window."""
        window.total_events += 1
        window.by_topic[topic] = window.by_topic.get(topic, 0) + 1
        window.by_source[source] = window.by_source.get(source, 0) + 1

        if topic not in window.topics:
            window.topics.append(topic)
        if source and source not in window.sources:
            window.sources.append(source)

        if payload and len(window.sample_payloads) < self._rule.max_samples:
            window.sample_payloads.append(payload)

    def _flush_window(self, window: AggregatedEvent) -> None:
        """Move window to completed list."""
        self._completed_windows.append(window)
        if len(self._completed_windows) > self._max_completed:
            self._completed_windows = self._completed_windows[-self._max_completed:]

        # Write to output if configured
        if self._output_dir:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            fname = f"agg_{int(window.window_start)}.json"
            tmp = self._output_dir / (fname + ".tmp")
            tmp.write_text(json.dumps(window.__dict__, ensure_ascii=False, indent=2))
            tmp.rename(self._output_dir / fname)

    def get_current(self) -> Optional[AggregatedEvent]:
        """Get the current (in-progress) window."""
        with self._lock:
            return self._current_window

    def get_completed(self, limit: int = 10) -> List[AggregatedEvent]:
        """Get most recent completed windows."""
        with self._lock:
            return list(reversed(self._completed_windows[-limit:]))

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics."""
        with self._lock:
            current_count = self._current_window.total_events if self._current_window else 0
            return {
                "window_seconds": self._rule.window_seconds,
                "completed_windows": len(self._completed_windows),
                "current_window_events": current_count,
                "rule_enabled": self._rule.enabled,
            }

    def flush(self) -> Optional[AggregatedEvent]:
        """Force-flush current window."""
        with self._lock:
            if self._current_window:
                self._flush_window(self._current_window)
                window = self._current_window
                self._current_window = None
                return window
            return None
