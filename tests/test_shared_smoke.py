"""Smoke test for shared/ module."""
from shared import ClawShellEvent, Task, Skill, EdgeNode, Insight, Broadcast
from shared import format_api_response, format_ws_frame, validate_ws_frame
from shared import content_hash, generate_node_id, validate_node_id
from shared.types import TaskStatus, TaskPriority, NodeStatus, EventCategory

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

# Test ClawShellEvent
e = ClawShellEvent(event_type='test', source='edge-1', category='task', payload={'msg': 'hello'})
check("Event creation", e.event_type == 'test')
check("Event category enum", e.category == EventCategory.TASK)
check("Event hash non-empty", len(e.content_hash()) == 64)

e_dict = e.to_dict()
e2 = ClawShellEvent.from_dict(e_dict)
check("Event round-trip", e2.event_type == 'test')

# Test Task
t = Task(title='Test Task', priority='medium', status='pending')
check("Task enum status", t.status == TaskStatus.PENDING)
check("Task enum priority", t.priority == TaskPriority.MEDIUM)

t_dict = t.to_dict()
t2 = Task.from_dict(t_dict)
check("Task round-trip status", t2.status == TaskStatus.PENDING)
check("Task round-trip priority", t2.priority == TaskPriority.MEDIUM)

# Test EdgeNode
n = EdgeNode(node_id='edge-test', hostname='test-host', status='online')
check("Node status", n.status == NodeStatus.ONLINE)

n_dict = n.to_dict()
n2 = EdgeNode.from_dict(n_dict)
check("Node round-trip", n2.status == NodeStatus.ONLINE)

# Test protocol
resp = format_api_response(True, data={'key': 'val'}, meta={'page': 1})
check("API response", resp['success'] is True and 'data' in resp and 'meta' in resp)

frame = format_ws_frame('event_push', {'event_id': '123'})
check("WS frame valid", validate_ws_frame(frame))

# Test utils
hid = content_hash({'test': 'data'})
check("Hash length", len(hid) == 64)

nid = generate_node_id('my-host')
check("NodeID format", validate_node_id(nid))

# Test Skill, Insight, Broadcast
s = Skill(name='test-skill', version='1.0.0')
check("Skill creation", s.name == 'test-skill')

ins = Insight(title='Best Practice', confidence=0.95, content='Use async')
check("Insight creation", ins.confidence == 0.95)

br = Broadcast(title='Announcement', broadcast_type='alert')
check("Broadcast creation", br.broadcast_type == 'alert')

# Test serialization
json_str = e.to_dict()
check("Event serializable", isinstance(json_str, dict))

# Summary
print()
print(f"{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("✅ ALL TESTS PASSED")
else:
    print(f"❌ {failed} TESTS FAILED")
