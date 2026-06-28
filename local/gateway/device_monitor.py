"""Device Monitor — real-time device health monitoring."""

import threading, time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class DeviceMetrics:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    process_count: int = 0
    uptime_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)

class DeviceMonitor:
    def __init__(self, collect_interval: int = 30):
        self._lock = threading.RLock()
        self._interval = collect_interval
        self._latest: Optional[DeviceMetrics] = None
        self._history: List[DeviceMetrics] = []
        self._running = False
        self._max_history = 1000

    def collect(self) -> DeviceMetrics:
        metrics = DeviceMetrics()
        try:
            import psutil
            metrics.cpu_percent = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            metrics.memory_percent = mem.percent
            disk = psutil.disk_usage("/")
            metrics.disk_percent = disk.percent
            net = psutil.net_io_counters()
            if net:
                metrics.network_rx_bytes = net.bytes_recv
                metrics.network_tx_bytes = net.bytes_sent
            metrics.process_count = len(psutil.pids())
            metrics.uptime_seconds = time.time() - psutil.boot_time()
        except ImportError:
            pass
        with self._lock:
            self._latest = metrics
            self._history.append(metrics)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        return metrics

    def get_latest(self) -> Optional[DeviceMetrics]:
        with self._lock:
            return self._latest

    def get_health_status(self) -> HealthStatus:
        m = self.get_latest()
        if not m:
            return HealthStatus.UNKNOWN
        if m.cpu_percent > 95 or m.memory_percent > 95 or m.disk_percent > 95:
            return HealthStatus.UNHEALTHY
        if m.cpu_percent > 75 or m.memory_percent > 80 or m.disk_percent > 85:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            m = self._latest
            return {
                "latest": {
                    "cpu_percent": round(m.cpu_percent, 1) if m else None,
                    "memory_percent": round(m.memory_percent, 1) if m else None,
                    "disk_percent": round(m.disk_percent, 1) if m else None,
                    "uptime_hours": round(m.uptime_seconds / 3600, 1) if m else None,
                } if m else None,
                "health": self.get_health_status().value,
                "history_size": len(self._history),
            }
