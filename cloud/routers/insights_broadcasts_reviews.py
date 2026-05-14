"""Insight/Broadcast/Review/Evolution REST API routers — v1.12.0 (uses app.state)."""
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

insights_router = APIRouter(prefix="/insights", tags=["insights"])
broadcasts_router = APIRouter(prefix="/broadcasts", tags=["broadcasts"])
reviews_router = APIRouter(prefix="/reviews", tags=["reviews"])
evolution_router = APIRouter(prefix="/evolution", tags=["evolution"])

def _get_evolution(request: Request = None):
    if request and hasattr(request.app.state, "evolution"):
        evo = request.app.state.evolution
        if evo: return evo
    from cloud.main import _evolution
    if not _evolution: raise HTTPException(503)
    return _evolution

def _get_broadcast(request: Request = None):
    if request and hasattr(request.app.state, "broadcast"):
        bc = request.app.state.broadcast
        if bc: return bc
    from cloud.main import _broadcast
    if not _broadcast: raise HTTPException(503)
    return _broadcast

def _get_review(request: Request = None):
    if request and hasattr(request.app.state, "review"):
        rv = request.app.state.review
        if rv: return rv
    from cloud.main import _review
    if not _review: raise HTTPException(503)
    return _review

# ── Insights ──
@insights_router.get("/")
async def list_insights(request: Request, limit: int = Query(50)):
    return format_api_response(True, data={"insights": _get_evolution(request).get_insights(limit=limit)})

@insights_router.post("/")
async def add_insight(request: Request):
    body = await request.json()
    iid = _get_evolution(request).add_insight(
        body.get("title", ""), body.get("content", ""),
        category=body.get("category", "general"),
        confidence=body.get("confidence", 0.5),
    )
    return format_api_response(True, data={"insight_id": iid})

# ── Broadcasts ──
@broadcasts_router.get("/")
async def list_broadcasts(request: Request, limit: int = Query(50)):
    return format_api_response(True, data={"broadcasts": _get_broadcast(request).get_broadcasts(limit=limit)})

@broadcasts_router.post("/")
async def create_broadcast(request: Request):
    body = await request.json()
    bid = _get_broadcast(request).broadcast(
        body.get("title", ""), body.get("content", ""),
        broadcast_type=body.get("broadcast_type", "announcement"),
    )
    return format_api_response(True, data={"broadcast_id": bid})

@broadcasts_router.get("/best-practices")
async def search_best_practices(request: Request, q: str = Query("")):
    return format_api_response(True, data={"practices": _get_broadcast(request).search_best_practices(q)})

@broadcasts_router.post("/best-practices")
async def register_best_practice(request: Request):
    body = await request.json()
    pid = _get_broadcast(request).register_best_practice(body.get("title", ""), body.get("content", ""))
    return format_api_response(True, data={"practice_id": pid})

# ── Reviews ──
@reviews_router.get("/")
async def list_reviews(request: Request, review_type: str = Query(None), limit: int = Query(20)):
    return format_api_response(True, data={"reviews": _get_review(request).get_recent_reviews(review_type, limit)})

@reviews_router.post("/run")
async def run_review(request: Request):
    body = await request.json()
    result = _get_review(request).run_review_now(body.get("type", "daily"))
    return format_api_response(True, data=result)

# ── Evolution ──
@evolution_router.get("/stats")
async def evolution_stats(request: Request):
    return format_api_response(True, data=_get_evolution(request).get_stats())

@evolution_router.get("/history")
async def evolution_history(request: Request, limit: int = Query(100)):
    return format_api_response(True, data={"history": _get_evolution(request).get_history(limit)})

@evolution_router.get("/patterns")
async def evolution_patterns(request: Request, limit: int = Query(50)):
    return format_api_response(True, data={"patterns": _get_evolution(request).get_patterns(limit)})
