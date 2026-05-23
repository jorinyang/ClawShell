"""SwarmManager — Multi-agent swarm coordination (L4)."""
from __future__ import annotations
import json, time, threading, os
from typing import Dict, List, Any

class SwarmManager:
    """Coordinates multiple edge agents in a swarm cluster."""
    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._nodes: Dict[str, dict] = {}
        self._tasks: List[dict] = []
        self._lock = threading.RLock()
        self._load()

    def register(self, node_id: str, capabilities: List[str] = None) -> dict:
        with self._lock:
            self._nodes[node_id] = {"node_id": node_id, "capabilities": capabilities or [],
                                     "status": "online", "joined": time.time(),
                                     "tasks_completed": 0}
            self._save()
        return self._nodes[node_id]

    def heartbeat(self, node_id: str, metrics: dict = None) -> bool:
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id]["last_heartbeat"] = time.time()
                if metrics: self._nodes[node_id]["metrics"] = metrics
                return True
        return False

    def get_online(self) -> List[dict]:
        cutoff = time.time() - 60
        return [n for n in self._nodes.values() if n.get("last_heartbeat", 0) > cutoff]

    def dispatch(self, task: dict, strategy: str = "round_robin") -> str:
        online = self.get_online()
        if not online: return ""
        target = online[hash(task.get("id","")) % len(online)]
        self._tasks.append({**task, "assigned_to": target["node_id"], "dispatched_at": time.time()})
        return target["node_id"]

    def stats(self) -> dict:
        with self._lock:
            return {"total_nodes": len(self._nodes), "online": len(self.get_online()),
                    "pending_tasks": sum(1 for t in self._tasks if not t.get("completed_at"))}

    def _load(self):
        try:
            with open(os.path.join(self._data_dir, "swarm.json")) as f:
                data = json.load(f)
                self._nodes = data.get("nodes", {})
        except Exception: pass

    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "swarm.json"), "w") as f:
                json.dump({"nodes": self._nodes}, f, indent=2)
        except Exception: pass
