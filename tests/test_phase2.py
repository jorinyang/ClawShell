"""Phase 2: Cloud Hub Complete Engine Verification."""
import sys, os, time, json, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond: passed += 1; print(f"  ✅ {name}")
    else: failed += 1; print(f"  ❌ {name}")

tmpdir = tempfile.mkdtemp(prefix="cs_p2_")

# ── TEST 1: GlobalTaskBoard ──
print("\n── TEST 1: GlobalTaskBoard ──")
from cloud.engines.task_board import GlobalTaskBoard, TaskStatus

tb = GlobalTaskBoard(data_dir=tmpdir)
tid = tb.create_task({"title": "Test Task", "priority": "high", "required_capabilities": ["code"]})
check("Create", tid is not None)
check("Get", tb.get_task(tid) is not None)
check("List all", len(tb.list_tasks()) == 1)
check("List by status", len(tb.list_tasks(status="pending")) == 1)

task = tb.claim(tid, "edge-1")
check("Claim", task["status"] == "in_progress")
check("Claim by edge", task["claimed_by"] == "edge-1")

task = tb.complete(tid, {"output": "done"})
check("Complete", task["status"] == "completed")
check("Results recorded", len(task.get("results", [])) == 1)

# Test transition guard
tid2 = tb.create_task({"title": "Task 2"})
try:
    tb.complete(tid2)  # Cannot complete from pending
    check("Transition guard blocks", False)
except ValueError:
    check("Transition guard blocks", True)

# Test stats
stats = tb.get_stats()
check("Stats total", stats["total"] == 2)
check("Stats by status", "completed" in stats["by_status"])

# Test priority ordering
tb.create_task({"title": "Low", "priority": "low"})
tb.create_task({"title": "Crit", "priority": "critical"})
tasks = tb.list_tasks(status="pending")
check("Priority order", tasks[0]["priority"] == "critical")

# Test assign
next_task = tb.get_next_pending(capability=[])
check("Next pending", next_task is not None)
tb.assign_to_edge(tasks[0]["task_id"], "edge-2")
check("Assign to edge", tb.get_task(tasks[0]["task_id"])["assigned_to"] == "edge-2")


# ── TEST 2: SkillMarket ──
print("\n── TEST 2: SkillMarket ──")
from cloud.engines.skill_market import SkillMarket

sm = SkillMarket(data_dir=tmpdir)
sid = sm.publish({"name": "Test Skill", "description": "A test", "tags": ["python", "test"], "capabilities": ["code"]})
check("Publish", sid is not None)
check("Get", sm.get_skill(sid) is not None)
check("List", len(sm.list_skills()) == 1)
check("Search by tag", len(sm.search_by_tag("python")) == 1)
check("Search text", len(sm.list_skills(search="test")) == 1)

sm.download(sid)
sm.download(sid)
s = sm.get_skill(sid)
check("Download count", s["download_count"] == 2)

sm.rate(sid, 5.0)
sm.rate(sid, 3.0)
s = sm.get_skill(sid)
check("Rating", s["rating"] == 4.0)

stats = sm.get_stats()
check("Skill stats", stats["total_skills"] == 1)

# Test updates_since
time.sleep(0.1)
now = time.time()
sm.publish({"name": "New Skill", "skill_id": None})
updates = sm.get_updates_since(now)
check("Updates since", len(updates) >= 1)


# ── TEST 3: SwarmCoordinator ──
print("\n── TEST 3: SwarmCoordinator ──")
from cloud.engines.swarm_coordinator import SwarmCoordinator

swarm = SwarmCoordinator(data_dir=tmpdir, heartbeat_interval=30, heartbeat_timeout=90)
nid = swarm.register_node({"node_id": "n1", "capabilities": ["code", "search"], "frameworks": ["hermes"]})
check("Register", nid == "n1")
check("List", len(swarm.list_nodes()) == 1)
check("Online count", swarm.online_count() == 1)
check("Heartbeat", swarm.heartbeat("n1", {"cpu_percent": 20, "memory_percent": 30}))

# Load balancing
swarm.register_node({"node_id": "n2", "capabilities": ["code"], "load_score": 0.1})
swarm.register_node({"node_id": "n3", "capabilities": ["code"], "load_score": 0.8})
least = swarm.get_least_loaded_node(["code"])
check("Least loaded", least in ("n1", "n2"))  # n2 or n1 (lower load)

swarm.assign_task("n1", "task-1")
n = swarm.get_node("n1")
check("Task assigned", n["task_count"] == 1)

events = swarm.get_recent_events()
check("Events recorded", len(events) >= 1)

swarm.deregister_node("n3")
check("Deregister", swarm.online_count() == 2)


