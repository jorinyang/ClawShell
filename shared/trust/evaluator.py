"""Behavioral Trust Scoring System.

Computes trust scores from node metrics using weighted components:
    trust_score = 0.4*success_rate + 0.2*uptime_ratio
                + 0.2*(1 - threat_penalty) + 0.2*data_integrity

Tracks per-node metrics, threat windows, and trust transitions.
Thread-safe, JSON-serializable, with file persistence.
"""

from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Enums ───────────────────────────────────────────────────────────────

class TrustLevel(Enum):
    """Trust levels for federation nodes."""
    UNTRUSTED = 0    # score < 0.2
    LOW = 1          # 0.2 <= score < 0.4
    STANDARD = 2     # 0.4 <= score < 0.6
    HIGH = 3         # 0.6 <= score < 0.8
    PRIVILEGED = 4   # score >= 0.8

    @staticmethod
    def from_score(score: float) -> TrustLevel:
        """Map a 0-1 score to the corresponding trust level."""
        if score >= 0.8:
            return TrustLevel.PRIVILEGED
        elif score >= 0.6:
            return TrustLevel.HIGH
        elif score >= 0.4:
            return TrustLevel.STANDARD
        elif score >= 0.2:
            return TrustLevel.LOW
        else:
            return TrustLevel.UNTRUSTED


# ── Data Classes ────────────────────────────────────────────────────────

@dataclass
class NodeMetrics:
    """Raw metrics collected from a federation node."""
    messages_sent: int = 0
    messages_received: int = 0
    hmac_failures: int = 0
    threat_detections: int = 0
    uptime_seconds: float = 0.0
    total_seconds: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0

    @property
    def messages_total(self) -> int:
        return self.messages_sent + self.messages_received

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> NodeMetrics:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TrustScore:
    """Computed trust result for a node."""
    score: float
    level: TrustLevel
    components: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level.value,
            "level_name": self.level.name,
            "components": self.components,
        }


@dataclass
class TrustTransition:
    """Record of a trust level change."""
    node_id: str
    previous_level: TrustLevel
    new_level: TrustLevel
    score: float
    reason: str
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "previous_level": self.previous_level.value,
            "new_level": self.new_level.value,
            "score": self.score,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> TrustTransition:
        return cls(
            node_id=d["node_id"],
            previous_level=TrustLevel(d["previous_level"]),
            new_level=TrustLevel(d["new_level"]),
            score=d["score"],
            reason=d["reason"],
            timestamp=d["timestamp"],
        )


# ── Immediate Downgrade Reasons ────────────────────────────────────────

ImmediateDowngradeReason = str  # 'hmac-verification-failure', 'session-hijack-attempt', etc.


# ── Trust Evaluator ────────────────────────────────────────────────────

