"""Relation Engine — Entity relationship derivation engine.

Design: Based on MacOS v2.0 event_store/relation_engine.py.
Adapted to Main's cloud/services/ architecture.

Derives and manages relationships between entities in the knowledge graph.
Supports transitive, symmetric, and inferred relations.
"""
from __future__ import annotations
from typing import List, Dict, Set, Optional, Any, Tuple


class RelationEngine:
    """Entity relationship derivation and management.
    
    Discovers and manages relationships between knowledge entities:
    - Direct relations (explicitly stated)
    - Inferred relations (derived via transitivity)
    - Co-occurrence relations (same tags, same category)
    """

    def __init__(self):
        self._relations: Dict[str, List[Tuple[str, str, float]]] = {}  # source → [(target, type, weight)]
        self._reverse: Dict[str, List[Tuple[str, str, float]]] = {}    # target → [(source, type, weight)]

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str = "related_to",
        weight: float = 1.0,
    ):
        """Add a direct relation between two entities.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            relation_type: Type of relation (related_to, depends_on, part_of, etc.)
            weight: Relation strength 0.0-1.0
        """
        if source_id not in self._relations:
            self._relations[source_id] = []
        self._relations[source_id].append((target_id, relation_type, weight))

        if target_id not in self._reverse:
            self._reverse[target_id] = []
        self._reverse[target_id].append((source_id, relation_type, weight))

    def get_relations(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get all relations for an entity.
        
        Args:
            entity_id: Entity ID to query
            
        Returns:
            List of relation dicts with target, type, weight
        """
        direct = self._relations.get(entity_id, [])
        return [
            {"target": target, "type": rtype, "weight": weight}
            for target, rtype, weight in direct
        ]

    def get_reverse_relations(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get all entities that relate TO this entity."""
        reverse = self._reverse.get(entity_id, [])
        return [
            {"source": source, "type": rtype, "weight": weight}
            for source, rtype, weight in reverse
        ]

    def find_related(
        self,
        entity_id: str,
        max_depth: int = 2,
        min_weight: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Find related entities via BFS up to max_depth.
        
        Args:
            entity_id: Starting entity
            max_depth: Maximum traversal depth
            min_weight: Minimum relation weight to consider
            
        Returns:
            List of related entities with depth and accumulated weight
        """
        visited: Set[str] = {entity_id}
        results: List[Dict[str, Any]] = []
        queue: List[Tuple[str, int, float]] = [(entity_id, 0, 1.0)]

        while queue:
            current, depth, acc_weight = queue.pop(0)
            if depth > 0:
                results.append({
                    "entity_id": current,
                    "depth": depth,
                    "weight": acc_weight,
                })

            if depth >= max_depth:
                continue

            for target, rtype, weight in self._relations.get(current, []):
                if target not in visited:
                    visited.add(target)
                    new_weight = acc_weight * weight
                    if new_weight >= min_weight:
                        queue.append((target, depth + 1, new_weight))

        return sorted(results, key=lambda x: x["weight"], reverse=True)

    def infer_co_occurrence(
        self,
        entity_id: str,
        all_entities: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[str]:
        """Infer relations based on shared tags or categories.
        
        Args:
            entity_id: Entity to find co-occurrences for
            all_entities: Dict of entity_id → {tags: [...], category: ...}
            
        Returns:
            List of co-occurring entity IDs
        """
        if not all_entities or entity_id not in all_entities:
            return []

        source = all_entities[entity_id]
        source_tags = set(source.get("tags", []))
        source_cat = source.get("category", "")

        co_occurring = []
        for eid, info in all_entities.items():
            if eid == entity_id:
                continue
            score = 0
            shared_tags = source_tags & set(info.get("tags", []))
            score += len(shared_tags) * 2
            if source_cat and info.get("category") == source_cat:
                score += 1
            if score > 0:
                co_occurring.append((eid, score))

        co_occurring.sort(key=lambda x: x[1], reverse=True)
        return [eid for eid, _ in co_occurring[:20]]

    @property
    def stats(self) -> dict:
        """Relation statistics."""
        total = sum(len(v) for v in self._relations.values())
        return {
            "total_relations": total,
            "entities_with_relations": len(self._relations),
            "entities_referenced": len(self._reverse),
        }
