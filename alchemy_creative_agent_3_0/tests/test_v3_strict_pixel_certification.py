"""Stored pixel certification accepts only literal True across shared review."""
import pytest

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.quality_review import OutputQualityReviewMerger
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.review_scope import classify_review_outcome
from alchemy_creative_agent_3_0.tests.test_v3_doc316_universal_review_scope import _inspection, _resolution
from alchemy_creative_agent_3_0.tests.test_v3_doc276_face_integrity_delivery_certification import _server_review_evidence_metadata

INVALID = [False, None, "false", "not-certified", "true", 1, 0, 1.0, [], [True], {}, {"certified": True}]


def package(rows):
    resolutions = [_resolution(row.output_id) for row in rows]
    plans = {r.output_id: _server_review_evidence_metadata(r, identity_required=False) for r in resolutions}
    return OutputQualityReviewMerger().build_package(
        job_id="job_doc316", project_id="project_doc316", resolutions=resolutions, inspections=rows,
        review_evidence_plans={key: value["review_evidence_plan"] for key, value in plans.items()},
        review_evidence_plan_digests={key: value["review_evidence_plan_digest"] for key, value in plans.items()},
        review_evidence_receipt_status="complete",
    )


@pytest.mark.parametrize("value", INVALID)
@pytest.mark.parametrize("status", ["pass", "warning", "fail_final"])
def test_invalid_certificates_do_not_establish_pixel_quality(value, status):
    row = _inspection(status=status, provider_pixel_result_certified=value, issue_codes=["visible_text_artifact"])
    for override in (None, True):
        result = classify_review_outcome(row, provider_pixel_certified=override)
        assert result["evidence_state"] != "certified"
        assert result["quality_assessment"] == "not_assessed"
        assert result["quality_failure"] is False


@pytest.mark.parametrize("value", INVALID)
def test_merger_never_recommends_invalid_certificate_but_keeps_valid_sibling(value):
    bad = _inspection(output_id="bad", provider_pixel_result_certified=value)
    invalid_only = package([bad])
    assert invalid_only.recommended_output_ids == []
    assert invalid_only.real_pixel_review is False
    mixed = package([bad, _inspection(output_id="good")])
    assert mixed.recommended_output_ids == ["good"]
    assert mixed.real_pixel_review is True
    assert mixed.metadata["review_output_outcomes"]["bad"]["evidence_state"] != "certified"


def test_missing_certificate_does_not_certify_or_recommend():
    row = _inspection()
    row.evidence.clear()
    assert classify_review_outcome(row)["quality_assessment"] == "not_assessed"
    assert package([row]).recommended_output_ids == []


@pytest.mark.parametrize("override", [False, "false", "not-certified", 1, 1.0])
def test_override_cannot_use_truthiness_to_authorize_pixels(override):
    result = classify_review_outcome(_inspection(), provider_pixel_certified=override)
    assert result["evidence_state"] != "certified"
    assert result["quality_assessment"] == "not_assessed"


def test_literal_true_retains_quality_and_recommendation():
    row = _inspection()
    assert classify_review_outcome(row)["evidence_state"] == "certified"
    assert classify_review_outcome(row)["quality_assessment"] == "pass"
    assert package([row]).recommended_output_ids == [row.output_id]
