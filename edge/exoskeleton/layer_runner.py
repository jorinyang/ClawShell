"""LayerRunner — stateless exoskeleton layer execution.

Extracted from ExoskeletonDaemon._run_l1.._run_genome (v2.2.1).
All methods receive (report, registry, stats) — no self._* coupling.
"""

from __future__ import annotations
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class LayerRunner:
    """Stateless layer executor. Takes registry+stats as parameters.

    Usage:
        runner = LayerRunner()
        runner.run_l1_health(registry, stats, report)
        runner.run_l2_repair(registry, stats, report, health_report)
    """

    @staticmethod
    def run_l1_health(registry, stats, report: Dict) -> Dict[str, Any]:
        health_data = registry.call("health_checker", "check_all") or {}
        report["layers"]["L1_health"] = {
            "healthy": registry.call("health_checker", "is_healthy"),
            "cpu": health_data.get("cpu_percent"),
            "memory": health_data.get("memory_percent"),
            "disk": health_data.get("disk_percent"),
            "network": health_data.get("network_healthy"),
        }
        return health_data

    @staticmethod
    def run_l2_repair(registry, stats, report: Dict, health_data: Dict):
        layer: Dict[str, Any] = {}
        issues = registry.call("repair_engine", "detect_issues") or []
        layer["issues_detected"] = len(issues)

        if not issues:
            report["layers"]["L2_repair"] = layer
            return

        stats.increment("health_issues_found", len(issues))

        # Health score
        healthy_checks = [v for k, v in health_data.items() if k.endswith("_healthy")]
        health_score = sum(1 for h in healthy_checks if h) / max(len(healthy_checks), 1)
        resource_pressure = 1.0 - health_score

        # Strategy
        strategy = registry.get("strategy_switcher")
        if strategy:
            try:
                new_s = strategy.evaluate(health_score=health_score,
                                          resource_pressure=resource_pressure,
                                          auto_apply=True)
                layer["strategy"] = strategy.current
                if new_s:
                    layer["strategy_changed"] = new_s
            except Exception as e:
                logger.debug("StrategySwitcher: %s", e)

        # Feedback
        feedback = registry.get("feedback_loop")
        if feedback:
            try:
                feedback.set_target(1.0)
                signal = feedback.update(health_score)
                layer["feedback_signal"] = round(signal, 4)
                layer["feedback_stable"] = feedback.is_stable
            except Exception as e:
                logger.debug("FeedbackLoop: %s", e)

        # Repairs
        escalation = registry.get("repair_escalation")
        repairs = []
        for issue in issues:
            stats.increment("repairs_attempted")
            result = registry.call("repair_engine", "repair", issue)
            if result and result.get("success"):
                stats.increment("repairs_succeeded")
            repairs.append(result)

            if escalation:
                try:
                    escalation.record_action(
                        component=issue.get("type", "unknown"),
                        layer="self_healing",
                        action=str(result.get("action", "")),
                        success=bool(result and result.get("success")),
                    )
                except Exception:
                    pass

        layer["repairs"] = len(repairs)
        layer["repairs_ok"] = sum(1 for r in repairs if r and r.get("success"))

        # Feedback update
        if feedback and layer["repairs"] > 0:
            try:
                feedback.update(layer["repairs_ok"] / layer["repairs"])
            except Exception:
                pass

        report["layers"]["L2_repair"] = layer

    @staticmethod
    def run_l3_organization(registry, stats, report: Dict):
        layer: Dict[str, Any] = {}
        tasks = registry.call("task_organizer", "get_executable_tasks")
        if tasks is not None:
            layer["executable_tasks"] = len(tasks)
        topo = registry.call("task_organizer", "get_topology")
        if topo is not None:
            layer["topology_size"] = len(topo)
        snap = registry.call("context_manager", "snapshot")
        if snap:
            layer["context_version"] = snap.get("version", 0)
            layer["context_keys"] = len(snap.get("state", {}))
        bus = registry.call("event_bus", "get_stats")
        if bus:
            layer["events_total"] = bus.get("total_events", 0)
            layer["subscribers"] = bus.get("subscribers", 0)
        report["layers"]["L3_organization"] = layer

    @staticmethod
    def run_l4_swarm(registry, stats, report: Dict):
        layer: Dict[str, Any] = {}
        nodes = registry.call("swarm_manager", "discover_nodes") or []
        layer["known_nodes"] = len(nodes)

        trust_eval = registry.get("trust_evaluator")
        if trust_eval and nodes:
            layer["trust_scores"] = {}
            for node in nodes:
                nid = node.get("node_id", "unknown")
                try:
                    layer["trust_scores"][nid] = round(trust_eval.get_trust(nid), 3)
                except Exception:
                    pass

        shared_trust = registry.get("shared_trust")
        if shared_trust:
            try:
                results = []
                for node in nodes:
                    nid = node.get("node_id", "")
                    if nid:
                        ts = shared_trust.evaluate(nid)
                        results.append({"node_id": nid, "score": round(ts.score, 3)})
                layer["shared_trust"] = results
            except Exception as e:
                logger.debug("SharedTrust: %s", e)

        niche = registry.get("niche_matcher")
        if niche and nodes:
            try:
                layer["niche_match"] = niche.match(["general"])
            except Exception:
                pass

        report["layers"]["L4_swarm"] = layer

    @staticmethod
    def run_gateway(registry, stats, report: Dict):
        layer: Dict[str, Any] = {}
        nd = registry.get("network_discovery")
        if nd:
            try:
                if not nd._running:
                    nd.start()
                nd.register_device(capabilities=["exoskeleton", "edge"])
                layer["discovery_registered"] = True
                layer["discovery_devices"] = len(nd.get_devices())
            except Exception as e:
                logger.debug("NetworkDiscovery: %s", e)

        metrics = registry.call("device_monitor", "collect")
        if metrics:
            layer["device_cpu"] = round(getattr(metrics, "cpu_percent", 0), 1)
            layer["device_memory"] = round(getattr(metrics, "memory_percent", 0), 1)
            layer["device_disk"] = round(getattr(metrics, "disk_percent", 0), 1)

        health = registry.call("device_monitor", "get_health_status")
        if health:
            layer["device_health"] = getattr(health, "value", str(health))

        insights = registry.call("knowledge_puller", "get_insights", 10)
        broadcasts = registry.call("knowledge_puller", "get_broadcasts", 10)
        layer["cached_insights"] = len(insights or [])
        layer["cached_broadcasts"] = len(broadcasts or [])

        sh = registry.get("self_healing")
        if sh:
            try:
                issues = sh.diagnose()
                layer["diagnosis_issues"] = len(issues)
                healed = sum(1 for i in issues if sh.heal(i))
                layer["healed"] = healed
            except Exception as e:
                logger.debug("SelfHealing: %s", e)

        report["layers"]["Gateway"] = layer

    @staticmethod
    def run_genome(registry, stats, report: Dict, cycle_start: float):
        layer: Dict[str, Any] = {}
        et = registry.get("evolution_tracker")
        if et:
            try:
                et.record_cycle(timestamp=cycle_start)
                layer["evolution_generations"] = len(et.get_history())
            except Exception as e:
                logger.debug("EvolutionTracker: %s", e)

        kh = registry.get("knowledge_heritage")
        if kh:
            try:
                kh.preserve()
                layer["heritage_preserved"] = True
            except Exception as e:
                logger.debug("KnowledgeHeritage: %s", e)

        report["layers"]["Genome"] = layer
