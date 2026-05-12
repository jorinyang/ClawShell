"""Event Metrics — statistical summaries for event stream monitoring.

Collects aggregate statistics: event rates, latency distributions,
error rates, topic frequencies.

Design: stdlib-only, in-memory.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EventMetric:
    """Aggregate metric for a specific event topic."""
    topic: str = ""
    total: int = 0
    success: int = 0
    error: int = 0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    last_seen: float = 0.0
    error_rate: float = 0.0
    # Moving average (events/second)
    rate_1m: float = 0.0
    rate_5m: float = 0.0
    rate_15m: float = 0.0


class EventMetrics:
    """Collector for per-topic event metrics.

    Tracks counts, latency, and error rates per topic.
    Uses simple moving average for rate calculation.

    Thread-safe via RLock.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._metrics: Dict[str, EventMetric] = {}
        self._rate_buckets: List[List[tuple]] = []  # [(timestamp, topic), ...]

    def record(self, topic: str, latency_ms: float = 0.0,
               is_error: bool = False) -> None:
        """Record an event occurrence with optional latency."""
        with self._lock:
            if topic not in self._metrics:
                self._metrics[topic] = EventMetric(topic=topic)

            m = self._metrics[topic]
            m.total += 1
            if is_error:
                m.error += 1
            else:
                m.success += 1

            if not is_error and latency_ms > 0:
                if latency_ms < m.min_latency_ms:
                    m.min_latency_ms = latency_ms
                if latency_ms > m.max_latency_ms:
                    m.max_latency_ms = latency_ms
                # Welford's online algorithm for running average
                m.avg_latency_ms += (latency_ms - m.avg_latency_ms) / m.success

            m.error_rate = m.error / max(m.total, 1)
            m.last_seen = time.time()

            # Record for rate calculation
            self._rate_buckets.append((time.time(), topic))
            self._trim_rate_buckets()

    def get_metric(self, topic: str) -> Optional[EventMetric]:
        """Get metrics for a specific topic."""
        with self._lock:
            m = self._metrics.get(topic)
            if m:
                # Update rates
                self._update_rates(m)
            return m

    def get_all(self) -> Dict[str, EventMetric]:
        """Get all topic metrics."""
        with self._lock:
            for m in self._metrics.values():
                self._update_rates(m)
            return dict(self._metrics)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics across all topics."""
        with self._lock:
            total_events = sum(m.total for m in self._metrics.values())
            total_errors = sum(m.error for m in self._metrics.values())
            top_topics = sorted(self._metrics.values(),
                               key=lambda m: m.total, reverse=True)[:10]
            return {
                "total_events": total_events,
                "total_errors": total_errors,
                "error_rate": total_errors / max(total_events, 1),
                "unique_topics": len(self._metrics),
                "top_topics": [
                    {"topic": m.topic, "total": m.total, "error_rate": m.error_rate}
                    for m in top_topics
                ],
            }

    def _update_rates(self, m: EventMetric) -> None:
        """Update moving average rates for a metric."""
        now = time.time()
        for window, attr in [(60, "rate_1m"), (300, "rate_5m"), (900, "rate_15m")]:
            cutoff = now - window
            count = sum(1 for ts, t in self._rate_buckets[-1000:]
                      if ts >= cutoff and t == m.topic)
            setattr(m, attr, count / (window / 60))  # events per minute

    def _trim_rate_buckets(self) -> None:
        """Keep only recent 15 minutes of rate data."""
        cutoff = time.time() - 900
        while self._rate_buckets and self._rate_buckets[0][0] < cutoff:
            self._rate_buckets.pop(0)

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()
            self._rate_buckets.clear()
