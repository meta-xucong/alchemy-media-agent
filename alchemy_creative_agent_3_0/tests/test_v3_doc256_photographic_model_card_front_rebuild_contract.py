"""Doc256 photographic model-card front rebuild contract tests.

This focused matrix keeps only the behaviorally distinct checks for Phase2:
neutral card-family framing, Face-local photographic front composition,
Expression-owned affect composition, and isolation from Formal Core / Body /
25-degree / target-only paths.
"""

from __future__ import annotations

import importlib
import inspect
import math
from pathlib import Path
from types import SimpleNamespace

import pytest


def _card_family_module():
    return importlib.import_module(
        "alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.card_family_framing"
    )


def _face_module():
    return importlib.import_module(
        "alchemy_creative_agent_3_0.app.visual_assets.photographic_model_card_front"
    )


def _expression_module():
    return importlib.import_module(
        "alchemy_creative_agent_3_0.app.visual_assets.expression_model_card_framing"
    )


def _expression_review_module():
    return importlib.import_module(
        "alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review"
    )


def _character_card_module():
    return importlib.import_module("alchemy_creative_agent_3_0.app.visual_assets.character_card")


def _anchor_pack_module():
    return importlib.import_module("alchemy_creative_agent_3_0.app.visual_assets.anchor_pack")


def _anchor_host_module():
    return importlib.import_module("alchemy_creative_agent_3_0.app.product_api.anchor_pack_host")


class _NoopAnchorGenerator:
    def generate(self, request):  # pragma: no cover - not called by propagation test
        raise AssertionError("generation must not run")


class _NoopAnchorReviewer:
    def review(self, candidate):  # pragma: no cover - not called by propagation test
        raise AssertionError("review must not run")


def _calibration(*, applies_to: list[str] | None = None, approved: bool = True) -> dict[str, object]:
    return {
        "artifact_id": "close_model_card_framing_family_calibration_v1",
        "profile_id": "card_family_framing_v1",
        "version": "v1",
        "provenance": "server_owned_calibration_v1",
        "approval_status": "approved" if approved else "draft",
        "source_fixture_set": "photographer_model_card_front_positive_negative_v1",
        "measurement_method": "shared_vision_close_model_card_crop_v1",
        "applies_to": applies_to
        or ["face_identity:standard_front", "expression_set:delivery_slots"],
        "dimension_bands": {
            "model_card_crop_closeness": [0.82, 0.96],
            "shoulder_collar_context": [0.72, 0.95],
            "headroom_commercial_balance": [0.74, 0.94],
            "camera_distance_consistency": [0.86, 1.0],
        },
        "round_variance_limits": {
            "model_card_crop_closeness": 0.04,
            "shoulder_collar_context": 0.06,
            "headroom_commercial_balance": 0.05,
        },
    }


def _metrics(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "module": "face_identity",
        "view_role": "standard_front",
        "slot_scope": "formal_slot",
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "operation_id": "op_model_card_front_round1",
        "round_id": "round1",
        "shared_review_status": "pass",
        "transport_canvas_size": "1024x1536",
        "prompt_mentions_model_card": True,
        "framing_boolean_verified": True,
        "visible_evidence": {
            "hair": "visible_reviewed",
            "face": "visible_reviewed",
            "neck": "visible_reviewed",
            "collar": "visible_reviewed",
            "upper_shoulder": "visible_reviewed",
        },
        "dimensions": {
            "model_card_crop_closeness": 0.9,
            "shoulder_collar_context": 0.86,
            "headroom_commercial_balance": 0.88,
            "camera_distance_consistency": 0.91,
        },
    }
    payload.update(overrides)
    return payload


def _framing_pass(**overrides: object) -> dict[str, object]:
    payload = {
        "owner": "shared_card_family_framing",
        "contract_version": "v3_card_family_framing_contract_v1",
        "profile_id": "card_family_framing_v1",
        "requirement_id": "close_photographic_model_card_framing_v1",
        "status": "pass",
        "module": "face_identity",
        "view_role": "standard_front",
        "slot_scope": "formal_slot",
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "operation_id": "op_model_card_front_round1",
        "round_id": "round1",
        "evidence_codes": ["close_model_card_crop_verified"],
        "dimensions": {
            "model_card_crop_closeness": 0.9,
            "shoulder_collar_context": 0.86,
            "headroom_commercial_balance": 0.88,
            "camera_distance_consistency": 0.91,
        },
    }
    payload.update(overrides)
    return payload


def _realism_pass(**overrides: object) -> dict[str, object]:
    payload = {
        "owner": "shared_human_realism_foundation",
        "profile_id": "human_realism_v3_shared",
        "status": "pass",
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "operation_id": "op_model_card_front_round1",
        "round_id": "round1",
        "evidence_codes": [
            "real_camera_skin_texture_present",
            "natural_hair_strand_variation_present",
            "non_plastic_lighting_gradient_present",
            "commercial_beauty_preserved",
        ],
        "dimensions": {"human_realism": 0.91, "commercial_beauty": 0.94},
    }
    payload.update(overrides)
    return payload


