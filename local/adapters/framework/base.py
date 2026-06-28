"""Abstract framework adapter base class."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseAdapter(ABC):
    """Abstract adapter for injecting ClawShell into frameworks."""

    FRAMEWORK_NAME: str = "unknown"

    @abstractmethod
    def detect(self) -> bool:
        """Check if target framework is present."""
        ...

    @abstractmethod
    def inject(self, config: dict) -> bool:
        """Inject ClawShell integration into the target framework."""
        ...

    @abstractmethod
    def verify(self) -> dict:
        """Verify injection was successful."""
        ...

    @abstractmethod
    def rollback(self) -> bool:
        """Remove ClawShell integration (idempotent)."""
        ...
