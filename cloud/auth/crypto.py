"""Cryptographic utilities for ClawShell v2.0 auth system.

Password hashing: bcrypt (available) or hashlib.pbkdf2_hmac fallback.
AES-256-GCM: cryptography lib (available) or XOR+base64 fallback.
JWT: HS256 using hmac+json+base64 (stdlib only).
"""

from __future__ import annotations
import os
import json
import time
import hmac
import hashlib
import base64
import secrets
import logging

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "clawshell-jwt-secret-2026")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "clawshell-enc-key-2026-32b!")
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "24"))

# ── Password Hashing ─────────────────────────────────

try:
    import bcrypt
    _USE_BCRYPT = True
    logger.info("Using bcrypt for password hashing")
except ImportError:
    _USE_BCRYPT = False
    logger.info("bcrypt not available, using hashlib.pbkdf2_hmac")


def hash_password(password: str) -> str:
    """Hash a password. Returns a portable hash string."""
    if _USE_BCRYPT:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    else:
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return f"pbkdf2:sha256:100000${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    if _USE_BCRYPT and not stored_hash.startswith("pbkdf2:"):
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    elif stored_hash.startswith("pbkdf2:"):
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        _, salt, dk_hex = parts
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    else:
        # fallback: try bcrypt first, then pbkdf2
        try:
            if _USE_BCRYPT:
                return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception:
            pass
        return False


# ── AES-256-GCM Encryption ──────────────────────────

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _USE_CRYPTO = True
    logger.info("Using cryptography lib for AES-256-GCM")
except ImportError:
    _USE_CRYPTO = False
    logger.info("cryptography not available, using XOR+base64 fallback")


def _get_aes_key() -> bytes:
    """Derive a 32-byte key from ENCRYPTION_KEY."""
    return hashlib.sha256(ENCRYPTION_KEY.encode("utf-8")).digest()


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    if _USE_CRYPTO:
        key = _get_aes_key()
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # nonce + ciphertext (includes tag)
        return base64.b64encode(nonce + ct).decode("utf-8")
    else:
        # XOR+base64 fallback
        key = _get_aes_key()
        data = plaintext.encode("utf-8")
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return "xor$" + base64.b64encode(xored).decode("utf-8")


def decrypt_value(encrypted: str) -> str:
    """Decrypt a value from encrypt_value()."""
    if encrypted.startswith("xor$"):
        # XOR fallback
        key = _get_aes_key()
        data = base64.b64decode(encrypted[4:])
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return xored.decode("utf-8")
    else:
        # AES-256-GCM
        key = _get_aes_key()
        raw = base64.b64decode(encrypted)
        nonce = raw[:12]
        ct = raw[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")


def mask_value(value: str) -> str:
    """Mask a credential value, showing only last 4 chars."""
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


# ── JWT (HS256, stdlib only) ─────────────────────────

def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_jwt(payload: dict, expires_hours: int = None) -> str:
    """Create a JWT token (HS256)."""
    if expires_hours is None:
        expires_hours = JWT_EXPIRE_HOURS
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {**payload, "iat": now, "exp": now + expires_hours * 3600}
    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_b64_encode(signature)}"


def verify_jwt(token: str) -> dict | None:
    """Verify and decode a JWT. Returns payload or None if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256
        ).digest()
        actual_sig = _b64_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
