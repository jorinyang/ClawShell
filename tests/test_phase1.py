"""Phase 1 Comprehensive Verification Test Suite.

Tests:
  TEST 1: shared/ — 18 data model + protocol tests
  TEST 2: CloudEventBus — ingest/query/dedup/expiry/stats
  TEST 3: CapabilityRegistry — register/heartbeat/offline/assign
  TEST 4: CronScheduler — cron parsing/matching/scheduling
  TEST 5: Cloud Config — env-based config management
"""
import sys
import os
import time
import json
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}")


# ── TEST 1: shared/ module ─────────────────────────
print("\n── TEST 1: shared/ data models & protocol ──")

from shared import ClawShellEvent, Task, Skill, EdgeNode, Insight, Broadcast
from shared import format_api_response, format_ws_frame, validate_ws_frame
from shared import content_hash, generate_node_id, validate_node_id
from shared.types import TaskStatus, TaskPriority, NodeStatus, EventCategory

e = ClawShellEvent(event_type='test', source='edge-1', category='task')
check("Event creation", e.event_type == 'test')
check("Event hash length", len(e.content_hash()) == 64)

e2 = ClawShellEvent.from_dict(e.to_dict())
check("Event round-trip", e2.event_type == 'test')

t = Task(title='Task', priority='medium', status='pending')
check("Task enum conversion", t.status == TaskStatus.PENDING)

n = EdgeNode(node_id='n1', status='online')
check("Node enum conversion", n.status == NodeStatus.ONLINE)

f = format_ws_frame('event_push', {'id': '1'})
check("WS frame valid", validate_ws_frame(f))

nid = generate_node_id('host')
check("NodeID valid", validate_node_id(nid))

s = Skill(name='s1')
check("Skill creation", s.name == 's1')
ins = Insight(title='insight', confidence=0.9)
check("Insight creation", ins.confidence == 0.9)
br = Broadcast(title='msg', broadcast_type='alert')
check("Broadcast creation", br.broadcast_type == 'alert')

print(f"  TEST 1: {passed}/{passed+failed} passed")


# ── TEST 2: CloudEventBus ──────────────────────────
print("\n── TEST 2: CloudEventBus engine ──")

tmpdir = tempfile.mkdtemp(prefix="clawshell_test_")
try:
    from cloud.engines.eventbus import CloudEventBus

    eb = CloudEventBus(data_dir=tmpdir)

    # Test ingest
    events = [
        {"event_id": f"evt_{i}", "event_type": "test", "source": "edge-A",
         "timestamp": time.time(), "payload": {"msg": f"hello {i}"}}
        for i in range(10)
    ]
    accepted = eb.ingest(events)
    check("Ingest 10 events", accepted == 10)

    # Test dedup
    accepted2 = eb.ingest(events)
    check("Dedup rejects duplicates", accepted2 == 0)

    # Test query all
    results = eb.query(limit=50)
    check("Query returns all", len(results) == 10)

    # Test query by type
    results = eb.query(event_type="test")
    check("Query by type", len(results) == 10)

    # Test query by source
    results = eb.query(source="edge-A")
    check("Query by source", len(results) == 10)

    # Test query by wildcard
    results = eb.query(event_type="test*")
    check("Query by wildcard", len(results) == 10)

    # Test get single event
    evt = eb.get_event("evt_0")
    check("Get single event", evt is not None and evt["event_id"] == "evt_0")

    # Test stats
    stats = eb.get_stats()
    check("Stats have fields", "total_events" in stats and stats["total_events"] == 10)

    # Test broadcast
    bc_events = [{"event_id": "bc_1", "event_type": "broadcast", "source": "cloud",
                   "timestamp": time.time(), "payload": {"msg": "hello"}}]
    ids = eb.broadcast(bc_events)
    check("Broadcast returns ID", len(ids) == 1)

    # Test recent broadcasts
    rbc = eb.get_recent_broadcasts()
    check("Recent broadcasts", len(rbc) >= 1)

    # Test shutdown
    eb.shutdown()
    check("Shutdown clean", True)

    print(f"  TEST 2: {passed}/{passed+failed} passed")
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── TEST 3: CapabilityRegistry ─────────────────────
print("\n── TEST 3: CapabilityRegistry engine ──")

