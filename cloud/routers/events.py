"""Event REST API router — v1.12.0 (uses app.state with fallback)."""
from fastapi import APIRouter, Request, Query, HTTPException
from typing import Optional
from shared.protocol import format_api_response

router = APIRouter(prefix="/events", tags=["events"])


def _get_eventbus(request: Request = None):
    if request and hasattr(request.app.state, "eventbus"):
        eb = request.app.state.eventbus
        if eb:
            return eb
    from cloud.main import _eventbus
    if not _eventbus:
        raise HTTPException(503, "EventBus not initialized")
    return _eventbus


@router.post("/batch")
async def ingest_events(request: Request):
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")
    events = body.get("events", [])
    if not isinstance(events, list):
        return format_api_response(False, error="'events' must be a list")
    eb = _get_eventbus(request)
    accepted = eb.ingest(events)
    return format_api_response(True, data={"accepted": accepted, "total": len(events)})


@router.get("/")
async def query_events(request: Request, event_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None), since: Optional[float] = Query(None),
    until: Optional[float] = Query(None), limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)):
    eb = _get_eventbus(request)
    results = eb.query(event_type=event_type, source=source, since=since, until=until, limit=limit, offset=offset)
    return format_api_response(True, data={"events": results, "count": len(results)})


@router.get("/stats")
async def event_stats(request: Request):
    eb = _get_eventbus(request)
    return format_api_response(True, data=eb.get_stats())


@router.get("/{event_id}")
async def get_event(event_id: str, request: Request):
    eb = _get_eventbus(request)
    event = eb.get_event(event_id)
    if not event:
        return format_api_response(False, error=f"Event '{event_id}' not found")
    return format_api_response(True, data=event)


@router.post("/broadcast")
async def broadcast_events(request: Request):
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")
    events = body.get("events", [])
    if not isinstance(events, list):
        return format_api_response(False, error="'events' must be a list")
    eb = _get_eventbus(request)
    accepted_ids = eb.broadcast(events)
    return format_api_response(True, data={"broadcast_ids": accepted_ids})
