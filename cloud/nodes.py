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


def _get_registry(request: Request = None):
    """Get CapabilityRegistry from app state (with fallback)."""
    if request and hasattr(request.app.state, "capability_registry"):
        reg = request.app.state.capability_registry
        if reg:
            return reg
    from cloud.main import _capability_registry
    if not _capability_registry:
        raise HTTPException(status_code=503, detail="CapabilityRegistry not initialized")
    return _capability_registry


def _get_swarm(request: Request = None):
    """Get SwarmCoordinator from app state (with fallback)."""
    if request and hasattr(request.app.state, "swarm"):
        sw = request.app.state.swarm
        if sw:
            return sw
    from cloud.main import _swarm
    return _swarm  # May be None, caller handles


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

    registry = _get_registry(request)
    # Also register with swarm for edges_online count
    swarm = _get_swarm(request)
    try:
        nid = registry.register(body)
        if swarm:
            swarm.register_node(body)
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

    registry = _get_registry(request)
    metrics = body.get("metrics") if body else None
    ok = registry.heartbeat(node_id, metrics)
    if not ok:
        return format_api_response(False, error=f"Node '{node_id}' not found")
    return format_api_response(True, data={"node_id": node_id, "status": "ack"})


@router.get("/nodes/")
async def list_nodes(
    request: Request,
    status: Optional[str] = Query(None),
):
    """List registered nodes."""
    registry = _get_registry(request)
    nodes = registry.list_nodes(status=status)
    return format_api_response(True, data={"nodes": nodes, "count": len(nodes)})


@router.get("/nodes/online")
async def online_count(request: Request):
    """Count online nodes."""
    registry = _get_registry(request)
    return format_api_response(True, data={"online": registry.online_count()})


@router.get("/nodes/{node_id}")
async def get_node(node_id: str, request: Request):
    """Get node details."""
    registry = _get_registry(request)
    node = registry.get_node(node_id)
    if not node:
        return format_api_response(False, error=f"Node '{node_id}' not found")
    return format_api_response(True, data=node)


@router.delete("/nodes/{node_id}")
async def deregister_node(node_id: str, request: Request):
    """Deregister a node."""
    registry = _get_registry(request)
    ok = registry.deregister(node_id)
    if not ok:
        return format_api_response(False, error=f"Node '{node_id}' not found")
    return format_api_response(True, data={"node_id": node_id, "status": "deregistered"})


# ── Health Reports ────────────────────────────────

@router.post("/health/report")
async def health_report(request: Request):
    """Edge health report."""
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")

    node_id = body.get("node_id", "")
    registry = _get_registry(request)

    metrics = body.get("metrics", {})
    ok = registry.heartbeat(node_id, metrics)

    if not ok:
        # Auto-register if not yet registered
        registry.register({
            "node_id": node_id,
            "metrics": metrics,
        })

    return format_api_response(True, data={"node_id": node_id, "status": "reported"})
