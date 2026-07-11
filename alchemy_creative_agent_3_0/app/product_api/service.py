"""Framework-neutral V3 product API service.

Route handlers can wrap this service later. The service deliberately exposes
product concepts such as jobs, asset series, candidates, selected result, and
balance estimate instead of image-model controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any

from ..app_shell.navigation import get_navigation_entry
from ..app_shell.routes import API_NAMESPACE, get_route_contracts
from ..brand_memory.profile_service import BrandProfileService
from ..creative_core.rules import RULE_VERSION, stable_id
from ..generation_router import GenerationRouter, ProductionImageGenerationProvider
from ..platform_adapters import V3BalanceAdapter, V3BalanceEstimate
from ..scenario_packs.ecommerce import EcommercePackOutput, EcommerceScenarioPackPlanner
from ..scenario_packs import ScenarioPackResolution
from ..scenario_runtime import ScenarioRuntime
from ..shared_capabilities import CapabilityRunResult
from ..shared_capabilities.visual_cluster import (
    HumanPhotorealismLayer,
    ModeAwareRoleDirector,
    OutputQualityReviewMerger,
    VisionOutputInspector,
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
    GenerateJobRequest,
    GeneralCreativeCapabilitySummary,
    ProductJobStatus,
    ProductJobStatusValue,
    ScenarioSummary,
    SelectResultRequest,
    SelectionResponse,
    SelectedResult,
    StyleContinuationSummary,
    V3AssetContentUploadRequest,
    V3AssetUploadCreateRequest,
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
    "ecommerce_slot_mismatch",
    "ecommerce_suite_role_mismatch",
    "format_layout_collapse",
    "selection_candidate_distance_risk",
}

DELIVERY_IDENTITY_HARD_GATE_ISSUES = {
    "identity_drift",
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
    "background_reference": "background reference",
    "composition_reference": "layout reference",
    "color_reference": "color reference",
    "negative_reference": "avoidance reference",
    "unknown_reference": "reference image",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProductJobRecord:
    request: CreateCreativeJobRequest
    status: ProductJobStatusValue
    job_id_value: str | None = None
    planning_result: PlanningResult | None = None
    generation_result: PlanningResult | None = None
    scenario_resolution: ScenarioPackResolution | None = None
    capability_run: CapabilityRunResult | None = None
    selected_result: SelectedResult | None = None
    lifecycle: JobLifecycleRecord | None = None
    balance_estimate: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    @property
    def job_id(self) -> str:
        if self.job_id_value:
            return self.job_id_value
        result = self.generation_result or self.planning_result
        if result is None:
            return "job_unavailable"
        return result.creative_job.job_id


class InMemoryProductJobStore:
    """Small deterministic job store for V3 product API tests and adapters."""

    def __init__(self) -> None:
        self._records: dict[str, ProductJobRecord] = {}

    def save(self, record: ProductJobRecord) -> ProductJobRecord:
        existing = self._records.get(record.job_id)
        if existing is not None:
            record.created_at = existing.created_at
        record.updated_at = _utc_now_iso()
        self._records[record.job_id] = record
        return record

    def get(self, job_id: str) -> ProductJobRecord | None:
        return self._records.get(job_id)

    def list_recent(self, limit: int = 20) -> list[ProductJobRecord]:
        bounded_limit = max(1, min(int(limit or 20), 100))
        return sorted(self._records.values(), key=lambda record: record.updated_at, reverse=True)[:bounded_limit]

    def delete_many(self, job_ids: list[str]) -> int:
        deleted = 0
        for job_id in list(dict.fromkeys(str(item or "").strip() for item in job_ids)):
            if job_id and self._records.pop(job_id, None) is not None:
                deleted += 1
        return deleted

    def count(self) -> int:
        return len(self._records)


class V3ProductApiService:
    """V3-owned product API facade over the Creative Core."""

    def __init__(
        self,
        brand_profile_service: BrandProfileService | None = None,
        balance_adapter: V3BalanceAdapter | None = None,
        scenario_runtime: ScenarioRuntime | None = None,
        job_store: InMemoryProductJobStore | None = None,
        ecommerce_planner: EcommerceScenarioPackPlanner | None = None,
        asset_store: V3UploadedAssetStore | None = None,
        output_store: V3GeneratedOutputStore | None = None,
        output_resolver: GeneratedOutputResolver | None = None,
        vision_inspector: VisionOutputInspector | None = None,
        review_merger: OutputQualityReviewMerger | None = None,
        mode_role_director: ModeAwareRoleDirector | None = None,
    ) -> None:
        self.brand_profile_service = brand_profile_service or BrandProfileService()
        self.balance_adapter = balance_adapter or V3BalanceAdapter()
        self.job_store = job_store or InMemoryProductJobStore()
        self.ecommerce_planner = ecommerce_planner or EcommerceScenarioPackPlanner()
        self.asset_store = asset_store or V3UploadedAssetStore()
        self.output_store = output_store or V3GeneratedOutputStore()
        self.scenario_runtime = scenario_runtime or ScenarioRuntime(
            brand_profile_service=self.brand_profile_service,
            generation_router=GenerationRouter(
                production_provider=ProductionImageGenerationProvider(output_store=self.output_store),
            ),
        )
        self.output_resolver = output_resolver or GeneratedOutputResolver(self.output_store)
        self.vision_inspector = vision_inspector or VisionOutputInspector()
        self.review_merger = review_merger or OutputQualityReviewMerger()
        self.mode_role_director = mode_role_director or ModeAwareRoleDirector()

    def create_creative_job(self, request: CreateCreativeJobRequest | dict[str, Any]) -> ProductJobStatus:
        create_request = self._coerce_create_job_request(request)
        runtime_result = self.scenario_runtime.plan_job(self._runtime_request_payload(create_request))
        planning_result = runtime_result.planning_result
        estimate = self._estimate_for_result(planning_result) if planning_result else self._empty_balance_estimate()
        status = ProductJobStatusValue.PLANNED if planning_result else ProductJobStatusValue.BLOCKED
        job_id = (
            planning_result.creative_job.job_id
            if planning_result
            else stable_id(
                "job",
                create_request.user_input,
                create_request.effective_brand_id,
                runtime_result.scenario_resolution.manifest.scenario_id,
            )
        )
        record = ProductJobRecord(
            request=create_request,
            status=status,
            job_id_value=job_id,
            planning_result=planning_result,
            scenario_resolution=runtime_result.scenario_resolution,
            capability_run=runtime_result.capability_run,
            balance_estimate=estimate,
            warnings=list(runtime_result.warnings),
        )
        record.lifecycle = self._build_lifecycle(record)
        self.job_store.save(record)
        return self._status_from_record(record)

    def create_job(self, request: CreateCreativeJobRequest | dict[str, Any]) -> ProductJobStatus:
        return self.create_creative_job(request)

    def create_uploaded_asset(self, request: V3AssetUploadCreateRequest | dict[str, Any]) -> V3UploadedAssetRecord:
        return self.asset_store.create_upload(request)

    def store_uploaded_asset_content(
        self,
        asset_id: str,
        request: V3AssetContentUploadRequest | dict[str, Any],
    ) -> V3UploadedAssetRecord | None:
        return self.asset_store.store_content(asset_id, request)

    def complete_uploaded_asset(self, asset_id: str) -> V3UploadedAssetRecord | None:
        return self.asset_store.complete_upload(asset_id)

    def get_uploaded_asset(self, asset_id: str) -> V3UploadedAssetRecord | None:
        return self.asset_store.get_upload(asset_id)

    def read_uploaded_asset_content(self, asset_id: str) -> tuple[bytes, str] | None:
        return self.asset_store.read_content(asset_id)

    def get_job(self, job_id: str) -> ProductJobStatus:
        record = self.job_store.get(job_id)
        if record is None:
            restored = self._status_from_output_store(job_id)
            return restored or self._not_found_status(job_id)
        return self._status_from_record(record)

    def list_history(self, limit: int = 20) -> V3JobHistoryResponse:
        bounded_limit = max(1, min(int(limit or 20), 100))
        records = self.job_store.list_recent(bounded_limit)
        record_items = [self._history_item_from_record(record) for record in records]
        known_job_ids = {item.job_id for item in record_items}
        restored_items = [
            item for item in self._history_items_from_output_store(bounded_limit) if item.job_id not in known_job_ids
        ]
        items = sorted([*record_items, *restored_items], key=lambda item: item.updated_at or item.created_at, reverse=True)[
            :bounded_limit
        ]
        return V3JobHistoryResponse(
            api_namespace=API_NAMESPACE,
            route=get_route_contracts()["history"],
            total=len(items),
            limit=bounded_limit,
            items=items,
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
                "imports_v1_v2_runtime": False,
                "imports_lab_runtime": False,
            },
        )

    def generate_asset_series(
        self,
        job_id: str,
        request: GenerateJobRequest | dict[str, Any] | None = None,
    ) -> ProductJobStatus:
        record = self.job_store.get(job_id)
        if record is None:
            return self._not_found_status(job_id)
        generate_request = self._coerce_generate_request(request or {})
        if not self.balance_adapter.has_available_credits(record.balance_estimate.get("credits_required", 0)):
            record.status = ProductJobStatusValue.BLOCKED
            record.warnings.append("Insufficient V3 balance adapter credits for this operation.")
            self.job_store.save(record)
            return self._status_from_record(record)
        if record.scenario_resolution is not None and not record.scenario_resolution.can_create_jobs:
            record.status = ProductJobStatusValue.BLOCKED
            record.warnings.extend(record.scenario_resolution.warnings)
            record.lifecycle = self._build_lifecycle(record)
            self.job_store.save(record)
            return self._status_from_record(record)
        provider_strategy = self._provider_strategy_for_generate(record, generate_request)
        if generate_request.metadata:
            record.request.metadata = {**dict(record.request.metadata), **dict(generate_request.metadata)}
        try:
            generation_runtime_result = self.scenario_runtime.generate_job(
                self._runtime_request_payload(record.request),
                mock_profile=QUALITY_MODE_TO_MOCK_PROFILE[generate_request.quality_mode],
                apply_memory_update=False,
                provider_strategy=provider_strategy,
                quality_mode=generate_request.quality_mode,
            )
        except Exception as exc:
            record.status = ProductJobStatusValue.BLOCKED
            provider_failure_retry = self._provider_failure_retry_summary_from_exception(exc)
            if provider_failure_retry:
                record.request.metadata = {
                    **dict(record.request.metadata),
                    "provider_failure_retry": provider_failure_retry,
                    "provider_failure_retry_exhausted": provider_failure_retry.get("final_status") == "failed",
                }
            record.warnings.append(self._generation_failure_message(exc, provider_strategy))
            record.lifecycle = self._build_lifecycle(record)
            self.job_store.save(record)
            return self._status_from_record(record)
        if generation_runtime_result.generation_result is None:
            record.status = ProductJobStatusValue.BLOCKED
            record.scenario_resolution = generation_runtime_result.scenario_resolution
            record.capability_run = generation_runtime_result.capability_run
            record.warnings.extend(generation_runtime_result.warnings)
            record.lifecycle = self._build_lifecycle(record)
            self.job_store.save(record)
            return self._status_from_record(record)
        generation_result = generation_runtime_result.generation_result
        generation_result = self._attach_post_generation_review(record, generation_result, generate_request)
        generation_result = self._run_visual_auto_retries(
            record=record,
            generate_request=generate_request,
            provider_strategy=provider_strategy,
            generation_result=generation_result,
        )
        generation_result = self._apply_reviewed_delivery_preference(generation_result)
        record.generation_result = generation_result
        record.scenario_resolution = generation_runtime_result.scenario_resolution
        record.capability_run = generation_runtime_result.capability_run
        record.status = ProductJobStatusValue.GENERATED
        record.balance_estimate = self._estimate_for_result(generation_result)
        record.lifecycle = self._build_lifecycle(record)
        self.job_store.save(record)
        return self._status_from_record(record)

    def generate_job(
        self,
        job_id: str,
        request: GenerateJobRequest | dict[str, Any] | None = None,
    ) -> ProductJobStatus:
        return self.generate_asset_series(job_id, request)

    def _provider_strategy_for_generate(
        self,
        record: ProductJobRecord,
        generate_request: GenerateJobRequest,
    ) -> ProviderStrategy:
        metadata = dict(generate_request.metadata)
        require_real_images = bool(metadata.get("require_real_images") or metadata.get("real_image_generation"))
        if not require_real_images:
            return ProviderStrategy.MOCK_GENERATION
        project_context = record.request.metadata.get("project_context_snapshot")
        has_project_references = False
        if isinstance(project_context, dict):
            has_project_references = bool(
                project_context.get("selected_output_assets")
                or project_context.get("selected_reference_assets")
                or project_context.get("uploaded_reference_assets")
                or project_context.get("selected_visual_references")
                or project_context.get("strong_reference_bindings")
                or project_context.get("strong_reference_continuation_plan")
            )
        if record.request.uploaded_asset_ids or has_project_references:
            return ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER
        return ProviderStrategy.DEFAULT_IMAGE_PROVIDER

    def _generation_failure_message(self, exc: Exception, provider_strategy: ProviderStrategy) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            detail_message = str(detail.get("message") or detail.get("error_message") or "").strip()
            detail_error = str(detail.get("error_type") or "").strip()
            if detail_message and detail_message not in message:
                message = f"{message} {detail_message}"
            elif detail_error and detail_error not in message:
                message = f"{message} {detail_error}"
        provider = getattr(exc, "provider", None)
        code = getattr(exc, "code", exc.__class__.__name__)
        prefix = "V3 real image generation failed"
        if provider_strategy == ProviderStrategy.MOCK_GENERATION:
            prefix = "V3 candidate generation failed"
        provider_text = f" via {provider}" if provider else ""
        return f"{prefix}{provider_text} ({code}): {message[:500]}"

    def _provider_failure_retry_summary_from_exception(self, exc: Exception) -> dict[str, Any]:
        summary = getattr(exc, "provider_failure_retry", None)
        if isinstance(summary, dict):
            return dict(summary)
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict) and isinstance(detail.get("provider_failure_retry"), dict):
            return dict(detail["provider_failure_retry"])
        message = self._generation_failure_message(exc, ProviderStrategy.DEFAULT_IMAGE_PROVIDER)
        lowered = message.lower()
        retryable_markers = (
            "timeout",
            "timed out",
            "gateway",
            "bad_response_status_code",
            "could not be downloaded",
            "image reference generation failed",
            "image generation failed",
            "provider returned no image",
            "no image outputs",
            "502",
            "503",
            "504",
            "500",
        )
        non_retryable_markers = (
            "not configured",
            "api key",
            "insufficient",
            "policy",
            "safety",
            "invalid uploaded asset",
            "source file was not found",
        )
        if any(marker in lowered for marker in non_retryable_markers):
            classification = "non_retryable_provider_failure"
            retryable = False
        elif any(marker in lowered for marker in retryable_markers):
            classification = "retryable_provider_failure"
            retryable = True
        else:
            classification = "unknown_retryable_failure"
            retryable = True
        return {
            "executed_count": 0,
            "max_attempts": 1,
            "fresh_upstream_requests": 1,
            "final_status": "failed",
            "final_classification": classification,
            "attempts": [
                {
                    "attempt": 1,
                    "status": "failed",
                    "classification": classification,
                    "error_type": exc.__class__.__name__,
                    "message": message[:500],
                    "retryable": retryable,
                }
            ],
        }

    def _attach_post_generation_review(
        self,
        record: ProductJobRecord,
        generation_result: PlanningResult,
        generate_request: GenerateJobRequest,
    ) -> PlanningResult:
        project_id = record.request.metadata.get("project_id")
        review_metadata = {
            **dict(record.request.metadata or {}),
            **dict(generate_request.metadata or {}),
            "quality_mode": generate_request.quality_mode,
            "scenario_id": generation_result.metadata.get("scenario_id"),
            "template_id": record.request.metadata.get("template_id") or generation_result.metadata.get("scenario_id"),
        }
        result_cluster = generation_result.metadata.get("visual_cluster")
        if not isinstance(result_cluster, dict):
            shared = generation_result.metadata.get("shared_capabilities")
            result_cluster = shared.get("visual_cluster") if isinstance(shared, dict) else {}
        if isinstance(result_cluster, dict):
            reference_policy = result_cluster.get("resolved_reference_policy_package")
            if isinstance(reference_policy, dict) and reference_policy:
                review_metadata.setdefault("resolved_reference_policy_package", reference_policy)
        if self._reference_conditioned_real_review_required(
            review_metadata,
            quality_mode=generate_request.quality_mode,
        ):
            review_metadata["enable_real_vision_inspection"] = True
        resolutions = self.output_resolver.resolve_result(generation_result, project_id=project_id)
        inspections = [
            self.vision_inspector.inspect(resolution, metadata=review_metadata)
            for resolution in resolutions
        ]
        package = self.review_merger.build_package(
            job_id=generation_result.creative_job.job_id,
            project_id=project_id,
            resolutions=resolutions,
            inspections=inspections,
            max_attempts=self._visual_auto_retry_max_attempts(generate_request),
        )
        package_payload = package.model_dump(mode="json")
        metadata = dict(generation_result.metadata)
        shared_capabilities = dict(metadata.get("shared_capabilities") or {})
        visual_cluster = dict(shared_capabilities.get("visual_cluster") or metadata.get("visual_cluster") or {})
        mode_review = self._mode_differentiation_review_for_result(
            generation_result=generation_result,
            project_id=project_id,
            visual_cluster=visual_cluster,
        )
        if mode_review:
            visual_cluster["mode_differentiation_review"] = mode_review
            package_payload.setdefault("metadata", {})["mode_differentiation_review"] = mode_review
        existing_reports = [
            report
            for report in visual_cluster.get("quality_review_reports", [])
            if not (isinstance(report, dict) and report.get("metadata", {}).get("post_generation"))
        ]
        visual_cluster["quality_review_reports"] = [
            *existing_reports,
            *[report.model_dump(mode="json") for report in package.quality_review_reports],
        ]
        visual_cluster["auto_retry_decisions"] = self._auto_retry_decisions_with_mode_review(
            package.auto_retry_decisions,
            mode_review=mode_review,
            job_id=generation_result.creative_job.job_id,
            project_id=project_id,
            max_attempts=self._visual_auto_retry_max_attempts(generate_request),
        )
        package_payload["auto_retry_decisions"] = list(visual_cluster["auto_retry_decisions"])
        if package.real_review_signal_package is not None:
            real_signal_payload = package.real_review_signal_package.model_dump(mode="json")
            package_payload["real_review_signal_package"] = real_signal_payload
            visual_cluster["real_review_signal_package"] = real_signal_payload
        visual_cluster["post_generation_review_package"] = package_payload
        visual_cluster["has_post_generation_review"] = True
        shared_capabilities["visual_cluster"] = visual_cluster
        metadata.update(
            {
                "shared_capabilities": shared_capabilities,
                "visual_cluster": visual_cluster,
                "post_generation_review_package": package_payload,
                "post_generation_review_summary": list(package.user_visible_summary),
            }
        )
        asset_pack = generation_result.asset_pack.model_copy(
            update={
                "manifest": {
                    **dict(generation_result.asset_pack.manifest),
                    "post_generation_review_package": package_payload,
                },
                "metadata": {
                    **dict(generation_result.asset_pack.metadata),
                    "post_generation_review_package": package_payload,
                },
            }
        )
        return generation_result.model_copy(update={"metadata": metadata, "asset_pack": asset_pack})

    def _reference_conditioned_real_review_required(
        self,
        metadata: dict[str, Any],
        *,
        quality_mode: str,
    ) -> bool:
        if bool(metadata.get("disable_real_vision_inspection")):
            return False
        if metadata.get("vision_inspection_mode") or metadata.get("post_generation_inspection_mode"):
            return False
        if str(quality_mode or "standard") not in {"standard", "strict"}:
            return False
        if not bool(metadata.get("require_real_images")):
            return False
        for key in ("uploaded_assets", "reference_assets"):
            if isinstance(metadata.get(key), list) and metadata[key]:
                return True
        context = metadata.get("project_context_snapshot")
        if isinstance(context, dict):
            for key in ("uploaded_reference_assets", "selected_visual_references", "strong_reference_bindings"):
                if isinstance(context.get(key), list) and context[key]:
                    return True
            package = context.get("resolved_reference_policy_package")
            if isinstance(package, dict) and bool(package.get("applies")):
                return True
        package = metadata.get("resolved_reference_policy_package")
        return isinstance(package, dict) and bool(package.get("applies"))

    def _mode_differentiation_review_for_result(
        self,
        *,
        generation_result: PlanningResult,
        project_id: str | None,
        visual_cluster: dict[str, Any],
    ) -> dict[str, Any]:
        role_plan_payload = visual_cluster.get("role_specific_generation_plan")
        if not isinstance(role_plan_payload, dict):
            suite = visual_cluster.get("general_suite_role_plan")
            suite_metadata = suite.get("metadata") if isinstance(suite, dict) else {}
            role_plan_payload = suite_metadata.get("role_specific_generation_plan") if isinstance(suite_metadata, dict) else {}
        if not isinstance(role_plan_payload, dict) or not role_plan_payload:
            return {}
        try:
            from ..shared_capabilities.visual_cluster import RoleSpecificGenerationPlan

            role_plan = RoleSpecificGenerationPlan.model_validate(role_plan_payload)
        except Exception:
            return {}
        candidates = self._mode_review_candidates(generation_result)
        review = self.mode_role_director.review(
            project_id=project_id,
            job_id=generation_result.creative_job.job_id,
            role_plan=role_plan,
            generated_candidates=candidates,
        )
        return review.model_dump(mode="json")

    def _mode_review_candidates(self, result: PlanningResult) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        assets_by_id = {asset.asset_id: asset for asset in result.series_plan.assets}
        for packaged in result.asset_pack.assets:
            candidate_metadata = packaged.metadata.get("candidate_metadata")
            if not isinstance(candidate_metadata, dict):
                candidate_metadata = {}
            asset_spec = assets_by_id.get(packaged.asset_id)
            asset_metadata = dict(asset_spec.metadata) if asset_spec else dict(packaged.metadata.get("asset_metadata") or {})
            recipe = (
                candidate_metadata.get("mode_role_recipe")
                or asset_metadata.get("mode_role_recipe")
                or packaged.metadata.get("mode_role_recipe")
            )
            payloads.append(
                {
                    "candidate_id": packaged.metadata.get("selected_candidate_id"),
                    "asset_id": packaged.asset_id,
                    "output_id": candidate_metadata.get("output_id"),
                    "mode_role_recipe": recipe if isinstance(recipe, dict) else {},
                    "mode_role_key": candidate_metadata.get("mode_role_key") or asset_metadata.get("mode_role_key"),
                    "mode_role_label": candidate_metadata.get("mode_role_label") or asset_metadata.get("mode_role_label"),
                    "requested_image_size": candidate_metadata.get("requested_image_size"),
                    "aspect_ratio": packaged.aspect_ratio,
                    "metadata": {**asset_metadata, **candidate_metadata},
                }
            )
        return payloads

    def _auto_retry_decisions_with_mode_review(
        self,
        decisions: list[Any],
        *,
        mode_review: dict[str, Any],
        job_id: str,
        project_id: str | None,
        max_attempts: int,
    ) -> list[dict[str, Any]]:
        payloads = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
            for item in decisions
            if isinstance(item, dict) or hasattr(item, "model_dump")
        ]
        if not mode_review or mode_review.get("status") != "retry_recommended":
            return payloads
        issue_codes = self._dedupe_strings(mode_review.get("issue_codes"))
        retry_patch = dict(mode_review.get("retry_patch") or {})
        payloads.append(
            {
                "decision_id": stable_id("mode_role_auto_retry_decision", job_id, ",".join(issue_codes)),
                "job_id": job_id,
                "project_id": project_id,
                "should_retry": bool(issue_codes and retry_patch),
                "retry_attempt": 0,
                "max_attempts": max_attempts,
                "reason_codes": issue_codes,
                "retry_patch": retry_patch,
                "blocked_reason": None if retry_patch else "empty_retry_patch",
                "user_visible_reason": "A role-specific retry can make this set clearer.",
                "metadata": {"source": "mode_differentiation_review", "doc": "59"},
            }
        )
        return payloads

    def _run_visual_auto_retries(
        self,
        *,
        record: ProductJobRecord,
        generate_request: GenerateJobRequest,
        provider_strategy: ProviderStrategy,
        generation_result: PlanningResult,
    ) -> PlanningResult:
        max_attempts = self._visual_auto_retry_max_attempts(generate_request)
        base_metadata = dict(record.request.metadata)
        records: list[dict[str, Any]] = []
        seen_issue_codes: set[str] = set()
        merged_result = generation_result

        for attempt_index in range(1, max_attempts + 1):
            plan = self._visual_retry_execution_plan(
                record=record,
                result=merged_result,
                generate_request=generate_request,
                attempt_index=attempt_index,
                max_attempts=max_attempts,
                seen_issue_codes=seen_issue_codes,
            )
            if not plan["should_retry"]:
                if plan.get("record"):
                    records.append(plan["record"])
                break

            retry_patch = dict(plan["retry_patch"])
            reason_codes = list(plan["reason_codes"])
            identity_local_repair = self._identity_local_repair_metadata(
                merged_result,
                attempt_index=attempt_index,
                reason_codes=reason_codes,
            )
            retry_metadata = {
                **base_metadata,
                "visual_auto_retry_active": True,
                "visual_auto_retry_attempt": attempt_index,
                "retry_attempt": attempt_index,
                "visual_retry_reason_codes": reason_codes,
                "visual_retry_patch": retry_patch,
                "max_visual_retry_attempts": max_attempts,
                **identity_local_repair,
            }
            record.request.metadata = retry_metadata
            try:
                retry_runtime_result = self.scenario_runtime.generate_job(
                    self._runtime_request_payload(record.request),
                    mock_profile=QUALITY_MODE_TO_MOCK_PROFILE[generate_request.quality_mode],
                    apply_memory_update=False,
                    provider_strategy=provider_strategy,
                    quality_mode=generate_request.quality_mode,
                )
            except Exception as exc:
                records.append(
                    self._visual_retry_execution_record(
                        record=record,
                        status="failed",
                        attempt_index=attempt_index,
                        max_attempts=max_attempts,
                        reason_codes=reason_codes,
                        retry_patch=retry_patch,
                        source="scenario_runtime",
                        blocked_reason=self._generation_failure_message(exc, provider_strategy),
                    )
                )
                break

            if retry_runtime_result.generation_result is None:
                records.append(
                    self._visual_retry_execution_record(
                        record=record,
                        status="blocked",
                        attempt_index=attempt_index,
                        max_attempts=max_attempts,
                        reason_codes=reason_codes,
                        retry_patch=retry_patch,
                        source="scenario_runtime",
                        blocked_reason="retry_generation_returned_no_result",
                    )
                )
                break

            reviewed_retry_result = self._attach_post_generation_review(
                record,
                retry_runtime_result.generation_result,
                generate_request,
            )
            retry_result = self._mark_retry_generation_result(
                reviewed_retry_result,
                attempt_index=attempt_index,
                reason_codes=reason_codes,
                retry_patch=retry_patch,
            )
            retry_output_ids = self._visual_result_output_ids(retry_result)
            records.append(
                self._visual_retry_execution_record(
                    record=record,
                    status="executed",
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    reason_codes=reason_codes,
                    retry_patch=retry_patch,
                    source=str(plan.get("source") or "visual_review"),
                    retry_output_ids=retry_output_ids,
                    retry_candidate_ids=self._visual_result_candidate_ids(retry_result),
                )
            )
            merged_result = self._merge_retry_generation_result(
                merged_result,
                retry_result,
                records=records,
                max_attempts=max_attempts,
            )
            seen_issue_codes.update(reason_codes)

        merged_result, max_attempts = self._run_post_retry_identity_closeout(
            record=record,
            generate_request=generate_request,
            provider_strategy=provider_strategy,
            result=merged_result,
            base_metadata=base_metadata,
            records=records,
            max_attempts=max_attempts,
        )

        record.request.metadata = {
            **base_metadata,
            "visual_auto_retry": self._visual_auto_retry_summary(records, max_attempts),
        }
        if not records:
            return self._with_visual_retry_metadata(merged_result, records, max_attempts)
        return self._with_visual_retry_metadata(merged_result, records, max_attempts)

    def _run_post_retry_identity_closeout(
        self,
        *,
        record: ProductJobRecord,
        generate_request: GenerateJobRequest,
        provider_strategy: ProviderStrategy,
        result: PlanningResult,
        base_metadata: dict[str, Any],
        records: list[dict[str, Any]],
        max_attempts: int,
    ) -> tuple[PlanningResult, int]:
        if max_attempts <= 0 or not any(item.get("status") == "executed" for item in records):
            return result, max_attempts
        if self._result_has_identity_local_repair(result):
            return result, max_attempts
        issue_codes, retry_patch, _source = self._visual_retry_signal(result, {})
        issue_codes = self._dedupe_strings(issue_codes)
        attempt_index = max_attempts + 1
        local_repair = self._identity_local_repair_metadata(
            result,
            attempt_index=attempt_index,
            reason_codes=issue_codes,
            post_retry_closeout=True,
        )
        if not local_repair:
            return result, max_attempts
        if not self._visual_retry_patch_has_content(retry_patch):
            retry_patch = self._visual_retry_patch_from_issues(issue_codes)
        retry_metadata = {
            **base_metadata,
            "visual_auto_retry_active": True,
            "visual_auto_retry_attempt": attempt_index,
            "retry_attempt": attempt_index,
            "visual_retry_reason_codes": issue_codes,
            "visual_retry_patch": retry_patch,
            "max_visual_retry_attempts": attempt_index,
            "identity_post_retry_closeout": True,
            **local_repair,
        }
        record.request.metadata = retry_metadata
        try:
            runtime_result = self.scenario_runtime.generate_job(
                self._runtime_request_payload(record.request),
                mock_profile=QUALITY_MODE_TO_MOCK_PROFILE[generate_request.quality_mode],
                apply_memory_update=False,
                provider_strategy=provider_strategy,
                quality_mode=generate_request.quality_mode,
            )
            if runtime_result.generation_result is None:
                raise RuntimeError("identity closeout returned no generation result")
            reviewed = self._attach_post_generation_review(
                record,
                runtime_result.generation_result,
                generate_request,
            )
            closeout_result = self._mark_retry_generation_result(
                reviewed,
                attempt_index=attempt_index,
                reason_codes=issue_codes,
                retry_patch=retry_patch,
            )
            records.append(
                self._visual_retry_execution_record(
                    record=record,
                    status="executed",
                    attempt_index=attempt_index,
                    max_attempts=attempt_index,
                    reason_codes=issue_codes,
                    retry_patch=retry_patch,
                    source="identity_post_retry_closeout",
                    retry_output_ids=self._visual_result_output_ids(closeout_result),
                    retry_candidate_ids=self._visual_result_candidate_ids(closeout_result),
                )
            )
            return (
                self._merge_retry_generation_result(
                    result,
                    closeout_result,
                    records=records,
                    max_attempts=attempt_index,
                ),
                attempt_index,
            )
        except Exception as exc:
            records.append(
                self._visual_retry_execution_record(
                    record=record,
                    status="failed",
                    attempt_index=attempt_index,
                    max_attempts=attempt_index,
                    reason_codes=issue_codes,
                    retry_patch=retry_patch,
                    source="identity_post_retry_closeout",
                    blocked_reason=self._generation_failure_message(exc, provider_strategy),
                )
            )
            return result, attempt_index

    def _result_has_identity_local_repair(self, result: PlanningResult) -> bool:
        for output_id in self._visual_result_output_ids(result):
            output = self.output_store.get_output(output_id)
            if output is not None and bool((output.metadata or {}).get("identity_local_repair")):
                return True
        return False

    def _identity_local_repair_metadata(
        self,
        result: PlanningResult,
        *,
        attempt_index: int,
        reason_codes: list[str],
        post_retry_closeout: bool = False,
    ) -> dict[str, Any]:
        if attempt_index != 1 and not post_retry_closeout:
            return {}
        identity_codes = {
            "identity_drift",
            "bone_structure_drift",
            "face_shape_drift",
            "cheek_jaw_chin_drift",
            "eye_shape_or_spacing_identity_drift",
            "eyebrow_eye_relationship_drift",
            "nose_mouth_relationship_identity_drift",
            "lip_contour_identity_drift",
            "same_type_not_same_person",
            "identity_reference_underweighted",
            "identity_metric_below_commercial_target",
        }
        if not identity_codes.intersection(reason_codes):
            return {}
        package = result.metadata.get("post_generation_review_package")
        inspections = package.get("inspections") if isinstance(package, dict) else []
        for inspection in inspections if isinstance(inspections, list) else []:
            if not isinstance(inspection, dict):
                continue
            evidence = inspection.get("evidence") if isinstance(inspection.get("evidence"), dict) else {}
            fusion = evidence.get("identity_review_fusion") if isinstance(evidence.get("identity_review_fusion"), dict) else {}
            metric = evidence.get("identity_metric") if isinstance(evidence.get("identity_metric"), dict) else {}
            fused_score = self._safe_score(fusion.get("fused_identity_score"))
            lower_bound = 0.72
            if fused_score is None or not lower_bound <= fused_score < 0.82:
                continue
            score_card = inspection.get("score_card") if isinstance(inspection.get("score_card"), dict) else {}
            detected_codes = {
                str(item.get("code") or "")
                for item in inspection.get("detected_issues", [])
                if isinstance(item, dict) and item.get("code")
            }
            local_repair_blockers = {
                "visible_text_artifact",
                "watermark_or_signature",
                "collage_or_split_panel",
                "bad_hands_or_body",
                "severe_face_artifact",
                "severe_body_artifact",
                "policy_or_safety_block",
                "prompt_owned_channel_ignored",
                "source_hair_overinherited",
                "source_makeup_overinherited",
                "source_wardrobe_overinherited",
                "source_lighting_overinherited",
                "source_color_grade_overinherited",
                "source_scene_overinherited",
                "source_camera_overinherited",
                "source_whole_style_overinherited",
            }
            if post_retry_closeout:
                local_repair_blockers.discard("source_hair_overinherited")
                local_repair_blockers.discard("source_makeup_overinherited")
            if detected_codes.intersection(local_repair_blockers):
                continue
            prompt_floor = 0.60 if post_retry_closeout else 0.75
            if (self._safe_score(score_card.get("prompt_owned_channel_obedience")) or 0.0) < prompt_floor:
                continue
            if (self._safe_score(score_card.get("commercial_finish")) or 0.0) < 0.70:
                continue
            if (self._safe_score(score_card.get("human_realism")) or 0.0) < 0.65:
                continue
            if post_retry_closeout:
                objective = self._safe_score(metric.get("calibrated_score"))
                geometry = self._safe_score(metric.get("geometry_score"))
                if objective is None or objective < 0.82 or geometry is None or geometry < 0.80:
                    continue
            output_id = str(inspection.get("output_id") or "").strip()
            face_box = metric.get("output_face_box")
            if not output_id or not isinstance(face_box, list) or len(face_box) != 4:
                continue
            output = self.output_store.get_output(output_id)
            if output is None or not output.file_path:
                continue
            try:
                from app.services.provider_reference import prepare_identity_repair_artifacts

                artifacts = prepare_identity_repair_artifacts(output.file_path, face_box)
            except Exception:
                continue
            return {
                "identity_local_repair_active": True,
                "identity_local_repair_source_output_id": output_id,
                "identity_local_repair_canvas_path": artifacts["canvas_path"],
                "identity_local_repair_mask_path": artifacts["mask_path"],
                "identity_local_repair_face_box": list(face_box),
                "identity_local_repair_initial_score": fused_score,
                "identity_local_repair_max_attempts": 1,
                "identity_local_repair_stage": "post_retry_closeout" if post_retry_closeout else "primary_retry",
                "identity_local_repair_artifacts": {
                    "canvas_size": artifacts.get("canvas_size"),
                    "mask_box": artifacts.get("mask_box"),
                    "ephemeral": True,
                },
            }
        return {}

    def _safe_score(self, value: Any) -> float | None:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return None

    def _visual_auto_retry_max_attempts(self, generate_request: GenerateJobRequest) -> int:
        metadata = dict(generate_request.metadata or {})
        if bool(metadata.get("disable_visual_auto_retry")):
            return 0
        requested = self._safe_int(metadata.get("max_visual_retry_attempts"), default=None)
        mode_limit = {"standard": 1, "strict": 2, "explore": 0}.get(generate_request.quality_mode, 1)
        if generate_request.quality_mode == "explore" and bool(metadata.get("enable_visual_auto_retry_in_explore")):
            mode_limit = 1
        if requested is None:
            return mode_limit
        return max(0, min(requested, mode_limit))

    def _visual_retry_execution_plan(
        self,
        *,
        record: ProductJobRecord,
        result: PlanningResult,
        generate_request: GenerateJobRequest,
        attempt_index: int,
        max_attempts: int,
        seen_issue_codes: set[str],
    ) -> dict[str, Any]:
        if max_attempts <= 0:
            return {"should_retry": False}
        metadata = dict(generate_request.metadata or {})
        if bool(metadata.get("disable_visual_auto_retry")):
            return {"should_retry": False}

        issue_codes, retry_patch, source = self._visual_retry_signal(result, metadata)
        issue_codes = self._dedupe_strings(issue_codes)
        if not issue_codes:
            return {"should_retry": False}
        if attempt_index > max_attempts:
            return {
                "should_retry": False,
                "record": self._visual_retry_execution_record(
                    record=record,
                    status="blocked",
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    reason_codes=issue_codes,
                    retry_patch=retry_patch,
                    source=source,
                    blocked_reason="max_retry_attempts_reached",
                ),
            }

        non_retryable = [code for code in issue_codes if code in VISUAL_AUTO_RETRY_NON_RETRYABLE_ISSUES]
        if non_retryable:
            return {
                "should_retry": False,
                "record": self._visual_retry_execution_record(
                    record=record,
                    status="blocked",
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    reason_codes=non_retryable,
                    retry_patch=retry_patch,
                    source=source,
                    blocked_reason="non_retryable_visual_issue",
                ),
            }
        retryable_codes = [code for code in issue_codes if code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES]
        if not retryable_codes:
            return {"should_retry": False}
        repeated = [code for code in retryable_codes if code in seen_issue_codes]
        if repeated:
            return {
                "should_retry": False,
                "record": self._visual_retry_execution_record(
                    record=record,
                    status="blocked",
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    reason_codes=repeated,
                    retry_patch=retry_patch,
                    source=source,
                    blocked_reason="same_issue_repeated",
                ),
            }

        if not retry_patch:
            retry_patch = self._visual_retry_patch_from_issues(retryable_codes)
        if bool(metadata.get("force_empty_visual_retry_patch")):
            retry_patch = {}
        if not self._visual_retry_patch_has_content(retry_patch):
            return {
                "should_retry": False,
                "record": self._visual_retry_execution_record(
                    record=record,
                    status="skipped",
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    reason_codes=retryable_codes,
                    retry_patch=retry_patch,
                    source=source,
                    blocked_reason="empty_retry_patch",
                ),
            }

        return {
            "should_retry": True,
            "reason_codes": retryable_codes,
            "retry_patch": retry_patch,
            "source": source,
        }

    def _visual_retry_signal(
        self,
        result: PlanningResult,
        request_metadata: dict[str, Any],
    ) -> tuple[list[str], dict[str, Any], str]:
        explicit_codes = self._metadata_issue_codes(request_metadata)
        if explicit_codes:
            return explicit_codes, self._metadata_retry_patch(request_metadata), "request_metadata"

        cluster = self._visual_cluster_metadata_from_result(result)
        real_signal = self._real_review_signal_package_from_cluster(cluster)
        if real_signal:
            signal_codes, signal_patch = self._visual_retry_signal_from_real_review(real_signal)
            if signal_codes:
                return signal_codes, signal_patch, "real_review_signal_package"
        if self._visual_cluster_is_preflight_only(cluster):
            return [], {}, "preflight_only"
        decisions = cluster.get("auto_retry_decisions") if isinstance(cluster, dict) else None
        if not isinstance(decisions, list):
            return [], {}, "visual_cluster"
        for decision in decisions:
            if not isinstance(decision, dict) or not bool(decision.get("should_retry")):
                continue
            return (
                self._dedupe_strings(decision.get("reason_codes")),
                dict(decision.get("retry_patch") or {}),
                "visual_cluster",
            )
        return [], {}, "visual_cluster"

    def _real_review_signal_package_from_cluster(self, cluster: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(cluster, dict):
            return {}
        direct = cluster.get("real_review_signal_package")
        if isinstance(direct, dict):
            return dict(direct)
        package = cluster.get("post_generation_review_package")
        if isinstance(package, dict) and isinstance(package.get("real_review_signal_package"), dict):
            return dict(package["real_review_signal_package"])
        return {}

    def _visual_retry_signal_from_real_review(self, package: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
        signals = package.get("candidate_signals")
        if not isinstance(signals, list):
            return [], {}
        retry_signals = [
            signal
            for signal in signals
            if isinstance(signal, dict)
            and signal.get("recommended_action") == "retry"
            and self._dedupe_strings(signal.get("retryable_issue_codes"))
        ]
        if not retry_signals:
            return [], {}
        reason_codes = self._dedupe_strings(
            code
            for signal in retry_signals
            for code in self._dedupe_strings(signal.get("retryable_issue_codes"))
        )
        patches = [dict(signal.get("retry_patch") or {}) for signal in retry_signals]
        retry_patch = self._merge_visual_retry_patches(patches)
        if not self._visual_retry_patch_has_content(retry_patch):
            retry_patch = self._visual_retry_patch_from_issues(reason_codes)
        target_candidate_ids = self._dedupe_strings(signal.get("candidate_id") for signal in retry_signals if signal.get("candidate_id"))
        target_output_ids = self._dedupe_strings(signal.get("output_id") for signal in retry_signals if signal.get("output_id"))
        issue_groups = self._dedupe_strings(
            group
            for signal in retry_signals
            for group in self._string_list((signal.get("metadata") or {}).get("issue_groups") if isinstance(signal.get("metadata"), dict) else [])
        )
        if target_candidate_ids:
            retry_patch["target_candidate_ids"] = target_candidate_ids
        if target_output_ids:
            retry_patch["target_output_ids"] = target_output_ids
        if issue_groups:
            retry_patch["issue_groups"] = issue_groups
        return reason_codes, retry_patch

    def _merge_visual_retry_patches(self, patches: list[dict[str, Any]]) -> dict[str, Any]:
        merge_fields = [*VISUAL_RETRY_PATCH_FIELDS, "brand_asset_reinforcement"]
        merged: dict[str, list[str]] = {field_name: [] for field_name in merge_fields}
        provider_hint_overrides: dict[str, Any] = {}
        for patch in patches:
            if not isinstance(patch, dict):
                continue
            for field_name in merge_fields:
                merged[field_name].extend(self._string_list(patch.get(field_name)))
            hints = patch.get("provider_hint_overrides")
            if isinstance(hints, dict):
                provider_hint_overrides.update(hints)
        result = {field_name: self._dedupe_strings(values) for field_name, values in merged.items() if self._dedupe_strings(values)}
        if provider_hint_overrides:
            result["provider_hint_overrides"] = provider_hint_overrides
        return result

    def _metadata_issue_codes(self, metadata: dict[str, Any]) -> list[str]:
        values: list[Any] = []
        for key in (
            "force_visual_retry_issue_codes",
            "visual_retry_issue_codes",
            "visual_auto_retry_issue_codes",
            "force_anti_ai_face_issue_codes",
            "anti_ai_face_issue_codes",
            "force_beautiful_realism_issue_codes",
            "beautiful_realism_issue_codes",
            "facial_feature_issue_codes",
            "identity_card_issue_codes",
        ):
            raw = metadata.get(key)
            if isinstance(raw, list):
                values.extend(raw)
            elif isinstance(raw, str):
                values.extend(part.strip() for part in raw.split(","))
        single = metadata.get("force_visual_retry_issue") or metadata.get("visual_retry_issue_code")
        if single:
            values.append(single)
        return self._dedupe_strings(values)

    def _metadata_retry_patch(self, metadata: dict[str, Any]) -> dict[str, Any]:
        patch = metadata.get("visual_retry_patch")
        if isinstance(patch, dict):
            return dict(patch)
        return {}

    def _visual_cluster_metadata_from_result(self, result: PlanningResult) -> dict[str, Any]:
        shared = result.metadata.get("shared_capabilities") if isinstance(result.metadata, dict) else {}
        if isinstance(shared, dict) and isinstance(shared.get("visual_cluster"), dict):
            return dict(shared["visual_cluster"])
        cluster = result.metadata.get("visual_cluster") if isinstance(result.metadata, dict) else {}
        return dict(cluster) if isinstance(cluster, dict) else {}

    def _visual_cluster_is_preflight_only(self, cluster: dict[str, Any]) -> bool:
        reports = cluster.get("quality_review_reports") if isinstance(cluster, dict) else None
        if not isinstance(reports, list) or not reports:
            return True
        report_dicts = [report for report in reports if isinstance(report, dict)]
        if not report_dicts:
            return True
        return all(bool((report.get("metadata") or {}).get("pre_generation")) for report in report_dicts)

    def _visual_retry_patch_from_issues(self, issue_codes: list[str]) -> dict[str, Any]:
        prompt_additions: list[str] = []
        negative_additions: list[str] = []
        identity_reinforcement: list[str] = []
        product_reinforcement: list[str] = []
        composition_repair: list[str] = []
        artifact_repair: list[str] = []
        object_removal_instruction: list[str] = []
        human_realism_layer: HumanPhotorealismLayer | None = None
        for code in issue_codes:
            if code in {
                "visible_text_artifact",
                "watermark_or_signature",
                "faint_corner_watermark",
                "ai_generated_badge_trace",
                "signature_like_artifact",
                "lower_right_mark_artifact",
                "third_party_aigc_metadata",
                "provider_provenance_mismatch",
                "commercial_cleanliness_failure",
            }:
                artifact_repair.append(
                    "keep the image completely clean with no visible text, corner watermark, signature, badge, AI mark, third-party AIGC label, lower-right logo, or semi-transparent mark"
                )
                negative_additions.extend(
                    [
                        "visible text",
                        "watermark",
                        "signature",
                        "AI-generated mark",
                        "third-party AIGC label",
                        "provider provenance mark",
                        "corner text",
                        "lower-right logo",
                        "semi-transparent mark",
                        "random letters",
                    ]
                )
            elif code == "collage_or_split_panel":
                composition_repair.append("generate one complete single-frame image, not a collage or split-panel layout")
                negative_additions.extend(["collage", "split screen", "multi-panel layout"])
            elif code in {"unrelated_object", "unrelated_product"}:
                object_removal_instruction.append("remove unrelated props or objects that were not requested")
                negative_additions.extend(["unrelated props", "unrequested objects", "random product"])
            elif code in {"identity_drift", "hair_or_outfit_drift", "camera_distance_drift"}:
                identity_reinforcement.append(
                    "preserve the exact uploaded portrait identity truth if present: face ratio, eye shape and spacing, eyebrow arc, nose-mouth relationship, jaw/chin direction, natural age impression, body identity direction, and skin-tone direction"
                )
                identity_reinforcement.append(
                    "use selected generated references only as continuation support when an uploaded identity truth source exists; keep hair, outfit category, camera distance, and natural proportions consistent"
                )
            elif code in {
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
            }:
                identity_reinforcement.extend(
                    [
                        "Doc86 same-person repair: use the uploaded portrait reference as the face-geometry truth source, not merely a beauty-style reference",
                        "preserve underlying bone structure: face width/length ratio, cheek volume, jawline slope, chin scale, eye spacing/base eye shape, eyebrow-eye relationship, nose-mouth relationship, lip contour, and age impression",
                        "allow makeup, wardrobe, hairstyle, lighting, pose, expression, and scene changes only as surface styling changes",
                        "Doc90 advanced reference priority repair: prompt face archetype wording may guide makeup, mood, and styling only; it must not replace uploaded facial geometry",
                    ]
                )
                prompt_additions.append(
                    "reduce generic beauty archetype pressure; target-style, delicate, or premium styling must not remodel the person's face"
                )
                negative_additions.extend(
                    [
                        "same type but different person",
                        "generic AI beauty replacement",
                        "face slimming",
                        "V-shaped jaw replacement",
                        "eye enlargement",
                        "eye spacing drift",
                        "nose reshaping",
                        "lip reshaping",
                        "jaw or chin remodeling",
                        "age impression drift",
                        "style changed face geometry",
                    ]
                )
            elif code in {
                "source_hair_overinherited",
                "source_makeup_overinherited",
                "source_color_grade_overinherited",
                "source_camera_overinherited",
                "source_whole_style_overinherited",
                "prompt_owned_channel_ignored",
                "selected_anchor_overrode_current_prompt",
                "structured_appearance_lock_misapplied",
            }:
                prompt_additions.extend(
                    [
                        "Doc93 channel repair: preserve valid identity or product truth while restoring current prompt-owned styling channels",
                        "follow the current request for hair, makeup, wardrobe, accessories, lighting, color, scene, camera, mood, and style unless that exact channel was explicitly locked",
                        "do not increase whole-image reference strength and do not let a selected generated output override the current prompt",
                    ]
                )
                identity_reinforcement.append(
                    "keep the same person's face geometry while repairing only leaked source styling; do not copy source wardrobe, light, scene, camera, or whole-image style"
                )
                negative_additions.extend(
                    [
                        "source hairstyle or makeup leakage",
                        "source wardrobe leakage",
                        "source lighting, color, scene, or camera leakage",
                        "source whole-image style leakage",
                        "selected anchor overrode current prompt",
                    ]
                )
            elif code in {
                "source_lighting_overinherited",
                "source_color_temperature_overinherited",
                "source_scene_overinherited",
                "source_wardrobe_overinherited",
                "source_camera_mood_overinherited",
                "reference_used_as_style_when_identity_only",
                "prompt_style_underweighted",
                "makeup_changed_face_geometry",
                "hair_change_replaced_identity",
                "retry_repaired_artifact_but_changed_identity",
            }:
                prompt_additions.extend(
                    [
                        "Doc87 reference-boundary repair: preserve the same person's face geometry from the portrait reference, but follow the current prompt for image direction",
                        "use the reference for identity only unless the user explicitly marked it as style guidance",
                        "do not copy source lighting, source color temperature, source scene, source wardrobe, source camera mood, or the original shoot style",
                        "follow the current prompt's lighting, color grade, background, camera angle, mood, wardrobe, and art direction",
                    ]
                )
                identity_reinforcement.extend(
                    [
                        "preserve the same person's face geometry while changing prompt-owned style channels",
                        "artifact or watermark repair must not replace the face with a cleaner generic beauty face",
                    ]
                )
                negative_additions.extend(
                    [
                        "copied source lighting",
                        "copied source color temperature",
                        "copied source scene",
                        "copied source camera mood",
                        "copied source wardrobe",
                        "reference used as full style template",
                        "prompt style ignored",
                        "same type but different person after cleanup",
                    ]
                )
            elif code in {
                "prompt_mood_regression",
                "prompt_color_tone_regression",
                "approved_style_anchor_ignored",
                "identity_repair_damaged_prompt_direction",
                "overconstrained_identity_prompt",
                "scenario_specific_negative_overfit",
            }:
                prompt_additions.extend(
                    [
                        "Doc88 balance repair: preserve the current prompt's requested mood, color, light, scene, camera, composition, and art direction while keeping uploaded portrait identity recognizable",
                        "use uploaded portrait references as identity truth, not as a whole-photo tone, lighting, or scene template",
                        "use user-approved generated outputs only as positive visual direction anchors when they do not conflict with the current prompt",
                    ]
                )
                identity_reinforcement.extend(
                    [
                        "same person inside the current prompt's atmosphere",
                        "identity, approved direction, and prompt mood must all survive the retry",
                    ]
                )
                negative_additions.extend(
                    [
                        "prompt mood regression",
                        "prompt color or lighting regression",
                        "identity repair that damages requested atmosphere",
                        "approved visual direction ignored",
                        "overloaded identity negative prompt",
                        "scenario-specific template face",
                    ]
                )
            elif code in {"product_identity_drift", "brand_asset_drift"}:
                product_reinforcement.append(
                    "preserve the supplied product or brand asset truth source exactly: same instance, shape, material, colors, proportions, surface finish, label/logo placement, and packaging silhouette"
                )
            elif code in {
                "product_silhouette_drift",
                "label_or_pattern_drift",
                "material_structure_drift",
                "generic_product_replacement",
            }:
                product_reinforcement.extend(
                    [
                        "Doc90 generic object/product repair: keep the uploaded object's silhouette, proportions, material direction, pattern family, label area, and distinctive structure",
                        "prompt product-category words must not replace the referenced object with a generic new item",
                    ]
                )
                negative_additions.extend(
                    [
                        "generic product replacement",
                        "changed product silhouette",
                        "changed label or pattern",
                        "changed material structure",
                    ]
                )
            elif code in {"product_label_drift", "product_label_unreadable", "product_logo_or_label_obscured"}:
                product_reinforcement.append(
                    "preserve the existing product label/logo exactly from the reference when visible; keep it readable, high-contrast, and unobscured"
                )
                artifact_repair.append("do not rewrite, translate, invent, blur, crop, darken, cover, or replace visible product label/logo details")
                negative_additions.extend(
                    [
                        "invented product label",
                        "rewritten logo",
                        "unreadable product label",
                        "covered product logo",
                        "blurred label text",
                        "darkened product label",
                    ]
                )
            elif code in {"lighting_mismatch", "composition_mismatch", "project_continuity_warning", "quality_warning"}:
                prompt_additions.append("follow the project visual direction more closely with clean lighting and consistent composition")
            elif code in {"scene_identity_drift", "background_space_drift", "camera_mood_drift", "reference_scene_replaced"}:
                composition_repair.extend(
                    [
                        "Doc90 scene continuity repair: preserve the reference background, broad space, camera mood, and scene continuity when scene preservation is enabled",
                        "refine the same world instead of replacing the environment with an unrelated new background",
                    ]
                )
                negative_additions.extend(["reference scene replaced", "background space drift", "camera mood drift"])
            elif code in {"bad_hands_or_body", "face_artifact"}:
                artifact_repair.append("prioritize natural anatomy, clean facial structure, and realistic body details")
                negative_additions.extend(["distorted hands", "face artifacts", "warped anatomy"])
            elif code in {
                "identity_card_missing",
                "identity_card_not_applied",
                "identity_feature_drift",
                "eyebrow_shape_drift",
                "eye_shape_or_spacing_drift",
                "nose_mouth_relationship_drift",
                "jaw_chin_direction_drift",
            }:
                prompt_additions.extend(
                    [
                        "preserve same-person facial feature relationships: attractive eyebrow shape and arc, awake eye shape and spacing, eyelid direction, nose-mouth relationship, jaw/chin direction, cheek volume, face ratio, and neck/shoulder balance",
                    ]
                )
                identity_reinforcement.append(
                    "use the selected image or project identity card as the truth source; vary pose, gaze, expression, scene, and camera angle without changing identity-critical face design"
                )
                artifact_repair.extend(
                    [
                        "repair facial features before style: eyebrows, eyes, nose-mouth spacing, jaw/chin, cheek volume, and face ratio must remain beautiful and recognizable",
                    ]
                )
                negative_additions.extend(
                    [
                        "bad eyebrow design",
                        "ugly eyebrow shape",
                        "drooping eyebrows",
                        "mismatched brows",
                        "random eyebrow thickness drift",
                        "sleepy dull eyes",
                        "unflattering nose-mouth drift",
                        "jaw or chin direction drift",
                        "facial feature degradation",
                    ]
                )
            elif HumanPhotorealismLayer.is_human_realism_issue_code(code):
                if human_realism_layer is None:
                    human_realism_layer = HumanPhotorealismLayer()
                human_patch = human_realism_layer.retry_patch_for_issue_codes(
                    [code],
                    child_model=code
                    in {
                        "doll_like_child_face",
                        "adultified_child_model",
                        "synthetic_child_skin",
                        "pageant_polish_child_face",
                        "frozen_child_smile",
                        "unreal_child_eyes",
                        "unreal_child_teeth",
                        "child_face_ai_render",
                    },
                )
                prompt_additions.extend(self._string_list(human_patch.get("prompt_additions")))
                negative_additions.extend(self._string_list(human_patch.get("negative_additions")))
                identity_reinforcement.extend(self._string_list(human_patch.get("identity_reinforcement")))
                artifact_repair.extend(self._string_list(human_patch.get("artifact_repair")))
            elif code == "low_commercial_finish":
                prompt_additions.append("raise the final polish with a clean, premium, directly usable visual finish")
            elif code in {
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
            }:
                prompt_additions.extend(
                    [
                        "raise the foundation aesthetic finish with intentional framing, clear subject readability, balanced exposure, stable color grade, natural contrast, and believable depth",
                        "make the result feel like a directed real-camera image rather than a generic stock render or accidental snapshot",
                    ]
                )
                composition_repair.append(
                    "repair exposure, color, contrast, depth, and framing so the subject reads clearly and the image feels directed"
                )
                artifact_repair.append("avoid overprocessed HDR, synthetic micro-detail, waxy polish, and generic stock-photo finish")
                negative_additions.extend(
                    [
                        "generic stock photo",
                        "weak aesthetic finish",
                        "flat low-contrast image",
                        "washed-out exposure",
                        "muddy underexposed frame",
                        "unstable color grade",
                        "unclear subject",
                        "weak depth separation",
                        "accidental composition",
                        "overprocessed HDR",
                        "synthetic micro detail",
                    ]
                )
            elif code in {
                "mode_role_gap",
                "mode_role_metadata_missing",
                "mode_role_duplication",
                "delivery_suite_role_collapse",
                "ecommerce_slot_mismatch",
                "ecommerce_suite_role_mismatch",
                "format_layout_collapse",
                "selection_candidate_distance_risk",
            }:
                prompt_additions.append(
                    "separate the planned image roles more clearly; each output must follow its own requested slot, camera distance, crop, angle, scene duty, or layout duty"
                )
                composition_repair.append("avoid repeating or replacing the requested image job across the set")
                negative_additions.extend(
                    [
                        "same crop for every output",
                        "same camera distance for every output",
                        "same pose repeated across the set",
                        "same image duty repeated",
                        "wrong ecommerce image role",
                        "requested listing slot ignored",
                    ]
                )
        return {
            "prompt_additions": self._dedupe_strings(prompt_additions),
            "negative_additions": self._dedupe_strings(negative_additions),
            "identity_reinforcement": self._dedupe_strings(identity_reinforcement),
            "product_reinforcement": self._dedupe_strings(product_reinforcement),
            "composition_repair": self._dedupe_strings(composition_repair),
            "artifact_repair": self._dedupe_strings(artifact_repair),
            "object_removal_instruction": self._dedupe_strings(object_removal_instruction),
        }

    def _visual_retry_patch_has_content(self, retry_patch: dict[str, Any]) -> bool:
        for field_name in VISUAL_RETRY_PATCH_FIELDS:
            value = retry_patch.get(field_name)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                return True
            if isinstance(value, str) and value.strip():
                return True
        provider_hint = retry_patch.get("provider_hint_overrides")
        return isinstance(provider_hint, dict) and bool(provider_hint)

    def _mark_retry_generation_result(
        self,
        result: PlanningResult,
        *,
        attempt_index: int,
        reason_codes: list[str],
        retry_patch: dict[str, Any],
    ) -> PlanningResult:
        marked_assets: list[PackagedAsset] = []
        for asset in result.asset_pack.assets:
            metadata = dict(asset.metadata)
            candidate_metadata = dict(metadata.get("candidate_metadata") or {})
            candidate_metadata.update(
                {
                    "visual_auto_retry_output": True,
                    "visual_auto_retry_attempt": attempt_index,
                    "retry_source_issue_codes": list(reason_codes),
                    "retry_patch": retry_patch,
                }
            )
            metadata.update(
                {
                    "visual_auto_retry_output": True,
                    "visual_auto_retry_attempt": attempt_index,
                    "retry_source_issue_codes": list(reason_codes),
                    "retry_patch": retry_patch,
                    "candidate_metadata": candidate_metadata,
                }
            )
            marked_assets.append(asset.model_copy(update={"metadata": metadata}))

        marked_reports = [
            report.model_copy(
                update={
                    "metadata": {
                        **dict(report.metadata),
                        "visual_auto_retry_output": True,
                        "visual_auto_retry_attempt": attempt_index,
                        "retry_source_issue_codes": list(reason_codes),
                    }
                }
            )
            for report in result.evaluation_reports
        ]
        asset_pack = result.asset_pack.model_copy(
            update={
                "assets": marked_assets,
                "metadata": {
                    **dict(result.asset_pack.metadata),
                    "visual_auto_retry_output": True,
                    "visual_auto_retry_attempt": attempt_index,
                },
            }
        )
        return result.model_copy(
            update={
                "evaluation_reports": marked_reports,
                "asset_pack": asset_pack,
                "metadata": {
                    **dict(result.metadata),
                    "visual_auto_retry_output": True,
                    "visual_auto_retry_attempt": attempt_index,
                    "retry_source_issue_codes": list(reason_codes),
                },
            }
        )

    def _merge_retry_generation_result(
        self,
        base_result: PlanningResult,
        retry_result: PlanningResult,
        *,
        records: list[dict[str, Any]],
        max_attempts: int,
    ) -> PlanningResult:
        review_updates = self._merge_post_generation_review_chain(
            base_result,
            retry_result,
            max_attempts=max_attempts,
        )
        asset_pack = base_result.asset_pack.model_copy(
            update={
                "assets": [*base_result.asset_pack.assets, *retry_result.asset_pack.assets],
                "manifest": {
                    **dict(base_result.asset_pack.manifest),
                    **dict(review_updates.get("asset_pack_manifest") or {}),
                    "visual_auto_retry": self._visual_auto_retry_summary(records, max_attempts),
                },
                "metadata": {
                    **dict(base_result.asset_pack.metadata),
                    **dict(review_updates.get("asset_pack_metadata") or {}),
                    "visual_auto_retry": self._visual_auto_retry_summary(records, max_attempts),
                },
            }
        )
        return base_result.model_copy(
            update={
                "layout_plans": [*base_result.layout_plans, *retry_result.layout_plans],
                "prompt_compilations": [*base_result.prompt_compilations, *retry_result.prompt_compilations],
                "condition_plans": [*base_result.condition_plans, *retry_result.condition_plans],
                "generation_plans": [*base_result.generation_plans, *retry_result.generation_plans],
                "evaluation_reports": [*base_result.evaluation_reports, *retry_result.evaluation_reports],
                "asset_pack": asset_pack,
                "metadata": {
                    **dict(base_result.metadata),
                    **dict(review_updates.get("result_metadata") or {}),
                    "visual_auto_retry": self._visual_auto_retry_summary(records, max_attempts),
                    "retry_generation_result_ids": self._dedupe_strings(
                        [
                            *self._string_list(base_result.metadata.get("retry_generation_result_ids")),
                            retry_result.planning_result_id,
                        ]
                    ),
                },
            }
        )

    def _merge_post_generation_review_chain(
        self,
        base_result: PlanningResult,
        retry_result: PlanningResult,
        *,
        max_attempts: int,
    ) -> dict[str, dict[str, Any]]:
        """Keep the retry output's review authoritative without losing the first review."""

        base_metadata = dict(base_result.metadata or {})
        retry_metadata = dict(retry_result.metadata or {})
        base_package = base_metadata.get("post_generation_review_package")
        retry_package = retry_metadata.get("post_generation_review_package")
        if not isinstance(retry_package, dict):
            return {}

        attempt_index = self._safe_int(retry_metadata.get("visual_auto_retry_attempt"), default=1) or 1
        history: list[dict[str, Any]] = []
        if isinstance(base_package, dict):
            previous = base_package.get("review_attempts")
            if isinstance(previous, list):
                history.extend(dict(item) for item in previous if isinstance(item, dict))
            else:
                history.append(self._post_generation_review_attempt(base_package, stage="initial", attempt_index=0))
        history.append(
            self._post_generation_review_attempt(
                retry_package,
                stage="final_retry" if attempt_index >= max_attempts else "retry",
                attempt_index=attempt_index,
            )
        )

        final_review = self._post_generation_final_review(
            retry_package,
            attempt_index=attempt_index,
            max_attempts=max_attempts,
        )
        final_package = dict(retry_package)
        final_package["review_attempts"] = history
        final_package["final_review"] = final_review
        final_package["metadata"] = {
            **dict(final_package.get("metadata") or {}),
            "review_stage": final_review["stage"],
            "review_attempt_count": len(history),
            "final_review_status": final_review["status"],
            "retry_budget_exhausted": not final_review["additional_retry_allowed"],
        }

        base_shared = dict(base_metadata.get("shared_capabilities") or {})
        retry_shared = dict(retry_metadata.get("shared_capabilities") or {})
        base_cluster = dict(base_shared.get("visual_cluster") or base_metadata.get("visual_cluster") or {})
        retry_cluster = dict(retry_shared.get("visual_cluster") or retry_metadata.get("visual_cluster") or {})
        merged_cluster = dict(base_cluster)
        for key in (
            "auto_retry_decisions",
            "real_review_signal_package",
            "mode_differentiation_review",
            "has_post_generation_review",
        ):
            if key in retry_cluster:
                merged_cluster[key] = retry_cluster[key]
        merged_cluster["quality_review_reports"] = self._merge_post_generation_quality_reports(
            base_cluster.get("quality_review_reports"),
            retry_cluster.get("quality_review_reports"),
        )
        merged_cluster["post_generation_review_package"] = final_package
        merged_cluster["post_generation_review_history"] = history
        base_shared["visual_cluster"] = merged_cluster

        result_metadata = {
            "shared_capabilities": base_shared,
            "visual_cluster": merged_cluster,
            "post_generation_review_package": final_package,
            "post_generation_review_history": history,
            "post_generation_review_summary": list(final_package.get("user_visible_summary") or []),
            "final_post_generation_review": final_review,
        }
        pack_review = {
            "post_generation_review_package": final_package,
            "post_generation_review_history": history,
            "final_post_generation_review": final_review,
        }
        return {
            "result_metadata": result_metadata,
            "asset_pack_manifest": pack_review,
            "asset_pack_metadata": pack_review,
        }

    def _post_generation_review_attempt(
        self,
        package: dict[str, Any],
        *,
        stage: str,
        attempt_index: int,
    ) -> dict[str, Any]:
        inspections = [dict(item) for item in package.get("inspections", []) if isinstance(item, dict)]
        issue_codes = self._dedupe_strings(
            issue.get("code")
            for inspection in inspections
            for issue in inspection.get("detected_issues", [])
            if isinstance(issue, dict) and issue.get("code")
        )
        return {
            "stage": stage,
            "attempt_index": attempt_index,
            "package_id": package.get("package_id"),
            "output_ids": self._dedupe_strings(inspection.get("output_id") for inspection in inspections),
            "inspection_ids": self._dedupe_strings(inspection.get("inspection_id") for inspection in inspections),
            "statuses": self._dedupe_strings(inspection.get("status") for inspection in inspections),
            "issue_codes": issue_codes,
            "inspections": inspections,
        }

    def _post_generation_final_review(
        self,
        package: dict[str, Any],
        *,
        attempt_index: int,
        max_attempts: int,
    ) -> dict[str, Any]:
        attempt = self._post_generation_review_attempt(
            package,
            stage="final_retry" if attempt_index >= max_attempts else "retry",
            attempt_index=attempt_index,
        )
        statuses = set(attempt["statuses"])
        if "fail_final" in statuses:
            status = "failed_final"
        elif "fail_retryable" in statuses:
            status = "failed_after_retry" if attempt_index >= max_attempts else "retry_recommended"
        elif "manual_review" in statuses:
            status = "manual_review"
        elif "warning" in statuses:
            status = "warning"
        elif statuses and statuses <= {"pass"}:
            status = "pass"
        else:
            status = "not_evaluated"
        return {
            "stage": attempt["stage"],
            "attempt_index": attempt_index,
            "status": status,
            "output_ids": attempt["output_ids"],
            "inspection_ids": attempt["inspection_ids"],
            "issue_codes": attempt["issue_codes"],
            "additional_retry_allowed": bool(status == "retry_recommended" and attempt_index < max_attempts),
        }

    def _merge_post_generation_quality_reports(self, *report_sets: Any) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        seen: set[str] = set()
        for report_set in report_sets:
            if not isinstance(report_set, list):
                continue
            for value in report_set:
                if not isinstance(value, dict):
                    continue
                key = str(value.get("review_id") or value)
                if key in seen:
                    continue
                seen.add(key)
                reports.append(dict(value))
        return reports

    def _with_visual_retry_metadata(
        self,
        result: PlanningResult,
        records: list[dict[str, Any]],
        max_attempts: int,
    ) -> PlanningResult:
        summary = self._visual_auto_retry_summary(records, max_attempts)
        asset_pack = result.asset_pack.model_copy(
            update={
                "manifest": {**dict(result.asset_pack.manifest), "visual_auto_retry": summary},
                "metadata": {**dict(result.asset_pack.metadata), "visual_auto_retry": summary},
            }
        )
        return result.model_copy(update={"asset_pack": asset_pack, "metadata": {**dict(result.metadata), "visual_auto_retry": summary}})

    def _apply_reviewed_delivery_preference(self, result: PlanningResult) -> PlanningResult:
        package = result.metadata.get("post_generation_review_package")
        if not isinstance(package, dict):
            return result
        attempts = package.get("review_attempts")
        if not isinstance(attempts, list) or len(attempts) < 2:
            return result

        ranked: list[dict[str, Any]] = []
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            output_ids = self._dedupe_strings(attempt.get("output_ids"))
            if not output_ids:
                continue
            score, hard_gate_passed = self._review_attempt_delivery_score(attempt)
            ranked.append(
                {
                    "attempt_index": self._safe_int(attempt.get("attempt_index"), default=0) or 0,
                    "stage": str(attempt.get("stage") or "review"),
                    "output_ids": output_ids,
                    "score": score,
                    "hard_gate_passed": hard_gate_passed,
                    "statuses": self._dedupe_strings(attempt.get("statuses")),
                    "issue_codes": self._dedupe_strings(attempt.get("issue_codes")),
                }
            )
        if len(ranked) < 2:
            return result

        ranked_outputs: list[dict[str, Any]] = []
        for attempt_summary in ranked:
            attempt = next(
                (
                    item
                    for item in attempts
                    if isinstance(item, dict)
                    and (self._safe_int(item.get("attempt_index"), default=0) or 0)
                    == attempt_summary["attempt_index"]
                    and str(item.get("stage") or "review") == attempt_summary["stage"]
                ),
                {},
            )
            inspections = [item for item in attempt.get("inspections", []) if isinstance(item, dict)]
            inspections_by_output = {
                str(item.get("output_id")): item
                for item in inspections
                if str(item.get("output_id") or "").strip()
            }
            for position, output_id in enumerate(attempt_summary["output_ids"]):
                inspection = inspections_by_output.get(output_id)
                if inspection is None and position < len(inspections):
                    inspection = inspections[position]
                score = attempt_summary["score"]
                hard_gate_passed = attempt_summary["hard_gate_passed"]
                hard_gate_failures: list[str] = []
                asset_id = ""
                score_card: dict[str, Any] = {}
                review_unavailable = False
                if inspection is not None:
                    score, hard_gate_passed, hard_gate_failures = self._review_inspection_delivery_score(inspection)
                    asset_id = str(inspection.get("asset_id") or "").strip()
                    score_card = dict(inspection.get("score_card") or {})
                    review_unavailable = "review_unavailable" in hard_gate_failures
                output_record = self.output_store.get_output(output_id)
                output_metadata = dict(output_record.metadata or {}) if output_record is not None else {}
                ranked_outputs.append(
                    {
                        "output_id": output_id,
                        "asset_id": asset_id,
                        "role_key": asset_id or f"position:{position}",
                        "attempt_index": attempt_summary["attempt_index"],
                        "stage": attempt_summary["stage"],
                        "score": score,
                        "hard_gate_passed": hard_gate_passed,
                        "hard_gate_failures": hard_gate_failures,
                        "identity_score": self._normalized_review_score(
                            score_card.get("same_person_readability", score_card.get("identity_consistency"))
                        ),
                        "prompt_score": self._normalized_review_score(
                            score_card.get("prompt_owned_channel_obedience", score_card.get("composition"))
                        ),
                        "human_score": self._normalized_review_score(
                            score_card.get("human_realism", score_card.get("artifact_safety"))
                        ),
                        "commercial_score": self._normalized_review_score(
                            score_card.get("commercial_finish", score_card.get("overall"))
                        ),
                        "identity_local_repair": bool(output_metadata.get("identity_local_repair")),
                        "review_unavailable": review_unavailable,
                    }
                )

        role_groups: dict[str, list[dict[str, Any]]] = {}
        for item in ranked_outputs:
            role_groups.setdefault(item["role_key"], []).append(item)
        per_role_comparison = bool(role_groups) and any(
            len({item["attempt_index"] for item in group}) > 1
            for group in role_groups.values()
        )
        if per_role_comparison:
            winners: list[dict[str, Any]] = []
            for role_key in sorted(role_groups):
                group = role_groups[role_key]
                for item in group:
                    item["identity_local_repair_acceptance_passed"] = self._identity_local_repair_candidate_accepted(
                        item,
                        group,
                    )
                accepted_group = [
                    item
                    for item in group
                    if not item["identity_local_repair"] or item["identity_local_repair_acceptance_passed"]
                ] or [item for item in group if not item["identity_local_repair"]] or group
                reviewed_group = [item for item in accepted_group if not item.get("review_unavailable")]
                if reviewed_group:
                    accepted_group = reviewed_group
                eligible = [item for item in accepted_group if item["hard_gate_passed"]] or accepted_group
                winners.append(max(eligible, key=lambda item: (item["score"], -item["attempt_index"])))
        else:
            eligible = [item for item in ranked if item["hard_gate_passed"]] or ranked
            attempt_winner = max(eligible, key=lambda item: (item["score"], -item["attempt_index"]))
            winners = [
                item
                for item in ranked_outputs
                if item["attempt_index"] == attempt_winner["attempt_index"]
            ]
            if not winners:
                winners = [
                    {
                        "output_id": output_id,
                        "asset_id": "",
                        "role_key": f"attempt:{attempt_winner['attempt_index']}",
                        "attempt_index": attempt_winner["attempt_index"],
                        "stage": attempt_winner["stage"],
                        "score": attempt_winner["score"],
                        "hard_gate_passed": attempt_winner["hard_gate_passed"],
                        "hard_gate_failures": [],
                    }
                    for output_id in attempt_winner["output_ids"]
                ]

        preferred_output_ids = self._dedupe_strings(item["output_id"] for item in winners)
        winner_attempts = sorted({item["attempt_index"] for item in winners})
        latest_attempt = max(item["attempt_index"] for item in ranked)
        preferred_score = sum(item["score"] for item in winners) / max(1, len(winners))
        preference = {
            "policy": "doc95_reviewed_best_attempt",
            "selection_scope": "per_asset_role" if per_role_comparison else "attempt",
            "preferred_output_ids": preferred_output_ids,
            "preferred_attempt_index": winner_attempts[0] if len(winner_attempts) == 1 else None,
            "preferred_attempt_indexes": winner_attempts,
            "preferred_score": round(preferred_score, 4),
            "latest_attempt_won": bool(winner_attempts and winner_attempts == [latest_attempt]),
            "ranked_attempts": ranked,
            "ranked_outputs": ranked_outputs,
            "append_only_attempt_history": True,
        }
        preferred = set(preference["preferred_output_ids"])
        for item in ranked_outputs:
            updater = getattr(self.output_store, "update_metadata", None)
            if callable(updater):
                updater(
                    item["output_id"],
                    {
                        "delivery_preferred_output": item["output_id"] in preferred,
                        "delivery_preference_policy": preference["policy"],
                        "delivery_preference_score": item["score"],
                        "delivery_preference_attempt_index": item["attempt_index"],
                        "delivery_preference_role_key": item["role_key"],
                        "delivery_preference_hard_gate_passed": item["hard_gate_passed"],
                        "delivery_preference_hard_gate_failures": list(item["hard_gate_failures"]),
                    },
                )

        asset_pack = result.asset_pack.model_copy(
            update={
                "manifest": {**dict(result.asset_pack.manifest), "reviewed_delivery_preference": preference},
                "metadata": {**dict(result.asset_pack.metadata), "reviewed_delivery_preference": preference},
            }
        )
        return result.model_copy(
            update={
                "asset_pack": asset_pack,
                "metadata": {**dict(result.metadata), "reviewed_delivery_preference": preference},
            }
        )

    def _identity_local_repair_candidate_accepted(
        self,
        candidate: dict[str, Any],
        group: list[dict[str, Any]],
    ) -> bool:
        if not candidate.get("identity_local_repair"):
            return True
        baselines = [
            item
            for item in group
            if not item.get("identity_local_repair")
            and int(item.get("attempt_index") or 0) < int(candidate.get("attempt_index") or 0)
        ]
        if not baselines:
            return False
        baseline = max(baselines, key=lambda item: (float(item.get("identity_score") or 0.0), -int(item.get("attempt_index") or 0)))
        identity = candidate.get("identity_score")
        baseline_identity = baseline.get("identity_score")
        if identity is None or baseline_identity is None:
            return False
        identity_improved = float(identity) >= 0.82 or float(identity) - float(baseline_identity) >= 0.06
        if not identity_improved:
            return False
        for key in ("prompt_score", "human_score", "commercial_score"):
            current = candidate.get(key)
            previous = baseline.get(key)
            if current is not None and previous is not None and float(current) < float(previous) - 0.03:
                return False
        return not candidate.get("hard_gate_failures")

    def _review_attempt_delivery_score(self, attempt: dict[str, Any]) -> tuple[float, bool]:
        inspections = [item for item in attempt.get("inspections", []) if isinstance(item, dict)]
        statuses = set(self._dedupe_strings(attempt.get("statuses")))
        issue_codes = set(self._dedupe_strings(attempt.get("issue_codes")))
        hard_gate_passed = not bool(
            statuses.intersection({"fail_final"})
            or issue_codes.intersection(DELIVERY_IDENTITY_HARD_GATE_ISSUES)
            or issue_codes.intersection(DELIVERY_PROMPT_CHANNEL_HARD_GATE_ISSUES)
        )
        status_score = 0.0
        if statuses and statuses <= {"pass"}:
            status_score = 1.0
        elif "warning" in statuses:
            status_score = 0.80
        elif "manual_review" in statuses:
            status_score = 0.55
        elif "fail_retryable" in statuses:
            status_score = 0.30

        dimension_scores: list[float] = []
        for inspection in inspections:
            card = inspection.get("score_card") if isinstance(inspection.get("score_card"), dict) else {}
            identity = self._normalized_review_score(
                card.get("same_person_readability", card.get("identity_consistency"))
            )
            prompt = self._normalized_review_score(
                card.get("prompt_owned_channel_obedience", card.get("composition"))
            )
            human = self._normalized_review_score(card.get("human_realism", card.get("artifact_safety")))
            commercial = self._normalized_review_score(card.get("commercial_finish", card.get("overall")))
            available = [value for value in (identity, prompt, human, commercial) if value is not None]
            if not available:
                continue
            identity = identity if identity is not None else sum(available) / len(available)
            prompt = prompt if prompt is not None else sum(available) / len(available)
            human = human if human is not None else sum(available) / len(available)
            commercial = commercial if commercial is not None else sum(available) / len(available)
            dimension_scores.append(identity * 0.45 + prompt * 0.25 + human * 0.15 + commercial * 0.15)
        quality_score = sum(dimension_scores) / len(dimension_scores) if dimension_scores else status_score
        return round(quality_score * 0.70 + status_score * 0.30, 4), hard_gate_passed

    def _review_inspection_delivery_score(self, inspection: dict[str, Any]) -> tuple[float, bool, list[str]]:
        status = str(inspection.get("status") or "").strip()
        detected = [item for item in inspection.get("detected_issues", []) if isinstance(item, dict)]
        issue_codes = set(
            self._dedupe_strings(
                [item.get("code") for item in detected]
                + list(inspection.get("issue_codes", []) if isinstance(inspection.get("issue_codes"), list) else [])
            )
        )
        hard_gate_failures: list[str] = []
        if status == "fail_final":
            hard_gate_failures.append("fail_final")
        if issue_codes.intersection(DELIVERY_IDENTITY_HARD_GATE_ISSUES):
            hard_gate_failures.append("identity_truth_not_respected")
        if issue_codes.intersection(DELIVERY_PROMPT_CHANNEL_HARD_GATE_ISSUES):
            hard_gate_failures.append("prompt_owned_channel_not_respected")
        if status == "manual_review" and issue_codes.intersection(
            {"provider_error", "vision_provider_unavailable", "vision_provider_not_configured"}
        ):
            hard_gate_failures.append("review_unavailable")

        status_score = {
            "pass": 1.0,
            "warning": 0.80,
            "manual_review": 0.55,
            "fail_retryable": 0.30,
            "fail_final": 0.0,
        }.get(status, 0.45)
        card = inspection.get("score_card") if isinstance(inspection.get("score_card"), dict) else {}
        values = [self._normalized_review_score(value) for value in card.values()]
        available = [value for value in values if value is not None]
        fallback = sum(available) / len(available) if available else status_score
        identity = self._normalized_review_score(
            card.get("same_person_readability", card.get("identity_consistency"))
        )
        prompt = self._normalized_review_score(
            card.get("prompt_owned_channel_obedience", card.get("composition"))
        )
        human = self._normalized_review_score(card.get("human_realism", card.get("artifact_safety")))
        commercial = self._normalized_review_score(card.get("commercial_finish", card.get("overall")))
        quality_score = (
            (identity if identity is not None else fallback) * 0.45
            + (prompt if prompt is not None else fallback) * 0.25
            + (human if human is not None else fallback) * 0.15
            + (commercial if commercial is not None else fallback) * 0.15
        )
        return (
            round(quality_score * 0.70 + status_score * 0.30, 4),
            not hard_gate_failures,
            hard_gate_failures,
        )

    def _normalized_review_score(self, value: Any) -> float | None:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return None
        if score > 1.0:
            score /= 100.0
        return max(0.0, min(1.0, score))

    def _visual_retry_execution_record(
        self,
        *,
        record: ProductJobRecord | None,
        status: str,
        attempt_index: int,
        max_attempts: int,
        reason_codes: list[str],
        retry_patch: dict[str, Any],
        source: str,
        retry_output_ids: list[str] | None = None,
        retry_candidate_ids: list[str] | None = None,
        blocked_reason: str | None = None,
    ) -> dict[str, Any]:
        job_id = record.job_id if record is not None else "job_unavailable"
        project_id = None
        if record is not None:
            project_id = record.request.metadata.get("project_id")
        return {
            "retry_execution_id": stable_id("visual_retry_execution", job_id, attempt_index, status, ",".join(reason_codes)),
            "project_id": project_id,
            "original_job_id": job_id,
            "retry_job_id": job_id,
            "attempt_index": attempt_index,
            "max_attempts": max_attempts,
            "status": status,
            "reason_codes": self._dedupe_strings(reason_codes),
            "retry_patch": retry_patch,
            "retry_output_ids": list(retry_output_ids or []),
            "retry_candidate_ids": list(retry_candidate_ids or []),
            "blocked_reason": blocked_reason,
            "source": source,
            "created_at": _utc_now_iso(),
            "metadata": {"append_only": True, "doc": "53"},
        }

    def _visual_auto_retry_summary(self, records: list[dict[str, Any]], max_attempts: int) -> dict[str, Any]:
        executed = [record for record in records if record.get("status") == "executed"]
        issue_codes = self._dedupe_strings(code for record in records for code in record.get("reason_codes", []))
        return {
            "enabled": max_attempts > 0,
            "executed_count": len(executed),
            "max_attempts": max_attempts,
            "issue_codes": issue_codes,
            "records": records,
            "append_only": True,
        }

    def _visual_result_output_ids(self, result: PlanningResult) -> list[str]:
        values: list[str] = []
        for asset in result.asset_pack.assets:
            metadata = dict(asset.metadata or {})
            candidate_metadata = metadata.get("candidate_metadata") if isinstance(metadata.get("candidate_metadata"), dict) else {}
            output_id = candidate_metadata.get("output_id") or metadata.get("output_id")
            if output_id:
                values.append(str(output_id))
        return self._dedupe_strings(values)

    def _visual_result_candidate_ids(self, result: PlanningResult) -> list[str]:
        values: list[str] = []
        for asset in result.asset_pack.assets:
            candidate_id = asset.metadata.get("selected_candidate_id")
            if candidate_id:
                values.append(str(candidate_id))
        return self._dedupe_strings(values)

    def _string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _dedupe_strings(self, values: Any) -> list[str]:
        if isinstance(values, str):
            raw_values = [part.strip() for part in values.split(",")]
        else:
            try:
                raw_values = list(values or [])
            except TypeError:
                raw_values = [values]
        result: list[str] = []
        seen: set[str] = set()
        for value in raw_values:
            text = str(value or "").strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    def _safe_int(self, value: Any, default: int | None = 0) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def select_result(
        self,
        job_id: str,
        request: SelectResultRequest | dict[str, Any] | None = None,
    ) -> SelectionResponse:
        record = self.job_store.get(job_id)
        if record is None:
            selected = SelectedResult(metadata={"selection_status": "job_not_found"})
            status = self._not_found_status(job_id)
            return SelectionResponse(
                job_id=job_id,
                status=ProductJobStatusValue.NOT_FOUND,
                selected_result=selected,
                job_status=status,
                warnings=["Creative job was not found in the V3 product API store."],
                metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
            )
        select_request = self._coerce_select_request(request or {})
        result = record.generation_result or record.planning_result
        if result is None:
            record.status = (
                ProductJobStatusValue.BLOCKED
                if record.scenario_resolution is not None and not record.scenario_resolution.can_create_jobs
                else ProductJobStatusValue.FAILED
            )
            record.warnings.append("Creative job has no planning or generation result to select.")
            record.lifecycle = self._build_lifecycle(record)
            self.job_store.save(record)
            selected = SelectedResult(metadata={"selection_status": "missing_result"})
            return SelectionResponse(
                job_id=job_id,
                status=record.status,
                selected_result=selected,
                job_status=self._status_from_record(record),
                warnings=list(record.warnings),
                metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
            )

        selected_assets = self._selected_assets(result, select_request)
        selected_candidate_ids = [
            asset.metadata["selected_candidate_id"]
            for asset in selected_assets
            if asset.metadata.get("selected_candidate_id")
        ]
        selected_asset_ids = [asset.asset_id for asset in selected_assets]
        update = self._memory_update_for_selection(result.asset_pack.brand_memory_update, selected_asset_ids)
        memory_update_applied = False
        if update is not None and select_request.apply_memory_update:
            memory_update_applied = self.brand_profile_service.apply_memory_update(update) is not None

        selected = SelectedResult(
            selected_candidate_ids=selected_candidate_ids,
            selected_asset_ids=selected_asset_ids,
            asset_pack_id=result.asset_pack.asset_pack_id,
            memory_update_id=update.memory_update_id if update else None,
            memory_update_applied=memory_update_applied,
            metadata={
                "selection_status": "selected",
                "source": "V3ProductApiService",
                "apply_memory_update_requested": select_request.apply_memory_update,
            },
        )
        record.selected_result = selected
        record.status = ProductJobStatusValue.SELECTED
        record.lifecycle = self._build_lifecycle(record)
        self.job_store.save(record)
        return SelectionResponse(
            job_id=job_id,
            status=record.status,
            selected_result=selected,
            job_status=self._status_from_record(record),
            warnings=list(record.warnings),
            metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
        )

    def create_brand(self, request: CreateBrandRequest | dict[str, Any]) -> BrandApiResponse:
        create_request = self._coerce_create_brand_request(request)
        brand_id = create_request.brand_id or stable_id(
            "brand",
            create_request.brand_name or "unnamed",
            ",".join(create_request.visual_tone),
            ",".join(create_request.color_palette),
        )
        profile = BrandProfile(
            brand_id=brand_id,
            brand_name=create_request.brand_name,
            industry=create_request.industry,
            is_temporary=False,
            visual_tone=list(create_request.visual_tone),
            color_palette=list(create_request.color_palette),
            layout_preference=create_request.layout_preference,
            typography_preference=create_request.typography_preference,
            copywriting_tone=create_request.copywriting_tone,
            platform_history=list(create_request.platform_history),
            metadata={
                **create_request.metadata,
                "source": "V3ProductApiService",
                "created_via_v3_product_api": True,
                "rules_version": RULE_VERSION,
            },
        )
        saved = self.brand_profile_service.save_profile(profile)
        return BrandApiResponse(
            status="created",
            brand=saved,
            api_namespace=API_NAMESPACE,
            route=get_route_contracts()["create_brand"],
            metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
        )

    def get_brand(self, brand_id: str) -> BrandApiResponse:
        profile = self.brand_profile_service.load_profile(brand_id)
        route = get_route_contracts()["get_brand"].format(brand_id=brand_id)
        if profile is None:
            return BrandApiResponse(
                status="not_found",
                brand=None,
                api_namespace=API_NAMESPACE,
                route=route,
                warnings=["Brand profile was not found in the V3 brand memory store."],
                metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
            )
        return BrandApiResponse(
            status="found",
            brand=profile,
            api_namespace=API_NAMESPACE,
            route=route,
            metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
        )

    def estimate_balance(self, asset_count: int) -> dict[str, Any]:
        return self._balance_estimate_to_dict(self.balance_adapter.estimate_planning_cost(asset_count))

    def export_job(self, job_id: str) -> V3ExportPackageResponse:
        record = self.job_store.get(job_id)
        download_route = f"{API_NAMESPACE}/jobs/{job_id}/export/download"
        if record is None:
            return V3ExportPackageResponse(
                job_id=job_id,
                status=ProductJobStatusValue.NOT_FOUND,
                api_namespace=API_NAMESPACE,
                download_route=download_route,
                warnings=["Creative job was not found in the V3 product API store."],
                metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
            )

        scenario_id = record.scenario_resolution.manifest.scenario_id if record.scenario_resolution else None
        if scenario_id != "ecommerce":
            manifest = self._generic_export_manifest(record, scenario_id)
            return V3ExportPackageResponse(
                job_id=record.job_id,
                status=record.status,
                api_namespace=API_NAMESPACE,
                scenario_id=scenario_id,
                manifest=manifest,
                download_route=download_route,
                warnings=["Dedicated export packaging is currently available for E-Commerce jobs."],
                metadata={
                    "source": "V3ProductApiService",
                    "rules_version": RULE_VERSION,
                    "export_scope": "generic_manifest_only",
                    "v3_independent_product_api": True,
                },
            )

        pack_output = self._ecommerce_pack_output(record)
        export_package = pack_output.export_package.model_dump(mode="json")
        manifest = self._ecommerce_export_manifest(record, pack_output)
        return V3ExportPackageResponse(
            job_id=record.job_id,
            status=record.status,
            api_namespace=API_NAMESPACE,
            scenario_id=scenario_id,
            package_id=pack_output.export_package.package_id,
            export_package=export_package,
            manifest=manifest,
            download_route=download_route,
            warnings=self._ecommerce_public_warnings(record, pack_output),
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "export_scope": "ecommerce_image_set_manifest",
                "v3_independent_product_api": True,
                "imports_v1_v2_runtime": False,
            },
        )

    def export_job_download(self, job_id: str) -> V3ExportDownloadPayload:
        response = self.export_job(job_id)
        payload = response.manifest or response.model_dump(mode="json")
        package_id = response.package_id or f"v3_export_{job_id}"
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        return V3ExportDownloadPayload(
            filename=f"{package_id}.json",
            content=content,
            response=response,
        )

    def _status_from_record(self, record: ProductJobRecord) -> ProductJobStatus:
        result = record.generation_result or record.planning_result
        if result is None:
            return self._empty_status_from_record(record)
        asset_pack = result.asset_pack
        nav = get_navigation_entry()
        return ProductJobStatus(
            job_id=record.job_id,
            status=record.status,
            api_namespace=API_NAMESPACE,
            ui_entry_route=nav["route"],
            brand_id=result.brand_profile.brand_id,
            planning_result_id=record.planning_result.planning_result_id if record.planning_result else None,
            generation_result_id=record.generation_result.planning_result_id if record.generation_result else None,
            asset_pack_id=asset_pack.asset_pack_id,
            scenario=self._scenario_summary(record),
            campaign=self._campaign_summary(record, result),
            asset_series=self._asset_series(result, record.status),
            candidates=self._candidate_summaries(result),
            style_continuation=self._style_continuation_summary(record, result),
            general_creative=self._general_creative_summary(record),
            ecommerce=self._ecommerce_summary(record),
            selected_result=record.selected_result,
            balance_estimate=dict(record.balance_estimate),
            routes=get_route_contracts(),
            warnings=list(dict.fromkeys(record.warnings + asset_pack.manifest.get("warnings", []))),
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
                "balance_adapter": self.balance_adapter.adapter_name,
                "selected_vertical_pack": result.metadata.get("selected_vertical_pack"),
                "scenario_id": result.metadata.get("scenario_id"),
                "shared_capabilities": result.metadata.get("shared_capabilities") or self._capability_run_summary(record.capability_run),
                "visual_auto_retry": result.metadata.get("visual_auto_retry", {}),
                "post_generation_review": result.metadata.get("post_generation_review_package", {}),
                "exposes_product_concepts_only": True,
                "lifecycle": self._lifecycle_summary(record),
                **self._workflow_artifacts_metadata(record, result),
                **self._project_mode_status_metadata(record),
            },
        )

    def _empty_status_from_record(self, record: ProductJobRecord) -> ProductJobStatus:
        nav = get_navigation_entry()
        return ProductJobStatus(
            job_id=record.job_id,
            status=record.status,
            api_namespace=API_NAMESPACE,
            ui_entry_route=nav["route"],
            scenario=self._scenario_summary(record),
            balance_estimate=dict(record.balance_estimate),
            routes=get_route_contracts(),
            warnings=list(dict.fromkeys(record.warnings)),
            general_creative=self._general_creative_summary(record),
            ecommerce=self._ecommerce_summary(record),
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
                "balance_adapter": self.balance_adapter.adapter_name,
                "exposes_product_concepts_only": True,
                "blocked_before_planning": record.status == ProductJobStatusValue.BLOCKED,
                "shared_capabilities": self._capability_run_summary(record.capability_run),
                "lifecycle": self._lifecycle_summary(record),
                **self._project_mode_status_metadata(record),
            },
        )

    def _project_mode_status_metadata(self, record: ProductJobRecord) -> dict[str, Any]:
        request_metadata = dict(record.request.metadata or {})
        allowed_keys = {
            "project_id",
            "template_id",
            "template_manifest_id",
            "project_job_sequence",
            "project_context_version",
            "project_context_snapshot",
            "project_mode",
            "apply_brand_memory_update_default",
            "variation_mode",
            "effective_variation_mode",
            "continuation_mode",
            "inferred_variation_mode",
            "variation_mode_source",
            "variation_mode_label",
            "scenario_parameters",
            "commerce_profile_present",
            "ecommerce_text_to_image_fallback",
            "has_product_reference",
            "provider_failure_retry",
            "provider_failure_retry_exhausted",
        }
        return {key: request_metadata[key] for key in allowed_keys if key in request_metadata}

    def _not_found_status(self, job_id: str) -> ProductJobStatus:
        nav = get_navigation_entry()
        return ProductJobStatus(
            job_id=job_id,
            status=ProductJobStatusValue.NOT_FOUND,
            api_namespace=API_NAMESPACE,
            ui_entry_route=nav["route"],
            routes=get_route_contracts(),
            warnings=["Creative job was not found in the V3 product API store."],
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
            },
        )

    def _history_item_from_record(self, record: ProductJobRecord) -> V3JobHistoryItem:
        status = self._status_from_record(record)
        scenario_id = status.scenario.scenario_id if status.scenario else None
        scenario_label = status.scenario.display_name if status.scenario else None
        selected_preset_id = status.scenario.selected_preset_id if status.scenario else None
        selected_asset_count = len(record.selected_result.selected_asset_ids) if record.selected_result else 0
        return V3JobHistoryItem(
            job_id=record.job_id,
            status=record.status,
            scenario_id=scenario_id,
            scenario_label=scenario_label,
            selected_preset_id=selected_preset_id,
            user_input=record.request.user_input,
            asset_count=len(status.asset_series),
            candidate_count=len(status.candidates),
            selected_asset_count=selected_asset_count,
            created_at=record.created_at,
            updated_at=record.updated_at,
            route=self._history_route_for_scenario(scenario_id),
            metadata={
                "source": "V3ProductApiService",
                "prompt_language": "product" if scenario_id == "ecommerce" else "neutral_subject",
                "v3_history_owned": True,
                "imports_v1_v2_runtime": False,
                "imports_lab_runtime": False,
            },
        )

    def _history_items_from_output_store(self, limit: int) -> list[V3JobHistoryItem]:
        by_job: dict[str, list[V3GeneratedOutputRecord]] = {}
        for record in self.output_store.list_outputs(limit=max(100, limit * 10)):
            by_job.setdefault(record.job_id, []).append(record)
        items: list[V3JobHistoryItem] = []
        for job_id, records in by_job.items():
            sorted_records = sorted(records, key=lambda item: item.created_at or "", reverse=True)
            latest = sorted_records[0]
            items.append(
                V3JobHistoryItem(
                    job_id=job_id,
                    status=ProductJobStatusValue.GENERATED,
                    scenario_id=None,
                    scenario_label="V3 Generated Output",
                    selected_preset_id=None,
                    user_input="Restored V3 generated image output",
                    asset_count=len(sorted_records),
                    candidate_count=len(sorted_records),
                    selected_asset_count=len(sorted_records),
                    created_at=sorted_records[-1].created_at,
                    updated_at=latest.created_at,
                    route=get_navigation_entry()["route"],
                    metadata={
                        "source": "V3GeneratedOutputStore",
                        "restored_from_output_store": True,
                        "first_output_id": latest.output_id,
                        "thumbnail_url": latest.thumbnail_url,
                        "preview_url": latest.preview_url,
                        "download_url": latest.download_url,
                        "v3_history_owned": True,
                        "imports_v1_v2_runtime": False,
                        "imports_lab_runtime": False,
                    },
                )
            )
        return sorted(items, key=lambda item: item.updated_at or item.created_at, reverse=True)[:limit]

    def _status_from_output_store(self, job_id: str) -> ProductJobStatus | None:
        records = self.output_store.list_by_job(job_id)
        if not records:
            return None
        records = sorted(records, key=lambda item: item.created_at or "")
        asset_series: list[AssetSeriesItem] = []
        candidates: list[CandidateSummary] = []
        for index, record in enumerate(records):
            candidate_metadata = self._candidate_metadata_from_output_record(record)
            asset_series.append(
                AssetSeriesItem(
                    asset_id=record.asset_id,
                    asset_type=AssetType.SINGLE_IMAGE.value,
                    platform=Platform.ECOMMERCE_GENERIC,
                    aspect_ratio=self._aspect_ratio_from_output_record(record),
                    purpose="Restored V3 generated image output",
                    status=ProductJobStatusValue.GENERATED.value,
                    selected_candidate_id=record.candidate_id,
                    preview_uri=record.thumbnail_url or record.preview_url,
                    output_id=record.output_id,
                    download_url=record.download_url,
                    preview_url=record.preview_url,
                    thumbnail_url=record.thumbnail_url,
                    metadata={
                        "requires_text_overlay": False,
                        "requires_brand_consistency": True,
                        "candidate_metadata": candidate_metadata,
                        "restored_from_output_store": True,
                        "restored_index": index + 1,
                    },
                )
            )
            candidates.append(
                CandidateSummary(
                    candidate_id=record.candidate_id,
                    asset_id=record.asset_id,
                    platform=Platform.ECOMMERCE_GENERIC,
                    preview_uri=record.thumbnail_url or record.preview_url,
                    output_id=record.output_id,
                    download_url=record.download_url,
                    preview_url=record.preview_url,
                    thumbnail_url=record.thumbnail_url,
                    overall_score=None,
                    recommendation="manual_review",
                    selected=True,
                    metadata={
                        "asset_pack_id": None,
                        "restored_from_output_store": True,
                        **candidate_metadata,
                    },
                )
            )
        nav = get_navigation_entry()
        return ProductJobStatus(
            job_id=job_id,
            status=ProductJobStatusValue.GENERATED,
            api_namespace=API_NAMESPACE,
            ui_entry_route=nav["route"],
            asset_series=asset_series,
            candidates=candidates,
            routes=get_route_contracts(),
            warnings=["This V3 job record was restored from generated output files because the in-memory job detail is unavailable."],
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
                "restored_from_output_store": True,
                "output_count": len(records),
                **self._workflow_artifacts_from_output_records(records),
            },
        )

    def _workflow_artifacts_metadata(self, record: ProductJobRecord, result: PlanningResult) -> dict[str, Any]:
        prompt = result.prompt_compilations[0] if result.prompt_compilations else None
        final_prompt = ""
        candidate_llm_brain: dict[str, Any] = {}
        for asset in result.asset_pack.assets:
            candidate_metadata = asset.metadata.get("candidate_metadata", {}) if asset.metadata else {}
            final_prompt = str(candidate_metadata.get("final_provider_prompt") or "").strip()
            if isinstance(candidate_metadata.get("llm_brain"), dict):
                candidate_llm_brain = candidate_metadata["llm_brain"]
            if final_prompt:
                break
        result_llm_brain = result.metadata.get("llm_brain") if isinstance(result.metadata.get("llm_brain"), dict) else {}
        prompt_llm_summary = (
            prompt.provider_notes.get("llm_brain_summary", {})
            if prompt is not None and isinstance(prompt.provider_notes.get("llm_brain_summary"), dict)
            else {}
        )
        if prompt is None and not final_prompt:
            return {}
        return {
            "workflow_artifacts": {
                "user_request": record.request.user_input,
                "optimized_direction": prompt.visual_prompt if prompt else "",
                "style_notes": list(prompt.style_notes) if prompt else [],
                "layout_notes": list(prompt.layout_notes) if prompt else [],
                "hard_constraints": list(prompt.hard_constraints) if prompt else [],
                "negative_prompt": prompt.negative_prompt if prompt else "",
                "final_provider_prompt": final_prompt,
                "llm_brain": candidate_llm_brain or result_llm_brain,
                "llm_brain_summary": prompt_llm_summary
                or (candidate_llm_brain.get("user_visible_summary") if isinstance(candidate_llm_brain, dict) else {})
                or (result_llm_brain.get("user_visible_summary") if isinstance(result_llm_brain, dict) else {}),
                "prompt_available": prompt is not None,
                "final_prompt_available": bool(final_prompt),
            }
        }

    def _workflow_artifacts_from_output_records(self, records: list[V3GeneratedOutputRecord]) -> dict[str, Any]:
        for record in sorted(records, key=lambda item: item.created_at or "", reverse=True):
            metadata = dict(record.metadata or {})
            if metadata.get("compiled_visual_direction") or metadata.get("final_provider_prompt"):
                llm_brain = metadata.get("llm_brain") if isinstance(metadata.get("llm_brain"), dict) else {}
                return {
                    "workflow_artifacts": {
                        "user_request": "",
                        "optimized_direction": str(metadata.get("compiled_visual_direction") or ""),
                        "style_notes": list(metadata.get("style_notes") or []),
                        "layout_notes": list(metadata.get("layout_notes") or []),
                        "hard_constraints": [],
                        "negative_prompt": ", ".join(metadata.get("negative_constraints") or []),
                        "final_provider_prompt": str(metadata.get("final_provider_prompt") or ""),
                        "llm_brain": llm_brain,
                        "llm_brain_summary": metadata.get("llm_brain_summary")
                        if isinstance(metadata.get("llm_brain_summary"), dict)
                        else llm_brain.get("user_visible_summary", {}),
                        "prompt_available": bool(metadata.get("compiled_visual_direction")),
                        "final_prompt_available": bool(metadata.get("final_provider_prompt")),
                        "restored_from_output_store": True,
                    }
                }
        return {
            "workflow_artifacts": {
                "prompt_available": False,
                "final_prompt_available": False,
                "restored_from_output_store": True,
            }
        }

    def _candidate_metadata_from_output_record(self, record: V3GeneratedOutputRecord) -> dict[str, Any]:
        return {
            **dict(record.metadata or {}),
            "output_id": record.output_id,
            "download_url": record.download_url,
            "preview_url": record.preview_url,
            "thumbnail_url": record.thumbnail_url,
            "url": record.download_url,
            "actual_provider": record.provider,
            "actual_model": record.model,
            "width": record.width,
            "height": record.height,
            "mime_type": record.mime_type,
            "format": record.output_format,
            "v3_owned_output": True,
        }

    def _aspect_ratio_from_output_record(self, record: V3GeneratedOutputRecord) -> str:
        width = int(record.width or 0)
        height = int(record.height or 0)
        if width <= 0 or height <= 0:
            return "1:1"
        if width == height:
            return "1:1"
        if width > height:
            return "16:9" if width / height > 1.5 else "4:3"
        return "9:16" if height / width > 1.5 else "4:5"

    def _history_route_for_scenario(self, scenario_id: str | None) -> str:
        route_tokens = {
            "general_creative": "general",
            "ecommerce": "ecommerce",
            "new_media": "new-media",
            "private_domain": "private-domain",
            "brand_ip": "brand-ip",
        }
        base_route = get_navigation_entry()["route"].rstrip("/")
        token = route_tokens.get(scenario_id or "")
        return f"{base_route}/{token}" if token else base_route

    def _scenario_summary(self, record: ProductJobRecord) -> ScenarioSummary | None:
        resolution = record.scenario_resolution
        if resolution is None:
            return None
        manifest = resolution.manifest
        return ScenarioSummary(
            scenario_id=manifest.scenario_id,
            display_name=manifest.display_name,
            status=resolution.status.value,
            can_create_jobs=resolution.can_create_jobs,
            selected_mode_id=resolution.selected_mode_id,
            selected_preset_id=resolution.selected_preset_id,
            route_hint=manifest.route_hint,
            ui_card=dict(manifest.ui_card),
            warnings=list(resolution.warnings),
            metadata={
                **resolution.metadata,
                "enabled_capabilities": list(manifest.enabled_capabilities),
            },
        )

    def _campaign_summary(self, record: ProductJobRecord, result: PlanningResult) -> CampaignSummary:
        brief = result.commercial_brief
        campaign = record.request.campaign
        return CampaignSummary(
            campaign_id=campaign.campaign_id if campaign and campaign.campaign_id else brief.brief_id,
            campaign_name=campaign.campaign_name if campaign else brief.metadata.get("campaign_name"),
            scenario=brief.scenario,
            business_goal=campaign.business_goal if campaign and campaign.business_goal else brief.business_goal,
            target_platforms=list(campaign.platforms) if campaign and campaign.platforms else list(brief.target_platforms),
            commercial_hooks=list(brief.commercial_hooks),
            metadata={
                "brief_id": brief.brief_id,
                "industry": brief.industry.value,
                "confidence": brief.confidence,
                "request_campaign_supplied": campaign is not None,
            },
        )

    def _style_continuation_summary(
        self,
        record: ProductJobRecord,
        result: PlanningResult,
    ) -> StyleContinuationSummary:
        requested_brand_id = record.request.continue_style_from_brand_id or record.request.brand_id
        enabled = requested_brand_id is not None and not result.brand_profile.is_temporary
        return StyleContinuationSummary(
            enabled=enabled,
            source_brand_id=requested_brand_id,
            visual_tone=list(result.brand_profile.visual_tone),
            color_palette=list(result.brand_profile.color_palette),
            reference_asset_count=len(result.brand_profile.reference_assets),
            metadata={
                "brand_id": result.brand_profile.brand_id,
                "brand_profile_temporary": result.brand_profile.is_temporary,
            },
        )

    def _asset_series(self, result: PlanningResult, status: ProductJobStatusValue) -> list[AssetSeriesItem]:
        packaged_by_id = {asset.asset_id: asset for asset in result.asset_pack.assets}
        items: list[AssetSeriesItem] = []
        for asset in result.series_plan.assets:
            packaged = packaged_by_id.get(asset.asset_id)
            render_manifest = packaged.metadata.get("render_manifest") if packaged else None
            selected_candidate_id = packaged.metadata.get("selected_candidate_id") if packaged else None
            candidate_metadata = packaged.metadata.get("candidate_metadata", {}) if packaged else {}
            item_status = "generated" if selected_candidate_id else status.value
            if status == ProductJobStatusValue.SELECTED and selected_candidate_id:
                item_status = "selected"
            items.append(
                AssetSeriesItem(
                    asset_id=asset.asset_id,
                    asset_type=asset.asset_type.value,
                    platform=asset.platform,
                    aspect_ratio=asset.aspect_ratio,
                    purpose=asset.purpose,
                    status=item_status,
                    selected_candidate_id=selected_candidate_id,
                    preview_uri=self._output_preview_uri(packaged.uri if packaged else None, candidate_metadata),
                    output_id=candidate_metadata.get("output_id"),
                    download_url=candidate_metadata.get("download_url") or candidate_metadata.get("url"),
                    preview_url=candidate_metadata.get("preview_url"),
                    thumbnail_url=candidate_metadata.get("thumbnail_url"),
                    editable_text_layer_count=len(render_manifest.get("editable_text_layers", [])) if render_manifest else 0,
                    metadata={
                        "requires_text_overlay": asset.requires_text_overlay,
                        "requires_brand_consistency": asset.requires_brand_consistency,
                        "asset_metadata": dict(asset.metadata),
                        "ecommerce_slot": asset.metadata.get("ecommerce_slot"),
                        "ecommerce_recipe": asset.metadata.get("ecommerce_recipe"),
                        "candidate_metadata": candidate_metadata,
                    },
                )
            )
        return items

    def _candidate_summaries(self, result: PlanningResult) -> list[CandidateSummary]:
        candidates: list[CandidateSummary] = []
        evals_by_candidate_id = {
            report.candidate_id: report for report in result.evaluation_reports if report.candidate_id is not None
        }
        assets_by_id = {asset.asset_id: asset for asset in result.series_plan.assets}
        selected_candidate_ids = {
            asset.metadata.get("selected_candidate_id")
            for asset in result.asset_pack.assets
            if asset.metadata.get("selected_candidate_id")
        }
        for asset in result.asset_pack.assets:
            candidate_id = asset.metadata.get("selected_candidate_id")
            if not candidate_id:
                continue
            report = evals_by_candidate_id.get(candidate_id)
            asset_spec = assets_by_id.get(asset.asset_id)
            candidate_metadata = asset.metadata.get("candidate_metadata", {})
            asset_metadata = dict(asset_spec.metadata) if asset_spec else dict(asset.metadata.get("asset_metadata", {}))
            candidates.append(
                CandidateSummary(
                    candidate_id=candidate_id,
                    asset_id=asset.asset_id,
                    platform=asset_spec.platform if asset_spec else asset.platform,
                    preview_uri=self._output_preview_uri(asset.uri, candidate_metadata),
                    output_id=candidate_metadata.get("output_id"),
                    download_url=candidate_metadata.get("download_url") or candidate_metadata.get("url"),
                    preview_url=candidate_metadata.get("preview_url"),
                    thumbnail_url=candidate_metadata.get("thumbnail_url"),
                    overall_score=report.overall_score if report else None,
                    recommendation=report.recommendation.value if report else None,
                    selected=candidate_id in selected_candidate_ids,
                    metadata={
                        "asset_pack_id": result.asset_pack.asset_pack_id,
                        "asset_metadata": asset_metadata,
                        "ecommerce_slot": asset.metadata.get("ecommerce_slot") or asset_metadata.get("ecommerce_slot"),
                        "ecommerce_recipe": asset.metadata.get("ecommerce_recipe") or asset_metadata.get("ecommerce_recipe"),
                        **candidate_metadata,
                    },
                )
            )
        return candidates

    def _output_preview_uri(self, fallback: str | None, metadata: dict[str, Any]) -> str | None:
        return metadata.get("thumbnail_url") or metadata.get("preview_url") or fallback

    def _selected_assets(self, result: PlanningResult, request: SelectResultRequest) -> list[PackagedAsset]:
        assets = result.asset_pack.assets
        if request.selected_candidate_id:
            return [
                asset
                for asset in assets
                if asset.metadata.get("selected_candidate_id") == request.selected_candidate_id
            ]
        if request.selected_asset_id:
            return [asset for asset in assets if asset.asset_id == request.selected_asset_id]
        return list(assets)

    def _memory_update_for_selection(
        self,
        update: MemoryUpdate | None,
        selected_asset_ids: list[str],
    ) -> MemoryUpdate | None:
        if update is None:
            return None
        selected_asset_set = set(selected_asset_ids)
        selected_refs = [
            ref for ref in update.new_reference_assets if ref.metadata.get("candidate_id") or ref.asset_id in selected_asset_set
        ]
        filtered = update.model_copy(deep=True)
        filtered.accepted_asset_ids = [asset_id for asset_id in update.accepted_asset_ids if asset_id in selected_asset_set]
        if not filtered.accepted_asset_ids:
            filtered.accepted_asset_ids = list(selected_asset_ids)
        filtered.new_reference_assets = selected_refs or list(update.new_reference_assets)
        filtered.metadata = {
            **filtered.metadata,
            "selected_via_v3_product_api": True,
            "selected_asset_ids": list(selected_asset_ids),
        }
        return filtered

    def _build_lifecycle(self, record: ProductJobRecord) -> JobLifecycleRecord:
        result = record.generation_result or record.planning_result
        scenario_id = record.scenario_resolution.manifest.scenario_id if record.scenario_resolution else None
        runs: list[RunRecord] = []
        candidates: list[CandidateRecord] = []
        selections: list[CandidateSelectionRecord] = []
        exports: list[ExportRecord] = []

        if record.planning_result is not None:
            run_id = stable_id("run", record.job_id, record.planning_result.planning_result_id, "planning")
            runs.append(
                RunRecord(
                    run_id=run_id,
                    job_id=record.job_id,
                    status="planned",
                    planning_result_id=record.planning_result.planning_result_id,
                    metadata={"run_type": "planning"},
                )
            )

        if record.generation_result is not None:
            run_id = stable_id("run", record.job_id, record.generation_result.planning_result_id, "generation")
            evals_by_candidate_id = {
                report.candidate_id: report
                for report in record.generation_result.evaluation_reports
                if report.candidate_id is not None
            }
            for asset in record.generation_result.asset_pack.assets:
                candidate_id = asset.metadata.get("selected_candidate_id")
                if not candidate_id:
                    continue
                report = evals_by_candidate_id.get(candidate_id)
                candidates.append(
                    CandidateRecord(
                        candidate_id=candidate_id,
                        job_id=record.job_id,
                        run_id=run_id,
                        asset_id=asset.asset_id,
                        status="selected_for_pack",
                        preview_uri=self._output_preview_uri(asset.uri, asset.metadata.get("candidate_metadata", {})),
                        overall_score=report.overall_score if report else None,
                        recommendation=report.recommendation.value if report else None,
                        metadata={
                            "asset_pack_id": record.generation_result.asset_pack.asset_pack_id,
                            **asset.metadata.get("candidate_metadata", {}),
                        },
                    )
                )
            runs.append(
                RunRecord(
                    run_id=run_id,
                    job_id=record.job_id,
                    status="generated",
                    generation_result_id=record.generation_result.planning_result_id,
                    candidate_ids=[candidate.candidate_id for candidate in candidates],
                    metadata={"run_type": "generation"},
                )
            )

        if record.selected_result is not None:
            selection_id = stable_id(
                "selection",
                record.job_id,
                ",".join(record.selected_result.selected_candidate_ids),
                ",".join(record.selected_result.selected_asset_ids),
            )
            selections.append(
                CandidateSelectionRecord(
                    selection_id=selection_id,
                    job_id=record.job_id,
                    selected_candidate_ids=list(record.selected_result.selected_candidate_ids),
                    selected_asset_ids=list(record.selected_result.selected_asset_ids),
                    memory_update_applied=record.selected_result.memory_update_applied,
                    metadata={"asset_pack_id": record.selected_result.asset_pack_id},
                )
            )

        if result is not None and result.asset_pack is not None:
            exports.append(
                ExportRecord(
                    export_id=stable_id("export", record.job_id, result.asset_pack.asset_pack_id),
                    job_id=record.job_id,
                    target="asset_pack",
                    asset_ids=[asset.asset_id for asset in result.asset_pack.assets],
                    status="ready",
                    metadata={"asset_pack_id": result.asset_pack.asset_pack_id},
                )
            )

        job = JobRecord(
            job_id=record.job_id,
            scenario_id=scenario_id,
            status=record.status.value,
            user_input=record.request.user_input,
            brand_id=record.request.effective_brand_id,
            run_ids=[run.run_id for run in runs],
            selection_ids=[selection.selection_id for selection in selections],
            export_ids=[export.export_id for export in exports],
            metadata={
                "has_planning_result": record.planning_result is not None,
                "has_generation_result": record.generation_result is not None,
                "blocked_before_planning": result is None and record.status == ProductJobStatusValue.BLOCKED,
            },
        )
        return JobLifecycleRecord(
            job=job,
            runs=runs,
            candidates=candidates,
            selections=selections,
            exports=exports,
            metadata={
                "source": "V3ProductApiService",
                "record_shape": "storage_ready_in_memory",
            },
        )

    def _lifecycle_summary(self, record: ProductJobRecord) -> dict[str, Any]:
        lifecycle = record.lifecycle or self._build_lifecycle(record)
        return {
            "job_id": lifecycle.job.job_id,
            "run_count": len(lifecycle.runs),
            "candidate_count": len(lifecycle.candidates),
            "selection_count": len(lifecycle.selections),
            "revision_count": len(lifecycle.revisions),
            "export_count": len(lifecycle.exports),
            "run_ids": list(lifecycle.job.run_ids),
            "selection_ids": list(lifecycle.job.selection_ids),
            "export_ids": list(lifecycle.job.export_ids),
        }

    def _capability_run_summary(self, capability_run: CapabilityRunResult | None) -> dict[str, Any]:
        if capability_run is None:
            return {"enabled": False, "module_ids": [], "warnings": []}
        return {
            "enabled": True,
            "status": capability_run.status.value,
            "module_ids": [result.module_id for result in capability_run.results],
            "result_statuses": {result.module_id: result.status.value for result in capability_run.results},
            "warning_count": len(capability_run.warnings),
            "visual_cluster": self._visual_cluster_from_results({result.module_id: result for result in capability_run.results}),
            "required_failures": list(capability_run.required_failures),
        }

    def _ecommerce_summary(self, record: ProductJobRecord) -> EcommerceCapabilitySummary | None:
        scenario_id = record.scenario_resolution.manifest.scenario_id if record.scenario_resolution else None
        if scenario_id != "ecommerce":
            return None
        pack_output = self._ecommerce_pack_output(record)
        warnings = self._ecommerce_public_warnings(record, pack_output)
        return EcommerceCapabilitySummary(
            enabled=True,
            scenario_id="ecommerce",
            selected_mode_id=record.scenario_resolution.selected_mode_id if record.scenario_resolution else None,
            selected_preset_id=record.scenario_resolution.selected_preset_id if record.scenario_resolution else None,
            platform=pack_output.marketplace_profile.platform,
            market=pack_output.marketplace_profile.market,
            product_truth={
                "product_category": pack_output.product_truth.product_category,
                "visible_attributes": list(pack_output.product_truth.visible_attributes),
                "immutable_attributes": list(pack_output.product_truth.immutable_attributes),
                "allowed_scene_changes": list(pack_output.product_truth.allowed_scene_changes),
                "forbidden_transformations": list(pack_output.product_truth.forbidden_transformations),
                "evidence_sources": list(pack_output.product_truth.evidence_sources),
                "review_obligations": list(pack_output.product_truth.review_obligations),
                "confidence": dict(pack_output.product_truth.confidence),
            },
            target_audience=list(pack_output.commerce_brief.target_audience),
            buying_motivations=list(pack_output.commerce_brief.buying_motivations),
            pain_points=list(pack_output.commerce_brief.pain_points),
            trust_drivers=list(pack_output.commerce_brief.trust_drivers),
            selling_points=list(pack_output.commerce_brief.differentiated_selling_points),
            keyword_intent_map=[dict(item) for item in pack_output.commerce_brief.keyword_intent_map],
            competitor_patterns=list(pack_output.commerce_brief.competitor_patterns),
            visual_strategy=list(pack_output.commerce_brief.visual_strategy),
            image_recipes=[recipe.model_dump(mode="json") for recipe in pack_output.recipes],
            critic_checks=[dict(item) for item in pack_output.critic.checks],
            export_package=pack_output.export_package.model_dump(mode="json"),
            closure_checks=self._ecommerce_closure_checks(pack_output),
            warnings=warnings,
            metadata={
                "product_language": True,
                "scenario_pack_logic": True,
                "imports_v1_v2_runtime": False,
                "external_research_used": False,
                "recipe_count": len(pack_output.recipes),
                "shared_capabilities": self._capability_run_summary(record.capability_run),
            },
        )

    def _ecommerce_export_manifest(self, record: ProductJobRecord, output: EcommercePackOutput) -> dict[str, Any]:
        return {
            "manifest_version": "v3_ecommerce_export_manifest_001",
            "job_id": record.job_id,
            "scenario_id": "ecommerce",
            "job_status": record.status.value,
            "package_id": output.export_package.package_id,
            "platform": output.marketplace_profile.platform,
            "market": output.marketplace_profile.market,
            "source_asset_ids": list(record.request.uploaded_asset_ids),
            "uploaded_assets": self._uploaded_asset_records(record.request.uploaded_asset_ids),
            "product_truth": output.product_truth.model_dump(mode="json"),
            "commerce_brief": output.commerce_brief.model_dump(mode="json"),
            "image_recipes": [recipe.model_dump(mode="json") for recipe in output.recipes],
            "generated_assets": self._generated_asset_records(record),
            "export_files": list(output.export_package.files),
            "review_checks": [dict(item) for item in output.critic.checks],
            "warnings": self._ecommerce_public_warnings(record, output),
            "metadata": {
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "export_package_review_status": output.export_package.review_status,
                "pixel_assets_required_before_download": output.export_package.metadata.get("pixel_assets_required_before_download", True),
                "imports_v1_v2_runtime": False,
            },
        }

    def _generic_export_manifest(self, record: ProductJobRecord, scenario_id: str | None) -> dict[str, Any]:
        return {
            "manifest_version": "v3_generic_export_manifest_001",
            "job_id": record.job_id,
            "scenario_id": scenario_id,
            "job_status": record.status.value,
            "source_asset_ids": list(record.request.uploaded_asset_ids),
            "uploaded_assets": self._uploaded_asset_records(record.request.uploaded_asset_ids),
            "generated_assets": self._generated_asset_records(record),
            "lifecycle": self._lifecycle_summary(record),
            "warnings": list(record.warnings),
            "metadata": {
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
            },
        }

    def _uploaded_asset_records(self, asset_ids: list[str]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for asset in self.asset_store.resolve_uploaded_assets(asset_ids):
            records.append(
                {
                    "asset_id": asset.asset_id,
                    "role": asset.role.value if asset.role else None,
                    "filename": asset.filename,
                    "mime_type": asset.mime_type,
                    "content_url": asset.uri,
                    "file_path": asset.file_path,
                    "upload_status": asset.metadata.get("upload_status") or asset.metadata.get("asset_lookup_status"),
                    "stored": bool(asset.file_path),
                }
            )
        return records

    def _generated_asset_records(self, record: ProductJobRecord) -> list[dict[str, Any]]:
        result = record.generation_result
        if result is None:
            return []
        records: list[dict[str, Any]] = []
        for asset in result.asset_pack.assets:
            candidate_metadata = asset.metadata.get("candidate_metadata", {})
            output_id = candidate_metadata.get("output_id")
            if not output_id:
                continue
            records.append(
                {
                    "asset_id": asset.asset_id,
                    "asset_type": asset.asset_type.value,
                    "platform": asset.platform.value,
                    "aspect_ratio": asset.aspect_ratio,
                    "purpose": asset.purpose,
                    "selected_candidate_id": asset.metadata.get("selected_candidate_id"),
                    "output_id": output_id,
                    "provider": candidate_metadata.get("actual_provider") or asset.metadata.get("selected_candidate_provider"),
                    "model": candidate_metadata.get("actual_model"),
                    "file_path": asset.file_path,
                    "download_url": candidate_metadata.get("download_url") or candidate_metadata.get("url"),
                    "preview_url": candidate_metadata.get("preview_url"),
                    "thumbnail_url": candidate_metadata.get("thumbnail_url"),
                    "width": candidate_metadata.get("width"),
                    "height": candidate_metadata.get("height"),
                    "mime_type": candidate_metadata.get("mime_type"),
                    "format": candidate_metadata.get("format"),
                    "review_status": "ready_for_manual_review",
                    "v3_owned_output": bool(candidate_metadata.get("v3_owned_output")),
                }
            )
        return records

    def _ecommerce_pack_output(self, record: ProductJobRecord) -> EcommercePackOutput:
        selection = record.request.scenario_selection
        parameters = dict(selection.parameters) if selection is not None else {}
        if record.scenario_resolution is not None:
            parameters.setdefault("mode", record.scenario_resolution.selected_mode_id)
            parameters.setdefault("preset", record.scenario_resolution.selected_preset_id)
        return self.ecommerce_planner.plan(
            user_input=record.request.user_input,
            product_profile=dict(record.request.product_profile),
            uploaded_asset_ids=list(record.request.uploaded_asset_ids),
            scenario_parameters=parameters,
            platform_profile=selection.platform_profile if selection is not None else None,
            job_key=record.job_id,
        )

    def _ecommerce_closure_checks(self, output: EcommercePackOutput) -> list[dict[str, Any]]:
        checks = [
            {
                "id": "product_truth",
                "label": "Product truth lock",
                "status": "done" if output.product_truth.immutable_attributes else "attention",
                "detail": f"{len(output.product_truth.immutable_attributes)} immutable product fact(s) will be checked.",
            },
            {
                "id": "commerce_brief",
                "label": "Audience and selling-point brief",
                "status": "done" if output.commerce_brief.differentiated_selling_points else "attention",
                "detail": f"{len(output.commerce_brief.differentiated_selling_points)} selling point(s) ranked for image planning.",
            },
            {
                "id": "marketplace_profile",
                "label": "Marketplace profile",
                "status": "done" if output.marketplace_profile.image_slots else "attention",
                "detail": f"{output.marketplace_profile.platform}/{output.marketplace_profile.market} profile is applied.",
            },
            {
                "id": "image_set_recipe",
                "label": "Image set recipe",
                "status": "done" if len(output.recipes) >= 5 else "attention",
                "detail": f"{len(output.recipes)} image slot(s) planned with one business job each.",
            },
            {
                "id": "export_package",
                "label": "Export package",
                "status": "done" if output.export_package.files else "attention",
                "detail": f"{len(output.export_package.files)} export file record(s) prepared.",
            },
        ]
        return [*checks, *[dict(item) for item in output.critic.checks]]

    def _ecommerce_public_warnings(self, record: ProductJobRecord, output: EcommercePackOutput) -> list[str]:
        warnings = [*record.warnings, *output.warnings, *output.critic.warnings]
        if record.capability_run is not None:
            warnings.extend(warning.message for warning in record.capability_run.warnings)
        return self._public_warnings_from(warnings, scenario_id="ecommerce")

    def _general_creative_summary(self, record: ProductJobRecord) -> GeneralCreativeCapabilitySummary | None:
        scenario_id = record.scenario_resolution.manifest.scenario_id if record.scenario_resolution else None
        if scenario_id != "general_creative":
            return None
        capability_run = record.capability_run
        results = {result.module_id: result for result in capability_run.results} if capability_run else {}
        warnings = self._general_creative_public_warnings(record)
        return GeneralCreativeCapabilitySummary(
            enabled=bool(results),
            scenario_id="general_creative",
            selected_mode_id=record.scenario_resolution.selected_mode_id if record.scenario_resolution else None,
            selected_preset_id=record.scenario_resolution.selected_preset_id if record.scenario_resolution else None,
            user_controls=list(GENERAL_CREATIVE_PUBLIC_CONTROLS),
            reference_understanding=self._reference_understanding_summary(results),
            reference_bindings=self._reference_binding_summary(results),
            visual_grammar=self._visual_grammar_summary(results),
            information_integrity=self._information_integrity_summary(results),
            review_hints=self._review_hint_summary(results),
            history_continuation=self._history_continuation_summary(record, results),
            closure_checks=self._general_creative_closure_checks(record, results, warnings),
            warnings=warnings,
            metadata={
                "prompt_language": "neutral_subject",
                "policy_boundary": "general_creative_neutral",
                "specialized_pack_logic": False,
                "internal_module_count": len(results),
            },
        )

    def _reference_understanding_summary(self, results: dict[str, Any]) -> list[str]:
        result = results.get("asset_role_analyzer")
        analyses = result.facts.get("asset_analyses", []) if result else []
        summaries: list[str] = []
        for analysis in analyses[:6]:
            role = ASSET_ROLE_PUBLIC_LABELS.get(str(analysis.get("role")), "reference image")
            asset_id = analysis.get("asset_id") or "reference"
            composition = analysis.get("composition") if isinstance(analysis.get("composition"), dict) else {}
            orientation = composition.get("orientation")
            detail = f"{asset_id} is treated as a {role}"
            if orientation:
                detail = f"{detail} with {orientation} composition"
            if analysis.get("stored") is False:
                detail = f"{detail}; local pixels were not available for deeper inspection"
            summaries.append(detail)
        return summaries

    def _reference_binding_summary(self, results: dict[str, Any]) -> list[str]:
        cluster = self._visual_cluster_from_results(results)
        binding_profile = cluster.get("reference_binding_profile") if isinstance(cluster, dict) else {}
        if isinstance(binding_profile, dict) and binding_profile:
            summaries: list[str] = []
            reference_count = int(binding_profile.get("reference_count") or 0)
            if reference_count:
                summaries.append(f"{reference_count} active visual reference(s) are organized for this project")
            hard_count = len(binding_profile.get("hard_reference_ids", []) or [])
            soft_count = len(binding_profile.get("soft_reference_ids", []) or [])
            if hard_count:
                summaries.append(f"{hard_count} identity-critical reference(s) require careful preservation")
            if soft_count:
                summaries.append(f"{soft_count} style or mood reference(s) guide the visual direction")
            summaries.extend(str(item) for item in (binding_profile.get("usage_rules") or [])[:3])
            if summaries:
                return summaries
        result = results.get("asset_binding_planner")
        plan = result.facts.get("asset_binding_plan", {}) if result else {}
        bindings = plan.get("bindings", []) if isinstance(plan, dict) else []
        summaries: list[str] = []
        for binding in bindings[:6]:
            role = ASSET_ROLE_PUBLIC_LABELS.get(str(binding.get("role")), "reference image")
            strength = str(binding.get("constraint_strength") or "soft")
            placement = str(binding.get("placement_intent") or "soft reference")
            summaries.append(f"{binding.get('asset_id') or 'Reference'} guides {placement} as a {strength} {role}")
        return summaries

    def _visual_grammar_summary(self, results: dict[str, Any]) -> list[str]:
        cluster = self._visual_cluster_from_results(results)
        profile = cluster.get("profile") if isinstance(cluster, dict) else {}
        snapshot = cluster.get("project_snapshot") if isinstance(cluster, dict) else {}
        guard = cluster.get("consistency_guard") if isinstance(cluster, dict) else {}
        if isinstance(profile, dict) and profile:
            summaries: list[str] = []
            style_signals = profile.get("style_signals") if isinstance(profile.get("style_signals"), list) else []
            lighting = profile.get("lighting_notes") if isinstance(profile.get("lighting_notes"), list) else []
            composition = profile.get("composition_rules") if isinstance(profile.get("composition_rules"), list) else []
            continuity = snapshot.get("continuity_strength") if isinstance(snapshot, dict) else None
            if continuity and continuity != "weak":
                summaries.append(f"Continue the confirmed project direction with {continuity} consistency")
            if style_signals:
                summaries.append("Keep style cues: " + ", ".join(str(item) for item in style_signals[:3]))
            if lighting:
                summaries.append("Keep lighting cues: " + ", ".join(str(item) for item in lighting[:3]))
            if composition:
                summaries.append("Use composition cues: " + ", ".join(str(item) for item in composition[:3]))
            keep_rules = guard.get("keep_rules") if isinstance(guard, dict) and isinstance(guard.get("keep_rules"), list) else []
            if keep_rules and not summaries:
                summaries.append("Keep confirmed direction: " + ", ".join(str(item) for item in keep_rules[:3]))
            if summaries:
                return summaries
        grammar_result = results.get("visual_grammar_lock")
        grammar = grammar_result.facts.get("visual_grammar_lock", {}) if grammar_result else {}
        if not grammar:
            return []
        summaries: list[str] = []
        case_title = grammar.get("primary_case_title")
        lock_strength = str(grammar.get("lock_strength") or "medium").replace("_", " ")
        if case_title:
            summaries.append(f"Use the layout rhythm of {case_title} with {lock_strength} guidance")
        elif grammar.get("reference_binding_count"):
            summaries.append(f"Use uploaded references for layout and style grammar with {lock_strength} guidance")
        visual_signals = grammar.get("visual_signal_brief") if isinstance(grammar.get("visual_signal_brief"), list) else []
        if visual_signals:
            summaries.append("Keep visual cues: " + ", ".join(str(item) for item in visual_signals[:3]))
        return summaries

    def _information_integrity_summary(self, results: dict[str, Any]) -> list[str]:
        integrity_result = results.get("information_integrity_lock")
        integrity = integrity_result.facts.get("information_integrity", {}) if integrity_result else {}
        if not integrity:
            return []
        summaries: list[str] = []
        required_text = integrity.get("required_text") if isinstance(integrity.get("required_text"), list) else []
        facts = integrity.get("must_preserve_facts") if isinstance(integrity.get("must_preserve_facts"), list) else []
        unsupported_claims = integrity.get("unsupported_claims") if isinstance(integrity.get("unsupported_claims"), list) else []
        if required_text:
            summaries.append("Keep exact visible text: " + ", ".join(str(item) for item in required_text[:3]))
        if facts:
            summaries.append("Review these supplied facts for preservation: " + ", ".join(str(item) for item in facts[:3]))
        if unsupported_claims:
            summaries.append("Do not visually assert unsupported claims without evidence: " + ", ".join(str(item) for item in unsupported_claims[:3]))
        return summaries

    def _review_hint_summary(self, results: dict[str, Any]) -> list[str]:
        cluster = self._visual_cluster_from_results(results)
        quality = cluster.get("quality_review") if isinstance(cluster, dict) else {}
        if isinstance(quality, dict) and quality:
            checklist = quality.get("checklist") if isinstance(quality.get("checklist"), list) else []
            warnings = quality.get("warning_notes") if isinstance(quality.get("warning_notes"), list) else []
            summaries = [str(item) for item in checklist[:4]]
            summaries.extend(str(item) for item in warnings[:3])
            if summaries:
                return summaries
        review_result = results.get("output_review")
        review = review_result.facts.get("output_review", {}) if review_result else {}
        if not review:
            return []
        issues = review.get("issues") if isinstance(review.get("issues"), list) else []
        summaries = [str(issue.get("message") or issue.get("code")) for issue in issues if isinstance(issue, dict)]
        check_count = review.get("evaluation_check_count")
        if check_count:
            summaries.append(f"{check_count} review obligation(s) should be checked before final export")
        return summaries

    def _history_continuation_summary(self, record: ProductJobRecord, results: dict[str, Any]) -> list[str]:
        history_result = results.get("history_reference")
        history = history_result.facts.get("history_reference", {}) if history_result else {}
        summaries: list[str] = []
        cluster = self._visual_cluster_from_results(results)
        snapshot = cluster.get("project_snapshot") if isinstance(cluster, dict) else {}
        guard = cluster.get("consistency_guard") if isinstance(cluster, dict) else {}
        if isinstance(snapshot, dict) and snapshot.get("continuity_strength") in {"medium", "strong"}:
            summaries.append(f"Continue project visual consistency: {snapshot.get('continuity_strength')}")
        avoid_rules = guard.get("avoid_rules") if isinstance(guard, dict) and isinstance(guard.get("avoid_rules"), list) else []
        if avoid_rules:
            summaries.append("Avoid project rejected directions: " + ", ".join(str(item) for item in avoid_rules[:3]))
        requested_brand_id = record.request.continue_style_from_brand_id or record.request.brand_id
        if requested_brand_id:
            summaries.append(f"Continue style from brand memory: {requested_brand_id}")
        visual_tone = history.get("visual_tone") if isinstance(history.get("visual_tone"), list) else []
        rejected = history.get("rejected_style_tags") if isinstance(history.get("rejected_style_tags"), list) else []
        reference_asset_count = history.get("reference_asset_count") if isinstance(history, dict) else 0
        if visual_tone:
            summaries.append("Use brand tone cues: " + ", ".join(str(item) for item in visual_tone[:4]))
        if rejected:
            summaries.append("Avoid previous rejected directions: " + ", ".join(str(item) for item in rejected[:3]))
        if reference_asset_count:
            summaries.append(f"{reference_asset_count} brand reference asset(s) are available for style continuity")
        return summaries

    def _general_creative_closure_checks(
        self,
        record: ProductJobRecord,
        results: dict[str, Any],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        has_assets = bool(record.request.uploaded_asset_ids)
        has_product_profile = bool(record.request.product_profile)
        has_history = bool(record.request.continue_style_from_brand_id or record.request.brand_id)
        visual_cluster_result = results.get("visual_capability_cluster")
        return [
            self._closure_check(
                "reference_understanding",
                "Reference understanding",
                results.get("asset_role_analyzer"),
                applicable=has_assets,
                not_applicable_detail="No uploaded references were supplied.",
            ),
            self._closure_check(
                "reference_binding",
                "Reference binding choices",
                results.get("asset_binding_planner"),
                applicable=has_assets,
                not_applicable_detail="No reference binding was needed.",
            ),
            self._closure_check(
                "visual_grammar",
                "Visual grammar preservation",
                visual_cluster_result or results.get("visual_grammar_lock"),
                applicable=bool(visual_cluster_result or results.get("case_library_retriever") or has_assets),
                not_applicable_detail="No selected visual grammar reference was needed.",
            ),
            self._closure_check(
                "information_integrity",
                "Text and fact preservation",
                results.get("information_integrity_lock"),
                applicable=has_product_profile,
                not_applicable_detail="No exact text, logo, or required details were supplied.",
            ),
            self._closure_check(
                "output_review",
                "Output review hints",
                results.get("output_review"),
                applicable=bool(results.get("output_review")),
                not_applicable_detail="No optional output review module was requested.",
            ),
            self._closure_check(
                "history_continuation",
                "History continuation",
                visual_cluster_result or results.get("history_reference"),
                applicable=bool(has_history or visual_cluster_result),
                not_applicable_detail="No brand history continuation was requested.",
            ),
            {
                "id": "public_warnings",
                "label": "User-visible warnings",
                "status": "attention" if warnings else "done",
                "detail": f"{len(warnings)} warning(s) need review." if warnings else "No user-visible warnings.",
            },
        ]

    def _visual_cluster_from_results(self, results: dict[str, Any]) -> dict[str, Any]:
        result = results.get("visual_capability_cluster")
        if result is None:
            return {}
        facts = getattr(result, "facts", {}) or {}
        cluster = facts.get("visual_capability_cluster") if isinstance(facts, dict) else {}
        return dict(cluster) if isinstance(cluster, dict) else {}

    def _closure_check(
        self,
        check_id: str,
        label: str,
        result: Any,
        *,
        applicable: bool,
        not_applicable_detail: str,
    ) -> dict[str, Any]:
        if not applicable:
            return {"id": check_id, "label": label, "status": "not_applicable", "detail": not_applicable_detail}
        if result is None:
            return {"id": check_id, "label": label, "status": "pending", "detail": "This check has not run yet."}
        status = result.status.value
        if status == "warning":
            public_status = "attention"
        elif status in {"success", "skipped"}:
            public_status = "done" if status == "success" else "not_applicable"
        else:
            public_status = "attention"
        detail = f"{label} completed." if public_status == "done" else f"{label} needs review."
        if status == "skipped":
            detail = not_applicable_detail
        return {"id": check_id, "label": label, "status": public_status, "detail": detail}

    def _general_creative_public_warnings(self, record: ProductJobRecord) -> list[str]:
        warnings = list(record.warnings)
        if record.capability_run is not None:
            warnings.extend(warning.message for warning in record.capability_run.warnings)
            for result in record.capability_run.results:
                warnings.extend(warning.message for warning in result.warnings)
        return self._public_warnings_from(warnings, scenario_id="general_creative")

    def _public_warnings_from(self, warnings: list[Any], *, scenario_id: str) -> list[str]:
        public: list[str] = []
        for item in warnings:
            text = self._public_warning_text(str(item))
            if not text or self._is_internal_warning_text(text, scenario_id=scenario_id):
                continue
            public.append(text)
        return list(dict.fromkeys(public))

    def _is_internal_warning_text(self, value: str, *, scenario_id: str) -> bool:
        text = str(value or "").strip().lower()
        if not text:
            return True
        if any(marker in text for marker in _PUBLIC_WARNING_INTERNAL_MARKERS):
            return True
        if scenario_id == "general_creative" and "marketplace" in text:
            return True
        return not any(marker in text for marker in _PUBLIC_WARNING_USER_ACTION_MARKERS)

    def _public_warning_text(self, value: str) -> str:
        if ": " in value:
            prefix, message = value.split(": ", 1)
            if "_" in prefix or prefix.endswith("error"):
                return message.strip()
        return value.strip()

    def _runtime_request_payload(self, request: CreateCreativeJobRequest) -> dict[str, Any]:
        return {
            "user_input": request.user_input,
            "optional_brand_id": request.effective_brand_id,
            "scenario_selection": request.scenario_selection,
            "uploaded_asset_ids": list(request.uploaded_asset_ids),
            "uploaded_assets": self.asset_store.resolve_uploaded_assets(list(request.uploaded_asset_ids)),
            "product_profile": dict(request.product_profile),
            "metadata": dict(request.metadata),
        }

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
            return request
        return GenerateJobRequest.model_validate(request)

    def _coerce_select_request(self, request: SelectResultRequest | dict[str, Any]) -> SelectResultRequest:
        if isinstance(request, SelectResultRequest):
            return request
        return SelectResultRequest.model_validate(request)

    def _coerce_create_brand_request(self, request: CreateBrandRequest | dict[str, Any]) -> CreateBrandRequest:
        if isinstance(request, CreateBrandRequest):
            return request
        return CreateBrandRequest.model_validate(request)


V3ProductApi = V3ProductApiService


def create_default_product_api() -> V3ProductApiService:
    return V3ProductApiService()
