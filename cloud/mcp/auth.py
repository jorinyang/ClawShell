"""MCP Authentication — JWT token generation and verification.

Simple HS256 JWT implementation using stdlib only.
For production use, integrate with PyJWT library.

Added in v1.8.1 from ClawShell-MacOS.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional


def generate_jwt(payload: Dict[str, Any], secret: str,
                 expiry_seconds: int = 3600) -> str:
    """Generate a simple HS256 JWT token.

    Args:
        payload: Claims to include (sub, edge_id, etc.)
        secret: HMAC secret key
        expiry_seconds: Token lifetime in seconds

    Returns:
        JWT token string (header.payload.signature)
    """
    header = {"alg": "HS256", "typ": "JWT"}

    now = int(time.time())
    payload.update({
        "iat": now,
        "exp": now + expiry_seconds,
        "jti": str(uuid.uuid4()),
    })

    def b64encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header_b64 = b64encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = b64encode(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()
    signature_b64 = b64encode(signature)

    return f"{signing_input}.{signature_b64}"


def verify_jwt(token: str, secret: str,
               aud: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Verify a JWT token and return payload if valid.

    Returns None if token is invalid, expired, or signature doesn't match.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts

        # Reconstruct and verify signature
        def b64decode(data: str) -> bytes:
            # Add padding
            data += "=" * (4 - len(data) % 4)
            return base64.urlsafe_b64decode(data)

        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            secret.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()

        actual_sig = b64decode(signature_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        payload = json.loads(b64decode(payload_b64))

        # Check expiry
        now = int(time.time())
        if payload.get("exp", 0) < now:
            return None

        # Check audience
        if aud and payload.get("aud") != aud:
            return None

        return payload

    except Exception:
        return None


def generate_edge_token(edge_id: str, secret: str,
                         expiry_seconds: int = 3600) -> str:
    """Generate a JWT token for an Edge node."""
    return generate_jwt({
        "sub": edge_id,
        "edge_id": edge_id,
        "type": "edge",
    }, secret, expiry_seconds)
