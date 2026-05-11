"""OpenClaw framework detector."""

import os
from edge.detector.base import BaseDetector, FrameworkInfo


class OpenClawDetector(BaseDetector):
    FRAMEWORK_NAME = "openclaw"
    SEARCH_PATHS = ["~/.openclaw"]
    CONFIG_FILES = ["package.json", "config.yaml", "openclaw.json"]
    PROCESS_MARKERS = ["openclaw", "openclaw-gateway"]
    ENV_MARKERS = ["OPENCLAW_HOME"]

    def detect(self) -> FrameworkInfo | None:
        paths = self.check_paths()
        if not paths:
            return None

        root = paths[0]
        configs = self.check_configs()

        version = "unknown"
        try:
            import json
            package = os.path.join(root, "package.json")
            if os.path.exists(package):
                with open(package) as f:
                    version = json.load(f).get("version", "unknown")
        except Exception:
            pass

        return FrameworkInfo(
            name="openclaw",
            version=version,
            root_path=root,
            config_path=configs[0] if configs else "",
            runtime_path=root,
            confidence=0.85 if configs else 0.6,
            metadata={"process_running": self.check_processes()}
        )


class QClawDetector(BaseDetector):
    FRAMEWORK_NAME = "qclaw"
    SEARCH_PATHS = ["~/.qclaw", "~/.qoder"]
    CONFIG_FILES = ["config.json", "qclaw.yaml"]

    def detect(self) -> FrameworkInfo | None:
        paths = self.check_paths()
        if not paths:
            return None
        return FrameworkInfo(
            name="qclaw", root_path=paths[0], confidence=0.7
        )


class CoPawDetector(BaseDetector):
    FRAMEWORK_NAME = "copaw"
    SEARCH_PATHS = ["~/.copaw"]
    CONFIG_FILES = ["config.json"]

    def detect(self) -> FrameworkInfo | None:
        paths = self.check_paths()
        if not paths:
            return None
        return FrameworkInfo(
            name="copaw", root_path=paths[0], confidence=0.7
        )


class HiClawDetector(BaseDetector):
    FRAMEWORK_NAME = "hiclaw"
    SEARCH_PATHS = ["~/.hiclaw"]
    CONFIG_FILES = ["config.yaml", "hiclaw.json"]

    def detect(self) -> FrameworkInfo | None:
        paths = self.check_paths()
        if not paths:
            return None
        return FrameworkInfo(
            name="hiclaw", root_path=paths[0], confidence=0.7
        )


class EasyClawDetector(BaseDetector):
    FRAMEWORK_NAME = "easyclaw"
    SEARCH_PATHS = ["~/.easyclaw"]
    CONFIG_FILES = ["config.json"]

    def detect(self) -> FrameworkInfo | None:
        paths = self.check_paths()
        if not paths:
            return None
        return FrameworkInfo(
            name="easyclaw", root_path=paths[0], confidence=0.7
        )


class WorkBuddyDetector(BaseDetector):
    FRAMEWORK_NAME = "workbuddy"
    SEARCH_PATHS = ["~/.workbuddy", "~/.work-buddy"]
    CONFIG_FILES = ["config.json"]

    def detect(self) -> FrameworkInfo | None:
        paths = self.check_paths()
        if not paths:
            return None
        return FrameworkInfo(
            name="workbuddy", root_path=paths[0], confidence=0.7
        )
