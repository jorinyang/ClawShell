"""Framework detector base class.

All framework detectors inherit from this abstract base.
Each detector identifies a specific OpenClaw-class framework by
checking paths, config files, processes, and environment markers.
"""

from __future__ import annotations
import os
import platform
import socket
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class FrameworkInfo:
    """Detected framework information."""
    def __init__(self, name: str, version: str = "", root_path: str = "",
                 config_path: str = "", runtime_path: str = "",
                 confidence: float = 1.0, metadata: Optional[dict] = None):
        self.name = name
        self.version = version
        self.root_path = root_path
        self.config_path = config_path
        self.runtime_path = runtime_path
        self.confidence = confidence
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "root_path": self.root_path,
            "config_path": self.config_path,
            "runtime_path": self.runtime_path,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class BaseDetector(ABC):
    """Abstract framework detector."""

    FRAMEWORK_NAME: str = "unknown"
    SEARCH_PATHS: List[str] = []  # Paths to check for this framework
    CONFIG_FILES: List[str] = []  # Config file names to look for
    PROCESS_MARKERS: List[str] = []  # Process name patterns
    ENV_MARKERS: List[str] = []  # Environment variable names

    @abstractmethod
    def detect(self) -> Optional[FrameworkInfo]:
        """Detect if this framework is installed. Returns FrameworkInfo or None."""
        ...

    def check_paths(self) -> List[str]:
        """Check which search paths exist."""
        found = []
        for p in self.SEARCH_PATHS:
            expanded = os.path.expanduser(p)
            if os.path.exists(expanded):
                found.append(expanded)
        return found

    def check_configs(self) -> List[str]:
        """Find config files."""
        found = []
        for p in self.SEARCH_PATHS:
            expanded = os.path.expanduser(p)
            for cf in self.CONFIG_FILES:
                cpath = os.path.join(expanded, cf)
                if os.path.isfile(cpath):
                    found.append(cpath)
        return found

    def check_processes(self) -> bool:
        """Check if any process markers are running."""
        try:
            import subprocess
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            )
            for marker in self.PROCESS_MARKERS:
                if marker.lower() in result.stdout.lower():
                    return True
        except Exception:
            pass
        return False

    def check_env_vars(self) -> bool:
        """Check if any environment markers are set."""
        for var in self.ENV_MARKERS:
            if var in os.environ:
                return True
        return False

    @staticmethod
    def get_hostname() -> str:
        return socket.gethostname()

    @staticmethod
    def get_os_info() -> dict:
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }
