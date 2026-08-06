"""Red tests for the superseding Body whole-person synthesis correction.

The prior attempt is evidence only: its generic balanced profile, duplicated
Face physical inputs, incomplete renderer authority, and high-confidence
generic review are not sufficient for a new refresh.  This feature must make
the morphology/profile, view-aware renderer inputs, integrated whole-person
directive, and Body-specific visual review evidence closed contracts before a
fresh attempt can start.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

import pytest

from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    _BODY_MORPHOLOGY_RENDERER_PHRASES,
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.generation_router.providers import (
    McpMaterializationProvider,
)
from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    _compact_body_morphology_server_context,
)
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    GeneratedOutputResolution,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector import (
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.visual_assets import (
    body_proportion_evidence_profile as profile_contracts,
    body_silhouette_source_standard as body_contracts,
)
from alchemy_creative_agent_3_0.app.visual_assets.body_proportion_evidence_profile import (
    BodyMorphologyEvidenceProfile,
    BodyProportionEvidenceProfile,
    BodyRefreshAnalysisContext,
    BodySourceAnalysisAssetEnvelope,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    default_body_silhouette_garment_continuity_contract,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc245_body_formal_slot_receipt_seam import (
    _body_review_metadata_for_vision,
    _doc245_body_refresh_presentation_intent,
    _mcp_body_generation_request,
)


def test_reference_assisted_profile_uses_richer_non_biometric_morphology_bands() -> None:
    profile_model = getattr(profile_contracts, "BodyMorphologyEvidenceProfile", None)
    assert profile_model is not None
    required_fields = {
        "relative_head_to_stature",
        "shoulder_to_head",
        "torso_to_leg",
        "arm_to_leg",
        "build",
        "neck_shoulder",
        "developmental_stage_context",
        "stance_ground",
        "cross_view_support",
    }
    assert required_fields <= set(profile_model.model_fields)
    assert "allowed_bands" not in set(profile_model.model_fields)
    assert getattr(profile_contracts, "BODY_REFRESH_ANALYSIS_CONTEXT_SCHEMA_VERSION", None) == (
        "body_refresh_analysis_context_v2"
    )


def test_face_renderer_plan_is_view_aware_and_deduplicated() -> None:
    builder = getattr(McpMaterializationProvider(), "_view_aware_face_identity_renderer_plan", None)
    assert callable(builder)

    plan = builder(
        [
            {
                "asset_id": "root-feature-front",
                "source_asset_id": "root-face",
                "role": "portrait_identity",
                "reference_truth_layer": "portrait_identity_truth",
                "provider_input_mode": "reference_image",
                "derivative_kind": "portrait_identity_crop",
                "identity_evidence_scope": "feature_detail",
                "body_view_kind": "front_full",
            },
            {
                "asset_id": "root-geometry-front",
                "source_asset_id": "root-face",
                "role": "portrait_identity",
                "reference_truth_layer": "portrait_identity_truth",
                "provider_input_mode": "reference_image",
                "derivative_kind": "portrait_identity_pose_geometry_crop",
                "identity_evidence_scope": "pose_geometry",
                "body_view_kind": "front_full",
            },
            {
                "asset_id": "profile-head-side",
                "source_asset_id": "profile-face",
                "role": "portrait_identity",
                "reference_truth_layer": "portrait_identity_truth",
                "provider_input_mode": "reference_image",
                "derivative_kind": "portrait_identity_pose_geometry_crop",
                "identity_evidence_scope": "pose_geometry",
                "body_view_kind": "side_full",
            },
            {
                "asset_id": "body-truth-front",
                "source_asset_id": "body-source",
                "role": "body_proportion_reference",
                "derivative_kind": "source",
                "body_view_kind": "front_full",
            },
        ],
        view_kind="front_full",
        face_view_binding={
            "front_full": {
                "face_slot": "face.front",
                "source_asset_id": "root-face",
            }
        },
    )

    renderer_refs = plan
    assert 1 <= len(renderer_refs) <= 2
    assert all(ref["role"] == "portrait_identity" for ref in renderer_refs)
    assert all(ref["source_asset_id"] != "body-source" for ref in renderer_refs)
    assert len({ref["source_asset_id"] for ref in renderer_refs}) == 1
    assert {ref["identity_evidence_scope"] for ref in renderer_refs} == {
        "feature_detail",
        "pose_geometry",
    }
    assert {ref["derivative_kind"] for ref in renderer_refs} == {
        "portrait_identity_crop",
        "portrait_identity_pose_geometry_crop",
    }


def test_face_renderer_plan_rejects_wrong_source_and_duplicate_geometry_scope() -> None:
    builder = McpMaterializationProvider()._view_aware_face_identity_renderer_plan  # noqa: SLF001
    base = {
        "role": "portrait_identity",
        "reference_truth_layer": "portrait_identity_truth",
        "provider_input_mode": "reference_image",
        "body_view_kind": "front_full",
    }
    binding = {"front_full": {"face_slot": "face.front", "source_asset_id": "root-face"}}
    with pytest.raises(Exception) as mismatch:
        builder(
            [
                {**base, "source_asset_id": "other-face", "derivative_kind": "portrait_identity_crop", "identity_evidence_scope": "feature_detail"},
                {**base, "source_asset_id": "other-face", "derivative_kind": "portrait_identity_pose_geometry_crop", "identity_evidence_scope": "pose_geometry"},
            ],
            view_kind="front_full",
            face_view_binding=binding,
        )
    assert mismatch.value.detail["failure_code"] == "professional_face_view_binding_mismatch"

    with pytest.raises(Exception) as duplicate:
        builder(
            [
                {**base, "source_asset_id": "root-face", "derivative_kind": "portrait_identity_crop", "identity_evidence_scope": "feature_detail"},
                {**base, "source_asset_id": "root-face", "derivative_kind": "portrait_identity_pose_geometry_crop", "identity_evidence_scope": "pose_geometry"},
                {**base, "source_asset_id": "root-face", "derivative_kind": "portrait_identity_pose_geometry_crop", "identity_evidence_scope": "head_geometry"},
            ],
            view_kind="front_full",
            face_view_binding=binding,
        )
    assert duplicate.value.detail["failure_code"] == "professional_face_view_binding_duplicate_scope"


def test_face_view_binding_is_server_owned_and_never_reused() -> None:
    key = "professional_character_card_face_view_binding"
    assert key in V3ProductApiService._SERVER_OWNED_RUNTIME_METADATA  # noqa: SLF001
    assert key in V3ProductApiService._NON_REUSABLE_SERVER_OWNED_RUNTIME_METADATA  # noqa: SLF001
    assert key not in V3ProductApiService._reusable_server_owned_runtime_metadata(  # noqa: SLF001
        {key: {"front_full": {"face_slot": "face.front", "source_asset_id": "forged"}}}
    )


def test_source_analyzer_morphology_result_freezes_v2_context_and_rejects_v1_resume(
    tmp_path: Path,
) -> None:
    profile = BodyMorphologyEvidenceProfile(
        contract_version="body_morphology_evidence_profile_v2",
        source_mode="reference_assisted",
        source_truth_layer="body_proportion_truth",
        relative_head_to_stature="larger",
        shoulder_to_head="narrower",
        torso_to_leg="shorter_torso",
        arm_to_leg="proportional",
        build="slender",
        neck_shoulder="narrow_transition",
        developmental_stage_context="middle_stage_context",
        stance_ground="grounded_full_contact",
        cross_view_support="multi_view_supported",
        source_count=5,
        analysis_receipt={
            "owner": "server_owned_body_proportion_analysis",
            "status": "complete",
            "analysis_provider": "configured_body_source_analysis_provider",
        },
    )
    envelopes = [
        BodySourceAnalysisAssetEnvelope(
            asset_id=f"v3_asset_{index}",
            role="body_proportion_reference",
            reference_truth_layer="body_proportion_truth",
            file_path=str(tmp_path / f"{index}.png"),
            mime_type="image/png",
            source_sha256=f"{index + 1:064x}",
            source_provenance="user_provided_body_reference",
            consent_reference="consent_body_reference",
            rights_reference="rights_body_reference",
        )
        for index in range(5)
    ]
    context = BodyRefreshAnalysisContext.from_analysis(
        attempt_id="body_refresh_attempt_0123456789abcdef0123456789abcdef",
        append_only_revision=1,
        admitted_body_assets=envelopes,
        profile=profile,
    )
    assert context.schema_version == "body_morphology_evidence_profile_v2"
    # A non-balanced fixture proves that the typed result is transmitted, but
    # the production contract must not force every real subject away from a
    # proportional value.
    assert profile.relative_head_to_stature == "larger"
    assert profile.torso_to_leg == "shorter_torso"
    safe = context.safe_metadata()
    assert safe["profile_digest"] == context.profile_digest
    assert "profile" not in safe
    assert all("asset" not in key and "path" not in key for key in safe)

    legacy_profile = BodyProportionEvidenceProfile(
        contract_version="body_proportion_evidence_profile_v1",
        source_mode="reference_assisted",
        source_truth_layer="body_proportion_truth",
        allowed_bands={
            "head_body_scale": "balanced_child_scale",
            "neck_shoulder": "balanced_child_transition",
            "torso_limb": "balanced_child_torso_limb",
            "arm_leg": "balanced_child_arm_leg",
            "developmental_stage": "middle_childhood_coherent",
            "stance_ground": "grounded_full_contact",
            "cross_view_support": "multi_view_supported",
        },
        source_count=5,
        analysis_receipt={
            "owner": "server_owned_body_proportion_analysis",
            "status": "complete",
            "analysis_provider": "configured_body_source_analysis_provider",
        },
    )
    legacy_context = BodyRefreshAnalysisContext.from_analysis(
        attempt_id="body_refresh_attempt_0123456789abcdef0123456789abcdef",
        append_only_revision=1,
        admitted_body_assets=envelopes,
        profile=legacy_profile,
    )
    require_current = getattr(
        profile_contracts,
        "require_current_body_refresh_analysis_context",
        None,
    )
    assert callable(require_current)
    with pytest.raises(ValueError, match="superseded"):
        require_current(legacy_context)


def test_brain_receives_exact_typed_morphology_bands_with_verified_digest() -> None:
    profile = BodyMorphologyEvidenceProfile(
        contract_version="body_morphology_evidence_profile_v2",
        source_mode="reference_assisted",
        source_truth_layer="body_proportion_truth",
        relative_head_to_stature="larger",
        shoulder_to_head="narrower",
        torso_to_leg="shorter_torso",
        arm_to_leg="proportional",
        build="slender",
        neck_shoulder="narrow_transition",
        developmental_stage_context="middle_stage_context",
        stance_ground="grounded_full_contact",
        cross_view_support="multi_view_supported",
        source_count=5,
        analysis_receipt={
            "owner": "server_owned_body_proportion_analysis",
            "status": "complete",
            "analysis_provider": "configured_body_source_analysis_provider",
        },
    )
    payload = profile.model_dump(mode="json")
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    request = SimpleNamespace(
        metadata={
            "professional_body_proportion_receipt_required": True,
            "professional_character_card_body_refresh_source_mode": "reference_assisted",
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": "body.front_full",
            "professional_body_proportion_server_context": {
                "body_proportion_evidence_profile": payload
            },
            "professional_body_refresh_analysis_context": {
                "profile_digest": digest,
                "target_age_scope": "age_6_child_only",
            },
        }
    )

    compact = _compact_body_morphology_server_context(request)

    assert compact == {
        "schema_version": "body_morphology_evidence_profile_v2",
        "profile_digest": digest,
        "target_age_scope": "age_6_child_only",
        "bands": {
            "relative_head_to_stature": "larger",
            "shoulder_to_head": "narrower",
            "torso_to_leg": "shorter_torso",
            "arm_to_leg": "proportional",
            "build": "slender",
            "neck_shoulder": "narrow_transition",
            "developmental_stage_context": "middle_stage_context",
            "stance_ground": "grounded_full_contact",
            "cross_view_support": "multi_view_supported",
        },
    }
    request.metadata["professional_body_refresh_analysis_context"]["profile_digest"] = "0" * 64
    with pytest.raises(ValueError, match="mismatch"):
        _compact_body_morphology_server_context(request)


def test_morphology_analysis_schema_has_closed_fields_not_generic_allowed_bands() -> None:
    schema_builder = getattr(
        profile_contracts,
        "build_body_morphology_analysis_response_schema",
        None,
    )
    assert callable(schema_builder)
    schema = schema_builder()
    assert set(schema["required"]) == {
        "relative_head_to_stature",
        "shoulder_to_head",
        "torso_to_leg",
        "arm_to_leg",
        "build",
        "neck_shoulder",
        "developmental_stage_context",
        "stance_ground",
        "cross_view_support",
    }
    assert "allowed_bands" not in schema["properties"]
    assert "neck_shoulder" in schema["properties"]
    assert "developmental_stage_context" in schema["properties"]


def test_every_legal_morphology_band_has_renderer_execution_semantics() -> None:
    for field_name, phrases in _BODY_MORPHOLOGY_RENDERER_PHRASES.items():
        legal_values = set(get_args(BodyMorphologyEvidenceProfile.model_fields[field_name].annotation))
        assert set(phrases) == legal_values
        assert all(isinstance(value, str) and value.strip() for value in phrases.values())


def test_morphology_source_count_is_strict_and_fresh_adapter_requires_explicit_v2() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BodyMorphologyEvidenceProfile(
            contract_version="body_morphology_evidence_profile_v2",
            source_mode="reference_assisted",
            source_truth_layer="body_proportion_truth",
            relative_head_to_stature="larger",
            shoulder_to_head="narrower",
            torso_to_leg="shorter_torso",
            arm_to_leg="proportional",
            build="slender",
            neck_shoulder="narrow_transition",
            developmental_stage_context="middle_stage_context",
            stance_ground="grounded_full_contact",
            cross_view_support="multi_view_supported",
            source_count="5",
            analysis_receipt={
                "owner": "server_owned_body_proportion_analysis",
                "status": "complete",
                "analysis_provider": "configured_body_source_analysis_provider",
            },
        )
    explicit_v2_guard = getattr(
        profile_contracts,
        "require_explicit_body_morphology_profile_version",
        None,
    )
    assert callable(explicit_v2_guard)
    with pytest.raises(ValueError, match="v2"):
        explicit_v2_guard("v1")
    assert explicit_v2_guard("v2") == "v2"


def test_general_adult_reference_assisted_profile_is_schema_legal() -> None:
    profile = BodyMorphologyEvidenceProfile(
        contract_version="body_morphology_evidence_profile_v2",
        source_mode="reference_assisted",
        source_truth_layer="body_proportion_truth",
        relative_head_to_stature="proportional",
        shoulder_to_head="proportional",
        torso_to_leg="proportional",
        arm_to_leg="proportional",
        build="medium",
        neck_shoulder="proportional_transition",
        developmental_stage_context="adult_stage_context",
        stance_ground="grounded_full_contact",
        cross_view_support="multi_view_supported",
        source_count=5,
        analysis_receipt={
            "owner": "server_owned_body_proportion_analysis",
            "status": "complete",
            "analysis_provider": "configured_body_source_analysis_provider",
        },
    )
    assert profile.developmental_stage_context == "adult_stage_context"
    assert not any("child" in value for value in profile.model_dump(mode="json").values() if isinstance(value, str))


def test_canonical_garment_identity_is_presentation_only_and_not_an_adult_age_signal() -> None:
    garment = default_body_silhouette_garment_continuity_contract()
    serialized = json.dumps(garment, sort_keys=True)

    assert garment["not_body_proportion_truth"] is True
    assert garment["not_identity_truth"] is True
    assert garment["not_age_truth"] is True
    assert "age_6_child_only" not in serialized
    assert "adult_stage_context" not in serialized
    assert "teen" not in serialized.lower()

    adult_profile = {
        "developmental_stage_context": "adult_stage_context",
        "age_scope": "current_request_age_owned",
    }
    assert "age_6_child_only" not in json.dumps(adult_profile)
    assert "canonical_identity" not in json.dumps(adult_profile)


def test_body_contract_declares_one_integrated_whole_person_synthesis_authority() -> None:
    contract_builder = getattr(
        body_contracts,
        "body_silhouette_integrated_whole_person_synthesis_contract",
        None,
    )
    assert callable(contract_builder)
    contract = contract_builder()
    assert contract["contract_version"] == (
        "professional_body_silhouette_integrated_whole_person_synthesis_v1"
    )
    assert contract["synthesis_mode"] == "one_coherent_whole_person"
    assert {
        "face",
        "head",
        "neck",
        "shoulders",
        "torso",
        "limbs",
    } <= set(contract["required_integrated_channels"])
    assert {
        "pasted_head_body_boundary",
        "mannequin_body_chain",
        "cardboard_stance",
    } <= set(contract["forbidden_composition_modes"])


def test_body_contract_declares_age6_naturalness_without_leaking_to_general_age_paths() -> None:
    contract_builder = getattr(
        body_contracts,
        "body_silhouette_age6_cross_view_naturalness_contract",
        None,
    )
    assert callable(contract_builder)
    contract = contract_builder()

    assert contract["target_age_scope"] == "age_6_child_only"
    assert contract["scope"] == "reference_assisted_body_refresh_only"
    assert contract["same_body_model_across_views"] is True
    assert contract["front_head_body_integration_required"] is True
    assert contract["forbid_teen_or_adult_model_elongation"] is True
    assert "model_like_limb_elongation" in contract["blocking_issue_codes"]
    assert "target_age_body_proportion_drift" in contract["blocking_issue_codes"]

    adult_profile = {
        "developmental_stage_context": "adult_stage_context",
        "age_scope": "current_request_age_owned",
    }
    assert "age_6_child_only" not in json.dumps(adult_profile)
    assert "school-age child" not in json.dumps(adult_profile)


def test_strict_body_mcp_handoff_freezes_integrated_contract() -> None:
    app_request, _, _ = McpMaterializationProvider()._build_app_request(  # noqa: SLF001
        _mcp_body_generation_request(
            "Full-body front-view Body Silhouette source-standard materialization. "
            "Use Face Identity references only for identity continuity. Resolve body scale, body chain, "
            "stage-aware proportion, neck-shoulder continuity, torso-limb relationship, stance-ground contact, "
            "and cross-view parity. Keep non-body visual channels unspecified.",
            source_mode="inference_first",
        )
    )
    context = app_request.prompt_plan.variables["mcp_materialization_context"]
    rendering_contract = context["rendering_contract"]
    integrated = rendering_contract[
        "body_silhouette_integrated_whole_person_synthesis_contract"
    ]
    assert integrated["synthesis_mode"] == "one_coherent_whole_person"
    assert integrated["contract_version"].endswith("_v1")


def test_typed_directive_is_the_actual_host_materialization_input(tmp_path: Path) -> None:
    prompt = (
        "Full-body front-view Body Silhouette source-standard materialization. "
        "Use Face Identity references only for identity continuity. Resolve body scale, body chain, "
        "stage-aware proportion, neck-shoulder continuity, torso-limb relationship, stance-ground contact, "
        "and cross-view parity. Keep non-body visual channels unspecified."
    )
    request = _mcp_body_generation_request(prompt, source_mode="inference_first")
    request.metadata["professional_character_card_body_refresh_presentation_intent"] = (
        _doc245_body_refresh_presentation_intent()
    )
    app_request, _, reference_assets = McpMaterializationProvider()._build_app_request(  # noqa: SLF001
        request
    )
    context = app_request.prompt_plan.variables["mcp_materialization_context"]
    store = McpMaterializationHandoffStore(tmp_path)
    handoff = store.ensure_pending(
        operation_id="body-whole-person-directive-test",
        prompt=prompt,
        prompt_sha256=context["prompt_sha256"],
        reference_assets=reference_assets,
        rendering_contract=context["rendering_contract"],
        require_body_rendering_contract=True,
    )
    host_requests: list[dict[str, object]] = []

    def fake_imagegen(host_request: dict[str, object]) -> None:
        host_requests.append(host_request)

    host_request = store.public_renderer_request(handoff["handoff_id"])
    fake_imagegen(host_request)
    assert host_requests[0]["canonical_prompt"] == prompt
    assert host_requests[0]["renderer_prompt"] != prompt
    assert "one coherent whole person" in str(host_requests[0]["renderer_prompt"]).lower()
    renderer_prompt = str(host_requests[0]["renderer_prompt"]).lower()
    assert "natural continuous transition from face through head, neck, shoulders, torso, arms, and legs" in renderer_prompt
    assert host_requests[0]["renderer_execution_directive_sha256"]


def test_ordinary_and_expression_materialization_do_not_inherit_whole_person_contract() -> None:
    provider = McpMaterializationProvider()
    ordinary = provider._build_app_request(  # noqa: SLF001
        _mcp_body_generation_request(
            "ordinary generic image materialization",
            stage="ordinary",
            source_mode="inference_first",
        )
    )[0]
    variables = ordinary.prompt_plan.variables
    assert "body_silhouette_integrated_whole_person_synthesis_contract" not in str(variables)
    assert "body_morphology" not in str(variables).lower()
    assert not hasattr(body_contracts, "whole_person_synthesis_for_expression")


def test_body_review_prompt_requires_explicit_blocking_issue_evaluation() -> None:
    evidence_code = getattr(
        body_contracts,
        "BODY_SILHOUETTE_BLOCKING_ISSUE_EVALUATION_EVIDENCE_CODE",
        None,
    )
    assert evidence_code
    prompt = _inspection_prompt(_body_review_metadata_for_vision())
    assert evidence_code in prompt


def test_body_visual_review_blocks_mannequin_and_pasted_head_findings_even_when_generic_passes() -> None:
    evaluator = getattr(body_contracts, "evaluate_body_silhouette_visual_review", None)
    assert callable(evaluator)
    for code in (
        "pasted_head_body_boundary",
        "head_neck_shoulder_discontinuity",
        "mannequin_body_chain",
        "cardboard_stance",
        "shoulder_width_incoherent",
        "head_body_integration_artifact",
        "face_reference_transplant_artifact",
        "face_body_texture_lighting_mismatch",
        "target_age_body_proportion_drift",
        "model_like_limb_elongation",
    ):
        result = evaluator(
            {
                "verified": True,
                "status": "pass",
                "evidence_codes": [
                    "body_silhouette_blocking_issue_evaluation_complete"
                ],
                "issue_codes": [code],
            }
        )
        assert result["status"] == "blocked"
        assert result["formal_eligible"] is False

    missing_pixel_evidence = evaluator(
        {"verified": True, "status": "pass", "evidence_codes": [], "issue_codes": []}
    )
    assert missing_pixel_evidence["status"] == "blocked"
    assert missing_pixel_evidence["formal_eligible"] is False


def test_body_review_prompt_requires_age6_naturalness_and_integration_evidence() -> None:
    metadata = _body_review_metadata_for_vision()
    metadata["professional_body_refresh_analysis_context"] = {
        "contract_version": "body_refresh_analysis_context_v2",
        "schema_version": "body_morphology_evidence_profile_v2",
        "source_mode": "reference_assisted",
        "attempt_id": "body_refresh_attempt_0123456789abcdef0123456789abcdef",
        "append_only_revision": 1,
        "source_binding_digest": "a" * 64,
        "source_evidence_id_digest": "b" * 64,
        "profile_digest": "c" * 64,
        "target_age_scope": "age_6_child_only",
        "target_age_scope_digest": hashlib.sha256(b"age_6_child_only").hexdigest(),
    }
    prompt = _inspection_prompt(metadata).lower()

    assert "target_age_body_proportion" in prompt
    assert "head_body_blend_naturalism" in prompt
    assert "not a pasted head" in prompt
    assert "not teen, adolescent, or adult fashion-model proportions" in prompt
    assert "model_like_limb_elongation" in prompt
    assert "target_age_body_proportion_drift" in prompt
    assert "head_body_integration_artifact" in prompt
    assert "face_reference_transplant_artifact" in prompt
    assert "face_body_texture_lighting_mismatch" in prompt
    assert "skin tone, lighting, edge transition, neck support, and shoulder relationship" in prompt


def test_body_review_prompt_without_age6_context_does_not_inherit_child_specific_language() -> None:
    prompt = _inspection_prompt(_body_review_metadata_for_vision()).lower()

    assert "six-year-old" not in prompt
    assert "school-age child" not in prompt
    assert "not teen, adolescent, or adult fashion-model proportions" not in prompt


def test_shared_vision_parser_fails_closed_without_integrated_pixel_evidence() -> None:
    inspector = VisionOutputInspector(min_confidence=0.1)
    resolution = GeneratedOutputResolution(
        resolution_id="resolution_whole_person",
        project_id="project_whole_person",
        job_id="job_whole_person",
        candidate_id="candidate_whole_person",
        asset_id="asset_whole_person",
        output_id="output_whole_person",
        status="ready",
    )
    metadata = _body_review_metadata_for_vision()
    payload = {
        "status": "pass",
        "confidence": 0.99,
        "issue_codes": [],
        "scores": {},
        "summary": ["generic pass must not certify Body integration"],
    }

    report = inspector._from_provider_payload(  # noqa: SLF001
        resolution,
        payload,
        mode="vision_model",
        provider_name="fake_vision",
        metadata=metadata,
    )

    assert report.status == "fail_retryable"
    assert "body_silhouette_integrated_review_evidence_missing" in {
        issue["code"] for issue in report.detected_issues
    }
    assert report.evidence["integrated_whole_person_review_evidence"] == {}


def test_shared_vision_parser_accepts_complete_integrated_pixel_evidence() -> None:
    inspector = VisionOutputInspector(min_confidence=0.1)
    resolution = GeneratedOutputResolution(
        resolution_id="resolution_whole_person_pass",
        project_id="project_whole_person",
        job_id="job_whole_person_pass",
        candidate_id="candidate_whole_person_pass",
        asset_id="asset_whole_person_pass",
        output_id="output_whole_person_pass",
        status="ready",
    )
    integrated = {
        dimension: {"status": "pass", "pixel_evidence_present": True}
        for dimension in body_contracts.BODY_SILHOUETTE_INTEGRATED_REVIEW_DIMENSIONS
    }
    payload = {
        "status": "pass",
        "confidence": 0.99,
        "issue_codes": [],
        "evidence_codes": [
            body_contracts.BODY_SILHOUETTE_BLOCKING_ISSUE_EVALUATION_EVIDENCE_CODE
        ],
        "integrated_whole_person_review_evidence": integrated,
        "scores": {},
        "summary": ["typed integrated Body evidence passed"],
    }

    report = inspector._from_provider_payload(  # noqa: SLF001
        resolution,
        payload,
        mode="vision_model",
        provider_name="fake_vision",
        metadata=_body_review_metadata_for_vision(),
    )

    assert report.status == "pass"
    assert report.evidence["integrated_whole_person_review_evidence"] == integrated
    assert not report.detected_issues


def test_gate_c_supersedes_body_physical_reference_and_names_integrated_review() -> None:
    docs_root = Path(__file__).resolve().parents[1] / "docs" / "visual_assets"
    gate_c = (docs_root / "PROFESSIONAL_MODE_BODY_SILHOUETTE_SOURCE_STANDARD_GATE_C_HANDOFF.md").read_text(
        encoding="utf-8"
    )
    runtime_projection = (docs_root / "PROFESSIONAL_MODE_BODY_PROPORTION_RUNTIME_PROJECTION_DESIGN.md").read_text(
        encoding="utf-8"
    )
    combined = f"{gate_c}\n{runtime_projection}".lower()
    assert "body evidence remains in the analysis/profile contract" in combined
    assert "integrated_whole_person" in combined
    assert "body 1 = 4" not in combined
    assert "old attempt" in combined and "superseded" in combined
    assert "face refs are identity evidence only" in combined
    assert "head swap" in combined or "composite" in combined
