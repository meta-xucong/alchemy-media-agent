"""Public-safe, prompt-plan-only provenance for Doc126."""

from __future__ import annotations

from typing import Any

from .contracts import (
    CONVERSATION_ONLY_DELIVERY_STATE,
    NATIVE_CREATIVE_DIRECTION_OWNER,
    NATIVE_EXECUTION_CHANNEL,
    NATIVE_RENDERER,
)


def native_plan_provenance(
    *,
    template_id: str,
    scenario_id: str,
    output_count: int,
    activation_plan_id: str,
    constraint_ledger_id: str,
    fallback_used: bool,
) -> dict[str, Any]:
    """Return identifiers only; no prompt, path, image, or conversation state."""

    return {
        "planner": NATIVE_CREATIVE_DIRECTION_OWNER,
        "creative_direction_owner": NATIVE_CREATIVE_DIRECTION_OWNER,
        "execution_channel": NATIVE_EXECUTION_CHANNEL,
        "renderer": NATIVE_RENDERER,
        "delivery_state": CONVERSATION_ONLY_DELIVERY_STATE,
        "fallback_used": bool(fallback_used),
        "template_id": template_id,
        "scenario_id": scenario_id,
        "requested_output_count": output_count,
        "activation_plan_id": activation_plan_id,
        "constraint_ledger_id": constraint_ledger_id,
    }
