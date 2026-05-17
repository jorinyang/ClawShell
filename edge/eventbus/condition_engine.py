"""Condition Engine — rule-based event condition evaluation.

Evaluates conditions like: "if cpu > 80% for 5 minutes, trigger alert".
v1.8.1: Ported from ClawShell-MacOS condition_engine.
"""

from enum import Enum
import threading, time
from typing import Any, Callable, Dict, List, Optional

class ConditionType(str, Enum):
    THRESHOLD = "threshold"
    DURATION = "duration"
    PATTERN = "pattern"
    RATE = "rate"

class Condition:
    def __init__(self, name: str, cond_type: ConditionType, metric: str,
                 operator: str = ">", threshold: float = 0.0,
                 duration_seconds: int = 0, action: Optional[Callable] = None):
        self.name = name
        self.cond_type = cond_type
        self.metric = metric
        self.operator = operator
        self.threshold = threshold
        self.duration_seconds = duration_seconds
        self.action = action
        self._trigger_start: Optional[float] = None

    def evaluate(self, value: float) -> bool:
        result = False
        if self.operator == ">": result = value > self.threshold
        elif self.operator == "<": result = value < self.threshold
        elif self.operator == ">=": result = value >= self.threshold
        elif self.operator == "<=": result = value <= self.threshold
        elif self.operator == "==": result = abs(value - self.threshold) < 0.001
        if result and self.duration_seconds > 0:
            now = time.time()
            if self._trigger_start is None:
                self._trigger_start = now
            elif now - self._trigger_start < self.duration_seconds:
                return False
        if not result:
            self._trigger_start = None
        else:
            self._trigger_start = self._trigger_start or time.time()
        return result

class ConditionEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self._conditions: Dict[str, Condition] = {}
        self._metric_values: Dict[str, List[tuple]] = {}

    def add_condition(self, condition: Condition) -> None:
        with self._lock:
            self._conditions[condition.name] = condition

    def update_metric(self, name: str, value: float) -> List[str]:
        triggered = []
        with self._lock:
            self._metric_values.setdefault(name, []).append((time.time(), value))
            for cond in self._conditions.values():
                if cond.metric == name and cond.evaluate(value):
                    triggered.append(cond.name)
                    if cond.action:
                        try: cond.action(cond.name, value)
                        except Exception: pass
        return triggered

    def evaluate(self, event: dict) -> tuple:
        """Evaluate all conditions against an event's data.

        Args:
            event: Event dict with 'data' field containing metric values.

        Returns:
            (allowed, blocked_by): allowed is True if no conditions triggered.
            blocked_by is a list of condition names that triggered (blocked).
        """
        blocked = []
        data = event.get("data") or {}
        if not isinstance(data, dict):
            return True, []
        with self._lock:
            for cond in self._conditions.values():
                value = data.get(cond.metric)
                if value is not None and isinstance(value, (int, float)):
                    if cond.evaluate(float(value)):
                        blocked.append(cond.name)
        return len(blocked) == 0, blocked

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"condition_count": len(self._conditions), "tracked_metrics": len(self._metric_values)}
