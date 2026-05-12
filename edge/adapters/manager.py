"""Unified Adapter Manager — manages multiple framework adapters.

v1.8.1: Ported from ClawShell-MacOS adapter manager.
Provides unified registration, lifecycle, and action reference injection.
"""

import threading
from typing import Any, Dict, List, Optional

class AdapterManager:
    """Manages multiple platform adapters (Hermes, OpenClaw, Wukong, etc.)."""

    def __init__(self):
        self._lock = threading.RLock()
        self._adapters: Dict[str, Any] = {}
        self._status: Dict[str, str] = {}

    def register(self, name: str, adapter: Any) -> None:
        with self._lock:
            self._adapters[name] = adapter
            self._status[name] = "registered"

    def get(self, name: str) -> Optional[Any]:
        with self._lock:
            return self._adapters.get(name)

    def list_adapters(self) -> List[str]:
        with self._lock:
            return list(self._adapters.keys())

    def inject_action_reference(self, insights: List[dict],
                                broadcasts: List[dict]) -> Dict[str, bool]:
        results = {}
        with self._lock:
            for name, adapter in self._adapters.items():
                try:
                    if hasattr(adapter, 'inject_action_reference'):
                        adapter.inject_action_reference(insights, broadcasts)
                        results[name] = True
                except Exception:
                    results[name] = False
        return results

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "adapter_count": len(self._adapters),
                "status": dict(self._status),
            }
