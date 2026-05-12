"""StrategySwitcher — 5-strategy state machine.

Design: based on DEEP StrategySwitcher.
Adapted to Main's threading model and L2 Self-Adaptation layer.

Strategies:
  DEFAULT       — Normal operation
  EMERGENCY     — Critical health, prioritize stability
  ECONOMY       — High resource pressure, reduce consumption
  AGGRESSIVE    — High capacity, maximize throughput
  CONSERVATIVE  — Post-emergency, gradual recovery

Placement: exoskeleton/layer2/ (Self-Adaptation layer).
"""
from __future__ import annotations
import time
from typing import Optional, List, Tuple
from shared.models import Strategy, HealthStatus


class StrategySwitcher:
    """5-strategy state machine with auto-evaluation.

    Manages strategy transitions based on system health and resource pressure.
    Only valid transitions (defined in TRANSITIONS) are allowed.

    Usage:
        sw = StrategySwitcher()
        new = sw.evaluate(health_score=0.2, resource_pressure=0.9)
        if new:
            sw.switch(new, "health critical + resource high")
    """

    # Valid transitions from each strategy
    TRANSITIONS = {
        Strategy.DEFAULT: [Strategy.EMERGENCY, Strategy.ECONOMY, Strategy.AGGRESSIVE],
        Strategy.EMERGENCY: [Strategy.DEFAULT, Strategy.CONSERVATIVE],
        Strategy.ECONOMY: [Strategy.DEFAULT],
        Strategy.AGGRESSIVE: [Strategy.DEFAULT, Strategy.EMERGENCY],
        Strategy.CONSERVATIVE: [Strategy.DEFAULT],
    }

    def __init__(self, initial: str = Strategy.DEFAULT):
        """Initialize strategy switcher.

        Args:
            initial: Starting strategy
        """
        self.current: str = initial
        self.history: List[Tuple[str, float, str]] = []  # (strategy, timestamp, reason)

    def evaluate(
        self,
        health_score: float,
        resource_pressure: float,
    ) -> Optional[str]:
        """Evaluate whether strategy should change.

        Args:
            health_score: 0.0 (critical) to 1.0 (optimal)
            resource_pressure: 0.0 (idle) to 1.0 (maxed out)

        Returns:
            New strategy if transition is needed, None otherwise.
        """
        new = self.current

        # Emergency: health critically low
        if health_score < 0.3:
            new = Strategy.EMERGENCY

        # Economy: resources under high pressure
        elif resource_pressure > 0.8:
            new = Strategy.ECONOMY

        # Aggressive: plenty of headroom
        elif health_score > 0.9 and resource_pressure < 0.2:
            new = Strategy.AGGRESSIVE

        # Recovery: health restored, pressure normal
        elif health_score > 0.8 and resource_pressure < 0.3:
            if self.current in (Strategy.EMERGENCY, Strategy.ECONOMY, Strategy.CONSERVATIVE):
                new = Strategy.DEFAULT

        # Validate transition
        if new != self.current and new in self.TRANSITIONS.get(self.current, []):
            return new
        return None

    def switch(self, new_strategy: str, reason: str = ""):
        """Execute a strategy switch.

        Args:
            new_strategy: Target strategy
            reason: Human-readable reason for the switch
        """
        old = self.current
        self.current = new_strategy
        self.history.append((new_strategy, time.time(), reason))

    def can_transition_to(self, target: str) -> bool:
        """Check if transitioning to target is valid."""
        return target in self.TRANSITIONS.get(self.current, [])

    def get_recent_history(self, limit: int = 10) -> List[dict]:
        """Get recent strategy transitions."""
        return [
            {"strategy": s, "timestamp": ts, "reason": r}
            for s, ts, r in self.history[-limit:]
        ]

    @property
    def stats(self) -> dict:
        """Get strategy statistics."""
        return {
            "current": self.current,
            "total_switches": len(self.history),
            "recent": self.get_recent_history(5),
        }
