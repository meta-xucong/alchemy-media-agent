"""Merge post-generation image inspection into V3 visual review contracts."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    AutoRetryDecision,
    GeneratedOutputResolution,
    PostGenerationReviewPackage,
    RealReviewCandidateSignal,
    RealReviewSignalPackage,
    VisualInspectionReport,
    VisualQualityReviewReport,
)


class OutputQualityReviewMerger:
    """Convert Doc55 inspection reports into Doc51/Doc53/Doc66 review contracts."""

    def build_package(
        self,
        *,
        job_id: str,
        project_id: str | None,
        resolutions: list[GeneratedOutputResolution],
        inspections: list[VisualInspectionReport],
        max_attempts: int = 1,
    ) -> PostGenerationReviewPackage:
        reports = [self._review_report(inspection) for inspection in inspections]
        decisions = self._auto_retry_decisions(job_id, project_id, inspections, max_attempts=max_attempts)
        real_review_signal_package = self._real_review_signal_package(
            job_id=job_id,
            project_id=project_id,
            inspections=inspections,
        )
        recommended_output_ids = [
            report.output_id
            for report in reports
            if report.output_id and report.status in {"pass", "warning"}
        ]
        hidden_output_ids = [
            report.output_id
            for report in reports
            if report.output_id and report.status in {"fail_final"}
        ]
        return PostGenerationReviewPackage(
            package_id=stable_id("post_generation_review_package", project_id, job_id, len(inspections)),
            project_id=project_id,
            job_id=job_id,
            resolutions=resolutions,
            inspections=inspections,
            quality_review_reports=reports,
            auto_retry_decisions=[decision.model_dump(mode="json") for decision in decisions],
            real_review_signal_package=real_review_signal_package,
            recommended_output_ids=list(dict.fromkeys(recommended_output_ids)),
            hidden_output_ids=list(dict.fromkeys(hidden_output_ids)),
            user_visible_summary=self._package_summary(inspections, decisions),
            metadata={
                "doc": "55,66",
                "post_generation": True,
                "inspection_count": len(inspections),
                "retry_decision_count": len(decisions),
                "real_review_signal_package_id": real_review_signal_package.package_id,
            },
        )

    def _review_report(self, inspection: VisualInspectionReport) -> VisualQualityReviewReport:
        passed_checks = ["resolved generated output", "checked output after generation"]
        if inspection.status in {"pass", "warning"}:
            passed_checks.append("no automatic retry needed")
        return VisualQualityReviewReport(
            review_id=stable_id(
                "visual_quality_review_report",
                inspection.job_id,
                inspection.candidate_id,
                inspection.output_id,
                inspection.status,
            ),
            project_id=inspection.project_id,
            job_id=inspection.job_id,
            candidate_id=inspection.candidate_id,
            output_id=inspection.output_id,
            status=inspection.status,
            review_mode=inspection.mode,
            scores=dict(inspection.score_card),
            detected_issues=list(inspection.detected_issues),
            passed_checks=passed_checks,
            warning_notes=[item for item in [*inspection.drift_warnings, *inspection.artifact_warnings] if item],
            retry_patch=dict(inspection.retry_patch),
            user_visible_summary=list(inspection.user_visible_summary),
            metadata={
                **dict(inspection.metadata),
                "post_generation": True,
                "pre_generation": False,
                "inspection_id": inspection.inspection_id,
                "confidence": inspection.confidence,
            },
        )

    def _auto_retry_decisions(
        self,
        job_id: str,
        project_id: str | None,
        inspections: list[VisualInspectionReport],
        *,
        max_attempts: int,
    ) -> list[AutoRetryDecision]:
        retryable = [inspection for inspection in inspections if inspection.status == "fail_retryable" and inspection.retryable]
        if not retryable:
            return [
                AutoRetryDecision(
                    decision_id=stable_id("visual_auto_retry_decision", job_id, "post_generation", "pass"),
                    job_id=job_id,
                    project_id=project_id,
                    should_retry=False,
                    max_attempts=max_attempts,
                    user_visible_reason="V3 checked the generated images and did not find a clear fixable issue.",
                    metadata={"post_generation": True, "retryable_report_count": 0},
                )
            ]
        reason_codes = _dedupe(
            issue.get("code")
            for inspection in retryable
            for issue in inspection.detected_issues
            if issue.get("retryable", False)
        )
        retry_patch = self._merge_retry_patches([inspection.retry_patch for inspection in retryable])
        return [
            AutoRetryDecision(
                decision_id=stable_id("visual_auto_retry_decision", job_id, "post_generation", ",".join(reason_codes)),
                job_id=job_id,
                project_id=project_id,
                should_retry=True,
                max_attempts=max_attempts,
                reason_codes=reason_codes,
                retry_patch=retry_patch,
                user_visible_reason="V3 found a fixable visual issue and prepared a cleaner retry.",
                metadata={
                    "post_generation": True,
                    "retryable_report_count": len(retryable),
                    "source_inspection_ids": [inspection.inspection_id for inspection in retryable],
                },
            )
        ]

    def _real_review_signal_package(
        self,
        *,
        job_id: str,
        project_id: str | None,
        inspections: list[VisualInspectionReport],
    ) -> RealReviewSignalPackage:
        candidate_signals = [self._candidate_signal(inspection) for inspection in inspections]
        retryable_candidate_ids = _dedupe(
            signal.candidate_id for signal in candidate_signals if signal.retryable_issue_codes and signal.candidate_id
        )
        retryable_output_ids = _dedupe(
            signal.output_id for signal in candidate_signals if signal.retryable_issue_codes and signal.output_id
        )
        non_retryable_candidate_ids = _dedupe(
            signal.candidate_id
            for signal in candidate_signals
            if signal.candidate_id
            and signal.status in {"fail_final", "manual_review"}
            and not signal.retryable_issue_codes
        )
        issue_summary: dict[str, int] = {}
        issue_groups: list[str] = []
        for signal in candidate_signals:
            for code in signal.issue_codes:
                issue_summary[code] = issue_summary.get(code, 0) + 1
                group = _issue_group(code)
                if group and group not in issue_groups:
                    issue_groups.append(group)

        statuses = {signal.status for signal in candidate_signals}
        retryable = bool(retryable_candidate_ids or retryable_output_ids)
        return RealReviewSignalPackage(
            package_id=stable_id("real_review_signal_package", project_id, job_id, len(candidate_signals), ",".join(sorted(issue_summary))),
            project_id=project_id,
            job_id=job_id,
            candidate_signals=candidate_signals,
            retryable_candidate_ids=retryable_candidate_ids,
            retryable_output_ids=retryable_output_ids,
            non_retryable_candidate_ids=non_retryable_candidate_ids,
            issue_summary=issue_summary,
            issue_groups=issue_groups,
            mode_quality_status=self._group_status(candidate_signals, "mode"),
            reference_continuity_status=self._group_status(candidate_signals, "identity", "product"),
            commercial_readiness_status="retryable_issue" if retryable else "manual_review" if "manual_review" in statuses else "pass",
            user_visible_summary=self._real_review_summary(candidate_signals, retryable),
            metadata={"doc": "66", "post_generation": True, "signal_count": len(candidate_signals)},
        )

    def _candidate_signal(self, inspection: VisualInspectionReport) -> RealReviewCandidateSignal:
        issue_codes = _dedupe(issue.get("code") for issue in inspection.detected_issues if issue.get("code"))
        retryable_issue_codes = _dedupe(
            issue.get("code")
            for issue in inspection.detected_issues
            if issue.get("code") and bool(issue.get("retryable"))
        )
        if inspection.status == "fail_retryable" and inspection.retryable and retryable_issue_codes:
            action = "retry"
        elif inspection.status == "fail_final":
            action = "hide"
        elif inspection.status == "manual_review":
            action = "review"
        elif inspection.status == "warning":
            action = "keep_with_warning"
        else:
            action = "keep"
        issue_groups = _dedupe(_issue_group(code) for code in issue_codes if _issue_group(code))
        return RealReviewCandidateSignal(
            candidate_id=inspection.candidate_id,
            output_id=inspection.output_id,
            status=inspection.status,
            issue_codes=issue_codes,
            retryable_issue_codes=retryable_issue_codes,
            retry_patch=dict(inspection.retry_patch),
            recommended_action=action,
            user_visible_summary=list(inspection.user_visible_summary) or [self._candidate_summary(action)],
            metadata={
                "inspection_id": inspection.inspection_id,
                "inspection_mode": inspection.mode,
                "confidence": inspection.confidence,
                "issue_groups": issue_groups,
            },
        )

    def _group_status(self, signals: list[RealReviewCandidateSignal], *groups: str) -> str:
        target_groups = set(groups)
        matched = [
            signal
            for signal in signals
            if target_groups.intersection(set(_string_list(signal.metadata.get("issue_groups"))))
        ]
        if not matched:
            return "pass"
        if any(signal.retryable_issue_codes for signal in matched):
            return "retryable_issue"
        if any(signal.status == "manual_review" for signal in matched):
            return "manual_review"
        return "warning"

    def _candidate_summary(self, action: str) -> str:
        if action == "retry":
            return "This image has a fixable visual issue."
        if action == "hide":
            return "This image should not be shown as a final result."
        if action == "review":
            return "This image needs manual confirmation."
        if action == "keep_with_warning":
            return "This image is usable with a small warning."
        return "This image passed the automatic visual check."

    def _real_review_summary(
        self,
        signals: list[RealReviewCandidateSignal],
        retryable: bool,
    ) -> list[str]:
        if retryable:
            return ["V3 checked the real images.", "Fixable issues were found and scoped to the affected candidate."]
        if any(signal.status == "manual_review" for signal in signals):
            return ["V3 checked the real images.", "Some images need manual confirmation before retry."]
        if any(signal.status == "warning" for signal in signals):
            return ["V3 checked the real images.", "The set is usable with minor warnings."]
        return ["V3 checked the real images.", "No clear visual issue was found."]

    def _merge_retry_patches(self, patches: list[dict[str, Any]]) -> dict[str, Any]:
        keys = {
            "prompt_additions",
            "negative_additions",
            "negative_prompt_additions",
            "reference_requirements",
            "identity_reinforcement",
            "product_reinforcement",
            "brand_asset_reinforcement",
            "composition_repair",
            "artifact_repair",
            "object_removal_instruction",
        }
        merged: dict[str, list[str]] = {key: [] for key in keys}
        for patch in patches:
            for key in keys:
                merged[key].extend(_string_list(patch.get(key)))
        return {key: _dedupe(values) for key, values in merged.items() if _dedupe(values)}

    def _package_summary(
        self,
        inspections: list[VisualInspectionReport],
        decisions: list[AutoRetryDecision],
    ) -> list[str]:
        if any(decision.should_retry for decision in decisions):
            return ["V3 checked the generated images.", "Fixable issues were found and a cleaner retry is ready."]
        if any(inspection.status == "manual_review" for inspection in inspections):
            return ["V3 checked the generated images.", "Some images need manual confirmation before automatic retry."]
        if any(inspection.status == "warning" for inspection in inspections):
            return ["V3 checked the generated images.", "Small risks were found, but the images can still be reviewed."]
        return ["V3 checked the generated images.", "No clear visual issue was found."]


def _issue_group(code: str) -> str:
    text = str(code or "")
    if any(token in text for token in ["watermark", "signature", "text", "badge", "artifact", "mark"]):
        return "artifact"
    if any(token in text for token in ["identity", "face", "hair", "outfit", "body", "skin", "smile", "eyes"]):
        return "identity"
    if "product" in text or "label" in text or "logo" in text or "brand" in text:
        return "product"
    if any(token in text for token in ["mode", "role", "suite", "slot", "evidence_dimension"]):
        return "mode"
    if any(token in text for token in ["layout", "composition", "crop", "camera"]):
        return "layout"
    if any(token in text for token in ["provider", "timeout", "rate_limit"]):
        return "provider"
    if "quality" in text or "commercial" in text:
        return "quality"
    return "general"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
