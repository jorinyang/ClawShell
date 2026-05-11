"""WebSocket manager for real-time event push from Cloud to Edges.

Features:
- /ws/events — Edge clients connect and receive real-time events
- WebSocket connection tracking
- Fan-out broadcast to all connected edges
- Event filtering per connection (by event_type)
"""

from __future__ import annotations
import json
import time
import asyncio
import logging
from typing import Dict, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from shared.protocol import format_ws_frame

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manage WebSocket connections and fan-out broadcasts."""

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}  # connection_id → ws
        self._filters: Dict[str, Set[str]] = {}        # connection_id → event_types to receive
        self._lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

    async def connect(self, websocket: WebSocket, conn_id: str,
                      event_filter: Optional[list] = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._connections[conn_id] = websocket
        if event_filter:
            self._filters[conn_id] = set(event_filter)
        else:
            self._filters[conn_id] = {"*"}  # Receive all
        logger.info(f"WebSocket connected: {conn_id} ({len(self._connections)} total)")

    async def disconnect(self, conn_id: str):
        """Handle client disconnect."""
        self._connections.pop(conn_id, None)
        self._filters.pop(conn_id, None)
        logger.info(f"WebSocket disconnected: {conn_id} ({len(self._connections)} total)")

    async def broadcast(self, event: dict, event_type: Optional[str] = None):
        """Push an event to all connected edges that match the filter."""
        etype = event_type or event.get("event_type", "")
        frame = format_ws_frame("event_push", event)

        disconnected = []
        for conn_id, ws in list(self._connections.items()):
            # Check filter
            allowed_types = self._filters.get(conn_id, {"*"})
            if "*" not in allowed_types and etype not in allowed_types:
                continue

            try:
                await ws.send_json(frame)
            except Exception:
                disconnected.append(conn_id)

        # Clean up disconnected clients
        for cid in disconnected:
            await self.disconnect(cid)

    async def send_to(self, conn_id: str, event: dict):
        """Send an event to a specific connection."""
        ws = self._connections.get(conn_id)
        if ws:
            try:
                frame = format_ws_frame("event_push", event)
                await ws.send_json(frame)
            except Exception:
                await self.disconnect(conn_id)

    async def broadcast_message(self, message_type: str, payload: dict):
        """Broadcast a typed message to all connections."""
        frame = format_ws_frame(message_type, payload)
        disconnected = []
        for conn_id, ws in list(self._connections.items()):
            try:
                await ws.send_json(frame)
            except Exception:
                disconnected.append(conn_id)
        for cid in disconnected:
            await self.disconnect(cid)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def list_connections(self) -> list:
        return list(self._connections.keys())


# Global manager instance
ws_manager = WebSocketManager()


def setup_websocket(app: FastAPI, eventbus=None):
    """Register WebSocket endpoint on the FastAPI app."""

    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket):
        """WebSocket endpoint for real-time event push."""
        import uuid
        conn_id = str(uuid.uuid4())[:8]

        # Accept connection
        await websocket.accept()
        ws_manager._connections[conn_id] = websocket
        ws_manager._filters[conn_id] = {"*"}

        # Send welcome
        await websocket.send_json(format_ws_frame("welcome", {
            "connection_id": conn_id,
            "message": "Connected to ClawShell Cloud Hub"
        }))

        try:
            while True:
                # Listen for filter updates from edge
                data = await websocket.receive_json()
                msg_type = data.get("type", "")

                if msg_type == "filter":
                    event_types = data.get("event_types", ["*"])
                    ws_manager._filters[conn_id] = set(event_types)
                    await websocket.send_json(format_ws_frame("ack", {
                        "filter_updated": list(event_types)
                    }))
                elif msg_type == "ping":
                    await websocket.send_json(format_ws_frame("pong", {
                        "timestamp": time.time()
                    }))

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning(f"WebSocket error {conn_id}: {e}")
        finally:
            await ws_manager.disconnect(conn_id)
