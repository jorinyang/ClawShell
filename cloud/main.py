"""Cloud Hub FastAPI server — 云枢主脑.

Unified REST + WebSocket server providing all cloud engine endpoints.
v2.0: Added auth/account management with SQLite database.
"""

from __future__ import annotations
import sys, os, time, threading, logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from cloud.config import config
from cloud.middleware import AuthMiddleware, RateLimitMiddleware, CORSMiddlewareWrapper
from shared.protocol import format_api_response

logging.basicConfig(level=logging.INFO)

# ── Global Engine References ──────────────────────────
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
_insight = None    # v1.9.0 InsightEngine
_brain = None      # v1.12.0 CloudBrain LLM analyst
_workflow = None   # v2.0 WorkflowEngine
_optimizer = None  # v2.0 GlobalOptimizer
_deep_think = None # v2.0 DeepThinkEngine
_topology = None   # v2.0 TopologyManager
_knowledge_graph = None  # v2.1 KnowledgeGraph
_cron_supervisor = None  # v2.1 CloudCronSupervisor
_dispatch_router = None   # v2.1 DispatchRouter

def set_engines(**kwargs):
    """Inject engine instances."""
    for name, engine in kwargs.items():
        globals()[f"_{name}"] = engine

# ── App Factory ────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="ClawShell Cloud Hub",
        description="一云多端云边协同分布式神经系统 — Cloud Hub API",
        version="2.0.0",
        docs_url="/docs" if config.debug else None,
        redoc_url=None,
    )

    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # v2.0: Expose engines via app.state for router access
    app.state.eventbus = _eventbus
    app.state.scheduler = _scheduler
    app.state.capability_registry = _capability_registry
    app.state.task_board = _task_board
    app.state.skill_market = _skill_market
    app.state.swarm = _swarm
    app.state.evolution = _evolution
    app.state.review = _review
    app.state.broadcast = _broadcast
    app.state.n8n_bridge = _n8n_bridge
    app.state.insight = _insight
    app.state.brain = _brain
    app.state.workflow = _workflow
    app.state.optimizer = _optimizer
    app.state.deep_think = _deep_think
    app.state.topology = _topology
    app.state.knowledge_graph = _knowledge_graph
    app.state.pubsub = getattr(_eventbus, '_pubsub', None)
    app.state.cron_supervisor = _cron_supervisor
    app.state.dispatch_router = _dispatch_router

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
            "version": "2.0.0",
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
                "insight": "active" if _insight else "inactive",
                "brain": "active" if _brain else "inactive",
                "workflow": "active" if _workflow else "inactive",
                "optimizer": "active" if _optimizer else "inactive",
                "deep_think": "active" if _deep_think else "inactive",
                "topology": "active" if _topology else "inactive",
                "knowledge_graph": "active" if _knowledge_graph else "inactive",
                "pubsub": "active" if (hasattr(_eventbus, '_pubsub') and _eventbus._pubsub) else "inactive",
                "cron_supervisor": "active" if _cron_supervisor else "inactive",
                "dispatch_router": "active" if _dispatch_router else "inactive",
            },
            "edges_online": _swarm.online_count() if _swarm else 0,
        }

    # ── v1.x Routers ─────────────────────────────────
    from cloud.routers.events import router as events_router
    from cloud.routers.nodes import router as nodes_router
    from cloud.routers.tasks import router as tasks_router
    from cloud.routers.skills import router as skills_router
    from cloud.routers.insights_broadcasts_reviews import (
        insights_router, broadcasts_router, reviews_router, evolution_router
    )
    from cloud.routers.brain import brain_router

    app.include_router(events_router, prefix="/api/v1")
    app.include_router(nodes_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(skills_router, prefix="/api/v1")
    app.include_router(insights_router, prefix="/api/v1")
    app.include_router(broadcasts_router, prefix="/api/v1")
    app.include_router(reviews_router, prefix="/api/v1")
    app.include_router(evolution_router, prefix="/api/v1")
    app.include_router(brain_router, prefix="/api/v1")

    from cloud.routers.engines import router as engines_router
    from cloud.routers.topology import router as topology_router

    app.include_router(engines_router, prefix="/api/v1")
    app.include_router(topology_router, prefix="/api/v1")

    # ── v2.1 CronSupervisor Router ─────────────────────
    from cloud.routers.cron_supervisor import router as cron_supervisor_router
    app.include_router(cron_supervisor_router, prefix="/api/v1")

    # ── Vault Router (Obsidian knowledge vault) ─────
    from cloud.routers.vault import router as vault_router
    app.include_router(vault_router, prefix="/api/v1")

    # ── v2.0 Auth & Admin Routers ────────────────────
    from cloud.routers.auth import router as auth_router
    from cloud.routers.admin import router as admin_router
    from cloud.routers.credentials import router as credentials_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(credentials_router, prefix="/api/v1")

    return app

# ── Startup ────────────────────────────────────────────

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
    from cloud.engines.insight import InsightEngine  # v1.9.0
    from cloud.brain.analyst import CloudAnalyst  # v1.12.0

    global _eventbus, _scheduler, _capability_registry
    global _task_board, _skill_market, _swarm
    global _evolution, _review, _broadcast, _n8n_bridge
    global _insight  # v1.9.0
    global _brain    # v1.12.0
    global _workflow, _optimizer, _deep_think, _topology
    global _knowledge_graph
    global _cron_supervisor, _dispatch_router

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

    # v1.9.0 — InsightEngine: real-time event analysis
    _insight = InsightEngine(eventbus=_eventbus, data_dir=config.data_dir)
    _insight.start()

    # v1.12.0 — CloudBrain: LLM-powered analysis (event-driven + periodic)
    _brain = CloudAnalyst(eventbus=_eventbus, data_dir=config.data_dir)
    _brain.start()
    # v2.0 — Workflow engine
    from cloud.engines.workflow import WorkflowEngine
    _workflow = WorkflowEngine(store_dir=os.path.join(config.data_dir, "workflows"))

    # v2.0 — Global optimizer
    from cloud.engines.optimizer import GlobalOptimizer
    _optimizer = GlobalOptimizer()

    # v2.0 — Deep think engine
    from cloud.engines.deep_think import DeepThinkEngine
    _deep_think = DeepThinkEngine()

    # v2.0 — Topology manager
    from cloud.engines.topology_manager import TopologyManager
    _topology = TopologyManager()

    # v2.1 — Knowledge graph service
    from cloud.services.knowledge_graph import KnowledgeGraph
    _knowledge_graph = KnowledgeGraph(store_dir=os.path.join(config.data_dir, "knowledge_graph"))

    # Wire knowledge graph to insight engine
    if _insight:
        _insight._knowledge_graph = _knowledge_graph

    # v2.1 — DispatchRouter (needs eventbus + task_board)
    from cloud.engines.dispatch_router import DispatchRouter
    _dispatch_router = DispatchRouter(
        eventbus=_eventbus,
        task_board=_task_board,
        data_dir=config.data_dir,
    )

    # v2.1 — CloudCronSupervisor (needs scheduler + capability_registry + dispatch_router)
    from cloud.engines.cron_supervisor import CloudCronSupervisor
    _cron_supervisor = CloudCronSupervisor(
        data_dir=config.data_dir,
        scheduler=_scheduler,
        eventbus=_eventbus,
        task_board=_task_board,
        capability_registry=_capability_registry,
        dispatch_router=_dispatch_router,
    )
    _cron_supervisor.start()

    logging.info(f"All 19 engines initialized (v2.1) — Brain LLM: {_brain._llm.is_configured}")

def init_auth_database():
    """Initialize the v2.0 auth database (SQLite WAL)."""
    from cloud.auth.database import init_database
    init_database()
    logging.info("Auth database initialized (v2.0)")

def main():
    """Entry point: clawshell-cloud"""
    import uvicorn

    init_auth_database()  # v2.0: init DB first
    init_engines()
    app = create_app()

    from cloud.websocket import setup_websocket
    setup_websocket(app, _eventbus)

    logging.info(f"Cloud Hub starting on {config.host}:{config.port}")
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")

if __name__ == "__main__":
    main()
