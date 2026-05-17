"""Topology Manager REST API router.

Endpoints:
- GET    /api/v1/topology              — Full topology state (nodes, edges, partitions)
- GET    /api/v1/topology/nodes        — List all nodes with roles and trust scores
- POST   /api/v1/topology/nodes        — Add a node to topology
- DELETE /api/v1/topology/nodes/{node_id} — Remove node
- GET    /api/v1/topology/route        — Query route between two nodes
- POST   /api/v1/topology/rebalance    — Trigger manual rebalance
- GET    /api/v1/topology/leader       — Get current leader
"""

from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

router = APIRouter(tags=["topology"])


def _get_topology():
    """Get TopologyManager from global engine reference."""
    from cloud.main import _topology
    if not _topology:
        raise HTTPException(status_code=503, detail="TopologyManager not initialized")
    return _topology


# ── Topology State ────────────────────────────────────

@router.get("/topology")
async def get_topology():
    """Return the full current topology state (nodes, edges, partitions)."""
    topology = _get_topology()
    state = topology.get_topology_state()
    return format_api_response(True, data={
        "topology_type": state.topology_type,
        "nodes": state.nodes,
        "edges": state.edges,
        "partitions": state.partitions,
        "queen_id": state.queen_id,
        "timestamp": state.timestamp,
    })


# ── Nodes ─────────────────────────────────────────────

@router.get("/topology/nodes")
async def list_topology_nodes():
    """List all nodes with roles and trust scores."""
    topology = _get_topology()
    state = topology.get_topology_state()
    nodes_list = [
        {**node_data, "node_id": node_id}
        for node_id, node_data in state.nodes.items()
    ]
    return format_api_response(True, data={"nodes": nodes_list, "count": len(nodes_list)})


@router.post("/topology/nodes")
async def add_topology_node(request: Request):
    """Add a node to the topology."""
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")

    node_id = body.get("node_id", "")
    if not node_id:
        return format_api_response(False, error="node_id is required")

    topology = _get_topology()
    try:
        capabilities = body.get("capabilities")
        trust_score = body.get("trust_score", 0.5)
        partition_id = body.get("partition_id")
        role_str = body.get("role")

        # Parse optional role
        role = None
        if role_str:
            from cloud.engines.topology_manager import NodeRole
            try:
                role = NodeRole(role_str)
            except ValueError:
                return format_api_response(
                    False,
                    error=f"Invalid role '{role_str}'. Valid: {[r.value for r in NodeRole]}"
                )

        node = topology.add_node(
            node_id=node_id,
            capabilities=capabilities,
            trust_score=trust_score,
            partition_id=partition_id,
            role=role,
        )
        return format_api_response(True, data=node.to_dict())
    except ValueError as e:
        return format_api_response(False, error=str(e))


@router.delete("/topology/nodes/{node_id}")
async def remove_topology_node(node_id: str):
    """Remove a node from the topology."""
    topology = _get_topology()
    try:
        result = topology.remove_node(node_id)
        return format_api_response(True, data=result.to_dict())
    except ValueError as e:
        return format_api_response(False, error=str(e))


# ── Routing ───────────────────────────────────────────

@router.get("/topology/route")
async def get_route(
    from_node: str = Query(..., description="Source node ID"),
    to_node: str = Query(..., description="Destination node ID"),
):
    """Find shortest path between two nodes."""
    topology = _get_topology()
    route = topology.get_route(from_node, to_node)
    if route is None:
        return format_api_response(False, error=f"No route found from '{from_node}' to '{to_node}'")
    return format_api_response(True, data={"route": route, "hops": len(route) - 1})


# ── Rebalance ─────────────────────────────────────────

@router.post("/topology/rebalance")
async def trigger_rebalance():
    """Trigger a manual topology rebalance."""
    topology = _get_topology()
    result = topology.rebalance()
    return format_api_response(True, data=result.to_dict())


# ── Leader ────────────────────────────────────────────

@router.get("/topology/leader")
async def get_leader():
    """Get the current leader (queen) of the topology."""
    topology = _get_topology()
    state = topology.get_topology_state()
    leader_id = state.queen_id

    leader_info = None
    if leader_id and leader_id in state.nodes:
        leader_info = {"node_id": leader_id, **state.nodes[leader_id]}

    return format_api_response(True, data={
        "leader_id": leader_id,
        "leader": leader_info,
    })
