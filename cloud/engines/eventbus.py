"""CloudEventBus — Persistent, deduplicated event bus for the Cloud Hub.

Features:
- File-based persistence: data/eventbus/YYYY-MM-DD/{event_id}.json
- SHA256 content-based deduplication
- Wildcard pattern query (fnmatch)
- 30-day auto-expiry via daemon thread
- Stats aggregation by event type and source
- Thread-safe via threading.RLock() (reentrant!)
"""

from __future__ import annotations
import os
import json
import time
import glob
import fnmatch
import hashlib
import threading
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict


class CloudEventBus:
    """Persistent event bus with deduplication and expiry."""

    CLEANUP_INTERVAL = 3600  # 1 hour between cleanup runs
    EXPIRY_DAYS = 30

    def __init__(self, data_dir: str = "data",
                 event_store=None):
        """Initialize CloudEventBus.

        Args:
            data_dir: Directory for persistent storage
            event_store: Optional cloud.eventing.EventStore for enhanced
                         Event Sourcing backend (v1.8.1)
        """
        self._data_dir = data_dir
        self._event_store = event_store  # v1.8.1 EventStore integration
        self._event_dir = os.path.join(data_dir, "eventbus")
        os.makedirs(self._event_dir, exist_ok=True)

        # RLock — reentrant to allow _save/_load calls from locked methods
        self._lock = threading.RLock()

        # In-memory indexes
        self._events: Dict[str, dict] = {}          # event_id → event dict
        self._hashes: set = set()                    # SHA256 hashes for dedup
        self._by_type: Dict[str, List[str]] = defaultdict(list)  # type → [event_ids]
        self._by_source: Dict[str, List[str]] = defaultdict(list)  # source → [event_ids]
        self._stats: Dict[str, int] = defaultdict(int)

        # Daemon control
        self._running = False
        self._cleanup_thread: Optional[threading.Thread] = None

        # Load existing events on init
        self._load_all()

    # ── Public API ────────────────────────────────

    def ingest(self, events: List[dict]) -> int:
        """Ingest a batch of events. Returns count of NEW events accepted."""
        with self._lock:
            accepted = 0
            for event in events:
                if not isinstance(event, dict):
                    continue

                event_id = event.get("event_id", "")
                if not event_id:
                    continue

                # Dedup: content hash
                content = json.dumps({
                    "event_type": event.get("event_type", ""),
                    "source": event.get("source", ""),
                    "payload": event.get("payload", {})
                }, sort_keys=True, default=str)
                ch = hashlib.sha256(content.encode()).hexdigest()

                if ch in self._hashes:
                    continue  # Duplicate, skip

                # Store
                event["_hash"] = ch
                event["_stored_at"] = time.time()
                self._events[event_id] = event
                self._hashes.add(ch)

                # Index
                event_type = event.get("event_type", "unknown")
                source = event.get("source", "unknown")
                self._by_type[event_type].append(event_id)
                self._by_source[source].append(event_id)

                # Stats
                self._stats["total_ingested"] += 1
                self._stats[f"type:{event_type}"] += 1
                self._stats[f"source:{source}"] += 1

                accepted += 1

            if accepted > 0:
                self._save_batch(list(self._events.values())[-accepted:])

            return accepted

    def query(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """Query events with optional filters. Supports fnmatch wildcards."""
        with self._lock:
            # Determine candidate IDs
            if event_type and not fnmatch_filter_all(event_type):
                candidates = self._match_wildcard_keys(self._by_type, event_type)
            elif source and not fnmatch_filter_all(source):
                candidates = self._match_wildcard_keys(self._by_source, source)
            else:
                candidates = list(self._events.keys())

            results = []
            for eid in candidates:
                event = self._events.get(eid)
                if not event:
                    continue

                # Source filter (if not already filtered by source)
                if source and event_type and not fnmatch_filter_all(source):
                    if not fnmatch.fnmatch(event.get("source", ""), source):
                        continue

                # Time filters
                ts = event.get("timestamp", 0)
                if since is not None and ts < since:
                    continue
                if until is not None and ts > until:
                    continue

                results.append(self._clean_event(event))

            # Sort by timestamp desc, paginate
            results.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
            return results[offset:offset + limit]

    def query_by_type(self, event_type: str, limit: int = 100) -> List[dict]:
        """Convenience: query by exact event type."""
        return self.query(event_type=event_type, limit=limit)

    def query_by_source(self, source: str, limit: int = 100) -> List[dict]:
        """Convenience: query by exact source."""
        return self.query(source=source, limit=limit)

    def get_event(self, event_id: str) -> Optional[dict]:
        """Get a single event by ID."""
        with self._lock:
            event = self._events.get(event_id)
            return self._clean_event(event) if event else None

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics."""
        with self._lock:
            return {
                "total_events": len(self._events),
                "total_hashes": len(self._hashes),
                "by_type": dict(self._stats),
                "unique_types": len(self._by_type),
                "unique_sources": len(self._by_source),
            }

    def broadcast(self, events: List[dict]) -> List[str]:
        """Broadcast events to all connected edges (via WebSocket).

        Events are stored AND returned for immediate push.
        Returns list of event_ids that were accepted.
        """
        accepted_ids = []
        with self._lock:
            for event in events:
                event_id = event.get("event_id", "")
                if not event_id:
                    continue
                event["target"] = "*"
                ch = hashlib.sha256(
                    json.dumps({
                        "event_type": event.get("event_type", ""),
                        "source": event.get("source", ""),
                        "payload": event.get("payload", {})
                    }, sort_keys=True, default=str).encode()
                ).hexdigest()

                if ch in self._hashes:
                    continue

                event["_hash"] = ch
                event["_stored_at"] = time.time()
                self._events[event_id] = event
                self._hashes.add(ch)

                # Index
                etype = event.get("event_type", "unknown")
                source = event.get("source", "unknown")
                self._by_type[etype].append(event_id)
                self._by_source[source].append(event_id)

                accepted_ids.append(event_id)

            if accepted_ids:
                self._save_batch([
                    self._events[eid] for eid in accepted_ids
                ])
        return accepted_ids

    def get_recent_broadcasts(self, limit: int = 50) -> List[dict]:
        """Get recent broadcast events."""
        return self.query(event_type="broadcast", limit=limit)

    # ── Daemon ────────────────────────────────────

    def start_cleanup_daemon(self):
        """Start background cleanup daemon."""
        if self._running:
            return
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="eventbus-cleanup"
        )
        self._cleanup_thread.start()

    def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=10)

    # ── Internal ──────────────────────────────────

    def _cleanup_loop(self):
        """Background cleanup loop — 5s chunks for fast shutdown."""
        while self._running:
            self._expire_old_events()
            for _ in range(int(self.CLEANUP_INTERVAL / 5)):
                if not self._running:
                    break
                time.sleep(5)

    def _expire_old_events(self):
        """Remove events older than EXPIRY_DAYS."""
        cutoff = time.time() - (self.EXPIRY_DAYS * 86400)
        with self._lock:
            expired = [
                eid for eid, evt in self._events.items()
                if evt.get("timestamp", 0) < cutoff
            ]
            for eid in expired:
                self._remove_event(eid)
            if expired:
                # Clean up empty date directories
                self._clean_empty_dirs()

    def _remove_event(self, event_id: str):
        """Remove a single event and its indices."""
        event = self._events.pop(event_id, None)
        if not event:
            return

        ch = event.get("_hash", "")
        if ch:
            self._hashes.discard(ch)

        etype = event.get("event_type", "unknown")
        if event_id in self._by_type.get(etype, []):
            self._by_type[etype].remove(event_id)

        source = event.get("source", "unknown")
        if event_id in self._by_source.get(source, []):
            self._by_source[source].remove(event_id)

    def _clean_empty_dirs(self):
        """Remove empty date subdirectories."""
        for d in os.listdir(self._event_dir):
            dpath = os.path.join(self._event_dir, d)
            if os.path.isdir(dpath) and not os.listdir(dpath):
                os.rmdir(dpath)

    def _save_batch(self, events: List[dict]):
        """Persist a batch of events to disk."""
        for event in events:
            self._save_event_file(event)

    def _save_event_file(self, event: dict):
        """Save a single event to its date-based JSON file."""
        ts = event.get("timestamp", time.time())
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        date_dir = os.path.join(self._event_dir, date_str)
        os.makedirs(date_dir, exist_ok=True)

        event_id = event.get("event_id", "")
        filepath = os.path.join(date_dir, f"{event_id}.json")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(event, f, ensure_ascii=False, default=str)
        except OSError:
            pass  # Log but don't crash

    def _load_all(self):
        """Load all existing events from disk into memory."""
        pattern = os.path.join(self._event_dir, "*", "*.json")
        for filepath in glob.glob(pattern):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    event = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            event_id = event.get("event_id", "")
            if not event_id:
                continue

            ch = event.get("_hash", "")
            self._events[event_id] = event
            if ch:
                self._hashes.add(ch)

            etype = event.get("event_type", "unknown")
            self._by_type[etype].append(event_id)
            source = event.get("source", "unknown")
            self._by_source[source].append(event_id)

    def _match_wildcard_keys(self, index: Dict[str, list], pattern: str) -> List[str]:
        """Match keys in an index using fnmatch wildcards."""
        keys = []
        for key, ids in index.items():
            if fnmatch.fnmatch(key, pattern):
                keys.extend(ids)
        return keys

    @staticmethod
    def _clean_event(event: dict) -> dict:
        """Remove internal metadata from event before returning."""
        return {k: v for k, v in event.items() if not k.startswith("_")}


def fnmatch_filter_all(pattern: str) -> bool:
    """Check if pattern matches everything."""
    return pattern in ("*", "**", "")
