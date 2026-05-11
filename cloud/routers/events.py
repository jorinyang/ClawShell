"""EventBus REST API router.

Endpoints:
- POST /api/v1/events/batch — Ingest events from edges
- GET  /api/v1/events/ — Query events
- GET  /api/v1/events/{event_id} — Get single event
- GET  /api/v1/events/stats — Get event statistics
- POST /api/v1/events/broadcast — Cloud-initiated broadcast
"""

from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

router = APIRouter(prefix="/events", tags=["events"])


def _get_eventbus():
    """Get CloudEventBus from app state."""
    from cloud.main import _eventbus
    if not _eventbus:
        raise HTTPException(status_code=503, detail="EventBus not initialized")
    return _eventbus


@router.post("/batch")
async def ingest_events(request: Request):
    """Ingest a batch of events from an edge node."""
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")

    events = body.get("events", [])
    if not isinstance(events, list):
        return format_api_response(False, error="'events' must be a list")

    eb = _get_eventbus()
    accepted = eb.ingest(events)
    return format_api_response(True, data={"accepted": accepted, "total": len(events)})


@router.get("/")
async def query_events(
    event_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    since: Optional[float] = Query(None),
    until: Optional[float] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Query events with optional filters."""
    eb = _get_eventbus()
    results = eb.query(
        event_type=event_type,
        source=source,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return format_api_response(True, data={"events": results, "count": len(results)})


@router.get("/stats")
async def event_stats():
    """Get EventBus statistics."""
    eb = _get_eventbus()
    return format_api_response(True, data=eb.get_stats())


@router.get("/{event_id}")
async def get_event(event_id: str):
    """Get a single event by ID."""
    eb = _get_eventbus()
    event = eb.get_event(event_id)
    if not event:
        return format_api_response(False, error=f"Event '{event_id}' not found")
    return format_api_response(True, data=event)


@router.post("/broadcast")
async def broadcast_events(request: Request):
    """Cloud-initiated broadcast to all edges."""
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")

    events = body.get("events", [])
    if not isinstance(events, list):
        return format_api_response(False, error="'events' must be a list")

    eb = _get_eventbus()
    accepted_ids = eb.broadcast(events)
    return format_api_response(True, data={"broadcast_ids": accepted_ids})
