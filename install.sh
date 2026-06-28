#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# ClawShell Local — One-Command Installer (Linux / macOS / WSL)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/jorinyang/ClawShell/main/install.sh | bash
#
# After install:
#   clawshell-local                 # Start API + Web UI → opens browser
#   clawshell-local --web-only      # Just the web UI
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

CLAWSHELL_HOME="${CLAWSHELL_HOME:-$HOME/.clawshell}"
REPO_URL="https://github.com/jorinyang/ClawShell.git"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[clawshell]${NC} $1"; }
warn() { echo -e "${YELLOW}[clawshell]${NC} $1"; }
err()  { echo -e "${RED}[clawshell]${NC} $1"; }

# ── OS Detection ────────────────────────────────────────────────
OS="linux"
case "$(uname -s)" in
    Darwin) OS="macos" ;;
    Linux)  OS="linux" ;;
    MINGW*|MSYS*) OS="windows" ;;
esac

log "Detected OS: $OS"

# ── Check/Install Prerequisites ─────────────────────────────────
check_python() {
    if command -v python3 &>/dev/null; then
        if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
            log "Python 3.10+ found: $(python3 --version)"
            return 0
        fi
    fi
    warn "Python 3.10+ required. Installing..."
    if command -v apt &>/dev/null; then
        sudo apt update -qq && sudo apt install -y python3 python3-pip python3-venv
    elif command -v brew &>/dev/null; then
        brew install python@3.12
    elif command -v yum &>/dev/null; then
        sudo yum install -y python3 python3-pip
    else
        err "Cannot install Python. Please install Python 3.10+ manually: https://python.org"
        exit 1
    fi
}

check_git() {
    if command -v git &>/dev/null; then
        log "Git found: $(git --version)"
        return 0
    fi
    warn "Git required. Installing..."
    if command -v apt &>/dev/null; then
        sudo apt install -y git
    elif command -v brew &>/dev/null; then
        brew install git
    else
        err "Cannot install Git. Please install Git manually: https://git-scm.com"
        exit 1
    fi
}

check_node() {
    if command -v node &>/dev/null; then
        log "Node.js found: $(node --version)"
        return 0
    fi
    warn "Node.js not found. Web UI requires Node.js."
    warn "Install from: https://nodejs.org (LTS recommended)"
    warn "Or use --api-only mode: clawshell-local --api-only"
    return 1
}

# ── Clone Repository ────────────────────────────────────────────
clone_repo() {
    if [ -d "$CLAWSHELL_HOME/.git" ]; then
        log "Repository exists, updating..."
        cd "$CLAWSHELL_HOME" && git pull --ff-only origin main 2>/dev/null || true
    else
        log "Cloning ClawShell..."
        mkdir -p "$CLAWSHELL_HOME"
        git clone "$REPO_URL" "$CLAWSHELL_HOME"
    fi
}

# ── Install Python Package ──────────────────────────────────────
install_package() {
    log "Installing Python package..."
    cd "$CLAWSHELL_HOME"
    python3 -m pip install --quiet -e . 2>/dev/null || \
    python3 -m pip install --user --quiet -e . 2>/dev/null || \
    { warn "pip install failed. Trying with --break-system-packages..."; \
      python3 -m pip install --break-system-packages --quiet -e . 2>/dev/null; }
    log "Python package installed."
}

# ── Install Web Dependencies ─────────────────────────────────────
install_web_deps() {
    if ! command -v node &>/dev/null; then
        warn "Skipping web deps (no Node.js)"
        return
    fi
    local web_dir="$CLAWSHELL_HOME/web"
    if [ ! -f "$web_dir/package.json" ]; then
        warn "web/package.json not found, skipping"
        return
    fi
    log "Installing web dependencies (npm install)..."
    cd "$web_dir"
    if [ ! -d "node_modules" ]; then
        npm install --silent 2>/dev/null || npm install 2>/dev/null
    fi

    # Build Next.js for production
    if [ -d "node_modules/.bin" ]; then
        log "Building Next.js frontend..."
        npx next build 2>/dev/null && log "Next.js build complete."
    fi
}

# ── Main ─────────────────────────────────────────────────────────
log ""
log "========================================="
log "  ClawShell Local v3.0 — Installer"
log "========================================="
log ""

check_python
check_git
clone_repo
install_package

# Check Node.js (optional)
NODE_OK=0
check_node && NODE_OK=1 || true

install_web_deps

# ── Done ─────────────────────────────────────────────────────────
log ""
log "========================================="
log "  Installation Complete!"
log ""
log "  Location: $CLAWSHELL_HOME"
log ""

if [ $NODE_OK -eq 1 ]; then
    log "  Quick Start:"
    echo "    clawshell-local              # Start API + Web UI → browser opens"
    echo "    clawshell-local --web-only   # Just the web interface"
    echo "    clawshell-local --api-only   # Just the API server"
else
    log "  Quick Start (API only, no Node.js):"
    echo "    clawshell-local --api-only   # Start local API on :8000"
    echo ""
    warn "  Install Node.js for the full Web UI experience."
    warn "  https://nodejs.org"
fi

echo ""
log "  The browser will open http://localhost:3456/login"
log "  Register a new account or login to get started."
echo ""
