from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable

from app.services.ids import new_id


# This is a guardrail for the compiled provider artifact, not permission to
# crop user intent.  It is deliberately large enough for normal template plus
# reference jobs; anything beyond it is stopped for explicit compaction rather
# than truncated on the way to the provider.
PROMPT_BUDGET_CHARS = 12000
HARD_REFERENCE_ROLES = {"subject_reference", "logo_reference", "face_reference", "background_reference"}


def compile_prompt_artifact(
    *,
    user_prompt: str,
    creative_prompt: str,
    creative_source: str,
    template_section: str = "",
    asset_sections: Iterable[dict[str, Any]] | None = None,
    visual_grammar_section: str = "",
    control_sections: Iterable[dict[str, Any]] | None = None,
    budget_chars: int = PROMPT_BUDGET_CHARS,
) -> tuple[str, dict[str, Any]]:
    """Compile V2's provider prompt without silently truncating semantic input.

    The compiler deliberately treats the user request and a usable Claude final
    decision as required sections.  It may omit only sections marked ``soft``;
    when the remaining required/strong content cannot fit, it returns the full
    artifact together with ``budget_satisfied=False``.  Generation preflight is
    responsible for stopping that request before it reaches a provider.
    """

    sections: list[dict[str, Any]] = []
    _append_section(
        sections,
        intent_id="intent_user_request",
        source="user_request",
        priority="required",
        title="USER REQUEST",
        text=user_prompt,
    )
    for index, asset in enumerate(asset_sections or [], start=1):
        role = str(asset.get("role") or "uploaded_reference")
        strength = str(asset.get("constraint_strength") or "strong")
        required = bool(asset.get("provider_input_required")) or role in HARD_REFERENCE_ROLES or strength == "required"
        reference_index = asset.get("reference_index")
        label = str(asset.get("title") or (f"REFERENCE IMAGE {reference_index}" if reference_index else f"UPLOADED ASSET {index}"))
        _append_section(
            sections,
            intent_id=str(asset.get("intent_id") or f"intent_asset_{index}"),
            source=str(asset.get("role_source") or "asset_binding"),
            priority="required" if required else "strong",
            title=label,
            text=str(asset.get("prompt_instruction") or asset.get("instruction") or ""),
            asset_id=str(asset.get("asset_id") or "") or None,
            role=role,
            reference_index=reference_index,
        )
    _append_section(
        sections,
        intent_id="intent_creative_decision",
        source=creative_source,
        priority="required" if creative_source == "claude_final_prompt" else "strong",
        title="CREATIVE DECISION" if creative_source == "claude_final_prompt" else "CREATIVE PLAN",
        text=creative_prompt,
    )
    _append_section(
        sections,
        intent_id="intent_template_frame",
        source="selected_template",
        priority="strong",
        title="TEMPLATE FRAME",
        text=template_section,
    )
    _append_section(
        sections,
        intent_id="intent_visual_grammar",
        source="visual_grammar_contract",
        priority="strong",
        title="VISUAL GRAMMAR",
        text=visual_grammar_section,
    )
    for index, control in enumerate(control_sections or [], start=1):
        _append_section(
            sections,
            intent_id=str(control.get("intent_id") or f"intent_control_{index}"),
            source=str(control.get("source") or "v2_control"),
            priority=str(control.get("priority") or "required"),
            title=str(control.get("title") or "REQUIRED CONTROL"),
            text=str(control.get("text") or ""),
        )

    required_ids = [item["intent_id"] for item in sections if item["priority"] == "required"]
    included = list(sections)
    omitted: list[dict[str, Any]] = []
    prompt = _render_sections(included)
    for candidate in [item for item in reversed(included) if item["priority"] == "soft"]:
        if len(prompt) <= budget_chars:
            break
        included.remove(candidate)
        omitted.append(
            {
                "intent_id": candidate["intent_id"],
                "reason": "optional_section_omitted_for_budget",
                "priority": candidate["priority"],
            }
        )
        prompt = _render_sections(included)

    included_ids = [item["intent_id"] for item in included]
    required_missing = [intent_id for intent_id in required_ids if intent_id not in included_ids]
    budget_satisfied = len(prompt) <= budget_chars and not required_missing
    manifest = {
        "manifest_id": new_id("imf"),
        "version": 1,
        "budget_chars": budget_chars,
        "budget_satisfied": budget_satisfied,
        "required_intent_ids": required_ids,
        "included_intent_ids": included_ids,
        "omitted_intents": omitted,
        "required_intent_ids_missing": required_missing,
        "atoms": [_trace_atom(item) for item in sections],
    }
    trace = {
        "trace_version": 1,
        "manifest": manifest,
        "compiled_prompt_hash": _hash_text(prompt),
        "compiled_prompt_length": len(prompt),
        "effective_payload_hash": None,
        "effective_payload_length": None,
        "preflight": {"status": "pending", "code": None, "message": ""},
    }
    return prompt, trace


def annotate_effective_payload(trace: dict[str, Any] | None, prompt: str) -> dict[str, Any]:
    result = dict(trace or {})
    result["effective_payload_hash"] = _hash_text(prompt)
    result["effective_payload_length"] = len(str(prompt or ""))
    return result


