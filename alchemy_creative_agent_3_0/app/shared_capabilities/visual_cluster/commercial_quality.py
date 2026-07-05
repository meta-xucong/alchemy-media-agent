"""Commercial quality closure review for the V3 visual cluster."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    AntiAIFaceReviewResult,
    BatchIdentityDiversityReview,
    CommercialQualityIssue,
    HumanPhotorealismGuidance,
    ModeDifferentiationReview,
    RoleSpecificGenerationPlan,
    StrongReferenceContinuationPlan,
    VisualCommercialQualityReview,
    VisualQualityReviewReport,
)


COMMERCIAL_QUALITY_REVIEW_MODULE_ID = "commercial_quality_review"


class CommercialQualityClosureReviewer:
    """Summarize Doc64 quality closure signals without replacing existing review loops."""

    module_id = COMMERCIAL_QUALITY_REVIEW_MODULE_ID

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        variation_mode: str,
        subject_type: str,
        quality_reports: list[VisualQualityReviewReport],
        mode_review: ModeDifferentiationReview | None,
        batch_review: BatchIdentityDiversityReview | None,
        strong_reference_plan: StrongReferenceContinuationPlan | None,
        role_specific_plan: RoleSpecificGenerationPlan | None,
        human_photorealism: HumanPhotorealismGuidance | None,
        anti_ai_face_review: AntiAIFaceReviewResult | None,
    ) -> VisualCommercialQualityReview:
        issues = self._issues_from_sources(
            quality_reports=quality_reports,
            mode_review=mode_review,
            batch_review=batch_review,
            anti_ai_face_review=anti_ai_face_review,
        )
        issue_codes = _dedupe([issue.code for issue in issues])
        reference_status = self._reference_status(subject_type, strong_reference_plan)
        suite_status = self._suite_status(role_specific_plan, mode_review)
        finish_status = self._finish_status(quality_reports, issues)
        artifact_status = "retry_recommended" if any(self._is_artifact_issue(code) for code in issue_codes) else "pass"
        human_status = self._human_status(human_photorealism, anti_ai_face_review)
        status = self._overall_status(
            issues=issues,
            reference_status=reference_status,
            suite_status=suite_status,
            finish_status=finish_status,
            artifact_status=artifact_status,
            human_status=human_status,
        )
        retry_patch = self._merge_retry_patches(
            [report.retry_patch for report in quality_reports],
            anti_ai_face_review.retry_patch if anti_ai_face_review else {},
        )
        return VisualCommercialQualityReview(
            review_id=stable_id("visual_commercial_quality_review", project_id, job_id, variation_mode, ",".join(issue_codes)),
            project_id=project_id,
            job_id=job_id,
            status=status,
            variation_mode=variation_mode,
            subject_type=subject_type,
            reference_continuity_status=reference_status,
            suite_role_coverage_status=suite_status,
            commercial_finish_status=finish_status,
            artifact_cleanliness_status=artifact_status,
            human_realism_status=human_status,
            issue_codes=issue_codes,
            issues=issues,
            retry_patch=retry_patch,
            user_visible_summary=self._summary(status, reference_status, suite_status, human_status),
            metadata={
                "doc": "64",
                "module_id": self.module_id,
                "quality_report_count": len(quality_reports),
                "mode_review_status": mode_review.status if mode_review else None,
                "batch_review_status": batch_review.status if batch_review else None,
                "strong_reference_active": strong_reference_plan is not None,
                "human_photorealism_applies": bool(human_photorealism and human_photorealism.applies),
            },
        )

    def _issues_from_sources(
        self,
        *,
        quality_reports: list[VisualQualityReviewReport],
        mode_review: ModeDifferentiationReview | None,
        batch_review: BatchIdentityDiversityReview | None,
        anti_ai_face_review: AntiAIFaceReviewResult | None,
    ) -> list[CommercialQualityIssue]:
        issues: list[CommercialQualityIssue] = []
        for report in quality_reports:
            for raw_issue in report.detected_issues:
                code = str(raw_issue.get("code") or "").strip()
                if code:
                    issues.append(
                        CommercialQualityIssue(
                            code=code,
                            severity=str(raw_issue.get("severity") or "watch"),
                            retryable=bool(raw_issue.get("retryable", True)),
                            confidence=_safe_float(raw_issue.get("confidence"), default=0.7),
                            summary=str(raw_issue.get("message") or code.replace("_", " ")),
                            metadata={"source": "quality_report", "review_id": report.review_id},
                        )
                    )
        if mode_review and mode_review.status == "retry_recommended":
            for code in mode_review.issue_codes:
                issues.append(
                    CommercialQualityIssue(
                        code=code,
                        severity="medium",
                        retryable=True,
                        confidence=0.78,
                        summary=code.replace("_", " "),
                        metadata={"source": "mode_differentiation_review", "review_id": mode_review.review_id},
                    )
                )
        if batch_review and batch_review.status == "retry_recommended":
            for code in batch_review.issue_codes:
                issues.append(
                    CommercialQualityIssue(
                        code=code,
                        severity="medium",
                        retryable=True,
                        confidence=0.78,
                        summary=code.replace("_", " "),
                        metadata={"source": "batch_identity_diversity_review", "review_id": batch_review.review_id},
                    )
                )
        if anti_ai_face_review and anti_ai_face_review.issue_codes:
            for code in anti_ai_face_review.issue_codes:
                issues.append(
                    CommercialQualityIssue(
                        code=code,
                        severity=anti_ai_face_review.severity,
                        retryable=True,
                        confidence=0.82,
                        summary=code.replace("_", " "),
                        metadata={"source": "anti_ai_face_review", "review_id": anti_ai_face_review.review_id},
                    )
                )
        return issues

    def _reference_status(self, subject_type: str, plan: StrongReferenceContinuationPlan | None) -> str:
        if subject_type not in {"character", "product"}:
            return "not_applicable"
        if plan and plan.active_anchor_ids and plan.provider_required_reference_ids:
            return "strong_reference_ready"
        if plan and plan.active_anchor_ids:
            return "prompt_reference_ready"
        return "watch_no_selected_reference"

    def _suite_status(
        self,
        role_specific_plan: RoleSpecificGenerationPlan | None,
        mode_review: ModeDifferentiationReview | None,
    ) -> str:
        if mode_review and mode_review.status == "retry_recommended":
            return "retry_recommended"
        if role_specific_plan and role_specific_plan.role_recipes:
            return "planned"
        return "watch_no_role_plan"

    def _finish_status(
        self,
        reports: list[VisualQualityReviewReport],
        issues: list[CommercialQualityIssue],
    ) -> str:
        if any(report.status in {"fail", "fail_final"} for report in reports):
            return "fail"
        if issues or any(report.status in {"retry_recommended", "warning"} for report in reports):
            return "retry_recommended"
        return "pass"

    def _human_status(
        self,
        human_photorealism: HumanPhotorealismGuidance | None,
        anti_ai_face_review: AntiAIFaceReviewResult | None,
    ) -> str:
        if not human_photorealism or not human_photorealism.applies:
            return "not_applicable"
        if anti_ai_face_review and anti_ai_face_review.issue_codes:
            return "retry_recommended"
        return "planned"

    def _overall_status(
        self,
        *,
        issues: list[CommercialQualityIssue],
        reference_status: str,
        suite_status: str,
        finish_status: str,
        artifact_status: str,
        human_status: str,
    ) -> str:
        if finish_status == "fail" or any(issue.severity == "high" for issue in issues):
            return "fail"
        retry_states = {
            "retry_recommended",
            "watch_no_selected_reference",
            "watch_no_role_plan",
        }
        if (
            issues
            or reference_status in retry_states
            or suite_status in retry_states
            or finish_status in retry_states
            or artifact_status in retry_states
            or human_status in retry_states
        ):
            return "retry_recommended"
        return "pass"

    def _merge_retry_patches(self, *patches: Any) -> dict[str, list[str]]:
        merged: dict[str, list[str]] = {}
        for patch in patches:
            if not isinstance(patch, dict):
                continue
            for key, value in patch.items():
                values = _string_list(value)
                if values:
                    merged.setdefault(str(key), []).extend(values)
        return {key: _dedupe(values) for key, values in merged.items() if _dedupe(values)}

    def _summary(
        self,
        status: str,
        reference_status: str,
        suite_status: str,
        human_status: str,
    ) -> list[str]:
        if status == "pass":
            summary = ["Commercial quality checks are ready"]
        elif status == "retry_recommended":
            summary = ["V3 found a fixable quality gap"]
        else:
            summary = ["This result is not ready for delivery"]
        if reference_status in {"strong_reference_ready", "prompt_reference_ready"}:
            summary.append("Reference continuity is active")
        if suite_status in {"planned", "pass"}:
            summary.append("Image roles are planned")
        if human_status in {"planned", "pass"}:
            summary.append("Human realism guidance is active")
        return summary[:4]

    def _is_artifact_issue(self, code: str) -> bool:
        return any(token in code for token in ["watermark", "text", "badge", "artifact", "aigc", "signature"])


def _safe_float(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
