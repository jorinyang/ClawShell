"""TaskBoard REST API router."""
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

router = APIRouter(prefix="/tasks", tags=["tasks"])

def _get_taskboard():
    from cloud.main import _task_board
    if not _task_board:
        raise HTTPException(503, "TaskBoard not initialized")
    return _task_board

@router.post("/")
async def create_task(request: Request):
    body = await request.json()
    tb = _get_taskboard()
    tid = tb.create_task(body)
    return format_api_response(True, data={"task_id": tid})

@router.get("/")
async def list_tasks(status: str = Query(None), priority: str = Query(None),
                     limit: int = Query(100), offset: int = Query(0)):
    tb = _get_taskboard()
    tasks = tb.list_tasks(status=status, priority=priority, limit=limit, offset=offset)
    return format_api_response(True, data={"tasks": tasks, "count": len(tasks)})

@router.get("/{task_id}")
async def get_task(task_id: str):
    tb = _get_taskboard()
    task = tb.get_task(task_id)
    if not task: return format_api_response(False, error="Not found")
    return format_api_response(True, data=task)

@router.post("/{task_id}/claim")
async def claim_task(task_id: str, request: Request):
    body = await request.json()
    edge_id = body.get("edge_id", "")
    tb = _get_taskboard()
    try:
        task = tb.claim(task_id, edge_id)
        return format_api_response(True, data=task)
    except ValueError as e:
        return format_api_response(False, error=str(e))

@router.post("/{task_id}/complete")
async def complete_task(task_id: str, request: Request):
    body = await request.json()
    tb = _get_taskboard()
    try:
        task = tb.complete(task_id, body.get("result"))
        return format_api_response(True, data=task)
    except ValueError as e:
        return format_api_response(False, error=str(e))

@router.post("/{task_id}/fail")
async def fail_task(task_id: str, request: Request):
    body = await request.json()
    tb = _get_taskboard()
    try:
        task = tb.fail(task_id, body.get("error"))
        return format_api_response(True, data=task)
    except ValueError as e:
        return format_api_response(False, error=str(e))

@router.get("/stats")
async def task_stats():
    return format_api_response(True, data=_get_taskboard().get_stats())
