"""FeedbackControlLoop — PID controller for system health.

Design: based on DEEP FeedbackControlLoop.
Adapted to Main's threading model — pure computation class, no I/O.

The PID (Proportional-Integral) controller monitors system health
and outputs a control signal [-1.0, 1.0] to guide strategy decisions.

Placement: exoskeleton/layer2/ (Self-Adaptation layer).
"""
from __future__ import annotations
from typing import Optional


class FeedbackControlLoop:
    """PID feedback control loop for system health regulation.

    Monitors health_score deviation from target and outputs
    a corrective control signal. Marks the system as "stable"
    when deviation stays within tolerance for 3+ consecutive cycles.

    PID formula:
        signal = kp * deviation + ki * deviation * min(iterations, 10)
        clamped to [-1.0, 1.0]

    Usage:
        loop = FeedbackControlLoop("system_health", kp=0.5, ki=0.1)
        loop.set_target(1.0)
        signal = loop.update(actual_health_score)
        if loop.is_stable:
            print("System stable")
    """

    def __init__(
        self,
        name: str = "default",
        kp: float = 0.5,
        ki: float = 0.1,
        tolerance: float = 0.1,
    ):
        """Initialize PID controller.

        Args:
            name: Identifier for this control loop
            kp: Proportional gain coefficient
            ki: Integral gain coefficient
            tolerance: Acceptable deviation range for stability
        """
        self.name = name
        self.kp = kp
        self.ki = ki
        self.tolerance = tolerance

        # State
        self.expected: float = 0.0   # Target value
        self.actual: float = 0.0     # Last observed value
        self.deviation: float = 0.0  # expected - actual
        self.iteration_count: int = 0
        self.stable_count: int = 0

    def set_target(self, target: float):
        """Set the target (expected) value."""
        self.expected = target

    def update(self, actual: float) -> float:
        """Update the controller with latest actual value.

        Args:
            actual: Current observed value

        Returns:
            Control signal in [-1.0, 1.0]
        """
        self.actual = actual
        self.deviation = self.expected - actual
        self.iteration_count += 1

        # Stability tracking
        if abs(self.deviation) <= self.tolerance:
            self.stable_count += 1
        else:
            self.stable_count = 0

        return self._compute_signal()

    def _compute_signal(self) -> float:
        """Compute PI control signal with anti-windup."""
        # Proportional term
        p_term = self.kp * self.deviation

        # Integral term with anti-windup (cap at 10 iterations)
        i_term = self.ki * self.deviation * min(self.iteration_count, 10)

        signal = p_term + i_term
        return max(-1.0, min(1.0, signal))

    def reset(self):
        """Reset controller state."""
        self.actual = 0.0
        self.deviation = 0.0
        self.iteration_count = 0
        self.stable_count = 0

    @property
    def is_stable(self) -> bool:
        """True if system has been stable for 3+ consecutive cycles."""
        return self.stable_count >= 3

    @property
    def state(self) -> dict:
        """Get controller state as a dict."""
        return {
            "name": self.name,
            "expected": self.expected,
            "actual": self.actual,
            "deviation": self.deviation,
            "signal": self._compute_signal(),
            "iterations": self.iteration_count,
            "stable": self.is_stable,
        }
