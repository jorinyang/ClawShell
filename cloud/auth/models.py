"""Pydantic v2 models for ClawShell v2.0 auth system."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ── User Models ──────────────────────────────────────

class UserCreate(BaseModel):
    account_id: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=6, max_length=256)
    role: str = Field(default="user", pattern="^(user|admin|core_admin)$")


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=128)
    role: Optional[str] = Field(None, pattern="^(user|admin|core_admin)$")
    is_active: Optional[int] = None


class UserResponse(BaseModel):
    user_id: str
    account_id: str
    display_name: str
    role: str
    must_change_pwd: int
    is_active: int
    created_at: str
    updated_at: str


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


class PasswordChange(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=256)


# ── Credential Type Constants ────────────────────────

CRED_TYPE_API_KEY = "api-key"
CRED_TYPE_ACCESS_KEY = "access-key"
CRED_TYPE_TOKEN_PLAN = "token-plan"
CRED_TYPE_LEGACY = "legacy"

VALID_CRED_TYPES = [CRED_TYPE_API_KEY, CRED_TYPE_ACCESS_KEY, CRED_TYPE_TOKEN_PLAN]


# ── Credential Models ────────────────────────────────

class CredentialCreate(BaseModel):
    """Create a credential. Fields vary by cred_type."""
    service: str = Field(..., min_length=1, max_length=128)
    cred_type: str = Field(..., pattern="^(api-key|access-key|token-plan)$")
    name: str = Field(..., min_length=1, max_length=256)
    # API-KEY fields
    api_key: Optional[str] = Field(None, max_length=4096)
    base_url: Optional[str] = Field(None, max_length=1024)
    # AccessKey fields
    access_key_id: Optional[str] = Field(None, max_length=4096)
    access_key_secret: Optional[str] = Field(None, max_length=4096)
    # Token Plan fields
    model: Optional[str] = Field(None, max_length=256)
    description: str = Field(default="", max_length=512)


class CredentialUpdate(BaseModel):
    """Update a credential. Only send fields you want to change."""
    service: Optional[str] = Field(None, max_length=128)
    name: Optional[str] = Field(None, max_length=256)
    # API-KEY fields
    api_key: Optional[str] = Field(None, max_length=4096)
    base_url: Optional[str] = Field(None, max_length=1024)
    # AccessKey fields
    access_key_id: Optional[str] = Field(None, max_length=4096)
    access_key_secret: Optional[str] = Field(None, max_length=4096)
    # Token Plan fields
    model: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = Field(None, max_length=512)


class CredentialResponse(BaseModel):
    """Credential response. Sensitive fields are masked."""
    cred_id: str
    user_id: str
    service: str
    cred_type: str
    name: str
    description: str
    # Type-specific fields (masked)
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    model: Optional[str] = None
    # Legacy compat
    cred_key: Optional[str] = None
    cred_value_masked: Optional[str] = None
    created_at: str
    updated_at: str


class CredentialSyncResponse(BaseModel):
    """Sync response: user's creds + shared creds, grouped by service."""
    user_credentials: Dict[str, List[CredentialResponse]]
    shared_credentials: Dict[str, List["SharedCredentialResponse"]]


# ── Shared Credential Models ─────────────────────────

class SharedCredentialCreate(BaseModel):
    service: str = Field(..., min_length=1, max_length=128)
    cred_type: str = Field(default=CRED_TYPE_LEGACY, pattern="^(api-key|access-key|token-plan|legacy)$")
    name: str = Field(default="", max_length=256)
    cred_key: str = Field(default="", max_length=256)
    cred_value: str = Field(default="", max_length=4096)
    api_key: Optional[str] = Field(None, max_length=4096)
    base_url: Optional[str] = Field(None, max_length=1024)
    access_key_id: Optional[str] = Field(None, max_length=4096)
    access_key_secret: Optional[str] = Field(None, max_length=4096)
    model: Optional[str] = Field(None, max_length=256)
    description: str = Field(default="", max_length=512)


class SharedCredentialUpdate(BaseModel):
    service: Optional[str] = Field(None, max_length=128)
    name: Optional[str] = Field(None, max_length=256)
    cred_key: Optional[str] = Field(None, max_length=256)
    cred_value: Optional[str] = Field(None, max_length=4096)
    api_key: Optional[str] = Field(None, max_length=4096)
    base_url: Optional[str] = Field(None, max_length=1024)
    access_key_id: Optional[str] = Field(None, max_length=4096)
    access_key_secret: Optional[str] = Field(None, max_length=4096)
    model: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = Field(None, max_length=512)


class SharedCredentialResponse(BaseModel):
    sc_id: str
    service: str
    cred_type: str = CRED_TYPE_LEGACY
    name: str = ""
    description: str
    created_by: str
    created_at: str
    updated_at: str
    # Type-specific fields (masked)
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    model: Optional[str] = None
    # Legacy compat
    cred_key: Optional[str] = None
    cred_value_masked: Optional[str] = None


# ── Auth / Session Models ────────────────────────────

class LoginRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
    must_change_pwd: int


class TokenResponse(BaseModel):
    token: str
    expires_at: str


class RegisterRequest(BaseModel):
    account_id: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=6, max_length=256)


# ── Audit Log Models ─────────────────────────────────

class AuditLogResponse(BaseModel):
    log_id: int
    user_id: Optional[str]
    action: str
    target: str
    details: str
    ip_address: str
    timestamp: str


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogResponse]
    total: int


# ── Admin / Dashboard Models ─────────────────────────

class NodeUpdate(BaseModel):
    node_name: Optional[str] = None
    node_type: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Optional[str] = None
    frameworks: Optional[str] = None
    ide_tools: Optional[str] = None
    user_id: Optional[str] = None


class EndpointConfig(BaseModel):
    endpoints: Dict[str, Any]


class DashboardResponse(BaseModel):
    total_users: int
    active_users: int
    total_credentials: int
    total_shared_credentials: int
    total_nodes: int
    online_nodes: int
    active_sessions: int
    recent_audit_count: int


class SystemInfoResponse(BaseModel):
    version: str
    database_path: str
    total_users: int
    total_credentials: int
    total_shared_credentials: int
    total_nodes: int
    total_sessions: int
    total_audit_logs: int
    uptime: Optional[str] = None
