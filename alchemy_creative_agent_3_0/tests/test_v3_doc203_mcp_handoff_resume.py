from __future__ import annotations

import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRouter,
    McpMaterializationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationHandoffStore,
    build_body_renderer_execution_receipt,
)
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import ProductApiAnchorPackPreparationHost
from alchemy_creative_agent_3_0.app.product_api.contracts import (
    CreateCreativeJobRequest,
    ProductJobStatus,
    ProductJobStatusValue,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import (
    PersistentProductJobStore,
    ProductJobRecord,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    expression_front_card_framing_materialization_directive,
    laugh_expression_materialization_directive,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    VisualInspectionReport,
)
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    BrandProfile,
    CommercialAssetPack,
    CommercialBrief,
    ConditionPlan,
    CreativeJob,
    CreativePlan,
    GenerationPlan,
    IndustryCategory,
    LayoutPlan,
    LayoutRegion,
    PackagedAsset,
    Platform,
    PlanningResult,
    PromptCompilationResult,
    ProviderStrategy,
    SeriesPlan,
    TextRenderingMode,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateUnavailable,
    AnchorGenerationRequest,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardCandidateRequest,
    CharacterCardPreparationService,
    CharacterCardState,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from app.providers.base import ProviderRuntimeError


def _doc203_body_frozen_contract_fields() -> dict[str, object]:
    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_integrated_whole_person_synthesis_contract,
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
        default_body_silhouette_backdrop_presentation_contract,
        default_body_silhouette_garment_continuity_contract,
        default_body_silhouette_hair_continuity_contract,
    )

    return {
        "body_refresh_source_mode": "inference_first",
        "body_silhouette_mcp_materialization_channel_contract": (
            body_silhouette_mcp_materialization_channel_contract()
        ),
        "body_silhouette_integrated_whole_person_synthesis_contract": (
            body_silhouette_integrated_whole_person_synthesis_contract()
        ),
        "body_refresh_presentation_intent": (
            default_body_refresh_presentation_intent().model_dump(mode="json")
        ),
        "body_silhouette_garment_continuity_contract": (
            default_body_silhouette_garment_continuity_contract()
        ),
        "body_silhouette_hair_continuity_contract": (
            default_body_silhouette_hair_continuity_contract()
        ),
        "body_silhouette_backdrop_presentation_contract": (
            default_body_silhouette_backdrop_presentation_contract()
        ),
    }


class _LocalBrainProvider:
    provider = "doc203_mcp_resume_test_brain"
    model = "contract-fixture-v1"

    def __init__(self) -> None:
        self.requests: list[dict] = []

    def available(self, *, force: bool = False) -> bool:
        return True

    def run(self, request) -> dict:  # noqa: ANN001
        self.requests.append(request.model_dump(mode="json"))
        payload = build_fallback_result(request).model_dump(mode="json")
        count = request.requested_image_count
        payload["image_set_plan"] = {
            "set_goal": "Test-only MCP handoff resume plan",
            "image_count": count,
            "size": request.requested_image_size,
            "shot_plan": [
                f"Complete renderer direction for output {index} while preserving the submitted MCP handoff contract."
                for index in range(1, count + 1)
            ],
            "composition_rules": ["Preserve the frozen renderer and reference contract."],
            "quality_bar": ["Do not replace an explicit MCP handoff with a local fallback."],
        }
        payload["visual_task_profile"] = {
            "profile_id": f"profile_{request.job_id or 'doc203'}",
            "project_id": request.project_id,
            "job_id": request.job_id or "job_doc203",
            "template_id": request.template_id or "general_template",
            "scenario_id": request.scenario_id or "general_creative",
            "output_medium": "image",
            "rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
                "evidence_ids": ["test_fixture_remote_rendering_intent"],
            },
            "developmental_age_intent": "not_applicable",
            "reference_channel_ownership_intent": {
                "applicability": "not_applicable",
                "decision_owner": "remote_brain",
                "reference_owned_channels": [],
                "current_request_owned_channels": [],
                "evidence_ids": ["test_fixture_no_reference_ownership"],
                "confidence": 0.99,
            },
            "subject_entities": [],
            "visual_intent_tags": ["mcp_handoff_resume"],
            "unknown_requirements": [],
            "confidence": 0.99,
            "evidence": [],
        }
        payload["canonical_provider_prompts"] = [
            {
                "output_index": index,
                "prompt": (
                    "Complete approved renderer prompt for the requested MCP materialization path, "
                    "preserving the submitted handoff identity and reference contract."
                ),
                "review_status": "approved",
                "semantic_preflight_status": "approved",
                "human_naturalness_decision": {
                    "contract_version": "v3_human_naturalness_decision_v1",
                    "status": "approved",
                    "owner": "remote_v3_llm_brain",
                },
                "human_developmental_presence_decision": {
                    "contract_version": "v3_human_developmental_presence_decision_v2",
                    "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                    "resolution_mode": "holistic_person_and_situation_resolution",
                    "status": "approved",
                    "owner": "remote_v3_llm_brain",
                },
            }
            for index in range(1, count + 1)
        ]
        return payload


def _png_bytes(color: tuple[int, int, int] = (224, 236, 255)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 48), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _renderer_submit_hashes(store: McpMaterializationHandoffStore, handoff: dict) -> dict[str, object]:
    payload = McpMaterializationHandoffStore.get(store, handoff["handoff_id"])
    assert payload is not None
    public = McpMaterializationHandoffStore._public_view_from_payload(payload)  # noqa: SLF001
    request = McpMaterializationHandoffStore._renderer_request_from_public_view(public)  # noqa: SLF001
    values: dict[str, object] = {
        "renderer_prompt_sha256": request["renderer_prompt_sha256"],
        "renderer_execution_directive_sha256": request["renderer_execution_directive_sha256"],
    }
    if isinstance(request.get("renderer_execution_directive"), dict):
        values["renderer_execution_receipt"] = build_body_renderer_execution_receipt(
            renderer_prompt_sha256=request["renderer_prompt_sha256"],
            renderer_execution_directive_sha256=request["renderer_execution_directive_sha256"],
            canonical_prompt_sha256=request["canonical_prompt_sha256"],
            rendering_contract_fingerprint=request["rendering_contract_fingerprint"],
            nonce_sha256=request["renderer_execution_directive"]["nonce_sha256"],
            reference_asset_hashes=request["reference_asset_hashes"],
        )
    return values


def _current_laugh_handoff_prompt(*, suffix: str = "") -> str:
    return (
        f"{laugh_expression_materialization_directive()} "
        f"{expression_front_card_framing_materialization_directive()} "
        f"{suffix}"
    ).strip()


def _current_expression_reference_assets() -> list[dict]:
    return [
        {
            "asset_id": "front_winner",
            "derivative_kind": "character_card_full_frame_framing_reference",
            "identity_evidence_scope": "card_framing",
            "sha256": "1" * 64,
        },
        {
            "asset_id": "front_winner::portrait_identity_crop",
            "derivative_kind": "portrait_identity_crop",
            "sha256": "2" * 64,
        },
        {
            "asset_id": "front_winner::portrait_identity_geometry_crop",
            "derivative_kind": "portrait_identity_pose_geometry_crop",
            "sha256": "3" * 64,
        },
    ]


def _laugh_pass_score_card() -> dict[str, float]:
    return {
        "same_person_readability": 0.94,
        "identity_consistency": 0.93,
        "distinctive_feature_readability": 0.91,
        "human_realism": 0.92,
        "visual_quality": 0.93,
        "pose_compliance": 0.90,
        "overall": 0.94,
        "mouth_eye_coherence": 0.90,
        "gaze_engagement": 0.89,
        "periocular_affect": 0.88,
        "cheek_jaw_coupling": 0.90,
        "jaw_relaxation": 0.85,
        "arousal_intensity_coherence": 0.88,
        "spontaneity_asymmetry": 0.78,
        "expression_age_coherence": 0.91,
        "expression_identity_preservation": 0.88,
        "expression_framing_parity": 0.93,
        "face_area_delta_from_front": 0.03,
        "top_margin_delta_from_front": 0.02,
        "bottom_margin_delta_from_front": 0.02,
        "eye_line_delta_from_front": 0.02,
        "center_x_delta_from_front": 0.02,
        "shoulder_span_delta_from_front": 0.04,
        "head_yaw_delta_from_front": 0.02,
        "head_pitch_delta_from_front": 0.02,
    }


def _provider_timeout_review_package(
    *,
    job_id: str,
    output_id: str,
    candidate_id: str,
) -> dict[str, object]:
    return {
        "package_id": f"review_timeout_{job_id}",
        "job_id": job_id,
        "inspections": [
            {
                "inspection_id": f"inspection_timeout_{job_id}",
                "job_id": job_id,
                "candidate_id": candidate_id,
                "output_id": output_id,
                "mode": "hybrid",
                "status": "manual_review",
                "verification_state": "unverified",
                "confidence": 0.35,
                "score_card": {
                    "same_person_readability": 0.94,
                    "identity_consistency": 0.93,
                    "overall": 0.5,
                },
                "detected_issues": [
                    {
                        "code": "provider_timeout",
                        "severity": "low",
                        "retryable": False,
                        "confidence": 0.4,
                    }
                ],
                "issue_codes": ["provider_timeout"],
                "evidence": {
                    "provider_error": "Vision inspection timed out after 90.00 seconds.",
                    "provider_timeout_seconds": 90.0,
                },
            }
        ],
        "metadata": {"post_generation": True, "inspection_count": 1},
    }


def _provider_unavailable_signal_review_package(
    *,
    job_id: str,
    output_id: str,
    candidate_id: str,
) -> dict[str, object]:
    return {
        "package_id": f"review_unavailable_{job_id}",
        "job_id": job_id,
        "resolutions": [],
        "inspections": [
            {
                "inspection_id": f"inspection_unavailable_{job_id}",
                "job_id": job_id,
                "candidate_id": candidate_id,
                "output_id": output_id,
                "mode": "hybrid",
                "status": "manual_review",
                "verification_state": "unverified",
                "confidence": 0.35,
                "score_card": {
                    "same_person_readability": 0.94,
                    "identity_consistency": 0.93,
                    "overall": 0.5,
                },
                "detected_issues": [],
                "issue_codes": [],
                "evidence": {},
            }
        ],
        "real_review_signal_package": {
            "package_id": f"real_review_signal_{job_id}",
            "job_id": job_id,
            "candidate_signals": [
                {
                    "candidate_id": candidate_id,
                    "output_id": output_id,
                    "status": "manual_review",
                    "issue_codes": ["vision_provider_unavailable"],
                    "observed_review_evidence": [
                        "This image needs manual confirmation before automatic retry."
                    ],
                }
            ],
        },
        "metadata": {"post_generation": True, "inspection_count": 1},
    }


def _attach_output_checkpoint(
    result: PlanningResult,
    *,
    output_id: str,
    candidate_id: str,
    handoff_id: str = "mcp_handoff_doc228_timeout",
    provider_prompt_sha256: str = "sha256:doc228",
    prompt_compilation_id: str = "prompt_doc228",
) -> PlanningResult:
    packaged = result.asset_pack.assets[0]
    candidate_metadata = {
        "output_id": output_id,
        "candidate_id": candidate_id,
        "provider_prompt_sha256": provider_prompt_sha256,
        "prompt_compilation_id": prompt_compilation_id,
        "provider_reference_image_count": 2,
        "prompt_reference_parity": {
            "verified": True,
            "expected_reference_count": 2,
            "actual_reference_count": 2,
        },
        "reference_evidence_parity": {
            "verified": True,
            "expected_reference_count": 2,
            "actual_reference_count": 2,
        },
        "mcp_materialization": {
            "handoff_id": handoff_id,
            "status": "job_checkpointed",
            "generation_channel": "mcp",
            "expected_checkpoint": {
                "job_id": result.creative_job.job_id,
                "candidate_id": candidate_id,
                "output_id": output_id,
            },
        },
    }
    updated_packaged = packaged.model_copy(
        update={
            "metadata": {
                **dict(packaged.metadata or {}),
                "selected_candidate_id": candidate_id,
                "output_id": output_id,
                "candidate_metadata": candidate_metadata,
            }
        }
    )
    asset_pack = result.asset_pack.model_copy(update={"assets": [updated_packaged], "planning_only": False})
    return result.model_copy(update={"asset_pack": asset_pack})


def _with_review_package(result: PlanningResult, package: dict[str, object]) -> PlanningResult:
    metadata = dict(result.metadata or {})
    visual_cluster = dict(metadata.get("visual_cluster") or {})
    shared_capabilities = dict(metadata.get("shared_capabilities") or {})
    shared_visual_cluster = dict(shared_capabilities.get("visual_cluster") or {})
    visual_cluster["post_generation_review_package"] = package
    visual_cluster["has_post_generation_review"] = True
    shared_visual_cluster["post_generation_review_package"] = package
    shared_visual_cluster["has_post_generation_review"] = True
    shared_capabilities["visual_cluster"] = shared_visual_cluster
    metadata.update(
        {
            "post_generation_review_package": package,
            "visual_cluster": visual_cluster,
            "shared_capabilities": shared_capabilities,
        }
    )
    asset_pack = result.asset_pack.model_copy(
        update={
            "manifest": {
                **dict(result.asset_pack.manifest or {}),
                "post_generation_review_package": package,
            },
            "metadata": {
                **dict(result.asset_pack.metadata or {}),
                "post_generation_review_package": package,
            },
        }
    )
    return result.model_copy(update={"metadata": metadata, "asset_pack": asset_pack})


def _doc228_generated_timeout_record(
    *,
    job_id: str,
    output_id: str,
    candidate_id: str,
    operation_id: str = "people_doc228:expression_set:expression.laugh:2:round5",
    handoff_id: str = "mcp_handoff_doc228_timeout",
    request_handoff_status: str = "pending",
) -> tuple[PlanningResult, ProductJobRecord, dict[str, object]]:
    timeout_package = _provider_timeout_review_package(
        job_id=job_id,
        output_id=output_id,
        candidate_id=candidate_id,
    )
    result = _with_review_package(
        _attach_output_checkpoint(
            _minimal_planning_result(
                job_id,
                generation_metadata=_current_character_card_planning_metadata(
                    operation_id=operation_id,
                    handoff={
                        "handoff_id": handoff_id,
                        "status": "job_checkpointed",
                        "generation_channel": "mcp",
                    },
                ),
            ),
            output_id=output_id,
            candidate_id=candidate_id,
            handoff_id=handoff_id,
        ),
        timeout_package,
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="positive expression keyframe",
            metadata={
                "project_id": "project_doc228",
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": handoff_id,
                    "status": request_handoff_status,
                    "generation_channel": "mcp",
                    "resume_required": True,
                },
            },
        ),
        status=ProductJobStatusValue.GENERATED,
        job_id_value=job_id,
        planning_result=result,
        generation_result=result,
    )
    return result, record, timeout_package


def _stale_crop_first_expression_reference_assets() -> list[dict]:
    return [
        {
            "asset_id": "front_winner::portrait_identity_crop",
            "derivative_kind": "portrait_identity_crop",
            "sha256": "2" * 64,
        },
        {
            "asset_id": "front_winner::portrait_identity_geometry_crop",
            "derivative_kind": "portrait_identity_pose_geometry_crop",
            "sha256": "3" * 64,
        },
        {"asset_id": "front_winner", "derivative_kind": "portrait_identity", "sha256": "1" * 64},
    ]


def _request_metadata(
    *,
    operation_id: str = "doc203-operation",
    materialization: dict | None = None,
) -> dict:
    metadata = {
        "mock_profile": "balanced",
        "requested_image_size": "1024x1536",
        "generation_channel": "mcp",
        "mcp_operation_id": operation_id,
        "llm_brain": {
            "llm_used": True,
            "fallback_used": False,
            "canonical_provider_prompts": [
                {
                    "output_index": 1,
                    "prompt": "same character card portrait, clean reference-card framing",
                    "review_status": "approved",
                }
            ],
            "audit": {
                "remote_canonical_provider_prompts_received": True,
                "canonical_provider_prompt_stage": "provider_prompt_finalize",
            },
        },
    }
    if materialization is not None:
        metadata["mcp_materialization"] = materialization
    return metadata


def _minimal_request(*, metadata: dict | None = None):
    asset = AssetSpec(
        asset_id="asset_doc203",
        asset_type=AssetType.MAIN_POSTER,
        platform=Platform.XIAOHONGSHU,
        aspect_ratio="2:3",
        purpose="character card validation image",
    )
    layout = LayoutPlan(
        layout_plan_id="layout_doc203",
        asset_id=asset.asset_id,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        text_rendering=TextRenderingMode.NO_TEXT,
        visual_hierarchy=["subject"],
        product_area=LayoutRegion(name="subject_area", position="center"),
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc203",
        asset_id=asset.asset_id,
        visual_prompt="same character card portrait",
        negative_prompt="no watermark",
        text_policy="no_text",
        style_notes=[],
        layout_notes=[],
        provider_notes={},
    )
    condition = ConditionPlan(condition_plan_id="condition_doc203", asset_id=asset.asset_id)
    generation = GenerationPlan(
        generation_plan_id="generation_doc203",
        asset_id=asset.asset_id,
        provider_strategy=ProviderStrategy.MCP_MATERIALIZATION,
        candidate_count=1,
        max_refine_rounds=0,
        metadata=metadata or _request_metadata(),
    )
    return build_provider_generation_request(
        asset_spec=asset,
        layout_plan=layout,
        prompt_compilation=prompt,
        condition_plan=condition,
        generation_plan=generation,
        job_id="job_doc203",
    )


def _current_character_card_planning_metadata(
    *,
    operation_id: str,
    refs: list[str] | None = None,
    stage: str = "expression_set",
    slot_key: str = "expression.laugh",
    attempt_round: int = 5,
    handoff: dict | None = None,
) -> dict:
    reference_ids = [str(item).strip() for item in (refs or ["front_winner"]) if str(item).strip()]
    metadata = {
        "professional_character_card_preparation": True,
        "professional_character_card_stage": stage,
        "professional_character_card_slot": slot_key,
        "professional_character_card_source_class": None,
        "professional_character_card_attempt_round": attempt_round,
        "professional_character_card_reference_output_ids": reference_ids,
        "professional_identity_reference_strategy": "character_card_shared_identity_v1",
        "professional_reference_stage": f"character_card_{stage}",
        "generation_channel": "mcp",
        "mcp_operation_id": operation_id,
        "professional_anchor_reference_assets": _current_expression_reference_assets(),
        "professional_planning_metadata": {
            "scope": f"character_card_{stage}",
            "slot_key": slot_key,
        },
    }
    if handoff is not None:
        metadata["mcp_materialization"] = handoff
    if stage == "body_silhouette":
        stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
            stage=stage,
            slot_key=slot_key,
        )
        metadata["professional_body_silhouette_source_contract"] = stage_metadata[
            "professional_body_silhouette_source_contract"
        ]
    return metadata


