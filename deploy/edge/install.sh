#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ClawShell Edge — One-line installer for Linux / macOS / WSL
#
# Usage:
#   curl -sSL https://clawshell.club/install.sh | bash
#   # or
#   bash install.sh
#
# Features:
#   - Auto-detect OS (Linux/macOS/WSL)
#   - Check python3/pip
#   - Clone repo to ~/.clawshell
#   - Install with pip install -e .[edge]
#   - Interactive: Cloud URL, Account ID, Password, Node Name
#   - Auto-login, start SyncDaemon, show status
# ═══════════════════════════════════════════════════════════════════
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}🦀 ClawShell 2.0 Edge Brain Installer${NC}"
echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo ""

# ── Detect OS ───────────────────────────────────────────
detect_os() {
    OS_TYPE="unknown"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if grep -qi microsoft /proc/version 2>/dev/null; then
            OS_TYPE="wsl"
            echo -e "  ${BLUE}OS:${NC} Windows Subsystem for Linux (WSL)"
        else
            OS_TYPE="linux"
            echo -e "  ${BLUE}OS:${NC} Linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS_TYPE="macos"
        echo -e "  ${BLUE}OS:${NC} macOS"
    else
        echo -e "  ${YELLOW}OS:${NC} Unknown ($OSTYPE)"
    fi
}

# ── Check Python ────────────────────────────────────────
check_python() {
    PYTHON=""
    if command -v python3 &>/dev/null; then
        PYTHON="python3"
    elif command -v python &>/dev/null; then
        PYTHON="python"
    else
        echo -e "  ${RED}❌ Python 3 not found!${NC}"
        echo "  Please install Python 3.8+ and try again."
        echo ""
        if [[ "$OS_TYPE" == "linux" ]] || [[ "$OS_TYPE" == "wsl" ]]; then
            echo "  Ubuntu/Debian:  sudo apt install python3 python3-pip python3-venv"
            echo "  Fedora/RHEL:    sudo dnf install python3 python3-pip"
        elif [[ "$OS_TYPE" == "macos" ]]; then
            echo "  brew install python3"
        fi
        exit 1
    fi

    PY_VERSION=$($PYTHON --version 2>&1)
    echo -e "  ${BLUE}Python:${NC} $PY_VERSION"

    # Check pip
    if ! $PYTHON -m pip --version &>/dev/null; then
        echo -e "  ${RED}❌ pip not found!${NC}"
        echo "  Install with: $PYTHON -m ensurepip --upgrade"
        exit 1
    fi
    echo -e "  ${BLUE}pip:${NC} $($PYTHON -m pip --version | cut -d' ' -f1-2)"
}

# ── Install ClawShell ───────────────────────────────────
install_clawshell() {
    INSTALL_DIR="$HOME/.clawshell"

    echo ""
    echo -e "${CYAN}📦 Installing ClawShell...${NC}"

    if [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/setup.py" ]; then
        echo -e "  ${GREEN}Found existing installation at $INSTALL_DIR${NC}"
        echo "  Updating..."
        cd "$INSTALL_DIR"
        $PYTHON -m pip install -e ".[edge]" --quiet 2>/dev/null || \
        $PYTHON -m pip install -e . --quiet 2>/dev/null || \
        echo -e "  ${YELLOW}⚠️  pip install editable mode failed, trying direct install...${NC}"
    elif [ -d "/tmp/clawshell2-build" ]; then
        echo "  Installing from local build..."
        $PYTHON -m pip install -e "/tmp/clawshell2-build[edge]" --quiet 2>/dev/null || \
        $PYTHON -m pip install -e /tmp/clawshell2-build --quiet
    else
        # Clone repo
        echo "  Cloning repository..."
        if [ -d "$INSTALL_DIR" ]; then
            cd "$INSTALL_DIR"
            git pull --quiet 2>/dev/null || true
        else
            git clone --depth 1 https://github.com/jorinyang/ClawShell.git "$INSTALL_DIR" 2>/dev/null || {
                echo -e "  ${YELLOW}⚠️  Git clone failed. Creating minimal install...${NC}"
                mkdir -p "$INSTALL_DIR"
            }
        fi
        cd "$INSTALL_DIR"
        $PYTHON -m pip install -e ".[edge]" --quiet 2>/dev/null || \
        $PYTHON -m pip install -e . --quiet 2>/dev/null || \
        echo -e "  ${YELLOW}⚠️  pip install failed. You may need to install manually.${NC}"
    fi

    echo -e "  ${GREEN}✅ ClawShell installed${NC}"
}

# ── Interactive Configuration ───────────────────────────
interactive_config() {
    echo ""
    echo -e "${CYAN}⚙️  Configuration${NC}"
    echo ""

    # Cloud URL
    DEFAULT_URL="https://clawshell.club"
    read -p "  Cloud URL [$DEFAULT_URL]: " CLOUD_URL
    CLOUD_URL="${CLOUD_URL:-$DEFAULT_URL}"

    # Account ID
    echo ""
    read -p "  Account ID: " ACCOUNT_ID
    if [ -z "$ACCOUNT_ID" ]; then
        echo -e "  ${RED}Account ID is required.${NC}"
        exit 1
    fi

    # Password (hidden)
    echo ""
    read -s -p "  Password: " PASSWORD
    echo ""
    if [ -z "$PASSWORD" ]; then
        echo -e "  ${RED}Password is required.${NC}"
        exit 1
    fi

    # Node Name
    DEFAULT_NAME="${HOSTNAME:-clawshell-edge}"
    echo ""
    read -p "  Node Name [$DEFAULT_NAME]: " NODE_NAME
    NODE_NAME="${NODE_NAME:-$DEFAULT_NAME}"
}

