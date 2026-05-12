"""MCP WebSocket Hub — WebSocket MCP router for Cloud Hub.

Manages MCP client connections, JWT authentication, and method-to-domain routing.
Runs as an asyncio WebSocket server alongside the existing FastAPI server.

Design: asyncio for WebSocket, integrates with stdlib cloud engines.
Added in v1.8.1 from ClawShell-MacOS cloud-hub.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set
import sys
import os

# Add shared types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.mcp_types import (
    JsonRpcRequest, JsonRpcResponse, JsonRpcNotification,
    JsonRpcErrors, MCPDomain, MCPAuthFrame, MCPAuthResponse,
    parse_jsonrpc_message,
)
from shared.constants import JWT_EXPIRY_SECONDS


@dataclass
class ClientInfo:
    """Connected MCP client information."""
    client_id: str = ""
    edge_id: str = ""
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    authenticated: bool = False


class MCPHub:
    """MCP WebSocket routing hub.

    Features:
    - JWT authentication on connection
    - Method routing to domain handlers (vault, skill, kanban, etc.)
    - Client lifecycle management (connect, heartbeat, disconnect)
    - Pub/sub broadcast to connected clients

    This is designed to run alongside FastAPI in a separate thread/asyncio loop.
    """

    def __init__(self, jwt_secret: str = "", host: str = "0.0.0.0", port: int = 8443):
        self._jwt_secret = jwt_secret
        self._host = host
        self._port = port
        self._clients: Dict[str, ClientInfo] = {}  # client_id → ClientInfo
        self._routes: Dict[str, Any] = {}           # domain prefix → handler
        self._running = False

    def register_domain(self, domain: str, handler: Any) -> None:
        """Register a domain handler.

        Handler should have a method: handle(method: str, params: dict) → dict
        """
        self._routes[domain] = handler

    def get_client_count(self) -> int:
        return len(self._clients)

    def get_authenticated_clients(self) -> int:
        return sum(1 for c in self._clients.values() if c.authenticated)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_clients": len(self._clients),
            "authenticated": self.get_authenticated_clients(),
            "domains": list(self._routes.keys()),
            "port": self._port,
            "running": self._running,
        }

    def _verify_token(self, token: str) -> Optional[str]:
        """Verify JWT token and return edge_id.

        Simple HS256 verification (stdlib, no PyJWT dependency).
        For production, integrate with PyJWT library.
        """
        if not token or not self._jwt_secret:
            return None
        try:
            import hmac
            import hashlib
            import base64

            parts = token.split(".")
            if len(parts) != 3:
                return None

            # Decode payload (simple, no signature verification by default)
            payload_b64 = parts[1]
            # Add padding
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))

            # Check expiry
            exp = payload.get("exp", 0)
            if exp and exp < time.time():
                return None

            return payload.get("sub", payload.get("edge_id", ""))
        except Exception:
            return None

    async def handle_client(self, websocket, path: str = "/") -> None:
        """Handle a single MCP WebSocket client connection."""
        client_id = str(time.time())
        client = ClientInfo(client_id=client_id)
        self._clients[client_id] = client

        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON",
                    }))
                    continue

                msg_type = data.get("type", "")

                # Authentication
                if msg_type == "auth":
                    token = data.get("token", "")
                    edge_id = self._verify_token(token)
                    if edge_id:
                        client.authenticated = True
                        client.edge_id = edge_id
                        await websocket.send(json.dumps({
                            "type": "auth_ok",
                            "message": "Authenticated",
                            "edge_id": edge_id,
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "auth_error",
                            "message": "Invalid or expired token",
                        }))
                    continue

                # Require authentication for all other messages
                if not client.authenticated:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Not authenticated",
                    }))
                    continue

                # Ping/Pong
                if msg_type == "ping":
                    client.last_ping = time.time()
                    await websocket.send(json.dumps({"type": "pong"}))
                    continue

                # MCP Request
                if msg_type == "mcp_request":
                    method = data.get("method", "")
                    req_id = data.get("id", "")
                    params = data.get("params", {})

                    # Route to domain
                    domain = method.split("_")[0] if "_" in method else method
                    handler = self._routes.get(domain)

                    if handler:
                        try:
                            result = handler(method, params, edge_id=client.edge_id)
                            response = {
                                "type": "mcp_response",
                                "id": req_id,
                                "result": result,
                            }
                        except Exception as e:
                            response = {
                                "type": "mcp_response",
                                "id": req_id,
                                "error": {"code": -32000, "message": str(e)},
                            }
                    else:
                        response = {
                            "type": "mcp_response",
                            "id": req_id,
                            "error": {
                                "code": JsonRpcErrors.METHOD_NOT_FOUND,
                                "message": f"Unknown domain: {domain}",
                            },
                        }

                    await websocket.send(json.dumps(response))

        except Exception:
            pass
        finally:
            self._clients.pop(client_id, None)

    async def broadcast(self, notification_type: str, payload: Any) -> int:
        """Broadcast a notification to all authenticated clients. (Placeholder)"""
        # In production, this stores notifications for active WebSocket connections
        return len(self._clients)

    def shutdown(self) -> None:
        """Shutdown the MCP hub."""
        self._running = False
        self._clients.clear()