def _minimal_planning_result(
    job_id: str,
    *,
    asset_id: str = "asset_doc223c",
    generation_metadata: dict | None = None,
) -> PlanningResult:
    asset = AssetSpec(
        asset_id=asset_id,
        asset_type=AssetType.MAIN_POSTER,
        platform=Platform.XIAOHONGSHU,
        aspect_ratio="2:3",
        purpose="durable MCP resume checkpoint",
    )
    layout = LayoutPlan(
        layout_plan_id=f"layout_{job_id}",
        asset_id=asset.asset_id,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        text_rendering=TextRenderingMode.NO_TEXT,
        visual_hierarchy=["subject"],
        product_area=LayoutRegion(name="subject_area", position="center"),
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id=f"prompt_{job_id}",
        asset_id=asset.asset_id,
        visual_prompt="same character card portrait",
        negative_prompt="no watermark",
        text_policy="no_text",
    )
    condition = ConditionPlan(condition_plan_id=f"condition_{job_id}", asset_id=asset.asset_id)
    generation = GenerationPlan(
        generation_plan_id=f"generation_{job_id}",
        asset_id=asset.asset_id,
        provider_strategy=ProviderStrategy.MCP_MATERIALIZATION,
        candidate_count=1,
        max_refine_rounds=0,
        metadata=generation_metadata or {},
    )
    packaged = PackagedAsset(
        asset_id=asset.asset_id,
        asset_type=asset.asset_type,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        purpose=asset.purpose,
        layout_plan_id=layout.layout_plan_id,
        prompt_compilation_id=prompt.prompt_compilation_id,
        metadata={},
    )
    return PlanningResult(
        planning_result_id=f"planning_{job_id}",
        creative_job=CreativeJob(job_id=job_id, raw_user_input="durable MCP resume checkpoint"),
        commercial_brief=CommercialBrief(
            brief_id=f"brief_{job_id}",
            job_id=job_id,
            industry=IndustryCategory.UNKNOWN,
            scenario="checkpoint",
            business_goal="checkpoint",
            target_platforms=[Platform.XIAOHONGSHU],
        ),
        brand_profile=BrandProfile(brand_id=f"brand_{job_id}"),
        creative_plan=CreativePlan(
            creative_plan_id=f"plan_{job_id}",
            job_id=job_id,
            brief_id=f"brief_{job_id}",
            concept="checkpoint",
            visual_direction="checkpoint",
            composition_strategy="single subject",
        ),
        series_plan=SeriesPlan(series_plan_id=f"series_{job_id}", job_id=job_id, assets=[asset]),
        layout_plans=[layout],
        prompt_compilations=[prompt],
        condition_plans=[condition],
        generation_plans=[generation],
        evaluation_reports=[],
        asset_pack=CommercialAssetPack(
            asset_pack_id=f"asset_pack_{job_id}",
            job_id=job_id,
            assets=[packaged],
            planning_only=False,
        ),
        metadata={},
    )


def _save_doc223c_noise_jobs(store: PersistentProductJobStore, count: int) -> None:
    for index in range(count):
        job_id = f"job_doc223c_noise_{index:03d}"
        store.save(
            ProductJobRecord(
                request=CreateCreativeJobRequest(
                    user_input="noise",
                    metadata={
                        "generation_channel": "mcp",
                        "mcp_operation_id": f"doc223c-noise-{index}",
                    },
                ),
                status=ProductJobStatusValue.GENERATING,
                job_id_value=job_id,
            )
        )


def _character_card_doc223c_request(
    *,
    operation_id: str,
    handoff_id: str | None = None,
) -> CharacterCardCandidateRequest:
    return CharacterCardCandidateRequest(
        project_id="project_doc223c",
        people_asset_id="people_doc223c",
        card_version_id="card_doc223c",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=handoff_id,
    )


def _anchor_doc223c_request(*, operation_id: str, handoff_id: str) -> AnchorGenerationRequest:
    return AnchorGenerationRequest(
        project_id="project_doc223c",
        people_asset_id="people_doc223c",
        pack_version_id="pack_doc223c",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="prepare front anchor",
        root_source_asset_id="root_doc223c",
        reference_evidence_ids=["root_doc223c"],
        generation_channel="mcp",
        mcp_operation_id=operation_id,
        mcp_handoff_id=handoff_id,
    )


def test_doc203_provider_request_preserves_explicit_mcp_materialization_handoff() -> None:
    explicit_handoff = {
        "handoff_id": "mcp_handoff_doc203_current",
        "status": "pending",
        "generation_channel": "mcp",
        "resume_required": True,
    }

    request = _minimal_request(
        metadata=_request_metadata(
            operation_id="doc203-explicit-operation",
            materialization=explicit_handoff,
        )
    )

    assert request.metadata["generation_channel"] == "mcp"
    assert request.metadata["mcp_operation_id"] == "doc203-explicit-operation"
    assert request.metadata["mcp_materialization"] == explicit_handoff


