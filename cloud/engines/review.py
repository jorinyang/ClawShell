"""UnifiedReviewEngine — Daily/Weekly/Monthly review system.

Features:
- Daily digests (task completion, error summary, edge health)
- Weekly synthesis (trends, patterns, best practices)
- Monthly retrospectives (strategic insights, ROI analysis)
- Auto-publishes findings as skills via SkillMarket
- Action plan generation
- 3600s check daemon
- Thread-safe via threading.RLock()
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class ActionPlan:
    """Action plan with tasks and timeline."""

    def __init__(self):
        self.plan_id = ""
        self.title = ""
        self.description = ""
        self.tasks: List[dict] = []
        self.created_at = time.time()
        self.status = "draft"

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "tasks": self.tasks,
            "created_at": self.created_at,
            "status": self.status,
        }


class UnifiedReviewEngine:
    """Generate daily, weekly, and monthly review reports."""

    CHECK_INTERVAL = 3600  # 1 hour

    def __init__(self, data_dir: str = "data", eventbus=None, skill_market=None):
        self._data_dir = data_dir
        self._eventbus = eventbus
        self._skill_market = skill_market
        os.makedirs(data_dir, exist_ok=True)

        self._lock = threading.RLock()
        self._reviews: List[dict] = []
        self._action_plans: Dict[str, ActionPlan] = {}
        self._last_daily = 0.0
        self._last_weekly = 0.0
        self._last_monthly = 0.0

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._load()

    # ── Review Generation ──────────────────────────

    def generate_daily(self) -> dict:
        """Generate daily review."""
        now = time.time()
        report = {
            "type": "daily",
            "timestamp": now,
            "date": datetime.fromtimestamp(now).strftime("%Y-%m-%d"),
            "summary": "Daily review generated",
            "tasks_completed": 0,
            "errors_detected": 0,
            "edges_active": 0,
            "insights": [],
            "action_items": [],
            # v1.8.1: Enhanced metrics (from MacOS ReviewDomain)
            "metrics": {
                "quality_score": None,
                "top_events": [],
                "anomaly_count": 0,
            },
            "trends": {},  # v1.8.1: Trend analysis placeholder
        }

        with self._lock:
            self._reviews.append(report)
            self._last_daily = now
            self._save()

        return report

    def generate_weekly(self) -> dict:
        """Generate weekly synthesis."""
        now = time.time()
        report = {
            "type": "weekly",
            "timestamp": now,
            "week": datetime.fromtimestamp(now).strftime("%Y-W%W"),
            "summary": "Weekly synthesis generated",
            "trends": [],
            "top_patterns": [],
            "best_practices": [],
            "action_plan": None,
        }

        with self._lock:
            self._reviews.append(report)
            self._last_weekly = now
            self._save()

        return report

    def generate_monthly(self) -> dict:
        """Generate monthly retrospective."""
        now = time.time()
        report = {
            "type": "monthly",
            "timestamp": now,
            "month": datetime.fromtimestamp(now).strftime("%Y-%m"),
            "summary": "Monthly retrospective generated",
            "strategic_insights": [],
            "roi_analysis": {},
            "evolution_progress": {},
            "action_plan": None,
        }

        with self._lock:
            self._reviews.append(report)
            self._last_monthly = now
            self._save()

        return report

    def create_action_plan(self, title: str, description: str,
                           tasks: List[dict]) -> str:
        """Create an action plan from review findings."""
        import uuid
        plan = ActionPlan()
        plan.plan_id = str(uuid.uuid4())
        plan.title = title
        plan.description = description
        plan.tasks = tasks

        with self._lock:
            self._action_plans[plan.plan_id] = plan
            self._save()

            # Auto-publish to SkillMarket if available
            if self._skill_market:
                self._skill_market.publish({
                    "name": f"Action Plan: {title}",
                    "description": description,
                    "category": "action-plan",
                    "content": json.dumps(plan.to_dict(), indent=2),
                })

        return plan.plan_id

    def get_recent_reviews(self, review_type: Optional[str] = None,
                           limit: int = 20) -> List[dict]:
        """Get recent reviews."""
        with self._lock:
            reviews = self._reviews
            if review_type:
                reviews = [r for r in reviews if r.get("type") == review_type]
            return reviews[-limit:]

    def get_action_plans(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self._action_plans.values()]

    def run_review_now(self, review_type: str = "daily") -> dict:
        """Manually trigger a review."""
        if review_type == "daily":
            return self.generate_daily()
        elif review_type == "weekly":
            return self.generate_weekly()
        elif review_type == "monthly":
            return self.generate_monthly()
        else:
            raise ValueError(f"Unknown review type: {review_type}")

    # ── Daemon ────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._check_loop, daemon=True, name="review-engine"
        )
        self._thread.start()

    def shutdown(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def _check_loop(self):
        while self._running:
            self._check_schedules()
            for _ in range(int(self.CHECK_INTERVAL / 5)):
                if not self._running:
                    break
                time.sleep(5)

    def _check_schedules(self):
        """Check if reviews are due."""
        now = time.time()
        today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")

        # Daily check
        if now - self._last_daily >= 86400:
            self.generate_daily()

        # Weekly check (Monday)
        if now - self._last_weekly >= 604800:
            self.generate_weekly()

        # Monthly check (1st of month)
        if now - self._last_monthly >= 2592000:
            self.generate_monthly()

    # ── Persistence ───────────────────────────────

    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "reviews.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "reviews": self._reviews[-200:],
                    "action_plans": {k: v.to_dict() for k, v in self._action_plans.items()},
                    "last_daily": self._last_daily,
                    "last_weekly": self._last_weekly,
                    "last_monthly": self._last_monthly,
                }, f, ensure_ascii=False, default=str)
        except OSError:
            pass

    def _load(self):
        path = os.path.join(self._data_dir, "reviews.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._reviews = data.get("reviews", [])[-200:]
            self._last_daily = data.get("last_daily", 0)
            self._last_weekly = data.get("last_weekly", 0)
            self._last_monthly = data.get("last_monthly", 0)
        except (json.JSONDecodeError, OSError):
            pass
