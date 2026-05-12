"""Edge Brain CLI."""

import argparse
import sys
import os


def cmd_install(args):
    """Install ClawShell Edge on this machine."""
    print("🔍 Detecting environment...")
    from edge.detector import detect_environment
    env = detect_environment()
    print(f"  OS: {env['system']['os_type']} ({env['system']['os_version']})")
    print(f"  Frameworks: {env['total_frameworks']} detected")
    for fw in env['frameworks']:
        print(f"    - {fw['name']} (confidence: {fw['confidence']})")

    print("\n📦 Installing ecosystem components...")
    from edge.ecosystem.installer import EcosystemInstaller
    ei = EcosystemInstaller()
    results = ei.install_selected(["psutil"])
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {name}")

    print("\n✅ ClawShell Edge installed successfully!")
    print("   Run 'clawshell-edge start' to begin sync with Cloud Hub.")


def cmd_start(args):
    """Start the Edge Sync Daemon."""
    from edge.wizard.config_wizard import ConfigWizard
    wizard = ConfigWizard()
    config = wizard.load_config()

    print(f"🔗 Connecting to Cloud Hub: {config['cloud_url']}")

    if not wizard.test_connection(config["cloud_url"], config.get("edge_token")):
        print("⚠️  Cloud Hub unreachable — will operate in autonomous mode")

    from edge.sync.daemon import EdgeSyncDaemon
    daemon = EdgeSyncDaemon(
        cloud_url=config["cloud_url"],
        edge_token=config.get("edge_token", ""),
        edge_id=config.get("node_id", ""),
    )
    daemon.start()

    print(f"✅ Edge Sync Daemon started (node: {config.get('node_id', 'unknown')})")
    print("   Running in background. Use 'clawshell-edge status' to check.")


def cmd_stop(args):
    """Stop the Edge Sync Daemon."""
    print("🛑 Stopping ClawShell Edge...")
    print("   Daemon will exit on next cycle.")


def cmd_status(args):
    """Show Edge status."""
    from edge.wizard.config_wizard import ConfigWizard
    wizard = ConfigWizard()
    config = wizard.load_config()

    print("📊 ClawShell Edge Status")
    print(f"  Node ID: {config.get('node_id', 'not configured')}")
    print(f"  Cloud URL: {config.get('cloud_url', 'not configured')}")

    connection = wizard.test_connection(
        config["cloud_url"], config.get("edge_token", "")
    )
    if connection.get("success"):
        print(f"  Cloud: ✅ Connected (v{connection.get('version', '?')})")
    else:
        print(f"  Cloud: ❌ {connection.get('error', 'Unreachable')}")

    from edge.detector import detect_environment
    env = detect_environment()
    print(f"  Frameworks detected: {env['total_frameworks']}")
    for fw in env['frameworks']:
        print(f"    - {fw['name']}: {'✅' if fw['confidence'] > 0.8 else '⚠️'} (conf={fw['confidence']})")

    from edge.ide_bridge import detect_ide_tools
    ides = detect_ide_tools()
    print(f"  IDE tools detected: {len(ides)}")
    for ide in ides:
        print(f"    - {ide}")

    from edge.ecosystem.installer import EcosystemInstaller
    ei = EcosystemInstaller()
    eco = ei.get_status()
    print(f"  Ecosystem: {eco['installed']}/{eco['total']} components installed")


def cmd_config(args):
    """Configure Edge settings."""
    from edge.wizard.config_wizard import ConfigWizard
    wizard = ConfigWizard()
    config = wizard.load_config()

    if args.cloud_url:
        config["cloud_url"] = args.cloud_url
    if args.edge_token:
        config["edge_token"] = args.edge_token
    if args.node_name:
        config["node_name"] = args.node_name

    wizard.save_config(config)
    print("✅ Configuration saved")
    print(f"   Cloud URL: {config['cloud_url']}")
    print(f"   Node ID: {config['node_id']}")


def main():
    parser = argparse.ArgumentParser(description="ClawShell Edge Brain CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("install", help="Install ClawShell Edge")
    sub.add_parser("start", help="Start Edge Sync Daemon")
    sub.add_parser("stop", help="Stop Edge Sync Daemon")
    sub.add_parser("status", help="Show Edge status")

    config_parser = sub.add_parser("config", help="Configure Edge")
    config_parser.add_argument("--cloud-url", help="Cloud Hub URL")
    config_parser.add_argument("--edge-token", help="Edge auth token")
    config_parser.add_argument("--node-name", help="Node display name")

    args = parser.parse_args()

    commands = {
        "install": cmd_install,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "config": cmd_config,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
