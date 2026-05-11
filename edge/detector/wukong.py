"""Wukong (悟空) framework detector."""

import os
import json
from edge.detector.base import BaseDetector, FrameworkInfo


class WukongDetector(BaseDetector):
    FRAMEWORK_NAME = "wukong"
    SEARCH_PATHS = [
        "~/.real",
        "~/.wukong",
        "/mnt/c/Users/*/.real",  # WSL path
        "%USERPROFILE%/.real",    # Windows path
    ]
    CONFIG_FILES = ["mcpServerConfig.json", "cron_tasks.json", ".node_registry.json"]
    PROCESS_MARKERS = ["dingtalk-rewind", "wukong"]
    ENV_MARKERS = ["WUKONG_HOME", "WUKONG_CONFIG"]

    def detect(self) -> FrameworkInfo | None:
        paths = self.check_paths()
        if not paths:
            return None

        root = paths[0]
        configs = self.check_configs()

        # Try to read version
        version = "unknown"
        try:
            package_json = os.path.join(root, "package.json")
            if os.path.exists(package_json):
                with open(package_json) as f:
                    pkg = json.load(f)
                    version = pkg.get("version", "unknown")
        except Exception:
            pass

        # Detect users
        users = []
        try:
            for item in os.listdir(root):
                if os.path.isdir(os.path.join(root, item)) and not item.startswith("."):
                    users.append(item)
        except Exception:
            pass

        confidence = 0.8
        if configs:
            confidence = 0.95
        if self.check_processes():
            confidence = 1.0

        return FrameworkInfo(
            name="wukong",
            version=version,
            root_path=root,
            config_path=configs[0] if configs else "",
            runtime_path=root,
            confidence=confidence,
            metadata={
                "config_files": [os.path.basename(c) for c in configs],
                "users": users,
                "process_running": self.check_processes(),
            }
        )
