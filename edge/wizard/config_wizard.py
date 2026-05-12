"""Edge Brain config wizard."""

from __future__ import annotations
import os
import json
import uuid
from typing import Dict


class ConfigWizard:
    """Interactive configuration wizard for Edge Brain setup."""

    CONFIG_FILE = "~/.clawshell-edge/config.json"

    def __init__(self):
        self._config_path = os.path.expanduser(self.CONFIG_FILE)

    def load_config(self) -> dict:
        """Load existing config or return defaults."""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path) as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "cloud_url": "http://localhost:8000",
            "edge_token": "",
            "node_id": f"edge-{uuid.uuid4().hex[:8]}",
            "node_name": "",
            "sync_interval": 5,
            "auto_register": True,
            "ecosystem_components": [],
        }

    def save_config(self, config: dict):
        """Save configuration."""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(config, f, indent=2)

    def configure(self, answers: dict) -> dict:
        """Apply configuration from provided answers."""
        config = self.load_config()
        config.update(answers)
        self.save_config(config)
        return config

    def test_connection(self, cloud_url: str, edge_token: str = "") -> dict:
        """Test connection to Cloud Hub."""
        import urllib.request
        import urllib.error

        url = f"{cloud_url.rstrip('/')}/health"
        headers = {}
        if edge_token:
            headers["Authorization"] = f"Bearer {edge_token}"

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            return {
                "success": True,
                "status": resp.status,
                "version": data.get("version", "unknown"),
                "engines": data.get("engines", {}),
            }
        except urllib.error.HTTPError as e:
            return {"success": False, "error": f"HTTP {e.code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
