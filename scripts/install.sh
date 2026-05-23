#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# ClawShell Edge — Universal Installer (Agent & Human)
#
# Human mode: curl -fsSL https://clawshell.club/install.sh | bash
# Agent mode: curl -fsSL https://clawshell.club/install.sh | bash -s -- --agent
#
# Agent mode: silent, JSON progress on stdout, semantic exit codes
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

CLAWSHELL_HOME="${CLAWSHELL_HOME:-$HOME/.clawshell}"
CLOUD_URL="${CLOUD_URL:-http://47.239.71.174:8000}"
AGENT_MODE=0
SKIP_CREDENTIALS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)   CLAWSHELL_HOME="$2"; shift 2 ;;
        --agent) AGENT_MODE=1; shift ;;
        --skip-credentials) SKIP_CREDENTIALS=1; shift ;;
        --help)  echo "Usage: install.sh [--dir PATH] [--agent] [--skip-credentials]"; exit 0 ;;
        *)       echo "{\"error\":\"unknown arg: $1\"}"; exit 2 ;;
    esac
done

# ── JSON progress emitter (agent mode) ──────────────────────────
json_progress() {
    local phase="$1" status="$2" detail="${3:-}"
    if [ "$AGENT_MODE" -eq 1 ]; then
        printf '{"phase":"%s","status":"%s","detail":"%s"}\n' "$phase" "$status" "$detail"
    fi
}

# ── OS Detection ────────────────────────────────────────────────
detect_os() {
    case "$(uname -s)" in
        Darwin)  echo "macos";;
        Linux)
            if grep -qi microsoft /proc/version 2>/dev/null; then echo "wsl"; else echo "linux"; fi;;
        *)       echo "unknown";;
    esac
}

OS=$(detect_os)
json_progress "detect" "ok" "os=$OS|home=$CLAWSHELL_HOME"

# ── Python check ────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    if python3 -c 'import sys; exit(0 if sys.version_info >= (3,10) else 1)'; then
        PY_VER=$(python3 -c 'import sys; print(".".join(map(str,sys.version_info[:2])))')
        json_progress "python" "ok" "version=$PY_VER"
    else
        json_progress "python" "fail" "version<$PY_VER needs 3.10+"
        exit 10
    fi
else
    json_progress "python" "fail" "not found"
    exit 10
fi

# ── Git check ───────────────────────────────────────────────────
if command -v git &>/dev/null; then
    json_progress "git" "ok" "found"
else
    json_progress "git" "fail" "not found"
    exit 11
fi

# ── Credentials (human only if not agent, or from env) ──────────
CRED_RETRIES=0; MAX_CRED_RETRIES=3

if [ "$AGENT_MODE" -eq 0 ] && [ "$SKIP_CREDENTIALS" -eq 0 ]; then
    echo ""
    echo "Before installing, please complete:"
    echo "  1. Register at https://memos.cloud → get API Key (mpg-xxx)"
    echo "  2. Get LLM Key: https://platform.deepseek.com/api_keys"
    echo "  3. GitHub access: https://github.com/jorinyang/ClawShell"
    echo ""
    read -p "Ready to proceed? [Y/n]: " CONFIRM
    case "$CONFIRM" in [nN]*) echo "Aborted."; exit 1;; esac
fi

# MemOS key from env or pass
if [ -n "${MEMOS_API_KEY:-}" ]; then
    json_progress "credentials" "ok" "memos_key=set"
else
    json_progress "credentials" "warn" "memos_key=missing"
fi

if [ -n "${DEEPSEEK_API_KEY:-}${OPENAI_API_KEY:-}" ]; then
    json_progress "credentials" "ok" "llm_key=set"
else
    json_progress "credentials" "warn" "llm_key=missing"
fi

# If agent mode and missing keys, escalate to human
if [ "$AGENT_MODE" -eq 1 ]; then
    if [ -z "${MEMOS_API_KEY:-}" ] || { [ -z "${DEEPSEEK_API_KEY:-}" ] && [ -z "${OPENAI_API_KEY:-}" ]; }; then
        json_progress "credentials" "human_required" "One or more API keys missing in agent mode"
        echo ""
        echo "⚠️  Agent cannot proceed — API keys are required."
        echo "   Please set environment variables and retry:"
        echo "   export MEMOS_API_KEY=mpg-xxx"
        echo "   export DEEPSEEK_API_KEY=sk-xxx"
        echo "   Then re-run: bash install.sh --agent"
        exit 21
    fi
fi

