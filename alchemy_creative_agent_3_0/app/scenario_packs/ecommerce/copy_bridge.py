"""Retired local copy-planning compatibility surface.

Copy is now either explicitly approved literal input or part of the remote
Brain and provider-native complete-image path.  This module must not localize,
write, allocate, or forbid copy by a hard-coded image role.
"""

from __future__ import annotations

from typing import Any


class EcommerceCopyBridge:
    """Return only explicit literal copy for archival callers."""

    def plan_for_slot(self, *, parameters: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        parameters = parameters or {}
        value = parameters.get("approved_literal_copy") or parameters.get("approved_copy") or parameters.get("literal_copy")
        text = str(value).strip() if value is not None else ""
        return {
            "text": text or None,
            "source": "explicit_user_approval" if text else "absent",
            "policy": "provider_native_only",
            "local_renderer": "forbidden",
            "creative_copy_generated": False,
        }
