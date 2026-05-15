"""Vault REST API router — v1.12.0 (OSS-backed Obsidian vault CRUD)."""
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

vault_router = APIRouter(prefix="/vault", tags=["vault"])


def _get_vault(request: Request = None):
    """Get VaultAPI from app state (with fallback to env-based creation)."""
    if request and hasattr(request.app.state, "vault_api"):
        vault = request.app.state.vault_api
        if vault:
            return vault
    # Fallback: create from environment
    try:
        from cloud.services.vault_api import VaultAPI
        return VaultAPI()
    except Exception:
        raise HTTPException(503, "VaultAPI not available")


@vault_router.get("/status")
async def vault_status(request: Request):
    """Get vault status."""
    vault = _get_vault(request)
    return format_api_response(True, data=vault.get_status())


@vault_router.get("/files")
async def list_files(request: Request, subpath: str = Query("")):
    """List vault markdown files."""
    vault = _get_vault(request)
    files = vault.list_files(subpath)
    return format_api_response(True, data={"files": files, "count": len(files)})


@vault_router.get("/search")
async def search_vault(request: Request, q: str = Query(""), limit: int = Query(10)):
    """Full-text search across vault notes."""
    if not q:
        return format_api_response(False, error="Query parameter 'q' is required")
    vault = _get_vault(request)
    results = vault.search(q, limit=limit)
    return format_api_response(True, data={"query": q, "results": results, "count": len(results)})


@vault_router.get("/note/{path:path}")
async def read_note(path: str, request: Request):
    """Read a markdown note."""
    vault = _get_vault(request)
    note = vault.read_note(path)
    if not note:
        return format_api_response(False, error=f"Note not found: {path}")
    return format_api_response(True, data=note)


@vault_router.post("/note/{path:path}")
async def write_note(path: str, request: Request):
    """Create or update a markdown note."""
    try:
        body = await request.json()
    except Exception:
        return format_api_response(False, error="Invalid JSON body")
    content = body.get("content", "")
    if not content:
        return format_api_response(False, error="content is required")
    try:
        vault = _get_vault(request)
        result = vault.write_note(path, content)
        return format_api_response(True, data=result)
    except ValueError as e:
        return format_api_response(False, error=str(e))


@vault_router.delete("/note/{path:path}")
async def delete_note(path: str, request: Request):
    """Delete a markdown note."""
    vault = _get_vault(request)
    ok = vault.delete_note(path)
    if not ok:
        return format_api_response(False, error=f"Note not found: {path}")
    return format_api_response(True, data={"path": path, "deleted": True})


@vault_router.post("/sync/push")
async def vault_sync_push(request: Request):
    """Push local vault to OSS."""
    vault = _get_vault(request)
    result = vault.sync_push()
    return format_api_response(True, data=result)


@vault_router.post("/sync/pull")
async def vault_sync_pull(request: Request):
    """Pull OSS vault to local."""
    vault = _get_vault(request)
    result = vault.sync_pull()
    return format_api_response(True, data=result)
