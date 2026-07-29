"""Doc245 / Task7 Body Silhouette formal-slot receipt seam contracts."""

from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_remote_required_result
from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    _canonical_provider_prompt_finalization_payload,
)
from alchemy_creative_agent_3_0.app.product_api.assets import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from app.providers.base import ProviderRuntimeError
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.generation_router.providers import GenerationRequest, McpMaterializationProvider
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    LayoutPlan,
    LayoutRegion,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    CapabilityActivationPlan,
    TemplateCapabilityPolicy,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateUnavailable,
    AnchorReviewDecision,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS,
    project_generic_visual_review_receipt,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    GeneratedOutputResolution,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector import (
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BODY_SLOT_KEYS,
    BODY_FORMAL_SLOT_NO_EXTERNAL_ELIGIBILITY_CODE,
    BODY_FORMAL_SLOT_NO_PASSING_SHARED_REVIEW_CODE,
    BODY_FORMAL_SLOT_SOURCE_STANDARD_MISSING_CODE,
    BODY_FORMAL_SLOT_CANDIDATE_CONTRACT_MISMATCH_CODE,
    BODY_FORMAL_SLOT_REVIEWED_COUNT_INVALID_CODE,
    BODY_FORMAL_SLOT_SHARED_REVIEW_RECEIPT_MISSING_CODE,
    CharacterCardCandidateLifecycleBoundaryError,
    BodyFormalSlotFailureDetails,
    CharacterCardCandidateLifecycleProjection,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardSlot,
    CharacterCardState,
    BodySilhouettePublicRequest,
    character_card_formal_slot_receipt_public_summary,
    project_character_card_slot_success_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    mark_formal_slot_receipt_reload_public_projection_verified,
)
from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
    BODY_SILHOUETTE_CROSS_VIEW_PARITY_DIMENSION,
    BODY_SILHOUETTE_CROSS_VIEW_PARITY_EVIDENCE_CODE,
    BODY_SILHOUETTE_MCP_ALLOWED_BODY_CHANNELS,
    BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS,
    BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES,
    BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS,
    BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR,
    body_silhouette_mcp_materialization_channel_contract,
    body_silhouette_mcp_materialization_prompt_findings,
    body_silhouette_source_standard_contract,
    validated_body_silhouette_source_standard_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    VisualAssetLibraryCatalog,
    VisualAssetLibraryLifecycleService,
)
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    ProductApiAnchorPackPreparationHost,
    _character_card_stage_mcp_prompt_current,
)
from alchemy_creative_agent_3_0.app.visual_assets import character_card as character_card_module
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge


BODY_SCENE_NEUTRAL_FORBIDDEN_TERMS = (
    "same child",
    "natural child",
    "six-year",
    "6-year",
    "swimwear",
    "poolside",
    "kidswear",
    "e-commerce",
    "ecommerce",
    "simple white short-sleeve top",
    "plain solid shorts",
    "bare feet",
    "barefoot",
    "skirt_or_dress",
    "body wardrobe contract",
    "body_wardrobe_contract_application",
)

BODY_MCP_NON_BODY_FORBIDDEN_TERMS = (
    "professional model-card",
    "professional model card",
    "commercial photography",
    "clean white studio",
    "white studio",
    "studio light",
    "white backdrop",
    "background",
    "wardrobe",
    "attire",
    "formal",
    "business",
    "suit",
    "headshot",
    "expression",
    "professional pose",
    "camera",
    "lighting",
)


def _tiny_png_b64() -> str:
    image = Image.new("RGB", (16, 16), (140, 120, 100))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _body_slot_delta_runtime_request(slot_key: str = "body.front_full") -> ScenarioRuntimeRequest:
    return ScenarioRuntimeRequest(
        user_input=(
            f"Body slot target: {slot_key}. Render the same person as a full-body professional "
            "model-card body reference on a clean white studio background. Keep body chain, "
            "stage-aware proportion, stance, and ground contact reviewable without a fixed wardrobe recipe."
        ),
        scenario_selection={"scenario_id": "general_creative"},
        metadata={
            "project_id": "project_doc245_body_recovery",
            "requested_image_count": 1,
            "require_real_images": True,
            "professional_mode": True,
            "professional_character_card_preparation": True,
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": slot_key,
            "professional_character_card_source_class": "brain_inferred",
            "professional_planning_metadata": ProfessionalModeRuntimeBridge.character_card_stage_metadata(
                stage="body_silhouette",
                slot_key=slot_key,
            ),
            "professional_anchor_reference_assets": [
                {
                    "asset_id": "front_winner_output",
                    "output_id": "front_winner_output",
                    "role": "face_reference",
                    "source_type": "selected_output",
                    "use_policy": "identity",
                    "strength": "hard",
                    "provider_input_required": True,
                },
                {
                    "asset_id": "profile_winner_output",
                    "output_id": "profile_winner_output",
                    "role": "face_reference",
                    "source_type": "selected_output",
                    "use_policy": "identity",
                    "strength": "hard",
                    "provider_input_required": True,
                },
                {
                    "asset_id": "rear_winner_output",
                    "output_id": "rear_winner_output",
                    "role": "face_reference",
                    "source_type": "selected_output",
                    "use_policy": "identity",
                    "strength": "hard",
                    "provider_input_required": True,
                },
            ],
            "generation_channel": "mcp",
            "mcp_operation_id": f"asset_doc245:body_silhouette:{slot_key}:2:round2",
        },
    )


def _remote_required_body_brain_result(slot_key: str = "body.front_full"):
    return build_remote_required_result(
        BrainRunRequest(
            user_input=f"Prepare one Character Card {slot_key} body slot.",
            stage="scenario_runtime",
            scenario_id="general_creative",
            template_id="general_template",
            requested_image_count=1,
            requested_image_size="1024x1536",
            metadata=_body_slot_delta_runtime_request(slot_key).metadata,
        ),
        "Remote Brain timed out before the Character Card body slot prompt.",
    )


def _mcp_body_generation_request(
    prompt: str,
    *,
    stage: str = "body_silhouette",
    slot_key: str = "body.front_full",
    source_mode: str = "inference_first",
) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc245_mcp_body",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC,
        aspect_ratio="2:3",
        purpose="character_card_body_silhouette",
    )
    prompt_compilation = PromptCompilationResult(
        prompt_compilation_id="prompt_doc245_mcp_body",
        asset_id=asset.asset_id,
        visual_prompt="Body Silhouette MCP handoff test.",
        text_policy="none",
    )
    layout = LayoutPlan(
        layout_plan_id="layout_doc245_mcp_body",
        asset_id=asset.asset_id,
        platform=Platform.GENERIC,
        aspect_ratio="2:3",
        product_area=LayoutRegion(name="subject", position="full_frame"),
    )
    metadata = {
        "job_id": "job_doc245_mcp_body",
        "output_index": 0,
        "generation_channel": "mcp",
        "mcp_operation_id": "asset_doc245:body_silhouette:body.front_full:1",
        "professional_character_card_stage": stage,
        "professional_character_card_slot": slot_key,
        "professional_character_card_body_refresh_source_mode": source_mode,
        "llm_brain": {
            "canonical_provider_prompts": [
                {
                    "output_index": 1,
                    "review_status": "approved",
                    "prompt": prompt,
                }
            ]
        },
    }
    return GenerationRequest(
        asset_spec=asset,
        layout_plan=layout,
        prompt_compilation=prompt_compilation,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc245_mcp_body", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc245_mcp_body",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
            metadata={"output_index": 0},
        ),
        metadata=metadata,
    )


def _doc245_slot_delta_finalizer_context(*, stage: str, slot_key: str) -> dict[str, object]:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage=stage,
        slot_key=slot_key,
    )
    slot_delta_contract = dict(stage_metadata["reference_led_slot_delta_contract"])
    slot_delta_contract["frozen_binding"] = {
        "envelope_id": "opaque_doc245_envelope",
        "ledger_id": "opaque_doc245_ledger",
    }
    context: dict[str, object] = {
        "frozen_binding": {
            "envelope_id": "opaque_doc245_envelope",
            "ledger_id": "opaque_doc245_ledger",
        },
        "professional_face_identity_quality_contract": stage_metadata[
            "professional_face_identity_quality_contract"
        ],
        "reference_led_slot_delta_decision": slot_delta_contract,
        "provider_admission_decision": {
            "required": True,
            "contract_version": "v3_provider_admission_decision_v1",
            "provider_admission_status": "admitted",
            "prompt_language_mode": "concise_positive_renderer_direction",
            "safety_sensitive_prompt_normalized": "applied",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": {
                "envelope_id": "opaque_doc245_envelope",
                "ledger_id": "opaque_doc245_ledger",
            },
        },
    }
    if stage == "body_silhouette":
        context["character_card_slot_delta_target"] = {
            "stage": "body_silhouette",
            "slot_key": slot_key,
            "body_slot": slot_key.split(".", 1)[1],
        }
    if stage == "expression_set":
        context["character_card_slot_delta_target"] = {
            "stage": "expression_set",
            "slot_key": slot_key,
            "expression": slot_key.split(".", 1)[1],
        }
    return context


def _doc245_finalizer_response_contract(context: dict[str, object]) -> str:
    payload = _canonical_provider_prompt_finalization_payload(
        BrainRunRequest(
            user_input="Finalize one Professional Character Card slot prompt.",
            stage="provider_prompt_finalize",
            scenario_id="general_creative",
            template_id="general_template",
            requested_image_count=1,
            requested_image_size="1024x1536",
            metadata={"canonical_prompt_context": context},
        )
    )
    return str(payload["remote_response_contract"])


def _generic_body_shared_receipt(
    *,
    status: str = "pass",
    include_source_standard: bool = True,
    include_source_standard_evidence: bool = True,
    include_cross_view_parity_evidence: bool = True,
    issue_codes: list[str] | None = None,
) -> dict[str, object]:
    normalized_issue_codes = list(issue_codes or ([] if status == "pass" else ["shared_visual_review_rejected"]))
    evidence_codes = [
        "shared_visual_review_verified",
        "shared_visual_review_status_pass",
        "body_silhouette_framing_reviewed",
    ]
    if status == "pass" and include_source_standard and include_source_standard_evidence:
        evidence_codes.extend(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES.values())
    if status == "pass" and include_cross_view_parity_evidence:
        evidence_codes.append(BODY_SILHOUETTE_CROSS_VIEW_PARITY_EVIDENCE_CODE)
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
        "status": status,
        "evidence_codes": evidence_codes if status == "pass" else ["shared_visual_review_unverified"],
        "issue_codes": normalized_issue_codes,
        "score_dimensions": [
            "generic_visual_quality",
            "identity_or_subject_consistency",
            *(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS if include_source_standard else ()),
            *((
                BODY_SILHOUETTE_CROSS_VIEW_PARITY_DIMENSION,
            ) if include_cross_view_parity_evidence else ()),
        ],
        "framing_delta_dimensions": ["body_scale_delta", "ground_contact_delta"],
    }


def _body_review_metadata_for_vision(slot_key: str = "body.front_full") -> dict[str, object]:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key=slot_key,
    )
    return {
        "project_id": "project_doc245_body_review",
        "capability_execution_envelope": {
            "activation_plan": {
                "plan_id": "plan_doc245_body_review",
                "activation_mode": "enforced",
                "active_capability_ids": ["human_realism"],
                "dependency_order": ["human_realism"],
                "metadata": {
                    "professional_face_identity_quality_contract": stage_metadata[
                        "professional_face_identity_quality_contract"
                    ],
                },
            },
            "resolved_constraint_ledger": {
                "hard_semantic_contract": True,
                "review_contracts": [],
                "provider_projection": {},
            },
        },
        "professional_planning_metadata": stage_metadata,
    }


def test_doc245_body_review_contract_exposes_framing_dimensions_to_shared_vision() -> None:
    contract = active_review_contract(_body_review_metadata_for_vision())

    professional_quality = contract["professional_identity_quality"]
    assert professional_quality["body_silhouette_review"]["applies"] is True
    assert set(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS).issubset(
        set(professional_quality["body_silhouette_review"]["source_standard_dimensions"])
    )
    assert set(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS).issubset(
        set(professional_quality["body_silhouette_review"]["score_dimensions"])
    )
    assert set(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS).issubset(set(contract["score_dimensions"]))
    assert set(BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS).issubset(
        set(professional_quality["body_silhouette_review"]["framing_delta_dimensions"])
    )
    assert set(BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS).issubset(set(contract["score_dimensions"]))


def test_doc245_body_review_contract_is_scene_neutral_without_fixed_wardrobe_contract() -> None:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.front_full",
    )

    quality_contract = stage_metadata["professional_face_identity_quality_contract"]

    serialized_quality = str(quality_contract).lower()
    assert "body_silhouette_wardrobe_contract" not in quality_contract
    for forbidden in BODY_SCENE_NEUTRAL_FORBIDDEN_TERMS:
        assert forbidden not in serialized_quality

    review_contract = active_review_contract(_body_review_metadata_for_vision("body.front_full"))
    body_review = review_contract["professional_identity_quality"]["body_silhouette_review"]

    assert "wardrobe_contract" not in body_review
    assert "body_silhouette_wardrobe_contract_drift" not in body_review["issue_codes"]
    assert body_review["source_standard_contract"]["scope"] == "body_silhouette_only"


def test_doc245_body_review_contract_carries_reference_driven_hair_continuity_without_fixed_style() -> None:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.side_full",
    )

    quality_contract = stage_metadata["professional_face_identity_quality_contract"]
    hair_contract = quality_contract["body_silhouette_hair_continuity_contract"]

    assert hair_contract["scope"] == "body_silhouette_only"
    assert hair_contract["source"] == "current_project_confirmed_face_identity_references"
    assert hair_contract["fixed_hairstyle_text"] is None
    assert set(hair_contract["required_continuity"]) == {
        "same_hairstyle_category",
        "same_hair_length_tier",
        "same_bangs_or_parting_pattern",
        "same_overall_hair_outline",
    }
    assert "view_angle" in hair_contract["allowed_variation"]
    assert "natural_body_view_movement" in hair_contract["allowed_variation"]
    assert "obvious_hair_length_tier_change" in hair_contract["forbidden"]

    serialized = str(hair_contract).lower()
    assert "long straight" not in serialized
    assert "long hair" not in serialized

    review_contract = active_review_contract(_body_review_metadata_for_vision("body.side_full"))
    body_review = review_contract["professional_identity_quality"]["body_silhouette_review"]

    assert body_review["hair_continuity_contract"] == hair_contract
    assert "body_silhouette_hair_continuity_drift" in body_review["issue_codes"]


class _Doc245IdentityMetricProvider:
    def __init__(self, *, objective: float, geometry: float = 0.18, confidence: float = 0.788) -> None:
        self.objective = objective
        self.geometry = geometry
        self.confidence = confidence

    def evaluate(self, output_path, references):
        assert references
        return {
            "calibrated_score": self.objective,
            "geometry_score": self.geometry,
            "metric_confidence": self.confidence,
            "metadata": {
                "viewpoint_relationship": "same_view",
                "geometry_comparability": "comparable",
            },
        }


def _doc245_identity_metric_metadata(tmp_path, *, slot_key: str) -> dict[str, object]:
    metadata = _body_review_metadata_for_vision(slot_key)
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(b"reference")
    metadata["reference_assets"] = [
        {
            "role": "portrait_identity",
            "use_policy": "identity",
            "file_path": str(reference_path),
        }
    ]
    return metadata


def _doc245_identity_metric_resolution(tmp_path) -> GeneratedOutputResolution:
    output_path = tmp_path / "output.png"
    output_path.write_bytes(b"output")
    return GeneratedOutputResolution(
        resolution_id="resolution_doc245_body_side_identity",
        job_id="job_doc245_body_side_identity",
        candidate_id="candidate_doc245_body_side_identity",
        output_id="output_doc245_body_side_identity",
        file_path=str(output_path),
        status="ready",
    )


def test_doc245_body_side_full_identity_metric_treats_close_crop_geometry_as_advisory(tmp_path) -> None:
    inspector = VisionOutputInspector(
        identity_metric_provider=_Doc245IdentityMetricProvider(objective=0.84, geometry=0.18)
    )

    _, fusion = inspector._identity_metric_fusion(
        _doc245_identity_metric_resolution(tmp_path),
        metadata=_doc245_identity_metric_metadata(tmp_path, slot_key="body.side_full"),
        multimodal_score=1.0,
    )

    assert fusion is not None
    assert fusion["hard_gate_passed"] is True
    assert fusion["geometry_evidence_mode"] == "body_full_body_side_geometry_advisory"
    assert fusion["fused_identity_score"] >= 0.82


def test_doc245_body_side_full_identity_metric_still_rejects_low_objective_identity(tmp_path) -> None:
    inspector = VisionOutputInspector(
        identity_metric_provider=_Doc245IdentityMetricProvider(objective=0.74, geometry=0.18)
    )

    _, fusion = inspector._identity_metric_fusion(
        _doc245_identity_metric_resolution(tmp_path),
        metadata=_doc245_identity_metric_metadata(tmp_path, slot_key="body.side_full"),
        multimodal_score=1.0,
    )

    assert fusion is not None
    assert fusion["hard_gate_passed"] is False
    assert fusion["reason_codes"] == ["identity_metric_below_commercial_target"]


def test_doc245_body_identity_metric_geometry_remains_hard_for_other_body_slots(tmp_path) -> None:
    inspector = VisionOutputInspector(
        identity_metric_provider=_Doc245IdentityMetricProvider(objective=0.84, geometry=0.18)
    )

    _, fusion = inspector._identity_metric_fusion(
        _doc245_identity_metric_resolution(tmp_path),
        metadata=_doc245_identity_metric_metadata(tmp_path, slot_key="body.front_full"),
        multimodal_score=1.0,
    )

    assert fusion is not None
    assert fusion["hard_gate_passed"] is False
    assert fusion["geometry_evidence_mode"] == "same_view_direct"


