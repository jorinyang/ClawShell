"""Exoskeleton Layer 4 — Multi-Agent Swarm (多Agent集群).

Core: Swarm discovery, Trust evaluation (known + stranger nodes),
Ecological niche matching, Collaboration protocol, Node registry.
"""

import os
import json
import time
import threading
import hashlib
from typing import Dict, List, Optional, Any, Set
from enum import Enum


class TrustLevel(Enum):
    FULL = 1.0
    HIGH = 0.8
    MEDIUM = 0.6
    LOW = 0.4
    NONE = 0.0


class SwarmManager:
    """Multi-agent swarm discovery and management."""

    def __init__(self):
        self._lock = threading.RLock()
        self._nodes: Dict[str, dict] = {}
        self._discovery_log: List[dict] = []

    def register_node(self, node_id: str, node_info: dict):
        with self._lock:
            node_info["registered_at"] = time.time()
            node_info["last_seen"] = time.time()
            self._nodes[node_id] = node_info
            self._discovery_log.append({
                "event": "node_registered",
                "node_id": node_id,
                "timestamp": time.time(),
            })

    def discover_nodes(self, capability: Optional[str] = None) -> List[dict]:
        with self._lock:
            nodes = list(self._nodes.values())
            if capability:
                nodes = [n for n in nodes if capability in n.get("capabilities", [])]
            return nodes

    def get_node(self, node_id: str) -> Optional[dict]:
        return self._nodes.get(node_id)

    def remove_node(self, node_id: str):
        with self._lock:
            self._nodes.pop(node_id, None)
            self._discovery_log.append({
                "event": "node_removed",
                "node_id": node_id,
                "timestamp": time.time(),
            })

    def is_alive(self, node_id: str, timeout: float = 60) -> bool:
        node = self._nodes.get(node_id)
        if not node:
            return False
        return (time.time() - node.get("last_seen", 0)) < timeout


class TrustEvaluator:
    """Trust evaluation with known-node (certificate) and stranger-node (behavior) models."""

    TRUST_PERMISSIONS = {
        TrustLevel.FULL: ["*"],
        TrustLevel.HIGH: ["read", "write", "execute", "delegate"],
        TrustLevel.MEDIUM: ["read", "write", "execute"],
        TrustLevel.LOW: ["read", "execute"],
        TrustLevel.NONE: [],
    }

    def __init__(self):
        self._lock = threading.RLock()
        self._trust_scores: Dict[str, dict] = {}
        self._known_nodes: Set[str] = set()
        self._behavior_history: Dict[str, List[dict]] = {}

    def add_known_node(self, node_id: str, pre_shared_key: str = ""):
        with self._lock:
            self._known_nodes.add(node_id)
            self._trust_scores[node_id] = {
                "score": TrustLevel.FULL.value,
                "level": TrustLevel.FULL,
                "source": "known_node",
            }

    def evaluate_behavior(self, node_id: str, interaction: dict) -> float:
        """Evaluate trust based on interaction behavior."""
        with self._lock:
            history = self._behavior_history.setdefault(node_id, [])
            history.append(interaction)
            if len(history) > 50:
                history = history[-50:]

            # Calculate behavior score
            successes = sum(1 for h in history if h.get("success", False))
            total = len(history)
            score = successes / total if total > 0 else 0.5

            self._trust_scores[node_id] = {
                "score": score,
                "level": self._score_to_level(score),
                "source": "behavior",
            }
            return score

    def get_trust(self, node_id: str) -> float:
        entry = self._trust_scores.get(node_id)
        return entry["score"] if entry else 0.0

    def can(self, node_id: str, action: str) -> bool:
        entry = self._trust_scores.get(node_id)
        if not entry:
            return False
        permissions = self.TRUST_PERMISSIONS.get(entry.get("level", TrustLevel.NONE), [])
        return "*" in permissions or action in permissions

    def revoke_trust(self, node_id: str, reason: str = ""):
        with self._lock:
            self._known_nodes.discard(node_id)
            self._trust_scores[node_id] = {
                "score": 0.0,
                "level": TrustLevel.NONE,
                "source": "revoked",
                "reason": reason,
            }

    @staticmethod
    def _score_to_level(score: float) -> TrustLevel:
        if score >= 1.0: return TrustLevel.FULL
        if score >= 0.8: return TrustLevel.HIGH
        if score >= 0.6: return TrustLevel.MEDIUM
        if score >= 0.4: return TrustLevel.LOW
        return TrustLevel.NONE


