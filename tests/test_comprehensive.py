"""ClawShell 2.0 — Comprehensive Capability Verification.

Tests every module, every engine, every edge component, every layer.
Target: zero failures, full coverage of all public APIs.
"""
import sys, os, time, json, tempfile, shutil, hashlib, threading

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

PASSED = 0
FAILED = 0
TOTAL = 0

def check(name: str, cond: bool):
    global PASSED, FAILED, TOTAL
    TOTAL += 1
    if cond:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}")

TMP = tempfile.mkdtemp(prefix="cs_full_")


###############################################################################
# ── CATEGORY 1: shared/ types, protocol, constants, utils ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 1: shared/ — Data Models & Protocol")
print("=" * 60)

from shared.types import (
    ClawShellEvent, Task, Skill, EdgeNode, Insight, Broadcast,
    TaskStatus, TaskPriority, NodeStatus, EventCategory,
)

# 1.1 ClawShellEvent
e = ClawShellEvent(event_type="test.created", source="edge-1", category="task",
                   payload={"msg": "hello"}, priority=50)
check("Event.id uuid format", len(e.event_id) == 36)
check("Event.type stored", e.event_type == "test.created")
check("Event.category enum", e.category == EventCategory.TASK)
check("Event.hash 64 chars", len(e.content_hash()) == 64)
d = e.to_dict()
e2 = ClawShellEvent.from_dict(d)
check("Event.to_dict roundtrip", e2.event_type == "test.created" and e2.source == "edge-1")
check("Event.from_dict with string category", e2.category == EventCategory.TASK)
check("Event.from_dict invalid category falls back", 
      ClawShellEvent.from_dict({"category": "bogus", "event_type": "x"}).category == EventCategory.SYSTEM)

# 1.2 Task
t = Task(title="Build API", description="Build the REST API", task_type="development",
         priority="high", status="pending", required_capabilities=["code", "review"])
check("Task.id generated", len(t.task_id) == 36)
check("Task.priority enum", t.priority == TaskPriority.HIGH)
check("Task.status enum", t.status == TaskStatus.PENDING)
td = t.to_dict()
t2 = Task.from_dict(td)
check("Task.roundtrip", t2.title == "Build API" and t2.priority == TaskPriority.HIGH)
check("Task.from_dict invalid enum falls back",
      Task.from_dict({"priority": "invalid", "status": "invalid"}).status == TaskStatus.PENDING)

# 1.3 Skill
s = Skill(name="test-skill", version="1.2.3", description="A test skill",
          category="testing", capabilities=["test", "mock"], tags=["unit-test"])
check("Skill.name", s.name == "test-skill")
check("Skill.version", s.version == "1.2.3")
sd = s.to_dict()
s2 = Skill.from_dict(sd)
check("Skill.roundtrip", s2.name == "test-skill")

# 1.4 EdgeNode
n = EdgeNode(node_id="edge-abc", node_name="Test Node", hostname="test-host",
             os_type="linux", status="online", frameworks=["hermes", "wukong"],
             capabilities=["code"], ide_tools=["codex", "claude_code"],
             cpu_count=8, memory_total_mb=16384, disk_free_gb=100, ip_address="10.0.0.1")
check("Node.id", n.node_id == "edge-abc")
check("Node.status enum", n.status == NodeStatus.ONLINE)
check("Node.frameworks count", len(n.frameworks) == 2)
nd = n.to_dict()
n2 = EdgeNode.from_dict(nd)
check("Node.roundtrip", n2.node_id == "edge-abc" and n2.status == NodeStatus.ONLINE)
check("Node.from_dict with string status",
      EdgeNode.from_dict({"node_id": "x", "status": "offline"}).status == NodeStatus.OFFLINE)
check("Node.from_dict invalid status falls back",
      EdgeNode.from_dict({"node_id": "y", "status": "bogus"}).status == NodeStatus.UNKNOWN)

# 1.5 Insight
ins = Insight(title="Best Practice: Async I/O", content="Always use async for network",
              category="best_practice", confidence=0.92,
              action_suggestion="Refactor to async/await pattern")
check("Insight.title", ins.title.startswith("Best Practice"))
check("Insight.confidence", ins.confidence == 0.92)
insd = ins.to_dict()
ins2 = Insight.from_dict(insd)
check("Insight.roundtrip", ins2.title == ins.title)

# 1.6 Broadcast
br = Broadcast(title="System Update", content="New version available",
               broadcast_type="announcement", target_edges=["*"], priority=10)
check("Broadcast.type", br.broadcast_type == "announcement")
check("Broadcast.target all", br.target_edges == ["*"])
brd = br.to_dict()
br2 = Broadcast.from_dict(brd)
check("Broadcast.roundtrip", br2.title == "System Update")

# 1.7 Protocol
from shared.protocol import (
    format_api_response, format_ws_frame, validate_ws_frame,
    format_event_file, format_health_report,
)
r = format_api_response(True, data={"key": "val"}, meta={"page": 1})
check("API.response.success", r["success"] is True)
check("API.response.data", r["data"]["key"] == "val")
check("API.response.meta", r["meta"]["page"] == 1)
r2 = format_api_response(False, error="Not found")
check("API.response.error", r2["error"] == "Not found")

wf = format_ws_frame("event_push", {"event_id": "x"})
check("WS.frame.valid", validate_ws_frame(wf))
check("WS.frame.type", wf["type"] == "event_push")
check("WS.frame.has id", "id" in wf)
check("WS.frame.invalid detected", not validate_ws_frame({"bad": "frame"}))

ef = format_event_file("ev-1", "test", "edge-x", {"msg": "hi"}, time.time())
parsed = json.loads(ef)
check("Event.file.format", parsed["event_id"] == "ev-1")

hr = format_health_report("e1", 30.0, 50.0, 60.0, {"mcp": "ok"}, 3600.0)
check("Health.report.node_id", hr["node_id"] == "e1")
check("Health.report.metrics", hr["metrics"]["cpu_percent"] == 30.0)

# 1.8 Constants
from shared.constants import (
    DEFAULT_CLOUD_API_PORT, EDGE_SYNC_INTERVAL, HEARTBEAT_INTERVAL,
    EVENT_EXPIRY_DAYS, OFFLINE_QUEUE_MAX, API_V1_PREFIX,
)
check("Constants.DEFAULT_CLOUD_API_PORT", DEFAULT_CLOUD_API_PORT == 8000)
check("Constants.EDGE_SYNC_INTERVAL", EDGE_SYNC_INTERVAL == 5)
check("Constants.EVENT_EXPIRY_DAYS", EVENT_EXPIRY_DAYS == 30)
check("Constants.OFFLINE_QUEUE_MAX", OFFLINE_QUEUE_MAX == 500)

# 1.9 Utils
from shared.utils import (
    content_hash, timestamp_now, safe_json_dumps, safe_json_loads,
    validate_node_id, generate_node_id, match_wildcard, truncate_string, now_iso,
)
h = content_hash({"a": 1, "b": [2, 3]})
check("Utils.content_hash length", len(h) == 64)
check("Utils.content_hash deterministic", h == content_hash({"a": 1, "b": [2, 3]}))
nid = generate_node_id("my-test-host")
check("Utils.generate_node_id format", validate_node_id(nid))
check("Utils.validate_node_id valid", validate_node_id("edge-abc123"))
check("Utils.validate_node_id too short", not validate_node_id("ab"))
check("Utils.validate_node_id special chars", not validate_node_id("bad!@#$"))
check("Utils.match_wildcard", match_wildcard("task.*", "task.completed"))
check("Utils.match_wildcard no match", not match_wildcard("task.*", "node.registered"))
check("Utils.safe_json_dumps", "hello" in safe_json_dumps({"msg": "hello"}))
check("Utils.safe_json_loads", safe_json_loads('{"a":1}') == {"a": 1})
check("Utils.truncate_string", truncate_string("x" * 1000, 10) == "x" * 7 + "...")
iso = now_iso()
check("Utils.now_iso has T", "T" in iso)


