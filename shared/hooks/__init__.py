"""
ClawShell Hook Event System v2.1
Interceptors that run in priority order and can modify/block actions.
"""

from .manager import (
    HookEvent,
    HookPriority,
    HookContext,
    HookEntry,
    HookManager,
)
from .registry import (
    get_hook_manager,
    reset_hook_manager,
    trigger_hook,
)

__all__ = [
    "HookEvent",
    "HookPriority",
    "HookContext",
    "HookEntry",
    "HookManager",
    "get_hook_manager",
    "reset_hook_manager",
    "trigger_hook",
]
