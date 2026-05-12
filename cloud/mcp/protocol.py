"""MCP Protocol — message frame encoding/decoding for MCP over WebSocket.

Handles JSON-RPC 2.0 message framing, method routing table,
and domain prefix conventions.

Added in v1.8.1 from ClawShell-MacOS.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from shared.mcp_types import MCPDomain, JsonRpcResponse, JsonRpcErrors


# ── Domain Routing Table ──────────────────────────

DOMAIN_METHODS = {
    MCPDomain.VAULT.value: [
        "vault_list", "vault_read", "vault_create",
        "vault_update", "vault_delete", "vault_search",
    ],
    MCPDomain.SKILL.value: [
        "skill_list", "skill_get", "skill_publish",
        "skill_search", "skill_install", "skill_version_history",
    ],
    MCPDomain.KANBAN.value: [
        "kanban_task_create", "kanban_task_update", "kanban_task_move",
        "kanban_task_list", "kanban_task_get", "kanban_column_list",
    ],
    MCPDomain.MEMORY.value: [
        "memory_add", "memory_search", "memory_get", "memory_delete",
    ],
    MCPDomain.NODE.value: [
        "node_list", "node_get", "node_register", "node_heartbeat",
    ],
    MCPDomain.WORKFLOW.value: [
        "workflow_list", "workflow_get", "workflow_create",
        "workflow_start", "workflow_status",
    ],
    MCPDomain.GENOME.value: [
        "genome_import", "genome_search", "genome_heritage",
        "genome_version",
    ],
}


def resolve_domain(method: str) -> Optional[str]:
    """Extract domain prefix from method name.

    Examples:
        "vault_list" → "vault"
        "skill_publish" → "skill"
        "unknown_method" → None
    """
    for domain, methods in DOMAIN_METHODS.items():
        if method in methods:
            return domain
    # Fallback: extract prefix before first underscore
    if "_" in method:
        prefix = method.split("_")[0]
        if prefix in DOMAIN_METHODS:
            return prefix
    return None


def create_mcp_response(req_id: str, result: Any = None,
                        error: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a standard MCP response frame."""
    frame = {
        "type": "mcp_response",
        "id": req_id,
    }
    if error:
        frame["error"] = error
    else:
        frame["result"] = result
    return frame


def create_mcp_error(req_id: str, code: int, message: str) -> Dict[str, Any]:
    """Create an MCP error response frame."""
    return create_mcp_response(req_id, error={"code": code, "message": message})


def create_notification(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create an MCP notification frame."""
    return {
        "type": "mcp_notification",
        "method": method,
        "params": params or {},
    }


def encode_frame(frame: Dict[str, Any]) -> str:
    """Encode an MCP frame to JSON string."""
    return json.dumps(frame, ensure_ascii=False)


def decode_frame(raw: str) -> Optional[Dict[str, Any]]:
    """Decode a JSON string to MCP frame."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
