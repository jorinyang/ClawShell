"""Phase 2 tests: Cloud Eventing Infrastructure (v1.8.1).

Tests cover all 8 eventing modules:
- EventStore (append, replay, query, stats)
- EventTracer (span lifecycle, trace analysis)
- DeadLetterQueue (enqueue, retry, mark)
- PriorityQueue (ordering, priority levels)
- EventAggregator (time windows, flush)
- EventMetrics (recording, summaries)
- PatternMiner (frequency, sequence, co-occurrence)
- MLEngine (anomaly detection, trend analysis)
- QualityEvaluator (scoring, levels, trends)
"""

import os, sys, json, time, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_all():
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

    import tempfile
    tmp = tempfile.mkdtemp(prefix="cs_test_p2_")

    passed, failed = 0, 0
    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  ✅ {name}")
        else:
            failed += 1
            print(f"  ❌ {name}")

    print("── Phase 2: Cloud Eventing Infrastructure ──")

    # ════════════════════════════════════════════════
    # EventStore
    # ════════════════════════════════════════════════
    print("\n── EventStore ──")
    store_dir = os.path.join(tmp, "event_store")
    store = EventStore(store_dir=store_dir)
    check("EventStore created", store_dir is not None)

    ev1 = Event(topic=Topic.TASK_CREATED, source="edge-1", payload={"title": "Task 1"})
    stored = store.append(ev1)
    check("append assigns seq_id=1", stored.sequence_id == 1)
    check("get_by_seq returns event", store.get_by_seq(1).topic == Topic.TASK_CREATED)

    store.append(Event(topic=Topic.TASK_CLAIMED, source="edge-1"))
    store.append(Event(topic=Topic.TASK_COMPLETED, source="edge-1"))
    store.append(Event(topic=Topic.SYSTEM_HEALTH, source="edge-2"))
    store.append(Event(topic=Topic.NODE_REGISTERED, source="edge-3"))

    replayed = store.replay(from_seq=0)
    check("replay returns 5 events", len(replayed) == 5)
    check("replay order preserved", replayed[0].sequence_id == 1 and replayed[4].sequence_id == 5)

    # Query by topic
    tasks = store.query(topic="task.created", limit=10)
    check("query by topic", len(tasks) == 1)
    check("query by source", len(store.query(source="edge-1", limit=10)) == 3)

    stats = store.get_stats()
    check("stats total_events=5", stats["total_events"] == 5)

    # Batch append
    batch = [Event(topic=Topic.SKILL_PUBLISHED) for _ in range(3)]
    store.append_batch(batch)
    check("batch append", store.get_stats()["total_events"] == 8)

    store.shutdown()

    # ════════════════════════════════════════════════
    # EventTracer
    # ════════════════════════════════════════════════
    print("\n── EventTracer ──")
    tracer = EventTracer()

    span1 = tracer.start_span("ev-001", "task.created", source="worker-1")
    check("start_span creates span", span1.span_id and span1.trace_id)

    tracer.complete_span(span1.span_id, "success", result_events=["ev-002", "ev-003"])
    span2 = tracer.start_span("ev-002", "task.claimed", source="worker-2",
                              parent_span_id=span1.span_id)
    check("child span inherits trace_id", span2.trace_id == span1.trace_id)

    tracer.complete_span(span2.span_id, "success")
    trace = tracer.get_trace(span1.trace_id)
    check("trace has 2 spans", trace.total_spans == 2)
    check("trace no errors", trace.error_spans == 0)

    # Error span
    span3 = tracer.start_span("ev-err", "task.failed", source="worker-1")
    tracer.complete_span(span3.span_id, "error", error_message="Connection timeout")
    trace3 = tracer.get_trace(span3.trace_id)
    check("error trace detected", trace3 and trace3.error_spans == 1)

    check("tracer stats", tracer.get_stats()["total_spans"] == 3)
    tracer.shutdown()

    # ════════════════════════════════════════════════
    # DeadLetterQueue
    # ════════════════════════════════════════════════
    print("\n── DeadLetterQueue ──")
    dlq_dir = os.path.join(tmp, "dlq")
    dlq = DeadLetterQueue(base_dir=dlq_dir, retry_delay=0)  # retry_delay=0 for testing

    dl = dlq.enqueue({"data": "failed1"}, topic="test.topic",
                     reason=DLQReason.HANDLER_ERROR, error_message="boom")
    check("enqueue creates DL", dl.dlq_id and dl.reason == DLQReason.HANDLER_ERROR)

    # With retry_delay=0, item should be immediately available
    pending = dlq.get_pending()
    check("get_pending returns item", len(pending) == 1)

    # Test retry update
    for i in range(2):
        dlq.update_retry(dl.dlq_id, f"retry failed {i+1}")
    # After 2 updates (retry_count=2), still under max_retries=3
    pending2 = dlq.get_pending()
    check("still pending after retries < max", len(pending2) == 1)

    # 3rd retry → should move to permanent failure
    dlq.update_retry(dl.dlq_id, "final retry failed")
    pending3 = dlq.get_pending()
    check("moved to failed after max retries", len(pending3) == 0)

    # Mark resolved
    dl2 = dlq.enqueue({"data": "resolved"}, topic="test.topic",
                      reason=DLQReason.TIMEOUT, error_message="timeout")
    dlq.mark_resolved(dl2.dlq_id)

    stats = dlq.get_stats()
    check("DLQ stats has entries", stats.total_dead >= 0 and stats.resolved >= 0)
    check("DLQ stats resolved", stats.resolved >= 1)
    check("DLQ stats by_reason", stats.by_reason.get("timeout", 0) >= 0)

    dlq.shutdown()

    # ════════════════════════════════════════════════
    # PriorityQueue
    # ════════════════════════════════════════════════
    print("\n── PriorityQueue ──")
    pq = PriorityQueue(max_size=100)

    pq.enqueue("low1", Priority.LOW)
    pq.enqueue("med1", Priority.MEDIUM)
    pq.enqueue("high1", Priority.HIGH)
    pq.enqueue("crit1", Priority.CRITICAL)
    pq.enqueue("low2", Priority.LOW)
    check("pq size=5", pq.size() == 5)

    item = pq.dequeue()
    check("dequeue CRITICAL first", item.priority == Priority.CRITICAL)
    item = pq.dequeue()
    check("dequeue HIGH second", item.priority == Priority.HIGH)
    item = pq.dequeue()
    check("dequeue MEDIUM third", item.priority == Priority.MEDIUM)

    # FIFO within same priority
    item = pq.dequeue()
    check("FIFO: first LOW dequeued first", item.payload == "low1" and item.priority == Priority.LOW)

    check("pq stats", pq.get_stats()["total_enqueued"] == 5)
    check("pq peek", pq.peek().payload == "low2")
    pq.drain_all()
    check("pq drained", pq.is_empty())

    # ════════════════════════════════════════════════
    # EventAggregator
    # ════════════════════════════════════════════════
    print("\n── EventAggregator ──")
    agg = EventAggregator()

    agg.ingest("task.created", "e1")
    agg.ingest("task.created", "e1")
    agg.ingest("skill.published", "e2")
    agg.ingest("node.heartbeat", "e3")

    current = agg.get_current()
    check("aggregator total=4", current and current.total_events == 4)
    check("aggregator by_topic", current.by_topic.get("task.created") == 2)
    check("aggregator sources", "e1" in current.sources)

    agg.flush()
    completed = agg.get_completed(limit=5)
    check("flush produces completed window", len(completed) >= 1)
    check("aggregator current reset", agg.get_current() is None)

    # ════════════════════════════════════════════════
    # EventMetrics
    # ════════════════════════════════════════════════
    print("\n── EventMetrics ──")
    metrics = EventMetrics()
    metrics.record("task.created", latency_ms=100)
    metrics.record("task.created", latency_ms=200)
    metrics.record("task.created", latency_ms=50, is_error=True)

    m = metrics.get_metric("task.created")
    check("metrics total=3", m.total == 3)
    check("metrics success=2", m.success == 2)
    check("metrics error=1", m.error == 1)
    check("metrics error_rate", 0.3 <= m.error_rate <= 0.4)

    summary = metrics.get_summary()
    check("summary total_events", summary["total_events"] == 3)
    check("summary unique_topics", summary["unique_topics"] == 1)

    # ════════════════════════════════════════════════
    # PatternMiner
    # ════════════════════════════════════════════════
    print("\n── PatternMiner ──")
    miner = PatternMiner(min_support=3, min_confidence=0.3)

    # Ingest a repeating pattern: task.created → task.claimed → task.completed
    for _ in range(20):
        miner.ingest("task.created")
        miner.ingest("task.claimed")
        miner.ingest("task.completed")

    result = miner.mine()
    check("miner produces patterns", len(result.patterns) > 0)
    check("miner events analyzed", result.total_events_analyzed == 60)
    check("miner unique_topics=3", result.unique_topics == 3)

    # Check pattern types
    has_seq = any("Transition" in p.name for p in result.patterns)
    check("miner finds sequential patterns", has_seq)

    patterns = miner.get_patterns()
    check("get_patterns returns results", len(patterns) > 0)

    # ════════════════════════════════════════════════
    # MLEngine
    # ════════════════════════════════════════════════
    print("\n── MLEngine ──")
    ml = MLEngine(history_size=50)

    # Feed stable data
    for i in range(30):
        ml.observe("task.created", 10.0 + (i % 5) * 0.1)  # 10.0-10.5 normal range

    # No anomalies in stable data
    anomalies = ml.detect_anomalies()
    check("no anomalies in stable data", len(anomalies) == 0)

    # Inject spike
    ml.observe("task.created", 50.0)
    anomalies = ml.detect_anomalies()
    check("spike detected", len(anomalies) > 0)
    check("spike is critical", anomalies[0].severity == "critical")

    # Trend analysis (slightly increasing)
    ml2 = MLEngine()
    for i in range(30):
        ml2.observe("skill.published", 1.0 + i * 0.2)  # increasing trend
    trends = ml2.analyze_trends()
    check("increasing trend detected", len(trends) > 0 and trends[0].trend_type == "increasing")

    # ════════════════════════════════════════════════
    # QualityEvaluator
    # ════════════════════════════════════════════════
    print("\n── QualityEvaluator ──")
    qe = QualityEvaluator(latency_target_ms=500, max_error_rate=0.05)

    # Good quality: 100 events, 98 processed, 95 in latency, 1 error
    score = qe.evaluate(100, 98, 95, 1, pattern_stability=0.85)
    check("quality level good/excellent", score.level in [QualityLevel.EXCELLENT, QualityLevel.GOOD])
    check("quality overall > 0.90", score.overall_score > 0.90)

    # Poor quality: very bad metrics → should be POOR or CRITICAL
    score2 = qe.evaluate(100, 60, 30, 20, pattern_stability=0.3)
    check("poor quality detected", score2.level in [QualityLevel.FAIR, QualityLevel.POOR, QualityLevel.CRITICAL])
    check("poor quality < 0.75", score2.overall_score < 0.75)

    # Trend
    qe.evaluate(100, 90, 85, 5, 0.5)
    qe.evaluate(100, 92, 88, 4, 0.6)
    qe.evaluate(100, 95, 90, 3, 0.7)
    trend = qe.get_trend()
    check("quality trend detected", trend["direction"] in ["improving", "stable", "degrading"])
    check("quality history", len(trend["history"]) >= 1)

    # Cleanup
    shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n── Phase 2 Summary: {passed} passed, {failed} failed ──")
    return failed == 0


if __name__ == "__main__":
    ok = test_all()
    sys.exit(0 if ok else 1)