def preflight_prompt_integrity(
    *,
    trace: dict[str, Any] | None,
    effective_prompt: str,
    input_images: Iterable[Any],
    provider_input_plan: dict[str, Any] | None,
    reference_delivery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a provider-safe preflight result without exposing prompt text."""

    provider_images = list(input_images)
    result = annotate_effective_payload(trace, effective_prompt)
    manifest = result.get("manifest") if isinstance(result.get("manifest"), dict) else {}
    if not manifest:
        return {
            **result,
            "preflight": {"status": "passed", "code": None, "message": "legacy_or_direct_prompt_without_integrity_trace"},
        }
    if not manifest.get("budget_satisfied"):
        return {
            **result,
            "preflight": {
                "status": "failed",
                "code": "constraint_budget_unsatisfied",
                "message": "Required V2 intent sections exceed the configured provider prompt budget.",
            },
        }
    budget_chars = _as_int(manifest.get("budget_chars"), PROMPT_BUDGET_CHARS)
    if len(str(effective_prompt or "")) > budget_chars:
        return {
            **result,
            "preflight": {
                "status": "failed",
                "code": "effective_prompt_budget_exceeded",
                "message": "The effective provider prompt exceeds the verified V2 prompt budget.",
            },
        }
    required_ids = set(_string_list(manifest.get("required_intent_ids")))
    included_ids = set(_string_list(manifest.get("included_intent_ids")))
    missing = sorted(required_ids - included_ids)
    if missing:
        return {
            **result,
            "preflight": {
                "status": "failed",
                "code": "required_intent_not_compiled",
                "message": "A required V2 intent was not compiled into the provider artifact.",
                "missing_intent_ids": missing,
            },
        }
    provider_plan = provider_input_plan if isinstance(provider_input_plan, dict) else {}
    expected_ids = _string_list(provider_plan.get("reference_image_asset_ids"))
    delivery_contract = reference_delivery if isinstance(reference_delivery, dict) else {}
    contract_ids = _string_list(delivery_contract.get("required_reference_asset_ids"))
    if contract_ids and expected_ids != contract_ids:
        return {
            **result,
            "preflight": {
                "status": "failed",
                "code": "reference_delivery_contract_drift",
                "message": "The V2 reference-delivery contract does not match the provider input plan.",
                "contract_asset_ids": contract_ids,
                "provider_plan_asset_ids": expected_ids,
            },
        }
    actual_ids = _provider_input_asset_ids(provider_images)
    missing_assets = [asset_id for asset_id in expected_ids if asset_id not in actual_ids]
    if missing_assets:
        return {
            **result,
            "preflight": {
                "status": "failed",
                "code": "required_reference_missing",
                "message": "A planned V2 reference image is missing from the provider request.",
                "missing_asset_ids": missing_assets,
            },
        }
    if expected_ids and not provider_plan.get("requires_image_reference"):
        return {
            **result,
            "preflight": {
                "status": "failed",
                "code": "provider_input_plan_invalid",
                "message": "Reference asset IDs require a V2 image-reference provider operation.",
            },
        }
    if expected_ids:
        actual_indices = _provider_input_reference_indices(provider_images)
        expected_indices = list(range(1, len(expected_ids) + 1))
        if actual_indices != expected_indices:
            return {
                **result,
                "preflight": {
                    "status": "failed",
                    "code": "reference_index_mismatch",
                    "message": "Provider reference image indexes do not match the compiled V2 reference order.",
                    "expected_reference_indices": expected_indices,
                    "actual_reference_indices": actual_indices,
                },
            }
    return {
        **result,
        "preflight": {"status": "passed", "code": None, "message": "intent_and_reference_contract_verified"},
    }


def _append_section(
    sections: list[dict[str, Any]],
    *,
    intent_id: str,
    source: str,
    priority: str,
    title: str,
    text: str,
    asset_id: str | None = None,
    role: str | None = None,
    reference_index: Any = None,
) -> None:
    clean = _normalise_text(text)
    if not clean:
        return
    sections.append(
        {
            "intent_id": intent_id,
            "source": source,
            "priority": priority if priority in {"required", "strong", "soft"} else "strong",
            "title": _normalise_text(title),
            "text": clean,
            "asset_id": asset_id,
            "role": role,
            "reference_index": reference_index,
        }
    )


def _render_sections(sections: Iterable[dict[str, Any]]) -> str:
    return "\n\n".join(f"{item['title']}:\n{item['text']}" for item in sections).strip()


def _trace_atom(section: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent_id": section["intent_id"],
        "source": section["source"],
        "priority": section["priority"],
        "asset_id": section.get("asset_id"),
        "role": section.get("role"),
        "reference_index": section.get("reference_index"),
        "text_hash": _hash_text(section["text"]),
        "text_length": len(section["text"]),
    }


def _provider_input_asset_ids(input_images: Iterable[Any]) -> list[str]:
    asset_ids: list[str] = []
    for image in input_images:
        if isinstance(image, dict):
            value = image.get("asset_id")
        else:
            value = getattr(image, "asset_id", None)
        clean = str(value or "").strip()
        if clean and clean not in asset_ids:
            asset_ids.append(clean)
    return asset_ids


def _provider_input_reference_indices(input_images: Iterable[Any]) -> list[int]:
    indices: list[int] = []
    for image in input_images:
        value = image.get("reference_index") if isinstance(image, dict) else getattr(image, "reference_index", None)
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        indices.append(index)
    return indices


def _normalise_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _hash_text(value: Any) -> str:
    return sha256(str(value or "").encode("utf-8")).hexdigest()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
