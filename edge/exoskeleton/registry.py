"""ModuleRegistry — lazy module loading with safe access.

Extracted from ExoskeletonDaemon (v2.2.1).
Provides: lazy init, isolated instances, built-in error recovery.
"""

from __future__ import annotations
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Lazy-loaded module container with safe method dispatch.

    Usage:
        registry = ModuleRegistry()
        registry.register("health_checker", lambda: HealthChecker())
        result = registry.call("health_checker", "check_all")
    """

    def __init__(self):
        self._init_factories: Dict[str, Callable[[], Any]] = {}
        self._instances: Dict[str, Any] = {}
        self._failures: Dict[str, str] = {}

    def register(self, name: str, factory: Callable[[], Any]):
        """Register a lazy module factory."""
        self._init_factories[name] = factory

    def get(self, name: str) -> Optional[Any]:
        """Get module instance (lazy-init if needed). Returns None on failure."""
        if name not in self._instances:
            factory = self._init_factories.get(name)
            if not factory:
                return None
            try:
                self._instances[name] = factory()
            except Exception as e:
                self._failures[name] = str(e)
                logger.warning("Module '%s' init failed: %s", name, e)
                self._instances[name] = None
            finally:
                self._init_factories.pop(name, None)  # Free factory after init
        return self._instances.get(name)

    def call(self, name: str, method: str, *args, **kwargs) -> Optional[Any]:
        """Safely call a method on a registered module. Returns None on failure."""
        mod = self.get(name)
        if mod is None:
            return None
        try:
            fn = getattr(mod, method, None)
            if fn is None:
                return None
            return fn(*args, **kwargs)
        except Exception as e:
            self._failures[f"{name}.{method}"] = str(e)
            return None

    def list_loaded(self) -> List[str]:
        """List successfully loaded module names."""
        return [k for k, v in self._instances.items() if v is not None]

    def list_failures(self) -> Dict[str, str]:
        """Return dict of module→error for failed initializations."""
        return dict(self._failures)

    def has(self, name: str) -> bool:
        """Check if module is registered and loaded."""
        return name in self._instances and self._instances[name] is not None
