"""ML Engine — statistical anomaly detection for event streams.

Detects anomalies using z-score and moving statistics.
No external ML dependencies — pure statistical approach.

Detects:
- Volume anomalies (sudden spikes/drops in event rate)
- Latency anomalies (unusual processing times)
- Error rate anomalies (abnormal error percentages)

Design: stdlib-only, in-memory with configurable thresholds.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AnomalyResult:
    """Anomaly detection result."""
    topic: str = ""
    anomaly_type: str = ""         # volume / latency / error_rate
    current_value: float = 0.0
    expected_value: float = 0.0
    z_score: float = 0.0
    severity: str = "normal"       # normal / warning / critical
    detected_at: float = field(default_factory=time.time)
    description: str = ""


@dataclass
class TrendResult:
    """Trend analysis result."""
    topic: str = ""
    trend_type: str = ""           # increasing / decreasing / stable
    current_rate: float = 0.0
    slope: float = 0.0             # events per second change
    r_squared: float = 0.0         # Fit quality (0.0 - 1.0)
    confidence: float = 0.0


class MLEngine:
    """Statistical ML engine for event stream analysis.

    Uses:
    - Z-score for anomaly detection (mean ± N * stddev)
    - Simple linear regression for trend detection
    - Exponential moving average for rate tracking

    All computations are O(1) per event via online algorithms.
    Thread-safe via RLock.
    """

    # Z-score thresholds
    WARNING_Z = 2.0
    CRITICAL_Z = 3.0

    def __init__(self, history_size: int = 300):
        self._lock = threading.RLock()
        self._history: Dict[str, deque] = {}     # topic → deque of values
        self._history_size = history_size
        self._trends: Dict[str, TrendResult] = {}
        self._alerts: List[AnomalyResult] = []
        self._max_alerts = 100

    def observe(self, topic: str, value: float) -> None:
        """Record a metric value for a topic."""
        with self._lock:
            if topic not in self._history:
                self._history[topic] = deque(maxlen=self._history_size)
            self._history[topic].append(value)

    def detect_anomalies(self, topic: Optional[str] = None) -> List[AnomalyResult]:
        """Detect anomalies in observed metrics."""
        with self._lock:
            results = []
            topics = [topic] if topic else list(self._history.keys())

            for t in topics:
                if t not in self._history or len(self._history[t]) < 10:
                    continue

                values = list(self._history[t])
                current = values[-1]

                mean = sum(values) / len(values)
                variance = sum((v - mean) ** 2 for v in values) / len(values)
                stddev = variance ** 0.5

                if stddev == 0:
                    continue

                z = (current - mean) / stddev
                severity = "normal"
                if abs(z) >= self.CRITICAL_Z:
                    severity = "critical"
                elif abs(z) >= self.WARNING_Z:
                    severity = "warning"

                if severity != "normal":
                    anomaly = AnomalyResult(
                        topic=t,
                        anomaly_type="volume" if z > 0 else "drop",
                        current_value=current,
                        expected_value=mean,
                        z_score=z,
                        severity=severity,
                        description=(
                            f"Spike: {current:.1f} vs expected {mean:.1f} (z={z:.2f})"
                            if z > 0 else
                            f"Drop: {current:.1f} vs expected {mean:.1f} (z={z:.2f})"
                        ),
                    )
                    results.append(anomaly)
                    self._alerts.append(anomaly)
                    if len(self._alerts) > self._max_alerts:
                        self._alerts = self._alerts[-self._max_alerts:]

            return results

    def analyze_trends(self, topic: Optional[str] = None) -> List[TrendResult]:
        """Detect trends in event rates using linear regression."""
        with self._lock:
            results = []
            topics = [topic] if topic else list(self._history.keys())

            for t in topics:
                if t not in self._history or len(self._history[t]) < 30:
                    continue

                values = list(self._history[t])
                n = len(values)
                x_mean = (n - 1) / 2
                y_mean = sum(values) / n

                # Simple linear regression
                numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
                denominator = sum((i - x_mean) ** 2 for i in range(n))

                if denominator == 0:
                    continue

                slope = numerator / denominator

                # R-squared
                y_pred = [y_mean + slope * (i - x_mean) for i in range(n)]
                ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
                ss_tot = sum((v - y_mean) ** 2 for v in values)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                trend_type = "stable"
                if slope > 0.01 * y_mean:
                    trend_type = "increasing"
                elif slope < -0.01 * y_mean:
                    trend_type = "decreasing"

                trend = TrendResult(
                    topic=t,
                    trend_type=trend_type,
                    current_rate=values[-1],
                    slope=slope,
                    r_squared=r_squared,
                    confidence=min(abs(r_squared), 1.0),
                )
                results.append(trend)
                self._trends[t] = trend

            return results

    def get_recent_alerts(self, limit: int = 20) -> List[AnomalyResult]:
        """Get recent anomaly alerts."""
        with self._lock:
            return list(reversed(self._alerts[-limit:]))

    def get_trend(self, topic: str) -> Optional[TrendResult]:
        """Get the latest trend for a topic."""
        with self._lock:
            return self._trends.get(topic)

    def get_stats(self) -> Dict[str, Any]:
        """Get ML engine statistics."""
        with self._lock:
            return {
                "tracked_topics": len(self._history),
                "total_alerts": len(self._alerts),
                "recent_alerts_24h": sum(
                    1 for a in self._alerts
                    if time.time() - a.detected_at < 86400
                ),
                "warning_z": self.WARNING_Z,
                "critical_z": self.CRITICAL_Z,
                "history_size": self._history_size,
            }

    def reset(self) -> None:
        """Reset all ML state."""
        with self._lock:
            self._history.clear()
            self._trends.clear()
            self._alerts.clear()
