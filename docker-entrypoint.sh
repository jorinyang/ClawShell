#!/usr/bin/env bash
# ── ClawShell Edge Docker Entrypoint ──
set -e

CLAWSHELL_HOME="/root/.clawshell"
cd "$CLAWSHELL_HOME"

# ── Init ──
init() {
    echo "[clawshell-edge] Initializing..."
    if [ ! -f .env ]; then
        echo "[clawshell-edge] WARNING: .env not found. Create one with:"
        echo "  CLAWSHELL_CLOUD_URL=http://47.239.71.174:8000"
        echo "  DEEPSEEK_API_KEY=sk-xxx"
        echo "  MEMOS_API_KEY=mpg-xxx"
    fi
    # Auto-detect and inject MCP config into mounted agent configs
    python3 -m edge.installer config 2>/dev/null || true
    # Run self-check
    python3 -m edge.installer check 2>/dev/null || true
}

# ── Daemon mode (default) ──
run_daemon() {
    init
    echo "[clawshell-edge] Starting SyncDaemon..."
    exec python3 -m edge.sync.sync_daemon
}

# ── MCP mode ──
run_mcp() {
    init
    echo "[clawshell-edge] Starting MCP Edge Server..."
    exec python3 -m edge.mcp.edge_server
}

# ── Shell ──
run_shell() {
    init
    exec /bin/bash
}

# ── Install mode (re-run installer) ──
run_install() {
    exec python3 -m edge.installer install --non-interactive
}

# ── Dispatch ──
case "${1:-daemon}" in
    daemon)   run_daemon ;;
    mcp)      run_mcp ;;
    shell)    run_shell ;;
    install)  run_install ;;
    check)    exec python3 -m edge.installer check ;;
    detect)   exec python3 -m edge.installer detect ;;
    *)        exec "$@" ;;
esac
