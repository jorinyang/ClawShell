"""Tests for P0 enhancements: claim timeout, backpressure, signals, offline."""
from __future__ import annotations
import sys, os, time, tempfile, uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest


# ═══════════════════════════════════════════════════════════════════
# CLAIM TIMEOUT (消费确认超时)
# ═══════════════════════════════════════════════════════════════════

class TestClaimTimeout:
    @pytest.fixture
    def board(self):
        from cloud.engines.task_board import GlobalTaskBoard
        with tempfile.TemporaryDirectory() as d:
            yield GlobalTaskBoard(data_dir=d)

    def test_release_stale_claims_releases_expired(self, board):
        tid = board.create_task({"title": "t1", "claim_timeout": 0})
        board.claim(tid, "edge-1")
        # Manually set claimed_at to 10 min ago
        board._tasks[tid]["claimed_at"] = time.time() - 600
        released = board.release_stale_claims()
        assert released >= 1
        t = board.get_task(tid)
        assert t["status"] == "pending"
        assert t["claimed_by"] is None
        assert len(t.get("claim_attempts", [])) >= 1

    def test_dont_release_fresh_claims(self, board):
        tid = board.create_task({"title": "t1", "claim_timeout": 300})
        board.claim(tid, "edge-1")
        released = board.release_stale_claims()
        assert released == 0

    def test_release_stale_keeps_pending_untouched(self, board):
        board.create_task({"title": "t1"})  # PENDING
        released = board.release_stale_claims()
        assert released == 0


# ═══════════════════════════════════════════════════════════════════
# BACKPRESSURE (背压控制)
# ═══════════════════════════════════════════════════════════════════

class TestBackpressure:
    def test_reject_when_queue_full(self):
        from cloud.engines.task_board import GlobalTaskBoard
        with tempfile.TemporaryDirectory() as d:
            board = GlobalTaskBoard(data_dir=d, max_pending=2)
            board.create_task({"title": "t1"})
            board.create_task({"title": "t2"})
            with pytest.raises(RuntimeError, match="backpressure"):
                board.create_task({"title": "t3"})

    def test_accept_when_below_limit(self):
        from cloud.engines.task_board import GlobalTaskBoard
        with tempfile.TemporaryDirectory() as d:
            board = GlobalTaskBoard(data_dir=d, max_pending=5)
            for i in range(3):
                board.create_task({"title": f"t{i}"})
            assert board.get_stats()["total"] == 3

    def test_unlimited_when_max_pending_zero(self):
        from cloud.engines.task_board import GlobalTaskBoard
        with tempfile.TemporaryDirectory() as d:
            board = GlobalTaskBoard(data_dir=d, max_pending=0)  # unlimited
            for i in range(10):
                board.create_task({"title": f"t{i}"})
            assert board.get_stats()["total"] == 10

    def test_backpressure_events_counter(self):
        from cloud.engines.task_board import GlobalTaskBoard
        with tempfile.TemporaryDirectory() as d:
            board = GlobalTaskBoard(data_dir=d, max_pending=1)
            board.create_task({"title": "t1"})
            try: board.create_task({"title": "t2"})
            except RuntimeError: pass
            try: board.create_task({"title": "t3"})
            except RuntimeError: pass
            stats = board.get_stats()
            assert stats["backpressure_events"] >= 2

    def test_freed_slot_allows_new_task(self):
        from cloud.engines.task_board import GlobalTaskBoard
        with tempfile.TemporaryDirectory() as d:
            board = GlobalTaskBoard(data_dir=d, max_pending=1)
            tid = board.create_task({"title": "t1"})
            # Free the slot by claiming
            board.claim(tid, "edge-1")
            # Now can create again
            board.create_task({"title": "t2"})
            assert board.get_stats()["total"] == 2


# ═══════════════════════════════════════════════════════════════════
# SIGNAL HANDLER (信号处理)
# ═══════════════════════════════════════════════════════════════════

class TestSignalHandler:
    def test_register_and_list_hooks(self):
        from edge.installer.signal_handler import SignalHandler
        calls = []
        h = SignalHandler(graceful_timeout=1)
        h.register("a", lambda: calls.append("a"))
        h.register("b", lambda: calls.append("b"))
        assert len(h._shutdown_hooks) == 2

    def test_hooks_run_in_order(self):
        from edge.installer.signal_handler import SignalHandler
        order = []
        h = SignalHandler()
        h.register("first", lambda: order.append(1))
        h.register("second", lambda: order.append(2))
        h._run_hooks()
        assert order == [1, 2]

    def test_timeout_doesnt_block_others(self):
        from edge.installer.signal_handler import SignalHandler
        order = []
        h = SignalHandler(graceful_timeout=0.1)
        h.register("slow", lambda: time.sleep(5))
        h.register("fast", lambda: order.append("fast"))
        h._run_hooks()
        assert "fast" in order


# ═══════════════════════════════════════════════════════════════════
# OFFLINE DEGRADATION (离线降级)
# ═══════════════════════════════════════════════════════════════════

class TestOfflineDegradation:
    @pytest.fixture
    def offline(self):
        from edge.installer.signal_handler import OfflineDegradation
        with tempfile.TemporaryDirectory() as d:
            yield OfflineDegradation(data_dir=d, check_interval=0)

    def test_enqueue_and_replay(self, offline):
        ops = [
            {"type": "sync", "data": "a"},
            {"type": "sync", "data": "b"},
            {"type": "cron_report", "task": "cleanup"},
        ]
        for op in ops:
            offline.enqueue(op)
        assert offline.queue_size() == 3

        replayed = []
        def sender(op):
            replayed.append(op)
            return True

        sent, failed = offline.replay(sender)
        assert sent == 3
        assert failed == 0
        assert len(replayed) == 3
        assert offline.queue_size() == 0

    def test_replay_partial_failure_requeues(self, offline):
        offline.enqueue({"type": "good"})
        offline.enqueue({"type": "bad"})
        offline.enqueue({"type": "good2"})

        def sender(op):
            return op["type"] != "bad"  # "bad" fails

        sent, failed = offline.replay(sender)
        assert sent == 2
        assert failed == 1
        assert offline.queue_size() == 1  # bad requeued

    def test_clear(self, offline):
        offline.enqueue({"type": "x"})
        assert offline.queue_size() == 1
        offline.clear()
        assert offline.queue_size() == 0

    def test_check_connectivity_graceful(self, offline):
        # Non-existent URL → offline
        ok = offline.check_connectivity("http://0.0.0.0:1")  # unreachable
        assert ok is False
