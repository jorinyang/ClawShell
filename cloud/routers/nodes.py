"""Node registry + health REST API router.

Endpoints:
- POST   /api/v1/nodes/register — Register/update edge node
- POST   /api/v1/nodes/{node_id}/heartbeat — Edge heartbeat
- GET    /api/v1/nodes/ — List all nodes
- GET    /api/v1/nodes/{node_id} — Get node details
- DELETE /api/v1/nodes/{node_id} — Deregister node
- POST   /api/v1/health/report — Health report from edge
- GET    /api/v1/nodes/online — Count online nodes
"""

from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

router = APIRouter(tags=["nodes"])


def _get_registry():
    """Get CapabilityRegistry from app state."""
    from cloud.main import _capability_registry
    if not _capability_registry:
        raise HTTPException(status_code=503, detail="CapabilityRegistry not initialized")
    return _capability_registry


def _get_topology():
    """Get TopologyManager from global engine reference (optional)."""
    from cloud.main import _topology
    return _topology  # May be None if not initialized yet


# ── Node Registration ─────────────────────────────

@router.post("/nodes/register")
async def register_node(request: Request):
    """Register or update an edge node."""
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")

    node_id = body.get("node_id", "")
    if not node_id:
        return format_api_response(False, error="node_id is required")

    registry = _get_registry()
    try:
        nid = registry.register(body)
        # Auto-register in TopologyManager
        topology = _get_topology()
        if topology:
            try:
                topology.add_node(
                    node_id=nid,
                    capabilities=body.get("capabilities"),
                    trust_score=body.get("trust_score", 0.5),
                )
            except ValueError:
                pass  # Already registered in topology
        return format_api_response(True, data={"node_id": nid, "status": "registered"})
    except ValueError as e:
        return format_api_response(False, error=str(e))


@router.post("/nodes/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, request: Request):
    """Edge heartbeat."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    registry = _get_registry()
    metrics = body.get("metrics") if body else None
    ok = registry.heartbeat(node_id, metrics)
    if not ok:
        return format_api_response(False, error=f"Node '{node_id}' not found")
    return format_api_response(True, data={"node_id": node_id, "status": "ack"})


@router.get("/nodes/")
async def list_nodes(
    status: Optional[str] = Query(None),
):
    """List registered nodes."""
    registry = _get_registry()
    nodes = registry.list_nodes(status=status)
    return format_api_response(True, data={"nodes": nodes, "count": len(nodes)})


@router.get("/nodes/online")
async def online_count():
    """Count online nodes."""
    registry = _get_registry()
    return format_api_response(True, data={"online": registry.online_count()})


@router.get("/nodes/{node_id}")
async def get_node(node_id: str):
    """Get node details."""
    registry = _get_registry()
    node = registry.get_node(node_id)
    if not node:
        return format_api_response(False, error=f"Node '{node_id}' not found")
    return format_api_response(True, data=node)


@router.delete("/nodes/{node_id}")
async def deregister_node(node_id: str):
    """Deregister a node."""
    registry = _get_registry()
    ok = registry.deregister(node_id)
    # Also remove from topology
    if ok:
        topology = _get_topology()
        if topology:
            try:
                topology.remove_node(node_id)
            except ValueError:
                pass  # Not in topology
    if not ok:
        return format_api_response(False, error=f"Node '{node_id}' not found")
    return format_api_response(True, data={"node_id": node_id, "status": "deregistered"})


# ── Health Reports ────────────────────────────────

@router.post("/health/report")
async def health_report(request: Request):
    """Edge health report.

    Accepts frameworks and ide_tools in the payload so the cloud can
    track which frameworks and IDE tools each edge node has.
    """
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")

    node_id = body.get("node_id", "")
    registry = _get_registry()

    metrics = body.get("metrics", {})
    frameworks = body.get("frameworks", None)
    ide_tools = body.get("ide_tools", None)
    ok = registry.heartbeat(node_id, metrics, frameworks=frameworks, ide_tools=ide_tools)

    if not ok:
        # Auto-register if not yet registered
        registry.register({
            "node_id": node_id,
            "metrics": metrics,
            "frameworks": frameworks or [],
            "ide_tools": ide_tools or [],
        })

    return format_api_response(True, data={"node_id": node_id, "status": "reported"})
