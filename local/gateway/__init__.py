"""Edge Gateway — network discovery, device monitoring, and self-healing.

v1.8.1: Ported from ClawShell-MacOS Edge Gateway.
"""

from local.gateway.network_discovery import NetworkDiscovery, DiscoveredDevice
from local.gateway.device_monitor import DeviceMonitor, DeviceMetrics, HealthStatus
from local.gateway.knowledge_puller import KnowledgePuller
from local.gateway.self_healing import EdgeSelfHealing, HealingAction, HealingState

__all__ = [
    "NetworkDiscovery", "DiscoveredDevice",
    "DeviceMonitor", "DeviceMetrics", "HealthStatus",
    "KnowledgePuller",
    "EdgeSelfHealing", "HealingAction", "HealingState",
]
