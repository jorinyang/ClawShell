#!/usr/bin/env python3
"""ClawShell Local — Desktop Launcher (v3.0.0)

Starts both the Next.js frontend and the Electron shell.
On first run, guides the user through login/registration.

Usage:
  python -m web.launcher              # Start the desktop app
  python -m web.launcher --dev        # Development mode (separate terminals)
  python -m web.launcher --web-only   # Web frontend only (no Electron)
"""

import sys
import os
import subprocess
import time
import json
import shutil
import webbrowser
import platform
from pathlib import Path

LOCAL_HOME = Path.home() / ".clawshell"
LOCAL_CONFIG = LOCAL_HOME / "config.json"
WEB_DIR = Path(__file__).resolve().parent


def ensure_config():
    """Ensure ~/.clawshell/config.json exists with defaults."""
    LOCAL_HOME.mkdir(parents=True, exist_ok=True)
    if not LOCAL_CONFIG.exists():
        default_config = {
            "cloud_url": os.environ.get("CLAWSHELL_CLOUD_URL", "https://clawshell.club"),
            "api_port": int(os.environ.get("CLAWSHELL_CLOUD_PORT", "8000")),
            "node_id": os.environ.get("CLAWSHELL_NODE_ID", f"local-{os.uname().nodename if hasattr(os, 'uname') else 'win'}"),
            "auto_start_sync": True,
            "first_run": True,
            "version": "3.0.0",
        }
        LOCAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_CONFIG.write_text(json.dumps(default_config, indent=2, ensure_ascii=False))
        print(f"[clawshell] Config created: {LOCAL_CONFIG}")
    return json.loads(LOCAL_CONFIG.read_text())


def check_prerequisites():
    """Check required tools are available."""
    issues = []

    # Check Python
    if shutil.which("python3") is None and shutil.which("python") is None:
        issues.append("Python 3.10+ not found. Install from https://python.org")

    # Check Node.js
    if shutil.which("node") is None:
        issues.append("Node.js not found. Install from https://nodejs.org")

    # Check npm
    if shutil.which("npm") is None and shutil.which("npx") is None:
        issues.append("npm not found (comes with Node.js)")

    # Check Git
    if shutil.which("git") is None:
        issues.append("Git not found. Install from https://git-scm.com")

    if issues:
        print("[clawshell] Prerequisites check failed:")
        for i in issues:
            print(f"  - {i}")
        return False
    return True


def install_web_deps():
    """Install npm dependencies if node_modules is missing."""
    node_modules = WEB_DIR / "node_modules"
    if not node_modules.exists():
        print("[clawshell] Installing web dependencies (npm install)...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(WEB_DIR),
            check=True,
        )
        print("[clawshell] Dependencies installed.")


def start_web_server():
    """Start Next.js dev server. Returns the process."""
    install_web_deps()

    print("[clawshell] Starting web server (Next.js)...")
    proc = subprocess.Popen(
        ["npx", "next", "dev", "-p", "3456"],
        cwd=str(WEB_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


def start_electron():
    """Start Electron shell."""
    print("[clawshell] Starting Electron shell...")

    # Check if electron is in node_modules
    electron_path = WEB_DIR / "node_modules" / ".bin" / "electron"
    if os.name == "nt":
        electron_path = WEB_DIR / "node_modules" / ".bin" / "electron.cmd"

    if not electron_path.exists():
        print("[clawshell] Installing Electron...")
        subprocess.run(
            ["npm", "install", "electron", "--save-dev", "concurrently", "wait-on"],
            cwd=str(WEB_DIR),
            check=True,
        )

    proc = subprocess.Popen(
        [str(electron_path), str(WEB_DIR)],
        cwd=str(WEB_DIR),
    )
    return proc


def print_welcome(config):
    """Print welcome banner."""
    print()
    print("=" * 56)
    print("  ClawShell Local v3.0.0")
    print("  Pluggable Exoskeleton for AI Agent Frameworks")
    print()
    print(f"  Cloud Hub: {config['cloud_url']}")
    print(f"  Node ID:   {config['node_id']}")
    print(f"  Web UI:    http://localhost:3456")
    print("=" * 56)
    print()
    print("  Press Ctrl+C to stop.")
    print()


def main():
    args = sys.argv[1:]

    if not check_prerequisites():
        sys.exit(1)

    config = ensure_config()

    if "--web-only" in args:
        # Web only (no Electron)
        install_web_deps()
        print("[clawshell] Starting Next.js (port 3456)...")
        print("[clawshell] Open http://localhost:3456 in your browser")
        subprocess.run(
            ["npx", "next", "dev", "-p", "3456"],
            cwd=str(WEB_DIR),
        )
        return

    # Start web server first
    web_proc = start_web_server()

    # Wait for Next.js to be ready
    print("[clawshell] Waiting for web server...")
    import urllib.request
    max_wait = 30
    for i in range(max_wait):
        try:
            urllib.request.urlopen("http://localhost:3456", timeout=1)
            print("[clawshell] Web server ready.")
            break
        except Exception:
            time.sleep(1)
    else:
        print("[clawshell] Web server not responding, but continuing anyway.")

    print_welcome(config)

    if "--dev" in args:
        print("[clawshell] Dev mode: Web server running. Open http://localhost:3456")
        print("[clawshell] Press Ctrl+C to stop.")
        try:
            web_proc.wait()
        except KeyboardInterrupt:
            web_proc.terminate()
    else:
        # Start Electron
        electron_proc = start_electron()
        try:
            electron_proc.wait()
        except KeyboardInterrupt:
            electron_proc.terminate()
        finally:
            web_proc.terminate()


if __name__ == "__main__":
    main()
