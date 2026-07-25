"""Doc252 micro real-human fidelity Enhanced module red contracts.

These tests intentionally describe the next module boundary before production
implementation exists.  They must not be satisfied by Doc248 alone, Formal
Core, Provider/MCP routing, prompt rewrites, or detector-evasion tricks.
"""

from __future__ import annotations

import importlib
import inspect
import ast
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    ProductApiAnchorPackPreparationHost,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import (
    ProfessionalModeRuntimeBridge,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    active_review_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateUnavailable,
    AnchorCandidateResult,
    AnchorGenerationRequest,
    AnchorPackPreparationRequest,
    AnchorPackPreparationService,
    AnchorReviewDecision,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotAcceptanceCore,
)


def _module():
    return importlib.import_module(
        "alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.micro_real_human_fidelity"
    )


def _passing_dimensions() -> dict[str, float]:
    return {
        "non_mirrored_catchlights": 0.94,
        "natural_eyelid_asymmetry": 0.91,
        "gaze_axis_consistency": 0.95,
        "sclera_micro_texture": 0.9,
        "non_plastic_iris_detail": 0.92,
        "strand_width_variation": 0.91,
        "flyaway_baby_hair_evidence": 0.88,
        "temple_hair_skin_integration": 0.9,
        "non_uniform_hair_edge_silhouette": 0.89,
        "pore_scale_texture": 0.9,
        "cheek_tonal_variation": 0.91,
        "nose_wing_shadow_naturalness": 0.88,
        "non_ceramic_highlight_transition": 0.9,
        "lip_chin_material_transition": 0.89,
        "natural_microcontrast": 0.91,
        "sensor_lens_response_plausibility": 0.88,
        "highlight_rolloff_believability": 0.9,
        "commercial_beauty_preserved": 0.95,
        "clean_model_card_finish": 0.96,
        "age_appropriate_attractiveness_preserved": 0.94,
    }


def _applicability() -> dict[str, dict[str, str]]:
    applicability = {
        key: {
            "applicability": "applicable",
            "visibility": "visible_and_reviewable",
            "status": "pass",
        }
        for key in _passing_dimensions()
    }
    for key in (
        "ear_cartilage_fold_clarity",
        "left_right_ear_nonidentity",
        "ear_hair_boundary_naturalness",
        "fabric_weave_irregularity",
        "collar_tension_plausibility",
        "seam_edge_nonuniformity",
    ):
        applicability[key] = {
            "applicability": "not_applicable",
            "visibility": "outside_frame",
            "status": "not_applicable",
        }
    return applicability


def _shared_receipt() -> dict[str, object]:
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
        "status": "pass",
        "evidence_codes": ["shared_visual_review_verified"],
        "issue_codes": [],
        "score_dimensions": ["generic_visual_quality"],
        "framing_delta_dimensions": ["front_card_framing"],
    }


def _anchor_candidate(index: int) -> AnchorCandidateResult:
    return AnchorCandidateResult(
        candidate_id=f"candidate_front_{index}",
        view_id=f"view_front_{index}",
        output_id=f"v3_output_front_{index}",
        view_role="standard_front",
        candidate_index=index,
        source_candidate_ids=[f"candidate_front_{index}"],
        source_asset_ids=["source_original"],
        brain_plan_id=f"brain_plan_{index}",
        canonical_prompt_hash=f"prompt_hash_{index}",
        prompt_compilation_id=f"prompt_compilation_{index}",
        prompt_reference_parity_verified=True,
    )


def _absolute_evidence() -> list[str]:
    return [
        "absolute_eye_gaze_alignment_verified",
        "absolute_facial_micro_asymmetry_verified",
        "absolute_skin_micro_texture_verified",
        "absolute_hair_strand_randomness_verified",
        "absolute_ear_anatomy_clarity_verified",
        "absolute_natural_light_transition_verified",
        "absolute_camera_texture_response_verified",
        "absolute_commercial_beauty_preserved",
    ]


def _micro_evidence(*, missing: str | None = None) -> list[str]:
    evidence = [
        f"micro_{dimension}_verified"
        for dimension in _passing_dimensions()
        if dimension != missing
    ]
    for dimension in (
        "ear_cartilage_fold_clarity",
        "left_right_ear_nonidentity",
        "ear_hair_boundary_naturalness",
        "fabric_weave_irregularity",
        "collar_tension_plausibility",
        "seam_edge_nonuniformity",
    ):
        if dimension != missing:
            evidence.append(f"micro_{dimension}_not_applicable_outside_frame")
    return evidence


