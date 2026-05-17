"""Tests for ClawShell Hook Event System."""

import threading
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.hooks.manager import HookEvent, HookPriority, HookContext, HookManager


class TestHookEnums:
    def test_hook_event_values(self):
        assert HookEvent.PRE_TASK.value == "pre_task"
        assert HookEvent.THREAT_DETECTED.value == "threat_detected"
        assert len(HookEvent) == 13

    def test_hook_priority_ordering(self):
        assert HookPriority.CRITICAL > HookPriority.HIGH > HookPriority.NORMAL > HookPriority.LOW > HookPriority.BACKGROUND
        assert HookPriority.CRITICAL == 1000
        assert HookPriority.BACKGROUND == 1


class TestHookContext:
    def test_init_copies_data(self):
        ctx = HookContext(event=HookEvent.PRE_TASK, data={"k": "v"}, source="test")
        assert ctx.modified_data == {"k": "v"}
        assert ctx.cancelled is False

    def test_set_and_get(self):
        ctx = HookContext(event=HookEvent.PRE_TASK, data={}, source="test")
        ctx.set("foo", 42)
        assert ctx.get("foo") == 42
        assert ctx.get("missing", "default") == "default"

    def test_cancel(self):
        ctx = HookContext(event=HookEvent.PRE_TASK, data={}, source="test")
        ctx.cancel()
        assert ctx.cancelled is True


class TestHookManager:
    def test_register_and_list(self):
        mgr = HookManager()
        handler = lambda ctx: None
        hid = mgr.register(HookEvent.PRE_TASK, handler, HookPriority.HIGH, "test")
        assert isinstance(hid, str)
        hooks = mgr.list_hooks()
        assert len(hooks) == 1
        assert hooks[0].name == "test"

    def test_unregister(self):
        mgr = HookManager()
        hid = mgr.register(HookEvent.PRE_TASK, lambda ctx: None)
        assert mgr.unregister(hid) is True
        assert mgr.unregister(hid) is False
        assert len(mgr.list_hooks()) == 0

    def test_priority_order(self):
        """Hooks fire highest-priority first."""
        mgr = HookManager()
        order = []
        mgr.register(HookEvent.PRE_TASK, lambda ctx: order.append("low"), HookPriority.LOW, "low")
        mgr.register(HookEvent.PRE_TASK, lambda ctx: order.append("critical"), HookPriority.CRITICAL, "critical")
        mgr.register(HookEvent.PRE_TASK, lambda ctx: order.append("normal"), HookPriority.NORMAL, "normal")
        mgr.trigger(HookEvent.PRE_TASK)
        assert order == ["critical", "normal", "low"]

    def test_data_modification_chain(self):
        """Each hook sees modified data from previous hooks."""
        mgr = HookManager()

        def add_key(ctx: HookContext):
            ctx.set("added", True)

        def double_value(ctx: HookContext):
            ctx.set("count", ctx.get("count", 0) * 2)

        mgr.register(HookEvent.PRE_TASK, add_key, HookPriority.HIGH)
        mgr.register(HookEvent.PRE_TASK, double_value, HookPriority.NORMAL)

        result = mgr.trigger(HookEvent.PRE_TASK, {"count": 5})
        assert result.modified_data["added"] is True
        assert result.modified_data["count"] == 10

    def test_cancel_stops_chain(self):
        mgr = HookManager()
        called = []

        def cancel_hook(ctx: HookContext):
            called.append("first")
            ctx.cancel()

        def should_not_run(ctx: HookContext):
            called.append("second")

        mgr.register(HookEvent.PRE_TASK, cancel_hook, HookPriority.HIGH, "cancel")
        mgr.register(HookEvent.PRE_TASK, should_not_run, HookPriority.LOW, "blocked")
        mgr.trigger(HookEvent.PRE_TASK)
        assert called == ["first"]

    def test_exception_doesnt_break_chain(self):
        mgr = HookManager()
        called = []

        def bad_hook(ctx: HookContext):
            called.append("bad")
            raise ValueError("boom")

        def good_hook(ctx: HookContext):
            called.append("good")

        mgr.register(HookEvent.PRE_TASK, bad_hook, HookPriority.HIGH, "bad")
        mgr.register(HookEvent.PRE_TASK, good_hook, HookPriority.LOW, "good")
        mgr.trigger(HookEvent.PRE_TASK)
        assert "bad" in called
        assert "good" in called

    def test_list_hooks_filtered(self):
        mgr = HookManager()
        mgr.register(HookEvent.PRE_TASK, lambda ctx: None, name="pre")
        mgr.register(HookEvent.POST_TASK, lambda ctx: None, name="post")
        assert len(mgr.list_hooks(HookEvent.PRE_TASK)) == 1
        assert len(mgr.list_hooks(HookEvent.POST_TASK)) == 1
        assert len(mgr.list_hooks()) == 2

    def test_clear(self):
        mgr = HookManager()
        mgr.register(HookEvent.PRE_TASK, lambda ctx: None)
        mgr.register(HookEvent.POST_TASK, lambda ctx: None)
        mgr.clear()
        assert len(mgr.list_hooks()) == 0

    def test_trigger_returns_context(self):
        mgr = HookManager()
        ctx = mgr.trigger(HookEvent.NODE_JOIN, {"ip": "10.0.0.1"}, "test")
        assert isinstance(ctx, HookContext)
        assert ctx.event == HookEvent.NODE_JOIN
        assert ctx.source == "test"

    def test_thread_safety(self):
        """Concurrent register/unregister/trigger doesn't crash."""
        mgr = HookManager()
        errors = []

        def writer():
            try:
                for _ in range(100):
                    h = mgr.register(HookEvent.PRE_TASK, lambda ctx: None)
                    mgr.unregister(h)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    mgr.trigger(HookEvent.PRE_TASK, {"x": 1})
                    mgr.list_hooks()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(5)]
        threads += [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
