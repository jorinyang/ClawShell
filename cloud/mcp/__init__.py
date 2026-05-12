"""Cloud MCP — MCP over WebSocket protocol layer for ClawShell 2.0.

Provides JWT-authenticated WebSocket MCP routing for Claude Desktop,
Codex, Cursor, and other MCP-compatible clients.

Modules:
- hub.py: WebSocket MCP router with domain-based method dispatch
- protocol.py: Frame encoding/decoding, method routing table
- auth.py: JWT token generation and verification (HS256)

Added in v1.8.1 from ClawShell-MacOS.
"""

from cloud.mcp.hub import MCPHub, ClientInfo
from cloud.mcp.protocol import (
    resolve_domain, DOMAIN_METHODS,
    create_mcp_response, create_mcp_error, create_notification,
    encode_frame, decode_frame,
)
from cloud.mcp.auth import (
    generate_jwt, verify_jwt, generate_edge_token,
)

__all__ = [
    "MCPHub", "ClientInfo",
    "resolve_domain", "DOMAIN_METHODS",
    "create_mcp_response", "create_mcp_error", "create_notification",
    "encode_frame", "decode_frame",
    "generate_jwt", "verify_jwt", "generate_edge_token",
]
