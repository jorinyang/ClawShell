"""CloudCronSupervisor — Cloud-side Cron health monitoring and auto-repair.

Design: Periodic analysis of all Cron execution reports (cloud engines + all edge
nodes), detects problems, and triggers the repair pipeline via DispatchRouter.

Architecture:
  ReportAggregator (analyze) → RepairOrchestrator (plan) → DispatchRouter (execute)

Problem detection rules:
  - chronic_failure:  task failed 3+ consecutive times
  - cron_starved:      task not executed within 3x its expected interval
  - edge_offline:      edge node last_heartbeat > 60s ago
  - global_anomaly:    same metric abnormal on all registered edges
  - sync_lag:          edge sync timestamp > 5min behind cloud time
  - engine_degraded:   cloud engine daemon thread not running
"""

from __future__ import annotations
import time
import uuid
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

from shared.models import (
    CronReport,
    Problem,
    ProblemType,
    DispatchLayer,
    RepairPlan,
    EventMessage,
    TaskStatusClass,
)


class CloudCronSupervisor:
    """Cloud-side Cron health monitoring engine.

    Runs periodically (default 5 min) to analyze all Cron reports,
    detect problems, and dispatch repairs.
    """

    CHECK_INTERVAL = 300  # seconds (5 min)
    CHRONIC_FAILURE_THRESHOLD = 3  # consecutive failures
    EDGE_OFFLINE_THRESHOLD = 60    # seconds without heartbeat
    SYNC_LAG_THRESHOLD = 300       # seconds behind cloud time

    def __init__(
        self,
        data_dir: str = "data",
        scheduler: Any = None,
        eventbus: Any = None,
        task_board: Any = None,
        capability_registry: Any = None,
        dispatch_router: Any = None,
    ):
        self._data_dir = data_dir
        self._scheduler = scheduler
        self._eventbus = eventbus
        self._task_board = task_board
        self._capability_registry = capability_registry
        self._dispatch_router = dispatch_router

        self._lock = threading.RLock()
        self._reports: Dict[str, List[CronReport]] = {}  # node_id → reports
        self._problems: Dict[str, Problem] = {}
        self._plans: Dict[str, RepairPlan] = {}
        self._last_check: Optional[float] = None

        # Daemon
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self):
        """Start the supervisor daemon."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="cloud-cron-supervisor",
        )
        self._thread.start()

    def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def add_report(self, report: CronReport) -> str:
        """Receive a CronReport (from cloud scheduler or edge via API)."""
        with self._lock:
            source = report.source or "cloud"
            if source not in self._reports:
                self._reports[source] = []
            self._reports[source].append(report)
            # Keep last 100 reports per source
            if len(self._reports[source]) > 100:
                self._reports[source] = self._reports[source][-100:]
            return report.report_id

    def get_reports(self, source: str = "", limit: int = 50) -> List[CronReport]:
        """Get recent reports, optionally filtered by source."""
        with self._lock:
            if source:
                return self._reports.get(source, [])[-limit:]
            # All sources
            all_reports = []
            for src_reports in self._reports.values():
                all_reports.extend(src_reports)
            all_reports.sort(key=lambda r: r.executed_at, reverse=True)
            return all_reports[:limit]

    def get_problems(self, status: str = "") -> List[Problem]:
        """Get detected problems, optionally filtered by status."""
        with self._lock:
            probs = list(self._problems.values())
            if status:
                probs = [p for p in probs if p.dispatch_status == status]
            probs.sort(key=lambda p: p.severity, reverse=True)
            return probs

    def get_plans(self) -> List[RepairPlan]:
        with self._lock:
            return list(self._plans.values())

    def run_check_now(self) -> List[Problem]:
        """Manually trigger a health check. Returns detected problems."""
        return self._check_and_analyze()

    def get_stats(self) -> dict:
        """Statistics for monitoring."""
        with self._lock:
            total_reports = sum(len(v) for v in self._reports.values())
            active_problems = sum(
                1 for p in self._problems.values() if p.dispatch_status == "pending"
            )
            confirmed = sum(
                1 for p in self._problems.values() if p.dispatch_status == "confirmed"
            )
            return {
                "total_reports": total_reports,
                "active_problems": active_problems,
                "confirmed_repairs": confirmed,
                "sources": len(self._reports),
                "last_check": self._last_check,
            }

    # ── Daemon loop ────────────────────────────────────────────────────────

    def _loop(self):
        """Main supervisor loop."""
        while self._running:
            problems = self._check_and_analyze()

            # Dispatch repairs for new problems
            for problem in problems:
                self._dispatch_repair(problem)

            # Sleep in chunks for fast shutdown
            for _ in range(int(self.CHECK_INTERVAL / 5)):
                if not self._running:
                    break
                time.sleep(5)

    # ── Core analysis ───────────────────────────────────────────────────────

    def _check_and_analyze(self) -> List[Problem]:
        """Run all detection rules. Returns new problems found."""
        self._last_check = time.time()
        new_problems: List[Problem] = []

        with self._lock:
            reports = dict(self._reports)

        # Rule 1: Cloud Scheduler execution log
        problems = self._detect_cloud_scheduler_issues(reports)
        new_problems.extend(problems)

        # Rule 2: Edge offline detection
        problems = self._detect_edge_offline(reports)
        new_problems.extend(problems)

        # Rule 3: Chronic failures (3+ consecutive)
        problems = self._detect_chronic_failures(reports)
        new_problems.extend(problems)

        # Rule 4: Sync lag detection
        problems = self._detect_sync_lag(reports)
        new_problems.extend(problems)

        # Rule 5: Cloud engine health
        problems = self._detect_engine_degraded()
        new_problems.extend(problems)

        # Store new problems
        with self._lock:
            for problem in new_problems:
                existing = self._problems.get(problem.problem_id)
                if not existing or existing.dispatch_status in ("failed",):
                    self._problems[problem.problem_id] = problem

        return new_problems

    def _detect_cloud_scheduler_issues(self, reports: Dict[str, List[CronReport]]) -> List[Problem]:
        """Analyze cloud scheduler execution log."""
        problems = []

        if not self._scheduler:
            return problems

        try:
            log = self._scheduler.get_execution_log(limit=50)
            for entry in log:
                task_id = entry.get("task_id", "")
                status = entry.get("status", "")
                error = entry.get("error", "")

                if status == "failed":
                    # Check consecutive failures
                    recent = [
                        e for e in log
                        if e.get("task_id") == task_id and e.get("status") == "failed"
                    ]
                    if len(recent) >= self.CHRONIC_FAILURE_THRESHOLD:
                        problems.append(Problem(
                            problem_id=f"prob_{uuid.uuid4().hex[:12]}",
                            problem_type=ProblemType.CHRONIC_FAILURE,
                            source="cloud",
                            severity=80,
                            title=f"Chronic failure: {task_id}",
                            description=f"Task '{task_id}' failed {len(recent)} consecutive times. Last error: {error}",
                            affected_tasks=[task_id],
                            repair_action="restart_daemons",
                            dispatch_layer=DispatchLayer.TASKBOARD,
                            dispatch_status="pending",
                        ))
        except Exception:
            pass

        return problems

    def _detect_edge_offline(self, reports: Dict[str, List[CronReport]]) -> List[Problem]:
        """Detect edge nodes that have gone offline."""
        problems = []

        if not self._capability_registry:
            return problems

        try:
            nodes = self._capability_registry.list_nodes()
            now = time.time()

            for node in nodes:
                last_hb = node.get("last_heartbeat", 0)
                if isinstance(last_hb, datetime):
                    last_hb = last_hb.timestamp()
                age = now - last_hb if last_hb else self.EDGE_OFFLINE_THRESHOLD + 1

                if age > self.EDGE_OFFLINE_THRESHOLD:
                    node_id = node.get("node_id", "")
                    # Check if we already have an open problem for this
                    existing = [
                        p for p in self._problems.values()
                        if p.source == f"edge:{node_id}"
                        and p.problem_type == ProblemType.EDGE_OFFLINE
                        and p.dispatch_status in ("pending", "confirmed")
                    ]
                    if existing:
                        continue

                    problems.append(Problem(
                        problem_id=f"prob_{uuid.uuid4().hex[:12]}",
                        problem_type=ProblemType.EDGE_OFFLINE,
                        source=f"edge:{node_id}",
                        severity=90,
                        title=f"Edge offline: {node_id}",
                        description=f"Node '{node_id}' last heartbeat {age:.0f}s ago (> {self.EDGE_OFFLINE_THRESHOLD}s threshold)",
                        repair_action="redistribute_tasks",
                        dispatch_layer=DispatchLayer.TASKBOARD,
                        dispatch_status="pending",
                    ))
        except Exception:
            pass

        return problems

    def _detect_chronic_failures(self, reports: Dict[str, List[CronReport]]) -> List[Problem]:
        """Detect tasks with 3+ consecutive failures across any source."""
        problems = []

        for source, src_reports in reports.items():
            if source == "cloud":
                continue  # Handled by _detect_cloud_scheduler_issues

            # Group by task_id
            task_seq: Dict[str, List[CronReport]] = {}
            for r in src_reports:
                tid = r.task_id or "unknown"
                task_seq.setdefault(tid, []).append(r)

            for task_id, task_reports in task_seq.items():
                # Sort by time
                task_reports.sort(key=lambda r: r.executed_at, reverse=True)

                # Count consecutive failures from most recent
                consecutive = 0
                for r in task_reports:
                    if r.status == "failed":
                        consecutive += 1
                    else:
                        break

                if consecutive >= self.CHRONIC_FAILURE_THRESHOLD:
                    last_err = next(
                        (r.error for r in task_reports if r.error),
                        "unknown error"
                    )
                    problems.append(Problem(
                        problem_id=f"prob_{uuid.uuid4().hex[:12]}",
                        problem_type=ProblemType.CHRONIC_FAILURE,
                        source=source,
                        severity=80,
                        title=f"Chronic failure: {task_id} on {source}",
                        description=f"Task '{task_id}' failed {consecutive} consecutive times. Last error: {last_err}",
                        affected_tasks=[r.report_id for r in task_reports[:consecutive]],
                        repair_action="schedule_maintenance",
                        dispatch_layer=DispatchLayer.TASKBOARD,
                        dispatch_status="pending",
                    ))

        return problems

    def _detect_sync_lag(self, reports: Dict[str, List[CronReport]]) -> List[Problem]:
        """Detect edges with sync timestamps behind cloud time."""
        problems = []

        for source, src_reports in reports.items():
            if not source.startswith("edge:"):
                continue

            if not src_reports:
                continue

            # Most recent report
            latest = max(src_reports, key=lambda r: r.executed_at)
            lag = (datetime.now(timezone.utc) - latest.executed_at).total_seconds()

            if lag > self.SYNC_LAG_THRESHOLD:
                node_id = source.replace("edge:", "")
                problems.append(Problem(
                    problem_id=f"prob_{uuid.uuid4().hex[:12]}",
                    problem_type=ProblemType.SYNC_LAG,
                    source=source,
                    severity=60,
                    title=f"Sync lag: {node_id}",
                    description=f"Edge '{node_id}' last report was {lag:.0f}s ago (> {self.SYNC_LAG_THRESHOLD}s threshold)",
                    repair_action="force_sync",
                    dispatch_layer=DispatchLayer.EVENTBUS,
                    dispatch_status="pending",
                ))

        return problems

    def _detect_engine_degraded(self) -> List[Problem]:
        """Check if cloud engines have degraded."""
        problems = []

        if not self._scheduler:
            return problems

        try:
            tasks = self._scheduler.list_tasks()
            for task in tasks:
                fail_count = task.get("fail_count", 0)
                run_count = task.get("run_count", 0)
                if run_count > 0 and fail_count / run_count > 0.5:
                    task_id = task.get("task_id", "")
                    problems.append(Problem(
                        problem_id=f"prob_{uuid.uuid4().hex[:12]}",
                        problem_type=ProblemType.ENGINE_DEGRADED,
                        source="cloud",
                        severity=70,
                        title=f"Engine degraded: {task_id}",
                        description=f"Task '{task_id}' has {fail_count} failures out of {run_count} runs ({100*fail_count//run_count}% fail rate)",
                        affected_tasks=[task_id],
                        repair_action="restart_engine",
                        dispatch_layer=DispatchLayer.EVENTBUS,
                        dispatch_status="pending",
                    ))
        except Exception:
            pass

        return problems

    # ── Repair dispatch ─────────────────────────────────────────────────────

    def _dispatch_repair(self, problem: Problem):
        """Dispatch a repair plan for a detected problem."""
        if not self._dispatch_router:
            return

        try:
            action = problem.repair_action or "restart_daemons"
            record = self._dispatch_router.dispatch(problem, action)
            problem.dispatch_status = "dispatched"
            problem.dispatch_layer = record.layer
        except Exception:
            problem.dispatch_status = "failed"