# ── TEST 4: Evolution + Review + Broadcast ──
print("\n── TEST 4: Evolution + Review + Broadcast ──")
from cloud.engines.evolution import EvolutionEngine
from cloud.engines.review import UnifiedReviewEngine
from cloud.engines.broadcast import BroadcastEngine

evo = EvolutionEngine(data_dir=tmpdir)
review = UnifiedReviewEngine(data_dir=tmpdir)
bc = BroadcastEngine(data_dir=tmpdir)

# Evolution
iid = evo.add_insight("Test Insight", "This is a test insight", confidence=0.9)
check("Add insight", bool(iid))
check("Get insights", len(evo.get_insights()) >= 1)
check("Evolution stats", evo.get_stats()["total_insights"] >= 1)

# Review
daily = review.run_review_now("daily")
check("Daily review", daily["type"] == "daily")
weekly = review.run_review_now("weekly")
check("Weekly review", weekly["type"] == "weekly")
check("Recent reviews", len(review.get_recent_reviews()) >= 2)

# Broadcast
bid = bc.broadcast("Announcement", "Hello edges!", broadcast_type="announcement")
check("Broadcast", bool(bid))
check("Get broadcasts", len(bc.get_broadcasts()) >= 1)

pid = bc.register_best_practice("Use async", "Always use async for I/O")
check("Register best practice", bool(pid))
check("Search best practice", len(bc.search_best_practices("async")) >= 1)

bc.ingest_edge_learning("edge-1", {"patterns": ["use_cache"], "success_rate": 0.95})
learning = bc.get_edge_learning("edge-1")
check("Edge learning", learning.get("success_rate") == 0.95)


# ── TEST 5: N8NBridge ──
print("\n── TEST 5: N8NBridge ──")
from cloud.engines.n8n_bridge import N8NBridge

n8n = N8NBridge(n8n_base_url="http://localhost:5678")
n8n.add_route("task.*", "http://localhost:5678/webhook/task")
n8n.add_route("error.*", "http://localhost:5678/webhook/error")
routes = n8n.list_routes()
check("Routes added", len(routes) == 2)

matches = n8n.match_routes("task.completed")
check("Match task route", len(matches) == 1)

matches2 = n8n.match_routes("error.critical")
check("Match error route", len(matches2) == 1)

matches3 = n8n.match_routes("unknown.event")
check("No match", len(matches3) == 0)

# Health check (will be unhealthy since no N8N running)
health = n8n.health_check()
check("Health check runs", isinstance(health, dict) and "status" in health)


# ── TEST 6: MemOS Cloud Client ──
print("\n── TEST 6: MemOS Cloud Client ──")
from cloud.services.memos_cloud import MemOSCloudClient

memos = MemOSCloudClient(user_id="test-user")
stats = memos.get_stats()
check("MemOS stats", isinstance(stats, dict))
check("API key not set", not stats["api_key_configured"])

# Test with API key
memos2 = MemOSCloudClient(api_key="mpg-test", user_id="test-user")
check("API key configured", memos2.get_stats()["api_key_configured"])


# ── TEST 7: Vault API ──
print("\n── TEST 7: Vault API ──")
from cloud.services.vault_api import VaultAPI

vault = VaultAPI(vault_path=tmpdir)
status = vault.get_status()
check("Vault status", isinstance(status, dict))

vault.write_note("test.md", "# Test Note\nContent here")
note = vault.read_note("test.md")
check("Read note", note is not None and "Content" in note["content"])

files = vault.list_files()
check("List files", len(files) == 1)

results = vault.search("Content")
check("Search", len(results) >= 1)

vault.delete_note("test.md")
check("Delete note", len(vault.list_files()) == 0)

# Test path traversal prevention
note2 = vault.read_note("../../../etc/passwd")
check("Path traversal blocked", note2 is None)


# ── TEST 8: OSS Sync ──
print("\n── TEST 8: OSS Vault Sync ──")
from cloud.services.oss_sync import OSSVaultSync

oss = OSSVaultSync(vault_path=tmpdir, oss_bucket="test-bucket")
stats = oss.get_stats()
check("OSS stats", stats["oss_configured"] is False)  # No creds

# Push without creds should skip
result = oss.push()
check("Push skipped (no creds)", result["status"] == "skipped")


# ── Cleanup ──
shutil.rmtree(tmpdir, ignore_errors=True)

# ── SUMMARY ──
print(f"\n{'='*50}")
print(f"Phase 2: {passed} passed, {failed} failed")
print("✅ PHASE 2 ALL TESTS PASSED" if failed == 0 else f"❌ {failed} FAILED")