def test_doc245_body_brain_timeout_uses_bounded_body_slot_delta_recovery() -> None:
    runtime = ScenarioRuntime()
    request = _body_slot_delta_runtime_request("body.front_full")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_body_brain_result("body.front_full"),
    )

    assert recovered.canonical_provider_prompts
    canonical = recovered.canonical_provider_prompts[0]
    assert "full-body front-view Body Silhouette source-standard materialization" in canonical.prompt
    assert "body scale" in canonical.prompt
    assert "body chain" in canonical.prompt
    assert "stage-aware proportion" in canonical.prompt
    assert "same hairstyle category" in canonical.prompt
    assert "same hair-length tier" in canonical.prompt
    serialized_recovery = " ".join(
        [
            canonical.prompt,
            *recovered.image_set_plan.composition_rules,
            *recovered.image_set_plan.quality_bar,
            recovered.prompt_guidance.optimized_direction,
            *recovered.prompt_guidance.visual_direction_addons,
            *recovered.prompt_guidance.hard_constraints,
            *recovered.prompt_guidance.negative_prompt_addons,
            *recovered.visual_task_profile.allowed_changes,
            *recovered.visual_task_profile.visual_intent_tags,
        ]
    ).lower()
    for forbidden in BODY_SCENE_NEUTRAL_FORBIDDEN_TERMS:
        assert forbidden not in serialized_recovery
    for forbidden in BODY_MCP_NON_BODY_FORBIDDEN_TERMS:
        assert forbidden not in serialized_recovery
    assert _character_card_stage_mcp_prompt_current("body.front_full", canonical.prompt)
    assert canonical.reference_led_slot_delta_decision is not None
    assert canonical.reference_led_slot_delta_decision.slot_delta_type == "body_pose"
    assert canonical.provider_admission_decision is not None
    assert canonical.provider_admission_decision.provider_admission_status == "admitted"
    assert recovered.audit["character_card_slot_delta_recovery_prompts_received"] is True
    assert recovered.audit["character_card_slot_delta_recovery_scope"] == "professional_character_card_body_silhouette"
    assert recovered.audit["character_card_slot_delta_recovery_slot_key"] == "body.front_full"
    assert recovered.visual_task_profile is not None
    assert recovered.visual_task_profile.allowed_changes == [
        "body_view_pose_and_full_body_framing_only",
        "scene_neutral_body_source_visibility",
        "natural_body_view_hair_movement",
    ]

    runtime._require_remote_creative_brain(  # noqa: SLF001
        request,
        TemplateCapabilityPolicy(requires_remote_creative_brain=True),
        recovered,
    )
    runtime._require_brain_signed_provider_prompts(  # noqa: SLF001
        request,
        TemplateCapabilityPolicy(requires_remote_creative_brain=True),
        recovered,
        CapabilityActivationPlan(
            plan_id="plan_doc245_body_recovery",
            fingerprint="fp_doc245_body_recovery",
            job_id="job_doc245_body_recovery",
            task_profile_id="profile_doc245_body_recovery",
            template_id="general_template",
            scenario_id="general_creative",
        ),
    )


def test_doc245_body_slot_delta_recovery_rejects_body_slot_contract_mismatch() -> None:
    runtime = ScenarioRuntime()
    request = _body_slot_delta_runtime_request("body.front_full")
    bad_metadata = dict(request.metadata or {})
    bad_metadata["professional_character_card_slot"] = "body.side_full"
    bad_metadata["professional_planning_metadata"] = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.front_full",
    )
    bad_request = request.model_copy(update={"metadata": bad_metadata})
    brain_result = _remote_required_body_brain_result("body.front_full")

    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        bad_request,
        brain_result,
    )

    assert not recovered.canonical_provider_prompts
    assert "character_card_slot_delta_recovery_prompts_received" not in recovered.audit


def test_doc245_body_slot_delta_recovery_rejects_superseded_wardrobe_contract() -> None:
    runtime = ScenarioRuntime()
    request = _body_slot_delta_runtime_request("body.front_full")
    metadata = dict(request.metadata or {})
    planning_metadata = dict(metadata["professional_planning_metadata"])
    quality_contract = dict(planning_metadata["professional_face_identity_quality_contract"])
    quality_contract["body_silhouette_wardrobe_contract"] = {
        "contract_version": "professional_body_silhouette_wardrobe_v1",
        "applies": True,
        "top": "simple_white_short_sleeve_top",
        "bottom": "plain_solid_shorts",
        "feet": "barefoot",
        "forbidden": ["skirt_or_dress"],
        "scope": "body_silhouette_only",
    }
    planning_metadata["professional_face_identity_quality_contract"] = quality_contract
    metadata["professional_planning_metadata"] = planning_metadata
    bad_request = request.model_copy(update={"metadata": metadata})
    brain_result = _remote_required_body_brain_result("body.front_full")

    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        bad_request,
        brain_result,
    )

    assert not recovered.canonical_provider_prompts
    assert "character_card_slot_delta_recovery_prompts_received" not in recovered.audit


def test_doc245_body_rear_review_uses_rear_continuity_instead_of_visible_face() -> None:
    metadata = _body_review_metadata_for_vision("body.rear_full")
    contract = active_review_contract(metadata)

    body_review = contract["professional_identity_quality"]["body_silhouette_review"]
    assert body_review["applies"] is True

    prompt = _inspection_prompt(metadata)

    assert "Body rear-full evidence rule" in prompt
    assert "visible face or facial landmarks are not required" in prompt
    assert "rear-head and hair outline" in prompt
    assert "full-body containment" in prompt


def test_doc245_body_source_standard_prompt_projection_is_scene_neutral() -> None:
    metadata = _body_review_metadata_for_vision("body.front_full")
    prompt = _inspection_prompt(metadata)

    assert "professional_body_silhouette_source_standard_v1" in prompt
    for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS:
        assert dimension in prompt
    for forbidden in BODY_SCENE_NEUTRAL_FORBIDDEN_TERMS:
        assert forbidden not in prompt.lower()


def test_doc245_body_stage_metadata_projects_mcp_body_owned_channel_contract() -> None:
    metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.front_full",
    )
    quality_contract = metadata["professional_face_identity_quality_contract"]

    contract = quality_contract["body_silhouette_mcp_materialization_channel_contract"]
    expected = body_silhouette_mcp_materialization_channel_contract()

    assert contract == expected
    assert contract["allowed_body_owned_channels"] == list(BODY_SILHOUETTE_MCP_ALLOWED_BODY_CHANNELS)
    assert contract["forbidden_channel_findings"] == list(BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS)
    assert contract["face_identity_reference_scope"] == "identity_continuity_only"

    expression_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="expression_set",
        slot_key="expression.smile",
    )
    expression_quality = expression_metadata["professional_face_identity_quality_contract"]
    assert "body_silhouette_mcp_materialization_channel_contract" not in expression_quality


def test_doc245_body_canonical_finalizer_uses_body_owned_contract_not_face_anchor_pack() -> None:
    context = _doc245_slot_delta_finalizer_context(
        stage="body_silhouette",
        slot_key="body.front_full",
    )

    contract = _doc245_finalizer_response_contract(context)
    normalized = contract.lower()

    for required in (
        "body-owned source-standard materialization",
        "body proportion",
        "body scale",
        "neck-shoulder continuity",
        "torso-limb relationship",
        "developmental-stage body context",
        "stance-ground contact",
        "cross-view parity",
        "approved face identity references only for identity continuity",
        "non-body-owned channels unspecified",
    ):
        assert required in normalized

    for forbidden in (
        "professional face identity anchor-pack contract",
        "mature photographer-shot model-card baseline",
        "commercially clean",
        "product framing and photography-quality boundary",
        "selected view and user-owned styling intact",
        "mature model-card photography finish",
    ):
        assert forbidden not in normalized

    assert body_silhouette_mcp_materialization_prompt_findings(contract) == ()


def test_doc245_face_and_expression_canonical_finalizers_keep_face_contract() -> None:
    expression_context = _doc245_slot_delta_finalizer_context(
        stage="expression_set",
        slot_key="expression.smile",
    )
    expression_contract = _doc245_finalizer_response_contract(expression_context).lower()

    assert "professional face identity anchor-pack contract" in expression_contract
    assert "mature photographer-shot model-card baseline" in expression_contract
    assert "the current expression slot is expression.smile" in expression_contract

    face_context = {
        "frozen_binding": {
            "envelope_id": "opaque_doc245_envelope",
            "ledger_id": "opaque_doc245_ledger",
        },
        "professional_face_identity_quality_contract": {
            "contract_version": "professional_face_identity_quality_v2",
            "scope": "character_card_face_identity",
            "owner": "remote_v3_llm_brain",
            "capture_presentation": "neutral_identity_evidence_capture",
            "geometry_scope": "face_and_head_only",
        },
        "professional_anchor_view_decision": {
            "required": True,
            "contract_version": "v3_professional_anchor_view_decision_v3",
            "target_view_role": "standard_front",
            "capture_presentation": "neutral_identity_evidence_capture",
            "capture_continuity": "establish_neutral_capture",
            "capture_scope": "character_card_face_identity",
            "framing_standard": "consistent_head_and_upper_shoulders_reference_crop",
            "crop_policy": "head_top_margin_full_face_neck_and_upper_shoulders_visible",
            "torso_scope": "visible_neck_collar_and_upper_shoulders",
            "aspect_ratio_standard": "honor_frozen_rendering_size_as_reference_card_aspect_ratio",
            "source_viewpoint_inheritance": "identity_only_do_not_inherit_source_pose_angle",
            "front_pose_normalization": "standard_front_model_card_view",
            "face_axis_alignment": "camera_facing_front_model_card_view",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": {
                "envelope_id": "opaque_doc245_envelope",
                "ledger_id": "opaque_doc245_ledger",
            },
        },
        "provider_admission_decision": {
            "required": True,
            "contract_version": "v3_provider_admission_decision_v1",
            "provider_admission_status": "admitted",
            "prompt_language_mode": "concise_positive_renderer_direction",
            "safety_sensitive_prompt_normalized": "applied",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": {
                "envelope_id": "opaque_doc245_envelope",
                "ledger_id": "opaque_doc245_ledger",
            },
        },
    }
    face_contract = _doc245_finalizer_response_contract(face_context).lower()

    assert "professional face identity anchor-pack contract" in face_contract
    assert "mature photographer-shot model-card baseline" in face_contract
    assert "character card face identity capture" in face_contract


def test_doc245_body_mcp_handoff_rejects_superseded_non_body_channels() -> None:
    stale_prompt = (
        "Create a full-body professional model-card photograph on a clean white studio background. "
        "Use a formal business suit, white shirt, a pleasant professional smile expression, "
        "studio lighting, camera-ready portrait pose, and polished commercial photography."
    )

    findings = body_silhouette_mcp_materialization_prompt_findings(stale_prompt)

    assert findings == BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS
    assert not _character_card_stage_mcp_prompt_current("body.front_full", stale_prompt)

    provider = McpMaterializationProvider()
    with pytest.raises(ProviderRuntimeError) as exc_info:
        provider._assert_character_card_body_mcp_materialization_prompt_current(  # noqa: SLF001
            {
                "professional_character_card_stage": "body_silhouette",
                "professional_character_card_slot": "body.front_full",
                "professional_character_card_body_refresh_source_mode": "inference_first",
            },
            stale_prompt,
        )

    detail = getattr(exc_info.value, "detail", {})
    serialized = repr(detail).lower()
    assert detail["failure_code"] == "character_card_body_mcp_source_contract_invalid"
    assert detail["forbidden_channel_findings"] == list(BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS)
    for raw in ("clean white studio", "business suit", "white shirt", "professional smile"):
        assert raw not in serialized


def test_doc245_body_mcp_handoff_allows_inference_and_reference_assisted_body_owned_prompt_only() -> None:
    prompt = (
        "Full-body front-view Body Silhouette source-standard materialization. "
        "Use Face Identity references only for identity continuity. Resolve body scale, body chain, "
        "stage-aware proportion, neck-shoulder continuity, torso-limb relationship, stance-ground contact, "
        "and cross-view parity. Keep non-body visual channels unspecified."
    )

    assert _character_card_stage_mcp_prompt_current("body.front_full", prompt)
    provider = McpMaterializationProvider()
    for mode in ("inference_first", "reference_assisted"):
        provider._assert_character_card_body_mcp_materialization_prompt_current(  # noqa: SLF001
            {
                "professional_character_card_stage": "body_silhouette",
                "professional_character_card_slot": "body.front_full",
                "professional_character_card_body_refresh_source_mode": mode,
            },
            prompt,
        )


def test_doc245_body_mcp_prompt_findings_do_not_flag_negative_or_unspecified_governance_language() -> None:
    prompt = (
        "Full-body side-view Body Silhouette source-standard materialization. "
        "Resolve body scale, neck-shoulder continuity, torso-limb relationship, stance-ground contact, "
        "and cross-view parity. Keep scene-neutral body source visibility. "
        "Do not author wardrobe, attire, formal styling, expression, professional pose, scene, studio, "
        "lighting, camera, or background; leave those channels unspecified."
    )

    assert body_silhouette_mcp_materialization_prompt_findings(prompt) == ()
    assert _character_card_stage_mcp_prompt_current("body.side_full", prompt)


def test_doc245_body_mcp_build_app_request_freezes_body_owned_rendering_contract() -> None:
    prompt = (
        "Full-body front-view Body Silhouette source-standard materialization. "
        "Use Face Identity references only for identity continuity. Resolve body scale, body chain, "
        "stage-aware proportion, neck-shoulder continuity, torso-limb relationship, stance-ground contact, "
        "and cross-view parity. Keep non-body visual channels unspecified."
    )
    provider = McpMaterializationProvider()

    app_request, _, _ = provider._build_app_request(  # noqa: SLF001
        _mcp_body_generation_request(prompt, source_mode="reference_assisted")
    )

    variables = app_request.prompt_plan.variables
    context = variables["mcp_materialization_context"]
    assert context["canonical_prompt"] == prompt
    assert context["rendering_contract"]["body_silhouette_mcp_materialization_channel_contract"] == (
        body_silhouette_mcp_materialization_channel_contract()
    )


def test_doc245_body_mcp_build_app_request_blocks_stale_prompt_before_handoff_creation() -> None:
    stale_prompt = (
        "Create a full-body professional model-card photograph on a clean white studio background. "
        "Use formal business attire, a suit, professional smile expression, professional pose, "
        "studio lighting, and camera-ready pose."
    )
    provider = McpMaterializationProvider()

    with pytest.raises(ProviderRuntimeError) as exc_info:
        provider._build_app_request(  # noqa: SLF001
            _mcp_body_generation_request(stale_prompt, source_mode="inference_first")
        )

    detail = getattr(exc_info.value, "detail", {})
    assert detail["failure_code"] == "character_card_body_mcp_source_contract_invalid"
    assert detail["forbidden_channel_findings"] == list(BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS)
    assert provider.handoff_store.list_unconsumed_by_operation(
        "asset_doc245:body_silhouette:body.front_full:1"
    ) == []


def test_doc245_body_mcp_channel_contract_isolated_from_expression_and_non_body_paths() -> None:
    expression_prompt = (
        "Same face in the front card, smiling naturally with white studio card framing and upper shoulders."
    )

    assert _character_card_stage_mcp_prompt_current("expression.smile", expression_prompt)
    provider = McpMaterializationProvider()
    provider._assert_character_card_body_mcp_materialization_prompt_current(  # noqa: SLF001
        {
            "professional_character_card_stage": "expression_set",
            "professional_character_card_slot": "expression.smile",
            "generation_channel": "mcp",
        },
        expression_prompt,
    )
    provider._assert_character_card_body_mcp_materialization_prompt_current(  # noqa: SLF001
        {
            "professional_template": "ecommerce_template",
            "generation_channel": "mcp",
        },
        "A product-on-person prompt may keep product styling in the E-Commerce owner path.",
    )


def test_doc245_generic_projector_preserves_body_source_standard_dimensions_only_when_allowed() -> None:
    score_card = {
        "generic_visual_quality": 0.96,
        "identity_or_subject_consistency": 0.94,
        "body_scale_delta": 0.02,
        "ground_contact_delta": 0.01,
        "body_chain_coherence": 0.91,
        "stage_aware_proportion": 0.92,
        "head_neck_shoulder_continuity": 0.93,
        "torso_limb_joint_plausibility": 0.90,
        "stance_ground_contact": 0.91,
        "cross_view_body_parity": 0.90,
        "raw_untrusted_body_private_dimension": 0.99,
    }

    missing_allowlist = project_generic_visual_review_receipt(
        score_card=score_card,
        issue_codes=[],
        verified=True,
        raw_status="pass",
    )
    assert missing_allowlist.status == "pass"
    assert missing_allowlist.framing_delta_dimensions == ()

    body_receipt = project_generic_visual_review_receipt(
        score_card=score_card,
        issue_codes=[],
        verified=True,
        raw_status="pass",
        framing_dimension_allowlist=(
            *BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS,
            *BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS,
        ),
        verified_dimension_evidence_codes=BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES,
        verified_dimension_floor=BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR,
    )

    assert set(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS).issubset(set(body_receipt.score_dimensions))
    assert set(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES.values()).issubset(
        set(body_receipt.evidence_codes)
    )
    assert set(body_receipt.framing_delta_dimensions) == {
        "body_scale_delta",
        "ground_contact_delta",
        *BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS,
    }
    assert "raw_untrusted_body_private_dimension" not in body_receipt.framing_delta_dimensions


