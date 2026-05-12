"""CapabilityRegistry — Edge node registration, capability declaration, and scheduling.

Features:
- Edge node registration with capability declaration
- Heartbeat monitoring (configurable interval, default 30s timeout)
- Offline detection (heartbeat timeout)
- Least-loaded-first task assignment (capability + load aware)
- Thread-safe via threading.RLock()
- Persistent node registry (data/nodes.json)
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict


class CapabilityRegistry:
    """Edge node registry with heartbeat monitoring and load-aware scheduling."""

    HEARTBEAT_INTERVAL = 30
    HEARTBEAT_TIMEOUT = 90
    MONITOR_INTERVAL = 15

    def __init__(self, data_dir: str = "data", heartbeat_interval: int = 30,
                 heartbeat_timeout: int = 90):
        self._data_dir = data_dir
        self._heartbeat_interval = heartbeat_interval or self.HEARTBEAT_INTERVAL
        self._heartbeat_timeout = heartbeat_timeout or self.HEARTBEAT_TIMEOUT

        os.makedirs(data_dir, exist_ok=True)
        self._state_file = os.path.join(data_dir, "nodes.json")

        # RLock — reentrant for nested calls
        self._lock = threading.RLock()
        self._nodes: Dict[str, dict] = {}  # node_id → node dict

        # Daemon
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        self._load()

    # ── Public API ────────────────────────────────

    def register(self, node_info: dict) -> str:
        """Register or update an edge node. Returns node_id."""
        node_id = node_info.get("node_id", "")
        if not node_id:
            raise ValueError("node_id is required")

        with self._lock:
            existing = self._nodes.get(node_id, {})
            existing.update(node_info)
            existing["last_heartbeat"] = time.time()
            existing.setdefault("status", "online")
            existing.setdefault("registered_at", time.time())
            existing.setdefault("capabilities", [])
            existing.setdefault("frameworks", [])
            existing.setdefault("ide_tools", [])
            existing.setdefault("load_score", 0)
            existing.setdefault("cpu_count", node_info.get("cpu_count", 0))
            existing.setdefault("memory_total_mb", node_info.get("memory_total_mb", 0.0))

            self._nodes[node_id] = existing
            self._save()
            return node_id

    def heartbeat(self, node_id: str, metrics: Optional[dict] = None) -> bool:
        """Record a heartbeat. Returns True if node exists."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False

            node["last_heartbeat"] = time.time()
            node["status"] = "online"
            if metrics:
                node.setdefault("metrics", {}).update(metrics)
                cpu = metrics.get("cpu_percent", 0)
                mem = metrics.get("memory_percent", 0)
                node["load_score"] = (cpu * 0.5 + mem * 0.5) / 100.0

            self._save()
            return True

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get a single node's info."""
        with self._lock:
            node = self._nodes.get(node_id)
            return dict(node) if node else None

    def list_nodes(self, status: Optional[str] = None) -> List[dict]:
        """List all registered nodes, optionally filtered by status."""
        with self._lock:
            nodes = list(self._nodes.values())
            if status:
                nodes = [n for n in nodes if n.get("status") == status]
            return [dict(n) for n in nodes]

    def online_count(self) -> int:
        """Count online nodes."""
        with self._lock:
            return sum(
                1 for n in self._nodes.values()
                if n.get("status") == "online"
            )

    def deregister(self, node_id: str) -> bool:
        """Remove a node from the registry."""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                self._save()
                return True
            return False

    def assign_task(self, required_capabilities: List[str],
                    exclude_nodes: Optional[List[str]] = None) -> Optional[str]:
        """Assign task to least-loaded node matching capabilities.

        Returns node_id of the best match, or None if no match found.
        """
        exclude = set(exclude_nodes or [])
        with self._lock:
            candidates = []
            for nid, node in self._nodes.items():
                if nid in exclude:
                    continue
                if node.get("status") != "online":
                    continue

                node_caps = set(node.get("capabilities", []))
                required = set(required_capabilities)

                if not required or required.issubset(node_caps):
                    candidates.append((nid, node.get("load_score", 0)))

            if not candidates:
                return None

            # Sort by load_score ASC (least loaded first)
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]

    def find_nodes_by_capability(self, capability: str) -> List[str]:
        """Find all online nodes with a specific capability."""
        with self._lock:
            return [
                nid for nid, node in self._nodes.items()
                if node.get("status") == "online"
                and capability in node.get("capabilities", [])
            ]

    def find_nodes_by_framework(self, framework: str) -> List[str]:
        """Find all online nodes running a specific framework."""
        with self._lock:
            return [
                nid for nid, node in self._nodes.items()
                if node.get("status") == "online"
                and framework.lower() in [f.lower() for f in node.get("frameworks", [])]
            ]

    def find_nodes_by_ide(self, ide_name: str) -> List[str]:
        """Find all online nodes with a specific IDE CLI tool."""
        with self._lock:
            return [
                nid for nid, node in self._nodes.items()
                if node.get("status") == "online"
                and ide_name.lower() in [i.lower() for i in node.get("ide_tools", [])]
            ]

    # ── Daemon ────────────────────────────────────

    def start_monitor(self):
        """Start heartbeat monitor daemon."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="capability-monitor"
        )
        self._monitor_thread.start()

    def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)

    def _monitor_loop(self):
        """Check heartbeats periodically — 5s chunks for fast shutdown."""
        while self._running:
            self._check_heartbeats()
            for _ in range(int(self.MONITOR_INTERVAL / 5)):
                if not self._running:
                    break
                time.sleep(5)

    def _check_heartbeats(self):
        """Mark nodes as offline if heartbeat timeout exceeded."""
        now = time.time()
        with self._lock:
            changed = False
            for node_id, node in self._nodes.items():
                last_hb = node.get("last_heartbeat", 0)
                if now - last_hb > self._heartbeat_timeout:
                    if node.get("status") != "offline":
                        node["status"] = "offline"
                        changed = True
                elif now - last_hb > self._heartbeat_interval * 2:
                    if node.get("status") != "degraded":
                        node["status"] = "degraded"
                        changed = True
            if changed:
                self._save()

    # ── Persistence ───────────────────────────────

    def _save(self):
        """Persist node registry to disk."""
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(list(self._nodes.values()), f, ensure_ascii=False, default=str)
        except OSError:
            pass

    def _load(self):
        """Load node registry from disk."""
        if not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                nodes = json.load(f)
            for node in nodes:
                nid = node.get("node_id")
                if nid:
                    # Reset status to unknown on restart
                    node["status"] = "unknown"
                    self._nodes[nid] = node
        except (json.JSONDecodeError, OSError):
            pass
