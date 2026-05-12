"""Cloud Event Store — persistent event storage with sequence numbers and replay.

Core of ClawShell's Event Sourcing infrastructure.
All events are append-only with immutable sequence IDs.
Supports replay for state reconstruction and cross-edge sync.

Design: stdlib-only, RLock thread-safe, JSON file storage.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Event Schema ────────────────────────────────────

class Topic(str, Enum):
    """Standard event topics in ClawShell."""
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_CLAIMED = "task.claimed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    SKILL_PUBLISHED = "skill.published"
    SKILL_DISCOVERED = "skill.discovered"
    NODE_REGISTERED = "node.registered"
    NODE_HEARTBEAT = "node.heartbeat"
    NODE_OFFLINE = "node.offline"
    INSIGHT_GENERATED = "insight.generated"
    BROADCAST_SENT = "broadcast.sent"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    SYSTEM_HEALTH = "system.health"
    SYSTEM_ERROR = "system.error"
    CUSTOM = "custom"


@dataclass
class Event:
    """Immutable event record with sequence ID.

    Events are append-only. Once written, sequence_id and event_id
    are permanent identifiers for replay and deduplication.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence_id: int = 0           # Monotonically increasing, assigned by store
    topic: str = ""
    source: str = ""               # edge_id or "cloud"
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.topic, Topic):
            d["topic"] = self.topic.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        d = d.copy()
        topic_val = d.get("topic", "")
        if isinstance(topic_val, str):
            try:
                d["topic"] = Topic(topic_val)
            except ValueError:
                pass
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Event Store ─────────────────────────────────────

