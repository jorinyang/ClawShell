"""Edge ecosystem package — installers, plugin manager, component management.

v1.9.0: PluginManager for plugin discovery and health checking.
v2.1.0: PluginLifecycleManager integration for lifecycle management.
"""
from edge.ecosystem.plugin_manager import PluginManager, BUILTIN_PLUGINS, YamlPluginAdapter
from edge.ecosystem.plugin_lifecycle import (
    PluginLifecycleManager,
    PluginState,
    PluginMetadata,
    PluginContext,
    HealthCheckResult,
)
