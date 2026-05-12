"""Network Discovery — discover ClawShell Edge nodes on LAN."""

import threading, time, uuid, socket, json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class DiscoveredDevice:
    device_id: str = ""
    hostname: str = ""
    ip_address: str = ""
    port: int = 0
    os_type: str = ""
    capabilities: List[str] = field(default_factory=list)
    discovered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

class NetworkDiscovery:
    """LAN-based ClawShell Edge node discovery via UDP broadcast."""

    BROADCAST_PORT = 17660
    DISCOVERY_MESSAGE = b"CLAWSHELL_DISCOVER"

    def __init__(self):
        self._lock = threading.RLock()
        self._devices: Dict[str, DiscoveredDevice] = {}
        self._running = False

    def start(self) -> None:
        self._running = True

    def register_device(self, hostname: str = "", ip_address: str = "",
                        port: int = 0, os_type: str = "",
                        capabilities: Optional[List[str]] = None) -> DiscoveredDevice:
        with self._lock:
            device_id = str(uuid.uuid4())
            device = DiscoveredDevice(
                device_id=device_id, hostname=hostname or socket.gethostname(),
                ip_address=ip_address, port=port, os_type=os_type,
                capabilities=capabilities or [],
            )
            self._devices[device_id] = device
            return device

    def get_devices(self) -> List[DiscoveredDevice]:
        with self._lock:
            return list(self._devices.values())

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"discovered_devices": len(self._devices)}

    def stop(self) -> None:
        self._running = False
