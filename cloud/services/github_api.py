"""GitHub API service — Repository management for user skill/knowledge repos.

Creates and manages per-user GitHub repositories:
  {pinyin_prefix}-skills   — User skill library
  {pinyin_prefix}-knowledge — User knowledge library

Uses GitHub Personal Access Token from CLAWSHELL_GITHUB_TOKEN env var.
"""
from __future__ import annotations
import json
import logging
import re
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubAPI:
    """GitHub REST API client for repository CRUD."""

    def __init__(self, token: str = ""):
        self._token = token

    # ── Repo CRUD ──────────────────────────────────────

    def create_repo(self, name: str, description: str = "",
                    private: bool = False) -> dict:
        """Create a new GitHub repository under the authenticated user."""
        payload = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": True,
        }
        return self._post("/user/repos", payload)

    def repo_exists(self, name: str) -> bool:
        """Check if a repository already exists under the authenticated user."""
        user = self._get_authenticated_user()
        if not user:
            return False
        try:
            self._get(f"/repos/{user}/{name}")
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            raise

    def find_available_name(self, prefix: str, suffix: str) -> str:
        """Find an available repo name: {prefix}-{suffix}, {prefix}2-{suffix}, etc."""
        candidate = f"{prefix}-{suffix}"
        if not self.repo_exists(candidate):
            return candidate
        for i in range(2, 100):
            candidate = f"{prefix}{i}-{suffix}"
            if not self.repo_exists(candidate):
                return candidate
        raise RuntimeError(f"Could not find available repo name for {prefix}-{suffix}")

    def get_repo_clone_url(self, name: str) -> str:
        """Get the HTTPS clone URL for a repository."""
        user = self._get_authenticated_user()
        return f"https://github.com/{user}/{name}.git"

    def push_file(self, repo_name: str, path: str, content: str,
                  message: str = "") -> dict:
        """Create or update a single file in a repository."""
        if not message:
            message = f"Update {path}"
        user = self._get_authenticated_user()
        api_path = f"/repos/{user}/{repo_name}/contents/{path}"
        payload = {
            "message": message,
            "content": _encode_b64(content),
        }
        return self._put(api_path, payload)

    def list_skills(self, repo_name: str, path: str = "") -> list[str]:
        """List skill directories in a skills repo."""
        user = self._get_authenticated_user()
        api_path = f"/repos/{user}/{repo_name}/contents/{path}"
        result = self._get(api_path)
        dirs = []
        if isinstance(result, list):
            dirs = [r["name"] for r in result if r.get("type") == "dir"]
        return dirs

    def read_file(self, repo_name: str, path: str) -> Optional[str]:
        """Read a file from a repository."""
        user = self._get_authenticated_user()
        api_path = f"/repos/{user}/{repo_name}/contents/{path}"
        try:
            result = self._get(api_path)
            if isinstance(result, dict) and result.get("content"):
                import base64
                return base64.b64decode(result["content"]).decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        return None

    # ── Internal HTTP ──────────────────────────────────

    def _get(self, path: str) -> Any:
        return self._request("GET", path)

    def _post(self, path: str, data: dict) -> dict:
        return self._request("POST", path, data)

    def _put(self, path: str, data: dict) -> dict:
        return self._request("PUT", path, data)

    def _request(self, method: str, path: str, data: Optional[dict] = None) -> Any:
        url = f"{GITHUB_API}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ClawShell/3.0",
        }
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            body_str = ""
            try:
                body_str = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            logger.error(f"GitHub API {method} {path} → {e.code}: {body_str}")
            raise

    def _get_authenticated_user(self) -> str:
        """Get the login of the authenticated user."""
        if not hasattr(self, "_cached_user"):
            result = self._get("/user")
            self._cached_user = result.get("login", "")
        return self._cached_user


def _encode_b64(s: str) -> str:
    import base64
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def generate_pinyin_prefix(display_name: str) -> str:
    """Generate pinyin prefix from Chinese display name.

    Falls back gracefully if pypinyin is not installed.
    """
    # Common surname mapping (fallback when pypinyin not available)
    _SURNAME_MAP: dict[str, str] = {
        "李": "l", "王": "w", "张": "z", "刘": "l", "陈": "c",
        "杨": "y", "赵": "z", "黄": "h", "周": "z", "吴": "w",
        "徐": "x", "孙": "s", "胡": "h", "朱": "z", "高": "g",
        "林": "l", "何": "h", "郭": "g", "马": "m", "罗": "l",
        "梁": "l", "宋": "s", "郑": "z", "谢": "x", "韩": "h",
        "唐": "t", "冯": "f", "于": "y", "董": "d", "萧": "x",
        "程": "c", "曹": "c", "袁": "y", "邓": "d", "许": "x",
        "傅": "f", "沈": "s", "曾": "z", "彭": "p", "吕": "l",
        "苏": "s", "卢": "l", "蒋": "j", "蔡": "c", "贾": "j",
        "丁": "d", "魏": "w", "薛": "x", "叶": "y", "阎": "y",
        "余": "y", "潘": "p", "杜": "d", "戴": "d", "夏": "x",
        "钟": "z", "汪": "w", "田": "t", "任": "r", "姜": "j",
        "范": "f", "方": "f", "石": "s", "姚": "y", "谭": "t",
        "廖": "l", "邹": "z", "熊": "x", "金": "j", "陆": "l",
        "郝": "h", "孔": "k", "白": "b", "崔": "c", "康": "k",
        "月": "y", "星": "x", "云": "y", "风": "f", "龙": "l",
    }

    try:
        from pypinyin import lazy_pinyin
        pinyin_list = lazy_pinyin(display_name)
        initials = "".join([p[0] for p in pinyin_list if p]).lower()
        if initials:
            return initials
    except ImportError:
        pass

    # Fallback: map each character through surname table
    result = ""
    for ch in display_name:
        if ch in _SURNAME_MAP:
            result += _SURNAME_MAP[ch]
        elif "a" <= ch.lower() <= "z":
            result += ch.lower()
    return result[:4] if result else "user"


def sanitize_repo_name(name: str) -> str:
    """Sanitize a repository name to GitHub-compatible format."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\-_]", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name[:100]
