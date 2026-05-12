# ClawShell 2.0 — Changelog

## v1.8 (2026-05-12)

### 🏗️ Architecture
- **Complete clean-room rebuild** from v1.0.0
- **一云多端云边协同分布式神经系统** architecture
- 1 Cloud Hub (云枢) + N Edge Brains (端脑)
- Cloud: 12 engines on FastAPI + WebSocket
- Edge: 10+ framework auto-detection + 6 IDE CLI bridge + L1-L4 exoskeleton

### ☁️ Cloud Hub (新增)
- CloudEventBus — persistent + dedup + wildcard query + 30d expiry
- GlobalTaskBoard — cross-edge task CRUD + state machine
- SkillMarket — publish/discover/sync with version management
- CapabilityRegistry — edge registration + heartbeat + scheduling
- SwarmCoordinator — multi-node management + load balancing
- CronScheduler — 5-field cron parser + execution logging
- EvolutionEngine — InsightAggregator → PatternMiner → AutoSkillPublisher
- UnifiedReviewEngine — daily/weekly/monthly reviews → ActionPlan
- BroadcastEngine — announcements + BestPracticeRegistry + CrossEdgeLearning
- N8NBridge — event → workflow routing
- VaultAPI + OSSVaultSync — Obsidian vault CRUD + OSS sync
- MemOSCloudClient — cross-device memory synchronization

### 🖥️ Edge Brain (新增)
- **Framework Detectors**: 8 frameworks auto-detect (Wukong/Hermes/OpenClaw/QClaw/CoPaw/HiClaw/EasyClaw/WorkBuddy)
- **IDE Bridge**: Codex/Claude Code/Kimi Code/DeepSeek TUI/Copilot + Orchestrator + Sandbox
- **Ecosystem Installer**: 10 components (MemPalace/ChromaDB/N8N/MemOS/Watchdog/BrowserRT/ONNX/psutil/websockets/Obsidian+OSS)
- **Sync Daemon**: 5s Cloud↔Edge sync loop (scan→enqueue→flush→pull→health)
- **Action Reference**: pre-action cloud insight injection (autonomous mode on disconnect)
- **Config Wizard**: interactive Cloud URL/Token/NodeID setup

### 🦴 Exoskeleton (迁移+重构)
- **L1 Self-Sensing**: HealthChecker with 27-item system health scan
- **L2 Self-Adaptation**: SelfRepairEngine + FeedbackControlLoop + AdaptiveParameterTuner
- **L3 Self-Organization**: LocalEventBus + TaskOrganizer(DAG) + ContextManager
- **L4 Multi-Agent Swarm**: SwarmManager + TrustEvaluator + EcologicalNicheMatcher + CollaborationProtocol

### 🚀 Deployment
- Terraform IaC for Alibaba Cloud ECS
- Docker Compose stack (API + N8N + Nginx)
- One-line install scripts (install.sh / install.ps1)

### 📊 Testing
- 128 total tests across all phases
- Phase 1: 45/45 (shared types, eventbus, capability registry, scheduler, config, FastAPI)
- Phase 2: 29/29 (task board, skill market, swarm, evolution, review, broadcast, N8N, services)
- Phase 3: 24/24 (detectors, IDE bridge, ecosystem, sync daemon)
- Phase 4: 30/30 (adapters, L1-L4 exoskeleton, config wizard, CLI)

### ❌ Removed
- All v1.0/v0.9 legacy code (lib/, scripts/, bin/)
- Old path references (~/.openclaw → framework-agnostic)
- "章鱼式" naming (replaced with formal "一云多端云边协同分布式神经系统")
