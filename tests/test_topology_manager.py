"""Tests for Swarm Topology Manager (ClawShell v2.1)."""

import pytest
import time

from cloud.engines.topology_manager import (
    TopologyType,
    NodeRole,
    TopologyNode,
    TopologyEdge,
    TopologyPartition,
    TopologyManager,
    RebalanceResult,
    TopologyState,
)


# ═══════════════════════════════════════════════════════════════════════
# Enum & Data Class Tests
# ═══════════════════════════════════════════════════════════════════════

class TestEnums:
    def test_topology_type_values(self):
        assert TopologyType.MESH.value == "mesh"
        assert TopologyType.HIERARCHICAL.value == "hierarchical"
        assert TopologyType.CENTRALIZED.value == "centralized"
        assert TopologyType.HYBRID.value == "hybrid"

    def test_node_role_values(self):
        assert NodeRole.QUEEN.value == "queen"
        assert NodeRole.WORKER.value == "worker"
        assert NodeRole.COORDINATOR.value == "coordinator"
        assert NodeRole.PEER.value == "peer"


class TestTopologyNode:
    def test_defaults(self):
        node = TopologyNode(node_id="n1", role=NodeRole.WORKER)
        assert node.node_id == "n1"
        assert node.status == "online"
        assert node.capabilities == []
        assert node.trust_score == 0.5
        assert node.connections == []
        assert node.workload == 0.0
        assert node.partition_id is None

    def test_to_dict_roundtrip(self):
        node = TopologyNode(
            node_id="n1", role=NodeRole.QUEEN,
            capabilities=["gpu", "cpu"], trust_score=0.9,
            workload=0.3, partition_id="p1",
        )
        d = node.to_dict()
        restored = TopologyNode.from_dict(d)
        assert restored.node_id == "n1"
        assert restored.role == NodeRole.QUEEN
        assert restored.capabilities == ["gpu", "cpu"]
        assert restored.trust_score == 0.9
        assert restored.partition_id == "p1"


class TestTopologyEdge:
    def test_defaults(self):
        edge = TopologyEdge(from_node="a", to_node="b")
        assert edge.weight == 1.0
        assert edge.bidirectional is True
        assert edge.latency_ms == 0.0

    def test_to_dict_roundtrip(self):
        edge = TopologyEdge(from_node="a", to_node="b", weight=2.5,
                            bidirectional=False, latency_ms=15.0)
        d = edge.to_dict()
        restored = TopologyEdge.from_dict(d)
        assert restored.from_node == "a"
        assert restored.to_node == "b"
        assert restored.weight == 2.5
        assert restored.bidirectional is False
        assert restored.latency_ms == 15.0


class TestTopologyPartition:
    def test_defaults(self):
        p = TopologyPartition(partition_id="p1")
        assert p.nodes == []
        assert p.leader is None
        assert p.replica_count == 1

    def test_to_dict_roundtrip(self):
        p = TopologyPartition(partition_id="p1", nodes=["n1", "n2"],
                              leader="n1", replica_count=3)
        d = p.to_dict()
        restored = TopologyPartition.from_dict(d)
        assert restored.partition_id == "p1"
        assert restored.nodes == ["n1", "n2"]
        assert restored.leader == "n1"
        assert restored.replica_count == 3


# ═══════════════════════════════════════════════════════════════════════
# TopologyManager — MESH
# ═══════════════════════════════════════════════════════════════════════

