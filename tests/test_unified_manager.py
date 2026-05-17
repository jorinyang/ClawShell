"""Tests for the Unified Memory Manager.

Run with: python -m pytest tests/test_unified_manager.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.memory.unified_manager import (
    AccessLevel,
    MemoryEntry,
    MemoryType,
    UnifiedMemoryManager,
    UnifiedSearchResult,
    _content_hash,
    _is_expired,
    _utcnow,
)


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_manager(**kwargs) -> UnifiedMemoryManager:
    """Create a small UnifiedMemoryManager for testing."""
    defaults = dict(dim=128, max_entries=500)
    defaults.update(kwargs)
    return UnifiedMemoryManager(**defaults)


def _future_iso(hours: float = 24.0) -> str:
    """Return an ISO timestamp *hours* in the future."""
    dt = datetime.now(timezone.utc) + timedelta(hours=hours)
    return dt.isoformat()


def _past_iso(hours: float = 1.0) -> str:
    """Return an ISO timestamp *hours* in the past."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.isoformat()


# ── Enums & Data Classes ─────────────────────────────────────────────


class TestMemoryType:
    def test_values(self):
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"
        assert MemoryType.WORKING.value == "working"
        assert MemoryType.CACHE.value == "cache"

    def test_roundtrip(self):
        for mt in MemoryType:
            assert MemoryType(mt.value) == mt


class TestAccessLevel:
    def test_values(self):
        assert AccessLevel.PRIVATE.value == "private"
        assert AccessLevel.TEAM.value == "team"
        assert AccessLevel.SWARM.value == "swarm"
        assert AccessLevel.PUBLIC.value == "public"

    def test_roundtrip(self):
        for al in AccessLevel:
            assert AccessLevel(al.value) == al


class TestMemoryEntry:
    def test_to_dict_roundtrip(self):
        entry = MemoryEntry(
            id="abc123",
            key="test_key",
            content="hello world",
            memory_type=MemoryType.SEMANTIC,
            namespace="ns",
            tags=["tag1", "tag2"],
            access_level=AccessLevel.TEAM,
            importance=0.8,
            metadata={"extra": 42},
            created_at="2025-01-01T00:00:00+00:00",
            updated_at="2025-01-01T00:00:00+00:00",
            expires_at=None,
            references=["ref1"],
            content_hash="abc",
        )
        d = entry.to_dict()
        assert d["memory_type"] == "semantic"
        assert d["access_level"] == "team"
        restored = MemoryEntry.from_dict(d)
        assert restored.id == entry.id
        assert restored.memory_type == MemoryType.SEMANTIC
        assert restored.access_level == AccessLevel.TEAM
        assert restored.tags == ["tag1", "tag2"]
        assert restored.importance == 0.8


# ── Store & Retrieve ─────────────────────────────────────────────────


class TestStoreRetrieve:
    def test_store_returns_id(self):
        mgr = _make_manager()
        eid = mgr.store(key="k1", content="Hello world")
        assert isinstance(eid, str)
        assert len(eid) > 0

    def test_retrieve_by_id(self):
        mgr = _make_manager()
        eid = mgr.store(key="k1", content="Hello world")
        entry = mgr.retrieve(eid)
        assert entry is not None
        assert entry.key == "k1"
        assert entry.content == "Hello world"

    def test_retrieve_by_key(self):
        mgr = _make_manager()
        mgr.store(key="unique_key", content="Some content")
        entry = mgr.retrieve("unique_key")
        assert entry is not None
        assert entry.content == "Some content"

    def test_retrieve_nonexistent(self):
        mgr = _make_manager()
        assert mgr.retrieve("no_such_id") is None

    def test_store_with_all_fields(self):
        mgr = _make_manager()
        eid = mgr.store(
            key="full",
            content="Full entry",
            memory_type=MemoryType.PROCEDURAL,
            namespace="ops",
            tags=["deploy", "aws"],
            access_level=AccessLevel.SWARM,
            importance=0.9,
            metadata={"region": "us-east-1"},
            expires_at=_future_iso(48),
            references=["doc1", "doc2"],
        )
        entry = mgr.retrieve(eid)
        assert entry is not None
        assert entry.memory_type == MemoryType.PROCEDURAL
        assert entry.namespace == "ops"
        assert "deploy" in entry.tags
        assert entry.access_level == AccessLevel.SWARM
        assert entry.importance == 0.9
        assert entry.metadata["region"] == "us-east-1"
        assert entry.references == ["doc1", "doc2"]

    def test_store_update_existing_key(self):
        mgr = _make_manager()
        eid1 = mgr.store(key="updatable", content="Version 1")
        eid2 = mgr.store(key="updatable", content="Version 2")
        assert eid1 == eid2  # same ID, updated in place
        entry = mgr.retrieve(eid1)
        assert entry is not None
        assert entry.content == "Version 2"

    def test_size_and_ids(self):
        mgr = _make_manager()
        assert mgr.size == 0
        mgr.store(key="a", content="A")
        mgr.store(key="b", content="B")
        assert mgr.size == 2
        assert len(mgr.ids) == 2

    def test_retrieve_returns_copy(self):
        """Mutating the returned entry should not affect the store."""
        mgr = _make_manager()
        eid = mgr.store(key="c", content="Original")
        entry = mgr.retrieve(eid)
        assert entry is not None
        entry.content = "HACKED"
        original = mgr.retrieve(eid)
        assert original is not None
        assert original.content == "Original"

    def test_custom_entry_id(self):
        mgr = _make_manager()
        eid = mgr.store(key="custom", content="C", entry_id="my_custom_id")
        assert eid == "my_custom_id"
        assert mgr.retrieve("my_custom_id") is not None


