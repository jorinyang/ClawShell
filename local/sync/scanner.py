from __future__ import annotations
"""ClawShell Edge — LocalEventScanner (v2.2.1)."""
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



class LocalEventScanner:
    """Scan local EventBus files for new events (mtime-based)."""

    def __init__(self, event_dirs: List[str] = None):
        self._event_dirs = event_dirs or ["~/.real/eventbus/events"]
        self._last_mtimes: Dict[str, float] = {}

    def scan(self) -> List[dict]:
        """Scan for new/modified event files."""
        events = []
        for d in self._event_dirs:
            expanded = os.path.expanduser(d)
            if not os.path.isdir(expanded):
                continue

            pattern = os.path.join(expanded, "*", "*.json")
            for filepath in glob.glob(pattern):
                try:
                    mtime = os.path.getmtime(filepath)
                    if self._last_mtimes.get(filepath, 0) >= mtime:
                        continue

                    with open(filepath) as f:
                        event = json.load(f)
                    events.append(event)
                    self._last_mtimes[filepath] = mtime
                except Exception:
                    pass

        return events


