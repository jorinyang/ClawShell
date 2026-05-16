#!/usr/bin/env python3
"""
ClawShell Edge MCP Server — STDIO transport
供 Wukong/Hermes 通过 STDIO 调用 ClawShell Edge 能力。

Wukong 配置:
  type: stdio
  command: wsl
  args: [-d, Ubuntu, --, bash, -c, cd ~/.clawshell && python3 -m edge.mcp.edge_server]

提供的 Tools:
  - clawshell_eventbus_publish  — 发布事件到 CloudHub
  - clawshell_eventbus_query    — 查询事件
  - clawshell_eventbus_stats    — 事件总线统计
  - clawshell_sync_push         — 推送本地变更到云端
  - clawshell_sync_pull         — 拉取云端变更到本地
  - clawshell_edge_status       — Edge 状态
  - clawshell_cloud_health      — CloudHub 健康检查
  - clawshell_vault_search      — 搜索 Obsidian Vault
"""

import sys
import os
import json
import uuid
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path setup ─────────────────────────────────────────────────
EDGE_HOME = Path(os.environ.get("CLAWSHELL_EDGE_HOME", os.path.expanduser("~/.clawshell-edge")))
REPO_HOME = Path(os.environ.get("CLAWSHELL_REPO", os.path.expanduser("~/.clawshell")))
sys.path.insert(0, str(REPO_HOME))

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Config ─────────────────────────────────────────────────────
def load_config() -> dict:
    config_path = EDGE_HOME / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}

CONFIG = load_config()
CLOUD_URL = CONFIG.get("cloud_url", os.environ.get("CLAWSHELL_CLOUD_URL", "http://47.239.71.174"))
NODE_ID = CONFIG.get("node_id", os.environ.get("CLAWSHELL_NODE_ID", f"edge-{uuid.uuid4().hex[:8]}"))

# ── HTTP Session ────────────────────────────────────────────────
def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

http = _session()

# ── Tool Implementations ────────────────────────────────────────

