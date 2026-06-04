"""MemOS Cloud Adapter — installer integration hook.

Called during ClawShell Edge installation (Phase 4).
Auto-detects installed agents and injects MemOS Cloud MCP config.
"""

from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def install_memos_to_all_agents(api_key: Optional[str] = None,
                                 user_id: str = "clawshell-user",
                                 base_url: Optional[str] = None) -> dict:
    """Install MemOS Cloud MCP to all detected agents.

    Called by ClawShell Edge Installer Phase 4 (ConfigAutoInjector).
    Returns installation report.
    """
    api_key = api_key or os.environ.get("MEMOS_API_KEY", "")
    base_url = base_url or os.environ.get(
        "MEMOS_CLOUD_URL",
        "https://memos.memtensor.cn/api/openmem/v1",
    )

    from edge.memos_adapter.agent_protocols import ALL_PROTOCOLS, inject_to_all

    # Command: python3 -m edge.memos_adapter.mcp_server
    python_cmd = sys.executable
    clawnshell_home = os.environ.get("CLAWSHELL_HOME", str(Path.home() / ".clawshell"))

    server_name = "clawshell-memos-cloud"
    command = python_cmd
    args = ["-m", "edge.memos_adapter.mcp_server"]
    env = {
        "MEMOS_API_KEY": api_key,
        "MEMOS_USER_ID": user_id,
        "MEMOS_CLOUD_URL": base_url,
        "CLAWSHELL_HOME": clawnshell_home,
    }

    injected = inject_to_all(server_name, command, args, env)

    return {
        "server": "clawshell-memos-cloud",
        "tools": ["memos_cloud_search", "memos_cloud_add", "memos_cloud_status"],
        "injected_agents": injected,
        "user_id": user_id,
        "endpoint": base_url,
    }


def install_memos_to_agent(agent_id: str, api_key: Optional[str] = None,
                            user_id: str = "clawshell-user") -> bool:
    """Install MemOS Cloud MCP to a specific agent by ID."""
    api_key = api_key or os.environ.get("MEMOS_API_KEY", "")

    from edge.memos_adapter.agent_protocols import ALL_PROTOCOLS

    python_cmd = sys.executable
    server_name = f"clawshell-memos-cloud"

    for proto in ALL_PROTOCOLS:
        if proto.agent_id == agent_id and proto.detect():
            return proto.inject_mcp(
                server_name,
                command=python_cmd,
                args=["-m", "edge.memos_adapter.mcp_server"],
                env={"MEMOS_API_KEY": api_key, "MEMOS_USER_ID": user_id},
            )
    return False
