"""Integration tests — HookManager wired into EventBus, SyncDaemon, TaskBoard."""

import sys
import os
import threading
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from shared.hooks.manager import HookEvent, HookPriority, HookContext, HookManager
from shared.hooks.registry import get_hook_manager, reset_hook_manager, trigger_hook
from edge.eventbus.core import EdgeEventBus
from edge.sync.daemon import EdgeSyncDaemon
from cloud.engines.task_board import GlobalTaskBoard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global HookManager singleton before each test."""
    reset_hook_manager()
    yield
    reset_hook_manager()


@pytest.fixture
def hook_mgr():
    return get_hook_manager()


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestHookRegistry:
    def test_singleton_identity(self):
        """get_hook_manager() always returns the same instance."""
        a = get_hook_manager()
        b = get_hook_manager()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_hook_manager()
        reset_hook_manager()
        b = get_hook_manager()
        assert a is not b

    def test_trigger_hook_convenience(self):
        """trigger_hook() calls the global manager."""
        captured = []

        def handler(ctx: HookContext):
            captured.append(ctx.data)

        get_hook_manager().register(HookEvent.PRE_TASK, handler, name="cap")
        ctx = trigger_hook(HookEvent.PRE_TASK, {"x": 1}, source="test")
        assert captured == [{"x": 1}]
        assert ctx.source == "test"


# ---------------------------------------------------------------------------
# EventBus → Hook bridge
# ---------------------------------------------------------------------------

class TestEventBusHookBridge:
    def test_publish_fires_post_event_hook(self):
        """publish() triggers HookEvent.POST_EVENT on the global hook manager."""
        captured = []

        def on_post_event(ctx: HookContext):
            captured.append(ctx.data)

        get_hook_manager().register(
            HookEvent.POST_EVENT, on_post_event, name="post_event_listener"
        )

        bus = EdgeEventBus()
        bus.publish("test.ping", data={"hello": "world"}, source="unittest")

        assert len(captured) == 1
        assert captured[0]["event_type"] == "test.ping"
        assert captured[0]["event"]["data"] == {"hello": "world"}

    def test_publish_no_hooks_registered(self):
        """publish() works fine even with no hooks registered."""
        bus = EdgeEventBus()
        result = bus.publish("test.empty")
        assert result["event_type"] == "test.empty"

    def test_multiple_publishes_fire_multiple_hooks(self):
        count = []

        def counter(ctx: HookContext):
            count.append(1)

        get_hook_manager().register(HookEvent.POST_EVENT, counter)
        bus = EdgeEventBus()
        bus.publish("a")
        bus.publish("b")
        bus.publish("c")
        assert len(count) == 3


# ---------------------------------------------------------------------------
# SyncDaemon — PRE_SYNC / POST_SYNC hooks
# ---------------------------------------------------------------------------

class TestSyncDaemonHooks:
    def _make_daemon(self):
        """Create a minimal daemon pointing at a nonexistent cloud URL."""
        return EdgeSyncDaemon(
            cloud_url="http://localhost:1",
            edge_token="fake",
            edge_id="test-edge",
            data_dir="/tmp/_clawshell_test_sync",
        )

    def test_pre_sync_cancel_skips_cycle(self):
        """A PRE_SYNC hook that cancels causes the sync cycle to be skipped."""
        cancelled_seen = []

        def cancel_sync(ctx: HookContext):
            ctx.cancel()
            cancelled_seen.append(True)

        get_hook_manager().register(
            HookEvent.PRE_SYNC, cancel_sync, HookPriority.HIGH, "cancel_sync"
        )

        daemon = self._make_daemon()
        result = daemon.run_once()

        assert cancelled_seen == [True]
        assert result.get("skipped") is True
        assert result["events_flushed"] == 0
        assert result["tasks_pulled"] == 0

    def test_post_sync_hook_fires(self):
        """POST_SYNC hook fires after a normal (non-cancelled) sync cycle."""
        post_sync_data = []

        def on_post_sync(ctx: HookContext):
            post_sync_data.append(ctx.data)

        get_hook_manager().register(
            HookEvent.POST_SYNC, on_post_sync, name="post_sync_listener"
        )

        daemon = self._make_daemon()
        # run_once will fail to connect to cloud but should still fire POST_SYNC
        try:
            daemon.run_once()
        except Exception:
            pass

        assert len(post_sync_data) == 1
        assert "result" in post_sync_data[0]
        assert "duration" in post_sync_data[0]


# ---------------------------------------------------------------------------
# TaskBoard — PRE_TASK / POST_TASK hooks
# ---------------------------------------------------------------------------

class TestTaskBoardHooks:
    def _make_board(self, tmp_path="/tmp/_clawshell_test_tasks"):
        """Create a TaskBoard with a temp data dir."""
        import shutil
        if os.path.exists(tmp_path):
            shutil.rmtree(tmp_path)
        return GlobalTaskBoard(data_dir=tmp_path)

    def test_create_task_fires_pre_task(self):
        """Creating a task triggers PRE_TASK."""
        captured = []

        def on_pre_task(ctx: HookContext):
            captured.append(ctx.data)

        get_hook_manager().register(
            HookEvent.PRE_TASK, on_pre_task, name="pre_task_listener"
        )

        board = self._make_board()
        task_id = board.create_task({"title": "Test task"})

        assert len(captured) == 1
        assert captured[0]["task_id"] == task_id
        assert captured[0]["task"]["title"] == "Test task"

    def test_complete_task_fires_post_task(self):
        """Completing a task triggers POST_TASK."""
        captured = []

        def on_post_task(ctx: HookContext):
            captured.append(ctx.data)

        get_hook_manager().register(
            HookEvent.POST_TASK, on_post_task, name="post_task_listener"
        )

        board = self._make_board()
        task_id = board.create_task({"title": "Complete me"})
        board.claim(task_id, "edge-1")
        board.complete(task_id, {"output": "done"})

        assert len(captured) == 1
        assert captured[0]["task_id"] == task_id
        assert captured[0]["target_status"] == "completed"

    def test_fail_task_fires_post_task(self):
        """Failing a task triggers POST_TASK."""
        captured = []

        def on_post_task(ctx: HookContext):
            captured.append(ctx.data)

        get_hook_manager().register(
            HookEvent.POST_TASK, on_post_task, name="post_task_listener"
        )

        board = self._make_board()
        task_id = board.create_task({"title": "Will fail"})
        board.claim(task_id, "edge-1")
        board.fail(task_id, "something went wrong")

        assert len(captured) == 1
        assert captured[0]["task_id"] == task_id
        assert captured[0]["target_status"] == "failed"

    def test_cancel_task_does_not_fire_post_task(self):
        """Cancelling a task does NOT trigger POST_TASK (only completed/failed do)."""
        captured = []

        def on_post_task(ctx: HookContext):
            captured.append(ctx.data)

        get_hook_manager().register(
            HookEvent.POST_TASK, on_post_task, name="post_task_listener"
        )

        board = self._make_board()
        task_id = board.create_task({"title": "Will cancel"})
        board.cancel(task_id, "no longer needed")

        assert len(captured) == 0


# ---------------------------------------------------------------------------
# Full integration: EventBus → Hook → verify
# ---------------------------------------------------------------------------

class TestFullIntegration:
    def test_eventbus_to_hook_pipeline(self):
        """Register hook → publish event on EventBus → hook fires with correct data."""
        pipeline = []

        def audit_hook(ctx: HookContext):
            pipeline.append({
                "event": ctx.event.name,
                "source": ctx.source,
                "event_type": ctx.data.get("event_type"),
            })

        get_hook_manager().register(
            HookEvent.POST_EVENT, audit_hook, HookPriority.NORMAL, "audit"
        )

        bus = EdgeEventBus()
        bus.publish("node.connected", {"node_id": "n1"}, source="topology")

        assert len(pipeline) == 1
        assert pipeline[0]["event"] == "POST_EVENT"
        assert pipeline[0]["source"] == "topology"
        assert pipeline[0]["event_type"] == "node.connected"

    def test_pre_sync_cancel_blocks_post_sync(self):
        """If PRE_SYNC cancels, POST_SYNC should NOT fire (cycle is skipped)."""
        events = []

        def pre_sync(ctx: HookContext):
            events.append("pre_sync")
            ctx.cancel()

        def post_sync(ctx: HookContext):
            events.append("post_sync")

        get_hook_manager().register(HookEvent.PRE_SYNC, pre_sync, HookPriority.HIGH)
        get_hook_manager().register(HookEvent.POST_SYNC, post_sync, HookPriority.NORMAL)

        daemon = EdgeSyncDaemon(
            cloud_url="http://localhost:1",
            edge_token="fake",
            edge_id="test-edge",
            data_dir="/tmp/_clawshell_test_sync2",
        )
        result = daemon.run_once()

        assert "pre_sync" in events
        assert "post_sync" not in events
        assert result.get("skipped") is True
