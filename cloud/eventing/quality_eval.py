"""QualityEvaluator — Event quality scoring."""
from __future__ import annotations
import time
from typing import Dict, List

class QualityEvaluator:
    def __init__(self):
        self._scores: List[dict] = []
        self._threshold = 0.5

    def score(self, event: dict) -> float:
        score = 0.5
        if event.get("timestamp") and event["timestamp"] > time.time() - 3600:
            score += 0.2
        if event.get("payload") and isinstance(event.get("payload"), dict):
            score += 0.1
        if event.get("event_id") and event.get("event_type"):
            score += 0.2
        return min(score, 1.0)

    def evaluate_batch(self, events: List[dict]) -> List[dict]:
        results = []
        for e in events:
            s = self.score(e)
            results.append({**e, "quality_score": s, "passes": s >= self._threshold})
            self._scores.append({"event_id": e.get("event_id"), "score": s})
        return results

    def stats(self) -> dict:
        if not self._scores:
            return {"avg_quality": 0, "total": 0}
        avg = sum(s["score"] for s in self._scores) / len(self._scores)
        return {"avg_quality": round(avg, 3), "total": len(self._scores)}
