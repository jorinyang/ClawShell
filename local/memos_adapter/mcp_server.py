"""Cloud MemOS MCP Server — universal memory tools for ALL agents.

Provides 3 standardized MCP tools that any agent (Hermes, Codex,
Claude Code, Wukong, etc.) can call via STDIO MCP protocol.

Tools:
  memos_cloud_search  — recall memories by query
  memos_cloud_add     — store a message as memory
  memos_cloud_status  — check MemOS Cloud connection
"""

from __future__ import annotations
import os, sys, json, time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from local.memos_adapter.api_client import MemOSCloudClient


def _get_client() -> Optional[MemOSCloudClient]:
    api_key = os.environ.get("MEMOS_API_KEY", "")
    if not api_key:
        return None
    base_url = os.environ.get("MEMOS_CLOUD_URL",
                              "https://memos.memtensor.cn/api/openmem/v1")
    user_id = os.environ.get("MEMOS_USER_ID", "clawshell-user")
    return MemOSCloudClient(api_key=api_key, base_url=base_url, user_id=user_id)


def _error(msg: str) -> dict:
    return {"success": False, "error": msg}


def memos_cloud_search(query: str, conversation_id: str = "",
                       top_k: int = 5) -> dict:
    """Search MemOS Cloud for relevant memories.

    Args:
        query: Search query text
        conversation_id: Optional conversation context
        top_k: Number of results (default 5, max 20)
    """
    client = _get_client()
    if not client:
        return _error("MEMOS_API_KEY not configured. Set env var or .env file.")

    try:
        result = client.search(
            query=query,
            conversation_id=conversation_id,
            top_k=min(top_k, 20),
        )
        records = result.get("records", result.get("data", []))
        return {
            "success": True,
            "total": result.get("total", len(records)),
            "memories": records,
        }
    except Exception as e:
        return _error(str(e))


def memos_cloud_add(role: str, content: str, conversation_id: str = "",
                    metadata: Optional[dict] = None) -> dict:
    """Add a message to MemOS Cloud memory.

    Args:
        role: "user" | "assistant" | "system"
        content: Message text
        conversation_id: Optional conversation grouping
        metadata: Optional key-value tags
    """
    client = _get_client()
    if not client:
        return _error("MEMOS_API_KEY not configured.")

    try:
        result = client.add_message(
            role=role,
            content=content,
            conversation_id=conversation_id,
            metadata=metadata,
        )
        return {"success": True, "result": result}
    except Exception as e:
        return _error(str(e))


def memos_cloud_status() -> dict:
    """Check MemOS Cloud connectivity."""
    client = _get_client()
    if not client:
        return {"connected": False, "reason": "MEMOS_API_KEY not set"}

    ok = client.health()
    return {
        "connected": ok,
        "user_id": client.user_id,
        "endpoint": client.base_url,
    }


# ═══════════════════════════════════════════════════════════════════
# MCP Tool Registry (STDIO compatible)
# ═══════════════════════════════════════════════════════════════════

TOOLS = {
    "memos_cloud_search": {
        "function": memos_cloud_search,
        "description": "Search MemOS Cloud for relevant memories by query",
        "parameters": {
            "query": {"type": "string", "required": True,
                       "description": "Search query"},
            "conversation_id": {"type": "string", "required": False,
                                 "description": "Conversation context"},
            "top_k": {"type": "integer", "required": False,
                       "description": "Max results (default 5)"},
        },
    },
    "memos_cloud_add": {
        "function": memos_cloud_add,
        "description": "Store a message as a memory in MemOS Cloud",
        "parameters": {
            "role": {"type": "string", "required": True,
                      "description": "user | assistant | system"},
            "content": {"type": "string", "required": True,
                         "description": "Message text"},
            "conversation_id": {"type": "string", "required": False,
                                 "description": "Conversation group"},
            "metadata": {"type": "object", "required": False,
                          "description": "Key-value tags"},
        },
    },
    "memos_cloud_status": {
        "function": memos_cloud_status,
        "description": "Check MemOS Cloud connection status",
        "parameters": {},
    },
}


# ── STDIO MCP Server Entry Point ──────────────────────────────────

def serve_stdio():
    """Run as STDIO MCP server — reads JSON-RPC from stdin, writes to stdout."""
    print("[clawshell-memos-mcp] Starting Cloud MemOS MCP Server...",
          file=sys.stderr)
    client = _get_client()
    if client:
        print(f"[clawshell-memos-mcp] Connected: {client.user_id}",
              file=sys.stderr)
    else:
        print("[clawshell-memos-mcp] WARNING: MEMOS_API_KEY not set — "
              "tools will return errors", file=sys.stderr)

    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            method = request.get("method", "")
            req_id = request.get("id")

            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {
                        "tools": [
                            {"name": n, "description": t["description"]}
                            for n, t in TOOLS.items()
                        ]
                    }
                }
            elif method == "tools/call":
                tool_name = request.get("params", {}).get("name", "")
                tool_args = request.get("params", {}).get("arguments", {})
                tool = TOOLS.get(tool_name)
                if tool:
                    result = tool["function"](**tool_args)
                    response = {
                        "jsonrpc": "2.0", "id": req_id,
                        "result": {"content": [{"type": "text",
                                                 "text": json.dumps(result,
                                                                    ensure_ascii=False)}]}
                    }
                else:
                    response = {
                        "jsonrpc": "2.0", "id": req_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                    }
            else:
                response = {
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"}
                }

            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except Exception as e:
            sys.stderr.write(f"[error] {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    serve_stdio()
