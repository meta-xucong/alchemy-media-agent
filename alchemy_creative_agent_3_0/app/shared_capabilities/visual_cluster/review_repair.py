"""Shared post-review repair evidence projection.

Doc213 keeps retry learning in the shared visual cluster.  Specialized
modules may pass a prior candidate review into this helper, but they must not
author a private prompt patch or reviewer.  The result is bounded evidence for
the next Brain/provider/MCP pass.
"""

from __future__ import annotations

from typing import Any


SHARED_REVIEW_REPAIR_CONTEXT_VERSION = "v3_shared_review_repair_context_v1"

REFERENCE_CHANNEL_REPAIR_ISSUE_CODES = frozenset(
    {
        "source_hair_overinherited",
        "source_makeup_overinherited",
        "source_wardrobe_overinherited",
        "source_lighting_overinherited",
        "source_color_grade_overinherited",
        "source_scene_overinherited",
        "source_camera_overinherited",
        "source_whole_style_overinherited",
        "reference_used_as_style_when_identity_only",
        "prompt_owned_channel_ignored",
        "selected_anchor_overrode_current_prompt",
        "structured_appearance_lock_misapplied",
    }
)

HUMAN_MATERIAL_REPAIR_ISSUE_CODES = frozenset(
    {
        "professional_ai_overperfection",
        "human_skin_or_retouch",
        "human_rendering_artifact",
        "generic_stock_photo_finish",
        "commercial_cleanliness_failure",
    }
)

SHARED_REVIEW_REPAIR_ISSUE_CODES = frozenset(
    {
        *REFERENCE_CHANNEL_REPAIR_ISSUE_CODES,
        *HUMAN_MATERIAL_REPAIR_ISSUE_CODES,
    }
)


def shared_review_repair_context_from_decision(
    *,
    candidate_id: str,
    output_id: str,
    issue_codes: Any,
    shared_review_receipts: Any | None = None,
) -> dict[str, Any] | None:
    """Return sanitized retry evidence for the next candidate, if useful."""

    normalized = _dedupe(
        str(item.get("code") if isinstance(item, dict) else item).strip()
        for item in (issue_codes if isinstance(issue_codes, (list, tuple, set)) else [])
        if str(item.get("code") if isinstance(item, dict) else item).strip()
    )
    repair_codes = [code for code in normalized if code in SHARED_REVIEW_REPAIR_ISSUE_CODES]
    if not repair_codes:
        return None
    observed = shared_review_observations_for_issue_codes(repair_codes)
    if not observed:
        return None
    receipts = [
        _public_receipt_digest(receipt)
        for receipt in (shared_review_receipts if isinstance(shared_review_receipts, list) else [])
        if isinstance(receipt, dict)
    ]
    return {
        "contract_version": SHARED_REVIEW_REPAIR_CONTEXT_VERSION,
        "owner": "v3_shared_visual_cluster",
        "source": "prior_candidate_shared_review",
        "retry_evidence_only": True,
        "target_candidate_id": str(candidate_id or "").strip(),
        "target_output_id": str(output_id or "").strip(),
        "issue_codes": repair_codes,
        "observed_review_evidence": observed,
        "shared_review_receipts": receipts[:3],
    }


def shared_review_observations_for_issue_codes(issue_codes: Any) -> list[str]:
    """Project issue codes into bounded semantic observations, not prompt text."""

    codes = _dedupe(str(item or "").strip() for item in issue_codes if str(item or "").strip())
    observations: list[str] = []
    reference_codes = [code for code in codes if code in REFERENCE_CHANNEL_REPAIR_ISSUE_CODES]
    material_codes = [code for code in codes if code in HUMAN_MATERIAL_REPAIR_ISSUE_CODES]
    if reference_codes:
        observations.append(
            "Shared review observed reference-channel overinheritance: keep assigned identity truth, "
            "but restore current-prompt-owned surface, styling, scene, lighting, camera, and finish channels."
        )
    if "source_hair_overinherited" in reference_codes:
        observations.append(
            "Shared review observed that source hair from the identity reference was copied into a prompt-owned hair channel."
        )
    if "source_wardrobe_overinherited" in reference_codes:
        observations.append(
            "Shared review observed that source wardrobe or accessories were copied into prompt-owned appearance channels."
        )
    if "source_makeup_overinherited" in reference_codes:
        observations.append(
            "Shared review observed that source makeup or facial styling leaked while the underlying face geometry should remain stable."
        )
    if "source_lighting_overinherited" in reference_codes or "source_color_grade_overinherited" in reference_codes:
        observations.append(
            "Shared review observed source lighting or color-grade leakage: lighting and color treatment must follow the current prompt."
        )
    if "source_scene_overinherited" in reference_codes:
        observations.append(
            "Shared review observed that the source environment was copied when the environment should follow the current prompt."
        )
    if "source_camera_overinherited" in reference_codes:
        observations.append(
            "Shared review observed that the source camera framing was copied when camera distance, crop, and viewpoint should follow the current slot contract."
        )
    if material_codes:
        observations.append(
            "Shared review observed over-polished or artificial human material finish: preserve camera-observed texture and commercial cleanliness without plastic smoothing."
        )
    return _dedupe(observations)[:8]


def shared_review_repair_prompt_delta(repair_context: Any) -> str:
    """Materialize repair evidence only for bounded local recovery prompts."""

    if not isinstance(repair_context, dict):
        return ""
    observed = repair_context.get("observed_review_evidence")
    if not isinstance(observed, list):
        return ""
    lines = [
        "Apply the prior shared review repair evidence without changing the approved slot goal:"
    ]
    for item in observed:
        text = " ".join(str(item or "").replace("\x00", " ").split())[:220].strip()
        if text:
            lines.append(text)
    return " ".join(lines).strip()


def _public_receipt_digest(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "owner": str(receipt.get("owner") or "").strip(),
        "contract_version": str(receipt.get("contract_version") or "").strip(),
        "status": str(receipt.get("status") or "").strip(),
        "issue_codes": _dedupe(str(item or "").strip() for item in receipt.get("issue_codes", []) if str(item or "").strip())[:12],
        "evidence_codes": _dedupe(str(item or "").strip() for item in receipt.get("evidence_codes", []) if str(item or "").strip())[:12],
    }


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


__all__ = [
    "SHARED_REVIEW_REPAIR_CONTEXT_VERSION",
    "SHARED_REVIEW_REPAIR_ISSUE_CODES",
    "shared_review_observations_for_issue_codes",
    "shared_review_repair_context_from_decision",
    "shared_review_repair_prompt_delta",
]
