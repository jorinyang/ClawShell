"""MemOS Cloud API Client — universal memory cloud connector.

API Reference: https://memos.memtensor.cn/api/openmem/v1
Endpoint: POST /search (recall) | POST /messages (store)
"""

from __future__ import annotations
import json, time, urllib.request, urllib.error
from typing import Optional, List, Dict, Any


class MemOSCloudClient:
    """Low-level MemOS Cloud API client."""

    BASE_URL = "https://memos.memtensor.cn/api/openmem/v1"

    def __init__(self, api_key: str, base_url: Optional[str] = None,
                 user_id: str = "clawshell-user", timeout: float = 10.0):
        self.api_key = api_key
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.user_id = user_id
        self.timeout = timeout

    # ── Search / Recall ─────────────────────────────────────────────

    def search(self, query: str, conversation_id: str = "",
               top_k: int = 5, source: str = "clawshell",
               filters: Optional[Dict] = None,
               **kwargs) -> Dict[str, Any]:
        """Recall relevant memories for a query.
        
        Returns: {"records": [...], "total": N}
        """
        payload = {
            "user_id": self.user_id,
            "query": query if query else "",
            "top_k": top_k,
            "source": source,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if filters:
            payload["filter"] = filters

        return self._post("/search", payload)

    # ── Store / Add ──────────────────────────────────────────────────

    def add_message(self, role: str, content: str,
                    conversation_id: str = "",
                    metadata: Optional[Dict] = None,
                    source: str = "clawshell") -> Dict[str, Any]:
        """Store a conversation message as a memory.
        
        Args:
            role: "user" | "assistant" | "system"
            content: message text
            conversation_id: optional conversation grouping
            metadata: extra key-value pairs
            source: origin identifier
        """
        payload = {
            "user_id": self.user_id,
            "messages": [{
                "role": role,
                "content": content,
            }],
            "source": source,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if metadata:
            payload["metadata"] = metadata

        return self._post("/messages", payload)

    def add_messages(self, messages: List[Dict[str, str]],
                     conversation_id: str = "",
                     metadata: Optional[Dict] = None,
                     source: str = "clawshell") -> Dict[str, Any]:
        """Store multiple messages as memories."""
        payload = {
            "user_id": self.user_id,
            "messages": messages,
            "source": source,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if metadata:
            payload["metadata"] = metadata

        return self._post("/messages", payload)

    # ── Health ───────────────────────────────────────────────────────

    def health(self) -> bool:
        """Check if MemOS Cloud is reachable."""
        try:
            self._post("/search", {"user_id": self.user_id, "query": "ping",
                                    "top_k": 1, "source": "clawshell"})
            return True
        except Exception:
            return False

    # ── Internal ─────────────────────────────────────────────────────

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url, data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            raise RuntimeError(
                f"MemOS Cloud API error {e.code}: {body[:200]}"
            ) from e
