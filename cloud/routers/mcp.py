"""MCP Status API — Protocol layer health check."""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/mcp", tags=["mcp"])

@router.get("/status")
async def mcp_status(request: Request):
    """MCP protocol layer status."""
    import sys
    mcp_hub = None
    for mod_name in ("__main__", "cloud.main"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_mcp_hub"):
            mcp_hub = getattr(mod, "_mcp_hub")
            break

    return {
        "protocol": "json-rpc 2.0",
        "transport": "websocket",
        "status": "active" if mcp_hub else "standby",
        "domains": ["memory", "vault", "eventbus", "node", "task", "skill", "system"],
        "version": "3.0.0",
    }
