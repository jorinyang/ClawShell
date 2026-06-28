"""Unified Adapter Manager — manages three types of adapters.

v1.8.1: Ported from ClawShell-MacOS adapter manager.
v3.0.0: Enhanced with detect_all/inject_all/verify_all/list_by_type for
        framework/bridge/ide adapter categorization.
"""

import threading
from typing import Any, Dict, List, Optional


class AdapterManager:
    """Manages all adapters: framework, bridge, and IDE types."""

    def __init__(self):
        self._lock = threading.RLock()
        self._adapters: Dict[str, Any] = {}

    def register(self, name: str, adapter: Any) -> None:
        with self._lock:
            self._adapters[name] = adapter

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._adapters.pop(name, None) is not None

    def get(self, name: str) -> Optional[Any]:
        with self._lock:
            return self._adapters.get(name)

    def list_adapters(self) -> List[str]:
        with self._lock:
            return list(self._adapters.keys())

    def list_by_type(self, adapter_type: str) -> List[Any]:
        """List adapters filtered by ADAPTER_TYPE (framework/bridge/ide)."""
        with self._lock:
            return [a for a in self._adapters.values()
                    if getattr(a, 'ADAPTER_TYPE', 'framework') == adapter_type]

    # ── Bulk Operations ──────────────────────────

    def detect_all(self) -> Dict[str, bool]:
        """Run detect() on every registered adapter."""
        results = {}
        with self._lock:
            for name, adapter in self._adapters.items():
                try:
                    results[name] = adapter.detect()
                except Exception:
                    results[name] = False
        return results

    def inject_all(self, config: Optional[dict] = None) -> Dict[str, bool]:
        """Run inject() on every adapter that detected its target."""
        cfg = config or {}
        results = {}
        with self._lock:
            for name, adapter in self._adapters.items():
                try:
                    if adapter.detect():
                        results[name] = adapter.inject(cfg)
                    else:
                        results[name] = False
                except Exception:
                    results[name] = False
        return results

    def verify_all(self) -> Dict[str, dict]:
        """Run verify() on every registered adapter."""
        results = {}
        with self._lock:
            for name, adapter in self._adapters.items():
                try:
                    results[name] = adapter.verify()
                except Exception as e:
                    results[name] = {"error": str(e)}
        return results

    def rollback_all(self) -> Dict[str, bool]:
        """Run rollback() on every registered adapter."""
        results = {}
        with self._lock:
            for name, adapter in self._adapters.items():
                try:
                    results[name] = adapter.rollback()
                except Exception:
                    results[name] = False
        return results

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
            by_type = {"framework": 0, "bridge": 0, "ide": 0, "unknown": 0}
            for a in self._adapters.values():
                t = getattr(a, 'ADAPTER_TYPE', 'unknown')
                by_type[t] = by_type.get(t, 0) + 1
            return {
                "adapter_count": len(self._adapters),
                "by_type": by_type,
                "names": list(self._adapters.keys()),
            }
