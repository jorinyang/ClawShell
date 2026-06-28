"""Edge Dead Letter Queue — local failed event handling."""

from enum import Enum
import threading, time, uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

class DLQReason(str, Enum):
    MAX_RETRIES = "max_retries"
    HANDLER_ERROR = "handler_error"
    TIMEOUT = "timeout"

@dataclass
class DeadLetter:
    dlq_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    data: Any = None
    reason: DLQReason = DLQReason.HANDLER_ERROR
    error_message: str = ""
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)

class EdgeDeadLetterQueue:
    def __init__(self, max_size: int = 500):
        self._lock = threading.RLock()
        self._items: List[DeadLetter] = []
        self._max_size = max_size

    def enqueue(self, event_type: str, data: Any = None,
                reason: DLQReason = DLQReason.HANDLER_ERROR,
                error_message: str = "") -> DeadLetter:
        with self._lock:
            if len(self._items) >= self._max_size:
                self._items.pop(0)
            dl = DeadLetter(event_type=event_type, data=data, reason=reason, error_message=error_message)
            self._items.append(dl)
            return dl

    def get_pending(self, limit: int = 50) -> List[DeadLetter]:
        with self._lock:
            return self._items[:limit]

    def remove(self, dlq_id: str) -> bool:
        with self._lock:
            for i, item in enumerate(self._items):
                if item.dlq_id == dlq_id:
                    self._items.pop(i)
                    return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"size": len(self._items), "max_size": self._max_size}
