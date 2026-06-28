<div align="center">
  <h1>🦀 ClawShell v3.0</h1>
  <p><strong>Pluggable Exoskeleton Enhancement Layer for AI Agent Frameworks</strong></p>
  <p>AI Agent 框架的即插即用外骨骼增强层</p>

  <p>
    <a href="https://clawshell.club"><img src="https://img.shields.io/badge/website-clawshell.club-22d3ee?style=flat-square" alt="Website"></a>
    <a href="https://github.com/jorinyang/ClawShell/releases"><img src="https://img.shields.io/badge/release-v3.0.0-6366f1?style=flat-square" alt="Version"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-fbbf24?style=flat-square" alt="License"></a>
    <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-34d399?style=flat-square" alt="Python"></a>
    <a href="#"><img src="https://img.shields.io/badge/arch-4%20layers-f472b6?style=flat-square" alt="Architecture"></a>
  </p>
</div>

---

## What is ClawShell

ClawShell is a **pluggable exoskeleton enhancement layer** for OpenClaw-class AI agent frameworks. It provides self-perception, self-adaptation, self-organization, and multi-agent cluster capabilities — without modifying the host framework.

```
Your AI Agent (Hermes / Wukong / Claude Code / OpenClaw / ...)
              ↓ Plug in ClawShell
  ☁️  Cloud Hub — 6-engine coordination layer
  💻  ClawShell Local — 4-layer exoskeleton + agent discovery
  🔌  5-way zero-config injection (MCP / Hook / Config / Loop / Skill)
  🖥️  Desktop GUI — Electron + Next.js management interface
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     ClawShell v3.0 Architecture                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ☁️ Cloud Hub (cloud/)                    🐙 GitHub (per-user)    │
│  ├─ EventBus + TaskBoard                   ├─ {prefix}-skills     │
│  ├─ CapabilityRegistry + AgentMesh         └─ {prefix}-knowledge  │
│  ├─ InsightEngine + HermesLoop                                   │
│  └─ Scheduler + Auth (register→approve→repos)                    │
│                                                                   │
│  💻 ClawShell Local (local/)              🖥️ Desktop GUI (web/)  │
│  ├─ compiler/  L1~L4 Exoskeleton          ├─ Agent Dashboard      │
│  ├─ adapters/  framework/bridge/ide       ├─ Adapter Panel        │
│  ├─ agent/     Scanner+Injector+Store     ├─ Skill & Knowledge    │
│  ├─ sync/      3-Channel SyncDaemon       ├─ Task Board           │
│  └─ detector/  10+ Framework Detection    └─ Admin Panel          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### v3.0 Key Changes from v2.x

| Dimension | v2.x | v3.0 |
|-----------|------|------|
| Cloud Engines | 19 engines | **6 engines** (slimmed, HermesLoop consolidates) |
| Edge Brain | `edge/` | **`local/`** (renamed) |
| Knowledge/Skills | Cloud-side storage | **Per-user GitHub repos** |
| User Management | None | **Register→Pending→Approve→GitHub repos created** |
| Agent Detection | Framework-level | **Individual Agent instance** discovery |
| Injection | Basic MCP | **5-way**: MCP + Hook + Config + Loop Skill + Skill |
| Adapters | Scattered (3 dirs) | **Unified**: framework/bridge/ide with single interface |
| Sync | 1 channel (Cloud) | **3 channels**: GitHub + MemOS Cloud + Cloud Hub |
| GUI | Basic admin pages | **16 pages**: register, agents, skills, knowledge, tasks, admin |
| Cross-device | Node-level | **AgentMesh**: Agent-level capability matching |

---

## Quick Start

### Agent Mode (Recommended)

```
# Tell your AI Agent:
请帮我完成安装与配置：https://github.com/jorinyang/clawshell
```

The Agent auto-detects your environment, installs dependencies, injects MCP configs, and generates a self-check report.

### CLI Mode

```bash
# Linux / macOS
curl -fsSL https://clawshell.club/install.sh | bash

# Windows
iwr https://clawshell.club/install.ps1 | iex

# Docker (Local Brain)
docker run -d --name clawshell-local \
  --network host \
  -v ~/.clawshell/data:/root/.clawshell/data \
  -v ~/.clawshell/.env:/root/.clawshell/.env \
  clawshell-local
```

### Docker Compose (Full Stack)

```bash
# Clone and start (Cloud Hub + Web + Nginx)
git clone https://github.com/jorinyang/ClawShell.git
cd ClawShell
cp .env.example .env  # Edit with your credentials
docker compose -f deploy/docker-compose.yml up -d
```

---

## User Registration Flow

```
1. Open clawshell.club → Register
   - Enter account ID, display name, password
   - System auto-generates pinyin_prefix from display name ("杨瑒"→"y")

