"""TrustEvaluator — Dynamic trust scoring for multi-agent collaboration (L4)."""
from __future__ import annotations
import json, time, threading, os
from typing import Dict, List

class TrustEvaluator:
    """4-dimension weighted trust scoring with 5 trust levels."""
    TRUST_LEVELS = ["untrusted", "low", "neutral", "high", "trusted"]

    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._scores: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._load()

    def evaluate(self, node_id: str, metrics: dict) -> dict:
        score = self._compute_score(metrics)
        level = self._score_to_level(score)
        with self._lock:
            self._scores[node_id] = {"score": score, "level": level,
                                       "updated": time.time(), "metrics": metrics}
            self._save()
        return {"node_id": node_id, "score": score, "level": level}

    def get_trust(self, node_id: str) -> dict:
        return self._scores.get(node_id, {"score": 0.5, "level": "neutral"})

    def demote(self, node_id: str, reason: str = "") -> dict:
        with self._lock:
            current = self._scores.get(node_id, {"score": 0.5})
            current["score"] = max(0.0, current["score"] - 0.3)
            current["level"] = self._score_to_level(current["score"])
            current["demoted_at"] = time.time()
            current["demote_reason"] = reason
            self._scores[node_id] = current
            self._save()
        return current

    def _compute_score(self, metrics: dict) -> float:
        weights = {"uptime": 0.25, "success_rate": 0.35, "response_time": 0.20, "error_rate": 0.20}
        score = 0.5
        if "success_rate" in metrics: score += metrics["success_rate"] * weights["success_rate"]
        if "response_time" in metrics: score += max(0, 1 - metrics["response_time"]/10) * weights["response_time"]
        return round(min(1.0, max(0.0, score)), 3)

    def _score_to_level(self, score: float) -> str:
        if score >= 0.9: return "trusted"
        if score >= 0.7: return "high"
        if score >= 0.5: return "neutral"
        if score >= 0.3: return "low"
        return "untrusted"

    def _load(self):
        try:
            with open(os.path.join(self._data_dir, "trust.json")) as f:
                self._scores = json.load(f)
        except Exception: pass

    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "trust.json"), "w") as f:
                json.dump(self._scores, f, indent=2)
        except Exception: pass
