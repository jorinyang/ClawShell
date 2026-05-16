"""Edge Brain CLI — ClawShell v2.0 with auth commands."""

import argparse
import sys
import os
import time


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
    print("   Next: clawshell login")
    print("   Then: clawshell start")


def cmd_login(args):
    """Login to ClawShell Cloud Hub."""
    from edge.wizard.config_wizard import ConfigWizard
    wizard = ConfigWizard()

    # Update cloud_url if provided
    if args.cloud_url:
        config = wizard.load_config()
        config["cloud_url"] = args.cloud_url
        wizard.save_config(config)

    # Non-interactive mode (from install script)
    if args.account_id and args.password:
        from edge.auth.client import AuthClient
        config = wizard.load_config()
        client = AuthClient(config.get("cloud_url", "http://localhost:8000"))
        result = client.login(args.account_id, args.password)
        if result.get("success"):
            wizard.save_session(result["token"], result["user"])
            config["account_id"] = args.account_id
            if args.node_name:
                config["node_name"] = args.node_name
            wizard.save_config(config)
            user = result["user"]
            print(f"✅ Logged in as: {user.get('display_name', args.account_id)}")
            if result.get("must_change_pwd"):
                print("⚠️  Password change required. Run: clawshell change-password")
            return
        else:
            error = result.get("error", "Login failed")
            print(f"❌ {error}")
            sys.exit(1)

    # Interactive mode
    try:
        wizard.interactive_login()
    except (ValueError, ConnectionError) as e:
        print(f"❌ {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)


def cmd_register(args):
    """Register a new account on ClawShell Cloud Hub."""
    from edge.wizard.config_wizard import ConfigWizard
    wizard = ConfigWizard()

    if args.cloud_url:
        config = wizard.load_config()
        config["cloud_url"] = args.cloud_url
        wizard.save_config(config)

    try:
        wizard.interactive_register()
    except (ValueError, ConnectionError) as e:
        print(f"❌ {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)


def cmd_logout(args):
    """Logout from ClawShell Cloud Hub."""
    from edge.wizard.config_wizard import ConfigWizard
    from edge.auth.client import AuthClient

    wizard = ConfigWizard()
    token = wizard.get_token()

    if token:
        config = wizard.load_config()
        client = AuthClient(config.get("cloud_url", "http://localhost:8000"))
        client.logout(token)

    wizard.clear_session()
    print("✅ Logged out successfully.")


def cmd_status(args):
    """Show Edge status including auth state."""
    from edge.wizard.config_wizard import ConfigWizard
    wizard = ConfigWizard()
    config = wizard.load_config()
    session = wizard.load_session()

    print("📊 ClawShell Edge Status")
    print(f"  Node ID: {config.get('node_id', 'not configured')}")
    print(f"  Node Name: {config.get('node_name', 'not set')}")
    print(f"  Cloud URL: {config.get('cloud_url', 'not configured')}")

    # Auth status
    if session.get("token"):
        user = session.get("user", {})
        print(f"  Auth: ✅ Logged in as {user.get('display_name', user.get('account_id', 'unknown'))}")
        print(f"    Role: {user.get('role', 'user')}")
    else:
        print("  Auth: ❌ Not logged in")

    # Connection test
    connection = wizard.test_connection(
        config["cloud_url"], config.get("edge_token", "")
    )
    if connection.get("success"):
        print(f"  Cloud: ✅ Connected (v{connection.get('version', '?')})")
    else:
        print(f"  Cloud: ❌ {connection.get('error', 'Unreachable')}")

    # Credential store summary
    try:
        from edge.auth.credential_store import LocalCredentialStore
        store = LocalCredentialStore()
        summary = store.summary()
        print(f"  Credentials: {summary['user_credential_count']} user, {summary['shared_credential_count']} shared")
        if summary['services']:
            print(f"    Services: {', '.join(summary['services'])}")
    except Exception:
        print("  Credentials: not available")

    # WebSocket client status
    try:
        from edge.auth.ws_client import CredentialWSClient
        print(f"  WebSocket: available ({'native' if hasattr(__import__('websockets', fromlist=['websockets']), 'connect') else 'polling fallback'})")
    except ImportError:
        print("  WebSocket: polling mode (install 'websockets' for real-time)")

    # Framework detection
    try:
        from edge.detector import detect_environment
        env = detect_environment()
        print(f"  Frameworks detected: {env['total_frameworks']}")
        for fw in env['frameworks']:
            print(f"    - {fw['name']}: {'✅' if fw['confidence'] > 0.8 else '⚠️'} (conf={fw['confidence']})")
    except Exception:
        pass


def cmd_start(args):
    """Start the Edge Sync Daemon."""
    from edge.wizard.config_wizard import ConfigWizard
    wizard = ConfigWizard()
    config = wizard.load_config()
    session = wizard.load_session()

    token = session.get("token", "") or config.get("edge_token", "")
    if not token:
        print("❌ Not logged in. Run 'clawshell login' first.")
        sys.exit(1)

    cloud_url = config.get("cloud_url", "http://localhost:8000")
    print(f"🔗 Connecting to Cloud Hub: {cloud_url}")

    if not wizard.test_connection(cloud_url, token).get("success"):
        print("⚠️  Cloud Hub unreachable — will operate in autonomous mode")

    from edge.sync.daemon import EdgeSyncDaemon
    daemon = EdgeSyncDaemon(
        cloud_url=cloud_url,
        edge_token=token,
        edge_id=config.get("node_id", ""),
    )
    daemon.start()

    print(f"✅ Edge Sync Daemon started (node: {config.get('node_id', 'unknown')})")
    print("   Press Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.shutdown()
        print("\n🛑 Daemon stopped.")


def cmd_stop(args):
    """Stop the Edge Sync Daemon."""
    print("🛑 Stopping ClawShell Edge...")
    print("   Daemon will exit on next cycle.")


def cmd_sync(args):
    """Manually trigger credential sync."""
    from edge.wizard.config_wizard import ConfigWizard
    from edge.auth.client import AuthClient
    from edge.auth.credential_store import LocalCredentialStore

    wizard = ConfigWizard()
    session = wizard.load_session()
    token = session.get("token", "")

    if not token:
        config = wizard.load_config()
        token = config.get("edge_token", "")
    if not token:
        print("❌ Not logged in. Run 'clawshell login' first.")
        sys.exit(1)

    config = wizard.load_config()
    cloud_url = config.get("cloud_url", "http://localhost:8000")

    print("🔄 Syncing credentials...")
    client = AuthClient(cloud_url)
    result = client.sync_credentials(token)

    if not result.get("success"):
        # Try refreshing token
        refresh = client.refresh(token)
        if refresh.get("success"):
            token = refresh["token"]
            wizard.save_session(token, session.get("user", {}))
            result = client.sync_credentials(token)

    if result.get("success"):
        store = LocalCredentialStore()
        user_creds = result.get("user_credentials", {})
        shared_creds = result.get("shared_credentials", {})

        # Flatten grouped creds into lists
        user_list = []
        for service, creds in user_creds.items():
            user_list.extend(creds)
        shared_list = []
        for service, creds in shared_creds.items():
            shared_list.extend(creds)

        store.merge_and_save(user_list)
        store.save_shared_credentials(shared_list)

        summary = store.summary()
        print(f"✅ Sync complete!")
        print(f"   User credentials: {summary['user_credential_count']}")
        print(f"   Shared credentials: {summary['shared_credential_count']}")
        print(f"   Services: {', '.join(summary['services']) if summary['services'] else 'none'}")
    else:
        error = result.get("error", "Sync failed")
        print(f"❌ {error}")
        sys.exit(1)


def cmd_dashboard(args):
    """Show credential dashboard."""
    from edge.auth.credential_store import LocalCredentialStore

    store = LocalCredentialStore()
    user_creds = store.load_credentials()
    shared_creds = store.load_shared_credentials()

    print("📊 ClawShell Credential Dashboard")
    print(f"  Total user credentials: {len(user_creds)}")
    print(f"  Total shared credentials: {len(shared_creds)}")

    # Group by service
    services: dict = {}
    for c in user_creds:
        svc = c.get("service", "unknown")
        services.setdefault(svc, {"user": 0, "shared": 0})
        services[svc]["user"] += 1
    for c in shared_creds:
        svc = c.get("service", "unknown")
        services.setdefault(svc, {"user": 0, "shared": 0})
        services[svc]["shared"] += 1

    if services:
        print("\n  Services:")
        for svc, counts in sorted(services.items()):
            print(f"    {svc}: {counts['user']} user, {counts['shared']} shared")
    else:
        print("\n  No credentials stored. Run 'clawshell sync' to fetch from cloud.")


def cmd_change_password(args):
    """Change password on ClawShell Cloud Hub."""
    import getpass
    from edge.wizard.config_wizard import ConfigWizard
    from edge.auth.client import AuthClient

    wizard = ConfigWizard()
    session = wizard.load_session()
    token = session.get("token", "")

    if not token:
        print("❌ Not logged in. Run 'clawshell login' first.")
        sys.exit(1)

    config = wizard.load_config()
    cloud_url = config.get("cloud_url", "http://localhost:8000")

    old_pw = getpass.getpass("   Current password: ")
    new_pw = getpass.getpass("   New password (min 6 chars): ")
    if len(new_pw) < 6:
        print("❌ Password must be at least 6 characters.")
        sys.exit(1)
    new_pw2 = getpass.getpass("   Confirm new password: ")
    if new_pw != new_pw2:
        print("❌ Passwords do not match.")
        sys.exit(1)

    client = AuthClient(cloud_url)
    result = client.change_password(token, old_pw, new_pw)
    if result.get("success"):
        print("✅ Password changed successfully.")
    else:
        error = result.get("error", "Failed")
        detail = result.get("detail", {})
        if isinstance(detail, dict) and detail.get("detail"):
            error = detail["detail"]
        print(f"❌ {error}")
        sys.exit(1)


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

    login_parser = sub.add_parser("login", help="Login to Cloud Hub")
    login_parser.add_argument("--cloud-url", help="Cloud Hub URL")
    login_parser.add_argument("--account-id", help="Account ID (non-interactive)")
    login_parser.add_argument("--password", help="Password (non-interactive)")
    login_parser.add_argument("--node-name", help="Node display name")

    reg_parser = sub.add_parser("register", help="Register a new account")
    reg_parser.add_argument("--cloud-url", help="Cloud Hub URL")

    sub.add_parser("logout", help="Logout from Cloud Hub")
    sub.add_parser("status", help="Show Edge status")
    sub.add_parser("start", help="Start Edge Sync Daemon")
    sub.add_parser("stop", help="Stop Edge Sync Daemon")
    sub.add_parser("sync", help="Manually sync credentials")
    sub.add_parser("dashboard", help="Show credential dashboard")
    sub.add_parser("change-password", help="Change Cloud Hub password")

    config_parser = sub.add_parser("config", help="Configure Edge")
    config_parser.add_argument("--cloud-url", help="Cloud Hub URL")
    config_parser.add_argument("--edge-token", help="Edge auth token")
    config_parser.add_argument("--node-name", help="Node display name")

    args = parser.parse_args()

    commands = {
        "install": cmd_install,
        "login": cmd_login,
        "register": cmd_register,
        "logout": cmd_logout,
        "status": cmd_status,
        "start": cmd_start,
        "stop": cmd_stop,
        "sync": cmd_sync,
        "dashboard": cmd_dashboard,
        "change-password": cmd_change_password,
        "config": cmd_config,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
