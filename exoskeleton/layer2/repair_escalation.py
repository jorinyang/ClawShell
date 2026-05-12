"""3-Layer Repair Upgrade — Escalation-based self-repair.

Design: Based on DEEP 3-layer repair escalation.
Adapted to Main's L2 SelfRepairEngine.

Layers:
  SELF_HEALING (秒级)  — Quick fixes: clear_cache, reduce_load, clean_temp
  AUTO_REPAIR (分钟级)  — Automated repair: restart_gateway, restart_daemons, rotate_logs
  MANUAL               — Human intervention required

Escalation: 3 self-healing failures → auto-repair, 2 auto-repair failures → manual
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any, Callable
from shared.models import RepairLayer, HealthStatus


# Default repair actions per layer
DEFAULT_ACTIONS: Dict[str, Dict[str, str]] = {
    RepairLayer.SELF_HEALING: {
        "memory_high": "clear_cache",
        "cpu_high": "reduce_load",
        "disk_full": "clean_temp",
    },
    RepairLayer.AUTO_REPAIR: {
        "memory_high": "restart_daemons",
        "cpu_high": "restart_gateway",
        "disk_full": "rotate_logs",
        "network_down": "restart_network",
    },
}


class RepairEscalation:
    """3-layer repair escalation manager.
    
    Tracks repair attempts per component and escalates
    when a layer fails too many times.
    """

    MAX_SELF_HEALING = 3   # Attempts before escalating to auto-repair
    MAX_AUTO_REPAIR = 2    # Attempts before escalating to manual

    def __init__(self):
        self._healing_history: Dict[str, int] = {}   # component → self_healing attempts
        self._repair_history: Dict[str, int] = {}    # component → auto_repair attempts
        self._action_log: List[Dict[str, Any]] = []

    def should_escalate(self, component: str, current_layer: str) -> tuple:
        """Check if current repair layer should escalate.
        
        Args:
            component: Component name (e.g., "memory", "cpu", "disk")
            current_layer: Current repair layer
            
        Returns:
            (should_escalate: bool, next_layer: str, reason: str)
        """
        if current_layer == RepairLayer.SELF_HEALING:
            attempts = self._healing_history.get(component, 0) + 1
            self._healing_history[component] = attempts
            if attempts >= self.MAX_SELF_HEALING:
                return True, RepairLayer.AUTO_REPAIR, f"Self-healing failed {attempts} times"

        elif current_layer == RepairLayer.AUTO_REPAIR:
            attempts = self._repair_history.get(component, 0) + 1
            self._repair_history[component] = attempts
            if attempts >= self.MAX_AUTO_REPAIR:
                return True, RepairLayer.MANUAL, f"Auto-repair failed {attempts} times"

        return False, current_layer, ""

    def get_recommended_action(self, component: str, layer: str) -> Optional[str]:
        """Get the recommended repair action for a component at a given layer."""
        actions = DEFAULT_ACTIONS.get(layer, {})
        return actions.get(component)

    def record_action(
        self,
        component: str,
        layer: str,
        action: str,
        success: bool,
    ):
        """Record a repair action and its outcome."""
        self._action_log.append({
            "component": component,
            "layer": layer,
            "action": action,
            "success": success,
        })
        if success:
            # Reset counters on success
            self._healing_history[component] = 0
            self._repair_history[component] = 0

    def reset_component(self, component: str):
        """Reset all counters for a component (e.g., after manual fix)."""
        self._healing_history.pop(component, None)
        self._repair_history.pop(component, None)

    @property
    def stats(self) -> dict:
        """Escalation statistics."""
        return {
            "healing_attempts": dict(self._healing_history),
            "repair_attempts": dict(self._repair_history),
            "total_actions": len(self._action_log),
        }
