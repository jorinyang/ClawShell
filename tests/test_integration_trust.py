"""Integration tests for TrustEvaluator wired into CapabilityRegistry and SwarmCoordinator.

Tests that:
- Trust scores are computed and stored on heartbeat
- Task routing prefers trusted nodes
- Offline nodes get negative trust signals
- get_trusted_nodes filters correctly
- Persistence of trust state works
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time

import pytest

from shared.trust import NodeMetrics, TrustEvaluator, TrustLevel


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_data_dir():
    """Create a temporary data directory, clean up after."""
    d = tempfile.mkdtemp(prefix="trust_integration_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _good_heartbeat_metrics() -> dict:
    """Heartbeat metrics that produce a high trust score."""
    return {
        "cpu_percent": 20,
        "memory_percent": 30,
        "messages_sent": 1000,
        "messages_received": 1000,
        "hmac_failures": 0,
        "threat_detections": 0,
        "uptime_seconds": 3600,
        "total_seconds": 3600,
        "tasks_completed": 100,
        "tasks_failed": 0,
    }


def _bad_heartbeat_metrics() -> dict:
    """Heartbeat metrics that produce a low trust score."""
    return {
        "cpu_percent": 80,
        "memory_percent": 90,
        "messages_sent": 100,
        "messages_received": 100,
        "hmac_failures": 150,
        "threat_detections": 5,
        "uptime_seconds": 10,
        "total_seconds": 100,
        "tasks_completed": 5,
        "tasks_failed": 95,
    }


def _minimal_heartbeat_metrics() -> dict:
    """Heartbeat with only CPU/mem (no trust fields) — backward compat."""
    return {
        "cpu_percent": 50,
        "memory_percent": 50,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CapabilityRegistry Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestCapabilityRegistryTrust:
    """TrustEvaluator integration with CapabilityRegistry."""

    def test_heartbeat_updates_trust_score(self, tmp_data_dir):
        """Heartbeat with good metrics should produce a high trust score."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(data_dir=tmp_data_dir)
        reg.register({"node_id": "node-1", "capabilities": ["python"]})

        # Send good heartbeat
        result = reg.heartbeat("node-1", _good_heartbeat_metrics())
        assert result is True

        node = reg.get_node("node-1")
        assert node is not None
        assert "trust_score" in node
        assert "trust_level" in node
        assert node["trust_score"] >= 0.8
        assert node["trust_level"] == "PRIVILEGED"

    def test_bad_metrics_low_trust(self, tmp_data_dir):
        """Heartbeat with bad metrics should produce a low trust score."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(data_dir=tmp_data_dir)
        reg.register({"node_id": "node-bad", "capabilities": ["python"]})

        reg.heartbeat("node-bad", _bad_heartbeat_metrics())
        node = reg.get_node("node-bad")
        assert node["trust_score"] < 0.5

    def test_heartbeat_without_trust_fields_backward_compat(self, tmp_data_dir):
        """Heartbeat with only CPU/mem (no trust fields) still works."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(data_dir=tmp_data_dir)
        reg.register({"node_id": "node-compat", "capabilities": []})

        result = reg.heartbeat("node-compat", _minimal_heartbeat_metrics())
        assert result is True

        node = reg.get_node("node-compat")
        assert node is not None
        # Should still have trust_score (defaults)
        assert "trust_score" in node
        assert "trust_level" in node

    def test_heartbeat_without_metrics_no_trust_update(self, tmp_data_dir):
        """Heartbeat without metrics dict should not crash."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(data_dir=tmp_data_dir)
        reg.register({"node_id": "node-nom", "capabilities": []})

        result = reg.heartbeat("node-nom")
        assert result is True

        node = reg.get_node("node-nom")
        # No trust_score since no metrics were sent
        assert "trust_score" not in node

    def test_offline_node_gets_negative_trust_signal(self, tmp_data_dir):
        """When a node goes offline, its trust score should decrease."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(
            data_dir=tmp_data_dir,
            heartbeat_interval=1,
            heartbeat_timeout=2,
        )
        reg.register({"node_id": "node-off", "capabilities": []})

        # Give it perfect metrics first
        reg.heartbeat("node-off", _good_heartbeat_metrics())
        node = reg.get_node("node-off")
        good_score = node["trust_score"]

        # Wait for timeout
        time.sleep(3)
        reg._check_heartbeats()

        node = reg.get_node("node-off")
        assert node["status"] == "offline"
        # Trust score should have decreased due to threat detection
        assert node["trust_score"] <= good_score

    def test_assign_task_prefers_trusted_node(self, tmp_data_dir):
        """Task assignment should prefer nodes with higher trust scores."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(data_dir=tmp_data_dir)
        reg.register({"node_id": "trusted", "capabilities": ["python"]})
        reg.register({"node_id": "untrusted", "capabilities": ["python"]})

        # Give good metrics to 'trusted'
        reg.heartbeat("trusted", _good_heartbeat_metrics())
        # Give bad metrics to 'untrusted'
        reg.heartbeat("untrusted", _bad_heartbeat_metrics())

        # Same load, but different trust
        with reg._lock:
            reg._nodes["trusted"]["load_score"] = 0.5
            reg._nodes["untrusted"]["load_score"] = 0.5

        chosen = reg.assign_task(["python"])
        assert chosen == "trusted"

    def test_get_trusted_nodes(self, tmp_data_dir):
        """get_trusted_nodes should filter by trust level."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(data_dir=tmp_data_dir)
        reg.register({"node_id": "good", "capabilities": []})
        reg.register({"node_id": "bad", "capabilities": []})

        reg.heartbeat("good", _good_heartbeat_metrics())
        reg.heartbeat("bad", _bad_heartbeat_metrics())

        # Only PRIVILEGED nodes
        trusted = reg.get_trusted_nodes(TrustLevel.PRIVILEGED)
        ids = [n["node_id"] for n in trusted]
        assert "good" in ids
        assert "bad" not in ids

        # All nodes at STANDARD or above
        standard = reg.get_trusted_nodes(TrustLevel.STANDARD)
        standard_ids = [n["node_id"] for n in standard]
        assert "good" in standard_ids

    def test_trust_state_persists(self, tmp_data_dir):
        """Trust state should survive registry save/load."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg1 = CapabilityRegistry(data_dir=tmp_data_dir)
        reg1.register({"node_id": "persist-node", "capabilities": []})
        reg1.heartbeat("persist-node", _good_heartbeat_metrics())

        node1 = reg1.get_node("persist-node")
        saved_score = node1["trust_score"]

        # Create new registry from same data dir
        reg2 = CapabilityRegistry(data_dir=tmp_data_dir)
        node2 = reg2.get_node("persist-node")
        assert node2 is not None
        # Trust score should be in the persisted node data
        assert node2.get("trust_score") == saved_score

        # The trust evaluator should also have the state
        level = reg2.trust_evaluator.get_level("persist-node")
        assert level == TrustLevel.PRIVILEGED

    def test_multiple_heartbeats_update_trust(self, tmp_data_dir):
        """Multiple heartbeats should accumulate trust data."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(data_dir=tmp_data_dir)
        reg.register({"node_id": "node-multi", "capabilities": []})

        # First heartbeat
        reg.heartbeat("node-multi", _good_heartbeat_metrics())
        score1 = reg.get_node("node-multi")["trust_score"]

        # Second heartbeat with even better metrics
        metrics = _good_heartbeat_metrics()
        metrics["messages_sent"] = 5000
        metrics["messages_received"] = 5000
        reg.heartbeat("node-multi", metrics)
        score2 = reg.get_node("node-multi")["trust_score"]

        # Both should be high
        assert score1 >= 0.8
        assert score2 >= 0.8

    def test_trust_evaluator_property(self, tmp_data_dir):
        """The trust_evaluator property should return the evaluator."""
        from cloud.engines.capability_registry import CapabilityRegistry

        reg = CapabilityRegistry(data_dir=tmp_data_dir)
        assert isinstance(reg.trust_evaluator, TrustEvaluator)


