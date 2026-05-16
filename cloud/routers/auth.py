"""Auth router: public endpoints for login/register/password."""

from __future__ import annotations
from fastapi import APIRouter, Request, Depends, HTTPException
from starlette.responses import JSONResponse

from cloud.auth.models import (
    LoginRequest, LoginResponse, TokenResponse, RegisterRequest,
    PasswordChange, UserResponse,
)
from cloud.auth.session_service import SessionService
from cloud.auth.user_service import UserService
from cloud.auth.audit_service import AuditService
from cloud.auth.models import UserCreate

router = APIRouter(prefix="/auth", tags=["Auth"])


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, request: Request):
    """Authenticate and get JWT token."""
    try:
        ip = _get_client_ip(request)
        ua = request.headers.get("User-Agent", "")
        result = SessionService.login(data, ip=ip, user_agent=ua)
        AuditService.log(result.user.user_id, "login", ip=ip)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/register", response_model=UserResponse)
async def register(data: RegisterRequest, request: Request):
    """Self-register a new user account (role=user)."""
    import secrets as _secrets
    from cloud.auth.database import db_ctx
    from cloud.auth.crypto import hash_password

    try:
        with db_ctx() as conn:
            existing = conn.execute(
                "SELECT user_id FROM users WHERE account_id = ?", (data.account_id,)
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="Account already exists")

            user_id = f"usr_{_secrets.token_hex(3)}"
            pwd_hash = hash_password(data.password)
            conn.execute(
                """INSERT INTO users (user_id, account_id, display_name, password_hash, role, must_change_pwd)
                   VALUES (?, ?, ?, ?, 'user', 0)""",
                (user_id, data.account_id, data.display_name, pwd_hash),
            )
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

        AuditService.log(user_id, "register", target=data.account_id, ip=_get_client_ip(request))
        return UserResponse(
            user_id=row["user_id"],
            account_id=row["account_id"],
            display_name=row["display_name"],
            role=row["role"],
            must_change_pwd=row["must_change_pwd"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/logout")
async def logout(request: Request):
    """Revoke current session."""
    token = _extract_token(request)
    if token:
        SessionService.logout(token)
        payload = SessionService.verify_token(token) or {}
        AuditService.log(payload.get("sub"), "logout", ip=_get_client_ip(request))
    return {"status": "ok"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request):
    """Refresh a valid JWT token."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    result = SessionService.refresh(token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return result


@router.get("/me", response_model=UserResponse)
async def me(request: Request):
    """Get current user info from JWT."""
    payload = _require_auth(request)
    user = UserService.get_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/password")
async def change_password(data: PasswordChange, request: Request):
    """Change current user's password."""
    payload = _require_auth(request)
    try:
        UserService.change_own_password(payload["sub"], data.old_password, data.new_password)
        AuditService.log(payload["sub"], "change_password", ip=_get_client_ip(request))
        return {"status": "ok", "message": "Password changed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Helpers ──────────────────────────────────────────

def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


def _require_auth(request: Request) -> dict:
    """Verify JWT and return payload. Raises 401 if invalid."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    payload = SessionService.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload
