"""Edge Brain package (deprecated — use 'local' instead).

v3.0: This module is a backward-compat shim. All new code should
import from 'local'. Existing imports from 'edge' still work.
"""

try:
    import local as _local

    adapters = _local.adapters
    detector = _local.detector
    sync = _local.sync
    installer = _local.installer
    gateway = _local.gateway
    mcp = _local.mcp
    eventbus = _local.eventbus
    auth = _local.auth
    memos_adapter = _local.memos_adapter
    wizard = _local.wizard
    ide_bridge = _local.ide_bridge
    ecosystem = _local.ecosystem
    exoskeleton = _local.compiler

except ImportError:
    pass