def _legacy_body_slot_success_receipt(slot_key: str, output_id: str) -> dict[str, object]:
    shared_reviews = [_generic_body_shared_receipt()]
    return project_character_card_slot_success_receipt(
        CharacterCardSharedRuntimeReceipt(
            reviewed_candidate_count=3,
            acceptance_mode="standard_three_candidate",
            final_winner_selection_verified=True,
            prompt_reference_parity_verified=True,
            shared_review_receipts=shared_reviews,
        ),
        module="body_silhouette",
        slot_key=slot_key,
        output_id=output_id,
        shared_review_receipts=shared_reviews,
    )


def _legacy_body_formal_receipt_without_source_standard(receipt):
    legacy_candidates = []
    for candidate in receipt.candidates:
        proof = candidate.enhanced_proof
        if proof is not None:
            proof = proof.model_copy(
                update={
                    "evidence_codes": [
                        code
                        for code in proof.evidence_codes
                        if code == "body_silhouette_profile_eligible"
                        or code.startswith("body_source_class_")
                        or code
                        in {
                            "body_face_reference_scope_verified",
                            "body_candidate_contract_verified",
                            "body_shared_review_pass_verified",
                            "body_consent_not_required",
                            "body_observed_consent_verified",
                        }
                    ],
                    "dimensions": {
                        "profile_score": 1.0 if proof.eligible else 0.0,
                        "face_reference_scope_score": 1.0,
                    },
                }
            )
        legacy_candidates.append(candidate.model_copy(update={"enhanced_proof": proof}))
    return receipt.model_copy(update={"candidates": legacy_candidates})


def _scores(index: int, *, body_eligible: bool = True) -> IdentityScoreSummary:
    evidence_codes = ["body_candidate_reviewed"]
    if body_eligible:
        evidence_codes.append("body_silhouette_profile_eligible")
    return IdentityScoreSummary(
        same_face_score=0.80 + index / 100,
        visual_quality_score=0.70 + index / 100,
        evidence_codes=evidence_codes,
    )


def _review(
    index: int,
    *,
    status: str = "pass",
    body_eligible: bool = True,
    include_source_standard: bool = True,
    include_source_standard_evidence: bool = True,
    include_cross_view_parity_evidence: bool = True,
    extra_issue_codes: list[str] | None = None,
) -> AnchorReviewDecision:
    normalized_issue_codes = [] if status == "pass" else ["candidate_failed"]
    normalized_issue_codes.extend(extra_issue_codes or [])
    if not body_eligible:
        normalized_issue_codes.append("body_silhouette_profile_rejected")
    return AnchorReviewDecision(
        status=status,  # type: ignore[arg-type]
        identity_scores=_scores(index, body_eligible=body_eligible),
        issue_codes=normalized_issue_codes,
        shared_review_receipts=[
            _generic_body_shared_receipt(
                status=status,
                include_source_standard=include_source_standard,
                include_source_standard_evidence=include_source_standard_evidence,
                include_cross_view_parity_evidence=include_cross_view_parity_evidence,
                issue_codes=normalized_issue_codes,
            )
        ],
    )


def _generic_pass_review_without_body_profile_evidence(index: int) -> AnchorReviewDecision:
    return AnchorReviewDecision(
        status="pass",
        identity_scores=IdentityScoreSummary(
            same_face_score=0.80 + index / 100,
            visual_quality_score=0.70 + index / 100,
            evidence_codes=[
                "shared_real_pixel_review_verified",
                "shared_visual_review_verified",
                "shared_visual_review_status_pass",
            ],
        ),
        issue_codes=[],
        shared_review_receipts=[_generic_body_shared_receipt(status="pass")],
    )


def _body_attempt(
    index: int,
    *,
    slot_key: str = "body.front_full",
    source_class: str = "brain_inferred",
    reference_output_ids: list[str] | None = None,
    consent_provenance_id: str | None = None,
    review: AnchorReviewDecision | None = None,
) -> object:
    refs = list(reference_output_ids or ["face_front_output", "face_profile_output", "face_rear_output"])
    body_source_admission = None
    if source_class == "observed":
        body_source_admission = {
            "contract_version": "professional_body_source_admission_v1",
            "source_class": "observed",
            "body_evidence_ids": ["body_source_asset"],
            "body_reference_role": "body_proportion_reference",
            "body_reference_truth_layer": "body_proportion_truth",
            "face_reference_output_ids": refs,
            "body_owned_channels": [
                "body_proportion",
                "body_scale",
                "neck_shoulder_transition",
                "torso_limb_proportion",
                "developmental_stage_coherence",
                "stance_ground_contact",
                "cross_view_body_parity",
            ],
        }
    elif source_class == "user_described":
        body_source_admission = {
            "contract_version": "professional_body_source_admission_v1",
            "source_class": "user_described",
            "body_evidence_ids": [],
            "body_reference_role": None,
            "body_reference_truth_layer": None,
            "face_reference_output_ids": refs,
            "body_owned_channels": [
                "body_proportion",
                "body_scale",
                "neck_shoulder_transition",
                "torso_limb_proportion",
                "developmental_stage_coherence",
                "stance_ground_contact",
                "cross_view_body_parity",
            ],
        }
    request = CharacterCardCandidateRequest(
        project_id="visual_asset_body",
        people_asset_id="people_body",
        card_version_id="card_body_formal",
        module="body_silhouette",
        slot_key=slot_key,  # type: ignore[arg-type]
        candidate_index=index,
        reference_output_ids=refs,
        user_intent="neutral body silhouette profile",
        source_class=source_class,  # type: ignore[arg-type]
        consent_provenance_id=consent_provenance_id,
        body_source_admission=body_source_admission,
        body_refresh_source_mode=(
            "reference_assisted"
            if source_class == "observed"
            else "inference_first"
            if source_class == "brain_inferred"
            else None
        ),
        body_model_context=(
            "similar_person_body_reference_assisted_v1"
            if source_class == "observed"
            else "system_inferred_body_model_scene_neutral_v1"
            if source_class == "brain_inferred"
            else None
        ),
    )
    candidate = CharacterCardCandidateResult(
        candidate_id=f"candidate_{slot_key}_{index}",
        output_id=f"output_{slot_key}_{index}",
        module="body_silhouette",
        slot_key=slot_key,
        candidate_index=index,
        source_candidate_ids=[f"source_{slot_key}_{index}"],
        source_output_ids=refs,
        canonical_prompt_hash=f"prompt_hash_{slot_key}_{index}",
        prompt_compilation_id=f"prompt_compilation_{slot_key}_{index}",
        prompt_reference_parity_verified=True,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import CharacterCardCandidateAttempt

    return CharacterCardCandidateAttempt(
        request=request,
        candidate=candidate,
        review=review or _review(index),
    )


class _BodyGenerator:
    def __init__(self) -> None:
        self.requests: list[CharacterCardCandidateRequest] = []

    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        self.requests.append(request)
        return CharacterCardCandidateResult(
            candidate_id=f"candidate_{request.slot_key}_{request.candidate_index}",
            output_id=f"output_{request.slot_key}_{request.candidate_index}",
            module=request.module,
            slot_key=request.slot_key,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"source_{request.slot_key}_{request.candidate_index}"],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash=f"prompt_hash_{request.slot_key}_{request.candidate_index}",
            prompt_compilation_id=f"prompt_compilation_{request.slot_key}_{request.candidate_index}",
            prompt_reference_parity_verified=True,
        )


class _BodyReviewer:
    def __init__(
        self,
        *,
        failing_indexes: set[int] | None = None,
        enhanced_failing_indexes: set[int] | None = None,
        cross_view_mismatch_slots: set[str] | None = None,
    ) -> None:
        self.failing_indexes = set(failing_indexes or set())
        self.enhanced_failing_indexes = set(enhanced_failing_indexes or set())
        self.cross_view_mismatch_slots = set(cross_view_mismatch_slots or set())

    def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
        return _review(
            candidate.candidate_index,
            status="fail" if candidate.candidate_index in self.failing_indexes else "pass",
            body_eligible=candidate.candidate_index not in self.enhanced_failing_indexes,
            extra_issue_codes=(
                ["cross_view_body_parity_mismatch"]
                if candidate.slot_key in self.cross_view_mismatch_slots
                else None
            ),
        )


class _BodyStageHost:
    production_shared_runtime = True

    def __init__(self, service: CharacterCardPreparationService) -> None:
        self.service = service
        self.refresh_calls = 0

    def refresh_body_silhouette(self, *, asset: object, card: CharacterCardState, request: object) -> object:
        self.refresh_calls += 1
        face_reference_output_ids = [
            str(card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ]
        return self.service.refresh_body_silhouette(
            card,
            face_reference_output_ids=face_reference_output_ids,
            source_class=request.source_class,
            body_evidence_ids=(
                [str(request.body_reference_asset_id)]
                if request.source_class == "observed" and request.body_reference_asset_id
                else []
            ),
            consent_provenance_id="consent_123" if request.source_class == "observed" else None,
            user_intent=str(getattr(asset, "preparation_intent", "") or "scene-neutral Body Silhouette source refresh"),
        )


def _card_ready_for_body() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_body_formal")
    face_slots = dict(card.face_slots)
    for slot_key, output_id in {
        "face.front": "face_front_output",
        "face.profile": "face_profile_output",
        "face.rear_head": "face_rear_output",
    }.items():
        face_slots[slot_key] = CharacterCardSlot.model_construct(
            slot_key=slot_key,
            module="face_identity",
            state="active",
            output_id=output_id,
            review_verified=True,
            prompt_reference_parity_verified=True,
        )
    expression_slots = dict(card.expression_slots)
    for slot_key in ("expression.laugh", "expression.anger", "expression.sad"):
        expression_slots[slot_key] = CharacterCardSlot.model_construct(
            slot_key=slot_key,
            module="expression_set",
            state="active",
            output_id=f"{slot_key}_output",
            review_verified=True,
            prompt_reference_parity_verified=True,
        )
    expression_slots["expression.neutral"] = CharacterCardSlot.model_construct(
        slot_key="expression.neutral",
        module="expression_set",
        state="active",
        is_alias=True,
        alias_of="face.front",
        review_verified=True,
        prompt_reference_parity_verified=True,
    )
    return card.model_copy(
        update={
            "face_identity_status": "active",
            "expression_set_status": "active",
            "face_slots": face_slots,
            "expression_slots": expression_slots,
        }
    )


def _active_body_card() -> CharacterCardState:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())
    prepared = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    verified = VisualAssetLibraryLifecycleService._mark_formal_receipts_after_projection(
        prepared.card,
        stage="body_silhouette",
    )
    return CharacterCardPreparationService.activate_module(
        verified,
        module="body_silhouette",
        confirmed=True,
    )


def test_doc245_body_slot_result_carries_per_slot_formal_receipt_after_three_reviewed_candidates() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert [request.slot_key for request in generator.requests] == [
        "body.front_full",
        "body.front_full",
        "body.front_full",
        "body.side_full",
        "body.side_full",
        "body.side_full",
        "body.rear_full",
        "body.rear_full",
        "body.rear_full",
    ]
    assert set(result.winner_output_ids) == set(BODY_SLOT_KEYS)
    assert set(result.formal_slot_receipts) == set(BODY_SLOT_KEYS)
    receipt = result.formal_slot_receipts["body.front_full"]
    assert receipt.module == "body_silhouette"
    assert receipt.slot_key == "body.front_full"
    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.winner_output_id == "output_body.front_full_3"
    assert receipt.activation_eligible is False


def test_doc245_body_preparation_does_not_require_whole_expression_set_activation() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    card = _card_ready_for_body().model_copy(update={"expression_set_status": "partial"})

    result = service.prepare_body_silhouette(
        card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "review"
    assert result.winner_output_ids["body.front_full"] == "output_body.front_full_3"
    assert result.formal_slot_receipts["body.front_full"].acceptance_mode == "standard_three_candidate"


def test_doc245_body_formal_core_filters_enhanced_ineligible_candidate_before_ranking() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_BodyReviewer(enhanced_failing_indexes={3}),
    )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    receipt = result.formal_slot_receipts["body.front_full"]
    assert receipt.winner_candidate_id == "candidate_body.front_full_2"
    assert receipt.candidates[2].shared_review.passed is True
    assert receipt.candidates[2].enhanced_proof is not None
    assert receipt.candidates[2].enhanced_proof.eligible is False


def test_doc245_body_adapter_projects_brain_inferred_source_scope_into_candidate_enhanced_proof() -> None:
    attempts = [_body_attempt(index) for index in (1, 2, 3)]

    receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.front_full",
        attempts=attempts,  # type: ignore[arg-type]
    )

    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.candidate_eligibility_required is True
    assert receipt.winner_output_id == "output_body.front_full_3"
    assert all(candidate.enhanced_proof is not None for candidate in receipt.candidates)
    assert all(candidate.enhanced_proof.eligible for candidate in receipt.candidates if candidate.enhanced_proof)
    assert {
        "body_silhouette_profile_eligible",
        "body_source_class_brain_inferred",
        "body_face_reference_scope_verified",
        "body_silhouette_source_standard_verified",
    }.issubset(set(receipt.candidates[0].enhanced_proof.evidence_codes))  # type: ignore[union-attr]
    assert receipt.candidates[0].enhanced_proof.dimensions["source_standard_score"] == 1.0  # type: ignore[union-attr]
    assert all(
        receipt.candidates[0].enhanced_proof.dimensions[f"source_standard_{dimension}"] == 1.0  # type: ignore[union-attr]
        for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS
    )


def test_doc245_body_formal_receipt_requires_source_standard_dimensions() -> None:
    attempts = [
        _body_attempt(index, review=_review(index, include_source_standard=False))
        for index in (1, 2, 3)
    ]

    with pytest.raises(ValueError, match="external eligibility passing candidate"):
        CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
            slot_key="body.front_full",
            attempts=attempts,  # type: ignore[arg-type]
        )

    proof = CharacterCardPreparationService._formal_body_enhanced_proof(  # noqa: SLF001
        slot_key="body.front_full",
        attempt=attempts[0],  # type: ignore[arg-type]
    )
    assert proof.eligible is False
    assert "body_silhouette_source_standard_evidence_missing" in proof.issue_codes
    assert proof.dimensions["source_standard_score"] == 0.0


def test_doc245_body_formal_receipt_rejects_dimensions_without_verified_evidence_codes() -> None:
    attempts = [
        _body_attempt(index, review=_review(index, include_source_standard_evidence=False))
        for index in (1, 2, 3)
    ]

    with pytest.raises(ValueError, match="external eligibility passing candidate"):
        CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
            slot_key="body.front_full",
            attempts=attempts,  # type: ignore[arg-type]
        )

    proof = CharacterCardPreparationService._formal_body_enhanced_proof(  # noqa: SLF001
        slot_key="body.front_full",
        attempt=attempts[0],  # type: ignore[arg-type]
    )
    assert proof.eligible is False
    assert "body_silhouette_source_standard_evidence_missing" in proof.issue_codes
    assert all(
        proof.dimensions[f"source_standard_{dimension}"] == 0.0
        for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS
    )


def test_doc245_body_source_standard_evidence_uses_score_floor_not_dimension_names() -> None:
    score_card = {
        "generic_visual_quality": 0.96,
        "identity_or_subject_consistency": 0.94,
        "body_scale_delta": 0.02,
        "ground_contact_delta": 0.01,
        **{dimension: 0.99 for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS},
    }
    score_card["head_neck_shoulder_continuity"] = BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR - 0.01

    receipt = project_generic_visual_review_receipt(
        score_card=score_card,
        issue_codes=[],
        verified=True,
        raw_status="pass",
        framing_dimension_allowlist=(
            *BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS,
            *BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS,
        ),
        verified_dimension_evidence_codes=BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES,
        verified_dimension_floor=BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR,
    )

    assert "head_neck_shoulder_continuity" in receipt.score_dimensions
    assert (
        BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES["head_neck_shoulder_continuity"]
        not in receipt.evidence_codes
    )


def test_doc245_body_source_standard_evidence_accepts_exact_floor_and_rejects_nonfinite_scores() -> None:
    exact_floor_score_card = {
        "generic_visual_quality": 0.96,
        "identity_or_subject_consistency": 0.94,
        **{dimension: BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS},
    }
    exact_floor_receipt = project_generic_visual_review_receipt(
        score_card=exact_floor_score_card,
        issue_codes=[],
        verified=True,
        raw_status="pass",
        verified_dimension_evidence_codes=BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES,
        verified_dimension_floor=BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR,
    )
    assert set(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES.values()).issubset(
        set(exact_floor_receipt.evidence_codes)
    )

    nonfinite_score_card = dict(exact_floor_score_card)
    nonfinite_score_card["body_chain_coherence"] = float("nan")
    nonfinite_receipt = project_generic_visual_review_receipt(
        score_card=nonfinite_score_card,
        issue_codes=[],
        verified=True,
        raw_status="pass",
        verified_dimension_evidence_codes=BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES,
        verified_dimension_floor=BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR,
    )
    assert BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES["body_chain_coherence"] not in (
        nonfinite_receipt.evidence_codes
    )


