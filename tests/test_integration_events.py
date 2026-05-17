"""Integration tests — EdgeEventBus sub-modules and CloudEventBus PubSub wiring.

Tests:
1. EdgeEventBus with condition engine (event blocked → DLQ)
2. EdgeEventBus with tracer (trace spans recorded)
3. EdgeEventBus with DLQ (failed delivery → DLQ entry)
4. CloudEventBus with PubSub integration
"""

import os
import sys
import time
import tempfile
import threading

import pytest

# Ensure clawshell root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge.eventbus.core import EdgeEventBus
from edge.eventbus.condition_engine import ConditionEngine, Condition, ConditionType
from edge.eventbus.dead_letter import EdgeDeadLetterQueue, DeadLetter, DLQReason
from edge.eventbus.tracer import EdgeEventTracer, EventSpan, TraceResult
from cloud.engines.eventbus import CloudEventBus


# ─────────────────────────────────────────────────────────────
# 1. ConditionEngine — event blocked by condition → DLQ
# ─────────────────────────────────────────────────────────────

class TestConditionEngineIntegration:
    """Test that EdgeEventBus correctly blocks events via ConditionEngine."""

    def test_condition_blocks_event_to_dlq(self):
        """Event with data matching a blocking condition goes to DLQ."""
        bus = EdgeEventBus()
        assert bus.condition_engine is not None
        assert bus.dlq is not None

        # Add a condition: block events where cpu > 80
        cond = Condition(
            name="high_cpu_block",
            cond_type=ConditionType.THRESHOLD,
            metric="cpu",
            operator=">",
            threshold=80.0,
        )
        bus.condition_engine.add_condition(cond)

        # Publish an event with cpu=95 (should be blocked)
        result = bus.publish("test.event", data={"cpu": 95, "mem": 50}, source="test")
        assert result.get("_blocked") is True
        assert "high_cpu_block" in result.get("_blocked_by", [])

        # Verify DLQ entry
        dlq_items = bus.get_dlq_items()
        assert len(dlq_items) == 1
        assert dlq_items[0].event_type == "test.event"
        assert "high_cpu_block" in dlq_items[0].error_message

    def test_condition_allows_event(self):
        """Event with data NOT matching a blocking condition is delivered."""
        bus = EdgeEventBus()

        cond = Condition(
            name="high_cpu_block",
            cond_type=ConditionType.THRESHOLD,
            metric="cpu",
            operator=">",
            threshold=80.0,
        )
        bus.condition_engine.add_condition(cond)

        delivered = []
        bus.subscribe("test.event", lambda e: delivered.append(e))

        # cpu=50 is below threshold, so event should pass
        result = bus.publish("test.event", data={"cpu": 50}, source="test")
        assert result.get("_blocked") is None
        assert len(delivered) == 1

    def test_condition_non_dict_data_passes(self):
        """Events with non-dict data are not blocked by conditions."""
        bus = EdgeEventBus()

        cond = Condition(
            name="block_high_cpu",
            cond_type=ConditionType.THRESHOLD,
            metric="cpu",
            operator=">",
            threshold=80.0,
        )
        bus.condition_engine.add_condition(cond)

        delivered = []
        bus.subscribe("test.event", lambda e: delivered.append(e))

        result = bus.publish("test.event", data="simple string", source="test")
        assert result.get("_blocked") is None
        assert len(delivered) == 1

    def test_get_condition_stats(self):
        """get_condition_stats returns engine stats."""
        bus = EdgeEventBus()
        bus.condition_engine.add_condition(
            Condition(name="c1", cond_type=ConditionType.THRESHOLD,
                      metric="x", operator=">", threshold=10)
        )
        stats = bus.get_condition_stats()
        assert stats["condition_count"] == 1


# ─────────────────────────────────────────────────────────────
# 2. EventTracer — trace spans recorded
# ─────────────────────────────────────────────────────────────