def _anchor_review(
    index: int,
    *,
    same_face_score: float,
    absolute_pass: bool = True,
    micro_pass: bool = True,
    missing_micro_dimension: str | None = None,
) -> AnchorReviewDecision:
    evidence_codes = ["face_identity_shared_identity_review_verified"]
    if absolute_pass:
        evidence_codes.extend(_absolute_evidence())
    if micro_pass:
        evidence_codes.extend(_micro_evidence(missing=missing_micro_dimension))
    return AnchorReviewDecision(
        status="pass",
        identity_scores=IdentityScoreSummary(
            same_face_score=same_face_score,
            distinctive_feature_score=same_face_score,
            human_realism_score=0.96,
            visual_quality_score=0.97,
            pose_compliance_score=0.95,
            evidence_codes=evidence_codes,
        ),
        shared_review_receipts=[_shared_receipt()],
    )


def test_doc252_visible_required_micro_dimension_missing_fails_closed() -> None:
    module = _module()
    dimensions = _passing_dimensions()
    dimensions.pop("sclera_micro_texture")

    proof = module.evaluate_micro_real_human_fidelity(
        candidate_id="candidate_front_1",
        output_id="v3_output_front_1",
        dimensions=dimensions,
        applicability=_applicability(),
        evidence_codes=["micro_real_human_fidelity_reviewed"],
        enabled_by="server_feature_flag_v1",
    )

    assert proof.eligible is False
    assert proof.status == "fail"
    assert "micro_real_human_visible_evidence_missing" in proof.issue_codes


def test_doc252_not_applicable_requires_visibility_receipt_and_is_not_pass_credit() -> None:
    module = _module()
    dimensions = _passing_dimensions()
    applicability = _applicability()
    dimensions.pop("ear_cartilage_fold_clarity", None)
    applicability["ear_cartilage_fold_clarity"] = {
        "applicability": "not_applicable",
        "visibility": "outside_frame",
        "status": "not_applicable",
    }

    proof = module.evaluate_micro_real_human_fidelity(
        candidate_id="candidate_front_1",
        output_id="v3_output_front_1",
        dimensions=dimensions,
        applicability=applicability,
        evidence_codes=["micro_real_human_fidelity_reviewed"],
        enabled_by="server_feature_flag_v1",
    )

    assert proof.eligible is True
    assert proof.applicability["ear_cartilage_fold_clarity"].status == "not_applicable"
    assert "ear_cartilage_fold_clarity" not in proof.passed_dimensions
    assert "ear_cartilage_fold_clarity" in proof.not_applicable_dimensions


def test_doc252_optional_dimension_missing_applicability_receipt_fails_closed() -> None:
    module = _module()
    applicability = _applicability()
    applicability.pop("ear_cartilage_fold_clarity")

    proof = module.evaluate_micro_real_human_fidelity(
        candidate_id="candidate_front_1",
        output_id="v3_output_front_1",
        dimensions=_passing_dimensions(),
        applicability=applicability,
        evidence_codes=["micro_real_human_fidelity_reviewed"],
        enabled_by="server_feature_flag_v1",
    )

    assert proof.eligible is False
    assert proof.status == "fail"
    assert "micro_real_human_applicability_missing" in proof.issue_codes


def test_doc252_visible_region_cannot_be_marked_not_applicable() -> None:
    module = _module()
    applicability = _applicability()
    applicability["pore_scale_texture"] = {
        "applicability": "not_applicable",
        "visibility": "visible_and_reviewable",
        "status": "not_applicable",
    }

    proof = module.evaluate_micro_real_human_fidelity(
        candidate_id="candidate_front_1",
        output_id="v3_output_front_1",
        dimensions=_passing_dimensions(),
        applicability=applicability,
        evidence_codes=["micro_real_human_fidelity_reviewed"],
        enabled_by="server_feature_flag_v1",
    )

    assert proof.eligible is False
    assert "visible_region_marked_not_applicable" in proof.issue_codes


def test_doc252_beauty_preservation_is_hard_requirement() -> None:
    module = _module()
    dimensions = _passing_dimensions()
    dimensions["commercial_beauty_preserved"] = 0.61

    proof = module.evaluate_micro_real_human_fidelity(
        candidate_id="candidate_front_1",
        output_id="v3_output_front_1",
        dimensions=dimensions,
        applicability=_applicability(),
        evidence_codes=["micro_real_human_fidelity_reviewed"],
        enabled_by="server_feature_flag_v1",
    )

    assert proof.eligible is False
    assert "commercial_beauty_not_preserved" in proof.issue_codes


