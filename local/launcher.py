#!/usr/bin/env python3
"""ClawShell Local — Unified Launcher (v3.0.0)

Single command to start the ClawShell Local experience:
  clawshell-local              # Start API + Web UI → open browser
  clawshell-local --web-only   # Skip backend, just web UI
  clawshell-local --api-only   # Skip web UI, just API
  clawshell-local --port 9000  # Custom API port

After install, the user just runs `clawshell-local` and a browser opens
to http://localhost:3456 with the login page ready.
"""

import sys
import os
import subprocess
import time
import json
import signal
import threading
import platform as pf
from pathlib import Path

HOME = Path.home()
INSTALL_DIR = Path(__file__).resolve().parent
WEB_DIR = INSTALL_DIR / "web"
LOCAL_CONFIG_DIR = HOME / ".clawshell"
CONFIG_FILE = LOCAL_CONFIG_DIR / "config.json"

API_HOST = os.environ.get("CLAWSHELL_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("CLAWSHELL_API_PORT", "8000"))
WEB_PORT = int(os.environ.get("CLAWSHELL_WEB_PORT", "3456"))


def ensure_config():
    LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    cfg = {
        "cloud_url": os.environ.get("CLAWSHELL_CLOUD_URL", f"http://{API_HOST}:{API_PORT}"),
        "api_port": API_PORT,
        "web_port": WEB_PORT,
        "version": "3.0.0",
        "first_run": True,
    }
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    return cfg


def check_node():
    """Check if Node.js is available."""
    import shutil
    if shutil.which("node"):
        return True
    # Try common paths on Windows
    for p in [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
    ]:
        if os.path.exists(p):
            return True
    return False


def check_python():
    return True  # we're already running


def start_api_server(port):
    """Start the Cloud Hub FastAPI server."""
    print(f"[clawshell] Starting API server on http://{API_HOST}:{port} ...")
    env = os.environ.copy()
    env["CLAWSHELL_API_PORT"] = str(port)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "cloud.main:create_app", "--factory",
         "--host", API_HOST, "--port", str(port), "--log-level", "warning"],
        cwd=str(INSTALL_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc


def start_web_server(port, api_url):
    """Start the Next.js web server."""
    print(f"[clawshell] Starting Web UI on http://localhost:{port} ...")
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["NEXT_PUBLIC_API_URL"] = api_url
    env["NODE_ENV"] = os.environ.get("NODE_ENV", "production")

    # Try standalone build first, fall back to dev
    standalone = WEB_DIR / ".next" / "standalone" / "server.js"
    start_script = standalone if standalone.exists() else None

    if start_script:
        proc = subprocess.Popen(
            ["node", str(start_script)],
            cwd=str(WEB_DIR / ".next" / "standalone"),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    else:
        # Fall back to next dev
        print("[clawshell] No production build found, using dev mode...")
        proc = subprocess.Popen(
            ["npx", "next", "dev", "-p", str(port)],
            cwd=str(WEB_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    return proc


def wait_for_port(port, timeout=30):
    """Wait for a port to become available."""
    import socket
    for i in range(timeout):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1)
            s.close()
            return True
        except (OSError, ConnectionRefusedError):
            time.sleep(1)
    return False


def open_browser(url):
    """Open browser to the given URL."""
    import webbrowser
    print(f"[clawshell] Opening browser: {url}")
    webbrowser.open(url)


def print_banner(api_port, web_port, api_url):
    print()
    print("=" * 56)
    print("  ClawShell Local v3.0.0")
    print("  Pluggable Exoskeleton Enhancement Layer")
    print()
    print(f"  API:     http://{API_HOST}:{api_port}")
    print(f"  Web UI:  http://localhost:{web_port}")
    print(f"  Login:   http://localhost:{web_port}/login")
    print("=" * 56)
    print()
    print("  Press Ctrl+C to stop all services.")
    print()


def main():
    args = sys.argv[1:]
    api_port = API_PORT
    web_port = WEB_PORT
    web_only = "--web-only" in args or "-w" in args
    api_only = "--api-only" in args or "-a" in args
    no_browser = "--no-browser" in args or "-n" in args

    for i, arg in enumerate(args):
        if arg in ("--port", "-p") and i + 1 < len(args):
            api_port = int(args[i + 1])
            web_port = api_port + 2656  # offset for web port
        if arg == "--web-port" and i + 1 < len(args):
            web_port = int(args[i + 1])

    cfg = ensure_config()
    api_url = f"http://{API_HOST}:{api_port}"

    procs = []

    # Start API
    if not web_only:
        api_proc = start_api_server(api_port)
        procs.append(("API", api_proc))
        print("[clawshell] Waiting for API server...")
        if not wait_for_port(api_port, timeout=20):
            print("[clawshell] WARNING: API may not be ready yet")

    # Start Web
    if not api_only:
        if not check_node():
            print("[clawshell] WARNING: Node.js not found. Web UI won't start.")
            print("            Install Node.js: https://nodejs.org")
        else:
            web_proc = start_web_server(web_port, api_url)
            procs.append(("Web", web_proc))
            print("[clawshell] Waiting for Web UI...")
            if not wait_for_port(web_port, timeout=30):
                print("[clawshell] WARNING: Web UI may not be ready yet")

    print_banner(api_port, web_port, api_url)

    if not no_browser and not api_only and check_node():
        time.sleep(1)
        open_browser(f"http://localhost:{web_port}/login")

    # Keep running
    def shutdown(signum=None, frame=None):
        print("\n[clawshell] Shutting down...")
        for name, proc in procs:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("[clawshell] Stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        for _, proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
