"""Tests for ExoskeletonDaemon — cycle execution, lifecycle, and error resilience."""

import time
import threading
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from edge.exoskeleton_daemon import ExoskeletonDaemon


# ── Helpers ──────────────────────────────────────────────────────────

def _make_mock_health_report():
    return {
        "cpu_percent": 25.0,
        "memory_percent": 40.0,
        "disk_percent": 50.0,
        "cpu_healthy": True,
        "memory_healthy": True,
        "disk_healthy": True,
        "network_healthy": True,
        "timestamp": time.time(),
    }


def _make_mock_device_metrics():
    m = MagicMock()
    m.cpu_percent = 30.0
    m.memory_percent = 45.0
    m.disk_percent = 55.0
    return m


def _build_daemon_with_mocks(interval=1.0):
    """Create a daemon with all modules mocked."""
    daemon = ExoskeletonDaemon(interval=interval)

    # L1
    health_checker = MagicMock()
    health_checker.check_all.return_value = _make_mock_health_report()
    health_checker.is_healthy.return_value = True

    # L2
    repair_engine = MagicMock()
    repair_engine.detect_issues.return_value = []
    repair_engine.repair.return_value = {"success": True, "action": "noop"}

    strategy_switcher = MagicMock()
    strategy_switcher.current = "default"
    strategy_switcher.evaluate.return_value = None

    feedback_loop = MagicMock()
    feedback_loop.is_stable = True
    feedback_loop.update.return_value = 0.0

    repair_escalation = MagicMock()

    # L3
    task_organizer = MagicMock()
    task_organizer.get_executable_tasks.return_value = []
    task_organizer.get_topology.return_value = []

    context_manager = MagicMock()
    context_manager.snapshot.return_value = {"state": {}, "version": 0}

    event_bus = MagicMock()
    event_bus.get_stats.return_value = {
        "total_events": 0,
        "subscribers": 0,
        "dead_letters": 0,
    }

    # L4
    swarm_manager = MagicMock()
    swarm_manager.discover_nodes.return_value = []

    trust_evaluator = MagicMock()
    trust_evaluator.get_trust.return_value = 0.8

    shared_trust = MagicMock()
    shared_trust.evaluate.return_value = MagicMock(score=0.9)

    niche_matcher = MagicMock()
    niche_matcher.match.return_value = None

    # Gateway
    network_discovery = MagicMock()
    network_discovery._running = False
    network_discovery.register_device.return_value = MagicMock()
    network_discovery.get_devices.return_value = []

    device_monitor = MagicMock()
    device_monitor.collect.return_value = _make_mock_device_metrics()
    device_monitor.get_health_status.return_value = MagicMock(value="healthy")

    knowledge_puller = MagicMock()
    knowledge_puller.get_insights.return_value = []
    knowledge_puller.get_broadcasts.return_value = []

    self_healing = MagicMock()
    self_healing.diagnose.return_value = []
    self_healing.heal.return_value = MagicMock()

    # Genome
    evolution_tracker = MagicMock()
    evolution_tracker.track_milestone.return_value = {"recorded": True}

    knowledge_heritage = MagicMock()
    knowledge_heritage.store_knowledge.return_value = {"stored": True}

    # Inject all modules
    daemon._modules = {
        "health_checker": health_checker,
        "repair_engine": repair_engine,
        "strategy_switcher": strategy_switcher,
        "feedback_loop": feedback_loop,
        "repair_escalation": repair_escalation,
        "task_organizer": task_organizer,
        "context_manager": context_manager,
        "event_bus": event_bus,
        "swarm_manager": swarm_manager,
        "trust_evaluator": trust_evaluator,
        "shared_trust": shared_trust,
        "niche_matcher": niche_matcher,
        "network_discovery": network_discovery,
        "device_monitor": device_monitor,
        "knowledge_puller": knowledge_puller,
        "self_healing": self_healing,
        "evolution_tracker": evolution_tracker,
        "knowledge_heritage": knowledge_heritage,
    }

    return daemon