@pytest.mark.parametrize(
    "issue_code",
    [
        "detector_evasion_requested",
        "random_noise_as_realism",
        "compression_damage_as_realism",
        "beauty_degraded_for_realism",
        "identity_asymmetry_injected",
    ],
)
def test_doc252_detector_evasion_and_degradation_are_rejected(issue_code: str) -> None:
    module = _module()

    proof = module.evaluate_micro_real_human_fidelity(
        candidate_id="candidate_front_1",
        output_id="v3_output_front_1",
        dimensions=_passing_dimensions(),
        applicability=_applicability(),
        evidence_codes=["micro_real_human_fidelity_reviewed"],
        issue_codes=[issue_code],
        enabled_by="server_feature_flag_v1",
    )

    assert proof.eligible is False
    assert "micro_realism_degradation_strategy_rejected" in proof.issue_codes


def test_doc252_is_default_off_and_user_payload_cannot_enable() -> None:
    module = _module()

    assert module.micro_real_human_fidelity_enabled_from_metadata({}) is False
    assert module.micro_real_human_fidelity_enabled_from_metadata(
        {
            "micro_real_human_fidelity_required": False,
            "micro_real_human_fidelity_provenance": "server_feature_flag_v1",
        }
    ) is False
    assert module.micro_real_human_fidelity_enabled_from_metadata(
        {
            "micro_real_human_fidelity_required": "false",
            "micro_real_human_fidelity_provenance": "server_feature_flag_v1",
        }
    ) is False
    assert module.micro_real_human_fidelity_enabled_from_metadata(
        {
            "micro_real_human_fidelity_required": 0,
            "micro_real_human_fidelity_provenance": "server_feature_flag_v1",
        }
    ) is False
    with pytest.raises(ValueError, match="trusted_host_required"):
        module.micro_real_human_fidelity_enabled_from_metadata(
            {"micro_real_human_fidelity_required": True}
        )


def test_doc252_trusted_host_enablement_is_additive_guidance_only() -> None:
    module = _module()

    guidance = module.build_micro_real_human_fidelity_guidance(
        enabled=True,
        enabled_by="server_feature_flag_v1",
        scope="character_card_face_identity:standard_front",
    )

    assert guidance.enabled is True
    assert guidance.mode == "additive_guidance"
    assert guidance.prompt_authority == "existing_trusted_brain_host"
    assert guidance.generation_channel is None
    assert guidance.retry_budget is None
    assert guidance.rewrites_user_prompt is False


@pytest.mark.parametrize(
    "scope",
    [
        "character_card_expression:expression.anger",
        "character_card_body:body.front_full",
        "face_identity:left_front_25",
        "arbitrary_future_scope",
    ],
)
def test_doc252_guidance_scope_is_explicitly_allowlisted(scope: str) -> None:
    module = _module()

    with pytest.raises(ValueError, match="micro_real_human_fidelity_scope_not_approved"):
        module.build_micro_real_human_fidelity_guidance(
            enabled=True,
            enabled_by="server_feature_flag_v1",
            scope=scope,
        )


def test_doc252_default_off_prompt_contract_projection_is_noop() -> None:
    module = _module()
    prompt_contract = {
        "prompt_authority": "remote_v3_llm_brain",
        "visual_direction_addons": ["existing visual direction"],
        "negative_prompt_addons": ["existing negative"],
        "generation_channel": "provider",
        "retry_budget": 0,
        "age_direction": "preserve_reference_age",
        "identity_policy": "preserve_person_identity",
        "reference_ownership": "identity_only",
    }

    projected = module.append_micro_real_human_fidelity_guidance(
        prompt_contract,
        metadata={},
        scope="character_card_face_identity:standard_front",
    )

    assert projected == prompt_contract


def test_doc252_prompt_contract_projection_rejects_untrusted_enablement() -> None:
    module = _module()

    with pytest.raises(ValueError, match="trusted_host_required"):
        module.append_micro_real_human_fidelity_guidance(
            {"prompt_authority": "remote_v3_llm_brain"},
            metadata={"micro_real_human_fidelity_required": True},
            scope="character_card_face_identity:standard_front",
        )


def test_doc252_prompt_contract_projection_requires_existing_prompt_authority() -> None:
    module = _module()

    with pytest.raises(ValueError, match="existing_prompt_author_required"):
        module.append_micro_real_human_fidelity_guidance(
            {"visual_direction_addons": ["existing visual direction"]},
            metadata={
                "micro_real_human_fidelity_required": True,
                "micro_real_human_fidelity_provenance": "server_feature_flag_v1",
            },
            scope="character_card_face_identity:standard_front",
        )


@pytest.mark.parametrize(
    "scope",
    [
        "character_card_expression:expression.anger",
        "character_card_body:body.front_full",
        "face_identity:left_front_25",
        "arbitrary_future_scope",
    ],
)
def test_doc252_prompt_contract_projection_rejects_unapproved_scope(scope: str) -> None:
    module = _module()

    with pytest.raises(ValueError, match="micro_real_human_fidelity_scope_not_approved"):
        module.append_micro_real_human_fidelity_guidance(
            {"prompt_authority": "remote_v3_llm_brain"},
            metadata={
                "micro_real_human_fidelity_required": True,
                "micro_real_human_fidelity_provenance": "server_feature_flag_v1",
            },
            scope=scope,
        )


