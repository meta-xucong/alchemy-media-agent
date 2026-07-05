"""Doc58 strong reference continuation planning."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import ProjectIdentityAnchor, StrongReferenceContinuationPlan, StrongReferenceBinding


class StrongReferenceLoopPlanner:
    """Turn active identity anchors into provider and prompt requirements."""

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        anchors: list[ProjectIdentityAnchor],
        strong_bindings: list[StrongReferenceBinding],
    ) -> StrongReferenceContinuationPlan | None:
        if not anchors and not strong_bindings:
            return None
        active_anchors = [anchor for anchor in anchors if anchor.active]
        provider_required_ids = _dedupe(
            binding.asset_id or binding.output_id or binding.source_id
            for binding in strong_bindings
            if binding.provider_input_required
        )
        prompt_only_ids = _dedupe(
            binding.asset_id or binding.output_id or binding.source_id
            for binding in strong_bindings
            if binding.prompt_only_fallback and not binding.provider_input_required
        )
        lock_targets = _dedupe(
            target
            for binding in strong_bindings
            for target in binding.lock_targets
        )
        prompt_additions = _dedupe(
            [
                *[
                    rule
                    for anchor in active_anchors
                    for rule in [*anchor.identity_keep_rules, *anchor.style_keep_rules]
                ],
                "use selected project output as the strongest positive reference",
                "continue the project direction without replacing previous outputs",
            ]
        )[:12]
        negative_additions = _dedupe(
            [
                *[rule for anchor in active_anchors for rule in anchor.forbidden_drift],
                "unselected candidates should not influence the new image",
            ]
        )[:12]
        reference_mode = "provider_image_reference" if provider_required_ids else "prompt_only_reference" if prompt_only_ids else "context_reference"
        return StrongReferenceContinuationPlan(
            plan_id=stable_id(
                "strong_reference_continuation_plan",
                project_id,
                job_id,
                ",".join(anchor.anchor_id for anchor in active_anchors),
                ",".join(provider_required_ids),
            ),
            project_id=project_id,
            job_id=job_id,
            active_anchor_ids=[anchor.anchor_id for anchor in active_anchors],
            provider_required_reference_ids=provider_required_ids,
            prompt_only_reference_ids=prompt_only_ids,
            lock_targets=lock_targets,
            prompt_additions=prompt_additions,
            negative_additions=negative_additions,
            reference_mode=reference_mode,
            user_visible_summary=[
                "Selected result will guide the next generation.",
                "V3 will preserve the important identity/style details while allowing useful variation.",
            ],
            metadata={
                "doc": "58",
                "active_anchor_count": len(active_anchors),
                "strong_binding_count": len(strong_bindings),
                "provider_reference_count": len(provider_required_ids),
            },
        )


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
