"""Doc256 photographic model-card front rebuild contract tests.

This focused matrix keeps only the behaviorally distinct checks for Phase2:
neutral card-family framing, Face-local photographic front composition,
Expression-owned affect composition, and isolation from Formal Core / Body /
25-degree / target-only paths.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path


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
