"""InsightEngine — Real-time event stream analysis engine.

Design: Based on DEEP InsightEngine + MacOS v2.1 InsightDomain.
Adapted to Main's threading model and CloudEventBus query-based pattern.

Capabilities:
- Error storm detection: 5+ errors from same source → Insight alert
- Periodic summary: Every 5 minutes, generate event statistics
- Pattern analysis: 3+ offline nodes in 1 hour → pattern Insight
- Knowledge extraction: Actionable insights → Knowledge entries

Integration:
- Works with CloudEventBus (cloud-side) via ingest/query
- Can also work with LocalEventBus (edge-side) via subscribe
- Insights published back to EventBus for BroadcastEngine consumption
- Synergizes with EvolutionEngine: Insight(real-time) → PatternMiner(mid-term) → AutoSkillPublisher(long-term)
"""
from __future__ import annotations
import os
import json
import time
import uuid
import threading
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable

from shared.models import Insight
from shared.models import EventCategory, EventPriority, TaskStatus


class InsightEngine:
    """Real-time event stream analysis engine.

    Subscribes to CloudEventBus (via query) or LocalEventBus (via subscribe),
    analyzes event patterns, and generates actionable Insights.
    """

    ERROR_STORM_THRESHOLD = 5        # 5+ errors from same source → alert
    OFFLINE_STORM_THRESHOLD = 3      # 3+ offline nodes in 1h → pattern
    SUMMARY_INTERVAL = 300           # 5 minutes
    ANALYSIS_INTERVAL = 30           # 30 seconds between analysis cycles

    def __init__(self, eventbus=None, data_dir: str = "data", knowledge_graph=None):
        """Initialize InsightEngine.

        Args:
            eventbus: CloudEventBus or LocalEventBus instance for event access
            data_dir: Directory for persistent storage
            knowledge_graph: Optional KnowledgeGraph instance for entity/relation storage
        """
        self._eventbus = eventbus
        self._data_dir = data_dir
        self._knowledge_graph = knowledge_graph
        self._insights_dir = os.path.join(data_dir, "insights")
        os.makedirs(self._insights_dir, exist_ok=True)

        # Event history (sliding window)
        self._history: deque[dict] = deque(maxlen=1000)

        # Error tracking: source → count
        self._error_count: Dict[str, int] = defaultdict(int)

        # Generated insights
        self._insights: List[Insight] = []

        # Daemon control
        self._running = False
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None

        # Subscriber management (for LocalEventBus pattern)
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self, auto_subscribe: bool = True):
        """Start the insight engine daemon.

        Args:
            auto_subscribe: If True and eventbus has subscribe(), auto-register handlers.
        """
        if auto_subscribe and self._eventbus and hasattr(self._eventbus, 'subscribe'):
            self._eventbus.subscribe("error.*", self._on_error)
            self._eventbus.subscribe("node.*", self._on_node)
            self._eventbus.subscribe("task.*", self._on_task)
            self._eventbus.subscribe("*", self._on_any)

        self._running = True
        self._thread = threading.Thread(
            target=self._analysis_loop, daemon=True, name="insight-engine"
        )
        self._thread.start()

    def stop(self):
        """Stop the insight engine daemon."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ── Event Handlers ────────────────────────────────────────

    def _on_error(self, event: dict):
        """Handle error events — track counts and detect error storms."""
        self._history.append(event)
        source = event.get("source", "unknown")
        self._error_count[source] += 1

        count = self._error_count[source]
        if count >= self.ERROR_STORM_THRESHOLD and count % self.ERROR_STORM_THRESHOLD == 0:
            insight = Insight(
                insight_id=str(uuid.uuid4()),
                title=f"Error storm detected: {source}",
                content=f"Node '{source}' has generated {count} errors. "
                        f"Latest: {event.get('payload', {}).get('message', event.get('event_type', 'unknown'))}",
                category="alert",
                severity=EventPriority.CRITICAL,
                source_node="insight-engine",
                actionable=True,
                action={"type": "investigate", "target": source, "error_count": count},
            )
            with self._lock:
                self._insights.append(insight)
            self._publish_insight(insight)
            # Reset counter after alert to avoid spam
            self._error_count[source] = 0

    def _on_node(self, event: dict):
        """Handle node events."""
        self._history.append(event)

    def _on_task(self, event: dict):
        """Handle task events."""
        self._history.append(event)

    def _on_any(self, event: dict):
        """Handle all events for history tracking."""
        self._history.append(event)

    # ── Analysis ──────────────────────────────────────────────

    def _analysis_loop(self):
        """Background analysis loop — periodic summary + pattern detection."""
        while self._running:
            for _ in range(int(self.ANALYSIS_INTERVAL / 5)):
                if not self._running:
                    return
                time.sleep(5)

            if not self._running:
                return

            try:
                # Also query CloudEventBus if available (pull mode for cloud-side)
                if self._eventbus and hasattr(self._eventbus, 'query') and callable(self._eventbus.query):
                    since = time.time() - self.ANALYSIS_INTERVAL
                    recent = self._eventbus.query(since=since, limit=200)
                    for event in recent:
                        if event not in self._history:
                            self._history.append(event)
            except Exception:
                pass  # EventBus query may fail during init

            # Generate periodic summary every SUMMARY_INTERVAL seconds
            self._maybe_generate_summary()

    def _maybe_generate_summary(self):
        """Generate a periodic summary if conditions are met."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=5)

        with self._lock:
            recent = [
                e for e in self._history
                if isinstance(e.get("timestamp"), (int, float))
                and datetime.fromtimestamp(e["timestamp"], tz=timezone.utc) > window_start
            ]

        if not recent:
            return

        errors = [e for e in recent if "error" in e.get("event_type", "").lower()]
        tasks = [e for e in recent if e.get("event_type", "").startswith("task.")]
        nodes = set(e.get("source", "") for e in recent if e.get("source"))

        content = (
            f"5-min summary: {len(nodes)} active nodes, "
            f"{len(tasks)} task events, {len(errors)} error events"
        )

        # Check for offline storm
        offline_count = sum(
            1 for e in recent
            if e.get("event_type") in ("node.offline", "node_timeout")
        )
        if offline_count >= self.OFFLINE_STORM_THRESHOLD:
            content += f"\n⚠️ {offline_count} nodes went offline in the last 5 minutes"

        insight = Insight(
            insight_id=str(uuid.uuid4()),
            title=f"Periodic Summary ({now.strftime('%H:%M')})",
            content=content,
            category="summary",
            severity=EventPriority.LOW if offline_count < self.OFFLINE_STORM_THRESHOLD else EventPriority.HIGH,
            source_node="insight-engine",
            tags=["periodic", "summary"],
        )

        with self._lock:
            self._insights.append(insight)
        self._publish_insight(insight)

    def analyze_patterns(self) -> List[Insight]:
        """Explicit pattern analysis — scan history for anomalies."""
        with self._lock:
            now = datetime.now(timezone.utc)
            one_hour_ago = now - timedelta(hours=1)

            # Offline pattern
            offline_events = [
                e for e in self._history
                if e.get("event_type") in ("node.offline", "node_timeout")
                and isinstance(e.get("timestamp"), (int, float))
                and datetime.fromtimestamp(e["timestamp"], tz=timezone.utc) > one_hour_ago
            ]

            patterns = []
            if len(offline_events) >= self.OFFLINE_STORM_THRESHOLD:
                offline_nodes = list(set(e.get("source", "unknown") for e in offline_events))
                insight = Insight(
                    insight_id=str(uuid.uuid4()),
                    title=f"Multiple offline nodes detected",
                    content=f"In the last hour, {len(offline_nodes)} nodes went offline: {offline_nodes}",
                    category="pattern",
                    severity=EventPriority.HIGH,
                    source_node="insight-engine",
                    actionable=True,
                    action={"type": "health_check", "targets": offline_nodes},
                )
                patterns.append(insight)
                self._insights.append(insight)
                self._publish_insight(insight)

            return patterns

    def generate_knowledge(self) -> List[dict]:
        """Extract Knowledge entries from actionable insights."""
        with self._lock:
            result = []
            for insight in self._insights[-20:]:
                if insight.actionable:
                    result.append({
                        "knowledge_id": f"k-{insight.insight_id}",
                        "title": insight.title,
                        "content": insight.content,
                        "category": insight.category,
                        "tags": insight.tags,
                        "source": "insight-engine",
                    })
            return result

    # ── Publish ───────────────────────────────────────────────

    def _publish_insight(self, insight: Insight):
        """Publish an insight to the EventBus and store in KnowledgeGraph."""
        if not self._eventbus:
            return

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "insight.generated",
            "category": "insight",
            "source": "insight-engine",
            "priority": insight.severity,
            "payload": insight.model_dump(),
            "timestamp": time.time(),
            "ttl_seconds": 86400,  # 24h
        }

        try:
            if hasattr(self._eventbus, 'publish'):
                self._eventbus.publish(event["event_type"], event)
            elif hasattr(self._eventbus, 'ingest'):
                self._eventbus.ingest([event])
        except Exception:
            pass  # EventBus may not be ready

        # Store insight as entity in KnowledgeGraph
        self._store_in_knowledge_graph(insight)

        # Also persist locally
        self._save_insight(insight)

    def _save_insight(self, insight: Insight):
        """Persist insight to disk."""
        try:
            path = os.path.join(self._insights_dir, f"{insight.insight_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(insight.model_dump_json(indent=2))
        except Exception:
            pass

    def _store_in_knowledge_graph(self, insight: Insight):
        """Store insight entities and relations in the KnowledgeGraph."""
        if not self._knowledge_graph:
            return
        try:
            from cloud.services.knowledge_graph import Entity, Relation
            # Create entity for the insight
            entity = Entity(
                entity_id=insight.insight_id,
                name=insight.title,
                entity_type="insight",
                description=insight.content,
                tags=insight.tags or [insight.category],
                properties={
                    "category": insight.category,
                    "severity": str(insight.severity),
                    "actionable": insight.actionable,
                    "source_node": insight.source_node,
                },
            )
            self._knowledge_graph.add_entity(entity)

            # If there's an action target, create a relation
            if insight.action and isinstance(insight.action, dict):
                target = insight.action.get("target") or insight.action.get("targets")
                if target:
                    target_name = target if isinstance(target, str) else str(target)
                    # Check if target entity exists or create one
                    existing = self._knowledge_graph.find_entities(
                        entity_type="node", tags=[target_name]
                    )
                    if existing:
                        rel = Relation(
                            source_id=insight.insight_id,
                            target_id=existing[0].entity_id,
                            relation_type="insight_about",
                            weight=0.8,
                        )
                        self._knowledge_graph.add_relation(rel)
        except Exception:
            pass  # Don't let KG errors break insight generation

    # ── Query ─────────────────────────────────────────────────

    def get_insights(self, limit: int = 20, category: Optional[str] = None) -> List[Insight]:
        """Get recent insights, optionally filtered by category."""
        with self._lock:
            result = self._insights
            if category:
                result = [i for i in result if i.category == category]
            return result[-limit:]

    def get_insights_as_dicts(self, limit: int = 20, category: Optional[str] = None) -> List[dict]:
        """Get recent insights as legacy dicts."""
        return [i.model_dump() for i in self.get_insights(limit, category)]

    # ── Stats ─────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        """Get engine statistics."""
        with self._lock:
            return {
                "total_events_tracked": len(self._history),
                "total_insights": len(self._insights),
                "error_sources": len(self._error_count),
                "running": self._running,
            }
