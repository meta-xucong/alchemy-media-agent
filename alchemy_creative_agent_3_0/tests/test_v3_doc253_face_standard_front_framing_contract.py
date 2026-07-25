"""Doc253 Face standard-front framing contract red tests.

The framing envelope is a Face / Character Card view-role concern.  These tests
must not be satisfied by Doc252 micro-realism, transport canvas size, Formal
Core geometry logic, target-only collection, or auxiliary 25-degree bridges.
"""

from __future__ import annotations

import importlib

import pytest


def _module():
    return importlib.import_module("alchemy_creative_agent_3_0.app.visual_assets.face_standard_front_framing")


def _calibration() -> object:
    module = _module()
    return module.StandardFrontFramingCalibrationArtifact(
        artifact_id="standard_front_framing_envelope_calibration_v1",
        provenance="server_owned_calibration_v1",
        approval_status="approved",
        source_fixture_set="accepted_model_card_front_refs_v1",
        measurement_method="shared_vision_face_box_v1",
        face_box_width_band=[0.45, 0.49],
        face_box_height_band=[0.32, 0.35],
        face_center_x_band=[0.49, 0.54],
        face_center_y_band=[0.52, 0.55],
        round_variance_limits={
            "face_box_width_ratio": 0.02,
            "face_box_height_ratio": 0.02,
            "face_center_x": 0.02,
            "face_center_y": 0.02,
        },
        applies_to="face.standard_front.formal_slot",
        version="v1",
    )


def _metrics(
    *,
    candidate_id: str,
    output_id: str,
    width: float = 0.47,
    height: float = 0.33,
    center_x: float = 0.52,
    center_y: float = 0.535,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "output_id": output_id,
        "view_role": "standard_front",
        "slot_scope": "formal_slot",
        "shared_review_status": "pass",
        "transport_canvas_size": "1024x1536",
        "face_box_width_ratio": width,
        "face_box_height_ratio": height,
        "face_center_x": center_x,
        "face_center_y": center_y,
        "eye_line_y": 0.42,
        "head_top_margin": 0.055,
        "shoulder_visibility_ratio": 0.78,
    }


def test_doc253_generic_pass_without_numeric_framing_envelope_fails_standard_front() -> None:
    module = _module()

    proof = module.evaluate_standard_front_framing_envelope(
        {
            "candidate_id": "candidate_1",
            "output_id": "output_1",
            "view_role": "standard_front",
            "slot_scope": "formal_slot",
            "shared_review_status": "pass",
            "transport_canvas_size": "1024x1536",
        },
        calibration=_calibration(),
    )

    assert proof.eligible is False
    assert "standard_front_numeric_framing_missing" in proof.issue_codes


def test_doc253_transport_canvas_does_not_satisfy_framing() -> None:
    module = _module()

    proof = module.evaluate_standard_front_framing_envelope(
        {
            "candidate_id": "candidate_1",
            "output_id": "output_1",
            "view_role": "standard_front",
            "slot_scope": "formal_slot",
            "transport_canvas_size": "1024x1536",
        },
        calibration=_calibration(),
    )

    assert proof.eligible is False
    assert "transport_canvas_is_not_framing_evidence" in proof.issue_codes


def test_doc253_round_level_variance_is_face_adapter_enhanced_eligibility() -> None:
    module = _module()

    round_proof = module.evaluate_standard_front_round_framing_consistency(
        [
            _metrics(candidate_id="candidate_1", output_id="output_1", width=0.476207, height=0.332980),
            _metrics(candidate_id="candidate_2", output_id="output_2", width=0.446465, height=0.304249),
            _metrics(candidate_id="candidate_3", output_id="output_3", width=0.452909, height=0.321446),
        ],
        calibration=_calibration(),
    )

    assert round_proof.eligible is False
    assert round_proof.owner == "face_standard_front_framing_profile"
    assert "round_face_box_variance_exceeds_calibration" in round_proof.issue_codes
    assert "formal_core" not in str(round_proof.public_summary()).lower()


def test_doc253_doc252_micro_realism_cannot_compensate_for_framing_failure() -> None:
    module = _module()

    proof = module.evaluate_standard_front_framing_envelope(
        {
            "candidate_id": "candidate_1",
            "output_id": "output_1",
            "view_role": "standard_front",
            "slot_scope": "formal_slot",
            "shared_review_status": "pass",
            "transport_canvas_size": "1024x1536",
            "micro_real_human_fidelity_eligible": True,
        },
        calibration=_calibration(),
    )

    assert proof.eligible is False
    assert "standard_front_numeric_framing_missing" in proof.issue_codes