# ── Search ───────────────────────────────────────────────────────────


class TestSearch:
    def test_search_basic(self):
        mgr = _make_manager()
        mgr.store(key="py", content="Python is a programming language")
        mgr.store(key="js", content="JavaScript runs in the browser")
        results = mgr.search("Python language", k=5)
        assert len(results) >= 1
        # Python entry should rank higher
        assert results[0].memory.key == "py"

    def test_search_returns_top_k(self):
        mgr = _make_manager()
        for i in range(20):
            mgr.store(key=f"item{i}", content=f"Unique topic number {i} about science")
        results = mgr.search("science topic", k=5)
        assert len(results) <= 5

    def test_search_empty_store(self):
        mgr = _make_manager()
        results = mgr.search("anything", k=5)
        assert results == []

    def test_search_composite_scoring_fields(self):
        mgr = _make_manager()
        mgr.store(key="s1", content="composite scoring test")
        results = mgr.search("composite scoring", k=1)
        assert len(results) == 1
        r = results[0]
        assert 0 <= r.vector_score <= 1
        assert 0 < r.time_decay <= 1  # recently created, so ~1
        assert 0.5 <= r.importance_boost <= 1.0
        assert r.final_score > 0

    def test_search_filter_by_memory_type(self):
        mgr = _make_manager()
        mgr.store(key="ep1", content="Meeting notes from Tuesday",
                   memory_type=MemoryType.EPISODIC)
        mgr.store(key="sem1", content="Meeting is a formal gathering",
                   memory_type=MemoryType.SEMANTIC)
        results = mgr.search("meeting", k=5,
                             memory_types=[MemoryType.EPISODIC])
        for r in results:
            assert r.memory.memory_type == MemoryType.EPISODIC

    def test_search_filter_by_namespace(self):
        mgr = _make_manager()
        mgr.store(key="n1", content="Deploy script for production",
                   namespace="ops")
        mgr.store(key="n2", content="Deploy marketing campaign",
                   namespace="marketing")
        results = mgr.search("deploy", k=5, namespace="ops")
        for r in results:
            assert r.memory.namespace == "ops"

    def test_search_filter_by_access_level(self):
        mgr = _make_manager()
        mgr.store(key="pub", content="Public announcement about event",
                   access_level=AccessLevel.PUBLIC)
        mgr.store(key="priv", content="Private announcement for staff",
                   access_level=AccessLevel.PRIVATE)
        results = mgr.search("announcement", k=5,
                             access_level=AccessLevel.PUBLIC)
        for r in results:
            assert r.memory.access_level == AccessLevel.PUBLIC

    def test_search_filter_by_tags(self):
        mgr = _make_manager()
        mgr.store(key="t1", content="Docker container setup guide",
                   tags=["docker", "devops"])
        mgr.store(key="t2", content="Docker whale mascot",
                   tags=["fun"])
        results = mgr.search("docker", k=5, tags=["devops"])
        for r in results:
            assert "devops" in r.memory.tags

    def test_search_filter_combined(self):
        mgr = _make_manager()
        mgr.store(key="c1", content="Q3 budget review meeting",
                   memory_type=MemoryType.EPISODIC,
                   namespace="finance",
                   tags=["budget", "q3"],
                   access_level=AccessLevel.TEAM,
                   importance=0.9)
        mgr.store(key="c2", content="Q3 marketing plan",
                   memory_type=MemoryType.SEMANTIC,
                   namespace="marketing")
        results = mgr.search(
            "Q3", k=10,
            memory_types=[MemoryType.EPISODIC],
            namespace="finance",
            tags=["budget"],
        )
        assert len(results) >= 1
        assert results[0].memory.key == "c1"

    def test_search_not_filtering_expired(self):
        mgr = _make_manager()
        mgr.store(key="alive", content="This is still valid content")
        mgr.store(key="dead", content="This expired content",
                   expires_at=_past_iso(2))
        results = mgr.search("content", k=10)
        keys = [r.memory.key for r in results]
        assert "alive" in keys
        assert "dead" not in keys

    def test_search_importance_boosts_ranking(self):
        """Higher importance entries should rank higher (all else equal)."""
        mgr = _make_manager()
        mgr.store(key="low", content="quantum computing advances today",
                   importance=0.1)
        mgr.store(key="high", content="quantum computing advances today",
                   importance=1.0)
        # Same content → same vector score and time decay,
        # but importance differs
        results = mgr.search("quantum computing", k=2)
        assert len(results) == 2
        assert results[0].memory.key == "high"

    def test_search_result_memory_is_copy(self):
        mgr = _make_manager()
        mgr.store(key="orig", content="Original text")
        results = mgr.search("original", k=1)
        if results:
            results[0].memory.content = "MODIFIED"
            again = mgr.retrieve("orig")
            assert again is not None
            assert again.content == "Original text"


