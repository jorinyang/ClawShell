"""Exoskeleton Daemon — activates ALL exoskeleton layers and gateway modules.

v2.2.1: Refactored — ModuleRegistry, CycleStats, LayerRunner extracted.
Daemon is now a thin orchestrator (~170 lines, was 553).
"""

from __future__ import annotations
import logging
import threading
import time
from typing import Any, Dict, Optional

from edge.exoskeleton.registry import ModuleRegistry
from edge.exoskeleton.stats import CycleStats
from edge.exoskeleton.layer_runner import LayerRunner

logger = logging.getLogger(__name__)


class ExoskeletonDaemon:
    """Daemon thread that runs all exoskeleton layers on a configurable interval."""

    def __init__(self, interval: float = 30.0):
        self._interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._stats_obj = CycleStats()
        self._registry = ModuleRegistry()
        self._runner = LayerRunner()
        self._register_modules()

    # ── Backward compat (tests) ──
    @property
    def _stats(self) -> Dict[str, Any]:
        return self._stats_obj._data

    @property
    def _modules(self) -> Dict[str, Any]:
        for name in list(self._registry._init_factories.keys()):
            self._registry.get(name)
        return dict(self._registry._instances)

    @_modules.setter
    def _modules(self, value: dict):
        for name, instance in value.items():
            self._registry._instances[name] = instance

    # ── Module Registration ──────────────────────────────────
    def _register_modules(self):
        mods = {
            "health_checker":       lambda: __import__("exoskeleton.layer1.health_check",fromlist=["HealthChecker"]).HealthChecker(),
            "repair_engine":        lambda: __import__("exoskeleton.layer2",fromlist=["SelfRepairEngine"]).SelfRepairEngine(),
            "strategy_switcher":    lambda: __import__("exoskeleton.layer2.strategy",fromlist=["StrategySwitcher"]).StrategySwitcher(),
            "feedback_loop":        lambda: __import__("exoskeleton.layer2.feedback_loop",fromlist=["FeedbackControlLoop"]).FeedbackControlLoop(name="health",kp=0.5,ki=0.1),
            "repair_escalation":    lambda: __import__("exoskeleton.layer2.repair_escalation",fromlist=["RepairEscalation"]).RepairEscalation(),
            "task_organizer":       lambda: __import__("exoskeleton.layer3",fromlist=["TaskOrganizer"]).TaskOrganizer(),
            "context_manager":      lambda: __import__("exoskeleton.layer3",fromlist=["ContextManager"]).ContextManager(),
            "event_bus":            lambda: __import__("exoskeleton.layer3",fromlist=["LocalEventBus"]).LocalEventBus(),
            "swarm_manager":        lambda: __import__("exoskeleton.layer4",fromlist=["SwarmManager"]).SwarmManager(),
            "trust_evaluator":      lambda: __import__("exoskeleton.layer4",fromlist=["TrustEvaluator"]).TrustEvaluator(),
            "shared_trust":         lambda: __import__("shared.trust",fromlist=["TrustEvaluator"]).TrustEvaluator(),
            "niche_matcher":        lambda: __import__("exoskeleton.layer4",fromlist=["EcologicalNicheMatcher"]).EcologicalNicheMatcher(),
            "network_discovery":    lambda: __import__("edge.gateway.network_discovery",fromlist=["NetworkDiscovery"]).NetworkDiscovery(),
            "device_monitor":       lambda: __import__("edge.gateway.device_monitor",fromlist=["DeviceMonitor"]).DeviceMonitor(),
            "knowledge_puller":     lambda: __import__("edge.gateway.knowledge_puller",fromlist=["KnowledgePuller"]).KnowledgePuller(),
            "self_healing":         lambda: __import__("edge.gateway.self_healing",fromlist=["EdgeSelfHealing"]).EdgeSelfHealing(),
            "evolution_tracker":    lambda: __import__("exoskeleton.genome.evolution_tracker",fromlist=["EvolutionTracker"]).EvolutionTracker(),
            "knowledge_heritage":   lambda: __import__("exoskeleton.genome.heritage",fromlist=["KnowledgeHeritage"]).KnowledgeHeritage(),
        }
        for name, factory in mods.items():
            self._registry.register(name, factory)

    # ── Lifecycle ───────────────────────────────────────────
    def start(self):
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="exoskeleton-daemon")
        self._thread.start()
        logger.info("ExoskeletonDaemon started (%.1fs)", self._interval)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None
        logger.info("ExoskeletonDaemon stopped")

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running, "interval": self._interval,
                "thread_alive": self._thread.is_alive() if self._thread else False,
                "stats": self._stats_obj.snapshot(),
                "modules_loaded": self._registry.list_loaded(),
            }

    # ── Main Loop ──────────────────────────────────────────
    def _loop(self):
        while self._running:
            try: self._run_cycle()
            except Exception as e:
                self._stats_obj.increment("errors")
                logger.error("Cycle error: %s", e, exc_info=True)
            for _ in range(int(self._interval)):
                if not self._running: break
                time.sleep(1)

    def _run_cycle(self):
        t0 = time.time()
        report: Dict[str, Any] = {"cycle": self._stats_obj.get("cycles") + 1, "layers": {}}
        health = self._runner.run_l1_health(self._registry, self._stats_obj, report)
        self._runner.run_l2_repair(self._registry, self._stats_obj, report, health)
        self._runner.run_l3_organization(self._registry, self._stats_obj, report)
        self._runner.run_l4_swarm(self._registry, self._stats_obj, report)
        self._runner.run_gateway(self._registry, self._stats_obj, report)
        self._runner.run_genome(self._registry, self._stats_obj, report, t0)
        dur = round(time.time() - t0, 3)
        self._stats_obj.finalize_cycle(dur)
        report["duration_s"] = dur
        logger.info("Cycle %d done in %.3fs", report["cycle"], dur)
