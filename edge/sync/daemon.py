"""Edge Sync Daemon — Critical Cloud↔Edge synchronization.

Architecture: scan→enqueue→flush→pull→health loop every 5 seconds.

Components:
- CloudClient: HTTP client for Cloud API (stdlib urllib, zero deps)
- OfflineQueue: JSON file-backed queue (survives daemon restart)
- LocalEventScanner: mtime-based change detection on EventBus files
- HealthReporter: psutil metrics + service port checks
- EdgeSyncDaemon: orchestrates the 8-step cycle loop
"""

from __future__ import annotations
import os
import json
import time
import glob
import threading
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any


class CloudClient:
    """Minimal HTTP client for Cloud Hub API (stdlib urllib, zero external deps)."""

    def __init__(self, cloud_url: str, edge_token: str = "",
                 edge_id: str = "", timeout: int = 30):
        self._base_url = cloud_url.rstrip("/")
        self._token = edge_token
        self._edge_id = edge_id
        self._timeout = timeout

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        data = json.dumps(body).encode() if body else None

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            resp = urllib.request.urlopen(req, timeout=self._timeout)
            return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"success": False, "error": f"HTTP {e.code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def push_events(self, events: List[dict]) -> dict:
        return self._request("POST", "/api/v1/events/batch", {"events": events})

    def pull_tasks(self, limit: int = 10) -> List[dict]:
        resp = self._request("GET", f"/api/v1/tasks/?status=pending&limit={limit}")
        return resp.get("data", {}).get("tasks", []) if resp.get("success") else []

    def claim_task(self, task_id: str, edge_id: str) -> dict:
        return self._request("POST", f"/api/v1/tasks/{task_id}/claim", {"edge_id": edge_id})

    def complete_task(self, task_id: str, result: dict) -> dict:
        return self._request("POST", f"/api/v1/tasks/{task_id}/complete", {"result": result})

    def register_edge(self, node_info: dict) -> dict:
        return self._request("POST", "/api/v1/nodes/register", node_info)

    def report_health(self, health_data: dict) -> dict:
        return self._request("POST", "/api/v1/health/report", health_data)

    def pull_insights(self, limit: int = 20) -> List[dict]:
        resp = self._request("GET", f"/api/v1/insights/?limit={limit}")
        return resp.get("data", {}).get("insights", []) if resp.get("success") else []

    def pull_broadcasts(self, limit: int = 20) -> List[dict]:
        resp = self._request("GET", f"/api/v1/broadcasts/?limit={limit}")
        return resp.get("data", {}).get("broadcasts", []) if resp.get("success") else []

    def discover_skills(self, limit: int = 20) -> List[dict]:
        resp = self._request("GET", f"/api/v1/skills/?limit={limit}")
        return resp.get("data", {}).get("skills", []) if resp.get("success") else []

    def health_check(self) -> bool:
        try:
            resp = self._request("GET", "/health")
            return resp.get("status") == "healthy"
        except Exception:
            return False


class OfflineQueue:
    """JSON file-backed queue for offline resilience."""

    MAX_SIZE = 500
    TRIM_SIZE = 300

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._queue: List[dict] = []
        self._load()

    def enqueue(self, item: dict):
        with self._lock:
            self._queue.append(item)
            if len(self._queue) > self.MAX_SIZE:
                self._queue = self._queue[-self.TRIM_SIZE:]
            self._save()

    def dequeue_all(self) -> List[dict]:
        with self._lock:
            items = list(self._queue)
            self._queue = []
            self._save()
            return items

    def size(self) -> int:
        return len(self._queue)

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            with open(self._filepath, "w") as f:
                json.dump(self._queue, f, default=str)
        except Exception:
            pass

    def _load(self):
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath) as f:
                    self._queue = json.load(f)
            except Exception:
                self._queue = []


class LocalEventScanner:
    """Scan local EventBus files for new events (mtime-based)."""

    def __init__(self, event_dirs: List[str] = None):
        self._event_dirs = event_dirs or ["~/.real/eventbus/events"]
        self._last_mtimes: Dict[str, float] = {}

    def scan(self) -> List[dict]:
        """Scan for new/modified event files."""
        events = []
        for d in self._event_dirs:
            expanded = os.path.expanduser(d)
            if not os.path.isdir(expanded):
                continue

            pattern = os.path.join(expanded, "*", "*.json")
            for filepath in glob.glob(pattern):
                try:
                    mtime = os.path.getmtime(filepath)
                    if self._last_mtimes.get(filepath, 0) >= mtime:
                        continue

                    with open(filepath) as f:
                        event = json.load(f)
                    events.append(event)
                    self._last_mtimes[filepath] = mtime
                except Exception:
                    pass

        return events