def test_doc203_mcp_provider_consumes_explicit_handoff_not_stale_same_operation(tmp_path: Path) -> None:
    operation_id = "doc203-same-operation"
    request = _minimal_request(metadata=_request_metadata(operation_id=operation_id))
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    app_request, _provider_name, _references = provider._build_app_request(request)
    contract = app_request.prompt_plan.variables["mcp_materialization_context"]["rendering_contract"]

    stale_prompt = "stale submitted handoff"
    current_prompt = "current explicitly requested handoff"
    stale = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=stale_prompt,
        prompt_sha256=hashlib.sha256(stale_prompt.encode()).hexdigest(),
        reference_assets=[],
        rendering_contract=contract,
    )
    current = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=current_prompt,
        prompt_sha256=hashlib.sha256(current_prompt.encode()).hexdigest(),
        reference_assets=[],
        rendering_contract=contract,
    )
    for handoff in (stale, current):
        handoffs.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=_png_bytes(),
        )

    explicit_request = _minimal_request(
        metadata=_request_metadata(
            operation_id=operation_id,
            materialization={
                "handoff_id": current["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        )
    )

    response = provider.generate(explicit_request)

    record = outputs.get_output(response.candidates[0].metadata["output_id"])
    assert record is not None
    assert record.metadata["provider_raw_summary"]["mcp_handoff_id"] == current["handoff_id"]
    assert handoffs.get(current["handoff_id"])["status"] == "output_checkpointed"
    assert handoffs.get(stale["handoff_id"])["status"] == "submitted"


def test_doc218_mcp_pending_handoff_with_stale_contract_is_superseded(tmp_path: Path) -> None:
    operation_id = "doc218-stale-pending-operation"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    provider = McpMaterializationProvider(
        output_store=V3GeneratedOutputStore(tmp_path / "outputs"),
        handoff_store=handoffs,
    )
    stale_path = tmp_path / "stale.png"
    current_path = tmp_path / "current.png"
    stale_path.write_bytes(_png_bytes())
    current_path.write_bytes(_png_bytes((255, 232, 224)))
    stale_refs = [{"asset_id": "stale_ref", "file_path": str(stale_path)}]
    current_refs = [{"asset_id": "current_ref", "file_path": str(current_path)}]
    prompt = "same frozen prompt"
    prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
    contract = {
        "size": "32x48",
        "quality": "standard",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
    }
    stale = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=stale_refs,
        rendering_contract=contract,
    )
    explicit_request = _minimal_request(
        metadata=_request_metadata(
            operation_id=operation_id,
            materialization={
                "handoff_id": stale["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        )
    )

    context = provider._existing_mcp_handoff_context(  # noqa: SLF001
        explicit_request,
        current_context={
            "operation_id": operation_id,
            "canonical_prompt": prompt,
            "prompt_sha256": prompt_sha,
        },
        current_reference_assets=current_refs,
        current_rendering_contract=contract,
    )

    assert context is None


def test_doc218_mcp_submitted_handoff_with_stale_contract_fails_closed(tmp_path: Path) -> None:
    operation_id = "doc218-stale-submitted-operation"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    provider = McpMaterializationProvider(
        output_store=V3GeneratedOutputStore(tmp_path / "outputs"),
        handoff_store=handoffs,
    )
    stale_path = tmp_path / "stale-submitted.png"
    current_path = tmp_path / "current-submitted.png"
    stale_path.write_bytes(_png_bytes())
    current_path.write_bytes(_png_bytes((255, 232, 224)))
    stale_refs = [{"asset_id": "stale_ref", "file_path": str(stale_path)}]
    current_refs = [{"asset_id": "current_ref", "file_path": str(current_path)}]
    prompt = "same frozen prompt"
    prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
    contract = {
        "size": "32x48",
        "quality": "standard",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
    }
    stale = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=stale_refs,
        rendering_contract=contract,
    )
    handoffs.submit(
        stale["handoff_id"],
        nonce=stale["nonce"],
        prompt_sha256=stale["prompt_sha256"],
        reference_asset_hashes=stale["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )
    explicit_request = _minimal_request(
        metadata=_request_metadata(
            operation_id=operation_id,
            materialization={
                "handoff_id": stale["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        )
    )

    with pytest.raises(ProviderRuntimeError) as exc_info:
        provider._existing_mcp_handoff_context(  # noqa: SLF001
            explicit_request,
            current_context={
                "operation_id": operation_id,
                "canonical_prompt": prompt,
                "prompt_sha256": prompt_sha,
            },
            current_reference_assets=current_refs,
            current_rendering_contract=contract,
        )

    assert getattr(exc_info.value, "detail", {})["failure_code"] == "mcp_materialization_reference_mismatch"


def test_doc203_character_card_stage_creation_receives_explicit_mcp_handoff() -> None:
    class _Store:
        def __init__(self) -> None:
            self.record = None

        def list_recent(self, _limit):
            return []

        def list_mcp_operation_records(self, _operation_id):
            return []

        def save(self, record) -> None:
            self.record = record

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.job_store = _Store()
            self.record = None
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                }
            )

        def create_professional_character_card_stage_job(self, payload, **_kwargs):
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc203_character_card_resume",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            self.job_store.record = self.record
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):
            assert job_id == "job_doc203_character_card_resume"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc203",
        people_asset_id="people_doc203",
        card_version_id="card_doc203",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=2,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc203_current",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    materialization = service.created_payloads[0]["metadata"]["mcp_materialization"]
    assert materialization["handoff_id"] == "mcp_handoff_doc203_current"


def test_doc203_scenario_runtime_projects_explicit_mcp_handoff_to_generation_metadata() -> None:
    materialization = {
        "handoff_id": "mcp_handoff_doc203_runtime",
        "status": "pending",
        "generation_channel": "mcp",
        "resume_required": True,
    }

    metadata = ScenarioRuntime._renderer_channel_metadata(
        SimpleNamespace(
            metadata={
                "generation_channel": "mcp",
                "mcp_operation_id": "doc203-runtime-operation",
                "mcp_materialization": materialization,
            }
        )
    )

    assert metadata["generation_channel"] == "mcp"
    assert metadata["mcp_operation_id"] == "doc203-runtime-operation"
    assert metadata["mcp_materialization"] == materialization


def test_doc209_scenario_runtime_preserves_explicit_mcp_handoff_in_frozen_generation_plan() -> None:
    materialization = {
        "handoff_id": "mcp_handoff_doc209_submitted",
        "status": "submitted",
        "generation_channel": "mcp",
        "resume_required": True,
    }

    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=_LocalBrainProvider())).plan_job(
        {
            "user_input": "Create one character-card laugh validation portrait.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {
                "requested_image_count": 1,
                "require_real_images": True,
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc209:expression_set:expression.laugh:1:round3",
                "mcp_materialization": materialization,
            },
        }
    )

    assert result.planning_result is not None
    generation_metadata = result.planning_result.generation_plans[0].metadata
    assert generation_metadata["generation_channel"] == "mcp"
    assert generation_metadata["mcp_operation_id"] == "people_doc209:expression_set:expression.laugh:1:round3"
    assert generation_metadata["mcp_materialization"] == materialization


def test_doc205_character_card_recovers_orphan_submitted_handoff_without_replanning(tmp_path: Path) -> None:
    operation_id = "people_doc205:expression_set:expression.laugh:2:round3"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    prompt = _current_laugh_handoff_prompt()
    handoff = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    handoffs.submit(
        handoff["handoff_id"],
        nonce=handoff["nonce"],
        prompt_sha256=handoff["prompt_sha256"],
        reference_asset_hashes=handoff["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoffs, handoff),
    )

    class _Store:
        def __init__(self) -> None:
            self.record = None

        def list_recent(self, _limit):
            return []

        def list_mcp_operation_records(self, _operation_id):
            return []

        def save(self, record) -> None:
            self.record = record

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.job_store = _Store()
            self.record = None
            self.mcp_materialization_store = handoffs

        def create_professional_character_card_stage_job(self, payload, **_kwargs):
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc205_orphan_resume",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            self.job_store.record = self.record
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):
            assert job_id == "job_doc205_orphan_resume"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc205",
        people_asset_id="people_doc205",
        card_version_id="card_doc205",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=3,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    materialization = service.created_payloads[0]["metadata"]["mcp_materialization"]
    assert materialization["handoff_id"] == handoff["handoff_id"]
    assert [item["handoff_id"] for item in handoffs.list_unconsumed_by_operation(operation_id)] == [
        handoff["handoff_id"]
    ]


def test_doc205_character_card_orphan_handoff_recovery_fails_closed_when_ambiguous(tmp_path: Path) -> None:
    operation_id = "people_doc205:expression_set:expression.laugh:2:round3"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    for prompt in (
        _current_laugh_handoff_prompt(suffix="candidate A"),
        _current_laugh_handoff_prompt(suffix="candidate B"),
    ):
        handoffs.ensure_pending(
            operation_id=operation_id,
            prompt=prompt,
            prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            reference_assets=_current_expression_reference_assets(),
            rendering_contract={
                "renderer": "codex_builtin_imagegen",
                "model": "gpt-image-2",
                "size": "1024x1536",
                "quality": "high",
                "output_format": "png",
                "count": 1,
                "api_operation": "image_edit",
            },
        )

    service = SimpleNamespace(
        visual_asset_catalog=None,
        mcp_materialization_store=handoffs,
        job_store=SimpleNamespace(list_recent=lambda _limit: []),
    )
    request = CharacterCardCandidateRequest(
        project_id="project_doc205",
        people_asset_id="people_doc205",
        card_version_id="card_doc205",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=3,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_operation_ambiguous"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]


def test_doc207_character_card_orphan_recovery_prefers_submitted_artifact_over_pending(tmp_path: Path) -> None:
    operation_id = "people_doc207:expression_set:expression.laugh:1:round3"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    pending = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=_current_laugh_handoff_prompt(suffix="pending draft"),
        prompt_sha256=hashlib.sha256(
            _current_laugh_handoff_prompt(suffix="pending draft").encode("utf-8")
        ).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    submitted = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=_current_laugh_handoff_prompt(suffix="submitted artifact"),
        prompt_sha256=hashlib.sha256(
            _current_laugh_handoff_prompt(suffix="submitted artifact").encode("utf-8")
        ).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    handoffs.submit(
        submitted["handoff_id"],
        nonce=submitted["nonce"],
        prompt_sha256=submitted["prompt_sha256"],
        reference_asset_hashes=submitted["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return []

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return []

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.job_store = _Store()
            self.mcp_materialization_store = handoffs
            self.record = None

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc207_submitted_priority",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):  # noqa: ANN001, ANN201
            assert job_id == "job_doc207_submitted_priority"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc207",
        people_asset_id="people_doc207",
        card_version_id="card_doc207",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=3,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    selected = service.created_payloads[0]["metadata"]["mcp_materialization"]
    assert selected["handoff_id"] == submitted["handoff_id"]
    assert selected["handoff_id"] != pending["handoff_id"]


def test_doc208_character_card_request_pending_hint_cannot_override_submitted_artifact(tmp_path: Path) -> None:
    operation_id = "people_doc208:expression_set:expression.laugh:1:round3"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    pending = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=_current_laugh_handoff_prompt(suffix="pending draft"),
        prompt_sha256=hashlib.sha256(
            _current_laugh_handoff_prompt(suffix="pending draft").encode("utf-8")
        ).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    submitted = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=_current_laugh_handoff_prompt(suffix="submitted artifact"),
        prompt_sha256=hashlib.sha256(
            _current_laugh_handoff_prompt(suffix="submitted artifact").encode("utf-8")
        ).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    handoffs.submit(
        submitted["handoff_id"],
        nonce=submitted["nonce"],
        prompt_sha256=submitted["prompt_sha256"],
        reference_asset_hashes=submitted["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )
    old_pending_record = SimpleNamespace(
        job_id="job_doc208_old_pending",
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": pending["handoff_id"],
                    "status": "pending",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [old_pending_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [old_pending_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.job_store = _Store()
            self.mcp_materialization_store = handoffs
            self.record = None

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc208_submitted_resume",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):  # noqa: ANN001, ANN201
            assert job_id != "job_doc208_old_pending"
            assert job_id == "job_doc208_submitted_resume"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc208",
        people_asset_id="people_doc208",
        card_version_id="card_doc208",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=3,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=pending["handoff_id"],
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    selected = service.created_payloads[0]["metadata"]["mcp_materialization"]
    assert selected["handoff_id"] == submitted["handoff_id"]
    assert selected["handoff_id"] != pending["handoff_id"]


def test_doc215_product_api_allows_only_pre_handoff_mcp_interruption_reentry() -> None:
    base_record = SimpleNamespace(
        status=ProductJobStatusValue.GENERATING,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc215:expression_set:expression.laugh:1:round5",
            }
        ),
    )

    assert V3ProductApiService._can_resume_interrupted_mcp_materialization(base_record) is True

    for metadata_patch, field_patch in (
        ({"mcp_materialization": {"handoff_id": "mcp_handoff_existing"}}, {}),
        ({}, {"generation_result": object()}),
        ({"generation_channel": "provider"}, {}),
        ({"professional_character_card_preparation": False}, {}),
        ({"background_generation_attempt_id": "attempt_running_elsewhere"}, {}),
    ):
        metadata = {**base_record.request.metadata, **metadata_patch}
        record = SimpleNamespace(
            status=ProductJobStatusValue.GENERATING,
            planning_result=object(),
            generation_result=None,
            request=SimpleNamespace(metadata=metadata),
        )
        for name, value in field_patch.items():
            setattr(record, name, value)
        assert V3ProductApiService._can_resume_interrupted_mcp_materialization(record) is False


def test_doc215_character_card_reenters_same_interrupted_mcp_job_without_replanning() -> None:
    operation_id = "people_doc215:expression_set:expression.laugh:1:round5"
    interrupted_record = SimpleNamespace(
        job_id="job_doc215_interrupted",
        status=ProductJobStatusValue.GENERATING,
        planning_result=_minimal_planning_result(
            "job_doc215_interrupted",
            generation_metadata=_current_character_card_planning_metadata(operation_id=operation_id),
        ),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [interrupted_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [interrupted_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.generated_calls = []
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(get=lambda _handoff_id: None)

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            raise AssertionError("Doc215 must reuse the interrupted job instead of re-planning")

        def generate_job(self, job_id, request):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, request))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return interrupted_record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc215",
        people_asset_id="people_doc215",
        card_version_id="card_doc215",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert service.created_payloads == []
    assert service.generated_calls[0][0] == "job_doc215_interrupted"
    assert (
        service.generated_calls[0][1]["metadata"]["_v3_resume_interrupted_mcp_materialization"]
        is True
    )
    assert service.generated_calls[0][1]["metadata"]["disable_visual_auto_retry"] is True
    assert service.generated_calls[0][1]["metadata"]["max_visual_retry_attempts"] == 0


def test_doc233_character_card_reenters_pre_handoff_job_with_logical_front_reference_plan() -> None:
    operation_id = "people_doc233:expression_set:expression.anger:1"
    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        slot_key="expression.anger",
        attempt_round=1,
    )
    # Real Product API Character Card plans freeze the logical face.front winner.
    # Provider/MCP materialization derives the full-frame/card-framing and crop
    # references later, before the durable handoff is created.  A pre-handoff
    # interrupted job must therefore be resumable from this logical plan; the
    # full-frame-first contract is enforced at the handoff boundary instead.
    planning_metadata["professional_anchor_reference_assets"] = [
        {"asset_id": "front_winner", "output_id": "front_winner"}
    ]
    interrupted_record = SimpleNamespace(
        job_id="job_doc233_interrupted_logical_front",
        status=ProductJobStatusValue.GENERATING,
        planning_result=_minimal_planning_result(
            "job_doc233_interrupted_logical_front",
            generation_metadata=planning_metadata,
        ),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.anger",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
            }
        ),
    )

    class _Store:
        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [interrupted_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.generated_calls = []
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(get=lambda _handoff_id: None)

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            raise AssertionError("pre-handoff recovery must reuse the interrupted job")

        def generate_job(self, job_id, request):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, request))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return interrupted_record

    request = CharacterCardCandidateRequest(
        project_id="project_doc233",
        people_asset_id="people_doc233",
        card_version_id="card_doc233",
        module="expression_set",
        slot_key="expression.anger",
        candidate_index=1,
        attempt_round=1,
        reference_output_ids=["front_winner"],
        user_intent="controlled anger keyframe",
        generation_channel="mcp",
    )

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert service.created_payloads == []
    assert service.generated_calls[0][0] == "job_doc233_interrupted_logical_front"
    assert service.generated_calls[0][1]["metadata"]["_v3_resume_interrupted_mcp_materialization"] is True
    assert service.generated_calls[0][1]["metadata"]["disable_visual_auto_retry"] is True
    assert service.generated_calls[0][1]["metadata"]["max_visual_retry_attempts"] == 0


def test_doc215_existing_mcp_handoff_still_uses_normal_handoff_resume_not_reentry() -> None:
    operation_id = "people_doc215:expression_set:expression.laugh:1:round5"
    pending_record = SimpleNamespace(
        job_id="job_doc215_pending",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=_minimal_planning_result(
            "job_doc215_pending",
            generation_metadata=_current_character_card_planning_metadata(
                operation_id=operation_id,
                handoff={
                    "handoff_id": "mcp_handoff_doc215_existing",
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            ),
        ),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc215_existing",
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [pending_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [pending_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.generated_calls = []
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                }
            )

        def generate_job(self, job_id, request):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, request))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return pending_record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc215",
        people_asset_id="people_doc215",
        card_version_id="card_doc215",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc215_existing",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert "_v3_resume_interrupted_mcp_materialization" not in service.generated_calls[0][1]["metadata"]
    assert service.generated_calls[0][1]["metadata"]["disable_visual_auto_retry"] is True
    assert service.generated_calls[0][1]["metadata"]["max_visual_retry_attempts"] == 0


def test_doc219_host_does_not_resume_stale_crop_first_pending_expression_handoff() -> None:
    operation_id = "people_doc219:expression_set:expression.laugh:2:round5"
    pending_record = SimpleNamespace(
        job_id="job_doc219_stale_pending",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc219_stale_pending",
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [pending_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [pending_record]

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _stale_crop_first_expression_reference_assets(),
                }
            )

    request = CharacterCardCandidateRequest(
        project_id="project_doc219",
        people_asset_id="people_doc219",
        card_version_id="card_doc219",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc219_stale_pending",
    )

    resume = ProductApiAnchorPackPreparationHost(_Service())._mcp_resume_character_card_stage_job_record(  # type: ignore[arg-type]  # noqa: SLF001
        request,
        operation_id,
    )

    assert resume is None


def test_doc219_host_fails_closed_on_stale_crop_first_submitted_expression_handoff() -> None:
    operation_id = "people_doc219:expression_set:expression.laugh:2:round5"
    submitted_record = SimpleNamespace(
        job_id="job_doc219_stale_submitted",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc219_stale_submitted",
                    "status": "submitted",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [submitted_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [submitted_record]

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "submitted",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _stale_crop_first_expression_reference_assets(),
                }
            )

    request = CharacterCardCandidateRequest(
        project_id="project_doc219",
        people_asset_id="people_doc219",
        card_version_id="card_doc219",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc219_stale_submitted",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_reference_mismatch"):
        ProductApiAnchorPackPreparationHost(_Service())._mcp_resume_character_card_stage_job_record(  # type: ignore[arg-type]  # noqa: SLF001
            request,
            operation_id,
        )


def test_doc220_stale_pending_handoff_hint_is_not_copied_into_new_stage_job() -> None:
    operation_id = "people_doc220:expression_set:expression.laugh:2:round5"

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return []

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return []

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.record = None
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _stale_crop_first_expression_reference_assets(),
                },
                list_unconsumed_by_operation=lambda _operation_id: [],
            )

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc220_new_without_stale_hint",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):  # noqa: ANN001, ANN201
            assert job_id == "job_doc220_new_without_stale_hint"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc220",
        people_asset_id="people_doc220",
        card_version_id="card_doc220",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc220_stale_pending",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert service.created_payloads
    assert "mcp_materialization" not in service.created_payloads[0]["metadata"]


def test_doc221_clean_interrupted_job_wins_over_older_stale_blocked_handoff_job() -> None:
    operation_id = "people_doc221:expression_set:expression.laugh:2:round5"
    stale_blocked_record = SimpleNamespace(
        job_id="job_doc221_stale_blocked",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc221_stale_pending",
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )
    clean_generating_record = SimpleNamespace(
        job_id="job_doc221_clean_generating",
        status=ProductJobStatusValue.GENERATING,
        planning_result=_minimal_planning_result(
            "job_doc221_clean_generating",
            generation_metadata=_current_character_card_planning_metadata(operation_id=operation_id),
        ),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [stale_blocked_record, clean_generating_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [stale_blocked_record, clean_generating_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = _Store()
            self.generated_calls = []
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _stale_crop_first_expression_reference_assets(),
                }
            )

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            assert job_id == "job_doc221_clean_generating"
            self.generated_calls.append((job_id, payload))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
                metadata={
                    "mcp_materialization": {
                        "handoff_id": "mcp_handoff_doc221_new_full_frame_first",
                        "status": "pending",
                        "generation_channel": "mcp",
                        "canonical_prompt": _current_laugh_handoff_prompt(),
                        "reference_assets": _current_expression_reference_assets(),
                    }
                },
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            if job_id == clean_generating_record.job_id:
                return clean_generating_record
            if job_id == stale_blocked_record.job_id:
                return stale_blocked_record
            return None

    request = CharacterCardCandidateRequest(
        project_id="project_doc221",
        people_asset_id="people_doc221",
        card_version_id="card_doc221",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc221_stale_pending",
    )

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert str(exc_info.value) == "mcp_materialization_pending"
    assert exc_info.value.mcp_handoff_id == "mcp_handoff_doc221_new_full_frame_first"
    assert service.generated_calls
    assert service.generated_calls[0][0] == "job_doc221_clean_generating"
    assert service.generated_calls[0][1]["metadata"]["_v3_resume_interrupted_mcp_materialization"] is True
    assert service.generated_calls[0][1]["metadata"]["disable_visual_auto_retry"] is True


def test_doc221_current_handoff_resume_still_requires_exact_operation_and_refs() -> None:
    requested_operation = "people_doc221:expression_set:expression.laugh:2:round5"
    current_handoff = "mcp_handoff_doc221_current"
    wrong_ref_record = SimpleNamespace(
        job_id="job_doc221_wrong_refs",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["other_front"],
                "generation_channel": "mcp",
                "mcp_operation_id": requested_operation,
                "mcp_materialization": {
                    "handoff_id": current_handoff,
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )
    wrong_operation_record = SimpleNamespace(
        job_id="job_doc221_wrong_operation",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc221:expression_set:expression.laugh:3:round5",
                "mcp_materialization": {
                    "handoff_id": current_handoff,
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )
    exact_record = SimpleNamespace(
        job_id="job_doc221_exact_current",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=_minimal_planning_result(
            "job_doc221_exact_current",
            generation_metadata=_current_character_card_planning_metadata(
                operation_id=requested_operation,
                handoff={
                    "handoff_id": current_handoff,
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            ),
        ),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": requested_operation,
                "mcp_materialization": {
                    "handoff_id": current_handoff,
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [wrong_ref_record, wrong_operation_record, exact_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [wrong_ref_record, wrong_operation_record, exact_record]

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                }
            )

    request = CharacterCardCandidateRequest(
        project_id="project_doc221",
        people_asset_id="people_doc221",
        card_version_id="card_doc221",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=current_handoff,
    )

    resume = ProductApiAnchorPackPreparationHost(_Service())._mcp_resume_character_card_stage_job_record(  # type: ignore[arg-type]  # noqa: SLF001
        request,
        requested_operation,
    )

    assert resume is exact_record


def test_doc223c_character_card_recovers_old_interrupted_job_beyond_recent_window(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:expression_set:expression.laugh:2:round5"
    store = PersistentProductJobStore(tmp_path / "jobs")
    target = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="positive expression keyframe",
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
            },
        ),
        status=ProductJobStatusValue.GENERATING,
        job_id_value="job_doc223c_character_old_checkpoint",
        planning_result=_minimal_planning_result(
            "job_doc223c_character_old_checkpoint",
            generation_metadata=_current_character_card_planning_metadata(operation_id=operation_id),
        ),
    )
    store.save(target)
    _save_doc223c_noise_jobs(store, 230)
    assert target.job_id not in {record.job_id for record in store.list_recent(200)}

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = SimpleNamespace(get=lambda _handoff_id: None)
            self.created_payloads = []
            self.generated_calls = []

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            raise AssertionError("Doc223-C must recover the durable job before creating a new Brain job")

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, payload))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            return self.job_store.get(job_id)

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(
            _character_card_doc223c_request(operation_id=operation_id)
        )  # type: ignore[arg-type]

    assert service.created_payloads == []
    assert service.generated_calls[0][0] == target.job_id
    assert len(store.list_mcp_operation_records(operation_id)) == 1


def test_doc228_service_review_only_resume_rechecks_generated_timeout_package_without_regeneration(
    tmp_path: Path,
) -> None:
    job_id = "job_doc228_generated_timeout"
    output_id = "v3_output_a27b83988d28f9010cd1"
    candidate_id = "candidate_doc228_timeout"
    operation_id = "people_doc228:expression_set:expression.laugh:2:round5"
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    prompt = _current_laugh_handoff_prompt()
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={"size": "32x48", "output_format": "png", "count": 1},
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=pending["prompt_sha256"],
        reference_asset_hashes=pending["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    consumed = handoff_store.consume(submitted["handoff_id"])
    handoff_store.mark_output_checkpoint(
        pending["handoff_id"],
        job_id=job_id,
        candidate_id=candidate_id,
        output_id=output_id,
        artifact_sha256=consumed["artifact_sha256"],
    )
    handoff_store.mark_job_checkpoint(
        pending["handoff_id"],
        job_id=job_id,
        candidate_id=candidate_id,
        output_id=output_id,
        generation_result_id=f"planning_{job_id}",
    )
    result, record, timeout_package = _doc228_generated_timeout_record(
        job_id=job_id,
        output_id=output_id,
        candidate_id=candidate_id,
        operation_id=operation_id,
        handoff_id=pending["handoff_id"],
        request_handoff_status="pending",
    )
    output_store.save_base64_output(
        job_id=job_id,
        candidate_id=candidate_id,
        asset_id=result.asset_pack.assets[0].asset_id,
        provider="mcp_materialization",
        model="gpt-image-2",
        encoded_image=base64.b64encode(_png_bytes()).decode("ascii"),
        output_id=output_id,
        metadata={
            "project_id": "project_doc228",
            "provider_prompt_sha256": "sha256:doc228",
            "prompt_compilation_id": "prompt_doc228",
            "provider_reference_image_count": 2,
            "prompt_reference_parity": {"verified": True},
            "reference_evidence_parity": {"verified": True},
        },
    )
    job_store.save(record)

    class _NoRuntime:
        calls = 0

        def generate_job(self, *_args, **_kwargs):  # noqa: ANN001, ANN201
            self.calls += 1
            raise AssertionError("review-only resume must not call ScenarioRuntime/provider generation")

    class _VisionStub:
        def __init__(self) -> None:
            self.calls = []

        def inspect(self, resolution, metadata=None):  # noqa: ANN001, ANN201
            self.calls.append((resolution.output_id, dict(metadata or {})))
            return VisualInspectionReport(
                inspection_id="visual_inspection_doc228_pass",
                project_id="project_doc228",
                job_id=job_id,
                candidate_id=candidate_id,
                output_id=output_id,
                mode="hybrid",
                status="pass",
                verification_state="verified",
                confidence=0.94,
                score_card=_laugh_pass_score_card(),
                detected_issues=[],
                evidence={"doc228_review_only_resume": True},
                user_visible_summary=["shared Vision review succeeded on resume"],
            )

    vision = _VisionStub()
    service = V3ProductApiService(
        scenario_runtime=_NoRuntime(),  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        vision_inspector=vision,  # type: ignore[arg-type]
        mcp_materialization_store=handoff_store,
    )

    status = service.generate_asset_series(
        job_id,
        {
            "quality_mode": "strict",
            "metadata": {
                "_v3_resume_finalizing_review": True,
                "disable_visual_auto_retry": True,
                "max_visual_retry_attempts": 0,
            },
        },
    )

    updated = job_store.get(job_id)
    assert status.status == ProductJobStatusValue.GENERATED
    assert _NoRuntime.calls == 0
    assert [item[0] for item in vision.calls] == [output_id]
    assert len(output_store.list_by_job(job_id)) == 1
    assert updated is not None
    assert updated.generation_result is not None
    inspection = updated.generation_result.metadata["post_generation_review_package"]["inspections"][0]
    assert inspection["inspection_id"] == "visual_inspection_doc228_pass"
    assert inspection["verification_state"] == "verified"
    assert inspection["status"] == "pass"
    assert updated.generation_result.metadata["post_generation_review_package"] != timeout_package
    assert updated.request.metadata["mcp_materialization"]["status"] == "job_checkpointed"
    assert "mcp_review_status" not in updated.request.metadata


def test_doc228_service_review_only_resume_rechecks_signal_provider_unavailable_without_regeneration(
    tmp_path: Path,
) -> None:
    job_id = "job_doc228_signal_unavailable"
    output_id = "v3_output_88888888888888888888"
    candidate_id = "candidate_doc228_signal_unavailable"
    operation_id = "people_doc228:expression_set:expression.anger:1:round2"
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    prompt = _current_laugh_handoff_prompt()
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={"size": "32x48", "output_format": "png", "count": 1},
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=pending["prompt_sha256"],
        reference_asset_hashes=pending["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    consumed = handoff_store.consume(submitted["handoff_id"])
    handoff_store.mark_output_checkpoint(
        pending["handoff_id"],
        job_id=job_id,
        candidate_id=candidate_id,
        output_id=output_id,
        artifact_sha256=consumed["artifact_sha256"],
    )
    handoff_store.mark_job_checkpoint(
        pending["handoff_id"],
        job_id=job_id,
        candidate_id=candidate_id,
        output_id=output_id,
        generation_result_id=f"planning_{job_id}",
    )
    result, record, _timeout_package = _doc228_generated_timeout_record(
        job_id=job_id,
        output_id=output_id,
        candidate_id=candidate_id,
        operation_id=operation_id,
        handoff_id=pending["handoff_id"],
        request_handoff_status="pending",
    )
    unavailable_package = _provider_unavailable_signal_review_package(
        job_id=job_id,
        output_id=output_id,
        candidate_id=candidate_id,
    )
    record.generation_result = _with_review_package(result, unavailable_package)
    record.planning_result = record.generation_result
    output_store.save_base64_output(
        job_id=job_id,
        candidate_id=candidate_id,
        asset_id=result.asset_pack.assets[0].asset_id,
        provider="mcp_materialization",
        model="gpt-image-2",
        encoded_image=base64.b64encode(_png_bytes()).decode("ascii"),
        output_id=output_id,
    )
    job_store.save(record)

    class _NoRuntime:
        calls = 0

        def generate_job(self, *_args, **_kwargs):  # noqa: ANN001, ANN201
            self.calls += 1
            raise AssertionError("review-only resume must not call ScenarioRuntime/provider generation")

    class _VisionStub:
        def __init__(self) -> None:
            self.calls = []

        def inspect(self, resolution, metadata=None):  # noqa: ANN001, ANN201
            self.calls.append((resolution.output_id, dict(metadata or {})))
            return VisualInspectionReport(
                inspection_id="visual_inspection_doc228_unavailable_rechecked",
                project_id="project_doc228",
                job_id=job_id,
                candidate_id=candidate_id,
                output_id=output_id,
                mode="hybrid",
                status="pass",
                verification_state="verified",
                confidence=0.94,
                score_card=_laugh_pass_score_card(),
                detected_issues=[],
                evidence={"doc228_review_only_resume": "provider_unavailable_rechecked"},
                user_visible_summary=["shared Vision review succeeded after provider config was restored"],
            )

    vision = _VisionStub()
    service = V3ProductApiService(
        scenario_runtime=_NoRuntime(),  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        vision_inspector=vision,  # type: ignore[arg-type]
        mcp_materialization_store=handoff_store,
    )

    status = service.generate_asset_series(
        job_id,
        {
            "quality_mode": "strict",
            "metadata": {
                "_v3_resume_finalizing_review": True,
                "disable_visual_auto_retry": True,
                "max_visual_retry_attempts": 0,
            },
        },
    )

    updated = job_store.get(job_id)
    assert status.status == ProductJobStatusValue.GENERATED
    assert _NoRuntime.calls == 0
    assert [item[0] for item in vision.calls] == [output_id]
    assert len(output_store.list_by_job(job_id)) == 1
    assert updated is not None
    assert updated.generation_result is not None
    package = updated.generation_result.metadata["post_generation_review_package"]
    inspection = package["inspections"][0]
    assert inspection["inspection_id"] == "visual_inspection_doc228_unavailable_rechecked"
    assert inspection["verification_state"] == "verified"
    assert inspection["status"] == "pass"
    assert package != unavailable_package
    assert updated.request.metadata["mcp_materialization"]["status"] == "job_checkpointed"
    assert "mcp_review_status" not in updated.request.metadata


def test_doc228_exact_body_handoff_resume_reenters_runtime_despite_stale_failed_projection(
    tmp_path: Path,
) -> None:
    job_id = "job_doc228_body_exact_resume"
    operation_id = "visual_asset_doc228_body:body_silhouette:body.front_full:2:refresh_attempt_doc228"
    prompt_sha = "4" * 64
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    frozen_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
    }
    # Import locally to keep Doc203's historical expression-focused imports stable.
    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")
    frozen_contract["body_silhouette_mcp_materialization_channel_contract"] = (
        body_silhouette_mcp_materialization_channel_contract()
    )
    frozen_contract["body_refresh_presentation_intent"] = body_intent
    frozen_contract.update(_doc203_body_frozen_contract_fields())
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt="closed Body Silhouette MCP prompt",
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract=frozen_contract,
        require_body_rendering_contract=True,
    )
    handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 2,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
        }
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="body exact resume",
            metadata={
                **planning_metadata,
                "project_id": "project_doc228_body",
                "mcp_materialization": {
                    "handoff_id": pending["handoff_id"],
                    "status": "failed",
                    "failure_code": "mcp_materialization_rendering_contract_mismatch",
                    "generation_channel": "mcp",
                    "resume_required": True,
                },
                "provider_failure_retry": {
                    "final_status": "failed",
                    "final_classification": "non_retryable_provider_failure",
                    "final_failure_code": "mcp_materialization_rendering_contract_mismatch",
                    "fresh_upstream_requests": 0,
                    "outer_request_count": 0,
                },
            },
        ),
        status=ProductJobStatusValue.BLOCKED,
        job_id_value=job_id,
        planning_result=_minimal_planning_result(
            job_id,
            generation_metadata=planning_metadata,
        ),
        generation_result=None,
        balance_estimate={"credits_required": 0},
    )
    job_store.save(record)

    class _RuntimeProbe:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.scenario_registry = ScenarioRuntime().scenario_registry

        def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.calls.append(dict(payload.get("metadata") or {}))
            raise RuntimeError("doc228_runtime_probe_stop")

    runtime = _RuntimeProbe()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )

    status = service.generate_asset_series(
        job_id,
        {
            "quality_mode": "strict",
            "metadata": {"_v3_resume_interrupted_mcp_materialization": True},
        },
    )

    assert runtime.calls, "exact submitted Body MCP handoff resume must re-enter ScenarioRuntime"
    metadata = runtime.calls[0]
    assert metadata["professional_character_card_stage"] == "body_silhouette"
    assert metadata["professional_character_card_slot"] == "body.front_full"
    assert metadata["professional_character_card_body_refresh_source_mode"] == "inference_first"
    assert metadata["professional_character_card_body_refresh_presentation_intent"] == body_intent
    assert metadata["mcp_materialization"]["handoff_id"] == pending["handoff_id"]
    assert status.status == ProductJobStatusValue.BLOCKED


def test_doc263_submitted_body_resume_uses_core_consumer_before_generate_stage(
    tmp_path: Path,
) -> None:
    """A submitted Body handoff must not re-enter Brain/capability generation.

    The fixture has a frozen plan, submitted typed pixels, and no
    generation_result; the expected path is consume -> generation_result ->
    post-generation review, while the fake runtime must remain untouched.
    """

    job_id = "job_doc263_body_submitted_consumer"
    operation_id = "visual_asset_doc263_body:body_silhouette:body.front_full:1"
    prompt = "closed Body Silhouette MCP prompt"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")

    class _RecordingHandoffStore(McpMaterializationHandoffStore):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.consume_calls: list[dict] = []
            self.observed_inflight_status: ProductJobStatusValue | None = None
            self.observed_inflight_metadata: dict = {}

        def consume(self, handoff_id: str, *, expected_checkpoint=None):  # noqa: ANN001, ANN201
            observed = job_store.get(job_id)
            if observed is not None:
                self.observed_inflight_status = observed.status
                self.observed_inflight_metadata = dict(observed.request.metadata)
            self.consume_calls.append(
                {
                    "handoff_id_present": bool(str(handoff_id or "").strip()),
                    "expected_checkpoint_keys": sorted(dict(expected_checkpoint or {}).keys()),
                }
            )
            return super().consume(handoff_id, expected_checkpoint=expected_checkpoint)

    handoff_store = _RecordingHandoffStore(tmp_path / "handoffs")
    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")
    frozen_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_generate",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
        **_doc203_body_frozen_contract_fields(),
    }
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract=frozen_contract,
        require_body_rendering_contract=True,
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    assert submitted["status"] == "submitted"
    frozen_handoff = handoff_store.get(pending["handoff_id"])
    assert frozen_handoff is not None
    frozen_rendering_fingerprint = frozen_handoff["rendering_contract_fingerprint"]
    frozen_reference_fingerprint = frozen_handoff["reference_semantic_fingerprint"]

    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
            "real_image_generation": True,
            "llm_brain": {
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": prompt,
                        "review_status": "approved",
                    }
                ]
            },
        }
    )
    frozen_planning = _minimal_planning_result(
        job_id,
        generation_metadata=planning_metadata,
    )
    frozen_planning = frozen_planning.model_copy(
        update={
            "generation_plans": [
                frozen_planning.generation_plans[0].model_copy(
                    update={"provider_strategy": ProviderStrategy.PLANNING_ONLY}
                )
            ]
        }
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="body submitted consumer checkpoint",
            metadata={
                **planning_metadata,
                "project_id": "project_doc263_body",
                    "mcp_materialization": {
                    "handoff_id": pending["handoff_id"],
                    "status": "submitted",
                    "generation_channel": "mcp",
                        "resume_required": True,
                    },
                    "generation_lifecycle_failure": {"failure_code": "stale_generation_failure"},
                    "remote_creative_brain_outcome": {"status": "stale"},
                    "provider_failure_retry": {"final_failure_code": "stale_provider_failure"},
                },
        ),
        status=ProductJobStatusValue.BLOCKED,
        job_id_value=job_id,
        planning_result=frozen_planning,
        generation_result=None,
        balance_estimate={"credits_required": 0},
    )
    job_store.save(record)
    handoff_store.job_store = job_store
    initial_job_count = job_store.count()
    frozen_planning_result_id = record.planning_result.planning_result_id
    frozen_prompt_compilation_id = record.planning_result.prompt_compilations[0].prompt_compilation_id

    class _BrainAndCapabilityProbeRuntime:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.scenario_registry = ScenarioRuntime().scenario_registry

        def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.calls.append(dict(payload.get("metadata") or {}))
            raise AssertionError("submitted Body resume must not re-enter ScenarioRuntime.generate_job")

    runtime = _BrainAndCapabilityProbeRuntime()
    runtime.generation_router = GenerationRouter(
        mcp_provider=McpMaterializationProvider(
            output_store=output_store,
            handoff_store=handoff_store,
        )
    )
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )
    assert service._is_submitted_body_mcp_resume(record)  # noqa: SLF001
    status = service.generate_asset_series(
        job_id,
        {
            "quality_mode": "strict",
            "metadata": {"_v3_resume_finalizing_review": True},
        },
    )

    assert runtime.calls == []
    assert len(handoff_store.consume_calls) == 1
    assert handoff_store.observed_inflight_status == ProductJobStatusValue.GENERATING
    assert "generation_lifecycle_failure" not in handoff_store.observed_inflight_metadata
    assert "remote_creative_brain_outcome" not in handoff_store.observed_inflight_metadata
    assert "provider_failure_retry" not in handoff_store.observed_inflight_metadata
    assert status.status == ProductJobStatusValue.GENERATED
    assert job_store.count() == initial_job_count
    assert len(output_store.list_by_job(job_id)) == 1
    updated = job_store.get(job_id)
    assert updated is not None
    assert updated.generation_result is not None
    assert updated.planning_result is not None
    assert updated.planning_result.planning_result_id == frozen_planning_result_id
    assert updated.planning_result.prompt_compilations[0].prompt_compilation_id == frozen_prompt_compilation_id
    assert updated.request.metadata["mcp_materialization"]["status"] == "job_checkpointed"
    assert updated.request.metadata["professional_character_card_body_refresh_source_mode"] == "inference_first"
    assert updated.request.metadata["professional_character_card_body_refresh_presentation_intent"] == body_intent
    assert "post_generation_review_package" in updated.generation_result.metadata
    resumed_handoff = handoff_store.get(pending["handoff_id"])
    assert resumed_handoff is not None
    assert resumed_handoff["rendering_contract_fingerprint"] == frozen_rendering_fingerprint
    assert resumed_handoff["reference_semantic_fingerprint"] == frozen_reference_fingerprint
    assert resumed_handoff["rendering_contract"]["body_refresh_presentation_intent"] == body_intent
    assert "body_silhouette_mcp_materialization_channel_contract" in resumed_handoff["rendering_contract"]


