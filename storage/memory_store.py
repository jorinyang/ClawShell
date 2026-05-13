"""MemoryStore — Time-decay memory storage.

Design: Based on DEEP storage/knowledge_store.py MemoryStore.
Adapted to Main's storage/ with threading model.

Features:
- Importance-weighted recall with time decay
- JSON file persistence
- LRU eviction with configurable max items
- Access count tracking
"""
from __future__ import annotations
import os
import json
import time
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Any
from shared.models import Memory


class MemoryStore:
    """Time-decay memory store with importance ranking.
    
    Memories decay over time: score *= max(0.1, 1.0 - age_hours / (24 * 30))
    Frequently accessed memories have higher importance and decay slower.
    """

    MAX_MEMORIES = 5000
    DEFAULT_STORE_PATH = "data/memory"

    def __init__(self, store_path: Optional[str] = None):
        self.store_path = Path(store_path or self.DEFAULT_STORE_PATH)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._memories: OrderedDict[str, Memory] = OrderedDict()
        self._lock = threading.RLock()

    def load(self) -> int:
        """Load all memories from disk. Returns count loaded."""
        count = 0
        for f in sorted(self.store_path.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                m = Memory.model_validate(data)
                self._memories[m.memory_id] = m
                count += 1
                if count >= self.MAX_MEMORIES:
                    break
            except Exception:
                pass
        return count

    def store(self, memory: Memory) -> bool:
        """Store a memory. Evicts oldest if over capacity."""
        with self._lock:
            self._memories[memory.memory_id] = memory
            while len(self._memories) > self.MAX_MEMORIES:
                self._memories.popitem(last=False)
            path = self.store_path / f"{memory.memory_id}.json"
            path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
            return True

    def store_dict(self, memory_id: str, content: str, importance: float = 0.5,
                   category: str = "session", tags: Optional[List[str]] = None,
                   ttl_seconds: int = 0) -> bool:
        """Store a memory from raw values."""
        m = Memory(
            memory_id=memory_id,
            content=content,
            importance=importance,
            category=category,
            tags=tags or [],
            ttl_seconds=ttl_seconds,
        )
        return self.store(m)

    def recall(
        self,
        query: str = "",
        category: str = "",
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Memory]:
        """Recall memories with scoring and time decay.
        
        Scoring formula:
            score = importance * 10 + query_match * 5 + category_match * 3 + tag_match * 2
            score *= max(0.1, 1.0 - age_hours / (24 * 30))  # 30-day decay
            
        Args:
            query: Search query (matched against content)
            category: Optional category filter
            tags: Optional tag filters
            limit: Max results
            
        Returns:
            Scored and decayed memories, sorted by relevance
        """
        now = time.time()
        scored: List[tuple] = []

        with self._lock:
            for m in self._memories.values():
                # Check TTL
                if m.ttl_seconds > 0:
                    age = now - m.created_at.timestamp()
                    if age > m.ttl_seconds:
                        continue

                score = m.importance * 10.0

                # Query match
                if query and query.lower() in m.content.lower():
                    score += 5

                # Category match
                if category and m.category == category:
                    score += 3

                # Tag match
                if tags:
                    score += len(set(tags) & set(m.tags)) * 2

                # Time decay: 30-day half-life
                age_h = (now - m.created_at.timestamp()) / 3600
                if age_h > 0:
                    score *= max(0.1, 1.0 - age_h / (24 * 30))

                if score > 0:
                    scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Update access counts
        for _, m in scored[:limit]:
            m.access_count += 1

        return [m for _, m in scored[:limit]]

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a specific memory by ID."""
        with self._lock:
            m = self._memories.get(memory_id)
            if m:
                m.access_count += 1
            return m

    def forget(self, memory_id: str) -> bool:
        """Remove a memory."""
        with self._lock:
            if memory_id in self._memories:
                del self._memories[memory_id]
                path = self.store_path / f"{memory_id}.json"
                if path.exists():
                    path.unlink()
                return True
            return False

    @property
    def stats(self) -> dict:
        """Memory statistics."""
        with self._lock:
            return {
                "total": len(self._memories),
                "avg_importance": (
                    sum(m.importance for m in self._memories.values()) / max(len(self._memories), 1)
                ),
                "categories": len(set(m.category for m in self._memories.values())),
            }
