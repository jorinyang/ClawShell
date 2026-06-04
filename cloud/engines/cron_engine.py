"""CronEngine — unified cloud scheduler + cron supervisor (v2.3).

Merges: CloudScheduler + CloudCronSupervisor into single engine.
v2.3.1: ThreadPoolExecutor for concurrent job execution.
"""
from __future__ import annotations
import os, json, time, threading, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Callable, Optional, Any


class CronEngine:
    """Unified Cron engine: job scheduling + health supervision + dispatch orchestration.

    Replaces: CloudScheduler (job management) + CloudCronSupervisor (health monitoring).
    Now: single engine handles scheduling, monitoring, and repair dispatch.
    """

    def __init__(self, data_dir: str, eventbus=None, task_board=None,
                 capability_registry=None, dispatch_router=None):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._eventbus = eventbus
        self._task_board = task_board
        self._cap_registry = capability_registry
        self._dispatch_router = dispatch_router

        # Scheduler state
        self._jobs: Dict[str, dict] = {}
        self._exec_log: List[dict] = []
        self._handlers: Dict[str, Callable] = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # v2.3.1: Thread pool for concurrent job execution
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers: int = 8

        # Supervisor state
        self._reports: List[dict] = []
        self._problems: List[dict] = []
        self._repairs: List[dict] = []
        self._last_check = 0.0

        self._load()

    # ── Scheduler API ──────────────────────────────────────────
    def register_job(self, name: str, schedule: str, handler: Callable,
                     tags: List[str] = None) -> str:
        jid = str(uuid.uuid4())[:8]
        with self._lock:
            self._jobs[jid] = {"id": jid, "name": name, "schedule": schedule,
                               "handler": handler.__name__, "tags": tags or [],
                               "fail_count": 0, "last_run": 0.0, "status": "active"}
            # v2.3.1: Auto-register handler so run_jobs_parallel can find it
            self._handlers[handler.__name__] = handler
            self._save()
        return jid

    def list_jobs(self) -> List[dict]:
        with self._lock:
            return [{"id": k, **{kk: vv for kk, vv in v.items() if kk != "handler"}}
                    for k, v in self._jobs.items()]

    def run_job_now(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            return {"error": "not found"}
        handler = self._handlers.get(job["handler"])
        if not handler:
            return {"error": "no handler"}
        try:
            result = handler()
            self._exec_log.append({"job_id": job_id, "time": time.time(), "success": True})
            return {"job_id": job_id, "success": True, "result": str(result)[:200]}
        except Exception as e:
            self._exec_log.append({"job_id": job_id, "time": time.time(), "success": False, "error": str(e)})
            with self._lock:
                job["fail_count"] += 1
            return {"job_id": job_id, "success": False, "error": str(e)}

    # v2.3.1: Concurrent job execution
    def _ensure_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="cron-job"
            )
        return self._executor

    def run_jobs_parallel(self, job_ids: List[str]) -> List[dict]:
        """Run multiple jobs concurrently in the thread pool."""
        executor = self._ensure_executor()
        futures = {}
        for jid in job_ids:
            job = self._jobs.get(jid)
            if not job:
                continue
            handler = self._handlers.get(job["handler"])
            if not handler:
                continue
            # Prevent concurrent execution of the same job
            with self._lock:
                if job.get("_running"):
                    continue
                job["_running"] = True
            futures[executor.submit(self._execute_safe, jid, handler)] = jid

        results = []
        for future in as_completed(futures, timeout=30):
            jid = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                results.append({"job_id": jid, "success": False, "error": str(e)})
        return results

    def _execute_safe(self, job_id: str, handler: Callable) -> dict:
        """Execute a handler and record the result safely."""
        try:
            result = handler()
            self._exec_log.append({"job_id": job_id, "time": time.time(), "success": True})
            with self._lock:
                self._jobs[job_id]["_running"] = False
            return {"job_id": job_id, "success": True, "result": str(result)[:200]}
        except Exception as e:
            self._exec_log.append({"job_id": job_id, "time": time.time(), "success": False, "error": str(e)})
            with self._lock:
                self._jobs[job_id]["fail_count"] += 1
                self._jobs[job_id]["_running"] = False
            return {"job_id": job_id, "success": False, "error": str(e)}

    # ── Supervisor API ────────────────────────────────────────
    def ingest_report(self, report: dict) -> dict:
        with self._lock:
            report["ingested_at"] = time.time()
            self._reports.append(report)
            if len(self._reports) > 1000:
                self._reports = self._reports[-500:]
            self._save()
        return {"status": "ingested", "report_id": report.get("report_id")}

    def check_health(self) -> dict:
        """Full health scan: detect problems from reports + engine status."""
        problems = []
        now = time.time()

        # Chronic failures (3+ consecutive fails)
        for jid, job in self._jobs.items():
            if job.get("fail_count", 0) >= 3:
                problems.append({"type": "chronic_failure", "target": f"job:{jid}",
                                 "detail": f"{job.get('name')} failed {job['fail_count']}x"})

        # Edge offline (>120s no heartbeat)
        if self._cap_registry:
            for node in (self._cap_registry.list_nodes() or []):
                last = node.get("last_heartbeat", 0)
                if now - last > 120:
                    problems.append({"type": "edge_offline", "target": node.get("node_id"),
                                     "detail": f"Offline {int(now-last)}s"})

        # Dispatch repairs
        with self._lock:
            self._problems = problems
            self._last_check = now

        if self._dispatch_router and problems:
            for p in problems:
                try:
                    result = self._dispatch_router.dispatch(p)
                    self._repairs.append({"problem": p, "dispatch": result, "time": now})
                except Exception:
                    pass

        return {"problems_found": len(problems), "problems": problems, "checked_at": now}

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "supervisor": {"total_reports": len(self._reports),
                               "active_problems": len(self._problems),
                               "confirmed_repairs": sum(1 for r in self._repairs if r.get("success")),
                               "last_check": self._last_check},
                "dispatch": {"total": len(self._repairs), "by_type": {}}
            }

    def start(self):
        self._running = True

    def shutdown(self):
        self._running = False
        self._save()

    def _load(self):
        try:
            with open(os.path.join(self._data_dir, "cron_engine.json")) as f:
                d = json.load(f)
                self._jobs = d.get("jobs", {})
                self._reports = d.get("reports", [])
        except: pass

    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "cron_engine.json"), "w") as f:
                json.dump({"jobs": self._jobs, "reports": self._reports}, f, indent=2)
        except: pass