def test_doc263_submitted_consumer_projects_persisted_output_record_before_shared_review(
    tmp_path: Path,
) -> None:
    """Submitted MCP pixels must become a file-backed current-job output."""

    job_id = "job_doc263_output_projection"
    operation_id = "visual_asset_doc263_output_projection:body_silhouette:body.front_full:1"
    prompt = "closed Body Silhouette MCP output projection prompt"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    body_intent = _doc203_body_frozen_contract_fields()["body_refresh_presentation_intent"]
    frozen_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_generate",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
        **_doc203_body_frozen_contract_fields(),
    }
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract=frozen_contract,
        require_body_rendering_contract=True,
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    assert submitted["status"] == "submitted"

    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
            "mcp_materialization": {
                "handoff_id": pending["handoff_id"],
                "status": "submitted",
                "generation_channel": "mcp",
                "resume_required": True,
            },
            "llm_brain": {
                "canonical_provider_prompts": [
                    {"output_index": 1, "prompt": prompt, "review_status": "approved"}
                ]
            },
        }
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="submitted MCP output projection checkpoint",
            metadata={**planning_metadata, "project_id": "project_doc263_output_projection"},
        ),
        status=ProductJobStatusValue.GENERATING,
        job_id_value=job_id,
        planning_result=_minimal_planning_result(job_id, generation_metadata=planning_metadata),
        generation_result=None,
        balance_estimate={"credits_required": 0},
    )
    job_store.save(record)
    handoff_store.job_store = job_store

    class _PersistedOutputRouter:
        def __init__(self) -> None:
            self.output_id = "v3_output_11111111111111111111"

        def generate(self, request):  # noqa: ANN001
            return SimpleNamespace(
                candidates=[
                    SimpleNamespace(
                        candidate_id="candidate_doc263_output_projection",
                        provider="mcp_materialization",
                        file_path=None,
                        uri=None,
                        prompt_compilation_id="prompt_doc263_output_projection",
                        condition_plan_id="condition_doc263_output_projection",
                        metadata={
                            "output_id": self.output_id,
                            "mcp_materialization": {
                                "handoff_id": pending["handoff_id"],
                                "expected_checkpoint": {
                                    "candidate_id": "candidate_doc263_output_projection",
                                    "output_id": self.output_id,
                                },
                            },
                        },
                    )
                ],
                provider_metadata={"test_only": True},
            )

    router = _PersistedOutputRouter()
    runtime = SimpleNamespace(
        generation_router=router,
        scenario_registry=ScenarioRuntime().scenario_registry,
    )
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )

    with pytest.raises(RuntimeError, match="mcp_materialization_output_projection_missing"):
        service._consume_submitted_body_mcp_artifact(record)  # noqa: SLF001

    missing_path_record = output_store.save_base64_output(
        job_id=job_id,
        candidate_id="candidate_doc263_output_projection",
        asset_id="asset_doc223c",
        provider="mcp_materialization",
        model="gpt-image-2",
        encoded_image=base64.b64encode(_png_bytes()).decode("ascii"),
        output_id="v3_output_22222222222222222222",
    )
    Path(missing_path_record.file_path).unlink()
    router.output_id = missing_path_record.output_id
    with pytest.raises(RuntimeError, match="mcp_materialization_output_projection_missing"):
        service._consume_submitted_body_mcp_artifact(record)  # noqa: SLF001

    persisted = output_store.save_base64_output(
        job_id=job_id,
        candidate_id="candidate_doc263_output_projection",
        asset_id="asset_doc223c",
        provider="mcp_materialization",
        model="gpt-image-2",
        encoded_image=base64.b64encode(_png_bytes((180, 212, 236))).decode("ascii"),
        output_id="v3_output_33333333333333333333",
    )
    router.output_id = persisted.output_id
    planning_id = record.planning_result.planning_result_id
    generated_result = service._consume_submitted_body_mcp_artifact(record)  # noqa: SLF001
    assert generated_result is not None
    assert generated_result.creative_job.job_id == job_id
    assert generated_result.planning_result_id != planning_id
    generated = generated_result.asset_pack.assets[0]
    assert generated.file_path == persisted.file_path
    assert generated.uri == persisted.thumbnail_url
    assert generated.metadata["output_id"] == persisted.output_id
    assert generated.metadata["candidate_metadata"]["output_id"] == persisted.output_id
    assert generated.metadata["candidate_metadata"]["file_path"] == persisted.file_path
    assert generated.metadata["candidate_metadata"]["uri"] == persisted.thumbnail_url
    assert Path(generated.file_path).is_file()


def test_doc263_existing_generated_body_resume_projects_submitted_artifact_before_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generated legacy result must not bypass the submitted-artifact projection."""

    job_id = "job_doc263_existing_generated"
    operation_id = "visual_asset_doc263_existing_generated:body_silhouette:body.rear_full:3"
    prompt = "closed Body Silhouette MCP existing generated projection prompt"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    body_contract = _doc203_body_frozen_contract_fields()
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "1024x1536",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_generate",
            "input_fidelity": "high",
            "input_fidelity_required": False,
            "size_normalization": "white_matte_contain_to_contract_size",
            **body_contract,
        },
        require_body_rendering_contract=True,
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes((180, 212, 236)),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    assert submitted["status"] == "submitted"

    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.rear_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 3,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_contract[
                "body_refresh_presentation_intent"
            ],
            "mcp_materialization": {
                "handoff_id": pending["handoff_id"],
                "status": "submitted",
                "generation_channel": "mcp",
                "resume_required": True,
            },
            "llm_brain": {
                "canonical_provider_prompts": [
                    {"output_index": 1, "prompt": prompt, "review_status": "approved"}
                ]
            },
        }
    )
    submitted_contract = handoff_store.get(pending["handoff_id"])
    assert submitted_contract is not None
    planning_metadata["mcp_materialization"].update(
        {
            "nonce": submitted_contract["nonce"],
            "prompt_sha256": submitted_contract["prompt_sha256"],
            "reference_asset_hashes": list(submitted_contract["reference_asset_hashes"]),
            "reference_semantic_fingerprint": submitted_contract["reference_semantic_fingerprint"],
            "rendering_contract_fingerprint": submitted_contract["rendering_contract_fingerprint"],
        }
    )
    planning = _minimal_planning_result(job_id, generation_metadata=planning_metadata)
    candidate_id = "candidate_doc263_existing_generated"
    existing_asset = planning.asset_pack.assets[0].model_copy(
        update={
            "metadata": {
                "planning_only": True,
                "selected_candidate_id": candidate_id,
                "selected_candidate_provider": "mcp_materialization",
                "selected_candidate_is_mock": False,
                "candidate_metadata": {"planning_only": True},
            }
        }
    )
    existing_result = planning.model_copy(
        update={
            "asset_pack": planning.asset_pack.model_copy(
                update={"assets": [existing_asset], "planning_only": False}
            ),
            "metadata": {
                "selected_candidate_id": candidate_id,
                "post_generation_review_package": {
                    "inspections": [
                        {
                            "status": "manual_review",
                            "verification_state": "unverified",
                            "issue_codes": [{"code": "file_missing"}],
                        }
                    ],
                    "real_review_signal_package": {"issue_summary": {"file_missing": 1}},
                },
            },
        }
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="existing generated submitted MCP projection checkpoint",
            metadata={**planning_metadata, "project_id": "project_doc263_existing_generated"},
        ),
        status=ProductJobStatusValue.GENERATED,
        job_id_value=job_id,
        planning_result=planning,
        generation_result=existing_result,
    )
    job_store.save(record)
    handoff_store.job_store = job_store

    review_calls: list[dict[str, object]] = []

    class _NoProviderRouter:
        def generate(self, request):  # noqa: ANN001
            raise AssertionError("existing generated resume must not call provider")

    runtime = SimpleNamespace(
        generation_router=_NoProviderRouter(),
        scenario_registry=ScenarioRuntime().scenario_registry,
    )
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )

    def fake_attach(existing_record, generation_result, generate_request):  # noqa: ANN001
        asset = existing_record.generation_result.asset_pack.assets[0]
        review_calls.append(
            {
                "output_id": asset.metadata.get("output_id"),
                "file_path": asset.file_path,
                "uri": asset.uri,
            }
        )
        return generation_result.model_copy(
            update={
                "metadata": {
                    **dict(generation_result.metadata),
                    "post_generation_review_package": {
                        "inspections": [
                            {"status": "verified", "verification_state": "verified"}
                        ]
                    },
                }
            }
        )

    monkeypatch.setattr(service, "_attach_post_generation_review", fake_attach)

    original_handoff = handoff_store.get(pending["handoff_id"])
    assert original_handoff is not None
    for field, bad_value in (
        ("nonce", "tampered-nonce"),
        ("prompt_sha256", "0" * 64),
        ("reference_asset_hashes", ["0" * 64]),
        ("reference_semantic_fingerprint", "0" * 64),
        ("rendering_contract_fingerprint", "0" * 64),
        ("artifact_sha256", "0" * 64),
    ):
        mutated_handoff = json.loads(json.dumps(original_handoff))
        mutated_handoff[field] = bad_value
        handoff_store._write(  # noqa: SLF001
            handoff_store._record_path(pending["handoff_id"]),  # noqa: SLF001
            mutated_handoff,
        )
        with pytest.raises(RuntimeError, match="mcp_materialization_output_projection_missing"):
            service._ensure_submitted_body_mcp_projection_for_existing_result(record)  # noqa: SLF001
        handoff_store._write(  # noqa: SLF001
            handoff_store._record_path(pending["handoff_id"]),  # noqa: SLF001
            original_handoff,
        )

    original_metadata = dict(record.request.metadata)
    for key, bad_value in (
        ("professional_character_card_candidate_index", 2),
        ("professional_character_card_candidate_count", 2),
        ("professional_character_card_slot", "body.side_full"),
    ):
        record.request.metadata = {**original_metadata, key: bad_value}
        with pytest.raises(RuntimeError, match="mcp_materialization_output_projection_missing"):
            service._ensure_submitted_body_mcp_projection_for_existing_result(record)  # noqa: SLF001
    record.request.metadata = original_metadata

    wrong_candidate_asset = record.generation_result.asset_pack.assets[0].model_copy(
        update={
            "metadata": {
                **dict(record.generation_result.asset_pack.assets[0].metadata),
                "selected_candidate_id": "candidate_wrong_server_binding",
            }
        }
    )
    record.generation_result = record.generation_result.model_copy(
        update={
            "asset_pack": record.generation_result.asset_pack.model_copy(
                update={"assets": [wrong_candidate_asset]}
            )
        }
    )
    with pytest.raises(RuntimeError, match="mcp_materialization_output_projection_missing"):
        service._ensure_submitted_body_mcp_projection_for_existing_result(record)  # noqa: SLF001
    record.generation_result = existing_result

    # Historical records may not carry the submit-time hashes in job metadata;
    # the submitted server-owned handoff remains the authority for those fields.
    record.request.metadata = {
        **original_metadata,
        "mcp_materialization": {
            "handoff_id": pending["handoff_id"],
            "status": "submitted",
            "generation_channel": "mcp",
            "resume_required": True,
        },
    }
    frozen_generation_plan = planning.generation_plans[0].model_copy(
        update={
            "metadata": {
                **dict(planning.generation_plans[0].metadata),
                "mcp_materialization": dict(record.request.metadata["mcp_materialization"]),
            }
        }
    )
    record.planning_result = planning.model_copy(
        update={"generation_plans": [frozen_generation_plan]}
    )

    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert status.status == ProductJobStatusValue.GENERATED
    assert len(review_calls) == 1
    assert review_calls[0]["output_id"]
    assert review_calls[0]["file_path"]
    assert review_calls[0]["uri"]
    updated = job_store.get(job_id)
    assert updated is not None and updated.generation_result is not None
    projected = updated.generation_result.asset_pack.assets[0]
    assert projected.metadata.get("output_id")
    assert projected.file_path and Path(projected.file_path).is_file()
    assert projected.uri
    assert len(output_store.list_by_job(job_id)) == 1
    assert not updated.generation_result.metadata.get("post_generation_review_recheck_required")

    # A stable verified package remains terminal and must not trigger a second
    # review-only pass on a later exact resume.
    second_status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )
    assert second_status.status == ProductJobStatusValue.GENERATED
    assert len(review_calls) == 1


def test_doc263_existing_generated_body_resume_missing_artifact_is_closed_without_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing generated strict Body results cannot review without a valid handoff artifact."""

    job_id = "job_doc263_existing_generated_missing_artifact"
    operation_id = "visual_asset_doc263_existing_generated_missing_artifact:body_silhouette:body.rear_full:3"
    prompt = "closed Body Silhouette MCP missing submitted artifact"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    body_contract = _doc203_body_frozen_contract_fields()
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "1024x1536",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_generate",
            "input_fidelity": "high",
            "input_fidelity_required": False,
            "size_normalization": "white_matte_contain_to_contract_size",
            **body_contract,
        },
        require_body_rendering_contract=True,
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    submitted_record = handoff_store.get(pending["handoff_id"])
    assert submitted_record is not None
    Path(str(submitted_record["artifact_file"])).unlink()

    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.rear_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 3,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_contract[
                "body_refresh_presentation_intent"
            ],
            "mcp_materialization": {
                "handoff_id": pending["handoff_id"],
                "status": "submitted",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        }
    )
    planning = _minimal_planning_result(job_id, generation_metadata=planning_metadata)
    existing_result = planning.model_copy(
        update={
            "asset_pack": planning.asset_pack.model_copy(
                update={
                    "assets": [
                        planning.asset_pack.assets[0].model_copy(
                            update={
                                "metadata": {
                                    "planning_only": True,
                                    "selected_candidate_id": "candidate_doc263_missing_artifact",
                                    "candidate_metadata": {"planning_only": True},
                                }
                            }
                        )
                    ],
                    "planning_only": False,
                }
            )
        }
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="existing generated missing artifact checkpoint",
            metadata={**planning_metadata, "project_id": "project_doc263_missing_artifact"},
        ),
        status=ProductJobStatusValue.GENERATED,
        job_id_value=job_id,
        planning_result=planning,
        generation_result=existing_result,
    )
    job_store.save(record)
    handoff_store.job_store = job_store
    runtime = SimpleNamespace(
        generation_router=SimpleNamespace(
            generate=lambda request: (_ for _ in ()).throw(AssertionError("provider must not run"))
        ),
        scenario_registry=ScenarioRuntime().scenario_registry,
    )
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )
    review_called = False

    def fake_review(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal review_called
        review_called = True
        return service._status_from_record(record)  # noqa: SLF001

    monkeypatch.setattr(service, "_resume_finalizing_generation_review", fake_review)
    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert status.status == ProductJobStatusValue.BLOCKED
    assert not review_called
    updated = job_store.get(job_id)
    assert updated is not None
    failure = updated.request.metadata.get("generation_lifecycle_failure")
    assert failure["failure_code"] == "mcp_materialization_output_projection_missing"
    assert len(output_store.list_by_job(job_id)) == 0


@pytest.mark.parametrize(
    "initial_status",
    [ProductJobStatusValue.GENERATING, ProductJobStatusValue.BLOCKED],
)
def test_doc263_body_resume_reconciles_submitted_handoff_before_consumer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initial_status: ProductJobStatusValue,
) -> None:
    """A submitted handoff must reconcile the job projection before the GENERATING guard."""

    job_id = "job_doc263_pending_projection"
    operation_id = "visual_asset_doc263_pending_projection:body_silhouette:body.front_full:1"
    prompt = "closed Body Silhouette MCP prompt for projection reconciliation"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")
    rendering_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_generate",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
        **_doc203_body_frozen_contract_fields(),
    }
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract=rendering_contract,
        require_body_rendering_contract=True,
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    assert submitted["status"] == "submitted"

    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        refs=["face_ref_front", "face_ref_side", "face_ref_rear"],
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
            "mcp_materialization": {
                "handoff_id": pending["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
                "nonce": pending["nonce"],
                "prompt_sha256": prompt_sha,
                "reference_asset_hashes": [],
            },
        }
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="pending submitted Body handoff projection",
            metadata={**planning_metadata, "project_id": "project_doc263_pending_projection"},
        ),
        status=initial_status,
        job_id_value=job_id,
        planning_result=_minimal_planning_result(job_id, generation_metadata=planning_metadata),
        generation_result=None,
        balance_estimate={"credits_required": 0},
    )
    job_store.save(record)
    initial_job_count = job_store.count()

    class _RuntimeProbe:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.scenario_registry = ScenarioRuntime().scenario_registry

        def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.calls.append(dict(payload.get("metadata") or {}))
            raise AssertionError("pending submitted Body resume must not re-enter ScenarioRuntime.generate_job")

    runtime = _RuntimeProbe()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )
    consume_calls: list[str] = []

    def fake_consume(current: ProductJobRecord):
        consume_calls.append(current.job_id)
        return None

    monkeypatch.setattr(service, "_consume_submitted_body_mcp_artifact", fake_consume)
    monkeypatch.setattr(service, "_blocked_submitted_body_mcp_resume", lambda current: service._status_from_record(current))

    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert runtime.calls == []
    assert consume_calls == [job_id]
    assert status.status == ProductJobStatusValue.GENERATING
    assert job_store.count() == initial_job_count
    updated = job_store.get(job_id)
    assert updated is not None
    assert updated.request.metadata["mcp_materialization"]["status"] == "submitted"
    assert updated.request.metadata["mcp_materialization"]["handoff_id"] == pending["handoff_id"]


