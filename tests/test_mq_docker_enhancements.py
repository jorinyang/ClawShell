"""Tests for MQ-inspired TaskBoard + Docker-inspired ResourceGuard."""
from __future__ import annotations
import sys, os, time, uuid, tempfile
from pathlib import Path
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════
# MQ-INSPIRED TASKBOARD ENHANCEMENTS
# ═══════════════════════════════════════════════════════════════════

class TestTaskBoardMQEnhancements:
    """4 new MQ-inspired capabilities."""

    @pytest.fixture
    def board(self):
        from cloud.engines.task_board import GlobalTaskBoard
        with tempfile.TemporaryDirectory() as d:
            yield GlobalTaskBoard(data_dir=d)

    # ── 1. Dedup ──────────────────────────────────────────────────

    def test_dedup_prevents_duplicate(self, board):
        h = str(uuid.uuid4())
        t1 = board.create_with_dedup(
            {"title": "cleanup", "content_hash": h}
        )
        t2 = board.create_with_dedup(
            {"title": "cleanup", "content_hash": h}
        )
        assert t1 == t2, "Same hash → same task_id"

    def test_dedup_different_hash_creates_new(self, board):
        t1 = board.create_with_dedup(
            {"title": "a"}, content_hash="h1"
        )
        t2 = board.create_with_dedup(
            {"title": "b"}, content_hash="h2"
        )
        assert t1 != t2

    def test_dedup_no_hash_creates_always(self, board):
        t1 = board.create_with_dedup({"title": "x"})
        t2 = board.create_with_dedup({"title": "x"})
        assert t1 != t2, "No hash → always creates new"

    # ── 2. Batch Claim ────────────────────────────────────────────

    def test_claim_batch(self, board):
        for i in range(5):
            board.create_task({"title": f"t{i}", "required_capabilities": ["cleanup"]})
        claimed = board.claim_batch("edge-1", "cleanup", max_count=3)
        assert len(claimed) == 3
        for t in claimed:
            assert t["status"] == "in_progress"
            assert t["claimed_by"] == "edge-1"

    def test_claim_batch_capability_filter(self, board):
        board.create_task({"title": "t1", "required_capabilities": ["cleanup"]})
        board.create_task({"title": "t2", "required_capabilities": ["monitor"]})
        claimed = board.claim_batch("edge-1", "cleanup", max_count=5)
        assert len(claimed) == 1
        assert claimed[0]["title"] == "t1"

    def test_claim_batch_empty_when_none_match(self, board):
        board.create_task({"title": "t1", "required_capabilities": ["cleanup"]})
        claimed = board.claim_batch("edge-1", "nonexistent", max_count=5)
        assert claimed == []

    # ── 3. Auto-Retry ─────────────────────────────────────────────

    def test_fail_with_retry_stays_pending(self, board):
        tid = board.create_task({"title": "t1", "max_retries": 5})
        board.claim(tid, "edge-1")
        result = board.fail_with_retry(tid, "transient error")
        assert result["status"] == "pending", "Should retry, not fail"
        assert result["retry_count"] == 1
        assert "retry_at" in result

    def test_fail_with_retry_exhausted(self, board):
        tid = board.create_task({"title": "t1", "max_retries": 1})
        board.claim(tid, "edge-1")
        board.fail_with_retry(tid, "err1")  # retry_count=1
        board.claim(tid, "edge-1")           # re-claim after retry
        result = board.fail_with_retry(tid, "err2")  # exhausted
        assert result["status"] == "failed", "Should finally fail"

    def test_fail_with_retry_backoff_increases(self, board):
        tid = board.create_task({"title": "t1", "max_retries": 5})
        board.claim(tid, "edge-1")
        r1 = board.fail_with_retry(tid, "e1")
        board.claim(tid, "edge-1")
        r2 = board.fail_with_retry(tid, "e2")
        # Backoff should increase: delay1=1s, delay2=2s
        delay1 = r1.get("retry_at", 0) - r1.get("updated_at", 0)
        delay2 = r2.get("retry_at", 0) - r2.get("updated_at", 0)
        assert delay2 >= delay1 * 1.5, f"Backoff should increase: {delay1} → {delay2}"

    # ── 4. TTL ────────────────────────────────────────────────────

    def test_expire_stale_tasks_cancels_expired(self, board):
        import time
        tid = board.create_task({"title": "t1", "ttl_seconds": 1})
        time.sleep(0.1)  # wait longer than TTL
        expired = board.expire_stale_tasks()
        assert expired >= 1
        task = board.get_task(tid)
        assert task["status"] == "cancelled"

    def test_expire_no_ttl_untouched(self, board):
        tid = board.create_task({"title": "t1"})  # No TTL
        expired = board.expire_stale_tasks()
        assert expired == 0
        task = board.get_task(tid)
        assert task["status"] == "pending"

    def test_expire_future_ttl_preserved(self, board):
        tid = board.create_task({"title": "t1", "ttl_seconds": 99999})
        expired = board.expire_stale_tasks()
        assert expired == 0
        assert board.get_task(tid)["status"] == "pending"