# ═══════════════════════════════════════════════════════════════════════════
# SwarmCoordinator Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestSwarmCoordinatorTrust:
    """TrustEvaluator integration with SwarmCoordinator."""

    def test_heartbeat_updates_trust_score(self, tmp_data_dir):
        """Heartbeat with good metrics should produce a high trust score."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        coord.register_node({"node_id": "node-1", "capabilities": ["python"]})

        result = coord.heartbeat("node-1", _good_heartbeat_metrics())
        assert result is True

        node = coord.get_node("node-1")
        assert node is not None
        assert "trust_score" in node
        assert "trust_level" in node
        assert node["trust_score"] >= 0.8
        assert node["trust_level"] == "PRIVILEGED"

    def test_bad_metrics_low_trust(self, tmp_data_dir):
        """Heartbeat with bad metrics should produce a low trust score."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        coord.register_node({"node_id": "node-bad", "capabilities": []})

        coord.heartbeat("node-bad", _bad_heartbeat_metrics())
        node = coord.get_node("node-bad")
        assert node["trust_score"] < 0.5

    def test_backward_compat_no_trust_fields(self, tmp_data_dir):
        """Heartbeat without trust fields should still work."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        coord.register_node({"node_id": "node-compat", "capabilities": []})

        result = coord.heartbeat("node-compat", _minimal_heartbeat_metrics())
        assert result is True

        node = coord.get_node("node-compat")
        assert "trust_score" in node

    def test_get_least_loaded_prefers_trusted(self, tmp_data_dir):
        """get_least_loaded_node should prefer trusted nodes."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        coord.register_node({"node_id": "trusted", "capabilities": ["ml"]})
        coord.register_node({"node_id": "untrusted", "capabilities": ["ml"]})

        # Give good metrics to trusted, bad to untrusted
        coord.heartbeat("trusted", _good_heartbeat_metrics())
        coord.heartbeat("untrusted", _bad_heartbeat_metrics())

        # Equalize load scores
        with coord._lock:
            coord._nodes["trusted"]["load_score"] = 0.5
            coord._nodes["untrusted"]["load_score"] = 0.5

        chosen = coord.get_least_loaded_node(required_capabilities=["ml"])
        assert chosen == "trusted"

    def test_get_least_loaded_considers_load_and_trust(self, tmp_data_dir):
        """A slightly more loaded but much more trusted node should win."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        coord.register_node({"node_id": "high-trust-high-load", "capabilities": []})
        coord.register_node({"node_id": "low-trust-low-load", "capabilities": []})

        coord.heartbeat("high-trust-high-load", _good_heartbeat_metrics())
        coord.heartbeat("low-trust-low-load", _bad_heartbeat_metrics())

        # high-trust node has higher load, but trust should compensate
        with coord._lock:
            coord._nodes["high-trust-high-load"]["load_score"] = 0.6
            coord._nodes["low-trust-low-load"]["load_score"] = 0.2

        # Composite: high-trust = 0.6*0.6 + (1-0.96)*0.4 = 0.36 + 0.016 = 0.376
        # Composite: low-trust = 0.2*0.6 + (1-0.15)*0.4 = 0.12 + 0.34 = 0.46
        chosen = coord.get_least_loaded_node()
        assert chosen == "high-trust-high-load"

    def test_get_trusted_nodes(self, tmp_data_dir):
        """get_trusted_nodes should filter by trust level."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        coord.register_node({"node_id": "good", "capabilities": []})
        coord.register_node({"node_id": "bad", "capabilities": []})

        coord.heartbeat("good", _good_heartbeat_metrics())
        coord.heartbeat("bad", _bad_heartbeat_metrics())

        # Only PRIVILEGED
        trusted = coord.get_trusted_nodes(TrustLevel.PRIVILEGED)
        ids = [n["node_id"] for n in trusted]
        assert "good" in ids
        assert "bad" not in ids

        # HIGH level — should include good (PRIVILEGED >= HIGH)
        high = coord.get_trusted_nodes(TrustLevel.HIGH)
        high_ids = [n["node_id"] for n in high]
        assert "good" in high_ids

    def test_get_trusted_nodes_only_online(self, tmp_data_dir):
        """get_trusted_nodes should only return online nodes."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        coord.register_node({"node_id": "online-node", "capabilities": []})
        coord.register_node({"node_id": "offline-node", "capabilities": []})

        coord.heartbeat("online-node", _good_heartbeat_metrics())
        coord.heartbeat("offline-node", _good_heartbeat_metrics())

        # Force one node offline
        with coord._lock:
            coord._nodes["offline-node"]["status"] = "offline"

        trusted = coord.get_trusted_nodes(TrustLevel.STANDARD)
        ids = [n["node_id"] for n in trusted]
        assert "online-node" in ids
        assert "offline-node" not in ids

    def test_offline_node_trust_decreases(self, tmp_data_dir):
        """When a node goes offline, trust should decrease."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(
            data_dir=tmp_data_dir,
            heartbeat_interval=1,
            heartbeat_timeout=2,
        )
        coord.register_node({"node_id": "node-off", "capabilities": []})

        coord.heartbeat("node-off", _good_heartbeat_metrics())
        good_score = coord.get_node("node-off")["trust_score"]

        # Wait for timeout
        time.sleep(3)
        coord._check_status()

        node = coord.get_node("node-off")
        assert node["status"] == "offline"
        assert node["trust_score"] <= good_score

    def test_trust_state_persists(self, tmp_data_dir):
        """Trust state should survive coordinator save/load."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord1 = SwarmCoordinator(data_dir=tmp_data_dir)
        coord1.register_node({"node_id": "persist", "capabilities": []})
        coord1.heartbeat("persist", _good_heartbeat_metrics())

        saved_score = coord1.get_node("persist")["trust_score"]

        # Reload
        coord2 = SwarmCoordinator(data_dir=tmp_data_dir)
        node2 = coord2.get_node("persist")
        assert node2 is not None
        assert node2.get("trust_score") == saved_score

        # Evaluator state should also persist
        level = coord2.trust_evaluator.get_level("persist")
        assert level == TrustLevel.PRIVILEGED

    def test_trust_evaluator_property(self, tmp_data_dir):
        """The trust_evaluator property should return the evaluator."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        assert isinstance(coord.trust_evaluator, TrustEvaluator)

    def test_assign_task_increments_count(self, tmp_data_dir):
        """assign_task should still work (backward compat)."""
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        coord = SwarmCoordinator(data_dir=tmp_data_dir)
        coord.register_node({"node_id": "worker", "capabilities": []})
        coord.assign_task("worker", "task-123")

        node = coord.get_node("worker")
        assert node["task_count"] == 1
        assert "task-123" in node["assigned_tasks"]


# ═══════════════════════════════════════════════════════════════════════════
# Cross-Engine Consistency
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossEngineConsistency:
    """Both engines should compute consistent trust scores."""

    def test_same_metrics_same_score(self, tmp_data_dir):
        """Both engines should produce the same trust score for same metrics."""
        from cloud.engines.capability_registry import CapabilityRegistry
        from cloud.engines.swarm_coordinator import SwarmCoordinator

        reg_dir = os.path.join(tmp_data_dir, "reg")
        coord_dir = os.path.join(tmp_data_dir, "coord")

        reg = CapabilityRegistry(data_dir=reg_dir)
        coord = SwarmCoordinator(data_dir=coord_dir)

        reg.register({"node_id": "n1", "capabilities": []})
        coord.register_node({"node_id": "n1", "capabilities": []})

        metrics = _good_heartbeat_metrics()
        reg.heartbeat("n1", metrics)
        coord.heartbeat("n1", metrics)

        reg_score = reg.get_node("n1")["trust_score"]
        coord_score = coord.get_node("n1")["trust_score"]

        assert reg_score == pytest.approx(coord_score, abs=1e-6)
