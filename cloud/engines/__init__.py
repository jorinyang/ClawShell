"""Cloud Hub engine modules.

v3.0 engine slim-down (15→6):
  Retained:  EventBus, TaskBoard, CapabilityRegistry, InsightEngine, Scheduler,
             CronSupervisor, DispatchRouter, SwarmCoordinator, ReportEngine
  Deprecated: SkillMarket, Evolution, Review(Rewind), Broadcast, N8NBridge,
              Optimizer, Workflow, DeepThink, TopologyManager
  New:       AgentMesh, HermesLoop (both in cloud/engines/)
"""
