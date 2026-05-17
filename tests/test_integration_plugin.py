"""Integration tests for PluginManager + PluginLifecycleManager.

Verifies that:
  - YAML plugin discovery wraps plugins in YamlPluginAdapter
  - Adapters are registered with PluginLifecycleManager
  - Health checks delegate through the lifecycle manager
  - Shutdown propagates to lifecycle-managed plugins
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from edge.ecosystem.plugin_manager import PluginManager, YamlPluginAdapter
from edge.ecosystem.plugin_lifecycle import (
    PluginLifecycleManager,
    PluginState,
    PluginContext,
    HealthCheckResult,
)
from shared.models import HealthStatus


logger = logging.getLogger("test_integration")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_yaml_plugin(plugins_dir: Path, plugin_id: str, cfg: dict) -> Path:
    """Create a YAML plugin directory with plugin.yaml."""
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir(parents=True, exist_ok=True)
    import yaml
    (plugin_dir / "plugin.yaml").write_text(yaml.dump(cfg), encoding="utf-8")
    return plugin_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestYamlPluginAdapter:
    """Unit tests for YamlPluginAdapter."""

    def test_metadata_from_config(self):
        cfg = {
            "name": "Test Plugin",
            "version": "2.0.0",
            "description": "A test plugin",
            "author": "tester",
            "dependencies": ["dep1"],
            "tags": ["test", "demo"],
        }
        adapter = YamlPluginAdapter("test_plugin", cfg)
        meta = adapter.metadata
        assert meta.name == "test_plugin"
        assert meta.version == "2.0.0"
        assert meta.description == "A test plugin"
        assert meta.author == "tester"
        assert meta.dependencies == ["dep1"]
        assert meta.tags == ["test", "demo"]

    def test_metadata_defaults(self):
        adapter = YamlPluginAdapter("minimal", {})
        meta = adapter.metadata
        assert meta.name == "minimal"
        assert meta.version == "0.1.0"
        assert meta.dependencies == []

    def test_initial_state_is_uninitialized(self):
        adapter = YamlPluginAdapter("test", {})
        assert adapter.state == PluginState.UNINITIALIZED

    def test_initialize_sets_active(self):
        adapter = YamlPluginAdapter("test", {})
        ctx = PluginContext(config={}, logger=logger)
        adapter.initialize(ctx)
        assert adapter.state == PluginState.ACTIVE
        assert adapter._initialized is True

    def test_shutdown_sets_shutdown(self):
        adapter = YamlPluginAdapter("test", {})
        ctx = PluginContext(config={}, logger=logger)
        adapter.initialize(ctx)
        adapter.shutdown()
        assert adapter.state == PluginState.SHUTDOWN
        assert adapter._shutdown_called is True

    def test_health_check_no_endpoint(self):
        adapter = YamlPluginAdapter("test", {})
        result = adapter.health_check()
        assert result.healthy is True
        assert "no endpoint" in result.message

    def test_health_check_with_unreachable_endpoint(self):
        cfg = {"endpoint": "http://localhost:99999"}
        adapter = YamlPluginAdapter("test", cfg)
        result = adapter.health_check()
        # Endpoint is unreachable, so should be unhealthy
        assert result.healthy is False


class TestPluginManagerLifecycleIntegration:
    """Integration tests for PluginManager + PluginLifecycleManager."""

    def test_discovery_creates_lifecycle_manager(self):
        """PluginManager should have a PluginLifecycleManager instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            assert isinstance(pm.lifecycle, PluginLifecycleManager)

    def test_discover_yaml_creates_adapter(self):
        """YAML plugin discovery should create YamlPluginAdapter instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_yaml_plugin(
                Path(tmpdir), "my_plugin",
                {"name": "My Plugin", "domain": "tool", "endpoint": None},
            )
            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            discovered = pm.discover()

            # Should find builtin plugins + our custom one
            plugin_ids = [p.plugin_id for p in discovered]
            assert "my_plugin" in plugin_ids

            # Adapter should be created and registered
            assert "my_plugin" in pm.adapters
            adapter = pm.adapters["my_plugin"]
            assert isinstance(adapter, YamlPluginAdapter)
            assert adapter.metadata.name == "my_plugin"

    def test_adapter_registered_with_lifecycle_manager(self):
        """YAML plugins should be registered in the lifecycle manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_yaml_plugin(
                Path(tmpdir), "lifecycle_plugin",
                {"name": "Lifecycle Plugin", "version": "1.0.0"},
            )
            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            pm.discover()

            # Check the lifecycle manager knows about it
            plugins = pm.lifecycle.list_plugins()
            assert "lifecycle_plugin" in plugins
            assert plugins["lifecycle_plugin"] == PluginState.UNINITIALIZED

    def test_multiple_yaml_plugins_discovered(self):
        """Multiple YAML plugins should all be wrapped and registered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_yaml_plugin(Path(tmpdir), "alpha", {"name": "Alpha"})
            _create_yaml_plugin(Path(tmpdir), "beta", {"name": "Beta"})
            _create_yaml_plugin(Path(tmpdir), "gamma", {"name": "Gamma"})

            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            pm.discover()

            assert len(pm.adapters) == 3
            assert set(pm.adapters.keys()) == {"alpha", "beta", "gamma"}

            lifecycle_plugins = pm.lifecycle.list_plugins()
            assert set(lifecycle_plugins.keys()) == {"alpha", "beta", "gamma"}

    def test_health_check_initializes_and_checks_lifecycle_plugins(self):
        """health_check() should initialize adapters and use lifecycle manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_yaml_plugin(
                Path(tmpdir), "hc_plugin",
                {"name": "HC Plugin", "endpoint": None},
            )
            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            pm.discover()

            # health_check should trigger initialization
            results = pm.health_check()

            # The YAML plugin should be in results
            assert "hc_plugin" in results
            # With no endpoint, health_check returns healthy
            assert results["hc_plugin"] == HealthStatus.HEALTHY

            # Plugin object should have updated health status
            plugin = pm.get_plugin("hc_plugin")
            assert plugin is not None
            assert plugin.health_status == HealthStatus.HEALTHY

            # Adapter should now be ACTIVE after initialization
            adapter = pm.adapters["hc_plugin"]
            assert adapter.state == PluginState.ACTIVE

    def test_health_check_lifecycle_unhealthy(self):
        """Health check with unreachable endpoint should report CRITICAL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_yaml_plugin(
                Path(tmpdir), "bad_plugin",
                {"name": "Bad Plugin", "endpoint": "http://localhost:1"},
            )
            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            pm.discover()

            results = pm.health_check()

            assert "bad_plugin" in results
            assert results["bad_plugin"] == HealthStatus.CRITICAL

    def test_stop_shuts_down_lifecycle_plugins(self):
        """stop() should shut down all lifecycle-managed plugins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_yaml_plugin(Path(tmpdir), "sd_plugin", {"name": "SD Plugin"})
            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            pm.discover()

            # Initialize first via health check
            pm.health_check()

            adapter = pm.adapters["sd_plugin"]
            assert adapter.state == PluginState.ACTIVE

            # Stop should shut down lifecycle plugins
            pm.stop()

            assert adapter.state == PluginState.SHUTDOWN
            assert adapter._shutdown_called is True

    def test_builtin_plugins_not_in_lifecycle_manager(self):
        """Builtin plugins should NOT be wrapped in adapters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            pm.discover()

            # Builtin plugins are discovered but not in adapters
            for builtin_id in ["n8n", "memos", "comfyui", "ollama", "openclaw_skills"]:
                assert builtin_id not in pm.adapters
                assert builtin_id not in pm.lifecycle.list_plugins()

            # But they should be in the regular plugin list
            assert "n8n" in [p.plugin_id for p in pm.list_all()]

    def test_discover_with_no_yaml_plugins(self):
        """Empty plugins directory should work fine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PluginManager(node_id="test", plugins_dir=tmpdir)
            discovered = pm.discover()

            # Only builtin plugins
            assert len(pm.adapters) == 0
            assert len(pm.lifecycle.list_plugins()) == 0
            assert len(discovered) == 5  # 5 builtin plugins

    def test_discover_with_no_plugins_dir(self):
        """Non-existent plugins directory should work fine."""
        pm = PluginManager(node_id="test", plugins_dir="/nonexistent/path")
        discovered = pm.discover()

        assert len(pm.adapters) == 0
        assert len(discovered) == 5  # 5 builtin plugins

    def test_adapter_satisfies_iprotocol(self):
        """YamlPluginAdapter should satisfy the IPlugin protocol."""
        from edge.ecosystem.plugin_lifecycle import IPlugin
        adapter = YamlPluginAdapter("test", {})
        # runtime_checkable protocol check
        assert isinstance(adapter, IPlugin)

    def test_full_lifecycle(self):
        """Test full lifecycle: discover -> health_check -> stop."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_yaml_plugin(
                Path(tmpdir), "full_lifecycle",
                {
                    "name": "Full Lifecycle Plugin",
                    "version": "1.0.0",
                    "description": "Tests full lifecycle",
                    "domain": "tool",
                    "endpoint": None,
                },
            )

            pm = PluginManager(node_id="test-node", plugins_dir=tmpdir)

            # 1. Discover
            discovered = pm.discover()
            plugin_ids = [p.plugin_id for p in discovered]
            assert "full_lifecycle" in plugin_ids

            # 2. Adapter registered and uninitialized
            adapter = pm.adapters["full_lifecycle"]
            assert adapter.state == PluginState.UNINITIALIZED

            # 3. Health check (triggers initialization)
            results = pm.health_check()
            assert results["full_lifecycle"] == HealthStatus.HEALTHY
            assert adapter.state == PluginState.ACTIVE

            # 4. Registry includes the plugin
            registry = pm.registry
            registry_ids = [p.plugin_id for p in registry.plugins]
            assert "full_lifecycle" in registry_ids

            # 5. Stats reflect the plugin
            stats = pm.stats
            assert stats["total"] >= 6  # 5 builtin + 1 custom

            # 6. Stop shuts down lifecycle plugins
            pm.stop()
            assert adapter.state == PluginState.SHUTDOWN