def tool_eventbus_publish(args: dict) -> dict:
    """发布事件到 CloudHub EventBus."""
    events = args.get("events", [])
    if not events:
        return {"error": "events is required"}
    try:
        r = http.post(f"{CLOUD_URL}/api/v1/events/batch", json={"events": events}, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def tool_eventbus_query(args: dict) -> dict:
    """查询 CloudHub 事件."""
    params = {}
    for key in ("event_type", "source", "since", "until", "limit"):
        if key in args:
            params[key] = args[key]
    params.setdefault("limit", 50)
    try:
        r = http.get(f"{CLOUD_URL}/api/v1/events/", params=params, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def tool_eventbus_stats(args: dict) -> dict:
    """获取事件总线统计."""
    try:
        r = http.get(f"{CLOUD_URL}/api/v1/events/stats", timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def tool_sync_push(args: dict) -> dict:
    """推送本地变更到 CloudHub OSS."""
    try:
        r = http.post(f"{CLOUD_URL}/api/v1/vault/sync/push", json={}, timeout=120)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

def tool_sync_pull(args: dict) -> dict:
    """拉取 OSS 变更到 CloudHub 本地 Vault."""
    try:
        r = http.post(f"{CLOUD_URL}/api/v1/vault/sync/pull", json={}, timeout=120)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

def tool_edge_status(args: dict) -> dict:
    """获取 Edge 状态."""
    return {
        "node_id": NODE_ID,
        "node_name": CONFIG.get("node_name", "unknown"),
        "cloud_url": CLOUD_URL,
        "version": "v1.12.0",
        "adapters": {
            "hermes": CONFIG.get("adapters", {}).get("hermes", {}).get("enabled", False),
            "wukong": CONFIG.get("adapters", {}).get("wukong", {}).get("enabled", False),
        },
        "config_path": str(EDGE_HOME),
    }

def tool_cloud_health(args: dict) -> dict:
    """CloudHub 健康检查."""
    try:
        r = http.get(f"{CLOUD_URL}/health", timeout=10)
        return r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def tool_vault_search(args: dict) -> dict:
    """搜索 Obsidian Vault (通过 CloudHub Vault API)."""
    query = args.get("query", args.get("q", ""))
    limit = args.get("limit", 10)
    if not query:
        return {"error": "query is required"}
    try:
        r = http.get(f"{CLOUD_URL}/api/v1/vault/search", params={"q": query, "limit": limit}, timeout=15)
        if r.ok:
            return r.json()
        # Fallback to brain semantic search
        r2 = http.post(f"{CLOUD_URL}/api/v1/brain/analyze", json={
            "query": f"Search the Obsidian knowledge vault for: {query}",
            "context": f"Search query: {query}, limit: {limit}"
        }, timeout=30)
        return r2.json() if r2.ok else {"error": r2.text}
    except Exception as e:
        return {"error": str(e)}

# ── NEW: Brain / LLM Analysis ───────────────────────────────
def tool_brain_analyze(args: dict) -> dict:
    """调用 CloudBrain LLM 进行深度分析."""
    query = args.get("query", "")
    context = args.get("context", "")
    if not query:
        return {"error": "query is required"}
    try:
        r = http.post(f"{CLOUD_URL}/api/v1/brain/analyze", json={
            "query": query,
            "context": context
        }, timeout=120)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

def tool_brain_status(args: dict) -> dict:
    """获取 CloudBrain LLM 引擎状态."""
    try:
        r = http.get(f"{CLOUD_URL}/api/v1/brain/status", timeout=10)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

# ── NEW: Node Management ────────────────────────────────────
def tool_nodes_list(args: dict) -> dict:
    """列出所有注册的边缘节点."""
    try:
        r = http.get(f"{CLOUD_URL}/api/v1/nodes/", timeout=10)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

def tool_nodes_register(args: dict) -> dict:
    """注册/更新边缘节点."""
    node_id = args.get("node_id", NODE_ID)
    try:
        r = http.post(f"{CLOUD_URL}/api/v1/nodes/register", json={
            "node_id": node_id,
            "node_name": args.get("node_name", "MCP-Client"),
            "node_type": args.get("node_type", "edge"),
            "capabilities": args.get("capabilities", ["mcp"]),
        }, timeout=10)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

# ── NEW: Task Management ────────────────────────────────────
def tool_tasks_create(args: dict) -> dict:
    """创建任务到全局任务板."""
    # Map priority: int → string enum
    p = args.get("priority", 50)
    if isinstance(p, (int, float)):
        p = "critical" if p >= 90 else "high" if p >= 70 else "medium" if p >= 40 else "low"
    try:
        r = http.post(f"{CLOUD_URL}/api/v1/tasks/", json={
            "title": args.get("title", "Untitled"),
            "description": args.get("description", ""),
            "priority": p,
            "assignee": args.get("assignee", NODE_ID),
            "tags": args.get("tags", []),
        }, timeout=10)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

def tool_tasks_list(args: dict) -> dict:
    """列出/查询任务."""
    params = {}
    for k in ("status", "assignee", "limit"):
        if k in args:
            params[k] = args[k]
    try:
        r = http.get(f"{CLOUD_URL}/api/v1/tasks/", params=params, timeout=10)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

# ── NEW: Skill Market ───────────────────────────────────────
def tool_skills_list(args: dict) -> dict:
    """列出可用技能."""
    params = {}
    if args.get("query"):
        params["q"] = args["query"]
    try:
        r = http.get(f"{CLOUD_URL}/api/v1/skills/", params=params, timeout=10)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

# ── Tool Registry ───────────────────────────────────────────────

TOOLS = {
    "clawshell_eventbus_publish": {
        "description": "发布事件到 ClawShell CloudHub EventBus",
        "inputSchema": {
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "description": "事件列表，每个事件需包含 event_id, event_type, source, timestamp, payload",
                    "items": {"type": "object"}
                }
            },
            "required": ["events"]
        },
        "handler": tool_eventbus_publish,
    },
    "clawshell_eventbus_query": {
        "description": "查询 ClawShell CloudHub 事件(支持按类型/来源/时间过滤)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "事件类型过滤"},
                "source": {"type": "string", "description": "事件来源过滤"},
                "since": {"type": "number", "description": "开始时间(Unix timestamp)"},
                "limit": {"type": "integer", "description": "返回数量限制，默认50", "default": 50}
            }
        },
        "handler": tool_eventbus_query,
    },
    "clawshell_eventbus_stats": {
        "description": "获取 ClawShell EventBus 统计信息(事件总数/类型分布/来源分布)",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_eventbus_stats,
    },
    "clawshell_sync_push": {
        "description": "推送本地 Obsidian Vault 变更到阿里云 OSS",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_sync_push,
    },
    "clawshell_sync_pull": {
        "description": "从阿里云 OSS 拉取 Vault 变更到本地",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_sync_pull,
    },
    "clawshell_edge_status": {
        "description": "获取 ClawShell Edge 端脑状态",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_edge_status,
    },
    "clawshell_cloud_health": {
        "description": "检查 ClawShell CloudHub 云枢健康状态",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_cloud_health,
    },
    "clawshell_vault_search": {
        "description": "语义搜索 Obsidian 知识库(通过 CloudBrain LLM)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词或问题"},
                "limit": {"type": "integer", "description": "返回数量限制", "default": 10}
            },
            "required": ["query"]
        },
        "handler": tool_vault_search,
    },
    "clawshell_brain_analyze": {
        "description": "调用 CloudBrain LLM 进行深度分析/推理/回答",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "分析问题"},
                "context": {"type": "string", "description": "补充上下文信息"}
            },
            "required": ["query"]
        },
        "handler": tool_brain_analyze,
    },
    "clawshell_brain_status": {
        "description": "获取 CloudBrain LLM 引擎运行状态",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_brain_status,
    },
    "clawshell_nodes_list": {
        "description": "列出所有注册到 CloudHub 的边缘节点",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_nodes_list,
    },
    "clawshell_nodes_register": {
        "description": "注册/更新边缘节点到 CloudHub",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "节点ID"},
                "node_name": {"type": "string", "description": "节点名称"},
                "capabilities": {"type": "array", "items": {"type": "string"}}
            }
        },
        "handler": tool_nodes_register,
    },
    "clawshell_tasks_create": {
        "description": "创建任务到 ClawShell 全局任务板",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "任务标题"},
                "description": {"type": "string", "description": "任务描述"},
                "priority": {"type": "integer", "description": "优先级(1-100)"},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["title"]
        },
        "handler": tool_tasks_create,
    },
    "clawshell_tasks_list": {
        "description": "查询 ClawShell 任务板中的任务",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "过滤状态(pending/claimed/completed)"},
                "limit": {"type": "integer", "description": "返回数量限制"}
            }
        },
        "handler": tool_tasks_list,
    },
    "clawshell_skills_list": {
        "description": "列出 ClawShell 技能市场中的可用技能",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词过滤"}
            }
        },
        "handler": tool_skills_list,
    },
}


