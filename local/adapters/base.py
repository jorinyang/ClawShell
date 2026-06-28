"""Abstract adapter base class.

v3.0: adds ADAPTER_TYPE for categorization (framework/bridge/ide).
All adapters implement this unified interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseAdapter(ABC):
    """Abstract adapter for injecting ClawShell into frameworks/tools/IDEs."""

    FRAMEWORK_NAME: str = "unknown"
    ADAPTER_TYPE: str = "framework"  # "framework" | "bridge" | "ide"

    @abstractmethod
    def detect(self) -> bool:
        """Check if target is present."""
        ...

    @abstractmethod
    def inject(self, config: dict) -> bool:
        """Inject ClawShell integration into the target."""
        ...

    @abstractmethod
    def verify(self) -> dict:
        """Verify injection was successful. Returns status dict."""
        ...

    @abstractmethod
    def rollback(self) -> bool:
        """Remove ClawShell integration (idempotent)."""
        ...