def test_doc263_generating_body_resume_identity_conflict_stays_fail_closed(
    tmp_path: Path,
) -> None:
    """A missing authoritative handoff must not unlock the submitted consumer."""

    job_id = "job_doc263_projection_conflict"
    operation_id = "visual_asset_doc263_projection_conflict:body_silhouette:body.front_full:1"
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")
    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        refs=["face_ref_front", "face_ref_side", "face_ref_rear"],
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
            "mcp_materialization": {
                "handoff_id": "mcp_handoff_missing_authority",
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        }
    )
    job_store.save(
        ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="projection identity conflict",
                metadata=planning_metadata,
            ),
            status=ProductJobStatusValue.GENERATING,
            job_id_value=job_id,
            planning_result=_minimal_planning_result(job_id, generation_metadata=planning_metadata),
            generation_result=None,
            balance_estimate={"credits_required": 0},
        )
    )

    class _RuntimeProbe:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.scenario_registry = ScenarioRuntime().scenario_registry

        def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.calls.append(dict(payload.get("metadata") or {}))
            raise AssertionError("identity-conflicted resume must not enter ScenarioRuntime")

    runtime = _RuntimeProbe()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )
    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert runtime.calls == []
    assert status.status == ProductJobStatusValue.GENERATING
    updated = job_store.get(job_id)
    assert updated is not None
    assert updated.request.metadata["mcp_materialization"]["status"] == "pending"


def test_doc263_ordinary_generating_job_does_not_use_submitted_body_bypass(tmp_path: Path) -> None:
    """The projection is not a general GENERATING-job resume escape hatch."""

    job_id = "job_doc263_ordinary_generating"
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    job_store.save(
        ProductJobRecord(
            request=CreateCreativeJobRequest(user_input="ordinary generating job", metadata={}),
            status=ProductJobStatusValue.GENERATING,
            job_id_value=job_id,
            planning_result=None,
            generation_result=None,
            balance_estimate={"credits_required": 0},
        )
    )

    class _RuntimeProbe:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.scenario_registry = ScenarioRuntime().scenario_registry

        def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.calls.append(dict(payload.get("metadata") or {}))
            raise AssertionError("ordinary generating job must remain behind the existing guard")

    runtime = _RuntimeProbe()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )
    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert runtime.calls == []
    assert status.status == ProductJobStatusValue.GENERATING


def test_doc263_submitted_body_resume_preserves_two_face_identity_reference_projection(
    tmp_path: Path,
) -> None:
    """The real two-face-reference Body envelope must reach the core consumer intact."""

    job_id = "job_doc263_body_two_face_refs"
    operation_id = "visual_asset_eab9d20_body:body_silhouette:body.front_full:1"
    prompt = "closed Body Silhouette MCP prompt with face continuity refs"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    reference_assets = [
        {
            "asset_id": "face_ref_front::portrait_identity_crop",
            "derivative_kind": "portrait_identity_crop",
            "identity_evidence_scope": "feature_detail",
            "sha256": "2" * 64,
        },
        {
            "asset_id": "face_ref_front::portrait_identity_geometry_crop",
            "derivative_kind": "portrait_identity_pose_geometry_crop",
            "identity_evidence_scope": "pose_geometry",
            "sha256": "3" * 64,
        },
    ]

    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")

    class _RecordingHandoffStore(McpMaterializationHandoffStore):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.consume_calls = 0

        def consume(self, handoff_id: str, *, expected_checkpoint=None):  # noqa: ANN001, ANN201
            self.consume_calls += 1
            return super().consume(handoff_id, expected_checkpoint=expected_checkpoint)

    handoff_store = _RecordingHandoffStore(tmp_path / "handoffs")
    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")
    frozen_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
        **_doc203_body_frozen_contract_fields(),
    }
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=reference_assets,
        rendering_contract=frozen_contract,
        require_body_rendering_contract=True,
    )
    reference_hashes = handoff_store._reference_hashes(reference_assets)
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=reference_hashes,
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    assert submitted["status"] == "submitted"
    frozen_handoff = handoff_store.get(pending["handoff_id"])
    assert frozen_handoff is not None
    assert len(frozen_handoff["reference_assets"]) == 2
    assert frozen_handoff["reference_asset_hashes"] == reference_hashes

    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
            "professional_character_card_reference_output_ids": [
                item["asset_id"] for item in reference_assets
            ],
            "reference_assets": reference_assets,
            "real_image_generation": True,
            "llm_brain": {
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": prompt,
                        "review_status": "approved",
                    }
                ]
            },
        }
    )
    materialization = {
        "handoff_id": pending["handoff_id"],
        "nonce": pending["nonce"],
        "status": "submitted",
        "generation_channel": "mcp",
        "resume_required": True,
    }
    planning_metadata["mcp_materialization"] = materialization
    planning = _minimal_planning_result(
        job_id,
        generation_metadata=planning_metadata,
    )
    frozen_generation_plan = planning.generation_plans[0].model_copy(
        update={"candidate_count": 3, "metadata": planning_metadata}
    )
    planning = planning.model_copy(update={"generation_plans": [frozen_generation_plan]})
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="body submitted consumer with two face identity refs",
            metadata={
                **planning_metadata,
                "project_id": "project_doc263_body_two_face_refs",
            },
        ),
        status=ProductJobStatusValue.BLOCKED,
        job_id_value=job_id,
        planning_result=planning,
        generation_result=None,
        balance_estimate={"credits_required": 0},
    )
    job_store.save(record)
    initial_job_count = job_store.count()

    class _SubmittedMcpConsumer:
        def __init__(self) -> None:
            self.requests: list[dict] = []

        def generate(self, request):  # noqa: ANN001, ANN201
            self.requests.append(dict(request.metadata))
            projected_refs = list(request.metadata.get("reference_assets") or [])
            assert [
                (item.get("asset_id"), item.get("sha256"))
                for item in projected_refs
            ] == [
                (item.get("asset_id"), item.get("sha256"))
                for item in reference_assets
            ]
            assert request.metadata["professional_character_card_candidate_count"] == 3
            assert request.metadata["professional_character_card_candidate_index"] == 1
            assert request.metadata["mcp_operation_id"] == operation_id
            handoff_id = request.metadata["mcp_materialization"]["handoff_id"]
            candidate_id = "candidate_doc263_body_two_face_refs"
            output_id = "v3_output_2632face000000000001"
            expected_checkpoint = {
                "job_id": job_id,
                "candidate_id": candidate_id,
                "output_id": output_id,
            }
            artifact = handoff_store.consume(
                handoff_id,
                expected_checkpoint=expected_checkpoint,
            )
            output = output_store.save_base64_output(
                job_id=job_id,
                candidate_id=candidate_id,
                asset_id=request.generation_plan.asset_id,
                provider="codex_builtin_imagegen",
                model="gpt-image-2",
                encoded_image=artifact["artifact_base64"],
                output_id=output_id,
                mime_type=artifact["artifact_mime_type"],
                output_format=artifact["artifact_format"],
                metadata={"mcp_handoff_id": handoff_id},
            )
            handoff_store.mark_output_checkpoint(
                handoff_id,
                job_id=job_id,
                candidate_id=candidate_id,
                output_id=output.output_id,
                artifact_sha256=artifact["artifact_sha256"],
            )
            return SimpleNamespace(
                candidates=[
                    SimpleNamespace(
                        candidate_id=candidate_id,
                        file_path=output.file_path,
                        uri=output.download_url,
                        provider="codex_builtin_imagegen",
                        prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
                        metadata={
                            "output_id": output.output_id,
                            "mcp_materialization": {
                                "handoff_id": handoff_id,
                                "expected_checkpoint": expected_checkpoint,
                            },
                        },
                    )
                ],
                provider_metadata={"generation_channel": "mcp"},
            )

    class _Runtime:
        def __init__(self) -> None:
            self.scenario_registry = ScenarioRuntime().scenario_registry
            self.generation_router = _SubmittedMcpConsumer()
            self.generate_job_calls = 0

        def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.generate_job_calls += 1
            raise AssertionError("submitted Body resume must not re-enter ScenarioRuntime.generate_job")

    runtime = _Runtime()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )
    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert runtime.generate_job_calls == 0
    assert len(runtime.generation_router.requests) == 1
    assert handoff_store.consume_calls == 1
    assert status.status == ProductJobStatusValue.GENERATED
    assert job_store.count() == initial_job_count
    assert len(output_store.list_by_job(job_id)) == 1
    updated = job_store.get(job_id)
    assert updated is not None
    assert updated.request.metadata["professional_character_card_candidate_count"] == 3
    assert updated.request.metadata["professional_character_card_candidate_index"] == 1
    assert updated.request.metadata["mcp_operation_id"] == operation_id
    assert updated.generation_result is not None
    assert "post_generation_review_package" in updated.generation_result.metadata
    resumed_handoff = handoff_store.get(pending["handoff_id"])
    assert resumed_handoff is not None
    assert resumed_handoff["status"] == "job_checkpointed"
    assert resumed_handoff["reference_asset_hashes"] == reference_hashes
    assert resumed_handoff["rendering_contract"]["body_refresh_presentation_intent"] == body_intent


@pytest.mark.parametrize(
    "mismatch",
    [
        "planning_result_missing",
        "handoff_status",
        "handoff_nonce",
        "handoff_prompt",
        "handoff_reference",
        "handoff_body_contract",
        "handoff_presentation_intent",
        "planning_identity",
    ],
)
def test_doc263_submitted_body_resume_contract_mismatch_fails_closed(
    tmp_path: Path,
    mismatch: str,
) -> None:
    """A malformed submitted Body resume never falls back into generation-stage Brain."""

    job_id = f"job_doc263_contract_{mismatch}"
    operation_id = f"visual_asset_doc263_contract:body_silhouette:body.front_full:1:{mismatch}"
    prompt = "closed Body Silhouette MCP prompt"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )
    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")

    frozen_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_generate",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
        **_doc203_body_frozen_contract_fields(),
    }

    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")

    class _MismatchHandoffStore(McpMaterializationHandoffStore):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.consume_calls = 0

        def get(self, handoff_id: str):  # noqa: ANN201
            payload = super().get(handoff_id)
            if not isinstance(payload, dict):
                return payload
            mutated = dict(payload)
            if mismatch == "handoff_status":
                mutated["status"] = "pending"
            elif mismatch == "handoff_nonce":
                mutated["nonce"] = "wrong_nonce"
            elif mismatch == "handoff_prompt":
                mutated["canonical_prompt"] = "different frozen prompt"
            elif mismatch == "handoff_reference":
                mutated["reference_asset_hashes"] = ["different_reference_hash"]
            elif mismatch == "handoff_body_contract":
                contract = dict(mutated.get("rendering_contract") or {})
                contract.pop("body_silhouette_mcp_materialization_channel_contract", None)
                mutated["rendering_contract"] = contract
            elif mismatch == "handoff_presentation_intent":
                contract = dict(mutated.get("rendering_contract") or {})
                contract["body_refresh_presentation_intent"] = {
                    "schema_version": "body_refresh_presentation_intent_v1",
                    "top_presentation": "unspecified",
                    "bottom_presentation": "unspecified",
                    "footwear_presentation": "unspecified",
                }
                mutated["rendering_contract"] = contract
            return mutated

        def consume(self, handoff_id: str, *, expected_checkpoint=None):  # noqa: ANN001, ANN201
            self.consume_calls += 1
            return super().consume(handoff_id, expected_checkpoint=expected_checkpoint)

    handoff_store = _MismatchHandoffStore(tmp_path / "handoffs")
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract=frozen_contract,
        require_body_rendering_contract=True,
    )
    handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )

    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
            "real_image_generation": True,
            "llm_brain": {
                "canonical_provider_prompts": [
                    {"output_index": 1, "prompt": prompt, "review_status": "approved"}
                ]
            },
        }
    )
    materialization = {
        "handoff_id": pending["handoff_id"],
        "status": "submitted",
        "generation_channel": "mcp",
        "resume_required": True,
        "nonce": pending["nonce"],
    }
    planning_generation_metadata = dict(planning_metadata)
    if mismatch == "planning_identity":
        planning_generation_metadata["mcp_operation_id"] = "different-operation"
    planning_result = (
        None
        if mismatch == "planning_result_missing"
        else _minimal_planning_result(job_id, generation_metadata=planning_generation_metadata)
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="submitted Body contract mismatch",
            metadata={**planning_metadata, "mcp_materialization": materialization},
        ),
        status=ProductJobStatusValue.BLOCKED,
        job_id_value=job_id,
        planning_result=planning_result,
        generation_result=None,
        balance_estimate={"credits_required": 0},
    )
    job_store.save(record)

    class _ProbeRuntime:
        def __init__(self) -> None:
            self.calls = 0
            self.scenario_registry = ScenarioRuntime().scenario_registry
            self.generation_router = GenerationRouter(
                mcp_provider=McpMaterializationProvider(
                    output_store=output_store,
                    handoff_store=handoff_store,
                )
            )

        def generate_job(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN201
            self.calls += 1
            raise AssertionError("invalid submitted Body resume must not fall back to generate-stage runtime")

    runtime = _ProbeRuntime()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )
    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert status.status == ProductJobStatusValue.BLOCKED
    assert runtime.calls == 0
    assert handoff_store.consume_calls == 0
    assert job_store.count() == 1
    updated = job_store.get(job_id)
    assert updated is not None
    assert updated.generation_result is None
    expected_failure_code = (
        "submitted_resume_planning_result_missing"
        if mismatch == "planning_result_missing"
        else "mcp_materialization_submitted_resume_contract_invalid"
    )
    assert updated.request.metadata["generation_lifecycle_failure"]["failure_code"] == expected_failure_code