# ── JSON-RPC Handler ────────────────────────────────────────────

def handle_request(msg: dict) -> dict:
    """Handle a single JSON-RPC request."""
    method = msg.get("method", "")
    req_id = msg.get("id")
    params = msg.get("params", {})

    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "clawshell-edge",
                        "version": "1.12.0"
                    }
                }
            }
        elif method == "notifications/initialized":
            return None  # No response for notifications

        elif method == "tools/list":
            tools = []
            for name, info in TOOLS.items():
                tools.append({
                    "name": name,
                    "description": info["description"],
                    "inputSchema": info["inputSchema"],
                })
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            tool = TOOLS.get(tool_name)
            if not tool:
                return {
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
                }
            result = tool["handler"](tool_args)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]
                }
            }

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        else:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
    except Exception as e:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32603, "message": str(e)}
        }


# ── STDIO Main Loop ─────────────────────────────────────────────

def main():
    """STDIO MCP server main loop."""
    # Log to stderr so stdout stays clean for JSON-RPC
    sys.stderr.write(f"[clawshell-edge-mcp] Starting v1.12.0 | Cloud={CLOUD_URL} | Node={NODE_ID}\n")
    # Auto-register with CloudHub on startup
    try:
        import requests as _r
        _r.post(f"{CLOUD_URL}/api/v1/nodes/register", json={
            "node_id": NODE_ID,
            "node_name": CONFIG.get("node_name", "MCP-Edge"),
            "node_type": "edge",
            "capabilities": ["hermes", "wukong", "mcp"],
            "host": "WSL-MCP-STDIO"
        }, timeout=5)
        sys.stderr.write(f"[clawshell-edge-mcp] Auto-registered with CloudHub\n")
    except Exception:
        pass
    sys.stderr.flush()

    buffer = ""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # Might be partial — accumulate
            buffer += line
            try:
                msg = json.loads(buffer)
                buffer = ""
            except json.JSONDecodeError:
                continue

        response = handle_request(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
