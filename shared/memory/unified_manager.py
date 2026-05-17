"""Unified Memory Manager for ClawShell v2.1.

Provides a single API over multiple memory types (episodic, semantic,
procedural, working, cache) backed by HNSW vector search.  Each memory
entry is stored with rich metadata including type, namespace, tags,
access level, importance, and optional expiration.

Features:
    - Thread-safe (``threading.RLock``)
    - HNSW-powered vector similarity search via ``HNSWVectorMemory``
    - Composite scoring: vector similarity × time decay × importance boost
    - Persistence to JSON metadata + HNSW index
    - Consolidation: expired-entry removal, duplicate merging, capacity eviction
    - Rich filtering by memory type, namespace, access level, and tags

Usage::

    from shared.memory.unified_manager import UnifiedMemoryManager

    mgr = UnifiedMemoryManager()
    mid = mgr.store(key="meeting", content="Discussed Q3 roadmap",
                    memory_type=MemoryType.EPISODIC, importance=0.8)
    results = mgr.search("Q3 roadmap", k=5)
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from shared.memory.hnsw_engine import (
    HNSWConfig,
    HNSWVectorMemory,
    embed_text_simple,
)


# ── Enums ────────────────────────────────────────────────────────────


class MemoryType(Enum):
    """Categories of stored memories."""
    EPISODIC = "episodic"        # Time-based events
    SEMANTIC = "semantic"        # Facts, knowledge
    PROCEDURAL = "procedural"    # How-to, skills
    WORKING = "working"          # Short-term operational
    CACHE = "cache"              # Temporary


class AccessLevel(Enum):
    """Visibility / sharing scope for a memory entry."""
    PRIVATE = "private"
    TEAM = "team"
    SWARM = "swarm"
    PUBLIC = "public"


# ── Memory Entry ─────────────────────────────────────────────────────


@dataclass
class MemoryEntry:
    """A single memory record managed by :class:`UnifiedMemoryManager`."""

    id: str
    key: str
    content: str
    memory_type: MemoryType
    namespace: str = "default"
    tags: List[str] = field(default_factory=list)
    access_level: AccessLevel = AccessLevel.PRIVATE
    importance: float = 0.5          # 0.0 – 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""             # ISO-8601
    updated_at: str = ""             # ISO-8601
    expires_at: Optional[str] = None # ISO-8601 or None
    references: List[str] = field(default_factory=list)
    content_hash: str = ""           # SHA-256 of content for dedup

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (enums → values)."""
        d = asdict(self)
        d["memory_type"] = self.memory_type.value
        d["access_level"] = self.access_level.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryEntry":
        """Deserialise from a plain dict."""
        d = dict(d)  # shallow copy
        d["memory_type"] = MemoryType(d["memory_type"])
        d["access_level"] = AccessLevel(d["access_level"])
        return cls(**d)


# ── Search Result ────────────────────────────────────────────────────


@dataclass
class UnifiedSearchResult:
    """A ranked result from :meth:`UnifiedMemoryManager.search`."""

    memory: MemoryEntry
    vector_score: float     # HNSW similarity (0-1)
    time_decay: float       # 0.95^hours (0-1)
    importance_boost: float # importance factor
    final_score: float      # composite: vector × time_decay × importance


# ── Unified Memory Manager ───────────────────────────────────────────