# ── Delete ───────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_by_id(self):
        mgr = _make_manager()
        eid = mgr.store(key="del", content="Delete me")
        assert mgr.delete(eid) is True
        assert mgr.retrieve(eid) is None
        assert mgr.size == 0

    def test_delete_by_key(self):
        mgr = _make_manager()
        mgr.store(key="del_key", content="Delete by key")
        assert mgr.delete("del_key") is True
        assert mgr.size == 0

    def test_delete_nonexistent(self):
        mgr = _make_manager()
        assert mgr.delete("ghost") is False

    def test_delete_removes_key_index(self):
        mgr = _make_manager()
        eid = mgr.store(key="dkey", content="Indexed entry")
        mgr.delete(eid)
        assert mgr.retrieve("dkey") is None

    def test_delete_then_store_same_key(self):
        mgr = _make_manager()
        mgr.store(key="recycled", content="First")
        mgr.delete("recycled")
        new_id = mgr.store(key="recycled", content="Second")
        entry = mgr.retrieve(new_id)
        assert entry is not None
        assert entry.content == "Second"


# ── Consolidation ────────────────────────────────────────────────────


class TestConsolidation:
    def test_removes_expired(self):
        mgr = _make_manager()
        mgr.store(key="good", content="Still here", expires_at=_future_iso(100))
        mgr.store(key="expired1", content="Gone", expires_at=_past_iso(1))
        mgr.store(key="expired2", content="Also gone", expires_at=_past_iso(5))
        summary = mgr.consolidate()
        assert summary["expired"] == 2
        assert mgr.size == 1
        assert mgr.retrieve("good") is not None

    def test_merges_duplicates(self):
        mgr = _make_manager()
        content = "This exact content appears twice"
        mgr.store(key="a", content=content, importance=0.3)
        mgr.store(key="b", content=content, importance=0.9)
        summary = mgr.consolidate()
        assert summary["merged"] == 1
        assert mgr.size == 1
        # Should keep the one with higher importance
        remaining = mgr.retrieve("b")
        assert remaining is not None

    def test_evicts_low_score_when_over_capacity(self):
        mgr = _make_manager(max_entries=5)
        for i in range(8):
            mgr.store(key=f"item{i}", content=f"Item {i} about topic Z",
                       importance=i / 10.0)
        assert mgr.size == 8  # over capacity
        summary = mgr.consolidate()
        assert summary["evicted"] > 0
        assert mgr.size <= 5

    def test_consolidate_noop_when_clean(self):
        mgr = _make_manager()
        mgr.store(key="ok", content="Everything is fine")
        summary = mgr.consolidate()
        assert summary == {"expired": 0, "merged": 0, "evicted": 0}
        assert mgr.size == 1

    def test_consolidate_preserves_non_expired(self):
        mgr = _make_manager()
        mgr.store(key="alive", content="Keep this",
                   expires_at=_future_iso(1000))
        mgr.consolidate()
        assert mgr.size == 1


