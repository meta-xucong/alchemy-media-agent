"""Doc252 micro real-human fidelity Enhanced module red contracts.

These tests intentionally describe the next module boundary before production
implementation exists.  They must not be satisfied by Doc248 alone, Formal
Core, Provider/MCP routing, prompt rewrites, or detector-evasion tricks.
"""

from __future__ import annotations

import importlib
import inspect
import ast

import pytest


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
    return {
        key: {
            "applicability": "applicable",
            "visibility": "visible_and_reviewable",
            "status": "pass",
        }
        for key in _passing_dimensions()
    }


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