def test_doc252_trusted_prompt_contract_projection_is_additive_only() -> None:
    module = _module()
    prompt_contract = {
        "prompt_authority": "remote_v3_llm_brain",
        "visual_direction_addons": ["existing visual direction"],
        "negative_prompt_addons": ["existing negative"],
        "generation_channel": "mcp",
        "retry_budget": 0,
        "age_direction": "preserve_reference_age",
        "identity_policy": "preserve_person_identity",
        "reference_ownership": "identity_only",
    }

    projected = module.append_micro_real_human_fidelity_guidance(
        prompt_contract,
        metadata={
            "micro_real_human_fidelity_required": True,
            "micro_real_human_fidelity_provenance": "server_feature_flag_v1",
        },
        scope="character_card_face_identity:standard_front",
    )

    assert projected["prompt_authority"] == "remote_v3_llm_brain"
    assert projected["generation_channel"] == "mcp"
    assert projected["retry_budget"] == 0
    assert projected["age_direction"] == "preserve_reference_age"
    assert projected["identity_policy"] == "preserve_person_identity"
    assert projected["reference_ownership"] == "identity_only"
    assert projected["micro_real_human_fidelity_guidance"] == {
        "profile_id": "micro_real_human_fidelity_v1",
        "requirement_id": "micro_real_human_visible_evidence_v1",
        "enabled": True,
        "mode": "additive_guidance",
        "prompt_authority": "remote_v3_llm_brain",
        "scope": "character_card_face_identity:standard_front",
        "provenance": "server_feature_flag_v1",
    }
    assert "existing visual direction" in projected["visual_direction_addons"]
    assert any("commercial beauty" in item for item in projected["visual_direction_addons"])
    assert "existing negative" in projected["negative_prompt_addons"]
    assert any("detector evasion" in item for item in projected["negative_prompt_addons"])


def test_doc252_public_summary_is_safe() -> None:
    module = _module()
    proof = module.evaluate_micro_real_human_fidelity(
        candidate_id="candidate_front_1",
        output_id="v3_output_front_1",
        dimensions=_passing_dimensions(),
        applicability=_applicability(),
        evidence_codes=["micro_real_human_fidelity_reviewed"],
        enabled_by="server_feature_flag_v1",
    )

    summary = proof.public_summary()
    serialized = str(summary).lower()
    for forbidden in ("prompt", "provider", "mcp", "handoff", "artifact", "path", "raw", "api_key"):
        assert forbidden not in serialized


def test_doc252_profile_thresholds_cannot_be_lowered_by_caller() -> None:
    module = _module()

    with pytest.raises(ValueError, match="micro_realism_dimension_floor_cannot_be_lowered"):
        module.evaluate_micro_real_human_fidelity(
            candidate_id="candidate_front_1",
            output_id="v3_output_front_1",
            dimensions=_passing_dimensions(),
            applicability=_applicability(),
            evidence_codes=["micro_real_human_fidelity_reviewed"],
            enabled_by="server_feature_flag_v1",
            minimum_dimension_score=0.0,
        )
    with pytest.raises(ValueError, match="micro_realism_beauty_floor_cannot_be_lowered"):
        module.evaluate_micro_real_human_fidelity(
            candidate_id="candidate_front_1",
            output_id="v3_output_front_1",
            dimensions=_passing_dimensions(),
            applicability=_applicability(),
            evidence_codes=["micro_real_human_fidelity_reviewed"],
            enabled_by="server_feature_flag_v1",
            minimum_beauty_score=0.0,
        )
    for bad_value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="micro_realism_dimension_floor_must_be_finite"):
            module.evaluate_micro_real_human_fidelity(
                candidate_id="candidate_front_1",
                output_id="v3_output_front_1",
                dimensions=_passing_dimensions(),
                applicability=_applicability(),
                evidence_codes=["micro_real_human_fidelity_reviewed"],
                enabled_by="server_feature_flag_v1",
                minimum_dimension_score=bad_value,
            )
        with pytest.raises(ValueError, match="micro_realism_beauty_floor_must_be_finite"):
            module.evaluate_micro_real_human_fidelity(
                candidate_id="candidate_front_1",
                output_id="v3_output_front_1",
                dimensions=_passing_dimensions(),
                applicability=_applicability(),
                evidence_codes=["micro_real_human_fidelity_reviewed"],
                enabled_by="server_feature_flag_v1",
                minimum_beauty_score=bad_value,
            )


