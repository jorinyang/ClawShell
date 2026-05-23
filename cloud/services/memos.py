"""MemOS Cloud Service — Memory sync bridge.

From README: Services — MemOS Cloud integration.
"""
from __future__ import annotations
import os, json, time, urllib.request, urllib.error
from typing import Dict, List, Any, Optional

class MemOSService:
    """Bridge to MemOS Cloud (cloud.memos.com) for cross-device memory sharing."""

    def __init__(self, api_key: str = "", api_url: str = "https://cloud.memos.com/api/v1"):
        self._api_key = api_key or os.environ.get("MEMOS_API_KEY", "")
        self._api_url = api_url
        self._configured = bool(self._api_key)

    @property
    def is_configured(self) -> bool:
        return self._configured

    def store_memory(self, content: str, tags: List[str] = None) -> dict:
        if not self._configured:
            return {"status": "skipped", "reason": "MemOS not configured"}
        try:
            data = json.dumps({"content": content, "tags": tags or []}).encode()
            req = urllib.request.Request(f"{self._api_url}/memories",
                data=data, headers={"Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read())
        except Exception as e:
            return {"status": "error", "reason": str(e)[:100]}

    def search_memories(self, query: str, limit: int = 10) -> List[dict]:
        if not self._configured: return []
        try:
            url = f"{self._api_url}/memories/search?q={query}&limit={limit}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._api_key}"})
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read())
        except Exception:
            return []

    def status(self) -> dict:
        return {"configured": self._configured, "api_url": self._api_url}