class TestMeshTopology:
    def test_add_node_peer_role(self):
        tm = TopologyManager(TopologyType.MESH)
        node = tm.add_node("n1")
        assert node.role == NodeRole.PEER

    def test_auto_connect_all(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.add_node("n2")
        tm.add_node("n3")

        n1 = tm.get_topology_state().nodes["n1"]
        n2 = tm.get_topology_state().nodes["n2"]
        n3 = tm.get_topology_state().nodes["n3"]

        # Every node should be connected to every other
        assert "n2" in n1["connections"]
        assert "n3" in n1["connections"]
        assert "n1" in n2["connections"]
        assert "n3" in n2["connections"]
        assert "n1" in n3["connections"]
        assert "n2" in n3["connections"]

    def test_bfs_route_direct(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.add_node("n2")
        route = tm.get_route("n1", "n2")
        assert route == ["n1", "n2"]

    def test_bfs_route_same_node(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        assert tm.get_route("n1", "n1") == ["n1"]

    def test_bfs_route_nonexistent(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        assert tm.get_route("n1", "ghost") is None

    def test_remove_node_mesh(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.add_node("n2")
        tm.add_node("n3")
        result = tm.remove_node("n2")
        assert isinstance(result, RebalanceResult)
        assert "n2" in result.moved_nodes
        state = tm.get_topology_state()
        assert "n2" not in state.nodes
        # n1 and n3 should still be connected
        assert "n3" in state.nodes["n1"]["connections"]

    def test_duplicate_node_raises(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        with pytest.raises(ValueError, match="already exists"):
            tm.add_node("n1")

    def test_remove_nonexistent_raises(self):
        tm = TopologyManager(TopologyType.MESH)
        with pytest.raises(ValueError, match="not found"):
            tm.remove_node("ghost")


# ═══════════════════════════════════════════════════════════════════════
# TopologyManager — HIERARCHICAL
# ═══════════════════════════════════════════════════════════════════════

class TestHierarchicalTopology:
    def test_first_node_is_queen(self):
        tm = TopologyManager(TopologyType.HIERARCHICAL)
        node = tm.add_node("n1")
        assert node.role == NodeRole.QUEEN

    def test_subsequent_nodes_are_workers(self):
        tm = TopologyManager(TopologyType.HIERARCHICAL)
        tm.add_node("n1")
        n2 = tm.add_node("n2")
        n3 = tm.add_node("n3")
        assert n2.role == NodeRole.WORKER
        assert n3.role == NodeRole.WORKER

    def test_workers_connect_to_queen(self):
        tm = TopologyManager(TopologyType.HIERARCHICAL)
        tm.add_node("n1")
        tm.add_node("n2")
        tm.add_node("n3")

        state = tm.get_topology_state()
        # n2 and n3 should be connected to queen
        assert "n1" in state.nodes["n2"]["connections"]
        assert "n1" in state.nodes["n3"]["connections"]

    def test_remove_queen_elects_new(self):
        tm = TopologyManager(TopologyType.HIERARCHICAL)
        tm.add_node("n1", trust_score=0.5)
        tm.update_node_metrics("n1", workload=0.5)
        tm.add_node("n2", trust_score=0.9)
        tm.update_node_metrics("n2", workload=0.1)
        tm.add_node("n3", trust_score=0.3)
        tm.update_node_metrics("n3", workload=0.7)

        result = tm.remove_node("n1")
        state = tm.get_topology_state()
        # n2 has best score: 0.9*0.6 + 0.9*0.4 = 0.54+0.36 = 0.90
        assert state.queen_id == "n2"
        assert result.leader_elected == "n2"


# ═══════════════════════════════════════════════════════════════════════
# TopologyManager — CENTRALIZED
# ═══════════════════════════════════════════════════════════════════════

class TestCentralizedTopology:
    def test_first_node_is_queen(self):
        tm = TopologyManager(TopologyType.CENTRALIZED)
        node = tm.add_node("n1")
        assert node.role == NodeRole.QUEEN

    def test_star_topology(self):
        tm = TopologyManager(TopologyType.CENTRALIZED)
        tm.add_node("queen")
        tm.add_node("w1")
        tm.add_node("w2")
        tm.add_node("w3")

        state = tm.get_topology_state()
        # All workers should only be connected to queen
        for wid in ["w1", "w2", "w3"]:
            assert "queen" in state.nodes[wid]["connections"]


# ═══════════════════════════════════════════════════════════════════════
# TopologyManager — HYBRID
# ═══════════════════════════════════════════════════════════════════════

class TestHybridTopology:
    def test_partition_assignment(self):
        tm = TopologyManager(TopologyType.HYBRID, max_partition_size=3)
        tm.add_node("n1", partition_id="p1")
        tm.add_node("n2", partition_id="p1")
        tm.add_node("n3", partition_id="p2")

        state = tm.get_topology_state()
        assert state.nodes["n1"]["partition_id"] == "p1"
        assert state.nodes["n2"]["partition_id"] == "p1"
        assert state.nodes["n3"]["partition_id"] == "p2"

    def test_first_in_partition_is_coordinator(self):
        tm = TopologyManager(TopologyType.HYBRID)
        tm.add_node("n1", partition_id="p1")
        assert tm.get_topology_state().nodes["n1"]["role"] == "coordinator"

    def test_auto_partition_assignment(self):
        tm = TopologyManager(TopologyType.HYBRID, max_partition_size=2)
        tm.add_node("n1")  # auto -> partition-0
        tm.add_node("n2")  # auto -> partition-0 (smallest, not full)
        tm.add_node("n3")  # auto -> partition-0 full, so new partition

        state = tm.get_topology_state()
        p1 = state.nodes["n1"]["partition_id"]
        p2 = state.nodes["n2"]["partition_id"]
        p3 = state.nodes["n3"]["partition_id"]
        assert p1 == p2
        assert p3 != p1  # Should be in a different partition

    def test_connectivity_within_partition(self):
        tm = TopologyManager(TopologyType.HYBRID)
        tm.add_node("n1", partition_id="p1")
        tm.add_node("n2", partition_id="p1")
        tm.add_node("n3", partition_id="p1")

        state = tm.get_topology_state()
        # All in same partition should be connected
        assert "n2" in state.nodes["n1"]["connections"]
        assert "n3" in state.nodes["n1"]["connections"]
        assert "n1" in state.nodes["n2"]["connections"]
        assert "n3" in state.nodes["n2"]["connections"]


# ═══════════════════════════════════════════════════════════════════════
# Leader Election
# ═══════════════════════════════════════════════════════════════════════

class TestLeaderElection:
    def test_elect_leader_formula(self):
        """Score = trust*0.6 + (1-workload)*0.4"""
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1", trust_score=0.9)
        tm.update_node_metrics("n1", workload=0.1)
        tm.add_node("n2", trust_score=0.5)
        tm.update_node_metrics("n2", workload=0.5)
        tm.add_node("n3", trust_score=0.8)
        tm.update_node_metrics("n3", workload=0.3)

        leader = tm.elect_leader()
        assert leader == "n1"

    def test_elect_leader_from_candidates(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1", trust_score=0.9)
        tm.update_node_metrics("n1", workload=0.1)
        tm.add_node("n2", trust_score=0.5)
        tm.update_node_metrics("n2", workload=0.5)
        tm.add_node("n3", trust_score=0.8)
        tm.update_node_metrics("n3", workload=0.3)

        # Only consider n2 and n3
        leader = tm.elect_leader(candidates=["n2", "n3"])
        assert leader == "n3"

    def test_elect_leader_no_candidates(self):
        tm = TopologyManager(TopologyType.MESH)
        assert tm.elect_leader(candidates=[]) is None

    def test_elect_leader_all_offline(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.update_node_status("n1", "offline")
        assert tm.elect_leader() is None

    def test_elect_leader_updates_queen_id(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1", trust_score=0.5)
        tm.update_node_metrics("n1", workload=0.5)
        tm.add_node("n2", trust_score=0.9)
        tm.update_node_metrics("n2", workload=0.1)
        leader = tm.elect_leader()
        state = tm.get_topology_state()
        assert state.queen_id == "n2"


# ═══════════════════════════════════════════════════════════════════════
# Status & Metrics Updates
# ═══════════════════════════════════════════════════════════════════════

class TestUpdates:
    def test_update_status(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.update_node_status("n1", "degraded")
        state = tm.get_topology_state()
        assert state.nodes["n1"]["status"] == "degraded"

    def test_update_status_nonexistent(self):
        tm = TopologyManager(TopologyType.MESH)
        with pytest.raises(ValueError):
            tm.update_node_status("ghost", "offline")

    def test_update_metrics(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.update_node_metrics("n1", trust_score=0.95, workload=0.2,
                               capabilities=["gpu"])
        state = tm.get_topology_state()
        assert state.nodes["n1"]["trust_score"] == 0.95
        assert state.nodes["n1"]["workload"] == 0.2
        assert state.nodes["n1"]["capabilities"] == ["gpu"]

    def test_update_metrics_clamping(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.update_node_metrics("n1", trust_score=1.5)
        tm.update_node_metrics("n1", workload=-0.1)
        state = tm.get_topology_state()
        assert state.nodes["n1"]["trust_score"] == 1.0
        assert state.nodes["n1"]["workload"] == 0.0

    def test_update_metrics_nonexistent(self):
        tm = TopologyManager(TopologyType.MESH)
        with pytest.raises(ValueError):
            tm.update_node_metrics("ghost", trust_score=0.5)


# ═══════════════════════════════════════════════════════════════════════
# Routing (BFS)
# ═══════════════════════════════════════════════════════════════════════

class TestRouting:
    def test_bfs_multi_hop(self):
        tm = TopologyManager(TopologyType.HIERARCHICAL)
        tm.add_node("queen")
        tm.add_node("w1")
        tm.add_node("w2")

        # w1 → queen → w2
        route = tm.get_route("w1", "w2")
        assert route is not None
        assert route[0] == "w1"
        assert route[-1] == "w2"
        assert "queen" in route

    def test_bfs_no_path(self):
        tm = TopologyManager(TopologyType.HYBRID)
        tm.add_node("n1", partition_id="p1")
        tm.add_node("n2", partition_id="p2")

        # Different partitions with no cross-connect should have no path
        # unless rebalance adds edges (it doesn't across partitions)
        route = tm.get_route("n1", "n2")
        # May be None (no cross-partition edges by default) or may have path
        # depending on connectivity. At minimum, it shouldn't crash.
        # The nodes are in different partitions, no cross edges → None
        assert route is None


# ═══════════════════════════════════════════════════════════════════════
# Rebalance
# ═══════════════════════════════════════════════════════════════════════

class TestRebalance:
    def test_rebalance_mesh_adds_missing_edges(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.add_node("n2")
        tm.add_node("n3")
        # Manually break an edge — find the n1-n3 edge key
        edge_key = ("n1", "n3") if ("n1", "n3") in tm._edges else ("n3", "n1")
        del tm._edges[edge_key]
        for a, b in [("n1", "n3"), ("n3", "n1")]:
            if b in tm._nodes[a].connections:
                tm._nodes[a].connections.remove(b)
        result = tm.rebalance()
        found = any(
            set(pair) == {"n1", "n3"} for pair in result.added_edges
        )
        assert found

    def test_rebalance_hierarchical_elects_queen(self):
        tm = TopologyManager(TopologyType.HIERARCHICAL)
        tm.add_node("n1", trust_score=0.9)
        tm.update_node_metrics("n1", workload=0.1)
        tm.add_node("n2", trust_score=0.5)
        tm.update_node_metrics("n2", workload=0.5)

        # Remove queen manually
        tm._queen_id = None
        tm._nodes["n1"].role = NodeRole.WORKER

        result = tm.rebalance()
        assert result.leader_elected is not None
        assert tm._queen_id == "n1"  # n1 has better score


# ═══════════════════════════════════════════════════════════════════════
# Topology State Snapshot
# ═══════════════════════════════════════════════════════════════════════

class TestTopologyState:
    def test_get_topology_state(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        tm.add_node("n2")

        state = tm.get_topology_state()
        assert isinstance(state, TopologyState)
        assert state.topology_type == "mesh"
        assert "n1" in state.nodes
        assert "n2" in state.nodes
        assert state.timestamp > 0

    def test_state_snapshot_independence(self):
        """Modifying snapshot shouldn't affect the manager."""
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        state = tm.get_topology_state()
        state.nodes["n1"]["trust_score"] = 0.0
        assert tm.get_topology_state().nodes["n1"]["trust_score"] == 0.5


# ═══════════════════════════════════════════════════════════════════════
# RebalanceResult
# ═══════════════════════════════════════════════════════════════════════

class TestRebalanceResult:
    def test_defaults(self):
        r = RebalanceResult()
        assert r.moved_nodes == []
        assert r.added_edges == []
        assert r.removed_edges == []
        assert r.partitions_changed is False
        assert r.leader_elected is None

    def test_to_dict(self):
        r = RebalanceResult(moved_nodes=["n1"], added_edges=[("a", "b")])
        d = r.to_dict()
        assert d["moved_nodes"] == ["n1"]
        assert d["added_edges"] == [("a", "b")]


# ═══════════════════════════════════════════════════════════════════════
# Edge Cases & Integration
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_single_node(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("only")
        state = tm.get_topology_state()
        assert len(state.nodes) == 1
        assert state.nodes["only"]["connections"] == []

    def test_remove_last_node(self):
        tm = TopologyManager(TopologyType.MESH)
        tm.add_node("n1")
        result = tm.remove_node("n1")
        state = tm.get_topology_state()
        assert len(state.nodes) == 0
        assert state.queen_id is None

    def test_full_lifecycle(self):
        """Add nodes → update → elect → route → remove → verify."""
        tm = TopologyManager(TopologyType.HIERARCHICAL)
        tm.add_node("queen", capabilities=["management"], trust_score=0.8)
        tm.add_node("w1", capabilities=["gpu"], trust_score=0.7)
        tm.update_node_metrics("w1", workload=0.3)
        tm.add_node("w2", capabilities=["cpu"], trust_score=0.6)
        tm.update_node_metrics("w2", workload=0.5)

        # Update metrics
        tm.update_node_metrics("w1", trust_score=0.95, workload=0.1)

        # Route
        route = tm.get_route("w1", "w2")
        assert route is not None
        assert "queen" in route

        # Elect new leader
        leader = tm.elect_leader(["w1", "w2"])
        assert leader == "w1"  # 0.95*0.6 + 0.9*0.4 = 0.93

        # Remove queen
        result = tm.remove_node("queen")
        assert isinstance(result, RebalanceResult)

        # Verify new topology
        state = tm.get_topology_state()
        assert len(state.nodes) == 2

    def test_mixed_topology_operations(self):
        """Verify operations don't interfere across topology types."""
        mesh = TopologyManager(TopologyType.MESH)
        hier = TopologyManager(TopologyType.HIERARCHICAL)

        mesh.add_node("m1")
        hier.add_node("h1")

        assert mesh.get_topology_state().topology_type == "mesh"
        assert hier.get_topology_state().topology_type == "hierarchical"

        mesh.add_node("m2")
        hier.add_node("h2")

        # Mesh should have edge between m1 and m2
        m_state = mesh.get_topology_state()
        assert len(m_state.edges) >= 1

        # Hierarchical should have queen + worker
        h_state = hier.get_topology_state()
        assert h_state.nodes["h1"]["role"] == "queen"
        assert h_state.nodes["h2"]["role"] == "worker"
