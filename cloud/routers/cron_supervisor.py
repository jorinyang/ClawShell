"""CronSupervisor REST API — v2.1

Endpoints for:
  - Edge reporting CronReports to cloud
  - Manual trigger of health checks
  - Retrieving problems and dispatch history
"""

from __future__ import annotations
import sys
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.models import CronReport, Problem, DispatchRecord

router = APIRouter(tags=["cron_supervisor"])


# ── Engine lookup ──────────────────────────────────────────────────────────

def _get_supervisor(request: Request):
    eng = getattr(request.app.state, "cron_supervisor", None)
    if not eng:
        raise HTTPException(503, "CronSupervisor engine not initialized")
    return eng


def _get_router(request: Request):
    eng = getattr(request.app.state, "dispatch_router", None)
    if not eng:
        raise HTTPException(503, "DispatchRouter not initialized")
    return eng


# ── Request/Response models ─────────────────────────────────────────────────

class ReportBatchRequest(BaseModel):
    reports: list[CronReport]


class TriggerCheckResponse(BaseModel):
    triggered_at: float
    problems_found: int
    problems: list[Problem]


# ── Report ingestion endpoints ──────────────────────────────────────────────

@router.post("/cron-supervisor/reports")
async def ingest_report(report: CronReport, request: Request):
    """Receive a single CronReport from an edge node.

    Edge nodes POST their Cron execution results here after each task completes.
    The CloudCronSupervisor aggregates reports and runs problem detection.
    """
    supervisor = _get_supervisor(request)
    report_id = supervisor.add_report(report)
    return {"report_id": report_id, "status": "ingested"}


@router.post("/cron-supervisor/reports/batch")
async def ingest_reports(batch: ReportBatchRequest, request: Request):
    """Receive a batch of CronReports (for offline-cached reports sync)."""
    supervisor = _get_supervisor(request)
    ids = []
    for report in batch.reports:
        rid = supervisor.add_report(report)
        ids.append(rid)
    return {"ingested": len(ids), "report_ids": ids}


@router.get("/cron-supervisor/reports")
async def list_reports(
    request: Request,
    source: str = "",
    limit: int = 50,
):
    """Get recent CronReports, optionally filtered by source."""
    supervisor = _get_supervisor(request)
    reports = supervisor.get_reports(source=source, limit=limit)
    return {
        "count": len(reports),
        "reports": [r.model_dump(mode="json") for r in reports],
    }


# ── Problem management endpoints ────────────────────────────────────────────

@router.get("/cron-supervisor/problems")
async def list_problems(request: Request, status: str = ""):
    """List detected problems, optionally filtered by dispatch status."""
    supervisor = _get_supervisor(request)
    problems = supervisor.get_problems(status=status)
    return {
        "count": len(problems),
        "problems": [p.model_dump(mode="json") for p in problems],
    }


@router.get("/cron-supervisor/problems/{problem_id}")
async def get_problem(problem_id: str, request: Request):
    """Get a specific problem with its full dispatch history."""
    supervisor = _get_supervisor(request)
    problem = supervisor.get_problems()
    found = next((p for p in problem if p.problem_id == problem_id), None)
    if not found:
        raise HTTPException(404, f"Problem '{problem_id}' not found")

    dispatch_router = _get_router(request)
    history = dispatch_router.get_dispatch_history(problem_id)

    return {
        "problem": found.model_dump(mode="json"),
        "dispatch_history": [r.model_dump(mode="json") for r in history],
    }


# ── Dispatch endpoints ─────────────────────────────────────────────────────

@router.post("/cron-supervisor/problems/{problem_id}/dispatch")
async def redispatch_problem(problem_id: str, request: Request):
    """Manually re-trigger dispatch for a problem."""
    supervisor = _get_supervisor(request)
    problems = supervisor.get_problems()
    problem = next((p for p in problems if p.problem_id == problem_id), None)
    if not problem:
        raise HTTPException(404, f"Problem '{problem_id}' not found")

    dispatch_router = _get_router(request)
    action = problem.repair_action or "restart_daemons"
    record = dispatch_router.dispatch(problem, action)
    return {"dispatch_id": record.dispatch_id, "layer": record.layer, "result": record.result}


@router.post("/cron-supervisor/dispatch/confirm")
async def confirm_dispatch(dispatch_id: str, request: Request):
    """Edge confirms execution started/completed."""
    dispatch_router = _get_router(request)
    ok = dispatch_router.confirm(dispatch_id)
    return {"dispatch_id": dispatch_id, "confirmed": ok}


@router.post("/cron-supervisor/dispatch/fail")
async def report_dispatch_failure(
    dispatch_id: str,
    error: str,
    request: Request,
    retry_layer: Optional[str] = None,
):
    """Edge reports execution failure, triggering automatic fallback."""
    dispatch_router = _get_router(request)
    result = dispatch_router.report_failure(dispatch_id, error, retry_layer=retry_layer)
    if not result:
        raise HTTPException(404, f"Dispatch '{dispatch_id}' not found")
    return {
        "dispatch_id": dispatch_id,
        "result": result.result,
        "next_layer": result.next_layer,
    }


# ── Manual trigger ─────────────────────────────────────────────────────────

@router.post("/cron-supervisor/check")
async def trigger_check(request: Request):
    """Manually trigger a health check immediately (bypasses the 5-min cycle)."""
    supervisor = _get_supervisor(request)
    problems = supervisor.run_check_now()
    return TriggerCheckResponse(
        triggered_at=time.time(),
        problems_found=len(problems),
        problems=problems,
    )


# ── Stats ──────────────────────────────────────────────────────────────────

@router.get("/cron-supervisor/stats")
async def get_stats(request: Request):
    """Get supervisor statistics."""
    supervisor = _get_supervisor(request)
    dispatch_router = _get_router(request)
    return {
        "supervisor": supervisor.get_stats(),
        "dispatch": dispatch_router.get_stats(),
    }
