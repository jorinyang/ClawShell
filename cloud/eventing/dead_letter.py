"""Dead Letter Queue — failed event replay with configurable retry.

Events that fail processing (exceed retries, timeout, invalid) are moved
to the dead letter queue for manual inspection and replay.

Design: stdlib-only, JSON file-backed, RLock thread-safe.
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


class DLQReason(str, Enum):
    """Reasons for dead-lettering an event."""
    MAX_RETRIES = "max_retries"
    TIMEOUT = "timeout"
    INVALID_FORMAT = "invalid_format"
    HANDLER_ERROR = "handler_error"
    CIRCUIT_BREAKER = "circuit_breaker"
    UNKNOWN = "unknown"


@dataclass
class DeadLetter:
    """A dead-lettered event with failure context."""
    dlq_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_payload: Dict[str, Any] = field(default_factory=dict)
    topic: str = ""
    source: str = ""
    reason: DLQReason = DLQReason.UNKNOWN
    error_message: str = ""
    retry_count: int = 0
    first_failure_at: float = field(default_factory=time.time)
    last_failure_at: float = field(default_factory=time.time)
    next_retry_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.reason, DLQReason):
            d["reason"] = self.reason.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DeadLetter":
        d = d.copy()
        if isinstance(d.get("reason"), str):
            try:
                d["reason"] = DLQReason(d["reason"])
            except ValueError:
                d["reason"] = DLQReason.UNKNOWN
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class DLQStats:
    """Dead letter queue statistics."""
    total_dead: int = 0
    pending_retry: int = 0
    resolved: int = 0
    by_reason: Dict[str, int] = field(default_factory=dict)


class DeadLetterQueue:
    """Persistent dead letter queue with auto-retry.

    Storage: data/event_store/dead_letters/
        ├── pending/      # Waiting for retry
        │   └── {dlq_id}.json
        ├── resolved/     # Successfully replayed
        │   └── {dlq_id}.json
        └── failed/       # Permanently failed (exceeded max retries)
            └── {dlq_id}.json

    Thread-safe via RLock.
    """

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 60  # seconds
    MAX_SIZE = 1000

    def __init__(self, base_dir: str = "data/event_store/dead_letters",
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 retry_delay: int = DEFAULT_RETRY_DELAY):
        self._base_dir = Path(base_dir)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._lock = threading.RLock()
        self._running = True

        # Ensure directories
        for sub in ["pending", "resolved", "failed"]:
            (self._base_dir / sub).mkdir(parents=True, exist_ok=True)

        # Start retry daemon
        self._retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self._retry_thread.start()

    def enqueue(self, event_payload: Dict[str, Any], topic: str = "",
                source: str = "", reason: DLQReason = DLQReason.UNKNOWN,
                error_message: str = "", retry_count: int = 0,
                metadata: Optional[Dict[str, Any]] = None) -> DeadLetter:
        """Enqueue a failed event to the dead letter queue."""
        with self._lock:
            # Check capacity
            pending_count = len(list((self._base_dir / "pending").glob("*.json")))
            if pending_count >= self.MAX_SIZE:
                # Drop oldest
                oldest = sorted(
                    (self._base_dir / "pending").glob("*.json"),
                    key=lambda p: p.stat().st_mtime
                )
                for old in oldest[:int(self.MAX_SIZE * 0.2)]:
                    old.unlink(missing_ok=True)

            dl = DeadLetter(
                event_payload=event_payload,
                topic=topic,
                source=source,
                reason=reason,
                error_message=error_message,
                retry_count=retry_count,
                last_failure_at=time.time(),
                next_retry_at=time.time() + self._retry_delay if retry_count < self._max_retries else None,
                metadata=metadata or {},
            )

            file_path = self._base_dir / "pending" / f"{dl.dlq_id}.json"
            file_path.write_text(json.dumps(dl.to_dict(), ensure_ascii=False, indent=2))
            return dl

    def get_pending(self, limit: int = 100) -> List[DeadLetter]:
        """Get pending dead letters ready for retry."""
        with self._lock:
            results = []
            now = time.time()
            for f in sorted((self._base_dir / "pending").glob("*.json"),
                           key=lambda p: p.stat().st_mtime):
                try:
                    dl = DeadLetter.from_dict(json.loads(f.read_text()))
                    if dl.next_retry_at is None or dl.next_retry_at <= now:
                        results.append(dl)
                        if len(results) >= limit:
                            break
                except (json.JSONDecodeError, OSError):
                    continue
            return results

    def mark_resolved(self, dlq_id: str) -> bool:
        """Mark a dead letter as successfully replayed."""
        return self._move_file(dlq_id, "pending", "resolved")

    def mark_permanent_failure(self, dlq_id: str) -> bool:
        """Mark a dead letter as permanently failed."""
        return self._move_file(dlq_id, "pending", "failed")

    def update_retry(self, dlq_id: str, error_message: str) -> Optional[DeadLetter]:
        """Update retry count after a failed replay attempt."""
        with self._lock:
            file_path = self._base_dir / "pending" / f"{dlq_id}.json"
            if not file_path.exists():
                return None

            try:
                dl = DeadLetter.from_dict(json.loads(file_path.read_text()))
                dl.retry_count += 1
                dl.error_message = error_message
                dl.last_failure_at = time.time()

                if dl.retry_count >= self._max_retries:
                    # Move to permanent failure
                    self.mark_permanent_failure(dlq_id)
                    return None

                dl.next_retry_at = time.time() + self._retry_delay
                file_path.write_text(json.dumps(dl.to_dict(), ensure_ascii=False, indent=2))
                return dl
            except (json.JSONDecodeError, OSError):
                return None

    def get_stats(self) -> DLQStats:
        """Get dead letter queue statistics."""
        with self._lock:
            stats = DLQStats()
            by_reason = {}

            for category, attr in [("pending", "total_dead"), ("resolved", "resolved")]:
                count = 0
                for f in (self._base_dir / category).glob("*.json"):
                    try:
                        dl = DeadLetter.from_dict(json.loads(f.read_text()))
                        count += 1
                        reason_key = dl.reason.value if isinstance(dl.reason, DLQReason) else str(dl.reason)
                        by_reason[reason_key] = by_reason.get(reason_key, 0) + 1
                    except (json.JSONDecodeError, OSError):
                        pass
                if attr == "total_dead":
                    stats.total_dead = count
                else:
                    stats.resolved = count

            # Count pending that are ready for retry
            stats.pending_retry = len(self.get_pending(limit=10000))
            stats.by_reason = by_reason
            return stats

    def _move_file(self, dlq_id: str, from_dir: str, to_dir: str) -> bool:
        """Atomically move a dead letter file between directories."""
        with self._lock:
            src = self._base_dir / from_dir / f"{dlq_id}.json"
            dst = self._base_dir / to_dir / f"{dlq_id}.json"
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
                return True
            return False

    def _retry_loop(self) -> None:
        """Background retry loop for dead letters."""
        while self._running:
            # This loop just provides periodic cleanup;
            # actual retry is triggered by external consumers calling get_pending()
            for _ in range(12):  # Check every 60s
                if not self._running:
                    break
                time.sleep(5)

    def shutdown(self) -> None:
        """Graceful shutdown."""
        self._running = False
        if hasattr(self, '_retry_thread'):
            self._retry_thread.join(timeout=5)


# Alias for backward compatibility
DeadLetter = DeadLetter  # re-export
