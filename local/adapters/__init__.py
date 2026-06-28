"""Local Adapters — Unified adapter layer for ClawShell injection.

Three adapter types (defined in shared.types.AdapterType):
  framework/ — AI agent frameworks (Hermes, Wukong, OpenClaw, ...)
  bridge/    — External tool bridges (N8N, Docker, ComfyUI, MemOS, ...)
  ide/       — IDE CLI adapters (Claude Code, Codex, Copilot, ...)

All adapters implement the unified BaseAdapter interface:
  detect() → bool, inject(config) → bool, verify() → dict, rollback() → bool
"""

from local.adapters.base import BaseAdapter
from local.adapters.manager import AdapterManager

# Framework adapters
from local.adapters.framework.hermes import HermesAdapter
from local.adapters.framework.wukong import WukongAdapter
from local.adapters.framework.openclaw import OpenClawAdapter
from local.adapters.framework.action_reference import ActionReferenceInjector

__all__ = [
    "BaseAdapter",
    "AdapterManager",
    "HermesAdapter",
    "WukongAdapter",
    "OpenClawAdapter",
    "ActionReferenceInjector",
]