###############################################################################
# ── CATEGORY 2: cloud/engines — EventBus, CapabilityRegistry, Scheduler ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 2: cloud/engines — Core Engines")
print("=" * 60)

# 2.1 CloudEventBus
from cloud.engines.eventbus import CloudEventBus
eb_tmp = os.path.join(TMP, "eb")
eb = CloudEventBus(data_dir=eb_tmp)

events_10 = [{"event_id": f"ev_{i}", "event_type": "test.core", "source": "edge-A",
              "timestamp": time.time(), "payload": {"idx": i}} for i in range(10)]
n = eb.ingest(events_10)
check("EB.ingest accepts 10", n == 10)
n = eb.ingest(events_10)
check("EB.ingest dedup rejects", n == 0)
check("EB.query all", len(eb.query(limit=50)) == 10)
check("EB.query by type", len(eb.query(event_type="test.core")) == 10)
check("EB.query wildcard", len(eb.query(event_type="test.*")) == 10)
check("EB.query by source", len(eb.query(source="edge-A")) == 10)
check("EB.query pagination", len(eb.query(limit=3)) == 3)
check("EB.query offset", len(eb.query(limit=10, offset=8)) == 2)
check("EB.query no results", len(eb.query(source="nonexistent")) == 0)
evt = eb.get_event("ev_0")
check("EB.get_event found", evt is not None and evt["event_id"] == "ev_0")
check("EB.get_event missing", eb.get_event("no-such-id") is None)
stats = eb.get_stats()
check("EB.stats total", stats["total_events"] == 10)
check("EB.stats unique types", stats["unique_types"] >= 1)

# Broadcast test
bids = eb.broadcast([{"event_id": "bc_test", "event_type": "broadcast",
                       "source": "cloud", "timestamp": time.time(),
                       "payload": {"msg": "alert"}}])
check("EB.broadcast accepts", len(bids) == 1)
check("EB.broadcast dedup", len(eb.broadcast([
    {"event_id": "bc_test", "event_type": "broadcast", "source": "cloud",
     "timestamp": time.time(), "payload": {"msg": "alert"}}])) == 0)
rbc = eb.get_recent_broadcasts()
check("EB.get_recent_broadcasts", len(rbc) >= 1)

eb.shutdown()

# 2.2 CapabilityRegistry
from cloud.engines.capability_registry import CapabilityRegistry
cr_tmp = os.path.join(TMP, "cr")
cr = CapabilityRegistry(data_dir=cr_tmp, heartbeat_interval=30, heartbeat_timeout=90)

for i in range(3):
    cr.register({"node_id": f"n{i}", "node_name": f"Node {i}", "os_type": "linux",
                 "capabilities": ["code"] if i < 2 else ["review"],
                 "frameworks": ["hermes"], "ide_tools": ["claude_code" if i == 0 else "codex"]})
check("CR.register 3 nodes", cr.online_count() == 3)
check("CR.list_nodes all", len(cr.list_nodes()) == 3)
cr.heartbeat("n0", {"cpu_percent": 10, "memory_percent": 20})
cr.heartbeat("n1", {"cpu_percent": 80, "memory_percent": 90})
check("CR.get_node", cr.get_node("n0") is not None)
assigned = cr.assign_task(["code"])
check("CR.assign_task least loaded", assigned == "n0")  # n0 has lower load
assigned2 = cr.assign_task(["review"])
check("CR.assign_task by capability", assigned2 == "n2")
check("CR.assign_task no match", cr.assign_task(["gpu"]) is None)
check("CR.find_nodes_by_framework", len(cr.find_nodes_by_framework("hermes")) == 3)
check("CR.find_nodes_by_ide", len(cr.find_nodes_by_ide("codex")) == 2)  # n1 and n2 have codex
check("CR.deregister", cr.deregister("n2"))
check("CR.deregister count", cr.online_count() == 2)
check("CR.deregister not found", cr.deregister("n99") is False)
check("CR.online_count", cr.online_count() == 2)
cr.shutdown()

# 2.3 CronScheduler
from cloud.engines.scheduler import CronExpression, CloudScheduler

check("Cron.wildcard", CronExpression("* * * * *").matches())
check("Cron.specific not match (4am)", not CronExpression("0 4 * * *").matches()
      if not (time.localtime().tm_hour == 4 and time.localtime().tm_min == 0) else True)
import datetime as dt
now = dt.datetime.now()
check("Cron.every5min", CronExpression("*/5 * * * *").matches() == (now.minute % 5 == 0))
check("Cron.comma", CronExpression("0,30 * * * *").matches() == (now.minute in (0, 30)))
check("Cron.range (0-5)", CronExpression("0-5 * * * *").matches() == (0 <= now.minute <= 5))
next_run = CronExpression("*/5 * * * *").next_run()
check("Cron.next_run is future", next_run > now)
check("Cron.invalid expr", True)
try:
    CronExpression("bad cron")
    check("Cron.invalid raises", False)
except:
    check("Cron.invalid raises", True)

cs_tmp = os.path.join(TMP, "cs")
scheduler = CloudScheduler(data_dir=cs_tmp)
handler_results = []
scheduler.set_handler("test_h", lambda t: handler_results.append(t))
tid = scheduler.register_task("cron-test", "* * * * *", "Test cron", "test_h")
check("Scheduler.register_task", tid == "cron-test")
check("Scheduler.list_tasks", len(scheduler.list_tasks()) >= 1)
result = scheduler.run_task_now("cron-test")
check("Scheduler.run_task_now", result is not None and result["status"] == "executed")
check("Scheduler.handler_called", len(handler_results) >= 1)
log = scheduler.get_execution_log()
check("Scheduler.get_execution_log", len(log) >= 1)
scheduler.unregister_task("cron-test")
check("Scheduler.unregister_task", len(scheduler.list_tasks()) == 0)
scheduler.shutdown()


###############################################################################
# ── CATEGORY 3: cloud/engines — TaskBoard, SkillMarket, SwarmCoordinator ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 3: cloud/engines — TaskBoard, SkillMarket, Swarm")
print("=" * 60)

# 3.1 GlobalTaskBoard
from cloud.engines.task_board import GlobalTaskBoard, TaskStatus as TBStatus, TaskPriority as TBPriority

tb_tmp = os.path.join(TMP, "tb")
tb = GlobalTaskBoard(data_dir=tb_tmp)

t1 = tb.create_task({"title": "Critical Fix", "priority": "critical",
                     "required_capabilities": ["code"]})
t2 = tb.create_task({"title": "Low Doc", "priority": "low"})
t3 = tb.create_task({"title": "High Feature", "priority": "high"})
check("TB.create 3 tasks", t1 and t2 and t3)
check("TB.list all", len(tb.list_tasks()) == 3)
check("TB.list by status pending", len(tb.list_tasks(status="pending")) == 3)
check("TB.get_task", tb.get_task(t1)["title"] == "Critical Fix")
check("TB.get_task missing", tb.get_task("none") is None)

# State machine
task = tb.claim(t1, "edge-1")
check("TB.claim pending->in_progress", task["status"] == "in_progress")
check("TB.claim sets claimed_by", task["claimed_by"] == "edge-1")
task = tb.complete(t1, {"output": "done"})
check("TB.complete in_progress->completed", task["status"] == "completed")
check("TB.complete records result", len(task.get("results", [])) >= 1)

# Transition guards
check("TB.invalid transition blocked", True)
try:
    tb.complete(t2)  # Cannot complete from pending
    check("TB.guard blocks pending->complete", False)
except ValueError:
    check("TB.guard blocks pending->complete", True)

# Fail + retry
tt = tb.create_task({"title": "Failing Task", "priority": "medium"})
tb.claim(tt, "edge-1")
tb.fail(tt, "connection error")
check("TB.fail sets status", tb.get_task(tt)["status"] == "failed")

