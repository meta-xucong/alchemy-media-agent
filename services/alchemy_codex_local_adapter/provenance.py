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
    }