# ── Tests ────────────────────────────────────────────────────────────


class TestExoskeletonDaemonLifecycle:
    """Test start/stop lifecycle."""

    def test_start_sets_running_flag(self):
        daemon = _build_daemon_with_mocks(interval=5.0)
        daemon.start()
        assert daemon._running is True
        assert daemon._thread is not None
        assert daemon._thread.is_alive()
        daemon.stop()

    def test_stop_clears_running_flag(self):
        daemon = _build_daemon_with_mocks(interval=5.0)
        daemon.start()
        time.sleep(0.1)
        daemon.stop()
        assert daemon._running is False

    def test_start_idempotent(self):
        daemon = _build_daemon_with_mocks(interval=5.0)
        daemon.start()
        thread1 = daemon._thread
        daemon.start()  # Should not create a new thread
        assert daemon._thread is thread1
        daemon.stop()

    def test_stop_without_start(self):
        daemon = ExoskeletonDaemon(interval=5.0)
        # Should not raise
        daemon.stop()

    def test_status_while_running(self):
        daemon = _build_daemon_with_mocks(interval=5.0)
        daemon.start()
        time.sleep(0.1)
        s = daemon.status()
        assert s["running"] is True
        assert s["thread_alive"] is True
        assert s["interval"] == 5.0
        daemon.stop()

    def test_status_after_stop(self):
        daemon = _build_daemon_with_mocks(interval=5.0)
        daemon.start()
        time.sleep(0.1)
        daemon.stop()
        s = daemon.status()
        assert s["running"] is False


