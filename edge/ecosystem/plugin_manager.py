"""PluginManager — Plugin discovery and health checking.

Design inspired by DEEP PluginManager + MacOS v2.1 PluginDomain.
Adapted to Main's edge/ecosystem/ with threading model.

Builtin plugins: n8n, MemOS, ComfyUI, Ollama, OpenClaw Skills
YAML-based custom plugin discovery via plugin.yaml files.
HTTP health checking for endpoints.
"""
from __future__ import annotations
import os
import logging
import subprocess
import socket
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

from shared.models import Plugin, PluginRegistry
from shared.models import HealthStatus, CapabilityDomain
from edge.ecosystem.plugin_lifecycle import (
    PluginLifecycleManager,
    PluginState,
    PluginMetadata,
    PluginContext,
    HealthCheckResult,
    IPlugin,
)


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


# ── YAML Plugin Adapter ────────────────────────────────────

class YamlPluginAdapter:
    """Wraps a YAML plugin config dict into the IPlugin protocol.

    Allows YAML-defined custom plugins to be managed by PluginLifecycleManager.
    Implements initialize / shutdown / health_check lifecycle hooks.
    """

    def __init__(self, plugin_id: str, cfg: dict):
        self._plugin_id = plugin_id
        self._cfg = cfg
        self._state = PluginState.UNINITIALIZED
        self._initialized = False
        self._shutdown_called = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._plugin_id,
            version=self._cfg.get("version", "0.1.0"),
            description=self._cfg.get("description", ""),
            author=self._cfg.get("author", ""),
            dependencies=self._cfg.get("dependencies", []),
            tags=self._cfg.get("tags", []),
        )

    @property
    def state(self) -> PluginState:
        return self._state

    def initialize(self, context: PluginContext) -> None:
        """Initialize the YAML plugin (runs startup commands if configured)."""
        self._initialized = True
        self._state = PluginState.ACTIVE

    def shutdown(self) -> None:
        """Shutdown the YAML plugin."""
        self._shutdown_called = True
        self._state = PluginState.SHUTDOWN

    def health_check(self) -> HealthCheckResult:
        """Health check via endpoint if available."""
        endpoint = self._cfg.get("endpoint")
        if not endpoint:
            return HealthCheckResult(healthy=True, message="no endpoint configured")
        try:
            req = Request(endpoint, method="HEAD")
            resp = urlopen(req, timeout=5)
            healthy = resp.status < 500
            return HealthCheckResult(
                healthy=healthy,
                message=f"HTTP {resp.status}",
            )
        except Exception as exc:
            # Fall back to TCP check
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
                        return HealthCheckResult(healthy=True, message="TCP ok, HTTP failed")
            except Exception:
                pass
            return HealthCheckResult(healthy=False, message=str(exc))


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
        self._lifecycle = PluginLifecycleManager()
        self._adapters: Dict[str, YamlPluginAdapter] = {}

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
                        # Wrap in adapter and register with lifecycle manager
                        adapter = YamlPluginAdapter(entry.name, cfg)
                        self._lifecycle.register(adapter)
                        self._adapters[entry.name] = adapter
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

        Uses PluginLifecycleManager.health_check_all() for YAML plugins
        and HTTP-based checks for builtin plugins.

        Returns:
            Dict mapping plugin_id → health status string.
        """
        with self._lock:
            results: Dict[str, str] = {}

            # Lifecycle-managed (YAML) plugins
            if self._adapters:
                ctx = PluginContext(config={}, logger=logging.getLogger(__name__))
                # Initialize any uninitialized adapters
                for name, adapter in self._adapters.items():
                    if adapter.state == PluginState.UNINITIALIZED:
                        try:
                            self._lifecycle.initialize_all(ctx)
                            break
                        except Exception:
                            pass
                lifecycle_results = self._lifecycle.health_check_all()
                for name, hcr in lifecycle_results.items():
                    if hcr.healthy:
                        status = HealthStatus.HEALTHY
                    else:
                        status = HealthStatus.CRITICAL
                    if name in self._plugins:
                        self._plugins[name].health_status = status
                    results[name] = status

            # Builtin plugins (HTTP-based check)
            for pid, plugin in self._plugins.items():
                if pid in self._adapters:
                    continue  # already handled by lifecycle manager
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
        # Shutdown lifecycle-managed plugins
        try:
            self._lifecycle.shutdown_all()
        except Exception:
            pass
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
    def lifecycle(self) -> PluginLifecycleManager:
        """Get the lifecycle manager instance."""
        return self._lifecycle

    @property
    def adapters(self) -> Dict[str, YamlPluginAdapter]:
        """Get the YAML plugin adapters."""
        return dict(self._adapters)

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
