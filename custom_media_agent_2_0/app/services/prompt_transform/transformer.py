from __future__ import annotations

from app.schemas import ImagePromptPlan
from app.services.intent_integrity import PROMPT_BUDGET_CHARS
from app.services.prompt_transform.guard import (
    build_guard_instructions,
    extract_constraints,
    sanitize_prompt_identifiers,
    wrap_guarded_prompt,
)
from app.services.prompt_transform.metadata import build_prompt_transform_metadata
from app.services.prompt_transform.mode import resolve_modes


def transform_prompt_plan(plan: ImagePromptPlan) -> ImagePromptPlan:
    if _already_transformed(plan):
        return plan
    base_prompt = _base_prompt(plan)
    mode_info = resolve_modes(plan)
    fidelity = mode_info["fidelity_mode"]
    constraints: list[str] = []
    final_prompt = base_prompt
    applied = False
    skipped_for_budget = False

    if fidelity == "strict":
        constraints = extract_constraints(base_prompt)
        guarded_prompt = wrap_guarded_prompt(base_prompt, build_guard_instructions(constraints))
        if len(guarded_prompt) <= PROMPT_BUDGET_CHARS:
            final_prompt = guarded_prompt
            applied = final_prompt != base_prompt
        else:
            # The base artifact already carries the complete intent manifest.
            # Drop only the added guard wrapper instead of pushing a valid
            # request over the provider budget or clipping user content.
            skipped_for_budget = True
    elif fidelity in {"original", "off"}:
        final_prompt = base_prompt
        applied = False

    user_variables = dict(plan.user_variables or {})
    user_variables.pop("prompt_transform_strength", None)
    user_variables["generation_prompt"] = final_prompt
    user_variables["prompt_transform"] = build_prompt_transform_metadata(
        base_prompt=base_prompt,
        final_prompt=final_prompt,
        mode_info=mode_info,
        constraints=constraints,
        applied=applied,
        skipped_for_budget=skipped_for_budget,
    )
    return plan.model_copy(update={"user_variables": user_variables})


def fallback_prompt_plan(plan: ImagePromptPlan, error: Exception) -> ImagePromptPlan:
    base_prompt = _base_prompt(plan)
    user_variables = dict(plan.user_variables or {})
    user_variables.pop("prompt_transform_strength", None)
    user_variables.setdefault("generation_prompt", base_prompt)
    user_variables["prompt_transform"] = build_prompt_transform_metadata(
        base_prompt=base_prompt,
        final_prompt=str(user_variables.get("generation_prompt") or base_prompt),
        mode_info={"source": "fallback", "v2_mode": str(plan.mode), "transform_mode": "", "fidelity_mode": ""},
        constraints=[],
        applied=False,
        fallback_used=True,
        error=f"{type(error).__name__}: {error}",
    )
    return plan.model_copy(update={"user_variables": user_variables})


def _base_prompt(plan: ImagePromptPlan) -> str:
    existing = (plan.user_variables or {}).get("generation_prompt")
    return sanitize_prompt_identifiers(str(existing if existing not in {None, ""} else plan.prompt))


def _already_transformed(plan: ImagePromptPlan) -> bool:
    variables = plan.user_variables or {}
    return bool(variables.get("generation_prompt") and isinstance(variables.get("prompt_transform"), dict))