def test_doc228_exact_body_handoff_resume_accepts_real_productapi_contract_envelope(
    tmp_path: Path,
) -> None:
    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    operation_id = "visual_asset_doc228:body_silhouette:body.front_full:2"
    prompt = "body silhouette frozen handoff prompt"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")
    frozen_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_generate",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
        **_doc203_body_frozen_contract_fields(),
    }
    metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 2,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
        }
    )
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    handoff = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract=frozen_contract,
        require_body_rendering_contract=True,
    )
    handoffs.submit(
        handoff["handoff_id"],
        nonce=handoff["nonce"],
        prompt_sha256=handoff["prompt_sha256"],
        reference_asset_hashes=handoff["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoffs, handoff),
    )

    current_request = _minimal_request(metadata=metadata)
    current_app_request, _provider_name, current_reference_assets = provider._build_app_request(current_request)
    current_context = current_app_request.prompt_plan.variables["mcp_materialization_context"]
    explicit_metadata = {
        **metadata,
        "mcp_materialization": {
            "handoff_id": handoff["handoff_id"],
            "status": "failed",
            "failure_code": "mcp_materialization_rendering_contract_mismatch",
            "generation_channel": "mcp",
            "resume_required": True,
        },
    }
    explicit_request = _minimal_request(metadata=explicit_metadata)

    assert provider._is_character_card_body_mcp_materialization(explicit_metadata) is True  # noqa: SLF001
    assert provider._is_strict_character_card_body_refresh(explicit_metadata) is True  # noqa: SLF001
    current_rendering_contract = current_context["rendering_contract"]
    safe_diff = {
        key: {
            "stored_type": type(frozen_contract.get(key)).__name__,
            "current_type": type(current_rendering_contract.get(key)).__name__,
            "stored_closed_value": frozen_contract.get(key),
            "current_closed_value": current_rendering_contract.get(key),
        }
        for key in sorted(set(frozen_contract) | set(current_rendering_contract))
        if frozen_contract.get(key) != current_rendering_contract.get(key)
    }
    assert safe_diff == {
        "input_fidelity": {
            "stored_type": "str",
            "current_type": "NoneType",
            "stored_closed_value": "high",
            "current_closed_value": None,
        },
        "quality": {
            "stored_type": "str",
            "current_type": "str",
            "stored_closed_value": "high",
            "current_closed_value": "medium",
        },
    }
    assert current_rendering_contract["body_silhouette_mcp_materialization_channel_contract"] == (
        frozen_contract["body_silhouette_mcp_materialization_channel_contract"]
    )
    assert current_rendering_contract["body_refresh_presentation_intent"] == body_intent
    assert provider._strict_body_handoff_resume_contract_compatible(  # noqa: SLF001
        explicit_metadata,
        frozen_rendering_contract=frozen_contract,
        current_rendering_contract=current_rendering_contract,
    ) is True

    resumed = provider._existing_mcp_handoff_context(  # noqa: SLF001
        explicit_request,
        current_context=current_context,
        current_reference_assets=current_reference_assets,
        current_rendering_contract=current_rendering_contract,
    )

    assert resumed is not None
    assert resumed["handoff_id"] == handoff["handoff_id"]
    assert resumed["rendering_contract"]["body_refresh_presentation_intent"] == body_intent
    non_envelope_drift = dict(current_rendering_contract)
    non_envelope_drift["size"] = "512x512"
    assert provider._strict_body_handoff_resume_contract_compatible(  # noqa: SLF001
        explicit_metadata,
        frozen_rendering_contract=frozen_contract,
        current_rendering_contract=non_envelope_drift,
    ) is False


def test_doc228_service_plain_generated_or_blocked_with_result_does_not_recheck_or_regenerate(
    tmp_path: Path,
) -> None:
    for status_value in (ProductJobStatusValue.GENERATED, ProductJobStatusValue.BLOCKED):
        job_id = f"job_doc228_plain_{status_value.value}"
        output_id = (
            "v3_output_11111111111111111111"
            if status_value == ProductJobStatusValue.GENERATED
            else "v3_output_22222222222222222222"
        )
        candidate_id = f"candidate_doc228_plain_{status_value.value}"
        timeout_package = _provider_timeout_review_package(
            job_id=job_id,
            output_id=output_id,
            candidate_id=candidate_id,
        )
        result = _with_review_package(
            _attach_output_checkpoint(
                _minimal_planning_result(job_id),
                output_id=output_id,
                candidate_id=candidate_id,
            ),
            timeout_package,
        )
        job_store = PersistentProductJobStore(tmp_path / f"jobs_{status_value.value}")
        output_store = V3GeneratedOutputStore(tmp_path / f"outputs_{status_value.value}")
        output_store.save_base64_output(
            job_id=job_id,
            candidate_id=candidate_id,
            asset_id=result.asset_pack.assets[0].asset_id,
            provider="mcp_materialization",
            model="gpt-image-2",
            encoded_image=base64.b64encode(_png_bytes()).decode("ascii"),
            output_id=output_id,
        )
        job_store.save(
            ProductJobRecord(
                request=CreateCreativeJobRequest(
                    user_input="plain generated resume",
                    metadata={"project_id": "project_doc228"},
                ),
                status=status_value,
                job_id_value=job_id,
                planning_result=result,
                generation_result=result,
            )
        )

        class _NoRuntime:
            calls = 0

            def generate_job(self, *_args, **_kwargs):  # noqa: ANN001, ANN201
                self.calls += 1
                raise AssertionError("plain completed resume must be idempotent")

        class _NoVision:
            calls = 0

            def inspect(self, *_args, **_kwargs):  # noqa: ANN001, ANN201
                self.calls += 1
                raise AssertionError("plain completed resume must not re-run Vision")

        service = V3ProductApiService(
            scenario_runtime=_NoRuntime(),  # type: ignore[arg-type]
            job_store=job_store,
            output_store=output_store,
            vision_inspector=_NoVision(),  # type: ignore[arg-type]
        )

        status = service.generate_asset_series(job_id, {"quality_mode": "strict", "metadata": {}})

        updated = job_store.get(job_id)
        assert status.status == status_value
        assert _NoRuntime.calls == 0
        assert _NoVision.calls == 0
        assert updated is not None
        assert updated.generation_result is not None
        assert updated.generation_result.metadata["post_generation_review_package"] == timeout_package


def test_doc228_host_reroutes_mcp_review_pending_to_review_only_resume_without_new_job() -> None:
    job_id = "job_doc228_host_timeout"
    output_id = "v3_output_33333333333333333333"
    candidate_id = "candidate_doc228_host"
    handoff_id = "mcp_handoff_doc228_host"
    operation_id = "people_doc228:expression_set:expression.laugh:2:round5"

    class _OutputStore:
        def __init__(self) -> None:
            self.records = [
                SimpleNamespace(
                    output_id=output_id,
                    candidate_id=candidate_id,
                    metadata={
                        "provider_prompt_sha256": "sha256:doc228",
                        "prompt_compilation_id": "prompt_doc228",
                        "provider_reference_image_count": 2,
                        "prompt_reference_parity": {"verified": True},
                        "reference_evidence_parity": {"verified": True},
                    },
                )
            ]

        def list_by_job(self, _job_id):  # noqa: ANN001, ANN201
            return list(self.records)

    class _JobStore:
        def __init__(self, record) -> None:  # noqa: ANN001
            self.record = record

        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [self.record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [self.record]

        def save(self, record):  # noqa: ANN001, ANN201
            self.record = record
            return record

    class _ResumeReviewService:
        visual_asset_catalog = None

        def __init__(self) -> None:
            timeout_package = _provider_timeout_review_package(
                job_id=job_id,
                output_id=output_id,
                candidate_id=candidate_id,
            )
            generation = _with_review_package(
                _attach_output_checkpoint(
                    _minimal_planning_result(
                        job_id,
                        generation_metadata=_current_character_card_planning_metadata(
                            operation_id=operation_id,
                            handoff={
                                "handoff_id": handoff_id,
                                "status": "job_checkpointed",
                                "generation_channel": "mcp",
                            },
                        ),
                    ),
                    output_id=output_id,
                    candidate_id=candidate_id,
                    handoff_id=handoff_id,
                ),
                timeout_package,
            )
            self.record = SimpleNamespace(
                job_id=job_id,
                status=ProductJobStatusValue.GENERATED,
                planning_result=generation,
                generation_result=generation,
                request=SimpleNamespace(
                    metadata={
                        "project_id": "project_doc228",
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.laugh",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": operation_id,
                        "mcp_materialization": {
                            "handoff_id": handoff_id,
                            "status": "job_checkpointed",
                            "generation_channel": "mcp",
                        },
                    }
                ),
            )
            self.created = 0
            self.generated_calls = []
            self.output_store = _OutputStore()
            self.job_store = _JobStore(self.record)
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda _handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "job_checkpointed",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                }
            )

        def create_professional_character_card_stage_job(self, *_args, **_kwargs):
            self.created += 1
            raise AssertionError("mcp_review_pending must resume the same job instead of creating a new one")

        def generate_job(self, job_id_arg, request):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            self.generated_calls.append((job_id_arg, request))
            assert request["metadata"]["_v3_resume_finalizing_review"] is True
            package = {
                "package_id": "review_doc228_host_pass",
                "job_id": job_id,
                "inspections": [
                    {
                        "inspection_id": "visual_inspection_doc228_host_pass",
                        "job_id": job_id,
                        "candidate_id": candidate_id,
                        "output_id": output_id,
                        "mode": "hybrid",
                        "status": "pass",
                        "verification_state": "verified",
                        "confidence": 0.94,
                        "score_card": _laugh_pass_score_card(),
                        "detected_issues": [],
                        "issue_codes": [],
                    }
                ],
                "metadata": {"post_generation": True, "inspection_count": 1},
            }
            self.record.generation_result = _with_review_package(self.record.generation_result, package)
            self.record.status = ProductJobStatusValue.GENERATED
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.GENERATED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id_arg):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            return self.record

    service = _ResumeReviewService()
    request = CharacterCardCandidateRequest(
        project_id="project_doc228",
        people_asset_id="people_doc228",
        card_version_id="card_doc228",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=handoff_id,
    )

    candidate = ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert service.created == 0
    assert service.generated_calls
    assert candidate.output_id == output_id
    assert len(service.output_store.list_by_job(job_id)) == 1


def test_doc228_review_only_resume_syncs_durable_job_checkpoint_and_review_pending(
    tmp_path: Path,
) -> None:
    job_id = "job_doc228_sync_checkpoint"
    output_id = "v3_output_44444444444444444444"
    candidate_id = "candidate_doc228_sync"
    operation_id = "people_doc228:expression_set:expression.laugh:2:round5"
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    prompt = _current_laugh_handoff_prompt()
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={"size": "32x48", "output_format": "png", "count": 1},
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=pending["prompt_sha256"],
        reference_asset_hashes=pending["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    consumed = handoff_store.consume(submitted["handoff_id"])
    handoff_store.mark_output_checkpoint(
        pending["handoff_id"],
        job_id=job_id,
        candidate_id=candidate_id,
        output_id=output_id,
        artifact_sha256=consumed["artifact_sha256"],
    )
    handoff_store.mark_job_checkpoint(
        pending["handoff_id"],
        job_id=job_id,
        candidate_id=candidate_id,
        output_id=output_id,
        generation_result_id=f"planning_{job_id}",
    )
    reloaded_handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    assert reloaded_handoff_store.get(pending["handoff_id"])["status"] == "job_checkpointed"

    result, record, _timeout_package = _doc228_generated_timeout_record(
        job_id=job_id,
        output_id=output_id,
        candidate_id=candidate_id,
        operation_id=operation_id,
        handoff_id=pending["handoff_id"],
        request_handoff_status="pending",
    )
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    output_store.save_base64_output(
        job_id=job_id,
        candidate_id=candidate_id,
        asset_id=result.asset_pack.assets[0].asset_id,
        provider="mcp_materialization",
        model="gpt-image-2",
        encoded_image=base64.b64encode(_png_bytes()).decode("ascii"),
        output_id=output_id,
    )
    job_store.save(record)

    class _NoRuntime:
        calls = 0

        def generate_job(self, *_args, **_kwargs):  # noqa: ANN001, ANN201
            self.calls += 1
            raise AssertionError("review-only timeout resume must not regenerate")

    class _TimeoutVision:
        calls = 0

        def inspect(self, resolution, metadata=None):  # noqa: ANN001, ANN201
            self.calls += 1
            return VisualInspectionReport(
                inspection_id="visual_inspection_doc228_timeout_again",
                project_id="project_doc228",
                job_id=job_id,
                candidate_id=candidate_id,
                output_id=resolution.output_id,
                mode="hybrid",
                status="manual_review",
                verification_state="unverified",
                confidence=0.35,
                score_card={"same_person_readability": 0.94, "overall": 0.5},
                detected_issues=[
                    {
                        "code": "provider_timeout",
                        "severity": "low",
                        "retryable": False,
                        "confidence": 0.4,
                    }
                ],
                evidence={"provider_error": "Vision inspection timed out after 90.00 seconds."},
            )

    timeout_vision = _TimeoutVision()
    service = V3ProductApiService(
        scenario_runtime=_NoRuntime(),  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        vision_inspector=timeout_vision,  # type: ignore[arg-type]
        mcp_materialization_store=reloaded_handoff_store,
    )

    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    updated = job_store.get(job_id)
    assert status.status == ProductJobStatusValue.BLOCKED
    assert _NoRuntime.calls == 0
    assert timeout_vision.calls == 1
    assert updated is not None
    assert updated.request.metadata["mcp_materialization"]["status"] == "job_checkpointed"
    assert updated.request.metadata["mcp_review_status"] == {
        "status": "pending",
        "reason_code": "provider_timeout",
        "handoff_id": pending["handoff_id"],
        "output_id": output_id,
        "candidate_id": candidate_id,
        "review_owner": "v3_shared_visual_cluster",
    }
    assert reloaded_handoff_store.get(pending["handoff_id"])["status"] == "job_checkpointed"
    reloaded_job = PersistentProductJobStore(tmp_path / "jobs").get(job_id)
    assert reloaded_job is not None
    assert reloaded_job.request.metadata["mcp_materialization"]["status"] == "job_checkpointed"
    assert reloaded_job.request.metadata["mcp_review_status"]["status"] == "pending"
    assert len(output_store.list_by_job(job_id)) == 1


@pytest.mark.parametrize(
    ("checkpoint_patch", "expected_reason"),
    [
        ({"job_id": "job_doc228_wrong"}, "mcp_materialization_checkpoint_mismatch"),
        ({"candidate_id": "candidate_doc228_wrong"}, "mcp_materialization_checkpoint_mismatch"),
        ({"output_id": "v3_output_66666666666666666666"}, "mcp_materialization_checkpoint_mismatch"),
        ({"generation_result_id": "generation_result_wrong"}, "mcp_materialization_checkpoint_mismatch"),
        ({"operation_id": ""}, "mcp_materialization_checkpoint_mismatch"),
    ],
)
def test_doc228_review_only_resume_rejects_checkpoint_identity_mismatch(
    tmp_path: Path,
    checkpoint_patch: dict[str, str],
    expected_reason: str,
) -> None:
    job_id = "job_doc228_identity_mismatch"
    output_id = "v3_output_77777777777777777777"
    candidate_id = "candidate_doc228_identity"
    handoff_id = "mcp_handoff_doc228_identity"
    operation_id = "people_doc228:expression_set:expression.laugh:2:round5"
    result, record, _timeout_package = _doc228_generated_timeout_record(
        job_id=job_id,
        output_id=output_id,
        candidate_id=candidate_id,
        operation_id=operation_id,
        handoff_id=handoff_id,
        request_handoff_status="pending",
    )
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    output_store.save_base64_output(
        job_id=job_id,
        candidate_id=candidate_id,
        asset_id=result.asset_pack.assets[0].asset_id,
        provider="mcp_materialization",
        model="gpt-image-2",
        encoded_image=base64.b64encode(_png_bytes()).decode("ascii"),
        output_id=output_id,
    )
    job_store.save(record)
    job_checkpoint = {
        "status": "job_checkpointed",
        "operation_id": operation_id,
        "handoff_id": handoff_id,
        "job_id": job_id,
        "candidate_id": candidate_id,
        "output_id": output_id,
        "generation_result_id": result.planning_result_id,
        **checkpoint_patch,
    }

    class _MismatchHandoffStore:
        def get(self, _handoff_id):  # noqa: ANN001, ANN201
            return {
                "handoff_id": handoff_id,
                "status": "job_checkpointed",
                "generation_channel": "mcp",
                "job_checkpoint": job_checkpoint,
                "mcp_checkpoint": dict(job_checkpoint),
            }

    class _NoRuntime:
        calls = 0

        def generate_job(self, *_args, **_kwargs):  # noqa: ANN001, ANN201
            self.calls += 1
            raise AssertionError("checkpoint mismatch must not regenerate")

    class _VisionPass:
        calls = 0

        def inspect(self, resolution, metadata=None):  # noqa: ANN001, ANN201
            self.calls += 1
            return VisualInspectionReport(
                inspection_id="visual_inspection_doc228_mismatch_pass",
                project_id="project_doc228",
                job_id=job_id,
                candidate_id=candidate_id,
                output_id=resolution.output_id,
                mode="hybrid",
                status="pass",
                verification_state="verified",
                confidence=0.94,
                score_card=_laugh_pass_score_card(),
                detected_issues=[],
            )

    vision = _VisionPass()
    service = V3ProductApiService(
        scenario_runtime=_NoRuntime(),  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        vision_inspector=vision,  # type: ignore[arg-type]
        mcp_materialization_store=_MismatchHandoffStore(),  # type: ignore[arg-type]
    )

    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    updated = job_store.get(job_id)
    assert status.status == ProductJobStatusValue.BLOCKED
    assert _NoRuntime.calls == 0
    assert vision.calls == 1
    assert updated is not None
    assert updated.request.metadata["mcp_review_status"]["reason_code"] == expected_reason
    assert updated.request.metadata["mcp_materialization"]["status"] == "pending"


def test_doc228_host_keeps_review_timeout_resumable_after_second_timeout() -> None:
    job_id = "job_doc228_host_timeout_again"
    output_id = "v3_output_55555555555555555555"
    candidate_id = "candidate_doc228_again"
    handoff_id = "mcp_handoff_doc228_again"
    operation_id = "people_doc228:expression_set:expression.laugh:2:round5"

    class _OutputStore:
        def list_by_job(self, _job_id):  # noqa: ANN001, ANN201
            return [
                SimpleNamespace(
                    output_id=output_id,
                    candidate_id=candidate_id,
                    metadata={
                        "provider_prompt_sha256": "sha256:doc228",
                        "prompt_compilation_id": "prompt_doc228",
                        "provider_reference_image_count": 2,
                        "prompt_reference_parity": {"verified": True},
                        "reference_evidence_parity": {"verified": True},
                    },
                )
            ]

    class _Store:
        def __init__(self, record) -> None:  # noqa: ANN001
            self.record = record

        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [self.record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [self.record]

        def save(self, record):  # noqa: ANN001, ANN201
            self.record = record
            return record

    class _TimeoutAgainService:
        visual_asset_catalog = None

        def __init__(self) -> None:
            generation = _with_review_package(
                _attach_output_checkpoint(
                    _minimal_planning_result(
                        job_id,
                        generation_metadata=_current_character_card_planning_metadata(
                            operation_id=operation_id,
                            handoff={
                                "handoff_id": handoff_id,
                                "status": "job_checkpointed",
                                "generation_channel": "mcp",
                            },
                        ),
                    ),
                    output_id=output_id,
                    candidate_id=candidate_id,
                    handoff_id=handoff_id,
                ),
                _provider_timeout_review_package(
                    job_id=job_id,
                    output_id=output_id,
                    candidate_id=candidate_id,
                ),
            )
            self.record = SimpleNamespace(
                job_id=job_id,
                status=ProductJobStatusValue.GENERATED,
                planning_result=generation,
                generation_result=generation,
                request=SimpleNamespace(
                    metadata={
                        "project_id": "project_doc228",
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.laugh",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": operation_id,
                        "mcp_materialization": {
                            "handoff_id": handoff_id,
                            "status": "job_checkpointed",
                            "generation_channel": "mcp",
                        },
                    }
                ),
            )
            self.output_store = _OutputStore()
            self.job_store = _Store(self.record)
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda _handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "job_checkpointed",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                }
            )

        def create_professional_character_card_stage_job(self, *_args, **_kwargs):
            raise AssertionError("review timeout resume must not create a new job")

        def generate_job(self, job_id_arg, request):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            assert request["metadata"]["_v3_resume_finalizing_review"] is True
            self.record.status = ProductJobStatusValue.BLOCKED
            self.record.request.metadata = {
                **dict(self.record.request.metadata),
                "mcp_review_status": {
                    "status": "pending",
                    "reason_code": "provider_timeout",
                    "handoff_id": handoff_id,
                    "output_id": output_id,
                    "candidate_id": candidate_id,
                    "review_owner": "v3_shared_visual_cluster",
                },
            }
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id_arg):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            return self.record

    request = CharacterCardCandidateRequest(
        project_id="project_doc228",
        people_asset_id="people_doc228",
        card_version_id="card_doc228",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=handoff_id,
    )

    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        ProductApiAnchorPackPreparationHost(_TimeoutAgainService()).generate(request)  # type: ignore[arg-type]

    assert exc_info.value.failure_code == "mcp_review_pending"
    assert exc_info.value.mcp_handoff_id == handoff_id
    assert exc_info.value.output_id == output_id
    assert exc_info.value.candidate_id == candidate_id