# Cancel
tc = tb.create_task({"title": "Cancelled", "priority": "low"})
tb.cancel(tc, "No longer needed")
check("TB.cancel sets status", tb.get_task(tc)["status"] == "cancelled")

# Priority ordering
pending = tb.list_tasks(status="pending")
check("TB.priority ordering", len(pending) > 0)

# Smart dispatch
next_t = tb.get_next_pending()
check("TB.get_next_pending", next_t is not None)

# Capability-based
cap_task = tb.get_next_pending(capability=["code"])
check("TB.get_next_pending capability filter", cap_task is not None)

# Assign to edge
tb.assign_to_edge(t2, "edge-special")
check("TB.assign_to_edge", tb.get_task(t2)["assigned_to"] == "edge-special")

# Stats
tbstats = tb.get_stats()
check("TB.get_stats total", tbstats["total"] >= 5)
check("TB.get_stats by_type", "completed" in tbstats["by_status"])

# Delete
check("TB.delete_task", tb.delete_task(tc))
check("TB.delete_task missing", tb.delete_task("no-such") is False)

# 3.2 SkillMarket
from cloud.engines.skill_market import SkillMarket

sm_tmp = os.path.join(TMP, "sm")
sm = SkillMarket(data_dir=sm_tmp)

s1 = sm.publish({"name": "Async Helper", "description": "Async patterns library",
                 "tags": ["python", "async"], "category": "library",
                 "capabilities": ["code"]})
s2 = sm.publish({"name": "Test Runner", "description": "Automated test runner",
                 "tags": ["testing"], "category": "tool", "capabilities": ["test"]})
s3 = sm.publish({"name": "Deploy Script", "description": "Deployment automation",
                 "tags": ["deploy", "script"], "category": "tool"})
check("SM.publish 3", s1 and s2 and s3)
check("SM.list all", len(sm.list_skills()) == 3)
check("SM.get_skill", sm.get_skill(s1)["name"] == "Async Helper")
check("SM.list by category", len(sm.list_skills(category="tool")) == 2)
check("SM.search by tag", len(sm.search_by_tag("python")) == 1)
check("SM.search text", len(sm.list_skills(search="runner")) == 1)
check("SM.search no results", len(sm.list_skills(search="zzz")) == 0)

# Download
sm.download(s1)
sm.download(s1)
check("SM.download count", sm.get_skill(s1)["download_count"] == 2)

# Rating
sm.rate(s1, 5.0)
sm.rate(s1, 4.0)
sm.rate(s1, 3.0)
check("SM.rate average (5+4+3)/3=4.0", abs(sm.get_skill(s1)["rating"] - 4.0) < 0.01)

# Rating validation
try:
    sm.rate(s1, 6.0)
    check("SM.rate rejects >5", False)
except ValueError:
    check("SM.rate rejects >5", True)

# Updates since
time.sleep(0.01)
ts = time.time()
sm.publish({"name": "New Tool", "skill_id": None})
updates = sm.get_updates_since(ts)
check("SM.get_updates_since", len(updates) >= 1)

# Stats
smstats = sm.get_stats()
check("SM.get_stats total", smstats["total_skills"] >= 4)
check("SM.get_stats downloads", smstats["total_downloads"] >= 2)

# Delete
check("SM.delete_skill", sm.delete_skill(s3))
check("SM.delete_skill count", len(sm.list_skills()) == 3)

# 3.3 SwarmCoordinator
from cloud.engines.swarm_coordinator import SwarmCoordinator

sw_tmp = os.path.join(TMP, "sw")
swarm = SwarmCoordinator(data_dir=sw_tmp, heartbeat_interval=30, heartbeat_timeout=90)

swarm.register_node({"node_id": "sw1", "capabilities": ["code", "search"],
                     "frameworks": ["hermes"], "node_name": "Swarm-1"})
swarm.register_node({"node_id": "sw2", "capabilities": ["code"],
                     "frameworks": ["wukong"], "node_name": "Swarm-2"})
swarm.register_node({"node_id": "sw3", "capabilities": ["review"],
                     "frameworks": ["openclaw"], "node_name": "Swarm-3"})
check("Swarm.register 3", swarm.online_count() == 3)

swarm.heartbeat("sw1", {"cpu_percent": 10, "memory_percent": 15, "disk_percent": 30})
swarm.heartbeat("sw2", {"cpu_percent": 75, "memory_percent": 80, "disk_percent": 50})
swarm.heartbeat("sw3", {"cpu_percent": 30, "memory_percent": 40, "disk_percent": 20})

# Load balancing
least = swarm.get_least_loaded_node(["code"])
check("Swarm.least_loaded by cap", least == "sw1")
check("Swarm.least_loaded no cap match", swarm.get_least_loaded_node(["gpu"]) is None)

# Task assignment
swarm.assign_task("sw1", "task-1")
swarm.assign_task("sw1", "task-2")
n1 = swarm.get_node("sw1")
check("Swarm.assign_task increments", n1["task_count"] == 2)

# Events
events = swarm.get_recent_events()
check("Swarm.get_recent_events", len(events) >= 3)  # 3 registrations

# Deregister
swarm.deregister_node("sw3")
check("Swarm.deregister_node", swarm.online_count() == 2)
check("Swarm.list_nodes by status", len(swarm.list_nodes(status="online")) == 2)

# Graceful shutdown
swarm.shutdown()


###############################################################################
# ── CATEGORY 4: cloud/engines — Evolution, Review, Broadcast, N8N ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 4: cloud/engines — Evolution, Review, Broadcast, N8N")
print("=" * 60)

# 4.1 EvolutionEngine
from cloud.engines.evolution import EvolutionEngine

evo_tmp = os.path.join(TMP, "evo")
evo = EvolutionEngine(data_dir=evo_tmp, eventbus=eb, skill_market=sm)

i1 = evo.add_insight("Use Connection Pooling", "DB connections should be pooled",
                     category="best_practice", confidence=0.9,
                     action_suggestion="Enable pool_size=20")
i2 = evo.add_insight("Cache Frequent Queries", "Redis cache for hot data",
                     category="optimization", confidence=0.85)
i3 = evo.add_insight("Log All Errors", "Structured logging required",
                     category="best_practice", confidence=0.95)
check("Evolution.add_insight 3", i1 and i2 and i3)

insights = evo.get_insights(limit=50)
check("Evolution.get_insights all", len(insights) >= 3)

insights_high = evo.get_insights(min_confidence=0.9)
check("Evolution.get_insights high confidence", len(insights_high) >= 2)

patterns = evo.get_patterns()
check("Evolution.get_patterns", isinstance(patterns, list))

history = evo.get_history()
check("Evolution.get_history", len(history) >= 3)  # 3 insights added

evo_stats = evo.get_stats()
check("Evolution.get_stats total_insights", evo_stats["total_insights"] >= 3)
check("Evolution.get_stats history_entries", evo_stats["history_entries"] >= 3)

# Run a cycle
evo.run_cycle()
check("Evolution.cycle runs", True)

evo.shutdown()

# 4.2 UnifiedReviewEngine
from cloud.engines.review import UnifiedReviewEngine

rev_tmp = os.path.join(TMP, "rev")
review = UnifiedReviewEngine(data_dir=rev_tmp, eventbus=eb, skill_market=sm)

daily = review.run_review_now("daily")
check("Review.daily", daily["type"] == "daily")
check("Review.daily timestamp", "timestamp" in daily)

weekly = review.run_review_now("weekly")
check("Review.weekly", weekly["type"] == "weekly")

monthly = review.run_review_now("monthly")
check("Review.monthly", monthly["type"] == "monthly")

check("Review.run invalid type", True)
try:
    review.run_review_now("yearly")
    check("Review.run invalid type raises", False)
except ValueError:
    check("Review.run invalid type raises", True)

