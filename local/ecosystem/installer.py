"""Edge ecosystem installer — manage 10 optional components."""

from __future__ import annotations
import os
import sys
import subprocess
import shutil
from typing import Dict, List, Callable, Optional


class EcosystemComponent:
    """An optional ecosystem component."""
    def __init__(self, name: str, description: str,
                 pip_packages: List[str] = None,
                 check_fn: Optional[Callable] = None,
                 install_fn: Optional[Callable] = None):
        self.name = name
        self.description = description
        self.pip_packages = pip_packages or []
        self._check_fn = check_fn
        self._install_fn = install_fn

    def is_installed(self) -> bool:
        if self._check_fn:
            return self._check_fn()
        # Default: check pip packages
        for pkg in self.pip_packages:
            try:
                __import__(pkg.replace("-", "_"))
                return True
            except ImportError:
                pass
        return False

    def install(self) -> bool:
        if self._install_fn:
            return self._install_fn()
        if self.pip_packages:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--quiet"] + self.pip_packages,
                    check=True, timeout=120
                )
                return True
            except Exception:
                return False
        return True


# ── Component definitions ──

COMPONENTS = {
    "psutil": EcosystemComponent("psutil", "System monitoring", pip_packages=["psutil"]),
    "websockets": EcosystemComponent("websockets", "WebSocket client", pip_packages=["websockets"]),
    "chromadb": EcosystemComponent("chromadb", "Vector database for MemPalace",
                                   pip_packages=["chromadb"]),
    "mempalace": EcosystemComponent("mempalace", "Local memory palace (SQLite + ChromaDB)",
                                    pip_packages=["mempalace"]),
    "n8n": EcosystemComponent("n8n", "Workflow automation engine",
                              check_fn=lambda: shutil.which("n8n") is not None),
    "memos_cloud": EcosystemComponent("memos_cloud", "MemOS Cloud sync client",
                                      pip_packages=["requests"]),
    "watchdog": EcosystemComponent("watchdog", "Filesystem monitoring",
                                   pip_packages=["watchdog"]),
    "browser_runtime": EcosystemComponent("browser_runtime",
                                          "Headless browser (Playwright CDP)",
                                          check_fn=lambda: shutil.which("playwright") is not None),
    "onnx_runtime": EcosystemComponent("onnx_runtime", "ONNX ML acceleration",
                                       pip_packages=["onnxruntime"]),
    "obsidian_oss": EcosystemComponent("obsidian_oss", "Obsidian vault + OSS sync",
                                       check_fn=lambda: shutil.which("ossutil") is not None),
}


class EcosystemInstaller:
    """Install and manage ecosystem components."""

    def __init__(self):
        self._components = dict(COMPONENTS)

    def list_components(self) -> List[dict]:
        """List all components with status."""
        return [
            {
                "name": c.name,
                "description": c.description,
                "installed": c.is_installed(),
            }
            for c in self._components.values()
        ]

    def check(self, name: str) -> Optional[bool]:
        """Check if a component is installed."""
        comp = self._components.get(name)
        return comp.is_installed() if comp else None

    def install(self, name: str) -> bool:
        """Install a component."""
        comp = self._components.get(name)
        if not comp:
            return False
        if comp.is_installed():
            return True  # Already installed (idempotent)
        return comp.install()

    def install_all(self) -> Dict[str, bool]:
        """Install all components. Returns {name: success}."""
        results = {}
        for name in self._components:
            results[name] = self.install(name)
        return results

    def install_selected(self, names: List[str]) -> Dict[str, bool]:
        """Install selected components."""
        results = {}
        for name in names:
            results[name] = self.install(name)
        return results

    def get_status(self) -> dict:
        """Get overall ecosystem status."""
        components = self.list_components()
        installed = sum(1 for c in components if c["installed"])
        return {
            "total": len(components),
            "installed": installed,
            "missing": len(components) - installed,
            "components": components,
        }
