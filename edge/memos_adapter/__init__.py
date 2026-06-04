"""ClawShell MemOS Cloud Adapter — universal agent memory integration.

Provides:
  - MemOSCloudClient: low-level API client
  - AgentProtocol plugins for 10+ agents
  - MCP server exposing memos_cloud_search/add/status
  - Installer hook for automatic agent config injection

Usage:
  # Python API
  from edge.memos_adapter import MemOSCloudClient
  client = MemOSCloudClient(api_key="mpg-xxx")
  client.search("my query")

  # MCP Server (STDIO)
  python3 -m edge.memos_adapter.mcp_server

  # Installer hook
  from edge.memos_adapter.installer_hook import install_memos_to_all_agents
  install_memos_to_all_agents()
"""

from edge.memos_adapter.api_client import MemOSCloudClient
from edge.memos_adapter.mcp_server import (
    memos_cloud_search,
    memos_cloud_add,
    memos_cloud_status,
)

__all__ = [
    "MemOSCloudClient",
    "memos_cloud_search",
    "memos_cloud_add",
    "memos_cloud_status",
]
