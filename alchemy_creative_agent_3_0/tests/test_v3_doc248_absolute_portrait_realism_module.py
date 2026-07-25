"""Doc248 absolute portrait realism hot-plug Enhanced module contracts."""

from __future__ import annotations

import inspect
import ast

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.absolute_portrait_realism import (
    ABSOLUTE_PORTRAIT_REALISM_PROFILE_ID,
    REQUIRED_REALISM_DIMENSIONS,
    AbsolutePortraitRealismProof,
    evaluate_absolute_portrait_realism,
    project_absolute_portrait_realism_enhanced_proof,
)


def _passing_dimensions() -> dict[str, float]:
    return {
        "eye_gaze_alignment": 0.91,
        "facial_micro_asymmetry": 0.84,
        "skin_micro_texture": 0.88,
        "hair_strand_randomness": 0.86,
        "ear_anatomy_clarity": 0.8,
        "natural_light_transition": 0.9,
        "camera_texture_response": 0.83,
        "commercial_beauty_preserved": 0.92,
    }


def _proof(**overrides: object) -> AbsolutePortraitRealismProof:
    payload = {
        "candidate_id": "candidate_front_1",
        "output_id": "v3_output_front_1",
        "dimensions": _passing_dimensions(),
        "evidence_codes": [
            "real_photo_eye_hair_skin_ear_light_verified",
            "commercial_beauty_preserved",
        ],
    }
    payload.update(overrides)
    return evaluate_absolute_portrait_realism(**payload)  # type: ignore[arg-type]


def test_doc248_passing_realism_proof_projects_to_formal_enhanced_proof() -> None:
    proof = _proof()
    enhanced = project_absolute_portrait_realism_enhanced_proof(proof)

    assert proof.eligible is True
    assert proof.status == "pass"
    assert enhanced.profile_id == ABSOLUTE_PORTRAIT_REALISM_PROFILE_ID
    assert enhanced.requirement_id == "absolute_portrait_realism_visible_evidence_v1"
    assert enhanced.candidate_id == "candidate_front_1"
    assert enhanced.output_id == "v3_output_front_1"
    assert enhanced.eligible is True
    assert set(REQUIRED_REALISM_DIMENSIONS) <= set(enhanced.dimensions)


@pytest.mark.parametrize(
    "missing_dimension",
    [
        "eye_gaze_alignment",
        "skin_micro_texture",
        "hair_strand_randomness",
        "ear_anatomy_clarity",
        "commercial_beauty_preserved",
    ],
)
def test_doc248_missing_visible_realism_dimension_fails_closed(missing_dimension: str) -> None:
    dimensions = _passing_dimensions()
    dimensions.pop(missing_dimension)

    proof = _proof(dimensions=dimensions)

    assert proof.eligible is False
    assert proof.status == "fail"
    assert "absolute_portrait_realism_evidence_missing" in proof.issue_codes
    enhanced = project_absolute_portrait_realism_enhanced_proof(proof)
    assert enhanced.eligible is False


@pytest.mark.parametrize(
    ("dimension", "issue"),
    [
        ("eye_gaze_alignment", "eye_gaze_or_perspective_inconsistent"),
        ("skin_micro_texture", "poreless_plastic_skin"),
        ("hair_strand_randomness", "pasted_or_over_regular_hair"),
        ("ear_anatomy_clarity", "simplified_ear_anatomy"),
    ],
)
def test_doc248_ai_face_artifact_dimensions_fail_without_lowering_gate(dimension: str, issue: str) -> None:
    dimensions = _passing_dimensions()
    dimensions[dimension] = 0.34

    proof = _proof(dimensions=dimensions, issue_codes=[issue])

    assert proof.eligible is False
    assert "absolute_portrait_realism_dimension_below_target" in proof.issue_codes
    assert issue in proof.issue_codes


@pytest.mark.parametrize(
    "issue",
    [
        "compression_noise_used_as_realism",
        "random_grain_used_as_realism",
        "blur_used_as_realism",
        "dirty_skin_used_as_realism",
        "beauty_degraded_for_realism",
        "identity_geometry_redesigned",
    ],
)
def test_doc248_fake_realism_degradation_strategy_is_rejected(issue: str) -> None:
    proof = _proof(issue_codes=[issue])

    assert proof.eligible is False
    assert "realism_degradation_strategy_rejected" in proof.issue_codes


def test_doc248_beauty_preservation_is_hard_requirement() -> None:
    dimensions = _passing_dimensions()
    dimensions["commercial_beauty_preserved"] = 0.62

    proof = _proof(dimensions=dimensions)

    assert proof.eligible is False
    assert "commercial_beauty_not_preserved" in proof.issue_codes


def test_doc248_public_summary_is_safe_and_stable() -> None:
    proof = _proof()
    summary = proof.public_summary()
    reloaded = AbsolutePortraitRealismProof.model_validate(proof.model_dump(mode="json"))

    assert reloaded == proof
    assert summary["eligible"] is True
    serialized = str(summary).lower()
    for forbidden in ("prompt", "provider", "mcp", "handoff", "artifact", "path", "raw", "api_key"):
        assert forbidden not in serialized


def test_doc248_private_or_malformed_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AbsolutePortraitRealismProof(
            candidate_id="candidate_1",
            output_id="output_1",
            status="pass",
            eligible=True,
            evidence_codes=["realism_verified"],
            dimensions={**_passing_dimensions(), "provider_raw_score": 0.9},
        )
    with pytest.raises(ValidationError):
        AbsolutePortraitRealismProof(
            candidate_id="candidate_1",
            output_id="output_1",
            status="pass",
            eligible=False,
            evidence_codes=["realism_verified"],
            dimensions=_passing_dimensions(),
        )


def test_doc248_module_does_not_import_provider_mcp_route_or_formal_core() -> None:
    import alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.absolute_portrait_realism as module

    tree = ast.parse(inspect.getsource(module))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(str(node.module or "").lower())

    for forbidden in ("formal_slot_acceptancecore", "product_api", "provider", "mcp", "route_handlers"):
        assert all(forbidden not in module_name for module_name in imported)

    source = inspect.getsource(module).lower()
    for forbidden_objective in ("undetectable", "detector evasion", "bypass detector"):
        assert forbidden_objective not in source


def test_doc248_module_is_slot_agnostic_and_hot_pluggable() -> None:
    proof = evaluate_absolute_portrait_realism(
        candidate_id="candidate_any_module",
        output_id="output_any_module",
        dimensions=_passing_dimensions(),
        evidence_codes=["real_photo_detail_review_verified"],
    )
    enhanced = project_absolute_portrait_realism_enhanced_proof(proof)

    assert enhanced.profile_id == "absolute_portrait_realism_v1"
    assert enhanced.owner == "v3_professional_enhanced_profile_contract"
    dumped = enhanced.model_dump(mode="json")
    assert "module" not in dumped
    assert "slot_key" not in dumped
