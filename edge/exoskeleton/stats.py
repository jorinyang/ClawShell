"""CycleStats — thread-safe metrics collector.

Extracted from ExoskeletonDaemon (v2.2.1).
"""

from __future__ import annotations
import threading
import time
from typing import Any, Dict


class CycleStats:
    """Thread-safe metrics accumulator for exoskeleton cycles."""

    def __init__(self):
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {
            "cycles": 0,
            "errors": 0,
            "last_cycle_duration": 0.0,
            "last_cycle_time": 0.0,
            "module_failures": {},
            "health_issues_found": 0,
            "repairs_attempted": 0,
            "repairs_succeeded": 0,
        }

    def increment(self, key: str, delta: int = 1):
        with self._lock:
            if key in self._data and isinstance(self._data[key], (int, float)):
                self._data[key] += delta

    def set(self, key: str, value: Any):
        with self._lock:
            self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def record_failure(self, module_name: str, error: str):
        with self._lock:
            self._data["module_failures"][module_name] = error

    def finalize_cycle(self, duration: float):
        with self._lock:
            self._data["cycles"] += 1
            self._data["last_cycle_duration"] = round(duration, 3)
            self._data["last_cycle_time"] = time.time()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)