def _visibility_pass(**overrides: object) -> dict[str, object]:
    payload = {
        "owner": "shared_human_realism_visibility",
        "status": "pass",
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "operation_id": "op_model_card_front_round1",
        "round_id": "round1",
        "applicability_receipts": {
            "eyes": "visible_reviewed",
            "skin": "visible_reviewed",
            "hair": "visible_reviewed",
            "ear_or_temple": "visible_reviewed",
            "garment_neckline": "visible_reviewed",
            "light_camera": "visible_reviewed",
        },
    }
    payload.update(overrides)
    return payload


def _affect_pass(**overrides: object) -> dict[str, object]:
    payload = {
        "owner": "expression_affect_profile",
        "profile_id": "expression.anger_affect_v1",
        "status": "pass",
        "module": "expression_set",
        "slot": "expression.anger",
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "operation_id": "op_expression_round1",
        "round_id": "round1",
        "evidence_codes": ["expression_affect_delta_verified"],
        "dimensions": {"affect_readability": 0.9, "identity_preserved_under_affect": 0.91},
    }
    payload.update(overrides)
    return payload


def _expression_framing_pass(**overrides: object) -> dict[str, object]:
    payload = _framing_pass(
        module="expression_set",
        slot="expression.anger",
        view_role="expression.anger",
        operation_id="op_expression_round1",
    )
    payload.update(overrides)
    return payload


def _expression_projector_score_card(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "model_card_crop_closeness": 0.9,
        "shoulder_collar_context": 0.86,
        "headroom_commercial_balance": 0.88,
        "camera_distance_consistency": 0.91,
        "expression_affect_readability": 0.9,
        "expression_identity_preserved_under_affect": 0.91,
    }
    payload.update(overrides)
    return payload


def _expression_review_binding(**overrides: object) -> dict[str, object]:
    payload = {
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "operation_id": "op_expression_round1",
        "round_id": "round1",
    }
    payload.update(overrides)
    return payload


def _assert_public_summary_safe(public_summary: dict[str, object]) -> None:
    text = str(public_summary).lower()
    for token in ("prompt", "provider", "path", "mcp", "handoff", "artifact", "raw"):
        assert token not in text


def test_doc256_card_family_framing_accepts_face_and_expression_scopes() -> None:
    card_family = _card_family_module()

    face = card_family.evaluate_card_family_framing(
        _metrics(),
        calibration=_calibration(),
    )
    expression = card_family.evaluate_card_family_framing(
        _metrics(module="expression_set", slot="expression.anger", view_role="expression.anger"),
        calibration=_calibration(),
    )

    assert face.eligible is True
    assert expression.eligible is True
    assert face.profile_id == expression.profile_id == "card_family_framing_v1"


def test_doc256_card_family_wrong_scope_or_transport_only_fails() -> None:
    card_family = _card_family_module()

    wrong_scope = card_family.evaluate_card_family_framing(
        _metrics(module="body_silhouette", view_role="body.front_full"),
        calibration=_calibration(),
    )
    transport_only = card_family.evaluate_card_family_framing(
        _metrics(dimensions={}),
        calibration=_calibration(),
    )

    assert wrong_scope.eligible is False
    assert "card_family_framing_scope_invalid" in wrong_scope.issue_codes
    assert transport_only.eligible is False
    assert "prompt_canvas_or_boolean_is_not_framing_proof" in transport_only.issue_codes


def test_doc256_card_family_calibration_missing_unapproved_or_wrong_scope_fails() -> None:
    card_family = _card_family_module()

    missing = card_family.evaluate_card_family_framing(_metrics(), calibration=None)
    unapproved = card_family.evaluate_card_family_framing(_metrics(), calibration=_calibration(approved=False))
    wrong_scope = card_family.evaluate_card_family_framing(
        _metrics(),
        calibration=_calibration(applies_to=["expression_set:delivery_slots"]),
    )

    assert "card_family_framing_calibration_required" in missing.issue_codes
    assert "card_family_framing_calibration_not_approved" in unapproved.issue_codes
    assert "card_family_calibration_scope_not_applicable" in wrong_scope.issue_codes


def test_doc256_card_family_visibility_binding_or_numeric_evidence_missing_fails() -> None:
    card_family = _card_family_module()

    visibility_missing = card_family.evaluate_card_family_framing(
        _metrics(visible_evidence={"hair": "visible_reviewed"}),
        calibration=_calibration(),
    )
    binding_mismatch = card_family.evaluate_card_family_framing(
        _metrics(candidate_id="other_candidate"),
        calibration=_calibration(),
        expected_binding={
            "candidate_id": "candidate_1",
            "output_id": "output_1",
            "operation_id": "op_model_card_front_round1",
            "round_id": "round1",
        },
    )
    non_finite = card_family.evaluate_card_family_framing(
        _metrics(dimensions=_metrics()["dimensions"] | {"model_card_crop_closeness": float("nan")}),
        calibration=_calibration(),
    )

    assert "card_family_visible_evidence_missing" in visibility_missing.issue_codes
    assert "card_family_binding_mismatch" in binding_mismatch.issue_codes
    assert "card_family_framing_dimension_not_finite" in non_finite.issue_codes


