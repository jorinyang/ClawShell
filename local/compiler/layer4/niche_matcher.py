"""Ecological Niche Matching — Swarm task assignment algorithm.

Design: Based on DEEP TerminalManager.find_best_ganglion().
Enhanced for Main's L4 SwarmCoordinator.

Formula: score = capability_match * 0.4 + load_score * 0.3 + trust_score * 0.3
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any


def compute_niche_score(
    capabilities: List[str],
    required_tags: List[str],
    current_load: int,
    max_load: int = 10,
    trust_score: float = 0.5,
) -> float:
    """Compute ecological niche match score for task assignment.
    
    Args:
        capabilities: Node's declared capabilities
        required_tags: Task's required capability tags
        current_load: Current active task count
        max_load: Maximum task capacity
        trust_score: Node's trust score (0.0-1.0)
        
    Returns:
        Niche match score (0.0-1.0), higher is better fit
    """
    # Capability match: how many required tags match node capabilities
    cap_score = 0.0
    if required_tags:
        matches = set(required_tags) & set(capabilities)
        cap_score = len(matches) / max(len(required_tags), 1)
    else:
        cap_score = 0.5  # Neutral if no tags specified
    
    # Load score: prefer nodes with more capacity
    load_score = 1.0 - min(current_load / max(max_load, 1), 1.0)
    
    # Weighted combination
    total = cap_score * 0.4 + load_score * 0.3 + trust_score * 0.3
    return max(0.0, min(1.0, total))


def find_best_node(
    nodes: Dict[str, Dict[str, Any]],
    required_tags: Optional[List[str]] = None,
    max_load: int = 10,
) -> Optional[str]:
    """Find the best node for a task using ecological niche matching.
    
    Args:
        nodes: Dict of node_id → {capabilities: [...], active_tasks: int, trust_score: float}
        required_tags: Task's required capability tags
        max_load: Maximum task capacity per node
        
    Returns:
        Best node_id, or None if no suitable node found
    """
    if not nodes:
        return None
    
    scored = []
    for nid, info in nodes.items():
        caps = info.get("capabilities", [])
        load = info.get("active_tasks", 0)
        trust = info.get("trust_score", 0.5)
        
        score = compute_niche_score(caps, required_tags or [], load, max_load, trust)
        scored.append((score, nid))
    
    scored.sort(reverse=True)
    return scored[0][1] if scored else None


class NicheMatcher:
    """Ecological niche matcher for swarm task assignment.
    
    Integrates with SwarmCoordinator to provide intelligent
    task assignment based on multi-dimensional scoring.
    """
    
    def __init__(self, capability_weight: float = 0.4,
                 load_weight: float = 0.3, trust_weight: float = 0.3):
        self.capability_weight = capability_weight
        self.load_weight = load_weight
        self.trust_weight = trust_weight
    
    def match(
        self,
        task_tags: List[str],
        available_nodes: Dict[str, Dict[str, Any]],
    ) -> List[tuple]:
        """Rank nodes by ecological niche fit.
        
        Args:
            task_tags: Required capability tags for the task
            available_nodes: Dict of node_id → {capabilities, active_tasks, trust_score}
            
        Returns:
            List of (node_id, score) sorted by score descending
        """
        results = []
        for nid, info in available_nodes.items():
            caps = info.get("capabilities", [])
            load = info.get("active_tasks", 0)
            trust = info.get("trust_score", 0.5)
            
            cap_score = 0.0
            if task_tags:
                matches = set(task_tags) & set(caps)
                cap_score = len(matches) / max(len(task_tags), 1)
            else:
                cap_score = 0.5
            
            load_score = 1.0 - min(load / 10.0, 1.0)
            total = cap_score * self.capability_weight + load_score * self.load_weight + trust * self.trust_weight
            
            results.append((nid, total))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def find_best(self, task_tags: List[str],
                  available_nodes: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """Find the single best node for a task."""
        ranked = self.match(task_tags, available_nodes)
        return ranked[0][0] if ranked else None
