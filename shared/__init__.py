"""Shared package — data types, protocol, constants, and utilities."""

from shared.types import (
    ClawShellEvent, Task, Skill, EdgeNode, Insight, Broadcast,
    TaskStatus, TaskPriority, NodeStatus, EventCategory,
)
from shared.protocol import (
    format_api_response, parse_api_request,
    format_ws_frame, validate_ws_frame,
    format_event_file, format_health_report,
)
from shared.constants import (
    DEFAULT_CLOUD_API_PORT, DEFAULT_CLOUD_WS_PORT,
    DEFAULT_EDGE_MCP_PORT, EDGE_SYNC_INTERVAL,
    HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT,
    EVENT_EXPIRY_DAYS, OFFLINE_QUEUE_MAX, OFFLINE_QUEUE_TRIM,
    API_V1_PREFIX, WS_EVENTS_PATH,
)
from shared.utils import (
    content_hash, timestamp_now, safe_json_dumps, safe_json_loads,
    validate_node_id, generate_node_id, match_wildcard,
)

__all__ = [
    # types
    "ClawShellEvent", "Task", "Skill", "EdgeNode", "Insight", "Broadcast",
    "TaskStatus", "TaskPriority", "NodeStatus", "EventCategory",
    # protocol
    "format_api_response", "parse_api_request",
    "format_ws_frame", "validate_ws_frame",
    "format_event_file", "format_health_report",
    # constants
    "DEFAULT_CLOUD_API_PORT", "DEFAULT_CLOUD_WS_PORT",
    "DEFAULT_EDGE_MCP_PORT", "EDGE_SYNC_INTERVAL",
    "HEARTBEAT_INTERVAL", "HEARTBEAT_TIMEOUT",
    "EVENT_EXPIRY_DAYS", "OFFLINE_QUEUE_MAX", "OFFLINE_QUEUE_TRIM",
    "API_V1_PREFIX", "WS_EVENTS_PATH",
    # utils
    "content_hash", "timestamp_now", "safe_json_dumps", "safe_json_loads",
    "validate_node_id", "generate_node_id", "match_wildcard",
]
