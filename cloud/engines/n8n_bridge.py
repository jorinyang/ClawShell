"""N8NBridge — Event→N8N workflow mapping and webhook triggering.

Features:
- Event type → webhook URL mapping
- Wildcard pattern matching for event routing
- Health check via HEAD request
- Thread-safe via threading.RLock()
"""

from __future__ import annotations
import fnmatch
import json
import threading
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any


class N8NBridge:
    """Bridge cloud events to N8N workflows."""

    DEFAULT_TIMEOUT = 10

    def __init__(self, n8n_base_url: str = "http://localhost:5678"):
        self._base_url = n8n_base_url.rstrip("/")
        self._lock = threading.RLock()
        self._routes: Dict[str, str] = {}  # event_pattern → webhook_url
        self._trigger_log: List[dict] = []

    # ── Route Management ──────────────────────────

    def add_route(self, event_pattern: str, webhook_url: str) -> str:
        """Map an event pattern to a webhook URL. Wildcards supported."""
        with self._lock:
            self._routes[event_pattern] = webhook_url
            return event_pattern

    def remove_route(self, event_pattern: str) -> bool:
        with self._lock:
            if event_pattern in self._routes:
                del self._routes[event_pattern]
                return True
            return False

    def list_routes(self) -> List[dict]:
        with self._lock:
            return [
                {"pattern": k, "webhook_url": v}
                for k, v in self._routes.items()
            ]

    # ── Event Routing ─────────────────────────────

    def match_routes(self, event_type: str) -> List[str]:
        """Find matching webhook URLs for an event type."""
        with self._lock:
            urls = []
            for pattern, url in self._routes.items():
                if fnmatch.fnmatch(event_type, pattern):
                    urls.append(url)
            return urls

    def trigger(self, event: dict) -> List[dict]:
        """Trigger matching N8N workflows for an event. Returns results."""
        event_type = event.get("event_type", "")
        urls = self.match_routes(event_type)

        results = []
        for url in urls:
            result = self._call_webhook(url, event)
            results.append(result)
            self._log_trigger(event_type, url, result.get("status", "error"))

        return results

    def trigger_workflow(self, webhook_url: str, payload: dict) -> dict:
        """Directly trigger a specific workflow."""
        return self._call_webhook(webhook_url, payload)

    # ── Health ────────────────────────────────────

    def health_check(self) -> dict:
        """Check N8N availability."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/healthz",
                method="HEAD"
            )
            resp = urllib.request.urlopen(req, timeout=5)
            return {"status": "healthy", "code": resp.status}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # ── Internal ──────────────────────────────────

    def _call_webhook(self, url: str, payload: dict) -> dict:
        """Call an N8N webhook with JSON payload."""
        start = time.time()
        try:
            data = json.dumps(payload, default=str).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=self.DEFAULT_TIMEOUT)
            body = resp.read().decode()
            return {
                "url": url,
                "status": "ok",
                "code": resp.status,
                "duration_ms": (time.time() - start) * 1000,
            }
        except urllib.error.HTTPError as e:
            return {
                "url": url,
                "status": "http_error",
                "code": e.code,
                "duration_ms": (time.time() - start) * 1000,
            }
        except Exception as e:
            return {
                "url": url,
                "status": "error",
                "error": str(e),
                "duration_ms": (time.time() - start) * 1000,
            }

    def _log_trigger(self, event_type: str, url: str, status: str):
        with self._lock:
            self._trigger_log.append({
                "event_type": event_type,
                "url": url,
                "status": status,
                "timestamp": time.time(),
            })
            if len(self._trigger_log) > 200:
                self._trigger_log = self._trigger_log[-100:]

    def get_trigger_log(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return self._trigger_log[-limit:]
