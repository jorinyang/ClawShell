"""Vault API — Obsidian knowledge vault CRUD + search via Alibaba Cloud OSS.

Endpoints:
- GET    /vault/status — Vault sync status
- GET    /vault/files — List vault files
- GET    /vault/search?q= — Full-text search
- GET    /vault/note/{path} — Read a note
- POST   /vault/note/{path} — Create/update a note
- DELETE /vault/note/{path} — Delete a note
- POST   /vault/sync/push — Trigger OSS push
- POST   /vault/sync/pull — Trigger OSS pull
"""

from __future__ import annotations
import os
import json
import subprocess
import time
from typing import Dict, List, Optional


class VaultAPI:
    """Obsidian vault CRUD + OSS sync API."""

    def __init__(self, vault_path: str = "", oss_bucket: str = "",
                 oss_endpoint: str = "", oss_key_id: str = "",
                 oss_key_secret: str = ""):
        self._vault_path = vault_path or os.environ.get("CLAWSHELL_VAULT_PATH", "")
        self._oss_bucket = oss_bucket or os.environ.get("CLAWSHELL_OSS_BUCKET", "clawshell-vault")
        self._oss_endpoint = oss_endpoint or os.environ.get("CLAWSHELL_OSS_ENDPOINT", "")
        self._oss_key_id = oss_key_id or os.environ.get("CLAWSHELL_ALIYUN_AK_ID", "")
        self._oss_key_secret = oss_key_secret or os.environ.get("CLAWSHELL_ALIYUN_AK_SECRET", "")

        self._last_sync = 0.0
        self._sync_log: List[dict] = []

    # ── Status ─────────────────────────────────────

    def get_status(self) -> dict:
        """Get vault status."""
        files = []
        if self._vault_path and os.path.isdir(self._vault_path):
            for root, dirs, filenames in os.walk(self._vault_path):
                for fn in filenames:
                    if fn.endswith(".md"):
                        fp = os.path.join(root, fn)
                        rel = os.path.relpath(fp, self._vault_path)
                        files.append({
                            "path": rel,
                            "size": os.path.getsize(fp),
                            "modified": os.path.getmtime(fp),
                        })

        return {
            "vault_path": self._vault_path,
            "oss_bucket": self._oss_bucket,
            "total_files": len(files),
            "last_sync": self._last_sync,
            "oss_configured": bool(self._oss_key_id and self._oss_endpoint),
        }

    # ── CRUD ───────────────────────────────────────

    def list_files(self, subpath: str = "") -> List[dict]:
        """List vault markdown files."""
        if not self._vault_path:
            return []

        base = os.path.join(self._vault_path, subpath) if subpath else self._vault_path
        if not os.path.isdir(base):
            return []

        files = []
        for root, dirs, filenames in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in filenames:
                if fn.endswith(".md"):
                    fp = os.path.join(root, fn)
                    files.append({
                        "path": os.path.relpath(fp, self._vault_path),
                        "size": os.path.getsize(fp),
                        "modified": os.path.getmtime(fp),
                    })
        return files

    def read_note(self, path: str) -> Optional[dict]:
        """Read a markdown note."""
        fp = self._safe_path(path)
        if not fp or not os.path.isfile(fp):
            return None

        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "path": path,
            "content": content,
            "size": len(content),
            "modified": os.path.getmtime(fp),
        }

    def write_note(self, path: str, content: str) -> dict:
        """Create or update a markdown note."""
        fp = self._safe_path(path)
        if not fp:
            raise ValueError(f"Invalid path: {path}")

        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)

        return {"path": path, "size": len(content), "written": True}

    def delete_note(self, path: str) -> bool:
        """Delete a markdown note."""
        fp = self._safe_path(path)
        if not fp or not os.path.isfile(fp):
            return False
        os.remove(fp)
        return True

    def search(self, query: str, limit: int = 20) -> List[dict]:
        """Full-text search across vault notes."""
        if not self._vault_path:
            return []

        results = []
        q = query.lower()
        for root, dirs, filenames in os.walk(self._vault_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue

                if q in content.lower():
                    # Find context around match
                    idx = content.lower().find(q)
                    start = max(0, idx - 80)
                    end = min(len(content), idx + len(q) + 80)
                    context = content[start:end]

                    results.append({
                        "path": os.path.relpath(fp, self._vault_path),
                        "context": context,
                        "match_position": idx,
                    })

                if len(results) >= limit:
                    break

        return results

    # ── OSS Sync ───────────────────────────────────

    def sync_push(self) -> dict:
        """Push local vault to OSS."""
        if not self._oss_key_id:
            return {"status": "skipped", "reason": "OSS not configured"}

        result = self._run_ossutil("sync", self._vault_path,
                                   f"oss://{self._oss_bucket}/vault/",
                                   "--update")
        self._last_sync = time.time()
        self._log_sync("push", result)
        return result

    def sync_pull(self) -> dict:
        """Pull OSS vault to local."""
        if not self._oss_key_id:
            return {"status": "skipped", "reason": "OSS not configured"}

        result = self._run_ossutil("sync",
                                   f"oss://{self._oss_bucket}/vault/",
                                   self._vault_path,
                                   "--update")
        self._last_sync = time.time()
        self._log_sync("pull", result)
        return result

    # ── Internal ──────────────────────────────────

    def _safe_path(self, path: str) -> Optional[str]:
        """Prevent path traversal."""
        if not self._vault_path:
            return None
        # Normalize and check for traversal
        full = os.path.normpath(os.path.join(self._vault_path, path))
        if not full.startswith(os.path.normpath(self._vault_path)):
            return None
        return full

    def _run_ossutil(self, *args) -> dict:
        """Run ossutil command."""
        try:
            env = os.environ.copy()
            env["OSS_ACCESS_KEY_ID"] = self._oss_key_id
            env["OSS_ACCESS_KEY_SECRET"] = self._oss_key_secret
            cmd = ["ossutil"] + list(args) + [
                f"--endpoint={self._oss_endpoint}"
            ] if self._oss_endpoint else ["ossutil"] + list(args)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
            return {
                "status": "ok" if result.returncode == 0 else "error",
                "stdout": result.stdout[-500:],
                "stderr": result.stderr[-500:],
            }
        except FileNotFoundError:
            return {"status": "error", "error": "ossutil not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _log_sync(self, direction: str, result: dict):
        self._sync_log.append({
            "direction": direction,
            "timestamp": time.time(),
            "result": result,
        })
        if len(self._sync_log) > 50:
            self._sync_log = self._sync_log[-25:]
