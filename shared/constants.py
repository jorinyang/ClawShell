"""Shared constants for ClawShell 2.0 Cloud↔Edge."""

# ── Ports ────────────────────────────────────────────
DEFAULT_CLOUD_API_PORT = 8000
DEFAULT_CLOUD_WS_PORT = 8000
DEFAULT_EDGE_MCP_PORT = 17655
DEFAULT_EDGE_BROWSER_PORT = 4240
DEFAULT_N8N_PORT = 5678

# ── Timeouts (seconds) ───────────────────────────────
DEFAULT_REQUEST_TIMEOUT = 30
EDGE_SYNC_INTERVAL = 5
HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 90
EVENT_EXPIRY_DAYS = 30
DAEMON_FIVE_SEC_CHUNK = 5

# ── Queue limits ─────────────────────────────────────
OFFLINE_QUEUE_MAX = 500
OFFLINE_QUEUE_TRIM = 300

# ── EventBus ─────────────────────────────────────────
EVENT_STORE_DIR = "data/eventbus"
DEFAULT_EVENT_BATCH_SIZE = 100

# ── API paths ────────────────────────────────────────
API_V1_PREFIX = "/api/v1"
WS_EVENTS_PATH = "/ws/events"

# ── Resource limits ──────────────────────────────────
MAX_EVENT_PAYLOAD_BYTES = 1_048_576  # 1 MB
MAX_TASK_PAYLOAD_BYTES = 5_242_880   # 5 MB
