"""IDE CLI adapters — inject ClawShell into developer AI coding tools.

Each adapter implements: detect/inject/verify/rollback.
ADAPTER_TYPE = "ide"
"""

from local.adapters.ide.base import BaseIDEBridge
