Warning: truncated output (original token count: 220035)
Total output lines: 18209

"""Framework-neutral V3 product API service.

Route handlers can wrap this service later. The service deliberately exposes
product concepts such as jobs, asset series, candidates, selected result, and
balance estimate instead of image-model controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
from time import sleep
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import ValidationError

from ..app_shell.navigation import get_navigation_entry
from ..app_shell.routes import API_NAMESPACE, get_route_contracts
from ..brand_memory.profile_service import BrandProfileService
from ..creative_core.rules import RULE_VERSION, stable_id
from ..creative_core.doc281_output_plan_binding import (
    DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY,
    validate_doc73_binding,
    issue_doc281_output_plan_binding,
)
from ..generation_router import GenerationRouter, ProductionImageGenerationProvider, safe_runtime_execution_budget
from ..generation_router.providers import (
    McpHandoffProvenance,
    McpMaterializationProvider,
    build_provider_generation_request,
)
from ..generation_router.mcp_materialization import McpMaterializationHandoffStore
from ..llm_brain.contracts import BRAIN_TRANSPORT_TIMEOUT_PHASES
from ..llm_brain.finalizer_lifecycle import (
    remote_brain_receipts_are_monotonic,
    safe_remote_brain_finalizer_lifecycle,
)
from ..platform_adapters import V3BalanceAdapter, V3BalanceEstimate
from ..photography_profiles import (
    PhotographerProfileBinding,
    PhotographerProfileCatalog,
    PhotographerProfileSelectionError,
    default_photographer_profile_catalog,
)
from ..scenario_packs.ecommerce import EcommercePackOutput, EcommerceScenarioPackPlanner, ecommerce_product_truth_reference_budget
from ..scenario_packs.ecommerce.reference_projection import (
    PhysicalProductReferenceProjection,
    ProductTruthAdmission,
    ProductTruthSource,
    build_physical_product_projection,
    build_product_truth_admission,
)
from ..scenario_packs.ecommerce.physical_renderer_reference_plan import (
    DOC269_MAX_REFERENCE_IMAGES,
    PhysicalRendererReferencePlan,
    build_physical_renderer_reference_plan,
)
from ..scenario_packs.ecommerce.provider_deliverability_closure import (
    _terminal_job_receipt,
    build_provider_deliverability_closure_receipt,
)
from ..scenario_packs.ecommerce.opaque_provider_rejection_hold import (
    build_ambiguous_provider_request_hold_receipt,
)
from ..scenario_packs import ScenarioPackResolution
from ..scenario_runtime import ScenarioRuntime, ScenarioRuntimeRequest
from ..visual_assets import (
    FrozenVisualAssetBindingSet,
    InMemoryVisualAssetCatalog,
    ProfessionalModeRuntimeBridge,
    ProjectVisualAssetBindingService,
    bind_professional_mode,
)
from ..visual_assets.formal_slot_acceptance import (
    FormalSlotReceipt,
    validate_formal_slot_receipt_for_activation,
)
from ..visual_assets.body_silhouette_source_standard import body_silhouette_mcp_materialization_channel_contract
from ..visual_assets.character_card import BodyRefreshPresentationIntent, BodySourceAdmission
from ..visual_assets.body_proportion_evidence_profile import (
    BODY_REFRESH_REFERENCE_AGE_SCOPE,
    BodyRefreshAnalysisContext,
    BodySourceAnalysisAssetEnvelope,
    BodySourceAnalysisProvider,
    create_configured_body_source_analysis_provider,
)
from . import body_cross_view_review_provider as body_cross_view_review_provider_module
from .body_cross_view_review_provider import BodyCrossViewReviewProvider
from ..shared_capabilities import CapabilityRunResult
from ..shared_capabilities.apparel_construction import APPAREL_CONSTRUCTION_REVIEW_ISSUES
from ..shared_capabilities.visual_cluster import (
    HumanPhotorealismLayer,
    ModeAwareRoleDirector,
    OutputQualityReviewMerger,
    VisionOutputInspector,
    reference_channel_retry_patch,
)
from ..shared_capabilities.visual_cluster.contracts import (
    GeneralVariationModeBinding,
    ModeRoleRecipe,
    ReviewEvidencePlan,
    VariationExecutionContract,
)
from ..shared_capabilities.visual_cluster.human_photorealism import (
    HUMAN_REALISM_REVIEW_DIMENSIONS,
    normalize_human_realism_issue_code,
)
from ..shared_capabilities.visual_cluster.review_evidence import ExactReviewEvidenceResolver, review_plan_digest
from ..shared_capabilities.visual_cluster.review_scope import (
    aggregate_review_outcomes,
    classify_review_outcome,
    universal_review_scope,
)
from ..shared_capabilities.visual_cluster.vision_provider import (
    VisionInspectionProviderError,
    VisionInspectionProviderUnavailable,
    active_review_contract,
)
from ..schemas import (
    AssetType,
    BrandProfile,
    MemoryUpdate,
    PackagedAsset,
    PlanningResult,
    Platform,
    ProviderStrategy,
    Recommendation,
    ReferenceAsset,
)
from .assets import V3UploadedAssetStore
from .contracts import (
    AssetSeriesItem,
    BrandApiResponse,
    CampaignSummary,
    CandidateSummary,
    CreateBrandRequest,
    CreateCreativeJobRequest,
    EcommerceCapabilitySummary,
    GenerateContinuation,
    GenerateJobRequest,
    GeneralCreativeCapabilitySummary,
    ImageOutputOptions,
    ProductJobStatus,
    ProductJobStatusValue,
    ScenarioSummary,
    SelectResultRequest,
    SelectionResponse,
    SelectedResult,
    StyleContinuationSummary,
    V3AssetContentUploadRequest,
    V3AssetUploadCreateRequest,
    V3AssetUploadStatusValue,
    V3ExportDownloadPayload,
    V3ExportPackageResponse,
    V3JobHistoryItem,
    V3JobHistoryResponse,
    V3UploadedAssetRecord,
)
from .lifecycle import (
    CandidateRecord,
    CandidateSelectionRecord,
    ExportRecord,
    JobLifecycleRecord,
    JobRecord,
    RunRecord,
)
from .outputs import V3GeneratedOutputRecord, V3GeneratedOutputStore
from .output_resolver import GeneratedOutputResolver


QUALITY_MODE_TO_MOCK_PROFILE = {
    "standard": "balanced",
    "explore": "needs_refinement",
    "strict": "balanced",
}

_REMOTE_BRAIN_LIFECYCLE_OUTCOME_SCHEMA = "v3_remote_creative_brain_outcome_v1"

_REMOTE_BRAIN_LIFECYCLE_OUTCOME_CLASSES = {
    "remote_brain_unavailable",
    "remote_brain_unauthorized",
    "remote_contract_invalid",
    "remote_prompt_signoff_unavailable",
    "remote_provider_error",
    "remote_provider_unavailable",
    "remote_output_count_mismatch",
    "remote_brain_skipped",
    "remote_creative_brain_required",
}

_REMOTE_BRAIN_LIFECYCLE_ERROR_CLASSES = {
    "timeout",
    "budget_exceeded",
    "execution_budget_exhausted",
    "provider_error",
    "unavailable",
    "upstream_transport_error",
    "upstream_http_error",
    "invalid_response",
    "truncated_response",
    "content_policy",
    "canceled",
    "serialization_failure",
    "contract_validation",
    "unknown",
}

_REMOTE_BRAIN_AVAILABILITY_REASONS = {
    "remote_disabled",
    "brain_disabled",
    "missing_credentials",
    "invalid_configuration",
    "capability_scope_inactive",
    "availability_check_failed",
    "provider_unavailable",
    "configured",
}

_REMOTE_BRAIN_LIFECYCLE_STAGES = {
    "plan",
    "semantic_plan",
    "provider_prompt_finalize",
    "generate",
    "unknown",
}

_CAPABILITY_ACTIVATION_FAILURE_CODES = {
    "capability_activation_error",
    "general_variation_suite_direction_not_active",
}

_REMOTE_BRAIN_TRANSPORT_ERROR_CLASSES = {
    "timeout",
    "protocol_error",
    "connection_error",
    "read_error",
    "http_status_error",
    "upstream_transport_error",
    "provider_error",
    "unknown",
}

_REMOTE_BRAIN_TIMEOUT_PHASES = set(BRAIN_TRANSPORT_TIMEOUT_PHASES)
_REMOTE_BRAIN_PROVIDER_TRANSPORT_KINDS = {
    "connection_error",
    "network_error",
    "protocol_error",
    "provider_api_error",
    "read_error",
    "timeout",
    "transport_error",
    "write_error",
}

# A deterministic, local-only pixel fixture for the mock runtime.  It gives
# contract tests a real V3 output record without pretending a provider image
# was produced.  Interactive production requests use a non-mock provider and
# never take this path.
_MOCK_OUTPUT_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOUMEhgYGBgYgAD"
    "AAfCAKzG2dL1AAAAAElFTkSuQmCC"
)

GENERAL_CREATIVE_PUBLIC_CONTROLS = [
    "Use uploaded images as subject or style references",
    "Keep layout similar when a reference or preset is selected",
    "Keep supplied text, logo, and important visible details exact",
    "Continue previous brand style when a brand is selected",
    "Avoid directions previously rejected in brand history",
]

_PUBLIC_WARNING_INTERNAL_MARKERS = (
    "output review ran without live image inspection",
    "no candidate pixels supplied",
    "review is metadata-only",
    "metadata-only output review",
    "marketplace policy guidance is versioned first-pass metadata",
    "not live legal or platform-policy advice",
)

_PUBLIC_WARNING_USER_ACTION_MARKERS = (
    "insufficient",
    "api key",
    "base url",
    "not configured",
    "provider",
    "timeout",
    "timed out",
    "could not be downloaded",
    "bad_response_status_code",
    "gateway",
    "claim",
    "unsupported",
    "missing",
    "failed",
    "blocked",
    "too large",
    "invalid",
    "policy",
)

# These historical fields may stay on restored records so operators can read
# them, but they are not creative input for a new E-Commerce Brain run.  The
# list deliberately contains only retired E-Commerce execution concepts; it
# has no effect on General or Photography metadata.
_ECOMMERCE_RETIRED_EXECUTION_FIELDS = frozenset(
    {
        "ecommerce_recipe",
        "ecommerce_recipes",
        "image_recipes",
        "suite_slot_request",
        "suite_slots_requested",
        "ecommerce_business_goal",
        "ecommerce_selling_point",
        "ecommerce_buyer_intent",
        "ecommerce_visual_scene",
        "overlay_copy",
        "overlay_text",
        "copy_render_plan",
        "copy_render_plans",
        "text_pixel_delivery_internal",
        "text_pixel_delivery",
        "text_pixel_delivery_batch",
        "role_specific_generation_plan",
        "mode_execution_policy",
        "mode_role_recipe",
        "mode_role_key",
        "mode_role_label",
        "specialized_scenario_plan",
        "specialized_execution_summary",
        # Historic UI mode/preset values can be retained on an old record,
        # but cannot become creative input for a new LLM-native E-Commerce
        # request.
        "mode",
        "preset",
        "mode_id",
        "preset_id",
        "selected_mode_id",
        "selected_preset_id",
    }
)

VISUAL_AUTO_RETRY_RETRYABLE_ISSUES = {
    "weak_aesthetic_finish",
    "generic_stock_photo_finish",
    "flat_low_contrast_finish",
    "overexposed_washout",
    "underexposed_muddy_frame",
    "unbalanced_color_grade",
    "weak_subject_readability",
    "weak_depth_and_material_separation",
    "unstable_composition_balance",
    "overprocessed_hdr_finish",
    "uncanny_micro_detail",
    "low_resolution_output",
    "visible_text_artifact",
    "watermark_or_signature",
    "faint_corner_watermark",
    "ai_generated_badge_trace",
    "signature_like_artifact",
    "lower_right_mark_artifact",
    "third_party_aigc_metadata",
    "provider_provenance_mismatch",
    "commercial_cleanliness_failure",
    "collage_or_split_panel",
    "unrelated_object",
    "unrelated_product",
    "identity_drift",
    "hair_or_outfit_drift",
    "camera_distance_drift",
    "bone_structure_drift",
    "face_shape_drift",
    "cheek_jaw_chin_drift",
    "eye_shape_or_spacing_identity_drift",
    "eyebrow_eye_relationship_drift",
    "nose_mouth_relationship_identity_drift",
    "lip_contour_identity_drift",
    "age_impression_drift",
    "styling_changed_face_geometry",
    "archetype_overrode_reference_identity",
    "same_type_not_same_person",
    "identity_reference_underweighted",
    "identity_metric_below_commercial_target",
    "identity_metric_low",
    "beauty_archetype_overrode_reference",
    "same_type_but_different_person",
    "prompt_face_description_replaced_reference_geometry",
    "generic_sweet_model_replaced_reference",
    "source_lighting_overinherited",
    "source_color_temperature_overinherited",
    "source_scene_overinherited",
    "source_wardrobe_overinherited",
    "source_camera_mood_overinherited",
    "source_hair_overinherited",
    "source_makeup_overinherited",
    "source_color_grade_overinherited",
    "source_camera_overinherited",
    "source_whole_style_overinherited",
    "reference_used_as_style_when_identity_only",
    "prompt_owned_channel_ignored",
    "selected_anchor_overrode_current_prompt",
    "structured_appearance_lock_misapplied",
    "prompt_style_underweighted",
    "makeup_changed_face_geometry",
    "hair_change_replaced_identity",
    "retry_repaired_artifact_but_changed_identity",
    "prompt_mood_regression",
    "prompt_color_tone_regression",
    "approved_style_anchor_ignored",
    "identity_repair_damaged_prompt_direction",
    "overconstrained_identity_prompt",
    "scenario_specific_negative_overfit",
    "identity_card_missing",
    "identity_card_not_applied",
    "identity_feature_drift",
    "eyebrow_shape_drift",
    "eye_shape_or_spacing_drift",
    "nose_mouth_relationship_drift",
    "jaw_chin_direction_drift",
    "unflattering_feature_degradation",
    "beautiful_realism_balance_failure",
    "realism_made_subject_less_attractive",
    "pretty_but_too_ai_filtered",
    "real_but_unflattering",
    "skin_texture_beauty_balance_failure",
    "product_identity_drift",
    *APPAREL_CONSTRUCTION_REVIEW_ISSUES.values(),
    "nonhuman_subject_identity_drift",
    "nonhuman_subject_marking_drift",
    "nonhuman_subject_proportion_drift",
    "nonhuman_reference_used_as_style",
    "product_silhouette_drift",
    "label_or_pattern_drift",
    "material_structure_drift",
    "generic_product_replacement",
    "product_label_drift",
    "product_label_unreadable",
    "product_logo_or_label_obscured",
    "brand_asset_drift",
    "lighting_mismatch",
    "composition_mismatch",
    "scene_identity_drift",
    "background_space_drift",
    "camera_mood_drift",
    "reference_scene_replaced",
    "bad_hands_or_body",
    "face_artifact",
    "ai_face_render",
    "plastic_skin",
    "over_smoothed_skin",
    "missing_skin_texture",
    "over_retouching",
    "poreless_beauty_surface",
    "synthetic_fashion_face",
    "weak_photographic_imperfection",
    "synthetic_beauty_filter",
    "doll_like_face",
    "template_smile",
    "over_perfect_symmetry",
    "wax_skin_highlight",
    "uncanny_eye_expression",
    "same_ai_face_repetition",
    "beauty_app_face",
    "idol_photocard_polish",
    "skin_blur_retouching",
    "over_uniform_skin_tone",
    "over_sharp_ai_detail",
    "perfect_smile_repetition",
    "face_slimming_filter",
    "beautified_facial_geometry",
    "generic_ai_beauty_identity",
    "dull_complexion",
    "muddy_skin_tone",
    "underexposed_face",
    "harsh_facial_shadow",
    "overly_matte_documentary_look",
    "tired_expression",
    "unflattering_color_cast",
    "suppressed_fair_complexion",
    "forced_tan_or_bronze_cast",
    "gray_brown_skin_cast",
    "head_body_proportion_distortion",
    "oversized_head",
    "compressed_neck_shoulders",
    "unflattering_face_drift",
    "doll_like_child_face",
    "adultified_child_model",
    "synthetic_child_skin",
    "pageant_polish_child_face",
    "frozen_child_smile",
    "unreal_child_eyes",
    "unreal_child_teeth",
    "child_face_ai_render",
    "same_expression_repetition",
    "same_head_angle_repetition",
    "same_pose_repetition",
    "studio_only_when_lifestyle_requested",
    "role_collapse",
    "flat_catalog_lighting",
    "weak_lifestyle_context",
    "repeated_concept_or_prop",
    "reference_guard_ignored",
    "low_commercial_finish",
    "project_continuity_warning",
    "quality_warning",
    "mode_role_gap",
    "mode_role_metadata_missing",
    "mode_role_duplication",
    "delivery_suite_role_collapse",
    "deliverable_intent_mismatch",
    "delivery_set_role_mismatch",
    "delivery_evidence_dimension_mismatch",
    "format_layout_collapse",
    "selection_candidate_distance_risk",
    "text_background_readability_failure",
}

DELIVERY_IDENTITY_HARD_GATE_ISSUES = {
    "identity_drift",
    "nonhuman_subject_identity_drift",
    "nonhuman_subject_marking_drift",
    "nonhuman_subject_proportion_drift",
    "identity_card_missing",
    "identity_card_not_applied",
    "identity_feature_drift",
    "bone_structure_drift",
    "face_shape_drift",
    "cheek_jaw_chin_drift",
    "eye_shape_or_spacing_identity_drift",
    "eyebrow_eye_relationship_drift",
    "nose_mouth_relationship_identity_drift",
    "lip_contour_identity_drift",
    "styling_changed_face_geometry",
    "archetype_overrode_reference_identity",
    "same_type_not_same_person",
    "same_type_but_different_person",
    "identity_reference_underweighted",
    "prompt_face_description_replaced_reference_geometry",
    "generic_sweet_model_replaced_reference",
}

DELIVERY_PROMPT_CHANNEL_HARD_GATE_ISSUES = {
    "nonhuman_reference_used_as_style",
    "prompt_owned_channel_ignored",
    "selected_anchor_overrode_current_prompt",
    "reference_used_as_style_when_identity_only",
    "prompt_style_underweighted",
    "identity_repair_damaged_prompt_direction",
    "prompt_mood_regression",
    "prompt_color_tone_regression",
    "source_hair_overinherited",
    "source_makeup_overinherited",
    "source_wardrobe_overinherited",
    "source_lighting_overinherited",
    "source_color_temperature_overinherited",
    "source_color_grade_overinherited",
    "source_scene_overinherited",
    "source_camera_overinherited",
    "source_camera_mood_overinherited",
    "source_whole_style_overinherited",
}

DELIVERY_TEMPLATE_EVIDENCE_HARD_GATE_ISSUES = {
    "delivery_evidence_dimension_mismatch",
}

VISUAL_AUTO_RETRY_NON_RETRYABLE_ISSUES = {
    "provider_error",
    "provider_timeout",
    "rate_limit",
    "insufficient_balance",
    "missing_api_key",
    "policy_or_safety_block",
    "unsupported_file",
    "file_download_failure",
    "low_confidence_review",
    "manual_review",
    "subjective_quality_only",
    "conflicting_user_request",
}

POST_GENERATION_REVIEW_RESUMABLE_PROVIDER_ISSUES = {
    "provider_timeout",
    "provider_error",
    "vision_provider_unavailable",
    "vision_provider_not_configured",
}

VISUAL_RETRY_PATCH_FIELDS = (
    "prompt_additions",
    "negative_additions",
    "negative_prompt_additions",
    "reference_requirements",
    "identity_reinforcement",
    "product_reinforcement",
    "brand_asset_reinforcement",
    "composition_repair",
    "artifact_repair",
    "object_removal_instruction",
)

ASSET_ROLE_PUBLIC_LABELS = {
    "product_reference": "product reference",
    "style_reference": "style reference",
    "logo_reference": "logo reference",
    "face_reference": "portrait reference",
    "nonhuman_identity_reference": "individual non-human subject reference",
    "background_reference": "background reference",
    "composition_reference": "layout reference",
    "color_reference": "color reference",
    "negative_reference": "avoidance reference",
    "unknown_reference": "reference image",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


V3_FAILED_ARTIFACT_RETENTION_DAYS = 7
V3_FAILED_ARTIFACT_STATUSES = frozenset(
    {
        ProductJobStatusValue.FAILED,
        ProductJobStatusValue.BLOCKED,
        ProductJobStatusValue.NOT_FOUND,
    }
)


def _failure_artifact_expiry(record: "ProductJobRecord") -> str | None:
    # Some legacy/read-only adapters expose only the fields needed for their
    # projection. They are not failure artifacts and must remain readable.
    if getattr(record, "status", None) not in V3_FAILED_ARTIFACT_STATUSES:
        return None
    try:
        updated_at = datetime.fromisoformat(str(getattr(record, "updated_at", "")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return (updated_at.astimezone(timezone.utc) + timedelta(days=V3_FAILED_ARTIFACT_RETENTION_DAYS)).isoformat()


def _failed_artifact_expired(record: "ProductJobRecord", *, now: datetime | None = None) -> bool:
    expiry = _failure_artifact_expiry(record)
    if expiry is None:
        return False
    try:
        expires_at = datetime.fromisoformat(expiry)
    except ValueError:
        return False
    current = now or datetime.now(timezone.utc)
    return current >= expires_at


_ECOMMERCE_AUTHORITY_SNAPSHOT_SCHEMA = "v3_product_api_ecommerce_authority_snapshot_v1"


def _ecommerce_authority_snapshot_digest(
    *,
    schema_version: str,
    project_id: str,
    job_id: str,
    requested_output_count: int,
    asset_ids: tuple[str, ...],
    admission: ProductTruthAdmission,
    projections: tuple[PhysicalProductReferenceProjection, ...],
    physical_plans: tuple[PhysicalRendererReferencePlan, ...],
) -> str:
    payload = {
        "schema_version": schema_version,
        "project_id": project_id,
        "job_id": job_id,
        "requested_output_count": requested_output_count,
        "asset_ids": list(asset_ids),
        "admission": admission.model_dump(),
        "projections": [item.model_dump() for item in projections],
        "physical_plans": [item.model_dump(mode="json") for item in physical_plans],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ProductApiEcommerceAuthoritySnapshot:
    """Typed Product API authority retained outside request/result metadata.

    The request and planning metadata still carry compatibility projections for
    older readers.  Native authority consumers use this snapshot instead, so a
    mutable metadata copy cannot become the source of Product Truth.
    """

    schema_version: str
    project_id: str
    job_id: str
    requested_output_count: int
    asset_ids: tuple[str, ...]
    admission: ProductTruthAdmission
    projections: tuple[PhysicalProductReferenceProjection, ...]
    physical_plans: tuple[PhysicalRendererReferencePlan, ...]
    authority_digest: str

    @classmethod
    def from_records(
        cls,
        *,
        project_id: str,
        job_id: str,
        asset_ids: tuple[str, ...],
        admission: ProductTruthAdmission,
        projections: tuple[PhysicalProductReferenceProjection, ...],
        physical_plans: tuple[PhysicalRendererReferencePlan, ...],
    ) -> "ProductApiEcommerceAuthoritySnapshot":
        requested_output_count = len(asset_ids)
        schema_version = _ECOMMERCE_AUTHORITY_SNAPSHOT_SCHEMA
        authority_digest = _ecommerce_authority_snapshot_digest(
            schema_version=schema_version,
            project_id=project_id,
            job_id=job_id,
            requested_output_count=requested_output_count,
            asset_ids=asset_ids,
            admission=admission,
            projections=projections,
            physical_plans=physical_plans,
        )
        return cls(
            schema_version=schema_version,
            project_id=project_id,
            job_id=job_id,
            requested_output_count=requested_output_count,
            asset_ids=asset_ids,
            admission=admission,
            projections=projections,
            physical_plans=physical_plans,
            authority_digest=authority_digest,
        )

    @classmethod
    def from_payload(cls, value: Any) -> "ProductApiEcommerceAuthoritySnapshot":
        expected_keys = {
            "schema_vers…208035 tokens truncated…ates": True,
                "terminal_attempt_limit_per_output": 1,
                "terminal_evidence_only": True,
            },
        }

    def _bind_ecommerce_physical_renderer_reference_plans(
        self,
        request: CreateCreativeJobRequest,
        *,
        admission: ProductTruthAdmission,
        projections: dict[str, dict[str, Any]],
        generation_plans: list[Any],
        metadata: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Freeze one exact physical renderer plan for every E-Commerce output."""

        context = metadata.get("ecommerce_creative_context")
        budget = context.get("provider_reference_budget") if isinstance(context, dict) else {}
        try:
            maximum_reference_images = min(
                int(
                    budget.get(
                        "max_total_reference_images",
                        self._configured_provider_reference_capacity(),
                    )
                    if isinstance(budget, dict)
                    else self._configured_provider_reference_capacity()
                ),
                DOC269_MAX_REFERENCE_IMAGES,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("doc269_reference_capacity_invalid") from exc
        if maximum_reference_images < 1:
            raise ValueError("doc269_reference_capacity_invalid")
        uploaded_assets = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
            for item in self.asset_store.resolve_uploaded_assets(list(request.uploaded_asset_ids))
        ]
        locked_identity_references = metadata.get("ecommerce_locked_identity_reference_assets")
        if not isinstance(locked_identity_references, list):
            locked_identity_references = []
        plans: dict[str, dict[str, Any]] = {}
        for output_index, raw_projection in projections.items():
            projection = PhysicalProductReferenceProjection.from_mapping(raw_projection)
            selected_continuations = self._doc269_selected_continuation_references(metadata)
            try:
                plan = build_physical_renderer_reference_plan(
                    admission=admission,
                    projection=projection,
                    uploaded_assets=uploaded_assets,
                    locked_identity_references=locked_identity_references,
                    selected_continuation_references=selected_continuations,
                    maximum_reference_images=maximum_reference_images,
                )
            except ValueError as exc:
                raise ValueError("doc269_physical_renderer_reference_plan_invalid") from exc
            if output_index != str(plan.output_index):
                raise ValueError("doc269_reference_plan_output_mismatch")
            plans[output_index] = plan.model_dump(mode="json")
        if set(plans) != set(projections):
            raise ValueError("doc269_reference_plan_output_mismatch")
        return plans

    def _doc269_selected_continuation_references(
        self,
        metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Resolve only Project Mode's already-validated Doc265 selection."""

        raw_admissions = metadata.get("doc269_selected_continuation_admissions", [])
        if not isinstance(raw_admissions, list) or len(raw_admissions) > 1:
            raise ValueError("doc269_continuation_admission_invalid")
        project_id = str(metadata.get("project_id") or "").strip()
        resolved: list[dict[str, Any]] = []
        for raw_admission in raw_admissions:
            if not isinstance(raw_admission, dict):
                raise ValueError("doc269_continuation_admission_invalid")
            required = {
                "selection_authority": "doc265_project_mode",
                "project_id": project_id,
                "source_type": "generated_selected",
                "use_policy": "style",
                "role": "selected_continuation_reference",
                "channel": "generated_selected",
            }
            if not project_id or any(
                str(raw_admission.get(key) or "").strip() != expected
                for key, expected in required.items()
            ):
                raise ValueError("doc269_continuation_admission_invalid")
            output_id = str(raw_admission.get("output_id") or "").strip()
            source_job_id = str(raw_admission.get("source_job_id") or "").strip()
            reference_id = str(raw_admission.get("reference_id") or "").strip()
            expected_digest = str(raw_admission.get("content_sha256") or "").strip().lower()
            project_job_ids = raw_admission.get("project_job_ids")
            if (
                not output_id
                or not source_job_id
                or not reference_id
                or not isinstance(project_job_ids, list)
                or source_job_id not in project_job_ids
                or len(project_job_ids) != len(set(project_job_ids))
                or any(not str(job_id or "").strip() for job_id in project_job_ids)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
            ):
                raise ValueError("doc269_continuation_admission_invalid")
            record = self.output_store.get_output(output_id)
            path = Path(str(getattr(record, "file_path", "") or "")) if record else None
            if (
                record is None
                or str(getattr(record, "output_id", "") or "") != output_id
                or str(getattr(record, "job_id", "") or "") != source_job_id
                or path is None
                or not path.is_file()
            ):
                raise ValueError("doc269_continuation_admission_invalid")
            try:
                actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError("doc269_continuation_admission_invalid") from exc
            if actual_digest != expected_digest:
                raise ValueError("doc269_continuation_admission_invalid")
            resolved.append(
                {
                    "output_id": output_id,
                    "source_type": "generated_selected",
                    "role": "selected_continuation_reference",
                    "file_path": str(path.resolve()),
                    "selection_binding": {
                        "selection_authority": "doc265_project_mode",
                        "project_id": project_id,
                        "reference_id": reference_id,
                        "output_id": output_id,
                        "source_job_id": source_job_id,
                        "project_job_ids": [str(job_id).strip() for job_id in project_job_ids],
                        "content_sha256": actual_digest,
                    },
                }
            )
        return resolved

    @staticmethod
    def _bind_ecommerce_n1_product_primary_presentation(raw_plan: dict[str, Any]) -> None:
        """Issue the specialized N=1 product-primary role on fresh plans only."""

        deliverables = raw_plan.get("deliverables")
        if not isinstance(deliverables, list) or len(deliverables) != 1:
            return
        deliverable = deliverables[0]
        if not isinstance(deliverable, dict) or deliverable.get("output_index") != 1:
            raise ValueError("ecommerce_product_primary_presentation_invalid")
        metadata = deliverable.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("ecommerce_product_primary_presentation_invalid")
        metadata["product_truth_selection_role"] = "product_primary_presentation"
        metadata["product_primary_presentation_contract"] = "doc267_v3_product_api_n1"

    @staticmethod
    def _assert_ecommerce_locked_identity_capacity(
        metadata: dict[str, Any],
        *,
        projections: dict[str, dict[str, Any]],
    ) -> None:
        """Fail closed before dispatch when a frozen identity/product plan cannot fit."""

        references = metadata.get("ecommerce_locked_identity_reference_assets")
        if references is None:
            return
        if not isinstance(references, list) or len(references) != 3:
            raise ValueError("ecommerce_locked_identity_reference_count_invalid")
        identity_ids = [
            str(item.get("output_id") or item.get("asset_id") or "").strip()
            for item in references
            if isinstance(item, dict)
        ]
        if (
            len(identity_ids) != 3
            or len(identity_ids) != len(set(identity_ids))
            or any(not source_id for source_id in identity_ids)
            or any(
                not isinstance(item, dict)
                or str(item.get("role") or "").strip() != "face_reference"
                or str(item.get("source_type") or "").strip() != "visual_asset_library"
                or str(item.get("use_policy") or "").strip() != "identity"
                or not bool((item.get("metadata") or {}).get("doc267_locked_people_identity"))
                or not bool((item.get("metadata") or {}).get("canonical_output_binding"))
                or not bool((item.get("metadata") or {}).get("visual_asset_library_evidence"))
                for item in references
            )
        ):
            raise ValueError("ecommerce_locked_identity_reference_invalid")
        identity_count = len(references)
        ecommerce_context = metadata.get("ecommerce_creative_context")
        budget = (
            ecommerce_context.get("provider_reference_budget")
            if isinstance(ecommerce_context, dict)
            and isinstance(ecommerce_context.get("provider_reference_budget"), dict)
            else {}
        )
        try:
            total_cap = int(budget.get("max_total_reference_images"))
        except (TypeError, ValueError):
            raise ValueError("ecommerce_locked_identity_capacity_missing") from None
        if total_cap < 1:
            raise ValueError("ecommerce_locked_identity_capacity_missing")
        for raw_projection in projections.values():
            projection = PhysicalProductReferenceProjection.from_mapping(raw_projection)
            if identity_count + len(projection.selected_product_asset_ids) > total_cap:
                raise ValueError("ecommerce_locked_identity_capacity_exceeded")

    @staticmethod
    def _validate_ecommerce_final_contract_metadata(
        metadata: dict[str, Any],
        *,
        job_id: str,
    ) -> tuple[ProductTruthAdmission, dict[str, dict[str, Any]], dict[str, Any]]:
        """Validate one final E-Commerce contract without selecting a fallback copy."""

        if (
            str(metadata.get("professional_ecommerce_contract_authority") or "")
            != "v3_product_api"
            or str(metadata.get("professional_ecommerce_contract_job_id") or "").strip()
            != job_id
            or str(metadata.get("job_id") or "").strip() != job_id
        ):
            raise ValueError("ecommerce_final_contract_binding_invalid")
        raw_admission = metadata.get("professional_ecommerce_product_truth_admission")
        raw_projections = metadata.get("professional_ecommerce_physical_product_projections")
        singular_projection = metadata.get("professional_ecommerce_physical_product_projection")
        if not isinstance(raw_admission, dict) or not isinstance(raw_projections, dict):
            raise ValueError("ecommerce_final_contract_missing")
        try:
            admission = ProductTruthAdmission.from_mapping(raw_admission)
        except ValueError as exc:
            raise ValueError("ecommerce_final_contract_admission_invalid") from exc
        if admission.job_id != job_id or not raw_projections:
            raise ValueError("ecommerce_final_contract_binding_invalid")
        projections: dict[str, dict[str, Any]] = {}
        for output_key, raw_projection in raw_projections.items():
            if not isinstance(output_key, str) or not isinstance(raw_projection, dict):
                raise ValueError("ecommerce_final_contract_projection_invalid")
            try:
                projection = PhysicalProductReferenceProjection.from_mapping(raw_projection)
                projection.validate_against(admission)
            except ValueError as exc:
                raise ValueError("ecommerce_final_contract_projection_invalid") from exc
            if projection.job_id != job_id or output_key != str(projection.output_index):
                raise ValueError("ecommerce_final_contract_binding_invalid")
            projections[output_key] = raw_projection
        primary = projections.get("1") or next(iter(projections.values()))
        if singular_projection != primary:
            raise ValueError("ecommerce_final_contract_projection_invalid")
        return admission, projections, primary

    def _assert_ecommerce_final_contract_for_record(self, record: ProductJobRecord) -> None:
        """Require exact request/result/plan parity before E-Commerce materialization."""

        if not self._is_ecommerce_request(record.request):
            return
        request_metadata = dict(record.request.metadata or {})
        if request_metadata.get("professional_product_truth_required") is not True:
            return
        _admission, projections, primary = self._validate_ecommerce_final_contract_metadata(
            request_metadata,
            job_id=record.job_id,
        )
        planning_result = record.planning_result
        if planning_result is None or planning_result.creative_job.job_id != record.job_id:
            raise ValueError("ecommerce_final_contract_planning_binding_invalid")
        contract_keys = (
            "professional_ecommerce_contract_authority",
            "professional_ecommerce_contract_job_id",
            "job_id",
            "professional_ecommerce_product_truth_admission",
            "professional_ecommerce_physical_product_projections",
            "professional_ecommerce_physical_product_projection",
        )
        expected = {key: request_metadata.get(key) for key in contract_keys}
        for metadata in [dict(planning_result.metadata or {}), *[
            dict(plan.metadata or {}) for plan in planning_result.generation_plans
        ]]:
            if any(metadata.get(key) != value for key, value in expected.items()):
                raise ValueError("ecommerce_final_contract_copy_mismatch")
            self._validate_ecommerce_final_contract_metadata(metadata, job_id=record.job_id)
        if not projections or primary != request_metadata.get(
            "professional_ecommerce_physical_product_projection"
        ):
            raise ValueError("ecommerce_final_contract_projection_invalid")

    def _record_ecommerce_runtime_provenance(self, request: CreateCreativeJobRequest, runtime_result: Any, *, stage: str) -> None:
        """Persist factual inputs and fail-closed reasons without replaying a recipe.

        This is an E-Commerce-only audit envelope.  It makes the source of a
        blocked state queryable from project/history recovery while keeping the
        actual Brain request free of legacy recipe, slot, and overlay values.
        """

        if not self._is_ecommerce_request(request):
            return
        metadata = dict(request.metadata or {})
        context = metadata.get("ecommerce_creative_context")
        context = dict(context) if isinstance(context, dict) else {}
        product_truth = context.get("product_truth")
        product_truth = dict(product_truth) if isinstance(product_truth, dict) else {}
        platform = context.get("platform_constraints")
        platform = dict(platform) if isinstance(platform, dict) else {}
        seller_inputs = context.get("seller_inputs")
        seller_inputs = dict(seller_inputs) if isinstance(seller_inputs, dict) else {}
        status = getattr(getattr(runtime_result, "status", None), "value", str(getattr(runtime_result, "status", "unknown")))
        warnings = list(getattr(runtime_result, "warnings", []) or [])
        reason_codes = self._ecommerce_failure_reason_codes(warnings) if status == "blocked" else []
        event = {
            "stage": stage,
            "runtime_status": status,
            "fail_closed": status == "blocked",
            "failure_reason_codes": reason_codes,
        }
        prior = metadata.get("ecommerce_runtime_provenance")
        prior_events = list(prior.get("events") or []) if isinstance(prior, dict) else []
        metadata["ecommerce_runtime_provenance"] = {
            "schema_version": "ecommerce_runtime_provenance_v1",
            "source": "V3ProductApiService",
            "factual_context": {
                "context_id": context.get("context_id"),
                "source_version": context.get("source_version"),
                "product_evidence_sources": list(product_truth.get("evidence_sources") or []),
                "seller_input_fields": sorted(
                    key for key in seller_inputs if not str(key).endswith("_source")
                ),
                "platform_profile_id": platform.get("profile_id"),
                "platform_profile_version": platform.get("profile_version"),
                "platform_profile_status": platform.get("profile_status"),
            },
            "legacy_execution": dict(metadata.get("ecommerce_legacy_execution_ignored") or {}),
            "events": [*prior_events, event][-8:],
        }
        request.metadata = metadata

    @staticmethod
    def _ecommerce_failure_reason_codes(warnings: list[Any]) -> list[str]:
        codes: list[str] = []
        for warning in warnings:
            text = str(warning or "").strip()
            if not text:
                continue
            if text.startswith("capability_activation_failed:"):
                text = text.split(":", 1)[1].strip()
            code = text.split(":", 1)[0].strip()
            if code and " " not in code:
                codes.append(code)
        return list(dict.fromkeys(codes))

    def _bind_internal_copy_render_plan(self, request: CreateCreativeJobRequest) -> None:
        """Mark a legacy plan as read-compatible without binding or executing it."""

        metadata = dict(request.metadata or {})
        envelope = metadata.get("text_pixel_delivery_internal")
        if isinstance(envelope, dict):
            metadata["text_pixel_delivery_internal"] = {
                **envelope,
                "legacy_read_compatibility": True,
                "binding_skipped_reason": "deterministic_text_pixel_delivery_retired",
            }
            request.metadata = metadata
            return

    def _seed_ecommerce_slot_root_lineage(self, request: CreateCreativeJobRequest, job_id: str) -> None:
        metadata = dict(request.metadata or {})
        if not metadata.get("ecommerce_slot_lineage_seed") or isinstance(metadata.get("ecommerce_slot_lineage"), dict):
            return
        plan_id = str(metadata.get("capability_activation_plan_id") or "").strip()
        if not plan_id:
            return
        metadata["ecommerce_slot_lineage"] = {
            "schema_version": "ecommerce_slot_lineage_v1",
            "root_job_id": job_id,
            "parent_job_id": None,
            "parent_slot_id": None,
            "continuation_kind": "ecommerce_root",
            "continuation_correction_note": None,
            "new_evidence_asset_ids": [],
            "capability_activation_plan_id": plan_id,
            "plan_amendment_id": None,
            "created_at": _utc_now_iso(),
        }
        request.metadata = metadata

    def _seed_photography_role_root_lineage(self, request: CreateCreativeJobRequest, job_id: str) -> None:
        """Seed append-only professional-set lineage after planning is frozen."""

        metadata = dict(request.metadata or {})
        if isinstance(metadata.get("photography_role_lineage"), dict):
            return
        specialized = metadata.get("specialized_scenario_plan")
        if not isinstance(specialized, dict):
            return
        execution = specialized.get("execution_plan")
        if not isinstance(execution, dict):
            return
        execution_metadata = execution.get("metadata")
        if not isinstance(execution_metadata, dict) or not execution_metadata.get("professional_set"):
            return
        plan_id = str(metadata.get("capability_activation_plan_id") or "").strip()
        set_id = str(execution_metadata.get("photography_set_id") or "").strip()
        role_recipes = execution.get("role_recipes")
        role_ids = [
            str(item.get("role_key") or "").strip()
            for item in role_recipes
            if isinstance(item, dict) and str(item.get("role_key") or "").strip()
        ] if isinstance(role_recipes, list) else []
        if not plan_id or not set_id or not role_ids:
            return
        metadata["photography_role_lineage"] = {
            "schema_version": "photography_role_lineage_v1",
            "root_job_id": job_id,
            "parent_job_id": None,
            "parent_role_id": None,
            "root_set_id": set_id,
            "continuation_kind": "photography_professional_set_root",
            "continuation_correction_note": None,
            "new_reference_asset_ids": [],
            "capability_activation_plan_id": plan_id,
            "plan_amendment_id": None,
            "created_at": _utc_now_iso(),
        }
        request.metadata = metadata

    def _empty_balance_estimate(self) -> dict[str, Any]:
        return self._balance_estimate_to_dict(
            V3BalanceEstimate(
                credits_required=0,
                currency="credits",
                metadata={"runtime_mode": "blocked_before_planning", "asset_count": 0},
            )
        )

    def _estimate_for_result(self, result: PlanningResult) -> dict[str, Any]:
        estimate = self.balance_adapter.estimate_planning_cost(len(result.series_plan.assets))
        return self._balance_estimate_to_dict(estimate)

    def _balance_estimate_to_dict(self, estimate: V3BalanceEstimate) -> dict[str, Any]:
        return {
            "credits_required": estimate.credits_required,
            "currency": estimate.currency,
            "metadata": {**estimate.metadata, "adapter": self.balance_adapter.adapter_name},
        }

    def _coerce_create_job_request(self, request: CreateCreativeJobRequest | dict[str, Any]) -> CreateCreativeJobRequest:
        if isinstance(request, CreateCreativeJobRequest):
            return request
        return CreateCreativeJobRequest.model_validate(request)

    def _coerce_generate_request(self, request: GenerateJobRequest | dict[str, Any]) -> GenerateJobRequest:
        if isinstance(request, GenerateJobRequest):
            generated = request
        else:
            generated = GenerateJobRequest.model_validate(request)
        if "provider_image_options" in dict(generated.metadata or {}):
            raise ValueError("runtime_metadata_server_owned: provider_image_options")
        return generated

    def _coerce_select_request(self, request: SelectResultRequest | dict[str, Any]) -> SelectResultRequest:
        if isinstance(request, SelectResultRequest):
            return request
        return SelectResultRequest.model_validate(request)

    def _coerce_create_brand_request(self, request: CreateBrandRequest | dict[str, Any]) -> CreateBrandRequest:
        if isinstance(request, CreateBrandRequest):
            return request
        return CreateBrandRequest.model_validate(request)


V3ProductApi = V3ProductApiService


def _doc270_canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_default_product_api() -> V3ProductApiService:
    return V3ProductApiService()