class TestExoskeletonDaemonCycle:
    """Test cycle execution with mocked sub-modules."""

    def test_single_cycle_runs_all_layers(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        stats = daemon._stats
        assert stats["cycles"] == 1
        assert stats["errors"] == 0

    def test_cycle_calls_health_check(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        daemon._modules["health_checker"].check_all.assert_called_once()

    def test_cycle_calls_repair_engine(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        daemon._modules["repair_engine"].detect_issues.assert_called_once()

    def test_cycle_calls_device_monitor(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        daemon._modules["device_monitor"].collect.assert_called_once()

    def test_cycle_calls_self_healing(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        daemon._modules["self_healing"].diagnose.assert_called_once()

    def test_cycle_calls_evolution_tracker(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        daemon._modules["evolution_tracker"].track_milestone.assert_called_once()

    def test_cycle_calls_knowledge_heritage(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        daemon._modules["knowledge_heritage"].store_knowledge.assert_called_once()

    def test_cycle_records_health_issues(self):
        """When health issues exist, repairs should be attempted."""
        daemon = _build_daemon_with_mocks(interval=10.0)
        # Make repair engine detect issues
        daemon._modules["repair_engine"].detect_issues.return_value = [
            {"type": "cpu_high", "severity": "warning"}
        ]
        daemon._run_cycle()
        assert daemon._stats["health_issues_found"] == 1
        assert daemon._stats["repairs_attempted"] == 1
        assert daemon._stats["repairs_succeeded"] == 1

    def test_multiple_cycles_increment_counter(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        daemon._run_cycle()
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 3

    def test_cycle_tracks_duration(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._run_cycle()
        assert daemon._stats["last_cycle_duration"] >= 0
        assert daemon._stats["last_cycle_time"] > 0


class TestExoskeletonDaemonErrorResilience:
    """Test that one module failure doesn't break the cycle."""

    def test_health_check_failure_doesnt_break_cycle(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["health_checker"].check_all.side_effect = RuntimeError(
            "health check boom"
        )
        # Should complete without raising
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1
        # Errors tracked at module level, not at top level
        assert "health_checker" in daemon._stats["module_failures"]

    def test_repair_engine_failure_doesnt_break_cycle(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["repair_engine"].detect_issues.side_effect = RuntimeError(
            "repair boom"
        )
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1

    def test_device_monitor_failure_doesnt_break_cycle(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["device_monitor"].collect.side_effect = RuntimeError(
            "monitor boom"
        )
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1

    def test_self_healing_failure_doesnt_break_cycle(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["self_healing"].diagnose.side_effect = RuntimeError(
            "healing boom"
        )
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1

    def test_evolution_tracker_failure_doesnt_break_cycle(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["evolution_tracker"].track_milestone.side_effect = RuntimeError(
            "tracker boom"
        )
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1

    def test_swarm_failure_doesnt_break_cycle(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["swarm_manager"].discover_nodes.side_effect = RuntimeError(
            "swarm boom"
        )
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1

    def test_network_discovery_failure_doesnt_break_cycle(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["network_discovery"].register_device.side_effect = RuntimeError(
            "discovery boom"
        )
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1
    def test_all_gateway_modules_fail_cycle_still_completes(self):
        """Even if ALL gateway modules fail, the cycle should complete."""
        daemon = _build_daemon_with_mocks(interval=10.0)

        daemon._modules["network_discovery"].register_device.side_effect = RuntimeError(
            "boom"
        )
        daemon._modules["network_discovery"]._running = False
        daemon._modules["device_monitor"].collect.side_effect = RuntimeError("boom")
        daemon._modules["device_monitor"].get_health_status.side_effect = RuntimeError(
            "boom"
        )
        daemon._modules["knowledge_puller"].get_insights.side_effect = RuntimeError(
            "boom"
        )
        daemon._modules["knowledge_puller"].get_broadcasts.side_effect = RuntimeError(
            "boom"
        )
        daemon._modules["self_healing"].diagnose.side_effect = RuntimeError("boom")

        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1

    def test_none_module_handled_gracefully(self):
        """If a module failed to init (None), cycle should still work."""
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["health_checker"] = None
        daemon._modules["device_monitor"] = None
        daemon._modules["evolution_tracker"] = None
        daemon._run_cycle()
        assert daemon._stats["cycles"] == 1


class TestExoskeletonDaemonThreadSafety:
    """Test thread safety of status and stats."""

    def test_status_thread_safe(self):
        daemon = _build_daemon_with_mocks(interval=0.5)
        daemon.start()

        results = []

        def reader():
            for _ in range(10):
                results.append(daemon.status())
                time.sleep(0.05)

        t = threading.Thread(target=reader)
        t.start()
        time.sleep(0.5)
        daemon.stop()
        t.join(timeout=5)

        assert len(results) > 0
        for r in results:
            assert "running" in r
            assert "stats" in r


class TestExoskeletonDaemonWithIssues:
    """Test repair path when health issues are detected."""

    def test_repair_triggers_strategy_evaluation(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["repair_engine"].detect_issues.return_value = [
            {"type": "cpu_high", "severity": "warning"},
            {"type": "memory_high", "severity": "warning"},
        ]
        daemon._run_cycle()
        # Strategy switcher should have been called
        daemon._modules["strategy_switcher"].evaluate.assert_called_once()

    def test_repair_triggers_feedback_loop(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["repair_engine"].detect_issues.return_value = [
            {"type": "disk_full", "severity": "critical"}
        ]
        daemon._run_cycle()
        # Feedback loop should have been called
        assert daemon._modules["feedback_loop"].update.call_count >= 1

    def test_failed_repair_tracked(self):
        daemon = _build_daemon_with_mocks(interval=10.0)
        daemon._modules["repair_engine"].detect_issues.return_value = [
            {"type": "network_down", "severity": "critical"}
        ]
        daemon._modules["repair_engine"].repair.return_value = {
            "success": False,
            "error": "could not fix",
        }
        daemon._run_cycle()
        assert daemon._stats["repairs_attempted"] == 1
        assert daemon._stats["repairs_succeeded"] == 0
