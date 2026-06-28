#!/usr/bin/env python3
"""
ClawShell Memory MCP Server — STDIO transport
供 Wukong/Hermes 通过 STDIO 访问三层记忆系统。

三层架构:
  1. MemPalace (SQLite+ChromaDB) — 本地语义记忆
  2. MemOS Local (Node/Bun, :18800) — 本地笔记
  3. MemOS Cloud (REST API) — 云端跨设备同步
  4. UnifiedMemoryManager (HNSW) — 本地向量语义搜索

Tools:
  - clawshell_memory_search  — 跨三层搜索记忆
  - clawshell_memory_store   — 存储记忆
  - clawshell_memory_stats   — 记忆系统统计
  - clawshell_memory_consolidate — 合并去重统一记忆
"""

import sys
import os
import json
import sqlite3
import uuid
import time
from datetime import datetime, timezone
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

# UnifiedMemoryManager integration (4th layer)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.memory.unified_manager import UnifiedMemoryManager, MemoryType

# ── Config ────────────────────────────────────────────────────
MEMPALACE_PATH = Path(os.environ.get("MEMPALACE_PATH", os.path.expanduser("~/.mempalace")))
MEMOS_CLOUD_URL = os.environ.get("MEMOS_CLOUD_URL", "https://memos.memtensor.cn/api/openmem/v1")
MEMOS_CLOUD_API_KEY = os.environ.get("MEMOS_CLOUD_API_KEY", "")
# ── Cloud API Key file fallback ─────────────────────────────────
if not MEMOS_CLOUD_API_KEY:
    _key_file = Path(os.path.expanduser('~/.openclaw/.cloud_env'))
    if _key_file.exists():
        for _line in _key_file.read_text().splitlines():
            if _line.startswith('MEMOS_CLOUD_API_KEY='):
                MEMOS_CLOUD_API_KEY = _line.split('=',1)[1].strip()
                break
MEMOS_CLOUD_USER_ID = os.environ.get("MEMOS_CLOUD_USER_ID", "1062695814-580275369")
MEMOS_LOCAL_URL = os.environ.get("MEMOS_LOCAL_URL", "http://127.0.0.1:18800")
CLOUDHUB_URL = os.environ.get("CLAWSHELL_CLOUD_URL", "http://47.239.71.174")  # v1.12.0: 事件推送
NODE_ID = os.environ.get("CLAWSHELL_NODE_ID", f"edge-mem-{uuid.uuid4().hex[:8]}")
UNIFIED_MEMORY_PATH = os.path.expanduser(
    os.environ.get("CLAWSHELL_UNIFIED_MEMORY_PATH", "~/.clawshell/data/unified_memory")
)

http = requests.Session()

# ── UnifiedMemoryManager (lazy singleton) ─────────────────────
_unified_mgr: Optional[UnifiedMemoryManager] = None


def _get_unified_manager() -> Optional[UnifiedMemoryManager]:
    """Return (or create) the global UnifiedMemoryManager instance."""
    global _unified_mgr
    if _unified_mgr is None:
        try:
            persist_base = os.path.join(UNIFIED_MEMORY_PATH, "index")
            os.makedirs(UNIFIED_MEMORY_PATH, exist_ok=True)
            # Try to load existing index; create new if not found
            try:
                _unified_mgr = UnifiedMemoryManager.load(persist_base, persist_path=persist_base)
            except (FileNotFoundError, Exception):
                _unified_mgr = UnifiedMemoryManager(persist_path=persist_base)
        except Exception:
            pass  # Gracefully degrade if HNSW unavailable
    return _unified_mgr


def _publish_memory_event(category: str, content_preview: str, source: str = "memory-mcp"):
    """发布 memory.stored 事件到 CloudHub EventBus，供云枢复盘分析。"""
    try:
        event_id = f"mem-{uuid.uuid4().hex[:12]}"
        http.post(
            f"{CLOUDHUB_URL}/api/v1/events/batch",
            json={"events": [{
                "event_id": event_id,
                "event_type": "memory.stored",
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "category": category,
                    "content_preview": content_preview[:200],
                    "stored_at": time.time(),
                    "node_id": NODE_ID,
                }
            }]},
            timeout=5,
        )
    except Exception:
        pass  # 静默失败，不影响记忆存储本身