def test_doc252_module_stays_out_of_core_route_and_lifecycle() -> None:
    module = _module()

    tree = ast.parse(inspect.getsource(module))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(str(node.module or "").lower())

    for forbidden in (
        "formal_slot_acceptance",
        "product_api",
        "route_handlers",
        "provider",
        "mcp",
        "library",
        "character_card",
    ):
        assert all(forbidden not in module_name for module_name in imported)


def test_doc252_disabled_preserves_existing_doc248_face_adapter_shape() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    attempts = [
        (_anchor_candidate(1), _anchor_review(1, same_face_score=0.91)),
        (_anchor_candidate(2), _anchor_review(2, same_face_score=0.93, absolute_pass=False)),
        (_anchor_candidate(3), _anchor_review(3, same_face_score=0.89)),
    ]

    baseline = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="standard_front",
        attempts=attempts,
        acceptance_mode="standard_three_candidate",
        absolute_portrait_realism_required=True,
    )
    with_disabled_doc252 = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="standard_front",
        attempts=attempts,
        acceptance_mode="standard_three_candidate",
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=False,
    )

    assert [
        candidate.enhanced_proof.model_dump(mode="json") if candidate.enhanced_proof else None
        for candidate in with_disabled_doc252.candidates
    ] == [
        candidate.enhanced_proof.model_dump(mode="json") if candidate.enhanced_proof else None
        for candidate in baseline.candidates
    ]
    assert with_disabled_doc252.winner_candidate_id == baseline.winner_candidate_id


def test_doc252_required_face_composite_requires_doc248_and_doc252_pass() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    attempts = [
        (_anchor_candidate(1), _anchor_review(1, same_face_score=0.88)),
        # Highest identity score, but Doc252 micro proof is missing.
        (_anchor_candidate(2), _anchor_review(2, same_face_score=0.99, micro_pass=False)),
        (_anchor_candidate(3), _anchor_review(3, same_face_score=0.92)),
    ]

    receipt = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="standard_front",
        attempts=attempts,
        acceptance_mode="standard_three_candidate",
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
    )

    assert receipt.candidate_eligibility_required is True
    assert receipt.winner_candidate_id == "candidate_front_3"
    candidate2 = receipt.candidates[1].enhanced_proof
    candidate3 = receipt.candidates[2].enhanced_proof
    assert candidate2 is not None
    assert candidate2.eligible is False
    assert "micro_real_human_fidelity_proof_missing" in candidate2.issue_codes
    assert candidate3 is not None
    assert candidate3.eligible is True
    assert candidate3.profile_id == "face_standard_front_enhanced_quality_bundle_v1"
    assert candidate3.requirement_id == "doc248_absolute_realism_plus_doc252_micro_fidelity_v1"
    assert {
        "absolute_portrait_realism_profile_passed",
        "micro_real_human_fidelity_profile_passed",
    }.issubset(set(candidate3.evidence_codes))


def test_doc252_required_face_composite_rejects_doc248_failure_even_if_micro_passes() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    attempts = [
        (_anchor_candidate(1), _anchor_review(1, same_face_score=0.88)),
        (_anchor_candidate(2), _anchor_review(2, same_face_score=0.99, absolute_pass=False)),
        (_anchor_candidate(3), _anchor_review(3, same_face_score=0.9)),
    ]

    receipt = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="standard_front",
        attempts=attempts,
        acceptance_mode="standard_three_candidate",
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
    )

    candidate2 = receipt.candidates[1].enhanced_proof
    assert receipt.winner_candidate_id == "candidate_front_3"
    assert candidate2 is not None
    assert candidate2.eligible is False
    assert "absolute_portrait_realism_profile_failed" in candidate2.issue_codes


def test_doc252_required_face_composite_treats_visible_not_applicable_as_ineligible() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    attempts = [
        (
            _anchor_candidate(1),
            _anchor_review(
                1,
                same_face_score=0.99,
                micro_pass=True,
                missing_micro_dimension="pore_scale_texture",
            ),
        ),
        (_anchor_candidate(2), _anchor_review(2, same_face_score=0.91)),
        (_anchor_candidate(3), _anchor_review(3, same_face_score=0.9)),
    ]

    receipt = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="standard_front",
        attempts=attempts,
        acceptance_mode="standard_three_candidate",
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
    )

    candidate1 = receipt.candidates[0].enhanced_proof
    assert receipt.winner_candidate_id == "candidate_front_2"
    assert candidate1 is not None
    assert candidate1.eligible is False
    assert "micro_real_human_fidelity_profile_failed" in candidate1.issue_codes