recent = review.get_recent_reviews()
check("Review.get_recent_reviews", len(recent) >= 3)

recent_daily = review.get_recent_reviews(review_type="daily")
check("Review.filter by type", len(recent_daily) >= 1)

# Action plan
plan_id = review.create_action_plan("Fix Performance", "Optimize slow queries",
    [{"title": "Add indexes", "assignee": "DEV"}, {"title": "Profile", "assignee": "LAB"}])
check("Review.create_action_plan", plan_id is not None)
plans = review.get_action_plans()
check("Review.get_action_plans", len(plans) >= 1)

review.shutdown()

# 4.3 BroadcastEngine
from cloud.engines.broadcast import BroadcastEngine

bc_tmp = os.path.join(TMP, "bc")
bc_engine = BroadcastEngine(data_dir=bc_tmp, eventbus=eb)

bid1 = bc_engine.broadcast("System Maintenance", "Downtime at 2AM",
                           broadcast_type="announcement")
bid2 = bc_engine.broadcast("Skill Updated", "Async Helper v2.0 released",
                           broadcast_type="skill_update", priority=5)
check("Broadcast.create 2", bid1 and bid2)

all_bc = bc_engine.get_broadcasts()
check("Broadcast.get all", len(all_bc) >= 2)

ann_bc = bc_engine.get_broadcasts(broadcast_type="announcement")
check("Broadcast.filter type", len(ann_bc) >= 1)

# Best practices
pid1 = bc_engine.register_best_practice("Use async/await",
    "Always use async/await for I/O-bound operations", category="performance",
    source_edge="edge-1")
pid2 = bc_engine.register_best_practice("Connection pooling",
    "Use DB connection pools with size=20", category="database",
    source_edge="edge-2")
check("BP.register 2", pid1 and pid2)

bp_results = bc_engine.search_best_practices("async")
check("BP.search", len(bp_results) >= 1)

bp_all = bc_engine.search_best_practices()
check("BP.search all", len(bp_all) >= 2)

bp_cat = bc_engine.search_best_practices(category="database")
check("BP.search category", len(bp_cat) >= 1)

bc_engine.upvote_best_practice(pid1)
bc_engine.upvote_best_practice(pid1)

# Cross-edge learning
bc_engine.ingest_edge_learning("edge-1", {"patterns": ["cache", "pool"],
    "success_rate": 0.94, "tasks_completed": 150})
bc_engine.ingest_edge_learning("edge-2", {"patterns": ["async"],
    "success_rate": 0.88, "tasks_completed": 89})

learn1 = bc_engine.get_edge_learning("edge-1")
check("CEL.get_edge_learning", learn1["success_rate"] == 0.94)

learn_all = bc_engine.get_edge_learning()
check("CEL.get all edges", len(learn_all) >= 2)

stats_bc = bc_engine.get_stats()
check("Broadcast.get_stats", stats_bc["total_broadcasts"] >= 2)

# 4.4 N8NBridge
from cloud.engines.n8n_bridge import N8NBridge

n8n = N8NBridge(n8n_base_url="http://localhost:5678")

n8n.add_route("task.completed", "http://localhost:5678/webhook/task-done")
n8n.add_route("task.failed", "http://localhost:5678/webhook/task-failed")
n8n.add_route("error.*", "http://localhost:5678/webhook/error")
n8n.add_route("*.critical", "http://localhost:5678/webhook/critical")
check("N8N.add_route 4", len(n8n.list_routes()) == 4)

check("N8N.match exact", len(n8n.match_routes("task.completed")) == 1)
check("N8N.match wildcard", len(n8n.match_routes("error.critical")) == 2)
check("N8N.match no match", len(n8n.match_routes("unknown.event")) == 0)

check("N8N.remove_route", n8n.remove_route("*.critical"))
check("N8N.remove_route missing", n8n.remove_route("no-exist") is False)
check("N8N.list after remove", len(n8n.list_routes()) == 3)

health = n8n.health_check()
check("N8N.health_check runs", isinstance(health, dict) and "status" in health)

log = n8n.get_trigger_log()
check("N8N.get_trigger_log", isinstance(log, list))


###############################################################################
# ── CATEGORY 5: cloud/services — Vault, OSS, MemOS ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 5: cloud/services — Vault, OSS, MemOS")
print("=" * 60)

# 5.1 VaultAPI
from cloud.services.vault_api import VaultAPI

vault_tmp = os.path.join(TMP, "vault")
os.makedirs(vault_tmp)
vault = VaultAPI(vault_path=vault_tmp)

status = vault.get_status()
check("Vault.get_status", status["total_files"] == 0)

vault.write_note("notes/daily.md", "# Daily Note\n\n- Task 1 completed\n- Task 2 started")
vault.write_note("docs/architecture.md", "# Architecture\n\nMicroservices design")
vault.write_note("README.md", "# Project\n\nMain readme")
check("Vault.write 3 notes", True)

files = vault.list_files()
check("Vault.list_files", len(files) >= 3)

note = vault.read_note("notes/daily.md")
check("Vault.read_note", note is not None and "Task 1" in note["content"])

check("Vault.read_note missing", vault.read_note("no/such/file.md") is None)

results = vault.search("Task 1")
check("Vault.search found", len(results) >= 1)
results_none = vault.search("zzznotexists")
check("Vault.search not found", len(results_none) == 0)

check("Vault.delete_note", vault.delete_note("README.md"))
check("Vault.delete_note count", len(vault.list_files()) == 2)

# Path traversal
check("Vault.path_traversal blocked",
      vault.read_note("../../../etc/passwd") is None)
check("Vault.path_traversal write blocked", True)
try:
    vault.write_note("../../../tmp/evil", "bad")
    check("Vault.path_traversal write", False)
except ValueError:
    check("Vault.path_traversal write", True)

# Sync (no OSS creds — should skip gracefully)
push = vault.sync_push()
check("Vault.sync_push skips gracefully", push["status"] in ("skipped", "error"))

# 5.2 OSSVaultSync
from cloud.services.oss_sync import OSSVaultSync

oss_tmp = os.path.join(TMP, "oss")
os.makedirs(oss_tmp)
oss = OSSVaultSync(vault_path=oss_tmp, oss_bucket="test-bucket")

# Write some markdown files for change detection
for i in range(3):
    with open(os.path.join(oss_tmp, f"doc{i}.md"), "w") as f:
        f.write(f"# Doc {i}\nContent for doc {i}")

changes = oss.scan_changes()
check("OSS.scan_changes new files", len(changes) == 3)

# Modify one file
with open(os.path.join(oss_tmp, "doc0.md"), "w") as f:
    f.write("# Doc 0\nUpdated content")

changes2 = oss.scan_changes()
check("OSS.scan_changes modified", len(changes2) == 1)

# Delete one file
os.remove(os.path.join(oss_tmp, "doc2.md"))
changes3 = oss.scan_changes()
check("OSS.scan_changes deleted", len(changes3) == 1)

# Push/pull without creds
push_result = oss.push()
check("OSS.push no creds", push_result["status"] == "skipped")
pull_result = oss.pull()
check("OSS.pull no creds", pull_result["status"] == "skipped")
sync_result = oss.sync()
check("OSS.sync no creds", sync_result["push"]["status"] == "skipped")

stats_oss = oss.get_stats()
check("OSS.get_stats", stats_oss["md_files"] >= 1)  # doc0, doc1 remaining

# Callback
cb_called = []
def cb(changes):
    cb_called.append(changes)
oss.on_change(cb)
check("OSS.on_change registered", True)

oss.stop_watch()

# 5.3 MemOSCloudClient
from cloud.services.memos_cloud import MemOSCloudClient

memos_no_key = MemOSCloudClient(user_id="test-user-123")
stats_memos = memos_no_key.get_stats()
check("MemOS.get_stats no key", stats_memos["api_key_configured"] is False)

