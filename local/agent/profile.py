"""Agent profile persistence and management.

Stores discovered AgentProfiles locally and syncs them to Cloud Hub
via SyncDaemon.
"""

from __future__ import annotations
import json
import logging
import os
import threading
from typing import Dict, List, Optional

from shared.types import AgentProfile, InjectionProfile

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_DIR = os.path.expanduser("~/.clawshell/agents")


class AgentProfileStore:
    """Local persistence for discovered AgentProfiles."""

    def __init__(self, storage_dir: str = DEFAULT_PROFILE_DIR):
        self._dir = os.path.expanduser(storage_dir)
        self._lock = threading.RLock()
        os.makedirs(self._dir, exist_ok=True)

    # ── CRUD ──────────────────────────────────────────

    def save(self, profile: AgentProfile):
        with self._lock:
            path = self._profile_path(profile.agent_id)
            data = profile.to_dict()
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)

    def load(self, agent_id: str) -> Optional[AgentProfile]:
        with self._lock:
            path = self._profile_path(agent_id)
            if not os.path.exists(path):
                return None
            try:
                with open(path) as f:
                    data = json.load(f)
                return AgentProfile.from_dict(data)
            except Exception as e:
                logger.error("Failed to load profile %s: %s", agent_id, e)
                return None

    def load_all(self) -> List[AgentProfile]:
        with self._lock:
            profiles = []
            if not os.path.isdir(self._dir):
                return profiles
            for fname in os.listdir(self._dir):
                if fname.endswith(".json"):
                    agent_id = fname[:-5]
                    p = self.load(agent_id)
                    if p:
                        profiles.append(p)
            return profiles

    def delete(self, agent_id: str) -> bool:
        with self._lock:
            path = self._profile_path(agent_id)
            if os.path.exists(path):
                os.remove(path)
                return True
            return False

    def update_injection_status(self, agent_id: str,
                                status: InjectionProfile):
        with self._lock:
            profile = self.load(agent_id)
            if not profile:
                return
            profile.injection_status = status
            self.save(profile)

    def count(self) -> int:
        with self._lock:
            if not os.path.isdir(self._dir):
                return 0
            return sum(1 for f in os.listdir(self._dir) if f.endswith(".json"))

    # ── Helpers ───────────────────────────────────────

    def _profile_path(self, agent_id: str) -> str:
        safe_name = agent_id.replace(":", "_").replace("/", "_")
        return os.path.join(self._dir, f"{safe_name}.json")
