"""Deep Think Engine — structured deep analysis for complex problem solving.

Provides a framework for multi-step deep analysis without ML dependencies.
The engine orchestrates: Decompose → Analyze → Synthesize → Recommend.

Design: stdlib-only, synchronous analysis pipeline.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ThinkNode:
    """A node in the deep think analysis tree."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    node_type: str = "question"     # question / analysis / finding / recommendation
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0         # 0.0 - 1.0
    evidence: List[str] = field(default_factory=list)  # Supporting evidence
    alternatives: List[str] = field(default_factory=list)  # Alternative viewpoints
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "content": self.content,
            "node_type": self.node_type,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "alternatives": self.alternatives,
            "metadata": self.metadata,
        }


@dataclass
class ThinkResult:
    """Complete deep think analysis result."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    question: str = ""
    root_node_id: str = ""
    nodes: Dict[str, ThinkNode] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "question": self.question,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "confidence": round(self.confidence, 3),
            "node_count": len(self.nodes),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class DeepThinkEngine:
    """Structured deep analysis engine.

    Orchestrates multi-step analysis:
    1. DECOMPOSE — break problem into sub-questions
    2. ANALYZE — examine each sub-question
    3. SYNTHESIZE — combine findings into coherent picture
    4. RECOMMEND — produce actionable recommendations

    The engine provides the framework; actual analysis content
    is filled by the caller (e.g., LLM-assisted analysis).

    Thread-safe via RLock.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: Dict[str, ThinkResult] = {}
        self._max_sessions = 100

    def start_session(self, question: str) -> ThinkResult:
        """Start a new deep think session."""
        with self._lock:
            result = ThinkResult(question=question)
            self._sessions[result.session_id] = result
            self._trim_sessions()
            return result

    def add_node(self, session_id: str, node: ThinkNode) -> Optional[ThinkResult]:
        """Add an analysis node to a session."""
        with self._lock:
            result = self._sessions.get(session_id)
            if not result:
                return None
            result.nodes[node.node_id] = node

            if node.parent_id:
                parent = result.nodes.get(node.parent_id)
                if parent and node.node_id not in parent.children_ids:
                    parent.children_ids.append(node.node_id)

            # Track root
            if not result.root_node_id and node.parent_id is None:
                result.root_node_id = node.node_id

            # Collect findings and recommendations
            if node.node_type == "finding":
                result.findings.append(node.content)
            elif node.node_type == "recommendation":
                result.recommendations.append(node.content)

            return result

    def complete_session(self, session_id: str, confidence: float = 0.0) -> Optional[ThinkResult]:
        """Complete a deep think session with final confidence score."""
        with self._lock:
            result = self._sessions.get(session_id)
            if result:
                result.completed_at = time.time()
                result.duration_seconds = result.completed_at - result.started_at
                result.confidence = confidence

                # Aggregated confidence from nodes if not explicitly set
                if confidence == 0.0 and result.nodes:
                    confidences = [n.confidence for n in result.nodes.values() if n.confidence > 0]
                    if confidences:
                        result.confidence = sum(confidences) / len(confidences)
            return result

    def get_session(self, session_id: str) -> Optional[ThinkResult]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self, limit: int = 20) -> List[ThinkResult]:
        with self._lock:
            sessions = sorted(
                self._sessions.values(),
                key=lambda r: r.started_at,
                reverse=True,
            )
            return sessions[:limit]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            completed = sum(1 for r in self._sessions.values() if r.completed_at)
            avg_confidence = 0.0
            if completed > 0:
                avg_confidence = sum(
                    r.confidence for r in self._sessions.values() if r.completed_at
                ) / completed
            return {
                "total_sessions": len(self._sessions),
                "completed_sessions": completed,
                "in_progress": len(self._sessions) - completed,
                "avg_confidence": round(avg_confidence, 3),
            }

    def _trim_sessions(self) -> None:
        """Remove oldest sessions if over max."""
        if len(self._sessions) > self._max_sessions:
            oldest = sorted(self._sessions.items(),
                          key=lambda x: x[1].started_at)
            for sid, _ in oldest[:len(self._sessions) - self._max_sessions]:
                del self._sessions[sid]
