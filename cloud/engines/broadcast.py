"""BroadcastEngine — Cloud-initiated broadcasts to edges + BestPractice registry.

Features:
- Announcement broadcasts (skill updates, config changes, alerts)
- Best practice registry (search, register, cross-edge learning)
- Cross-edge learning data aggregation
- Broadcast persistence and query
- Thread-safe via threading.RLock()
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, List, Optional, Any


class BestPracticeRegistry:
    """Registered best practices from edges."""

    def __init__(self):
        self._lock = threading.RLock()
        self._practices: Dict[str, dict] = {}

    def register(self, title: str, content: str, category: str = "general",
                 source_edge: str = "", tags: Optional[List[str]] = None) -> str:
        import uuid
        pid = str(uuid.uuid4())
        with self._lock:
            self._practices[pid] = {
                "practice_id": pid,
                "title": title,
                "content": content,
                "category": category,
                "source_edge": source_edge,
                "tags": tags or [],
                "created_at": time.time(),
                "upvotes": 0,
            }
            return pid

    def search(self, query: str = "", category: Optional[str] = None,
               limit: int = 50) -> List[dict]:
        with self._lock:
            results = list(self._practices.values())
            if query:
                q = query.lower()
                results = [p for p in results
                          if q in p.get("title", "").lower()
                          or q in p.get("content", "").lower()]
            if category:
                results = [p for p in results if p.get("category") == category]
            results.sort(key=lambda p: p.get("upvotes", 0), reverse=True)
            return results[:limit]

    def upvote(self, practice_id: str):
        with self._lock:
            p = self._practices.get(practice_id)
            if p:
                p["upvotes"] = p.get("upvotes", 0) + 1


class CrossEdgeLearning:
    """Aggregated learning data across edges."""

    def __init__(self):
        self._lock = threading.RLock()
        self._learning_data: Dict[str, dict] = {}  # edge_id → learning data

    def ingest(self, edge_id: str, data: dict):
        with self._lock:
            existing = self._learning_data.get(edge_id, {})
            existing.update(data)
            existing["last_updated"] = time.time()
            self._learning_data[edge_id] = existing

    def get_learning(self, edge_id: Optional[str] = None) -> dict:
        with self._lock:
            if edge_id:
                return dict(self._learning_data.get(edge_id, {}))
            return dict(self._learning_data)


class BroadcastEngine:
    """Broadcast announcements and best practices to edges."""

    def __init__(self, data_dir: str = "data", eventbus=None):
        self._data_dir = data_dir
        self._eventbus = eventbus
        os.makedirs(data_dir, exist_ok=True)

        self._lock = threading.RLock()
        self._broadcasts: List[dict] = []
        self._best_practices = BestPracticeRegistry()
        self._cross_edge = CrossEdgeLearning()

        self._load()

    # ── Broadcasts ────────────────────────────────

    def broadcast(self, title: str, content: str,
                  broadcast_type: str = "announcement",
                  target_edges: Optional[List[str]] = None,
                  priority: int = 0) -> str:
        """Create and publish a broadcast."""
        import uuid
        bid = str(uuid.uuid4())
        bc = {
            "broadcast_id": bid,
            "title": title,
            "content": content,
            "broadcast_type": broadcast_type,
            "target_edges": target_edges or ["*"],
            "created_at": time.time(),
            "priority": priority,
        }

        with self._lock:
            self._broadcasts.append(bc)
            if len(self._broadcasts) > 500:
                self._broadcasts = self._broadcasts[-250:]
            self._save()

        # Also push to EventBus
        if self._eventbus:
            self._eventbus.broadcast([{
                "event_id": f"bc-{bid}",
                "event_type": "broadcast",
                "source": "cloud",
                "timestamp": time.time(),
                "payload": bc,
            }])

        return bid

    def get_broadcasts(self, broadcast_type: Optional[str] = None,
                       since: Optional[float] = None,
                       limit: int = 50) -> List[dict]:
        """Get recent broadcasts."""
        with self._lock:
            results = list(self._broadcasts)
            if broadcast_type:
                results = [b for b in results if b.get("broadcast_type") == broadcast_type]
            if since:
                results = [b for b in results if b.get("created_at", 0) >= since]
            results.sort(key=lambda b: b.get("created_at", 0), reverse=True)
            return results[:limit]

    # ── Best Practices ────────────────────────────

    def register_best_practice(self, title: str, content: str, **kwargs) -> str:
        pid = self._best_practices.register(title, content, **kwargs)
        # Auto-broadcast as best_practice
        self.broadcast(
            title=f"Best Practice: {title}",
            content=content,
            broadcast_type="best_practice",
        )
        return pid

    def search_best_practices(self, query: str = "", **kwargs) -> List[dict]:
        return self._best_practices.search(query, **kwargs)

    def upvote_best_practice(self, practice_id: str):
        self._best_practices.upvote(practice_id)

    # ── Cross-Edge Learning ───────────────────────

    def ingest_edge_learning(self, edge_id: str, data: dict):
        self._cross_edge.ingest(edge_id, data)

    def get_edge_learning(self, edge_id: Optional[str] = None) -> dict:
        return self._cross_edge.get_learning(edge_id)

    # ── Stats ─────────────────────────────────────

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_broadcasts": len(self._broadcasts),
                "best_practices": len(self._best_practices._practices),
                "edges_with_learning": len(self._cross_edge._learning_data),
            }

    # ── Persistence ───────────────────────────────

    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "broadcasts.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "broadcasts": self._broadcasts[-200:],
                    "best_practices": list(self._best_practices._practices.values()),
                }, f, ensure_ascii=False, default=str)
        except OSError:
            pass

    def _load(self):
        path = os.path.join(self._data_dir, "broadcasts.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._broadcasts = data.get("broadcasts", [])[-200:]
            for p in data.get("best_practices", []):
                pid = p.get("practice_id")
                if pid:
                    self._best_practices._practices[pid] = p
        except (json.JSONDecodeError, OSError):
            pass