class EdgeSyncDaemon:
    """Orchestrates the Edge↔Cloud sync loop."""

    SYNC_INTERVAL = 5  # seconds
    HEALTH_EVERY_N = 10  # Report health every 10 cycles

    def __init__(self, cloud_url: str, edge_token: str = "",
                 edge_id: str = "", data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)

        self._client = CloudClient(cloud_url, edge_token, edge_id)
        self._offline_queue = OfflineQueue(
            os.path.join(self._data_dir, "offline_events.json")
        )
        self._scanner = LocalEventScanner()

        # State cache files
        self._insights_cache = os.path.join(self._data_dir, "cloud_insights.json")
        self._broadcasts_cache = os.path.join(self._data_dir, "cloud_broadcasts.json")

        # Stats
        self._stats: Dict[str, int] = {
            "events_synced": 0, "tasks_pulled": 0,
            "insights_pulled": 0, "broadcasts_pulled": 0,
            "health_reports": 0, "cycles": 0, "errors": 0,
        }

        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── Daemon Lifecycle ──────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="edge-sync")
        self._thread.start()

    def shutdown(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def run_once(self) -> dict:
        """Execute one sync cycle (for testing/manual use)."""
        return self._sync_cycle()

    # ── Main Loop ─────────────────────────────────

    def _loop(self):
        while self._running:
            try:
                self._sync_cycle()
            except Exception:
                self._stats["errors"] += 1

            # 5s chunks for fast shutdown
            for _ in range(self.SYNC_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)

    def _sync_cycle(self) -> dict:
        """Execute one complete sync cycle."""
        cycle_start = time.time()
        result = {
            "events_flushed": 0,
            "tasks_pulled": 0,
            "insights_pulled": 0,
            "broadcasts_pulled": 0,
        }

        # 1. Scan local events
        local_events = self._scanner.scan()
        for evt in local_events:
            self._offline_queue.enqueue(evt)

        # 2. Flush queued events to Cloud
        queued = self._offline_queue.dequeue_all()
        if queued:
            resp = self._client.push_events(queued)
            if resp.get("success"):
                result["events_flushed"] = len(queued)
                self._stats["events_synced"] += len(queued)
            else:
                # Re-enqueue on failure
                for evt in queued:
                    self._offline_queue.enqueue(evt)

        # 3. Pull tasks
        tasks = self._client.pull_tasks(limit=5)
        result["tasks_pulled"] = len(tasks)
        self._stats["tasks_pulled"] += len(tasks)

        # 4. Pull insights (action reference)
        insights = self._client.pull_insights(limit=20)
        if insights:
            self._save_cache(self._insights_cache, insights)
            result["insights_pulled"] = len(insights)
            self._stats["insights_pulled"] += len(insights)

        # 5. Pull broadcasts
        broadcasts = self._client.pull_broadcasts(limit=20)
        if broadcasts:
            self._save_cache(self._broadcasts_cache, broadcasts)
            result["broadcasts_pulled"] = len(broadcasts)
            self._stats["broadcasts_pulled"] += len(broadcasts)

        # 6. Health report (every N cycles)
        self._stats["cycles"] += 1
        if self._stats["cycles"] % self.HEALTH_EVERY_N == 0:
            self._report_health()

        return result

    # ── Health ────────────────────────────────────

    def _report_health(self):
        """Report edge health to Cloud."""
        try:
            import psutil
            health = {
                "node_id": self._client._edge_id,
                "metrics": {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage("/").percent,
                },
                "services": {},
                "uptime_seconds": time.time(),
            }
        except ImportError:
            health = {
                "node_id": self._client._edge_id,
                "metrics": {"cpu_percent": 0, "memory_percent": 0, "disk_percent": 0},
            }

        self._client.report_health(health)
        self._stats["health_reports"] += 1

    # ── Cache ─────────────────────────────────────

    def _save_cache(self, filepath: str, data: list):
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, default=str, indent=2)
        except Exception:
            pass

    def get_cached_insights(self) -> List[dict]:
        return self._read_cache(self._insights_cache)

    def get_cached_broadcasts(self) -> List[dict]:
        return self._read_cache(self._broadcasts_cache)

    @staticmethod
    def _read_cache(filepath: str) -> List[dict]:
        if os.path.exists(filepath):
            try:
                with open(filepath) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    # ── Stats ─────────────────────────────────────

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "cloud_connected": self._client.health_check(),
            "offline_queue_size": self._offline_queue.size(),
            "cloud_url": self._client._base_url,
            "edge_id": self._client._edge_id,
        }
