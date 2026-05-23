"""EventStore — Persistent event storage with replay."""
from __future__ import annotations
import os, json, time, threading
from typing import Dict, List, Any

class EventStore:
    def __init__(self, data_dir: str):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._store_file = os.path.join(self._data_dir, "event_store.json")
        self._events: List[dict] = []
        self._lock = threading.RLock()
        self._load()

    def append(self, event: dict) -> str:
        event_id = event.get("event_id", f"evt-{int(time.time()*1e6)}")
        event["event_id"] = event_id
        event["stored_at"] = time.time()
        with self._lock:
            self._events.append(event)
            self._flush()
        return event_id

    def query(self, source: str = "", event_type: str = "", since: float = 0,
              limit: int = 50) -> List[dict]:
        with self._lock:
            results = []
            for e in reversed(self._events):
                if source and e.get("source") != source: continue
                if event_type and e.get("event_type") != event_type: continue
                if since and e.get("timestamp", 0) < since: continue
                results.append(e)
                if len(results) >= limit: break
            return results

    def replay(self, since: float) -> List[dict]:
        return self.query(since=since, limit=1000)

    def stats(self) -> dict:
        with self._lock:
            types = {}
            for e in self._events:
                t = e.get("event_type", "unknown")
                types[t] = types.get(t, 0) + 1
            return {"total": len(self._events), "by_type": types}

    def _load(self):
        try:
            if os.path.exists(self._store_file):
                with open(self._store_file) as f:
                    self._events = json.load(f)
        except Exception:
            self._events = []

    def _flush(self):
        try:
            with open(self._store_file, "w") as f:
                json.dump(self._events[-10000:], f)
        except Exception:
            pass
