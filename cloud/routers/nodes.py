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


def _get_registry(request: Request = None):
    """Get CapabilityRegistry — app.state first, then module global fallback."""
    if request:
        reg = getattr(request.app.state, 'capability_registry', None)
        if reg:
            return reg
    import sys
    main_mod = sys.modules.get('cloud.main') or sys.modules.get('__main__')
    reg = getattr(main_mod, '_capability_registry', None) if main_mod else None
    if not reg:
        raise HTTPException(status_code=503, detail="CapabilityRegistry not initialized")
    return reg


def _get_topology(request: Request = None):
    """Get TopologyManager (optional, may not exist) — app.state first."""
    if request:
        topo = getattr(request.app.state, 'topology', None)
        if topo:
            return topo
    import sys
    mod = sys.modules.get('__main__') or sys.modules.get('cloud.main')
    return getattr(mod, '_topology', None) if mod else None


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


def _ensure_edge_nodes_table():
    """Create edge_nodes table with all columns if it doesn't exist."""
    try:
        from cloud.auth.database import db_ctx
        with db_ctx() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edge_nodes (
                    node_id         TEXT PRIMARY KEY,
                    node_name       TEXT NOT NULL,
                    node_type       TEXT DEFAULT 'edge',
                    status          TEXT DEFAULT 'offline',
                    ip_address      TEXT DEFAULT '',
                    metadata        TEXT DEFAULT '{}',
                    frameworks      TEXT DEFAULT '[]',
                    ide_tools       TEXT DEFAULT '[]',
                    user_id         TEXT DEFAULT '',
                    hostname        TEXT DEFAULT '',
                    os              TEXT DEFAULT '',
                    os_version      TEXT DEFAULT '',
                    python_version  TEXT DEFAULT '',
                    cpu_count       INTEGER DEFAULT 0,
                    memory_total_mb REAL DEFAULT 0,
                    last_seen       TEXT DEFAULT (datetime('now')),
                    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
    except Exception:
        pass


def _migrate_edge_nodes_columns():
    """Add new system info columns to edge_nodes if missing."""
    try:
        from cloud.auth.database import db_ctx
        with db_ctx() as conn:
            for col, col_def in [
                ("hostname", "ALTER TABLE edge_nodes ADD COLUMN hostname TEXT DEFAULT ''"),
                ("os", "ALTER TABLE edge_nodes ADD COLUMN os TEXT DEFAULT ''"),
                ("os_version", "ALTER TABLE edge_nodes ADD COLUMN os_version TEXT DEFAULT ''"),
                ("python_version", "ALTER TABLE edge_nodes ADD COLUMN python_version TEXT DEFAULT ''"),
                ("cpu_count", "ALTER TABLE edge_nodes ADD COLUMN cpu_count INTEGER DEFAULT 0"),
                ("memory_total_mb", "ALTER TABLE edge_nodes ADD COLUMN memory_total_mb REAL DEFAULT 0"),
            ]:
                try:
                    conn.execute(f"SELECT {col} FROM edge_nodes LIMIT 1")
                except Exception:
                    conn.execute(col_def)
    except Exception:
        pass


def _sync_node_to_sqlite(node_id: str, node_info: dict, user_id: str = ""):
    """INSERT or UPDATE a node in the SQLite edge_nodes table."""
    try:
        from cloud.auth.database import db_ctx
        _ensure_edge_nodes_table()
        _migrate_edge_nodes_columns()

        node_name = node_info.get("node_name", node_id)
        node_type = node_info.get("node_type", "edge")
        status = node_info.get("status", "online")
        ip_address = node_info.get("ip_address", "")
        metadata = _json.dumps(node_info.get("metadata", {}))
        frameworks = _json.dumps(node_info.get("frameworks", []))
        ide_tools = _json.dumps(node_info.get("ide_tools", []))
        hostname = node_info.get("hostname", "")
        os_name = node_info.get("os", "")
        os_version = node_info.get("os_version", "")
        python_version = node_info.get("python_version", "")
        cpu_count = node_info.get("cpu_count", 0)
        memory_total_mb = node_info.get("memory_total_mb", 0)
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        with db_ctx() as conn:
            conn.execute("""
                INSERT INTO edge_nodes (node_id, node_name, node_type, status, ip_address,
                                        metadata, frameworks, ide_tools, user_id,
                                        hostname, os, os_version, python_version,
                                        cpu_count, memory_total_mb,
                                        last_seen, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    node_name = excluded.node_name,
                    node_type = excluded.node_type,
                    status = excluded.status,
                    ip_address = CASE WHEN excluded.ip_address != '' THEN excluded.ip_address ELSE edge_nodes.ip_address END,
                    metadata = excluded.metadata,
                    frameworks = excluded.frameworks,
                    ide_tools = excluded.ide_tools,
                    user_id = CASE WHEN excluded.user_id != '' THEN excluded.user_id ELSE edge_nodes.user_id END,
                    hostname = CASE WHEN excluded.hostname != '' THEN excluded.hostname ELSE edge_nodes.hostname END,
                    os = CASE WHEN excluded.os != '' THEN excluded.os ELSE edge_nodes.os END,
                    os_version = CASE WHEN excluded.os_version != '' THEN excluded.os_version ELSE edge_nodes.os_version END,
                    python_version = CASE WHEN excluded.python_version != '' THEN excluded.python_version ELSE edge_nodes.python_version END,
                    cpu_count = CASE WHEN excluded.cpu_count != 0 THEN excluded.cpu_count ELSE edge_nodes.cpu_count END,
                    memory_total_mb = CASE WHEN excluded.memory_total_mb != 0 THEN excluded.memory_total_mb ELSE edge_nodes.memory_total_mb END,
                    last_seen = excluded.last_seen
            """, (node_id, node_name, node_type, status, ip_address,
                  metadata, frameworks, ide_tools, user_id,
                  hostname, os_name, os_version, python_version,
                  cpu_count, memory_total_mb, now, now))
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

    registry = _get_registry(request)
    try:
        nid = registry.register(body)
        # Auto-register in TopologyManager
        topology = _get_topology(request)
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

    registry = _get_registry(request)
    metrics = body.get("metrics") if body else None
    ok = registry.heartbeat(node_id, metrics)
    if not ok:
        return format_api_response(False, error=f"Node '{node_id}' not found")

    # Update SQLite
    _update_node_heartbeat_sqlite(node_id, status="online")

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
    # Also remove from topology
    if ok:
        topology = _get_topology(request)
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
    Also accepts system info fields (hostname, ip_address, os, os_version,
    python_version, cpu_count, memory_total_mb) to keep node info current.
    """
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")

    node_id = body.get("node_id", "")
    registry = _get_registry(request)

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

    # Update system info in registry if provided in health report
    system_info_fields = ["hostname", "ip_address", "os", "os_version",
                          "python_version", "cpu_count", "memory_total_mb"]
    has_system_info = any(body.get(f) for f in system_info_fields)
    if has_system_info:
        node = registry.get_node(node_id)
        if node:
            update = {}
            for field in system_info_fields:
                val = body.get(field)
                if val:
                    update[field] = val
            if update:
                with registry._lock:
                    node_obj = registry._nodes.get(node_id)
                    if node_obj:
                        node_obj.update(update)
                        registry._save()

    # Update SQLite with latest heartbeat data
    _update_node_heartbeat_sqlite(
        node_id, status="online",
        frameworks=frameworks, ide_tools=ide_tools,
    )

    # Sync system info to SQLite if provided
    if has_system_info:
        sys_info = {f: body.get(f) for f in system_info_fields if body.get(f)}
        sys_info["status"] = "online"
        _sync_node_to_sqlite(node_id, sys_info)

    return format_api_response(True, data={"node_id": node_id, "status": "reported"})