def search_mempalace(query: str, limit: int = 10) -> List[dict]:
    """Search MemPalace with hybrid BM25 + Vector ranking (v2.1.1).

    Uses mempalace_bridge for CJK-aware hybrid search when available,
    falls back to SQLite LIKE search otherwise.
    """
    try:
        from .mempalace_bridge import search_hybrid
        return search_hybrid(query, limit=limit)
    except ImportError:
        # Fallback: direct SQLite search
        results = []
        db_path = MEMPALACE_PATH / "knowledge_graph.sqlite3"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                try:
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
                        })
                except Exception:
                    pass
                conn.close()
            except Exception:
                pass
        return results


def search_memos_cloud(query: str, limit: int = 10) -> List[dict]:
    """Search MemOS Cloud API (Token auth, POST /search/memory)."""
    results = []
    if MEMOS_CLOUD_API_KEY:
        try:
            r = http.post(
                f"{MEMOS_CLOUD_URL}/search/memory",
                json={"user_id": MEMOS_CLOUD_USER_ID, "query": query, "limit": limit},
                headers={
                    "Authorization": f"Token {MEMOS_CLOUD_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if r.ok:
                data = r.json()
                items = data.get("results", data.get("data", []))
                if isinstance(items, list):
                    for item in items:
                        results.append({
                            "source": "memos_cloud",
                            "content": str(item.get("content", item))[:300],
                            "key": str(item.get("id", "")),
                        })
        except Exception:
            pass
    return results


def search_memos_local(query: str, limit: int = 10) -> List[dict]:
    """Search MemOS Local Bridge API (port 18800)."""
    results = []
    try:
        r = http.get(
            f"{MEMOS_LOCAL_URL}/api/search",
            params={"q": query, "limit": limit},
            timeout=5,
        )
        if r.ok:
            data = r.json()
            for item in data.get("results", []):
                results.append({
                    "source": "memos_local",
                    "content": str(item.get("content", ""))[:300],
                    "key": item.get("key", ""),
                })
    except Exception:
        pass
    return results


# ── Unified Memory (4th layer) helpers ───────────────────────

# Map category strings to MemoryType for classification
_CATEGORY_TO_MEMORY_TYPE: Dict[str, MemoryType] = {
    "fact": MemoryType.SEMANTIC,
    "knowledge": MemoryType.SEMANTIC,
    "semantic": MemoryType.SEMANTIC,
    "event": MemoryType.EPISODIC,
    "episode": MemoryType.EPISODIC,
    "episodic": MemoryType.EPISODIC,
    "howto": MemoryType.PROCEDURAL,
    "procedure": MemoryType.PROCEDURAL,
    "procedural": MemoryType.PROCEDURAL,
    "skill": MemoryType.PROCEDURAL,
    "working": MemoryType.WORKING,
    "temp": MemoryType.CACHE,
    "cache": MemoryType.CACHE,
}


def _classify_category(category: str) -> MemoryType:
    """Map a category string to a MemoryType enum value."""
    return _CATEGORY_TO_MEMORY_TYPE.get(category.lower().strip(), MemoryType.SEMANTIC)


def search_unified(query: str, limit: int = 10) -> List[dict]:
    """Search the UnifiedMemoryManager (HNSW-powered)."""
    results: List[dict] = []
    mgr = _get_unified_manager()
    if mgr is None:
        return results
    try:
        hits = mgr.search(query, k=limit)
        for hit in hits:
            entry = hit.memory
            results.append({
                "source": "unified",
                "key": entry.key,
                "content": entry.content[:300],
                "type": entry.memory_type.value,
                "score": round(hit.final_score, 4),
            })
    except Exception:
        pass
    return results


def _deduplicate_results(results: List[dict]) -> List[dict]:
    """Remove near-duplicate results across sources by content similarity.

    Uses simple normalised content comparison.  When two results from
    different sources have very similar content (>90% overlap of the
    shorter string), keep the one with the higher score (or the first
    occurrence).
    """
    if not results:
        return results

    def _norm(s: str) -> str:
        return " ".join(s.lower().split())

    def _overlap(a: str, b: str) -> float:
        """Simple character-level overlap ratio."""
        if not a or not b:
            return 0.0
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        # Check if shorter is a substring of longer
        if shorter in longer:
            return 1.0
        # Count common words
        words_a = set(shorter.split())
        words_b = set(longer.split())
        if not words_a:
            return 0.0
        common = words_a & words_b
        return len(common) / len(words_a)

    deduped: List[dict] = []
    seen_contents: List[str] = []
    for r in results:
        nc = _norm(r.get("content", ""))
        is_dup = False
        for sc in seen_contents:
            if _overlap(nc, sc) > 0.9:
                is_dup = True
                break
        if not is_dup:
            deduped.append(r)
            seen_contents.append(nc)
    return deduped


# ── Tools ─────────────────────────────────────────────────────

def tool_memory_search(args: dict) -> dict:
    query = args.get("query", args.get("q", ""))
    limit = args.get("limit", 10)
    if not query:
        return {"error": "query is required"}

    results = []
    results.extend(search_mempalace(query, limit))
    results.extend(search_memos_cloud(query, limit))
    results.extend(search_memos_local(query, limit))
    results.extend(search_unified(query, limit))

    # Deduplicate across sources
    results = _deduplicate_results(results)

    return {
        "query": query,
        "total": len(results),
        "sources": {
            "mempalace": sum(1 for r in results if r["source"] == "mempalace"),
            "memos_cloud": sum(1 for r in results if r["source"] == "memos_cloud"),
            "memos_local": sum(1 for r in results if r["source"] == "memos_local"),
            "unified": sum(1 for r in results if r["source"] == "unified"),
        },
        "results": results,
    }


def tool_memory_store(args: dict) -> dict:
    content = args.get("content", "")
    category = args.get("category", "general")
    if not content:
        return {"error": "content is required"}

    stored = []

    # Store to MemPalace
    db_path = MEMPALACE_PATH / "knowledge_graph.sqlite3"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "INSERT OR REPLACE INTO entities (name, type, properties, created_at) VALUES (?, ?, ?, datetime('now'))",
                (f"mcp_{category}", "memory", content),
            )
            conn.commit()
            conn.close()
            stored.append("mempalace")
        except Exception:
            pass

    # Store to MemOS Cloud (Token auth, POST /message)
    # Note: Write operations may return 500 if API key has read-only permissions
    if MEMOS_CLOUD_API_KEY:
        try:
            r = http.post(
                f"{MEMOS_CLOUD_URL}/message",
                json={"user_id": MEMOS_CLOUD_USER_ID, "content": content, "role": "user"},
                headers={
                    "Authorization": f"Token {MEMOS_CLOUD_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if r.ok:
                stored.append("memos_cloud")
            # Silently skip on auth/permission errors (403=forbidden, 500=server error)
            # MemOS Cloud store is best-effort; MemPalace is the authoritative store
        except Exception:
            pass

    # v1.12.0: 推送记忆事件到 CloudHub，供云枢复盘
    if stored:
        _publish_memory_event(category, content[:200], source=NODE_ID)

    # Store to UnifiedMemoryManager (4th layer)
    mgr = _get_unified_manager()
    if mgr is not None:
        try:
            mem_type = _classify_category(category)
            mgr.store(
                key=f"mcp_{category}_{uuid.uuid4().hex[:8]}",
                content=content,
                memory_type=mem_type,
                tags=[category],
                importance=0.6,
                metadata={"source": "memory-mcp", "category": category},
            )
            stored.append("unified")
        except Exception:
            pass  # Best-effort; don't fail the store

    return {"stored_to": stored, "content_preview": content[:100]}


def tool_memory_stats(args: dict) -> dict:
    stats = {"mempalace": {}, "memos_cloud": "unknown", "memos_local": "unknown"}

    # v2.1.1: Use bridge for detailed MemPalace stats
    try:
        from .mempalace_bridge import get_stats as bridge_stats
        mp_stats = bridge_stats()
        stats["mempalace"] = mp_stats
    except ImportError:
        # Fallback: direct SQLite check
        db_path = MEMPALACE_PATH / "knowledge_graph.sqlite3"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
                conn.close()
                stats["mempalace"] = {"entries": count, "path": str(db_path), "engine": "sqlite_like"}
            except Exception:
                stats["mempalace"] = {"error": "read failed"}

    try:
        r = http.get(f"{MEMOS_LOCAL_URL}/health", timeout=5)
        stats["memos_local"] = r.json() if r.ok else "unhealthy"
    except Exception:
        stats["memos_local"] = "unreachable"

    if MEMOS_CLOUD_API_KEY:
        try:
            r = http.post(
                f"{MEMOS_CLOUD_URL}/search/memory",
                json={"user_id": MEMOS_CLOUD_USER_ID, "query": "health_check", "limit": 1},
                headers={
                    "Authorization": f"Token {MEMOS_CLOUD_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if r.ok:
                stats["memos_cloud"] = "connected"
            elif r.status_code == 400:
                stats["memos_cloud"] = "connected (API OK — no memories yet)"
            elif r.status_code == 500:
                stats["memos_cloud"] = "degraded (server error)"
            else:
                stats["memos_cloud"] = f"error (HTTP {r.status_code})"
        except Exception:
            stats["memos_cloud"] = "unreachable"

    return stats


def tool_memory_consolidate(args: dict) -> dict:
    """Trigger consolidation on the UnifiedMemoryManager.

    Runs expire → deduplicate → evict housekeeping.
    """
    mgr = _get_unified_manager()
    if mgr is None:
        return {"error": "UnifiedMemoryManager not available"}
    try:
        summary = mgr.consolidate()
        return {
            "status": "ok",
            "entries_after": mgr.size,
            "consolidation": summary,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Tool Registry ─────────────────────────────────────────────

TOOLS = {
    "clawshell_memory_search": {
        "description": "跨三层记忆系统搜索(MemPalace→MemOS Local→MemOS Cloud)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回数量限制", "default": 10},
            },
            "required": ["query"],
        },
        "handler": tool_memory_search,
    },
    "clawshell_memory_store": {
        "description": "存储记忆到 MemPalace + MemOS Cloud",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "记忆内容"},
                "category": {"type": "string", "description": "分类标签", "default": "general"},
            },
            "required": ["content"],
        },
        "handler": tool_memory_store,
    },
    "clawshell_memory_stats": {
        "description": "获取三层记忆系统统计信息",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_memory_stats,
    },
    "clawshell_memory_consolidate": {
        "description": "合并去重统一记忆(HNSW层): 过期清理、重复合并、容量淘汰",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_memory_consolidate,
    },
}


# ── JSON-RPC Handler ──────────────────────────────────────────

def handle_request(msg: dict) -> Optional[dict]:
    method = msg.get("method", "")
    req_id = msg.get("id")
    params = msg.get("params", {})

    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "clawshell-memory", "version": "2.1.1"},
                },
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            tools = [{"name": n, "description": i["description"], "inputSchema": i["inputSchema"]}
                     for n, i in TOOLS.items()]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
        elif method == "tools/call":
            name = params.get("name", "")
            tool = TOOLS.get(name)
            if not tool:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}
            result = tool["handler"](params.get("arguments", {}))
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}}
        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown: {method}"}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}


def main():
    sys.stderr.write("[clawshell-memory-mcp] Starting v2.1.1\n")
    sys.stderr.flush()
    buffer = ""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            buffer += line
            try:
                msg = json.loads(buffer)
                buffer = ""
            except json.JSONDecodeError:
                continue
        resp = handle_request(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
