"""Bounded V2 semantic-repair policy.

This module only produces a safe directive.  Dispatch remains owned by the
existing V2 queue/controller so this policy cannot silently create an
unbounded, chargeable generation loop.
"""

from __future__ import annotations

from typing import Any

from app.schemas import ImageReviewDecision


def build_semantic_retry_directive(
    review: ImageReviewDecision,
    contract: dict[str, Any] | None,
    *,
    attempts_completed: int = 0,
) -> dict[str, Any]:
    contract = contract if isinstance(contract, dict) else {}
    policy = contract.get("semantic_retry") if isinstance(contract.get("semantic_retry"), dict) else {}
    max_attempts = max(0, int(policy.get("max_attempts") or 0))
    eligible_risks = {str(item) for item in policy.get("eligible_risks", []) if str(item or "")}
    matched = [risk for risk in review.detected_risks if risk in eligible_risks]
    remaining = max(0, max_attempts - max(0, int(attempts_completed)))
    eligible = bool(remaining and matched and review.decision in {"needs_review", "retry_recommended"})
    return {
        "policy_version": 1,
        "eligible": eligible,
        "max_attempts": max_attempts,
        "attempts_completed": max(0, int(attempts_completed)),
        "remaining_attempts": remaining,
        "reason_codes": matched,
        "retry_scope": "reference_delivery_repair" if eligible else None,
        "requires_same_reference_inputs": bool(contract.get("requires_image_reference")),
    }