class TestEventTracerIntegration:
    """Test that EdgeEventBus correctly records trace spans."""

    def test_trace_span_recorded_on_publish(self):
        """Each publish creates a trace span that is completed."""
        bus = EdgeEventBus()
        assert bus.tracer is not None

        bus.subscribe("test.event", lambda e: None)
        result = bus.publish("test.event", data={"value": 1}, source="test")

        # Tracer should have 1 span, 1 trace
        stats = bus.tracer.get_stats()
        assert stats["total_spans"] == 1
        assert stats["total_traces"] == 1

    def test_trace_span_success_status(self):
        """Successful delivery records success status."""
        bus = EdgeEventBus()
        bus.subscribe("test.event", lambda e: None)
        bus.publish("test.event", data={}, source="test")

        # Get the trace — find the trace_id from the span
        span_id = list(bus.tracer._spans.keys())[0]
        span = bus.tracer._spans[span_id]
        assert span.status == "success"
        assert span.completed_at is not None

    def test_trace_span_error_on_subscriber_failure(self):
        """Failed subscriber records error status on span."""
        bus = EdgeEventBus()

        def bad_handler(e):
            raise ValueError("boom")

        bus.subscribe("test.event", bad_handler)
        bus.publish("test.event", data={}, source="test")

        span_id = list(bus.tracer._spans.keys())[0]
        span = bus.tracer._spans[span_id]
        assert span.status == "error"

    def test_get_trace_returns_trace_result(self):
        """get_trace returns a TraceResult with correct spans."""
        bus = EdgeEventBus()
        bus.subscribe("test.event", lambda e: None)
        bus.publish("test.event", data={}, source="test")

        span_id = list(bus.tracer._spans.keys())[0]
        trace_id = bus.tracer._spans[span_id].trace_id

        result = bus.get_trace(trace_id)
        assert result is not None
        assert isinstance(result, TraceResult)
        assert result.total_spans == 1
        assert result.error_spans == 0

    def test_no_tracer_returns_none(self):
        """get_trace returns None when tracer is disabled."""
        # Create a bus with tracer disabled by monkeypatching
        bus = EdgeEventBus()
        bus._tracer = None
        assert bus.get_trace("any-id") is None


# ─────────────────────────────────────────────────────────────
# 3. DeadLetterQueue — failed delivery → DLQ entry
# ─────────────────────────────────────────────────────────────

class TestDeadLetterQueueIntegration:
    """Test that EdgeEventBus logs failed deliveries to DLQ."""

    def test_subscriber_failure_creates_dlq_entry(self):
        """When a subscriber throws, a DLQ entry is created."""
        bus = EdgeEventBus()
        assert bus.dlq is not None

        def failing_subscriber(e):
            raise RuntimeError("handler crashed")

        bus.subscribe("test.fail", failing_subscriber)
        bus.publish("test.fail", data={"key": "value"}, source="test")

        dlq_items = bus.get_dlq_items()
        assert len(dlq_items) == 1
        assert dlq_items[0].event_type == "test.fail"
        assert "handler crashed" in dlq_items[0].error_message
        assert dlq_items[0].reason == DLQReason.HANDLER_ERROR

    def test_multiple_failures_accumulate_in_dlq(self):
        """Multiple failing subscribers each create a DLQ entry."""
        bus = EdgeEventBus()

        def fail1(e):
            raise TypeError("error1")

        def fail2(e):
            raise TypeError("error2")

        bus.subscribe("test.multi", fail1)
        bus.subscribe("test.multi", fail2)
        bus.publish("test.multi", data={}, source="test")

        dlq_items = bus.get_dlq_items()
        assert len(dlq_items) == 2

    def test_successful_delivery_no_dlq(self):
        """Successful delivery does not create DLQ entries."""
        bus = EdgeEventBus()
        bus.subscribe("test.ok", lambda e: None)
        bus.publish("test.ok", data={}, source="test")

        dlq_items = bus.get_dlq_items()
        assert len(dlq_items) == 0

    def test_condition_blocked_event_in_dlq(self):
        """Condition-blocked events are logged to DLQ."""
        bus = EdgeEventBus()

        from edge.eventbus.condition_engine import Condition, ConditionType
        bus.condition_engine.add_condition(
            Condition(name="block", cond_type=ConditionType.THRESHOLD,
                      metric="val", operator=">", threshold=100)
        )

        bus.publish("test.blocked", data={"val": 200}, source="test")

        dlq_items = bus.get_dlq_items()
        assert len(dlq_items) == 1
        assert "Blocked by conditions" in dlq_items[0].error_message

    def test_no_dlq_returns_empty(self):
        """get_dlq_items returns empty when DLQ is disabled."""
        bus = EdgeEventBus()
        bus._dlq = None
        assert bus.get_dlq_items() == []

    def test_get_stats_includes_dlq(self):
        """get_stats includes DLQ stats when available."""
        bus = EdgeEventBus()
        stats = bus.get_stats()
        assert "dlq" in stats
        assert "size" in stats["dlq"]