def test_doc252_composite_summary_is_candidate_bound_and_public_safe() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    summary = service._formal_candidate_summary(  # noqa: SLF001
        _anchor_candidate(1),
        _anchor_review(1, same_face_score=0.91),
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
    )

    proof = summary.enhanced_proof
    assert proof is not None
    assert proof.candidate_id == "candidate_front_1"
    assert proof.output_id == "v3_output_front_1"
    serialized = str(proof.model_dump(mode="json")).lower()
    for forbidden in (
        "prompt",
        "provider",
        "mcp",
        "handoff",
        "artifact",
        "path",
        "raw",
        "api",
        "absolute_eye_gaze_alignment_verified",
        "micro_pore_scale_texture_verified",
    ):
        assert forbidden not in serialized


def test_doc252_composite_does_not_apply_to_auxiliary_25_degree() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    attempts = [(_anchor_candidate(1), _anchor_review(1, same_face_score=0.99))]
    attempts[0][0].view_role = "left_front_25"

    receipt = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="left_front_25",
        attempts=attempts,
        acceptance_mode="auxiliary_first_pass_reference",
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
    )

    assert receipt.candidate_eligibility_required is False
    assert receipt.candidates[0].enhanced_proof is None


def test_doc252_trusted_host_threads_micro_guidance_only_for_standard_front() -> None:
    captured: list[dict[str, object]] = []

    class _FakeService:
        visual_asset_catalog = None

        def create_professional_anchor_preparation_job(self, request, **kwargs):  # noqa: ANN001, ANN201
            captured.append(dict(request["metadata"]))
            return SimpleNamespace(job_id="job_blocked", status=ProductJobStatusValue.BLOCKED)

        def get_job_record(self, job_id: str):  # noqa: ANN001, ANN201
            return SimpleNamespace(request=SimpleNamespace(metadata={}))

    host = ProductApiAnchorPackPreparationHost(_FakeService())  # type: ignore[arg-type]

    front_request = AnchorGenerationRequest(
        project_id="project_micro_realism",
        people_asset_id="asset_micro_realism",
        pack_version_id="pack_micro_realism",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="character card front identity",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original", "source_supplemental"],
        initial_supplementary_source_asset_ids=["source_supplemental"],
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
        capture_scope="character_card_face_identity",
    )
    bridge_request = front_request.model_copy(
        update={
            "view_role": "left_front_25",
            "reference_evidence_ids": ["source_original", "front_output"],
            "initial_supplementary_source_asset_ids": [],
        }
    )

    with pytest.raises(AnchorCandidateUnavailable):
        host.generate(front_request)
    with pytest.raises(AnchorCandidateUnavailable):
        host.generate(bridge_request)

    assert captured[0]["professional_micro_real_human_fidelity_required"] is True
    assert captured[0]["professional_micro_real_human_fidelity_provenance"] == "server_feature_flag_v1"
    assert "professional_micro_real_human_fidelity_guidance" in captured[0]
    assert "professional_micro_real_human_fidelity_required" not in captured[1]
    assert "professional_micro_real_human_fidelity_guidance" not in captured[1]


def test_doc252_base_anchor_pack_request_cannot_enable_micro_realism() -> None:
    asset = PeopleAsset(
        project_id="project_micro_realism",
        people_asset_id="asset_micro_realism",
        subject_kind="human_person",
        face_identity_module={
            "module_id": "face_identity_micro_realism",
            "people_asset_id": "asset_micro_realism",
        },
        preparation_intent="base anchor pack",
    )
    provenance = RootSourceProvenance(
        source_type="uploaded_portrait",
        project_id="project_micro_realism",
        source_asset_id="source_original",
    )

    with pytest.raises(ValueError, match="micro_real_human_fidelity_requires_character_card_standard_front"):
        AnchorPackPreparationRequest(
            project_id="project_micro_realism",
            asset=asset,
            root_source_provenance=provenance,
            preparation_intent="base anchor pack",
            face_view_scope="base",
            micro_real_human_fidelity_required=True,
        )


def test_doc252_base_anchor_pack_generation_request_cannot_enable_micro_realism() -> None:
    with pytest.raises(ValueError, match="micro_real_human_fidelity_requires_character_card_standard_front"):
        AnchorGenerationRequest(
            project_id="project_micro_realism",
            people_asset_id="asset_micro_realism",
            pack_version_id="pack_micro_realism",
            view_role="standard_front",
            candidate_index=1,
            preparation_intent="base anchor pack",
            root_source_asset_id="source_original",
            reference_evidence_ids=["source_original", "source_supplemental"],
            initial_supplementary_source_asset_ids=["source_supplemental"],
            micro_real_human_fidelity_required=True,
            capture_scope="anchor_pack",
        )


