"""Public-safe canonical-provider-prompt provenance for Doc130."""

from __future__ import annotations

from typing import Any

from .contracts import (
    CONVERSATION_ONLY_DELIVERY_STATE,
    NATIVE_CREATIVE_DIRECTION_OWNER,
    NATIVE_EXECUTION_CHANNEL,
    NATIVE_PLANNING_AUTHORITY,
    NATIVE_RENDERER,
)


def renderer_parity_receipt(
    *,
    expected_contract: dict[str, Any],
    actual_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare a host-reported native renderer contract without reading pixels.

    Native Mode deliberately does not import or certify conversation images.
    This pure helper gives an embedding host one strict, auditable comparison
    before it may count an equivalent M5 run. Missing fields are blocked rather
    than inferred from file dimensions or a caller's renderer claim.
    """

    expected = dict(expected_contract or {})
    expected.setdefault("renderer", "codex_builtin_imagegen")
    actual = dict(actual_contract or {})
    required = ("renderer", "model", "size", "quality", "output_format")
    missing = [key for key in required if not str(actual.get(key) or "").strip()]
    mismatches = [
        key
        for key in required
        if key not in missing and str(actual.get(key)) != str(expected.get(key))
    ]
    state = "verified" if not missing and not mismatches else "blocked"
    return {
        "schema_version": "native_renderer_parity_v1",
        "state": state,
        "expected": {key: expected.get(key) for key in required},
        "actual": {key: actual.get(key) for key in required},
        "missing_fields": missing,
        "mismatch_fields": mismatches,
        "reason_code": None if state == "verified" else (
            "renderer_contract_fields_missing" if missing else "renderer_contract_mismatch"
        ),
        "pixel_bytes_read": False,
        "conversation_only": True,
    }


def native_plan_provenance(
    *,
    template_id: str,
    scenario_id: str,
    output_count: int,
    activation_plan_id: str,
    constraint_ledger_id: str,
    admission_fallback_observed: bool,
    canonical_prompt_signing: dict[str, Any],
) -> dict[str, Any]:
    """Return identifiers only; no prompt, path, image, or conversation state."""

    return {
        "planner": NATIVE_PLANNING_AUTHORITY,
        "creative_direction_owner": NATIVE_CREATIVE_DIRECTION_OWNER,
        "execution_channel": NATIVE_EXECUTION_CHANNEL,
        "renderer": NATIVE_RENDERER,
        "delivery_state": CONVERSATION_ONLY_DELIVERY_STATE,
        "admission_fallback_observed": bool(admission_fallback_observed),
        "legacy_creative_output_projected": False,
        "canonical_provider_prompt_projected": True,
        # This is an audit receipt only. It confirms which shared Brain
        # signing path produced the exact prompt relay without exposing the
        # prompt twice, an endpoint, a model credential, or review evidence.
        "canonical_prompt_signing": canonical_prompt_signing,
        "template_id": template_id,
        "scenario_id": scenario_id,
        "requested_output_count": output_count,
        "activation_plan_id": activation_plan_id,
        "constraint_ledger_id": constraint_ledger_id,
        "renderer_parity": {
            "schema_version": "native_renderer_parity_v1",
            "state": "awaiting_host_receipt",
            "reason_code": "native_host_must_report_actual_renderer_contract",
            "conversation_only": True,
        },
    }
