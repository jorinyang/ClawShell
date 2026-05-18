"""Robust Controller — disturbance-tolerant control with adaptive bounds.

Implements a robust control loop that maintains stability under perturbations
by applying saturation limits, anti-windup, and disturbance estimation.
"""

import time
import threading
from typing import Dict, Optional


class RobustController:
    """Disturbance-tolerant controller with adaptive bounds."""

    def __init__(self, kp: float = 0.5, ki: float = 0.1, kd: float = 0.05,
                 output_min: float = -1.0, output_max: float = 1.0,
                 disturbance_threshold: float = 0.3):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.disturbance_threshold = disturbance_threshold

        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._disturbance_estimate = 0.0
        self._lock = threading.RLock()
        self._history = []

    def compute(self, setpoint: float, measurement: float, dt: float = 1.0) -> float:
        """Compute robust control output."""
        with self._lock:
            error = setpoint - measurement

            # Disturbance estimation (difference between expected and actual)
            expected = self.kp * error
            disturbance = measurement - (setpoint - expected)
            self._disturbance_estimate = 0.8 * self._disturbance_estimate + 0.2 * disturbance

            # Apply disturbance compensation
            compensated_error = error + self._disturbance_estimate * 0.5

            # PID with anti-windup
            self._integral += compensated_error * dt
            # Anti-windup: clamp integral
            max_integral = (self.output_max - self.output_min) / max(self.ki, 0.001)
            self._integral = max(-max_integral, min(max_integral, self._integral))

            derivative = (error - self._prev_error) / max(dt, 0.001)

            output = self.kp * compensated_error + self.ki * self._integral + self.kd * derivative

            # Saturation limits
            saturated_output = max(self.output_min, min(self.output_max, output))

            # Back-calculation anti-windup
            if output != saturated_output:
                self._integral -= (output - saturated_output) * 0.5

            self._prev_error = error
            self._prev_output = saturated_output

            self._history.append({
                "timestamp": time.time(),
                "error": error,
                "output": saturated_output,
                "disturbance": self._disturbance_estimate,
            })
            if len(self._history) > 100:
                self._history = self._history[-50:]

            return saturated_output

    def reset(self):
        """Reset controller state."""
        with self._lock:
            self._integral = 0.0
            self._prev_error = 0.0
            self._disturbance_estimate = 0.0
            self._history.clear()

    def get_stats(self) -> dict:
        """Get controller statistics."""
        with self._lock:
            return {
                "kp": self.kp, "ki": self.ki, "kd": self.kd,
                "integral": self._integral,
                "disturbance_estimate": self._disturbance_estimate,
                "history_size": len(self._history),
                "last_output": self._prev_output,
            }

    def adapt_gains(self, performance_score: float):
        """Adapt PID gains based on performance feedback."""
        with self._lock:
            if performance_score < 0.3:
                # Poor performance: increase damping
                self.kp *= 0.9
                self.ki *= 0.8
            elif performance_score > 0.8:
                # Good performance: increase responsiveness
                self.kp = min(2.0, self.kp * 1.05)
                self.ki = min(1.0, self.ki * 1.02)
