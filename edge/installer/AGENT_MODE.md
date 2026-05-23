# ClawShell Edge — Agent Installation Guide v2.2

> **This document is designed to be consumed by an AI Agent.**
> Follow each phase in order. Report progress using `[OK]` / `[FAIL]` markers.
> The ONLY human interaction is in Phase 1: collecting 2 API keys.
> All other phases are fully automated. Do not ask the user for confirmation on automated steps.

---

## Execution Rules for Agents

1. **Ordered phases** — Execute Phase 1 → 2 → ... → 6 in sequence. Do not skip.
2. **Exit code checks** — After each `bash` block, check `$?`. If 0, proceed. If non-zero, the step has failed.
3. **Transient failures** — Git clone / pip install may fail due to network. Retry ONCE. If still failing, report to user.
4. **Progress markers** — After each phase completes, say `[OK] Phase N complete` so the user (and parsing tools) can track progress.
5. **Human interaction rule** — The ONLY time you ask the user for input is Phase 1 (API keys). Should be ONE message with 2 items. Collect both at once. Do not ask "should I proceed" — just proceed after collecting.
6. **Install directory** — Default: `~/.clawshell`. If the user specified a different path, use it throughout.
7. **Windows** — On Windows (PowerShell), substitute `python3` → `python`, `~/.clawshell` → `$env:USERPROFILE\.clawshell`.

---

## Phase 1: Collect Credentials (HUMAN)

**This is the only human interaction. Ask the user ONCE for both keys.**

Ask the user:
```
To install ClawShell Edge, I need 2 API keys:

1. MemOS Cloud API Key → Register at https://memos.cloud
   Format: mpg-xxxxxxxxxxxx

2. LLM Configuration (model name auto-detects provider + endpoint):

   **Default: deepseek-v4-pro**
   - Provider: deepseek (auto)  |  Endpoint: https://api.deepseek.com/v1 (auto)
   - API Key: https://platform.deepseek.com/api_keys

   **Alternative: MiniMax-M2.7-highspeed**
   - Provider: minimax (auto)  |  Endpoint: https://api.minimax.chat/v1 (auto)

   **Other supported models (auto-detected by prefix):**
   - deepseek-* → deepseek     |  gpt-* / o1-* / o3-* → openai
   - claude-* → anthropic       |  MiniMax-* → minimax

Please provide: model name and API Key (or say "skip").

Please provide both keys (or say "skip" for either).
```

Store the keys in environment variables:
```bash
export MEMOS_API_KEY="mpg-xxxx"
export LLM_PROVIDER="deepseek"
export LLM_ENDPOINT="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-chat"
export DEEPSEEK_API_KEY="sk-xxxx"    # if using DeepSeek
# or
export OPENAI_API_KEY="sk-xxxx"      # if using OpenAI
```

If user says "skip" for LLM: ClawShell uses CloudHub's built-in Brain LLM. Proceed with warning.
If user says "skip" for MemOS key: memory sync is disabled. Proceed with warning.

**[OK] Phase 1 complete** — credentials collected.

---

## Phase 2: Environment Scan

Detect OS, Python version, existing agents. All automated.

```bash
# OS detection
uname -s
python3 --version
which git || which git.exe
```

**Check results:**
- Python must be ≥ 3.10. If not, tell user to upgrade: `apt install python3.11` or `brew install python@3.12`
- Git must be installed. If not: `apt install git` or `brew install git`

```bash
# Hardware check
python3 -c "
import os, platform
print(f'CPU: {os.cpu_count()} cores')
print(f'Arch: {platform.machine()}')
"
```

**If running in WSL**: note that Windows-side agents are at `/mnt/c/Users/*` paths.

**[OK] Phase 2 complete** — environment is compatible.

---

## Phase 3: Clone & Install

Clone ClawShell and install dependencies. All automated.

```bash
# Clone or update
if [ -d ~/.clawshell/.git ]; then
    echo "[UPDATE] Pulling latest..."
    cd ~/.clawshell && git pull --ff-only
else
    echo "[CLONE] Cloning ClawShell..."
    git clone https://github.com/jorinyang/ClawShell.git ~/.clawshell
fi
```

**Check**: `~/.clawshell/edge/installer/` exists. If not, clone failed — retry ONCE.

```bash
# Install Python dependencies
cd ~/.clawshell
python3 -m pip install --quiet pyyaml requests aiohttp websockets
```

**If pip fails**: try `python3 -m pip install --user pyyaml requests aiohttp websockets`

```bash
# Install MemPalace (memory plugin)
if ! python3 -c "import mempalace" 2>/dev/null; then
    echo "[INSTALL] MemPalace..."
    git clone https://github.com/mempalace/mempalace.git ~/.mempalace 2>/dev/null || true
    cd ~/.mempalace && python3 -m pip install --quiet -e . 2>/dev/null || true
fi
```

**Check**: `python3 -c "import mempalace"` succeeds. If not, mark as `[SKIPPED]` — not critical.

```bash
# Install MemOS Cloud Plugin
if ! python3 -c "import memos_local" 2>/dev/null; then
    echo "[INSTALL] MemOS Cloud Plugin..."
    python3 -m pip install --quiet memos-local-plugin 2>/dev/null || true
fi
```

**Check**: `python3 -c "import memos_local"` succeeds. If not, mark as `[SKIPPED]`.

**[OK] Phase 3 complete** — ClawShell + plugins installed.

---

## Phase 4: Configuration Auto-Injection

Detect local AI agents and inject ClawShell MCP config. All automated.

```bash
cd ~/.clawshell && python3 -m edge.installer config
```