def test_doc256_card_family_round_consistency_requires_three_bound_candidates_and_stable_scale() -> None:
    card_family = _card_family_module()

    wrong_count = card_family.evaluate_card_family_round_consistency(
        [_metrics(candidate_id="candidate_1", output_id="output_1")],
        calibration=_calibration(),
        operation_id="op_model_card_front_round1",
        round_id="round1",
    )
    variance = card_family.evaluate_card_family_round_consistency(
        [
            _metrics(candidate_id="candidate_1", output_id="output_1"),
            _metrics(
                candidate_id="candidate_2",
                output_id="output_2",
                dimensions=_metrics()["dimensions"] | {"model_card_crop_closeness": 0.74},
            ),
            _metrics(candidate_id="candidate_3", output_id="output_3", round_id="other_round"),
        ],
        calibration=_calibration(),
        operation_id="op_model_card_front_round1",
        round_id="round1",
    )

    assert "card_family_round_requires_three_candidates" in wrong_count.issue_codes
    assert "card_family_round_scale_variance_exceeds_calibration" in variance.issue_codes
    assert "card_family_binding_mismatch" in variance.issue_codes


def test_doc256_face_composite_accepts_framing_realism_and_visibility_pass() -> None:
    face = _face_module()

    proof = face.evaluate_photographic_model_card_front_candidate(
        module="face_identity",
        view_role="standard_front",
        slot_scope="formal_slot",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_model_card_front_round1",
        round_id="round1",
        card_family_framing=_framing_pass(),
        shared_human_realism=_realism_pass(),
        shared_human_visibility=_visibility_pass(),
    )

    assert proof.eligible is True
    assert proof.profile_id == "photographic_model_card_front_v1"


def test_doc256_face_composite_fails_when_framing_fails() -> None:
    face = _face_module()

    proof = face.evaluate_photographic_model_card_front_candidate(
        module="face_identity",
        view_role="standard_front",
        slot_scope="formal_slot",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_model_card_front_round1",
        round_id="round1",
        card_family_framing=_framing_pass(
            status="fail",
            evidence_codes=["identity_document_headshot_crop_detected"],
        ),
        shared_human_realism=_realism_pass(),
        shared_human_visibility=_visibility_pass(),
    )

    assert proof.eligible is False
    assert "identity_document_headshot_crop_rejected" in proof.issue_codes


def test_doc256_face_composite_requires_card_family_authority_and_binding() -> None:
    face = _face_module()
    missing_binding = _framing_pass()
    missing_binding.pop("candidate_id")
    wrong_authority = _framing_pass(owner="face_local_framing", requirement_id="legacy_requirement")

    missing = face.evaluate_photographic_model_card_front_candidate(
        module="face_identity",
        view_role="standard_front",
        slot_scope="formal_slot",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_model_card_front_round1",
        round_id="round1",
        card_family_framing=missing_binding,
        shared_human_realism=_realism_pass(),
        shared_human_visibility=_visibility_pass(),
    )
    wrong = face.evaluate_photographic_model_card_front_candidate(
        module="face_identity",
        view_role="standard_front",
        slot_scope="formal_slot",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_model_card_front_round1",
        round_id="round1",
        card_family_framing=wrong_authority,
        shared_human_realism=_realism_pass(),
        shared_human_visibility=_visibility_pass(),
    )

    assert "candidate_binding_mismatch" in missing.issue_codes
    assert "card_family_framing_owner_invalid" in wrong.issue_codes
    assert "card_family_framing_requirement_invalid" in wrong.issue_codes


def test_doc256_face_composite_fails_when_shared_realism_beauty_or_visibility_invalid() -> None:
    face = _face_module()

    realism_bad = face.evaluate_photographic_model_card_front_candidate(
        module="face_identity",
        view_role="standard_front",
        slot_scope="formal_slot",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_model_card_front_round1",
        round_id="round1",
        card_family_framing=_framing_pass(),
        shared_human_realism=_realism_pass(
            status="fail",
            dimensions={"human_realism": 0.4, "commercial_beauty": 0.5},
        ),
        shared_human_visibility=_visibility_pass(),
    )
    visibility_bad = face.evaluate_photographic_model_card_front_candidate(
        module="face_identity",
        view_role="standard_front",
        slot_scope="formal_slot",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_model_card_front_round1",
        round_id="round1",
        card_family_framing=_framing_pass(),
        shared_human_realism=_realism_pass(candidate_id="other_candidate"),
        shared_human_visibility=_visibility_pass(owner="face_local_visibility"),
    )

    assert "shared_human_realism_failed" in realism_bad.issue_codes
    assert "commercial_beauty_degraded" in realism_bad.issue_codes
    assert "shared_human_realism_binding_mismatch" in visibility_bad.issue_codes
    assert "shared_human_visibility_owner_invalid" in visibility_bad.issue_codes