def test_doc245_generic_projector_does_not_emit_body_evidence_without_body_owner_map() -> None:
    score_card = {
        "generic_visual_quality": 0.96,
        "identity_or_subject_consistency": 0.94,
        **{dimension: 0.99 for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS},
        BODY_SILHOUETTE_CROSS_VIEW_PARITY_DIMENSION: 0.99,
    }

    receipt = project_generic_visual_review_receipt(
        score_card=score_card,
        issue_codes=[],
        verified=True,
        raw_status="pass",
    )

    body_evidence = set(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES.values())
    body_evidence.add(BODY_SILHOUETTE_CROSS_VIEW_PARITY_EVIDENCE_CODE)
    assert body_evidence.isdisjoint(set(receipt.evidence_codes))


def test_doc245_body_source_standard_contract_validator_rejects_tampered_runtime_contract() -> None:
    contract = body_silhouette_source_standard_contract()
    assert validated_body_silhouette_source_standard_contract(contract) == contract

    tampered = dict(contract)
    tampered["dimension_score_floor"] = "0.8"
    assert validated_body_silhouette_source_standard_contract(tampered) == {}

    tampered = dict(contract)
    tampered["dimension_score_floor"] = float("nan")
    assert validated_body_silhouette_source_standard_contract(tampered) == {}

    tampered = dict(contract)
    tampered["required_dimensions"] = [*contract["required_dimensions"], contract["required_dimensions"][0]]
    assert validated_body_silhouette_source_standard_contract(tampered) == {}

    tampered = dict(contract)
    tampered["required_dimensions"] = [*contract["required_dimensions"], "poolside_body_recipe"]
    assert validated_body_silhouette_source_standard_contract(tampered) == {}

    tampered = dict(contract)
    tampered["provider_private_payload"] = {"unsafe": True}
    assert validated_body_silhouette_source_standard_contract(tampered) == {}


def test_doc245_body_formal_receipt_blocks_source_standard_issue_codes() -> None:
    attempts = [
        _body_attempt(
            index,
            review=_review(index, extra_issue_codes=["pasted_head_body_boundary"]),
        )
        for index in (1, 2, 3)
    ]

    with pytest.raises(ValueError, match="external eligibility passing candidate"):
        CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
            slot_key="body.front_full",
            attempts=attempts,  # type: ignore[arg-type]
        )

    proof = CharacterCardPreparationService._formal_body_enhanced_proof(  # noqa: SLF001
        slot_key="body.front_full",
        attempt=attempts[0],  # type: ignore[arg-type]
    )
    assert proof.eligible is False
    assert "pasted_head_body_boundary" in proof.issue_codes


def test_doc245_rear_body_no_visible_face_issue_does_not_block_rear_role_evidence() -> None:
    rear_attempts = [
        _body_attempt(
            index,
            slot_key="body.rear_full",
            review=_review(index).model_copy(update={"issue_codes": ["output_face_not_detected"]}),
        )
        for index in (1, 2, 3)
    ]

    receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.rear_full",
        attempts=rear_attempts,  # type: ignore[arg-type]
    )

    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.winner_output_id == "output_body.rear_full_3"
    assert all(candidate.enhanced_proof is not None for candidate in receipt.candidates)
    assert all(candidate.enhanced_proof.eligible for candidate in receipt.candidates if candidate.enhanced_proof)


def test_doc245_rear_body_missing_rear_evidence_still_fails_closed() -> None:
    rear_attempts = [_body_attempt(index, slot_key="body.rear_full") for index in (1, 2, 3)]
    rear_attempts[1] = _body_attempt(
        2,
        slot_key="body.rear_full",
        review=_review(2, status="fail", body_eligible=False),
    )

    receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.rear_full",
        attempts=rear_attempts,  # type: ignore[arg-type]
    )

    assert receipt.winner_candidate_id == "candidate_body.rear_full_3"
    rejected = receipt.candidates[1]
    assert rejected.shared_review.passed is False
    assert rejected.enhanced_proof is not None
    assert rejected.enhanced_proof.eligible is False


def test_doc245_body_adapter_rejects_observed_without_consent_or_reference_scope_mismatch() -> None:
    observed_missing_consent = [
        _body_attempt(index, source_class="observed", consent_provenance_id="consent_123")
        for index in (1, 2, 3)
    ]
    observed_missing_consent[0] = observed_missing_consent[0].model_copy(
        update={
            "request": observed_missing_consent[0].request.model_construct(
                **{
                    **observed_missing_consent[0].request.model_dump(mode="python"),
                    "source_class": "observed",
                    "consent_provenance_id": None,
                }
            )
        }
    )

    with pytest.raises(ValueError, match="Body formal slot enhanced proof contract mismatch"):
        CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
            slot_key="body.front_full",
            attempts=observed_missing_consent,  # type: ignore[arg-type]
        )

    mismatched_refs = [_body_attempt(index) for index in (1, 2, 3)]
    mismatched_refs[1] = mismatched_refs[1].model_copy(
        update={
            "request": mismatched_refs[1].request.model_copy(
                update={"reference_output_ids": ["face_front_output", "face_profile_output", "wrong_rear_output"]}
            )
        }
    )
    with pytest.raises(ValueError, match="Body formal slot enhanced proof contract mismatch"):
        CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
            slot_key="body.front_full",
            attempts=mismatched_refs,  # type: ignore[arg-type]
        )


def test_doc245_body_formal_core_blocks_when_all_enhanced_profiles_fail() -> None:
    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_BodyReviewer(enhanced_failing_indexes={1, 2, 3}),
    )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.winner_output_ids == {}
    assert result.formal_slot_receipts == {}
    assert result.failures[-1].failure_code == "character_card_formal_slot_receipt_invalid"
    assert result.failures[-1].failure_details is not None
    assert result.failures[-1].failure_details.failure_code == BODY_FORMAL_SLOT_NO_EXTERNAL_ELIGIBILITY_CODE
    assert result.failures[-1].failure_details.passed_shared_review_count == 3
    assert result.failures[-1].failure_details.enhanced_eligible_count == 0
    assert result.card.last_failure_code == "character_card_formal_slot_receipt_invalid"
    assert result.card.last_failure_details == result.failures[-1].failure_details


def test_doc245_body_formal_failure_projection_classifies_shared_review_rejection_without_ids() -> None:
    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_BodyReviewer(failing_indexes={1, 2, 3}),
    )

    result = service.refresh_body_silhouette(
        _active_body_card(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_source_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.failures[-1].failure_code == "character_card_formal_slot_receipt_invalid"
    details = result.failures[-1].failure_details
    assert details is not None
    assert details.failure_code == BODY_FORMAL_SLOT_NO_PASSING_SHARED_REVIEW_CODE
    assert details.slot_key == "body.front_full"
    assert details.candidate_count == 3
    assert details.candidate_indexes == [1, 2, 3]
    assert details.passed_shared_review_count == 0
    assert details.enhanced_eligible_count == 0
    assert all(
        "shared_review_not_pass" in summary.issue_categories
        for summary in details.candidate_summaries
    )
    assert details.failure_code != BODY_FORMAL_SLOT_SOURCE_STANDARD_MISSING_CODE
    serialized = str(details)
    assert "candidate_body" not in serialized
    assert "output_body" not in serialized
    assert "face_front_output" not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized
    assert "D:\\" not in serialized
    assert "raw" not in serialized.lower()
    assert result.card.last_failure_code == "character_card_formal_slot_receipt_invalid"
    assert result.card.last_failure_details == details


def test_doc245_body_formal_failure_preserves_candidate_generation_blocked_evidence() -> None:
    class _ThirdCandidateProviderBlockedGenerator(_BodyGenerator):
        def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
            if request.candidate_index == 3:
                self.requests.append(request)
                raise AnchorCandidateUnavailable("image_edit_invalid_request_unattributed")
            return super().generate(request)

    class _SecondCandidateSourceStandardBlockedReviewer(_BodyReviewer):
        def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
            if candidate.candidate_index == 2:
                return _review(
                    candidate.candidate_index,
                    status="fail",
                    include_source_standard=True,
                    include_source_standard_evidence=False,
                    extra_issue_codes=["head_body_scale_mismatch"],
                )
            return _review(candidate.candidate_index)

    generator = _ThirdCandidateProviderBlockedGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_SecondCandidateSourceStandardBlockedReviewer(),
    )

    result = service.refresh_body_silhouette(
        _active_body_card(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="scene-neutral inference-first body silhouette profile",
    )

    assert [request.candidate_index for request in generator.requests] == [1, 2, 3]
    assert result.status == "blocked"
    assert result.failures[0].failure_code == "image_edit_invalid_request_unattributed"
    assert result.failures[-1].failure_code == "character_card_formal_slot_receipt_invalid"
    details = result.failures[-1].failure_details
    assert details is not None
    assert details.failure_code == BODY_FORMAL_SLOT_REVIEWED_COUNT_INVALID_CODE
    assert details.candidate_count == 2
    assert details.candidate_indexes == [1, 2]
    assert details.passed_shared_review_count == 1
    assert details.source_standard_evidence_missing_count == 1
    assert details.source_standard_blocking_issue_count == 1
    assert details.candidate_generation_blocked_count == 1
    assert details.candidate_generation_blocked_indexes == [3]
    assert len(details.candidate_generation_failures) == 1
    blocked = details.candidate_generation_failures[0]
    assert blocked.candidate_index == 3
    assert blocked.failure_family == "provider_no_pixel"
    assert blocked.failure_code == "image_edit_invalid_request_unattributed"
    serialized = details.model_dump_json()
    assert "OpenAI image reference generation failed" not in serialized
    assert "provider_payload" not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized
    assert "D:\\" not in serialized


def test_doc245_body_candidate_lifecycle_projects_pre_durable_plan_block_without_raw_leak() -> None:
    raw_secret = (
        "raw prompt http://provider.invalid/path C:\\secret\\prompt.txt "
        "provider_payload asset_private_123 output_private_456"
    )

    class _ThirdCandidatePreDurablePlanBlockedGenerator(_BodyGenerator):
        def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
            self.requests.append(request)
            if request.slot_key == "body.front_full" and request.candidate_index == 3:
                error = CharacterCardCandidateLifecycleBoundaryError(
                    lifecycle_phase="planning",
                    failure_family="candidate_planning",
                    failure_code="candidate_pre_durable_planning_blocked",
                )
                error.raw_secret = raw_secret
                raise error
            return CharacterCardCandidateResult(
                candidate_id=f"candidate_{request.slot_key}_{request.candidate_index}",
                output_id=f"output_{request.slot_key}_{request.candidate_index}",
                module=request.module,
                slot_key=request.slot_key,
                candidate_index=request.candidate_index,
                source_candidate_ids=[f"source_{request.slot_key}_{request.candidate_index}"],
                source_output_ids=list(request.reference_output_ids),
                canonical_prompt_hash=f"prompt_hash_{request.slot_key}_{request.candidate_index}",
                prompt_compilation_id=f"prompt_compilation_{request.slot_key}_{request.candidate_index}",
                prompt_reference_parity_verified=True,
            )

    original = _active_body_card()
    generator = _ThirdCandidatePreDurablePlanBlockedGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.refresh_body_silhouette(
        original,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="scene-neutral inference-first body silhouette profile",
    )

    assert [request.slot_key for request in generator.requests] == [
        "body.front_full",
        "body.front_full",
        "body.front_full",
    ]
    assert [request.candidate_index for request in generator.requests] == [1, 2, 3]
    assert result.status == "blocked"
    assert result.winner_output_ids == {}
    assert result.formal_slot_receipts == {}
    assert result.card.body_slots == original.body_slots
    assert result.card.body_silhouette_refresh_slots == {}

    lifecycle_events = [
        failure.candidate_lifecycle
        for failure in result.failures
        if failure.candidate_lifecycle is not None
    ]
    assert len(lifecycle_events) == 1
    lifecycle = lifecycle_events[0]
    assert lifecycle.stage == "body_silhouette"
    assert lifecycle.slot_key == "body.front_full"
    assert lifecycle.candidate_index == 3
    assert lifecycle.candidate_count == 3
    assert lifecycle.lifecycle_phase == "planning"
    assert lifecycle.status == "blocked"
    assert lifecycle.failure_family == "candidate_planning"
    assert lifecycle.failure_code == "candidate_pre_durable_planning_blocked"

    details = result.card.last_failure_details
    assert details is not None
    assert details.failure_code == BODY_FORMAL_SLOT_REVIEWED_COUNT_INVALID_CODE
    assert details.candidate_count == 2
    assert details.candidate_indexes == [1, 2]
    assert details.candidate_generation_blocked_count == 1
    assert details.candidate_generation_blocked_indexes == [3]
    assert details.candidate_lifecycle_blocked_count == 1
    assert details.candidate_lifecycle_blocked_indexes == [3]
    assert details.candidate_lifecycle_failures[0].failure_family == "candidate_planning"
    assert details.candidate_lifecycle_failures[0].failure_code == "candidate_pre_durable_planning_blocked"

    serialized = result.card.model_dump_json()
    for forbidden in (
        "raw prompt",
        "http://provider.invalid",
        "C:\\secret",
        "provider_payload",
        "asset_private_123",
        "output_private_456",
    ):
        assert forbidden not in serialized


def test_doc245_body_candidate_lifecycle_projects_review_block_without_accepting_artifact() -> None:
    class _SecondCandidateReviewBlockedReviewer(_BodyReviewer):
        def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
            if candidate.slot_key == "body.front_full" and candidate.candidate_index == 2:
                error = CharacterCardCandidateLifecycleBoundaryError(
                    lifecycle_phase="review",
                    failure_family="candidate_review",
                    failure_code="candidate_review_blocked",
                )
                error.raw_secret = (
                    "review raw response https://review.invalid C:\\review\\payload.json output_secret_789"
                )
                raise error
            return super().review(candidate)

    original = _active_body_card()
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_SecondCandidateReviewBlockedReviewer(),
    )

    result = service.refresh_body_silhouette(
        original,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="scene-neutral inference-first body silhouette profile",
    )

    assert [request.slot_key for request in generator.requests] == [
        "body.front_full",
        "body.front_full",
    ]
    assert [request.candidate_index for request in generator.requests] == [1, 2]
    assert result.status == "blocked"
    assert result.winner_output_ids == {}
    assert result.formal_slot_receipts == {}
    assert result.card.body_slots == original.body_slots
    assert result.card.body_silhouette_refresh_slots == {}

    lifecycle_events = [
        failure.candidate_lifecycle
        for failure in result.failures
        if failure.candidate_lifecycle is not None
    ]
    assert len(lifecycle_events) == 1
    lifecycle = lifecycle_events[0]
    assert lifecycle.slot_key == "body.front_full"
    assert lifecycle.candidate_index == 2
    assert lifecycle.lifecycle_phase == "review"
    assert lifecycle.status == "blocked"
    assert lifecycle.failure_family == "candidate_review"
    assert lifecycle.failure_code == "candidate_review_blocked"

    details = result.card.last_failure_details
    assert details is not None
    assert details.failure_code == BODY_FORMAL_SLOT_REVIEWED_COUNT_INVALID_CODE
    assert details.candidate_count == 1
    assert details.candidate_indexes == [1]
    assert details.candidate_lifecycle_blocked_count == 1
    assert details.candidate_lifecycle_blocked_indexes == [2]
    assert details.candidate_lifecycle_failures[0].failure_family == "candidate_review"
    assert details.candidate_lifecycle_failures[0].failure_code == "candidate_review_blocked"

    serialized = result.card.model_dump_json()
    for forbidden in (
        "review raw response",
        "https://review.invalid",
        "C:\\review",
        "payload.json",
        "output_secret_789",
    ):
        assert forbidden not in serialized


def test_doc245_body_candidate_lifecycle_projection_rejects_unclosed_or_wrong_typed_payload() -> None:
    valid = {
        "contract": "character_card_candidate_lifecycle_projection_v1",
        "stage": "body_silhouette",
        "slot_key": "body.front_full",
        "candidate_index": 3,
        "candidate_count": 3,
        "lifecycle_phase": "planning",
        "status": "blocked",
        "failure_family": "candidate_planning",
        "failure_code": "candidate_pre_durable_planning_blocked",
    }
    assert CharacterCardCandidateLifecycleProjection.model_validate(valid).candidate_index == 3
    for bad in (
        {**valid, "candidate_index": "3"},
        {**valid, "candidate_count": True},
        {**valid, "lifecycle_phase": "http://provider.invalid/path"},
        {**valid, "raw_prompt": "do not leak"},
        {**valid, "failure_code": "provider_payload_secret"},
        {**valid, "status": "completed", "failure_family": "candidate_planning"},
    ):
        with pytest.raises(ValueError):
            CharacterCardCandidateLifecycleProjection.model_validate(bad)


def test_doc245_body_candidate_lifecycle_does_not_swallow_unknown_programming_errors() -> None:
    class _UnknownRuntimeGenerator(_BodyGenerator):
        def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
            self.requests.append(request)
            raise RuntimeError("programming bug http://provider.invalid C:\\raw\\payload")

    service = CharacterCardPreparationService(
        generator=_UnknownRuntimeGenerator(),
        reviewer=_BodyReviewer(),
    )

    with pytest.raises(RuntimeError, match="programming bug"):
        service.refresh_body_silhouette(
            _active_body_card(),
            face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            source_class="brain_inferred",
            user_intent="scene-neutral inference-first body silhouette profile",
        )


def test_doc245_body_candidate_lifecycle_does_not_swallow_keyboard_interrupt() -> None:
    class _InterruptingReviewer(_BodyReviewer):
        def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
            raise KeyboardInterrupt()

    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_InterruptingReviewer(),
    )

    with pytest.raises(KeyboardInterrupt):
        service.refresh_body_silhouette(
            _active_body_card(),
            face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            source_class="brain_inferred",
            user_intent="scene-neutral inference-first body silhouette profile",
        )


