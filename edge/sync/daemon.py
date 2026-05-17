"""Edge Sync Daemon — Critical Cloud↔Edge synchronization.

Architecture: scan→enqueue→flush→pull→health→credentials loop every 5 seconds.

Components:
- CloudClient: HTTP client for Cloud API (stdlib urllib, zero deps)
- OfflineQueue: JSON file-backed queue (survives daemon restart)
- LocalEventScanner: mtime-based change detection on EventBus files
- HealthReporter: psutil metrics + service port checks
- CredentialSyncer: credential sync + local store management
- EdgeSyncDaemon: orchestrates the 9-step cycle loop

v2.0: Added auth token refresh, credential sync, WebSocket push integration.
"""

from __future__ import annotations
import os
import json
import time
import glob
import threading
import urllib.request
import urllib.error
import logging
from typing import Dict, List, Optional, Any

try:
    from shared.hooks.registry import trigger_hook
    from shared.hooks.manager import HookEvent
except ImportError:
    trigger_hook = None
    HookEvent = None

logger = logging.getLogger(__name__)


class CloudClient:
    """Minimal HTTP client for Cloud Hub API (stdlib urllib, zero external deps)."""

    def __init__(self, cloud_url: str, edge_token: str = "",
                 edge_id: str = "", timeout: int = 30):
        self._base_url = cloud_url.rstrip("/")
        self._token = edge_token
        self._edge_id = edge_id
        self._timeout = timeout
        self._lock = threading.RLock()

    @property
    def token(self) -> str:
        return self._token

    @token.setter
    def token(self, value: str):
        self._token = value

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        data = json.dumps(body).encode() if body else None

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            resp = urllib.request.urlopen(req, timeout=self._timeout)
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
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

    # ── Auth API (v2.0) ────────────────────────────────

    def refresh_token(self) -> Optional[str]:
        """Refresh the JWT token. Returns new token or None."""
        resp = self._request("POST", "/api/v2/auth/refresh")
        if "token" in resp:
            return resp["token"]
        return None

    def sync_credentials(self) -> dict:
        """Pull credentials from cloud."""
        resp = self._request("GET", "/api/v1/credentials/sync")
        if "user_credentials" in resp or "shared_credentials" in resp:
            return {
                "success": True,
                "user_credentials": resp.get("user_credentials", {}),
                "shared_credentials": resp.get("shared_credentials", {}),
            }
        return {"success": False, "error": resp.get("error", "Sync failed")}


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
    """Orchestrates the Edge↔Cloud sync loop.

    v2.0: Added token auto-refresh, credential sync on startup, and
    WebSocket push integration via CredentialWSClient.
    """

    SYNC_INTERVAL = 5  # seconds
    HEALTH_EVERY_N = 10  # Report health every 10 cycles
    TOKEN_REFRESH_EVERY_N = 120  # Refresh token every 120 cycles (~10 min)
    CRED_SYNC_EVERY_N = 60  # Sync credentials every 60 cycles (~5 min)

    def __init__(self, cloud_url: str, edge_token: str = "",
                 edge_id: str = "", data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)

        self._cloud_url = cloud_url
        self._client = CloudClient(cloud_url, edge_token, edge_id)
        self._offline_queue = OfflineQueue(
            os.path.join(self._data_dir, "offline_events.json")
        )
        self._scanner = LocalEventScanner()

        # State cache files
        self._insights_cache = os.path.join(self._data_dir, "cloud_insights.json")
        self._broadcasts_cache = os.path.join(self._data_dir, "cloud_broadcasts.json")

        # v2.0: Credential store and WebSocket client
        self._cred_store = None
        self._ws_client = None
        self._init_auth_components()

        # Stats
        self._stats: Dict[str, int] = {
            "events_synced": 0, "tasks_pulled": 0,
            "insights_pulled": 0, "broadcasts_pulled": 0,
            "health_reports": 0, "cycles": 0, "errors": 0,
            "cred_syncs": 0, "token_refreshes": 0,
        }

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _init_auth_components(self):
        """Initialize credential store and WebSocket client."""
        try:
            from edge.auth.credential_store import LocalCredentialStore
            self._cred_store = LocalCredentialStore(data_dir=self._data_dir)
            logger.info("LocalCredentialStore initialized")
        except ImportError:
            logger.warning("CredentialStore not available")

        # Start WebSocket client if we have a token
        if self._client.token:
            self._start_ws_client()

    def _start_ws_client(self):
        """Start the WebSocket client for real-time credential push."""
        try:
            from edge.auth.ws_client import CredentialWSClient
            if self._ws_client and self._ws_client.connected:
                return  # Already running

            self._ws_client = CredentialWSClient(
                cloud_url=self._cloud_url,
                token=self._client.token,
                on_change=self._on_cred_change,
            )
            self._ws_client.start()
            logger.info("CredentialWSClient started")
        except ImportError:
            logger.debug("CredentialWSClient not available")

    def _on_cred_change(self):
        """Callback: credential change detected via WebSocket."""
        logger.info("Credential change detected — triggering sync")
        self._sync_credentials()

    # ── Daemon Lifecycle ──────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="edge-sync")
        self._thread.start()

        # v2.0: Sync credentials on startup
        if self._cred_store and self._client.token:
            threading.Thread(
                target=self._sync_credentials, daemon=True, name="startup-cred-sync"
            ).start()

    def shutdown(self):
        self._running = False
        if self._ws_client:
            self._ws_client.stop()
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
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"Sync cycle error: {e}")

            # 5s chunks for fast shutdown
            for _ in range(self.SYNC_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)

    def _sync_cycle(self) -> dict:
        """Execute one complete sync cycle."""
        # Pre-sync hook: allow cancellation
        if trigger_hook is not None:
            try:
                pre_ctx = trigger_hook(
                    HookEvent.PRE_SYNC,
                    {"cycle": self._stats["cycles"] + 1},
                    source="sync_daemon",
                )
                if pre_ctx.cancelled:
                    logger.debug("Sync cycle skipped (PRE_SYNC hook cancelled)")
                    return {
                        "events_flushed": 0,
                        "tasks_pulled": 0,
                        "insights_pulled": 0,
                        "broadcasts_pulled": 0,
                        "skipped": True,
                    }
            except Exception:
                pass

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

        # 7. v2.0: Token refresh (every N cycles)
        if (self._client.token and
                self._stats["cycles"] % self.TOKEN_REFRESH_EVERY_N == 0):
            self._refresh_token()

        # 8. v2.0: Credential sync (every N cycles, if no WebSocket)
        if (self._cred_store and self._client.token and
                self._stats["cycles"] % self.CRED_SYNC_EVERY_N == 0):
            if not (self._ws_client and self._ws_client.connected):
                # Only poll if WebSocket is not connected
                self._sync_credentials()

        # Post-sync hook
        if trigger_hook is not None:
            try:
                trigger_hook(
                    HookEvent.POST_SYNC,
                    {"result": result, "duration": time.time() - cycle_start},
                    source="sync_daemon",
                )
            except Exception:
                pass

        return result

    # ── v2.0: Auth Operations ─────────────────────

    def _refresh_token(self):
        """Auto-refresh JWT token before expiry."""
        new_token = self._client.refresh_token()
        if new_token:
            self._client.token = new_token
            self._stats["token_refreshes"] += 1
            logger.info("Token refreshed successfully")

            # Update session file
            try:
                session_path = os.path.expanduser("~/.clawshell-edge/session.json")
                if os.path.exists(session_path):
                    with open(session_path) as f:
                        session = json.load(f)
                    session["token"] = new_token
                    with open(session_path, "w") as f:
                        json.dump(session, f, indent=2)
            except Exception:
                pass

            # Update WebSocket client token
            if self._ws_client:
                self._ws_client.update_token(new_token)
        else:
            logger.warning("Token refresh failed")

    def _sync_credentials(self):
        """Sync credentials from cloud to local store."""
        if not self._cred_store:
            return

        try:
            result = self._client.sync_credentials()
            if result.get("success"):
                user_creds = result.get("user_credentials", {})
                shared_creds = result.get("shared_credentials", {})

                # Flatten grouped creds
                user_list = []
                for service, creds in user_creds.items():
                    user_list.extend(creds)
                shared_list = []
                for service, creds in shared_creds.items():
                    shared_list.extend(creds)

                if user_list:
                    self._cred_store.merge_and_save(user_list)
                if shared_list:
                    self._cred_store.save_shared_credentials(shared_list)

                self._stats["cred_syncs"] += 1
                summary = self._cred_store.summary()
                logger.info(
                    f"Credentials synced: {summary['user_credential_count']} user, "
                    f"{summary['shared_credential_count']} shared"
                )
            else:
                logger.warning(f"Credential sync failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Credential sync error: {e}")

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
        status = {
            "running": self._running,
            "cloud_connected": self._client.health_check(),
            "offline_queue_size": self._offline_queue.size(),
            "cloud_url": self._client._base_url,
            "edge_id": self._client._edge_id,
        }
        # v2.0: Add credential and WebSocket status
        if self._cred_store:
            status["credentials"] = self._cred_store.summary()
        if self._ws_client:
            status["websocket"] = self._ws_client.get_status()
        return status
