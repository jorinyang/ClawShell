"""Cloud Hub FastAPI server — 云枢主脑.

Unified REST + WebSocket server providing:
- /health — Health check
- /api/v1/events/* — EventBus
- /api/v1/nodes/* — Node registry
- /api/v1/health/* — Edge health reports
- /ws/events — Real-time WebSocket push
"""

from __future__ import annotations
import sys
import os
import time
import threading
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from cloud.config import config
from cloud.middleware import AuthMiddleware, RateLimitMiddleware, CORSMiddlewareWrapper
from shared.protocol import format_api_response

# ── App Factory ─────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ClawShell Cloud Hub",
        description="一云多端云边协同分布式神经系统 — Cloud Hub API",
        version="2.0.0-dev",
        docs_url="/docs" if config.debug else None,
        redoc_url=None,
    )

    # Middleware
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # CORS (via event hook)
    @app.middleware("http")
    async def cors_middleware(request, call_next):
        if request.method == "OPTIONS":
            return JSONResponse({}, status_code=200)
        response = await call_next(request)
        return CORSMiddlewareWrapper.add_cors_headers(response)

    # ── Routes ──────────────────────────────────

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "2.0.0-dev",
            "timestamp": time.time(),
            "engines": {
                "eventbus": "active" if _eventbus else "inactive",
                "scheduler": "active" if _scheduler else "inactive",
                "capability_registry": "active" if _capability_registry else "inactive",
            },
            "edges_online": _capability_registry.online_count() if _capability_registry else 0,
        }

    # Register routers from Phase 1
    from cloud.routers.events import router as events_router
    from cloud.routers.nodes import router as nodes_router
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(nodes_router, prefix="/api/v1")

    return app


# ── Global Engine References (set during startup) ──

_eventbus = None
_scheduler = None
_capability_registry = None


def set_engines(eventbus, scheduler=None, capability_registry=None):
    """Inject engine instances into the app context."""
    global _eventbus, _scheduler, _capability_registry
    _eventbus = eventbus
    _scheduler = scheduler
    _capability_registry = capability_registry


# ── Startup ────────────────────────────────────────

def init_engines():
    """Initialize cloud engines on startup."""
    global _eventbus, _scheduler, _capability_registry

    from cloud.engines.eventbus import CloudEventBus
    from cloud.engines.capability_registry import CapabilityRegistry
    from cloud.engines.scheduler import CloudScheduler

    _eventbus = CloudEventBus(data_dir=config.data_dir)
    _eventbus.start_cleanup_daemon()

    _capability_registry = CapabilityRegistry(data_dir=config.data_dir)
    _capability_registry.start_monitor()

    _scheduler = CloudScheduler(data_dir=config.data_dir)
    _scheduler.start()

    logging.info("All cloud engines initialized")


def main():
    """Entry point for `clawshell-cloud` CLI command."""
    import uvicorn

    init_engines()

    app = create_app()

    # Register WebSocket endpoint
    from cloud.websocket import setup_websocket
    setup_websocket(app, _eventbus)

    logging.info(f"Cloud Hub starting on {config.host}:{config.port}")
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
