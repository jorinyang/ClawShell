"""Vault Router — Obsidian knowledge vault REST API.

Endpoints (mounted at /api/v1):
  GET    /vault/status
  GET    /vault/files
  GET    /vault/search
  GET    /vault/note/{path:path}
  POST   /vault/note/{path:path}
  DELETE /vault/note/{path:path}
  POST   /vault/sync/push
  POST   /vault/sync/pull
"""

from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/vault", tags=["vault"])


class NoteWrite(BaseModel):
    content: str


class VaultRequest(BaseModel):
    user_id: str = ""


def _get_vault(request: Request):
    """Resolve VaultAPI from app.state."""
    # Check app.state first (test fixtures), then sys.modules (production)
    app = getattr(request, "app", None)
    if app and hasattr(app.state, "vault_api"):
        return app.state.vault_api

    import sys
    for mod_name in ("__main__", "cloud.main"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_vault_api"):
            return getattr(mod, "_vault_api")

    # Fallback: create on demand
    import os
    from cloud.services.vault_api import VaultAPI
    vault_path = os.path.expanduser("~/Documents/Obsidian")
    return VaultAPI(vault_path=vault_path, user_id="")


@router.get("/status")
async def vault_status(request: Request):
    return _get_vault(request).get_status()


@router.get("/files")
async def vault_files(request: Request, subpath: str = ""):
    return {"files": _get_vault(request).list_files(subpath)}


@router.get("/search")
async def vault_search(request: Request, q: str = "", limit: int = 20):
    if not q:
        return {"results": []}
    return {"results": _get_vault(request).search(q, limit=limit)}


@router.get("/note/{path:path}")
async def vault_read(request: Request, path: str):
    note = _get_vault(request).read_note(path)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    return note


@router.post("/note/{path:path}")
async def vault_write(request: Request, path: str, body: NoteWrite):
    return _get_vault(request).write_note(path, body.content)


@router.delete("/note/{path:path}")
async def vault_delete(request: Request, path: str):
    ok = _get_vault(request).delete_note(path)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    return {"deleted": path}


@router.post("/sync/push")
async def vault_sync_push(request: Request):
    return _get_vault(request).sync_push()


@router.post("/sync/pull")
async def vault_sync_pull(request: Request):
    return _get_vault(request).sync_pull()
