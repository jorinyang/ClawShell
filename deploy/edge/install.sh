#!/bin/bash
# ClawShell Edge — One-line installer for Linux/macOS/WSL
set -e

echo "🦀 ClawShell 2.0 Edge Brain Installer"
echo "======================================"

# Detect Python
PYTHON=$(which python3 || which python)
echo "Python: $($PYTHON --version)"

# Install dependencies
echo "Installing dependencies..."
$PYTHON -m pip install --quiet psutil

# Install ClawShell
if [ -d "/tmp/clawshell2-build" ]; then
    echo "Installing from local build..."
    $PYTHON -m pip install -e /tmp/clawshell2-build
else
    echo "Installing from GitHub..."
    $PYTHON -m pip install git+https://github.com/jorinyang/ClawShell.git
fi

# Detect environment
echo ""
echo "Detecting environment..."
$PYTHON -c "
from edge.detector import detect_environment
import json
env = detect_environment()
print(f'  OS: {env[\"system\"][\"os_type\"]}')
for fw in env['frameworks']:
    print(f'  Framework: {fw[\"name\"]} (v{fw[\"version\"]})')
"

echo ""
echo "✅ ClawShell Edge installed!"
echo ""
echo "Next steps:"
echo "  1. Configure:   clawshell-edge config --cloud-url https://your-cloud:8000"
echo "  2. Start sync:  clawshell-edge start"
echo "  3. Check status: clawshell-edge status"
