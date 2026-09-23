"""Shared output-scoped review authority; CELISIA is only a regression fixture."""
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.review_scope import classify_review_outcome


def inspection(output_id, status="pass", *, mode="hybrid", verified="verified", issues=()):
    return {
        "output_id": output_id, "asset_id": f"asset_{output_id}", "mode": mode,
        "verification_state": verified, "status": status,
        "detected_issues": [{"code": code} for code in issues],
        "evidence": {"provider_pixel_result_certified": mode == "hybrid"},
    }


def delivery(rows, **package_fields):
    result = SimpleNamespace(metadata={"post_generation_review_package": {
        "review_evidence_receipt_status": "complete", "inspections": rows,
        **package_fields,
    }})
    service = V3ProductApiService.__new__(V3ProductApiService)
    return service._public_final_delivery_projection(result)

@pytest.mark.parametrize("held_status", ["manual_review", "fail_retryable", "fail_final"])
def test_passing_sibling_is_delivered_independently(held_status):
    state, outputs, assets = delivery([
        inspection("good"), inspection("held", held_status),
    ])
    assert state["final_delivery_status"] == "ready"
    assert state["automatic_delivery_available"] is True
    assert outputs == {"good"}
    assert assets == {"asset_good"}
    assert state["partial_delivery"] is True


def test_missing_face_receipt_only_withholds_its_own_output():
    state, outputs, _ = delivery(
        [inspection("good")], doc276_face_integrity_required_output_ids=["missing"],
    )
    assert state["final_delivery_status"] == "ready"
    assert outputs == {"good"}


@pytest.mark.parametrize("mode", ["metadata_preflight", "metadata_only"])
@pytest.mark.parametrize("status", ["fail_retryable", "fail_final", "pass", "warning"])
def test_metadata_without_pixels_is_never_a_quality_verdict(mode, status):
    outcome = classify_review_outcome(inspection("preflight", status, mode=mode, verified="unverified"))
    assert outcome["quality_failure"] is False
    assert outcome["quality_assessment"] == "not_assessed"

def test_evidence_only_failure_is_not_a_pixel_defect():
    outcome = classify_review_outcome(inspection("held", "fail_final", issues=["face_integrity_unverified"]))
    assert outcome["quality_failure"] is False
    assert outcome["quality_assessment"] == "not_assessed"


def test_real_defect_remains_quality_failure():
    outcome = classify_review_outcome(inspection("bad", "fail_final", issues=["visible_text_artifact"]))
    assert outcome["quality_failure"] is True


def test_real_review_supersedes_legacy_mock_reject():
    report = SimpleNamespace(recommendation="reject")
    assert V3ProductApiService._public_candidate_recommendation(
        report, output_id="good", visible_output_ids={"good"},
    ) == "accept"
    assert V3ProductApiService._public_candidate_recommendation(
        report, output_id="held", visible_output_ids={"good"},
    ) is None


def test_metadata_package_cannot_authorize_mock_delivery():
    state, outputs, _ = delivery([inspection("preflight", mode="metadata_only", verified="unverified")])
    assert state["delivery_gate_applies"] is True
    assert state["automatic_delivery_available"] is False
    assert outputs == set()


def test_missing_review_receipt_boundary_fails_closed():
    result = SimpleNamespace(metadata={"post_generation_review_package": {
        "inspections": [inspection("good")],
    }})
    service = V3ProductApiService.__new__(V3ProductApiService)

    state, outputs, _ = service._public_final_delivery_projection(result)

    assert state["final_delivery_status"] == "withheld_review_failure"
    assert state["automatic_delivery_available"] is False
    assert outputs == set()


def test_missing_provider_pixel_certificate_cannot_authorize_delivery():
    row = inspection("uncertified")
    row["evidence"].pop("provider_pixel_result_certified")

    state, outputs, _ = delivery([row])

    assert state["final_delivery_status"] == "not_evaluated"
    assert state["automatic_delivery_available"] is False
    assert outputs == set()


