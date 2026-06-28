"""IDE Bridge — abstract base for Agent CLI IDE integration.

Harness Engineering methodology: The Edge Brain can delegate code development
tasks to multiple Agent CLI IDEs (Codex, Claude Code, Kimi Code, DeepSeek TUI, Copilot),
matching each task to the optimal IDE based on capability (ecological niche matching).

Standard interface:
- detect(): Check if IDE is installed
- invoke(task): Execute a coding task with the IDE
- get_capabilities(): Return IDE capabilities for matching
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import time


@dataclass
class IDETask:
    """A coding task to be delegated to an Agent CLI IDE."""
    task_id: str = ""
    description: str = ""
    task_type: str = "code"          # code / review / debug / refactor / test
    language: str = ""               # python / javascript / go / etc.
    context: str = ""                # Additional context for the IDE
    files: List[str] = field(default_factory=list)
    working_dir: str = ""
    timeout_seconds: int = 300
    priority: int = 0


@dataclass
class IDEResult:
    """Result from an IDE task execution."""
    task_id: str = ""
    ide_name: str = ""
    success: bool = False
    output: str = ""
    error: str = ""
    duration_seconds: float = 0.0
    files_modified: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseIDEBridge(ABC):
    """Abstract IDE bridge for Agent CLI tools."""

    IDE_NAME: str = "unknown"
    CLI_COMMAND: str = ""           # CLI command name (e.g., "codex", "claude")
    CHECK_COMMAND: str = ""         # Command to check installation

    @abstractmethod
    def detect(self) -> bool:
        """Check if this IDE CLI is installed and usable."""
        ...

    @abstractmethod
    def invoke(self, task: IDETask) -> IDEResult:
        """Execute a coding task with this IDE."""
        ...

    def get_capabilities(self) -> List[str]:
        """Return IDE capabilities for ecological niche matching."""
        return ["code"]  # Override in subclasses

    def get_name(self) -> str:
        return self.IDE_NAME

    # ── Shared helpers ────────────────────────────

    @staticmethod
    def _run_command(cmd: list, cwd: str = ".", timeout: int = 300) -> tuple[int, str, str]:
        """Run a shell command and return (exit_code, stdout, stderr)."""
        import subprocess
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=cwd, timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0] if cmd else 'unknown'}"
        except Exception as e:
            return -1, "", str(e)

    @staticmethod
    def _check_command(cmd: str) -> bool:
        """Check if a command exists in PATH."""
        import shutil
        return shutil.which(cmd) is not None
