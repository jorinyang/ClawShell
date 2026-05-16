"""WebSocket client for real-time credential change notifications.

Connects to cloud hub's /ws/events endpoint. Listens for credential.change
events and triggers a callback (typically a credential sync).

Thread-based with automatic reconnection on disconnect.
Uses only stdlib — relies on the 'websockets' package if available,
otherwise falls back to a polling-based approach via urllib.
"""

from __future__ import annotations
import json
import time
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Check if websockets is available
try:
    import websockets
    import asyncio
    _HAS_WEBSOCKETS = True
except ImportError:
    _HAS_WEBSOCKETS = False


class CredentialWSClient:
    """WebSocket client that listens for credential change events.

    When a credential.change event is received, calls the on_change callback.
    Runs in a daemon thread. Auto-reconnects on disconnect.

    If the 'websockets' package is not available, falls back to periodic
    polling via the credential sync API (every poll_interval seconds).
    """

    def __init__(
        self,
        cloud_url: str,
        token: str,
        on_change: Optional[Callable[[], None]] = None,
        reconnect_delay: float = 5.0,
        poll_interval: float = 30.0,
    ):
        self._cloud_url = cloud_url.rstrip("/")
        self._token = token
        self._on_change = on_change
        self._reconnect_delay = reconnect_delay
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._lock = threading.RLock()
        self._event_count = 0
        self._last_event_time: Optional[float] = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def event_count(self) -> int:
        return self._event_count

    def start(self):
        """Start listening for credential change events."""
        if self._running:
            return
        self._running = True

        if _HAS_WEBSOCKETS:
            self._thread = threading.Thread(
                target=self._ws_loop, daemon=True, name="cred-ws"
            )
        else:
            self._thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="cred-poll"
            )

        self._thread.start()
        logger.info(
            f"CredentialWSClient started ({'WebSocket' if _HAS_WEBSOCKETS else 'polling'} mode)"
        )

    def stop(self):
        """Stop listening."""
        self._running = False
        with self._lock:
            self._connected = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("CredentialWSClient stopped")

    def get_status(self) -> dict:
        """Get current status."""
        return {
            "running": self._running,
            "connected": self._connected,
            "mode": "websocket" if _HAS_WEBSOCKETS else "polling",
            "event_count": self._event_count,
            "last_event_time": self._last_event_time,
        }

    def update_token(self, token: str):
        """Update the JWT token (e.g., after a refresh)."""
        with self._lock:
            self._token = token

    # ── WebSocket Mode ──────────────────────────────────

    def _ws_loop(self):
        """WebSocket event loop (runs in thread)."""
        while self._running:
            try:
                asyncio.run(self._ws_connect())
            except Exception as e:
                logger.warning(f"WebSocket connection error: {e}")

            with self._lock:
                self._connected = False

            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                time.sleep(self._reconnect_delay)

    async def _ws_connect(self):
        """Connect and listen for events."""
        ws_url = self._cloud_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/events"

        async with websockets.connect(ws_url) as ws:
            with self._lock:
                self._connected = True
            logger.info(f"WebSocket connected to {ws_url}")

            # Set filter for credential events
            await ws.send(json.dumps({
                "type": "filter",
                "event_types": ["credential.change", "credential.create", "credential.update", "credential.delete"]
            }))

            while self._running:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    self._handle_message(msg)
                except asyncio.TimeoutError:
                    # Send ping to keep alive
                    await ws.send(json.dumps({"type": "ping"}))
                except Exception as e:
                    logger.warning(f"WebSocket receive error: {e}")
                    break

    def _handle_message(self, raw_msg: str):
        """Process a WebSocket message."""
        try:
            data = json.loads(raw_msg)
            msg_type = data.get("type", "")
            payload = data.get("data", data.get("payload", {}))
            event_type = payload.get("event_type", "")

            if msg_type == "event_push" or event_type.startswith("credential"):
                logger.info(f"Credential change event received: {event_type}")
                self._event_count += 1
                self._last_event_time = time.time()

                if self._on_change:
                    try:
                        self._on_change()
                    except Exception as e:
                        logger.error(f"on_change callback failed: {e}")

            elif msg_type == "welcome":
                logger.info(f"WebSocket welcome: {payload.get('message', '')}")

        except json.JSONDecodeError:
            logger.warning(f"Non-JSON WebSocket message: {raw_msg[:100]}")

    # ── Polling Fallback ────────────────────────────────

    def _poll_loop(self):
        """Polling-based fallback when websockets package is not available."""
        import urllib.request
        import urllib.error

        last_sync_hash = ""

        while self._running:
            try:
                # Quick check: has credential data changed?
                url = f"{self._cloud_url}/api/v1/credentials/sync"
                headers = {
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/json",
                }
                req = urllib.request.Request(url, headers=headers, method="GET")
                resp = urllib.request.urlopen(req, timeout=10)
                data = json.loads(resp.read().decode("utf-8"))

                # Hash the response to detect changes
                current_hash = str(hash(json.dumps(data, sort_keys=True)))
                with self._lock:
                    self._connected = True

                if current_hash != last_sync_hash and last_sync_hash:
                    logger.info("Credential change detected via polling")
                    self._event_count += 1
                    self._last_event_time = time.time()
                    if self._on_change:
                        try:
                            self._on_change()
                        except Exception as e:
                            logger.error(f"on_change callback failed: {e}")

                last_sync_hash = current_hash

            except Exception as e:
                logger.debug(f"Poll error (expected during offline): {e}")
                with self._lock:
                    self._connected = False

            # Sleep in small increments for fast shutdown
            for _ in range(int(self._poll_interval)):
                if not self._running:
                    break
                time.sleep(1)
