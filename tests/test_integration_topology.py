"""Integration tests for TopologyManager API endpoints.

Tests the REST API endpoints for topology management,
verifying that nodes appear in topology when registered.
"""

import pytest
import sys
import os

# Ensure the clawshell package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixtures ──────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global engine references before each test."""
    import cloud.main as main_mod
    # Save originals
    orig = {
        k: getattr(main_mod, k)
        for k in dir(main_mod)
        if k.startswith("_") and not k.startswith("__") and isinstance(getattr(main_mod, k, None), type(None)) or k in (
            "_eventbus", "_scheduler", "_capability_registry", "_task_board",
            "_skill_market", "_swarm", "_evolution", "_review", "_broadcast",
            "_n8n_bridge", "_insight", "_brain", "_topology",
        )
    }
    yield
    # Restore
    for k, v in orig.items():
        if hasattr(main_mod, k):
            setattr(main_mod, k, v)


@pytest.fixture
def topology():
    """Create a fresh TopologyManager instance."""
    from cloud.engines.topology_manager import TopologyManager, TopologyType
    return TopologyManager(topology_type=TopologyType.MESH)


@pytest.fixture
def capability_registry(tmp_path):
    """Create a fresh CapabilityRegistry instance."""
    from cloud.engines.capability_registry import CapabilityRegistry
    return CapabilityRegistry(data_dir=str(tmp_path))


@pytest.fixture
def app(topology, capability_registry):
    """Create a FastAPI test app with topology and capability registry."""
    import cloud.main as main_mod
    main_mod._topology = topology
    main_mod._capability_registry = capability_registry
    app = main_mod.create_app()
    return app


@pytest.fixture
def client(app):
    """Create a FastAPI TestClient."""
    from fastapi.testclient import TestClient
    return TestClient(app)


# ── Topology State Endpoint ───────────────────────────

class TestGetTopology:
    def test_get_topology_empty(self, client):
        """GET /api/v1/topology returns empty topology."""
        resp = client.get("/api/v1/topology")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["topology_type"] == "mesh"
        assert data["data"]["nodes"] == {}
        assert data["data"]["edges"] == []
        assert data["data"]["partitions"] == []
        assert data["data"]["queen_id"] is None

    def test_get_topology_with_nodes(self, client, topology):
        """GET /api/v1/topology returns nodes after adding them."""
        topology.add_node("n1")
        topology.add_node("n2")
        resp = client.get("/api/v1/topology")
        data = resp.json()
        assert data["success"] is True
        assert "n1" in data["data"]["nodes"]
        assert "n2" in data["data"]["nodes"]


# ── Nodes List Endpoint ───────────────────────────────

