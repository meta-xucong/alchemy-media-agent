from __future__ import annotations

from typing import Any, Literal

from app.schemas import ImagePromptPlan


TransformMode = Literal["stable", "enhanced", "exploration"]
FidelityMode = Literal["original", "strict", "off"]

VALID_TRANSFORM_MODES: set[str] = {"stable", "enhanced", "exploration"}
VALID_FIDELITY_MODES: set[str] = {"original", "strict", "off"}

TRANSFORM_TO_FIDELITY: dict[str, FidelityMode] = {
    "stable": "original",
    "enhanced": "strict",
    "exploration": "off",
}
V2_MODE_TO_TRANSFORM: dict[str, TransformMode] = {
    "template_customize": "stable",
    "smart_enhance": "enhanced",
    "revision": "enhanced",
    "batch": "enhanced",
}


def resolve_modes(plan: ImagePromptPlan) -> dict[str, str]:
    explicit = _clean_mode((plan.user_variables or {}).get("prompt_transform_mode"))
    if explicit:
        transform_mode = explicit
        source = "user_variables.prompt_transform_mode"
    else:
        transform_mode = V2_MODE_TO_TRANSFORM.get(str(plan.mode), "enhanced")
        source = "image_prompt_plan.mode"
    fidelity_mode = TRANSFORM_TO_FIDELITY[transform_mode]
    return {
        "source": source,
        "transform_mode": transform_mode,
        "fidelity_mode": fidelity_mode,
        "v2_mode": str(plan.mode),
    }


def _clean_mode(value: Any) -> TransformMode | None:
    raw = str(value or "").strip().lower()
    if raw in VALID_TRANSFORM_MODES:
        return raw  # type: ignore[return-value]
    if raw in VALID_FIDELITY_MODES:
        reverse = {fidelity: transform for transform, fidelity in TRANSFORM_TO_FIDELITY.items()}
        return reverse[raw]  # type: ignore[return-value]
    return None