def test_doc256_face_legacy_profiles_do_not_promote_or_mix_with_new_profile() -> None:
    face = _face_module()

    legacy = face.project_legacy_profile_for_doc256_compatibility(
        {
            "profile_id": "absolute_portrait_realism_v1",
            "status": "pass",
            "candidate_id": "candidate_1",
            "output_id": "output_1",
        }
    )
    mixed = face.evaluate_photographic_model_card_front_candidate(
        module="face_identity",
        view_role="standard_front",
        slot_scope="formal_slot",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_model_card_front_round1",
        round_id="round1",
        card_family_framing=_framing_pass(),
        shared_human_realism=_realism_pass(
            profile_id="micro_real_human_fidelity_v1",
            evidence_codes=["micro_real_human_fidelity_profile_passed"],
        ),
        shared_human_visibility=_visibility_pass(),
    )

    assert legacy.compatibility_read_only is True
    assert legacy.eligible is False
    assert "legacy_profile_not_doc256_completion" in legacy.issue_codes
    assert "legacy_profile_mixed_with_doc256_profile" in mixed.issue_codes


def test_doc256_face_public_summary_sanitizes_private_fields() -> None:
    face = _face_module()

    proof = face.evaluate_photographic_model_card_front_candidate(
        module="face_identity",
        view_role="standard_front",
        slot_scope="formal_slot",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_model_card_front_round1",
        round_id="round1",
        card_family_framing=_framing_pass(),
        shared_human_realism=_realism_pass(
            evidence_codes=[
                "real_camera_skin_texture_present",
                "provider_raw_payload_should_not_leak",
                "prompt_reference_should_not_leak",
                "mcp_handoff_should_not_leak",
            ]
        ),
        shared_human_visibility=_visibility_pass(),
    )

    _assert_public_summary_safe(proof.public_summary())


def _doc256_anchor_candidate_and_review(
    *,
    evidence_codes: list[str] | None = None,
    operation_id: str | None = "op_model_card_front_round1",
    round_id: str | None = "round1",
    enhanced_review_dimensions: dict[str, float] | None = None,
):
    anchor_pack = _anchor_pack_module()
    candidate = anchor_pack.AnchorCandidateResult(
        candidate_id="candidate_1",
        view_id="view_output_1",
        output_id="output_1",
        view_role="standard_front",
        candidate_index=1,
        source_candidate_ids=["candidate_1"],
        source_asset_ids=["source_asset_1"],
        brain_plan_id="brain_plan_1",
        canonical_prompt_hash="prompt_hash_1",
        prompt_compilation_id="prompt_compile_1",
        prompt_reference_parity_verified=True,
        operation_id=operation_id,
        round_id=round_id,
    )
    shared = anchor_pack.FormalSlotSharedReviewSummary(
        status="pass",
        evidence_codes=["shared_real_pixel_review_verified"],
        score_dimensions=["same_person_readability", "human_realism"],
        framing_delta_dimensions=["model_card_crop_closeness"],
    )
    review = anchor_pack.AnchorReviewDecision(
        status="pass",
        identity_scores=anchor_pack.IdentityScoreSummary(
            same_face_score=0.93,
            visual_quality_score=0.94,
            distinctive_feature_score=0.92,
            human_realism_score=0.91,
            pose_compliance_score=0.93,
            ai_overperfection_penalty=0.02,
            evidence_codes=evidence_codes
            or [
                "doc256_card_family_framing_profile_passed",
                "doc256_shared_human_realism_profile_passed",
                "doc256_shared_human_visibility_profile_passed",
                "doc256_visibility_eyes_visible_reviewed",
                "doc256_visibility_skin_visible_reviewed",
                "doc256_visibility_hair_visible_reviewed",
                "doc256_visibility_ear_or_temple_visible_reviewed",
                "doc256_visibility_garment_neckline_visible_reviewed",
                "doc256_visibility_light_camera_visible_reviewed",
            ],
        ),
        shared_review_receipts=[shared.model_dump()],
        enhanced_review_dimensions=enhanced_review_dimensions
        if enhanced_review_dimensions is not None
        else {
            "model_card_crop_closeness": 0.9,
            "shoulder_collar_context": 0.86,
            "headroom_commercial_balance": 0.88,
            "camera_distance_consistency": 0.91,
        },
    )
    return candidate, review


def test_doc256_phase3a_face_standard_front_projects_one_doc256_enhanced_summary() -> None:
    anchor_pack = _anchor_pack_module()
    candidate, review = _doc256_anchor_candidate_and_review()

    summary = anchor_pack.AnchorPackPreparationService._face_standard_front_enhanced_proof(
        candidate,
        review,
        photographic_model_card_front_required=True,
        absolute_portrait_realism_required=False,
        micro_real_human_fidelity_required=False,
    )

    assert summary.profile_id == "photographic_model_card_front_v1"
    assert summary.requirement_id == "photographic_model_card_front_enhanced_eligibility_v1"
    assert summary.eligible is True
    assert summary.candidate_id == "candidate_1"
    assert summary.output_id == "output_1"
    assert "photographic_model_card_front_profile_passed" in summary.evidence_codes
    assert all("absolute_portrait" not in code and "micro_real" not in code for code in summary.evidence_codes)