def test_doc252_host_never_projects_micro_metadata_for_anchor_pack_scope() -> None:
    captured: list[dict[str, object]] = []

    class _FakeService:
        visual_asset_catalog = None

        def create_professional_anchor_preparation_job(self, request, **kwargs):  # noqa: ANN001, ANN201
            captured.append(dict(request["metadata"]))
            return SimpleNamespace(job_id="job_blocked", status=ProductJobStatusValue.BLOCKED)

        def get_job_record(self, job_id: str):  # noqa: ANN001, ANN201
            return SimpleNamespace(request=SimpleNamespace(metadata={}))

    host = ProductApiAnchorPackPreparationHost(_FakeService())  # type: ignore[arg-type]
    # Defensive Host seam test: even if an invalid caller bypasses request-model
    # validation, ordinary Anchor Pack must not receive Doc252 professional_micro_*
    # metadata or proof.
    request = AnchorGenerationRequest.model_construct(
        project_id="project_micro_realism",
        people_asset_id="asset_micro_realism",
        pack_version_id="pack_micro_realism",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="base anchor pack",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original", "source_supplemental"],
        initial_supplementary_source_asset_ids=["source_supplemental"],
        reference_strategy="serial_anchor_pack_root_reuse_v1",
        generation_channel="provider",
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
        capture_scope="anchor_pack",
    )

    with pytest.raises(AnchorCandidateUnavailable):
        host.generate(request)

    assert captured
    assert all(not str(key).startswith("professional_micro_") for key in captured[0])


def test_doc252_host_consumes_existing_prompt_authority_instead_of_fabricating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, object]] = []

    class _FakeService:
        visual_asset_catalog = None

        def create_professional_anchor_preparation_job(self, request, **kwargs):  # noqa: ANN001, ANN201
            captured.append(dict(request["metadata"]))
            return SimpleNamespace(job_id="job_blocked", status=ProductJobStatusValue.BLOCKED)

        def get_job_record(self, job_id: str):  # noqa: ANN001, ANN201
            return SimpleNamespace(request=SimpleNamespace(metadata={}))

    def _fake_anchor_metadata(*, view_role: str, capture_scope: str) -> dict[str, object]:
        assert view_role == "standard_front"
        assert capture_scope == "character_card_face_identity"
        return {
            "creative_direction_owner": "existing_test_brain_authority",
            "professional_anchor_capture_scope": capture_scope,
        }

    monkeypatch.setattr(
        ProfessionalModeRuntimeBridge,
        "anchor_pack_preparation_metadata",
        staticmethod(_fake_anchor_metadata),
    )

    host = ProductApiAnchorPackPreparationHost(_FakeService())  # type: ignore[arg-type]
    request = AnchorGenerationRequest(
        project_id="project_micro_realism",
        people_asset_id="asset_micro_realism",
        pack_version_id="pack_micro_realism",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="character card front identity",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original", "source_supplemental"],
        initial_supplementary_source_asset_ids=["source_supplemental"],
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
        capture_scope="character_card_face_identity",
    )

    with pytest.raises(AnchorCandidateUnavailable):
        host.generate(request)

    guidance = captured[0]["professional_micro_real_human_fidelity_guidance"]
    assert isinstance(guidance, dict)
    assert guidance["prompt_authority"] == "existing_test_brain_authority"


def test_doc252_visible_optional_micro_dimension_missing_is_not_synthesized_not_applicable() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    review = _anchor_review(1, same_face_score=0.99)
    evidence = [
        code
        for code in review.identity_scores.evidence_codes
        if not code.startswith("micro_ear_cartilage_fold_clarity_")
    ]
    evidence.append("micro_ear_cartilage_fold_clarity_visible")
    review.identity_scores.evidence_codes = evidence

    summary = service._formal_candidate_summary(  # noqa: SLF001
        _anchor_candidate(1),
        review,
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
    )

    assert summary.enhanced_proof is not None
    assert summary.enhanced_proof.eligible is False
    assert "micro_real_human_fidelity_profile_failed" in summary.enhanced_proof.issue_codes


