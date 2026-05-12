"""Phase 3 tests: New Cloud Engines (v1.8.1).

Tests: WorkflowEngine, GlobalOptimizer, DeepThinkEngine, KnowledgeGraph
"""
import os, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_all():
    from cloud.engines.workflow import (WorkflowEngine, Workflow, Step, StepType, ExecutionStatus)
    from cloud.engines.optimizer import (GlobalOptimizer, OptimizationGoal, ResourceQuota, CostModel)
    from cloud.engines.deep_think import DeepThinkEngine, ThinkNode
    from cloud.services.knowledge_graph import KnowledgeGraph, Entity, Relation, GraphQuery

    passed, failed = 0, 0
    def check(n,c):
        nonlocal passed, failed
        if c: passed+=1; print(f"  ✅ {n}")
        else: failed+=1; print(f"  ❌ {n}")

    print("── Phase 3: New Cloud Engines ──")

    # WorkflowEngine
    print("\n── WorkflowEngine ──")
    engine = WorkflowEngine(store_dir=tempfile.mkdtemp())
    wf = Workflow(name="Test Saga", steps=[
        Step(name="step1", step_type=StepType.TASK, compensation="compensate_step1"),
        Step(name="step2", step_type=StepType.SAGA, compensation="compensate_step2"),
    ])
    engine.register_workflow(wf)
    check("register workflow", engine.get_workflow(wf.workflow_id) is not None)
    check("list workflows", len(engine.list_workflows()) == 1)
    ex = engine.start_execution(wf.workflow_id)
    check("start execution", ex is not None)
    check("status=running", ex.status == ExecutionStatus.RUNNING)
    s1 = wf.steps[0].step_id
    engine.step_completed(ex.execution_id, s1, {"ok": True})
    check("step completed", engine.get_execution(ex.execution_id).step_states[s1] == ExecutionStatus.COMPLETED)
    s2 = wf.steps[1].step_id
    engine.step_failed(ex.execution_id, s2, "test error")
    check("saga compensating", engine.get_execution(ex.execution_id).status == ExecutionStatus.COMPENSATING)
    check("compensation queue", len(engine.get_execution(ex.execution_id).compensation_queue) > 0)
    check("stats", engine.get_stats()["total_workflows"] == 1)

    # GlobalOptimizer
    print("\n── GlobalOptimizer ──")
    opt = GlobalOptimizer()
    opt.register_node("e1", "edge1", cpu_cores=4, max_tasks=10, current_tasks=3)
    opt.register_node("e2", "edge2", cpu_cores=8, max_tasks=20, current_tasks=15)
    opt.register_node("e3", "edge3", cpu_cores=2, max_tasks=5, current_tasks=5)
    result = opt.optimize(task_count=5, goal=OptimizationGoal.BALANCED)
    check("plans produced", len(result.plans) > 0)
    check("full node excluded", all(p.node_id != "e3" for p in result.plans))
    check("least-loaded first", result.plans[0].node_id == "e1")
    check("cost model works", CostModel.estimate(ResourceQuota(cpu_cores=2)) > 0)
    check("stats", opt.get_stats()["registered_nodes"] == 3)
    opt.remove_node("e3")
    check("remove node", opt.get_stats()["registered_nodes"] == 2)

    # DeepThinkEngine
    print("\n── DeepThinkEngine ──")
    dt = DeepThinkEngine()
    s = dt.start_session("How to improve reliability?")
    check("start session", s.session_id != "")
    n1 = ThinkNode(title="Root Cause", node_type="finding", content="Network timeouts", confidence=0.85)
    dt.add_node(s.session_id, n1)
    n2 = ThinkNode(title="Fix", node_type="recommendation", content="Add retry", parent_id=n1.node_id, confidence=0.9)
    dt.add_node(s.session_id, n2)
    dt.complete_session(s.session_id)
    check("findings", len(dt.get_session(s.session_id).findings) == 1)
    check("recommendations", len(dt.get_session(s.session_id).recommendations) == 1)
    check("confidence", dt.get_session(s.session_id).confidence > 0.8)
    check("stats", dt.get_stats()["completed_sessions"] == 1)

    # KnowledgeGraph
    print("\n── KnowledgeGraph ──")
    kg = KnowledgeGraph()
    e1 = kg.add_entity(Entity(name="Retry Pattern", entity_type="pattern", description="Exponential backoff", tags=["reliability"]))
    e2 = kg.add_entity(Entity(name="Circuit Breaker", entity_type="pattern", description="Fail fast", tags=["reliability"]))
    e3 = kg.add_entity(Entity(name="Timeout Bug", entity_type="insight", description="Common timeout", tags=["bug"]))
    check("add entities", kg.get_stats()["entity_count"] == 3)
    kg.add_relation(Relation(source_id=e1.entity_id, target_id=e2.entity_id, relation_type="complements", weight=0.8))
    kg.add_relation(Relation(source_id=e3.entity_id, target_id=e1.entity_id, relation_type="solved_by", weight=0.9))
    check("add relations", kg.get_stats()["relation_count"] == 2)
    q = GraphQuery(start_entity_id=e3.entity_id, max_depth=2)
    check("traverse", len(kg.traverse(q)) >= 1)
    check("find_paths", len(kg.find_paths(e3.entity_id, e2.entity_id)) >= 1)
    search = kg.search("retry timeout")
    check("search", any("Retry" in r.entity.name for r in search))
    check("find by type", len(kg.find_entities(entity_type="pattern")) == 2)
    kg.remove_entity(e3.entity_id)
    check("remove entity", kg.get_stats()["entity_count"] == 2)

    print(f"\n── Phase 3 Summary: {passed}/{passed+failed} passed ──")
    return failed == 0

if __name__ == "__main__":
    ok = test_all()
    sys.exit(0 if ok else 1)