# ── Persistence ──────────────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load(self):
        mgr = _make_manager(dim=128)
        mgr.store(key="persist1", content="Save me to disk",
                   memory_type=MemoryType.SEMANTIC,
                   tags=["persist"],
                   importance=0.7)
        mgr.store(key="persist2", content="Also save me",
                   memory_type=MemoryType.EPISODIC)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "unified_mem")
            mgr.save(path)

            assert os.path.exists(f"{path}.json")
            assert os.path.exists(f"{path}.hnsw")
            assert os.path.exists(f"{path}.meta")

            loaded = UnifiedMemoryManager.load(path)
            assert loaded.size == 2

            entry = loaded.retrieve("persist1")
            assert entry is not None
            assert entry.content == "Save me to disk"
            assert entry.memory_type == MemoryType.SEMANTIC
            assert entry.tags == ["persist"]
            assert entry.importance == 0.7

    def test_load_search_works(self):
        mgr = _make_manager(dim=128)
        mgr.store(key="search1", content="Machine learning algorithms")
        mgr.store(key="search2", content="Cooking pasta recipe")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "search_mem")
            mgr.save(path)
            loaded = UnifiedMemoryManager.load(path)

            results = loaded.search("machine learning", k=2)
            assert len(results) >= 1
            assert results[0].memory.key == "search1"

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            UnifiedMemoryManager.load("/nonexistent/unified_mem")

    def test_persist_path_auto_saves(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "auto_save")
            mgr = UnifiedMemoryManager(dim=128, persist_path=path)
            mgr.store(key="auto", content="Auto-saved entry")
            assert os.path.exists(f"{path}.json")


# ── Thread Safety ────────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_stores(self):
        mgr = _make_manager(dim=64)
        errors = []

        def add_entries(prefix: str, count: int):
            try:
                for i in range(count):
                    mgr.store(
                        key=f"{prefix}_{i}",
                        content=f"Thread {prefix} entry {i}",
                        importance=i / count,
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_entries, args=(f"t{t}", 20))
            for t in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert mgr.size == 80

    def test_concurrent_read_write(self):
        mgr = _make_manager(dim=64)
        for i in range(10):
            mgr.store(key=f"init{i}", content=f"Initial entry {i}")

        errors = []

        def reader():
            try:
                for _ in range(50):
                    mgr.search("entry", k=3)
                    mgr.retrieve("init5")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    mgr.store(
                        key=f"new_{i}",
                        content=f"New entry {i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ── Edge Cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_content(self):
        mgr = _make_manager()
        eid = mgr.store(key="empty", content="")
        entry = mgr.retrieve(eid)
        assert entry is not None
        assert entry.content == ""

    def test_very_long_content(self):
        mgr = _make_manager()
        long_text = "word " * 10000
        eid = mgr.store(key="long", content=long_text)
        entry = mgr.retrieve(eid)
        assert entry is not None
        assert len(entry.content) == len(long_text)

    def test_unicode_content(self):
        mgr = _make_manager()
        eid = mgr.store(key="uni", content="日本語のテスト 🎉 émojis")
        entry = mgr.retrieve(eid)
        assert entry is not None
        assert entry.content == "日本語のテスト 🎉 émojis"

    def test_repr(self):
        mgr = _make_manager(dim=64)
        r = repr(mgr)
        assert "UnifiedMemoryManager" in r
        assert "entries=0" in r
        assert "dim=64" in r

    def test_store_and_retrieve_all_memory_types(self):
        mgr = _make_manager()
        for mt in MemoryType:
            mgr.store(key=f"type_{mt.value}", content=f"Content for {mt.value}",
                       memory_type=mt)
        for mt in MemoryType:
            entry = mgr.retrieve(f"type_{mt.value}")
            assert entry is not None
            assert entry.memory_type == mt

    def test_store_and_retrieve_all_access_levels(self):
        mgr = _make_manager()
        for al in AccessLevel:
            mgr.store(key=f"level_{al.value}", content=f"Content for {al.value}",
                       access_level=al)
        for al in AccessLevel:
            entry = mgr.retrieve(f"level_{al.value}")
            assert entry is not None
            assert entry.access_level == al

    def test_importance_clamped(self):
        mgr = _make_manager()
        eid = mgr.store(key="clamp_high", content="High", importance=5.0)
        entry = mgr.retrieve(eid)
        assert entry is not None
        assert entry.importance == 1.0

        eid2 = mgr.store(key="clamp_low", content="Low", importance=-1.0)
        entry2 = mgr.retrieve(eid2)
        assert entry2 is not None
        assert entry2.importance == 0.0

    def test_content_hash_consistency(self):
        """Same content always produces the same hash."""
        h1 = _content_hash("hello world")
        h2 = _content_hash("hello world")
        assert h1 == h2
        h3 = _content_hash("hello worlds")
        assert h1 != h3


# ── Helpers ──────────────────────────────────────────────────────────


class TestHelpers:
    def test_is_expired_past(self):
        assert _is_expired(_past_iso(1)) is True

    def test_is_expired_future(self):
        assert _is_expired(_future_iso(1)) is False

    def test_is_expired_none(self):
        # None passed as string should not crash
        assert _is_expired("") is False

    def test_utcnow_returns_iso(self):
        ts = _utcnow()
        # Should parse without error
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None
