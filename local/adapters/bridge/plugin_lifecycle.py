"""
ClawShell Plugin Lifecycle Framework v2.1
Manages plugin state machines, dependency ordering, health checks, and services.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PluginState(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    ERROR = "error"


# Valid state transitions
_VALID_TRANSITIONS: Dict[PluginState, set[PluginState]] = {
    PluginState.UNINITIALIZED: {PluginState.INITIALIZING},
    PluginState.INITIALIZING: {PluginState.INITIALIZED, PluginState.ERROR},
    PluginState.INITIALIZED: {PluginState.ACTIVE},
    PluginState.ACTIVE: {PluginState.SHUTTING_DOWN},
    PluginState.SHUTTING_DOWN: {PluginState.SHUTDOWN},
    PluginState.SHUTDOWN: {PluginState.INITIALIZING},  # restart
    PluginState.ERROR: {PluginState.INITIALIZING},  # retry
}


def _can_transition(current: PluginState, target: PluginState) -> bool:
    return target in _VALID_TRANSITIONS.get(current, set())


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PluginMetadata:
    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    min_clawshell_version: str = "0.0.0"
    tags: List[str] = field(default_factory=list)


@dataclass
class PluginContext:
    config: Dict[str, Any]
    logger: logging.Logger
    services: Dict[str, Any] = field(default_factory=dict)
    data_dir: str = ""
    version: str = "2.1.0"


@dataclass
class HealthCheckResult:
    healthy: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Plugin Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class IPlugin(Protocol):
    @property
    def metadata(self) -> PluginMetadata: ...
    @property
    def state(self) -> PluginState: ...
    def initialize(self, context: PluginContext) -> None: ...
    def shutdown(self) -> None: ...
    def health_check(self) -> HealthCheckResult: ...


# ---------------------------------------------------------------------------
# Plugin Lifecycle Manager
# ---------------------------------------------------------------------------

class PluginLifecycleManager:
    """Registers, initialises (in dependency order), and shuts down plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, IPlugin] = {}
        self._states: Dict[str, PluginState] = {}
        self._services: Dict[str, Any] = {}

    # -- registration -------------------------------------------------------

    def register(self, plugin: IPlugin) -> None:
        name = plugin.metadata.name
        if name in self._plugins:
            raise ValueError(f"Plugin '{name}' already registered")
        self._plugins[name] = plugin
        self._states[name] = PluginState.UNINITIALIZED

    # -- service registry ---------------------------------------------------

    def register_service(self, name: str, service: Any) -> None:
        self._services[name] = service

    def get_service(self, name: str) -> Any:
        return self._services.get(name)

    # -- state machine helpers ----------------------------------------------

    @staticmethod
    def _transition(name: str, plugin: IPlugin, target: PluginState) -> None:
        current = plugin.state
        if not _can_transition(current, target):
            raise RuntimeError(
                f"Plugin '{name}': invalid transition {current.value} -> {target.value}"
            )

    # -- initialise all (topological order) ---------------------------------

    def initialize_all(
        self,
        context: PluginContext,
        data_dir: str = "",
    ) -> List[str]:
        """Initialise every registered plugin in dependency order.

        Returns list of plugin names in the order they were initialised.
        Raises RuntimeError on missing dependencies or circular deps.
        """
        order = self._resolve_dependency_order()
        ctx = PluginContext(
            config=context.config,
            logger=context.logger,
            services=dict(self._services),
            data_dir=data_dir or context.data_dir,
            version=context.version,
        )

        initialised: List[str] = []
        for name in order:
            plugin = self._plugins[name]

            # Check dependencies are already active
            for dep in plugin.metadata.dependencies:
                if dep not in self._states or self._states[dep] != PluginState.ACTIVE:
                    raise RuntimeError(
                        f"Plugin '{name}' depends on '{dep}' which is not active"
                    )

            # UNINITIALIZED -> INITIALIZING -> INITIALIZED -> ACTIVE
            self._states[name] = PluginState.INITIALIZING
            try:
                plugin.initialize(ctx)
            except Exception as exc:
                self._states[name] = PluginState.ERROR
                raise RuntimeError(f"Plugin '{name}' failed to initialise: {exc}") from exc

            self._states[name] = PluginState.INITIALIZED
            self._states[name] = PluginState.ACTIVE
            initialised.append(name)

        return initialised

    # -- shutdown all (reverse order) ---------------------------------------

    def shutdown_all(self) -> None:
        """Shut down all active plugins in reverse initialisation order."""
        active_names = [
            n for n, s in self._states.items() if s == PluginState.ACTIVE
        ]
        for name in reversed(active_names):
            plugin = self._plugins[name]
            self._states[name] = PluginState.SHUTTING_DOWN
            try:
                plugin.shutdown()
            except Exception:
                logging.getLogger(__name__).exception("Plugin '%s' shutdown error", name)
            self._states[name] = PluginState.SHUTDOWN

    # -- health checks ------------------------------------------------------

    def health_check_all(self) -> Dict[str, HealthCheckResult]:
        """Run health_check on every active plugin."""
        results: Dict[str, HealthCheckResult] = {}
        for name, plugin in self._plugins.items():
            if self._states.get(name) != PluginState.ACTIVE:
                continue
            start = time.monotonic()
            try:
                result = plugin.health_check()
                result.latency_ms = (time.monotonic() - start) * 1000
            except Exception as exc:
                result = HealthCheckResult(healthy=False, message=str(exc))
                result.latency_ms = (time.monotonic() - start) * 1000
            results[name] = result
        return results

    # -- introspection ------------------------------------------------------

    def get_state(self, name: str) -> PluginState:
        return self._states[name]

    def list_plugins(self) -> Dict[str, PluginState]:
        return dict(self._states)

    # -- dependency resolution (topological sort) ---------------------------

    def _resolve_dependency_order(self) -> List[str]:
        """Kahn's algorithm – raises RuntimeError on cycles."""
        # Build adjacency
        in_degree: Dict[str, int] = {n: 0 for n in self._plugins}
        dependents: Dict[str, List[str]] = {n: [] for n in self._plugins}

        for name, plugin in self._plugins.items():
            for dep in plugin.metadata.dependencies:
                if dep not in self._plugins:
                    raise RuntimeError(
                        f"Plugin '{name}' depends on unknown plugin '{dep}'"
                    )
                dependents[dep].append(name)
                in_degree[name] += 1

        queue = [n for n, d in in_degree.items() if d == 0]
        order: List[str] = []
        while queue:
            queue.sort()  # deterministic
            node = queue.pop(0)
            order.append(node)
            for child in dependents[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(self._plugins):
            raise RuntimeError("Circular dependency detected among plugins")

        return order
