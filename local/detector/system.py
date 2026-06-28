"""System information detector — OS, CPU, Memory, Disk, Network."""

import os
import platform
import socket
import shutil


def detect_system_info() -> dict:
    """Collect comprehensive system information."""
    info = {
        "hostname": socket.gethostname(),
        "os_type": _detect_os_type(),
        "os": platform.system(),
        "os_version": platform.release(),
        "os_full": platform.platform(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count() or 0,
        "memory_total_mb": _get_memory_mb(),
        "disk_free_gb": _get_disk_free_gb(),
        "ip_address": _get_ip(),
    }

    # Detect WSL
    info["is_wsl"] = _is_wsl()
    if info["is_wsl"]:
        info["os_type"] = "wsl"

    return info


def _detect_os_type() -> str:
    system = platform.system().lower()
    if _is_wsl():
        return "wsl"
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    return system


def _is_wsl() -> bool:
    """Detect if running under WSL."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        pass
    return "WSL_DISTRO_NAME" in os.environ


def _get_memory_mb() -> float:
    """Get total memory in MB."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 * 1024), 1)
    except ImportError:
        pass

    # Linux fallback
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if "MemTotal" in line:
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:
        pass

    return 0.0


def _get_disk_free_gb() -> float:
    """Get free disk space in GB for home directory."""
    try:
        usage = shutil.disk_usage(os.path.expanduser("~"))
        return round(usage.free / (1024 * 1024 * 1024), 1)
    except Exception:
        return 0.0


def _get_ip() -> str:
    """Get primary IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