**What this does:**
- Detects Hermes, Wukong, OpenClaw, Cline, Cursor
- Adds `clawshell-edge` + `clawshell-memory` MCP servers to each agent's config
- Creates backup of original config (`.yaml.bak` / `.json.bak`)
- Reports which agents were configured and which were skipped

**If the `config` subcommand is not found**: you're on an older version. Manually inject:
- Hermes: `~/.hermes/config.yaml` → add under `mcp_servers:`
- Wukong: `mcpServerConfig.json` → add STDIO server entry

Template for manual injection — see Appendix A.

**[OK] Phase 4 complete** — agents configured.

---

## Phase 5: Environment Setup & Self-Check

Write `.env` and run self-check. All automated.

```bash
# Create .env with credentials
cat > ~/.clawshell/.env << EOF
CLAWSHELL_HOME=$HOME/.clawshell
CLAWSHELL_CLOUD_URL=http://47.239.71.174:8000
CLAWSHELL_NODE_ID=edge-$(hostname)

# LLM Configuration
LLM_PROVIDER=${LLM_PROVIDER:-deepseek}
LLM_ENDPOINT=${LLM_ENDPOINT:-https://api.deepseek.com/v1}
LLM_MODEL=${LLM_MODEL:-deepseek-chat}
DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY
# or: OPENAI_API_KEY=$OPENAI_API_KEY

# Memory
MEMOS_API_KEY=$MEMOS_API_KEY
EOF
```

```bash
# Full self-check
cd ~/.clawshell && python3 -m edge.installer check
```

**The `check` command outputs a Markdown report.** Present it to the user.

**If `check` is unavailable** (old version), run manual checks:
```bash
[ -d ~/.clawshell/edge ] && echo "[OK] edge/" || echo "[FAIL] edge/"
[ -d ~/.clawshell/exoskeleton ] && echo "[OK] exoskeleton/" || echo "[FAIL] exoskeleton/"
python3 -c "from edge.mcp.edge_server import main" 2>/dev/null && echo "[OK] MCP edge server" || echo "[FAIL] MCP edge server"
curl -s --max-time 5 http://47.239.71.174:8000/health && echo "[OK] CloudHub" || echo "[FAIL] CloudHub"
```

**[OK] Phase 5 complete** — self-check passed.

---

## Phase 6: Report to User

After all phases complete, present this structured report to the user:

```markdown
## 🦀 ClawShell Edge — Installation Complete

**Status**: `healthy` | **Path**: `~/.clawshell`

### System
- OS: {detected} | Python: {version} | CPU: {cores} cores | RAM: {memory}

### Agents Configured
| Agent | Status | MCP Injected |
|-------|--------|-------------|
| Hermes | ✅/❌ | ✅/❌ |
| Wukong | ✅/❌ | ✅/❌ |
| OpenClaw | ✅/❌ | ✅/❌ |

### Capabilities Enabled
- **Self-Awareness (L1)**: Auto-detect agents & environment
- **Self-Repair (L2)**: Auto-detect failures + 4 repair strategies
- **Task Orchestration (L3)**: Global TaskBoard + Workflow Engine
- **Agent Mesh (L4)**: Multi-agent collaborative network
- **MCP Protocol**: 19 tools via STDIO
- **Triple Memory**: MemPalace → MemOS Local → MemOS Cloud
- **Cloud-Edge Sync**: 5-second cycle, 9-step protocol

### Model Configuration
- LLM: DeepSeek V4 Pro (configured)
- Cloud Brain: DeepSeek V4 Pro (via CloudHub)
- Memory: MemOS Cloud

### Application Scenarios
- Multi-agent task orchestration & delegation
- Cross-device knowledge sync & memory
- Cron health monitoring with auto-repair
- Enterprise AI workflow automation

### Connection Status
- CloudHub: ✅ Connected (47.239.71.174:8000)
- Dashboard: https://clawshell.club/login
- Account: {jorinyang or user-specified}

### Next Steps
1. Start Edge daemon: `cd ~/.clawshell && python3 -m edge.sync.sync_daemon`
2. Your agents now have ClawShell tools auto-loaded on next restart
3. Visit https://clawshell.club/login to view your edge node
```

Replace `{placeholders}` with actual detected values.

**That's it. Installation complete. The user provided 2 API keys. Everything else was automated.**

---

## Appendix A: Manual MCP Config Injection

If `python3 -m edge.installer config` is unavailable, manually add these entries:

### Hermes (`~/.hermes/config.yaml`)
```yaml
mcp_servers:
  clawshell-edge:
    command: python3
    args: ["-m", "edge.mcp.edge_server"]
    cwd: "~/.clawshell"
    enabled: true
  clawshell-memory:
    command: python3
    args: ["-m", "edge.mcp.memory_server"]
    cwd: "~/.clawshell"
    enabled: true
```

### Wukong (`mcpServerConfig.json`)
```json
{
  "name": "clawshell-edge",
  "type": "stdio",
  "command": "python3",
  "args": ["-m", "edge.mcp.edge_server"],
  "cwd": "/home/user/.clawshell",
  "isActive": true
}
```

---

## Appendix B: Troubleshooting

| Problem | Action |
|---------|--------|
| `git clone` timeout | Retry once. If persistent, tell user to check GitHub access |
| `pip install` fails | Try `pip install --user`. If still fails, report to user |
| `import mempalace` fails | Not critical. Proceed. Memory sync works via MemOS Cloud alone |
| `curl cloud healthcheck` fails | CloudHub may be restarting. Wait 30s and retry. If persistent, report |
| Config injection skipped for an agent | Agent config file may have non-standard format. Tell user which agent needs manual config |
| Wukong config not found | Wukong may be installed on Windows host while agent runs in WSL. Use the Windows path |