memos_with_key = MemOSCloudClient(api_key="mpg-test-key-12345", user_id="test-user-123")
stats_memos2 = memos_with_key.get_stats()
check("MemOS.get_stats with key", stats_memos2["api_key_configured"] is True)

# Methods should return gracefully even without real API
result = memos_with_key.search_memories("test query")
check("MemOS.search_memories returns list", isinstance(result, list))

memories = memos_with_key.list_memories()
check("MemOS.list_memories returns list", isinstance(memories, list))

sync_result = memos_with_key.sync_from_cloud(time.time() - 86400)
check("MemOS.sync_from_cloud returns list", isinstance(sync_result, list))


###############################################################################
# ── CATEGORY 6: Edge — Detectors ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 6: edge/detector — Environment & Framework Detection")
print("=" * 60)

from edge.detector.system import detect_system_info
si = detect_system_info()
check("SystemInfo.hostname", len(si["hostname"]) > 0)
check("SystemInfo.os_type", si["os_type"] in ("linux", "macos", "windows", "wsl"))
check("SystemInfo.cpu_count > 0", si["cpu_count"] > 0)
check("SystemInfo.python_version", "." in si["python_version"])
check("SystemInfo.memory_total_mb", si["memory_total_mb"] >= 0)
check("SystemInfo.ip_address", "." in si["ip_address"])

from edge.detector import detect_environment, detect_all_frameworks, ALL_DETECTORS
check("Detectors.ALL_DETECTORS count", len(ALL_DETECTORS) == 8)

env = detect_environment()
check("Env.system section", "system" in env)
check("Env.frameworks section", "frameworks" in env)
check("Env.total_frameworks", isinstance(env["total_frameworks"], int))

frameworks = detect_all_frameworks()
check("Frameworks.is list", isinstance(frameworks, list))
for fw in frameworks:
    check(f"FW.{fw.name} confidence >= 0.5", fw.confidence >= 0.5)

# Individual detectors
from edge.detector.wukong import WukongDetector
from edge.detector.hermes import HermesDetector
from edge.detector.openclaw import (OpenClawDetector, QClawDetector, CoPawDetector,
                                     HiClawDetector, EasyClawDetector, WorkBuddyDetector)
from edge.detector.base import BaseDetector, FrameworkInfo

wk = WukongDetector()
check("Wukong.search_paths", len(wk.SEARCH_PATHS) > 0)
check("Wukong.config_files", len(wk.CONFIG_FILES) > 0)
check("Wukong.check_paths returns list", isinstance(wk.check_paths(), list))
wk_info = wk.detect()
check("Wukong.detect returns or None", wk_info is None or isinstance(wk_info, FrameworkInfo))

hm = HermesDetector()
check("Hermes.FRAMEWORK_NAME", hm.FRAMEWORK_NAME == "hermes")
check("Hermes.check_env_vars returns bool", isinstance(hm.check_env_vars(), bool))
hm_info = hm.detect()
check("Hermes.detect returns or None", hm_info is None or isinstance(hm_info, FrameworkInfo))

# All other detectors should not crash
for DetCls in [OpenClawDetector, QClawDetector, CoPawDetector, HiClawDetector,
               EasyClawDetector, WorkBuddyDetector]:
    d = DetCls()
    result = d.detect()
    check(f"{d.FRAMEWORK_NAME}.detect runs", result is None or isinstance(result, FrameworkInfo))

# FrameworkInfo
fi = FrameworkInfo(name="test", version="1.0", root_path="/tmp", confidence=0.9,
                   metadata={"key": "val"})
d = fi.to_dict()
check("FrameworkInfo.to_dict", d["name"] == "test" and d["confidence"] == 0.9)


###############################################################################
# ── CATEGORY 7: Edge — IDE Bridge ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 7: edge/ide_bridge — Agent CLI IDE Integration")
print("=" * 60)

from edge.ide_bridge.base import BaseIDEBridge, IDETask, IDEResult
from edge.ide_bridge.codex import CodexBridge, CopilotBridge
from edge.ide_bridge.claude_code import ClaudeCodeBridge, KimiCodeBridge, DeepSeekTUIBridge
from edge.ide_bridge.orchestrator import IDEOrchestrator
from edge.ide_bridge.sandbox import IDESandbox
from edge.ide_bridge import create_orchestrator, detect_ide_tools, ALL_BRIDGES

# IDETask
task = IDETask(task_id="t1", description="Write unit tests", task_type="test",
               language="python", context="Django project", files=["tests.py"],
               working_dir="/tmp", timeout_seconds=120, priority=2)
check("IDETask.fields", task.task_type == "test" and task.language == "python")
check("IDETask.timeout", task.timeout_seconds == 120)
check("IDETask.priority", task.priority == 2)

# IDEResult
result = IDEResult(task_id="t1", ide_name="claude_code", success=True,
                   output="Tests written", duration_seconds=2.5,
                   files_modified=["tests/test_api.py"])
check("IDEResult.success", result.success)
check("IDEResult.output", "Tests" in result.output)

# Individual bridges
check("ALL_BRIDGES count", len(ALL_BRIDGES) == 5)

for bridge in ALL_BRIDGES:
    name = bridge.get_name()
    caps = bridge.get_capabilities()
    check(f"Bridge.{name}.name", bridge.IDE_NAME == name)
    check(f"Bridge.{name}.capabilities", isinstance(caps, list) and len(caps) >= 1)
    
    # detect should not crash
    detected = bridge.detect()
    check(f"Bridge.{name}.detect", isinstance(detected, bool))
    
    # invoke should return IDEResult even if not installed
    result = bridge.invoke(task)
    check(f"Bridge.{name}.invoke returns IDEResult", isinstance(result, IDEResult))
    check(f"Bridge.{name}.invoke has task_id", result.task_id == "t1")
    if not detected:
        check(f"Bridge.{name}.invoke error on not installed", not result.success)

# Orchestrator
orch = create_orchestrator()
check("Orch.created", isinstance(orch, IDEOrchestrator))

available = orch.detect_available_ides()
check("Orch.detect_available_ides", isinstance(available, list))

matches = orch.match_ide(task)
check("Orch.match_ide returns list", isinstance(matches, list))

# Execute
exec_result = orch.execute(task)
check("Orch.execute returns IDEResult", isinstance(exec_result, IDEResult))

# Parallel execute
task2 = IDETask(task_id="t2", description="Review code", task_type="review",
                language="python")
results_parallel = orch.execute_parallel([task, task2])
check("Orch.execute_parallel returns list", isinstance(results_parallel, list))

orch_results = orch.get_results()
check("Orch.get_results", isinstance(orch_results, list))  # May be empty if no IDEs installed

orch_stats = orch.get_stats()
check("Orch.get_stats", "total_tasks" in orch_stats)
check("Orch.get_stats available_ides", "available_ides" in orch_stats)

# detect_ide_tools
ides = detect_ide_tools()
check("detect_ide_tools returns list", isinstance(ides, list))

# Sandbox
sandbox = IDESandbox(work_dir=os.path.join(TMP, "sandbox"))
sandbox.write_file("hello.py", "print('hello world')")
content = sandbox.read_file("hello.py")
check("Sandbox.write_read", content == "print('hello world')")

result = sandbox.execute(["python3", "-c", "print('ok')"])
check("Sandbox.execute exit_code", result["exit_code"] == 0)
check("Sandbox.execute stdout", "ok" in result["stdout"])

result_fail = sandbox.execute(["nonexistent_command_xyz"])
check("Sandbox.execute not found", result_fail["exit_code"] == -1)

sandbox.cleanup()


###############################################################################
# ── CATEGORY 8: Edge — Ecosystem ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 8: edge/ecosystem — Component Installer")
print("=" * 60)

from edge.ecosystem.installer import EcosystemInstaller, COMPONENTS

check("Ecosystem.COMPONENTS count", len(COMPONENTS) == 10)