def test_complete_receipt_with_closure_errors_cannot_authorize_delivery():
    state, outputs, _ = delivery(
        [inspection("contradictory")],
        review_evidence_receipt_errors=["closure_error"],
    )

    assert state["final_delivery_status"] == "withheld_review_failure"
    assert state["automatic_delivery_available"] is False
    assert outputs == set()


def test_complete_receipt_with_closure_errors_cannot_claim_public_certification():
    public = V3ProductApiService._public_post_generation_review({
        "review_evidence_receipt_status": "complete",
        "review_evidence_receipt_errors": ["closure_error"],
        "inspections": [inspection("contradictory")],
    })

    assert public["real_pixel_review_attempted"] is True
    assert public["real_pixel_review_certified"] is False


def test_non_dict_review_package_fails_closed():
    result = SimpleNamespace(metadata={"post_generation_review_package": "corrupt"})
    service = V3ProductApiService.__new__(V3ProductApiService)

    state, outputs, _ = service._public_final_delivery_projection(result)

    assert state["final_delivery_status"] == "withheld_review_failure"
    assert state["delivery_gate_applies"] is True
    assert outputs == set()


@pytest.mark.parametrize("bad_value", [None, "not-a-list", {"output": "good"}, 17])
def test_malformed_face_receipt_collection_fails_closed_without_projection_crash(bad_value):
    state, outputs, _ = delivery(
        [inspection("good")],
        doc276_face_integrity_required_output_ids=bad_value,
    )
    assert state["final_delivery_status"] == "withheld_review_failure"
    assert state["delivery_gate_applies"] is True
    assert outputs == set()


def test_malformed_inspections_are_projected_without_crashing():
    public = V3ProductApiService._public_post_generation_review({
        "review_evidence_receipt_status": "complete",
        "inspections": None,
    })

    assert public["inspections"] == []
    assert public["real_pixel_review_certified"] is False


def test_ecommerce_compaction_normalizes_malformed_review_collections():
    compact = V3ProductApiService._doc280_public_review_summary({
        "inspections": None,
        "recommended_output_ids": None,
    })

    assert compact["review_items"] == []
    assert compact["recommended_output_ids"] == []


def test_malformed_review_collections_survive_public_to_ecommerce_projection():
    row = inspection("corrupt")
    row["detected_issues"] = None
    public = V3ProductApiService._public_post_generation_review({
        "review_evidence_receipt_status": "complete",
        "inspections": [row],
        "recommended_output_ids": None,
    })
    compact = V3ProductApiService._doc280_public_review_summary(public)

    assert public["inspections"][0]["detected_issues"] == []
    assert compact["review_items"][0]["detected_issues"] == []
    assert compact["recommended_output_ids"] == []


def test_malformed_mode_and_hidden_collections_are_projected_safely():
    public = V3ProductApiService._public_post_generation_review({
        "inspections": [],
        "recommended_output_ids": [],
        "hidden_output_ids": None,
        "metadata": {
            "mode_differentiation_review": {
                "mode": "suite_expansion",
                "issue_codes": None,
                "user_visible_summary": None,
            }
        },
    })

    assert public["hidden_output_ids"] == []
    assert public["mode_semantics"]["issue_codes"] == []
    assert public["mode_semantics"]["user_visible_summary"] == []


def test_ecommerce_compaction_keeps_safe_per_output_delivery_authority():
    public = V3ProductApiService._public_post_generation_review({
        "review_evidence_receipt_status": "complete",
        "recommended_output_ids": ["good"],
        "inspections": [inspection("good"), inspection("held", "manual_review")],
    })
    compact = V3ProductApiService._doc280_public_review_summary(public)
    assert compact["recommended_output_ids"] == ["good"]
    assert [row["output_id"] for row in compact["review_items"]] == ["good", "held"]
    assert compact["quality_failure"] is False
    assert all("asset_id" not in row and "evidence" not in row for row in compact["review_items"])
    status = SimpleNamespace(metadata={"post_generation_review": compact, "final_delivery": {
        "final_delivery_status": "ready", "automatic_delivery_available": True,
        "delivery_gate_applies": True,
    }})
    assert V3ProjectModeService._canonical_final_delivery_output_ids(status) == {"good"}


