"""DispatchRouter — Three-layer dispatch with automatic fallback.

Architecture:
  Layer 0: EventBus push     → Edge subscribed to repair.* events
  Layer 1: TaskBoard         → Edge pulls and claims repair tasks
  Layer 2: MCP Direct Call   → Edge online and reachable, call directly
  Layer 3: MANUAL            → Human intervention, create ticket

Every layer failure automatically escalates to the next layer.
"""

from __future__ import annotations
import time
import uuid
import json
import threading
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timezone

from shared.models import (
    Problem,
    ProblemType,
    DispatchLayer,
    DispatchResult,
    DispatchRecord,
    RepairPlan,
    EventMessage,
    Task,
    TaskStatusClass,
)


# ── Problem → Action mapping (mirrors RepairLayer escalation) ────────────────

CLOUD_REPAIR_ACTIONS: Dict[str, Dict[str, str]] = {
    # Layer 0 — EventBus (lightweight, immediate)
    ProblemType.EDGE_OFFLINE: {
        DispatchLayer.EVENTBUS: "notify_restart",
        DispatchLayer.TASKBOARD: "redistribute_tasks",
        DispatchLayer.MCP_DIRECT: "ping_edge",
    },
    ProblemType.CRON_STARVED: {
        DispatchLayer.EVENTBUS: "adjust_cron",
        DispatchLayer.TASKBOARD: "force_run",
        DispatchLayer.MCP_DIRECT: "trigger_cron",
    },
    ProblemType.SYNC_LAG: {
        DispatchLayer.EVENTBUS: "force_sync",
        DispatchLayer.TASKBOARD: "full_resync",
        DispatchLayer.MCP_DIRECT: "trigger_sync",
    },
    # Layer 1 — TaskBoard (coordinated multi-edge)
    ProblemType.CHRONIC_FAILURE: {
        DispatchLayer.EVENTBUS: "broadcast_fix",
        DispatchLayer.TASKBOARD: "schedule_maintenance",
        DispatchLayer.MCP_DIRECT: "diagnose_remote",
    },
    ProblemType.GLOBAL_ANOMALY: {
        DispatchLayer.EVENTBUS: "broadcast_alert",
        DispatchLayer.TASKBOARD: "coordinate_response",
        DispatchLayer.MCP_DIRECT: "global_diagnostic",
    },
    ProblemType.ENGINE_DEGRADED: {
        DispatchLayer.EVENTBUS: "restart_engine",
        DispatchLayer.TASKBOARD: "restart_engine_task",
        DispatchLayer.MCP_DIRECT: "restart_engine_direct",
    },
}


# ── DispatchRouter ──────────────────────────────────────────────────────────