def test_doc256_phase3a_face_missing_visibility_fails_closed_without_doc248_or_doc252_fallback() -> None:
    anchor_pack = _anchor_pack_module()
    candidate, review = _doc256_anchor_candidate_and_review(
        evidence_codes=[
            "doc256_card_family_framing_profile_passed",
            "doc256_shared_human_realism_profile_passed",
            "doc256_shared_human_visibility_profile_passed",
        ]
    )

    summary = anchor_pack.AnchorPackPreparationService._face_standard_front_enhanced_proof(
        candidate,
        review,
        photographic_model_card_front_required=True,
        absolute_portrait_realism_required=False,
        micro_real_human_fidelity_required=False,
    )

    assert summary.eligible is False
    assert "shared_human_visibility_evidence_missing" in summary.issue_codes
    assert all("absolute_portrait" not in code and "micro_real" not in code for code in summary.evidence_codes)


def test_doc256_phase3a_face_requires_numeric_framing_dimensions_not_pass_code_only() -> None:
    anchor_pack = _anchor_pack_module()
    candidate, review = _doc256_anchor_candidate_and_review(enhanced_review_dimensions={})

    summary = anchor_pack.AnchorPackPreparationService._face_standard_front_enhanced_proof(
        candidate,
        review,
        photographic_model_card_front_required=True,
        absolute_portrait_realism_required=False,
        micro_real_human_fidelity_required=False,
    )

    assert summary.eligible is False
    assert "card_family_framing_failed" in summary.issue_codes


def test_doc256_phase3a_face_requires_real_operation_and_round_binding() -> None:
    anchor_pack = _anchor_pack_module()
    candidate, review = _doc256_anchor_candidate_and_review(operation_id=None, round_id=None)

    summary = anchor_pack.AnchorPackPreparationService._face_standard_front_enhanced_proof(
        candidate,
        review,
        photographic_model_card_front_required=True,
        absolute_portrait_realism_required=False,
        micro_real_human_fidelity_required=False,
    )

    assert summary.eligible is False
    assert "candidate_binding_mismatch" in summary.issue_codes


def test_doc256_phase3a_trusted_face_scope_required_and_host_evidence_is_scope_gated() -> None:
    anchor_pack = _anchor_pack_module()
    anchor_host = _anchor_host_module()

    with pytest.raises(ValueError, match="photographic_model_card_front_requires_character_card_standard_front"):
        anchor_pack.AnchorGenerationRequest(
            project_id="project_1",
            people_asset_id="asset_1",
            pack_version_id="pack_1",
            view_role="standard_front",
            candidate_index=1,
            preparation_intent="front",
            root_source_asset_id="source_asset_1",
            reference_evidence_ids=["source_asset_1"],
            photographic_model_card_front_required=True,
            capture_scope="anchor_pack",
        )

    request = anchor_pack.AnchorGenerationRequest(
        project_id="project_1",
        people_asset_id="asset_1",
        pack_version_id="pack_1",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="front",
        root_source_asset_id="source_asset_1",
        reference_evidence_ids=["source_asset_1"],
        photographic_model_card_front_required=True,
        capture_scope="character_card_face_identity",
    )
    score_card = {
        "doc256_card_family_framing_profile_passed": 1.0,
        "doc256_shared_human_realism_profile_passed": 1.0,
        "doc256_shared_human_visibility_profile_passed": 1.0,
        "doc256_visibility_eyes_visible_reviewed": 1.0,
        "doc256_visibility_skin_visible_reviewed": 1.0,
        "doc256_visibility_hair_visible_reviewed": 1.0,
        "doc256_visibility_ear_or_temple_visible_reviewed": 1.0,
        "doc256_visibility_garment_neckline_visible_reviewed": 1.0,
        "doc256_visibility_light_camera_visible_reviewed": 1.0,
        "model_card_crop_closeness": 0.9,
        "shoulder_collar_context": 0.86,
        "headroom_commercial_balance": 0.88,
        "camera_distance_consistency": 0.91,
    }

    evidence = anchor_host.ProductApiAnchorPackPreparationHost._photographic_model_card_front_evidence_codes(
        request,
        score_card,
    )
    dimensions = anchor_host.ProductApiAnchorPackPreparationHost._photographic_model_card_front_dimensions(
        request,
        score_card,
    )

    assert "doc256_card_family_framing_profile_passed" in evidence
    assert "doc256_visibility_eyes_visible_reviewed" in evidence
    assert dimensions == {
        "model_card_crop_closeness": 0.9,
        "shoulder_collar_context": 0.86,
        "headroom_commercial_balance": 0.88,
        "camera_distance_consistency": 0.91,
    }


