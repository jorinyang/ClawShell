"""AdaptiveController — unified L2 control (Strategy+Feedback+Robust) v2.3.

Merges: StrategySwitcher + FeedbackControlLoop + RobustController into one class.
"""
from __future__ import annotations
import time, threading
from typing import Dict, List, Optional
from exoskeleton.layer2.strategy import StrategySwitcher
from exoskeleton.layer2.feedback_loop import FeedbackControlLoop

class AdaptiveController:
    """Unified L2 adaptive controller: strategy switching + PID feedback + robust gain adaptation."""

    STRATEGIES = ["emergency", "aggressive", "default", "conservative", "recovery"]

    def __init__(self, initial_strategy: str = "default", kp: float = 0.5, ki: float = 0.1,
                 disturbance_bound: float = 0.3, safety_margin: float = 0.15):
        self.strategy = StrategySwitcher(initial=initial_strategy)
        self.feedback = FeedbackControlLoop(name="system_health", kp=kp, ki=ki)
        self._disturbance_bound = disturbance_bound
        self._safety_margin = safety_margin
        self._last_setpoint = 0.0
        self._lock = threading.RLock()

    # ── Unified Control API ──
    def evaluate_and_control(self, health_score: float, resource_pressure: float = 0.0,
                             dt: float = 1.0, auto_apply: bool = True) -> dict:
        """Full control loop: evaluate strategy → compute PID → apply robust correction."""
        # Strategy evaluation
        result = {"health_score": health_score}
        try:
            new_st = self.strategy.evaluate(health_score=health_score,
                                            resource_pressure=resource_pressure,
                                            auto_apply=auto_apply)
            result["strategy"] = self.strategy.current
            if new_st: result["strategy_changed"] = new_st
        except Exception as e:
            result["strategy_error"] = str(e)

        # Feedback control
        try:
            self.feedback.set_target(1.0)
            signal = self.feedback.update(health_score)
            result["feedback_signal"] = round(signal, 4)
            result["feedback_stable"] = self.feedback.is_stable
        except Exception as e:
            result["feedback_error"] = str(e)

        # Robust correction (perturbation-aware)
        deviation = abs(1.0 - health_score)
        safe_signal = max(self._safety_margin, min(max(0, signal), 1 - self._safety_margin))
        if deviation > self._disturbance_bound:
            safe_signal *= 1.2  # amplify correction under high disturbance
        result["robust_signal"] = round(safe_signal, 4)
        result["disturbance_detected"] = deviation > self._disturbance_bound

        self._last_setpoint = health_score
        return result

    def adapt_gains(self, performance_score: float):
        """Adapt PID gains based on performance feedback (robust controller logic)."""
        if performance_score > 0.8:
            self.feedback.kp = min(2.0, self.feedback.kp * 1.05)
        else:
            self.feedback.kp = max(0.1, self.feedback.kp * 0.95)
            self.feedback.ki = max(0.01, self.feedback.ki * 0.9)

    def reset(self):
        self.feedback.reset()
        self._last_setpoint = 0.0

    def get_state(self) -> dict:
        return {
            "strategy": self.strategy.current,
            "feedback_state": self.feedback.state(),
            "disturbance_bound": self._disturbance_bound,
            "safety_margin": self._safety_margin,
        }
