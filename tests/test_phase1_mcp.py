"""Phase 1 tests: Shared MCP types and protocol extensions (v1.8.1).

Tests cover:
- JsonRpcRequest/Response/Notification serialization
- parse_jsonrpc_message dispatching
- MCPMethod/MCPDomain enums
- MCP_FRAME_TYPES completeness
- MCP constants
- Backward compatibility with existing shared modules
"""

import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_all():
    from shared.mcp_types import (
        JsonRpcRequest, JsonRpcResponse, JsonRpcNotification,
        JsonRpcErrors, MCPMethod, MCPDomain,
        MCPTool, MCPAuthFrame, MCPAuthResponse,
        MCPServerCapabilities, MCPClientCapabilities,
        parse_jsonrpc_message,
    )
    from shared.protocol import MCP_FRAME_TYPES, format_api_response
    from shared.constants import (
        MCP_DEFAULT_PORT, MCP_WS_PATH, MCP_REST_PATH,
        JWT_EXPIRY_SECONDS, JWT_ALGORITHM, MCP_PROTOCOL_VERSION,
        EVENT_STORE_ROOT, EVENT_RETENTION_DAYS,
        EVENT_MAX_BATCH_SIZE, DLQ_MAX_SIZE, DLQ_RETRY_DELAY,
    )

    passed, failed = 0, 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  ✅ {name}")
        else:
            failed += 1
            print(f"  ❌ {name}")

    # ── JsonRpcRequest ──
    req = JsonRpcRequest(method="ping")
    parsed = JsonRpcRequest.from_raw(req.to_json())
    check("JsonRpcRequest roundtrip", parsed.method == "ping" and parsed.id == req.id)

    # ── JsonRpcResponse ──
    resp = JsonRpcResponse.success("1", {"ok": True})
    check("JsonRpcResponse.success not error", not resp.is_error)
    resp_err = JsonRpcResponse.error_response("2", -32600, "Bad")
    check("JsonRpcResponse.error_response", resp_err.is_error and resp_err.error["code"] == -32600)

    # ── JsonRpcNotification ──
    n = JsonRpcNotification(method="notifications/initialized")
    pn = JsonRpcNotification.from_raw(n.to_json())
    check("JsonRpcNotification roundtrip", pn.method == "notifications/initialized")

    # ── parse_jsonrpc_message ──
    for raw, exp_type in [
        ('{"jsonrpc":"2.0","id":"a","method":"m","params":{}}', JsonRpcRequest),
        ('{"jsonrpc":"2.0","id":"a","result":{}}', JsonRpcResponse),
        ('{"jsonrpc":"2.0","method":"n","params":{}}', JsonRpcNotification),
        ("not json", type(None)),
        ('{"not_jsonrpc":true}', type(None)),
    ]:
        result = parse_jsonrpc_message(raw)
        check(f"parse {exp_type.__name__ if exp_type else 'None'}", isinstance(result, exp_type))

    # ── MCP Enums ──
    for method_name in ["INITIALIZE", "TOOLS_LIST", "TOOLS_CALL", "PING"]:
        check(f"MCPMethod.{method_name}", hasattr(MCPMethod, method_name))

    for domain_name in ["VAULT", "SKILL", "KANBAN", "MEMORY", "NODE", "WORKFLOW", "GENOME"]:
        check(f"MCPDomain.{domain_name}", hasattr(MCPDomain, domain_name))

    # ── MCP_FRAME_TYPES ──
    for key in ["auth", "auth_ok", "auth_error", "mcp_request", "mcp_response",
                "mcp_notification", "ping", "pong"]:
        check(f"MCP_FRAME_TYPES[{key}]", key in MCP_FRAME_TYPES)

    # ── Constants ──
    check("MCP_DEFAULT_PORT", MCP_DEFAULT_PORT == 8443)
    check("MCP_WS_PATH", MCP_WS_PATH == "/mcp/ws")
    check("JWT_EXPIRY_SECONDS", JWT_EXPIRY_SECONDS == 3600)
    check("JWT_ALGORITHM", JWT_ALGORITHM == "HS256")
    check("MCP_PROTOCOL_VERSION", MCP_PROTOCOL_VERSION == "2024-11-05")
    check("EVENT_STORE_ROOT", EVENT_STORE_ROOT == "data/event_store")
    check("EVENT_MAX_BATCH_SIZE", EVENT_MAX_BATCH_SIZE == 100)
    check("DLQ_MAX_SIZE", DLQ_MAX_SIZE == 1000)
    check("DLQ_RETRY_DELAY", DLQ_RETRY_DELAY == 60)

    # ── JSON-RPC Error codes ──
    check("PARSE_ERROR", JsonRpcErrors.PARSE_ERROR == -32700)
    check("METHOD_NOT_FOUND", JsonRpcErrors.METHOD_NOT_FOUND == -32601)
    check("INTERNAL_ERROR", JsonRpcErrors.INTERNAL_ERROR == -32603)

    # ── MCP data classes ──
    tool = MCPTool(name="t", description="d", inputSchema={"type": "object"})
    check("MCPTool.to_dict", tool.to_dict()["name"] == "t")

    auth = MCPAuthFrame(token="jwt")
    check("MCPAuthFrame", auth.type == "auth")

    caps = MCPServerCapabilities(tools={"listChanged": True})
    check("MCPServerCapabilities", caps.tools["listChanged"] is True)

    client_caps = MCPClientCapabilities(roots={"listChanged": True})
    check("MCPClientCapabilities", client_caps.roots["listChanged"] is True)

    # ── Backward compatibility ──
    resp = format_api_response(True, data={"k": "v"})
    check("format_api_response", resp["success"] and resp["data"]["k"] == "v")

    # ── Shared __init__ exports ──
    import shared
    check("shared exports MCP_DEFAULT_PORT", hasattr(shared, "MCP_DEFAULT_PORT"))
    check("shared exports JsonRpcRequest", hasattr(shared, "JsonRpcRequest"))
    check("shared exports MCP_FRAME_TYPES", hasattr(shared, "MCP_FRAME_TYPES"))
    check("shared exports parse_jsonrpc_message", hasattr(shared, "parse_jsonrpc_message"))

    print(f"\n── Phase 1 Summary: {passed} passed, {failed} failed ──")
    return failed == 0


if __name__ == "__main__":
    ok = test_all()
    sys.exit(0 if ok else 1)
