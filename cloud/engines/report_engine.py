"""ReportEngine — unified review + broadcast (v2.3 — merged from review.py + broadcast.py).

Single engine for: generate reports (daily/weekly/monthly) → broadcast to all edges.
"""
from __future__ import annotations
import os, json, time, uuid, threading
from typing import Dict, List, Optional

class ReviewEngine:
    """Review generation (backward-compat alias)."""
    def __init__(self, data_dir="data", eventbus=None, skill_market=None):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._eventbus = eventbus
        self._skill_market = skill_market
        self._reviews = []
        self._action_plans = []
        self._lock = threading.RLock()
        self._running = False
        self._load()

    def generate_daily(self) -> dict:
        review = {"type": "daily", "timestamp": time.time(), "id": str(uuid.uuid4())[:8]}
        with self._lock: self._reviews.append(review); self._save()
        return review

    def generate_weekly(self) -> dict:
        return self.generate_daily() | {"type": "weekly"}

    def generate_monthly(self) -> dict:
        return self.generate_daily() | {"type": "monthly"}

    def create_action_plan(self, title: str, description: str, priority: str = "medium") -> dict:
        plan = {"id": str(uuid.uuid4())[:8], "title": title, "description": description,
                "priority": priority, "created": time.time()}
        with self._lock: self._action_plans.append(plan); self._save()
        return plan

    def get_recent_reviews(self, review_type: str = None, limit: int = 10) -> List[dict]:
        with self._lock:
            items = [r for r in self._reviews if not review_type or r.get("type") == review_type]
            return items[-limit:]

    def get_action_plans(self) -> List[dict]:
        with self._lock: return list(self._action_plans)

    def run_review_now(self, review_type: str = "daily") -> dict:
        gen = getattr(self, f"generate_{review_type}", self.generate_daily)
        return gen()

    def start(self): self._running = True
    def shutdown(self): self._running = False; self._save()
    def _load(self):
        try:
            with open(os.path.join(self._data_dir, "reviews.json")) as f:
                d = json.load(f)
                self._reviews = d.get("reviews", [])
                self._action_plans = d.get("plans", [])
        except: pass
    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "reviews.json"), "w") as f:
                json.dump({"reviews": self._reviews, "plans": self._action_plans}, f, indent=2)
        except: pass


class BroadcastEngine:
    """Broadcast distribution (backward-compat alias)."""
    def __init__(self, data_dir="data", eventbus=None):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._eventbus = eventbus
        self._broadcasts = []
        self._practices = []
        self._learning: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._load()

    def broadcast(self, title: str, content: str, broadcast_type: str = "info") -> dict:
        b = {"id": str(uuid.uuid4())[:8], "title": title, "content": content,
             "type": broadcast_type, "timestamp": time.time()}
        with self._lock: self._broadcasts.append(b); self._save()
        if self._eventbus: self._eventbus.publish("broadcast.created", b)
        return b

    def get_broadcasts(self, broadcast_type: str = None, limit: int = 20) -> List[dict]:
        with self._lock:
            items = [b for b in self._broadcasts if not broadcast_type or b.get("type") == broadcast_type]
            return items[-limit:]

    def register_best_practice(self, title: str, content: str, category: str = "general") -> str:
        pid = str(uuid.uuid4())[:8]
        with self._lock:
            self._practices.append({"id": pid, "title": title, "content": content,
                                    "category": category, "votes": 0, "timestamp": time.time()})
            self._save()
        return pid

    def search_best_practices(self, query: str = "", category: str = None, limit: int = 20) -> List[dict]:
        with self._lock:
            results = []
            for p in self._practices:
                if category and p.get("category") != category: continue
                if query and query.lower() not in p.get("title","").lower() and query.lower() not in p.get("content","").lower(): continue
                results.append(p)
                if len(results) >= limit: break
            return results

    def ingest_learning(self, edge_id: str, data: dict):
        with self._lock:
            if edge_id not in self._learning: self._learning[edge_id] = []
            self._learning[edge_id].append({"timestamp": time.time(), "data": data})
            self._save()

    def get_learning(self, edge_id: str = None) -> dict:
        with self._lock:
            return self._learning if edge_id is None else self._learning.get(edge_id, {})

    def _load(self):
        try:
            with open(os.path.join(self._data_dir, "broadcasts.json")) as f:
                d = json.load(f)
                self._broadcasts = d.get("broadcasts", [])
                self._practices = d.get("practices", [])
        except: pass
    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "broadcasts.json"), "w") as f:
                json.dump({"broadcasts": self._broadcasts, "practices": self._practices}, f, indent=2)
        except: pass


class ReportEngine:
    """Unified report generation + broadcast distribution.

    Replaces: UnifiedReviewEngine + BroadcastEngine (separate engines).
    Now: single engine generates review AND broadcasts it to all edges.
    """
    def __init__(self, data_dir="data", eventbus=None, skill_market=None):
        self.review = ReviewEngine(data_dir, eventbus, skill_market)
        self.broadcast = BroadcastEngine(data_dir, eventbus)

    def generate_and_broadcast(self, review_type: str = "daily") -> dict:
        review = self.review.run_review_now(review_type)
        broadcast = self.broadcast.broadcast(
            title=f"{review_type} Review",
            content=json.dumps(review),
            broadcast_type="review"
        )
        return {"review": review, "broadcast": broadcast}

    def start(self):
        self.review.start()
    def shutdown(self):
        self.review.shutdown()
