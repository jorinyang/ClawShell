"""Wire protocol definitions for ClawShell Cloud↔Edge communication.

Primary: REST API (HTTPS JSON)
Realtime: WebSocket JSON frames
Fallback: Filesystem EventBus (JSON files)
"""

from __future__ import annotations
from typing import Any, Dict, Optional


# ── REST API Protocol ────────────────────────────────

def format_api_response(
    success: bool,
    data: Any = None,
    error: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Standard API response envelope."""
    resp = {"success": success}
    if data is not None:
        resp["data"] = data
    if error is not None:
        resp["error"] = error
    if meta is not None:
        resp["meta"] = meta
    return resp


def parse_api_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize incoming API request body."""
    return {k: v for k, v in body.items() if not k.startswith("_")}


# ── WebSocket Protocol ───────────────────────────────

WS_FRAME_TYPES = {
    "event_push": "cloud → edge: real-time event delivery",
    "broadcast": "cloud → edge: announcement/best-practice",
    "task_assign": "cloud → edge: task assignment",
    "heartbeat_ack": "cloud → edge: heartbeat acknowledgement",
    "ping": "bidirectional: keepalive",
    "pong": "bidirectional: keepalive response",
    "error": "bidirectional: protocol error",
}


def format_ws_frame(
    frame_type: str,
    payload: Any,
    message_id: Optional[str] = None
) -> Dict[str, Any]:
    """Format a WebSocket JSON frame."""
    import time
    import uuid
    return {
        "type": frame_type,
        "id": message_id or str(uuid.uuid4()),
        "timestamp": time.time(),
        "payload": payload,
    }


def validate_ws_frame(frame: Dict[str, Any]) -> bool:
    """Validate a WebSocket frame structure."""
    required = ["type", "payload"]
    return all(k in frame for k in required)


# ── Filesystem EventBus Protocol ─────────────────────

EVENT_FILE_TEMPLATE = """{
    "event_id": "{event_id}",
    "event_type": "{event_type}",
    "source": "{source}",
    "timestamp": {timestamp},
    "payload": {payload}
}
"""


def format_event_file(event_id: str, event_type: str, source: str,
                      payload: Dict[str, Any], timestamp: float) -> str:
    """Format an EventBus JSON file content."""
    import json
    return json.dumps({
        "event_id": event_id,
        "event_type": event_type,
        "source": source,
        "timestamp": timestamp,
        "payload": payload,
    }, ensure_ascii=False, indent=2)


# ── Health Report Protocol ───────────────────────────

def format_health_report(
    node_id: str,
    cpu_percent: float,
    memory_percent: float,
    disk_percent: float,
    services: Dict[str, str],
    uptime_seconds: float,
) -> Dict[str, Any]:
    """Format an Edge health report for Cloud."""
    import time
    return {
        "node_id": node_id,
        "timestamp": time.time(),
        "metrics": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
        },
        "services": services,
        "uptime_seconds": uptime_seconds,
    }