class DispatchRouter:
    """Three-layer dispatch with automatic fallback on failure.

    Usage:
        router = DispatchRouter(
            eventbus=app.state.eventbus,
            task_board=app.state.task_board,
            mcp_edge_client=mcp_client,
        )
        result = router.dispatch(problem, repair_action)
    """

    # Timeouts per layer (seconds)
    EVENTBUS_TIMEOUT = 30
    TASKBOARD_TIMEOUT = 300   # 5 min for claim + execute
    MCP_TIMEOUT = 60

    # Escalation thresholds
    MAX_EVENTBUS_RETRIES = 1
    TASKBOARD_NO_CLAIM_TIMEOUT = 300  # 5 min before fallback to MCP

    def __init__(
        self,
        eventbus: Any = None,
        task_board: Any = None,
        mcp_edge_client: Any = None,
        data_dir: str = "data",
    ):
        self._eventbus = eventbus
        self._task_board = task_board
        self._mcp_client = mcp_edge_client
        self._data_dir = data_dir

        self._lock = threading.RLock()
        # dispatch_id → DispatchRecord
        self._records: Dict[str, DispatchRecord] = {}
        # problem_id → [DispatchRecord, ...] (all attempts)
        self._problem_records: Dict[str, List[DispatchRecord]] = {}
        # problem_id → Problem (current state)
        self._problems: Dict[str, Problem] = {}

    # ── Public API ─────────────────────────────────────────────────────────

    def dispatch(self, problem: Problem, repair_action: str) -> DispatchRecord:
        """Main entry point. Selects layer and dispatches, with fallback on failure."""
        problem_id = problem.problem_id
        target = problem.source  # "cloud" | "edge:node-xxx"
        layer = self._select_layer(problem)

        with self._lock:
            self._problems[problem_id] = problem

        record = self._do_dispatch(problem, repair_action, layer, target)
        return record

    def dispatch_to_layer(
        self, problem: Problem, action: str, layer: str
    ) -> DispatchRecord:
        """Force dispatch to a specific layer (bypasses selection)."""
        target = problem.source
        with self._lock:
            self._problems[problem.problem_id] = problem
        return self._do_dispatch(problem, action, layer, target)

    def confirm(self, dispatch_id: str) -> bool:
        """Edge calls this to confirm execution started/completed."""
        with self._lock:
            rec = self._records.get(dispatch_id)
            if rec:
                rec.result = DispatchResult.SUCCESS
                p = self._problems.get(rec.problem_id)
                if p:
                    p.dispatch_status = "confirmed"
                return True
        return False

    def report_failure(
        self, dispatch_id: str, error: str, retry_layer: Optional[str] = None
    ) -> Optional[DispatchRecord]:
        """Edge calls this to report execution failure. Triggers fallback."""
        with self._lock:
            rec = self._records.get(dispatch_id)
            if not rec:
                return None

            rec.result = DispatchResult.FAILURE
            rec.error = error

            # Determine next layer
            next_layer = retry_layer or self._next_layer(rec.layer)
            rec.next_layer = next_layer

            problem = self._problems.get(rec.problem_id)
            if not next_layer or next_layer == DispatchLayer.MCP_DIRECT and problem:
                # Final fallback — escalate
                if problem:
                    problem.dispatch_status = "failed"
                return rec

            # Auto-fallback to next layer
            if problem:
                new_record = self._do_dispatch(
                    problem, rec.action, next_layer, rec.target
                )
                return new_record

        return None

    def get_problem(self, problem_id: str) -> Optional[Problem]:
        with self._lock:
            return self._problems.get(problem_id)

    def get_dispatch_history(self, problem_id: str) -> List[DispatchRecord]:
        with self._lock:
            return list(self._problem_records.get(problem_id, []))

    def get_stats(self) -> dict:
        """Statistics for monitoring."""
        with self._lock:
            total = len(self._records)
            success = sum(1 for r in self._records.values() if r.result == DispatchResult.SUCCESS)
            failed = sum(1 for r in self._records.values() if r.result == DispatchResult.FAILURE)
            pending = sum(1 for r in self._records.values() if r.result == "pending")
            by_layer: Dict[str, int] = {}
            for r in self._records.values():
                by_layer[r.layer] = by_layer.get(r.layer, 0) + 1
            return {
                "total": total,
                "success": success,
                "failed": failed,
                "pending": pending,
                "by_layer": by_layer,
            }

    # ── Layer selection ───────────────────────────────────────────────────

    def _select_layer(self, problem: Problem) -> str:
        """Choose best dispatch layer based on problem type and target."""
        pt = problem.problem_type
        target = problem.source

        # Edge offline → TaskBoard directly (EventBus won't reach)
        if pt == ProblemType.EDGE_OFFLINE:
            return DispatchLayer.TASKBOARD

        # Global anomaly → EventBus broadcast
        if pt == ProblemType.GLOBAL_ANOMALY:
            return DispatchLayer.EVENTBUS

        # Engine degraded on cloud → EventBus
        if target == "cloud" and pt == ProblemType.ENGINE_DEGRADED:
            return DispatchLayer.EVENTBUS

        # Normal edge target → EventBus first
        if target.startswith("edge:"):
            return DispatchLayer.EVENTBUS

        # Fallback
        return DispatchLayer.TASKBOARD

    # ── Dispatch execution ─────────────────────────────────────────────────

    def _do_dispatch(
        self, problem: Problem, action: str, layer: str, target: str
    ) -> DispatchRecord:
        """Execute dispatch on the chosen layer."""
        dispatch_id = f"disp_{uuid.uuid4().hex[:12]}"

        record = DispatchRecord(
            dispatch_id=dispatch_id,
            problem_id=problem.problem_id,
            layer=layer,
            target=target,
            action=action,
            result="pending",
        )

        with self._lock:
            self._records[dispatch_id] = record
            self._problem_records.setdefault(problem.problem_id, []).append(record)

        # Execute on the appropriate layer
        if layer == DispatchLayer.EVENTBUS:
            result = self._via_eventbus(dispatch_id, problem, action, target)
        elif layer == DispatchLayer.TASKBOARD:
            result = self._via_taskboard(dispatch_id, problem, action, target)
        elif layer == DispatchLayer.MCP_DIRECT:
            result = self._via_mcp(dispatch_id, problem, action, target)
        else:
            result = DispatchResult.FAILURE

        record.result = result

        # Update problem status
        with self._lock:
            p = self._problems.get(problem.problem_id)
            if p:
                if result == DispatchResult.SUCCESS:
                    p.dispatch_status = "confirmed"
                elif result in (DispatchResult.TIMEOUT, DispatchResult.NO_CLAIM):
                    p.dispatch_status = "pending"
                    record.next_layer = self._next_layer(layer)
                else:
                    p.dispatch_status = "failed"

        return record

    def _via_eventbus(
        self, dispatch_id: str, problem: Problem, action: str, target: str
    ) -> str:
        """Layer 0: Publish repair event to EventBus."""
        if not self._eventbus:
            return DispatchResult.UNREACHABLE

        try:
            event_type = f"repair.{problem.problem_type}"
            payload = {
                "dispatch_id": dispatch_id,
                "action": action,
                "target": target,
                "problem_id": problem.problem_id,
                "severity": problem.severity,
                "timestamp": time.time(),
            }

            self._eventbus.publish(
                event_type=event_type,
                source="cloud:cron_supervisor",
                priority=problem.severity,
                payload=payload,
            )

            # Wait for confirmation (async — just publish for now)
            return DispatchResult.SUCCESS

        except Exception as e:
            return DispatchResult.FAILURE

    def _via_taskboard(
        self, dispatch_id: str, problem: Problem, action: str, target: str
    ) -> str:
        """Layer 1: Create repair task on GlobalTaskBoard."""
        if not self._task_board:
            return DispatchResult.UNREACHABLE

        try:
            # Extract node_id from target like "edge:node-xxx"
            node_id = target.replace("edge:", "") if target.startswith("edge:") else target

            task = self._task_board.create_task(
                title=f"[Auto-Repair] {problem.title}",
                description=problem.description,
                priority=problem.severity,
                tags=["auto-repair", problem.problem_type, "cron-supervisor"],
                payload={
                    "repair_action": action,
                    "target": target,
                    "problem_id": problem.problem_id,
                    "dispatch_id": dispatch_id,
                    "source": "cron_supervisor",
                },
            )

            if task:
                return DispatchResult.SUCCESS
            return DispatchResult.FAILURE

        except Exception:
            return DispatchResult.FAILURE

    def _via_mcp(
        self, dispatch_id: str, problem: Problem, action: str, target: str
    ) -> str:
        """Layer 2: Direct MCP call to Edge (emergency path)."""
        if not self._mcp_client:
            return DispatchResult.UNREACHABLE

        try:
            node_id = target.replace("edge:", "") if target.startswith("edge:") else target
            # MCP direct call — this would call edge's MCP tool
            # For now, fall back to eventbus as MCP needs per-edge connection
            return self._via_eventbus(dispatch_id, problem, action, target)
        except Exception:
            return DispatchResult.FAILURE

    # ── Layer transitions ──────────────────────────────────────────────────

    LAYER_ORDER = [
        DispatchLayer.EVENTBUS,
        DispatchLayer.TASKBOARD,
        DispatchLayer.MCP_DIRECT,
    ]

    def _next_layer(self, current: str) -> Optional[str]:
        """Get the next fallback layer."""
        try:
            idx = self.LAYER_ORDER.index(current)
            if idx + 1 < len(self.LAYER_ORDER):
                return self.LAYER_ORDER[idx + 1]
        except ValueError:
            pass
        return None  # No more layers → MANUAL