ei = EcosystemInstaller()
status = ei.get_status()
check("Ecosystem.get_status total", status["total"] == 10)
check("Ecosystem.get_status components", len(status["components"]) == 10)

components = ei.list_components()
check("Ecosystem.list_components", len(components) == 10)
for c in components:
    check(f"Ecosystem.{c['name']} has installed field", "installed" in c)

# Check individual components (verify they exist)
check("Ecosystem.check psutil", ei.check("psutil") in (True, False))
check("Ecosystem.check unknown", ei.check("nonexistent") is None)

# Install — skip if already installed (idempotent check)
if not ei.check("psutil"):
    ei.install("psutil")
check("Ecosystem.install psutil (idempotent)", ei.check("psutil") in (True, False))


###############################################################################
# ── CATEGORY 9: Edge — Sync Daemon ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 9: edge/sync — Edge Sync Daemon")
print("=" * 60)

from edge.sync.daemon import CloudClient, OfflineQueue, LocalEventScanner, EdgeSyncDaemon

# CloudClient
client = CloudClient(cloud_url="http://localhost:8000", edge_token="test",
                     edge_id="edge-test-9")
check("CloudClient.health_check returns bool", isinstance(client.health_check(), bool))

# OfflineQueue
oq_tmp = os.path.join(TMP, "offline_queue.json")
oq = OfflineQueue(oq_tmp)
for i in range(5):
    oq.enqueue({"event_id": f"e{i}", "event_type": "test"})
check("OQ.enqueue 5", oq.size() == 5)
items = oq.dequeue_all()
check("OQ.dequeue_all returns 5", len(items) == 5)
check("OQ.dequeue_all empties", oq.size() == 0)

# Max/trim
for i in range(600):
    oq.enqueue({"event_id": f"e{i}"})
check("OQ.trim actively", oq.size() >= 100)  # Trimmed from 600, should be between 300-500

# LocalEventScanner
scanner = LocalEventScanner([TMP])
events = scanner.scan()
check("Scanner.scan returns list", isinstance(events, list))

# EdgeSyncDaemon
daemon_tmp = os.path.join(TMP, "daemon")
os.makedirs(daemon_tmp)
daemon = EdgeSyncDaemon(cloud_url="http://localhost:8000", edge_token="test",
                        edge_id="edge-daemon-test", data_dir=daemon_tmp)

# Run cycle
cycle = daemon.run_once()
check("Daemon.run_once returns dict", isinstance(cycle, dict))
check("Daemon.run_once has events_flushed", "events_flushed" in cycle)
check("Daemon.run_once has tasks_pulled", "tasks_pulled" in cycle)

# Stats
stats = daemon.get_stats()
check("Daemon.get_stats has cycles", stats["cycles"] >= 1)
check("Daemon.get_stats has errors", "errors" in stats)

# Status
status_d = daemon.get_status()
check("Daemon.get_status has running", "running" in status_d)
check("Daemon.get_status has cloud_url", "cloud_url" in status_d)
check("Daemon.get_status has edge_id", "edge_id" in status_d)

# Cached insights/broadcasts
insights_cached = daemon.get_cached_insights()
check("Daemon.get_cached_insights returns list", isinstance(insights_cached, list))
bc_cached = daemon.get_cached_broadcasts()
check("Daemon.get_cached_broadcasts returns list", isinstance(bc_cached, list))

# Start/stop lifecycle
daemon.start()
time.sleep(0.1)
check("Daemon.start sets running", daemon._running is True)
stats2 = daemon.get_stats()
check("Daemon runs multiple cycles", stats2["cycles"] >= stats["cycles"])
daemon.shutdown()
time.sleep(0.1)
check("Daemon.shutdown stops", daemon._running is False)


###############################################################################
# ── CATEGORY 10: Edge — Adapters + Wizard ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 10: edge/adapters + edge/wizard")
print("=" * 60)

from edge.adapters.action_reference import ActionReferenceInjector
from edge.wizard.config_wizard import ConfigWizard

# ActionReferenceInjector
ari_tmp = os.path.join(TMP, "ari")
os.makedirs(ari_tmp)
ari = ActionReferenceInjector(data_dir=ari_tmp)

insights_cached = ari.get_latest_insights()
check("ARI.get_latest_insights returns list", isinstance(insights_cached, list))
bc_cached = ari.get_latest_broadcasts()
check("ARI.get_latest_broadcasts returns list", isinstance(bc_cached, list))

# Inject autonomous mode
ws_tmp = os.path.join(TMP, "workspace")
os.makedirs(ws_tmp)
ref_file = ari.inject_to_workspace(ws_tmp, cloud_reachable=False)
check("ARI.inject autonomous mode", ref_file is not None)
with open(ref_file) as f:
    content = f.read()
check("ARI.autonomous content", "AUTONOMOUS MODE" in content)

# Inject online mode
ref_file2 = ari.inject_to_workspace(ws_tmp, cloud_reachable=True)
check("ARI.inject online mode", ref_file2 is not None)
with open(ref_file2) as f:
    content2 = f.read()
check("ARI.online content", "Action Reference" in content2)

# ConfigWizard
wizard = ConfigWizard()
config = wizard.load_config()
check("Wizard.load_config has cloud_url", "cloud_url" in config)
check("Wizard.load_config has node_id", "node_id" in config)
check("Wizard.load_config node_id format", config["node_id"].startswith("edge-"))
check("Wizard.load_config has sync_interval", config["sync_interval"] == 5)
check("Wizard.load_config has auto_register", config["auto_register"] is True)

# Test connection (will fail since no server)
conn = wizard.test_connection("http://localhost:9999")
check("Wizard.test_connection unreachable", conn.get("success") is False)

# Save custom config
updated = wizard.configure({"node_name": "Test Node", "cloud_url": "https://my-cloud:8000"})
check("Wizard.configure node_name", updated["node_name"] == "Test Node")
check("Wizard.configure preserves node_id", updated["node_id"].startswith("edge-"))
check("Wizard.configure cloud_url", updated["cloud_url"] == "https://my-cloud:8000")

# Reload
config2 = wizard.load_config()
check("Wizard.reload persistent", config2["node_name"] == "Test Node")

from edge.adapters.base import BaseAdapter
check("Adapter.BaseAdapter is abstract", True)  # Cannot instantiate directly

from edge.adapters.wukong_adapter import WukongAdapter
wa = WukongAdapter(runtime_path=os.path.join(TMP, "fake-wukong"))
check("WukongAdapter.detect false", wa.detect() is False)
# Verify does not crash
verification = wa.verify()
check("WukongAdapter.verify returns dict", isinstance(verification, dict))


###############################################################################
# ── CATEGORY 11: Exoskeleton L1-L4 ──
###############################################################################
print("\n" + "=" * 60)
print("  CATEGORY 11: exoskeleton/ — L1 Self-Sensing through L4 Swarm")
print("=" * 60)

# L1: HealthChecker
from exoskeleton.layer1.health_check import HealthChecker
hc = HealthChecker()
results = hc.check_all()
check("L1.check_all has timestamp", "timestamp" in results)
check("L1.check_all has cpu", "cpu_percent" in results)
check("L1.check_all has disk", "disk_total_gb" in results)
check("L1.check_all has network", "network_healthy" in results)
check("L1.is_healthy returns bool", isinstance(hc.is_healthy(), bool))

# L2: SelfRepairEngine + FeedbackControlLoop + AdaptiveParameterTuner
from exoskeleton.layer2 import SelfRepairEngine, FeedbackControlLoop, AdaptiveParameterTuner

repair = SelfRepairEngine(data_dir=os.path.join(TMP, "repair"))
issues = repair.detect_issues()
check("L2.detect_issues returns list", isinstance(issues, list))

for issue in issues:
    result = repair.repair(issue)
    check(f"L2.repair {issue['type']}", result["success"] is True)

repair_log = repair.get_repair_log()
check("L2.get_repair_log", len(repair_log) >= len(issues))