class EventStore:
    """Append-only event store with sequence-number-based replay.

    Storage layout:
        data/event_store/
        ├── seq_counter          # Current sequence ID
        ├── YYYY-MM-DD/          # Daily partition
        │   ├── 000001.json
        │   ├── 000002.json
        │   └── ...
        └── index.json           # seq_id → file_path index (in-memory, periodic flush)

    Thread-safe via RLock. All I/O uses atomic writes (write temp → rename).
    """

    def __init__(self, store_dir: str = "data/event_store",
                 max_events_per_file: int = 1000,
                 retention_days: int = 30):
        self._store_dir = Path(store_dir)
        self._max_per_file = max_events_per_file
        self._retention_days = retention_days
        self._lock = threading.RLock()
        self._seq = 0
        self._index: Dict[int, str] = {}  # seq_id → relative file path
        self._running = True

        self._init_store()

    def _init_store(self) -> None:
        """Initialize or recover the store from disk."""
        self._store_dir.mkdir(parents=True, exist_ok=True)

        seq_file = self._store_dir / "seq_counter"
        if seq_file.exists():
            self._seq = int(seq_file.read_text().strip())
        else:
            self._seq = 0
            seq_file.write_text("0")

        # Rebuild index from existing files
        self._rebuild_index()

        # Start cleanup daemon
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _rebuild_index(self) -> None:
        """Scan existing event files and rebuild the sequence index."""
        for date_dir in sorted(self._store_dir.glob("????-??-??")):
            if not date_dir.is_dir():
                continue
            for event_file in sorted(date_dir.glob("*.json")):
                try:
                    events = json.loads(event_file.read_text())
                    if isinstance(events, list):
                        for event in events:
                            seq = event.get("sequence_id", 0)
                            if seq > 0:
                                rel_path = str(event_file.relative_to(self._store_dir))
                                self._index[seq] = rel_path
                except (json.JSONDecodeError, OSError):
                    continue

    def append(self, event: Event) -> Event:
        """Append an event and assign a sequence ID.

        Returns the event with assigned sequence_id.
        Thread-safe, atomic write.
        """
        with self._lock:
            self._seq += 1
            event.sequence_id = self._seq

            # Determine file path
            today = time.strftime("%Y-%m-%d", time.localtime(event.timestamp))
            date_dir = self._store_dir / today
            date_dir.mkdir(parents=True, exist_ok=True)

            # Find or create current batch file
            existing = sorted(date_dir.glob("*.json"))
            current_file = None
            current_events = []

            if existing:
                last_file = existing[-1]
                try:
                    current_events = json.loads(last_file.read_text())
                    if isinstance(current_events, list) and len(current_events) < self._max_per_file:
                        current_file = last_file
                except (json.JSONDecodeError, OSError):
                    current_events = []

            if current_file is None:
                file_index = len(existing) + 1
                current_file = date_dir / f"{file_index:06d}.json"
                current_events = []

            # Append and write atomically
            current_events.append(event.to_dict())
            tmp_file = current_file.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(current_events, ensure_ascii=False, indent=2))
            tmp_file.rename(current_file)

            # Update index
            rel_path = str(current_file.relative_to(self._store_dir))
            self._index[self._seq] = rel_path

            # Update seq counter
            (self._store_dir / "seq_counter").write_text(str(self._seq))

            return event

    def append_batch(self, events: List[Event]) -> List[Event]:
        """Append multiple events atomically."""
        return [self.append(e) for e in events]

    def get_by_seq(self, sequence_id: int) -> Optional[Event]:
        """Retrieve a specific event by sequence ID."""
        with self._lock:
            if sequence_id not in self._index:
                return None
            file_path = self._store_dir / self._index[sequence_id]
            try:
                events = json.loads(file_path.read_text())
                for e in events:
                    if e.get("sequence_id") == sequence_id:
                        return Event.from_dict(e)
            except (json.JSONDecodeError, OSError):
                pass
            return None

    def replay(self, from_seq: int = 0, to_seq: Optional[int] = None,
               topics: Optional[List[str]] = None) -> List[Event]:
        """Replay events from a sequence range.

        Used by StateAggregator to rebuild state after restart.
        """
        results = []
        with self._lock:
            if to_seq is None:
                to_seq = self._seq
            for seq in range(from_seq + 1, to_seq + 1):
                event = self.get_by_seq(seq)
                if event:
                    if topics is None or event.topic in topics or (
                        isinstance(event.topic, Topic) and event.topic.value in topics
                    ):
                        results.append(event)
        return results

    def query(self, topic: Optional[str] = None, source: Optional[str] = None,
              limit: int = 100, offset: int = 0) -> List[Event]:
        """Query events by topic and/or source.

        Scans recent files in reverse chronological order.
        """
        results = []
        with self._lock:
            date_dirs = sorted(self._store_dir.glob("????-??-??"), reverse=True)
            for date_dir in date_dirs:
                if not date_dir.is_dir():
                    continue
                for event_file in sorted(date_dir.glob("*.json"), reverse=True):
                    try:
                        events = json.loads(event_file.read_text())
                        if isinstance(events, list):
                            for event_dict in reversed(events):
                                ev_topic = event_dict.get("topic", "")
                                ev_source = event_dict.get("source", "")
                                if topic and ev_topic != topic:
                                    continue
                                if source and ev_source != source:
                                    continue
                                # Skip until offset
                                if offset > 0:
                                    offset -= 1
                                    continue
                                results.append(Event.from_dict(event_dict))
                                if len(results) >= limit:
                                    return results
                    except (json.JSONDecodeError, OSError):
                        continue
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        with self._lock:
            total_events = self._seq
            total_files = len(self._index)
            date_dirs = list(self._store_dir.glob("????-??-??"))
            topic_counts = {}
            # Sample recent events for topic distribution
            recent = self.query(limit=1000)
            for e in recent:
                t = e.topic.value if isinstance(e.topic, Topic) else e.topic
                topic_counts[t] = topic_counts.get(t, 0) + 1
            return {
                "total_events": total_events,
                "total_files": total_files,
                "days_of_data": len(date_dirs),
                "retention_days": self._retention_days,
                "topic_distribution": topic_counts,
                "max_per_file": self._max_per_file,
            }

    def _cleanup_loop(self) -> None:
        """Background cleanup: remove expired events beyond retention period."""
        while self._running:
            self._purge_expired()
            for _ in range(12):  # Check every hour (12 * 5s chunks)
                if not self._running:
                    break
                time.sleep(5)

    def _purge_expired(self) -> int:
        """Remove event files older than retention_days. Returns count of purged files."""
        cutoff = time.time() - (self._retention_days * 86400)
        purged = 0
        with self._lock:
            for date_dir in self._store_dir.glob("????-??-??"):
                if not date_dir.is_dir():
                    continue
                try:
                    dir_date = time.strptime(date_dir.name, "%Y-%m-%d")
                    dir_ts = time.mktime(dir_date)
                    if dir_ts < cutoff:
                        # Remove expired index entries
                        for event_file in date_dir.glob("*.json"):
                            try:
                                events = json.loads(event_file.read_text())
                                for e in events:
                                    self._index.pop(e.get("sequence_id", 0), None)
                            except (json.JSONDecodeError, OSError):
                                pass
                        # Remove the directory
                        import shutil
                        shutil.rmtree(date_dir, ignore_errors=True)
                        purged += 1
                except ValueError:
                    continue
        return purged

    def shutdown(self) -> None:
        """Graceful shutdown: stop cleanup daemon."""
        self._running = False
        if hasattr(self, '_cleanup_thread'):
            self._cleanup_thread.join(timeout=10)