class TestListTopologyNodes:
    def test_list_nodes_empty(self, client):
        """GET /api/v1/topology/nodes returns empty list."""
        resp = client.get("/api/v1/topology/nodes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["nodes"] == []
        assert data["data"]["count"] == 0

    def test_list_nodes_populated(self, client, topology):
        """GET /api/v1/topology/nodes returns nodes with roles and trust."""
        topology.add_node("n1", trust_score=0.9)
        topology.add_node("n2", trust_score=0.7)
        resp = client.get("/api/v1/topology/nodes")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
        node_ids = [n["node_id"] for n in data["data"]["nodes"]]
        assert "n1" in node_ids
        assert "n2" in node_ids


# ── Add Node Endpoint ─────────────────────────────────

class TestAddTopologyNode:
    def test_add_node_success(self, client):
        """POST /api/v1/topology/nodes adds a node."""
        resp = client.post("/api/v1/topology/nodes", json={
            "node_id": "edge-1",
            "capabilities": ["gpu", "cpu"],
            "trust_score": 0.85,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["node_id"] == "edge-1"
        assert data["data"]["role"] == "peer"  # MESH topology
        assert data["data"]["trust_score"] == 0.85
        assert data["data"]["capabilities"] == ["gpu", "cpu"]

    def test_add_node_missing_id(self, client):
        """POST /api/v1/topology/nodes without node_id returns error."""
        resp = client.post("/api/v1/topology/nodes", json={
            "capabilities": ["gpu"],
        })
        data = resp.json()
        assert data["success"] is False
        assert "node_id is required" in data["error"]

    def test_add_node_invalid_json(self, client):
        """POST /api/v1/topology/nodes with bad body returns error."""
        resp = client.post(
            "/api/v1/topology/nodes",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        data = resp.json()
        assert data["success"] is False
        assert "Invalid JSON" in data["error"]

    def test_add_node_duplicate(self, client):
        """POST /api/v1/topology/nodes with duplicate ID returns error."""
        client.post("/api/v1/topology/nodes", json={"node_id": "n1"})
        resp = client.post("/api/v1/topology/nodes", json={"node_id": "n1"})
        data = resp.json()
        assert data["success"] is False
        assert "already exists" in data["error"]

    def test_add_node_with_role(self, client):
        """POST /api/v1/topology/nodes with explicit role."""
        resp = client.post("/api/v1/topology/nodes", json={
            "node_id": "queen-1",
            "role": "queen",
        })
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["role"] == "queen"

    def test_add_node_invalid_role(self, client):
        """POST /api/v1/topology/nodes with invalid role returns error."""
        resp = client.post("/api/v1/topology/nodes", json={
            "node_id": "n1",
            "role": "invalid_role",
        })
        data = resp.json()
        assert data["success"] is False
        assert "Invalid role" in data["error"]


# ── Remove Node Endpoint ──────────────────────────────

class TestRemoveTopologyNode:
    def test_remove_node_success(self, client, topology):
        """DELETE /api/v1/topology/nodes/{id} removes a node."""
        topology.add_node("n1")
        topology.add_node("n2")
        resp = client.delete("/api/v1/topology/nodes/n1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "n1" in data["data"]["moved_nodes"]

        # Verify node is gone
        state = topology.get_topology_state()
        assert "n1" not in state.nodes

    def test_remove_nonexistent_node(self, client):
        """DELETE /api/v1/topology/nodes/{id} with bad ID returns error."""
        resp = client.delete("/api/v1/topology/nodes/ghost")
        data = resp.json()
        assert data["success"] is False
        assert "not found" in data["error"]


# ── Route Endpoint ─────────────────────────────────────

class TestGetRoute:
    def test_route_found(self, client, topology):
        """GET /api/v1/topology/route finds path between connected nodes."""
        topology.add_node("n1")
        topology.add_node("n2")
        topology.add_node("n3")
        resp = client.get("/api/v1/topology/route", params={
            "from_node": "n1",
            "to_node": "n3",
        })
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["route"][0] == "n1"
        assert data["data"]["route"][-1] == "n3"
        assert data["data"]["hops"] >= 1

    def test_route_same_node(self, client, topology):
        """GET /api/v1/topology/route same source and dest."""
        topology.add_node("n1")
        resp = client.get("/api/v1/topology/route", params={
            "from_node": "n1",
            "to_node": "n1",
        })
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["route"] == ["n1"]
        assert data["data"]["hops"] == 0

    def test_route_not_found(self, client, topology):
        """GET /api/v1/topology/route returns error for disconnected nodes."""
        from cloud.engines.topology_manager import TopologyType
        # Use separate topology for isolation
        topology._topology_type = TopologyType.HYBRID
        topology.add_node("n1", partition_id="p1")
        topology.add_node("n2", partition_id="p2")
        resp = client.get("/api/v1/topology/route", params={
            "from_node": "n1",
            "to_node": "n2",
        })
        data = resp.json()
        assert data["success"] is False
        assert "No route found" in data["error"]

    def test_route_nonexistent_node(self, client, topology):
        """GET /api/v1/topology/route with nonexistent node returns error."""
        topology.add_node("n1")
        resp = client.get("/api/v1/topology/route", params={
            "from_node": "n1",
            "to_node": "ghost",
        })
        data = resp.json()
        assert data["success"] is False
        assert "No route found" in data["error"]


# ── Rebalance Endpoint ────────────────────────────────

class TestRebalance:
    def test_rebalance_success(self, client, topology):
        """POST /api/v1/topology/rebalance triggers rebalance."""
        topology.add_node("n1")
        topology.add_node("n2")
        resp = client.post("/api/v1/topology/rebalance")
        data = resp.json()
        assert data["success"] is True
        assert "moved_nodes" in data["data"]
        assert "added_edges" in data["data"]
        assert "removed_edges" in data["data"]

    def test_rebalance_empty(self, client):
        """POST /api/v1/topology/rebalance on empty topology."""
        resp = client.post("/api/v1/topology/rebalance")
        data = resp.json()
        assert data["success"] is True


# ── Leader Endpoint ───────────────────────────────────

class TestGetLeader:
    def test_leader_none_when_empty(self, client):
        """GET /api/v1/topology/leader returns None for empty topology."""
        resp = client.get("/api/v1/topology/leader")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["leader_id"] is None
        assert data["data"]["leader"] is None

    def test_leader_elected(self, client, topology):
        """GET /api/v1/topology/leader returns elected leader."""
        from cloud.engines.topology_manager import TopologyType
        # Use HIERARCHICAL so first node becomes queen
        topology._topology_type = TopologyType.HIERARCHICAL
        topology.add_node("n1", trust_score=0.9)
        topology.add_node("n2", trust_score=0.5)
        resp = client.get("/api/v1/topology/leader")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["leader_id"] == "n1"
        assert data["data"]["leader"] is not None
        assert data["data"]["leader"]["node_id"] == "n1"


# ── Auto-Registration Wiring ──────────────────────────

class TestAutoRegistration:
    """Test that nodes registered via /nodes/register also appear in topology."""

    def test_node_register_appears_in_topology(self, client, topology):
        """Registering a node via /nodes/register also adds to topology."""
        resp = client.post("/api/v1/nodes/register", json={
            "node_id": "edge-1",
            "capabilities": ["python", "gpu"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify the node appears in topology
        topo_resp = client.get("/api/v1/topology/nodes")
        topo_data = topo_resp.json()
        assert topo_data["success"] is True
        node_ids = [n["node_id"] for n in topo_data["data"]["nodes"]]
        assert "edge-1" in node_ids

    def test_node_deregister_removes_from_topology(self, client, topology):
        """Deregistering a node via /nodes/{id} also removes from topology."""
        # Register first
        client.post("/api/v1/nodes/register", json={
            "node_id": "edge-2",
            "capabilities": ["python"],
        })

        # Verify in topology
        topo_resp = client.get("/api/v1/topology/nodes")
        node_ids = [n["node_id"] for n in topo_resp.json()["data"]["nodes"]]
        assert "edge-2" in node_ids

        # Deregister
        del_resp = client.delete("/api/v1/nodes/edge-2")
        assert del_resp.status_code == 200

        # Verify removed from topology
        topo_resp = client.get("/api/v1/topology/nodes")
        node_ids = [n["node_id"] for n in topo_resp.json()["data"]["nodes"]]
        assert "edge-2" not in node_ids

    def test_multiple_registrations_in_topology(self, client, topology):
        """Multiple nodes registered appear in topology."""
        for i in range(3):
            resp = client.post("/api/v1/nodes/register", json={
                "node_id": f"node-{i}",
                "capabilities": ["cpu"],
            })
            assert resp.status_code == 200

        topo_resp = client.get("/api/v1/topology")
        topo_data = topo_resp.json()
        assert len(topo_data["data"]["nodes"]) == 3


# ── Health Check ──────────────────────────────────────

class TestHealthCheck:
    def test_topology_in_health(self, client):
        """Topology engine appears in /health endpoint."""
        resp = client.get("/health")
        data = resp.json()
        assert "topology" in data["engines"]
        assert data["engines"]["topology"] == "active"
