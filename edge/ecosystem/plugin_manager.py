"""PluginManager — Plugin discovery and health checking.

Design inspired by DEEP PluginManager + MacOS v2.1 PluginDomain.
Adapted to Main's edge/ecosystem/ with threading model.

Builtin plugins: n8n, MemOS, ComfyUI, Ollama, OpenClaw Skills
YAML-based custom plugin discovery via plugin.yaml files.
HTTP health checking for endpoints.
"""
from __future__ import annotations
import os
import subprocess
import socket
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

from shared.models import Plugin, PluginRegistry
from shared.models import HealthStatus, CapabilityDomain


# ── Builtin Plugin Definitions ─────────────────────────────

BUILTIN_PLUGINS: Dict[str, dict] = {
    "n8n": {
        "name": "N8N Workflow",
        "domain": CapabilityDomain.SERVICE,
        "provider": "n8n",
        "endpoint": "http://localhost:5678",
    },
    "memos": {
        "name": "MemOS Cloud",
        "domain": CapabilityDomain.SERVICE,
        "provider": "memos",
        "endpoint": "https://api.memos.cloud/v1",
    },
    "comfyui": {
        "name": "ComfyUI",
        "domain": CapabilityDomain.TOOL,
        "provider": "comfyui",
        "endpoint": "http://localhost:8188",
    },
    "ollama": {
        "name": "Ollama",
        "domain": CapabilityDomain.MODEL,
        "provider": "ollama",
        "endpoint": "http://localhost:11434",
    },
    "openclaw_skills": {
        "name": "OpenClaw Skills",
        "domain": CapabilityDomain.SKILL,
        "provider": "openclaw",
        "endpoint": None,
    },
}


class PluginManager:
    """Plugin discovery, health checking, and lifecycle management.

    Discovers builtin plugins + YAML-based custom plugins from plugins_dir.
    Runs periodic health checks on enabled plugins.
    """

    HEALTH_CHECK_INTERVAL = 60  # seconds

    def __init__(
        self,
        node_id: str = "",
        plugins_dir: str = "plugins",
    ):
        """Initialize PluginManager.

        Args:
            node_id: Edge node ID for plugin registry
            plugins_dir: Directory for custom plugin YAML files
        """
        self.node_id = node_id
        self.plugins_dir = Path(plugins_dir)
        self._plugins: Dict[str, Plugin] = {}
        self._registry = PluginRegistry(node_id=node_id)
        self._running = False
        self._lock = threading.RLock()
        self._health_thread: Optional[threading.Thread] = None

    # ── Discovery ──────────────────────────────────────────

    def discover(self) -> List[Plugin]:
        """Discover all plugins: builtin + YAML-based custom plugins.

        Returns:
            List of discovered Plugin objects.
        """
        with self._lock:
            discovered: List[Plugin] = []

            # Builtin plugins
            for pid, info in BUILTIN_PLUGINS.items():
                p = Plugin(
                    plugin_id=pid,
                    name=info["name"],
                    domain=info["domain"],
                    provider=info["provider"],
                    endpoint=info.get("endpoint"),
                    enabled=True,
                    health_status=HealthStatus.UNKNOWN,
                )
                discovered.append(p)
                self._plugins[pid] = p

            # Custom YAML plugins
            if self.plugins_dir.exists():
                for entry in self.plugins_dir.iterdir():
                    if not entry.is_dir():
                        continue
                    yaml_path = entry / "plugin.yaml"
                    if not yaml_path.exists():
                        continue
                    try:
                        import yaml
                        cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                        if not cfg:
                            continue
                        p = Plugin(
                            plugin_id=entry.name,
                            name=cfg.get("name", entry.name),
                            domain=cfg.get("domain", "tool"),
                            provider=cfg.get("provider", "custom"),
                            endpoint=cfg.get("endpoint"),
                            enabled=cfg.get("enabled", True),
                            health_status=HealthStatus.UNKNOWN,
                        )
                        discovered.append(p)
                        self._plugins[p.plugin_id] = p
                    except ImportError:
                        # yaml not installed, skip custom plugins
                        pass
                    except Exception:
                        pass

            self._registry.plugins = list(self._plugins.values())
            return discovered

    # ── Health Check ───────────────────────────────────────

    def health_check(self) -> Dict[str, str]:
        """Run health checks on all enabled plugins.

        Returns:
            Dict mapping plugin_id → health status string.
        """
        with self._lock:
            results: Dict[str, str] = {}
            for pid, plugin in self._plugins.items():
                if not plugin.enabled:
                    results[pid] = HealthStatus.UNKNOWN
                    continue
                status = self._check_plugin(plugin)
                plugin.health_status = status
                results[pid] = status
            return results

    def _check_plugin(self, plugin: Plugin) -> str:
        """Health check a single plugin via its endpoint."""
        info = BUILTIN_PLUGINS.get(plugin.plugin_id, {})
        endpoint = plugin.endpoint or info.get("endpoint")

        if not endpoint:
            return HealthStatus.UNKNOWN

        try:
            req = Request(endpoint, method="HEAD")
            resp = urlopen(req, timeout=5)
            if resp.status < 500:
                return HealthStatus.HEALTHY
            return HealthStatus.DEGRADED
        except Exception:
            # Try TCP check as fallback
            if endpoint and "://" in endpoint:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(endpoint)
                    host = parsed.hostname
                    port = parsed.port or (443 if parsed.scheme == "https" else 80)
                    if host:
                        sock = socket.socket()
                        sock.settimeout(3)
                        result = sock.connect_ex((host, port))
                        sock.close()
                        if result == 0:
                            return HealthStatus.DEGRADED  # TCP OK, HTTP failed
                except Exception:
                    pass
            return HealthStatus.CRITICAL

    # ── Lifecycle ──────────────────────────────────────────

    def start(self):
        """Start the plugin manager (discover + health loop)."""
        self.discover()
        self._running = True
        self._health_thread = threading.Thread(
            target=self._health_loop, daemon=True, name="plugin-health"
        )
        self._health_thread.start()

    def stop(self):
        """Stop the plugin manager."""
        self._running = False
        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=5)

    def _health_loop(self):
        """Periodic health check loop."""
        while self._running:
            for _ in range(int(self.HEALTH_CHECK_INTERVAL / 5)):
                if not self._running:
                    return
                import time
                time.sleep(5)
            if not self._running:
                return
            try:
                self.health_check()
            except Exception:
                pass

    # ── Query ──────────────────────────────────────────────

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a plugin by ID."""
        return self._plugins.get(plugin_id)

    def list_enabled(self) -> List[Plugin]:
        """List all enabled plugins."""
        with self._lock:
            return [p for p in self._plugins.values() if p.enabled]

    def list_all(self) -> List[Plugin]:
        """List all plugins."""
        with self._lock:
            return list(self._plugins.values())

    def enable(self, plugin_id: str) -> bool:
        """Enable a plugin."""
        if plugin_id in self._plugins:
            self._plugins[plugin_id].enabled = True
            return True
        return False

    def disable(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        if plugin_id in self._plugins:
            self._plugins[plugin_id].enabled = False
            return True
        return False

    @property
    def registry(self) -> PluginRegistry:
        """Get the plugin registry snapshot."""
        with self._lock:
            self._registry.plugins = list(self._plugins.values())
            return self._registry

    @property
    def stats(self) -> dict:
        """Get plugin statistics."""
        with self._lock:
            healthy = sum(1 for p in self._plugins.values() if p.health_status == HealthStatus.HEALTHY)
            return {
                "total": len(self._plugins),
                "enabled": len(self.list_enabled()),
                "healthy": healthy,
            }
