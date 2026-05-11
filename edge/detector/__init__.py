"""Edge detector package — auto-discover OpenClaw-class frameworks."""

from edge.detector.base import BaseDetector, FrameworkInfo
from edge.detector.system import detect_system_info
from edge.detector.wukong import WukongDetector
from edge.detector.hermes import HermesDetector
from edge.detector.openclaw import (
    OpenClawDetector, QClawDetector, CoPawDetector,
    HiClawDetector, EasyClawDetector, WorkBuddyDetector
)

# All registered detectors
ALL_DETECTORS = [
    WukongDetector(),
    HermesDetector(),
    OpenClawDetector(),
    QClawDetector(),
    CoPawDetector(),
    HiClawDetector(),
    EasyClawDetector(),
    WorkBuddyDetector(),
]


def detect_all_frameworks() -> list[FrameworkInfo]:
    """Run all detectors and return discovered frameworks."""
    results = []
    for detector in ALL_DETECTORS:
        try:
            info = detector.detect()
            if info and info.confidence >= 0.5:
                results.append(info)
        except Exception:
            pass
    return results


def detect_environment() -> dict:
    """Full environment scan: system + frameworks."""
    sys_info = detect_system_info()
    frameworks = detect_all_frameworks()
    return {
        "system": sys_info,
        "frameworks": [f.to_dict() for f in frameworks],
        "total_frameworks": len(frameworks),
    }
