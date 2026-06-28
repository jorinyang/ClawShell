"""Knowledge Puller — pull cloud insights and broadcasts for Edge."""

import json, os, threading, time
from pathlib import Path
from typing import Any, Dict, List, Optional

class KnowledgePuller:
    """Pulls cloud insights, broadcasts, and skills to local cache."""

    def __init__(self, cache_dir: str = ""):
        self._cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".clawshell" / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def pull_insights(self, insights: List[dict]) -> int:
        cache_file = self._cache_dir / "cloud_insights.json"
        with self._lock:
            existing = []
            if cache_file.exists():
                try:
                    existing = json.loads(cache_file.read_text())
                except (json.JSONDecodeError, OSError):
                    pass
            existing.extend(insights)
            cache_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
            return len(existing)

    def pull_broadcasts(self, broadcasts: List[dict]) -> int:
        cache_file = self._cache_dir / "cloud_broadcasts.json"
        with self._lock:
            existing = []
            if cache_file.exists():
                try:
                    existing = json.loads(cache_file.read_text())
                except (json.JSONDecodeError, OSError):
                    pass
            existing.extend(broadcasts)
            cache_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
            return len(existing)

    def get_insights(self, limit: int = 50) -> List[dict]:
        cache_file = self._cache_dir / "cloud_insights.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())[-limit:]
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def get_broadcasts(self, limit: int = 50) -> List[dict]:
        cache_file = self._cache_dir / "cloud_broadcasts.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())[-limit:]
            except (json.JSONDecodeError, OSError):
                pass
        return []
