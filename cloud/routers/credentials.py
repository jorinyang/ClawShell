"""Credentials router: user-scoped credential CRUD + sync."""

from fastapi import APIRouter, Request, HTTPException
from cloud.auth.models import CredentialCreate, CredentialResponse, CredentialUpdate
from cloud.auth.credential_service import CredentialService
from cloud.auth.audit_service import AuditService
from cloud.auth.session_service import SessionService

router = APIRouter(prefix="/credentials", tags=["Credentials"])


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _require_auth(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    payload = SessionService.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


@router.post("", response_model=CredentialResponse)
async def create_credential(data: CredentialCreate, request: Request):
    payload = _require_auth(request)
    try:
        cred = CredentialService.create_credential(payload["sub"], data)
        AuditService.log(payload["sub"], "cred_create", target=data.service, ip=_get_client_ip(request))
        return cred
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[CredentialResponse])
async def list_credentials(request: Request):
    payload = _require_auth(request)
    return CredentialService.get_user_credentials(payload["sub"])


@router.get("/sync")
async def sync_credentials(request: Request):
    payload = _require_auth(request)
    return CredentialService.sync_credentials(payload["sub"])


@router.put("/{cred_id}", response_model=CredentialResponse)
async def update_credential(cred_id: str, data: CredentialUpdate, request: Request):
    payload = _require_auth(request)
    try:
        cred = CredentialService.update_credential(cred_id, payload["sub"], data)
    except ValueError:
        raise HTTPException(status_code=404, detail="Credential not found")
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    AuditService.log(payload["sub"], "cred_update", target=cred_id, ip=_get_client_ip(request))
    return cred


@router.delete("/{cred_id}")
async def delete_credential(cred_id: str, request: Request):
    payload = _require_auth(request)
    CredentialService.delete_credential(cred_id, payload["sub"])
    AuditService.log(payload["sub"], "cred_delete", target=cred_id, ip=_get_client_ip(request))
    return {"status": "ok", "message": "Credential deleted"}
