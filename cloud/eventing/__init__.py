"""Cloud Eventing — Event Sourcing infrastructure for ClawShell 2.0.

Event Store: append-only persistent event storage with sequence-based replay.
Event Tracer: causal chain tracking for debugging event flows.
Dead Letter Queue: failed event replay with configurable retry.
Priority Queue: heap-based ordering for event processing.
Event Aggregator: time-window aggregation for pattern detection.
Event Metrics: statistical summaries for monitoring.
Pattern Miner: recurring pattern detection in event streams.
ML Engine: statistical anomaly detection (z-score, trend analysis).
Quality Evaluator: multi-dimensional quality scoring.

All modules: stdlib-only, RLock thread-safe, daemon-friendly (5s chunks).
"""

from cloud.eventing.store import EventStore, Event, Topic
from cloud.eventing.tracer import EventTracer, EventSpan, TraceResult
from cloud.eventing.dead_letter import (
    DeadLetterQueue, DeadLetter, DLQReason, DLQStats,
)
from cloud.eventing.priority_queue import PriorityQueue, Priority, PQItem
from cloud.eventing.aggregator import (
    EventAggregator, AggregatedEvent, AggregationRule,
)
from cloud.eventing.metrics import EventMetrics, EventMetric
from cloud.eventing.pattern_miner import PatternMiner, Pattern, MiningResult
from cloud.eventing.ml_engine import MLEngine, AnomalyResult, TrendResult
from cloud.eventing.quality import QualityEvaluator, QualityScore, QualityLevel

__all__ = [
    # Store
    "EventStore", "Event", "Topic",
    # Tracer
    "EventTracer", "EventSpan", "TraceResult",
    # Dead Letter
    "DeadLetterQueue", "DeadLetter", "DLQReason", "DLQStats",
    # Priority
    "PriorityQueue", "Priority", "PQItem",
    # Aggregator
    "EventAggregator", "AggregatedEvent", "AggregationRule",
    # Metrics
    "EventMetrics", "EventMetric",
    # Pattern
    "PatternMiner", "Pattern", "MiningResult",
    # ML
    "MLEngine", "AnomalyResult", "TrendResult",
    # Quality
    "QualityEvaluator", "QualityScore", "QualityLevel",
]
