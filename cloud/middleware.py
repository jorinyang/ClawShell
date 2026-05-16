"""FastAPI middleware — auth, CORS, rate limiting, JWT verification, RBAC."""

from __future__ import annotations
import time
import hashlib
import hmac
import functools
from typing import Callable, Dict, Optional, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import Depends, HTTPException

from cloud.config import config
from shared.protocol import format_api_response

# ── Paths that skip token-based auth ─────────────────
AUTH_SKIP_PATHS = {
    "/health", "/docs", "/openapi.json", "/favicon.ico",
}
AUTH_SKIP_PREFIXES = ("/docs", "/redoc", "/openapi")

# Auth endpoints that use JWT (not the legacy API token)
JWT_AUTH_PREFIXES = ("/api/v2/auth", "/api/v2/admin", "/api/v1/auth", "/api/v1/admin")


class AuthMiddleware(BaseHTTPMiddleware):
    """Token-based authentication middleware.

    Skips auth for: health, docs, auth endpoints (they handle their own JWT).
    All other requests require Bearer token matching CLAWSHELL_API_TOKEN.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip for health/docs/favicon
        if path in AUTH_SKIP_PATHS or any(path.startswith(p) for p in AUTH_SKIP_PREFIXES):
            return await call_next(request)

        # Skip for v2 auth/admin endpoints (they use JWT internally)
        if any(path.startswith(p) for p in JWT_AUTH_PREFIXES):
            return await call_next(request)

        # If auth is disabled, pass through
        if not config.auth_enabled:
            return await call_next(request)

        # Check Bearer token (legacy API token for v1 endpoints)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                format_api_response(False, error="Missing authorization token"),
                status_code=401,
            )

        token = auth_header[7:]
        if not hmac.compare_digest(token, config.api_token or ""):
            return JSONResponse(
                format_api_response(False, error="Invalid authorization token"),
                status_code=403,
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter (per-IP, sliding window)."""

    MAX_REQUESTS = 100
    WINDOW_SECONDS = 60
    _buckets: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        if client_ip not in self._buckets:
            self._buckets[client_ip] = []
        self._buckets[client_ip] = [
            t for t in self._buckets[client_ip] if now - t < self.WINDOW_SECONDS
        ]

        if len(self._buckets[client_ip]) >= self.MAX_REQUESTS:
            return JSONResponse(
                format_api_response(False, error="Rate limit exceeded"),
                status_code=429,
            )

        self._buckets[client_ip].append(now)
        return await call_next(request)


class CORSMiddlewareWrapper:
    """Simple CORS header injector for Edge clients."""

    @staticmethod
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response


# ── FastAPI Dependencies for JWT Auth ────────────────

async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and verify JWT from Authorization header or cookie.

    Returns payload dict with keys: sub, account_id, role, iat, exp.
    """
    from cloud.auth.session_service import SessionService

    token = None

    # Try Authorization header first
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]

    # Fall back to cookie
    if not token:
        token = request.cookies.get("clawshell_token")

    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    payload = SessionService.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


async def require_admin_user(request: Request) -> dict:
    """FastAPI dependency: require admin or core_admin role."""
    payload = await get_current_user(request)
    if payload.get("role") not in ("core_admin", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


async def require_core_admin_user(request: Request) -> dict:
    """FastAPI dependency: require core_admin role."""
    payload = await get_current_user(request)
    if payload.get("role") != "core_admin":
        raise HTTPException(status_code=403, detail="Core admin access required")
    return payload


async def optional_auth(request: Request) -> Optional[dict]:
    """FastAPI dependency: extract JWT if present, return None if not.

    Useful for endpoints that work with or without authentication.
    """
    from cloud.auth.session_service import SessionService

    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get("clawshell_token")
    if not token:
        return None
    return SessionService.verify_token(token)


# ── RBAC Decorator (for function-based views) ────────

def rbac(roles: List[str]):
    """Decorator to enforce RBAC on FastAPI endpoint handlers.

    Usage:
        @router.get("/admin-only")
        @rbac(["core_admin", "admin"])
        async def admin_endpoint(current_user: dict = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Find current_user in kwargs
            current_user = kwargs.get("current_user")
            if current_user is None:
                raise HTTPException(status_code=500, detail="RBAC: current_user not injected")
            if current_user.get("role") not in roles:
                raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
