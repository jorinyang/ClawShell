"""ClawShell Local (v3.0) — renamed from 'edge'.

Provides:
  compiler/  — L1-L4 exoskeleton layers
  adapters/  — Unified framework/bridge/ide adapters
  agent/     — Agent discovery + 5-way injection
  sync/      — SyncDaemon (3-channel sync)
  detector/  — Framework and agent detection
  installer/ — One-click install wizard
  gui/       — Electron + Next.js desktop client (Phase 7)
"""

# Make subpackages importable
import local.detector
import local.sync
import local.installer
import local.gateway
import local.mcp
import local.eventbus
import local.auth
import local.memos_adapter
import local.wizard
import local.ide_bridge
import local.ecosystem
import local.compiler as exoskeleton

# Re-export from subpackages
from local.detector import detect_environment
from local.sync.daemon import EdgeSyncDaemon
from local.adapters.manager import AdapterManager
from local.adapters.base import BaseAdapter

