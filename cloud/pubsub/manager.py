"""PubSubManager — WebSocket-based real-time pub/sub.

Design: Based on MacOS v2.0 pubsub/manager.py.
Adapted to Main's threading model and CloudEventBus integration.

Provides real-time event broadcasting to all connected edges via WebSocket,
replacing the HTTP polling model with push-based event delivery.
"""
from __future__ import annotations
import json
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict


class PubSubManager:
    """Real-time publish/subscribe manager.
    
    Manages WebSocket connections from edge nodes and broadcasts
    events in real-time, eliminating the need for HTTP polling.
    
    Falls back to CloudEventBus query if WebSocket is unavailable.
    """

    HEARTBEAT_INTERVAL = 30
    HEARTBEAT_TIMEOUT = 90

    def __init__(self, eventbus=None):
        """Initialize PubSubManager.
        
        Args:
            eventbus: CloudEventBus for event persistence and fallback
        """
        self._eventbus = eventbus
        self._lock = threading.RLock()
        
        # Connection tracking
        self._connections: Dict[str, Any] = {}        # node_id → ws_client
        self._heartbeats: Dict[str, float] = {}       # node_id → last_heartbeat_ts
        self._subscriptions: Dict[str, List[str]] = defaultdict(list)  # node_id → [patterns]
        
        # Message queue for offline nodes
        self._offline_queues: Dict[str, List[dict]] = defaultdict(list)
        self._max_queue_size = 1000
        
        # Daemon control
        self._running = False
        self._cleanup_thread: Optional[threading.Thread] = None

    # ── Connection Management ──────────────────────────

    def register(self, node_id: str, ws_client=None, subscriptions: Optional[List[str]] = None):
        """Register an edge node connection.
        
        Args:
            node_id: Edge node identifier
            ws_client: WebSocket client object (or None for polling mode)
            subscriptions: List of event patterns to subscribe to
        """
        with self._lock:
            self._connections[node_id] = ws_client
            self._heartbeats[node_id] = time.time()
            if subscriptions:
                self._subscriptions[node_id] = subscriptions

    def unregister(self, node_id: str):
        """Unregister an edge node (on disconnect)."""
        with self._lock:
            self._connections.pop(node_id, None)
            self._heartbeats.pop(node_id, None)
            self._subscriptions.pop(node_id, None)

    def heartbeat(self, node_id: str):
        """Record a heartbeat from an edge node."""
        with self._lock:
            self._heartbeats[node_id] = time.time()

    # ── Publish / Subscribe ────────────────────────────

    def publish(self, event: dict, target: Optional[str] = None):
        """Publish an event to subscribers.
        
        Args:
            event: Event dict with event_type, payload, etc.
            target: Specific node_id to target, or None for broadcast
        """
        with self._lock:
            if target:
                self._send_to_node(target, event)
            else:
                # Broadcast to all connected nodes
                for node_id in list(self._connections.keys()):
                    self._send_to_node(node_id, event)
        
        # Also store in CloudEventBus for persistence
        if self._eventbus and hasattr(self._eventbus, 'ingest'):
            try:
                self._eventbus.ingest([event])
            except Exception:
                pass

    def broadcast(self, event: dict):
        """Broadcast event to all connected nodes."""
        self.publish(event)

    def _send_to_node(self, node_id: str, event: dict):
        """Send event to a specific node, or queue if offline."""
        ws = self._connections.get(node_id)
        if ws:
            try:
                # Check if node subscribed to this event type
                patterns = self._subscriptions.get(node_id, ["*"])
                event_type = event.get("event_type", "")
                if any(self._match_pattern(event_type, p) for p in patterns):
                    if hasattr(ws, 'send'):
                        ws.send(json.dumps(event))
            except Exception:
                self._queue_for_node(node_id, event)
        else:
            self._queue_for_node(node_id, event)

    def _queue_for_node(self, node_id: str, event: dict):
        """Queue event for offline node delivery."""
        queue = self._offline_queues[node_id]
        if len(queue) < self._max_queue_size:
            queue.append(event)

    def flush_queue(self, node_id: str) -> List[dict]:
        """Flush offline queue for a reconnected node."""
        with self._lock:
            queue = list(self._offline_queues.get(node_id, []))
            self._offline_queues[node_id] = []
            return queue

    # ── Cleanup ────────────────────────────────────────

    def start_cleanup(self):
        """Start background heartbeat checker."""
        if self._running:
            return
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="pubsub-cleanup"
        )
        self._cleanup_thread.start()

    def stop(self):
        """Stop cleanup daemon."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

    def _cleanup_loop(self):
        """Check for timed-out connections."""
        while self._running:
            for _ in range(int(self.HEARTBEAT_INTERVAL / 5)):
                if not self._running:
                    return
                time.sleep(5)
            if not self._running:
                return
            now = time.time()
            with self._lock:
                timed_out = [
                    nid for nid, ts in self._heartbeats.items()
                    if now - ts > self.HEARTBEAT_TIMEOUT
                ]
                for nid in timed_out:
                    self.unregister(nid)

    # ── Stats ──────────────────────────────────────────

    @property
    def stats(self) -> dict:
        """PubSub statistics."""
        with self._lock:
            total_queued = sum(len(q) for q in self._offline_queues.values())
            return {
                "connections": len(self._connections),
                "subscriptions": len(self._subscriptions),
                "offline_queued": total_queued,
                "offline_nodes": len(self._offline_queues),
            }

    @staticmethod
    def _match_pattern(event_type: str, pattern: str) -> bool:
        """Simple fnmatch-style pattern matching."""
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            return event_type.startswith(pattern[:-2])
        return event_type == pattern
