"""Cloud Hub FastAPI server — 云枢主脑.

Unified REST + WebSocket server providing all cloud engine endpoints.
"""

from __future__ import annotations
import sys, os, time, threading, logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from cloud.config import config
from cloud.middleware import AuthMiddleware, RateLimitMiddleware, CORSMiddlewareWrapper
from shared.protocol import format_api_response

logging.basicConfig(level=logging.INFO)

# ── Global Engine References ──────────────────────
_eventbus = None
_scheduler = None
_capability_registry = None
_task_board = None
_skill_market = None
_swarm = None
_evolution = None
_review = None
_broadcast = None
_n8n_bridge = None


def set_engines(**kwargs):
    """Inject engine instances."""
    for name, engine in kwargs.items():
        globals()[f"_{name}"] = engine


# ── App Factory ────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="ClawShell Cloud Hub",
        description="一云多端云边协同分布式神经系统 — Cloud Hub API",
        version="1.9.1",
        docs_url="/docs" if config.debug else None,
        redoc_url=None,
    )

    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)

    @app.middleware("http")
    async def cors_middleware(request, call_next):
        if request.method == "OPTIONS":
            return JSONResponse({}, status_code=200)
        response = await call_next(request)
        return CORSMiddlewareWrapper.add_cors_headers(response)

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "1.9.1",
            "timestamp": time.time(),
            "engines": {
                "eventbus": "active" if _eventbus else "inactive",
                "scheduler": "active" if _scheduler else "inactive",
                "capability_registry": "active" if _capability_registry else "inactive",
                "task_board": "active" if _task_board else "inactive",
                "skill_market": "active" if _skill_market else "inactive",
                "swarm": "active" if _swarm else "inactive",
                "evolution": "active" if _evolution else "inactive",
                "review": "active" if _review else "inactive",
                "broadcast": "active" if _broadcast else "inactive",
                "n8n": "active" if _n8n_bridge else "inactive",
            },
            "edges_online": _swarm.online_count() if _swarm else 0,
        }

    # Register routers
    from cloud.routers.events import router as events_router
    from cloud.routers.nodes import router as nodes_router
    from cloud.routers.tasks import router as tasks_router
    from cloud.routers.skills import router as skills_router
    from cloud.routers.insights_broadcasts_reviews import (
        insights_router, broadcasts_router, reviews_router, evolution_router
    )

    app.include_router(events_router, prefix="/api/v1")
    app.include_router(nodes_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(skills_router, prefix="/api/v1")
    app.include_router(insights_router, prefix="/api/v1")
    app.include_router(broadcasts_router, prefix="/api/v1")
    app.include_router(reviews_router, prefix="/api/v1")
    app.include_router(evolution_router, prefix="/api/v1")

    return app


# ── Startup ────────────────────────────────────────

def init_engines():
    """Initialize all cloud engines."""
    from cloud.engines.eventbus import CloudEventBus
    from cloud.engines.capability_registry import CapabilityRegistry
    from cloud.engines.scheduler import CloudScheduler
    from cloud.engines.task_board import GlobalTaskBoard
    from cloud.engines.skill_market import SkillMarket
    from cloud.engines.swarm_coordinator import SwarmCoordinator
    from cloud.engines.evolution import EvolutionEngine
    from cloud.engines.review import UnifiedReviewEngine
    from cloud.engines.broadcast import BroadcastEngine
    from cloud.engines.n8n_bridge import N8NBridge

    global _eventbus, _scheduler, _capability_registry
    global _task_board, _skill_market, _swarm
    global _evolution, _review, _broadcast, _n8n_bridge

    _eventbus = CloudEventBus(data_dir=config.data_dir)
    _eventbus.start_cleanup_daemon()

    _capability_registry = CapabilityRegistry(data_dir=config.data_dir)
    _capability_registry.start_monitor()

    _scheduler = CloudScheduler(data_dir=config.data_dir)
    _scheduler.start()

    _task_board = GlobalTaskBoard(data_dir=config.data_dir)

    _skill_market = SkillMarket(data_dir=config.data_dir)

    _swarm = SwarmCoordinator(data_dir=config.data_dir)
    _swarm.start_monitor()

    _broadcast = BroadcastEngine(data_dir=config.data_dir, eventbus=_eventbus)

    _evolution = EvolutionEngine(
        data_dir=config.data_dir, eventbus=_eventbus, skill_market=_skill_market
    )
    _evolution.start()

    _review = UnifiedReviewEngine(
        data_dir=config.data_dir, eventbus=_eventbus, skill_market=_skill_market
    )
    _review.start()

    _n8n_bridge = N8NBridge(n8n_base_url=config.n8n_url)

    logging.info("All 9 cloud engines initialized")


def main():
    """Entry point: clawshell-cloud"""
    import uvicorn

    init_engines()
    app = create_app()

    from cloud.websocket import setup_websocket
    setup_websocket(app, _eventbus)

    logging.info(f"Cloud Hub starting on {config.host}:{config.port}")
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
