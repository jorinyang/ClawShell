"""Hermes Agent framework detector."""

import os
import json
from local.detector.base import BaseDetector, FrameworkInfo


class HermesDetector(BaseDetector):
    FRAMEWORK_NAME = "hermes"
    SEARCH_PATHS = ["~/.hermes"]
    CONFIG_FILES = ["config.yaml", "config.yml"]
    PROCESS_MARKERS = ["hermes", "hermes-agent"]
    ENV_MARKERS = ["HERMES_HOME", "HERMES_CONFIG"]

    def detect(self) -> FrameworkInfo | None:
        paths = self.check_paths()
        if not paths:
            return None

        root = paths[0]
        configs = self.check_configs()
        config_path = configs[0] if configs else ""

        # Read version: try hermes CLI first, then VERSION file
        version = "unknown"
        try:
            import subprocess
            result = subprocess.run(
                ["hermes", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Parse "Hermes Agent v0.14.0 (2026.5.16)" → "0.14.0"
                import re
                m = re.search(r"v(\d+\.\d+\.\d+)", result.stdout)
                version = m.group(1) if m else result.stdout.strip()
        except Exception:
            pass

        # Fallback: read from VERSION file
        if version == "unknown":
            try:
                version_file = os.path.join(root, "VERSION")
                if os.path.exists(version_file):
                    with open(version_file) as f:
                        version = f.read().strip()
            except Exception:
                pass

        # Count skills
        skill_count = 0
        skills_dir = os.path.join(root, "skills")
        if os.path.isdir(skills_dir):
            skill_count = sum(
                1 for _ in os.walk(skills_dir)
                for f in _[2] if f.endswith(".md")
            )

        # Check if running
        running = self.check_processes()

        confidence = 0.7
        if config_path:
            confidence = 0.9
        if running:
            confidence = 1.0

        return FrameworkInfo(
            name="hermes",
            version=version,
            root_path=root,
            config_path=config_path,
            runtime_path=root,
            confidence=confidence,
            metadata={
                "skill_count": skill_count,
                "process_running": running,
            }
        )
