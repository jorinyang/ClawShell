"""MemOS Cloud API client — Cross-device memory synchronization.

Uses the MemOS Cloud API for storing and retrieving agent memories.
Credentials via environment variables (CLAWSHELL_MEMOS_API_KEY).
"""

from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any


class MemOSCloudClient:
    """Client for MemOS Cloud API (memos.memtensor.cn)."""

    DEFAULT_BASE_URL = "https://memos.memtensor.cn/api/openmem/v1"

    def __init__(self, api_key: str = "", user_id: str = "",
                 base_url: str = ""):
        self._api_key = api_key or ""
        self._user_id = user_id or ""
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._last_call_time = 0.0
        self._call_count = 0

    # ── Memory CRUD ───────────────────────────────

    def store_memory(self, content: str, tags: Optional[List[str]] = None,
                     metadata: Optional[dict] = None) -> dict:
        """Store a memory entry."""
        payload = {
            "user_id": self._user_id,
            "content": content,
            "tags": tags or [],
            "metadata": metadata or {},
        }
        return self._post("/memories", payload)

    def search_memories(self, query: str, limit: int = 10) -> List[dict]:
        """Search memories by semantic similarity."""
        result = self._post("/memories/search", {
            "user_id": self._user_id,
            "query": query,
            "limit": limit,
        })
        return result.get("memories", []) if isinstance(result, dict) else []

    def get_memory(self, memory_id: str) -> Optional[dict]:
        """Get a single memory by ID."""
        return self._get(f"/memories/{memory_id}")

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        result = self._delete(f"/memories/{memory_id}")
        return isinstance(result, dict) and result.get("success", False)

    def list_memories(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """List recent memories."""
        result = self._get(f"/memories?user_id={self._user_id}&limit={limit}&offset={offset}")
        return result.get("memories", []) if isinstance(result, dict) else []

    # ── Sync ──────────────────────────────────────

    def sync_from_cloud(self, since_timestamp: float = 0) -> List[dict]:
        """Pull memories updated since a timestamp."""
        result = self._get(
            f"/memories/sync?user_id={self._user_id}&since={since_timestamp}"
        )
        return result.get("memories", []) if isinstance(result, dict) else []

    def batch_store(self, memories: List[dict]) -> dict:
        """Store multiple memories in batch."""
        return self._post("/memories/batch", {
            "user_id": self._user_id,
            "memories": memories,
        })

    # ── Stats ──────────────────────────────────────

    def get_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "api_base": self._base_url,
            "user_id": self._user_id[:20] + "..." if self._user_id else "not set",
            "api_key_configured": bool(self._api_key),
            "total_calls": self._call_count,
        }

    # ── Internal HTTP ──────────────────────────────

    def _request(self, method: str, path: str, body: Optional[dict] = None,
                 timeout: int = 30) -> Any:
        """Make an HTTP request to MemOS Cloud."""
        if not self._api_key:
            return {"error": "API key not configured", "memories": []}

        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        data = None
        if body:
            data = json.dumps(body).encode()

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            resp = urllib.request.urlopen(req, timeout=timeout)
            self._call_count += 1
            self._last_call_time = time.time()
            return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}", "detail": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def _get(self, path: str) -> Any:
        return self._request("GET", path)

    def _post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, body)

    def _delete(self, path: str) -> Any:
        return self._request("DELETE", path)