class UnifiedMemoryManager:
    """Single API over all ClawShell memory subsystems.

    Wraps :class:`HNSWVectorMemory` as the vector search backend and adds
    metadata-rich storage, composite scoring, persistence, and
    consolidation.
    """

    DEFAULT_MAX_ENTRIES: int = 50_000
    TIME_DECAY_BASE: float = 0.95       # per-hour decay factor
    IMPORTANCE_WEIGHT: float = 1.0      # multiplier for importance
    DUPLICATE_THRESHOLD: float = 0.001  # cosine distance for dedup

    def __init__(
        self,
        *,
        dim: int = 384,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        space: str = "cosine",
        persist_path: Optional[str] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._entries: Dict[str, MemoryEntry] = {}       # id → MemoryEntry
        self._key_index: Dict[str, str] = {}             # key → id (unique keys)
        self._persist_path = persist_path
        self._max_entries = max_entries

        # Give HNSW extra capacity so consolidation can run *after*
        # the logical limit is exceeded (entries accumulate, then get pruned).
        hnsw_capacity = max(max_entries + 100, max_entries * 2)
        hnsw_cfg = HNSWConfig(
            dim=dim,
            max_elements=hnsw_capacity,
            space=space,
        )
        self._vector = HNSWVectorMemory(hnsw_cfg)

    # ── Properties ──────────────────────────────────────────────────

    @property
    def size(self) -> int:
        """Number of memory entries currently stored."""
        with self._lock:
            return len(self._entries)

    @property
    def ids(self) -> List[str]:
        """All stored memory IDs."""
        with self._lock:
            return list(self._entries.keys())

    # ── Core API ────────────────────────────────────────────────────

    def store(
        self,
        *,
        key: str,
        content: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        namespace: str = "default",
        tags: Optional[List[str]] = None,
        access_level: AccessLevel = AccessLevel.PRIVATE,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[str] = None,
        references: Optional[List[str]] = None,
        entry_id: Optional[str] = None,
    ) -> str:
        """Store a new memory entry.  Returns the entry ID.

        If *key* already exists the existing entry is **updated** (its
        vector embedding is refreshed, timestamps are bumped).
        """
        now = _utcnow()
        content_hash = _content_hash(content)

        with self._lock:
            # Check if key already exists → update path
            existing_id = self._key_index.get(key)
            if existing_id and existing_id in self._entries:
                entry = self._entries[existing_id]
                entry.content = content
                entry.memory_type = memory_type
                entry.namespace = namespace
                entry.tags = tags or []
                entry.access_level = access_level
                entry.importance = _clamp01(importance)
                entry.metadata = metadata or {}
                entry.updated_at = now
                entry.expires_at = expires_at
                entry.references = references or []
                entry.content_hash = content_hash
                # Re-embed
                vec = embed_text_simple(content, dim=self._vector.config.dim)
                self._vector.add(existing_id, vec, entry.to_dict())
                self._maybe_persist()
                return existing_id

            # New entry
            eid = entry_id or uuid.uuid4().hex[:16]
            entry = MemoryEntry(
                id=eid,
                key=key,
                content=content,
                memory_type=memory_type,
                namespace=namespace,
                tags=tags or [],
                access_level=access_level,
                importance=_clamp01(importance),
                metadata=metadata or {},
                created_at=now,
                updated_at=now,
                expires_at=expires_at,
                references=references or [],
                content_hash=content_hash,
            )
            self._entries[eid] = entry
            self._key_index[key] = eid

            vec = embed_text_simple(content, dim=self._vector.config.dim)
            self._vector.add(eid, vec, entry.to_dict())

        self._maybe_persist()
        return eid

    def retrieve(self, id_or_key: str) -> Optional[MemoryEntry]:
        """Retrieve a memory by ID *or* key.

        Looks up by ID first, then by key.  Returns a **copy** of the
        entry (or ``None``).
        """
        with self._lock:
            entry = self._entries.get(id_or_key)
            if entry is not None:
                return _deep_copy_entry(entry)
            eid = self._key_index.get(id_or_key)
            if eid:
                entry = self._entries.get(eid)
                if entry is not None:
                    return _deep_copy_entry(entry)
            return None

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        memory_types: Optional[List[MemoryType]] = None,
        namespace: Optional[str] = None,
        access_level: Optional[AccessLevel] = None,
        tags: Optional[List[str]] = None,
    ) -> List[UnifiedSearchResult]:
        """Search memories with composite scoring.

        Scoring::

            final = vector_score × (0.95 ^ hours_old) × (0.5 + importance/2)

        Filters are applied after vector retrieval.
        """
        with self._lock:
            if not self._entries:
                return []

        query_vec = embed_text_simple(query, dim=self._vector.config.dim)

        # Build a filter closure for the HNSW backend
        def _filter(vid: str, meta: dict) -> bool:
            entry = self._entries.get(vid)
            if entry is None:
                return False
            # Expired?
            if entry.expires_at and _is_expired(entry.expires_at):
                return False
            if memory_types and entry.memory_type not in memory_types:
                return False
            if namespace and entry.namespace != namespace:
                return False
            if access_level and entry.access_level != access_level:
                return False
            if tags and not _has_tags(entry.tags, tags):
                return False
            return True

        with self._lock:
            n = len(self._entries)
            if n == 0:
                return []
            fetch_k = min(k * 4, n)
            raw_results = self._vector.search(
                query_vec, k=fetch_k, filter_fn=_filter,
            )

        now = time.time()
        results: List[UnifiedSearchResult] = []
        for sr in raw_results:
            entry = self._entries.get(sr.id)
            if entry is None:
                continue
            hours = _hours_since(entry.updated_at, now)
            time_decay = self.TIME_DECAY_BASE ** hours
            importance_boost = 0.5 + entry.importance / 2.0
            final_score = sr.score * time_decay * importance_boost
            results.append(UnifiedSearchResult(
                memory=_deep_copy_entry(entry),
                vector_score=sr.score,
                time_decay=time_decay,
                importance_boost=importance_boost,
                final_score=final_score,
            ))

        # Sort by composite score descending
        results.sort(key=lambda r: r.final_score, reverse=True)
        return results[:k]

    def delete(self, id_or_key: str) -> bool:
        """Delete a memory entry by ID or key.  Returns ``True`` on success."""
        with self._lock:
            eid: Optional[str] = None
            if id_or_key in self._entries:
                eid = id_or_key
            elif id_or_key in self._key_index:
                eid = self._key_index[id_or_key]
            if eid is None or eid not in self._entries:
                return False

            entry = self._entries.pop(eid)
            self._key_index.pop(entry.key, None)
            self._vector.delete(eid)

        self._maybe_persist()
        return True

    # ── Consolidation ───────────────────────────────────────────────

    def consolidate(self) -> Dict[str, int]:
        """Run housekeeping: expire, deduplicate, and evict if needed.

        Returns a summary dict with counts of removed/expired/merged entries.
        """
        expired_count = 0
        merged_count = 0
        evicted_count = 0

        with self._lock:
            # 1. Remove expired entries
            expired_ids = [
                eid for eid, entry in self._entries.items()
                if entry.expires_at and _is_expired(entry.expires_at)
            ]
            for eid in expired_ids:
                self._delete_internal(eid)
            expired_count = len(expired_ids)

            # 2. Merge duplicates (same content_hash)
            hash_map: Dict[str, List[str]] = {}
            for eid, entry in self._entries.items():
                hash_map.setdefault(entry.content_hash, []).append(eid)
            for chash, eids in hash_map.items():
                if len(eids) <= 1:
                    continue
                # Keep the one with highest importance, discard the rest
                eids_sorted = sorted(
                    eids,
                    key=lambda e: self._entries[e].importance,
                    reverse=True,
                )
                for dup in eids_sorted[1:]:
                    self._delete_internal(dup)
                    merged_count += 1

            # 3. Evict low-score entries if over capacity
            if len(self._entries) > self._max_entries:
                now = time.time()
                scored: List[Tuple[str, float]] = []
                for eid, entry in self._entries.items():
                    hours = _hours_since(entry.updated_at, now)
                    score = (self.TIME_DECAY_BASE ** hours) * (
                        0.5 + entry.importance / 2.0
                    )
                    scored.append((eid, score))
                scored.sort(key=lambda x: x[1])  # lowest score first
                excess = len(self._entries) - self._max_entries
                for eid, _ in scored[:excess]:
                    self._delete_internal(eid)
                    evicted_count += 1

        self._maybe_persist()
        return {
            "expired": expired_count,
            "merged": merged_count,
            "evicted": evicted_count,
        }

    # ── Persistence ─────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Persist all entries to *path*.json and the HNSW index alongside."""
        with self._lock:
            payload = {
                "version": "2.1.0",
                "max_entries": self._max_entries,
                "entries": {eid: e.to_dict() for eid, e in self._entries.items()},
                "key_index": dict(self._key_index),
            }
            json_path = f"{path}.json"
            os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)

            # Save HNSW index with same base path
            self._vector.save(path)

    @classmethod
    def load(
        cls,
        path: str,
        *,
        persist_path: Optional[str] = None,
    ) -> "UnifiedMemoryManager":
        """Load a previously saved manager from disk."""
        json_path = f"{path}.json"
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Unified memory JSON not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)

        # Load HNSW vector index
        vector = HNSWVectorMemory.load(path)

        instance = cls.__new__(cls)
        instance._lock = threading.RLock()
        instance._persist_path = persist_path
        instance._max_entries = payload.get("max_entries", vector.config.max_elements // 2)
        instance._vector = vector
        instance._entries = {
            eid: MemoryEntry.from_dict(ed)
            for eid, ed in payload["entries"].items()
        }
        instance._key_index = dict(payload.get("key_index", {}))
        return instance

    # ── Private helpers ─────────────────────────────────────────────

    def _delete_internal(self, eid: str) -> None:
        """Delete an entry **without** acquiring the lock (caller must hold it)."""
        entry = self._entries.pop(eid, None)
        if entry is not None:
            self._key_index.pop(entry.key, None)
        self._vector.delete(eid)

    def _maybe_persist(self) -> None:
        if self._persist_path:
            try:
                self.save(self._persist_path)
            except Exception:
                pass  # best-effort

    def __repr__(self) -> str:
        return (
            f"UnifiedMemoryManager(entries={self.size}, "
            f"max={self._max_entries}, dim={self._vector.config.dim})"
        )


# ── Module-level helpers ─────────────────────────────────────────────


def _utcnow() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _content_hash(content: str) -> str:
    """SHA-256 hex digest of *content*."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _is_expired(expires_at: str) -> bool:
    """Return ``True`` if *expires_at* (ISO-8601) is in the past."""
    try:
        exp = datetime.fromisoformat(expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp
    except Exception:
        return False


def _hours_since(iso_ts: str, now_epoch: float) -> float:
    """Hours elapsed since *iso_ts* (positive number)."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        elapsed = now_epoch - dt.timestamp()
        return max(0.0, elapsed / 3600.0)
    except Exception:
        return 0.0


def _has_tags(entry_tags: List[str], required: List[str]) -> bool:
    """Return ``True`` if *entry_tags* contains **all** *required* tags."""
    tag_set = set(entry_tags)
    return all(t in tag_set for t in required)


def _deep_copy_entry(entry: MemoryEntry) -> MemoryEntry:
    """Return a shallow-ish copy so callers can't mutate internal state."""
    return MemoryEntry(
        id=entry.id,
        key=entry.key,
        content=entry.content,
        memory_type=entry.memory_type,
        namespace=entry.namespace,
        tags=list(entry.tags),
        access_level=entry.access_level,
        importance=entry.importance,
        metadata=dict(entry.metadata),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        expires_at=entry.expires_at,
        references=list(entry.references),
        content_hash=entry.content_hash,
    )