# ── Login ───────────────────────────────────────────────
do_login() {
    echo ""
    echo -e "${CYAN}🔐 Logging in...${NC}"

    # Try using clawshell CLI
    if command -v clawshell &>/dev/null; then
        clawshell login \
            --cloud-url "$CLOUD_URL" \
            --account-id "$ACCOUNT_ID" \
            --password "$PASSWORD" \
            --node-name "$NODE_NAME" 2>/dev/null && return 0
    fi

    # Fallback: direct Python
    $PYTHON -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.clawshell'))
from edge.auth.client import AuthClient
from edge.wizard.config_wizard import ConfigWizard

wizard = ConfigWizard()
config = wizard.load_config()
config['cloud_url'] = '$CLOUD_URL'
config['node_name'] = '$NODE_NAME'
wizard.save_config(config)

client = AuthClient('$CLOUD_URL')
result = client.login('$ACCOUNT_ID', '$PASSWORD')

if result.get('success'):
    wizard.save_session(result['token'], result['user'])
    config['account_id'] = '$ACCOUNT_ID'
    wizard.save_config(config)
    user = result['user']
    print(f'  ✅ Logged in as: {user.get(\"display_name\", \"$ACCOUNT_ID\")}')
else:
    error = result.get('error', 'Login failed')
    print(f'  ❌ {error}')
    sys.exit(1)
" 2>&1 || {
        echo -e "  ${RED}❌ Login failed. Please run 'clawshell login' manually.${NC}"
        return 1
    }
}

# ── Start Daemon ────────────────────────────────────────
do_start() {
    echo ""
    echo -e "${CYAN}🚀 Starting Edge Sync Daemon...${NC}"

    # Start daemon in background
    if command -v clawshell &>/dev/null; then
        nohup clawshell start > ~/.clawshell-edge/daemon.log 2>&1 &
        DAEMON_PID=$!
        echo -e "  ${GREEN}✅ Daemon started (PID: $DAEMON_PID)${NC}"
    else
        nohup $PYTHON -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.clawshell'))
from edge.wizard.config_wizard import ConfigWizard
from edge.sync.daemon import EdgeSyncDaemon
wizard = ConfigWizard()
config = wizard.load_config()
session = wizard.load_session()
token = session.get('token', '') or config.get('edge_token', '')
daemon = EdgeSyncDaemon(
    cloud_url=config['cloud_url'],
    edge_token=token,
    edge_id=config.get('node_id', ''),
)
daemon.start()
import time
while True:
    time.sleep(60)
" > ~/.clawshell-edge/daemon.log 2>&1 &
        DAEMON_PID=$!
        echo -e "  ${GREEN}✅ Daemon started (PID: $DAEMON_PID)${NC}"
    fi
}

# ── Show Status ─────────────────────────────────────────
do_status() {
    echo ""
    echo -e "${CYAN}📊 Status${NC}"

    if command -v clawshell &>/dev/null; then
        clawshell status 2>/dev/null || echo "  (run 'clawshell status' for details)"
    else
        $PYTHON -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.clawshell'))
from edge.wizard.config_wizard import ConfigWizard
from edge.auth.credential_store import LocalCredentialStore

wizard = ConfigWizard()
config = wizard.load_config()
session = wizard.load_session()

print(f'  Node: {config.get(\"node_name\", config.get(\"node_id\", \"unknown\"))}')
print(f'  Cloud: {config.get(\"cloud_url\", \"not set\")}')
if session.get('token'):
    user = session.get('user', {})
    print(f'  Auth: ✅ {user.get(\"display_name\", user.get(\"account_id\", \"unknown\"))}')
else:
    print('  Auth: ❌ Not logged in')

try:
    store = LocalCredentialStore()
    s = store.summary()
    print(f'  Credentials: {s[\"user_credential_count\"]} user, {s[\"shared_credential_count\"]} shared')
except: pass
" 2>/dev/null || echo "  (run 'clawshell status' for details)"
    fi
}

# ── Main ────────────────────────────────────────────────
main() {
    detect_os
    check_python
    install_clawshell
    interactive_config
    do_login
    do_start

    sleep 2
    do_status

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ ClawShell Edge installed and running!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    echo ""
    echo "  Commands:"
    echo "    clawshell status          # Show status"
    echo "    clawshell sync            # Sync credentials"
    echo "    clawshell dashboard       # Credential dashboard"
    echo "    clawshell change-password # Change password"
    echo "    clawshell stop            # Stop daemon"
    echo "    clawshell start           # Start daemon"
    echo ""
}

main "$@"