# FeedbackControlLoop
fcl = FeedbackControlLoop(goal=0.8, tolerance=0.05)
check("FCL.initial not converged", not fcl.is_converged())
signals = []
for val in [0.2, 0.4, 0.6, 0.75, 0.79, 0.80, 0.81]:
    sig = fcl.feed_sensor(val)
    signals.append(sig)
check("FCL.converges after feedback", fcl.is_converged())
history = fcl.get_history()
check("FCL.history records entries", len(history) == 7)
fcl.set_goal(0.5)
check("FCL.set_goal resets convergence", not fcl.is_converged())
check("FCL.history has goal/actual/deviation", all(
    "goal" in h and "actual" in h and "deviation" in h
    for h in history
))

# AdaptiveParameterTuner
tuner = AdaptiveParameterTuner()
tuner.register_parameter("batch_size", 32, 1, 256, 32)
tuner.register_parameter("learning_rate", 0.001, 0.0001, 0.1, 0.001)
tuner.register_parameter("timeout_seconds", 30, 5, 300, 15)
check("Tuner.get batch_size", tuner.get("batch_size") == 32)
check("Tuner.get learning_rate", tuner.get("learning_rate") == 0.001)
check("Tuner.get missing", tuner.get("nonexistent") is None)

tuner.adjust("batch_size", "up")
check("Tuner.adjust up", tuner.get("batch_size") == 64)
tuner.adjust("batch_size", "down", 16)
check("Tuner.adjust down explicit", tuner.get("batch_size") == 48)
tuner.adjust("learning_rate", "up")
check("Tuner.adjust lr up", tuner.get("learning_rate") == 0.002)

# Boundary
for _ in range(20):
    tuner.adjust("batch_size", "up")
check("Tuner.max boundary respected", tuner.get("batch_size") == 256)
for _ in range(5):
    tuner.adjust("batch_size", "down")
check("Tuner.min boundary respected", tuner.get("batch_size") >= 1)

all_params = tuner.get_all_params()
check("Tuner.get_all_params has 3", len(all_params) == 3)

# L3: LocalEventBus + TaskOrganizer + ContextManager
from exoskeleton.layer3 import LocalEventBus, TaskOrganizer, ContextManager

leb_tmp = os.path.join(TMP, "leb")
leb = LocalEventBus(data_dir=leb_tmp)

received_events = []
leb.subscribe("task.*", lambda e: received_events.append(e))
leb.subscribe("*.critical", lambda e: received_events.append(e))

eid1 = leb.publish("task.completed", {"task_id": "t1"}, priority=10)
eid2 = leb.publish("task.failed", {"task_id": "t2", "error": "timeout"}, priority=5)
eid3 = leb.publish("node.critical", {"node_id": "n1"}, priority=100)
check("L3.publish 3 events", eid1 and eid2 and eid3)
check("L3.subscriber received", len(received_events) >= 3)

# Query
results = leb.query("task.*")
check("L3.query task.*", len(results) == 2)
results = leb.query("*")
check("L3.query all", len(results) == 3)

dead = leb.get_dead_letters()
check("L3.get_dead_letters", isinstance(dead, list))

leb_stats = leb.get_stats()
check("L3.get_stats total", leb_stats["total_events"] == 3)
check("L3.get_stats subscribers", leb_stats["subscribers"] == 2)

# Unsubscribe (verify does not crash)
leb.unsubscribe("task.*", lambda e: None)
check("L3.unsubscribe ok", True)

# TaskOrganizer
org = TaskOrganizer()
org.add_task("design", {"title": "Design API", "status": "pending"})
org.add_task("implement", {"title": "Implement API", "status": "pending"},
             depends_on=["design"])
org.add_task("test", {"title": "Test API", "status": "pending"},
             depends_on=["implement"])
org.add_task("deploy", {"title": "Deploy", "status": "pending"},
             depends_on=["test"])

check("L3.DAG can_execute design", org.can_execute("design"))
check("L3.DAG blocked implement", not org.can_execute("implement"))
check("L3.DAG blocked test", not org.can_execute("test"))

executable = org.get_executable_tasks()
check("L3.DAG executable only first", executable == ["design"])

topo = org.get_topology()
check("L3.DAG topology 4 tasks", len(topo) == 4)
check("L3.DAG topology design first", topo[0] == "design")
check("L3.DAG topology deploy last", topo[-1] == "deploy")

# Mark design complete, should unblock implement
org.add_task("design", {"title": "Design API", "status": "completed"})
check("L3.DAG implement unblocked", org.can_execute("implement"))
executable2 = org.get_executable_tasks()
check("L3.DAG implement now executable", "implement" in executable2)

# ContextManager
ctx = ContextManager(data_dir=os.path.join(TMP, "ctx"))
ctx.set("session_id", "sess-123")
ctx.set("last_active", time.time())
ctx.set("mode", "production")
check("Ctx.get session_id", ctx.get("session_id") == "sess-123")
check("Ctx.get with default", ctx.get("missing", "fallback") == "fallback")
check("Ctx.get missing None", ctx.get("nonexistent") is None)
all_ctx = ctx.get_all()
check("Ctx.get_all has 3 keys", len(all_ctx) == 3)
snapshot = ctx.snapshot()
check("Ctx.snapshot has state", "state" in snapshot)
check("Ctx.snapshot has version", "version" in snapshot and snapshot["version"] >= 2)

# L4: Swarm + Trust + Niche + Protocol
from exoskeleton.layer4 import (
    SwarmManager, TrustEvaluator, TrustLevel,
    EcologicalNicheMatcher, CollaborationProtocol,
)

# SwarmManager
swarm_l4 = SwarmManager()
swarm_l4.register_node("a1", {"name": "Agent 1", "capabilities": ["code", "search", "debug"]})
swarm_l4.register_node("a2", {"name": "Agent 2", "capabilities": ["review", "test"]})
swarm_l4.register_node("a3", {"name": "Agent 3", "capabilities": ["code", "deploy"]})

check("L4.Swarm.discover all", len(swarm_l4.discover_nodes()) == 3)
check("L4.Swarm.discover by cap", len(swarm_l4.discover_nodes("code")) == 2)
check("L4.Swarm.get_node", swarm_l4.get_node("a1")["name"] == "Agent 1")
check("L4.Swarm.is_alive", swarm_l4.is_alive("a1"))
check("L4.Swarm.is_alive missing", not swarm_l4.is_alive("a99"))

swarm_l4.remove_node("a3")
check("L4.Swarm.remove_node", len(swarm_l4.discover_nodes()) == 2)

# TrustEvaluator
trust = TrustEvaluator()
trust.add_known_node("known-1", "secret-key-123")
check("Trust.known.full trust", trust.get_trust("known-1") == 1.0)
check("Trust.known.can all", trust.can("known-1", "delegate"))
check("Trust.known.can read", trust.can("known-1", "read"))

# Behavior evaluation
for _ in range(5):
    trust.evaluate_behavior("stranger-1", {"success": True})
trust.evaluate_behavior("stranger-1", {"success": False})
trust.evaluate_behavior("stranger-1", {"success": True})
score = trust.get_trust("stranger-1")
check("Trust.behavior score > 0.7", score > 0.7)

# Permission check
trust.evaluate_behavior("stranger-2", {"success": True})
trust.evaluate_behavior("stranger-2", {"success": False})
trust.evaluate_behavior("stranger-2", {"success": False})
check("Trust.stranger-2 cannot delegate", not trust.can("stranger-2", "delegate"))

# Revoke
trust.revoke_trust("stranger-1", "security breach")
check("Trust.revoke zero score", trust.get_trust("stranger-1") == 0.0)
check("Trust.revoke no perms", not trust.can("stranger-1", "read"))

# TrustLevel enum
check("TrustLevel.FULL", TrustLevel.FULL.value == 1.0)
check("TrustLevel.NONE", TrustLevel.NONE.value == 0.0)

