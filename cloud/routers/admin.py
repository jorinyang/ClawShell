"""Admin router: dashboard, user management, shared credentials, nodes, audit logs, endpoints."""

from __future__ import annotations
import time
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

from cloud.auth.models import (
    UserCreate, UserUpdate, UserResponse, UserListResponse,
    SharedCredentialCreate, SharedCredentialUpdate, SharedCredentialResponse,
    AuditLogListResponse, NodeUpdate,
    DashboardResponse, SystemInfoResponse, PasswordChange,
)
from cloud.auth.user_service import UserService
from cloud.auth.credential_service import CredentialService
from cloud.auth.shared_cred_service import SharedCredentialService
from cloud.auth.session_service import SessionService
from cloud.auth.audit_service import AuditService
from cloud.auth.database import db_ctx, DB_PATH

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Auth helper ──────────────────────────────────────

def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


def _require_auth(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    payload = SessionService.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def _require_admin(request: Request) -> dict:
    payload = _require_auth(request)
    if payload.get("role") not in ("core_admin", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


def _require_core_admin(request: Request) -> dict:
    payload = _require_auth(request)
    if payload.get("role") != "core_admin":
        raise HTTPException(status_code=403, detail="Core admin access required")
    return payload


def _get_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ── Dashboard ────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(request: Request):
    payload = _require_admin(request)
    user_stats = UserService.count_users()
    return DashboardResponse(
        total_users=user_stats["total"],
        active_users=user_stats["active"],
        total_credentials=CredentialService.count_credentials(),
        total_shared_credentials=SharedCredentialService.count(),
        total_nodes=_count_nodes(),
        online_nodes=_count_online_nodes(),
        active_sessions=SessionService.active_session_count(),
        recent_audit_count=AuditService.recent_count(24),
    )


@router.get("/system", response_model=SystemInfoResponse)
async def system_info(request: Request):
    payload = _require_admin(request)
    user_stats = UserService.count_users()
    return SystemInfoResponse(
        version="2.0.0",
        database_path=DB_PATH,
        total_users=user_stats["total"],
        total_credentials=CredentialService.count_credentials(),
        total_shared_credentials=SharedCredentialService.count(),
        total_nodes=_count_nodes(),
        total_sessions=SessionService.active_session_count(),
        total_audit_logs=AuditService.total_count(),
    )


# ── User Management ──────────────────────────────────

@router.get("/users", response_model=UserListResponse)
async def list_users(request: Request):
    payload = _require_admin(request)
    users = UserService.list_users()
    return UserListResponse(users=users, total=len(users))


@router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, request: Request):
    payload = _require_core_admin(request)
    try:
        user = UserService.create_user(data, actor_role=payload["role"])
        AuditService.log(payload["sub"], "create_user", target=user.user_id, ip=_get_ip(request))
        return user
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate, request: Request):
    payload = _require_admin(request)
    try:
        user = UserService.update_user(user_id, data, payload["role"], payload["sub"])
        AuditService.log(payload["sub"], "update_user", target=user_id, ip=_get_ip(request))
        return user
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request):
    payload = _require_core_admin(request)
    try:
        UserService.delete_user(user_id, payload["role"], payload["sub"])
        AuditService.log(payload["sub"], "delete_user", target=user_id, ip=_get_ip(request))
        return {"status": "ok"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class AdminPasswordChange(BaseModel):
    new_password: str

@router.put("/users/{user_id}/password")
async def admin_change_password(user_id: str, data: AdminPasswordChange, request: Request):
    payload = _require_admin(request)
    try:
        # Admin can only reset non-core_admin passwords; core_admin can reset anyone
        if payload["role"] == "admin":
            target = UserService.get_by_id(user_id)
            if not target:
                raise HTTPException(status_code=404, detail="User not found")
            if target.role == "core_admin":
                raise HTTPException(status_code=403, detail="Admin cannot reset core_admin password")
        UserService.change_password(user_id, data.new_password)
        AuditService.log(payload["sub"], "admin_change_password", target=user_id, ip=_get_ip(request))
        return {"status": "ok", "message": "Password changed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Shared Credentials ───────────────────────────────

@router.get("/shared-credentials", response_model=list[SharedCredentialResponse])
async def list_shared_credentials(request: Request):
    _require_admin(request)
    return SharedCredentialService.list_all()


@router.post("/shared-credentials", response_model=SharedCredentialResponse)
async def create_shared_credential(data: SharedCredentialCreate, request: Request):
    payload = _require_admin(request)
    sc = SharedCredentialService.create(data, created_by=payload["sub"])
    AuditService.log(payload["sub"], "create_shared_cred", target=sc.sc_id, ip=_get_ip(request))
    return sc


@router.patch("/shared-credentials/{sc_id}", response_model=SharedCredentialResponse)
async def update_shared_credential(sc_id: str, data: SharedCredentialUpdate, request: Request):
    payload = _require_admin(request)
    try:
        sc = SharedCredentialService.update(sc_id, data)
        AuditService.log(payload["sub"], "update_shared_cred", target=sc_id, ip=_get_ip(request))
        return sc
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/shared-credentials/{sc_id}")
async def delete_shared_credential(sc_id: str, request: Request):
    payload = _require_admin(request)
    SharedCredentialService.delete(sc_id)
    AuditService.log(payload["sub"], "delete_shared_cred", target=sc_id, ip=_get_ip(request))
    return {"status": "ok"}


# ── Edge Nodes ───────────────────────────────────────

@router.patch("/nodes/{node_id}")
async def update_node(node_id: str, data: NodeUpdate, request: Request):
    payload = _require_admin(request)
    with db_ctx() as conn:
        row = conn.execute("SELECT * FROM edge_nodes WHERE node_id = ?", (node_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Node not found")
        updates = []
        params = []
        for field in ("node_name", "node_type", "status", "ip_address", "metadata", "frameworks", "ide_tools"):
            val = getattr(data, field, None)
            if val is not None:
                updates.append(f"{field} = ?")
                params.append(val)
        if updates:
            params.append(node_id)
            conn.execute(f"UPDATE edge_nodes SET {', '.join(updates)} WHERE node_id = ?", params)
        AuditService.log(payload["sub"], "update_node", target=node_id, ip=_get_ip(request))
    return {"status": "ok"}


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str, request: Request):
    payload = _require_admin(request)
    with db_ctx() as conn:
        conn.execute("DELETE FROM edge_nodes WHERE node_id = ?", (node_id,))
    AuditService.log(payload["sub"], "delete_node", target=node_id, ip=_get_ip(request))
    return {"status": "ok"}


# ── Audit Logs ───────────────────────────────────────

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = Query(None),
):
    _require_admin(request)
    return AuditService.get_logs(limit=limit, offset=offset, user_id=user_id)


# ── Endpoints (config per-endpoint) ──────────────────

class EndpointUpdate(BaseModel):
    enabled: bool
    config: Optional[dict] = None

_endpoints_config: dict = {
    "events": {"enabled": True, "config": {}},
    "nodes": {"enabled": True, "config": {}},
    "tasks": {"enabled": True, "config": {}},
    "skills": {"enabled": True, "config": {}},
    "insights": {"enabled": True, "config": {}},
    "broadcasts": {"enabled": True, "config": {}},
    "reviews": {"enabled": True, "config": {}},
    "evolution": {"enabled": True, "config": {}},
    "brain": {"enabled": True, "config": {}},
    "auth": {"enabled": True, "config": {}},
    "admin": {"enabled": True, "config": {}},
}

@router.get("/endpoints")
async def get_endpoints(request: Request):
    _require_admin(request)
    return {"endpoints": _endpoints_config}


@router.put("/endpoints/{endpoint_id}")
async def update_endpoint(endpoint_id: str, data: EndpointUpdate, request: Request):
    payload = _require_admin(request)
    global _endpoints_config
    _endpoints_config[endpoint_id] = {
        "enabled": data.enabled,
        "config": data.config or {},
    }
    AuditService.log(payload["sub"], "update_endpoint", target=endpoint_id, ip=_get_ip(request))
    return {"status": "ok", "endpoint_id": endpoint_id, **_endpoints_config[endpoint_id]}


# ── Helpers ──────────────────────────────────────────

def _count_nodes() -> int:
    with db_ctx() as conn:
        return conn.execute("SELECT COUNT(*) FROM edge_nodes").fetchone()[0]


def _count_online_nodes() -> int:
    with db_ctx() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM edge_nodes WHERE status = 'online'"
        ).fetchone()[0]
