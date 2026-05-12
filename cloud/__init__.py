"""Cloud Hub package.

Exports all cloud engines, services, and API components.
v1.8.1: Added Eventing infrastructure + new engines (Workflow/Optimizer/DeepThink/KnowledgeGraph)
"""

from cloud.config import config
from cloud.engines.eventbus import CloudEventBus
from cloud.engines.capability_registry import CapabilityRegistry
from cloud.engines.scheduler import CloudScheduler, CronExpression
from cloud.engines.task_board import GlobalTaskBoard, TaskStatus, TaskPriority
from cloud.engines.skill_market import SkillMarket
from cloud.engines.swarm_coordinator import SwarmCoordinator
from cloud.engines.evolution import EvolutionEngine
from cloud.engines.review import UnifiedReviewEngine
from cloud.engines.broadcast import BroadcastEngine
from cloud.engines.n8n_bridge import N8NBridge
from cloud.services.vault_api import VaultAPI
from cloud.services.oss_sync import OSSVaultSync
from cloud.services.memos_cloud import MemOSCloudClient

# v1.8.1 Eventing infrastructure
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

# v1.8.1 New engines
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
    "CloudEventBus",
    "CapabilityRegistry",
    "CloudScheduler", "CronExpression",
    "GlobalTaskBoard", "TaskStatus", "TaskPriority",
    "SkillMarket",
    "SwarmCoordinator",
    "EvolutionEngine",
    "UnifiedReviewEngine",
    "BroadcastEngine",
    "N8NBridge",
    "VaultAPI",
    "OSSVaultSync",
    "MemOSCloudClient",
    # Eventing
    "EventStore", "Event", "Topic",
    "EventTracer", "EventSpan", "TraceResult",
    "DeadLetterQueue", "DeadLetter", "DLQReason", "DLQStats",
    "PriorityQueue", "Priority", "PQItem",
    "EventAggregator", "AggregatedEvent", "AggregationRule",
    "EventMetrics", "EventMetric",
    "PatternMiner", "Pattern", "MiningResult",
    "MLEngine", "AnomalyResult", "TrendResult",
    "QualityEvaluator", "QualityScore", "QualityLevel",
    # New engines
    "WorkflowEngine", "Workflow", "Step", "Execution",
    "StepType", "ExecutionStatus",
    "GlobalOptimizer", "OptimizationGoal", "ResourceType",
    "ResourceQuota", "AllocationPlan", "OptimizationResult", "CostModel",
    "DeepThinkEngine", "ThinkNode", "ThinkResult",
    "KnowledgeGraph", "Entity", "Relation", "GraphQuery", "SearchResult",
]
