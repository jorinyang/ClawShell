"""Edge Adapters — framework-specific integration adapters.

v1.8.1: Added unified AdapterManager.
"""

from edge.adapters.base import BaseAdapter
from edge.adapters.wukong_adapter import WukongAdapter
from edge.adapters.hermes_adapter import HermesAdapter
from edge.adapters.action_reference import ActionReferenceInjector
from edge.adapters.manager import AdapterManager

__all__ = [
    "BaseAdapter",
    "WukongAdapter",
    "HermesAdapter",
    "ActionReferenceInjector",
    "AdapterManager",
]
