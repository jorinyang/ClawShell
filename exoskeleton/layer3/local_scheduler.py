"""Local Cron Scheduler — edge-side task scheduling.

5-field cron expression parser with 60s loop.
"""

import time
import threading
import re
from typing import Callable, Dict, List, Optional


class LocalScheduler:
    """Edge-side cron scheduler with 5-field expressions."""

    def __init__(self):
        self._jobs: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_job(self, job_id: str, cron_expr: str, callback: Callable,
                description: str = "") -> bool:
        """Add a scheduled job."""
        with self._lock:
            fields = cron_expr.strip().split()
            if len(fields) != 5:
                return False
            self._jobs[job_id] = {
                "cron": cron_expr,
                "fields": fields,
                "callback": callback,
                "description": description,
                "last_run": 0,
                "run_count": 0,
            }
            return True

    def remove_job(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def list_jobs(self) -> List[dict]:
        with self._lock:
            return [
                {"job_id": jid, "cron": j["cron"], "description": j["description"],
                 "last_run": j["last_run"], "run_count": j["run_count"]}
                for jid, j in self._jobs.items()
            ]

    def _match_field(self, field: str, value: int) -> bool:
        """Match a single cron field against a value."""
        if field == "*":
            return True
        if "," in field:
            return value in [int(x) for x in field.split(",")]
        if "/" in field:
            parts = field.split("/")
            base = 0 if parts[0] == "*" else int(parts[0])
            step = int(parts[1])
            return value >= base and (value - base) % step == 0
        if "-" in field:
            lo, hi = field.split("-")
            return int(lo) <= value <= int(hi)
        return value == int(field)

    def _should_run(self, fields: List[str], t: time.struct_time) -> bool:
        """Check if cron fields match current time."""
        checks = [
            (fields[0], t.tm_min),
            (fields[1], t.tm_hour),
            (fields[2], t.tm_mday),
            (fields[3], t.tm_mon),
            (fields[4], t.tm_wday),
        ]
        return all(self._match_field(f, v) for f, v in checks)

    def _loop(self):
        while self._running:
            now = time.localtime()
            with self._lock:
                for jid, job in self._jobs.items():
                    try:
                        if self._should_run(job["fields"], now):
                            if time.time() - job["last_run"] >= 55:  # Prevent re-fire within 1min
                                job["callback"]()
                                job["last_run"] = time.time()
                                job["run_count"] += 1
                    except Exception:
                        pass
            for _ in range(12):  # 60s in 5s chunks
                if not self._running:
                    break
                time.sleep(5)

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="local-scheduler")
            self._thread.start()

    def stop(self):
        self._running = False

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "job_count": len(self._jobs),
                "jobs": self.list_jobs(),
            }