@pytest.mark.parametrize("receipt", ["closed", "pending", "", None])
def test_incomplete_receipt_stays_fail_closed(receipt):
    state, outputs, _ = delivery([inspection("good")], review_evidence_receipt_status=receipt)
    assert state["automatic_delivery_available"] is False
    assert not outputs

def test_merger_retains_certified_sibling_when_other_review_lacks_pixels():
    from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.quality_review import OutputQualityReviewMerger
    from alchemy_creative_agent_3_0.tests.test_v3_doc316_universal_review_scope import _inspection, _resolution
    from alchemy_creative_agent_3_0.tests.test_v3_doc276_face_integrity_delivery_certification import _server_review_evidence_metadata
    resolutions = [_resolution("good"), _resolution("held")]
    evidence = {row.output_id: _server_review_evidence_metadata(row, identity_required=False) for row in resolutions}
    package = OutputQualityReviewMerger().build_package(job_id="job_doc316", project_id="project_doc316",
        resolutions=resolutions,
        inspections=[_inspection(output_id="good"), _inspection(output_id="held", status="manual_review", provider_pixel_result_certified=False)],
        review_evidence_plans={key: value["review_evidence_plan"] for key, value in evidence.items()},
        review_evidence_plan_digests={key: value["review_evidence_plan_digest"] for key, value in evidence.items()},
        review_evidence_receipt_status="complete")
    assert package.recommended_output_ids == ["good"]
    assert package.real_pixel_review is True
    assert package.metadata["universal_quality_failure"] is False


def test_explicitly_uncertified_pixels_cannot_authorize_delivery():
    row = inspection("not_certified")
    row["evidence"]["provider_pixel_result_certified"] = False
    state, outputs, _ = delivery([row])
    assert not outputs
    assert state["automatic_delivery_available"] is False

def test_duplicate_conflicting_rows_do_not_certify_the_same_output():
    state, outputs, _ = delivery([inspection("ambiguous"), inspection("ambiguous", "fail_final"), inspection("good")])
    assert state["final_delivery_status"] == "ready"
    assert outputs == {"good"}


def test_project_certification_cannot_promote_withheld_output_by_batch_ready_state():
    review = V3ProductApiService._public_post_generation_review({
        "inspections": [inspection("good"), inspection("held")],
        "recommended_output_ids": ["good"], "review_evidence_receipt_status": "complete"})
    status = SimpleNamespace(metadata={"post_generation_review": review, "final_delivery": {
        "final_delivery_status": "ready", "delivery_gate_applies": True, "automatic_delivery_available": True}})
    good = V3ProjectModeService._public_output_review_projection(status, SimpleNamespace(output_id="good"))
    held = V3ProjectModeService._public_output_review_projection(status, SimpleNamespace(output_id="held"))
    assert V3ProjectModeService._review_projection_allows_project_delivery(good) is True
    assert V3ProjectModeService._review_projection_allows_project_delivery(held) is False
    assert held["certification_state"] != "certified"

def test_asset_series_cannot_leak_held_candidate_through_shared_asset_id():
    asset = SimpleNamespace(asset_id="same_asset", priority=1, asset_type=SimpleNamespace(value="hero"),
        platform="generic_social", aspect_ratio="1:1", purpose="product", requires_text_overlay=False,
        requires_brand_consistency=True, metadata={})
    packaged = SimpleNamespace(asset_id="same_asset", uri="/held.png", metadata={
        "selected_candidate_id": "held_candidate", "candidate_metadata": {"output_id": "held"}})
    result = SimpleNamespace(series_plan=SimpleNamespace(assets=[asset]), asset_pack=SimpleNamespace(assets=[packaged]))
    service = V3ProductApiService.__new__(V3ProductApiService)
    service._project_candidate_metadata_from_result = lambda result, metadata, **kw: metadata
    from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
    assert service._asset_series(result, ProductJobStatusValue.GENERATED,
        visible_output_ids={"good"}, visible_asset_ids={"same_asset"}) == []


