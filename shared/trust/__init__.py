"""Behavioral Trust Scoring System for ClawShell v2.1.

Adapted from Ruflo's plugin-agent-federation trust-evaluator.
Provides per-node trust scoring, threat window tracking,
and trust level transitions with persistence.
"""

from .evaluator import (
    TrustLevel,
    NodeMetrics,
    TrustScore,
    TrustTransition,
    TrustEvaluator,
)

__all__ = [
    "TrustLevel",
    "NodeMetrics",
    "TrustScore",
    "TrustTransition",
    "TrustEvaluator",
]
