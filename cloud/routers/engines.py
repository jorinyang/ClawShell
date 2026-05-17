"""Engines API Router — endpoints for N8N, Swarm, Scheduler, Optimizer, Workflow, DeepThink.

Exposes all previously headless engines via REST API.
v1.8.1 / v1.9.0
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter(tags=["engines"])


# ── Request/Response Models ────────────────────────────

class N8NTriggerRequest(BaseModel):
    webhook_url: str
    payload: Dict[str, Any] = {}


class SchedulerTriggerRequest(BaseModel):
    task_id: str


class OptimizerRequest(BaseModel):
    task_count: int = 1
    goal: str = "balanced"
    required_cpu: float = 0.1
    required_memory_mb: float = 64.0


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    steps: List[Dict[str, Any]] = []
    tags: List[str] = []


class DeepThinkRequest(BaseModel):
    question: str
    complete: bool = True
    confidence: float = 0.0


# ── N8N Endpoints ──────────────────────────────────────

@router.get("/n8n/status")
async def n8n_status(request: Request):
    """Get N8N bridge health status."""
    bridge = getattr(request.app.state, 'n8n_bridge', None)
    if not bridge:
        return {"status": "unavailable", "error": "N8N bridge not initialized"}
    try:
        health = bridge.health_check()
        routes = bridge.list_routes()
        return {
            "status": "ok",
            "health": health,
            "routes_count": len(routes),
            "routes": routes,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/n8n/trigger")
async def n8n_trigger(body: N8NTriggerRequest, request: Request):
    """Trigger an N8N workflow via webhook URL."""
    bridge = getattr(request.app.state, 'n8n_bridge', None)
    if not bridge:
        raise HTTPException(503, "N8N bridge not available")
    result = bridge.trigger_workflow(body.webhook_url, body.payload)
    return {"status": "ok", "result": result}


# ── Swarm Endpoints ────────────────────────────────────

@router.get("/swarm/status")
async def swarm_status(request: Request):
    """Get SwarmCoordinator status."""
    swarm = getattr(request.app.state, 'swarm', None)
    if not swarm:
        return {"status": "unavailable", "error": "Swarm coordinator not initialized"}
    nodes = swarm.list_nodes()
    online = swarm.online_count()
    return {
        "status": "ok",
        "total_nodes": len(nodes),
        "online_nodes": online,
        "recent_events": swarm.get_recent_events(limit=10),
    }


@router.get("/swarm/nodes")
async def swarm_nodes(request: Request, status: Optional[str] = None):
    """List swarm nodes, optionally filtered by status."""
    swarm = getattr(request.app.state, 'swarm', None)
    if not swarm:
        raise HTTPException(503, "Swarm coordinator not available")
    nodes = swarm.list_nodes(status=status)
    return {"nodes": nodes, "count": len(nodes)}


# ── Scheduler Endpoints ────────────────────────────────

@router.get("/scheduler/jobs")
async def scheduler_jobs(request: Request):
    """List all scheduled jobs."""
    scheduler = getattr(request.app.state, 'scheduler', None)
    if not scheduler:
        raise HTTPException(503, "Scheduler not available")
    tasks = scheduler.list_tasks()
    return {"jobs": tasks, "count": len(tasks)}


@router.post("/scheduler/trigger")
async def scheduler_trigger(body: SchedulerTriggerRequest, request: Request):
    """Manually trigger a scheduled job."""
    scheduler = getattr(request.app.state, 'scheduler', None)
    if not scheduler:
        raise HTTPException(503, "Scheduler not available")
    result = scheduler.run_task_now(body.task_id)
    if result is None:
        raise HTTPException(404, f"Task '{body.task_id}' not found")
    return {"status": "ok", "result": result}


# ── Optimizer Endpoints ────────────────────────────────

@router.get("/optimizer/status")
async def optimizer_status(request: Request):
    """Get optimizer status and stats."""
    optimizer = getattr(request.app.state, 'optimizer', None)
    if not optimizer:
        return {"status": "unavailable", "error": "Optimizer not initialized"}
    stats = optimizer.get_stats()
    last_result = optimizer.get_last_result()
    return {
        "status": "ok",
        "stats": stats,
        "last_result": last_result.to_dict() if last_result else None,
    }


@router.post("/optimizer/optimize")
async def optimizer_optimize(body: OptimizerRequest, request: Request):
    """Trigger resource optimization."""
    from cloud.engines.optimizer import OptimizationGoal
    optimizer = getattr(request.app.state, 'optimizer', None)
    if not optimizer:
        raise HTTPException(503, "Optimizer not available")

    try:
        goal = OptimizationGoal(body.goal)
    except ValueError:
        goal = OptimizationGoal.BALANCED

    result = optimizer.optimize(
        task_count=body.task_count,
        goal=goal,
        required_cpu=body.required_cpu,
        required_memory_mb=body.required_memory_mb,
    )
    return {"status": "ok", "result": result.to_dict()}


# ── Workflow Endpoints ─────────────────────────────────

@router.get("/workflow/list")
async def workflow_list(request: Request):
    """List all workflows."""
    workflow_engine = getattr(request.app.state, 'workflow', None)
    if not workflow_engine:
        raise HTTPException(503, "Workflow engine not available")
    workflows = workflow_engine.list_workflows()
    return {
        "workflows": [w.to_dict() for w in workflows],
        "count": len(workflows),
        "stats": workflow_engine.get_stats(),
    }


@router.post("/workflow/create")
async def workflow_create(body: WorkflowCreateRequest, request: Request):
    """Create a new workflow."""
    from cloud.engines.workflow import Workflow, Step, StepType
    workflow_engine = getattr(request.app.state, 'workflow', None)
    if not workflow_engine:
        raise HTTPException(503, "Workflow engine not available")

    steps = []
    for s in body.steps:
        step_type = StepType(s.get("step_type", "task"))
        steps.append(Step(
            name=s.get("name", ""),
            step_type=step_type,
            description=s.get("description", ""),
            config=s.get("config", {}),
        ))

    wf = Workflow(name=body.name, description=body.description,
                  steps=steps, tags=body.tags)
    created = workflow_engine.register_workflow(wf)
    return {"status": "ok", "workflow": created.to_dict()}


@router.post("/workflow/{workflow_id}/execute")
async def workflow_execute(workflow_id: str, request: Request):
    """Execute a workflow."""
    workflow_engine = getattr(request.app.state, 'workflow', None)
    if not workflow_engine:
        raise HTTPException(503, "Workflow engine not available")
    execution = workflow_engine.start_execution(workflow_id)
    if not execution:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found or has no steps")
    return {"status": "ok", "execution": execution.to_dict()}


# ── Deep Think Endpoints ───────────────────────────────

@router.get("/deep-think/status")
async def deep_think_status(request: Request):
    """Get deep think engine status."""
    engine = getattr(request.app.state, 'deep_think', None)
    if not engine:
        return {"status": "unavailable", "error": "DeepThink engine not initialized"}
    return {"status": "ok", "stats": engine.get_stats()}


@router.post("/deep-think/analyze")
async def deep_think_analyze(body: DeepThinkRequest, request: Request):
    """Start a deep analysis session."""
    engine = getattr(request.app.state, 'deep_think', None)
    if not engine:
        raise HTTPException(503, "DeepThink engine not available")

    result = engine.start_session(body.question)
    if body.complete:
        result = engine.complete_session(result.session_id, confidence=body.confidence)
    return {"status": "ok", "session": result.to_dict() if result else None}
