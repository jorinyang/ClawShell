"""GitHub Adapter — GitHub API integration.

Design: Based on DEEP cortex/adapters/github.py + MacOS v2.0.
Provides repository read/write and issue management via GitHub API.
"""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any


class GitHubAdapter:
    """GitHub API adapter for repository and issue management."""

    API_BASE = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, repo: Optional[str] = None):
        """Initialize GitHub adapter.
        
        Args:
            token: GitHub personal access token (or from GITHUB_TOKEN env)
            repo: Repository in owner/name format (or from GITHUB_REPOSITORY env)
        """
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._repo = repo or os.environ.get("GITHUB_REPOSITORY", "")

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        """Make an authenticated GitHub API request."""
        url = f"{self.API_BASE}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ClawShell/1.10.0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        data = json.dumps(body).encode() if body else None
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}", "message": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def get_file(self, path: str, ref: str = "main") -> Optional[str]:
        """Read a file from the repository."""
        result = self._request("GET", f"/repos/{self._repo}/contents/{path}?ref={ref}")
        if "content" in result:
            import base64
            return base64.b64decode(result["content"]).decode("utf-8")
        return None

    def create_issue(self, title: str, body: str = "", labels: Optional[List[str]] = None) -> dict:
        """Create a GitHub issue."""
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        return self._request("POST", f"/repos/{self._repo}/issues", payload)

    def list_issues(self, state: str = "open", limit: int = 10) -> List[dict]:
        """List repository issues."""
        result = self._request(
            "GET", f"/repos/{self._repo}/issues?state={state}&per_page={limit}"
        )
        if isinstance(result, list):
            return result
        return []

    def suggest_optimizations(self, file_paths: List[str]) -> List[str]:
        """Suggest optimization opportunities based on file analysis."""
        suggestions = []
        for path in file_paths:
            content = self.get_file(path)
            if content:
                lines = content.count("\n")
                if lines > 500:
                    suggestions.append(f"Large file: {path} ({lines} lines) — consider splitting")
                if "TODO" in content or "FIXME" in content:
                    suggestions.append(f"TODOs found in: {path}")
        return suggestions

    @property
    def is_configured(self) -> bool:
        """Check if adapter has valid credentials."""
        return bool(self._token and self._repo)