def test_doc245_anchor_host_propagates_closed_pre_durable_candidate_lifecycle_boundary() -> None:
    class _PreDurableBoundaryProductService:
        visual_asset_catalog = object()

        def __init__(self) -> None:
            self.create_calls = 0

        def create_professional_character_card_stage_job(self, *args: object, **kwargs: object) -> object:
            self.create_calls += 1
            error = CharacterCardCandidateLifecycleBoundaryError(
                lifecycle_phase="planning",
                failure_family="candidate_planning",
                failure_code="candidate_pre_durable_planning_blocked",
            )
            error.raw_secret = "http://provider.invalid C:\\raw\\provider_payload asset_private output_private"
            raise error

    service = _PreDurableBoundaryProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    request = _body_attempt(3).request

    with pytest.raises(CharacterCardCandidateLifecycleBoundaryError) as raised:
        host.generate(request)

    assert service.create_calls == 1
    assert raised.value.candidate_lifecycle_phase == "planning"
    assert raised.value.candidate_lifecycle_failure_family == "candidate_planning"
    assert raised.value.candidate_lifecycle_failure_code == "candidate_pre_durable_planning_blocked"
    public = CharacterCardPreparationService._candidate_lifecycle_projection_from_exception(  # noqa: SLF001
        raised.value,
        module="body_silhouette",
        slot_key="body.front_full",
        candidate_index=3,
        default_phase="generation",
        default_family="candidate_generation",
        default_code="unknown_candidate_generation_failure",
    )
    serialized = public.model_dump_json()
    for forbidden in (
        "http://provider.invalid",
        "C:\\raw",
        "provider_payload",
        "asset_private",
        "output_private",
    ):
        assert forbidden not in serialized


def test_doc245_anchor_host_sends_server_owned_candidate_index_to_product_api_boundary() -> None:
    class _CapturingBoundaryProductService:
        visual_asset_catalog = object()

        def __init__(self) -> None:
            self.captured_kwargs: dict[str, object] | None = None

        def create_professional_character_card_stage_job(self, *args: object, **kwargs: object) -> object:
            self.captured_kwargs = dict(kwargs)
            raise CharacterCardCandidateLifecycleBoundaryError(
                lifecycle_phase="planning",
                failure_family="candidate_planning",
                failure_code="candidate_pre_durable_planning_blocked",
            )

    service = _CapturingBoundaryProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    request = _body_attempt(2, slot_key="body.rear_full").request

    with pytest.raises(CharacterCardCandidateLifecycleBoundaryError):
        host.generate(request)

    assert service.captured_kwargs is not None
    assert service.captured_kwargs["stage"] == "body_silhouette"
    assert service.captured_kwargs["slot_key"] == "body.rear_full"
    assert service.captured_kwargs["candidate_index"] == 2


def _checkpoint_value(checkpoint: object, key: str) -> object:
    if isinstance(checkpoint, dict):
        return checkpoint.get(key)
    if hasattr(checkpoint, "model_dump"):
        dumped = checkpoint.model_dump()  # type: ignore[attr-defined]
        if isinstance(dumped, dict):
            return dumped.get(key)
    return getattr(checkpoint, key, None)


def test_doc245_candidate_lifecycle_checkpoint_contract_is_closed_typed_and_no_leak() -> None:
    checkpoint_model = getattr(character_card_module, "CharacterCardCandidateLifecycleCheckpoint", None)
    assert checkpoint_model is not None, "CharacterCardCandidateLifecycleCheckpoint missing"

    valid = {
        "contract": "character_card_candidate_lifecycle_checkpoint_v1",
        "stage": "body_silhouette",
        "slot_key": "body.rear_full",
        "candidate_index": 1,
        "candidate_count": 3,
        "lifecycle_phase": "review_extraction",
        "status": "blocked",
        "failure_family": "candidate_review",
        "failure_code": "candidate_review_extraction_unbound",
    }
    checkpoint = checkpoint_model.model_validate(valid)
    assert _checkpoint_value(checkpoint, "candidate_index") == 1
    for bad in (
        {**valid, "candidate_index": "1"},
        {**valid, "candidate_count": 1},
        {**valid, "candidate_count": 2},
        {**valid, "candidate_count": True},
        {**valid, "candidate_count": "3"},
        {**valid, "candidate_count": 3.0},
        {**valid, "slot_key": "body.unknown"},
        {**valid, "lifecycle_phase": "https://provider.invalid/review"},
        {**valid, "raw_prompt": "raw prompt must not leak"},
        {**valid, "provider_payload": {"secret": "do not persist"}},
        {**valid, "asset_id": "asset_private_123"},
        {**valid, "output_id": "v3_output_private_456"},
    ):
        with pytest.raises(ValueError):
            checkpoint_model.model_validate(bad)


def test_doc245_candidate_lifecycle_checkpoint_helper_does_not_clamp_invalid_candidate_index() -> None:
    for value in (0, 4, True, False, "2", None):
        with pytest.raises(ValueError):
            CharacterCardPreparationService._candidate_lifecycle_checkpoint(  # noqa: SLF001[arg-type]
                module="body_silhouette",
                slot_key="body.front_full",
                candidate_index=value,
                lifecycle_phase="generation",
                status="completed",
            )


def test_doc245_anchor_host_sends_server_owned_candidate_count_to_product_api_boundary() -> None:
    class _CapturingBoundaryProductService:
        visual_asset_catalog = object()

        def __init__(self) -> None:
            self.captured_kwargs: dict[str, object] | None = None

        def create_professional_character_card_stage_job(self, *args: object, **kwargs: object) -> object:
            self.captured_kwargs = dict(kwargs)
            raise CharacterCardCandidateLifecycleBoundaryError(
                lifecycle_phase="planning",
                failure_family="candidate_planning",
                failure_code="candidate_pre_durable_planning_blocked",
            )

    service = _CapturingBoundaryProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    request = _body_attempt(2, slot_key="body.rear_full").request

    with pytest.raises(CharacterCardCandidateLifecycleBoundaryError):
        host.generate(request)

    assert service.captured_kwargs is not None
    assert service.captured_kwargs["stage"] == "body_silhouette"
    assert service.captured_kwargs["slot_key"] == "body.rear_full"
    assert service.captured_kwargs["candidate_index"] == 2
    assert service.captured_kwargs["candidate_count"] == 3


def test_doc245_anchor_generated_job_records_review_extraction_checkpoints_before_boundary() -> None:
    class _EmptyOutputStore:
        def list_by_job(self, job_id: str) -> list[object]:
            return []

    class _GeneratedButUnboundProductService:
        visual_asset_catalog = object()

        def __init__(self) -> None:
            self.output_store = _EmptyOutputStore()
            self.candidate_lifecycle_checkpoints: list[object] = []

        def create_professional_character_card_stage_job(self, *args: object, **kwargs: object) -> object:
            return SimpleNamespace(job_id="safe_job_generated_unbound", status=ProductJobStatusValue.PLANNED)

        def generate_job(self, job_id: str, payload: dict[str, object]) -> object:
            return SimpleNamespace(job_id=job_id, status=ProductJobStatusValue.GENERATED, metadata={})

        def get_job_record(self, job_id: str) -> object:
            return SimpleNamespace(
                generation_result=SimpleNamespace(
                    metadata={
                        "post_generation_review_package": {
                            "inspections": [
                                {
                                    "output_id": "v3_output_private_should_not_project",
                                    "raw_prompt": "raw prompt must not leak",
                                    "provider_payload": "secret provider payload",
                                    "source_url": "https://provider.invalid/private",
                                    "path": "C:\\private\\artifact.png",
                                }
                            ]
                        }
                    }
                ),
                planning_result=None,
                request=SimpleNamespace(metadata={}),
            )

        def record_character_card_candidate_lifecycle_checkpoint(
            self,
            *,
            job_id: str,
            checkpoint: object,
        ) -> None:
            self.candidate_lifecycle_checkpoints.append(checkpoint)

    service = _GeneratedButUnboundProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    request = _body_attempt(2, slot_key="body.rear_full").request

    with pytest.raises(CharacterCardCandidateLifecycleBoundaryError):
        host.generate(request)

    phases = [
        (
            _checkpoint_value(item, "lifecycle_phase"),
            _checkpoint_value(item, "status"),
            _checkpoint_value(item, "failure_code"),
        )
        for item in service.candidate_lifecycle_checkpoints
    ]
    assert ("generation", "completed", None) in phases
    assert ("review_extraction", "started", None) in phases
    assert ("review_extraction", "blocked", "candidate_review_extraction_unbound") in phases

    serialized = str(service.candidate_lifecycle_checkpoints)
    for forbidden in (
        "raw prompt",
        "provider_payload",
        "https://provider.invalid",
        "C:\\private",
        "v3_output_private_should_not_project",
    ):
        assert forbidden not in serialized


def test_doc245_body_prepare_slot_records_formal_receipt_before_after_checkpoints() -> None:
    original = _active_body_card().model_copy(update={"body_activation_confirmed": False})
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())

    result = service.refresh_body_silhouette(
        original,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="scene-neutral inference-first body silhouette profile",
    )

    checkpoints = list(getattr(result, "candidate_lifecycle_checkpoints", []) or [])
    phases = [
        (
            _checkpoint_value(item, "slot_key"),
            _checkpoint_value(item, "candidate_index"),
            _checkpoint_value(item, "candidate_count"),
            _checkpoint_value(item, "lifecycle_phase"),
            _checkpoint_value(item, "status"),
        )
        for item in checkpoints
    ]
    assert ("body.front_full", 3, 3, "formal_receipt", "started") in phases
    assert ("body.front_full", 3, 3, "formal_receipt", "completed") in phases
    assert result.card.body_slots == original.body_slots
    assert result.card.body_activation_confirmed is False


def test_doc245_anchor_generated_review_extraction_gap_projects_closed_lifecycle_boundary() -> None:
    class _EmptyOutputStore:
        def list_by_job(self, job_id: str) -> list[object]:
            return []

    class _GeneratedButUnboundProductService:
        visual_asset_catalog = object()

        def __init__(self) -> None:
            self.output_store = _EmptyOutputStore()

        def create_professional_character_card_stage_job(self, *args: object, **kwargs: object) -> object:
            return SimpleNamespace(job_id="safe_job_generated_unbound", status=ProductJobStatusValue.PLANNED)

        def generate_job(self, job_id: str, payload: dict[str, object]) -> object:
            return SimpleNamespace(job_id=job_id, status=ProductJobStatusValue.GENERATED, metadata={})

        def get_job_record(self, job_id: str) -> object:
            return SimpleNamespace(
                generation_result=SimpleNamespace(
                    metadata={
                        "post_generation_review_package": {
                            "inspections": [
                                {
                                    "output_id": "v3_output_missing_store",
                                    "raw_prompt": "raw prompt must not leak",
                                    "provider_payload": "secret provider payload",
                                    "source_url": "https://provider.invalid/private",
                                    "path": "C:\\private\\artifact.png",
                                }
                            ]
                        }
                    }
                ),
                planning_result=None,
                request=SimpleNamespace(metadata={}),
            )

    host = ProductApiAnchorPackPreparationHost(_GeneratedButUnboundProductService())  # type: ignore[arg-type]
    request = _body_attempt(2, slot_key="body.rear_full").request

    with pytest.raises(CharacterCardCandidateLifecycleBoundaryError) as raised:
        host.generate(request)

    public = CharacterCardPreparationService._candidate_lifecycle_projection_from_exception(  # noqa: SLF001
        raised.value,
        module="body_silhouette",
        slot_key="body.rear_full",
        candidate_index=2,
        default_phase="review",
        default_family="candidate_review",
        default_code="candidate_review_blocked",
    )
    assert public.lifecycle_phase == "review"
    assert public.failure_family == "candidate_review"
    assert public.failure_code == "candidate_review_extraction_unbound"
    serialized = public.model_dump_json()
    for forbidden in (
        "raw prompt",
        "provider_payload",
        "https://provider.invalid",
        "C:\\private",
        "v3_output_missing_store",
    ):
        assert forbidden not in serialized


