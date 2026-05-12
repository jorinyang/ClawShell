"""Priority Queue — heap-based ordering for event processing.

Events are ordered by priority level: CRITICAL > HIGH > MEDIUM > LOW.
Within same priority, FIFO order is maintained via insertion counter.

Design: stdlib-only (heapq), RLock thread-safe.
"""

from __future__ import annotations

import heapq
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def weight(self) -> int:
        """Lower weight = higher priority (for min-heap)."""
        return {Priority.CRITICAL: 0, Priority.HIGH: 1,
                Priority.MEDIUM: 2, Priority.LOW: 3}[self]


@dataclass(order=True)
class PQItem:
    """Heap-ordered priority queue item."""
    priority_weight: int = 99      # Sort key (auto-set from priority)
    insertion_order: int = 0       # Tiebreaker for same priority
    item_id: str = field(compare=False, default="")
    priority: Priority = field(compare=False, default=Priority.MEDIUM)
    payload: Any = field(compare=False, default=None)
    enqueued_at: float = field(compare=False, default_factory=time.time)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)


class PriorityQueue:
    """Thread-safe priority queue backed by heapq.

    Lower priority_weight = higher priority (CRITICAL=0, LOW=3).
    FIFO within same priority via insertion_order counter.
    """

    def __init__(self, max_size: int = 10000):
        self._heap: List[PQItem] = []
        self._lock = threading.RLock()
        self._counter = 0
        self._max_size = max_size
        self._total_enqueued = 0
        self._total_dequeued = 0

    def enqueue(self, payload: Any, priority: Priority = Priority.MEDIUM,
                item_id: str = "", metadata: Optional[Dict[str, Any]] = None) -> PQItem:
        """Add an item to the priority queue.

        If the queue is full, drops the lowest-priority item.
        """
        with self._lock:
            self._counter += 1
            self._total_enqueued += 1

            item = PQItem(
                priority_weight=priority.weight,
                insertion_order=self._counter,
                item_id=item_id or str(self._counter),
                priority=priority,
                payload=payload,
                metadata=metadata or {},
            )

            if len(self._heap) >= self._max_size:
                # Remove lowest priority item (highest weight)
                if self._heap and self._heap[-1].priority_weight <= priority.weight:
                    self._heap.pop()  # Drop lowest-priority

            heapq.heappush(self._heap, item)
            return item

    def dequeue(self) -> Optional[PQItem]:
        """Remove and return the highest-priority item."""
        with self._lock:
            if not self._heap:
                return None
            self._total_dequeued += 1
            return heapq.heappop(self._heap)

    def peek(self) -> Optional[PQItem]:
        """Return the highest-priority item without removing it."""
        with self._lock:
            return self._heap[0] if self._heap else None

    def size(self) -> int:
        with self._lock:
            return len(self._heap)

    def is_empty(self) -> bool:
        return self.size() == 0

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            by_priority = {}
            for item in self._heap:
                p = item.priority.value
                by_priority[p] = by_priority.get(p, 0) + 1
            return {
                "size": len(self._heap),
                "max_size": self._max_size,
                "total_enqueued": self._total_enqueued,
                "total_dequeued": self._total_dequeued,
                "by_priority": by_priority,
            }

    def drain_all(self) -> List[PQItem]:
        """Dequeue all items in priority order."""
        with self._lock:
            items = []
            while self._heap:
                items.append(heapq.heappop(self._heap))
            self._total_dequeued += len(items)
            return items
