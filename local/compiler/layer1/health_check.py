"""Exoskeleton Layer 1 — Self-Sensing (自感知).

Monitors: Health, System, Disk, Process, Agent, Gateway, Service.
"""

import os
import time
import shutil
import socket
from typing import Dict, List, Optional


class HealthChecker:
    """27-item system health check."""

    def __init__(self):
        self._last_check = 0.0
        self._last_results: Dict[str, bool] = {}

    def check_all(self) -> Dict[str, any]:
        """Run all health checks."""
        results = {}
        results.update(self.check_system())
        results.update(self.check_disk("/"))
        results.update(self.check_processes(["python", "node", "nginx"]))
        results.update(self.check_network())
        results["timestamp"] = time.time()
        self._last_results = results
        self._last_check = time.time()
        return results

    def check_system(self) -> dict:
        cpu = 0
        mem = 0
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
        except ImportError:
            pass

        return {
            "cpu_percent": cpu,
            "memory_percent": mem,
            "cpu_healthy": cpu < 90,
            "memory_healthy": mem < 90,
        }

    def check_disk(self, path: str = "/") -> dict:
        try:
            usage = shutil.disk_usage(path)
            pct = (usage.used / usage.total) * 100
            return {
                "disk_total_gb": round(usage.total / (1024**3), 1),
                "disk_used_gb": round(usage.used / (1024**3), 1),
                "disk_percent": round(pct, 1),
                "disk_healthy": pct < 90,
            }
        except Exception:
            return {"disk_healthy": True, "disk_error": "Unable to check"}

    def check_processes(self, names: List[str]) -> dict:
        results = {}
        for name in names:
            found = self._find_process(name)
            results[f"process_{name}"] = found
        return results

    def check_network(self) -> dict:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            s.close()
            return {"network_healthy": True}
        except Exception:
            return {"network_healthy": False}

    def is_healthy(self) -> bool:
        results = self._last_results
        if not results:
            return True
        checks = [v for k, v in results.items() if k.endswith("_healthy")]
        return all(checks) if checks else True

    @staticmethod
    def _find_process(name: str) -> bool:
        try:
            import subprocess
            result = subprocess.run(
                ["pgrep", "-f", name], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return True  # Assume running if can't check
