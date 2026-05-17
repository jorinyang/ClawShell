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

__all__ = [
    "HookEvent",
    "HookPriority",
    "HookContext",
    "HookEntry",
    "HookManager",
]