def test_doc256_phase3a_round_id_propagates_without_default_and_bad_dimensions_return_empty() -> None:
    anchor_pack = _anchor_pack_module()
    anchor_host = _anchor_host_module()
    root = anchor_pack.RootSourceProvenance(
        source_type="uploaded_portrait",
        source_asset_id="source_asset_1",
        project_id="project_1",
    )
    asset = anchor_pack.PeopleAsset(
        people_asset_id="asset_1",
        project_id="project_1",
        subject_kind="human_person",
        face_identity_module=anchor_pack.FaceIdentityModule(
            module_id="face_module_1",
            people_asset_id="asset_1",
        ),
        root_source_provenance=root,
        preparation_intent="front",
    )
    service = anchor_pack.AnchorPackPreparationService(
        generator=_NoopAnchorGenerator(),
        reviewer=_NoopAnchorReviewer(),
    )
    request = anchor_pack.AnchorPackPreparationRequest(
        project_id="project_1",
        asset=asset,
        root_source_provenance=root,
        preparation_intent="front",
        face_view_scope="character_card",
        generation_channel="mcp",
        round_id="round42",
        photographic_model_card_front_required=True,
    )

    generation_request = service._generation_request(
        request=request,
        pack_version_id="pack_1",
        view_role="standard_front",
        candidate_index=1,
        reference_evidence_ids=["source_asset_1"],
    )
    missing_round_request = anchor_pack.AnchorPackPreparationRequest(
        project_id="project_1",
        asset=asset,
        root_source_provenance=root,
        preparation_intent="front",
        face_view_scope="character_card",
        generation_channel="mcp",
        photographic_model_card_front_required=True,
    )

    assert generation_request.round_id == "round42"
    assert service._generation_request(
        request=missing_round_request,
        pack_version_id="pack_1",
        view_role="standard_front",
        candidate_index=1,
        reference_evidence_ids=["source_asset_1"],
    ).round_id is None
    assert anchor_host.ProductApiAnchorPackPreparationHost._photographic_model_card_front_dimensions(
        generation_request,
        {
            "model_card_crop_closeness": 0.9,
            "shoulder_collar_context": math.nan,
            "headroom_commercial_balance": 0.88,
            "camera_distance_consistency": 0.91,
        },
    ) == {}


def test_doc256_expression_composite_accepts_neutral_framing_and_owned_affect() -> None:
    expression = _expression_module()

    summary = expression.compose_expression_model_card_enhanced_summary(
        module="expression_set",
        slot="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        card_family_framing=_expression_framing_pass(),
        affect_proof=_affect_pass(),
    )

    assert summary.eligible is True
    assert summary.summary_kind == "module_neutral_enhanced_eligibility"
    assert not hasattr(summary, "winner_candidate_id")
    assert not hasattr(summary, "formal_slot_receipt")


def test_doc256_expression_composite_fails_when_framing_fails() -> None:
    expression = _expression_module()

    summary = expression.compose_expression_model_card_enhanced_summary(
        module="expression_set",
        slot="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        card_family_framing=_expression_framing_pass(status="fail"),
        affect_proof=_affect_pass(),
    )

    assert summary.eligible is False
    assert "card_family_framing_failed" in summary.issue_codes
    assert "affect_pass_cannot_compensate_framing_fail" in summary.issue_codes


def test_doc256_expression_composite_fails_when_affect_fails() -> None:
    expression = _expression_module()

    summary = expression.compose_expression_model_card_enhanced_summary(
        module="expression_set",
        slot="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        card_family_framing=_expression_framing_pass(),
        affect_proof=_affect_pass(status="fail"),
    )

    assert summary.eligible is False
    assert "expression_affect_profile_failed" in summary.issue_codes
    assert "framing_pass_cannot_compensate_affect_fail" in summary.issue_codes


def test_doc256_expression_binding_or_legacy_target_only_fails() -> None:
    expression = _expression_module()

    mismatch = expression.compose_expression_model_card_enhanced_summary(
        module="expression_set",
        slot="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        card_family_framing=_expression_framing_pass(candidate_id="other_candidate"),
        affect_proof=_affect_pass(output_id="other_output"),
    )
    legacy = expression.project_legacy_expression_receipt_for_doc256_compatibility(
        {
            "module": "expression_set",
            "slot": "expression.anger",
            "acceptance_mode": "target_only_existing_candidate_collection",
            "winner_output_id": "old_output",
        }
    )

    assert "expression_card_family_binding_mismatch" in mismatch.issue_codes
    assert "expression_affect_binding_mismatch" in mismatch.issue_codes
    assert legacy.compatibility_read_only is True
    assert "legacy_target_only_not_doc256_completion" in legacy.issue_codes


def test_doc256_expression_requires_card_family_and_affect_authority_and_binding() -> None:
    expression = _expression_module()
    framing_missing = _expression_framing_pass()
    framing_missing.pop("output_id")
    affect_missing = _affect_pass()
    affect_missing.pop("candidate_id")

    summary = expression.compose_expression_model_card_enhanced_summary(
        module="expression_set",
        slot="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        card_family_framing=framing_missing | {"owner": "expression_local_framing"},
        affect_proof=affect_missing | {"owner": "shared_card_family_framing", "profile_id": "shared_affect"},
    )

    assert "expression_card_family_binding_mismatch" in summary.issue_codes
    assert "card_family_framing_owner_invalid" in summary.issue_codes
    assert "expression_affect_binding_mismatch" in summary.issue_codes
    assert "expression_affect_owner_invalid" in summary.issue_codes
    assert "expression_affect_profile_invalid" in summary.issue_codes


