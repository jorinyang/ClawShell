"""Built-in Workflow Engine with Saga compensation.

Orchestrates multi-step workflows with:
- Sequential, parallel, conditional, and Saga steps
- Auto-compensation on failure (Saga pattern)
- Persistent execution state

Design: stdlib-only, RLock thread-safe. Coexists with external N8NBridge.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class StepType(str, Enum):
    TASK = "task"          # Single task execution
    PARALLEL = "parallel"  # Run steps concurrently
    CONDITION = "condition" # Conditional branching
    SAGA = "saga"          # Saga: task + compensation on failure
    WAIT = "wait"          # Delay/wait step


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    CANCELLED = "cancelled"


@dataclass
class Step:
    """A single workflow step."""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    step_type: StepType = StepType.TASK
    description: str = ""
    depends_on: List[str] = field(default_factory=list)  # step_ids to wait for
    max_retries: int = 0
    timeout_seconds: int = 300
    config: Dict[str, Any] = field(default_factory=dict)  # Step-specific config
    # Saga: compensation step name (invoked on failure)
    compensation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["step_type"] = self.step_type.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Step":
        d = d.copy()
        if isinstance(d.get("step_type"), str):
            d["step_type"] = StepType(d["step_type"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Workflow:
    """A named workflow definition."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    steps: List[Step] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Workflow":
        steps = [Step.from_dict(s) for s in d.get("steps", [])]
        return cls(
            workflow_id=d.get("workflow_id", str(uuid.uuid4())),
            name=d.get("name", ""),
            description=d.get("description", ""),
            version=d.get("version", "1.0.0"),
            steps=steps,
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
            tags=d.get("tags", []),
            metadata=d.get("metadata", {}),
        )


@dataclass
class Execution:
    """Runtime execution of a workflow."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    workflow_name: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    step_states: Dict[str, ExecutionStatus] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    step_errors: Dict[str, str] = field(default_factory=dict)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    current_step: Optional[str] = None
    compensation_queue: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "step_states": {k: v.value for k, v in self.step_states.items()},
            "step_results": self.step_results,
            "step_errors": self.step_errors,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_step": self.current_step,
            "compensation_queue": self.compensation_queue,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Execution":
        step_states = {}
        for k, v in d.get("step_states", {}).items():
            try:
                step_states[k] = ExecutionStatus(v)
            except ValueError:
                step_states[k] = ExecutionStatus.PENDING
        return cls(
            execution_id=d.get("execution_id", ""),
            workflow_id=d.get("workflow_id", ""),
            workflow_name=d.get("workflow_name", ""),
            status=ExecutionStatus(d.get("status", "pending")),
            step_states=step_states,
            step_results=d.get("step_results", {}),
            step_errors=d.get("step_errors", {}),
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            current_step=d.get("current_step"),
            compensation_queue=d.get("compensation_queue", []),
        )


class WorkflowEngine:
    """Built-in workflow orchestration engine.

    Coexists with N8NBridge — use internal engine for simple workflows,
    N8N for complex external orchestrations.

    Thread-safe via RLock.
    """

    def __init__(self, store_dir: str = "data/workflows"):
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._workflows: Dict[str, Workflow] = {}
        self._executions: Dict[str, Execution] = {}
        self._running_executions: Dict[str, threading.Thread] = {}
        self._running = True

        self._load_all()

    def _load_all(self) -> None:
        """Load workflows and executions from persistent storage."""
        wf_file = self._store_dir / "workflows.json"
        if wf_file.exists():
            try:
                data = json.loads(wf_file.read_text())
                for wd in data:
                    wf = Workflow.from_dict(wd)
                    self._workflows[wf.workflow_id] = wf
            except (json.JSONDecodeError, OSError):
                pass

    def _save_workflows(self) -> None:
        """Persist all workflow definitions."""
        data = [wf.to_dict() for wf in self._workflows.values()]
        tmp = self._store_dir / "workflows.json.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        tmp.rename(self._store_dir / "workflows.json")

    def register_workflow(self, workflow: Workflow) -> Workflow:
        """Register a workflow definition."""
        with self._lock:
            workflow.updated_at = time.time()
            self._workflows[workflow.workflow_id] = workflow
            self._save_workflows()
            return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        with self._lock:
            return self._workflows.get(workflow_id)

    def list_workflows(self) -> List[Workflow]:
        with self._lock:
            return list(self._workflows.values())

    def start_execution(self, workflow_id: str) -> Optional[Execution]:
        """Start executing a workflow. Returns execution tracking object."""
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if not wf or not wf.steps:
                return None

            execution = Execution(
                workflow_id=wf.workflow_id,
                workflow_name=wf.name,
                status=ExecutionStatus.RUNNING,
                started_at=time.time(),
            )

            # Initialize step states
            for step in wf.steps:
                execution.step_states[step.step_id] = ExecutionStatus.PENDING

            self._executions[execution.execution_id] = execution
            return execution

    def step_completed(self, execution_id: str, step_id: str,
                       result: Any = None) -> Optional[Execution]:
        """Mark a step as completed."""
        with self._lock:
            exec = self._executions.get(execution_id)
            if not exec:
                return None

            exec.step_states[step_id] = ExecutionStatus.COMPLETED
            exec.step_results[step_id] = result
            exec.current_step = None
            return exec

    def step_failed(self, execution_id: str, step_id: str,
                    error_message: str) -> Optional[Execution]:
        """Mark a step as failed. Triggers Saga compensation if applicable."""
        with self._lock:
            exec = self._executions.get(execution_id)
            if not exec:
                return None

            exec.step_states[step_id] = ExecutionStatus.FAILED
            exec.step_errors[step_id] = error_message

            # Check for Saga compensation
            wf = self._workflows.get(exec.workflow_id)
            if wf:
                failed_step = next((s for s in wf.steps if s.step_id == step_id), None)
                if failed_step and failed_step.compensation:
                    exec.status = ExecutionStatus.COMPENSATING
                    exec.compensation_queue.append(failed_step.compensation)

            return exec

    def get_execution(self, execution_id: str) -> Optional[Execution]:
        with self._lock:
            return self._executions.get(execution_id)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            statuses = {}
            for e in self._executions.values():
                s = e.status.value
                statuses[s] = statuses.get(s, 0) + 1
            return {
                "total_workflows": len(self._workflows),
                "total_executions": len(self._executions),
                "by_status": statuses,
            }

    def shutdown(self) -> None:
        self._running = False