tmpdir = tempfile.mkdtemp(prefix="clawshell_test_")
try:
    from cloud.engines.capability_registry import CapabilityRegistry

    cr = CapabilityRegistry(data_dir=tmpdir, heartbeat_interval=30, heartbeat_timeout=90)

    # Test register
    nid = cr.register({
        "node_id": "edge-001",
        "node_name": "Test Edge",
        "hostname": "test-host",
        "os_type": "linux",
        "capabilities": ["code", "search"],
        "frameworks": ["hermes", "wukong"],
        "ide_tools": ["codex", "claude_code"],
    })
    check("Register node", nid == "edge-001")

    # Test list
    nodes = cr.list_nodes()
    check("List nodes", len(nodes) == 1)

    # Test heartbeat
    ok = cr.heartbeat("edge-001", {"cpu_percent": 50, "memory_percent": 30})
    check("Heartbeat", ok is True)

    # Test online count
    check("Online count", cr.online_count() == 1)

    # Test get node
    node = cr.get_node("edge-001")
    check("Get node", node is not None and node["node_id"] == "edge-001")

    # Test capability assignment
    assign = cr.assign_task(["code"])
    check("Assign by capability", assign == "edge-001")

    assign_none = cr.assign_task(["gpu"])
    check("No match returns None", assign_none is None)

    # Test find by framework
    fw_nodes = cr.find_nodes_by_framework("hermes")
    check("Find by framework", "edge-001" in fw_nodes)

    # Test find by IDE
    ide_nodes = cr.find_nodes_by_ide("codex")
    check("Find by IDE", "edge-001" in ide_nodes)

    # Test deregister
    ok = cr.deregister("edge-001")
    check("Deregister", ok is True)
    check("Empty after deregister", cr.online_count() == 0)

    cr.shutdown()
    check("Shutdown clean", True)

    print(f"  TEST 3: {passed}/{passed+failed} passed")
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── TEST 4: CronScheduler ──────────────────────────
print("\n── TEST 4: CloudScheduler engine ──")

from cloud.engines.scheduler import CronExpression

# Test CronExpression
check("Wildcard matches always", CronExpression("* * * * *").matches())

# Test specific time (should not match now unless it happens to be that minute)
expr = CronExpression("0 4 * * *")  # 4:00 AM
import datetime
now = datetime.datetime.now()
if now.hour == 4 and now.minute == 0:
    check("Specific time match (coincidental)", expr.matches())
else:
    check("Specific time no-match", not expr.matches())

# Test */N (every 5 minutes)
expr_every5 = CronExpression("*/5 * * * *")
# Should match if current minute is divisible by 5
minute_match = now.minute % 5 == 0
check("Every 5 min expression", expr_every5.matches() == minute_match)

# Test comma-separated
expr_comma = CronExpression("0,30 * * * *")
match_0_30 = now.minute in (0, 30)
check("Comma-separated matches", expr_comma.matches() == match_0_30)

# Test range
expr_range = CronExpression("0-5 * * * *")
match_range = 0 <= now.minute <= 5
check("Range matches", expr_range.matches() == match_range)

# Test next_run
next_t = expr.next_run()
check("Next run is in the future", next_t > now)

# Test CloudScheduler
tmpdir = tempfile.mkdtemp(prefix="clawshell_test_")
try:
    from cloud.engines.scheduler import CloudScheduler

    scheduler = CloudScheduler(data_dir=tmpdir)

    # Track handler calls
    handler_calls = []
    def _scheduler_handler(task):
        handler_calls.append(task["task_id"])

    scheduler.set_handler("_scheduler_handler", _scheduler_handler)

    # Register a task
    tid = scheduler.register_task(
        "test-task", "* * * * *", "Test task", "_scheduler_handler"
    )
    check("Register task", tid == "test-task")

    # List tasks
    tasks = scheduler.list_tasks()
    check("List tasks", len(tasks) >= 1)

    # Run task now
    result = scheduler.run_task_now("test-task")
    check("Run task now", result is not None)
    check("Handler called", len(handler_calls) >= 1)
    check("Handler got correct ID", "test-task" in handler_calls)

    # Execution log
    log = scheduler.get_execution_log()
    check("Execution log populated", len(log) >= 1)

    scheduler.shutdown()
    check("Scheduler shutdown clean", True)

    print(f"  TEST 4: {passed}/{passed+failed} passed")
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── TEST 5: Cloud Config ───────────────────────────
print("\n── TEST 5: Cloud Config ──")

from cloud.config import CloudConfig, config

check("Config loaded", config is not None)
check("Config has host", isinstance(config.host, str))
check("Config has port", isinstance(config.port, int))
check("Config safe dict masks secrets", "****" in json.dumps(config.to_dict(safe=True)))

print(f"  TEST 5: {passed}/{passed+failed} passed")


# ── SUMMARY ────────────────────────────────────────
print()
print("=" * 50)
print(f"Phase 1 Verification: {passed} passed, {failed} failed")
if failed == 0:
    print("✅ PHASE 1: ALL TESTS PASSED")
else:
    print(f"❌ PHASE 1: {failed} TESTS FAILED")
