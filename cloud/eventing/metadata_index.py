"""Metadata Index — Temporal index for EventStore queries.

Design: Based on MacOS v2.0 event_store/metadata_index.py.
Speed up event queries by maintaining in-memory temporal + category indices.
"""
from __future__ import annotations
import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Any


class MetadataIndex:
    """Temporal and categorical index for EventStore.
    
    Maintains:
    - Time-based buckets (hourly) for fast time-range queries
    - Category-based indices for fast topic filtering
    - Source-based indices for node-specific queries
    """
    
    MAX_BUCKET_AGE = 7 * 24 * 3600  # 7 days
    
    def __init__(self):
        self._lock = threading.RLock()
        # time_bucket → [event_ids]
        self._time_index: Dict[int, List[str]] = defaultdict(list)
        # category → [event_ids]
        self._category_index: Dict[str, List[str]] = defaultdict(list)
        # source → [event_ids]
        self._source_index: Dict[str, List[str]] = defaultdict(list)
        self._total_indexed = 0
    
    def index_event(self, event_id: str, event: dict):
        """Index a single event."""
        with self._lock:
            ts = event.get("timestamp", time.time())
            bucket = int(ts // 3600)  # Hourly buckets
            
            self._time_index[bucket].append(event_id)
            
            category = event.get("category", event.get("event_type", "unknown").split(".")[0])
            self._category_index[category].append(event_id)
            
            source = event.get("source", "unknown")
            self._source_index[source].append(event_id)
            
            self._total_indexed += 1
    
    def index_batch(self, events: Dict[str, dict]):
        """Index a batch of events."""
        with self._lock:
            for event_id, event in events.items():
                self.index_event(event_id, event)
    
    def query_by_time(self, since: float, until: Optional[float] = None) -> List[str]:
        """Get event IDs in time range."""
        until = until or time.time()
        with self._lock:
            start_bucket = int(since // 3600)
            end_bucket = int(until // 3600)
            event_ids = []
            for bucket in range(start_bucket, end_bucket + 1):
                event_ids.extend(self._time_index.get(bucket, []))
            return event_ids
    
    def query_by_category(self, category: str) -> List[str]:
        """Get event IDs by category."""
        with self._lock:
            return list(self._category_index.get(category, []))
    
    def query_by_source(self, source: str) -> List[str]:
        """Get event IDs by source."""
        with self._lock:
            return list(self._source_index.get(source, []))
    
    def cleanup(self):
        """Remove expired bucket entries."""
        cutoff = int((time.time() - self.MAX_BUCKET_AGE) // 3600)
        with self._lock:
            expired = [b for b in self._time_index if b < cutoff]
            for bucket in expired:
                del self._time_index[bucket]
    
    @property
    def stats(self) -> dict:
        """Index statistics."""
        with self._lock:
            return {
                "total_indexed": self._total_indexed,
                "time_buckets": len(self._time_index),
                "categories": len(self._category_index),
                "sources": len(self._source_index),
            }
