"""AgentMesh — Agent-level cross-device collaboration engine.

Replaces TopologyManager (node-level) with Agent-level capability-based task matching.
Supersedes SwarmCoordinator for Agent-to-Agent dispatch.

v3.0: Core engine — handles agent registration, capability indexing,
      task matching (by capability), and cross-device dispatch.
"""

from __future__ import annotations
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentMesh:
    """Agent-level capability registry and task matching engine.

    Each agent registers with its capabilities (skills, tools, domains).
    When a task arrives, AgentMesh matches it to the best agent by
    capability overlap score.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._agents: Dict[str, dict] = {}  # agent_id → agent entry
        self._cap_index: Dict[str, set[str]] = {}  # capability → set of agent_ids
        self._started = False

    # ── Registration ─────────────────────────────────

    def register_agent(self, agent_id: str, node_id: str, user_id: str,
                       framework: str, capabilities: List[str],
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """Register an agent in the mesh. Returns agent_id."""
        with self._lock:
            entry = {
                "agent_id": agent_id,
                "node_id": node_id,
                "user_id": user_id,
                "framework": framework,
                "capabilities": capabilities,
                "status": "online",
                "registered_at": time.time(),
                "last_heartbeat": time.time(),
                "current_task_id": "",
                "metadata": metadata or {},
            }
            self._agents[agent_id] = entry

            for cap in capabilities:
                cap_lower = cap.lower()
                if cap_lower not in self._cap_index:
                    self._cap_index[cap_lower] = set()
                self._cap_index[cap_lower].add(agent_id)

            logger.info("AgentMesh registered: %s (capabilities: %s)", agent_id, capabilities)
            return agent_id

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the mesh."""
        with self._lock:
            entry = self._agents.pop(agent_id, None)
            if not entry:
                return False
            for cap in entry["capabilities"]:
                cap_lower = cap.lower()
                if cap_lower in self._cap_index:
                    self._cap_index[cap_lower].discard(agent_id)
                    if not self._cap_index[cap_lower]:
                        del self._cap_index[cap_lower]
            logger.info("AgentMesh unregistered: %s", agent_id)
            return True

    def heartbeat(self, agent_id: str) -> bool:
        """Update last_heartbeat for an agent."""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id]["last_heartbeat"] = time.time()
                self._agents[agent_id]["status"] = "online"
                return True
            return False

    # ── Matching ──────────────────────────────────────

    def match_task(self, required_capabilities: List[str],
                   user_id: Optional[str] = None,
                   exclude_agent_id: Optional[str] = None) -> List[dict]:
        """Find agents matching required capabilities, sorted by score desc.

        Score = number of matched capabilities. Filters by user_id if provided.
        """
        with self._lock:
            candidates: Dict[str, int] = {}
            for cap in required_capabilities:
                cap_lower = cap.lower()
                for agent_id in self._cap_index.get(cap_lower, set()):
                    agent = self._agents.get(agent_id)
                    if not agent or agent["status"] != "online":
                        continue
                    if exclude_agent_id and agent_id == exclude_agent_id:
                        continue
                    if user_id and agent["user_id"] != user_id:
                        continue
                    candidates[agent_id] = candidates.get(agent_id, 0) + 1

            ranked = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
            return [self._agents[aid] for aid, score in ranked]

    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent."""
        with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id]["current_task_id"] = task_id
            return True

    def release_task(self, agent_id: str) -> bool:
        """Release current task from an agent."""
        with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id]["current_task_id"] = ""
            return True

    # ── Query ─────────────────────────────────────────

    def get_agent(self, agent_id: str) -> Optional[dict]:
        with self._lock:
            return self._agents.get(agent_id)

    def get_user_agents(self, user_id: str) -> List[dict]:
        with self._lock:
            return [a for a in self._agents.values() if a["user_id"] == user_id]

    def get_node_agents(self, node_id: str) -> List[dict]:
        with self._lock:
            return [a for a in self._agents.values() if a["node_id"] == node_id]

    def list_agents(self, status: Optional[str] = None) -> List[dict]:
        with self._lock:
            if status:
                return [a for a in self._agents.values() if a["status"] == status]
            return list(self._agents.values())

    def online_count(self) -> int:
        with self._lock:
            return sum(1 for a in self._agents.values() if a["status"] == "online")

    def get_capabilities(self) -> List[str]:
        with self._lock:
            return sorted(self._cap_index.keys())

    # ── Lifecycle ─────────────────────────────────────

    def start(self):
        self._started = True
        logger.info("AgentMesh started")

    def stop(self):
        self._started = False
        with self._lock:
            self._agents.clear()
            self._cap_index.clear()
        logger.info("AgentMesh stopped")

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._agents)
            online = sum(1 for a in self._agents.values() if a["status"] == "online")
            busy = sum(1 for a in self._agents.values() if a.get("current_task_id"))
            return {
                "total_agents": total,
                "online_agents": online,
                "busy_agents": busy,
                "capabilities": len(self._cap_index),
                "started": self._started,
            }