def test_doc253_valid_framing_does_not_require_doc252_micro_realism() -> None:
    module = _module()

    proof = module.evaluate_standard_front_framing_envelope(
        _metrics(candidate_id="candidate_1", output_id="output_1"),
        calibration=_calibration(),
    )

    assert proof.eligible is True
    assert proof.profile_id == "standard_front_framing_envelope_v1"
    assert "micro_real_human_fidelity" not in proof.model_dump(mode="json")


@pytest.mark.parametrize(
    ("override", "issue"),
    [
        ({"module": "expression_set"}, "standard_front_framing_scope_invalid"),
        ({"view_role": "expression.anger"}, "standard_front_framing_scope_invalid"),
        ({"slot_scope": "historical_context_only"}, "standard_front_framing_scope_invalid"),
        ({"shared_review_status": "manual_review"}, "standard_front_shared_review_not_pass"),
        ({"candidate_id": ""}, "standard_front_candidate_identity_missing"),
        ({"output_id": ""}, "standard_front_output_identity_missing"),
    ],
)
def test_doc253_evaluator_fail_closes_wrong_scope_review_or_identity(
    override: dict[str, str],
    issue: str,
) -> None:
    module = _module()
    metrics = _metrics(candidate_id="candidate_1", output_id="output_1")
    metrics["module"] = "face_identity"
    metrics.update(override)

    proof = module.evaluate_standard_front_framing_envelope(
        metrics,
        calibration=_calibration(),
    )

    assert proof.eligible is False
    assert issue in proof.issue_codes


@pytest.mark.parametrize(
    "scope",
    [
        {"module": "face_identity", "view_role": "standard_front", "slot_scope": "historical_context_only"},
        {"module": "face_identity", "view_role": "standard_front", "slot_scope": "target_only_existing_candidate_collection"},
        {"module": "face_identity", "view_role": "left_front_25", "slot_scope": "auxiliary_reference"},
        {"module": "face_identity", "view_role": "right_front_25", "slot_scope": "auxiliary_reference"},
        {"module": "expression_set", "view_role": "expression.anger", "slot_scope": "formal_slot"},
        {"module": "body_silhouette", "view_role": "body.front_full", "slot_scope": "formal_slot"},
    ],
)
def test_doc253_numeric_envelope_does_not_apply_to_excluded_scopes(scope: dict[str, str]) -> None:
    module = _module()

    assert module.standard_front_framing_envelope_applies(**scope) is False


def test_doc253_missing_calibration_artifact_prevents_production_enablement() -> None:
    module = _module()

    with pytest.raises(ValueError, match="standard_front_framing_calibration_required"):
        module.evaluate_standard_front_framing_envelope(
            _metrics(candidate_id="candidate_1", output_id="output_1"),
            calibration=None,
        )


@pytest.mark.parametrize(
    "override",
    [
        {"provenance": "user_supplied"},
        {"approval_status": "draft"},
        {"artifact_id": "unreviewed_calibration"},
    ],
)
def test_doc253_forged_or_unapproved_calibration_is_rejected(override: dict[str, str]) -> None:
    module = _module()
    payload = {
        "artifact_id": "standard_front_framing_envelope_calibration_v1",
        "provenance": "server_owned_calibration_v1",
        "approval_status": "approved",
        "source_fixture_set": "accepted_model_card_front_refs_v1",
        "measurement_method": "shared_vision_face_box_v1",
        "face_box_width_band": [0.45, 0.49],
        "face_box_height_band": [0.32, 0.35],
        "face_center_x_band": [0.49, 0.54],
        "face_center_y_band": [0.52, 0.55],
        "round_variance_limits": {
            "face_box_width_ratio": 0.02,
            "face_box_height_ratio": 0.02,
            "face_center_x": 0.02,
            "face_center_y": 0.02,
        },
        "applies_to": "face.standard_front.formal_slot",
        "version": "v1",
    }
    payload.update(override)

    with pytest.raises(ValueError):
        module.StandardFrontFramingCalibrationArtifact(**payload)
