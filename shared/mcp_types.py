"""MCP (Model Context Protocol) type definitions for ClawShell 2.0.

Implements JSON-RPC 2.0 as required by the MCP specification.
Coexists with existing REST protocol in shared/protocol.py.

Added in v1.8.1 — cross-repo fusion from ClawShell-MacOS.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from enum import Enum
import json
import uuid


# ── JSON-RPC 2.0 Base Types ────────────────────────

@dataclass
class JsonRpcRequest:
    """MCP/JSON-RPC 2.0 request object."""
    jsonrpc: str = "2.0"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: str = ""
    params: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, data: dict) -> "JsonRpcRequest":
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id", str(uuid.uuid4())),
            method=data.get("method", ""),
            params=data.get("params", {}),
        )

    @classmethod
    def from_raw(cls, raw: str) -> "JsonRpcRequest":
        return cls.from_json(json.loads(raw))


@dataclass
class JsonRpcResponse:
    """MCP/JSON-RPC 2.0 response object."""
    jsonrpc: str = "2.0"
    id: str = ""
    result: Any = None
    error: Optional[dict] = None

    def to_json(self) -> str:
        d = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return json.dumps(d, ensure_ascii=False, default=str)

    @classmethod
    def success(cls, req_id: str, result: Any) -> "JsonRpcResponse":
        return cls(id=req_id, result=result)

    @classmethod
    def error_response(cls, req_id: str, code: int, message: str,
              data: Any = None) -> "JsonRpcResponse":
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return cls(id=req_id, error=err)

    @property
    def is_error(self) -> bool:
        return self.error is not None


@dataclass
class JsonRpcNotification:
    """MCP/JSON-RPC 2.0 notification (no id, no response)."""
    jsonrpc: str = "2.0"
    method: str = ""
    params: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)

    @classmethod
    def from_raw(cls, raw: str) -> "JsonRpcNotification":
        data = json.loads(raw)
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            method=data.get("method", ""),
            params=data.get("params", {}),
        )


# ── JSON-RPC 2.0 Error Codes ───────────────────────

class JsonRpcErrors:
    """Standard JSON-RPC 2.0 error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Server errors (implementation-defined)
    SERVER_ERROR_START = -32000
    SERVER_NOT_INITIALIZED = -32002
    UNKNOWN_ERROR = -32001


# ── MCP Protocol Constants ─────────────────────────

class MCPMethod(str, Enum):
    """Standard MCP method names per spec 2024-11-05."""
    INITIALIZE = "initialize"
    INITIALIZED = "notifications/initialized"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_TEMPLATES = "resources/templates/list"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    PING = "ping"
    COMPLETION = "completion/complete"
    SET_LEVEL = "logging/setLevel"


class MCPDomain(str, Enum):
    """ClawShell MCP domain routing prefixes.

    Based on ClawShell-MacOS SPEC.md domain routing table.
    """
    VAULT = "vault"        # Obsidian Vault CRUD
    SKILL = "skill"        # Skill registry
    KANBAN = "kanban"      # Task kanban
    MEMORY = "memory"      # Memory management
    NODE = "node"          # Node management
    WORKFLOW = "workflow"  # Workflow engine
    GENOME = "genome"      # Knowledge genome


# ── MCP-Specific Types ─────────────────────────────

@dataclass
class MCPTool:
    """MCP tool descriptor."""
    name: str = ""
    description: str = ""
    inputSchema: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MCPAuthFrame:
    """Authentication frame for MCP WebSocket connection.

    Sent as first frame after WebSocket upgrade.
    """
    type: str = "auth"
    token: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_raw(cls, raw: str) -> "MCPAuthFrame":
        data = json.loads(raw)
        return cls(
            type=data.get("type", "auth"),
            token=data.get("token", ""),
        )


@dataclass
class MCPAuthResponse:
    """Authentication response frame."""
    type: str = ""          # "auth_ok" or "auth_error"
    message: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class MCPServerCapabilities:
    """MCP server capabilities declaration (per spec)."""
    tools: dict = field(default_factory=dict)     # {"listChanged": True}
    resources: dict = field(default_factory=dict)  # {"subscribe": True, "listChanged": True}
    prompts: dict = field(default_factory=dict)    # {"listChanged": True}
    logging: dict = field(default_factory=dict)


@dataclass
class MCPClientCapabilities:
    """MCP client capabilities declaration (per spec)."""
    roots: dict = field(default_factory=dict)      # {"listChanged": True}
    sampling: dict = field(default_factory=dict)   # {}


# ── Utility Functions ──────────────────────────────

def parse_jsonrpc_message(raw: str) -> Optional[JsonRpcRequest | JsonRpcNotification | JsonRpcResponse]:
    """Parse a raw JSON string into the appropriate JSON-RPC type.

    Returns None if the message doesn't match any JSON-RPC format.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
        return None

    has_id = "id" in data
    has_method = "method" in data
    has_result = "result" in data or "error" in data

    if has_id and has_method:
        # Request
        return JsonRpcRequest.from_json(data)
    elif has_id and has_result:
        # Response
        resp = JsonRpcResponse(id=data["id"])
        if "error" in data:
            resp.error = data["error"]
        else:
            resp.result = data.get("result")
        return resp
    elif has_method and not has_id:
        # Notification
        return JsonRpcNotification(method=data["method"], params=data.get("params", {}))
    else:
        return None
