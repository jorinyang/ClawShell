"""Knowledge Graph — entity-relation storage with semantic search.

Stores entities and their relationships as a semantic graph.
Supports path queries, similarity search, and relevance scoring.

Design: stdlib-only, in-memory with optional JSON persistence.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class Entity:
    """A knowledge entity (node in the graph)."""
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    entity_type: str = "concept"     # concept / task / skill / pattern / insight / node
    description: str = ""
    tags: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "tags": self.tags,
            "properties": self.properties,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Entity":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Relation:
    """A directed relationship between two entities."""
    relation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation_type: str = "related_to"  # depends_on / produces / improves / conflicts_with / ...
    weight: float = 1.0               # Relationship strength (0.0 - 1.0)
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "weight": self.weight,
            "properties": self.properties,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Relation":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class GraphQuery:
    """Query specification for knowledge graph traversal."""
    start_entity_id: Optional[str] = None
    relation_type: Optional[str] = None
    max_depth: int = 3
    min_weight: float = 0.0
    entity_type_filter: Optional[str] = None


@dataclass
class SearchResult:
    """Semantic search result."""
    entity: Entity
    score: float = 0.0          # Relevance score (0.0 - 1.0)
    matched_terms: List[str] = field(default_factory=list)
    relevant_relations: List[str] = field(default_factory=list)


class KnowledgeGraph:
    """Entity-relation knowledge graph with semantic search.

    Key capabilities:
    - CRUD for entities and relations
    - Graph traversal (find paths between entities)
    - TF-IDF-based semantic search (stdlib, no external deps)
    - Relevance scoring

    Thread-safe via RLock.
    """

    def __init__(self, store_dir: Optional[str] = None):
        self._lock = threading.RLock()
        self._entities: Dict[str, Entity] = {}
        self._relations: Dict[str, Relation] = {}
        # Adjacency index for fast traversal
        self._outgoing: Dict[str, List[str]] = defaultdict(list)  # source → [relation_ids]
        self._incoming: Dict[str, List[str]] = defaultdict(list)  # target → [relation_ids]
        # Search index
        self._term_index: Dict[str, Set[str]] = defaultdict(set)  # term → {entity_ids}
        self._store_dir = Path(store_dir) if store_dir else None

        if self._store_dir:
            self._load()

    # ── Entity CRUD ─────────────────────────────────

    def add_entity(self, entity: Entity) -> Entity:
        with self._lock:
            entity.updated_at = time.time()
            self._entities[entity.entity_id] = entity
            self._index_entity(entity)
            self._save()
            return entity

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        with self._lock:
            return self._entities.get(entity_id)

    def find_entities(self, entity_type: Optional[str] = None,
                      tags: Optional[List[str]] = None) -> List[Entity]:
        with self._lock:
            results = []
            for e in self._entities.values():
                if entity_type and e.entity_type != entity_type:
                    continue
                if tags and not any(t in e.tags for t in tags):
                    continue
                results.append(e)
            return results

    def remove_entity(self, entity_id: str) -> bool:
        with self._lock:
            if entity_id not in self._entities:
                return False
            del self._entities[entity_id]
            # Remove related relations
            to_remove = []
            for rid, rel in self._relations.items():
                if rel.source_id == entity_id or rel.target_id == entity_id:
                    to_remove.append(rid)
            for rid in to_remove:
                self._remove_relation_internal(rid)
            self._save()
            return True

    # ── Relation CRUD ───────────────────────────────

    def add_relation(self, relation: Relation) -> Optional[Relation]:
        with self._lock:
            if (relation.source_id not in self._entities or
                relation.target_id not in self._entities):
                return None
            self._relations[relation.relation_id] = relation
            self._outgoing[relation.source_id].append(relation.relation_id)
            self._incoming[relation.target_id].append(relation.relation_id)
            self._save()
            return relation

    def get_relations(self, entity_id: str,
                      direction: str = "both") -> List[Relation]:
        with self._lock:
            result = []
            if direction in ("outgoing", "both"):
                for rid in self._outgoing.get(entity_id, []):
                    if rid in self._relations:
                        result.append(self._relations[rid])
            if direction in ("incoming", "both"):
                for rid in self._incoming.get(entity_id, []):
                    if rid in self._relations:
                        result.append(self._relations[rid])
            return result

    def _remove_relation_internal(self, relation_id: str) -> None:
        rel = self._relations.pop(relation_id, None)
        if rel:
            self._outgoing[rel.source_id].remove(relation_id)
            self._incoming[rel.target_id].remove(relation_id)

    # ── Graph Traversal ─────────────────────────────

    def traverse(self, query: GraphQuery) -> List[Tuple[Entity, List[Relation]]]:
        """BFS traversal from a start entity.

        Returns list of (entity, path_of_relations) pairs.
        """
        with self._lock:
            if not query.start_entity_id or query.start_entity_id not in self._entities:
                return []

            visited: Set[str] = {query.start_entity_id}
            results: List[Tuple[Entity, List[Relation]]] = []
            # (entity_id, depth, path_relations)
            queue = [(query.start_entity_id, 0, [])]

            while queue:
                eid, depth, path = queue.pop(0)
                entity = self._entities.get(eid)
                if not entity:
                    continue

                if depth > 0:  # Skip start entity in results
                    results.append((entity, path))

                if depth >= query.max_depth:
                    continue

                for rid in self._outgoing.get(eid, []):
                    rel = self._relations.get(rid)
                    if not rel:
                        continue
                    if query.relation_type and rel.relation_type != query.relation_type:
                        continue
                    if rel.weight < query.min_weight:
                        continue
                    if rel.target_id not in visited:
                        visited.add(rel.target_id)
                        queue.append((rel.target_id, depth + 1, path + [rel]))

            # Apply entity type filter
            if query.entity_type_filter:
                results = [
                    (e, p) for e, p in results
                    if e.entity_type == query.entity_type_filter
                ]

            return results

    def find_paths(self, from_id: str, to_id: str,
                   max_depth: int = 5) -> List[List[Relation]]:
        """Find all paths between two entities (BFS)."""
        with self._lock:
            if from_id not in self._entities or to_id not in self._entities:
                return []

            paths = []
            # BFS with path tracking
            queue = [(from_id, [])]
            visited_paths: Set[Tuple[str, ...]] = set()

            while queue:
                current, path = queue.pop(0)
                if len(path) >= max_depth:
                    continue

                for rid in self._outgoing.get(current, []):
                    rel = self._relations.get(rid)
                    if not rel:
                        continue

                    new_path = path + [rel]
                    path_key = tuple(r.relation_id for r in new_path)
                    if path_key in visited_paths:
                        continue
                    visited_paths.add(path_key)

                    if rel.target_id == to_id:
                        paths.append(new_path)
                    else:
                        queue.append((rel.target_id, new_path))

            return paths

    # ── Semantic Search ─────────────────────────────

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """TF-IDF-inspired semantic search over entities.

        Searches entity names, descriptions, and tags.
        """
        with self._lock:
            query_terms = self._tokenize(query)
            if not query_terms or not self._entities:
                return []

            # Compute TF-IDF-like scores
            N = len(self._entities)
            scores: Dict[str, float] = {}

            for term in query_terms:
                matching_entities = self._term_index.get(term, set())
                idf = self._idf(term, N)

                for eid in matching_entities:
                    entity = self._entities.get(eid)
                    if not entity:
                        continue

                    # TF: how many times term appears in entity
                    entity_text = f"{entity.name} {entity.description} {' '.join(entity.tags)}"
                    tf = entity_text.lower().count(term) / max(len(entity_text.split()), 1)

                    scores[eid] = scores.get(eid, 0) + tf * idf

            # Sort by score
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            results = []
            for eid, score in ranked[:limit]:
                entity = self._entities[eid]
                matched = [t for t in query_terms if t.lower() in entity.name.lower()
                          or t.lower() in entity.description.lower()]
                relations = self.get_relations(eid, "both")
                results.append(SearchResult(
                    entity=entity,
                    score=min(score, 1.0),
                    matched_terms=matched,
                    relevant_relations=[r.relation_type for r in relations[:5]],
                ))
            return results

    # ── Internal Helpers ────────────────────────────

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer."""
        return [t.lower().strip(".,!?;:()[]\"'") for t in text.split()
                if len(t.strip(".,!?;:()[]\"'")) > 1]

    def _idf(self, term: str, N: int) -> float:
        """Inverse document frequency."""
        doc_count = len(self._term_index.get(term, set()))
        import math
        return math.log((N + 1) / (doc_count + 1)) + 1

    def _index_entity(self, entity: Entity) -> None:
        """Index entity terms for search."""
        text = f"{entity.name} {entity.description} {' '.join(entity.tags)}"
        terms = set(self._tokenize(text))
        for term in terms:
            self._term_index[term].add(entity.entity_id)

    # ── Persistence ─────────────────────────────────

    def _save(self) -> None:
        if not self._store_dir:
            return
        self._store_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "entities": [e.to_dict() for e in self._entities.values()],
            "relations": [r.to_dict() for r in self._relations.values()],
        }
        tmp = self._store_dir / "graph.json.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        tmp.rename(self._store_dir / "graph.json")

    def _load(self) -> None:
        if not self._store_dir:
            return
        graph_file = self._store_dir / "graph.json"
        if not graph_file.exists():
            return
        try:
            data = json.loads(graph_file.read_text())
            for ed in data.get("entities", []):
                e = Entity.from_dict(ed)
                self._entities[e.entity_id] = e
                self._index_entity(e)
            for rd in data.get("relations", []):
                r = Relation.from_dict(rd)
                self._relations[r.relation_id] = r
                self._outgoing[r.source_id].append(r.relation_id)
                self._incoming[r.target_id].append(r.relation_id)
        except (json.JSONDecodeError, OSError):
            pass

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "entity_count": len(self._entities),
                "relation_count": len(self._relations),
                "indexed_terms": len(self._term_index),
                "by_type": self._entity_type_counts(),
            }

    def _entity_type_counts(self) -> Dict[str, int]:
        counts = {}
        for e in self._entities.values():
            counts[e.entity_type] = counts.get(e.entity_type, 0) + 1
        return counts