def _doc256_expression_candidate(**overrides: object) -> SimpleNamespace:
    payload = {
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "module": "expression_set",
        "slot_key": "expression.anger",
        "candidate_index": 1,
        "operation_id": "op_expression_round1",
        "round_id": "round1",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _doc256_expression_review(
    *,
    card_family_framing: dict[str, object] | None = None,
    affect_proof: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        status="pass",
        expression_model_card_proofs={
            "card_family_framing": card_family_framing
            if card_family_framing is not None
            else _expression_framing_pass(),
            "affect_proof": affect_proof if affect_proof is not None else _affect_pass(),
        },
    )


def test_doc256_phase3b_expression_candidate_contract_carries_operation_round_binding() -> None:
    character_card = _character_card_module()

    candidate = character_card.CharacterCardCandidateResult(
        candidate_id="candidate_1",
        output_id="output_1",
        module="expression_set",
        slot_key="expression.anger",
        candidate_index=1,
        source_candidate_ids=["candidate_1"],
        source_output_ids=["output_1"],
        canonical_prompt_hash="prompt_hash_1",
        prompt_compilation_id="prompt_compile_1",
        prompt_reference_parity_verified=True,
        operation_id="op_expression_round1",
        round_id="round1",
    )

    assert candidate.operation_id == "op_expression_round1"
    assert candidate.round_id == "round1"


def test_doc256_phase3b_expression_formal_proof_uses_card_family_and_affect_summary() -> None:
    character_card = _character_card_module()

    summary = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=_doc256_expression_review(),
    )

    assert summary.profile_id == "expression_model_card_delivery_v1"
    assert summary.requirement_id == "expression_model_card_framing_and_affect_v1"
    assert summary.eligible is True
    assert "expression_model_card_profile_passed" in summary.evidence_codes
    assert not hasattr(summary, "winner_candidate_id")
    assert not hasattr(summary, "formal_slot_receipt")


def test_doc256_phase3b_expression_framing_and_affect_do_not_compensate_each_other() -> None:
    character_card = _character_card_module()

    framing_failed = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=_doc256_expression_review(card_family_framing=_expression_framing_pass(status="fail")),
    )
    affect_failed = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=_doc256_expression_review(affect_proof=_affect_pass(status="fail")),
    )

    assert framing_failed.eligible is False
    assert "card_family_framing_failed" in framing_failed.issue_codes
    assert affect_failed.eligible is False
    assert "expression_affect_profile_failed" in affect_failed.issue_codes


def test_doc256_phase3b_expression_formal_proof_requires_operation_round_binding() -> None:
    character_card = _character_card_module()

    missing_binding = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(operation_id=None),
        review=_doc256_expression_review(),
    )
    mismatched_binding = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(operation_id="wrong_operation"),
        review=_doc256_expression_review(),
    )

    assert missing_binding.eligible is False
    assert "expression_model_card_binding_missing" in missing_binding.issue_codes
    assert mismatched_binding.eligible is False
    assert "expression_card_family_binding_mismatch" in mismatched_binding.issue_codes
    assert "expression_affect_binding_mismatch" in mismatched_binding.issue_codes


def test_doc256_expression_review_projector_supplies_proofs_to_existing_consumer() -> None:
    expression_review = _expression_review_module()
    character_card = _character_card_module()

    proofs = expression_review.project_expression_model_card_proofs(
        slot_key="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        review_binding=_expression_review_binding(),
        score_card=_expression_projector_score_card(),
        issue_codes=[],
        verified=True,
        raw_status="pass",
        acceptance_mode="standard_three_candidate",
    )
    summary = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=SimpleNamespace(status="pass", expression_model_card_proofs=proofs),
    )

    assert set(proofs) == {"card_family_framing", "affect_proof"}
    assert proofs["card_family_framing"]["owner"] == "shared_card_family_framing"
    assert proofs["affect_proof"]["owner"] == "expression_affect_profile"
    assert summary.profile_id == "expression_model_card_delivery_v1"
    assert summary.eligible is True


def test_doc256_expression_review_projector_fails_when_proof_missing_or_binding_mismatches() -> None:
    expression_review = _expression_review_module()
    character_card = _character_card_module()

    missing_framing = expression_review.project_expression_model_card_proofs(
        slot_key="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        review_binding=_expression_review_binding(),
        score_card=_expression_projector_score_card(model_card_crop_closeness=None),
        issue_codes=[],
        verified=True,
        raw_status="pass",
        acceptance_mode="standard_three_candidate",
    )
    mismatched_binding = expression_review.project_expression_model_card_proofs(
        slot_key="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        review_binding=_expression_review_binding(output_id="other_output"),
        score_card=_expression_projector_score_card(),
        issue_codes=[],
        verified=True,
        raw_status="pass",
        acceptance_mode="standard_three_candidate",
    )

    missing_summary = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=SimpleNamespace(status="pass", expression_model_card_proofs=missing_framing),
    )
    mismatched_summary = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=SimpleNamespace(status="pass", expression_model_card_proofs=mismatched_binding),
    )

    assert missing_summary.eligible is False
    assert "card_family_framing_failed" in missing_summary.issue_codes
    assert mismatched_summary.eligible is False
    assert "expression_card_family_binding_mismatch" in mismatched_summary.issue_codes
    assert "expression_affect_binding_mismatch" in mismatched_summary.issue_codes


