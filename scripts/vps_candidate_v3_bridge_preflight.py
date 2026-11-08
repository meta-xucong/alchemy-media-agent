#!/usr/bin/env python3
"""Read-only gate preventing candidate V3 smoke from falling back to an API renderer."""

from __future__ import annotations

import asyncio
import re
import sys
from typing import Any

from render_bridge_primary.core import PrimaryError, PrimaryRequest, PrimarySettings, PrimaryTransport
from render_bridge_primary.http import BridgeClient


class CandidateBridgePreflightError(RuntimeError):
    def __init__(self, code: str, diagnostic: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.diagnostic = diagnostic


def validate_candidate_v3_bridge_state(settings: Any, capabilities: object) -> None:
    """Apply the same profile and admission boundaries as the V3 route resolver."""
    if not bool(getattr(settings, "enabled", False)) or str(getattr(settings, "profile", "")) != "codex-image":
        raise CandidateBridgePreflightError("candidate_bridge_profile_not_enabled")
    if not all(
        isinstance(getattr(settings, name, None), str) and getattr(settings, name).strip()
        for name in ("base_url", "token", "workspace")
    ):
        raise CandidateBridgePreflightError("candidate_bridge_configuration_invalid")
    if not isinstance(capabilities, dict):
        raise CandidateBridgePreflightError("candidate_bridge_capabilities_invalid")

    admission = capabilities.get("admission")
    if not isinstance(admission, dict) or admission.get("accepting_new_tasks") is not True:
        raise CandidateBridgePreflightError("candidate_bridge_admission_not_open")

    # Match V3's normalized Codex adapter payload without creating a task.
    # V3's request_for() maps size, quality, and output-format controls to
    # Codex native defaults; a non-transparent request carries only the
    # adapter marker here. Testing the API-facing defaults would reject a
    # Bridge profile that correctly supports the actual Codex wire contract.
    request = PrimaryRequest(
        product="v3",
        owner_id="candidate-preflight",
        unit_id="candidate-preflight",
        prompt="A neutral still-life image.",
        parameters={"codex_adapter": "codex_cli_imagegen_v1"},
        hard_requirements={},
    )
    rejection = PrimaryTransport._safe_support_rejection(  # noqa: SLF001 - exact route preflight
        request,
        capabilities,
        "codex-image",
    )
    if rejection is not None:
        code = rejection.get("code")
        field = rejection.get("field")
        safe_code = code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code) else "unknown"
        safe_fields = {"quality", "output_format", "transparent_background", "references", "exact_dimensions"}
        safe_field = field if isinstance(field, str) and field in safe_fields else None
        diagnostic = f"code={safe_code}" + (f" field={safe_field}" if safe_field else "")
        raise CandidateBridgePreflightError("candidate_bridge_request_unsupported", diagnostic)


async def _read_capabilities(settings: PrimarySettings) -> dict[str, Any]:
    client = BridgeClient(settings.base_url, settings.token)
    try:
        return await client.capabilities()
    finally:
        await client.close()


def main() -> int:
    try:
        settings = PrimarySettings.from_env(product="v3")
    except PrimaryError:
        print("candidate_bridge_configuration_invalid", file=sys.stderr)
        return 2
    try:
        if not settings.enabled or settings.profile != "codex-image":
            raise CandidateBridgePreflightError("candidate_bridge_profile_not_enabled")
        capabilities = asyncio.run(_read_capabilities(settings))
        validate_candidate_v3_bridge_state(settings, capabilities)
    except CandidateBridgePreflightError as exc:
        print(exc.code, file=sys.stderr)
        if exc.diagnostic:
            print(f"candidate_bridge_request_rejection {exc.diagnostic}", file=sys.stderr)
        return 2
    except Exception:
        # Transport errors can contain URLs or low-level details. Keep the
        # action log limited to a stable, non-secret diagnostic.
        print("candidate_bridge_capabilities_unavailable", file=sys.stderr)
        return 2
    print("GUARDED_CANDIDATE_V3_BRIDGE_PREFLIGHT=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
