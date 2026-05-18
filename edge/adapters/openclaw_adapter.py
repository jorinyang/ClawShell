"""OpenClaw framework adapter — inject ClawShell into OpenClaw.

OpenClaw uses event-driven architecture with skills loader.
This adapter hooks into OpenClaw's event system.
"""

import os
import json
from typing import Optional
from edge.adapters.base import BaseAdapter


class OpenClawAdapter(BaseAdapter):
    """Adapter for OpenClaw framework."""

    FRAMEWORK_NAME = "openclaw"

    def detect(self) -> bool:
        """Detect if OpenClaw is installed."""
        paths = [
            os.path.expanduser("~/.openclaw"),
            os.path.expanduser("~/.openclaw/config.json"),
            "/opt/openclaw",
        ]
        return any(os.path.exists(p) for p in paths)

    def inject(self, config: dict) -> bool:
        """Inject ClawShell hooks into OpenClaw.

        Args:
            config: dict with optional keys: cloud_url, token (or edge_token)
        """
        cloud_url = config.get("cloud_url", "")
        token = config.get("token", config.get("edge_token", ""))

        config_dir = os.path.expanduser("~/.openclaw")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

        # Register ClawShell as an event listener
        hooks_file = os.path.join(config_dir, "clawshell_hooks.json")
        hooks = {
            "clawshell": {
                "enabled": True,
                "cloud_url": cloud_url,
                "token": token[:20] + "..." if token else "",
                "event_hooks": [
                    "task.created",
                    "task.completed",
                    "skill.published",
                    "insight.generated",
                ],
                "sync_interval": 5,
            }
        }
        with open(hooks_file, "w") as f:
            json.dump(hooks, f, indent=2)
        return True

    def verify(self) -> dict:
        """Verify injection status."""
        hooks_file = os.path.expanduser("~/.openclaw/clawshell_hooks.json")
        if os.path.exists(hooks_file):
            with open(hooks_file) as f:
                hooks = json.load(f)
            return {"injected": True, "config": hooks.get("clawshell", {})}
        return {"injected": False}

    def rollback(self) -> bool:
        """Remove ClawShell hooks from OpenClaw."""
        hooks_file = os.path.expanduser("~/.openclaw/clawshell_hooks.json")
        if os.path.exists(hooks_file):
            os.remove(hooks_file)
        return True
