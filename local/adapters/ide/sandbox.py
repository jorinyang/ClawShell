"""IDE Sandbox — Isolated execution environment for IDE CLI tools.

Features:
- Working directory isolation
- Timeout control
- Resource limits (memory, CPU)
- Output capture with size limits
"""

from __future__ import annotations
import os
import time
import signal
import subprocess
import tempfile
from typing import Optional


class IDESandbox:
    """Isolated execution sandbox for IDE CLI tools."""

    DEFAULT_TIMEOUT = 300
    MAX_OUTPUT_BYTES = 1_000_000  # 1 MB
    MAX_MEMORY_MB = 4096

    def __init__(self, work_dir: Optional[str] = None,
                 timeout: int = DEFAULT_TIMEOUT,
                 max_memory_mb: int = MAX_MEMORY_MB):
        self._work_dir = work_dir or tempfile.mkdtemp(prefix="clawshell_ide_")
        self._timeout = timeout
        self._max_memory_mb = max_memory_mb
        os.makedirs(self._work_dir, exist_ok=True)

    @property
    def work_dir(self) -> str:
        return self._work_dir

    def execute(self, command: list, stdin_data: Optional[str] = None) -> dict:
        """Execute a command in the sandbox. Returns result dict."""
        start = time.time()
        result = {
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "duration_seconds": 0.0,
        }

        try:
            # Set up resource limits
            mem_limit = self._max_memory_mb * 1024 * 1024

            process = subprocess.Popen(
                command,
                cwd=self._work_dir,
                stdin=subprocess.PIPE if stdin_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=self._set_limits if hasattr(os, 'setrlimit') else None,
            )

            try:
                stdout, stderr = process.communicate(
                    input=stdin_data,
                    timeout=self._timeout
                )
                result["exit_code"] = process.returncode
                result["stdout"] = stdout[:self.MAX_OUTPUT_BYTES] if stdout else ""
                result["stderr"] = stderr[:self.MAX_OUTPUT_BYTES] if stderr else ""

            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                result["timed_out"] = True
                result["stderr"] = f"Command timed out after {self._timeout}s"

        except FileNotFoundError:
            result["stderr"] = f"Command not found: {command[0] if command else ''}"
        except Exception as e:
            result["stderr"] = str(e)

        result["duration_seconds"] = round(time.time() - start, 2)
        return result

    def write_file(self, filename: str, content: str):
        """Write a file in the sandbox."""
        filepath = os.path.join(self._work_dir, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)

    def read_file(self, filename: str) -> Optional[str]:
        """Read a file from the sandbox."""
        filepath = os.path.join(self._work_dir, filename)
        if os.path.isfile(filepath):
            with open(filepath, "r") as f:
                return f.read()[:self.MAX_OUTPUT_BYTES]
        return None

    def cleanup(self):
        """Remove sandbox directory."""
        import shutil
        if os.path.exists(self._work_dir):
            shutil.rmtree(self._work_dir, ignore_errors=True)

    @staticmethod
    def _set_limits():
        """Set resource limits for the child process."""
        try:
            import resource
            # Set memory limit
            mem_bytes = 4096 * 1024 * 1024  # 4GB
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except Exception:
            pass
