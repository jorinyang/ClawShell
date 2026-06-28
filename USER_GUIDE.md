# ClawShell v3.0 — User Guide

> 中文手册 | English Guide | Version 3.0.0 | 2026-06-29

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Registration & Approval](#registration--approval)
4. [Agent Discovery & Injection](#agent-discovery--injection)
5. [Skills & Knowledge Management](#skills--knowledge-management)
6. [Three-Channel Sync](#three-channel-sync)
7. [Adapter Management](#adapter-management)
8. [Task Board](#task-board)
9. [Admin Panel](#admin-panel)
10. [Docker Deployment](#docker-deployment)
11. [Troubleshooting](#troubleshooting)

---

## Overview

**ClawShell** is a pluggable exoskeleton enhancement layer for OpenClaw-class AI agent frameworks. It adds four layers of intelligence (self-perception, self-adaptation, self-organization, multi-agent cluster) to your existing AI agents — without modifying the host framework.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Cloud Hub** | Lightweight coordination server (clawshell.club). 6 engines: EventBus, TaskBoard, CapabilityRegistry, AgentMesh, InsightEngine, HermesLoop. |
| **ClawShell Local** | Runs on your device. Detects agents, injects configs, syncs data 3 ways. |
| **Agent** | An AI agent instance (e.g. a specific Hermes agent profile, a Claude Code project). First-class citizen in v3.0. |
| **Skill** | Reusable capability module stored in your `{prefix}-skills` GitHub repo. |
| **Knowledge** | Curated knowledge entries stored in your `{prefix}-knowledge` GitHub repo. |

---

## Installation

### Prerequisites

| Dependency | Minimum | Check |
|-----------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Git | 2.30+ | `git --version` |
| pip | bundled | `python3 -m pip --version` |

### Method 1: Agent Auto-Install (Recommended)

Tell your AI agent this one sentence:

```
请帮我完成安装与配置：https://github.com/jorinyang/clawshell
```

The agent will:
1. Clone the ClawShell repository
2. Detect your installed AI frameworks
3. Install Python dependencies
4. Auto-inject MCP/Hook/Config/Loop/Skill configurations
5. Generate a self-check report

### Method 2: Manual Install

```bash
# Clone
git clone https://github.com/jorinyang/ClawShell.git ~/.clawshell
cd ~/.clawshell

# Install
pip install -e .

# Configure
cp .env.example .env
# Edit .env: set CLAWSHELL_CLOUD_URL, CLAWSHELL_API_TOKEN, your credentials

# Start sync daemon
python -m local.sync.daemon
```

### Method 3: Desktop Application (Electron)

ClawShell Local ships as an installable desktop app for Windows, macOS, and Linux.

**Download from GitHub Releases:**

Visit [https://github.com/jorinyang/ClawShell/releases](https://github.com/jorinyang/ClawShell/releases) and download the installer for your platform:

| Platform | File |
|----------|------|
| Windows | `ClawShell Local Setup *.exe` (NSIS installer) |
| macOS | `ClawShell Local-*.dmg` |
| Linux | `ClawShell Local-*.AppImage` or `*.deb` |

**Windows Installation:**
1. Download the `.exe` installer
2. Double-click to run (Windows may show SmartScreen — click "More info" → "Run anyway")
3. Choose install directory, create desktop shortcut
4. Launch "ClawShell Local" from Start Menu or desktop

**macOS Installation:**
1. Download the `.dmg` file
2. Open and drag `ClawShell Local.app` to Applications
3. On first launch, right-click the app → "Open" (Gatekeeper bypass once)

**Linux Installation:**
```bash
# AppImage
chmod +x "ClawShell Local-*.AppImage"
./ClawShell Local-*.AppImage

# Or via deb
sudo dpkg -i clawshell-local_*.deb
```

**Build from source:**
```bash
# Auto-build for current platform
python scripts/build_local_gui.py

# Or for a specific platform
python scripts/build_local_gui.py --platform win
python scripts/build_local_gui.py --platform mac
python scripts/build_local_gui.py --platform linux
```

The desktop app opens a local login window. Enter your Cloud Hub account credentials to connect.

### Method 4: Docker

```bash
# Local Brain (runs on your device)
docker run -d --name clawshell-local \
  --network host \
  -v ~/.clawshell/data:/root/.clawshell/data \
  -v ~/.clawshell/.env:/root/.clawshell/.env \
  clawshell-local

# Full Cloud Hub stack
docker compose -f deploy/docker-compose.yml up -d
```

### Method 5: Install Script

```bash
# Linux / macOS
curl -fsSL https://clawshell.club/install.sh | bash

# Windows PowerShell
iwr https://clawshell.club/install.ps1 | iex
```

---

## Registration & Approval

### User Registration

1. Open `https://clawshell.club` in your browser
2. Click **Register**
3. Fill in:
   - **Account ID** — your login username (e.g. `zhangsan`)
   - **Display Name** — your Chinese display name (e.g. `张三`)
   - **Password** — your login password (min 6 characters)
   - **Confirm Password**
4. Click **Register**

The system automatically generates a `pinyin_prefix` from your display name:
- `杨瑒` → `y`
- `张三` → `z`
- `李四` → `l`

Your account status will be **pending** — awaiting admin approval.

### Admin Approval (Cloud Hub Admin)

1. Log in as admin at `https://clawshell.club/admin/pending`
2. Review pending users
3. Click **Approve** for each user

On approval, the system automatically:
1. Creates `{pinyin_prefix}-skills` GitHub repository
2. Creates `{pinyin_prefix}-knowledge` GitHub repository
3. Sets user status to `active`

### First Login After Approval

1. Login at `https://clawshell.club/login`
2. On first login, you may be asked to change your password
3. The Local client will auto-clone your skill/knowledge repos

---

## Agent Discovery & Injection

### Automatic Agent Discovery

ClawShell Local automatically discovers all AI agent instances on your device:

```bash
# Run agent scanner
python -m local.agent.scanner --scan

# Output example:
# Discovered 5 agents:
#   hermes:default          — /home/user/.hermes/config.yaml
#   claude_code:clawshell   — /home/user/.claude/projects/clawshell
#   claude_code:mybot       — /home/user/.claude/projects/mybot
#   claude_code:webapp      — /home/user/.claude/projects/webapp
#   copaw:default           — /home/user/.copaw/config.yaml
```

### Supported Frameworks

| Framework | Detection Method |
|-----------|-----------------|
| **Hermes** | Parse `~/.hermes/config.yaml` → agents section → MCP configs |
| **Wukong** | Parse `~/.real/users/*/` → MCP configs per user |
| **OpenClaw** | Parse `~/.openclaw/config.yaml` → agent sections |
| **Claude Code** | Scan `~/.claude/projects/` → per-project agent config |
| **QClaw** | Check `~/.qclaw/` directory |
| **CoPaw** | Check `~/.copaw/` directory |
| **HiClaw** | Check `~/.hiclaw/` directory |
| **EasyClaw** | Check `~/.easyclaw/` directory |
| **WorkBuddy** | Check `~/.workbuddy/` directory |
| **Copaw** | Check `~/.copaw/` directory |

### Injection Status

Each agent has 5 injection methods. Check status:

```bash
python -m local.agent.scanner --injection-status

# Shows per-agent:
#   MCP:       ✓ injected
#   Hook:      ✓ injected
#   Config:    ✗ missing
#   Loop Skill: ✗ missing
#   Skill:     ✓ injected
```

### Inject All Missing Methods

```bash
# Inject all agents
python -m local.agent.injector --inject-all

# Inject specific agent
python -m local.agent.injector --agent hermes:default

# Inject only missing methods
python -m local.agent.injector --agent hermes:default --missing-only
```

### What Each Injection Does

| Injection | What Gets Modified | Effect |
|-----------|-------------------|--------|
| **MCP** | Agent's MCP server config | ClawShell MCP server registered |
| **Hook** | Agent's event hook config | Events published to Cloud EventBus |
| **Config** | Agent's config.yaml | ClawShell integration settings added |
| **Loop Skill** | Agent's cron/loop config | Scheduled sync tasks added |
| **Skill** | Agent's skills/ directory | `clawshell-sync` SKILL.md written |

---

## Skills & Knowledge Management

### Skills

Skills are reusable AI agent capabilities stored in your personal GitHub repo.

**Repository:** `{your-pinyin-prefix}-skills` (e.g. `y-skills`)

**Adding a Skill:**
1. Write a `SKILL.md` file following the skill specification
2. Push to your `{prefix}-skills` repo
3. ClawShell Local auto-pulls and loads the skill

**Skill Format:**
```markdown
# Skill: My Custom Skill

## Description
What this skill does

## Configuration
Required environment variables and settings

## Usage
How agents should use this skill
```

### Knowledge

Knowledge entries are curated information generated by agents, stored in your personal GitHub repo.

**Repository:** `{your-pinyin-prefix}-knowledge` (e.g. `z-knowledge`)

Knowledge is auto-generated by:
- HermesLoop Loop 1 (session summaries)
- HermesLoop Loop 3 (session reviews → patterns)
- HermesLoop Loop 4 (approved knowledge → git push)

### Viewing Skills & Knowledge

Open the Desktop GUI at `http://localhost:3000`:
- **Skills** page: browse and manage your skills library
- **Knowledge** page: browse and search your knowledge base

---

## Three-Channel Sync

ClawShell Local maintains synchronization across three independent channels:

### Channel 1: GitHub (Skills & Knowledge)

```
Local ←→ git clone/pull/push ←→ GitHub Repos
```

- **On startup:** `git clone` your skill and knowledge repos
- **Periodically:** `git pull` for updates from Cloud HermesLoop
- **On skill creation:** `git push` new skills

### Channel 2: MemOS Cloud (Memory)

```
Local ←→ MemOS REST API ←→ MemOS Cloud
```

- **After session ends:** Push local memories to MemOS Cloud
- **On startup:** Pull cloud memories to local cache
- **Periodically:** Bidirectional sync

### Channel 3: Cloud Hub (Tasks, Credentials, Insights)

```
Local ←→ REST + WebSocket ←→ Cloud Hub (5-second cycle)
```

The SyncDaemon runs a 9-step protocol every 5 seconds:
1. Flush local events to Cloud
2. Pull assigned tasks
3. Sync agent health report
4. Pull insights & broadcasts
5. Pull credential updates
6. Flush cron reports
7. Refresh auth token (periodically)
8. Sync credentials (periodically)
9. WebSocket keepalive

### Starting the SyncDaemon

```bash
# Foreground
python -m local.sync.daemon

# Background (Linux/macOS)
nohup python -m local.sync.daemon &

# As systemd service
sudo systemctl enable --now clawshell-local
```

---

## Adapter Management

### Adapter Types

| Type | Description | Examples |
|------|------------|---------|
| **framework** | AI agent frameworks | Hermes, Wukong, OpenClaw |
| **bridge** | External tool bridges | N8N, Docker, ComfyUI, MemOS |
| **ide** | IDE CLI integrations | Claude Code, Codex, Copilot |

### Viewing Adapters

Open the GUI → **Adapters** tab to see all detected adapters grouped by type.

```bash
# CLI: detect all adapters
python -m local.adapters.manager --detect-all

# CLI: show stats by type
python -m local.adapters.manager --stats
```

### Managing Adapters

From the GUI Adapter Panel:
- **Verify** — check if the adapter is properly configured
- **Inject** — inject ClawShell configuration into the adapter
- **Rollback** — revert injected configuration

---

## Task Board

### How Tasks Work

1. Tasks are created (by agents, HermesLoop, or admin)
2. AgentMesh matches tasks to the best agent by capability overlap
3. Tasks are dispatched to the matched agent
4. Agent executes and reports results

### Viewing Tasks

Open the GUI → **Tasks** page to see:
- All tasks with status (pending/running/completed/failed)
- Assigned agent
- Priority level
- Tags
- Creation date

### Task Lifecycle

```
pending → claimed → in_progress → completed
                          ↘ failed
```

---

## Admin Panel

### Access

Log in with an admin account at `https://clawshell.club/admin`.

### User Management

- **Pending Users:** Review and approve/reject new registrations
- **Users List:** View all users, their status, GitHub repos
- **Disable User:** Temporarily disable a user account

### System Dashboard

- Total users, active users, pending users
- Total credentials, shared credentials
- Online nodes, active sessions
- Recent audit log count

### Audit Logs

All security-relevant actions are logged:
- User registration and approval
- Login attempts (success/failure)
- Credential creation and access
- Configuration changes

---

## Docker Deployment

### Local Brain (Single Device)

```bash
# Build
docker build -t clawshell-local .

# Run
docker run -d --name clawshell-local \
  --network host \
  -v ~/.clawshell/data:/root/.clawshell/data \
  -v ~/.clawshell/.env:/root/.clawshell/.env \
  clawshell-local
```

### Full Cloud Hub Stack

```bash
# Clone repo
git clone https://github.com/jorinyang/ClawShell.git
cd ClawShell

# Configure environment
cp .env.example .env
# Edit .env with your credentials:
#   CLAWSHELL_ALIYUN_AK_ID, CLAWSHELL_ALIYUN_AK_SECRET
#   CLAWSHELL_MEMOS_API_KEY, CLAWSHELL_MEMOS_USER_ID
#   CLAWSHELL_GITHUB_TOKEN
#   JWT_SECRET, ENCRYPTION_KEY

# Start all services
docker compose -f deploy/docker-compose.yml up -d

# Check status
docker compose -f deploy/docker-compose.yml ps
```

**Services started:**
- `clawshell-api` — Cloud Hub API (port 8000)
- `clawshell-web` — Next.js web frontend (port 3000)
- `clawshell-nginx` — Nginx reverse proxy (ports 80/443)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CLAWSHELL_CLOUD_HOST` | Yes | Bind address (default: 0.0.0.0) |
| `CLAWSHELL_CLOUD_PORT` | Yes | Bind port (default: 8000) |
| `JWT_SECRET` | Yes | JWT signing secret |
| `ENCRYPTION_KEY` | Yes | AES-256-GCM encryption key (32 chars) |
| `JWT_EXPIRE_HOURS` | No | Token expiry in hours (default: 24) |
| `CLAWSHELL_GITHUB_TOKEN` | No | GitHub personal access token for repo creation |
| `CLAWSHELL_ALIYUN_AK_ID` | No | Alibaba Cloud AccessKey ID (OSS backup) |
| `CLAWSHELL_ALIYUN_AK_SECRET` | No | Alibaba Cloud AccessKey Secret |
| `CLAWSHELL_OSS_ENDPOINT` | No | OSS endpoint |
| `CLAWSHELL_OSS_BUCKET` | No | OSS bucket name |
| `CLAWSHELL_MEMOS_API_KEY` | No | MemOS Cloud API key |
| `CLAWSHELL_MEMOS_USER_ID` | No | MemOS Cloud user ID |
| `CLAWSHELL_N8N_URL` | No | N8N workflow engine URL |

---

## Troubleshooting

### Agent Not Detected

1. Check the framework is installed and configured
2. Verify config file paths: `~/.hermes/config.yaml`, `~/.real/`, `~/.openclaw/`
3. Run `python -m local.agent.scanner --dry-run` for debug output
4. Check file permissions on config directories

### Injection Failed

1. Ensure the target config file is writable
2. Check for syntax errors in existing config files
3. Run `python -m local.agent.injector --verify` to check current state
4. Use GUI Adapter Panel → Verify for detailed diagnostics

### SyncDaemon Not Connecting

1. Check network: `curl http://clawshell.club/health`
2. Verify API token in `.env`
3. Check Cloud Hub is running: `docker compose ps`
4. View daemon logs: `python -m local.sync.daemon --verbose`

### Registration Pending

New registrations require admin approval. Contact your ClawShell administrator or check the admin panel if you have access.

### GitHub Repo Not Created

1. Verify `CLAWSHELL_GITHUB_TOKEN` is set in Cloud Hub `.env`
2. Check GitHub token has `repo` scope
3. Check rate limits: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`

### Password Reset

Contact your ClawShell administrator. Admins can reset passwords via the Users panel.

---

## Support

- **Website:** [https://clawshell.club](https://clawshell.club)
- **GitHub:** [https://github.com/jorinyang/ClawShell](https://github.com/jorinyang/ClawShell)
- **Issues:** [https://github.com/jorinyang/ClawShell/issues](https://github.com/jorinyang/ClawShell/issues)

---

*ClawShell v3.0.0 — Engineering Cybernetics for AI Agents*
