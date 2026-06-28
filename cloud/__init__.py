"""Cloud Hub package.

Exports all cloud engines, services, and API components.
v1.8.1: Added Eventing infrastructure + new engines (Workflow/Optimizer/DeepThink/KnowledgeGraph)
v3.0.0: Engine slim-down (15→6). Deprecated engines kept for backward compat.
"""

from cloud.config import config

# ── v3.0 Core Engines (6) ─────────────────────────────
from cloud.engines.eventbus import CloudEventBus
from cloud.engines.task_board import GlobalTaskBoard, TaskStatus, TaskPriority
from cloud.engines.capability_registry import CapabilityRegistry
from cloud.engines.insight import InsightEngine
from cloud.engines.scheduler import CloudScheduler, CronExpression

# ── v3.0 Services ─────────────────────────────────────
from cloud.services.vault_api import VaultAPI
from cloud.services.oss_sync import OSSVaultSync
from cloud.services.memos_cloud import MemOSCloudClient

# ── v1.8.1 Eventing infrastructure (retained) ─────────
from cloud.eventing import (
    EventStore, Event, Topic,
    EventTracer, EventSpan, TraceResult,
    DeadLetterQueue, DeadLetter, DLQReason, DLQStats,
    PriorityQueue, Priority, PQItem,
    EventAggregator, AggregatedEvent, AggregationRule,
    EventMetrics, EventMetric,
    PatternMiner, Pattern, MiningResult,
    MLEngine, AnomalyResult, TrendResult,
    QualityEvaluator, QualityScore, QualityLevel,
)

# ── Deprecated engines (v1.8.1, superseded by v3.0 AgentMesh/HermesLoop) ─
from cloud.engines.swarm_coordinator import SwarmCoordinator
from cloud.engines.skill_market import SkillMarket
from cloud.engines.evolution import EvolutionEngine
from cloud.engines.review import UnifiedReviewEngine
from cloud.engines.broadcast import BroadcastEngine
from cloud.engines.n8n_bridge import N8NBridge

from cloud.engines.workflow import (
    WorkflowEngine, Workflow, Step, Execution,
    StepType, ExecutionStatus,
)
from cloud.engines.optimizer import (
    GlobalOptimizer, OptimizationGoal, ResourceType,
    ResourceQuota, AllocationPlan, OptimizationResult, CostModel,
)
from cloud.engines.deep_think import (
    DeepThinkEngine, ThinkNode, ThinkResult,
)
from cloud.services.knowledge_graph import (
    KnowledgeGraph, Entity, Relation, GraphQuery, SearchResult,
)

__all__ = [
    "config",
    # Core (v3.0)
    "CloudEventBus",
    "GlobalTaskBoard", "TaskStatus", "TaskPriority",
    "CapabilityRegistry",
    "InsightEngine",
    "CloudScheduler", "CronExpression",
    # Services
    "VaultAPI", "OSSVaultSync", "MemOSCloudClient",
    # Eventing (retained)
    "EventStore", "Event", "Topic",
    "EventTracer", "EventSpan", "TraceResult",
    "DeadLetterQueue", "DeadLetter", "DLQReason", "DLQStats",
    "PriorityQueue", "Priority", "PQItem",
    "EventAggregator", "AggregatedEvent", "AggregationRule",
    "EventMetrics", "EventMetric",
    "PatternMiner", "Pattern", "MiningResult",
    "MLEngine", "AnomalyResult", "TrendResult",
    "QualityEvaluator", "QualityScore", "QualityLevel",
    # Deprecated (kept for compat, superseded in v3.0)
    "SwarmCoordinator",
    "SkillMarket",
    "EvolutionEngine",
    "BroadcastEngine",
    "N8NBridge",
    "UnifiedReviewEngine",
    "WorkflowEngine", "Workflow", "Step", "Execution",
    "StepType", "ExecutionStatus",
    "GlobalOptimizer", "OptimizationGoal", "ResourceType",
    "ResourceQuota", "AllocationPlan", "OptimizationResult", "CostModel",
    "DeepThinkEngine", "ThinkNode", "ThinkResult",
    "KnowledgeGraph", "Entity", "Relation", "GraphQuery", "SearchResult",
]
