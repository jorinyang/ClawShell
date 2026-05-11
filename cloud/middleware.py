"""FastAPI middleware — auth, CORS, rate limiting."""

from __future__ import annotations
import time
import hashlib
import hmac
from typing import Callable, Dict, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from cloud.config import config
from shared.protocol import format_api_response


class AuthMiddleware(BaseHTTPMiddleware):
    """Token-based authentication middleware.

    Skips auth for: GET /health, GET /docs, GET /openapi.json.
    All other requests require Bearer token matching CLAWSHELL_API_TOKEN.
    """

    SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health/docs
        if request.url.path in self.SKIP_PATHS or request.url.path.startswith("/docs"):
            return await call_next(request)

        # If auth is disabled, pass through
        if not config.auth_enabled:
            return await call_next(request)

        # Check Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                format_api_response(False, error="Missing authorization token"),
                status_code=401
            )

        token = auth_header[7:]
        if not hmac.compare_digest(token, config.api_token or ""):
            return JSONResponse(
                format_api_response(False, error="Invalid authorization token"),
                status_code=403
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

        # Initialize or clean bucket
        if client_ip not in self._buckets:
            self._buckets[client_ip] = []
        self._buckets[client_ip] = [
            t for t in self._buckets[client_ip]
            if now - t < self.WINDOW_SECONDS
        ]

        # Check rate
        if len(self._buckets[client_ip]) >= self.MAX_REQUESTS:
            return JSONResponse(
                format_api_response(False, error="Rate limit exceeded"),
                status_code=429
            )

        self._buckets[client_ip].append(now)
        return await call_next(request)


class CORSMiddlewareWrapper:
    """Simple CORS header injector for Edge clients."""
    
    @staticmethod
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