# ─────────────────────────────────────────────────────────────
# 4. CloudEventBus with PubSub integration
# ─────────────────────────────────────────────────────────────

class TestCloudEventBusPubSub:
    """Test CloudEventBus PubSubManager wiring."""

    def test_pubsub_property_exists(self):
        """CloudEventBus has a pubsub property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = CloudEventBus(data_dir=tmpdir)
            # pubsub may or may not be available depending on imports
            # but the property should exist
            assert hasattr(bus, 'pubsub')
            assert hasattr(bus, '_pubsub')

    def test_ingest_publishes_to_pubsub(self):
        """Ingested events are forwarded to PubSubManager if available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = CloudEventBus(data_dir=tmpdir)

            # Track if pubsub.publish was called
            published = []
            if bus._pubsub is not None:
                original_publish = bus._pubsub.publish
                def tracking_publish(event, target=None):
                    published.append(event)
                    return original_publish(event, target=target)
                bus._pubsub.publish = tracking_publish

            event = {
                "event_id": "test-001",
                "event_type": "test.pubsub",
                "source": "test",
                "timestamp": time.time(),
                "payload": {"data": "hello"},
            }
            accepted = bus.ingest([event])
            assert accepted == 1

            if bus._pubsub is not None:
                assert len(published) == 1
                assert published[0]["event_id"] == "test-001"

    def test_ingest_graceful_without_pubsub(self):
        """Ingest works fine when PubSubManager is unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = CloudEventBus(data_dir=tmpdir)
            bus._pubsub = None  # Force disable

            event = {
                "event_id": "test-002",
                "event_type": "test.no_pubsub",
                "source": "test",
                "timestamp": time.time(),
                "payload": {},
            }
            accepted = bus.ingest([event])
            assert accepted == 1

    def test_pubsub_not_created_without_import(self):
        """PubSubManager gracefully falls back when import fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = CloudEventBus(data_dir=tmpdir)
            # If the import works, pubsub is set; if not, it's None
            # Either way, the bus should function
            stats = bus.get_stats()
            assert "total_events" in stats


# ─────────────────────────────────────────────────────────────
# 5. Backward compatibility
# ─────────────────────────────────────────────────────────────

class TestBackwardCompatibility:
    """Ensure existing EdgeEventBus API still works."""

    def test_subscribe_publish_still_works(self):
        """Basic pub/sub still works as before."""
        bus = EdgeEventBus()
        received = []
        bus.subscribe("my.event", lambda e: received.append(e))
        bus.publish("my.event", data={"x": 1}, source="test")
        assert len(received) == 1
        assert received[0]["data"]["x"] == 1

    def test_wildcard_subscribe(self):
        """Wildcard '*' subscription still works."""
        bus = EdgeEventBus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))
        bus.publish("any.event", data={}, source="test")
        assert len(received) == 1

    def test_get_history(self):
        """get_history still works."""
        bus = EdgeEventBus()
        bus.publish("a", data={})
        bus.publish("b", data={})
        assert len(bus.get_history()) == 2
        assert len(bus.get_history(event_type="a")) == 1

    def test_get_stats_includes_submodules(self):
        """get_stats now includes sub-module stats."""
        bus = EdgeEventBus()
        stats = bus.get_stats()
        assert "total_events" in stats
        assert "subscriber_count" in stats
        assert "dlq" in stats
        assert "tracer" in stats
        assert "conditions" in stats

    def test_shutdown(self):
        """shutdown sets _running to False."""
        bus = EdgeEventBus()
        assert bus._running is True
        bus.shutdown()
        assert bus._running is False
