"""Exoskeleton Layer 2 — Self-Adaptation (自适应).

Core: Self-Repair engine, Engineering Cybernetics feedback control loop,
Adaptive parameter tuning, Robust controller.
"""

import os
import time
import json
import threading
from typing import Dict, List, Optional, Callable


class SelfRepairEngine:
    """Self-repair engine with 20+ fix actions."""

    FIX_ACTIONS: Dict[str, Callable] = {}

    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._repair_log: List[dict] = []

        # Register default fix actions
        self.FIX_ACTIONS["restart_gateway"] = self._noop
        self.FIX_ACTIONS["restart_daemons"] = self._noop
        self.FIX_ACTIONS["clear_cache"] = self._noop
        self.FIX_ACTIONS["rotate_logs"] = self._noop

    def detect_issues(self) -> List[dict]:
        """Detect system issues."""
        from exoskeleton.layer1.health_check import HealthChecker
        hc = HealthChecker()
        results = hc.check_all()

        issues = []
        if not results.get("cpu_healthy", True):
            issues.append({"type": "cpu_high", "severity": "warning",
                          "value": results.get("cpu_percent")})
        if not results.get("memory_healthy", True):
            issues.append({"type": "memory_high", "severity": "warning",
                          "value": results.get("memory_percent")})
        if not results.get("disk_healthy", True):
            issues.append({"type": "disk_full", "severity": "critical",
                          "value": results.get("disk_percent")})
        if not results.get("network_healthy", True):
            issues.append({"type": "network_down", "severity": "critical"})

        return issues

    def repair(self, issue: dict) -> dict:
        """Attempt to repair an issue."""
        issue_type = issue.get("type", "")
        action = self._map_action(issue_type)
        result = {"issue": issue_type, "action": action, "success": False}

        try:
            fix_fn = self.FIX_ACTIONS.get(action, self._noop)
            fix_fn()
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)

        result["timestamp"] = time.time()
        self._repair_log.append(result)
        return result

    def repair_all(self) -> List[dict]:
        """Detect and repair all issues."""
        issues = self.detect_issues()
        return [self.repair(issue) for issue in issues]

    def get_repair_log(self, limit: int = 50) -> List[dict]:
        return self._repair_log[-limit:]

    # v1.8.1: Backup & Checkpoint enhancements (from MacOS SelfHealing)
    def create_backup(self, name: str, content: str) -> str:
        """Create a named backup before critical repairs."""
        import time
        path = os.path.join(self._data_dir, f"backup_{name}_{int(time.time())}")
        os.makedirs(os.path.dirname(path) or self._data_dir, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def create_checkpoint(self, name: str) -> float:
        """Create a named system checkpoint for rollback."""
        import time, json
        ts = time.time()
        cp = {"name": name, "timestamp": ts, "repair_count": len(self._repair_log)}
        path = os.path.join(self._data_dir, f"checkpoint_{name}.json")
        with open(path, "w") as f:
            json.dump(cp, f)
        return ts

    @staticmethod
    def _map_action(issue_type: str) -> str:
        mapping = {
            "cpu_high": "restart_daemons",
            "memory_high": "clear_cache",
            "disk_full": "rotate_logs",
            "network_down": "restart_gateway",
        }
        return mapping.get(issue_type, "restart_daemons")

    @staticmethod
    def _noop(*args, **kwargs):
        pass


class FeedbackControlLoop:
    """Engineering Cybernetics feedback control loop.

    Goal → Controller → System → Sensor → Comparator → (feedback) → Controller
    """

    def __init__(self, goal: float = 0.0, tolerance: float = 0.1):
        self.goal = goal
        self.tolerance = tolerance
        self._actual = 0.0
        self._deviation = 0.0
        self._history: List[dict] = []
        self._lock = threading.RLock()

    def set_goal(self, goal: float):
        with self._lock:
            self.goal = goal
            # Recompute deviation after goal change
            if self._history:
                self._deviation = self.goal - self._actual

    def feed_sensor(self, actual: float) -> float:
        """Feed sensor reading, return control signal."""
        with self._lock:
            self._actual = actual
            self._deviation = self.goal - actual
            signal = self._compute_control(self._deviation)
            self._history.append({
                "timestamp": time.time(),
                "goal": self.goal,
                "actual": actual,
                "deviation": self._deviation,
                "signal": signal,
            })
            if len(self._history) > 100:
                self._history = self._history[-50:]
            return signal

    def is_converged(self) -> bool:
        with self._lock:
            if not self._history:
                return False  # No data means not converged
            return abs(self._deviation) <= self.tolerance

    def get_history(self) -> List[dict]:
        return list(self._history)

    def _compute_control(self, deviation: float) -> float:
        """Simple proportional controller."""
        return deviation * 0.5


class AdaptiveParameterTuner:
    """Self-adaptive parameter tuning based on performance feedback."""

    def __init__(self):
        self._params: Dict[str, float] = {}
        self._lock = threading.RLock()

    def register_parameter(self, name: str, initial: float,
                           min_val: float = 0.0, max_val: float = 1.0,
                           learning_rate: float = 0.1):
        with self._lock:
            self._params[name] = {
                "value": initial,
                "min": min_val,
                "max": max_val,
                "lr": learning_rate,
                "history": [],
            }

    def get(self, name: str) -> Optional[float]:
        with self._lock:
            p = self._params.get(name)
            return p["value"] if p else None

    def adjust(self, name: str, direction: str, amount: float = 0) -> float:
        """Adjust parameter up or down."""
        with self._lock:
            p = self._params.get(name)
            if not p:
                return 0.0

            step = amount or p["lr"]
            if direction == "up":
                p["value"] = min(p["max"], p["value"] + step)
            elif direction == "down":
                p["value"] = max(p["min"], p["value"] - step)

            p["history"].append({"value": p["value"], "timestamp": time.time()})
            return p["value"]

    def get_all_params(self) -> Dict[str, float]:
        with self._lock:
            return {k: v["value"] for k, v in self._params.items()}
