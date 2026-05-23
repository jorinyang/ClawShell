from __future__ import annotations
"""ClawShell Edge — CloudClient (v2.2.1)."""
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


