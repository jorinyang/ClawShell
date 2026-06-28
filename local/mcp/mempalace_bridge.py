"""
mempalace_bridge.py — 端脑 MemPalace 混合搜索桥接
=================================================

将 MemPalace 的 BM25 + Vector 混合搜索能力集成到 ClawShell 端脑记忆系统。

v2.1.1 新增:
  - CJK bigram 分词 (中文/日文/韩文)
  - BM25 + Vector 混合搜索 (Layer3)
  - 可配置搜索权重 (env/config)
  - 向后兼容: MemPalace 未安装时回退到 SQLite LIKE 搜索

Architecture:
  ClawShell Edge (端脑)
    └── memory_server.py (MCP STDIO)
        └── mempalace_bridge.py (本模块)
            └── mempalace package (pip)
                ├── searcher.py — BM25 + hybrid rank
                ├── layers.py — 4-layer memory stack
                └── config.py — configurable weights
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("clawshell.mempalace_bridge")

# ── Lazy import flag ─────────────────────────────────────────
_MEMPALACE_AVAILABLE: Optional[bool] = None


def _check_mempalace() -> bool:
    """Check if mempalace package is installed and palace exists."""
    global _MEMPALACE_AVAILABLE
    if _MEMPALACE_AVAILABLE is not None:
        return _MEMPALACE_AVAILABLE
    try:
        import mempalace  # noqa: F401
        palace_path = Path(os.path.expanduser("~/.mempalace/palace"))
        _MEMPALACE_AVAILABLE = palace_path.exists()
        if _MEMPALACE_AVAILABLE:
            logger.info("MemPalace bridge: hybrid search available")
        else:
            logger.info("MemPalace bridge: package installed but no palace at %s", palace_path)
    except ImportError:
        _MEMPALACE_AVAILABLE = False
        logger.info("MemPalace bridge: package not installed, using fallback")
    return _MEMPALACE_AVAILABLE


def search_hybrid(
    query: str,
    limit: int = 10,
    wing: Optional[str] = None,
    room: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search MemPalace with BM25 + Vector hybrid ranking.

    Falls back to SQLite LIKE search if mempalace package is unavailable.

    Returns list of dicts with keys:
        source, key, type, content, similarity, bm25_score, wing, room
    """
    if not _check_mempalace():
        return _fallback_sqlite_search(query, limit)

    try:
        from mempalace.layers import MemoryStack

        stack = MemoryStack()
        hits = stack.l3.search_raw(query, wing=wing, room=room, n_results=limit)

        results = []
        for h in hits:
            results.append({
                "source": "mempalace",
                "key": h.get("source_file", ""),
                "type": "drawer",
                "content": h.get("text", "")[:500],
                "similarity": h.get("similarity", 0),
                "bm25_score": h.get("bm25_score", 0),
                "wing": h.get("wing", ""),
                "room": h.get("room", ""),
            })
        return results

    except Exception as e:
        logger.warning("MemPalace hybrid search failed: %s, falling back", e)
        return _fallback_sqlite_search(query, limit)


def search_context(
    query: str = "",
    wing: Optional[str] = None,
) -> str:
    """Get memory context: wake-up (L0+L1) or search (L3).

    Returns formatted text suitable for injection into agent prompts.
    """
    if not _check_mempalace():
        return ""

    try:
        from mempalace.layers import MemoryStack

        stack = MemoryStack()
        if query:
            return stack.search(query, wing=wing, n_results=5)
        else:
            return stack.wake_up(wing=wing)
    except Exception as e:
        logger.warning("MemPalace context failed: %s", e)
        return ""


def get_stats() -> Dict[str, Any]:
    """Get MemPalace statistics including search engine info."""
    stats = {
        "available": _check_mempalace(),
        "engine": "hybrid (BM25 + Vector)" if _check_mempalace() else "sqlite_like",
    }

    if not _check_mempalace():
        return stats

    try:
        from mempalace.layers import MemoryStack
        from mempalace.config import MempalaceConfig

        stack = MemoryStack()
        layer_status = stack.status()
        stats.update(layer_status)

        cfg = MempalaceConfig()
        stats["search_config"] = {
            "vector_weight": cfg.search_vector_weight,
            "bm25_weight": cfg.search_bm25_weight,
        }
    except Exception as e:
        stats["error"] = str(e)

    return stats


def _fallback_sqlite_search(query: str, limit: int) -> List[Dict[str, Any]]:
    """Fallback: search knowledge_graph.sqlite3 with LIKE."""
    import sqlite3

    results = []
    db_path = Path(os.path.expanduser("~/.mempalace")) / "knowledge_graph.sqlite3"
    if not db_path.exists():
        return results

    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT name, type, properties FROM entities WHERE name LIKE ? OR properties LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        for name, etype, props in rows:
            results.append({
                "source": "mempalace",
                "key": name,
                "type": etype,
                "content": str(props)[:300],
                "similarity": 0,
                "bm25_score": 0,
            })
        conn.close()
    except Exception:
        pass
    return results