def test_doc245_body_formal_failure_projection_classifies_source_standard_missing_separately() -> None:
    class _MissingSourceStandardReviewer(_BodyReviewer):
        def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
            return _review(candidate.candidate_index, include_source_standard=False)

    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_MissingSourceStandardReviewer(),
    )

    result = service.refresh_body_silhouette(
        _active_body_card(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_source_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.failure_codes[0] == "body.front_full_no_reviewed_winner"
    assert "character_card_formal_slot_receipt_invalid" in result.failure_codes
    details = result.failures[-1].failure_details
    assert details is not None
    assert details.failure_code == BODY_FORMAL_SLOT_SOURCE_STANDARD_MISSING_CODE
    assert details.passed_shared_review_count == 3
    assert details.enhanced_eligible_count == 0
    assert details.source_standard_evidence_missing_count == 3
    assert details.shared_review_receipt_missing_count == 0
    assert details.candidate_contract_mismatch_count == 0
    assert details.failure_code != BODY_FORMAL_SLOT_NO_PASSING_SHARED_REVIEW_CODE
    lifecycle = result.failures[-1].candidate_lifecycle
    assert lifecycle is not None
    assert lifecycle.stage == "body_silhouette"
    assert lifecycle.slot_key == "body.front_full"
    assert lifecycle.candidate_index == 3
    assert lifecycle.candidate_count == 3
    assert lifecycle.lifecycle_phase == "formal_receipt"
    assert lifecycle.status == "blocked"
    assert lifecycle.failure_family == "formal_receipt"
    assert lifecycle.failure_code == "candidate_formal_receipt_blocked"


def test_doc245_body_formal_failure_details_reject_raw_unknown_or_wrong_typed_readback() -> None:
    valid = {
        "contract": "body_formal_slot_failure_projection_v1",
        "failure_code": BODY_FORMAL_SLOT_NO_PASSING_SHARED_REVIEW_CODE,
        "module": "body_silhouette",
        "slot_key": "body.rear_full",
        "candidate_count": 3,
        "candidate_indexes": [1, 2, 3],
        "passed_shared_review_count": 0,
        "enhanced_eligible_count": 0,
        "shared_review_receipt_missing_count": 0,
        "source_standard_evidence_missing_count": 0,
        "source_standard_blocking_issue_count": 0,
        "candidate_contract_mismatch_count": 0,
        "candidate_summaries": [
            {
                "candidate_index": index,
                "shared_review_status": "fail",
                "shared_review_passed": False,
                "enhanced_proof_eligible": False,
                "issue_categories": ["shared_review_not_pass"],
            }
            for index in (1, 2, 3)
        ],
    }

    assert BodyFormalSlotFailureDetails.model_validate(valid).failure_code == (
        BODY_FORMAL_SLOT_NO_PASSING_SHARED_REVIEW_CODE
    )

    unsafe_payloads = [
        {"raw_prompt": "secret renderer prompt"},
        {"provider_payload": {"secret": True}},
        {"file_path": "D:\\unsafe\\body.png"},
        {"source_url": "https://example.invalid/private"},
        {"asset_id": "asset_private"},
    ]
    for extra in unsafe_payloads:
        with pytest.raises(ValueError):
            BodyFormalSlotFailureDetails.model_validate({**valid, **extra})

    wrong_type = dict(valid)
    wrong_type["candidate_count"] = "3"
    with pytest.raises(ValueError):
        BodyFormalSlotFailureDetails.model_validate(wrong_type)

    wrong_category = dict(valid)
    wrong_category["candidate_summaries"] = [
        {
            **valid["candidate_summaries"][0],
            "issue_categories": ["raw_provider_payload"],
        },
        *valid["candidate_summaries"][1:],
    ]
    with pytest.raises(ValueError):
        BodyFormalSlotFailureDetails.model_validate(wrong_category)

    with pytest.raises(ValueError):
        CharacterCardState.model_validate(
            {
                "card_version_id": "card_injected",
                "last_failure_details": {**valid, "raw_response": "unsafe"},
            }
        )


def test_doc245_body_formal_failure_projection_classifies_missing_shared_review_receipt() -> None:
    class _MissingSharedReceiptReviewer(_BodyReviewer):
        def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
            return _review(candidate.candidate_index).model_copy(update={"shared_review_receipts": []})

    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_MissingSharedReceiptReviewer(),
    )

    result = service.refresh_body_silhouette(
        _active_body_card(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_source_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.failures[-1].failure_code == "character_card_formal_slot_receipt_invalid"
    details = result.failures[-1].failure_details
    assert details is not None
    assert details.failure_code == BODY_FORMAL_SLOT_SHARED_REVIEW_RECEIPT_MISSING_CODE
    assert details.shared_review_receipt_missing_count == 3
    assert details.failure_code != BODY_FORMAL_SLOT_NO_PASSING_SHARED_REVIEW_CODE


def test_doc245_body_formal_failure_projection_classifies_candidate_contract_mismatch() -> None:
    attempts = [_body_attempt(index, slot_key="body.rear_full") for index in (1, 2, 3)]
    attempts[1] = attempts[1].model_copy(
        update={
            "request": attempts[1].request.model_copy(
                update={"reference_output_ids": ["face_front_output", "face_profile_output", "wrong_rear_output"]}
            )
        }
    )

    details = CharacterCardPreparationService._formal_body_slot_failure_projection(  # noqa: SLF001
        slot_key="body.rear_full",
        attempts=attempts,  # type: ignore[arg-type]
    )

    assert details.failure_code == BODY_FORMAL_SLOT_CANDIDATE_CONTRACT_MISMATCH_CODE
    assert details.candidate_contract_mismatch_count == 1
    assert details.failure_code != BODY_FORMAL_SLOT_SHARED_REVIEW_RECEIPT_MISSING_CODE


def test_doc245_body_formal_failure_projection_classifies_reviewed_count_invalid() -> None:
    details = CharacterCardPreparationService._formal_body_slot_failure_projection(  # noqa: SLF001
        slot_key="body.rear_full",
        attempts=[_body_attempt(1, slot_key="body.rear_full")],  # type: ignore[arg-type]
    )

    assert details.failure_code == BODY_FORMAL_SLOT_REVIEWED_COUNT_INVALID_CODE
    assert details.candidate_count == 1
    assert details.candidate_indexes == [1]


def test_doc245_body_three_slot_acceptance_blocks_cross_view_parity_mismatch() -> None:
    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_BodyReviewer(cross_view_mismatch_slots={"body.side_full"}),
    )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["body_silhouette_cross_view_parity_mismatch"]
    assert result.card.body_silhouette_status == "blocked"
    assert result.formal_slot_receipts == {}


def test_doc245_body_three_slot_acceptance_requires_cross_view_positive_evidence() -> None:
    class _MissingCrossViewBodyReviewer(_BodyReviewer):
        def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
            return _review(candidate.candidate_index, include_cross_view_parity_evidence=False)

    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_MissingCrossViewBodyReviewer(),
    )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["body_silhouette_cross_view_parity_evidence_missing"]
    assert result.card.body_silhouette_status == "blocked"


def test_doc245_body_stage_level_runtime_receipt_cannot_replace_per_slot_formal_receipts() -> None:
    card = _card_ready_for_body()
    body_slots = {}
    for slot_key in BODY_SLOT_KEYS:
        body_slots[slot_key] = CharacterCardSlot(
            slot_key=slot_key,
            module="body_silhouette",
            state="winner_selected",
            output_id=f"output_{slot_key}_3",
            source_candidate_ids=[f"candidate_{slot_key}_3"],
            source_class="brain_inferred",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
            shared_runtime_receipt=_legacy_body_slot_success_receipt(slot_key, f"output_{slot_key}_3"),
        )
    card = card.model_copy(update={"body_silhouette_status": "reviewing", "body_slots": body_slots})

    with pytest.raises(ValueError, match="formal"):
        CharacterCardPreparationService.activate_module(card, module="body_silhouette", confirmed=True)


def test_doc245_active_body_refresh_adds_pending_review_without_replacing_active_slots() -> None:
    active_card = _active_body_card()
    active_slots_before = {
        key: slot.model_dump(mode="json")
        for key, slot in active_card.body_slots.items()
    }
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.refresh_body_silhouette(
        active_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_source_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )

    assert [request.slot_key for request in generator.requests] == [
        "body.front_full",
        "body.front_full",
        "body.front_full",
        "body.side_full",
        "body.side_full",
        "body.side_full",
        "body.rear_full",
        "body.rear_full",
        "body.rear_full",
    ]
    assert result.status == "review"
    assert result.card.body_silhouette_status == "active"
    assert result.card.body_activation_confirmed is True
    assert result.card.body_slots == active_card.body_slots
    assert {
        key: slot.model_dump(mode="json")
        for key, slot in result.card.body_slots.items()
    } == active_slots_before
    assert result.card.body_silhouette_refresh_status == "reviewing"
    assert set(result.card.body_silhouette_refresh_slots) == set(BODY_SLOT_KEYS)
    assert set(result.formal_slot_receipts) == set(BODY_SLOT_KEYS)
    for slot_key, refresh_slot in result.card.body_silhouette_refresh_slots.items():
        assert refresh_slot.state == "winner_selected"
        assert refresh_slot.output_id == f"output_{slot_key}_3"
        assert refresh_slot.formal_slot_receipt is not None
        assert refresh_slot.formal_slot_receipt.activation_eligible is False
    refresh_intents = " ".join(str(request.user_intent) for request in generator.requests).lower()
    assert "pool" not in refresh_intents
    assert "swim" not in refresh_intents
    assert "ecommerce" not in refresh_intents
    assert "kidswear" not in refresh_intents


def test_doc245_body_refresh_slots_reject_non_body_or_activation_bypass() -> None:
    active_card = _active_body_card()

    invalid_module = active_card.model_copy(
        update={
            "body_silhouette_refresh_status": "reviewing",
            "body_silhouette_refresh_slots": {
                slot_key: slot.model_copy(
                    update={"module": "expression_set"} if slot_key == "body.front_full" else {}
                )
                for slot_key, slot in active_card.body_slots.items()
            },
        }
    )
    with pytest.raises(ValueError, match="module mismatch"):
        invalid_module.validate_slots_and_order()
    with pytest.raises(ValueError, match="Body Silhouette refresh cannot activate"):
        active_card.model_copy(
            update={
                "body_silhouette_refresh_status": "reviewing",
                "body_silhouette_refresh_slots": {
                    slot_key: slot.model_copy(update={"state": "active"})
                    for slot_key, slot in active_card.body_slots.items()
                },
            }
        ).validate_slots_and_order()


def test_doc245_normal_body_prepare_still_skips_active_winners_without_refresh() -> None:
    active_card = _active_body_card()
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.prepare_body_silhouette(
        active_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert generator.requests == []
    assert result.winner_output_ids == {
        slot_key: active_card.body_slots[slot_key].output_id
        for slot_key in BODY_SLOT_KEYS
    }


def test_doc245_body_refresh_rejects_existing_pending_refresh_without_overwrite() -> None:
    active_card = _active_body_card()
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    first = service.refresh_body_silhouette(
        active_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_source_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )
    pending_version = first.card.body_silhouette_refresh_version_id
    pending_winners = {
        slot_key: slot.output_id
        for slot_key, slot in first.card.body_silhouette_refresh_slots.items()
    }
    request_count = len(generator.requests)

    with pytest.raises(ValueError, match="body_silhouette_refresh_pending"):
        service.refresh_body_silhouette(
            first.card,
            face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            source_class="observed",
            body_evidence_ids=["body_source_asset"],
            consent_provenance_id="consent_123",
            user_intent="observed body silhouette profile",
        )

    assert len(generator.requests) == request_count
    assert first.card.body_silhouette_refresh_version_id == pending_version
    assert {
        slot_key: slot.output_id
        for slot_key, slot in first.card.body_silhouette_refresh_slots.items()
    } == pending_winners


def test_doc245_inference_first_strict_body_refresh_allows_generation_without_body_truth() -> None:
    active_card = _active_body_card()
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.refresh_body_silhouette(
        active_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "review"
    assert len(generator.requests) == 9
    assert result.card.body_slots == active_card.body_slots
    assert result.card.body_silhouette_refresh_status == "reviewing"
    for request in generator.requests:
        assert request.source_class == "brain_inferred"
        assert request.body_refresh_source_mode == "inference_first"
        assert request.body_model_context == "system_inferred_body_model_scene_neutral_v1"
        assert request.body_refresh_contract_required is True
        assert request.body_source_admission is None
        assert request.reference_output_ids == [
            "face_front_output",
            "face_profile_output",
            "face_rear_output",
        ]
        serialized = str(request.model_dump(mode="json"))
        assert "body_proportion_truth" not in serialized
        assert "body_proportion_reference" not in serialized
        assert "observed" not in serialized


def test_doc245_user_described_strict_body_refresh_remains_non_certifying() -> None:
    active_card = _active_body_card()
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    with pytest.raises(ValueError, match="body_silhouette_refresh_body_source_unavailable"):
        service.refresh_body_silhouette(
            active_card,
            face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            source_class="user_described",
            user_intent="user described body silhouette profile",
        )

    assert generator.requests == []


def test_doc245_legacy_brain_inferred_body_candidate_remains_readable_without_source_mode() -> None:
    request = CharacterCardCandidateRequest(
        project_id="project_doc245_legacy_body",
        people_asset_id="people_doc245_legacy_body",
        card_version_id="card_doc245_legacy_body",
        module="body_silhouette",
        slot_key="body.rear_full",
        candidate_index=2,
        reference_output_ids=["front_winner", "side_winner", "rear_prior"],
        source_class="brain_inferred",
        user_intent="scene neutral historical Body Silhouette candidate",
    )

    assert request.source_class == "brain_inferred"
    assert request.body_refresh_source_mode is None
    assert request.body_model_context is None
    assert request.body_refresh_contract_required is False
    assert request.body_source_admission is None


def test_doc245_body_refresh_contract_required_marker_rejects_truthy_coercion() -> None:
    base_payload = {
        "project_id": "project_doc245_refresh_marker",
        "people_asset_id": "people_doc245_refresh_marker",
        "card_version_id": "card_doc245_refresh_marker",
        "module": "body_silhouette",
        "slot_key": "body.rear_full",
        "candidate_index": 1,
        "reference_output_ids": ["front_winner", "side_winner", "rear_prior"],
        "source_class": "brain_inferred",
        "user_intent": "scene neutral strict Body Silhouette refresh candidate",
    }

    legacy = CharacterCardCandidateRequest(**base_payload)
    assert legacy.body_refresh_contract_required is False
    strict = CharacterCardCandidateRequest(
        **base_payload,
        body_refresh_contract_required=True,
        body_refresh_source_mode="inference_first",
        body_model_context="system_inferred_body_model_scene_neutral_v1",
    )
    assert strict.body_refresh_contract_required is True

    for marker in (1, 0, "true", "false", None, [], {}):
        with pytest.raises(Exception, match="bool|Boolean|valid boolean"):
            CharacterCardCandidateRequest(
                **base_payload,
                body_refresh_contract_required=marker,
                body_refresh_source_mode="inference_first",
                body_model_context="system_inferred_body_model_scene_neutral_v1",
            )


def test_doc245_refresh_body_candidate_missing_or_wrong_source_mode_blocks() -> None:
    with pytest.raises(ValueError, match="inference-first source mode required"):
        CharacterCardCandidateRequest(
            project_id="project_doc245_refresh_body",
            people_asset_id="people_doc245_refresh_body",
            card_version_id="card_doc245_refresh_body",
            module="body_silhouette",
            slot_key="body.rear_full",
            candidate_index=1,
            reference_output_ids=["front_winner", "side_winner", "rear_prior"],
            source_class="brain_inferred",
            user_intent="scene neutral strict Body Silhouette refresh candidate",
            body_refresh_contract_required=True,
        )

    with pytest.raises(ValueError, match="inference-first source mode required"):
        CharacterCardCandidateRequest(
            project_id="project_doc245_refresh_body",
            people_asset_id="people_doc245_refresh_body",
            card_version_id="card_doc245_refresh_body",
            module="body_silhouette",
            slot_key="body.rear_full",
            candidate_index=1,
            reference_output_ids=["front_winner", "side_winner", "rear_prior"],
            source_class="brain_inferred",
            user_intent="scene neutral strict Body Silhouette refresh candidate",
            body_refresh_contract_required=True,
            body_refresh_source_mode="reference_assisted",
            body_model_context="similar_person_body_reference_assisted_v1",
        )


def test_doc245_body_refresh_candidate_receipt_separates_body_source_from_face_identity() -> None:
    active_card = _active_body_card()
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.refresh_body_silhouette(
        active_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_source_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )

    assert result.status == "review"
    assert generator.requests
    for request in generator.requests:
        assert request.source_class == "observed"
        assert request.body_refresh_source_mode == "reference_assisted"
        assert request.body_model_context == "similar_person_body_reference_assisted_v1"
        assert request.body_refresh_contract_required is True
        assert request.body_source_admission is not None
        assert request.body_source_admission.source_class == "observed"
        assert request.body_source_admission.body_evidence_ids == ["body_source_asset"]
        assert request.body_source_admission.body_reference_role == "body_proportion_reference"
        assert request.body_source_admission.body_reference_truth_layer == "body_proportion_truth"
        assert request.body_source_admission.face_reference_output_ids == [
            "face_front_output",
            "face_profile_output",
            "face_rear_output",
        ]
        assert "body_source_asset" not in request.reference_output_ids


def test_doc245_body_stage_metadata_rejects_non_body_owned_channel_injection() -> None:
    with pytest.raises(ValueError, match="body_stage_channel_not_owned"):
        CharacterCardCandidateRequest(
            project_id="visual_asset_body",
            people_asset_id="people_body",
            card_version_id="card_body_formal",
            module="body_silhouette",
            slot_key="body.rear_full",
            candidate_index=1,
            reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            user_intent="neutral body silhouette profile",
            source_class="observed",
            consent_provenance_id="consent_123",
            body_source_admission={
                "contract_version": "professional_body_source_admission_v1",
                "source_class": "observed",
                "body_evidence_ids": ["body_source_asset"],
                "body_reference_role": "body_proportion_reference",
                "body_reference_truth_layer": "body_proportion_truth",
                "face_reference_output_ids": [
                    "face_front_output",
                    "face_profile_output",
                    "face_rear_output",
                ],
                "body_owned_channels": ["body_proportion", "attire"],
            },
        )


def test_doc245_user_described_body_facts_cannot_certify_strict_refresh_or_enter_prompt_payload() -> None:
    raw_body_facts = (
        "raw_prompt: make the body taller; file_path=D:/unsafe/body.png; "
        "url=https://example.invalid/private; provider_payload={'secret': true}; asset_id=v3_asset_private"
    )
    active_card = _active_body_card()
    generator = _BodyGenerator()
    body_service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    host = _BodyStageHost(body_service)
    asset = SimpleNamespace(
        visual_asset_id="asset_body_no_leak",
        preparation_intent="scene-neutral Body Silhouette source refresh",
    )

    with pytest.raises(ValueError, match="body_silhouette_refresh_body_source_unavailable"):
        host.refresh_body_silhouette(
            asset=asset,
            card=active_card,
            request=BodySilhouettePublicRequest(
                source_class="user_described",
                body_facts=raw_body_facts,
            ),
        )

    assert generator.requests == []
    serialized_requests = str([request.model_dump(mode="json") for request in generator.requests])
    assert raw_body_facts not in serialized_requests
    for forbidden in (
        "raw_prompt",
        "D:/unsafe",
        "https://example.invalid",
        "provider_payload",
        "v3_asset_private",
    ):
        assert forbidden not in serialized_requests


def test_doc245_user_described_body_prepare_remains_non_certifying_legacy_provenance() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="user_described",
        user_intent="server-owned non-certifying body provenance direction",
    )

    assert result.status == "review"
    for request in generator.requests:
        assert request.user_intent == "server-owned non-certifying body provenance direction"
        assert request.body_source_admission is not None
        assert request.body_source_admission.source_class == "user_described"
        assert request.body_source_admission.body_evidence_ids == []
        assert request.body_source_admission.body_reference_role is None
        assert request.body_source_admission.body_reference_truth_layer is None


def test_doc245_product_api_body_source_ref_is_body_only_and_separate_from_face_refs(tmp_path) -> None:
    upload_store = V3UploadedAssetStore(tmp_path / "uploads")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(asset_store=upload_store, output_store=output_store)
    encoded = _tiny_png_b64()
    body_upload = service.create_uploaded_asset(
        {
            "filename": "body-source.png",
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(encoded)),
            "role": "body_proportion_reference",
        }
    )
    service.store_uploaded_asset_content(body_upload.asset_id, {"content_base64": encoded, "mime_type": "image/png"})
    service.complete_uploaded_asset(body_upload.asset_id)
    face_outputs = [
        output_store.save_base64_output(
            job_id=f"job_{name}",
            candidate_id=f"candidate_{name}",
            asset_id=f"asset_{name}",
            provider="test",
            model="test",
            encoded_image=encoded,
            mime_type="image/png",
        ).output_id
        for name in ("front", "profile", "rear")
    ]
    admission = {
        "contract_version": "professional_body_source_admission_v1",
        "source_class": "observed",
        "body_evidence_ids": [body_upload.asset_id],
        "body_reference_role": "body_proportion_reference",
        "body_reference_truth_layer": "body_proportion_truth",
        "face_reference_output_ids": face_outputs,
        "body_owned_channels": [
            "body_proportion",
            "body_scale",
            "neck_shoulder_transition",
            "torso_limb_proportion",
            "developmental_stage_coherence",
            "stance_ground_contact",
            "cross_view_body_parity",
        ],
    }

    refs = [
        *service._professional_character_card_reference_assets(  # noqa: SLF001
            service._professional_character_card_provider_reference_output_ids(  # noqa: SLF001
                stage="body_silhouette",
                slot_key="body.rear_full",
                reference_output_ids=face_outputs,
            )
        ),
        *service._professional_character_card_body_reference_assets(  # noqa: SLF001
            admission,
            source_class="observed",
            face_reference_output_ids=face_outputs,
        ),
    ]

    assert [ref["role"] for ref in refs].count("body_proportion_reference") == 1
    assert [ref["role"] for ref in refs].count("face_reference") == 2
    body_ref = next(ref for ref in refs if ref["role"] == "body_proportion_reference")
    assert body_ref["asset_id"] == body_upload.asset_id
    assert body_ref["metadata"]["reference_truth_layer"] == "body_proportion_truth"
    assert body_ref["metadata"]["body_reference_policy"] == (
        "body_scale_neck_shoulder_torso_limb_developmental_stage_only"
    )
    face_ref_payload = str([ref for ref in refs if ref["role"] == "face_reference"])
    assert body_upload.asset_id not in face_ref_payload
    serialized_refs = str(refs)
    for forbidden in (
        "raw_prompt",
        "provider_payload",
        "https://example.invalid",
        "D:/unsafe",
    ):
        assert forbidden not in serialized_refs


def test_doc245_public_metadata_cannot_forge_body_source_admission() -> None:
    for scenario_id in ("general_creative", "ecommerce_template", "photographer_template"):
        with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
            V3ProductApiService().create_job(
                {
                    "user_input": "ordinary public generation",
                    "scenario_selection": {"scenario_id": scenario_id},
                    "metadata": {
                        "professional_character_card_body_source_admission": {
                            "contract_version": "professional_body_source_admission_v1",
                            "source_class": "observed",
                        }
                    },
                }
            )


def test_doc245_public_metadata_cannot_forge_body_refresh_source_mode() -> None:
    for scenario_id in ("general_creative", "ecommerce_template", "photographer_template"):
        for metadata in (
            {
                "professional_character_card_body_refresh_source_mode": "reference_assisted",
                "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
            },
            {
                "professional_character_card_body_refresh_source_mode": "inference_first",
                "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
                "professional_character_card_body_refresh_contract_required": True,
                "professional_character_card_candidate_index": 2,
                "body_reference_asset_id": "D:/unsafe/body.png",
                "raw_body_facts": "raw_prompt provider_payload https://example.invalid",
            },
        ):
            with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
                V3ProductApiService().create_job(
                    {
                        "user_input": "ordinary public generation",
                        "scenario_selection": {"scenario_id": scenario_id},
                        "metadata": metadata,
                    }
                )


def test_doc245_product_api_body_stage_rejects_missing_or_forbidden_source_admission() -> None:
    service = V3ProductApiService()
    with pytest.raises(ValueError, match="professional_character_card_body_source_admission_required"):
        service.create_professional_character_card_stage_job(
            {
                "user_input": "body refresh",
                "scenario_selection": {"scenario_id": "general_creative"},
            },
            stage="body_silhouette",
            slot_key="body.front_full",
            reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            candidate_index=1,
            source_class="observed",
            body_refresh_source_mode="reference_assisted",
            body_model_context="similar_person_body_reference_assisted_v1",
        )

    with pytest.raises(ValueError, match="professional_character_card_body_source_admission_forbidden"):
        service.create_professional_character_card_stage_job(
            {
                "user_input": "body refresh",
                "scenario_selection": {"scenario_id": "general_creative"},
            },
            stage="body_silhouette",
            slot_key="body.front_full",
            reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            candidate_index=1,
            source_class="brain_inferred",
            body_refresh_source_mode="inference_first",
            body_model_context="system_inferred_body_model_scene_neutral_v1",
            body_refresh_contract_required=True,
            body_source_admission={
                "contract_version": "professional_body_source_admission_v1",
                "source_class": "observed",
                "body_evidence_ids": ["body_source_asset"],
                "body_reference_role": "body_proportion_reference",
                "body_reference_truth_layer": "body_proportion_truth",
                "face_reference_output_ids": [
                    "face_front_output",
                    "face_profile_output",
                    "face_rear_output",
                ],
                "body_owned_channels": [
                    "body_proportion",
                    "body_scale",
                    "neck_shoulder_transition",
                    "torso_limb_proportion",
                    "developmental_stage_coherence",
                    "stance_ground_contact",
                    "cross_view_body_parity",
                ],
            },
        )


def test_doc245_product_api_body_stage_inference_first_has_no_body_reference_or_truth(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(output_store=output_store)
    encoded = _tiny_png_b64()
    face_outputs = [
        output_store.save_base64_output(
            job_id=f"job_{name}",
            candidate_id=f"candidate_{name}",
            asset_id=f"asset_{name}",
            provider="test",
            model="test",
            encoded_image=encoded,
            mime_type="image/png",
        ).output_id
        for name in ("front", "profile", "rear")
    ]

    source_mode_contract = service._safe_professional_character_card_body_refresh_source_mode(  # noqa: SLF001
        "inference_first",
        body_model_context="system_inferred_body_model_scene_neutral_v1",
        contract_required=True,
        source_class="brain_inferred",
        body_source_admission=None,
    )

    metadata = {
        **source_mode_contract,
        "professional_anchor_reference_assets": service._professional_character_card_reference_assets(  # noqa: SLF001
            service._professional_character_card_provider_reference_output_ids(  # noqa: SLF001
                stage="body_silhouette",
                slot_key="body.side_full",
                reference_output_ids=face_outputs,
            )
        ),
    }
    assert metadata["professional_character_card_body_refresh_source_mode"] == "inference_first"
    assert metadata["professional_character_card_body_model_context"] == "system_inferred_body_model_scene_neutral_v1"
    assert "professional_character_card_body_source_admission" not in metadata
    refs = list(metadata["professional_anchor_reference_assets"])
    assert refs
    assert {ref["role"] for ref in refs} == {"face_reference"}
    serialized = str(metadata)
    assert "body_proportion_truth" not in serialized
    assert "body_proportion_reference" not in serialized
    for forbidden in ("raw_prompt", "provider_payload", "https://example.invalid", "D:/unsafe"):
        assert forbidden not in serialized


def test_doc245_product_api_ordinary_body_stage_keeps_legacy_brain_inferred_without_mode(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(output_store=output_store)
    encoded = _tiny_png_b64()
    face_outputs = [
        output_store.save_base64_output(
            job_id=f"job_legacy_{name}",
            candidate_id=f"candidate_legacy_{name}",
            asset_id=f"asset_legacy_{name}",
            provider="test",
            model="test",
            encoded_image=encoded,
            mime_type="image/png",
        ).output_id
        for name in ("front", "profile", "rear")
    ]

    source_mode_contract = service._safe_professional_character_card_body_refresh_source_mode(  # noqa: SLF001
        None,
        body_model_context=None,
        contract_required=False,
        source_class="brain_inferred",
        body_source_admission=None,
    )

    metadata = {
        **source_mode_contract,
        "professional_anchor_reference_assets": service._professional_character_card_reference_assets(  # noqa: SLF001
            service._professional_character_card_provider_reference_output_ids(  # noqa: SLF001
                stage="body_silhouette",
                slot_key="body.front_full",
                reference_output_ids=face_outputs,
            )
        ),
    }
    assert "professional_character_card_body_refresh_source_mode" not in metadata
    assert "professional_character_card_body_model_context" not in metadata
    assert "professional_character_card_body_source_admission" not in metadata
    assert {ref["role"] for ref in metadata["professional_anchor_reference_assets"]} == {"face_reference"}


def test_doc245_product_api_strict_refresh_missing_or_invalid_source_mode_blocks() -> None:
    service = V3ProductApiService()

    with pytest.raises(ValueError, match="professional_character_card_body_refresh_source_mode_invalid"):
        service._safe_professional_character_card_body_refresh_source_mode(  # noqa: SLF001
            None,
            body_model_context=None,
            contract_required=True,
            source_class="brain_inferred",
            body_source_admission=None,
        )

    with pytest.raises(ValueError, match="professional_character_card_body_refresh_source_mode_forbidden"):
        service._safe_professional_character_card_body_refresh_source_mode(  # noqa: SLF001
            None,
            body_model_context=None,
            contract_required=True,
            source_class="user_described",
            body_source_admission={
                "contract_version": "professional_body_source_admission_v1",
                "source_class": "user_described",
                "body_evidence_ids": [],
                "body_reference_role": None,
                "body_reference_truth_layer": None,
                "face_reference_output_ids": [
                    "face_front_output",
                    "face_profile_output",
                    "face_rear_output",
                ],
                "body_owned_channels": [
                    "body_proportion",
                    "body_scale",
                    "neck_shoulder_transition",
                    "torso_limb_proportion",
                    "developmental_stage_coherence",
                    "stance_ground_contact",
                    "cross_view_body_parity",
                ],
            },
        )


def test_doc245_product_api_body_refresh_contract_required_marker_is_strict_bool(tmp_path) -> None:
    service = V3ProductApiService()

    assert service._safe_professional_character_card_body_refresh_source_mode(  # noqa: SLF001
        None,
        body_model_context=None,
        contract_required=False,
        source_class="brain_inferred",
        body_source_admission=None,
    ) == {}

    for marker in (1, 0, "true", "false", None, [], {}):
        with pytest.raises(ValueError, match="professional_character_card_body_refresh_contract_required_invalid"):
            service._safe_professional_character_card_body_refresh_source_mode(  # noqa: SLF001
                "inference_first",
                body_model_context="system_inferred_body_model_scene_neutral_v1",
                contract_required=marker,
                source_class="brain_inferred",
                body_source_admission=None,
            )


def test_doc245_product_api_character_card_candidate_index_is_strict_server_owned_int() -> None:
    service = V3ProductApiService()

    assert service._safe_professional_character_card_candidate_index(1) == 1  # noqa: SLF001
    assert service._safe_professional_character_card_candidate_index(3) == 3  # noqa: SLF001
    for value in (0, 4, True, False, "1", "3", None, [], {}):
        with pytest.raises(ValueError, match="professional_character_card_candidate_index_invalid"):
            service._safe_professional_character_card_candidate_index(value)  # noqa: SLF001[arg-type]


def test_doc245_product_api_character_card_candidate_count_is_exact_formal_count() -> None:
    service = V3ProductApiService()

    assert service._safe_professional_character_card_candidate_count(3) == 3  # noqa: SLF001
    for value in (0, 1, 2, 4, True, False, "3", 3.0, None, [], {}):
        with pytest.raises(ValueError, match="professional_character_card_candidate_count_invalid"):
            service._safe_professional_character_card_candidate_count(value)  # noqa: SLF001[arg-type]


def test_doc245_public_metadata_cannot_forge_candidate_count_or_lifecycle_checkpoints() -> None:
    for metadata in (
        {"professional_character_card_candidate_count": 3},
        {
            "professional_character_card_candidate_lifecycle_checkpoints": [
                {
                    "contract": "character_card_candidate_lifecycle_checkpoint_v1",
                    "stage": "body_silhouette",
                    "slot_key": "body.front_full",
                    "candidate_index": 1,
                    "candidate_count": 3,
                    "lifecycle_phase": "generation",
                    "status": "completed",
                }
            ]
        },
    ):
        with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
            V3ProductApiService().create_job(
                {
                    "user_input": "ordinary public generation",
                    "scenario_selection": {"scenario_id": "general_creative"},
                    "metadata": metadata,
                }
            )


def test_doc245_product_api_candidate_lifecycle_checkpoint_durable_public_readback_no_leak(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(output_store=output_store)
    encoded = _tiny_png_b64()
    face_outputs = [
        output_store.save_base64_output(
            job_id=f"job_checkpoint_{name}",
            candidate_id=f"candidate_checkpoint_{name}",
            asset_id=f"asset_checkpoint_{name}",
            provider="test",
            model="test",
            encoded_image=encoded,
            mime_type="image/png",
        ).output_id
        for name in ("front", "profile", "rear")
    ]
    status = service.create_professional_character_card_stage_job(
        {
            "user_input": "body refresh",
            "scenario_selection": {"scenario_id": "general_creative"},
        },
        stage="body_silhouette",
        slot_key="body.front_full",
        reference_output_ids=face_outputs,
        candidate_index=1,
        candidate_count=3,
        source_class="brain_inferred",
        body_refresh_source_mode="inference_first",
        body_model_context="system_inferred_body_model_scene_neutral_v1",
        body_refresh_contract_required=True,
    )

    service.record_character_card_candidate_lifecycle_checkpoint(
        job_id=status.job_id,
        checkpoint={
            "contract": "character_card_candidate_lifecycle_checkpoint_v1",
            "stage": "body_silhouette",
            "slot_key": "body.front_full",
            "candidate_index": 1,
            "candidate_count": 3,
            "lifecycle_phase": "generation",
            "status": "completed",
        },
    )
    record = service.job_store.get(status.job_id)
    assert record is not None
    record.request.metadata["professional_character_card_candidate_lifecycle_checkpoints"].append(
        {
            "contract": "character_card_candidate_lifecycle_checkpoint_v1",
            "stage": "body_silhouette",
            "slot_key": "body.front_full",
            "candidate_index": 1,
            "candidate_count": 3,
            "lifecycle_phase": "review_extraction",
            "status": "blocked",
            "failure_family": "candidate_review",
            "failure_code": "candidate_review_extraction_unbound",
            "raw_prompt": "raw prompt must not leak",
            "source_url": "https://provider.invalid/private",
            "path": "C:\\private\\artifact.png",
            "provider_payload": {"secret": "do not persist"},
            "output_id": "v3_output_private",
        }
    )
    public = service.get_job(status.job_id)
    checkpoints = public.metadata["professional_character_card_candidate_lifecycle_checkpoints"]
    assert checkpoints == [
        {
            "contract": "character_card_candidate_lifecycle_checkpoint_v1",
            "stage": "body_silhouette",
            "slot_key": "body.front_full",
            "candidate_index": 1,
            "candidate_count": 3,
            "lifecycle_phase": "generation",
            "status": "completed",
            "failure_family": None,
            "failure_code": None,
        }
    ]
    serialized = public.model_dump_json()
    for forbidden in (
        "raw prompt",
        "https://provider.invalid",
        "C:\\private",
        "provider_payload",
        "v3_output_private",
    ):
        assert forbidden not in serialized


def test_doc245_character_card_stage_job_starts_with_empty_lifecycle_checkpoints(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(output_store=output_store)
    encoded = _tiny_png_b64()
    face_outputs = [
        output_store.save_base64_output(
            job_id=f"job_empty_checkpoint_{name}",
            candidate_id=f"candidate_empty_checkpoint_{name}",
            asset_id=f"asset_empty_checkpoint_{name}",
            provider="test",
            model="test",
            encoded_image=encoded,
            mime_type="image/png",
        ).output_id
        for name in ("front", "profile", "rear")
    ]

    status = service.create_professional_character_card_stage_job(
        {
            "user_input": "body refresh",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {
                "professional_character_card_candidate_lifecycle_checkpoints": [
                    {
                        "contract": "character_card_candidate_lifecycle_checkpoint_v1",
                        "stage": "body_silhouette",
                        "slot_key": "body.side_full",
                        "candidate_index": 3,
                        "candidate_count": 3,
                        "lifecycle_phase": "review_extraction",
                        "status": "blocked",
                        "failure_family": "candidate_review",
                        "failure_code": "candidate_review_extraction_unbound",
                    }
                ],
            },
        },
        stage="body_silhouette",
        slot_key="body.front_full",
        reference_output_ids=face_outputs,
        candidate_index=1,
        candidate_count=3,
        source_class="brain_inferred",
        body_refresh_source_mode="inference_first",
        body_model_context="system_inferred_body_model_scene_neutral_v1",
        body_refresh_contract_required=True,
    )

    record = service.job_store.get(status.job_id)
    assert record is not None
    assert record.request.metadata["professional_character_card_candidate_lifecycle_checkpoints"] == []
    assert record.request.metadata["professional_character_card_candidate_count"] == 3
    public = service.get_job(status.job_id)
    assert "professional_character_card_candidate_lifecycle_checkpoints" not in public.metadata

    service.record_character_card_candidate_lifecycle_checkpoint(
        job_id=status.job_id,
        checkpoint={
            "contract": "character_card_candidate_lifecycle_checkpoint_v1",
            "stage": "body_silhouette",
            "slot_key": "body.front_full",
            "candidate_index": 1,
            "candidate_count": 3,
            "lifecycle_phase": "generation",
            "status": "completed",
        },
    )
    public_after_checkpoint = service.get_job(status.job_id)
    checkpoints = public_after_checkpoint.metadata[
        "professional_character_card_candidate_lifecycle_checkpoints"
    ]
    assert len(checkpoints) == 1
    assert checkpoints[0]["slot_key"] == "body.front_full"
    assert checkpoints[0]["candidate_index"] == 1


def test_doc245_anchor_stage_plan_reuse_does_not_copy_character_card_lifecycle_checkpoints() -> None:
    source_metadata = {
        "professional_mode": True,
        "professional_anchor_pack_preparation": True,
        "professional_reference_stage": "standard_front",
        "professional_anchor_capture_scope": "anchor_pack",
        "professional_character_card_candidate_count": 3,
        "professional_character_card_candidate_lifecycle_checkpoints": [
            {
                "contract": "character_card_candidate_lifecycle_checkpoint_v1",
                "stage": "body_silhouette",
                "slot_key": "body.front_full",
                "candidate_index": 1,
                "candidate_count": 3,
                "lifecycle_phase": "generation",
                "status": "completed",
            }
        ],
        "professional_anchor_rendering_contract": "size:1024x1536|quality:strict|reference_card",
    }

    reusable = V3ProductApiService._reusable_server_owned_runtime_metadata(source_metadata)  # noqa: SLF001

    assert reusable["professional_mode"] is True
    assert reusable["professional_anchor_pack_preparation"] is True
    assert reusable["professional_reference_stage"] == "standard_front"
    assert "professional_character_card_candidate_count" not in reusable
    assert "professional_character_card_candidate_lifecycle_checkpoints" not in reusable


def _safe_provider_no_pixel_retry_summary() -> dict[str, object]:
    return {
        "executed_count": 0,
        "max_attempts": 2,
        "fresh_upstream_requests": 1,
        "final_status": "failed",
        "final_classification": "non_retryable_provider_failure",
        "final_failure_code": "image_edit_invalid_request_unattributed",
        "attempts": [
            {
                "attempt": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "image_edit_invalid_request_unattributed",
                "message": "OpenAI image reference generation failed. Error code: 400 - raw provider body",
                "retryable": False,
            }
        ],
        "reference_input_execution": {
            "schema_version": "v3_reference_input_execution_v1",
            "admission_outcome": "admitted",
            "operation_outcome": "failed",
            "operation": "image_edit",
            "reference_count": 2,
            "failure_code": "image_edit_invalid_request_unattributed",
            "safe_message": "The image-edit request was rejected before image pixels were returned.",
        },
        "execution_audit": {
            "gateway_managed_failover": False,
            "gateway_managed_failover_timeout_seconds": 660.0,
            "outer_timeout_seconds": 435.0,
            "outer_max_attempts": 2,
            "operation": "image_edit",
        },
    }


def test_doc245_anchor_maps_safe_provider_no_pixel_failure_without_raw_text() -> None:
    safe_retry = V3ProductApiService._public_provider_failure_retry(_safe_provider_no_pixel_retry_summary())  # noqa: SLF001
    status = SimpleNamespace(metadata={"provider_failure_retry": safe_retry})

    failure_code = ProductApiAnchorPackPreparationHost._candidate_failure_code_from_blocked_status(  # noqa: SLF001
        status
    )

    assert failure_code == "image_edit_invalid_request_unattributed"
    serialized = str(safe_retry)
    assert "raw provider body" not in serialized
    assert "OpenAI image reference generation failed" not in serialized


def test_doc245_product_api_public_warnings_sanitize_provider_error_text() -> None:
    raw_warning = (
        "V3 real image generation failed via openai_gpt_image (provider_error): "
        "OpenAI image reference generation failed. Error code: 400 - raw provider body"
    )

    warnings = V3ProductApiService._public_job_warnings(  # noqa: SLF001
        [raw_warning, "asset packaged with reject recommendation"],
        {"provider_failure_retry": _safe_provider_no_pixel_retry_summary()},
    )

    joined = "\n".join(warnings)
    assert "OpenAI image reference generation failed" not in joined
    assert "raw provider body" not in joined
    assert "image_edit_invalid_request_unattributed" in joined
    assert "asset packaged with reject recommendation" in warnings


def test_doc245_body_refresh_fail_closed_without_cross_view_positive_evidence() -> None:
    class _MissingCrossViewBodyReviewer(_BodyReviewer):
        def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
            return _review(candidate.candidate_index, include_cross_view_parity_evidence=False)

    active_card = _active_body_card()
    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_MissingCrossViewBodyReviewer(),
    )

    result = service.refresh_body_silhouette(
        active_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_source_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["body_silhouette_cross_view_parity_evidence_missing"]
    assert result.card.body_silhouette_status == "active"
    assert result.card.body_slots == active_card.body_slots
    assert result.card.body_silhouette_refresh_status == "blocked"
    blocked_revision = result.card.append_only_revision

    recovered = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_BodyReviewer(),
    ).refresh_body_silhouette(
        result.card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_source_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )

    assert recovered.status == "review"
    assert recovered.card.append_only_revision == blocked_revision + 1
    assert recovered.card.body_silhouette_refresh_status == "reviewing"
    assert recovered.card.body_slots == active_card.body_slots


def test_doc245_visual_asset_library_body_refresh_uses_explicit_lifecycle_entry() -> None:
    catalog = VisualAssetLibraryCatalog()
    created = catalog.create(
        owner_scope="owner",
        request=LibraryVisualAssetCreateRequest(
            display_name="Model",
            root_source_asset_id="root_source",
            consent_reference="consent",
            preparation_intent="scene-neutral body silhouette source refresh",
        ),
    )
    active_card = _active_body_card()
    asset = created.model_copy(
        update={
            "lifecycle_status": "active",
            "active_version_id": "version_1",
            "versions": [
                {
                    "version_id": "version_1",
                    "visual_asset_id": created.visual_asset_id,
                    "lifecycle_status": "active",
                    "approved_evidence_ids": ["face_front_output"],
                    "activation_confirmed": True,
                    "immutable_source_provenance": created.root_source_provenance,
                }
            ],
            "character_card": active_card,
        }
    )
    catalog.save(asset)
    generator = _BodyGenerator()
    body_service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    lifecycle = VisualAssetLibraryLifecycleService(
        catalog,
        root_source_resolver=lambda source_id: SimpleNamespace(
            status="ready",
            role="body_proportion_reference",
            metadata={
                "consent_reference": "consent_123",
                "reference_truth_layer": "body_proportion_truth",
            },
        )
        if source_id == "body_source_asset"
        else None,
        character_card_stage_host=_BodyStageHost(body_service),
    )

    refreshed = lifecycle.refresh_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=created.visual_asset_id,
        body_request=BodySilhouettePublicRequest(
            source_class="observed",
            body_reference_asset_id="body_source_asset",
        ),
    )

    assert len(generator.requests) == 9
    assert refreshed.character_card.body_slots == active_card.body_slots
    assert refreshed.character_card.body_silhouette_status == "active"
    assert refreshed.character_card.body_silhouette_refresh_status == "reviewing"
    assert set(refreshed.character_card.body_silhouette_refresh_slots) == set(BODY_SLOT_KEYS)
    reloaded = lifecycle.get(owner_scope="owner", visual_asset_id=created.visual_asset_id)
    assert reloaded.character_card.body_slots == active_card.body_slots
    assert reloaded.character_card.body_silhouette_refresh_status == "reviewing"

    pending_version = reloaded.character_card.body_silhouette_refresh_version_id
    pending_winners = {
        slot_key: slot.output_id
        for slot_key, slot in reloaded.character_card.body_silhouette_refresh_slots.items()
    }
    request_count = len(generator.requests)
    with pytest.raises(ValueError, match="character_card_body_refresh_pending"):
        lifecycle.refresh_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=created.visual_asset_id,
            body_request=BodySilhouettePublicRequest(
                source_class="observed",
                body_reference_asset_id="body_source_asset",
            ),
        )
    blocked_reloaded = lifecycle.get(owner_scope="owner", visual_asset_id=created.visual_asset_id)
    assert len(generator.requests) == request_count
    assert blocked_reloaded.character_card.body_silhouette_refresh_version_id == pending_version
    assert {
        slot_key: slot.output_id
        for slot_key, slot in blocked_reloaded.character_card.body_silhouette_refresh_slots.items()
    } == pending_winners
    assert blocked_reloaded.character_card.body_slots == active_card.body_slots


def test_doc245_visual_asset_library_body_refresh_inference_first_uses_no_body_truth() -> None:
    catalog = VisualAssetLibraryCatalog()
    created = catalog.create(
        owner_scope="owner",
        request=LibraryVisualAssetCreateRequest(
            display_name="Model",
            root_source_asset_id="root_source",
            consent_reference="consent",
            preparation_intent="scene-neutral body silhouette source refresh",
        ),
    )
    active_card = _active_body_card()
    asset = created.model_copy(
        update={
            "lifecycle_status": "active",
            "active_version_id": "version_1",
            "versions": [
                {
                    "version_id": "version_1",
                    "visual_asset_id": created.visual_asset_id,
                    "lifecycle_status": "active",
                    "approved_evidence_ids": ["face_front_output"],
                    "activation_confirmed": True,
                    "immutable_source_provenance": created.root_source_provenance,
                }
            ],
            "character_card": active_card,
        }
    )
    catalog.save(asset)
    generator = _BodyGenerator()
    body_service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    lifecycle = VisualAssetLibraryLifecycleService(
        catalog,
        root_source_resolver=lambda source_id: pytest.fail(f"unexpected body source resolver call: {source_id}"),
        character_card_stage_host=_BodyStageHost(body_service),
    )

    refreshed = lifecycle.refresh_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=created.visual_asset_id,
        body_request=BodySilhouettePublicRequest(source_class="brain_inferred"),
    )

    assert len(generator.requests) == 9
    assert refreshed.character_card.body_slots == active_card.body_slots
    assert refreshed.character_card.body_silhouette_status == "active"
    assert refreshed.character_card.body_silhouette_refresh_status == "reviewing"
    assert set(refreshed.character_card.body_silhouette_refresh_slots) == set(BODY_SLOT_KEYS)
    for request in generator.requests:
        assert request.body_refresh_source_mode == "inference_first"
        assert request.body_model_context == "system_inferred_body_model_scene_neutral_v1"
        assert request.body_refresh_contract_required is True
        assert request.body_source_admission is None
        serialized = str(request.model_dump(mode="json"))
        assert "body_proportion_truth" not in serialized
        assert "body_proportion_reference" not in serialized


def test_doc245_strict_body_refresh_requires_observed_body_proportion_truth_before_host() -> None:
    catalog = VisualAssetLibraryCatalog()
    created = catalog.create(
        owner_scope="owner",
        request=LibraryVisualAssetCreateRequest(
            display_name="Model",
            root_source_asset_id="root_source",
            consent_reference="consent",
            preparation_intent="scene-neutral body silhouette source refresh",
        ),
    )
    active_card = _active_body_card()
    catalog.save(
        created.model_copy(
            update={
                "lifecycle_status": "active",
                "active_version_id": "version_1",
                "versions": [
                    {
                        "version_id": "version_1",
                        "visual_asset_id": created.visual_asset_id,
                        "lifecycle_status": "active",
                        "approved_evidence_ids": ["face_front_output"],
                        "activation_confirmed": True,
                        "immutable_source_provenance": created.root_source_provenance,
                    }
                ],
                "character_card": active_card,
            }
        )
    )
    generator = _BodyGenerator()
    body_service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    invalid_sources = {
        "legacy_full_body_asset": SimpleNamespace(
            status="ready",
            role="full_body_reference",
            metadata={
                "consent_reference": "consent_123",
                "reference_truth_layer": "body_proportion_truth",
            },
        ),
        "missing_truth_layer_asset": SimpleNamespace(
            status="ready",
            role="body_proportion_reference",
            metadata={"consent_reference": "consent_123"},
        ),
    }
    lifecycle = VisualAssetLibraryLifecycleService(
        catalog,
        root_source_resolver=lambda source_id: invalid_sources.get(source_id),
        character_card_stage_host=_BodyStageHost(body_service),
    )

    with pytest.raises(ValueError, match="character_card_body_reference_role_invalid"):
        lifecycle.refresh_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=created.visual_asset_id,
            body_request=BodySilhouettePublicRequest(
                source_class="observed",
                body_reference_asset_id="legacy_full_body_asset",
            ),
        )
    with pytest.raises(ValueError, match="character_card_body_reference_truth_layer_invalid"):
        lifecycle.refresh_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=created.visual_asset_id,
            body_request=BodySilhouettePublicRequest(
                source_class="observed",
                body_reference_asset_id="missing_truth_layer_asset",
            ),
        )

    assert generator.requests == []
    reloaded = lifecycle.get(owner_scope="owner", visual_asset_id=created.visual_asset_id)
    assert reloaded.character_card.body_slots == active_card.body_slots
    assert reloaded.character_card.body_silhouette_refresh_slots == {}
    assert reloaded.character_card.body_silhouette_refresh_status == "empty"


