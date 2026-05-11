"""IDE Orchestrator — Multi-IDE task matching and parallel execution.

Harness Engineering: Match coding tasks to the optimal Agent CLI IDE
based on task type, language, and IDE capabilities (ecological niche matching).
Execute multiple IDEs in parallel, collect results, and aggregate.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import uuid

from edge.ide_bridge.base import BaseIDEBridge, IDETask, IDEResult


# IDE Capability Matrix (ecological niches)
IDE_CAPABILITY_MATRIX = {
    "codex": {
        "primary": ["code", "debug", "refactor"],
        "languages": ["*"],
        "strength": "full_stack",
    },
    "claude_code": {
        "primary": ["architect", "code", "review", "refactor"],
        "languages": ["*"],
        "strength": "architecture",
    },
    "kimi_code": {
        "primary": ["code", "debug"],
        "languages": ["python", "javascript", "typescript"],
        "strength": "rapid_prototyping",
    },
    "deepseek_tui": {
        "primary": ["code", "review", "explain"],
        "languages": ["*"],
        "strength": "code_generation",
    },
    "copilot": {
        "primary": ["code", "suggest", "explain"],
        "languages": ["*"],
        "strength": "inline_suggestions",
    },
}


class IDEOrchestrator:
    """Multi-IDE task orchestrator."""

    def __init__(self):
        self._bridges: Dict[str, BaseIDEBridge] = {}
        self._results: List[IDEResult] = []
        self._max_workers = 3

    def register_bridge(self, bridge: BaseIDEBridge):
        """Register an IDE bridge."""
        self._bridges[bridge.get_name()] = bridge

    def detect_available_ides(self) -> List[str]:
        """Detect which IDEs are installed."""
        available = []
        for name, bridge in self._bridges.items():
            if bridge.detect():
                available.append(name)
        return available

    def get_available_bridges(self) -> Dict[str, BaseIDEBridge]:
        """Get all detected and registered bridges."""
        available = {}
        for name, bridge in self._bridges.items():
            if bridge.detect():
                available[name] = bridge
        return available

    def match_ide(self, task: IDETask) -> List[str]:
        """Match a task to the best IDE(s) using ecological niche matching."""
        available = self.get_available_bridges()
        scores = []

        for name, bridge in available.items():
            caps = bridge.get_capabilities()
            profile = IDE_CAPABILITY_MATRIX.get(name, {})

            score = 0
            # Task type match
            if task.task_type in caps:
                score += 3
            if task.task_type in profile.get("primary", []):
                score += 5

            # Language match
            if task.language:
                plangs = profile.get("languages", ["*"])
                if "*" in plangs or task.language in plangs:
                    score += 2

            # Priority bonus
            score += task.priority * 0.1

            scores.append((name, score))

        # Sort by score DESC
        scores.sort(key=lambda x: x[1], reverse=True)
        return [name for name, score in scores if score > 0]

    def execute(self, task: IDETask, ide_names: Optional[List[str]] = None) -> IDEResult:
        """Execute a task on the best matching IDE."""
        if ide_names is None:
            ide_names = self.match_ide(task)

        if not ide_names:
            return IDEResult(
                task_id=task.task_id,
                ide_name="none",
                success=False,
                error="No matching IDE available",
            )

        # Use the best-matching IDE
        best_ide = ide_names[0]
        bridge = self._bridges.get(best_ide)
        if not bridge:
            return IDEResult(
                task_id=task.task_id, ide_name="unknown",
                success=False, error=f"IDE '{best_ide}' not registered",
            )

        result = bridge.invoke(task)
        self._results.append(result)
        return result

    def execute_parallel(self, tasks: List[IDETask]) -> List[IDEResult]:
        """Execute multiple tasks in parallel across available IDEs."""
        results = []

        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(tasks))) as executor:
            futures = {}
            for task in tasks:
                ide_names = self.match_ide(task)
                if ide_names:
                    bridge = self._bridges.get(ide_names[0])
                    if bridge:
                        futures[executor.submit(bridge.invoke, task)] = task

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=task.timeout_seconds)
                    results.append(result)
                    self._results.append(result)
                except Exception as e:
                    task = futures[future]
                    results.append(IDEResult(
                        task_id=task.task_id, ide_name="error",
                        success=False, error=str(e),
                    ))

        return results

    def get_results(self, limit: int = 50) -> List[IDEResult]:
        """Get recent execution results."""
        return self._results[-limit:]

    def get_stats(self) -> dict:
        """Get orchestrator statistics."""
        results = self._results
        total = len(results)
        successful = sum(1 for r in results if r.success)
        return {
            "total_tasks": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": round(successful / total * 100, 1) if total else 0,
            "available_ides": self.detect_available_ides(),
        }
