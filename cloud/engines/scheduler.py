"""CloudScheduler — Cron-based task scheduler for the Cloud Hub.

Features:
- Standard 5-field cron expression parser
- Supports *, */N, comma-separated, ranges
- 60s check loop with execution logging
- Thread-safe via threading.RLock()
- Persistent task definitions (data/cron_tasks.json)
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime


class CronExpression:
    """Parse and evaluate standard 5-field cron expressions."""

    FIELD_NAMES = ["minute", "hour", "day_of_month", "month", "day_of_week"]
    FIELD_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    MONTH_NAMES = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                   "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    DOW_NAMES = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}

    def __init__(self, expression: str):
        self.expression = expression.strip()
        self._fields = self._parse(self.expression)

    def _parse(self, expr: str) -> List[set]:
        """Parse a cron expression into sets of valid values per field."""
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: '{expr}' — need 5 fields")

        fields = []
        for i, (part, (lo, hi)) in enumerate(zip(parts, self.FIELD_RANGES)):
            values = set()
            for segment in part.split(","):
                segment = segment.strip()

                # Name substitution (months, days of week)
                if i == 3:  # Month
                    for name, num in self.MONTH_NAMES.items():
                        segment = segment.replace(name, str(num))
                elif i == 4:  # Day of week
                    for name, num in self.DOW_NAMES.items():
                        segment = segment.replace(name, str(num))

                if segment == "*":
                    values.update(range(lo, hi + 1))
                elif segment.startswith("*/"):
                    step = int(segment[2:])
                    values.update(range(lo, hi + 1, step))
                elif "-" in segment:
                    start, end = map(int, segment.split("-"))
                    values.update(range(max(lo, start), min(hi, end) + 1))
                else:
                    try:
                        v = int(segment)
                        if lo <= v <= hi:
                            values.add(v)
                    except ValueError:
                        raise ValueError(f"Invalid cron field: '{segment}' in '{expr}'")
            fields.append(values)
        return fields

    def matches(self, dt: Optional[datetime] = None) -> bool:
        """Check if this cron expression matches a given datetime (default: now)."""
        if dt is None:
            dt = datetime.now()
        check = [dt.minute, dt.hour, dt.day, dt.month, dt.weekday()]
        # Sunday is 6 in Python, 0 or 7 in cron
        if check[4] == 6:
            check[4] = 0  # Normalize Python Sunday (6) to cron Sunday (0)
        return all(check[i] in self._fields[i] for i in range(5))

    def next_run(self, from_dt: Optional[datetime] = None) -> datetime:
        """Find the next datetime matching this expression."""
        dt = from_dt or datetime.now()
        dt = dt.replace(second=0, microsecond=0)

        # Simple approach: advance minute by minute up to 366 days
        max_iterations = 366 * 24 * 60
        for _ in range(max_iterations):
            dt = datetime.fromtimestamp(dt.timestamp() + 60)
            if self.matches(dt):
                return dt

        raise ValueError(f"Cannot find next match for: {self.expression}")


class CloudScheduler:
    """Cron-based cloud task scheduler."""

    CHECK_INTERVAL = 60  # seconds

    def __init__(self, data_dir: str = "data"):
        self._data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._tasks_file = os.path.join(data_dir, "cron_tasks.json")

        self._lock = threading.RLock()
        self._tasks: Dict[str, dict] = {}
        self._handlers: Dict[str, Callable] = {}
        self._execution_log: List[dict] = []

        # Daemon
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._load()

    # ── Public API ────────────────────────────────

    def register_task(self, task_id: str, cron_expr: str, description: str = "",
                      handler_name: str = "", enabled: bool = True) -> str:
        """Register a scheduled task. Returns task_id."""
        with self._lock:
            try:
                CronExpression(cron_expr)  # Validate
            except ValueError as e:
                raise ValueError(f"Invalid cron expression '{cron_expr}': {e}")

            self._tasks[task_id] = {
                "task_id": task_id,
                "cron": cron_expr,
                "description": description,
                "handler_name": handler_name,
                "enabled": enabled,
                "last_run": None,
                "run_count": 0,
                "fail_count": 0,
            }
            self._save()
            return task_id

    def unregister_task(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._save()
                return True
            return False

    def set_handler(self, name: str, handler: Callable):
        """Register a named handler function."""
        self._handlers[name] = handler

    def list_tasks(self) -> List[dict]:
        """List all registered tasks."""
        with self._lock:
            return list(self._tasks.values())

    def get_execution_log(self, limit: int = 50) -> List[dict]:
        """Get recent execution log entries."""
        with self._lock:
            return self._execution_log[-limit:]

    def run_task_now(self, task_id: str) -> Optional[dict]:
        """Manually trigger a task execution."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return self._execute_task(task)

    # ── Daemon ────────────────────────────────────

    def start(self):
        """Start the scheduler daemon."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="cloud-scheduler"
        )
        self._thread.start()

    def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def _scheduler_loop(self):
        """Main scheduler loop — 5s chunks for fast shutdown."""
        while self._running:
            self._check_and_execute()
            for _ in range(int(self.CHECK_INTERVAL / 5)):
                if not self._running:
                    break
                time.sleep(5)

    def _check_and_execute(self):
        """Check all enabled tasks and execute due ones."""
        now = datetime.now()
        due_tasks = []

        with self._lock:
            for task in self._tasks.values():
                if not task.get("enabled", True):
                    continue

                try:
                    expr = CronExpression(task["cron"])
                    if expr.matches(now):
                        due_tasks.append(dict(task))
                except ValueError:
                    continue

        for task in due_tasks:
            self._execute_task(task)

    def _execute_task(self, task: dict) -> dict:
        """Execute a single task and log the result."""
        task_id = task["task_id"]
        start_time = time.time()
        result = {
            "task_id": task_id,
            "started_at": start_time,
            "status": "executed",
            "error": None,
        }

        handler_name = task.get("handler_name", "")
        handler = self._handlers.get(handler_name)

        if handler:
            try:
                handler(task)
            except Exception as e:
                result["status"] = "failed"
                result["error"] = str(e)
        else:
            result["status"] = "skipped"
            result["error"] = f"No handler: {handler_name}"

        result["duration_ms"] = (time.time() - start_time) * 1000

        with self._lock:
            t = self._tasks.get(task_id)
            if t:
                t["last_run"] = start_time
                t["run_count"] = t.get("run_count", 0) + 1
                if result["status"] == "failed":
                    t["fail_count"] = t.get("fail_count", 0) + 1
            self._execution_log.append(result)
            if len(self._execution_log) > 1000:
                self._execution_log = self._execution_log[-500:]
            self._save()

        return result

    # ── Persistence ───────────────────────────────

    def _save(self):
        """Persist task definitions."""
        try:
            with open(self._tasks_file, "w", encoding="utf-8") as f:
                json.dump(list(self._tasks.values()), f, ensure_ascii=False, default=str)
        except OSError:
            pass

    def _load(self):
        """Load task definitions from disk."""
        if not os.path.exists(self._tasks_file):
            return
        try:
            with open(self._tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            for task in tasks:
                tid = task.get("task_id")
                if tid:
                    self._tasks[tid] = task
        except (json.JSONDecodeError, OSError):
            pass
