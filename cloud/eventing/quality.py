"""Quality Evaluator — assess event processing quality metrics.

Evaluates event processing quality across dimensions:
- Completeness (are all events being processed?)
- Timeliness (are latency targets being met?)
- Correctness (are error rates within thresholds?)
- Consistency (are patterns stable over time?)

Design: stdlib-only, rule-based scoring.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QualityLevel(str, Enum):
    EXCELLENT = "excellent"    # All metrics in optimal range
    GOOD = "good"             # Minor deviations
    FAIR = "fair"             # Noticeable issues
    POOR = "poor"             # Significant problems
    CRITICAL = "critical"     # System at risk


@dataclass
class QualityScore:
    """Quality evaluation result."""
    level: QualityLevel = QualityLevel.FAIR
    overall_score: float = 0.0       # 0.0 - 1.0
    completeness: float = 0.0        # Event processing rate
    timeliness: float = 0.0          # Latency compliance
    correctness: float = 0.0         # Error rate
    consistency: float = 0.0         # Pattern stability
    evaluated_at: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "overall_score": round(self.overall_score, 3),
            "completeness": round(self.completeness, 3),
            "timeliness": round(self.timeliness, 3),
            "correctness": round(self.correctness, 3),
            "consistency": round(self.consistency, 3),
            "evaluated_at": self.evaluated_at,
            "details": self.details,
        }


class QualityEvaluator:
    """Rule-based quality evaluator for event processing.

    Scores are computed from statistical metrics:
    - Completeness: events_processed / events_received
    - Timeliness: events_within_latency_target / total_events
    - Correctness: 1.0 - error_rate
    - Consistency: pattern stability score

    Overall score = weighted average of dimensions.
    Thread-safe via RLock.
    """

    # Quality thresholds
    EXCELLENT_SCORE = 0.95
    GOOD_SCORE = 0.85
    FAIR_SCORE = 0.70

    # Weights for overall score
    WEIGHTS = {
        "completeness": 0.30,
        "timeliness": 0.25,
        "correctness": 0.30,
        "consistency": 0.15,
    }

    def __init__(self, latency_target_ms: float = 500.0,
                 max_error_rate: float = 0.05):
        self._lock = threading.RLock()
        self._latency_target_ms = latency_target_ms
        self._max_error_rate = max_error_rate
        self._last_score: Optional[QualityScore] = None
        self._score_history: List[QualityScore] = []
        self._max_history = 1000

    def evaluate(self, events_received: int, events_processed: int,
                 events_within_latency: int, error_count: int,
                 pattern_stability: float = 0.5) -> QualityScore:
        """Compute quality score from metric counters.

        Args:
            events_received: Total events received
            events_processed: Total events successfully processed
            events_within_latency: Events that met latency target
            error_count: Number of processing errors
            pattern_stability: Stability score (0.0-1.0) from PatternMiner
        """
        with self._lock:
            # Completeness
            completeness = events_processed / max(events_received, 1)

            # Timeliness
            timeliness = events_within_latency / max(events_processed, 1)

            # Correctness
            error_rate = error_count / max(events_received, 1)
            correctness = max(0.0, 1.0 - (error_rate / max(self._max_error_rate, 0.001)))

            # Consistency (capped at 1.0)
            consistency = min(pattern_stability, 1.0)

            # Weighted overall score
            overall = (
                self.WEIGHTS["completeness"] * completeness +
                self.WEIGHTS["timeliness"] * timeliness +
                self.WEIGHTS["correctness"] * correctness +
                self.WEIGHTS["consistency"] * consistency
            )

            # Determine quality level
            if overall >= self.EXCELLENT_SCORE:
                level = QualityLevel.EXCELLENT
            elif overall >= self.GOOD_SCORE:
                level = QualityLevel.GOOD
            elif overall >= self.FAIR_SCORE:
                level = QualityLevel.FAIR
            elif overall >= 0.5:
                level = QualityLevel.POOR
            else:
                level = QualityLevel.CRITICAL

            score = QualityScore(
                level=level,
                overall_score=overall,
                completeness=completeness,
                timeliness=timeliness,
                correctness=correctness,
                consistency=consistency,
                details={
                    "events_received": events_received,
                    "events_processed": events_processed,
                    "events_within_latency": events_within_latency,
                    "error_count": error_count,
                    "error_rate": error_rate,
                    "latency_target_ms": self._latency_target_ms,
                },
            )

            self._last_score = score
            self._score_history.append(score)
            if len(self._score_history) > self._max_history:
                self._score_history = self._score_history[-self._max_history:]

            return score

    def get_current(self) -> Optional[QualityScore]:
        """Get the most recent quality score."""
        with self._lock:
            return self._last_score

    def get_history(self, limit: int = 50) -> List[QualityScore]:
        """Get recent quality score history."""
        with self._lock:
            return list(reversed(self._score_history[-limit:]))

    def get_trend(self) -> Dict[str, Any]:
        """Get quality trend over history."""
        with self._lock:
            if len(self._score_history) < 2:
                return {"direction": "stable", "history": []}

            scores = self._score_history[-20:]
            first = scores[0].overall_score
            last = scores[-1].overall_score
            delta = last - first

            if delta > 0.05:
                direction = "improving"
            elif delta < -0.05:
                direction = "degrading"
            else:
                direction = "stable"

            return {
                "direction": direction,
                "delta": round(delta, 3),
                "current": round(last, 3),
                "history": [round(s.overall_score, 3) for s in scores],
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get evaluator statistics."""
        with self._lock:
            current = self._last_score
            return {
                "latency_target_ms": self._latency_target_ms,
                "max_error_rate": self._max_error_rate,
                "current_level": current.level.value if current else "none",
                "current_score": round(current.overall_score, 3) if current else 0.0,
                "history_count": len(self._score_history),
            }
