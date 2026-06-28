"""ClawShell Edge Installer CLI — python3 -m edge.installer [install|check|agent-mode]","""
import sys, os, argparse
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from local.installer.installer import ClawShellEdgeInstaller
from local.installer.reporter import SelfCheckReporter

def main():
    parser = argparse.ArgumentParser(description='ClawShell Edge Installer v2.2.0')
    parser.add_argument('action', nargs='?', default='install',
                        choices=['install', 'check', 'agent-mode', 'detect', 'config'])
    parser.add_argument('--dir', '-d', default=None, help='Installation directory')
    parser.add_argument('--non-interactive', '-n', action='store_true', help='Non-interactive mode')
    parser.add_argument('--skip-checklist', action='store_true', help='Skip prerequisites')
    args = parser.parse_args()
    
    if args.action == 'check':
        reporter = SelfCheckReporter(args.dir)
        print(reporter.generate_report(as_markdown=True))
    elif args.action == 'detect':
        from local.installer.detector import SystemDetector
        info = SystemDetector().detect_all()
        print(f'OS: {info.os_name} ({info.os_version})')
        print(f'Arch: {info.arch} | Python: {info.python_version}')
        print(f'Agents:')
        for a in info.agents:
            print(f'  {"✓" if a.installed else "✗"} {a.name} {"→" + a.config_path if a.config_path else ""}')
        print(f'IDEs:')
        for i in info.ides:
            print(f'  {"✓" if i.installed else "✗"} {i.name}')
    elif args.action == 'agent-mode':
        print(open(os.path.join(os.path.dirname(__file__), 'AGENT_MODE.md')).read())
    elif args.action == 'config':
        from local.installer.detector import SystemDetector
        from local.installer.configurator import ConfigAutoInjector
        info = SystemDetector().detect_all()
        configurator = ConfigAutoInjector(clawshell_dir=args.dir or str(Path.home() / '.clawshell'))
        results = configurator.inject_all(info.agents)
        for agent, ok in results.items():
            s = '✓' if ok else '✗'
            print(f'  {s} {agent}')
        print(f'Done: {sum(1 for v in results.values() if v)}/{len(results)} agents configured')
        # Also show non-configured
        for a in info.agents:
            if a.installed and a.config_path and not a.claWSHELL_configured:
                print(f'  Skipped {a.name}: config at {a.config_path} (manual check needed)')
    else:
        installer = ClawShellEdgeInstaller(
            workdir=args.dir,
            interactive=not args.non_interactive,
            skip_checklist=args.skip_checklist,
        )
        report = installer.install()
        _print_report(report)

def _print_report(report):
    print('')
    print('[1mInstallation Report[0m')
    print(f'  Status: {report["status"]}')
    print(f'  Path: {report["path"]}')
    for step, result in report["steps"].items():
        s = '✓' if result == 'ok' else '✗'
        print(f'  {s} {step}: {result}')

if __name__ == '__main__':
    main()
