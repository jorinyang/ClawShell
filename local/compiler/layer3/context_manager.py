"""ContextManager — Cross-task state and context manager (L3).

From README: L3 自组织 — ContextManager for shared state.
"""
from __future__ import annotations
import json, time, threading, os
from typing import Dict, Any

class ContextManager:
    """Manages shared state context across concurrent tasks."""

    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._storage = os.path.join(os.path.expanduser(data_dir), "context.json")
        os.makedirs(os.path.dirname(self._storage), exist_ok=True)
        self._context: Dict[str, Any] = {}
        self._history: list = []
        self._lock = threading.RLock()
        self._load()

    def set(self, key: str, value: Any):
        with self._lock:
            old = self._context.get(key)
            self._context[key] = value
            self._history.append({"key": key, "old": old, "new": value, "timestamp": time.time()})
            self._save()

    def get(self, key: str, default: Any = None) -> Any:
        return self._context.get(key, default)

    def snapshot(self) -> dict:
        with self._lock:
            return {"context": dict(self._context), "history_len": len(self._history), "timestamp": time.time()}

    def _load(self):
        try:
            with open(self._storage) as f:
                data = json.load(f)
                self._context = data.get("context", {})
                self._history = data.get("history", [])
        except Exception:
            self._context, self._history = {}, []

    def _save(self):
        try:
            with open(self._storage, "w") as f:
                json.dump({"context": self._context, "history": self._history[-50:]}, f, indent=2)
        except Exception:
            pass
