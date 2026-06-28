"""SignalHandler — graceful shutdown for ClawShell Edge Brain.

Docker/K8s-inspired: SIGTERM → flush → release → disconnect → exit.
"""

from __future__ import annotations
import signal
import sys
import time
import threading
from typing import Optional, Callable, List


class SignalHandler:
    """Graceful shutdown manager — catches SIGTERM/SIGINT.

    Usage:
        handler = SignalHandler()
        handler.register("sync", sync_daemon.stop)
        handler.register("mcp", mcp_server.shutdown)
        handler.install()  # Starts listening for SIGTERM/SIGINT
    """

    def __init__(self, graceful_timeout: float = 10.0):
        self._timeout = graceful_timeout
        self._shutdown_hooks: List[tuple[str, Callable[[], None]]] = []
        self._received = threading.Event()
        self._installed = False

    def register(self, name: str, hook: Callable[[], None]):
        """Register a shutdown hook. Hooks run in registration order."""
        self._shutdown_hooks.append((name, hook))

    def install(self):
        """Start listening for shutdown signals."""
        if self._installed:
            return
        signal.signal(signal.SIGTERM, self._handle)
        signal.signal(signal.SIGINT, self._handle)
        self._installed = True

    def _handle(self, signum, frame):
        print(f"\n[clawshell-edge] Received signal {signum}, shutting down...")
        self._received.set()
        self._run_hooks()
        sys.exit(0)

    def _run_hooks(self):
        """Execute all registered hooks with timeout."""
        for name, hook in self._shutdown_hooks:
            try:
                t = threading.Thread(target=hook, daemon=True)
                t.start()
                t.join(timeout=self._timeout)
                if t.is_alive():
                    print(f"[clawshell-edge] Hook '{name}' timed out after {self._timeout}s")
                else:
                    print(f"[clawshell-edge] Hook '{name}' completed")
            except Exception as e:
                print(f"[clawshell-edge] Hook '{name}' failed: {e}")


class OfflineDegradation:
    """Offline mode — when CloudHub unreachable, queue operations locally.

    K8s-inspired: degraded pod continues serving from local state.
    """

    def __init__(self, data_dir: Optional[str] = None, check_interval: float = 10.0):
        from pathlib import Path
        self._dir = Path(data_dir) if data_dir else Path.home() / ".clawshell" / "data"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._queue_file = self._dir / "offline_queue.jsonl"
        self._online = True
        self._check_interval = check_interval
        self._last_check: float = 0.0

    @property
    def is_online(self) -> bool:
        return self._online

    def check_connectivity(self, cloud_url: str) -> bool:
        """Check if CloudHub is reachable. Throttled to check_interval."""
        now = time.time()
        if now - self._last_check < self._check_interval:
            return self._online  # Return cached status
        self._last_check = now

        try:
            import urllib.request
            req = urllib.request.Request(
                f"{cloud_url}/health", method="GET"
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                self._online = resp.status == 200
        except Exception:
            self._online = False
            # Don't log on every check to avoid noise
        return self._online

    def enqueue(self, operation: dict) -> int:
        """Queue an operation for later replay. Returns queue size after enqueue."""
        import json
        operation["queued_at"] = time.time()
        with open(self._queue_file, "a") as f:
            f.write(json.dumps(operation) + "\n")
        # Count queue items
        try:
            return sum(1 for _ in open(self._queue_file))
        except Exception:
            return -1

    def replay(self, sender: Callable[[dict], bool]) -> tuple[int, int]:
        """Replay queued operations via sender callback.
        Returns (sent, failed)."""
        import json
        if not self._queue_file.exists():
            return 0, 0

        sent = 0
        failed = 0
        remaining = []

        try:
            with open(self._queue_file) as f:
                for line in f:
                    if not line.strip():
                        continue
                    op = json.loads(line)
                    try:
                        if sender(op):
                            sent += 1
                        else:
                            failed += 1
                            remaining.append(json.dumps(op))
                    except Exception:
                        failed += 1
                        remaining.append(json.dumps(op))

            # Write back only failed items
            with open(self._queue_file, "w") as f:
                for r in remaining:
                    f.write(r + "\n")

        except Exception:
            return 0, -1

        return sent, failed

    def queue_size(self) -> int:
        try:
            return sum(1 for _ in open(self._queue_file))
        except Exception:
            return 0

    def clear(self):
        self._queue_file.unlink(missing_ok=True)
