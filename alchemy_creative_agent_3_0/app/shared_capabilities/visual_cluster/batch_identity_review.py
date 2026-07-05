"""Doc58 batch-level identity and diversity review planning."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    BatchIdentityDiversityReview,
    GeneralSuiteRolePlan,
    HumanNaturalVariationPlan,
    ProjectIdentityAnchor,
)


class BatchIdentityDiversityReviewer:
    """Build batch-level checks for identity drift and over-cloned repetition."""

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        anchors: list[ProjectIdentityAnchor],
        suite_role_plan: GeneralSuiteRolePlan | None,
        human_variation_plan: HumanNaturalVariationPlan | None,
        generated_candidates: list[dict[str, Any]] | None = None,
    ) -> BatchIdentityDiversityReview:
        generated_candidates = list(generated_candidates or [])
        applies = bool(anchors or suite_role_plan or (human_variation_plan and human_variation_plan.applies))
        if not applies:
            return BatchIdentityDiversityReview(
                review_id=stable_id("batch_identity_diversity_review", project_id, job_id, "not_applicable"),
                project_id=project_id,
                job_id=job_id,
                applies=False,
            )
        identity_checks = _dedupe(
            rule
            for anchor in anchors
            for rule in anchor.identity_keep_rules[:4]
        )
        diversity_checks = _dedupe(
            [
                *(
                    human_variation_plan.batch_review_rules
                    if human_variation_plan and human_variation_plan.applies
                    else []
                ),
                "batch should preserve identity without cloning the exact same still",
                "at least two useful frames should differ in pose, angle, crop, expression, scene, or layout according to mode",
            ]
        )
        suite_checks = [
            f"{index}. {role.label}: {role.purpose}"
            for index, role in enumerate(suite_role_plan.roles, 1)
        ] if suite_role_plan else []
        issue_codes = _issue_codes(
            anchors=anchors,
            suite_role_plan=suite_role_plan,
            human_variation_plan=human_variation_plan,
            generated_candidates=generated_candidates,
        )
        status = "retry_recommended" if issue_codes else "planned"
        retry_patch = _retry_patch(issue_codes, anchors, suite_role_plan)
        return BatchIdentityDiversityReview(
            review_id=stable_id(
                "batch_identity_diversity_review",
                project_id,
                job_id,
                ",".join(anchor.anchor_id for anchor in anchors),
                suite_role_plan.plan_id if suite_role_plan else "",
            ),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            status=status,
            issue_codes=issue_codes,
            identity_keep_checks=identity_checks,
            diversity_checks=diversity_checks,
            suite_role_checks=suite_checks,
            retry_patch=retry_patch,
            user_visible_summary=[
                "V3 will check that the set keeps the same direction.",
                "V3 will also avoid making every image look like the same frozen frame.",
            ],
            metadata={
                "doc": "58",
                "anchor_count": len(anchors),
                "suite_role_count": len(suite_role_plan.roles) if suite_role_plan else 0,
                "candidate_count": len(generated_candidates),
            },
        )


def _issue_codes(
    *,
    anchors: list[ProjectIdentityAnchor],
    suite_role_plan: GeneralSuiteRolePlan | None,
    human_variation_plan: HumanNaturalVariationPlan | None,
    generated_candidates: list[dict[str, Any]],
) -> list[str]:
    codes: list[str] = []
    if suite_role_plan and suite_role_plan.requested_image_count >= 2 and len(suite_role_plan.roles) < suite_role_plan.requested_image_count:
        codes.append("suite_role_gap")
    if anchors and generated_candidates:
        repeated_roles = _repeated_values(item.get("suite_role") or item.get("role") for item in generated_candidates)
        if repeated_roles and suite_role_plan and suite_role_plan.variation_mode != "selection_candidates":
            codes.append("role_duplication_risk")
    if human_variation_plan and human_variation_plan.applies and generated_candidates:
        repeated_pose = _repeated_values(item.get("pose_signature") for item in generated_candidates)
        if repeated_pose:
            codes.append("over_cloned_pose_risk")
    return _dedupe(codes)


def _retry_patch(
    issue_codes: list[str],
    anchors: list[ProjectIdentityAnchor],
    suite_role_plan: GeneralSuiteRolePlan | None,
) -> dict[str, Any]:
    if not issue_codes:
        return {}
    prompt_additions = [
        "preserve the same identity/style anchor while changing pose, expression, camera angle, crop, or scene according to the planned role",
        *([f"follow suite roles: {', '.join(role.label for role in suite_role_plan.roles)}"] if suite_role_plan else []),
    ]
    negative_additions = [
        "same exact face angle, expression, pose, and crop in every image",
        *[rule for anchor in anchors for rule in anchor.forbidden_drift[:3]],
    ]
    return {
        "prompt_additions": _dedupe(prompt_additions),
        "negative_additions": _dedupe(negative_additions),
        "reason_codes": issue_codes,
    }


def _repeated_values(values: Any) -> list[str]:
    counts: dict[str, int] = {}
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return [key for key, count in counts.items() if count > 1]


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
