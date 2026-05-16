"""EvolutionTracker — milestone tracking and metric trend analysis.

File-based JSON storage for evolution milestones.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvolutionTracker:
    """Tracks evolution milestones with metric trend analysis."""

    def __init__(self, storage_path: str = None):
        self._storage_path = Path(storage_path or os.path.expanduser("~/.clawshell/genome/evolution"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._milestones_path = self._storage_path / "milestones.json"
        self._milestones: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if self._milestones_path.exists():
            try:
                with open(self._milestones_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save(self):
        with open(self._milestones_path, "w", encoding="utf-8") as f:
            json.dump(self._milestones, f, indent=2, ensure_ascii=False)

    def track_milestone(self, title: str, description: str = "", metrics: Dict[str, float] = None) -> Dict:
        """Record an evolution milestone.

        Args:
            title: Milestone title
            description: Detailed description
            metrics: Optional metrics dict (e.g. {"score": 0.9, "latency": 120})

        Returns:
            The recorded milestone entry
        """
        milestone = {
            "title": title,
            "description": description,
            "metrics": metrics or {},
            "timestamp": time.time(),
        }
        self._milestones.append(milestone)
        self._save()
        return milestone

    def get_timeline(self, limit: int = 20) -> List[Dict]:
        """Get chronological milestone history.

        Args:
            limit: Maximum number of milestones to return

        Returns:
            List of recent milestones in reverse chronological order
        """
        return list(reversed(self._milestones[-limit:]))

    def get_metrics_trend(self, metric_name: str) -> List[Dict]:
        """Track a specific metric over time.

        Args:
            metric_name: Name of the metric to track

        Returns:
            List of {timestamp, value} entries for the metric
        """
        trend = []
        for m in self._milestones:
            if metric_name in m.get("metrics", {}):
                trend.append({
                    "timestamp": m.get("timestamp"),
                    "value": m["metrics"][metric_name],
                    "title": m.get("title", ""),
                })
        return trend

    def detect_regression(self, metric_name: str) -> Optional[Dict]:
        """Alert if a metric has degraded.

        Args:
            metric_name: Name of the metric to check

        Returns:
            Dict with regression details if detected, None otherwise
        """
        trend = self.get_metrics_trend(metric_name)
        if len(trend) < 2:
            return None

        prev = trend[-2]["value"]
        curr = trend[-1]["value"]

        # Regression: current value is worse than previous
        # For most metrics, lower is worse, but for "score"-like metrics
        # we check if current < previous
        if curr < prev:
            return {
                "metric": metric_name,
                "previous": prev,
                "current": curr,
                "change": curr - prev,
                "change_pct": ((curr - prev) / prev * 100) if prev != 0 else 0,
                "detected_at": trend[-1]["timestamp"],
                "title": trend[-1]["title"],
            }
        return None