def test_doc245_visual_asset_library_body_refresh_requires_explicit_shared_host() -> None:
    catalog = VisualAssetLibraryCatalog()
    created = catalog.create(
        owner_scope="owner",
        request=LibraryVisualAssetCreateRequest(
            display_name="Model",
            root_source_asset_id="root_source",
            consent_reference="consent",
            preparation_intent="scene-neutral body silhouette source refresh",
        ),
    )
    catalog.save(created.model_copy(update={"character_card": _active_body_card()}))
    lifecycle = VisualAssetLibraryLifecycleService(catalog)

    with pytest.raises(Exception, match="character_card_body_refresh_unavailable"):
        lifecycle.refresh_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=created.visual_asset_id,
            body_request=BodySilhouettePublicRequest(source_class="brain_inferred"),
        )


def test_doc245_body_source_class_and_consent_contract_still_apply() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())

    with pytest.raises(ValueError, match="consent"):
        service.prepare_body_silhouette(
            _card_ready_for_body(),
            face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            source_class="observed",
            body_evidence_ids=["body_reference_asset"],
            user_intent="observed body silhouette profile",
        )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_reference_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )
    assert result.card.body_slots["body.front_full"].source_class == "observed"
    assert result.card.body_slots["body.front_full"].consent_provenance_id == "consent_123"


