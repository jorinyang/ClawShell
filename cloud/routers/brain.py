"""Cloud Brain REST API router — LLM-powered analysis endpoints.

v1.12.0: Manual and scheduled analysis triggers.
"""
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

brain_router = APIRouter(prefix="/brain", tags=["brain"])


def _get_brain():
    from cloud.main import _brain
    if not _brain:
        raise HTTPException(503, "CloudBrain not initialized")
    return _brain


@brain_router.get("/status")
async def brain_status():
    """Get CloudBrain status and stats."""
    brain = _get_brain()
    return format_api_response(True, data=brain.stats)


@brain_router.get("/analyses")
async def list_analyses(limit: int = Query(20)):
    """Get recent LLM analyses."""
    return format_api_response(True, data={
        "analyses": _get_brain().get_recent_analyses(limit)
    })


@brain_router.post("/analyze")
async def trigger_analysis(request: Request):
    """Trigger an LLM analysis on demand."""
    body = await request.json()
    query = body.get("query", "")
    brain = _get_brain()
    
    if query:
        result = brain.generate_insight(query)
    else:
        result = brain.analyze_periodic()
    
    return format_api_response(result.get("success", False), data=result)


@brain_router.post("/review")
async def trigger_deep_review():
    """Trigger a deep architecture review (6h scope)."""
    result = _get_brain().deep_review()
    return format_api_response(result.get("success", False), data=result)


@brain_router.post("/plan")
async def trigger_planning(request: Request):
    """Trigger architecture planning for a specific problem."""
    body = await request.json()
    description = body.get("description", "Analyze the current system state and suggest improvements.")
    result = _get_brain().plan_architecture(description)
    return format_api_response(result.get("success", False), data=result)