class TrustEvaluator:
    """Behavioral trust scoring engine.

    Tracks per-node metrics and threat windows, computes trust scores,
    and manages trust level transitions. Thread-safe.
    """

    # Threat window configuration
    THREAT_WINDOW_SECONDS: float = 3600.0   # 1-hour rolling window
    THREAT_WINDOW_THRESHOLD: int = 2        # 2+ threats triggers penalty

    # Weights
    W_SUCCESS: float = 0.4
    W_UPTIME: float = 0.2
    W_THREAT: float = 0.2
    W_INTEGRITY: float = 0.2

    def __init__(self, persistence_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._persistence_path = persistence_path

        # Per-node state
        self._node_levels: Dict[str, TrustLevel] = {}
        self._node_metrics: Dict[str, NodeMetrics] = {}
        self._threat_windows: Dict[str, List[float]] = {}  # node_id -> [timestamps]
        self._transitions: List[TrustTransition] = []

        # Load persisted state if available
        if persistence_path:
            self._load(persistence_path)

    # ── Public API ──────────────────────────────────────────────────────

    def record_metrics(self, node_id: str, metrics: NodeMetrics) -> TrustScore:
        """Record metrics and compute the trust score for a node."""
        with self._lock:
            self._node_metrics[node_id] = metrics
            return self._compute_score(node_id, metrics)

    def evaluate(self, node_id: str) -> TrustScore:
        """Evaluate trust for a node using its current metrics."""
        with self._lock:
            metrics = self._node_metrics.get(node_id, NodeMetrics())
            return self._compute_score(node_id, metrics)

    def record_threat_detection(self, node_id: str, timestamp: Optional[float] = None) -> bool:
        """Record a threat detection event. Returns True if window threshold exceeded."""
        ts = timestamp or time.time()
        with self._lock:
            window = self._threat_windows.setdefault(node_id, [])
            window.append(ts)
            # Prune expired entries
            cutoff = ts - self.THREAT_WINDOW_SECONDS
            window[:] = [t for t in window if t > cutoff]
            return len(window) >= self.THREAT_WINDOW_THRESHOLD

    def immediate_downgrade(
        self,
        node_id: str,
        reason: ImmediateDowngradeReason = "security-event",
    ) -> TrustTransition:
        """Immediately set a node to UNTRUSTED on a security event."""
        with self._lock:
            current = self._node_levels.get(node_id, TrustLevel.STANDARD)
            self._node_levels[node_id] = TrustLevel.UNTRUSTED

            transition = TrustTransition(
                node_id=node_id,
                previous_level=current,
                new_level=TrustLevel.UNTRUSTED,
                score=0.0,
                reason=f"Immediate downgrade: {reason}",
                timestamp=time.time(),
            )
            self._transitions.append(transition)
            return transition

    def get_level(self, node_id: str) -> TrustLevel:
        """Get the current trust level for a node."""
        with self._lock:
            return self._node_levels.get(node_id, TrustLevel.STANDARD)

    def get_transitions(self, node_id: Optional[str] = None) -> List[TrustTransition]:
        """Get trust transition history, optionally filtered by node."""
        with self._lock:
            if node_id is None:
                return list(self._transitions)
            return [t for t in self._transitions if t.node_id == node_id]

    def get_threat_count(self, node_id: str, now: Optional[float] = None) -> int:
        """Get the number of threat detections within the current window."""
        ts = now or time.time()
        with self._lock:
            window = self._threat_windows.get(node_id, [])
            cutoff = ts - self.THREAT_WINDOW_SECONDS
            return sum(1 for t in window if t > cutoff)

    # ── Persistence ─────────────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> None:
        """Persist trust state to a JSON file."""
        target = path or self._persistence_path
        if not target:
            raise ValueError("No persistence path configured")

        with self._lock:
            state = {
                "node_levels": {nid: lvl.value for nid, lvl in self._node_levels.items()},
                "node_metrics": {nid: m.to_dict() for nid, m in self._node_metrics.items()},
                "threat_windows": dict(self._threat_windows),
                "transitions": [t.to_dict() for t in self._transitions],
            }

        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(json.dumps(state, indent=2))

    def load(self, path: Optional[str] = None) -> None:
        """Load trust state from a JSON file."""
        self._load(path or self._persistence_path)

    # ── Internals ───────────────────────────────────────────────────────

    def _load(self, path: Optional[str]) -> None:
        if not path or not Path(path).exists():
            return

        text = Path(path).read_text().strip()
        if not text:
            return

        with self._lock:
            state = json.loads(text)

            self._node_levels = {
                nid: TrustLevel(lvl) for nid, lvl in state.get("node_levels", {}).items()
            }
            self._node_metrics = {
                nid: NodeMetrics.from_dict(m) for nid, m in state.get("node_metrics", {}).items()
            }
            self._threat_windows = {
                nid: list(w) for nid, w in state.get("threat_windows", {}).items()
            }
            self._transitions = [
                TrustTransition.from_dict(t) for t in state.get("transitions", [])
            ]

    def _compute_score(self, node_id: str, metrics: NodeMetrics) -> TrustScore:
        """Compute trust score and handle transitions. Caller must hold lock."""
        total = metrics.messages_total
        hmac_f = metrics.hmac_failures

        # Success rate
        success_rate = (total - hmac_f) / total if total > 0 else 0.0

        # Uptime ratio (clamped)
        if metrics.total_seconds > 0:
            uptime_ratio = max(0.0, min(1.0, metrics.uptime_seconds / metrics.total_seconds))
        else:
            uptime_ratio = 0.0

        # Threat penalty (uses rolling window, not cumulative count)
        threat_count = self._get_threat_window_count(node_id)
        threat_penalty = self._compute_threat_penalty(threat_count, total)

        # Data integrity
        data_integrity = 1.0 - (hmac_f / total) if total > 0 else 1.0

        # Composite score
        raw_score = (
            self.W_SUCCESS * success_rate
            + self.W_UPTIME * uptime_ratio
            + self.W_THREAT * (1.0 - threat_penalty)
            + self.W_INTEGRITY * data_integrity
        )
        score = max(0.0, min(1.0, raw_score))

        components = {
            "success_rate": success_rate,
            "uptime_ratio": uptime_ratio,
            "threat_penalty": threat_penalty,
            "data_integrity": data_integrity,
        }

        new_level = TrustLevel.from_score(score)
        previous_level = self._node_levels.get(node_id, TrustLevel.STANDARD)

        # Record transition if level changed
        if new_level != previous_level:
            direction = "upgrade" if new_level.value > previous_level.value else "downgrade"
            transition = TrustTransition(
                node_id=node_id,
                previous_level=previous_level,
                new_level=new_level,
                score=score,
                reason=f"Score {score:.3f} → {direction} to {new_level.name}",
                timestamp=time.time(),
            )
            self._transitions.append(transition)
            self._node_levels[node_id] = new_level
        elif node_id not in self._node_levels:
            self._node_levels[node_id] = new_level

        return TrustScore(score=score, level=self._node_levels[node_id], components=components)

    def _get_threat_window_count(self, node_id: str) -> int:
        """Count threats in the rolling window. Caller must hold lock."""
        now = time.time()
        window = self._threat_windows.get(node_id, [])
        cutoff = now - self.THREAT_WINDOW_SECONDS
        return sum(1 for t in window if t > cutoff)

    @staticmethod
    def _compute_threat_penalty(threat_count: int, total_messages: int) -> float:
        """Compute threat penalty.  Scaled by 10x to amplify impact."""
        if total_messages == 0:
            return 0.0
        ratio = threat_count / total_messages
        return min(1.0, ratio * 10)
