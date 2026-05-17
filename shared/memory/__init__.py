"""ClawShell shared memory subsystem — HNSW vector memory engine.

Provides approximate nearest neighbor search using HNSW (Hierarchical
Navigable Small World) indexing via ``hnswlib``.

Version: 2.1.0
"""

from shared.memory.hnsw_engine import (
    HNSWConfig,
    SearchResult,
    HNSWVectorMemory,
    embed_text_simple,
)

__all__ = [
    "HNSWConfig",
    "SearchResult",
    "HNSWVectorMemory",
    "embed_text_simple",
]

__version__ = "2.1.0"
