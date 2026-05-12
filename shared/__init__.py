"""Shared package — data types, protocol, constants, and utilities."""

from shared.types import (
    ClawShellEvent, Task, Skill, EdgeNode, Insight, Broadcast,
    TaskStatus, TaskPriority, NodeStatus, EventCategory,
)
from shared.protocol import (
    format_api_response, parse_api_request,
    format_ws_frame, validate_ws_frame,
    format_event_file, format_health_report,
    WS_FRAME_TYPES, MCP_FRAME_TYPES,
)
from shared.constants import (
    DEFAULT_CLOUD_API_PORT, DEFAULT_CLOUD_WS_PORT,
    DEFAULT_EDGE_MCP_PORT, EDGE_SYNC_INTERVAL,
    HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT,
    EVENT_EXPIRY_DAYS, OFFLINE_QUEUE_MAX, OFFLINE_QUEUE_TRIM,
    API_V1_PREFIX, WS_EVENTS_PATH,
    # v1.8.1 MCP + EventStore constants
    MCP_DEFAULT_PORT, MCP_WS_PATH, MCP_REST_PATH,
    JWT_EXPIRY_SECONDS, JWT_ALGORITHM, MCP_PROTOCOL_VERSION,
    EVENT_STORE_ROOT, EVENT_RETENTION_DAYS,
    EVENT_MAX_BATCH_SIZE, DLQ_MAX_SIZE, DLQ_RETRY_DELAY,
)
from shared.mcp_types import (
    JsonRpcRequest, JsonRpcResponse, JsonRpcNotification,
    JsonRpcErrors, MCPMethod, MCPDomain,
    MCPTool, MCPAuthFrame, MCPAuthResponse,
    MCPServerCapabilities, MCPClientCapabilities,
    parse_jsonrpc_message,
)
from shared.utils import (
    content_hash, timestamp_now, safe_json_dumps, safe_json_loads,
    validate_node_id, generate_node_id, match_wildcard,
)
# v1.9.0 — Pydantic v2 models (additive, backward compatible)
from shared.models import (
    NodeInfo, NodeHeartbeat, CortexInfo,
    Task as PydanticTask, TaskResult,
    EventMessage, Insight as PydanticInsight,
    Knowledge, Memory,
    Plugin, PluginRegistry,
    HealthReport, RepairAction,
    SystemPerception, NetworkPerception, PerceptionResult,
    SwarmNode,
    CortexConfig, GanglionConfig,
    Strategy, HealthStatus, TrustLevel, RepairLayer,
    CapabilityDomain, PerceptionDimension, OpenClawVariant,
    NodeID, TaskID, PluginID, EventID,
)

__all__ = [
    # types
    "ClawShellEvent", "Task", "Skill", "EdgeNode", "Insight", "Broadcast",
    "TaskStatus", "TaskPriority", "NodeStatus", "EventCategory",
    # protocol
    "format_api_response", "parse_api_request",
    "format_ws_frame", "validate_ws_frame",
    "format_event_file", "format_health_report",
    "WS_FRAME_TYPES", "MCP_FRAME_TYPES",
    # constants
    "DEFAULT_CLOUD_API_PORT", "DEFAULT_CLOUD_WS_PORT",
    "DEFAULT_EDGE_MCP_PORT", "EDGE_SYNC_INTERVAL",
    "HEARTBEAT_INTERVAL", "HEARTBEAT_TIMEOUT",
    "EVENT_EXPIRY_DAYS", "OFFLINE_QUEUE_MAX", "OFFLINE_QUEUE_TRIM",
    "API_V1_PREFIX", "WS_EVENTS_PATH",
    "MCP_DEFAULT_PORT", "MCP_WS_PATH", "MCP_REST_PATH",
    "JWT_EXPIRY_SECONDS", "JWT_ALGORITHM", "MCP_PROTOCOL_VERSION",
    "EVENT_STORE_ROOT", "EVENT_RETENTION_DAYS",
    "EVENT_MAX_BATCH_SIZE", "DLQ_MAX_SIZE", "DLQ_RETRY_DELAY",
    # mcp_types
    "JsonRpcRequest", "JsonRpcResponse", "JsonRpcNotification",
    "JsonRpcErrors", "MCPMethod", "MCPDomain",
    "MCPTool", "MCPAuthFrame", "MCPAuthResponse",
    "MCPServerCapabilities", "MCPClientCapabilities",
    "parse_jsonrpc_message",
    # utils
    "content_hash", "timestamp_now", "safe_json_dumps", "safe_json_loads",
    "validate_node_id", "generate_node_id", "match_wildcard",
]
