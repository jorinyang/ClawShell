"""Global Resource Optimizer — optimize resource allocation across Edge nodes.

Balances CPU, memory, disk, and network resources across registered
Edge nodes using cost-model-based optimization.

Design: stdlib-only, RLock thread-safe.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OptimizationGoal(str, Enum):
    COST = "cost"             # Minimize operational cost
    LATENCY = "latency"       # Minimize latency
    THROUGHPUT = "throughput" # Maximize throughput
    BALANCED = "balanced"     # Balance all factors


class ResourceType(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


@dataclass
class ResourceQuota:
    """Resource allocation for a single node."""
    cpu_cores: float = 1.0
    memory_mb: float = 512.0
    disk_gb: float = 10.0
    network_mbps: float = 10.0
    max_tasks: int = 5
    current_tasks: int = 0

    @property
    def cpu_utilization(self) -> float:
        return self.current_tasks / max(self.max_tasks, 1)

    @property
    def available_capacity(self) -> float:
        """Available capacity as fraction (0.0 = full, 1.0 = empty)."""
        return 1.0 - self.cpu_utilization


@dataclass
class AllocationPlan:
    """Resource allocation plan for an Edge node."""
    node_id: str = ""
    node_name: str = ""
    quota: ResourceQuota = field(default_factory=ResourceQuota)
    allocated_tasks: int = 0
    estimated_cost: float = 0.0
    score: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "quota": {
                "cpu_cores": self.quota.cpu_cores,
                "memory_mb": self.quota.memory_mb,
                "disk_gb": self.quota.disk_gb,
                "network_mbps": self.quota.network_mbps,
                "max_tasks": self.quota.max_tasks,
                "current_tasks": self.quota.current_tasks,
                "utilization": round(self.quota.cpu_utilization, 3),
            },
            "allocated_tasks": self.allocated_tasks,
            "estimated_cost": round(self.estimated_cost, 2),
            "score": round(self.score, 3),
            "reasoning": self.reasoning,
        }


@dataclass
class OptimizationResult:
    """Result of a resource optimization run."""
    goal: OptimizationGoal = OptimizationGoal.BALANCED
    plans: List[AllocationPlan] = field(default_factory=list)
    total_tasks_allocated: int = 0
    total_estimated_cost: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal.value,
            "plans": [p.to_dict() for p in self.plans],
            "total_tasks_allocated": self.total_tasks_allocated,
            "total_estimated_cost": round(self.total_estimated_cost, 2),
            "timestamp": self.timestamp,
        }


class CostModel:
    """Simple cost model for resource estimation.

    Costs are abstract units, not actual currency.
    """

    COST_PER_CPU_CORE = 10.0
    COST_PER_GB_MEMORY = 2.0
    COST_PER_GB_DISK = 0.5
    COST_PER_MBPS_NETWORK = 1.0

    @classmethod
    def estimate(cls, quota: ResourceQuota) -> float:
        """Estimate cost for a resource quota."""
        return (
            quota.cpu_cores * cls.COST_PER_CPU_CORE +
            quota.memory_mb / 1024 * cls.COST_PER_GB_MEMORY +
            quota.disk_gb * cls.COST_PER_GB_DISK +
            quota.network_mbps * cls.COST_PER_MBPS_NETWORK
        )


class GlobalOptimizer:
    """Global resource optimizer for cross-edge allocation.

    Balances workload across registered Edge nodes based on
    optimization goals and available capacity.

    Thread-safe via RLock.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._node_quotas: Dict[str, ResourceQuota] = {}
        self._last_result: Optional[OptimizationResult] = None

    def register_node(self, node_id: str, node_name: str,
                      cpu_cores: float = 1.0, memory_mb: float = 512.0,
                      disk_gb: float = 10.0, network_mbps: float = 10.0,
                      max_tasks: int = 5, current_tasks: int = 0) -> ResourceQuota:
        """Register or update a node's resource quota."""
        with self._lock:
            quota = ResourceQuota(
                cpu_cores=cpu_cores,
                memory_mb=memory_mb,
                disk_gb=disk_gb,
                network_mbps=network_mbps,
                max_tasks=max_tasks,
                current_tasks=current_tasks,
            )
            self._node_quotas[node_id] = quota
            return quota

    def optimize(self, task_count: int = 1,
                 goal: OptimizationGoal = OptimizationGoal.BALANCED,
                 required_cpu: float = 0.1,
                 required_memory_mb: float = 64.0) -> OptimizationResult:
        """Optimize task allocation across registered nodes.

        Returns allocation plans sorted by suitability score.
        """
        with self._lock:
            plans: List[AllocationPlan] = []

            for node_id, quota in self._node_quotas.items():
                # Check capacity
                available = quota.max_tasks - quota.current_tasks
                if available <= 0:
                    continue

                # Check resource fit
                if quota.cpu_cores < required_cpu or quota.memory_mb < required_memory_mb:
                    continue

                # Allocate tasks (never exceed available)
                allocatable = min(task_count, available)
                if allocatable <= 0:
                    continue

                # Score based on goal
                utilization = quota.cpu_utilization
                cost = CostModel.estimate(quota)

                if goal == OptimizationGoal.COST:
                    score = 1.0 / max(cost, 0.01)
                elif goal == OptimizationGoal.LATENCY:
                    score = 1.0 - utilization  # Prefer idle nodes
                elif goal == OptimizationGoal.THROUGHPUT:
                    score = quota.cpu_cores * (1.0 - utilization)
                else:  # BALANCED
                    score = (1.0 - utilization) * 2.0 + 1.0 / max(cost, 0.01)

                plan = AllocationPlan(
                    node_id=node_id,
                    node_name=node_id,  # Placeholder, caller provides real name
                    quota=quota,
                    allocated_tasks=allocatable,
                    estimated_cost=cost * (allocatable / max(quota.max_tasks, 1)),
                    score=score,
                    reasoning=(
                        f"Node {node_id}: {allocatable} tasks allocated "
                        f"({quota.current_tasks}/{quota.max_tasks} in use, "
                        f"{utilization:.0%} utilized)"
                    ),
                )
                plans.append(plan)

            # Sort by score descending
            plans.sort(key=lambda p: p.score, reverse=True)

            result = OptimizationResult(
                goal=goal,
                plans=plans,
                total_tasks_allocated=sum(p.allocated_tasks for p in plans),
                total_estimated_cost=sum(p.estimated_cost for p in plans),
            )
            self._last_result = result
            return result

    def get_last_result(self) -> Optional[OptimizationResult]:
        with self._lock:
            return self._last_result

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            nodes = len(self._node_quotas)
            total_capacity = sum(q.max_tasks for q in self._node_quotas.values())
            total_used = sum(q.current_tasks for q in self._node_quotas.values())
            return {
                "registered_nodes": nodes,
                "total_capacity": total_capacity,
                "total_used": total_used,
                "utilization": total_used / max(total_capacity, 1),
            }

    def remove_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._node_quotas:
                del self._node_quotas[node_id]
                return True
            return False