def test_doc256_expression_review_projector_rejects_warning_status() -> None:
    expression_review = _expression_review_module()
    character_card = _character_card_module()

    proofs = expression_review.project_expression_model_card_proofs(
        slot_key="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        review_binding=_expression_review_binding(),
        score_card=_expression_projector_score_card(),
        issue_codes=[],
        verified=True,
        raw_status="warning",
        acceptance_mode="standard_three_candidate",
    )
    summary = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=SimpleNamespace(status="warning", expression_model_card_proofs=proofs),
    )

    assert proofs["card_family_framing"]["status"] == "fail"
    assert proofs["affect_proof"]["status"] == "fail"
    assert "expression_model_card_shared_review_not_pass" in proofs["card_family_framing"]["issue_codes"]
    assert summary.eligible is False
    assert "card_family_framing_failed" in summary.issue_codes


def test_doc256_expression_review_projector_requires_nonempty_expected_binding() -> None:
    expression_review = _expression_review_module()
    character_card = _character_card_module()

    proofs = expression_review.project_expression_model_card_proofs(
        slot_key="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="",
        round_id="round1",
        review_binding=_expression_review_binding(operation_id=""),
        score_card=_expression_projector_score_card(),
        issue_codes=[],
        verified=True,
        raw_status="pass",
        acceptance_mode="standard_three_candidate",
    )
    summary = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(operation_id=""),
        review=SimpleNamespace(status="pass", expression_model_card_proofs=proofs),
    )

    assert "expression_model_card_review_binding_mismatch" in proofs["card_family_framing"]["issue_codes"]
    assert "expression_model_card_review_binding_mismatch" in proofs["affect_proof"]["issue_codes"]
    assert summary.eligible is False
    assert "expression_model_card_binding_missing" in summary.issue_codes


def test_doc256_expression_review_projector_does_not_upgrade_legacy_target_only() -> None:
    expression_review = _expression_review_module()
    character_card = _character_card_module()

    proofs = expression_review.project_expression_model_card_proofs(
        slot_key="expression.anger",
        candidate_id="candidate_1",
        output_id="output_1",
        operation_id="op_expression_round1",
        round_id="round1",
        review_binding=_expression_review_binding(),
        score_card=_expression_projector_score_card(),
        issue_codes=[],
        verified=True,
        raw_status="pass",
        acceptance_mode="target_only_existing_candidate_collection",
    )
    doc256_summary = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=SimpleNamespace(status="pass", expression_model_card_proofs=proofs),
    )
    legacy_summary = character_card.CharacterCardPreparationService._formal_expression_enhanced_proof(
        slot_key="expression.anger",
        candidate=_doc256_expression_candidate(),
        review=SimpleNamespace(status="pass"),
    )

    assert doc256_summary.eligible is False
    assert "legacy_target_only_not_doc256_completion" in proofs["card_family_framing"]["issue_codes"]
    assert "legacy_target_only_not_doc256_completion" in proofs["affect_proof"]["issue_codes"]
    assert "card_family_framing_failed" in doc256_summary.issue_codes
    assert "expression_affect_profile_failed" in doc256_summary.issue_codes
    assert legacy_summary.profile_id == "expression_slot_profile_v1"


def test_doc256_expression_adapter_does_not_import_face_local_front_module() -> None:
    expression = _expression_module()
    source = inspect.getsource(expression)

    assert "photographic_model_card_front" not in source
    assert "evaluate_photographic_model_card_front_candidate" not in source
    assert "card_family_framing" in source


def test_doc256_formal_core_remains_unaware_of_doc256_tokens() -> None:
    formal_core = Path("alchemy_creative_agent_3_0/app/visual_assets/formal_slot_acceptance.py").read_text(
        encoding="utf-8"
    )

    forbidden_tokens = [
        "Doc256",
        "photographic_model_card",
        "card_family_framing",
        "model_card_crop",
        "human_realism",
        "identity_document_headshot",
    ]
    for token in forbidden_tokens:
        assert token not in formal_core


def test_doc256_body_25_degree_target_only_and_historical_context_are_excluded() -> None:
    card_family = _card_family_module()

    excluded_scopes = [
        {"module": "body_silhouette", "slot": "body.front_full", "view_role": "body.front_full", "slot_scope": "formal_slot"},
        {"module": "face_identity", "slot": "left_front_25", "view_role": "left_front_25", "slot_scope": "auxiliary_reference"},
        {"module": "face_identity", "slot": "standard_front", "view_role": "standard_front", "slot_scope": "target_only_existing_candidate_collection"},
        {"module": "face_identity", "slot": "standard_front", "view_role": "standard_front", "slot_scope": "historical_context_only"},
    ]

    for scope in excluded_scopes:
        assert card_family.card_family_framing_applies(**scope) is False