def test_explicit_pixel_certification_denial_is_respected_by_classifier():
    row = inspection("candidate")
    outcome = classify_review_outcome(row, provider_pixel_certified=False)
    assert outcome["quality_assessment"] == "not_assessed"
    assert outcome["quality_failure"] is False

def test_project_job_mixed_pixel_results_keep_delivery_and_review_counts_separate(tmp_path, monkeypatch):
    from alchemy_creative_agent_3_0.tests.test_v3_post_generation_vision_review import _service, _SequencedVisionProvider
    from alchemy_creative_agent_3_0.tests.test_v3_product_api_minimal_ux import _install_local_pixel_review_fixture
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import VisionOutputInspector
    monkeypatch.setenv("ALCHEMY_V3_JOB_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("ALCHEMY_V3_OUTPUT_DIR", str(tmp_path / "outputs"))
    service = _service(tmp_path)
    _install_local_pixel_review_fixture(service, tmp_path)
    service.vision_inspector = VisionOutputInspector(vision_provider=_SequencedVisionProvider([
        {"status": "pass", "confidence": 0.98, "issue_codes": []},
        {"status": "manual_review", "confidence": 0.3, "issue_codes": []},
    ]))
    handlers = V3ProductRouteHandlers(service=service)
    project = handlers.post_projects({"user_goal": "Two commercial product-only poster alternatives.",
        "primary_template_id": "general_template"})["project"]
    created = handlers.post_project_job(project["project_id"], {
        "user_input": "Two commercial product-only poster alternatives, no people.",
        "metadata": {"requested_image_count": 2}})
    generated = handlers.post_project_job_generate(project["project_id"], created["job_id"])
    review = generated["metadata"]["post_generation_review"]
    good_ids = set(review["recommended_output_ids"])
    assert len(good_ids) == 1
    assert generated["metadata"]["final_delivery"]["partial_delivery"] is True
    assert {row["output_id"] for row in generated["candidates"]} == good_ids
    full = handlers.get_project_outputs(project_id=project["project_id"], compact=True)
    assert {row["output_id"] for row in full["items"]} == good_ids
    assert len(full["review_items"]) == 1
    assert not good_ids.intersection(row["output_id"] for row in full["review_items"])
    home = handlers.get_project_outputs(project_ids=[project["project_id"]], surface="home_preview", compact=True)
    assert home["project_output_counts"][project["project_id"]] == 1
    assert home["project_review_counts"][project["project_id"]] == 1
    record = service.get_job_record(created["job_id"])
    assert len(record.generation_result.metadata["post_generation_review_package"]["inspections"]) == 2


@pytest.mark.parametrize("receipt", ["missing", "closed", "pending"])
@pytest.mark.parametrize("rows", [None, 17, {"bad": "row"}])
def test_malformed_inspections_do_not_crash_incomplete_receipt_projection(receipt, rows):
    package = {"inspections": rows}
    if receipt != "missing":
        package["review_evidence_receipt_status"] = receipt
    result = SimpleNamespace(metadata={"post_generation_review_package": package})
    state, outputs, _ = V3ProductApiService.__new__(V3ProductApiService)._public_final_delivery_projection(result)
    assert state["delivery_gate_applies"] is True
    assert state["automatic_delivery_available"] is False
    assert outputs == set()


@pytest.mark.parametrize("certificate", ["false", "true", 1, None])
def test_non_boolean_pixel_certificate_never_certifies_public_review(certificate):
    row = inspection("bad_certificate")
    row["evidence"]["provider_pixel_result_certified"] = certificate
    public = V3ProductApiService._public_post_generation_review({
        "review_evidence_receipt_status": "complete", "inspections": [row],
    })
    assert public["real_pixel_review_certified"] is False
    assert public["quality_assessment"] == "not_assessed"
    assert delivery([row])[1] == set()
