"""Exoskeleton Daemon — activates ALL exoskeleton layers and gateway modules.

Runs a periodic cycle that exercises:
  L1: HealthChecker (27-item self-sensing)
  L2: SelfRepairEngine + StrategySwitcher + FeedbackControlLoop + RepairEscalation
  L3: TaskOrganizer + ContextManager + LocalEventBus
  L4: SwarmManager + TrustEvaluator + EcologicalNicheMatcher
  Gateway: NetworkDiscovery + DeviceMonitor + KnowledgePuller + EdgeSelfHealing
  Genome: EvolutionTracker + KnowledgeHeritage

Each module is wrapped in try/except so one failure never breaks the cycle.

Placement: edge/exoskeleton_daemon.py
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExoskeletonDaemon:
    """Daemon thread that runs all exoskeleton layers on a configurable interval.

    Usage:
        daemon = ExoskeletonDaemon(interval=30)
        daemon.start()
        # ... later ...
        daemon.stop()
        print(daemon.status())
    """

    def __init__(self, interval: float = 30.0):
        self._interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Stats
        self._stats: Dict[str, Any] = {
            "cycles": 0,
            "errors": 0,
            "last_cycle_duration": 0.0,
            "last_cycle_time": 0.0,
            "module_failures": {},
            "health_issues_found": 0,
            "repairs_attempted": 0,
            "repairs_succeeded": 0,
        }

        # Lazily-initialized module instances (created once on first cycle)
        self._modules: Dict[str, Any] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────

    def start(self):
        """Start the exoskeleton daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="exoskeleton-daemon"
        )
        self._thread.start()
        logger.info("ExoskeletonDaemon started (interval=%.1fs)", self._interval)

    def stop(self):
        """Stop the daemon gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None
        logger.info("ExoskeletonDaemon stopped")

    def status(self) -> Dict[str, Any]:
        """Return daemon status and stats."""
        with self._lock:
            return {
                "running": self._running,
                "interval": self._interval,
                "thread_alive": self._thread.is_alive() if self._thread else False,
                "stats": dict(self._stats),
                "modules_initialized": list(self._modules.keys()),
            }

    # ── Main Loop ─────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            try:
                self._run_cycle()
            except Exception as e:
                self._stats["errors"] += 1
                logger.error("ExoskeletonDaemon cycle error: %s", e, exc_info=True)

            # Sleep in 1-second chunks for fast shutdown
            for _ in range(int(self._interval)):
                if not self._running:
                    break
                time.sleep(1)

    def _run_cycle(self):
        """Execute one full exoskeleton cycle."""
        cycle_start = time.time()
        cycle_report: Dict[str, Any] = {
            "cycle": self._stats["cycles"] + 1,
            "layers": {},
        }

        # Initialize modules lazily
        if not self._modules:
            self._init_modules()

        # ── L1: Health Check ──────────────────────────────────
        health_report = self._run_l1_health(cycle_report)

        # ── L2: Self-Repair + Strategy ────────────────────────
        self._run_l2_repair(cycle_report, health_report)

        # ── L3: Self-Organization ─────────────────────────────
        self._run_l3_organization(cycle_report)

        # ── L4: Multi-Agent Swarm ─────────────────────────────
        self._run_l4_swarm(cycle_report)

        # ── Gateway ───────────────────────────────────────────
        self._run_gateway(cycle_report)

        # ── Genome ────────────────────────────────────────────
        self._run_genome(cycle_report, cycle_start)

        # Finalize
        duration = time.time() - cycle_start
        with self._lock:
            self._stats["cycles"] += 1
            self._stats["last_cycle_duration"] = round(duration, 3)
            self._stats["last_cycle_time"] = cycle_start

        cycle_report["duration_s"] = round(duration, 3)
        logger.info(
            "Exoskeleton cycle %d complete in %.3fs",
            cycle_report["cycle"],
            duration,
        )

    # ── Module Initialization ─────────────────────────────────────────

    def _init_modules(self):
        """Lazily initialize all exoskeleton and gateway modules."""
        initializers = {
            "health_checker": self._init_health_checker,
            "repair_engine": self._init_repair_engine,
            "strategy_switcher": self._init_strategy_switcher,
            "feedback_loop": self._init_feedback_loop,
            "repair_escalation": self._init_repair_escalation,
            "task_organizer": self._init_task_organizer,
            "context_manager": self._init_context_manager,
            "event_bus": self._init_event_bus,
            "swarm_manager": self._init_swarm_manager,
            "trust_evaluator": self._init_trust_evaluator,
            "shared_trust": self._init_shared_trust,
            "niche_matcher": self._init_niche_matcher,
            "network_discovery": self._init_network_discovery,
            "device_monitor": self._init_device_monitor,
            "knowledge_puller": self._init_knowledge_puller,
            "self_healing": self._init_self_healing,
            "evolution_tracker": self._init_evolution_tracker,
            "knowledge_heritage": self._init_knowledge_heritage,
        }
        for name, init_fn in initializers.items():
            try:
                self._modules[name] = init_fn()
                logger.debug("Initialized %s", name)
            except Exception as e:
                logger.warning("Failed to init %s: %s", name, e)
                self._modules[name] = None

    def _init_health_checker(self):
        from exoskeleton.layer1.health_check import HealthChecker
        return HealthChecker()

    def _init_repair_engine(self):
        from exoskeleton.layer2 import SelfRepairEngine
        return SelfRepairEngine()

    def _init_strategy_switcher(self):
        from exoskeleton.layer2.strategy import StrategySwitcher
        return StrategySwitcher()

    def _init_feedback_loop(self):
        from exoskeleton.layer2.feedback_loop import FeedbackControlLoop
        return FeedbackControlLoop(name="system_health", kp=0.5, ki=0.1)

    def _init_repair_escalation(self):
        from exoskeleton.layer2.repair_escalation import RepairEscalation
        return RepairEscalation()

    def _init_task_organizer(self):
        from exoskeleton.layer3 import TaskOrganizer
        return TaskOrganizer()

    def _init_context_manager(self):
        from exoskeleton.layer3 import ContextManager
        return ContextManager()

    def _init_event_bus(self):
        from exoskeleton.layer3 import LocalEventBus
        return LocalEventBus()

    def _init_swarm_manager(self):
        from exoskeleton.layer4 import SwarmManager
        return SwarmManager()

    def _init_trust_evaluator(self):
        from exoskeleton.layer4 import TrustEvaluator
        return TrustEvaluator()

    def _init_shared_trust(self):
        from shared.trust import TrustEvaluator as SharedTrustEvaluator
        return SharedTrustEvaluator()

    def _init_niche_matcher(self):
        from exoskeleton.layer4 import EcologicalNicheMatcher
        return EcologicalNicheMatcher()

    def _init_network_discovery(self):
        from edge.gateway.network_discovery import NetworkDiscovery
        return NetworkDiscovery()

    def _init_device_monitor(self):
        from edge.gateway.device_monitor import DeviceMonitor
        return DeviceMonitor()

    def _init_knowledge_puller(self):
        from edge.gateway.knowledge_puller import KnowledgePuller
        return KnowledgePuller()

    def _init_self_healing(self):
        from edge.gateway.self_healing import EdgeSelfHealing
        return EdgeSelfHealing()

    def _init_evolution_tracker(self):
        from exoskeleton.genome.evolution_tracker import EvolutionTracker
        return EvolutionTracker()

    def _init_knowledge_heritage(self):
        from exoskeleton.genome.heritage import KnowledgeHeritage
        return KnowledgeHeritage()

    # ── Layer Execution ────────────────────────────────────────────────

    def _safe_call(self, module_name: str, method_name: str, *args, **kwargs) -> Any:
        """Call a module method safely. Returns result or None on failure."""
        mod = self._modules.get(module_name)
        if mod is None:
            return None
        try:
            method = getattr(mod, method_name, None)
            if method is None:
                logger.debug("Module %s has no method %s", module_name, method_name)
                return None
            return method(*args, **kwargs)
        except Exception as e:
            logger.warning("Module %s.%s failed: %s", module_name, method_name, e)
            with self._lock:
                self._stats["module_failures"][module_name] = str(e)
            return None

    def _run_l1_health(self, report: Dict) -> Dict[str, Any]:
        """L1: Run health checks."""
        health_report = self._safe_call("health_checker", "check_all") or {}
        report["layers"]["L1_health"] = {
            "healthy": self._safe_call("health_checker", "is_healthy"),
            "cpu": health_report.get("cpu_percent"),
            "memory": health_report.get("memory_percent"),
            "disk": health_report.get("disk_percent"),
            "network": health_report.get("network_healthy"),
        }
        return health_report

    def _run_l2_repair(self, report: Dict, health_report: Dict):
        """L2: Self-repair, strategy switching, feedback loop."""
        layer_result: Dict[str, Any] = {}

        # Detect issues
        issues = self._safe_call("repair_engine", "detect_issues") or []
        layer_result["issues_detected"] = len(issues)

        if issues:
            with self._lock:
                self._stats["health_issues_found"] += len(issues)

            # Use StrategySwitcher to evaluate strategy
            # Compute health_score from health_report
            healthy_checks = [
                v for k, v in health_report.items() if k.endswith("_healthy")
            ]
            health_score = (
                sum(1 for h in healthy_checks if h) / len(healthy_checks)
                if healthy_checks
                else 1.0
            )
            resource_pressure = 1.0 - health_score

            strategy_switcher = self._modules.get("strategy_switcher")
            if strategy_switcher:
                try:
                    new_strategy = strategy_switcher.evaluate(
                        health_score=health_score,
                        resource_pressure=resource_pressure,
                        auto_apply=True,
                    )
                    layer_result["strategy"] = strategy_switcher.current
                    if new_strategy:
                        layer_result["strategy_changed"] = new_strategy
                except Exception as e:
                    logger.debug("StrategySwitcher error: %s", e)

            # Use FeedbackControlLoop
            feedback = self._modules.get("feedback_loop")
            if feedback:
                try:
                    feedback.set_target(1.0)
                    signal = feedback.update(health_score)
                    layer_result["feedback_signal"] = round(signal, 4)
                    layer_result["feedback_stable"] = feedback.is_stable
                except Exception as e:
                    logger.debug("FeedbackLoop error: %s", e)

            # Attempt repairs
            escalation = self._modules.get("repair_escalation")
            repair_results = []
            for issue in issues:
                with self._lock:
                    self._stats["repairs_attempted"] += 1
                result = self._safe_call("repair_engine", "repair", issue)
                if result and result.get("success"):
                    with self._lock:
                        self._stats["repairs_succeeded"] += 1
                repair_results.append(result)

                # Record with escalation
                if escalation:
                    try:
                        issue_type = issue.get("type", "unknown")
                        escalation.record_action(
                            component=issue_type,
                            layer="self_healing",
                            action=str(result.get("action", "")),
                            success=bool(result and result.get("success")),
                        )
                    except Exception:
                        pass

            layer_result["repairs"] = len(repair_results)
            layer_result["repairs_ok"] = sum(
                1 for r in repair_results if r and r.get("success")
            )

            # Feed repair success back to FeedbackLoop
            if feedback:
                try:
                    success_rate = (
                        layer_result["repairs_ok"] / max(layer_result["repairs"], 1)
                    )
                    feedback.update(success_rate)
                except Exception:
                    pass

        report["layers"]["L2_repair"] = layer_result

    def _run_l3_organization(self, report: Dict):
        """L3: Task organizer, context manager, event bus."""
        layer_result: Dict[str, Any] = {}

        # TaskOrganizer: get executable tasks
        exec_tasks = self._safe_call("task_organizer", "get_executable_tasks")
        if exec_tasks is not None:
            layer_result["executable_tasks"] = len(exec_tasks)

        topo = self._safe_call("task_organizer", "get_topology")
        if topo is not None:
            layer_result["topology_size"] = len(topo)

        # ContextManager: snapshot
        snapshot = self._safe_call("context_manager", "snapshot")
        if snapshot:
            layer_result["context_version"] = snapshot.get("version", 0)
            layer_result["context_keys"] = len(snapshot.get("state", {}))

        # EventBus: stats
        bus_stats = self._safe_call("event_bus", "get_stats")
        if bus_stats:
            layer_result["events_total"] = bus_stats.get("total_events", 0)
            layer_result["subscribers"] = bus_stats.get("subscribers", 0)

        report["layers"]["L3_organization"] = layer_result

    def _run_l4_swarm(self, report: Dict):
        """L4: Swarm discovery, trust evaluation, niche matching."""
        layer_result: Dict[str, Any] = {}

        # SwarmManager: discover nodes
        nodes = self._safe_call("swarm_manager", "discover_nodes") or []
        layer_result["known_nodes"] = len(nodes)

        # TrustEvaluator (L4 built-in): evaluate known nodes
        trust_eval = self._modules.get("trust_evaluator")
        if trust_eval and nodes:
            trust_scores = {}
            for node in nodes:
                nid = node.get("node_id", "unknown")
                try:
                    score = trust_eval.get_trust(nid)
                    trust_scores[nid] = round(score, 3)
                except Exception:
                    pass
            layer_result["trust_scores"] = trust_scores

        # Shared trust evaluator: check any registered nodes
        shared_trust = self._modules.get("shared_trust")
        if shared_trust:
            try:
                # Just run evaluate on any known node IDs
                shared_nodes = []
                for node in nodes:
                    nid = node.get("node_id", "")
                    if nid:
                        ts = shared_trust.evaluate(nid)
                        shared_nodes.append(
                            {"node_id": nid, "score": round(ts.score, 3)}
                        )
                layer_result["shared_trust"] = shared_nodes
            except Exception as e:
                logger.debug("SharedTrust error: %s", e)

        # EcologicalNicheMatcher: match capabilities
        niche = self._modules.get("niche_matcher")
        if niche and nodes:
            try:
                # Try to match "general" capability
                match = niche.match(["general"])
                layer_result["niche_match"] = match
            except Exception:
                pass

        report["layers"]["L4_swarm"] = layer_result

    def _run_gateway(self, report: Dict):
        """Gateway: network discovery, device monitor, knowledge puller, self-healing."""
        layer_result: Dict[str, Any] = {}

        # NetworkDiscovery: register local device (broadcast presence)
        nd = self._modules.get("network_discovery")
        if nd:
            try:
                if not nd._running:
                    nd.start()
                dev = nd.register_device(capabilities=["exoskeleton", "edge"])
                layer_result["discovery_registered"] = True
                layer_result["discovery_devices"] = len(nd.get_devices())
            except Exception as e:
                logger.debug("NetworkDiscovery error: %s", e)

        # DeviceMonitor: collect metrics
        metrics = self._safe_call("device_monitor", "collect")
        if metrics:
            layer_result["device_cpu"] = round(metrics.cpu_percent, 1)
            layer_result["device_memory"] = round(metrics.memory_percent, 1)
            layer_result["device_disk"] = round(metrics.disk_percent, 1)

        health_status = self._safe_call("device_monitor", "get_health_status")
        if health_status:
            layer_result["device_health"] = health_status.value

        # KnowledgePuller: pull latest (get cached insights & broadcasts)
        insights = self._safe_call("knowledge_puller", "get_insights", 10)
        broadcasts = self._safe_call("knowledge_puller", "get_broadcasts", 10)
        layer_result["cached_insights"] = len(insights or [])
        layer_result["cached_broadcasts"] = len(broadcasts or [])

        # EdgeSelfHealing: diagnose and heal
        sh = self._modules.get("self_healing")
        if sh:
            try:
                issues_found = sh.diagnose()
                layer_result["diagnosis_issues"] = len(issues_found)
                healed = 0
                for issue in issues_found:
                    action = sh.heal(issue)
                    if action:
                        healed += 1
                layer_result["healed"] = healed
            except Exception as e:
                logger.debug("SelfHealing error: %s", e)

        report["layers"]["Gateway"] = layer_result

    def _run_genome(self, report: Dict, cycle_start: float):
        """Genome: evolution tracking and knowledge heritage."""
        layer_result: Dict[str, Any] = {}

        # EvolutionTracker: record cycle outcome
        cycle_num = self._stats["cycles"] + 1
        duration = time.time() - cycle_start

        # Collect key metrics from this cycle
        health_report = report.get("layers", {}).get("L1_health", {})
        gateway_report = report.get("layers", {}).get("Gateway", {})

        metrics = {
            "cycle_duration_s": round(duration, 3),
            "cpu": health_report.get("cpu") or 0,
            "memory": health_report.get("memory") or 0,
            "health_issues": report.get("layers", {})
            .get("L2_repair", {})
            .get("issues_detected", 0),
            "repairs_ok": report.get("layers", {})
            .get("L2_repair", {})
            .get("repairs_ok", 0),
        }

        milestone = self._safe_call(
            "evolution_tracker",
            "track_milestone",
            title=f"exoskeleton_cycle_{cycle_num}",
            description=f"Automated exoskeleton cycle #{cycle_num}",
            metrics=metrics,
        )
        if milestone:
            layer_result["milestone_recorded"] = True

        # KnowledgeHeritage: inherit cycle knowledge
        knowledge_content = (
            f"Cycle {cycle_num}: duration={duration:.3f}s, "
            f"issues={metrics['health_issues']}, repairs={metrics['repairs_ok']}, "
            f"cpu={metrics['cpu']:.1f}%, mem={metrics['memory']:.1f}%"
        )
        stored = self._safe_call(
            "knowledge_heritage",
            "store_knowledge",
            knowledge_id=f"exoskeleton/cycle/{cycle_num}",
            content=knowledge_content,
            tags=["exoskeleton", "auto", f"cycle_{cycle_num}"],
        )
        if stored:
            layer_result["knowledge_stored"] = True

        report["layers"]["Genome"] = layer_result