class EcologicalNicheMatcher:
    """Match tasks to agents based on capability (ecological niche)."""

    DEMAND_WEIGHT = 1.0
    CAPABILITY_WEIGHT = 0.8

    def __init__(self):
        self._lock = threading.RLock()
        self._agent_capabilities: Dict[str, List[str]] = {}

    def register_capabilities(self, agent_id: str, capabilities: List[str]):
        with self._lock:
            self._agent_capabilities[agent_id] = capabilities

    def match(self, required_capabilities: List[str]) -> Optional[str]:
        """Find best agent for required capabilities."""
        with self._lock:
            if not required_capabilities:
                # Return first available agent
                agents = list(self._agent_capabilities.keys())
                return agents[0] if agents else None

            required = set(required_capabilities)
            best_agent = None
            best_score = 0

            for agent_id, caps in self._agent_capabilities.items():
                agent_caps = set(caps)
                # Capability match
                cap_score = len(required & agent_caps) / len(required) if required else 0
                # Demand match: prefer agents with closest capability set size
                demand_score = 1.0 / (1 + abs(len(caps) - len(required)))

                total = cap_score * self.CAPABILITY_WEIGHT + demand_score * self.DEMAND_WEIGHT
                if total > best_score:
                    best_score = total
                    best_agent = agent_id

            return best_agent

    def get_agents_for_capability(self, capability: str) -> List[str]:
        with self._lock:
            return [aid for aid, caps in self._agent_capabilities.items()
                   if capability in caps]


class CollaborationProtocol:
    """Intent-level collaboration protocol: parse → decompose → assign → execute → summarize."""

    STATUSES = ["initialized", "decomposing", "assigning", "executing", "summarizing", "completed", "failed"]

    def __init__(self):
        self._lock = threading.RLock()
        self._collaborations: Dict[str, dict] = {}
        self._niche_matcher = EcologicalNicheMatcher()

    def start_collaboration(self, intent: str, participants: List[str],
                            context: Optional[dict] = None) -> str:
        """Start a new collaboration. Returns collaboration_id."""
        import uuid
        cid = str(uuid.uuid4())
        with self._lock:
            self._collaborations[cid] = {
                "collaboration_id": cid,
                "intent": intent,
                "participants": participants,
                "context": context or {},
                "status": "initialized",
                "tasks": [],
                "results": {},
                "started_at": time.time(),
            }
        return cid

    def decompose(self, collaboration_id: str, tasks: List[dict]):
        """Decompose intent into executable tasks."""
        with self._lock:
            collab = self._collaborations.get(collaboration_id)
            if collab:
                collab["tasks"] = tasks
                collab["status"] = "decomposing"

    def assign_tasks(self, collaboration_id: str) -> dict:
        """Assign tasks to best-matching participants."""
        with self._lock:
            collab = self._collaborations.get(collaboration_id)
            if not collab:
                return {}

            assignments = {}
            for task in collab["tasks"]:
                required = task.get("required_capabilities", [])
                agent = self._niche_matcher.match(required)
                if agent:
                    assignments[task.get("task_id", "")] = agent

            collab["assignments"] = assignments
            collab["status"] = "assigning"
            return assignments

    def record_result(self, collaboration_id: str, task_id: str, result: dict):
        with self._lock:
            collab = self._collaborations.get(collaboration_id)
            if collab:
                collab["results"][task_id] = result

    def complete(self, collaboration_id: str) -> dict:
        with self._lock:
            collab = self._collaborations.get(collaboration_id)
            if collab:
                collab["status"] = "completed"
                collab["completed_at"] = time.time()
                return dict(collab)
            return {}

    def get_collaboration(self, collaboration_id: str) -> Optional[dict]:
        return self._collaborations.get(collaboration_id)

    def list_active(self) -> List[dict]:
        return [
            c for c in self._collaborations.values()
            if c["status"] not in ("completed", "failed")
        ]