def test_doc230_host_reuses_job_checkpoint_when_planning_reference_projection_is_stale() -> None:
    job_id = "job_doc230_real_review_only"
    output_id = "v3_output_doc230_existing"
    candidate_id = "candidate_doc230_existing"
    handoff_id = "mcp_handoff_doc230_existing"
    operation_id = "people_doc230:expression_set:expression.laugh:2:round5"

    class _OutputStore:
        def __init__(self) -> None:
            self.records = [
                SimpleNamespace(
                    output_id=output_id,
                    candidate_id=candidate_id,
                    metadata={
                        "provider_prompt_sha256": "sha256:doc230",
                        "prompt_compilation_id": "prompt_doc230",
                        "provider_reference_image_count": 3,
                        "reference_asset_count": 3,
                        "provider_reference_assets": _current_expression_reference_assets(),
                        "prompt_reference_parity": {"verified": True},
                        "reference_evidence_parity": {"verified": True},
                    },
                )
            ]

        def list_by_job(self, _job_id):  # noqa: ANN001, ANN201
            return list(self.records)

    stale_planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        handoff={
            "handoff_id": handoff_id,
            "status": "job_checkpointed",
            "generation_channel": "mcp",
        },
    )
    # Real post-Doc229 evidence: the old job/output is valid and the durable
    # handoff is authoritative, but the frozen planning projection only kept the
    # logical face.front id and lacks the newer full-frame/card-framing fields.
    stale_planning_metadata["professional_anchor_reference_assets"] = [
        {"asset_id": "front_winner"}
    ]

    timeout_package = _provider_timeout_review_package(
        job_id=job_id,
        output_id=output_id,
        candidate_id=candidate_id,
    )
    generation = _with_review_package(
        _attach_output_checkpoint(
            _minimal_planning_result(
                job_id,
                generation_metadata=stale_planning_metadata,
            ),
            output_id=output_id,
            candidate_id=candidate_id,
            handoff_id=handoff_id,
            provider_prompt_sha256="sha256:doc230",
            prompt_compilation_id="prompt_doc230",
        ),
        timeout_package,
    )
    record = SimpleNamespace(
        job_id=job_id,
        status=ProductJobStatusValue.BLOCKED,
        planning_result=generation,
        generation_result=generation,
        request=SimpleNamespace(
            metadata={
                "project_id": "project_doc230",
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": handoff_id,
                    "status": "job_checkpointed",
                    "generation_channel": "mcp",
                    "resume_required": True,
                    "job_checkpoint": {
                        "status": "job_checkpointed",
                        "operation_id": operation_id,
                        "handoff_id": handoff_id,
                        "job_id": job_id,
                        "candidate_id": candidate_id,
                        "output_id": output_id,
                        "generation_result_id": generation.planning_result_id,
                    },
                },
                "mcp_review_status": {
                    "status": "pending",
                    "reason_code": "provider_timeout",
                    "handoff_id": handoff_id,
                    "output_id": output_id,
                    "candidate_id": candidate_id,
                    "review_owner": "v3_shared_visual_cluster",
                },
            }
        ),
    )

    class _JobStore:
        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [record]

        def save(self, new_record):  # noqa: ANN001, ANN201
            return new_record

    class _ResumeReviewService:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created = 0
            self.generated_calls = []
            self.output_store = _OutputStore()
            self.job_store = _JobStore()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda _handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "job_checkpointed",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                    "reference_semantic_fingerprint": "semantic_doc230",
                    "rendering_contract_fingerprint": "rendering_doc230",
                    "job_checkpoint": {
                        "status": "job_checkpointed",
                        "operation_id": operation_id,
                        "handoff_id": handoff_id,
                        "job_id": job_id,
                        "candidate_id": candidate_id,
                        "output_id": output_id,
                        "generation_result_id": generation.planning_result_id,
                    },
                }
            )

        def create_professional_character_card_stage_job(self, *_args, **_kwargs):
            self.created += 1
            raise AssertionError("review-only must reuse the checkpointed job, not create a new job")

        def generate_job(self, job_id_arg, request):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            self.generated_calls.append((job_id_arg, request))
            assert request["metadata"]["_v3_resume_finalizing_review"] is True
            package = {
                "package_id": "review_doc230_host_pass",
                "job_id": job_id,
                "inspections": [
                    {
                        "inspection_id": "visual_inspection_doc230_host_pass",
                        "job_id": job_id,
                        "candidate_id": candidate_id,
                        "output_id": output_id,
                        "mode": "hybrid",
                        "status": "pass",
                        "verification_state": "verified",
                        "confidence": 0.94,
                        "score_card": _laugh_pass_score_card(),
                        "detected_issues": [],
                        "issue_codes": [],
                    }
                ],
                "metadata": {"post_generation": True, "inspection_count": 1},
            }
            record.generation_result = _with_review_package(record.generation_result, package)
            record.status = ProductJobStatusValue.GENERATED
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.GENERATED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id_arg):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            return record

    service = _ResumeReviewService()
    request = CharacterCardCandidateRequest(
        project_id="project_doc230",
        people_asset_id="people_doc230",
        card_version_id="card_doc230",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=handoff_id,
    )

    candidate = ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert service.created == 0
    assert service.generated_calls[0][0] == job_id
    assert candidate.output_id == output_id
    assert candidate.candidate_id == candidate_id


def test_doc230_character_host_preserves_checkpoint_mismatch_failure_code() -> None:
    job_id = "job_doc230_checkpoint_mismatch"
    handoff_id = "mcp_handoff_doc230_mismatch"
    operation_id = "people_doc230:expression_set:expression.laugh:2:round5"

    class _JobStore:
        def save(self, record):  # noqa: ANN001, ANN201
            return record

    class _MismatchService:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.output_store = SimpleNamespace()
            self.job_store = _JobStore()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda _handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "job_checkpointed",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                    "job_checkpoint": {
                        "status": "job_checkpointed",
                        "operation_id": operation_id,
                        "handoff_id": handoff_id,
                        "job_id": "job_doc230_different",
                        "candidate_id": "candidate_doc230_different",
                        "output_id": "v3_output_doc230_different",
                        "generation_result_id": "generation_result_doc230_different",
                    },
                }
            )
            self.record = SimpleNamespace(
                job_id=job_id,
                status=ProductJobStatusValue.PLANNED,
                planning_result=_minimal_planning_result(
                    job_id,
                    generation_metadata=_current_character_card_planning_metadata(
                        operation_id=operation_id,
                        handoff={"handoff_id": handoff_id, "status": "pending"},
                    ),
                ),
                generation_result=None,
                request=SimpleNamespace(
                    metadata={
                        "project_id": "project_doc230",
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.laugh",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": operation_id,
                        "mcp_materialization": {
                            "handoff_id": handoff_id,
                            "status": "pending",
                            "generation_channel": "mcp",
                            "resume_required": True,
                        },
                    }
                ),
            )

        def create_professional_character_card_stage_job(self, *_args, **_kwargs):
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id_arg, _request):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            self.record.request.metadata["mcp_materialization"] = {
                "handoff_id": handoff_id,
                "status": "job_checkpointed",
                "generation_channel": "mcp",
                "resume_required": True,
                "failure_code": "mcp_materialization_checkpoint_mismatch",
            }
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id_arg):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            return self.record

    request = CharacterCardCandidateRequest(
        project_id="project_doc230",
        people_asset_id="people_doc230",
        card_version_id="card_doc230",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=handoff_id,
    )

    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        ProductApiAnchorPackPreparationHost(_MismatchService()).generate(request)  # type: ignore[arg-type]

    assert exc_info.value.failure_code == "mcp_materialization_checkpoint_mismatch"
    assert exc_info.value.mcp_handoff_id == handoff_id


def test_doc230_checkpoint_mismatch_hard_stops_instead_of_advancing_candidate3() -> None:
    card = CharacterCardState.initial(card_version_id="card_doc230")
    front = card.face_slots["face.front"].model_copy(
        update={
            "state": "active",
            "output_id": "front_winner",
            "review_verified": True,
            "prompt_reference_parity_verified": True,
        }
    )
    card = card.model_copy(
        update={
            "face_identity_status": "active",
            "face_slots": {**card.face_slots, "face.front": front},
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_review_pending",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "pending_mcp_handoff_ids": ["mcp_handoff_doc230_existing"],
            "slot_retry_rounds": {"expression.laugh": 5},
        }
    )

    class _Generator:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def generate(self, request):  # noqa: ANN001, ANN201
            self.calls.append(request.candidate_index)
            if request.candidate_index != 2:
                raise AssertionError("checkpoint mismatch must hard-stop before candidate 3")
            raise AnchorCandidateUnavailable(
                "mcp_materialization_checkpoint_mismatch",
                mcp_handoff_id="mcp_handoff_doc230_existing",
            )

    class _Reviewer:
        def review(self, _candidate):  # noqa: ANN001, ANN201
            raise AssertionError("checkpoint mismatch has no reviewed pixel")

    generator = _Generator()
    result = CharacterCardPreparationService(generator=generator, reviewer=_Reviewer()).prepare_expression_set(
        card,
        front_output_id="front_winner",
        project_id="project_doc230",
        people_asset_id="people_doc230",
        user_intents={"laugh": "laugh", "anger": "anger", "sad": "sad"},
        generation_channel="mcp",
    )

    assert generator.calls == [2]
    assert result.status == "blocked"
    assert result.card.last_failure_code == "mcp_materialization_checkpoint_mismatch"


def test_doc231_review_only_resume_does_not_forward_stale_pending_handoff_after_checkpoint_mismatch() -> None:
    handoff_id = "mcp_handoff_doc231_stale"
    card = CharacterCardState.initial(card_version_id="card_doc231")
    front = card.face_slots["face.front"].model_copy(
        update={
            "state": "active",
            "output_id": "front_winner",
            "review_verified": True,
            "prompt_reference_parity_verified": True,
        }
    )
    card = card.model_copy(
        update={
            "face_identity_status": "active",
            "face_slots": {**card.face_slots, "face.front": front},
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_checkpoint_mismatch",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "pending_mcp_handoff_ids": [handoff_id],
            "slot_retry_rounds": {"expression.laugh": 5},
        }
    )

    class _Generator:
        def __init__(self) -> None:
            self.requests: list[CharacterCardCandidateRequest] = []

        def generate(self, request):  # noqa: ANN001, ANN201
            self.requests.append(request)
            assert request.candidate_index == 2
            assert request.attempt_round == 5
            assert request.mcp_handoff_id is None
            assert request.review_only_resume is True
            raise AnchorCandidateUnavailable("mcp_review_pending")

    class _Reviewer:
        def review(self, _candidate):  # noqa: ANN001, ANN201
            raise AssertionError("review-only pending checkpoint must stop before pixel review")

    generator = _Generator()
    result = CharacterCardPreparationService(generator=generator, reviewer=_Reviewer()).prepare_expression_slot(
        card,
        expression="laugh",
        front_output_id="front_winner",
        project_id="project_doc231",
        people_asset_id="people_doc231",
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        review_only_resume=True,
    )

    assert [request.candidate_index for request in generator.requests] == [2]
    assert result.status == "blocked"
    assert result.card.last_failure_code == "mcp_review_pending"
    assert result.card.pending_mcp_handoff_ids == []


def test_doc231_review_only_resume_preserves_review_pending_handoff() -> None:
    handoff_id = "mcp_handoff_doc231_existing"
    card = CharacterCardState.initial(card_version_id="card_doc231_review_pending")
    front = card.face_slots["face.front"].model_copy(
        update={
            "state": "active",
            "output_id": "front_winner",
            "review_verified": True,
            "prompt_reference_parity_verified": True,
        }
    )
    card = card.model_copy(
        update={
            "face_identity_status": "active",
            "face_slots": {**card.face_slots, "face.front": front},
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_review_pending",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "pending_mcp_handoff_ids": [handoff_id],
            "slot_retry_rounds": {"expression.laugh": 5},
        }
    )

    class _Generator:
        def generate(self, request):  # noqa: ANN001, ANN201
            assert request.candidate_index == 2
            assert request.attempt_round == 5
            assert request.mcp_handoff_id == handoff_id
            assert request.review_only_resume is True
            raise AnchorCandidateUnavailable("mcp_review_pending", mcp_handoff_id=handoff_id)

    class _Reviewer:
        def review(self, _candidate):  # noqa: ANN001, ANN201
            raise AssertionError("review-only pending checkpoint must stop before pixel review")

    result = CharacterCardPreparationService(generator=_Generator(), reviewer=_Reviewer()).prepare_expression_slot(
        card,
        expression="laugh",
        front_output_id="front_winner",
        project_id="project_doc231",
        people_asset_id="people_doc231",
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        review_only_resume=True,
    )

    assert result.status == "blocked"
    assert result.card.last_failure_code == "mcp_review_pending"
    assert result.card.pending_mcp_handoff_ids == [handoff_id]


def test_doc231_review_only_missing_target_fails_closed_without_creating_job() -> None:
    handoff_id = "mcp_handoff_doc231_missing"
    operation_id = "people_doc231:expression_set:expression.laugh:2:round5"

    class _JobStore:
        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return []

        def get(self, _job_id):  # noqa: ANN001, ANN201
            return None

        def save(self, record):  # noqa: ANN001, ANN201
            return record

    class _MissingTargetService:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created = 0
            self.job_store = _JobStore()
            self.output_store = SimpleNamespace()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda _handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "job_checkpointed",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                    "job_checkpoint": {
                        "status": "job_checkpointed",
                        "operation_id": operation_id,
                        "handoff_id": handoff_id,
                        "job_id": "job_doc231_missing",
                        "candidate_id": "candidate_doc231_missing",
                        "output_id": "v3_output_doc231_missing",
                        "generation_result_id": "generation_result_doc231_missing",
                    },
                }
            )

        def create_professional_character_card_stage_job(self, *_args, **_kwargs):
            self.created += 1
            raise AssertionError("review-only collection must not create a replacement job")

        def generate_job(self, *_args, **_kwargs):
            raise AssertionError("review-only missing target must not generate")

    service = _MissingTargetService()
    request = CharacterCardCandidateRequest(
        project_id="project_doc231",
        people_asset_id="people_doc231",
        card_version_id="card_doc231",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=handoff_id,
        review_only_resume=True,
    )

    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert exc_info.value.failure_code == "mcp_review_target_not_found"
    assert exc_info.value.mcp_handoff_id == handoff_id
    assert service.created == 0


def test_doc231_review_only_ignores_orphan_pending_handoff_and_uses_job_checkpoint() -> None:
    job_id = "job_doc231_review_only_checkpoint"
    output_id = "v3_output_doc231_existing"
    candidate_id = "candidate_doc231_existing"
    checkpoint_handoff_id = "mcp_handoff_doc231_checkpointed"
    stale_pending_handoff_id = "mcp_handoff_doc231_stale_pending"
    operation_id = "people_doc231:expression_set:expression.laugh:2:round5"

    stale_planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        handoff={
            "handoff_id": checkpoint_handoff_id,
            "status": "job_checkpointed",
            "generation_channel": "mcp",
        },
    )
    stale_planning_metadata["professional_anchor_reference_assets"] = [{"asset_id": "front_winner"}]
    generation = _with_review_package(
        _attach_output_checkpoint(
            _minimal_planning_result(
                job_id,
                generation_metadata=stale_planning_metadata,
            ),
            output_id=output_id,
            candidate_id=candidate_id,
            handoff_id=checkpoint_handoff_id,
            provider_prompt_sha256="sha256:doc231",
            prompt_compilation_id="prompt_doc231",
        ),
        _provider_timeout_review_package(
            job_id=job_id,
            output_id=output_id,
            candidate_id=candidate_id,
        ),
    )
    record = SimpleNamespace(
        job_id=job_id,
        status=ProductJobStatusValue.BLOCKED,
        planning_result=generation,
        generation_result=generation,
        request=SimpleNamespace(
            metadata={
                "project_id": "project_doc231",
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": checkpoint_handoff_id,
                    "status": "job_checkpointed",
                    "generation_channel": "mcp",
                    "resume_required": True,
                },
                "mcp_review_status": {
                    "status": "pending",
                    "reason_code": "provider_timeout",
                    "handoff_id": checkpoint_handoff_id,
                    "output_id": output_id,
                    "candidate_id": candidate_id,
                    "review_owner": "v3_shared_visual_cluster",
                },
            }
        ),
    )

    def _handoff_payload(handoff_id):  # noqa: ANN001, ANN202
        if handoff_id == stale_pending_handoff_id:
            return {
                "handoff_id": stale_pending_handoff_id,
                "status": "pending",
                "canonical_prompt": _current_laugh_handoff_prompt(),
                "reference_assets": _current_expression_reference_assets(),
            }
        if handoff_id == checkpoint_handoff_id:
            return {
                "handoff_id": checkpoint_handoff_id,
                "status": "job_checkpointed",
                "canonical_prompt": _current_laugh_handoff_prompt(),
                "reference_assets": _current_expression_reference_assets(),
                "job_checkpoint": {
                    "status": "job_checkpointed",
                    "operation_id": operation_id,
                    "handoff_id": checkpoint_handoff_id,
                    "job_id": job_id,
                    "candidate_id": candidate_id,
                    "output_id": output_id,
                    "generation_result_id": generation.planning_result_id,
                },
            }
        return None

    class _JobStore:
        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [record]

        def save(self, new_record):  # noqa: ANN001, ANN201
            return new_record

    class _ResumeReviewService:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created = 0
            self.generated_calls = []
            self.output_store = SimpleNamespace(
                list_by_job=lambda _job_id: [
                    SimpleNamespace(
                        output_id=output_id,
                        candidate_id=candidate_id,
                        metadata={
                            "provider_prompt_sha256": "sha256:doc231",
                            "prompt_compilation_id": "prompt_doc231",
                            "provider_reference_image_count": 3,
                            "reference_asset_count": 3,
                            "provider_reference_assets": _current_expression_reference_assets(),
                            "prompt_reference_parity": {"verified": True},
                            "reference_evidence_parity": {"verified": True},
                        },
                    )
                ]
            )
            self.job_store = _JobStore()
            self.mcp_materialization_store = SimpleNamespace(
                get=_handoff_payload,
                list_unconsumed_by_operation=lambda _operation_id: [
                    _handoff_payload(stale_pending_handoff_id)
                ],
            )

        def create_professional_character_card_stage_job(self, *_args, **_kwargs):
            self.created += 1
            raise AssertionError("review-only must not recover a stale pending handoff or create a new job")

        def generate_job(self, job_id_arg, request):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            self.generated_calls.append((job_id_arg, request))
            assert request["metadata"]["_v3_resume_finalizing_review"] is True
            package = {
                "package_id": "review_doc231_host_pass",
                "job_id": job_id,
                "inspections": [
                    {
                        "inspection_id": "visual_inspection_doc231_host_pass",
                        "job_id": job_id,
                        "candidate_id": candidate_id,
                        "output_id": output_id,
                        "mode": "hybrid",
                        "status": "pass",
                        "verification_state": "verified",
                        "confidence": 0.94,
                        "score_card": _laugh_pass_score_card(),
                        "detected_issues": [],
                        "issue_codes": [],
                    }
                ],
                "metadata": {"post_generation": True, "inspection_count": 1},
            }
            record.generation_result = _with_review_package(record.generation_result, package)
            record.status = ProductJobStatusValue.GENERATED
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.GENERATED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id_arg):  # noqa: ANN001, ANN201
            assert job_id_arg == job_id
            return record

    service = _ResumeReviewService()
    request = CharacterCardCandidateRequest(
        project_id="project_doc231",
        people_asset_id="people_doc231",
        card_version_id="card_doc231",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        review_only_resume=True,
    )

    candidate = ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert service.created == 0
    assert service.generated_calls[0][0] == job_id
    assert candidate.output_id == output_id
    assert candidate.candidate_id == candidate_id


def test_doc223c_anchor_pack_recovers_old_handoff_job_beyond_recent_window(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:anchor_pack:standard_front:1"
    store = PersistentProductJobStore(tmp_path / "jobs")
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    prompt = "front anchor MCP handoff"
    handoff = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        reference_assets=[],
        rendering_contract={"size": "32x48", "output_format": "png"},
    )
    target = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="prepare front anchor",
            metadata={
                "professional_anchor_pack_preparation": True,
                "professional_reference_stage": "standard_front",
                "professional_anchor_capture_scope": "anchor_pack",
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": handoff["handoff_id"],
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            },
        ),
        status=ProductJobStatusValue.GENERATING,
        job_id_value="job_doc223c_anchor_old_checkpoint",
        planning_result=_minimal_planning_result("job_doc223c_anchor_old_checkpoint"),
    )
    store.save(target)
    _save_doc223c_noise_jobs(store, 130)
    assert target.job_id not in {record.job_id for record in store.list_recent(100)}

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = handoffs
            self.created_payloads = []
            self.generated_calls = []

        def create_professional_anchor_preparation_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            raise AssertionError("Doc223-C must recover the durable anchor job before creating a new Brain job")

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, payload))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            return self.job_store.get(job_id)

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending") as exc_info:
        ProductApiAnchorPackPreparationHost(service).generate(
            _anchor_doc223c_request(
                operation_id=operation_id,
                handoff_id=handoff["handoff_id"],
            )
        )  # type: ignore[arg-type]

    assert exc_info.value.mcp_handoff_id == handoff["handoff_id"]
    assert service.created_payloads == []
    assert service.generated_calls[0][0] == target.job_id
    assert len(store.list_mcp_operation_records(operation_id)) == 1


