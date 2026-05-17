"""SwarmCoordinator — Multi-edge node management with heartbeat and load balancing.

Features:
- Node registration with capability declaration
- Heartbeat monitoring (30s interval, 90s timeout)
- Offline/degraded detection
- Least-loaded-first load balancing for task assignment
- Thread-safe via threading.RLock()
- Daemon thread with 5s chunk sleep for fast shutdown
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime

from shared.trust import TrustEvaluator, TrustLevel
from shared.trust import NodeMetrics as TrustNodeMetrics

class SwarmCoordinator:
    """Manage edge nodes, heartbeats, and load balancing."""

    HEARTBEAT_INTERVAL = 30
    HEARTBEAT_TIMEOUT = 90
    MONITOR_INTERVAL = 15      # Check every 15s
    OFFLINE_CLEANUP_DAYS = 7

    def __init__(self, data_dir: str = "data",
                 heartbeat_interval: int = 30,
                 heartbeat_timeout: int = 90):
        self._data_dir = data_dir
        self._heartbeat_interval = heartbeat_interval or self.HEARTBEAT_INTERVAL
        self._heartbeat_timeout = heartbeat_timeout or self.HEARTBEAT_TIMEOUT
        os.makedirs(data_dir, exist_ok=True)
        self._state_file = os.path.join(data_dir, "swarm_nodes.json")
        self._trust_file = os.path.join(data_dir, "swarm_trust_state.json")

        self._lock = threading.RLock()
        self._nodes: Dict[str, dict] = {}
        self._events: List[dict] = []  # Recent swarm events
        self._trust_evaluator = TrustEvaluator(persistence_path=self._trust_file)

        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        self._load()

    # ── Node Management ───────────────────────────

    def register_node(self, node_info: dict) -> str:
        """Register or update a node."""
        node_id = node_info.get("node_id", "")
        if not node_id:
            raise ValueError("node_id required")

        with self._lock:
            existing = self._nodes.get(node_id, {})
            existing.update(node_info)
            existing["last_heartbeat"] = time.time()
            existing.setdefault("status", "online")
            existing.setdefault("registered_at", time.time())
            existing.setdefault("load_score", 0.0)
            existing.setdefault("task_count", 0)
            existing.setdefault("capabilities", [])
            existing.setdefault("frameworks", [])
            existing.setdefault("ide_tools", [])

            self._nodes[node_id] = existing
            self._log_event("node_registered", {"node_id": node_id})
            self._save()
            return node_id

    def heartbeat(self, node_id: str, metrics: Optional[dict] = None) -> bool:
        """Record heartbeat with optional metrics."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False

            node["last_heartbeat"] = time.time()
            node["status"] = "online"
            if metrics:
                node.setdefault("metrics", {}).update(metrics)
                # Calculate load score
                cpu = metrics.get("cpu_percent", 0)
                mem = metrics.get("memory_percent", 0)
                disk = metrics.get("disk_percent", 0)
                node["load_score"] = (cpu * 0.4 + mem * 0.4 + disk * 0.2) / 100.0

                # Update trust score from heartbeat metrics
                trust_metrics = TrustNodeMetrics(
                    messages_sent=metrics.get("messages_sent", 0),
                    messages_received=metrics.get("messages_received", 0),
                    hmac_failures=metrics.get("hmac_failures", 0),
                    threat_detections=metrics.get("threat_detections", 0),
                    uptime_seconds=metrics.get("uptime_seconds", 0.0),
                    total_seconds=metrics.get("total_seconds", 0.0),
                    tasks_completed=metrics.get("tasks_completed", 0),
                    tasks_failed=metrics.get("tasks_failed", 0),
                )
                trust_score = self._trust_evaluator.record_metrics(node_id, trust_metrics)
                node["trust_score"] = trust_score.score
                node["trust_level"] = trust_score.level.name

            self._save()
            return True

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get node details."""
        with self._lock:
            n = self._nodes.get(node_id)
            return dict(n) if n else None

    def list_nodes(self, status: Optional[str] = None) -> List[dict]:
        """List all nodes."""
        with self._lock:
            nodes = list(self._nodes.values())
            if status:
                nodes = [n for n in nodes if n.get("status") == status]
            return [dict(n) for n in nodes]

    def online_count(self) -> int:
        """Count online nodes."""
        with self._lock:
            return sum(1 for n in self._nodes.values() if n.get("status") == "online")

    @property
    def trust_evaluator(self) -> TrustEvaluator:
        """Access the trust evaluator instance."""
        return self._trust_evaluator

    def get_trusted_nodes(self, min_trust_level: TrustLevel = TrustLevel.STANDARD) -> List[dict]:
        """Get online nodes that meet or exceed the minimum trust level."""
        with self._lock:
            result = []
            for nid, node in self._nodes.items():
                if node.get("status") != "online":
                    continue
                level_name = node.get("trust_level", "STANDARD")
                try:
                    node_level = TrustLevel[level_name]
                except KeyError:
                    node_level = TrustLevel.STANDARD
                if node_level.value >= min_trust_level.value:
                    result.append(dict(node))
            return result

    def deregister_node(self, node_id: str) -> bool:
        """Remove a node."""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                self._log_event("node_deregistered", {"node_id": node_id})
                self._save()
                return True
            return False

    def get_least_loaded_node(self, required_capabilities: Optional[List[str]] = None,
                              exclude: Optional[List[str]] = None) -> Optional[str]:
        """Find the least-loaded online node with matching capabilities.

        Considers trust_score as a weighting factor alongside load.
        Uses composite score: load_score * 0.6 + (1 - trust_score) * 0.4

        """
        exclude_set = set(exclude or [])
        with self._lock:
            candidates = []
            for nid, node in self._nodes.items():
                if nid in exclude_set:
                    continue
                if node.get("status") != "online":
                    continue

                if required_capabilities:
                    node_caps = set(node.get("capabilities", []))
                    if not set(required_capabilities).issubset(node_caps):
                        continue

                load = node.get("load_score", 0)
                trust = node.get("trust_score", 0.5)
                composite = load * 0.6 + (1.0 - trust) * 0.4
                candidates.append((nid, composite, node.get("task_count", 0)))

            if not candidates:
                return None

            # Sort by composite ASC (best load+trust combo), then task_count ASC
            candidates.sort(key=lambda x: (x[1], x[2]))
            return candidates[0][0]

    def assign_task(self, node_id: str, task_id: str):
        """Record task assignment (increments counter)."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node["task_count"] = node.get("task_count", 0) + 1
                node.setdefault("assigned_tasks", []).append(task_id)
                self._save()

    # ── Events ────────────────────────────────────

    def get_recent_events(self, limit: int = 50) -> List[dict]:
        """Get recent swarm events."""
        with self._lock:
            return self._events[-limit:]

    def _log_event(self, event_type: str, data: dict):
        """Log a swarm event."""
        self._events.append({
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        })
        if len(self._events) > 500:
            self._events = self._events[-250:]

    # ── Daemon ────────────────────────────────────

    def start_monitor(self):
        """Start heartbeat monitor daemon."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="swarm-monitor"
        )
        self._monitor_thread.start()

    def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)

    def _monitor_loop(self):
        """Monitor heartbeats in 5s chunks."""
        while self._running:
            self._check_status()
            for _ in range(int(self.MONITOR_INTERVAL / 5)):
                if not self._running:
                    break
                time.sleep(5)

    def _check_status(self):
        """Update node statuses based on heartbeat recency."""
        now = time.time()
        with self._lock:
            changed = False
            for node_id, node in self._nodes.items():
                last_hb = node.get("last_heartbeat", 0)
                gap = now - last_hb

                if gap > self._heartbeat_timeout:
                    if node.get("status") != "offline":
                        node["status"] = "offline"
                        self._log_event("node_offline", {"node_id": node_id, "gap_seconds": gap})
                        # Record negative trust signal for going offline
                        self._trust_evaluator.record_threat_detection(node_id)
                        trust_score = self._trust_evaluator.evaluate(node_id)
                        node["trust_score"] = trust_score.score
                        node["trust_level"] = trust_score.level.name
                        changed = True
                elif gap > self._heartbeat_interval * 2:
                    if node.get("status") != "degraded":
                        node["status"] = "degraded"
                        changed = True

            if changed:
                self._save()

    # ── Persistence ───────────────────────────────

    def _save(self):
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "nodes": list(self._nodes.values()),
                    "events": self._events[-100:],
                }, f, ensure_ascii=False, default=str)
        except OSError:
            pass
        # Persist trust state alongside swarm data
        try:
            self._trust_evaluator.save(self._trust_file)
        except (OSError, ValueError):
            pass

    def _load(self):
        if not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for node in data.get("nodes", []):
                nid = node.get("node_id")
                if nid:
                    node["status"] = "unknown"  # Reset on restart
                    self._nodes[nid] = node
            self._events = data.get("events", [])[-200:]
        except (json.JSONDecodeError, OSError):
            pass
