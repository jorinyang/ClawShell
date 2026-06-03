"""ResourceGuard — self-imposed resource limits for Edge Brain.

Docker-inspired mechanisms:
  1. Memory limit monitoring — alert CloudHub if usage exceeds threshold
  2. Disk space guard — refuse writes if free space drops below floor
  3. CPU watchdog — detect sustained high CPU and throttle background tasks

Usage:
    guard = ResourceGuard(memory_limit_mb=2048, disk_floor_gb=1.0)
    if not guard.check_memory():
        logger.warning("Memory limit approaching, skipping heavy task")
"""

from __future__ import annotations
import os
import time
import threading
from pathlib import Path
from typing import Optional, Callable


class ResourceGuard:
    """Self-imposed resource limits — Docker-style cgroups in user space."""

    def __init__(
        self,
        memory_limit_mb: float = 2048,
        disk_floor_gb: float = 1.0,
        cpu_threshold_pct: float = 90.0,
        alert_callback: Optional[Callable[[str, dict], None]] = None,
    ):
        self.memory_limit_mb = memory_limit_mb
        self.disk_floor_gb = disk_floor_gb
        self.cpu_threshold_pct = cpu_threshold_pct
        self._alert = alert_callback or (lambda msg, data: None)
        self._last_alert: dict[str, float] = {}  # cooldown per alert type
        self._alert_cooldown = 300  # 5 min between same alerts

    # ── Memory Check ─────────────────────────────────────────────────

    def check_memory(self) -> bool:
        """Returns True if memory usage is within limits."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            used_mb = (mem.total - mem.available) / (1024 * 1024)
        except ImportError:
            used_mb = self._read_meminfo()
        return used_mb < self.memory_limit_mb

    def get_memory_usage_mb(self) -> float:
        """Current memory usage in MB."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return (mem.total - mem.available) / (1024 * 1024)
        except ImportError:
            return self._read_meminfo()

    def _read_meminfo(self) -> float:
        """Linux fallback — read /proc/meminfo."""
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            total = int([l for l in lines if "MemTotal" in l][0].split()[1])
            avail = int([l for l in lines if "MemAvailable" in l][0].split()[1])
            return (total - avail) / 1024
        except Exception:
            return 0.0

    # ── Disk Check ───────────────────────────────────────────────────

    def check_disk(self, path: Optional[str] = None) -> bool:
        """Returns True if free disk space is above floor."""
        p = Path(path) if path else Path.home()
        try:
            stat = os.statvfs(str(p))
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            return free_gb >= self.disk_floor_gb
        except Exception:
            return True  # Can't check → don't block

    # ── CPU Watchdog ─────────────────────────────────────────────────

    def check_cpu(self) -> bool:
        """Returns True if CPU usage is below threshold."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            return cpu < self.cpu_threshold_pct
        except ImportError:
            return True

    # ── Full Health Check ────────────────────────────────────────────

    def full_check(self) -> dict:
        """Returns {check_name: bool} for all resource checks."""
        return {
            "memory_ok": self.check_memory(),
            "disk_ok": self.check_disk(),
            "cpu_ok": self.check_cpu(),
            "memory_used_mb": round(self.get_memory_usage_mb(), 1),
            "memory_limit_mb": self.memory_limit_mb,
            "disk_floor_gb": self.disk_floor_gb,
        }

    # ── Alert with Cooldown ──────────────────────────────────────────

    def alert_if_exceeded(self) -> dict[str, bool]:
        """Check all resources. If any exceeded, trigger alert (with cooldown).
        Returns {resource_name: exceeded}."""
        results = {}
        now = time.time()

        if not self.check_memory():
            results["memory"] = True
            if now - self._last_alert.get("memory", 0) > self._alert_cooldown:
                self._last_alert["memory"] = now
                self._alert("memory_high", {"used_mb": self.get_memory_usage_mb(),
                                             "limit_mb": self.memory_limit_mb})

        if not self.check_disk():
            results["disk"] = True
            if now - self._last_alert.get("disk", 0) > self._alert_cooldown:
                self._last_alert["disk"] = now
                self._alert("disk_low", {"floor_gb": self.disk_floor_gb})

        if not self.check_cpu():
            results["cpu"] = True
            if now - self._last_alert.get("cpu", 0) > self._alert_cooldown:
                self._last_alert["cpu"] = now
                self._alert("cpu_high", {"threshold_pct": self.cpu_threshold_pct})

        return results


class ConfigSnapshot:
    """Checkpoint agent config before modification — Docker layer snapshot.

    Before MCP injection, takes a snapshot. On failure, restores from snapshot.
    """

    def __init__(self, snapshot_dir: Optional[str] = None):
        self._dir = Path(snapshot_dir) if snapshot_dir else Path.home() / ".clawshell" / "snapshots"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, path: str, label: str = "") -> Optional[str]:
        """Save a snapshot of a config file. Returns snapshot_id."""
        src = Path(path)
        if not src.exists():
            return None
        import uuid
        snap_id = f"{label or src.name}_{uuid.uuid4().hex[:8]}"
        dest = self._dir / snap_id
        dest.write_bytes(src.read_bytes())
        return snap_id

    def restore(self, path: str, snapshot_id: str) -> bool:
        """Restore a file from snapshot."""
        snap = self._dir / snapshot_id
        if not snap.exists():
            return False
        Path(path).write_bytes(snap.read_bytes())
        return True

    def list_snapshots(self) -> list[str]:
        return sorted([p.name for p in self._dir.iterdir() if p.is_file()])

    def prune(self, keep: int = 10):
        """Keep only the N most recent snapshots."""
        files = sorted(self._dir.iterdir(), key=os.path.getmtime, reverse=True)
        for f in files[keep:]:
            f.unlink()
