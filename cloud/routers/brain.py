"""Cloud Brain REST API router — v1.12.0 (uses app.state)."""
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

brain_router = APIRouter(prefix="/brain", tags=["brain"])


def _get_brain(request: Request):
    brain = request.app.state.brain if hasattr(request.app.state, "brain") else None
    if not brain:
        raise HTTPException(503, "CloudBrain not initialized")
    return brain


@brain_router.get("/status")
async def brain_status(request: Request):
    return format_api_response(True, data=_get_brain(request).stats)


@brain_router.get("/analyses")
async def list_analyses(request: Request, limit: int = Query(20)):
    return format_api_response(True, data={
        "analyses": _get_brain(request).get_recent_analyses(limit)
    })


@brain_router.post("/analyze")
async def trigger_analysis(request: Request):
    body = await request.json()
    query = body.get("query", "")
    brain = _get_brain(request)
    result = brain.generate_insight(query) if query else brain.analyze_periodic()
    return format_api_response(result.get("success", False), data=result)


@brain_router.post("/review")
async def trigger_deep_review(request: Request):
    result = _get_brain(request).deep_review()
    return format_api_response(result.get("success", False), data=result)


@brain_router.post("/plan")
async def trigger_planning(request: Request):
    body = await request.json()
    desc = body.get("description", "Analyze system state")
    result = _get_brain(request).plan_architecture(desc)
    return format_api_response(result.get("success", False), data=result)
