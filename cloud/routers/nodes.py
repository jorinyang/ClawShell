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
import json as _json
import time
from typing import Optional
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

router = APIRouter(tags=["nodes"])


def _get_registry():
    """Get CapabilityRegistry from the running main module."""
    import sys
    main_mod = sys.modules.get('cloud.main') or sys.modules.get('__main__')
    reg = getattr(main_mod, '_capability_registry', None) if main_mod else None
    if not reg:
        raise HTTPException(status_code=503, detail="CapabilityRegistry not initialized")
    return reg


def _get_topology():
    """Get TopologyManager (optional, may not exist)."""
    return getattr(__import__('cloud.main', fromlist=['_topology']), '_topology', None)


def _extract_user_id(request: Request) -> str:
    """Try to extract user_id from JWT token. Returns '' if no auth."""
    try:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return ""
        token = auth[7:]
        from cloud.auth.session_service import SessionService
        payload = SessionService.verify_token(token)
        if payload:
            return payload.get("sub", "")
    except Exception:
        pass
    return ""


def _sync_node_to_sqlite(node_id: str, node_info: dict, user_id: str = ""):
    """INSERT or UPDATE a node in the SQLite edge_nodes table."""
    try:
        from cloud.auth.database import db_ctx
        node_name = node_info.get("node_name", node_id)
        node_type = node_info.get("node_type", "edge")
        status = node_info.get("status", "online")
        ip_address = node_info.get("ip_address", "")
        metadata = _json.dumps(node_info.get("metadata", {}))
        frameworks = _json.dumps(node_info.get("frameworks", []))
        ide_tools = _json.dumps(node_info.get("ide_tools", []))
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        with db_ctx() as conn:
            conn.execute("""
                INSERT INTO edge_nodes (node_id, node_name, node_type, status, ip_address,
                                        metadata, frameworks, ide_tools, user_id, last_seen, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    node_name = excluded.node_name,
                    node_type = excluded.node_type,
                    status = excluded.status,
                    ip_address = excluded.ip_address,
                    metadata = excluded.metadata,
                    frameworks = excluded.frameworks,
                    ide_tools = excluded.ide_tools,
                    user_id = CASE WHEN excluded.user_id != '' THEN excluded.user_id ELSE edge_nodes.user_id END,
                    last_seen = excluded.last_seen
            """, (node_id, node_name, node_type, status, ip_address,
                  metadata, frameworks, ide_tools, user_id, now, now))
    except Exception:
        pass  # Don't break registration if SQLite write fails


def _update_node_heartbeat_sqlite(node_id: str, status: str = "online",
                                   metrics: Optional[dict] = None, frameworks=None, ide_tools=None):
    """UPDATE a node's last_seen and status in SQLite on heartbeat."""
    try:
        from cloud.auth.database import db_ctx
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with db_ctx() as conn:
            updates = ["last_seen = ?", "status = ?"]
            params = [now, status]
            if frameworks is not None:
                updates.append("frameworks = ?")
                params.append(_json.dumps(frameworks))
            if ide_tools is not None:
                updates.append("ide_tools = ?")
                params.append(_json.dumps(ide_tools))
            params.append(node_id)
            conn.execute(
                f"UPDATE edge_nodes SET {', '.join(updates)} WHERE node_id = ?",
                params
            )
    except Exception:
        pass


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

    # Try to extract user_id from JWT (backward compatible — no auth required)
    user_id = _extract_user_id(request)

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

        # Sync to SQLite so the admin dashboard can see it
        body_with_status = {**body, "status": "online"}
        _sync_node_to_sqlite(nid, body_with_status, user_id=user_id)

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

    # Update SQLite
    _update_node_heartbeat_sqlite(node_id, status="online")

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
        # Also remove from SQLite
        try:
            from cloud.auth.database import db_ctx
            with db_ctx() as conn:
                conn.execute("DELETE FROM edge_nodes WHERE node_id = ?", (node_id,))
        except Exception:
            pass
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

    # Update SQLite with latest heartbeat data
    _update_node_heartbeat_sqlite(
        node_id, status="online",
        frameworks=frameworks, ide_tools=ide_tools,
    )

    return format_api_response(True, data={"node_id": node_id, "status": "reported"})
