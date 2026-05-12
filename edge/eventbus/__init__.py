"""Edge EventBus — enhanced local event bus with condition engine.

v1.8.1: Replaces simple LocalEventBus with MacOS-enhanced version
featuring Condition Engine, Dead Letter Queue, and Event Tracer.
"""

from edge.eventbus.core import EdgeEventBus
from edge.eventbus.condition_engine import ConditionEngine, Condition, ConditionType
from edge.eventbus.dead_letter import EdgeDeadLetterQueue, DeadLetter, DLQReason
from edge.eventbus.tracer import EdgeEventTracer, EventSpan, TraceResult

__all__ = [
    "EdgeEventBus",
    "ConditionEngine", "Condition", "ConditionType",
    "EdgeDeadLetterQueue", "DeadLetter", "DLQReason",
    "EdgeEventTracer", "EventSpan", "TraceResult",
]
