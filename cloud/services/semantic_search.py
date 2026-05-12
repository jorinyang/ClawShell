"""Semantic Search — Knowledge graph semantic search engine.

Design: Based on MacOS v2.0 event_store/semantic_search.py.
Adapted to Main's cloud/services/ architecture.

Provides keyword and semantic search across knowledge entries
stored in the KnowledgeGraph.
"""
from __future__ import annotations
from typing import List, Dict, Optional, Any


class SemanticSearch:
    """Semantic search over knowledge graph entries.
    
    Uses keyword matching with scoring and relevance ranking.
    Integrates with KnowledgeGraph for entity-aware search.
    """

    def __init__(self, knowledge_graph=None):
        """Initialize semantic search engine.
        
        Args:
            knowledge_graph: Optional KnowledgeGraph instance for entity-aware search
        """
        self._kg = knowledge_graph
        self._index: Dict[str, List[str]] = {}  # keyword → [knowledge_ids]

    def index_knowledge(self, knowledge_id: str, content: str, title: str = ""):
        """Index a knowledge entry for search.
        
        Args:
            knowledge_id: Unique knowledge entry ID
            content: Text content to index
            title: Optional title (weighted higher)
        """
        import re
        # Extract keywords (simple word-based)
        words = set()
        text = title + " " + content
        for word in text.split():
            clean = re.sub(r'[^\w]', '', word.lower())
            if len(clean) > 1:
                words.add(clean)
        for word in words:
            if word not in self._index:
                self._index[word] = []
            if knowledge_id not in self._index[word]:
                self._index[word].append(knowledge_id)

    def search(
        self,
        query: str,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search knowledge entries by query.
        
        Args:
            query: Search query string
            limit: Max results to return
            category: Optional category filter
            
        Returns:
            List of scored results with knowledge_id, title, score
        """
        import re
        query_words = set()
        for word in query.split():
            clean = re.sub(r'[^\w]', '', word.lower())
            if len(clean) > 1:
                query_words.add(clean)

        if not query_words:
            return []

        # Score each knowledge entry by keyword matches
        scores: Dict[str, float] = {}
        for word in query_words:
            for kid in self._index.get(word, []):
                scores[kid] = scores.get(kid, 0) + 1

        # If we have a knowledge graph, boost entity matches
        if self._kg:
            for kid in list(scores.keys()):
                # Check if any knowledge entry links to this one
                try:
                    linked = self._kg.get_linked_entities(kid) if hasattr(self._kg, 'get_linked_entities') else []
                    for link in linked:
                        scores[kid] = scores.get(kid, 0) + 0.5
                except Exception:
                    pass

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"knowledge_id": kid, "score": score}
            for kid, score in ranked[:limit]
        ]

    def search_with_content(
        self,
        query: str,
        knowledge_store=None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search and return full content of matching entries.
        
        Args:
            query: Search query
            knowledge_store: Optional KnowledgeStore to fetch full content
            limit: Max results
            
        Returns:
            List of knowledge entries with content
        """
        results = self.search(query, limit=limit)
        if knowledge_store:
            enriched = []
            for r in results:
                entry = knowledge_store.get(r["knowledge_id"]) if hasattr(knowledge_store, 'get') else None
                if entry:
                    enriched.append({
                        "knowledge_id": r["knowledge_id"],
                        "score": r["score"],
                        "title": getattr(entry, "title", ""),
                        "content": getattr(entry, "content", ""),
                    })
            return enriched
        return results

    @property
    def stats(self) -> dict:
        """Index statistics."""
        return {
            "total_keywords": len(self._index),
            "indexed_entries": len(set(
                kid for kids in self._index.values() for kid in kids
            )),
        }
