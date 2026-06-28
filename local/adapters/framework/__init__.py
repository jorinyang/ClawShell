"""Framework adapters — inject ClawShell into AI agent frameworks.

ADAPTER_TYPE = "framework"
Targets: Hermes, Wukong, OpenClaw, CoPaw, QClaw, HiClaw, EasyClaw, WorkBuddy
"""

from local.adapters.framework.hermes import HermesAdapter
from local.adapters.framework.wukong import WukongAdapter
from local.adapters.framework.openclaw import OpenClawAdapter
from local.adapters.framework.action_reference import ActionReferenceInjector

__all__ = [
    "HermesAdapter",
    "WukongAdapter",
    "OpenClawAdapter",
    "ActionReferenceInjector",
]
