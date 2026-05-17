"""Global Hook Registry — singleton HookManager accessible everywhere.

Usage:
    from shared.hooks.registry import get_hook_manager, trigger_hook

    # Get the singleton manager
    mgr = get_hook_manager()

    # Register a hook
    mgr.register(HookEvent.PRE_TASK, my_handler, HookPriority.HIGH, "my_hook")

    # Convenience: trigger a hook in one call
    ctx = trigger_hook(HookEvent.PRE_TASK, {"task_id": "abc"}, source="taskboard")
"""

from __future__ import annotations

import threading
from typing import Optional

from .manager import HookContext, HookEvent, HookManager

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[HookManager] = None
_lock = threading.Lock()


def get_hook_manager() -> HookManager:
    """Return the global singleton ``HookManager`` (thread-safe, lazy-init)."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = HookManager()
    return _instance


def reset_hook_manager() -> None:
    """Reset the singleton (useful in tests)."""
    global _instance
    with _lock:
        _instance = None


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def trigger_hook(
    event: HookEvent,
    data: dict,
    source: str = "",
) -> HookContext:
    """Trigger a hook on the global manager. Returns the ``HookContext``.

    This is a thin wrapper around ``get_hook_manager().trigger(...)``.
    """
    return get_hook_manager().trigger(event, data, source)
