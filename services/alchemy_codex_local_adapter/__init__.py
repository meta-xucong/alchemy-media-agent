"""Doc117 local-only Codex-to-Alchemy adapter.

This package is intentionally outside ``alchemy_creative_agent_3_0.app``.
Nothing in the Web runtime imports, registers, or starts it.  An interactive
Codex MCP client is its only supported caller.
"""

from .contracts import (
    LOCAL_CREATIVE_DIRECTION_OWNER,
    LOCAL_EXECUTION_CHANNEL,
    LOCAL_RENDERER,
    PLATFORM_OPENAI_GPT_IMAGE_2_MODEL,
    PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER,
    FrozenLocalJobContract,
    LocalJobSpec,
    LocalModeAdapterError,
    LocalModeDisabledError,
    PlatformRenderedImage,
)
from .facade import CodexLocalExecutionFacade
from .platform_renderer import PlatformImageRenderer

__all__ = [
    "CodexLocalExecutionFacade",
    "FrozenLocalJobContract",
    "LOCAL_CREATIVE_DIRECTION_OWNER",
    "LOCAL_EXECUTION_CHANNEL",
    "LOCAL_RENDERER",
    "LocalJobSpec",
    "LocalModeAdapterError",
    "LocalModeDisabledError",
    "PLATFORM_OPENAI_GPT_IMAGE_2_MODEL",
    "PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER",
    "PlatformImageRenderer",
    "PlatformRenderedImage",
]
