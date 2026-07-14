"""Doc117 local-only Codex-to-Alchemy adapter.

This package is intentionally outside ``alchemy_creative_agent_3_0.app``.
Nothing in the Web runtime imports, registers, or starts it.  An interactive
Codex MCP client is its only supported caller.
"""

from .contracts import (
    LOCAL_CREATIVE_DIRECTION_OWNER,
    LOCAL_EXECUTION_CHANNEL,
    LOCAL_RENDERER,
    FrozenLocalJobContract,
    LocalArtifactImportRequest,
    LocalJobSpec,
    LocalModeAdapterError,
    LocalModeDisabledError,
)
from .facade import CodexLocalExecutionFacade

__all__ = [
    "CodexLocalExecutionFacade",
    "FrozenLocalJobContract",
    "LOCAL_CREATIVE_DIRECTION_OWNER",
    "LOCAL_EXECUTION_CHANNEL",
    "LOCAL_RENDERER",
    "LocalArtifactImportRequest",
    "LocalJobSpec",
    "LocalModeAdapterError",
    "LocalModeDisabledError",
]
