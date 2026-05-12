"""EvolutionEngine — Self-evolution pipeline: InsightAggregator → PatternMiner → AutoSkillPublisher → EvolutionTracker.

Features:
- Aggregates events and tasks to extract insights
- Mines recurring patterns across edges
- Auto-publishes validated patterns as skills to SkillMarket
- Tracks evolution history
- 300s cycle daemon thread
- Thread-safe via threading.RLock()
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, List, Optional, Any, Callable


class InsightAggregator:
    """Aggregate events and task results into actionable insights."""

    def __init__(self):
        self._lock = threading.RLock()
        self._insights: Dict[str, dict] = {}
        self._counter = 0

    def add_insight(self, title: str, content: str, category: str = "general",
                    source_edges: Optional[List[str]] = None,
                    confidence: float = 0.5,
                    action_suggestion: str = "") -> str:
        """Add a new insight. Returns insight_id."""
        import uuid
        iid = str(uuid.uuid4())
        with self._lock:
            self._insights[iid] = {
                "insight_id": iid,
                "title": title,
                "content": content,
                "category": category,
                "source_edges": source_edges or [],
                "confidence": confidence,
                "created_at": time.time(),
                "action_suggestion": action_suggestion,
            }
            self._counter += 1
            return iid

    def get_insights(self, limit: int = 50, min_confidence: float = 0.0) -> List[dict]:
        """Get recent insights."""
        with self._lock:
            insights = [
                i for i in self._insights.values()
                if i.get("confidence", 0) >= min_confidence
            ]
            insights.sort(key=lambda i: i.get("created_at", 0), reverse=True)
            return insights[:limit]

    def total(self) -> int:
        return self._counter


class PatternMiner:
    """Mine recurring patterns from events and tasks."""

    def __init__(self):
        self._patterns: List[dict] = []
        self._lock = threading.RLock()

    def mine_from_events(self, events: List[dict], min_occurrences: int = 3) -> List[dict]:
        """Mine patterns from event data."""
        patterns = []
        type_counts: Dict[str, int] = {}
        for evt in events:
            etype = evt.get("event_type", "")
            type_counts[etype] = type_counts.get(etype, 0) + 1

        for etype, count in type_counts.items():
            if count >= min_occurrences:
                pattern = {
                    "pattern_id": f"pattern-{etype}",
                    "pattern_type": "recurring_event",
                    "event_type": etype,
                    "occurrences": count,
                    "discovered_at": time.time(),
                    "suggestion": f"Consider automating response to frequent '{etype}' events."
                }
                patterns.append(pattern)

        with self._lock:
            self._patterns.extend(patterns)
        return patterns

    def get_patterns(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return self._patterns[-limit:]


class AutoSkillPublisher:
    """Auto-publish validated patterns as skills to SkillMarket."""

    def __init__(self, skill_market=None):
        self._skill_market = skill_market
        self._published: List[dict] = []
        self._lock = threading.RLock()

    def set_skill_market(self, sm):
        self._skill_market = sm

    def publish_pattern(self, pattern: dict) -> Optional[str]:
        """Publish a pattern as a skill."""
        if not self._skill_market:
            return None

        skill = {
            "name": f"Auto: {pattern.get('pattern_type', 'pattern')}",
            "description": pattern.get("suggestion", ""),
            "category": "auto-generated",
            "tags": ["auto", pattern.get("event_type", "")],
            "capabilities": ["automation"],
            "content": json.dumps(pattern, indent=2),
            "version": "1.0.0",
        }
        sid = self._skill_market.publish(skill)
        with self._lock:
            self._published.append({"skill_id": sid, "pattern": pattern, "published_at": time.time()})
        return sid


class EvolutionTracker:
    """Track evolution history."""

    def __init__(self):
        self._history: List[dict] = []
        self._lock = threading.RLock()

    def record(self, event_type: str, data: dict):
        with self._lock:
            self._history.append({
                "event": event_type,
                "timestamp": time.time(),
                "data": data,
            })
            if len(self._history) > 1000:
                self._history = self._history[-500:]

    def get_history(self, limit: int = 100) -> List[dict]:
        with self._lock:
            return self._history[-limit:]


class EvolutionEngine:
    """Self-evolution pipeline orchestrator."""

    CYCLE_INTERVAL = 300  # 5 minutes

    def __init__(self, data_dir: str = "data", eventbus=None, skill_market=None):
        self._data_dir = data_dir
        self._eventbus = eventbus
        os.makedirs(data_dir, exist_ok=True)

        self._lock = threading.RLock()
        self._aggregator = InsightAggregator()
        self._miner = PatternMiner()
        self._publisher = AutoSkillPublisher(skill_market)
        self._tracker = EvolutionTracker()

        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── Public API ────────────────────────────────

    def add_insight(self, title: str, content: str, **kwargs) -> str:
        """Add an insight manually."""
        iid = self._aggregator.add_insight(title, content, **kwargs)
        self._tracker.record("insight_added", {"insight_id": iid, "title": title})
        return iid

    def get_insights(self, limit: int = 50, min_confidence: float = 0.0) -> List[dict]:
        return self._aggregator.get_insights(limit=limit, min_confidence=min_confidence)

    def get_patterns(self, limit: int = 50) -> List[dict]:
        return self._miner.get_patterns(limit=limit)

    def get_history(self, limit: int = 100) -> List[dict]:
        return self._tracker.get_history(limit=limit)

    def get_stats(self) -> dict:
        return {
            "total_insights": self._aggregator.total(),
            "patterns_found": len(self._miner.get_patterns()),
            "auto_published": len(self._publisher._published),
            "history_entries": len(self._tracker.get_history()),
        }

    def run_cycle(self):
        """Execute one evolution cycle (called by daemon)."""
        with self._lock:
            # 1. Aggregate insights from recent events
            if self._eventbus:
                # Query recent critical events
                pass  # EventBus integration in Phase 5

            # 2. Mine patterns
            events = []  # placeholder
            patterns = self._miner.mine_from_events(events)

            # 3. Auto-publish high-confidence patterns
            for p in patterns:
                if p.get("occurrences", 0) >= 3:
                    self._publisher.publish_pattern(p)

            self._tracker.record("cycle_completed", {"patterns_found": len(patterns)})

    # ── Daemon ────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._cycle_loop, daemon=True, name="evolution-engine"
        )
        self._thread.start()

    def shutdown(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def _cycle_loop(self):
        while self._running:
            try:
                self.run_cycle()
            except Exception:
                pass
            for _ in range(int(self.CYCLE_INTERVAL / 5)):
                if not self._running:
                    break
                time.sleep(5)
