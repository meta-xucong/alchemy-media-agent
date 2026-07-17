"""Provider capability materialization for V2 reference-delivery contracts."""

from __future__ import annotations

from typing import Any


# Keep the capability map deliberately conservative.  A provider parameter is
# only emitted after its support is explicitly declared here; receipt metadata
# records a requested-but-not-supported fidelity requirement without sending an
# unknown API key upstream.
_OPENAI_IMAGE_CAPABILITIES = {
    "gpt-image-2": {"edit": True, "input_fidelity": False},
}


def materialize_openai_reference_request(
    *,
    plan: Any,
    model: str,
    operation: str,
    reference_image_count: int,
    base_kwargs: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return supported kwargs and a safe, persistable request receipt."""

    kwargs = dict(base_kwargs)
    variables = getattr(plan, "user_variables", {}) or {}
    contract = variables.get("reference_delivery") if isinstance(variables, dict) and isinstance(variables.get("reference_delivery"), dict) else {}
    capabilities = _OPENAI_IMAGE_CAPABILITIES.get(str(model), {"edit": True, "input_fidelity": False})
    hard_reference = any(
        isinstance(item, dict) and item.get("authority") == "required"
        for item in contract.get("reference_intents", [])
    )
    fidelity_requested = bool(hard_reference and operation == "images.edit")
    fidelity_applied = None
    omission_reason = None
    if fidelity_requested:
        if capabilities.get("input_fidelity"):
            kwargs["input_fidelity"] = "high"
            fidelity_applied = "high"
        else:
            omission_reason = "model_capability_not_declared"
    receipt = {
        "provider_contract_version": 1,
        "operation": operation,
        "model": str(model),
        "reference_image_count": max(0, int(reference_image_count)),
        "reference_delivery_contract_id": contract.get("contract_id"),
        "hard_reference_contract": hard_reference,
        "input_fidelity_requested": fidelity_requested,
        "input_fidelity_applied": fidelity_applied,
        "input_fidelity_omission_reason": omission_reason,
        "parameter_names": sorted(str(key) for key in kwargs),
    }
    return kwargs, receipt


def provider_receipt_for_output(metadata: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Attach a safe receipt without exposing prompt, image bytes, or headers."""

    return {**dict(metadata or {}), "reference_delivery_provider_receipt": dict(receipt)}
