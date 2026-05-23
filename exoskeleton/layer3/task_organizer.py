"""TaskOrganizer — DAG task orchestration engine (L3 Self-Organization).

From README: L3 自组织 — TaskOrganizer(DAG) + ContextManager + N8N.
"""
from __future__ import annotations
import json, time, threading
import os
from typing import Dict, List, Any, Optional

class TaskOrganizer:
    """DAG-based task decomposition and execution orchestrator."""

    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._data_dir = data_dir
        self._storage = os.path.join(os.path.expanduser(data_dir), "task_dag.json") if not data_dir.startswith("/") else os.path.join(data_dir, "task_dag.json")
        os.makedirs(os.path.dirname(self._storage), exist_ok=True)
        self._dags: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._load()

    def decompose(self, task: dict) -> dict:
        """Decompose a complex task into DAG sub-tasks."""
        dag_id = task.get("task_id", f"dag-{int(time.time())}")
        subtasks = self._topological_decompose(task)
        dag = {"dag_id": dag_id, "parent": task, "subtasks": subtasks, "created_at": time.time(), "status": "pending"}
        with self._lock:
            self._dags[dag_id] = dag
            self._save()
        return dag

    def next_ready(self, dag_id: str) -> Optional[dict]:
        """Get next ready subtask respecting DAG dependencies."""
        dag = self._dags.get(dag_id, {})
        subtasks = dag.get("subtasks", [])
        completed = {s["id"] for s in subtasks if s.get("status") == "completed"}
        for st in subtasks:
            deps = set(st.get("depends_on", []))
            if deps.issubset(completed) and st.get("status") == "pending":
                return st
        return None

    def mark_complete(self, dag_id: str, subtask_id: str, result: Any = None):
        with self._lock:
            dag = self._dags.get(dag_id, {})
            for st in dag.get("subtasks", []):
                if st["id"] == subtask_id:
                    st["status"] = "completed"
                    st["result"] = result
                    st["completed_at"] = time.time()
            all_done = all(s.get("status") == "completed" for s in dag.get("subtasks", []))
            if all_done:
                dag["status"] = "completed"
            self._save()

    def stats(self) -> dict:
        with self._lock:
            statuses = {}
            for d in self._dags.values():
                s = d.get("status", "unknown")
                statuses[s] = statuses.get(s, 0) + 1
            return {"total_dags": len(self._dags), "by_status": statuses}

    def _topological_decompose(self, task: dict) -> List[dict]:
        desc = task.get("description", task.get("title", ""))
        return [{"id": f"{task.get('task_id','t')}-s{i+1}", "description": f"Step {i+1}: {desc[:40]}",
                 "status": "pending", "depends_on": [f"{task.get('task_id','t')}-s{i}"] if i > 0 else [],
                 "order": i + 1} for i in range(min(3, max(1, len(desc)//50)))]

    def _load(self):
        try:
            with open(self._storage) as f:
                self._dags = json.load(f)
        except Exception:
            self._dags = {}

    def _save(self):
        try:
            with open(self._storage, "w") as f:
                json.dump(self._dags, f, indent=2)
        except Exception:
            pass
