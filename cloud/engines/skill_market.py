"""SkillMarket — Cross-edge skill publishing, discovery, and synchronization.

Features:
- Skill publishing with version management
- Tag-based and capability-based discovery
- Incrementing download counter
- Rating system
- Cross-edge sync (skills available to all registered edges)
- Thread-safe via threading.RLock()
- Persistent storage (data/skills.json)
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, List, Optional, Any


class SkillMarket:
    """Cross-edge skill marketplace."""

    def __init__(self, data_dir: str = "data"):
        self._data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._skills_file = os.path.join(data_dir, "skills.json")

        self._lock = threading.RLock()
        self._skills: Dict[str, dict] = {}  # skill_id → skill
        self._by_tag: Dict[str, set] = {}    # tag → {skill_ids}
        self._by_category: Dict[str, set] = {}  # category → {skill_ids}

        self._load()
        self._rebuild_indexes()

    # ── CRUD ──────────────────────────────────────

    def publish(self, skill: dict) -> str:
        """Publish a new skill or update existing. Returns skill_id."""
        skill_id = skill.get("skill_id", "")
        if not skill_id:
            import uuid
            skill_id = str(uuid.uuid4())
            skill["skill_id"] = skill_id

        with self._lock:
            existing = self._skills.get(skill_id)
            if existing:
                # Update existing — bump version if content changed
                if skill.get("content") != existing.get("content"):
                    existing_version = existing.get("version", "1.0.0")
                    parts = existing_version.split(".")
                    parts[-1] = str(int(parts[-1]) + 1)
                    skill["version"] = ".".join(parts)
                existing.update(skill)
                existing["updated_at"] = time.time()
            else:
                skill.setdefault("version", "1.0.0")
                skill.setdefault("published_at", time.time())
                skill.setdefault("updated_at", time.time())
                skill.setdefault("download_count", 0)
                skill.setdefault("rating", 0.0)
                skill.setdefault("ratings_count", 0)
                skill.setdefault("tags", [])
                skill.setdefault("category", "general")
                skill.setdefault("capabilities", [])
                self._skills[skill_id] = skill

            self._save()
            self._rebuild_indexes()
            return skill_id

    def get_skill(self, skill_id: str) -> Optional[dict]:
        """Get a skill by ID."""
        with self._lock:
            s = self._skills.get(skill_id)
            return dict(s) if s else None

    def list_skills(self, category: Optional[str] = None,
                    tags: Optional[List[str]] = None,
                    capability: Optional[str] = None,
                    search: Optional[str] = None,
                    sort_by: str = "published_at",
                    limit: int = 100, offset: int = 0) -> List[dict]:
        """List skills with optional filters."""
        with self._lock:
            results = list(self._skills.values())

            if category:
                results = [s for s in results if s.get("category") == category]

            if tags:
                tag_set = set(tags)
                results = [s for s in results if tag_set.intersection(set(s.get("tags", [])))]

            if capability:
                results = [s for s in results
                          if capability in s.get("capabilities", [])]

            if search:
                search_lower = search.lower()
                results = [
                    s for s in results
                    if search_lower in s.get("name", "").lower()
                    or search_lower in s.get("description", "").lower()
                ]

            # Sort
            reverse = sort_by in ("published_at", "updated_at", "download_count")
            results.sort(key=lambda s: s.get(sort_by, 0), reverse=reverse)

            return [dict(s) for s in results[offset:offset + limit]]

    def search_by_tag(self, tag: str, limit: int = 50) -> List[dict]:
        """Search skills by tag."""
        with self._lock:
            skill_ids = self._by_tag.get(tag, set())
            return [dict(self._skills[sid]) for sid in list(skill_ids)[:limit]
                    if sid in self._skills]

    def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill."""
        with self._lock:
            if skill_id in self._skills:
                del self._skills[skill_id]
                self._save()
                self._rebuild_indexes()
                return True
            return False

    # ── Interactions ──────────────────────────────

    def get_version_history(self, skill_name: str) -> List[dict]:
        """Get version history for a skill (v1.8.1: from MacOS SkillDomain).

        Returns list of {version, published_at, skill_id, download_count} dicts
        sorted by version publish time.
        """
        with self._lock:
            versions = []
            for sid, skill in self._skills.items():
                if skill.get("name") == skill_name:
                    versions.append({
                        "version": skill.get("version", "1.0.0"),
                        "published_at": skill.get("published_at", 0),
                        "skill_id": sid,
                        "download_count": skill.get("download_count", 0),
                    })
            return sorted(versions, key=lambda v: v["published_at"])

    def download(self, skill_id: str) -> Optional[dict]:
        """Record a download and return skill content."""
        with self._lock:
            skill = self._skills.get(skill_id)
            if not skill:
                return None
            skill["download_count"] = skill.get("download_count", 0) + 1
            self._save()
            return dict(skill)

    def rate(self, skill_id: str, rating: float) -> Optional[dict]:
        """Rate a skill (1.0-5.0)."""
        if not 1.0 <= rating <= 5.0:
            raise ValueError("Rating must be between 1.0 and 5.0")

        with self._lock:
            skill = self._skills.get(skill_id)
            if not skill:
                return None

            current_rating = skill.get("rating", 0.0)
            current_count = skill.get("ratings_count", 0)
            new_count = current_count + 1
            new_rating = (current_rating * current_count + rating) / new_count

            skill["rating"] = round(new_rating, 2)
            skill["ratings_count"] = new_count
            self._save()
            return dict(skill)

    # ── Sync ──────────────────────────────────────

    def get_updates_since(self, timestamp: float, limit: int = 50) -> List[dict]:
        """Get skills updated since a given timestamp (for cross-edge sync)."""
        with self._lock:
            updated = [
                s for s in self._skills.values()
                if s.get("updated_at", 0) > timestamp
            ]
            updated.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
            return [dict(s) for s in updated[:limit]]

    # ── Stats ─────────────────────────────────────

    def get_stats(self) -> dict:
        """Get skill market statistics."""
        with self._lock:
            return {
                "total_skills": len(self._skills),
                "total_downloads": sum(s.get("download_count", 0) for s in self._skills.values()),
                "categories": len(self._by_category),
                "tags": len(self._by_tag),
                "top_downloaded": self._top_by("download_count", 5),
                "top_rated": self._top_by("rating", 5),
            }

    def _top_by(self, field: str, n: int = 5) -> List[dict]:
        skills = sorted(
            self._skills.values(),
            key=lambda s: s.get(field, 0),
            reverse=True
        )
        return [
            {"skill_id": s["skill_id"], "name": s.get("name"), field: s.get(field)}
            for s in skills[:n]
        ]

    # ── Persistence ───────────────────────────────

    def _save(self):
        try:
            with open(self._skills_file, "w", encoding="utf-8") as f:
                json.dump(list(self._skills.values()), f, ensure_ascii=False, default=str)
        except OSError:
            pass

    def _load(self):
        if not os.path.exists(self._skills_file):
            return
        try:
            with open(self._skills_file, "r", encoding="utf-8") as f:
                skills = json.load(f)
            for s in skills:
                sid = s.get("skill_id")
                if sid:
                    self._skills[sid] = s
        except (json.JSONDecodeError, OSError):
            pass

    def _rebuild_indexes(self):
        """Rebuild tag and category indexes."""
        self._by_tag.clear()
        self._by_category.clear()
        for sid, skill in self._skills.items():
            for tag in skill.get("tags", []):
                self._by_tag.setdefault(tag, set()).add(sid)
            cat = skill.get("category", "general")
            self._by_category.setdefault(cat, set()).add(sid)