2. Wait for admin approval
   - Status: pending

3. Admin approves (Admin Panel → Pending Users → Approve)
   - GitHub repos auto-created: {prefix}-skills, {prefix}-knowledge
   - Status: active

4. Login → Local auto-clones your skill/knowledge repos
```

---

## Capability Matrix

### ☁️ Cloud Hub — 6 Core Engines

| Engine | Responsibility |
|--------|---------------|
| `EventBus` | Persistent event stream with dedup and broadcast |
| `TaskBoard` | Cross-device shared task board |
| `CapabilityRegistry` | Agent registration + capability declaration |
| `AgentMesh` | Agent-level capability matching + cross-device task dispatch |
| `InsightEngine` | Session insight aggregation + pattern mining |
| `HermesLoop` | 4 cron loops: session summary, task dispatch, session review, knowledge push |

### 💻 ClawShell Local

| Layer | Capability |
|-------|-----------|
| **L1 Self-Perception** | 7 monitors (Health/System/Disk/Process/Agent/Gateway/Service) |
| **L2 Self-Adaptation** | SelfRepairEngine (4 strategies) + FeedbackControlLoop + AdaptiveTuner |
| **L3 Self-Organization** | EventBus + TaskOrganizer (DAG) + ContextManager + Ecology |
| **L4 Multi-Agent Cluster** | SwarmEngine + TrustEvaluator + NicheMatcher + SwarmProtocol |
| **Genome** | Knowledge heritage + Cache + EvolutionTracker |

### 🔌 Five Injection Methods

| Method | Target | How |
|--------|--------|-----|
| **MCP** | Register MCP Server | Modify `mcpServerConfig.json` |
| **Hook** | Event hooks | Register event hook in agent config |
| **Config** | Configuration injection | Write `config.yaml` / `.env` |
| **Loop Skill** | Scheduled tasks | Register cron task / loop skill |
| **Skill** | Skill injection | Write `SKILL.md` to skills directory |

### 🔄 Three-Channel Sync

| Channel | Data | Transport |
|---------|------|-----------|
| **GitHub** | Knowledge + Skills | git clone/pull/push |
| **MemOS Cloud** | Memory | MemOS REST API |
| **Cloud Hub** | Tasks + Credentials + Insights | REST + WebSocket (5s cycle) |

---

## Supported Frameworks & Tools

### Agent Frameworks (Auto-Detected)
Hermes · Wukong · OpenClaw · QClaw · CoPaw · HiClaw · EasyClaw · WorkBuddy · Claude Code · Copaw

### IDE CLI Bridges
Codex · Claude Code · Kimi Code · DeepSeek TUI · Copilot · Windsurf

### Adapter Types
| Type | Examples |
|------|---------|
| **framework** | Hermes, Wukong, OpenClaw |
| **bridge** | N8N, Docker, ComfyUI, MemOS |
| **ide** | Claude Code, Codex |

---

## Project Structure

```
ClawShell/
├── cloud/           # Cloud Hub — FastAPI + 6 Engines + Event Sourcing
│   ├── auth/        # User auth, approval flow, credential encryption
│   ├── engines/     # EventBus, TaskBoard, AgentMesh, HermesLoop, etc.
│   ├── routers/     # REST API endpoints (auth, admin, agents, tasks)
│   └── services/    # GitHub API, MemOS Cloud client
├── local/           # ClawShell Local (formerly "edge")
│   ├── compiler/    # L1~L4 exoskeleton layers + Genome
│   ├── adapters/    # framework/ bridge/ ide/ — unified BaseAdapter
│   ├── agent/       # Scanner, Injector (5-way), ProfileStore
│   ├── sync/        # 3-channel SyncDaemon
│   └── detector/    # 10+ framework auto-detection
├── shared/          # Shared types, models, utilities
├── web/             # Desktop GUI — Electron + Next.js (16 pages)
├── tests/           # Test suites
├── deploy/          # Docker, Nginx, Terraform deployment configs
└── docs/            # Architecture & design documents
```

---

## Design Principles

> **Engineering Cybernetics** — Information feedback, dynamic regulation, holistic system thinking

**Non-Invasive** · **Low Coupling** · **High Robustness** · **High Generality** · **High Collaboration** · **High Extensibility** · **Idempotency** · **Cloud-Local Version Decoupling**

---

## License

MIT © [智询工作室](https://clawshell.club)