def test_doc223c_character_card_conflicting_operation_records_fail_closed(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:expression_set:expression.laugh:2:round5"
    store = PersistentProductJobStore(tmp_path / "jobs")
    for index in range(2):
        job_id = f"job_doc223c_conflict_{index}"
        store.save(
            ProductJobRecord(
                request=CreateCreativeJobRequest(
                    user_input="positive expression keyframe",
                    metadata={
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.laugh",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": operation_id,
                    },
                ),
                status=ProductJobStatusValue.GENERATING,
                job_id_value=job_id,
                planning_result=_minimal_planning_result(
                    job_id,
                    generation_metadata=_current_character_card_planning_metadata(
                        operation_id=operation_id
                    ),
                ),
            )
        )

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = SimpleNamespace(get=lambda _handoff_id: None)

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_operation_ambiguous"):
        ProductApiAnchorPackPreparationHost(_Service()).generate(  # type: ignore[arg-type]
            _character_card_doc223c_request(operation_id=operation_id)
        )


def test_doc223c_character_card_wrong_reference_record_is_not_reused(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:expression_set:expression.laugh:2:round5"
    store = PersistentProductJobStore(tmp_path / "jobs")
    store.save(
        ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="positive expression keyframe",
                metadata={
                    "professional_character_card_preparation": True,
                    "professional_character_card_stage": "expression_set",
                    "professional_character_card_slot": "expression.laugh",
                    "professional_character_card_reference_output_ids": ["wrong_front"],
                    "generation_channel": "mcp",
                    "mcp_operation_id": operation_id,
                },
            ),
            status=ProductJobStatusValue.GENERATING,
            job_id_value="job_doc223c_wrong_reference",
            planning_result=_minimal_planning_result("job_doc223c_wrong_reference"),
        )
    )

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda _handoff_id: None,
                list_unconsumed_by_operation=lambda _operation_id: [],
            )
            self.created_payloads = []
            self.record = ProductJobRecord(
                request=CreateCreativeJobRequest(
                    user_input="positive expression keyframe",
                    metadata={
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.laugh",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": operation_id,
                    },
                ),
                status=ProductJobStatusValue.PLANNED,
                job_id_value="job_doc223c_new_after_wrong_reference",
                planning_result=_minimal_planning_result("job_doc223c_new_after_wrong_reference"),
            )

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            assert job_id == self.record.job_id
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            if job_id == self.record.job_id:
                return self.record
            return self.job_store.get(job_id)

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(
            _character_card_doc223c_request(operation_id=operation_id)
        )  # type: ignore[arg-type]

    assert service.created_payloads
    assert service.created_payloads[0]["metadata"].get("mcp_materialization") is None


def test_doc226_character_card_stale_planning_metadata_does_not_resume_old_operation_job(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:expression_set:expression.laugh:2:round5"
    store = PersistentProductJobStore(tmp_path / "jobs")
    stale_record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="positive expression keyframe",
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
            },
        ),
        status=ProductJobStatusValue.GENERATING,
        job_id_value="job_doc226_stale_same_operation",
        # This reproduces the real Doc225 pre-fix checkpoint: request metadata
        # says Character Card, but the frozen generation plan has no
        # Character Card stage/slot/preparation transport and no materialized
        # handoff yet, so a naive interrupted-job resume would re-enter the
        # stale frozen plan instead of creating a current full-frame handoff.
        planning_result=_minimal_planning_result("job_doc226_stale_same_operation"),
    )
    store.save(stale_record)

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda _handoff_id: None,
                list_unconsumed_by_operation=lambda _operation_id: [],
            )
            self.created_payloads = []
            self.generated_calls = []
            self.record = ProductJobRecord(
                request=CreateCreativeJobRequest(
                    user_input="positive expression keyframe",
                    metadata={
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.laugh",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": operation_id,
                    },
                ),
                status=ProductJobStatusValue.PLANNED,
                job_id_value="job_doc226_new_current_contract",
                planning_result=_minimal_planning_result(
                    "job_doc226_new_current_contract",
                    generation_metadata=_current_character_card_planning_metadata(
                        operation_id=operation_id
                    ),
                ),
            )

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, payload))
            assert job_id == self.record.job_id
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            if job_id == self.record.job_id:
                return self.record
            return self.job_store.get(job_id)

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(
            _character_card_doc223c_request(operation_id=operation_id)
        )  # type: ignore[arg-type]

    assert service.created_payloads
    assert service.generated_calls == [
        (
            "job_doc226_new_current_contract",
            {
                "quality_mode": "strict",
                "metadata": {
                    "disable_visual_auto_retry": True,
                    "max_visual_retry_attempts": 0,
                },
            },
        )
    ]


def test_doc203_submitted_body_resume_without_durable_planning_does_not_remain_generating(
    tmp_path: Path,
) -> None:
    """The observed missing-plan handoff must not stay indefinitely in-flight."""

    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    job_id = "job_doc203_planning_durability_missing"
    operation_id = "visual_asset_doc203:body_silhouette:body.front_full:1:planning-missing"
    prompt = "body silhouette submitted handoff planning diagnosis"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")
    contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_generate",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
        **_doc203_body_frozen_contract_fields(),
    }
    jobs = PersistentProductJobStore(tmp_path / "jobs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    pending = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=[],
        rendering_contract=contract,
        require_body_rendering_contract=True,
    )
    submitted = handoffs.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoffs, pending),
    )
    assert submitted["status"] == "submitted"

    metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
        handoff=None,
    )
    metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": "system_inferred_body_model_scene_neutral_v1",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
            "mcp_materialization": {
                "handoff_id": pending["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
                "nonce": pending["nonce"],
            },
        }
    )
    jobs.save(
        ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="submitted Body handoff with no durable planning result",
                metadata=metadata,
            ),
            status=ProductJobStatusValue.GENERATING,
            job_id_value=job_id,
            planning_result=None,
            generation_result=None,
            balance_estimate={"credits_required": 0},
        )
    )

    class _ProbeRuntime:
        def __init__(self) -> None:
            self.scenario_registry = ScenarioRuntime().scenario_registry
            self.generate_job_calls = 0
            self.generation_router = SimpleNamespace()

        def generate_job(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN201
            self.generate_job_calls += 1
            raise AssertionError("missing-plan submitted resume must not re-enter planning")

    runtime = _ProbeRuntime()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=jobs,
        output_store=outputs,
        mcp_materialization_store=handoffs,
    )
    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert status.status == ProductJobStatusValue.BLOCKED
    assert runtime.generate_job_calls == 0
    assert getattr(handoffs, "consume_calls", []) == []
    updated = jobs.get(job_id)
    assert updated is not None
    assert updated.planning_result is None
    assert updated.generation_result is None
    failure = updated.request.metadata.get("generation_lifecycle_failure")
    assert isinstance(failure, dict)
    assert failure["failure_code"] == "submitted_resume_planning_result_missing"
    assert failure["failure_family"] == "mcp_materialization"


def test_doc203_body_mcp_generation_without_planning_fails_closed_before_runtime(
    tmp_path: Path,
) -> None:
    """A Body MCP job cannot enter generation or create a handoff without its plan."""

    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    job_id = "job_doc203_body_mcp_plan_required"
    operation_id = "visual_asset_doc203:body_silhouette:body.front_full:1:plan-required"
    metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        refs=["face_reference_front", "face_reference_side", "face_reference_rear"],
        stage="body_silhouette",
        slot_key="body.front_full",
        attempt_round=1,
    )
    metadata.update(
        {
            "professional_character_card_source_class": "brain_inferred",
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_character_card_body_model_context": (
                "system_inferred_body_model_scene_neutral_v1"
            ),
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": (
                default_body_refresh_presentation_intent().model_dump(mode="json")
            ),
            "mcp_materialization": {
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        }
    )
    jobs = PersistentProductJobStore(tmp_path / "jobs")
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    jobs.save(
        ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="Body MCP generation without durable planning",
                metadata=metadata,
            ),
            status=ProductJobStatusValue.BLOCKED,
            job_id_value=job_id,
            planning_result=None,
            generation_result=None,
            balance_estimate={"credits_required": 0},
        )
    )

    class _RuntimeProbe:
        def __init__(self) -> None:
            self.scenario_registry = ScenarioRuntime().scenario_registry
            self.generate_job_calls = 0

        def generate_job(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN201
            self.generate_job_calls += 1
            raise AssertionError("Body MCP without planning must not enter generation")

    runtime = _RuntimeProbe()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=jobs,
        output_store=V3GeneratedOutputStore(tmp_path / "outputs"),
        mcp_materialization_store=handoffs,
    )
    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {}},
    )

    assert status.status == ProductJobStatusValue.BLOCKED
    assert runtime.generate_job_calls == 0
    updated = jobs.get(job_id)
    assert updated is not None
    assert updated.generation_result is None
    failure = updated.request.metadata.get("generation_lifecycle_failure")
    assert isinstance(failure, dict)
    assert failure["failure_code"] == "mcp_materialization_planning_required"
    assert failure["failure_family"] == "mcp_materialization"


def test_doc203_character_card_plan_result_is_durable_at_stage_creation_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normal planned stage saves its PlanningResult before later resume."""

    from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import (
        ScenarioRuntimeResult,
        ScenarioRuntimeStatus,
    )

    job_id = "job_doc203_planning_durable_at_create"
    planning = _minimal_planning_result(job_id)
    base_runtime = ScenarioRuntime()
    resolution = base_runtime.scenario_registry.resolve({"scenario_id": "general_creative"})

    class _PlannedRuntime:
        def __init__(self) -> None:
            self.scenario_registry = base_runtime.scenario_registry
            self.plan_calls = 0

        def plan_job(self, _payload):  # noqa: ANN001, ANN201
            self.plan_calls += 1
            return ScenarioRuntimeResult(
                status=ScenarioRuntimeStatus.PLANNED,
                scenario_resolution=resolution,
                planning_result=planning,
            )

    monkeypatch.setattr(
        V3ProductApiService,
        "_professional_character_card_reference_assets",
        lambda _self, _ids: [{"asset_id": "face_reference_fixture", "role": "face_reference"}],
    )
    monkeypatch.setattr(
        V3ProductApiService,
        "_professional_character_card_body_reference_assets",
        lambda _self, *_args, **_kwargs: [],
    )
    jobs = PersistentProductJobStore(tmp_path / "jobs")
    runtime = _PlannedRuntime()
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=jobs,
        output_store=V3GeneratedOutputStore(tmp_path / "outputs"),
        mcp_materialization_store=McpMaterializationHandoffStore(tmp_path / "handoffs"),
    )

    status = service.create_professional_character_card_stage_job(
        {"user_input": "planned Body stage durability fixture", "metadata": {}},
        stage="body_silhouette",
        slot_key="body.front_full",
        reference_output_ids=[
            "face_reference_front_fixture",
            "face_reference_side_fixture",
            "face_reference_rear_fixture",
        ],
        candidate_index=1,
        candidate_count=3,
        source_class="brain_inferred",
        body_refresh_source_mode="inference_first",
        body_model_context="system_inferred_body_model_scene_neutral_v1",
        body_refresh_contract_required=True,
        generation_channel="mcp",
        mcp_operation_id="visual_asset_doc203:body_silhouette:body.front_full:1:planned",
    )

    assert runtime.plan_calls == 1
    assert status.status == ProductJobStatusValue.PLANNED
    durable = jobs.get(job_id)
    assert durable is not None
    assert durable.planning_result is not None
    assert durable.generation_result is None


def test_doc263_reference_assisted_submitted_resume_reuses_frozen_physical_face_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A submitted strict Body handoff must be replayed with its frozen Face refs.

    The real rear candidate3 boundary had two physical Face references frozen in
    the handoff, while the resume reconstruction rebuilt only one from the
    durable generation plan.  The consumer must not silently reinterpret that
    handoff as a different provider request.
    """

    job_id = "job_doc263_reference_assisted_rear3"
    operation_id = "visual_asset_doc263_reference_assisted:body_silhouette:body.rear_full:3"
    prompt = "closed reference-assisted Body rear candidate three renderer prompt"
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    handoff_store = McpMaterializationHandoffStore(tmp_path / "handoffs")

    from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
        body_silhouette_mcp_materialization_channel_contract,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
        default_body_refresh_presentation_intent,
    )

    body_intent = default_body_refresh_presentation_intent().model_dump(mode="json")
    physical_face_refs = [
        {
            "asset_id": "face_rear_feature_detail",
            "source_asset_id": "face_rear_source",
            "sha256": "1" * 64,
            "role": "portrait_identity",
            "derivative_kind": "feature_detail",
        },
        {
            "asset_id": "face_rear_head_geometry",
            "source_asset_id": "face_rear_source",
            "sha256": "2" * 64,
            "role": "portrait_identity",
            "derivative_kind": "portrait_identity_pose_geometry_crop",
        },
    ]
    body_partition = {
        "contract_version": "body_mcp_reference_partition_v1",
        "body_proportion_reference": {
            "role": "body_proportion_reference",
            "truth_layer": "body_proportion_truth",
            "asset_count": 5,
            "asset_hashes": ["3" * 64] * 5,
        },
        "face_identity_reference": {
            "role": "face_identity_reference",
            "truth_layer": "identity_continuity",
            "identity_continuity_only": True,
            # The typed partition counts semantic Face sources.  The frozen
            # renderer handoff may carry two complementary derivatives from
            # that one source.
            "asset_count": 1,
            "asset_hashes": ["9" * 64],
        },
    }
    morphology_bands = {
        "relative_head_to_stature": "proportional",
        "shoulder_to_head": "proportional",
        "torso_to_leg": "proportional",
        "arm_to_leg": "proportional",
        "build": "medium",
        "neck_shoulder": "proportional_transition",
        "developmental_stage_context": "unknown_stage_context",
        "stance_ground": "grounded_full_contact",
        "cross_view_support": "multi_view_supported",
    }
    morphology_digest = hashlib.sha256(
        json.dumps(morphology_bands, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    rendering_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
        "input_fidelity": "high",
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
        **_doc203_body_frozen_contract_fields(),
        "body_refresh_source_mode": "reference_assisted",
        "target_age_scope": "age_6_child_only",
        "body_mcp_reference_partition": body_partition,
        "body_morphology_profile": {
            "schema_version": "body_morphology_evidence_profile_v2",
            "profile_digest": "a" * 64,
            "bands_digest": morphology_digest,
            "bands": morphology_bands,
            "target_age_scope": "age_6_child_only",
        },
    }
    pending = handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=physical_face_refs,
        rendering_contract=rendering_contract,
        require_body_rendering_contract=True,
    )
    submitted = handoff_store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_sha,
        reference_asset_hashes=pending["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
        **_renderer_submit_hashes(handoff_store, pending),
    )
    assert submitted["status"] == "submitted"

    planning_metadata = _current_character_card_planning_metadata(
        operation_id=operation_id,
        refs=["face_rear_source"],
        stage="body_silhouette",
        slot_key="body.rear_full",
        attempt_round=1,
        handoff=None,
    )
    planning_metadata.update(
        {
            "professional_character_card_source_class": "observed",
            "professional_character_card_body_refresh_source_mode": "reference_assisted",
            "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
            "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
            "professional_character_card_candidate_index": 3,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": body_intent,
            "professional_character_card_face_view_binding": {
                "rear_full": {
                    "face_slot": "face.rear_head",
                    "source_asset_id": "face_rear_source",
                }
            },
            "mcp_materialization": {
                "handoff_id": pending["handoff_id"],
                "status": "failed",
                "failure_code": "mcp_materialization_reference_mismatch",
                "generation_channel": "mcp",
                "resume_required": True,
                "nonce": pending["nonce"],
                "prompt_sha256": prompt_sha,
                "reference_asset_hashes": pending["reference_asset_hashes"],
            },
        }
    )
    generation_metadata = {
        **planning_metadata,
        # This deliberately models the observed replay defect: the frozen
        # handoff owns two Face derivatives, but the reconstructed plan owns
        # three stale physical references.  The fix must project the handoff's
        # exact pair before the provider request/capability boundary.
        "reference_assets": [
            *physical_face_refs,
            {
                "asset_id": "stale_planning_reference",
                "source_asset_id": "stale_planning_source",
                "sha256": "8" * 64,
                "role": "portrait_identity",
                "derivative_kind": "portrait_identity_pose_geometry_crop",
            },
        ],
        # The historical plan may also carry a third uploaded/anchor asset.
        # A submitted handoff must suppress that stale physical channel
        # instead of letting the provider combine it with the frozen pair.
        "uploaded_assets": [physical_face_refs[0]],
        "llm_brain": {
            "canonical_provider_prompts": [
                {"output_index": 1, "prompt": prompt, "review_status": "approved"}
            ]
        },
    }
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="strict Body submitted resume with frozen Face partition",
            metadata={**planning_metadata, "project_id": "project_doc263_reference_assisted"},
        ),
        status=ProductJobStatusValue.BLOCKED,
        job_id_value=job_id,
        planning_result=_minimal_planning_result(
            job_id,
            generation_metadata=generation_metadata,
        ),
        generation_result=None,
        balance_estimate={"credits_required": 0},
    )
    job_store.save(record)
    handoff_store.job_store = job_store

    artifact_path = tmp_path / "generated.png"
    artifact_path.write_bytes(_png_bytes())
    output_id = "v3_output_44444444444444444444"
    output_store.save_base64_output(
        job_id=job_id,
        candidate_id="candidate_doc263_reference_assisted_rear3",
        asset_id="asset_doc223c",
        provider="mcp_materialization",
        model="gpt-image-2",
        encoded_image=base64.b64encode(_png_bytes()).decode("ascii"),
        output_id=output_id,
    )

    class _RecordingRouter:
        def __init__(self) -> None:
            self.requests = []

        def generate(self, request):  # noqa: ANN001
            self.requests.append(request)
            return SimpleNamespace(
                candidates=[
                    SimpleNamespace(
                        candidate_id="candidate_doc263_reference_assisted_rear3",
                        provider="mcp_materialization",
                        file_path=str(artifact_path),
                        uri=str(artifact_path),
                        prompt_compilation_id="prompt_doc263_reference_assisted_rear3",
                        metadata={
                            "output_id": output_id,
                            "mcp_materialization": {
                                "handoff_id": pending["handoff_id"],
                                "expected_checkpoint": {
                                    "candidate_id": "candidate_doc263_reference_assisted_rear3",
                                    "output_id": output_id,
                                },
                            },
                        },
                    )
                ],
                provider_metadata={"test_only": True},
            )

    router = _RecordingRouter()
    runtime = SimpleNamespace(
        generation_router=router,
        scenario_registry=ScenarioRuntime().scenario_registry,
    )
    service = V3ProductApiService(
        scenario_runtime=runtime,  # type: ignore[arg-type]
        job_store=job_store,
        output_store=output_store,
        mcp_materialization_store=handoff_store,
    )
    monkeypatch.setattr(service, "_checkpoint_mcp_generation_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "_resume_finalizing_generation_review",
        lambda current, *_args, **_kwargs: service._status_from_record(current),
    )

    status = service.generate_asset_series(
        job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_finalizing_review": True}},
    )

    assert router.requests, (
        "strict submitted Body resume must reach the frozen consumer; current code "
        "rejects the handoff before provider request construction"
    )
    assert len(router.requests[0].metadata["reference_assets"]) == len(physical_face_refs)
    assert router.requests[0].metadata["uploaded_assets"] == []
    assert status.status == ProductJobStatusValue.FINALIZING
    updated = job_store.get(job_id)
    assert updated is not None
    assert updated.generation_result is not None