def test_doc245_body_formal_receipt_becomes_public_safe_only_after_projection_verification() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())
    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    shared_runtime = CharacterCardSharedRuntimeReceipt(
        reviewed_candidate_count=3,
        acceptance_mode="standard_three_candidate",
        final_winner_selection_verified=True,
        prompt_reference_parity_verified=True,
        shared_review_receipts=[_generic_body_shared_receipt()],
    )
    attached = result.model_copy(update={"shared_runtime_receipt": shared_runtime})

    persisted = VisualAssetLibraryLifecycleService._persist_character_card_success_receipts(
        attached,
        stage="body_silhouette",
    )
    slot = persisted.body_slots["body.front_full"]

    assert slot.formal_slot_receipt is not None
    assert slot.formal_slot_receipt.reload_public_projection_verified is False
    assert slot.formal_slot_receipt.activation_eligible is False
    with pytest.raises(ValueError, match="standard_three_candidate"):
        character_card_formal_slot_receipt_public_summary(slot)

    verified = VisualAssetLibraryLifecycleService._mark_formal_receipts_after_projection(
        persisted,
        stage="body_silhouette",
    )
    verified_slot = verified.body_slots["body.front_full"]
    summary = character_card_formal_slot_receipt_public_summary(verified_slot)
    assert summary is not None
    assert summary["activation_eligible"] is True
    assert summary["acceptance_mode"] == "standard_three_candidate"
    assert summary["reviewed_candidate_count"] == 3


def test_doc245_body_set_carries_existing_formal_receipts_during_partial_resume() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    base_card = _card_ready_for_body()
    existing_result = service.prepare_body_silhouette(
        base_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    existing_front = existing_result.card.body_slots["body.front_full"]
    assert existing_front.formal_slot_receipt is not None
    legacy_front = existing_front.model_copy(
        update={
            "formal_slot_receipt": _legacy_body_formal_receipt_without_source_standard(
                existing_front.formal_slot_receipt
            )
        }
    )
    card_with_existing_front = base_card.model_copy(
        update={
            "body_silhouette_status": "reviewing",
            "body_slots": {
                **base_card.body_slots,
                "body.front_full": legacy_front,
            },
        }
    )

    generator.requests.clear()
    result = service.prepare_body_silhouette(
        card_with_existing_front,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "review"
    assert result.winner_output_ids["body.front_full"] == legacy_front.output_id
    assert "body.front_full" in result.formal_slot_receipts
    assert result.formal_slot_receipts["body.front_full"].winner_output_id == legacy_front.output_id
    assert not any(
        "source_standard" in code
        for candidate in result.formal_slot_receipts["body.front_full"].candidates
        if candidate.enhanced_proof is not None
        for code in candidate.enhanced_proof.evidence_codes
    )
    assert [request.slot_key for request in generator.requests] == [
        "body.side_full",
        "body.side_full",
        "body.side_full",
        "body.rear_full",
        "body.rear_full",
        "body.rear_full",
    ]


def test_doc245_legacy_body_formal_receipt_survives_persisted_public_readback_without_recompute() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())
    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    front = result.card.body_slots["body.front_full"]
    assert front.formal_slot_receipt is not None
    legacy_front = front.model_copy(
        update={
            "formal_slot_receipt": _legacy_body_formal_receipt_without_source_standard(
                front.formal_slot_receipt
            )
        }
    )
    serialized = legacy_front.model_dump(mode="json")

    reloaded_slot = CharacterCardSlot.model_validate(serialized)
    assert reloaded_slot.formal_slot_receipt is not None
    assert reloaded_slot.formal_slot_receipt.reload_public_projection_verified is False
    verified_slot = reloaded_slot.model_copy(
        update={
            "formal_slot_receipt": mark_formal_slot_receipt_reload_public_projection_verified(
                reloaded_slot.formal_slot_receipt
            )
        }
    )
    summary = character_card_formal_slot_receipt_public_summary(verified_slot)

    assert summary is not None
    assert summary["module"] == "body_silhouette"
    assert summary["slot_key"] == "body.front_full"
    assert summary["winner_output_id"] == legacy_front.output_id
    evidence_codes = {
        code
        for candidate in reloaded_slot.formal_slot_receipt.candidates
        if candidate.enhanced_proof is not None
        for code in candidate.enhanced_proof.evidence_codes
    }
    assert "body_silhouette_source_standard_verified" not in evidence_codes


def test_doc245_body_provider_reference_subset_keeps_side_profile_authority() -> None:
    refs = ["face_front_winner", "face_profile_90_winner", "face_rear_winner"]

    assert V3ProductApiService._professional_character_card_provider_reference_output_ids(
        stage="body_silhouette",
        slot_key="body.front_full",
        reference_output_ids=refs,
    ) == ["face_front_winner", "face_rear_winner"]
    assert V3ProductApiService._professional_character_card_provider_reference_output_ids(
        stage="body_silhouette",
        slot_key="body.side_full",
        reference_output_ids=refs,
    ) == ["face_profile_90_winner", "face_front_winner"]
    assert V3ProductApiService._professional_character_card_provider_reference_output_ids(
        stage="body_silhouette",
        slot_key="body.rear_full",
        reference_output_ids=refs,
    ) == ["face_rear_winner", "face_profile_90_winner"]


def test_doc245_body_provider_reference_subset_rejects_invalid_body_chain() -> None:
    with pytest.raises(ValueError, match="professional_character_card_reference_chain_invalid"):
        V3ProductApiService._professional_character_card_provider_reference_output_ids(
            stage="body_silhouette",
            slot_key="body.side_full",
            reference_output_ids=["face_front_winner", "face_profile_90_winner"],
        )

    with pytest.raises(ValueError, match="professional_character_card_slot_invalid"):
        V3ProductApiService._professional_character_card_provider_reference_output_ids(
            stage="body_silhouette",
            slot_key="body.unknown",
            reference_output_ids=["face_front_winner", "face_profile_90_winner", "face_rear_winner"],
        )
