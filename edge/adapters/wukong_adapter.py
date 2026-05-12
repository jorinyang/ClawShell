"""Wukong adapter — inject ClawShell into Wukong runtime (~/.real)."""

import os
import json
from edge.adapters.base import BaseAdapter


class WukongAdapter(BaseAdapter):
    FRAMEWORK_NAME = "wukong"

    def __init__(self, runtime_path: str = "~/.real"):
        self._root = os.path.expanduser(runtime_path)

    def detect(self) -> bool:
        return os.path.isdir(self._root)

    def inject(self, config: dict) -> bool:
        """Inject ClawShell MCP server + cron tasks + workspace."""
        try:
            # 1. Register MCP server
            mcp_config = os.path.join(self._root, "mcpServerConfig.json")
            mcp = {}
            if os.path.exists(mcp_config):
                with open(mcp_config) as f:
                    mcp = json.load(f)

            mcp["clawshell-mcp"] = {
                "type": "streamableHttp",
                "url": config.get("cloud_url", "http://localhost:8000") + "/api/v1",
                "description": "ClawShell Cloud Hub MCP Bridge",
            }

            with open(mcp_config, "w") as f:
                json.dump(mcp, f, indent=2)

            # 2. Add edge sync cron task
            cron_file = os.path.join(self._root, "cron_tasks.json")
            cron_tasks = []
            if os.path.exists(cron_file):
                with open(cron_file) as f:
                    cron_tasks = json.load(f)

            cron_tasks.append({
                "name": "clawshell-edge-sync",
                "schedule": "*/5 * * * *",
                "command": f"python3 -m edge.sync.daemon --once",
                "enabled": True,
            })

            with open(cron_file, "w") as f:
                json.dump(cron_tasks, f, indent=2)

            # 3. Create workspace directories
            for d in ["clawshell", "clawshell/inbox", "clawshell/outbox", "clawshell/archive"]:
                os.makedirs(os.path.join(self._root, "workspace", d), exist_ok=True)

            return True
        except Exception:
            return False

    def verify(self) -> dict:
        issues = []
        if not os.path.exists(self._root):
            issues.append("Runtime path not found")

        mcp = os.path.join(self._root, "mcpServerConfig.json")
        if os.path.exists(mcp):
            with open(mcp) as f:
                config = json.load(f)
            if "clawshell-mcp" not in config:
                issues.append("MCP server not registered")
        else:
            issues.append("MCP config not found")

        return {
            "framework": self.FRAMEWORK_NAME,
            "injected": len(issues) == 0,
            "issues": issues,
        }

    def rollback(self) -> bool:
        """Remove ClawShell integration."""
        try:
            # Remove MCP registration
            mcp = os.path.join(self._root, "mcpServerConfig.json")
            if os.path.exists(mcp):
                with open(mcp) as f:
                    config = json.load(f)
                config.pop("clawshell-mcp", None)
                with open(mcp, "w") as f:
                    json.dump(config, f, indent=2)
            return True
        except Exception:
            return False
