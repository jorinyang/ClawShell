#!/usr/bin/env python3
"""ClawShell Local — Desktop GUI Installer (v3.0.0)

Produces a distributable package for the ClawShell Local desktop application.

Usage:
  python scripts/build_local_gui.py              # Build for current platform
  python scripts/build_local_gui.py --platform win    # Windows NSIS installer
  python scripts/build_local_gui.py --platform mac    # macOS DMG
  python scripts/build_local_gui.py --platform linux  # Linux AppImage + deb
"""

import sys
import os
import subprocess
import shutil
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


def check_prerequisites():
    """Verify Node.js and npm are available."""
    issues = []
    if shutil.which("node") is None:
        issues.append("Node.js not found")
    if shutil.which("npm") is None and shutil.which("npx") is None:
        issues.append("npm not found")
    if issues:
        for i in issues:
            print(f"  [ERROR] {i}")
        sys.exit(1)
    print(f"  [OK] Node.js {subprocess.check_output(['node', '--version']).decode().strip()}")


def install_deps():
    """Install npm dependencies."""
    print("[1/5] Installing npm dependencies...")
    subprocess.run(["npm", "install"], cwd=str(WEB_DIR), check=True)
    print("  Done.")


def build_nextjs():
    """Build Next.js for production."""
    print("[2/5] Building Next.js (standalone mode)...")
    subprocess.run(["npx", "next", "build"], cwd=str(WEB_DIR), check=True)
    print("  Done.")


def install_electron_deps():
    """Install electron-builder and dependencies."""
    print("[3/5] Installing Electron + electron-builder...")
    subprocess.run(
        ["npm", "install", "--save-dev", "electron", "electron-builder", "concurrently", "wait-on"],
        cwd=str(WEB_DIR),
        check=True,
    )
    print("  Done.")


def package_app(platform=None):
    """Package the Electron app for the target platform."""
    if platform is None:
        if sys.platform == "win32":
            platform = "win"
        elif sys.platform == "darwin":
            platform = "mac"
        else:
            platform = "linux"

    print(f"[4/5] Packaging for {platform}...")

    target_map = {
        "win": "win",
        "mac": "mac",
        "linux": "linux",
    }

    subprocess.run(
        ["npx", "electron-builder", f"--{target_map[platform]}", "--config", "package.json"],
        cwd=str(WEB_DIR),
        check=True,
    )
    print("  Done.")


def show_output():
    """Display output artifacts."""
    print("[5/5] Build complete.")
    output_dir = WEB_DIR / "dist-electron"
    if output_dir.exists():
        print(f"\n  Output: {output_dir}")
        for f in sorted(output_dir.iterdir()):
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"    {f.name}  ({size_mb:.1f} MB)")
    else:
        print("\n  No output found (check for errors above).")


def main():
    platform = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--platform" and i + 1 < len(args):
            platform = args[i + 1]

    print("=" * 56)
    print("  ClawShell Local — Desktop GUI Builder v3.0.0")
    print(f"  Platform: {platform or 'current'}")
    print("=" * 56)
    print()

    check_prerequisites()
    install_deps()
    build_nextjs()
    install_electron_deps()
    package_app(platform)
    show_output()

    print("\n  To run the packaged app:")
    if platform == "win" or (platform is None and sys.platform == "win32"):
        print("    Open dist-electron/ClawShell Local Setup *.exe")
    elif platform == "mac" or (platform is None and sys.platform == "darwin"):
        print("    Open dist-electron/ClawShell Local-*.dmg")
    elif platform == "linux" or (platform is None and not sys.platform.startswith("win")):
        print("    ./dist-electron/ClawShell Local-*.AppImage")
    print()


if __name__ == "__main__":
    main()
