"""DOC316 universal review scope and evidence/quality separation tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatus
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    GeneratedOutputResolution,
    VisualInspectionReport,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.quality_review import (
    OutputQualityReviewMerger,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.review_scope import (
    UNIVERSAL_REVIEW_ISSUE_CODES,
    UNIVERSAL_REVIEW_MODES,
    classify_review_outcome,
    universal_review_scope,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector import VisionOutputInspector


def _inspection(
    *,
    output_id: str = "output_doc316",
    status: str = "pass",
    mode: str = "hybrid",
    verification_state: str = "verified",
    issue_codes: list[str] | None = None,
    provider_pixel_result_certified: bool = True,
) -> VisualInspectionReport:
    return VisualInspectionReport(
        inspection_id=f"inspection_{output_id}",
        project_id="project_doc316",
        job_id="job_doc316",
        candidate_id=f"candidate_{output_id}",
        asset_id=f"asset_{output_id}",
        output_id=output_id,
        mode=mode,
        status=status,
        verification_state=verification_state,
        confidence=0.96,
        detected_issues=[
            {
                "code": code,
                "severity": "low" if code == "face_integrity_unverified" else "medium",
                "retryable": False,
            }
            for code in (issue_codes or [])
        ],
        evidence={"provider_pixel_result_certified": provider_pixel_result_certified},
    )


def _resolution(output_id: str = "output_doc316") -> GeneratedOutputResolution:
    return GeneratedOutputResolution(
        resolution_id=f"resolution_{output_id}",
        project_id="project_doc316",
        job_id="job_doc316",
        candidate_id=f"candidate_{output_id}",
        asset_id=f"asset_{output_id}",
        output_id=output_id,
        status="ready",
        mime_type="image/png",
    )


@pytest.mark.parametrize(
    ("finding", "status", "action"),
    [
        (None, "manual_review", "review"),
        ({"region": "Face shadow", "expected_excerpt": "cool white light", "observed": "Amber reflection."}, "manual_review", "review"),
        ({"region": "Face shadow", "expected_excerpt": "soft reflected fill", "observed": "soft reflected fill"}, "manual_review", "review"),
        ({"region": "Unlit cheek", "expected_excerpt": "soft reflected fill", "observed": "The cheek disappears into a hard black shadow."}, "fail_retryable", "retry"),
    ],
)
def test_lighting_retry_requires_local_pixel_evidence_against_this_output(finding, status, action) -> None:
    resolution = _resolution()
    metadata = {
        "user_input": "Cold white alley lighting.",
        "reviewed_output_direction": {
            "source": "persisted_output_record",
            "output_id": resolution.output_id,
            "prompt": "Warm amber from screen left with soft reflected fill on the shadow side.",
        },
    }
    report = VisionOutputInspector()._from_provider_payload(
        resolution, {"status": "fail_retryable", "confidence": 0.9, "issue_codes": ["lighting_mismatch"],
                     "lighting_mismatch_evidence": finding, "summary": ["The lighting feels different."]},
        mode="hybrid", provider_name="fixture", metadata=metadata,
    )
    assert report.status == status
    signal = OutputQualityReviewMerger()._candidate_signal(report)
    assert signal.recommended_action == action
    if action == "retry":
        assert "Unlit cheek" in signal.observed_review_evidence[0]
        assert "soft reflected fill" in signal.observed_review_evidence[1]
    else:
        assert not signal.retryable_issue_codes
        assert classify_review_outcome(report)["quality_failure"] is False
    review_prompt = _inspection_prompt(metadata)
    assert "lighting_mismatch_evidence" in review_prompt
    assert "current output's signed lighting" in review_prompt


def test_lighting_refinement_uses_only_the_targeted_output_evidence() -> None:
    service = V3ProductApiService()
    signals = [
        {"output_id": output_id, "recommended_action": "retry", "observed_review_evidence": [finding]}
        for output_id, finding in (("left", "Hard shadow on cheek."), ("right", "The sign is unreadable."))
    ]
    review = {
        "inspections": [{"output_id": output_id, "asset_id": f"asset_{output_id}"} for output_id in ("left", "right")],
        "real_review_signal_package": {"candidate_signals": signals},
    }
    result = SimpleNamespace(
        metadata={"post_generation_review_package": review, "visual_cluster": review},
        series_plan=SimpleNamespace(assets=[SimpleNamespace(asset_id=f"asset_{side}") for side in ("left", "right")]),
    )
    observations = service._brain_retry_review_observations(result, ["asset_left"])
    assert observations == ["Output 1: Hard shadow on cheek."]
    request = BrainRunRequest(
        user_input="Warm storefront with reflected fill",
        stage="provider_prompt_finalize",
        metadata={"canonical_prompt_context": {"retry_evidence": {
            "active": True, "issue_codes": ["lighting_mismatch"], "observed_review_evidence": observations,
        }}},
    )
    payload = json.loads(build_remote_payload(request))
    contract = payload["remote_response_contract"]
    assert "only to its named output index" in contract
    assert "key light's screen direction and relative position" in contract
    assert "where reflected fill should reach" in contract
    assert "relative strength and color" in contract


def test_review_card_uses_its_own_lighting_reason_and_keeps_history() -> None:
    issue = {"code": "lighting_mismatch", "message": "Lighting may not match the intended direction."}
    original = {
        "output_id": "original", "status": "fail_retryable", "detected_issues": [issue],
        "user_visible_summary": ["Foreground reflections were cooler than expected."],
        "evidence": {"signed_lighting_mismatch": {"expected_excerpt": "SIGNED PROMPT"}},
    }
    retry = {
        "output_id": "refined", "status": "fail_retryable", "detected_issues": [
            {**issue, "message": "Lighting: the cheek on the shadow side still has a hard edge."},
        ],
    }
    kept = {"output_id": "kept", "status": "pass"}
    source = {"review_attempts": [{"inspections": [original, kept]}], "inspections": [retry, kept]}
    review = V3ProductApiService._public_post_generation_review(source)
    status = ProductJobStatus(
        job_id="job_doc316", status="generated", api_namespace="/api/v3", ui_entry_route="/v3",
        metadata={"post_generation_review": review},
    )
    status = V3ProjectModeService._project_output_job_status_projection(status)
    for row, reason in (
        (original, original["user_visible_summary"][0]),
        (retry, retry["detected_issues"][0]["message"]),
    ):
        item = V3ProjectModeService._public_output_review_projection(status, SimpleNamespace(output_id=row["output_id"]))
        assert V3ProjectModeService._public_project_review_reason(item) == reason
        assert "SIGNED PROMPT" not in str(item)
    assert set(review["output_review_details"]) == {"original", "refined"}


def test_doc316_evidence_only_manual_review_is_not_quality_failure() -> None:
    outcome = classify_review_outcome(
        _inspection(
            status="manual_review",
            issue_codes=["face_integrity_unverified"],
        )
    )

    assert outcome["quality_assessment"] == "not_assessed"
    assert outcome["quality_failure"] is False
    assert outcome["evidence_state"] == "incomplete"
    assert outcome["review_reason"] == "evidence_incomplete"
    assert outcome["quality_issue_codes"] == []
    assert outcome["evidence_issue_codes"] == ["face_integrity_unverified"]


def test_doc316_real_quality_failure_remains_a_quality_failure() -> None:
    outcome = classify_review_outcome(
        _inspection(
            status="fail_retryable",
            issue_codes=["visible_text_artifact"],
        )
    )

    assert outcome["quality_assessment"] == "fail_retryable"
    assert outcome["quality_failure"] is True
    assert outcome["evidence_state"] == "certified"
    assert outcome["review_reason"] == "quality_issue"


def test_doc316_mode_contract_is_shared_across_all_generation_modes() -> None:
    scope = universal_review_scope()
    assert scope["applies_to_modes"] == list(UNIVERSAL_REVIEW_MODES)
    for mode in UNIVERSAL_REVIEW_MODES:
        metadata = {"variation_mode": mode, "user_input": "a coherent visual request"}
        contract = active_review_contract(metadata)
        prompt = _inspection_prompt(metadata)
        assert contract["universal_review_scope"] == scope
        assert set(UNIVERSAL_REVIEW_ISSUE_CODES).issubset(set(contract["issue_codes"]))
        assert contract["mode_semantics_separate"] is True
        assert "same universal visual-quality contract in every V3 generation mode" in prompt
        assert "ModeAwareRoleDirector review" in prompt


def test_doc316_package_records_evidence_hold_without_claiming_quality_failure() -> None:
    inspection = _inspection(
        status="manual_review",
        issue_codes=["face_integrity_unverified"],
    )
    package = OutputQualityReviewMerger().build_package(
        job_id="job_doc316",
        project_id="project_doc316",
        resolutions=[_resolution()],
        inspections=[inspection],
        review_evidence_receipt_status="closed",
    )

    # The fixture exercises the package classifier only; plan identity is
    # intentionally not revalidated by the merger itself.
    metadata = package.metadata
    assert metadata["universal_review_scope"]["mode_agnostic"] is True
    assert metadata["universal_quality_failure"] is False
    assert metadata["review_evidence_state"] == "incomplete"
    assert metadata["review_reason"] == "evidence_incomplete"
    assert "no visual quality failure was established" in package.user_visible_summary[0]
    assert metadata["review_candidate_output_ids"] == ["output_doc316"]


def test_doc316_public_projection_exposes_separate_quality_and_evidence_axes() -> None:
    review = V3ProductApiService._public_post_generation_review(  # noqa: SLF001
        {
            "review_evidence_receipt_status": "complete",
            "resolutions": [{"output_id": "output_doc316", "status": "ready"}],
            "inspections": [
                {
                    "output_id": "output_doc316",
                    "mode": "hybrid",
                    "status": "manual_review",
                    "verification_state": "verified",
                    "detected_issues": [{"code": "face_integrity_unverified"}],
                    "evidence": {"provider_pixel_result_certified": True},
                }
            ],
            "metadata": {
                "mode_differentiation_review": {
                    "mode": "delivery_suite",
                    "status": "pass",
                    "role_coverage_status": "pass",
                    "issue_codes": [],
                    "user_visible_summary": ["suite roles remain distinct"],
                }
            },
        }
    )

    assert review["quality_assessment"] == "not_assessed"
    assert review["quality_failure"] is False
    assert review["evidence_state"] == "incomplete"
    assert review["review_reason"] == "evidence_incomplete"
    assert review["inspections"][0]["quality_failure"] is False
    assert review["inspections"][0]["evidence_state"] == "incomplete"
    assert review["mode_semantics"]["mode"] == "delivery_suite"
    assert review["mode_semantics"]["separate_from_universal_quality"] is True


def test_doc316_frontends_use_evidence_specific_hold_copy() -> None:
    root = Path(__file__).resolve().parents[2]
    desktop = (root / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    mobile = (root / "src_skeleton" / "app" / "mobile_static" / "mobile.js").read_text(encoding="utf-8")

    assert "v3UniversalReviewHoldKind" in desktop
    assert "mobileV3UniversalReviewHoldKind" in mobile
    assert "尚未证明图片质量不合格" in desktop
    assert "尚未证明图片质量不合格" in mobile
    # Keep the legacy fallback string for old jobs that predate DOC316.
    assert "图片已经生成，但自动质量审查未通过" in desktop
    assert "图片已经生成，但自动质量审查未通过" in mobile
