"""OrchestrationEngine — unified L3 orchestration (TaskOrganizer+ContextManager) v2.3."""
from __future__ import annotations
import json, time, threading, os
from typing import Dict, List, Any, Optional

class OrchestrationEngine:
    """Unified L3 orchestration: DAG task decomposition + shared state context."""

    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._dags: Dict[str, dict] = {}
        self._context: Dict[str, Any] = {}
        self._history: list = []
        self._lock = threading.RLock()
        self._load()

    # ── Task DAG ──
    def decompose(self, task: dict) -> dict:
        dag_id = task.get("task_id", f"dag-{int(time.time())}")
        desc = task.get("description", task.get("title", ""))
        subtasks = [{"id": f"{dag_id}-s{i+1}", "description": f"Step {i+1}: {desc[:40]}",
                     "status": "pending", "depends_on": [f"{dag_id}-s{i}"] if i>0 else [], "order": i+1}
                    for i in range(min(3, max(1, len(desc)//50)))]
        with self._lock:
            self._dags[dag_id] = {"dag_id": dag_id, "parent": task, "subtasks": subtasks,
                                   "status": "pending", "created_at": time.time()}
            self._save()
        return self._dags[dag_id]

    def next_ready(self, dag_id: str) -> Optional[dict]:
        dag = self._dags.get(dag_id, {})
        completed = {s["id"] for s in dag.get("subtasks", []) if s.get("status") == "completed"}
        for st in dag.get("subtasks", []):
            if st.get("status") == "pending" and set(st.get("depends_on", [])).issubset(completed):
                return st
        return None

    def mark_complete(self, dag_id: str, subtask_id: str, result: Any = None):
        with self._lock:
            for st in self._dags.get(dag_id, {}).get("subtasks", []):
                if st["id"] == subtask_id:
                    st["status"] = "completed"; st["result"] = result; st["completed_at"] = time.time()
            if all(s.get("status")=="completed" for s in self._dags[dag_id]["subtasks"]):
                self._dags[dag_id]["status"] = "completed"
            self._save()

    def get_dag_stats(self) -> dict:
        statuses = {}
        for d in self._dags.values():
            s = d.get("status", "unknown"); statuses[s] = statuses.get(s, 0) + 1
        return {"total_dags": len(self._dags), "by_status": statuses}

    # ── Context ──
    def set_context(self, key: str, value: Any):
        with self._lock:
            old = self._context.get(key)
            self._context[key] = value
            self._history.append({"key": key, "old": old, "new": value, "timestamp": time.time()})
            self._save()

    def get_context(self, key: str, default: Any = None) -> Any:
        return self._context.get(key, default)

    def snapshot(self) -> dict:
        with self._lock:
            return {"context": dict(self._context), "history_len": len(self._history), "timestamp": time.time()}

    def _load(self):
        try:
            with open(os.path.join(self._data_dir, "orchestration.json")) as f:
                d = json.load(f); self._dags = d.get("dags", {}); self._context = d.get("context", {})
        except: pass
    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "orchestration.json"), "w") as f:
                json.dump({"dags": self._dags, "context": self._context}, f, indent=2)
        except: pass