# ═══════════════════════════════════════════════════════════════════
# DOCKER-INSPIRED RESOURCE GUARD
# ═══════════════════════════════════════════════════════════════════

class TestResourceGuard:
    """Docker-style resource protection."""

    def test_check_memory_returns_bool(self):
        from edge.installer.resource_guard import ResourceGuard
        g = ResourceGuard(memory_limit_mb=999999)  # Very high limit
        assert g.check_memory() is True

    def test_check_memory_exceeded(self):
        from edge.installer.resource_guard import ResourceGuard
        g = ResourceGuard(memory_limit_mb=1)  # 1MB limit — will always exceed
        assert g.check_memory() is False

    def test_check_disk_normal(self):
        from edge.installer.resource_guard import ResourceGuard
        g = ResourceGuard(disk_floor_gb=0.001)  # 1MB floor
        assert g.check_disk() is True

    def test_check_disk_exceeded(self):
        from edge.installer.resource_guard import ResourceGuard
        g = ResourceGuard(disk_floor_gb=99999)  # 100TB floor
        assert g.check_disk() is False

    def test_full_check_returns_dict(self):
        from edge.installer.resource_guard import ResourceGuard
        g = ResourceGuard()
        result = g.full_check()
        for key in ("memory_ok", "disk_ok", "cpu_ok"):
            assert key in result
            assert isinstance(result[key], bool)

    def test_alert_if_exceeded_with_cooldown(self):
        from edge.installer.resource_guard import ResourceGuard
        alerts = []
        g = ResourceGuard(memory_limit_mb=100000, alert_callback=lambda m, d: alerts.append((m, d)))
        # First call — should not alert (within limit)
        result = g.alert_if_exceeded()
        assert len(alerts) == 0
        assert not any(result.values())

    def test_config_snapshot_save_restore(self):
        from edge.installer.resource_guard import ConfigSnapshot
        with tempfile.TemporaryDirectory() as d:
            cs = ConfigSnapshot(snapshot_dir=d)
            # Create a file
            f = Path(d) / "test_config.yaml"
            f.write_text("original content")
            # Snapshot
            sid = cs.save(str(f), label="test")
            assert sid is not None
            # Modify
            f.write_text("modified content")
            # Restore
            ok = cs.restore(str(f), str(sid))
            assert ok
            assert f.read_text() == "original content"

    def test_config_snapshot_list_and_prune(self):
        from edge.installer.resource_guard import ConfigSnapshot
        with tempfile.TemporaryDirectory() as d:
            # Keep test file OUTSIDE snapshot dir
            cs = ConfigSnapshot(snapshot_dir=d)
            f = Path(d) / ".." / "outer_test.yaml"  # outside
            import os as _os
            f = Path(_os.path.join(d, "..", "outer_test.yaml")).resolve()
            f.write_text("content")
            for _ in range(5):
                cs.save(str(f))
            assert len(cs.list_snapshots()) == 5, f"Got: {cs.list_snapshots()}"
            cs.prune(keep=3)
            assert len(cs.list_snapshots()) == 3
