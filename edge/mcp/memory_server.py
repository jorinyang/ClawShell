#!/usr/bin/env python3
"""
ClawShell Memory MCP Server — STDIO transport
供 Wukong/Hermes 通过 STDIO 访问三层记忆系统。

三层架构:
  1. MemPalace (SQLite+ChromaDB) — 本地语义记忆
  2. MemOS Local (Node/Bun, :18800) — 本地笔记
  3. MemOS Cloud (REST API) — 云端跨设备同步

Tools:
  - clawshell_memory_search  — 跨三层搜索记忆
  - clawshell_memory_store   — 存储记忆
  - clawshell_memory_stats   — 记忆系统统计
"""

import sys
import os
import json
import sqlite3
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Config ────────────────────────────────────────────────────
MEMPALACE_PATH = Path(os.environ.get("MEMPALACE_PATH", os.path.expanduser("~/.mempalace")))
MEMOS_CLOUD_URL = os.environ.get("MEMOS_CLOUD_URL", "https://memos.memtensor.cn/api/openmem/v1")
MEMOS_CLOUD_API_KEY = os.environ.get("MEMOS_CLOUD_API_KEY", "")
MEMOS_CLOUD_USER_ID = os.environ.get("MEMOS_CLOUD_USER_ID", "1062695814-580275369")
MEMOS_LOCAL_URL = os.environ.get("MEMOS_LOCAL_URL", "http://127.0.0.1:18800")

http = requests.Session()


def search_mempalace(query: str, limit: int = 10) -> List[dict]:
    """Search MemPalace knowledge graph + ChromaDB."""
    results = []
    db_path = MEMPALACE_PATH / "knowledge_graph.sqlite3"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            # Try entities table
            try:
                rows = conn.execute(
                    "SELECT name, type, properties FROM entities WHERE name LIKE ? OR properties LIKE ? LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit)
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

    return {
        "query": query,
        "total": len(results),
        "sources": {
            "mempalace": sum(1 for r in results if r["source"] == "mempalace"),
            "memos_cloud": sum(1 for r in results if r["source"] == "memos_cloud"),
            "memos_local": sum(1 for r in results if r["source"] == "memos_local"),
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
        except Exception:
            pass

    return {"stored_to": stored, "content_preview": content[:100]}


def tool_memory_stats(args: dict) -> dict:
    stats = {"mempalace": {}, "memos_cloud": "unknown", "memos_local": "unknown"}

    db_path = MEMPALACE_PATH / "knowledge_graph.sqlite3"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            conn.close()
            stats["mempalace"] = {"entries": count, "path": str(db_path)}
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
                    "serverInfo": {"name": "clawshell-memory", "version": "1.12.0"},
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
    sys.stderr.write("[clawshell-memory-mcp] Starting v1.12.0\n")
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
