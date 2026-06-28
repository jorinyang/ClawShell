"""KnowledgeHeritage — versioned knowledge storage (知识传承).

File-based JSON storage for versioned knowledge entries with tag-based querying.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class KnowledgeHeritage:
    """Versioned knowledge store with file-based JSON persistence.

    Each knowledge entry is stored with version history, tags, and metadata.
    """

    def __init__(self, storage_path: str = None):
        self._storage_path = Path(storage_path or os.path.expanduser("~/.clawshell/genome/heritage"))
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, knowledge_id: str) -> Path:
        return self._storage_path / f"{knowledge_id}.json"

    def _load_entry(self, knowledge_id: str) -> Optional[Dict]:
        path = self._entry_path(knowledge_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_entry(self, knowledge_id: str, data: Dict):
        path = self._entry_path(knowledge_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def store_knowledge(self, knowledge_id: str, content: str, version: str = None, tags: List[str] = None) -> Dict:
        """Store a knowledge entry with versioning.

        Args:
            knowledge_id: Unique identifier for the knowledge
            content: The knowledge content
            version: Version string (auto-incremented if not provided)
            tags: Optional tags for categorization

        Returns:
            The stored knowledge entry
        """
        entry = self._load_entry(knowledge_id)
        if entry is None:
            entry = {"knowledge_id": knowledge_id, "versions": [], "tags": tags or []}

        # Determine version
        if version is None:
            if entry["versions"]:
                last_ver = entry["versions"][-1]["version"]
                # Try to auto-increment numeric versions
                try:
                    parts = last_ver.split(".")
                    parts[-1] = str(int(parts[-1]) + 1)
                    version = ".".join(parts)
                except (ValueError, IndexError):
                    version = f"{last_ver}.1"
            else:
                version = "1.0"

        # Add new version
        entry["versions"].append({
            "version": version,
            "content": content,
            "timestamp": time.time(),
        })

        # Merge tags
        if tags:
            existing = set(entry.get("tags", []))
            existing.update(tags)
            entry["tags"] = sorted(existing)

        self._save_entry(knowledge_id, entry)
        return entry["versions"][-1]

    def get_knowledge(self, knowledge_id: str, version: str = None) -> Optional[Dict]:
        """Retrieve a knowledge entry by ID and optional version.

        Args:
            knowledge_id: Unique identifier
            version: Specific version to retrieve, or None for latest

        Returns:
            The knowledge version entry, or None if not found
        """
        entry = self._load_entry(knowledge_id)
        if not entry or not entry.get("versions"):
            return None

        if version is None:
            return entry["versions"][-1]

        for v in entry["versions"]:
            if v["version"] == version:
                return v
        return None

    def list_knowledge(self, category: str = None, tags: List[str] = None) -> List[Dict]:
        """List knowledge entries with optional filtering.

        Args:
            category: Filter by category (matches knowledge_id prefix)
            tags: Filter by tags (must have ALL specified tags)

        Returns:
            List of matching knowledge entries (latest version summary)
        """
        results = []
        for path in self._storage_path.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            # Category filter
            if category and not entry.get("knowledge_id", "").startswith(category):
                continue

            # Tags filter
            if tags:
                entry_tags = set(entry.get("tags", []))
                if not set(tags).issubset(entry_tags):
                    continue

            latest = entry["versions"][-1] if entry.get("versions") else {}
            results.append({
                "knowledge_id": entry.get("knowledge_id"),
                "tags": entry.get("tags", []),
                "latest_version": latest.get("version"),
                "latest_timestamp": latest.get("timestamp"),
                "content_preview": (latest.get("content", ""))[:100],
            })

        return results

    def diff_versions(self, knowledge_id: str, v1: str, v2: str) -> Optional[Dict]:
        """Compare two versions of a knowledge entry.

        Args:
            knowledge_id: Unique identifier
            v1: First version
            v2: Second version

        Returns:
            Dict with both versions and a simple diff summary, or None if either not found
        """
        entry = self._load_entry(knowledge_id)
        if not entry:
            return None

        ver1 = ver2 = None
        for v in entry.get("versions", []):
            if v["version"] == v1:
                ver1 = v
            if v["version"] == v2:
                ver2 = v

        if ver1 is None or ver2 is None:
            return None

        content1 = ver1.get("content", "")
        content2 = ver2.get("content", "")
        lines1 = content1.splitlines()
        lines2 = content2.splitlines()

        added = [l for l in lines2 if l not in lines1]
        removed = [l for l in lines1 if l not in lines2]

        return {
            "knowledge_id": knowledge_id,
            "v1": ver1,
            "v2": ver2,
            "summary": {
                "lines_added": len(added),
                "lines_removed": len(removed),
                "content_changed": content1 != content2,
                "added_lines": added[:20],
                "removed_lines": removed[:20],
            },
        }
