from __future__ import annotations
"""ClawShell Edge — OfflineQueue (v2.2.1)."""
import os
import json
import time
import glob
import threading
import urllib.request
import urllib.error
import logging
from typing import Dict, List, Optional, Any

try:
    from shared.hooks.registry import trigger_hook
    from shared.hooks.manager import HookEvent
except ImportError:
    trigger_hook = None
    HookEvent = None

logger = logging.getLogger(__name__)



class OfflineQueue:
    """JSON file-backed queue for offline resilience."""

    MAX_SIZE = 500
    TRIM_SIZE = 300

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._lock = threading.RLock()
        self._queue: List[dict] = []
        self._load()

    def enqueue(self, item: dict):
        with self._lock:
            self._queue.append(item)
            if len(self._queue) > self.MAX_SIZE:
                self._queue = self._queue[-self.TRIM_SIZE:]
            self._save()

    def dequeue_all(self) -> List[dict]:
        with self._lock:
            items = list(self._queue)
            self._queue = []
            self._save()
            return items

    def size(self) -> int:
        return len(self._queue)

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            with open(self._filepath, "w") as f:
                json.dump(self._queue, f, default=str)
        except Exception:
            pass

    def _load(self):
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath) as f:
                    self._queue = json.load(f)
            except Exception:
                self._queue = []