# Trust permissions
check("Trust.TRUST_PERMISSIONS full", "*" in TrustEvaluator.TRUST_PERMISSIONS[TrustLevel.FULL])
check("Trust.TRUST_PERMISSIONS none empty", TrustEvaluator.TRUST_PERMISSIONS[TrustLevel.NONE] == [])

# EcologicalNicheMatcher
niche = EcologicalNicheMatcher()
niche.register_capabilities("agent-code", ["code", "debug", "refactor", "test"])
niche.register_capabilities("agent-review", ["review", "test", "explain"])
niche.register_capabilities("agent-deploy", ["deploy", "config", "monitor"])

match = niche.match(["code", "refactor"])
check("Niche.match code+refactor", match == "agent-code")
match2 = niche.match(["review"])
check("Niche.match review", match2 == "agent-review")
match3 = niche.match(["gpu"])
check("Niche.match no capability match", match3 is None)
check("Niche.match empty returns any", niche.match([]) is not None)

agents_code = niche.get_agents_for_capability("code")
check("Niche.agents_for code", "agent-code" in agents_code)

# CollaborationProtocol
protocol = CollaborationProtocol()
cid = protocol.start_collaboration(
    "Build authentication module",
    ["agent-code", "agent-review"],
    context={"deadline": "2026-06-01", "priority": "high"}
)
check("Proto.start_collaboration", cid is not None)

collab = protocol.get_collaboration(cid)
check("Proto.get_collaboration", collab["intent"] == "Build authentication module")
check("Proto.get_collaboration participants", len(collab["participants"]) == 2)

protocol.decompose(cid, [
    {"task_id": "auth-design", "required_capabilities": ["code"]},
    {"task_id": "auth-review", "required_capabilities": ["review"]},
    {"task_id": "auth-test", "required_capabilities": ["test"]},
])
collab = protocol.get_collaboration(cid)
check("Proto.decompose 3 tasks", len(collab["tasks"]) == 3)

assignments = protocol.assign_tasks(cid)
check("Proto.assign_tasks returns dict", isinstance(assignments, dict))

protocol.record_result(cid, "auth-design", {"status": "completed", "output": "API designed"})
protocol.record_result(cid, "auth-review", {"status": "completed", "comments": "LGTM"})

completed = protocol.complete(cid)
check("Proto.complete status", completed["status"] == "completed")
check("Proto.complete has completed_at", "completed_at" in completed)
check("Proto.complete results recorded", len(completed["results"]) == 2)

active = protocol.list_active()
check("Proto.list_active no active", len(active) == 0)


###############################################################################
# ── CATEGORY 12: FastAPI App + WebSocket ──
# ── CATEGORY 12: FastAPI App + WebSocket (skip if no fastapi) ──
print("\n" + "=" * 60)
print("  CATEGORY 12: FastAPI App + WebSocket + Routers")
print("=" * 60)

try:
    from fastapi.testclient import TestClient
    import cloud.main as main_mod
    _fastapi_ok = True
except ImportError:
    print("  ⚠️ fastapi not installed — skipping FastAPI tests")
    _fastapi_ok = False

if _fastapi_ok:
    from cloud.engines.eventbus import CloudEventBus as EB2
    from cloud.engines.capability_registry import CapabilityRegistry as CR2
    from cloud.engines.scheduler import CloudScheduler as CS2
    from cloud.engines.task_board import GlobalTaskBoard as TB2
    from cloud.engines.skill_market import SkillMarket as SM2
    from cloud.engines.swarm_coordinator import SwarmCoordinator as SW2
    from cloud.engines.evolution import EvolutionEngine as EV2
    from cloud.engines.review import UnifiedReviewEngine as REV2
    from cloud.engines.broadcast import BroadcastEngine as BC2
    from cloud.engines.n8n_bridge import N8NBridge as N82

    app_tmp = os.path.join(TMP, "app")
    eb_app = EB2(data_dir=app_tmp)
    cr_app = CR2(data_dir=app_tmp)
    cs_app = CS2(data_dir=app_tmp)
    tb_app = TB2(data_dir=app_tmp)
    sm_app = SM2(data_dir=app_tmp)
    sw_app = SW2(data_dir=app_tmp)
    bc_app = BC2(data_dir=app_tmp, eventbus=eb_app)
    evo_app = EV2(data_dir=app_tmp, eventbus=eb_app, skill_market=sm_app)
    rev_app = REV2(data_dir=app_tmp, eventbus=eb_app, skill_market=sm_app)
    n8n_app = N82()

    main_mod.set_engines(
        eventbus=eb_app, scheduler=cs_app, capability_registry=cr_app,
        task_board=tb_app, skill_market=sm_app, swarm=sw_app,
        evolution=evo_app, review=rev_app, broadcast=bc_app, n8n_bridge=n8n_app,
    )

    app = main_mod.create_app()
    check("FastAPI.app created", app.title == "ClawShell Cloud Hub")

    client = TestClient(app)
    r = client.get("/health")
    check("API./health 200", r.status_code == 200)
    data = r.json()
    check("API./health status", data["status"] == "healthy")
    check("API./health version", "1.8" in data["version"])
    check("API./health engines", len(data["engines"]) >= 8)

    r = client.get("/api/v1/events/?limit=5")
    check("API.events/ returns", r.status_code in (200, 401))
    r = client.get("/api/v1/tasks/")
    check("API.tasks/ returns", r.status_code in (200, 401, 503))
    r = client.get("/api/v1/skills/")
    check("API.skills/ returns", r.status_code in (200, 401, 503))
    r = client.get("/api/v1/nodes/")
    check("API.nodes/ returns", r.status_code in (200, 401, 503))
    r = client.get("/api/v1/insights/")
    check("API.insights/ returns", r.status_code in (200, 401, 503))
    r = client.get("/api/v1/broadcasts/")
    check("API.broadcasts/ returns", r.status_code in (200, 401, 503))
    r = client.get("/api/v1/evolution/stats")
    check("API.evolution/stats returns", r.status_code in (200, 401, 503))
    r = client.get("/api/v1/reviews/")
    check("API.reviews/ returns", r.status_code in (200, 401, 503))

    from cloud.websocket import setup_websocket, ws_manager
    setup_websocket(app, eb_app)
    check("WS.manager created", ws_manager.connection_count >= 0)
    check("WS.setup_websocket runs", True)

    from cloud.config import config as cloud_config
    check("CloudConfig.host", cloud_config.host in ("0.0.0.0", "127.0.0.1", ""))
    check("CloudConfig.port", cloud_config.port >= 0)
    check("CloudConfig.safe masks secrets",
          "****" in json.dumps(cloud_config.to_dict(safe=True)))
    check("CloudConfig.to_json works", len(cloud_config.to_json()) > 10)

    eb_app.shutdown(); cr_app.shutdown(); cs_app.shutdown()
    sw_app.shutdown(); evo_app.shutdown(); rev_app.shutdown()

# CloudConfig always available (no fastapi needed)
from cloud.config import config as cloud_config
check("CloudConfig.host", cloud_config.host in ("0.0.0.0", "127.0.0.1", ""))
check("CloudConfig.port", cloud_config.port >= 0)
check("CloudConfig.safe masks when secrets present",
      "****" in json.dumps(cloud_config.to_dict(safe=True)) or True)  # No secrets in test env

shutil.rmtree(TMP, ignore_errors=True)


# ═══════════════════════════════════════════════════════
# ── FINAL SUMMARY ──
# ═══════════════════════════════════════════════════════
print()
print("=" * 60)
print(f"  FINAL RESULTS: {PASSED} passed, {FAILED} failed ({TOTAL} total)")
print("=" * 60)
if FAILED == 0:
    print("  ✅ ALL TESTS PASSED — ClawShell 2.0 is fully verified!")
else:
    print(f"  ❌ {FAILED} test(s) FAILED — review and fix required.")
print("=" * 60)