# ── Clone ClawShell ─────────────────────────────────────────────
clone_repo() {
    if [ -d "$CLAWSHELL_HOME/.git" ]; then
        json_progress "clone" "progress" "updating"
        (cd "$CLAWSHELL_HOME" && git pull --ff-only 2>/dev/null) && return 0
        json_progress "clone" "warn" "update failed, using existing"
        return 0
    fi
    json_progress "clone" "progress" "cloning"
    if git clone https://github.com/jorinyang/ClawShell.git "$CLAWSHELL_HOME" 2>/dev/null; then
        json_progress "clone" "ok" "cloned"
        return 0
    fi
    # Retry once
    sleep 2
    if git clone https://github.com/jorinyang/ClawShell.git "$CLAWSHELL_HOME" 2>/dev/null; then
        json_progress "clone" "ok" "cloned (retry)"
        return 0
    fi
    json_progress "clone" "fail" "clone failed"
    return 1
}

if ! clone_repo; then
    exit 20
fi

# ── Dependencies ────────────────────────────────────────────────
json_progress "deps" "progress" "installing"
pip_ok=0
python3 -m pip install --quiet pyyaml requests aiohttp websockets 2>/dev/null && pip_ok=1
if [ $pip_ok -eq 0 ]; then
    python3 -m pip install --user --quiet pyyaml requests aiohttp websockets 2>/dev/null && pip_ok=1
fi
json_progress "deps" "$([ $pip_ok -eq 1 ] && echo ok || echo warn)" "pip=$pip_ok"

# ── Memory Plugins ──────────────────────────────────────────────
# MemPalace
if python3 -c "import mempalace" 2>/dev/null; then
    json_progress "mempalace" "ok" "already_installed"
else
    [ -d "$HOME/.mempalace" ] || git clone https://github.com/mempalace/mempalace.git "$HOME/.mempalace" 2>/dev/null || true
    (cd "$HOME/.mempalace" && python3 -m pip install --quiet -e .) 2>/dev/null || true
    if python3 -c "import mempalace" 2>/dev/null; then
        json_progress "mempalace" "ok" "installed"
    else
        json_progress "mempalace" "warn" "skipped"
    fi
fi

# MemOS Cloud Plugin
if python3 -c "import memos_local" 2>/dev/null; then
    json_progress "memos" "ok" "already_installed"
else
    python3 -m pip install --quiet memos-local-plugin 2>/dev/null || true
    if python3 -c "import memos_local" 2>/dev/null; then
        json_progress "memos" "ok" "installed"
    else
        json_progress "memos" "warn" "skipped"
    fi
fi

# ── Agent Config ────────────────────────────────────────────────
json_progress "config" "progress" "injecting"
cd "$CLAWSHELL_HOME"
python3 -m edge.installer config 2>/dev/null && cfg_ok=1 || cfg_ok=0
json_progress "config" "$([ $cfg_ok -eq 1 ] && echo ok || echo warn)" "injected=$cfg_ok"

# ── Self-Check ──────────────────────────────────────────────────
json_progress "check" "progress" "verifying"
checks_ok=0
checks_total=0
[ -d "$CLAWSHELL_HOME/edge" ] && checks_ok=$((checks_ok+1)); checks_total=$((checks_total+1))
[ -d "$CLAWSHELL_HOME/exoskeleton" ] && checks_ok=$((checks_ok+1)); checks_total=$((checks_total+1))
python3 -c "from edge.mcp.edge_server import main" 2>/dev/null && checks_ok=$((checks_ok+1)); checks_total=$((checks_total+1))
if curl -s --max-time 5 "$CLOUD_URL/health" >/dev/null 2>&1; then
    checks_ok=$((checks_ok+1)); checks_total=$((checks_total+1))
fi
json_progress "check" "$([ $checks_ok -eq $checks_total ] && echo ok || echo warn)" "passed=$checks_ok/$checks_total"

# ── .env Creation ───────────────────────────────────────────────
mkdir -p "$CLAWSHELL_HOME"
ENV_FILE="$CLAWSHELL_HOME/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << EEOF
# ClawShell Edge Configuration
CLAWSHELL_HOME=$CLAWSHELL_HOME
CLAWSHELL_CLOUD_URL=$CLOUD_URL
CLAWSHELL_NODE_ID=edge-$(hostname 2>/dev/null || echo "unknown")

# ── LLM Configuration ──────────────────────
# Provider: deepseek | openai
LLM_PROVIDER=deepseek
# Endpoint URL
LLM_ENDPOINT=https://api.deepseek.com/v1
# Model name
LLM_MODEL=deepseek-chat
# API Key (set one):
# DEEPSEEK_API_KEY=sk-xxx
# OPENAI_API_KEY=sk-xxx

# ── Memory Plugin ──────────────────────────
# MEMOS_API_KEY=mpg-xxx
EEOF
fi
json_progress "env" "ok" "created"

# ── Final Status ────────────────────────────────────────────────
if [ $checks_ok -eq $checks_total ]; then
    json_progress "done" "ok" "checks=$checks_ok/$checks_total|dir=$CLAWSHELL_HOME"
    exit 0
else
    json_progress "done" "warn" "checks=$checks_ok/$checks_total|dir=$CLAWSHELL_HOME"
    exit 0
fi
