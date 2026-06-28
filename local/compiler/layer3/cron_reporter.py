"""CronReporter — Edge-side Cron execution reporting to Cloud.

Sits alongside LocalScheduler. After each Cron task executes, generates a
standardized CronReport and queues it for sync to CloudCronSupervisor.

The report is pushed to Cloud via:
  1. Immediate HTTP POST to CloudHub /api/v1/cron-supervisor/reports (if online)
  2. Stored locally for SyncDaemon to pick up (if offline)
"""

from __future__ import annotations
import time
import uuid
import json
import threading
import os
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timezone

from shared.models import CronReport


class CronReporter:
    """Edge-side Cron execution reporter.

    Usage:
        reporter = CronReporter(
            node_id="edge-wsl-001",
            cloud_url="http://47.239.71.174",
        )
        reporter.start()

        # After LocalScheduler executes a Cron job:
        reporter.report(
            task_id="edge.cleanup",
            status="success",
            duration_ms=123.4,
        )
    """

    REPORT_QUEUE_MAX = 100
    SYNC_INTERVAL = 5  # seconds between sync attempts

    def __init__(
        self,
        node_id: str,
        cloud_url: str = "http://47.239.71.174",
        data_dir: str = "~/.clawshell-edge",
    ):
        self.node_id = node_id
        self.cloud_url = cloud_url.rstrip("/")
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)

        self._queue_file = os.path.join(self._data_dir, "cron_reports.jsonl")
        self._lock = threading.RLock()

        # In-memory queue (mirrors queue file)
        self._pending: List[dict] = []

        # Daemon
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Metrics
        self._sent_count = 0
        self._failed_count = 0

        self._load_queue()

    # ── Public API ───────────────────────────────────────────────────────

    def start(self):
        """Start the reporter daemon (syncs queued reports periodically)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="cron-reporter",
        )
        self._thread.start()

    def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def report(
        self,
        task_id: str,
        status: str,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
        cpu_avg: float = 0.0,
        memory_mb: float = 0.0,
        recommendations: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[datetime] = None,
    ) -> str:
        """Generate and enqueue a CronReport for this execution.

        Returns the report_id.
        """
        now = datetime.now(timezone.utc)
        report = CronReport(
            report_id=f"rep_{uuid.uuid4().hex[:12]}",
            source=f"edge:local_scheduler:{self.node_id}",
            task_id=task_id,
            scheduled_at=scheduled_at or now,
            executed_at=now,
            status=status,
            error=error,
            duration_ms=duration_ms,
            cpu_avg=cpu_avg,
            memory_mb=memory_mb,
            recommendations=recommendations or [],
            metadata=metadata or {},
        )

        report_dict = report.model_dump(mode="json")

        with self._lock:
            self._pending.append(report_dict)
            if len(self._pending) > self.REPORT_QUEUE_MAX:
                self._pending = self._pending[-self.REPORT_QUEUE_MAX:]
            self._save_queue()

        # Try immediate sync
        self._sync_immediate(report_dict)

        return report.report_id

    def report_from_scheduler_result(
        self,
        task_id: str,
        scheduler_result: dict,
    ) -> str:
        """Helper: build report from LocalScheduler result dict."""
        return self.report(
            task_id=task_id,
            status=scheduler_result.get("status", "success"),
            error=scheduler_result.get("error"),
            duration_ms=scheduler_result.get("duration_ms", 0.0),
            cpu_avg=scheduler_result.get("cpu_avg", 0.0),
            memory_mb=scheduler_result.get("memory_mb", 0.0),
            recommendations=scheduler_result.get("recommendations", []),
            metadata=scheduler_result.get("metadata", {}),
        )

    def get_pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def get_stats(self) -> dict:
        return {
            "node_id": self.node_id,
            "pending": self.get_pending_count(),
            "sent": self._sent_count,
            "failed": self._failed_count,
        }

    # ── Sync logic ───────────────────────────────────────────────────────

    def _sync_loop(self):
        """Background sync loop — tries to flush pending reports to cloud."""
        while self._running:
            time.sleep(self.SYNC_INTERVAL)
            self._sync_pending()

    def _sync_immediate(self, report: dict):
        """Try to send a single report immediately (non-blocking)."""
        try:
            import urllib.request
            import urllib.error

            url = f"{self.cloud_url}/api/v1/cron-supervisor/reports"
            data = json.dumps(report).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": f"ClawShell-Edge/{self.node_id}",
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=5)
            if resp.status == 200:
                with self._lock:
                    self._remove_from_queue(report.get("report_id"))
                    self._sent_count += 1
        except Exception:
            pass  # Will be synced later via queue

    def _sync_pending(self):
        """Sync all pending reports to cloud."""
        with self._lock:
            pending = list(self._pending)

        if not pending:
            return {"flushed": 0}

        try:
            import urllib.request
            import urllib.error

            url = f"{self.cloud_url}/api/v1/cron-supervisor/reports/batch"
            data = json.dumps({"reports": pending}).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": f"ClawShell-Edge/{self.node_id}",
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=10)
            if resp.status == 200:
                with self._lock:
                    for r in pending:
                        rid = r.get("report_id") or ""
                        self._pending = [
                            x for x in self._pending
                            if (x.get("report_id") or "") != rid
                        ]
                    self._sent_count += len(pending)
        except Exception:
            with self._lock:
                self._failed_count += len(pending)

    def _remove_from_queue(self, report_id: str):
        """Remove a report from pending queue by report_id."""
        self._pending = [r for r in self._pending if r.get("report_id") != report_id]
        self._save_queue()

    # ── Persistence ──────────────────────────────────────────────────────

    def _save_queue(self):
        """Persist pending queue to disk."""
        try:
            with open(self._queue_file, "w", encoding="utf-8") as f:
                for r in self._pending:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def _load_queue(self):
        """Load pending queue from disk (for edge restart)."""
        if not os.path.exists(self._queue_file):
            return
        try:
            with open(self._queue_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._pending.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except OSError:
            pass