def test_doc252_vision_contract_requests_micro_dimensions_only_for_trusted_face_standard_front() -> None:
    module = _module()
    planning_metadata = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front",
        capture_scope="character_card_face_identity",
    )
    envelope = {
        "activation_plan": {
            "metadata": {
                "professional_face_identity_quality_contract": planning_metadata[
                    "professional_face_identity_quality_contract"
                ]
            }
        },
        "resolved_constraint_ledger": {},
    }

    disabled = active_review_contract({"capability_execution_envelope": envelope})
    forged = active_review_contract(
        {
            "capability_execution_envelope": envelope,
            "professional_micro_real_human_fidelity_required": True,
        }
    )
    wrong_scope = active_review_contract(
        {
            "capability_execution_envelope": envelope,
            "professional_anchor_capture_scope": "anchor_pack",
            "professional_micro_real_human_fidelity_required": True,
            "professional_micro_real_human_fidelity_provenance": "server_feature_flag_v1",
        }
    )
    enabled = active_review_contract(
        {
            "capability_execution_envelope": envelope,
            "professional_anchor_capture_scope": "character_card_face_identity",
            "professional_micro_real_human_fidelity_required": True,
            "professional_micro_real_human_fidelity_provenance": "server_feature_flag_v1",
        }
    )

    expected_dimensions = (
        set(module.REQUIRED_STANDARD_FRONT_MINIMUM_GROUP_DIMENSIONS)
        | set(module.OPTIONAL_VISIBLE_DIMENSIONS)
    )
    for dimension in expected_dimensions:
        assert dimension not in disabled["score_dimensions"]
        assert dimension not in forged["score_dimensions"]
        assert dimension not in wrong_scope["score_dimensions"]
        assert dimension in enabled["score_dimensions"]
    micro_contract = enabled["professional_identity_quality"]["micro_real_human_fidelity"]
    assert micro_contract["applies"] is True
    assert micro_contract["provenance"] == "server_feature_flag_v1"
    assert micro_contract["detector_evasion_objective"] is False
    assert disabled["professional_identity_quality"]["micro_real_human_fidelity"]["applies"] is False


def test_doc252_host_projects_micro_evidence_from_shared_vision_score_card_only_when_required() -> None:
    score_card = _passing_dimensions()
    score_card.update(
        {
            "ear_cartilage_fold_clarity_not_applicable_outside_frame": 1.0,
            "left_right_ear_nonidentity_not_applicable_outside_frame": 1.0,
            "ear_hair_boundary_naturalness_not_applicable_outside_frame": 1.0,
            "fabric_weave_irregularity_not_applicable_outside_frame": 1.0,
            "collar_tension_plausibility_not_applicable_outside_frame": 1.0,
            "seam_edge_nonuniformity_not_applicable_outside_frame": 1.0,
        }
    )
    request = AnchorGenerationRequest(
        project_id="project_micro_realism",
        people_asset_id="asset_micro_realism",
        pack_version_id="pack_micro_realism",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="character card front identity",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original", "source_supplemental"],
        initial_supplementary_source_asset_ids=["source_supplemental"],
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
        capture_scope="character_card_face_identity",
    )

    evidence = ProductApiAnchorPackPreparationHost._micro_real_human_fidelity_evidence_codes(  # noqa: SLF001
        request,
        score_card,
    )

    assert "micro_non_mirrored_catchlights_verified" in evidence
    assert "micro_pore_scale_texture_verified" in evidence
    assert "micro_ear_cartilage_fold_clarity_not_applicable_outside_frame" in evidence
    disabled_request = request.model_copy(update={"micro_real_human_fidelity_required": False})
    assert ProductApiAnchorPackPreparationHost._micro_real_human_fidelity_evidence_codes(  # noqa: SLF001
        disabled_request,
        score_card,
    ) == []


def test_doc252_host_micro_projection_fails_closed_when_optional_applicability_missing() -> None:
    score_card = dict(_passing_dimensions())
    request = AnchorGenerationRequest(
        project_id="project_micro_realism",
        people_asset_id="asset_micro_realism",
        pack_version_id="pack_micro_realism",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="character card front identity",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original", "source_supplemental"],
        initial_supplementary_source_asset_ids=["source_supplemental"],
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
        capture_scope="character_card_face_identity",
    )

    evidence = ProductApiAnchorPackPreparationHost._micro_real_human_fidelity_evidence_codes(  # noqa: SLF001
        request,
        score_card,
    )
    review = _anchor_review(1, same_face_score=0.99)
    review.identity_scores.evidence_codes = [
        code
        for code in review.identity_scores.evidence_codes
        if not code.startswith("micro_")
    ] + evidence

    summary = AnchorPackPreparationService(
        generator=object(),
        reviewer=object(),
    )._formal_candidate_summary(  # noqa: SLF001
        _anchor_candidate(1),
        review,
        absolute_portrait_realism_required=True,
        micro_real_human_fidelity_required=True,
    )

    assert summary.enhanced_proof is not None
    assert summary.enhanced_proof.eligible is False
    assert "micro_real_human_fidelity_profile_failed" in summary.enhanced_proof.issue_codes


def test_doc252_formal_core_source_does_not_learn_doc252_or_face_bundle_semantics() -> None:
    source = inspect.getsource(FormalSlotAcceptanceCore).lower()
    for forbidden in (
        "micro_real",
        "doc252",
        "absolute_portrait",
        "standard_front",
        "face_standard_front_enhanced_quality_bundle",
    ):
        assert forbidden not in source
