"""GenomeCacheManager — LRU cache with TTL for genome knowledge.

Thread-safe (RLock), tracks hit rate, size, evictions.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class GenomeCacheManager:
    """LRU cache with TTL expiration.

    Thread-safe with RLock. Tracks hit rate, evictions, and size.
    """

    def __init__(self, max_size: int = 1000):
        self._max_size = max_size
        self._cache: OrderedDict[str, tuple] = OrderedDict()  # key -> (value, expiry)
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache. Returns None if missing or expired."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            value, expiry = self._cache[key]
            if expiry and time.time() > expiry:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: str, value: Any, ttl_seconds: int = 300):
        """Put a value into cache with TTL.

        Args:
            key: Cache key
            value: Value to store
            ttl_seconds: Time-to-live in seconds (0 = no expiry)
        """
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._evictions += 1

            expiry = time.time() + ttl_seconds if ttl_seconds > 0 else None
            self._cache[key] = (value, expiry)

    def invalidate(self, key: str) -> bool:
        """Remove a key from cache. Returns True if it existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "evictions": self._evictions,
            }
