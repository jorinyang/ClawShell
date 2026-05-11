"""OSS Vault sync engine — Bidirectional sync between local Obsidian vault and Alibaba Cloud OSS.

Uses ossutil CLI for reliable sync operations.
"""

from __future__ import annotations
import os
import json
import time
import subprocess
import hashlib
import threading
import fnmatch
from typing import Dict, List, Optional, Callable


class OSSVaultSync:
    """Bidirectional sync engine for Obsidian vault ↔ OSS."""

    def __init__(self, vault_path: str, oss_bucket: str,
                 oss_endpoint: str = "", oss_key_id: str = "",
                 oss_key_secret: str = ""):
        self._vault_path = vault_path
        self._oss_bucket = oss_bucket
        self._oss_endpoint = oss_endpoint
        self._oss_key_id = oss_key_id or os.environ.get("CLAWSHELL_ALIYUN_AK_ID", "")
        self._oss_key_secret = oss_key_secret or os.environ.get("CLAWSHELL_ALIYUN_AK_SECRET", "")
        self._oss_prefix = f"oss://{self._oss_bucket}/vault/"

        self._lock = threading.RLock()
        self._file_hashes: Dict[str, str] = {}
        self._watchers: List[Callable] = []

        self._running = False
        self._watch_thread: Optional[threading.Thread] = None

    # ── Sync Operations ────────────────────────────

    def push(self, dry_run: bool = False) -> dict:
        """Push local changes to OSS."""
        return self._run_sync("push", self._vault_path, self._oss_prefix, dry_run)

    def pull(self, dry_run: bool = False) -> dict:
        """Pull remote changes from OSS."""
        return self._run_sync("pull", self._oss_prefix, self._vault_path, dry_run)

    def sync(self, dry_run: bool = False) -> dict:
        """Bidirectional sync (push then pull)."""
        push_result = self.push(dry_run)
        pull_result = self.pull(dry_run)
        return {
            "push": push_result,
            "pull": pull_result,
            "timestamp": time.time(),
        }

    # ── Change Detection ───────────────────────────

    def scan_changes(self) -> List[dict]:
        """Scan vault for changed files (MD5-based)."""
        changes = []
        current_hashes = {}

        for root, dirs, filenames in os.walk(self._vault_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, self._vault_path)
                ch = self._file_hash(fp)
                current_hashes[rel] = ch

                old_hash = self._file_hashes.get(rel)
                if old_hash is None:
                    changes.append({"path": rel, "change": "added", "hash": ch})
                elif old_hash != ch:
                    changes.append({"path": rel, "change": "modified", "hash": ch})

        # Detect deletions
        for rel in self._file_hashes:
            if rel not in current_hashes:
                changes.append({"path": rel, "change": "deleted", "hash": None})

        with self._lock:
            self._file_hashes = current_hashes

        return changes

    # ── Watch Mode ─────────────────────────────────

    def start_watch(self, interval: int = 30):
        """Start watching for changes (auto-push on change)."""
        if self._running:
            return
        self._running = True
        self._watch_thread = threading.Thread(
            target=self._watch_loop, args=(interval,), daemon=True
        )
        self._watch_thread.start()

    def stop_watch(self):
        self._running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=10)

    def on_change(self, callback: Callable):
        """Register a callback for file changes."""
        self._watchers.append(callback)

    def _watch_loop(self, interval: int):
        while self._running:
            changes = self.scan_changes()
            if changes:
                self.push()
                for cb in self._watchers:
                    try:
                        cb(changes)
                    except Exception:
                        pass
            for _ in range(int(interval)):
                if not self._running:
                    break
                time.sleep(1)

    # ── Stats ──────────────────────────────────────

    def get_stats(self) -> dict:
        """Get vault sync statistics."""
        md_count = 0
        total_size = 0
        if os.path.isdir(self._vault_path):
            for root, dirs, filenames in os.walk(self._vault_path):
                for fn in filenames:
                    if fn.endswith(".md"):
                        md_count += 1
                        total_size += os.path.getsize(os.path.join(root, fn))

        return {
            "vault_path": self._vault_path,
            "oss_bucket": self._oss_bucket,
            "md_files": md_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "tracked_hashes": len(self._file_hashes),
            "oss_configured": bool(self._oss_key_id),
        }

    # ── Internal ──────────────────────────────────

    def _run_sync(self, direction: str, source: str, dest: str,
                  dry_run: bool = False) -> dict:
        """Execute ossutil sync command."""
        if not self._oss_key_id:
            return {"status": "skipped", "reason": "OSS credentials not configured"}

        endpoint_arg = [f"--endpoint={self._oss_endpoint}"] if self._oss_endpoint else []
        dry_arg = ["--dry-run"] if dry_run else []
        cmd = ["ossutil", "sync", source, dest, "--update"] + endpoint_arg + dry_arg

        try:
            env = os.environ.copy()
            env["OSS_ACCESS_KEY_ID"] = self._oss_key_id
            env["OSS_ACCESS_KEY_SECRET"] = self._oss_key_secret

            start = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
            return {
                "status": "ok" if result.returncode == 0 else "error",
                "direction": direction,
                "returncode": result.returncode,
                "duration_s": round(time.time() - start, 2),
                "stdout_tail": result.stdout[-300:],
                "stderr_tail": result.stderr[-300:],
            }
        except FileNotFoundError:
            return {"status": "error", "error": "ossutil not installed. Install: pip install ossutil"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Sync timed out (>300s)"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def _file_hash(filepath: str) -> str:
        """MD5 hash of file content."""
        try:
            with open(filepath, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
