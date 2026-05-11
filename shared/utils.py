"""Shared utility functions."""

from __future__ import annotations
import hashlib
import json
import time
import re
from typing import Any, Dict, Optional


def content_hash(data: Any) -> str:
    """SHA256 hash of any JSON-serializable content."""
    raw = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def timestamp_now() -> float:
    """Current Unix timestamp."""
    return time.time()


def safe_json_dumps(obj: Any, indent: int = 2) -> str:
    """JSON dump without throwing on non-serializable types."""
    return json.dumps(obj, ensure_ascii=False, indent=indent, default=str)


def safe_json_loads(s: str) -> Optional[Any]:
    """JSON load without throwing."""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def validate_node_id(node_id: str) -> bool:
    """Validate node_id format: alphanumeric + hyphens, 4-64 chars."""
    return bool(re.match(r'^[a-zA-Z0-9\-_]{4,64}$', node_id))


def generate_node_id(hostname: str = "", prefix: str = "edge") -> str:
    """Generate a unique node_id from hostname."""
    import uuid
    if hostname:
        short = hashlib.md5(hostname.encode()).hexdigest()[:8]
        return f"{prefix}-{short}"
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def truncate_string(s: str, max_len: int = 500) -> str:
    """Truncate a string with ellipsis."""
    if len(s) <= max_len:
        return s
    return s[:max_len - 3] + "..."


def match_wildcard(pattern: str, text: str) -> bool:
    """Simple wildcard matching: * matches any sequence."""
    import fnmatch
    return fnmatch.fnmatch(text, pattern)


def now_iso() -> str:
    """Current time as ISO 8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
