"""LLM Cache — response cache with hash-based deduplication (v2.3.1).

Caches LLM responses keyed by (system_prompt, user_message, model, temperature).
Reduces API calls and latency for repeated queries.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
import threading
from collections import OrderedDict
from typing import Optional, Dict, Any


class LLMCache:
    """Thread-safe LRU cache for LLM responses with TTL."""

    def __init__(self, max_size: int = 200, ttl_seconds: int = 3600,
                 persist_path: Optional[str] = None):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
        self._persist_path = persist_path
        if persist_path and os.path.exists(persist_path):
            self._load()

    def _key(self, system_prompt: str, user_message: str, model: str,
             temperature: float) -> str:
        content = f"{system_prompt}\x00{user_message}\x00{model}\x00{temperature}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, system_prompt: str, user_message: str, model: str,
            temperature: float = 0.7) -> Optional[Dict[str, Any]]:
        key = self._key(system_prompt, user_message, model, temperature)
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            entry = self._cache[key]
            if time.time() - entry["ts"] > self._ttl:
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            self._cache.move_to_end(key)  # LRU
            self._stats["hits"] += 1
            return entry["response"]

    def set(self, system_prompt: str, user_message: str, model: str,
            temperature: float, response: Dict[str, Any]):
        if not response.get("success"):
            return  # Don't cache failures
        key = self._key(system_prompt, user_message, model, temperature)
        with self._lock:
            self._cache[key] = {
                "ts": time.time(),
                "response": response,
            }
            self._cache.move_to_end(key)
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1
        if self._persist_path:
            self._save()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "hit_rate": round(hit_rate, 3),
            }

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _save(self):
        try:
            data = {k: v for k, v in self._cache.items()}
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _load(self):
        try:
            with open(self._persist_path) as f:
                data = json.load(f)
            with self._lock:
                self._cache = OrderedDict(data)
        except Exception:
            pass
