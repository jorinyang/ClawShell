"""HermesLoop — Cloud-side cron-driven Hermes loop engine.

Supersedes Evolution, Review, Optimizer, DeepThink, and Workflow engines
by consolidating their logic into 4 Hermes loops.

Loops (driven by CloudScheduler):
  Loop 1 (every 5 min): Session summary — pull session.* events, aggregate into insights
  Loop 2 (every 2 min): Task dispatch — read TaskBoard + AgentMesh, match and dispatch
  Loop 3 (every 30 min): Session review — review completed sessions, suggest reusable skills
  Loop 4 (every 1 hour): Knowledge push — approved knowledge/skills → git push to GitHub repos

Cloud Hermes only produces (never executes) — Local Hermes pulls via SyncDaemon.
"""

from __future__ import annotations
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HermesLoop:
    """Cloud-side Hermes loop engine — 4 cron-driven loops.

    Communicates with other engines via CloudEventBus (push) and
    TaskBoard/AgentMesh (pull). Results are stored as Insights
    or pushed to GitHub repos.
    """

    def __init__(self, eventbus=None, taskboard=None, agentmesh=None,
                 insight_engine=None, github_api=None):
        self._eventbus = eventbus
        self._taskboard = taskboard
        self._agentmesh = agentmesh
        self._insight = insight_engine
        self._github = github_api
        self._lock = threading.RLock()
        self._loop_stats: Dict[str, dict] = {}
        self._started = False

    # ── Loop Implementations ──────────────────────────

    def loop_session_summary(self) -> dict:
        """Loop 1 (every 5 min): Pull session events, aggregate into insights."""
        events = []
        if self._eventbus:
            events = self._eventbus.query(category="session", limit=50)

        insights = []
        # Group events by session_id and summarize
        sessions: Dict[str, list] = {}
        for evt in events:
            sid = evt.get("payload", {}).get("session_id", "unknown")
            sessions.setdefault(sid, []).append(evt)

        for sid, evts in sessions.items():
            summary = {
                "session_id": sid,
                "event_count": len(evts),
                "summary": f"Session {sid}: {len(evts)} events in last interval",
                "timestamp": time.time(),
            }
            insights.append(summary)

        if self._insight:
            for ins in insights:
                self._insight.add_insight(
                    title=f"Session summary: {ins['session_id']}",
                    content=ins["summary"],
                    category="session_summary",
                    tags=["hermes-loop", "session"],
                )

        result = {"loop": "session_summary", "sessions": len(sessions), "insights": len(insights)}
        self._record_loop("session_summary", result)
        return result

    def loop_task_dispatch(self) -> dict:
        """Loop 2 (every 2 min): Read TaskBoard, match with AgentMesh, dispatch."""
        dispatched = 0
        if self._taskboard and self._agentmesh:
            pending = self._taskboard.list_tasks(status="pending")
            for task in pending:
                required = task.get("required_capabilities", [])
                if not required:
                    continue
                matches = self._agentmesh.match_task(required)
                if matches:
                    best = matches[0]
                    self._taskboard.assign_task(task["task_id"], best["agent_id"])
                    self._agentmesh.assign_task(task["task_id"], best["agent_id"])
                    dispatched += 1

        result = {"loop": "task_dispatch", "dispatched": dispatched}
        self._record_loop("task_dispatch", result)
        return result

    def loop_session_review(self) -> dict:
        """Loop 3 (every 30 min): Review completed sessions, suggest reusable skills."""
        suggestions = []
        if self._eventbus:
            completed = self._eventbus.query(category="task", status="completed", limit=100)
            # Look for patterns: tasks with same capability requirements, same tags
            tag_counts: Dict[str, int] = {}
            for evt in completed:
                for tag in evt.get("payload", {}).get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            for tag, count in tag_counts.items():
                if count >= 3:
                    suggestions.append({
                        "tag": tag,
                        "count": count,
                        "suggestion": f"Consider creating a reusable skill for '{tag}' tasks",
                    })

        if self._insight and suggestions:
            for s in suggestions:
                self._insight.add_insight(
                    title=f"Skill suggestion: {s['tag']}",
                    content=s["suggestion"],
                    category="skill_suggestion",
                    tags=["hermes-loop", "review", s["tag"]],
                )

        result = {"loop": "session_review", "suggestions": len(suggestions)}
        self._record_loop("session_review", result)
        return result

    def loop_knowledge_push(self) -> dict:
        """Loop 4 (every 1 hour): Push approved knowledge/skills to GitHub repos."""
        pushed = 0
        if self._insight and self._github:
            # Find insights marked for knowledge push
            knowledge = []
            if self._insight:
                knowledge = getattr(self._insight, 'get_knowledge_pending_push', lambda: [])()
            for entry in knowledge:
                try:
                    repo = entry.get("repo_name", "")
                    path = entry.get("path", "")
                    content = entry.get("content", "")
                    if repo and path and content:
                        self._github.push_file(repo, path, content,
                                               message=f"HermesLoop: {entry.get('title', 'knowledge update')}")
                        pushed += 1
                except Exception as e:
                    logger.error("Knowledge push failed for %s: %s", entry.get("path"), e)

        result = {"loop": "knowledge_push", "pushed": pushed}
        self._record_loop("knowledge_push", result)
        return result

    # ── Run All Loops ─────────────────────────────────

    def run_all(self) -> Dict[str, dict]:
        """Execute all 4 loops and return aggregated results."""
        results = {}
        for loop_fn, name in [
            (self.loop_session_summary, "summary"),
            (self.loop_task_dispatch, "dispatch"),
            (self.loop_session_review, "review"),
            (self.loop_knowledge_push, "knowledge"),
        ]:
            try:
                results[name] = loop_fn()
            except Exception as e:
                logger.error("HermesLoop %s failed: %s", name, e)
                results[name] = {"error": str(e)}
        return results

    # ── Lifecycle ─────────────────────────────────────

    def start(self):
        self._started = True
        logger.info("HermesLoop started (4 loops)")

    def stop(self):
        self._started = False
        logger.info("HermesLoop stopped")

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "started": self._started,
                "loop_stats": dict(self._loop_stats),
            }

    def _record_loop(self, name: str, result: dict):
        with self._lock:
            if name not in self._loop_stats:
                self._loop_stats[name] = {"runs": 0}
            self._loop_stats[name]["runs"] += 1
            self._loop_stats[name]["last_result"] = result
            self._loop_stats[name]["last_run"] = time.time()
