"""Framework-neutral V3 product API service.

Route handlers can wrap this service later. The service deliberately exposes
product concepts such as jobs, asset series, candidates, selected result, and
balance estimate instead of image-model controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from uuid import uuid4

from ..app_shell.navigation import get_navigation_entry
from ..app_shell.routes import API_NAMESPACE, get_route_contracts
from ..brand_memory.profile_service import BrandProfileService
from ..creative_core.rules import RULE_VERSION, stable_id
from ..generation_router import GenerationRouter, ProductionImageGenerationProvider
from ..platform_adapters import V3BalanceAdapter, V3BalanceEstimate
from ..photography_profiles import (
    PhotographerProfileBinding,
    PhotographerProfileCatalog,
    PhotographerProfileSelectionError,
    default_photographer_profile_catalog,
)
from ..scenario_packs.ecommerce import EcommercePackOutput, EcommerceScenarioPackPlanner
from ..scenario_packs import ScenarioPackResolution
from ..scenario_runtime import ScenarioRuntime
from ..shared_capabilities import CapabilityRunResult
from ..shared_capabilities.apparel_construction import APPAREL_CONSTRUCTION_REVIEW_ISSUES
from ..shared_capabilities.visual_cluster import (
    HumanPhotorealismLayer,
    ModeAwareRoleDirector,
    OutputQualityReviewMerger,
    VisionOutputInspector,
    reference_channel_retry_patch,
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


_PRODUCT_JOB_ID_PATTERN = re.compile(r"^job_[A-Za-z0-9_-]{1,128}$")


class PersistentProductJobStore(InMemoryProductJobStore):
    """Durable V3 Job records for Project Mode and restart-safe delivery.

    Generated image files were already durable, but the planning, frozen
    Central Brain binding, review evidence, retry history, continuation
    lineage, and terminal state were previously held only in the process.
    Restoring from an output PNG alone cannot safely recreate those contracts.
    This store persists the typed V3 record atomically while retaining the
    in-memory store as the deterministic default for isolated unit tests.
    """

    schema_version = "v3_product_job_record_v1"

    def __init__(self, storage_root: str | Path | None = None) -> None:
        super().__init__()
        self.storage_root = Path(storage_root) if storage_root else _default_product_job_storage_root()

    def save(self, record: ProductJobRecord) -> ProductJobRecord:
        saved = super().save(record)
        self._write_record(saved)
        return saved

    def get(self, job_id: str) -> ProductJobRecord | None:
        cached = super().get(job_id)
        if cached is not None:
            return cached
        restored = self._read_record(job_id)
        if restored is not None:
            self._records[restored.job_id] = restored
        return restored

    def list_recent(self, limit: int = 20) -> list[ProductJobRecord]:
        self._load_all_records()
        return super().list_recent(limit)

    def delete_many(self, job_ids: list[str]) -> int:
        deleted = super().delete_many(job_ids)
        for job_id in list(dict.fromkeys(str(item or "").strip() for item in job_ids)):
            if not _valid_product_job_id(job_id):
                continue
            path = self._record_path(job_id)
            if path.exists():
                path.unlink()
                deleted += 1
        return deleted

    def _load_all_records(self) -> None:
        if not self.storage_root.exists():
            return
        for path in self.storage_root.glob("job_*.json"):
            restored = self._read_record(path.stem)
            if restored is not None:
                self._records[restored.job_id] = restored

    def _read_record(self, job_id: str) -> ProductJobRecord | None:
        if not _valid_product_job_id(job_id):
            return None
        path = self._record_path(job_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("schema_version") != self.schema_version:
            return None
        try:
            return ProductJobRecord(
                request=CreateCreativeJobRequest.model_validate(payload["request"]),
                status=ProductJobStatusValue(payload["status"]),
                job_id_value=str(payload["job_id"]),
                planning_result=(
                    PlanningResult.model_validate(payload["planning_result"])
                    if isinstance(payload.get("planning_result"), dict)
                    else None
                ),
                generation_result=(
                    PlanningResult.model_validate(payload["generation_result"])
                    if isinstance(payload.get("generation_result"), dict)
                    else None
                ),
                scenario_resolution=(
                    ScenarioPackResolution.model_validate(payload["scenario_resolution"])
                    if isinstance(payload.get("scenario_resolution"), dict)
                    else None
                ),
                capability_run=(
                    CapabilityRunResult.model_validate(payload["capability_run"])
                    if isinstance(payload.get("capability_run"), dict)
                    else None
                ),
                selected_result=(
                    SelectedResult.model_validate(payload["selected_result"])
                    if isinstance(payload.get("selected_result"), dict)
                    else None
                ),
                lifecycle=(
                    JobLifecycleRecord.model_validate(payload["lifecycle"])
                    if isinstance(payload.get("lifecycle"), dict)
                    else None
                ),
                balance_estimate=dict(payload.get("balance_estimate") or {}),
                warnings=[str(item) for item in payload.get("warnings") or []],
                created_at=str(payload.get("created_at") or _utc_now_iso()),
                updated_at=str(payload.get("updated_at") or _utc_now_iso()),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _write_record(self, record: ProductJobRecord) -> None:
        if not _valid_product_job_id(record.job_id):
            raise ValueError("refusing to persist an invalid V3 job id")
        path = self._record_path(record.job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.schema_version,
            "job_id": record.job_id,
            "request": record.request.model_dump(mode="json"),
            "status": record.status.value,
            "planning_result": _model_json(record.planning_result),
            "generation_result": _model_json(record.generation_result),
            "scenario_resolution": _model_json(record.scenario_resolution),
            "capability_run": _model_json(record.capability_run),
            "selected_result": _model_json(record.selected_result),
            "lifecycle": _model_json(record.lifecycle),
            "balance_estimate": dict(record.balance_estimate),
            "warnings": list(record.warnings),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _record_path(self, job_id: str) -> Path:
        return self.storage_root / f"{job_id}.json"


def _model_json(value: Any) -> dict[str, Any] | None:
    return value.model_dump(mode="json") if value is not None else None


def _valid_product_job_id(job_id: str) -> bool:
    return bool(_PRODUCT_JOB_ID_PATTERN.match(str(job_id or "")))


def _default_product_job_storage_root() -> Path:
    configured = os.getenv("ALCHEMY_V3_JOB_DIR") or os.getenv("MEDIA_STORAGE_ROOT")
    if configured:
        return Path(configured) / "v3_jobs"
    return Path(__file__).resolve().parents[3] / ".media_storage" / "v3_jobs"


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
        photographer_profile_catalog: PhotographerProfileCatalog | None = None,
        photographer_profile_region_resolver: Callable[[], str | None] | None = None,
    ) -> None:
        self.brand_profile_service = brand_profile_service or BrandProfileService()
        self.balance_adapter = balance_adapter or V3BalanceAdapter()
        self.job_store = job_store or InMemoryProductJobStore()
        self.ecommerce_planner = ecommerce_planner or EcommerceScenarioPackPlanner()
        self.asset_store = asset_store or V3UploadedAssetStore()
        self.output_store = output_store or V3GeneratedOutputStore()
        operator_catalog = self._default_photography_operator_catalog() if scenario_runtime is None else None
        self.photographer_profile_catalog = (
            photographer_profile_catalog
            or (operator_catalog.shared_catalog() if operator_catalog is not None else default_photographer_profile_catalog())
        )
        self.scenario_runtime = scenario_runtime or self._default_scenario_runtime(operator_catalog)
        self.output_resolver = output_resolver or GeneratedOutputResolver(self.output_store)
        self.vision_inspector = vision_inspector or VisionOutputInspector()
        self.review_merger = review_merger or OutputQualityReviewMerger()
        self.mode_role_director = mode_role_director or ModeAwareRoleDirector()
        self.photographer_profile_region_resolver = photographer_profile_region_resolver or (lambda: None)

    def _default_scenario_runtime(self, operator_catalog=None) -> ScenarioRuntime:
        """Compose the default runtime from one reviewed Photography catalog source."""

        generation_router = GenerationRouter(
            production_provider=ProductionImageGenerationProvider(output_store=self.output_store),
        )
        if operator_catalog is None:
            return ScenarioRuntime(
                brand_profile_service=self.brand_profile_service,
                generation_router=generation_router,
            )
        from ..scenario_packs.photography import PhotographyScenarioPackPlanner
        from ..scenario_runtime.specialized_planning import PhotographyScenarioPlanningAdapter

        adapter = PhotographyScenarioPlanningAdapter(
            planner=PhotographyScenarioPackPlanner(profile_catalog=operator_catalog, named_profiles_enabled=True)
        )
        return ScenarioRuntime(
            brand_profile_service=self.brand_profile_service,
            generation_router=generation_router,
            specialized_planning_adapters=[adapter],
        )

    def _default_photography_operator_catalog(self):
        """Return an operator catalog only while the deployment gate is open."""

        from ..scenario_packs.photography import default_photography_operator_catalog, photography_production_enabled

        return default_photography_operator_catalog() if photography_production_enabled() else None

    def create_creative_job(self, request: CreateCreativeJobRequest | dict[str, Any]) -> ProductJobStatus:
        return self._create_creative_job(request)

    def create_trusted_photography_continuation_job(
        self,
        request: CreateCreativeJobRequest | dict[str, Any],
    ) -> ProductJobStatus:
        """Internal Project Mode seam for a server-validated role child.

        This method is deliberately not exposed by the public Product API.
        It is the sole path allowed to reuse the parent's immutable profile
        binding and specialized frozen plan for append-only Photography role
        continuation.
        """

        return self.create_trusted_capability_continuation_job(
            request,
            trusted_photography_continuation=True,
        )

    def create_trusted_capability_continuation_job(
        self,
        request: CreateCreativeJobRequest | dict[str, Any],
        *,
        trusted_photography_continuation: bool = False,
    ) -> ProductJobStatus:
        """Internal-only continuation seam for a server-validated frozen plan.

        Project Mode is responsible for append-only lineage.  This service
        verifies that the plan comes from its persisted parent job (or from
        its one recorded amendment) before Scenario Runtime may reuse it.
        """

        return self._create_creative_job(
            request,
            trusted_photography_continuation=trusted_photography_continuation,
            trusted_capability_plan_reuse=True,
        )

    def _create_creative_job(
        self,
        request: CreateCreativeJobRequest | dict[str, Any],
        *,
        trusted_photography_continuation: bool = False,
        trusted_capability_plan_reuse: bool = False,
    ) -> ProductJobStatus:
        create_request = self._coerce_create_job_request(request)
        self._assert_runtime_metadata_server_owned(
            create_request,
            trusted_capability_plan_reuse=trusted_capability_plan_reuse,
        )
        self._bind_server_job_instance_id(create_request)
        if trusted_capability_plan_reuse:
            self._validate_and_bind_trusted_capability_plan_reuse(create_request)
        self._resolve_and_pin_photographer_profile(
            create_request,
            trusted_photography_continuation=trusted_photography_continuation,
        )
        self._prepare_ecommerce_creative_context(create_request)
        runtime_result = self.scenario_runtime.plan_job(
            self._runtime_request_payload(
                create_request,
                trusted_capability_plan_reuse=trusted_capability_plan_reuse,
            )
        )
        self._record_ecommerce_runtime_provenance(create_request, runtime_result, stage="planning")
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
                create_request.metadata.get("v3_job_instance_id"),
            )
        )
        activation_metadata = {
            key: runtime_result.metadata[key]
            for key in (
                "visual_task_profile",
                "capability_activation_intent",
                "capability_activation_plan",
                "capability_activation_plan_id",
                "capability_catalog_version",
                "capability_activation_mode",
                "normalized_v3_job_intent",
                "normalized_v3_job_intent_id",
                "template_deliverable_plan",
                "template_deliverable_plan_id",
                "resolved_constraint_ledger",
                "resolved_constraint_ledger_id",
                "capability_execution_envelope",
                "capability_execution_envelope_id",
                "remote_creative_brain_outcome",
                "specialized_scenario_plan",
                "specialized_scenario_plan_summary",
                "specialized_execution_summary",
            )
            if key in runtime_result.metadata
        }
        if activation_metadata:
            create_request.metadata = {**dict(create_request.metadata), **activation_metadata}
        self._bind_capability_plan_provenance(create_request, job_id)
        self._bind_frozen_remote_creative_brain(create_request, runtime_result)
        self._bind_internal_copy_render_plan(create_request)
        self._seed_ecommerce_slot_root_lineage(create_request, job_id)
        self._seed_photography_role_root_lineage(create_request, job_id)
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

    def get_job_record(self, job_id: str) -> ProductJobRecord | None:
        """Internal Project Mode lookup; no new public low-level API is exposed."""

        return self.job_store.get(job_id)

    def get_photographer_profiles(self) -> dict[str, Any]:
        """Return the public, read-only profile catalog for the Photography workspace."""

        return self.photographer_profile_catalog.public_catalog(region=self._photographer_profile_region())

    def photographer_profile_binding_for_job(self, job_id: str) -> PhotographerProfileBinding | None:
        """Internal Project Mode lookup of the immutable server-owned job binding."""

        record = self.job_store.get(job_id)
        if record is None:
            return None
        binding = dict(record.request.metadata or {}).get("photographer_profile_binding")
        if not isinstance(binding, dict):
            return None
        return PhotographerProfileBinding.model_validate(binding)

    def preview_capability_activation(
        self,
        request: CreateCreativeJobRequest | dict[str, Any],
    ) -> dict[str, Any]:
        """Plan a possible evidence amendment without creating a job or provider call."""

        create_request = self._coerce_create_job_request(request)
        self._assert_runtime_metadata_server_owned(
            create_request,
            trusted_capability_plan_reuse=False,
        )
        self._resolve_and_pin_photographer_profile(create_request)
        runtime_result = self.scenario_runtime.plan_job(self._runtime_request_payload(create_request))
        plan = runtime_result.metadata.get("capability_activation_plan")
        if not isinstance(plan, dict) or not plan.get("plan_id"):
            raise ValueError("capability activation amendment could not be planned")
        return {
            key: runtime_result.metadata[key]
            for key in (
                "capability_activation_plan",
                "capability_activation_plan_id",
                "visual_task_profile",
                "capability_activation_intent",
                "capability_catalog_version",
                "capability_activation_mode",
            )
            if key in runtime_result.metadata
        }

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
        self._expire_background_generation_if_due(record)
        return self._partial_output_recovery_status(record) or self._status_from_record(record)

    def mark_job_generating(
        self,
        job_id: str,
        *,
        background_attempt_id: str | None = None,
        background_timeout_seconds: float | None = None,
    ) -> ProductJobStatus:
        """Persist the public pre-render state before a background worker starts.

        A generated output file is not a user delivery while shared review and
        bounded retry are still running.  Persisting this state before the
        worker is submitted prevents project polling from treating a partially
        written output store as a completed job.
        """

        record = self.job_store.get(job_id)
        if record is None:
            return self._not_found_status(job_id)
        if record.status in {ProductJobStatusValue.PLANNED, ProductJobStatusValue.BLOCKED, ProductJobStatusValue.FAILED}:
            record.status = ProductJobStatusValue.GENERATING
            if background_attempt_id:
                watchdog = {
                    "background_attempt_id": str(background_attempt_id),
                    "enabled": background_timeout_seconds is not None,
                    "started_at": _utc_now_iso(),
                }
                if background_timeout_seconds is not None:
                    watchdog["timeout_seconds"] = max(1, int(round(float(background_timeout_seconds))))
                record.request.metadata = {
                    **dict(record.request.metadata),
                    "background_generation_attempt_id": str(background_attempt_id),
                    "background_generation_watchdog": watchdog,
                }
            record.lifecycle = self._build_lifecycle(record)
            self.job_store.save(record)
        return self._status_from_record(record)

    def _expire_background_generation_if_due(self, record: ProductJobRecord) -> None:
        """Polling is a durable fallback when a host loses a timer thread."""

        watchdog = dict(record.request.metadata).get("background_generation_watchdog")
        if not isinstance(watchdog, dict) or not watchdog.get("enabled"):
            return
        if record.status not in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}:
            return
        attempt_id = str(watchdog.get("background_attempt_id") or "")
        timeout_seconds = watchdog.get("timeout_seconds")
        started_at = str(watchdog.get("started_at") or "")
        if not attempt_id or not started_at:
            return
        try:
            deadline = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            elapsed_seconds = (datetime.now(timezone.utc) - deadline).total_seconds()
            timeout_value = float(timeout_seconds)
        except (TypeError, ValueError):
            return
        if elapsed_seconds < max(1.0, timeout_value):
            return
        self.mark_job_generation_timed_out(
            record.job_id,
            background_attempt_id=attempt_id,
            timeout_seconds=timeout_value,
        )

    def mark_job_generation_timed_out(
        self,
        job_id: str,
        *,
        background_attempt_id: str,
        timeout_seconds: float,
    ) -> ProductJobStatus:
        """Close a background run that outlived the gateway-owned deadline.

        A later return from the non-cancellable worker must not turn this
        terminal timeout into a delivery. The attempt ID also protects a
        deliberate later rerun from a stale watchdog callback.
        """

        record = self.job_store.get(job_id)
        if record is None:
            return self._not_found_status(job_id)
        active_attempt_id = str(dict(record.request.metadata).get("background_generation_attempt_id") or "")
        if (
            active_attempt_id != str(background_attempt_id)
            or record.status not in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}
        ):
            return self._status_from_record(record)
        rounded_timeout = max(1, int(round(float(timeout_seconds))))
        provider_failure_retry = {
            "executed_count": 0,
            "max_attempts": 1,
            "fresh_upstream_requests": 1,
            "final_status": "failed",
            "final_classification": "gateway_managed_lifecycle_timeout",
            "attempts": [
                {
                    "attempt": 1,
                    "status": "failed",
                    "classification": "gateway_managed_lifecycle_timeout",
                    "error_type": "TimeoutError",
                    "message": f"V3 background generation exceeded {rounded_timeout}s without a terminal gateway response.",
                    "retryable": False,
                }
            ],
        }
        record.status = ProductJobStatusValue.BLOCKED
        record.request.metadata = {
            **dict(record.request.metadata),
            "provider_failure_retry": provider_failure_retry,
            "provider_failure_retry_exhausted": True,
            "generation_lifecycle_timeout": {
                "background_attempt_id": active_attempt_id,
                "timeout_seconds": rounded_timeout,
                "status": "terminal_timeout",
                "owner": "v3_background_generation_watchdog",
            },
        }
        record.warnings.append(
            f"V3 real image generation failed (gateway_managed_lifecycle_timeout): "
            f"no terminal gateway response after {rounded_timeout}s."
        )
        record.lifecycle = self._build_lifecycle(record)
        self.job_store.save(record)
        return self._status_from_record(record)

    def mark_job_generation_worker_failed(
        self,
        job_id: str,
        *,
        background_attempt_id: str,
        failure_code: str,
    ) -> ProductJobStatus:
        """Close a background worker exception without fabricating a Provider failure.

        The asynchronous HTTP wrapper marks a Job as ``generating`` before it
        submits work.  Payload validation or another local worker exception
        can therefore occur before ``generate_asset_series`` gets far enough
        to persist its own terminal status.  Leaving that Job pending until a
        long gateway watchdog expires is misleading and permits no useful
        operator diagnosis.  Record a safe, non-Provider terminal reason
        instead; raw exception text stays in server logs.
        """

        record = self.job_store.get(job_id)
        if record is None:
            return self._not_found_status(job_id)
        active_attempt_id = str(dict(record.request.metadata).get("background_generation_attempt_id") or "")
        if (
            active_attempt_id != str(background_attempt_id)
            or record.status not in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}
        ):
            return self._status_from_record(record)
        normalized_code = (
            "background_generation_request_invalid"
            if str(failure_code).strip() == "background_generation_request_invalid"
            else "background_generation_worker_error"
        )
        record.status = ProductJobStatusValue.BLOCKED
        record.request.metadata = {
            **dict(record.request.metadata),
            "generation_lifecycle_failure": {
                "background_attempt_id": active_attempt_id,
                "failure_code": normalized_code,
                "status": "terminal_failure",
                "owner": "v3_background_generation_worker",
            },
        }
        record.warnings.append(
            "V3 background generation ended before a terminal image result "
            f"({normalized_code}); no image request was replayed automatically."
        )
        record.lifecycle = self._build_lifecycle(record)
        self.job_store.save(record)
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
        self._assert_photographer_profile_binding_immutable(record, generate_request)
        worker_claim = bool(generate_request.metadata.pop("_v3_background_worker_claim", False))
        background_attempt_id = str(generate_request.metadata.pop("_v3_background_generation_attempt_id", "") or "")
        if worker_claim and not self._background_generation_attempt_is_current(record, background_attempt_id):
            return self._status_from_record(record)
        if record.status == ProductJobStatusValue.FINALIZING:
            return self._status_from_record(record)
        if record.status == ProductJobStatusValue.GENERATING and not worker_claim:
            return self._status_from_record(record)
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
        record.status = ProductJobStatusValue.GENERATING
        record.lifecycle = self._build_lifecycle(record)
        self.job_store.save(record)
        try:
            generation_runtime_result = self.scenario_runtime.generate_job(
                self._runtime_request_payload(record.request),
                mock_profile=QUALITY_MODE_TO_MOCK_PROFILE[generate_request.quality_mode],
                apply_memory_update=False,
                provider_strategy=provider_strategy,
                quality_mode=generate_request.quality_mode,
            )
        except Exception as exc:
            if not self._background_generation_attempt_is_current(record, background_attempt_id):
                return self._status_from_record(record)
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
        self._record_ecommerce_runtime_provenance(record.request, generation_runtime_result, stage="generation")
        if not self._background_generation_attempt_is_current(record, background_attempt_id):
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
        if provider_strategy == ProviderStrategy.MOCK_GENERATION:
            generation_result = self._materialize_mock_output_records(record, generation_result)
        # Outputs may already be in the local store at this point.  They remain
        # process artifacts until review, optional text delivery, and bounded
        # visual retry decide the final delivery set.
        record.generation_result = generation_result
        record.scenario_resolution = generation_runtime_result.scenario_resolution
        record.capability_run = generation_runtime_result.capability_run
        record.status = ProductJobStatusValue.FINALIZING
        record.lifecycle = self._build_lifecycle(record)
        self.job_store.save(record)
        generation_result = self._attach_post_generation_review(record, generation_result, generate_request)
        if not self._background_generation_attempt_is_current(record, background_attempt_id):
            return self._status_from_record(record)
        self._clear_superseded_pre_generation_review_warning(record, generation_result)
        generation_result = self._apply_text_pixel_delivery(record, generation_result)
        if not self._background_generation_attempt_is_current(record, background_attempt_id):
            return self._status_from_record(record)
        generation_result = self._run_visual_auto_retries(
            record=record,
            generate_request=generate_request,
            provider_strategy=provider_strategy,
            generation_result=generation_result,
        )
        generation_result = self._apply_reviewed_delivery_preference(generation_result)
        if not self._background_generation_attempt_is_current(record, background_attempt_id):
            return self._status_from_record(record)
        record.generation_result = generation_result
        record.scenario_resolution = generation_runtime_result.scenario_resolution
        record.capability_run = generation_runtime_result.capability_run
        specialized_execution = self._specialized_role_execution_terminal_summary(record, generation_result)
        if specialized_execution is not None:
            record.request.metadata = {
                **dict(record.request.metadata),
                "specialized_execution_summary": specialized_execution,
                # The internal summary keeps append-only execution diagnostics.
                # The separate projection is deliberately safe for Job/Project
                # clients: it contains certification truth, never raw provider
                # errors, candidates, assets, or other implementation details.
                "review_certification": specialized_execution["review_certification"],
            }
            if specialized_execution["status"] != "complete":
                missing = ", ".join(specialized_execution["missing_role_keys"])
                noncertifying = ", ".join(specialized_execution.get("noncertifying_role_keys", []))
                record.status = ProductJobStatusValue.BLOCKED
                if noncertifying:
                    record.warnings.append(
                        "Specialized role delivery lacks certifying real-pixel review; final project delivery is withheld"
                        f": roles {noncertifying}."
                    )
                else:
                    record.warnings.append(
                        "Specialized role execution is incomplete; final project delivery is withheld"
                        + (f": missing {missing}." if missing else ".")
                    )
                record.balance_estimate = self._estimate_for_result(generation_result)
                record.lifecycle = self._build_lifecycle(record)
                self.job_store.save(record)
                return self._status_from_record(record)
        record.status = ProductJobStatusValue.GENERATED
        record.balance_estimate = self._estimate_for_result(generation_result)
        record.lifecycle = self._build_lifecycle(record)
        self.job_store.save(record)
        return self._status_from_record(record)

    def _specialized_role_execution_terminal_summary(
        self,
        record: ProductJobRecord,
        generation_result: PlanningResult,
    ) -> dict[str, Any] | None:
        """Make a frozen multi-role execution truthful at the Product boundary.

        A specialized Template may declare several roles, but it never owns a
        provider, reviewer, retry loop, or result selector.  The shared
        executor therefore records every role here and fails closed for the
        ordinary project delivery surface when a role did not reach a winner.
        """

        specialized = dict(record.request.metadata or {}).get("specialized_scenario_plan")
        execution = specialized.get("execution_plan") if isinstance(specialized, dict) else None
        execution_metadata = execution.get("metadata") if isinstance(execution, dict) else None
        if not isinstance(execution_metadata, dict) or not execution_metadata.get("require_independent_role_terminal_states"):
            return None
        recipes = execution.get("role_recipes") if isinstance(execution, dict) else None
        expected_role_keys = [
            str(item.get("role_key") or "").strip()
            for item in recipes
            if isinstance(item, dict) and str(item.get("role_key") or "").strip()
        ] if isinstance(recipes, list) else []
        if not expected_role_keys:
            return None

        raw_execution = generation_result.metadata.get("specialized_role_execution")
        raw_roles = raw_execution.get("roles") if isinstance(raw_execution, dict) else []
        by_role = {
            str(item.get("role_key") or "").strip(): dict(item)
            for item in raw_roles
            if isinstance(item, dict) and str(item.get("role_key") or "").strip()
        } if isinstance(raw_roles, list) else {}

        review_package = generation_result.metadata.get("post_generation_review_package")
        inspections = review_package.get("inspections") if isinstance(review_package, dict) else []
        inspections_by_candidate = {
            str(item.get("candidate_id") or "").strip(): dict(item)
            for item in inspections
            if isinstance(item, dict) and str(item.get("candidate_id") or "").strip()
        } if isinstance(inspections, list) else {}
        requires_real_pixel_review = bool(execution_metadata.get("requires_real_pixel_review"))

        roles: list[dict[str, Any]] = []
        missing_role_keys: list[str] = []
        noncertifying_role_keys: list[str] = []
        for role_key in expected_role_keys:
            item = dict(by_role.get(role_key) or {})
            status = str(item.get("status") or "missing").strip().lower()
            if status != "generated":
                missing_role_keys.append(role_key)
            inspection = inspections_by_candidate.get(str(item.get("candidate_id") or "").strip())
            review_mode = str(inspection.get("mode") or "").strip().lower() if inspection else ""
            review_status = str(inspection.get("status") or "").strip().lower() if inspection else ""
            verification_state = str(inspection.get("verification_state") or "").strip().lower() if inspection else ""
            real_pixel_certified = (
                not requires_real_pixel_review
                or (review_mode in {"vision_model", "hybrid"} and review_status in {"pass", "warning"})
            )
            if status == "generated" and not real_pixel_certified:
                noncertifying_role_keys.append(role_key)
            certification_state = (
                "certified"
                if status == "generated" and real_pixel_certified
                else "manual_confirmation_required"
                if (
                    status == "generated"
                    and review_mode in {"vision_model", "hybrid"}
                    and review_status == "manual_review"
                )
                else "blocked"
            )
            roles.append(
                {
                    "role_key": role_key,
                    "status": status,
                    "asset_id": item.get("asset_id"),
                    "candidate_id": item.get("candidate_id"),
                    "error_type": item.get("error_type"),
                    "error_message": item.get("error_message"),
                    "review_mode": review_mode or None,
                    "review_status": review_status or None,
                    "verification_state": verification_state or None,
                    "real_pixel_certified": real_pixel_certified,
                    "certification_state": certification_state,
                }
            )
        status = "incomplete" if missing_role_keys else "non_certifying" if noncertifying_role_keys else "complete"
        noncertifying_roles = [item for item in roles if item["certification_state"] != "certified"]
        certification_state = (
            "certified"
            if not missing_role_keys and not noncertifying_roles
            else "manual_confirmation_required"
            if (
                not missing_role_keys
                and noncertifying_roles
                and all(item["certification_state"] == "manual_confirmation_required" for item in noncertifying_roles)
            )
            else "blocked"
        )
        review_certification = {
            "schema_version": "v3_review_certification_v1",
            "scenario_id": "photography",
            "state": certification_state,
            "automatic_delivery_certified": certification_state == "certified",
            "manual_confirmation_required": certification_state == "manual_confirmation_required",
            "final_delivery_withheld": bool(missing_role_keys or noncertifying_role_keys),
            "roles": [
                {
                    "role_key": item["role_key"],
                    "state": item["certification_state"],
                    "review_mode": item["review_mode"],
                    "review_status": item["review_status"],
                    "verification_state": item["verification_state"],
                }
                for item in roles
            ],
        }
        return {
            "requested_image_count": len(expected_role_keys),
            "role_keys": expected_role_keys,
            "shared_execution_only": True,
            "status": status,
            "roles": roles,
            "missing_role_keys": missing_role_keys,
            "noncertifying_role_keys": noncertifying_role_keys,
            "final_delivery_withheld": bool(missing_role_keys or noncertifying_role_keys),
            "append_only_history_preserved": True,
            "review_certification": review_certification,
        }

    def _materialize_mock_output_records(
        self,
        record: ProductJobRecord,
        generation_result: PlanningResult,
    ) -> PlanningResult:
        """Give mock-only contract runs the same immutable output shape as production.

        This is intentionally a local test fixture, marked in output metadata.
        It prevents Project Mode tests from relying on an asset-only reference,
        while preserving the production rule that visual delivery comes from
        provider pixels.
        """

        updated_assets: list[PackagedAsset] = []
        changed = False
        for asset in generation_result.asset_pack.assets:
            metadata = dict(asset.metadata or {})
            candidate_metadata = dict(metadata.get("candidate_metadata") or {})
            candidate_id = str(metadata.get("selected_candidate_id") or "").strip()
            existing_output_id = str(candidate_metadata.get("output_id") or metadata.get("output_id") or "").strip()
            existing = self.output_store.get_output(existing_output_id) if existing_output_id else None
            if existing is None and candidate_id:
                existing = self.output_store.save_base64_output(
                    job_id=record.job_id,
                    candidate_id=candidate_id,
                    asset_id=asset.asset_id,
                    provider="v3_mock_contract_fixture",
                    model="deterministic-2px",
                    encoded_image=_MOCK_OUTPUT_PNG_BASE64,
                    mime_type="image/png",
                    output_format="png",
                    metadata={
                        "mock_contract_fixture": True,
                        "not_a_provider_delivery": True,
                        "project_id": record.request.metadata.get("project_id"),
                        "template_id": record.request.metadata.get("template_id"),
                        "requested_image_count": len(generation_result.asset_pack.assets),
                    },
                )
            if existing is None:
                updated_assets.append(asset)
                continue
            changed = True
            candidate_metadata.update(
                {
                    "output_id": existing.output_id,
                    "url": existing.download_url,
                    "download_url": existing.download_url,
                    "preview_url": existing.preview_url,
                    "thumbnail_url": existing.thumbnail_url,
                    "mime_type": existing.mime_type,
                    "format": existing.output_format,
                    "width": existing.width,
                    "height": existing.height,
                    "mock_contract_fixture": True,
                }
            )
            metadata.update(
                {
                    "candidate_metadata": candidate_metadata,
                    "output_id": existing.output_id,
                    "mock_contract_fixture": True,
                }
            )
            updated_assets.append(
                asset.model_copy(
                    update={
                        "file_path": existing.file_path,
                        "uri": existing.thumbnail_url,
                        "metadata": metadata,
                    }
                )
            )
        if not changed:
            return generation_result
        asset_pack = generation_result.asset_pack.model_copy(
            update={
                "assets": updated_assets,
                "metadata": {**dict(generation_result.asset_pack.metadata), "mock_output_records_materialized": True},
            }
        )
        return generation_result.model_copy(
            update={
                "asset_pack": asset_pack,
                "metadata": {**dict(generation_result.metadata), "mock_output_records_materialized": True},
            }
        )

    def generate_job(
        self,
        job_id: str,
        request: GenerateJobRequest | dict[str, Any] | None = None,
    ) -> ProductJobStatus:
        return self.generate_asset_series(job_id, request)

    def _background_generation_attempt_is_current(self, record: ProductJobRecord, background_attempt_id: str) -> bool:
        if not background_attempt_id:
            return True
        active_attempt_id = str(dict(record.request.metadata).get("background_generation_attempt_id") or "")
        return (
            active_attempt_id == background_attempt_id
            and record.status in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}
        )

    def _provider_strategy_for_generate(
        self,
        record: ProductJobRecord,
        generate_request: GenerateJobRequest,
    ) -> ProviderStrategy:
        # A project/job can freeze its real-provider requirement when it is
        # created, while the later generate request normally contains only
        # per-attempt controls.  Choosing a strategy from the latter alone
        # silently downgraded an already-required real image job to the mock
        # fixture.  Persisted job intent is therefore a hard baseline; a
        # per-attempt request may require real generation too, but cannot
        # relax a persisted real-provider requirement.
        frozen_metadata = dict(record.request.metadata)
        attempt_metadata = dict(generate_request.metadata)
        metadata = {**frozen_metadata, **attempt_metadata}
        require_real_images = bool(
            frozen_metadata.get("require_real_images")
            or frozen_metadata.get("real_image_generation")
            or attempt_metadata.get("require_real_images")
            or attempt_metadata.get("real_image_generation")
        )
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
        execution_envelope = generation_result.metadata.get("capability_execution_envelope")
        if isinstance(execution_envelope, dict):
            review_metadata["capability_execution_envelope"] = dict(execution_envelope)
        enforced = (
            isinstance(execution_envelope, dict)
            and str((execution_envelope.get("activation_plan") or {}).get("activation_mode") or "").lower() == "enforced"
        )
        if enforced:
            ledger = execution_envelope.get("resolved_constraint_ledger")
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
            result_cluster = (
                dict(projection.get("capability_projection") or {})
                if isinstance(projection, dict)
                else {}
            )
            reference_policy = result_cluster.get("resolved_reference_policy_package")
            if isinstance(reference_policy, dict) and reference_policy:
                review_metadata["resolved_reference_policy_package"] = reference_policy
            review_metadata["resolved_constraint_ledger"] = dict(ledger) if isinstance(ledger, dict) else {}
        else:
            result_cluster = generation_result.metadata.get("visual_cluster")
            if not isinstance(result_cluster, dict):
                shared = generation_result.metadata.get("shared_capabilities")
                result_cluster = shared.get("visual_cluster") if isinstance(shared, dict) else {}
            if isinstance(result_cluster, dict):
                review_metadata["visual_cluster"] = dict(result_cluster)
                composed = result_cluster.get("composed_visual_contribution")
                if isinstance(composed, dict):
                    review_metadata["composed_visual_contribution"] = dict(composed)
                reference_policy = result_cluster.get("resolved_reference_policy_package")
                if isinstance(reference_policy, dict) and reference_policy:
                    review_metadata.setdefault("resolved_reference_policy_package", reference_policy)
        if self._reference_conditioned_real_review_required(
            review_metadata,
            quality_mode=generate_request.quality_mode,
        ):
            review_metadata["enable_real_vision_inspection"] = True
        resolutions = self.output_resolver.resolve_result(generation_result, project_id=project_id)
        frozen_output_review_contracts = self._frozen_output_review_contracts_by_asset_id(
            generation_result,
            review_metadata,
        )
        inspections = [
            self.vision_inspector.inspect(
                resolution,
                metadata={
                    **review_metadata,
                    "frozen_output_review_contract": self._frozen_output_review_contract(
                        resolution,
                        frozen_output_review_contracts,
                    ),
                },
            )
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
        if enforced:
            # Keep executor results readable for job diagnostics and legacy
            # history, but replace the mutable visual-cluster surface used by
            # downstream review/retry with the frozen ledger projection.
            shared_capabilities["source"] = "resolved_constraint_ledger"
        visual_cluster = (
            dict(result_cluster or {})
            if enforced
            else dict(shared_capabilities.get("visual_cluster") or metadata.get("visual_cluster") or {})
        )
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

    @staticmethod
    def _frozen_output_review_contracts_by_asset_id(
        generation_result: PlanningResult,
        review_metadata: dict[str, Any],
    ) -> dict[str, dict[str, str]]:
        """Bind each generated asset to its frozen deliverable before review.

        E-Commerce deliberately emits no shared ``mode_role_recipe``.  The
        immutable mapping is instead the series asset priority selected before
        generation and the matching frozen ledger ``output_index``.  Candidate
        and provider response metadata are never used to decide which Brain
        evidence contract a pixel reviewer receives.
        """

        envelope = review_metadata.get("capability_execution_envelope")
        ledger = envelope.get("resolved_constraint_ledger") if isinstance(envelope, dict) else {}
        projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
        deliverables = projection.get("deliverables") if isinstance(projection, dict) else []
        if not isinstance(deliverables, list):
            return {}

        deliverable_by_index: dict[int, str] = {}
        for item in deliverables:
            if not isinstance(item, dict):
                continue
            try:
                index = int(item.get("output_index"))
            except (TypeError, ValueError):
                continue
            deliverable_id = str(item.get("deliverable_id") or "").strip()
            if index > 0 and deliverable_id and index not in deliverable_by_index:
                deliverable_by_index[index] = deliverable_id

        contracts: dict[str, dict[str, str]] = {}
        for asset in generation_result.series_plan.assets:
            asset_id = str(asset.asset_id or "").strip()
            try:
                output_index = int(asset.priority)
            except (TypeError, ValueError):
                continue
            deliverable_id = deliverable_by_index.get(output_index)
            if asset_id and deliverable_id:
                contracts[asset_id] = {
                    "source": "resolved_constraint_ledger",
                    "deliverable_id": deliverable_id,
                }
        return contracts

    @staticmethod
    def _frozen_output_review_contract(
        resolution: Any,
        contracts_by_asset_id: dict[str, dict[str, str]],
    ) -> dict[str, str]:
        """Return the pre-bound frozen contract for exactly this output."""

        asset_id = str(getattr(resolution, "asset_id", "") or "").strip()
        contract = contracts_by_asset_id.get(asset_id)
        return dict(contract) if isinstance(contract, dict) else {}

    def _clear_superseded_pre_generation_review_warning(
        self,
        record: ProductJobRecord,
        generation_result: PlanningResult,
    ) -> None:
        """Drop the planning-only warning after a real final-pixel review runs.

        The shared planning capability correctly records that it had no pixels
        at planning time. Once the post-generation path has actually run a
        vision-model or hybrid inspection, keeping that warning on the public
        Job status is stale and misleading. It remains for local-only or
        metadata-only inspection, where it still accurately signals a missing
        live review route.
        """
        package = generation_result.metadata.get("post_generation_review_package")
        if not isinstance(package, dict):
            return
        reports = package.get("quality_review_reports")
        if not isinstance(reports, list):
            return
        has_live_pixel_review = any(
            isinstance(report, dict)
            and str(report.get("review_mode") or report.get("mode") or "").strip().lower()
            in {"vision_model", "hybrid"}
            for report in reports
        )
        if not has_live_pixel_review:
            return
        record.warnings = [
            warning
            for warning in record.warnings
            if "output_review_metadata_only" not in str(warning).lower()
            and "output review ran without live image inspection" not in str(warning).lower()
        ]

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

    def _apply_text_pixel_delivery(
        self,
        record: ProductJobRecord,
        generation_result: PlanningResult,
    ) -> PlanningResult:
        """Run the shared post-generation stage only for an internal frozen plan.

        The envelope is intentionally not a public request control.  A future
        template maps approved copy intent into it before the activation plan is
        frozen; this shared path has no E-Commerce vocabulary or provider call.
        """

        envelope = record.request.metadata.get("text_pixel_delivery_internal")
        raw_plan = envelope.get("copy_render_plan") if isinstance(envelope, dict) else None
        raw_plans = envelope.get("copy_render_plans") if isinstance(envelope, dict) else None
        if not isinstance(raw_plan, dict) and not isinstance(raw_plans, list):
            return generation_result
        is_batch = isinstance(raw_plans, list)
        # Doc111 retires deterministic post-generation composition.  Keep a
        # structured historical result for callers that still submit a legacy
        # envelope, but never resolve fonts, rasterize text, or replace a
        # provider output.  New provider-native text requests are compiled
        # into the generation brief before this point.
        retired_delivery = {
            "status": "provider_native_required",
            "rendered": False,
            "review_passed": False,
            "issue_codes": ["deterministic_text_pixel_delivery_retired"],
            "user_visible_summary": ["Text must be generated and reviewed as part of the complete provider image; local overlay delivery is unavailable."],
            "metadata": {"append_only": True, "legacy_read_compatibility": True},
        }
        if is_batch:
            return self._with_text_pixel_delivery_metadata(
                generation_result,
                {
                    "text_pixel_delivery_batch": {
                        "schema_version": "v3_text_pixel_delivery_batch_v1",
                        "batch_id": stable_id("text_pixel_delivery_batch", "retired"),
                        "deliveries": [
                            {
                                "delivery_id": stable_id("text_pixel_delivery", "retired"),
                                **retired_delivery,
                            }
                        ],
                        "source_asset_ids_by_plan": {},
                        "metadata": {"append_only": True, "legacy_read_compatibility": True},
                    }
                },
            )
        return self._with_text_pixel_delivery_metadata(generation_result, {"text_pixel_delivery": retired_delivery})

    def _with_text_pixel_delivery_metadata(self, result: PlanningResult, delivery_metadata: dict[str, Any]) -> PlanningResult:
        asset_pack = result.asset_pack.model_copy(
            update={
                "manifest": {**dict(result.asset_pack.manifest), **delivery_metadata},
                "metadata": {**dict(result.asset_pack.metadata), **delivery_metadata},
            }
        )
        return result.model_copy(update={"asset_pack": asset_pack, "metadata": {**dict(result.metadata), **delivery_metadata}})

    def _run_visual_auto_retries(
        self,
        *,
        record: ProductJobRecord,
        generate_request: GenerateJobRequest,
        provider_strategy: ProviderStrategy,
        generation_result: PlanningResult,
    ) -> PlanningResult:
        max_attempts = self._visual_auto_retry_limit_for_record(record, generate_request)
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
                "max_visual_retry_attempts": max_attempts,
                **self._resolved_retry_metadata(merged_result, retry_patch),
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
            reviewed_retry_result = self._apply_text_pixel_delivery(record, reviewed_retry_result)
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
        if (
            not self._visual_retry_patch_has_content(retry_patch)
            and str(self._activation_plan_from_result(result).get("activation_mode") or "").lower() != "enforced"
        ):
            retry_patch = self._visual_retry_patch_from_issues(issue_codes)
        if not self._visual_retry_patch_has_content(retry_patch):
            return result, max_attempts
        retry_metadata = {
            **base_metadata,
            "visual_auto_retry_active": True,
            "visual_auto_retry_attempt": attempt_index,
            "retry_attempt": attempt_index,
            "visual_retry_reason_codes": issue_codes,
            "max_visual_retry_attempts": attempt_index,
            "identity_post_retry_closeout": True,
            **self._resolved_retry_metadata(result, retry_patch),
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

    def _identity_repair_strategy_from_result(self, result: PlanningResult) -> dict[str, Any]:
        plan = self._activation_plan_from_result(result)
        if str(plan.get("activation_mode") or "").lower() == "enforced":
            ledger = self._constraint_ledger_from_result(result)
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
            capability_projection = projection.get("capability_projection") if isinstance(projection, dict) else {}
            strategy = capability_projection.get("identity_repair_strategy_plan") if isinstance(capability_projection, dict) else None
            return dict(strategy) if isinstance(strategy, dict) and strategy.get("applies") else {}
        cluster = self._visual_cluster_metadata_from_result(result)
        plan = cluster.get("identity_repair_strategy_plan") if isinstance(cluster, dict) else None
        return dict(plan) if isinstance(plan, dict) and plan.get("applies") else {}

    def _identity_local_repair_metadata(
        self,
        result: PlanningResult,
        *,
        attempt_index: int,
        reason_codes: list[str],
        post_retry_closeout: bool = False,
    ) -> dict[str, Any]:
        plan = self._activation_plan_from_result(result)
        active = plan.get("dependency_order") or plan.get("active_capability_ids") or []
        if "nonhuman_subject_identity" in {str(item) for item in active if str(item).strip()}:
            return {}
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
        repair_strategy = self._identity_repair_strategy_from_result(result)
        if repair_strategy and not bool(repair_strategy.get("allow_face_local_repair")):
            return {}
        package = result.metadata.get("post_generation_review_package")
        inspections = package.get("inspections") if isinstance(package, dict) else []
        if post_retry_closeout and isinstance(package, dict):
            candidates = [item for item in inspections if isinstance(item, dict)] if isinstance(inspections, list) else []
            for attempt in package.get("review_attempts", []) if isinstance(package.get("review_attempts"), list) else []:
                if not isinstance(attempt, dict):
                    continue
                candidates.extend(item for item in attempt.get("inspections", []) if isinstance(item, dict))
            deduplicated: dict[str, dict[str, Any]] = {}
            for item in candidates:
                output_id = str(item.get("output_id") or "").strip()
                if output_id and output_id not in deduplicated:
                    deduplicated[output_id] = item
            inspections = sorted(
                deduplicated.values(),
                key=lambda item: self._safe_score(
                    ((item.get("evidence") or {}).get("identity_review_fusion") or {}).get("fused_identity_score")
                    if isinstance(item.get("evidence"), dict)
                    else None
                )
                or -1.0,
                reverse=True,
            )
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

    def _visual_auto_retry_limit_for_record(
        self,
        record: ProductJobRecord,
        generate_request: GenerateJobRequest,
    ) -> int:
        limit = self._visual_auto_retry_max_attempts(generate_request)
        return min(limit, 1) if self._record_has_active_capability(record, "nonhuman_subject_identity") else limit

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

        if not retry_patch and str(self._activation_plan_from_result(result).get("activation_mode") or "").lower() != "enforced":
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
            return self._activation_filtered_retry_signal(
                result,
                explicit_codes,
                self._metadata_retry_patch(request_metadata),
                "request_metadata",
            )

        enforced = str(self._activation_plan_from_result(result).get("activation_mode") or "").lower() == "enforced"
        result_metadata = dict(result.metadata or {})
        if enforced:
            review_package = result_metadata.get("post_generation_review_package")
            real_signal = self._real_review_signal_package_from_cluster(
                dict(review_package) if isinstance(review_package, dict) else {}
            )
            if real_signal:
                signal_codes, signal_patch = self._visual_retry_signal_from_real_review(
                    real_signal,
                    allow_legacy_patch=False,
                )
                if signal_codes:
                    return self._activation_filtered_retry_signal(
                        result,
                        signal_codes,
                        signal_patch,
                        "real_review_signal_package",
                    )
            return [], {}, "envelope_bound_review"

        text_deliveries: list[dict[str, Any]] = []
        single_delivery = result_metadata.get("text_pixel_delivery")
        if isinstance(single_delivery, dict):
            text_deliveries.append(single_delivery)
        batch_delivery = result_metadata.get("text_pixel_delivery_batch")
        if isinstance(batch_delivery, dict):
            text_deliveries.extend(item for item in batch_delivery.get("deliveries", []) if isinstance(item, dict))
        for text_delivery in text_deliveries:
            recovery = text_delivery.get("recovery")
            generation_retry = recovery.get("generation_retry") if isinstance(recovery, dict) else None
            if isinstance(generation_retry, dict) and bool(generation_retry.get("eligible")):
                return self._activation_filtered_retry_signal(
                    result,
                    self._dedupe_strings(generation_retry.get("reason_codes")),
                    dict(generation_retry.get("retry_patch") or {}),
                    "text_pixel_delivery",
                )

        cluster = self._visual_cluster_metadata_from_result(result)
        real_signal = self._real_review_signal_package_from_cluster(cluster)
        if real_signal:
            signal_codes, signal_patch = self._visual_retry_signal_from_real_review(real_signal)
            if signal_codes:
                return self._activation_filtered_retry_signal(
                    result,
                    signal_codes,
                    signal_patch,
                    "real_review_signal_package",
                )
        if self._visual_cluster_is_preflight_only(cluster):
            return [], {}, "preflight_only"
        decisions = cluster.get("auto_retry_decisions") if isinstance(cluster, dict) else None
        if not isinstance(decisions, list):
            return [], {}, "visual_cluster"
        for decision in decisions:
            if not isinstance(decision, dict) or not bool(decision.get("should_retry")):
                continue
            return self._activation_filtered_retry_signal(
                result,
                self._dedupe_strings(decision.get("reason_codes")),
                dict(decision.get("retry_patch") or {}),
                "visual_cluster",
            )
        return [], {}, "visual_cluster"

    def _activation_plan_from_result(self, result: PlanningResult) -> dict[str, Any]:
        creative_job = getattr(result, "creative_job", None)
        creative_job_metadata = getattr(creative_job, "metadata", {})
        for source in (getattr(result, "metadata", {}), creative_job_metadata):
            if not isinstance(source, dict):
                continue
            envelope = source.get("capability_execution_envelope")
            if isinstance(envelope, dict) and isinstance(envelope.get("activation_plan"), dict):
                return dict(envelope["activation_plan"])
            plan = source.get("capability_activation_plan")
            if isinstance(plan, dict):
                return dict(plan)
        cluster = self._visual_cluster_metadata_from_result(result)
        summary = cluster.get("capability_activation_plan_summary") if isinstance(cluster, dict) else None
        return dict(summary) if isinstance(summary, dict) else {}

    def _resolved_retry_metadata(self, result: PlanningResult, retry_patch: dict[str, Any]) -> dict[str, Any]:
        """Carry an active-ledger retry patch back through the shared runtime."""

        plan = self._activation_plan_from_result(result)
        if str(plan.get("activation_mode") or "").lower() != "enforced":
            return {"visual_retry_patch": dict(retry_patch)}
        plan_id = str(plan.get("plan_id") or "").strip()
        fingerprint = str(plan.get("fingerprint") or "").strip()
        if not plan_id or not fingerprint:
            return {}
        return {
            "resolved_retry_patch": dict(retry_patch),
            "resolved_retry_provenance": {
                "authority": "v3_product_api",
                "activation_plan_id": plan_id,
                "activation_plan_fingerprint": fingerprint,
            },
        }

    def _constraint_ledger_from_result(self, result: PlanningResult) -> dict[str, Any]:
        creative_job = getattr(result, "creative_job", None)
        creative_job_metadata = getattr(creative_job, "metadata", {})
        for source in (getattr(result, "metadata", {}), creative_job_metadata):
            if not isinstance(source, dict):
                continue
            envelope = source.get("capability_execution_envelope")
            ledger = envelope.get("resolved_constraint_ledger") if isinstance(envelope, dict) else None
            if isinstance(ledger, dict):
                return dict(ledger)
            ledger = source.get("resolved_constraint_ledger")
            if isinstance(ledger, dict):
                return dict(ledger)
        return {}

    def _record_has_active_capability(self, record: ProductJobRecord, capability_id: str) -> bool:
        plan = dict(record.request.metadata or {}).get("capability_activation_plan")
        if not isinstance(plan, dict):
            return False
        active = plan.get("dependency_order") or plan.get("active_capability_ids") or []
        return str(capability_id) in {str(item) for item in active if str(item).strip()}

    def _activation_filtered_retry_signal(
        self,
        result: PlanningResult,
        issue_codes: list[str],
        retry_patch: dict[str, Any],
        source: str,
    ) -> tuple[list[str], dict[str, Any], str]:
        plan = self._activation_plan_from_result(result)
        if str(plan.get("activation_mode") or "").lower() != "enforced":
            return self._dedupe_strings(issue_codes), retry_patch, source
        ledger = self._constraint_ledger_from_result(result)
        if not ledger:
            audit = result.metadata.setdefault("capability_activation_audit", {})
            audit["retry_blocked_reason"] = "resolved_constraint_ledger_missing"
            return [], {}, source
        active = {
            str(item)
            for item in (plan.get("dependency_order") or plan.get("active_capability_ids") or [])
            if str(item).strip()
        }
        retry_contracts = [
            dict(contract)
            for contract in ledger.get("retry_contracts", [])
            if isinstance(contract, dict)
            and (
                str(contract.get("capability_id") or "") in active
                or str(contract.get("capability_id") or "") == "template_deliverable_owner"
            )
        ]
        filtered: list[str] = []
        ignored: list[str] = []
        for raw_code in self._dedupe_strings(issue_codes):
            code = self._normalize_legacy_review_issue_code(raw_code)
            owner = self._review_issue_capability_owner(code)
            matching_contracts = [
                contract
                for contract in retry_contracts
                if str(contract.get("capability_id") or "") == owner
                or code in self._dedupe_strings(contract.get("issue_codes"))
            ]
            if owner is None and code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES:
                matching_contracts = [
                    contract
                    for contract in retry_contracts
                    if str(contract.get("capability_id") or "") == "universal_visual_quality"
                ]
            owner_is_frozen_template_contract = owner == "template_deliverable_owner" and any(
                str(contract.get("capability_id") or "") == "template_deliverable_owner"
                for contract in matching_contracts
            )
            if (owner is None or owner in active or owner_is_frozen_template_contract) and matching_contracts:
                filtered.append(code)
            else:
                ignored.append(code)
        if ignored:
            audit = result.metadata.setdefault("capability_activation_audit", {})
            audit["ignored_out_of_scope_issue_codes"] = self._dedupe_strings(
                [*audit.get("ignored_out_of_scope_issue_codes", []), *ignored]
            )
        if not filtered:
            return [], {}, source
        # Enforced retries use only templates published by active capability
        # contracts in the frozen ledger.  Review/request metadata may name an
        # issue, but cannot inject a prompt patch or revive a legacy mapper.
        resolved_patch = self._ledger_retry_patch(ledger, filtered)
        # Candidate/output targeting is review provenance, not prompt text.
        # Preserve it so append-only history explains which failed output the
        # bounded retry supersedes, while discarding every caller-supplied
        # prompt/reinforcement field.
        for key in ("target_candidate_ids", "target_output_ids", "issue_groups"):
            values = self._dedupe_strings(retry_patch.get(key)) if isinstance(retry_patch, dict) else []
            if values:
                resolved_patch[key] = values
        return filtered, resolved_patch, source

    def _ledger_retry_patch(self, ledger: dict[str, Any], issue_codes: list[str]) -> dict[str, Any]:
        contracts = [item for item in ledger.get("retry_contracts", []) if isinstance(item, dict)]
        patches: list[dict[str, Any]] = []
        for code in self._dedupe_strings(issue_codes):
            owner = self._review_issue_capability_owner(code)
            for contract in contracts:
                capability_id = str(contract.get("capability_id") or "")
                contract_codes = self._dedupe_strings(contract.get("issue_codes"))
                if capability_id != owner and code not in contract_codes:
                    if not (owner is None and code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES and capability_id == "universal_visual_quality"):
                        continue
                templates = contract.get("templates")
                if isinstance(templates, dict):
                    patches.append(dict(templates))
        template_evidence_patch = self._frozen_template_evidence_retry_patch(ledger, issue_codes)
        if template_evidence_patch:
            patches.append(template_evidence_patch)
        return self._merge_visual_retry_patches(patches)

    def _frozen_template_evidence_retry_patch(
        self,
        ledger: dict[str, Any],
        issue_codes: list[str],
    ) -> dict[str, Any]:
        """Carry only a prior frozen Brain evidence map into a bounded retry."""

        if "delivery_evidence_dimension_mismatch" not in set(self._dedupe_strings(issue_codes)):
            return {}
        projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
        deliverables = projection.get("deliverables") if isinstance(projection, dict) else []
        assignments: list[str] = []
        for item in (deliverables if isinstance(deliverables, list) else []):
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            dimensions = self._dedupe_strings(metadata.get("brain_evidence_dimensions"))
            if not dimensions:
                continue
            index = self._safe_int(item.get("output_index"), default=None)
            if index is None:
                continue
            assignments.append(f"output {index}: {', '.join(dimensions)}")
        if not assignments:
            return {}
        return {
            "prompt_additions": [
                "preserve this prior frozen template-owned evidence map on retry: " + "; ".join(assignments)
            ],
            "composition_repair": [
                "make each output visibly prove its assigned evidence dimension without changing the Brain-owned delivery intent"
            ],
        }

    def _review_issue_capability_owner(self, issue_code: str) -> str | None:
        code = str(issue_code or "").strip().lower()
        if not code:
            return None
        if "nonhuman_subject" in code or "nonhuman_reference" in code:
            return "nonhuman_subject_identity"
        if code == "delivery_evidence_dimension_mismatch":
            return "template_deliverable_owner"
        if code in {
            "flat_scene_lighting",
            "airbrushed_background_texture",
            "synthetic_material_response",
            "frozen_centered_pose",
        }:
            return "human_realism"
        if any(token in code for token in ("product", "packaging", "label", "logo_drift", "sku_")):
            return "product_identity"
        if any(
            token in code
            for token in ("scene_", "background_drift", "background_space", "landmark", "spatial_", "camera_mood")
        ):
            return "scene_continuity"
        if any(token in code for token in ("typography", "text_accuracy", "layout_", "crop_safety")):
            return "typography_layout"
        if "text_background_readability" in code:
            return "text_pixel_delivery"
        if any(
            token in code
            for token in (
                "role_",
                "suite_",
                "batch_duplication",
                "same_pose_repetition",
                "deliverable_intent",
                "delivery_set",
            )
        ):
            return "suite_direction"
        if any(
            token in code
            for token in (
                "identity_drift",
                "bone_structure",
                "face_shape",
                "cheek_jaw",
                "eye_shape_or_spacing_identity",
                "eyebrow_eye_relationship",
                "nose_mouth_relationship_identity",
                "lip_contour_identity",
                "age_impression_drift",
                "age_identity_drift",
                "styling_changed_face",
                "same_person",
            )
        ):
            return "portrait_identity"
        if any(
            token in code
            for token in (
                "ai_face",
                "plastic_skin",
                "skin_",
                "anatomy",
                "doll_like",
                "beauty_filter",
                "uncanny_eye",
                "body_proportion",
                "bad_hands",
                "face_artifact",
                "child_face",
                "child_model",
                "complexion",
                "unintended_skin",
                "realism_",
                "flat_scene_lighting",
                "airbrushed_background_texture",
                "synthetic_material_response",
                "frozen_centered_pose",
            )
        ):
            return "human_realism"
        return None

    @staticmethod
    def _normalize_legacy_review_issue_code(issue_code: str) -> str:
        """Read historical vertical aliases only at the Product API boundary."""

        aliases = {
            "ecommerce_slot_mismatch": "deliverable_intent_mismatch",
            "ecommerce_suite_role_mismatch": "delivery_set_role_mismatch",
        }
        code = str(issue_code or "").strip()
        return aliases.get(code, code)

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

    def _visual_retry_signal_from_real_review(
        self,
        package: dict[str, Any],
        *,
        allow_legacy_patch: bool = True,
    ) -> tuple[list[str], dict[str, Any]]:
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
        if allow_legacy_patch and not self._visual_retry_patch_has_content(retry_patch):
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
        return self._dedupe_strings(self._normalize_legacy_review_issue_code(value) for value in values)

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
            elif code in {
                "nonhuman_subject_identity_drift",
                "nonhuman_subject_marking_drift",
                "nonhuman_subject_proportion_drift",
                "nonhuman_reference_used_as_style",
            }:
                identity_reinforcement.extend(
                    [
                        "preserve the individual non-human subject's stable morphology, head geometry, body proportions, distinctive markings or pattern, and visible coat, feather, scale, or surface character from the typed reference",
                        "keep habitat, action, camera, lighting, color treatment, and finish owned by the current prompt; do not recreate the source frame as a style template",
                    ]
                )
                negative_additions.extend(
                    [
                        "generic replacement subject",
                        "changed stable markings or pattern",
                        "changed morphology or body proportions",
                        "copied source habitat or lighting",
                    ]
                )
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
                "source_wardrobe_overinherited",
                "source_lighting_overinherited",
                "source_color_grade_overinherited",
                "source_scene_overinherited",
                "source_camera_overinherited",
                "source_whole_style_overinherited",
                "reference_used_as_style_when_identity_only",
                "prompt_owned_channel_ignored",
                "selected_anchor_overrode_current_prompt",
                "structured_appearance_lock_misapplied",
            }:
                channel_patch = reference_channel_retry_patch([code])
                prompt_additions.extend(channel_patch["prompt_additions"])
                negative_additions.extend(channel_patch["negative_additions"])
                identity_reinforcement.extend(channel_patch["identity_reinforcement"])
                composition_repair.extend(channel_patch["composition_repair"])
            elif code in {
                "source_color_temperature_overinherited",
                "source_camera_mood_overinherited",
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
                "deliverable_intent_mismatch",
                "delivery_set_role_mismatch",
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
                        "wrong requested image role",
                        "requested delivery intent ignored",
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
        text_delivery = self._merge_text_pixel_delivery_chain(base_result, retry_result)
        text_delivery_metadata = self._text_pixel_delivery_metadata_updates(text_delivery)
        asset_pack = base_result.asset_pack.model_copy(
            update={
                "assets": [*base_result.asset_pack.assets, *retry_result.asset_pack.assets],
                "manifest": {
                    **dict(base_result.asset_pack.manifest),
                    **dict(review_updates.get("asset_pack_manifest") or {}),
                    "visual_auto_retry": self._visual_auto_retry_summary(records, max_attempts),
                    **text_delivery_metadata,
                },
                "metadata": {
                    **dict(base_result.asset_pack.metadata),
                    **dict(review_updates.get("asset_pack_metadata") or {}),
                    "visual_auto_retry": self._visual_auto_retry_summary(records, max_attempts),
                    **text_delivery_metadata,
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
                    **text_delivery_metadata,
                    "retry_generation_result_ids": self._dedupe_strings(
                        [
                            *self._string_list(base_result.metadata.get("retry_generation_result_ids")),
                            retry_result.planning_result_id,
                        ]
                    ),
                },
            }
        )

    def _merge_text_pixel_delivery_chain(
        self,
        base_result: PlanningResult,
        retry_result: PlanningResult,
    ) -> dict[str, Any]:
        """Keep deterministic composition/review records append-only across retries."""

        base_batch = base_result.metadata.get("text_pixel_delivery_batch") if isinstance(base_result.metadata, dict) else None
        retry_batch = retry_result.metadata.get("text_pixel_delivery_batch") if isinstance(retry_result.metadata, dict) else None
        if isinstance(base_batch, dict) or isinstance(retry_batch, dict):
            return self._merge_text_pixel_delivery_batches(
                dict(base_batch) if isinstance(base_batch, dict) else {},
                dict(retry_batch) if isinstance(retry_batch, dict) else {},
            )
        base = base_result.metadata.get("text_pixel_delivery") if isinstance(base_result.metadata, dict) else None
        retry = retry_result.metadata.get("text_pixel_delivery") if isinstance(retry_result.metadata, dict) else None
        if not isinstance(base, dict):
            return dict(retry) if isinstance(retry, dict) else {}
        if not isinstance(retry, dict):
            return dict(base)
        return self._merge_text_pixel_delivery_values(base, retry)

    def _merge_text_pixel_delivery_values(self, base: dict[str, Any], retry: dict[str, Any]) -> dict[str, Any]:
        """Select the reviewed delivery while retaining an append-only attempt chain."""
        base_passed = base.get("status") == "passed" and bool(base.get("current_output_id"))
        retry_passed = retry.get("status") == "passed" and bool(retry.get("current_output_id"))
        selected = retry if retry_passed or not base_passed else base
        attempts = [
            *[dict(item) for item in base.get("attempts", []) if isinstance(item, dict)],
            *[dict(item) for item in retry.get("attempts", []) if isinstance(item, dict)],
        ]
        prior_output_ids = self._dedupe_strings(
            [
                base.get("source_output_id"),
                base.get("current_output_id"),
                retry.get("source_output_id"),
                retry.get("current_output_id"),
            ]
        )
        return {
            **dict(selected),
            "attempts": attempts,
            "recovery": {
                **dict(selected.get("recovery") or {}),
                "append_only": True,
                "prior_output_ids": prior_output_ids,
                "retry_delivery_preserved_previous": base_passed and not retry_passed,
            },
            "metadata": {
                **dict(selected.get("metadata") or {}),
                "append_only": True,
                "merged_retry_delivery_history": True,
            },
        }

    def _merge_text_pixel_delivery_batches(self, base: dict[str, Any], retry: dict[str, Any]) -> dict[str, Any]:
        """Merge independently reviewed batch members without cross-asset replacement."""

        base_items = [dict(item) for item in base.get("deliveries", []) if isinstance(item, dict)]
        retry_items = [dict(item) for item in retry.get("deliveries", []) if isinstance(item, dict)]

        def item_key(item: dict[str, Any], index: int, prefix: str) -> str:
            return str(item.get("copy_render_plan_id") or item.get("delivery_id") or f"{prefix}-{index}")

        base_by_key = {item_key(item, index, "base"): item for index, item in enumerate(base_items)}
        retry_by_key = {item_key(item, index, "retry"): item for index, item in enumerate(retry_items)}
        ordered_keys = [item_key(item, index, "base") for index, item in enumerate(base_items)]
        ordered_keys.extend(key for key in (item_key(item, index, "retry") for index, item in enumerate(retry_items)) if key not in base_by_key)
        merged_deliveries: list[dict[str, Any]] = []
        for key in ordered_keys:
            base_item = base_by_key.get(key)
            retry_item = retry_by_key.get(key)
            if base_item is not None and retry_item is not None:
                merged_deliveries.append(self._merge_text_pixel_delivery_values(base_item, retry_item))
            elif retry_item is not None:
                merged_deliveries.append(dict(retry_item))
            elif base_item is not None:
                merged_deliveries.append(dict(base_item))
        return {
            "schema_version": "v3_text_pixel_delivery_batch_v1",
            "batch_id": str(retry.get("batch_id") or base.get("batch_id") or stable_id("text_pixel_delivery_batch", *ordered_keys)),
            "deliveries": merged_deliveries,
            "source_asset_ids_by_plan": {
                **dict(base.get("source_asset_ids_by_plan") or {}),
                **dict(retry.get("source_asset_ids_by_plan") or {}),
            },
            "metadata": {
                **dict(base.get("metadata") or {}),
                **dict(retry.get("metadata") or {}),
                "append_only": True,
                "merged_retry_delivery_history": True,
            },
        }

    def _text_pixel_delivery_metadata_updates(self, delivery: dict[str, Any]) -> dict[str, Any]:
        if not delivery:
            return {}
        if isinstance(delivery.get("deliveries"), list):
            return {"text_pixel_delivery_batch": delivery}
        return {"text_pixel_delivery": delivery}

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
            or issue_codes.intersection(DELIVERY_TEMPLATE_EVIDENCE_HARD_GATE_ISSUES)
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
        if issue_codes.intersection(DELIVERY_TEMPLATE_EVIDENCE_HARD_GATE_ISSUES):
            hard_gate_failures.append("template_delivery_evidence_not_respected")
        if status == "manual_review" and issue_codes.intersection(
            {"provider_error", "vision_provider_unavailable", "vision_provider_not_configured"}
        ):
            hard_gate_failures.append("review_unavailable")
        inspection_metadata = inspection.get("metadata") if isinstance(inspection.get("metadata"), dict) else {}
        if (
            str(inspection_metadata.get("scenario_id") or "").strip().lower() == "photography"
            and status == "manual_review"
            and issue_codes.intersection({"metadata_only_non_certifying", "hard_semantic_contract_unverified"})
        ):
            # P10/production Photography requires shared vision-model or
            # hybrid final-pixel inspection.  A record-only review remains in
            # append-only history but cannot become a delivery winner.
            hard_gate_failures.append("photography_real_pixel_review_required")

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
        if record.status in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}:
            selected = SelectedResult(metadata={"selection_status": "finalization_pending"})
            return SelectionResponse(
                job_id=job_id,
                status=record.status,
                selected_result=selected,
                job_status=self._status_from_record(record),
                warnings=["Creative job finalization is still in progress; its outputs cannot be selected yet."],
                metadata={
                    "source": "V3ProductApiService",
                    "rules_version": RULE_VERSION,
                    "selection_held": True,
                    "hold_reason": "finalization_pending",
                },
            )
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
        export_package = self._ecommerce_runtime_export_package(record, pack_output)
        manifest = self._ecommerce_export_manifest(record, pack_output, export_package)
        return V3ExportPackageResponse(
            job_id=record.job_id,
            status=record.status,
            api_namespace=API_NAMESPACE,
            scenario_id=scenario_id,
            package_id=str(export_package.get("package_id") or pack_output.export_package.package_id),
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
        delivery_settling = record.status in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}
        public_visual_retry = self._public_visual_auto_retry_summary(result.metadata.get("visual_auto_retry"))
        public_review = self._public_post_generation_review(result.metadata.get("post_generation_review_package"))
        public_warnings = list(record.warnings + asset_pack.manifest.get("warnings", []))
        if public_visual_retry.get("manual_confirmation_required"):
            public_warnings.append(
                "The image was generated, but the automatic refinement did not complete; manual confirmation is required."
            )
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
            asset_series=[] if delivery_settling else self._asset_series(result, record.status),
            candidates=[] if delivery_settling else self._candidate_summaries(result),
            style_continuation=self._style_continuation_summary(record, result),
            general_creative=self._general_creative_summary(record),
            ecommerce=self._ecommerce_summary(record),
            selected_result=record.selected_result,
            balance_estimate=dict(record.balance_estimate),
            routes=get_route_contracts(),
            warnings=list(dict.fromkeys(public_warnings)),
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
                "balance_adapter": self.balance_adapter.adapter_name,
                "selected_vertical_pack": result.metadata.get("selected_vertical_pack"),
                "scenario_id": result.metadata.get("scenario_id"),
                "shared_capabilities": self._public_metadata_projection(
                    result.metadata.get("shared_capabilities") or self._capability_run_summary(record.capability_run)
                ),
                "visual_auto_retry": public_visual_retry,
                "post_generation_review": public_review,
                "text_pixel_delivery": result.metadata.get("text_pixel_delivery", {}),
                "text_pixel_delivery_batch": result.metadata.get("text_pixel_delivery_batch", {}),
                "exposes_product_concepts_only": True,
                "lifecycle": self._lifecycle_summary(record),
                "delivery_settling": delivery_settling,
                "continuation_available": not delivery_settling,
                **self._workflow_artifacts_metadata(record, result),
                **self._project_mode_status_metadata(record),
                **self._ecommerce_runtime_provenance_status_metadata(record),
            },
        )

    @staticmethod
    def _public_visual_auto_retry_summary(value: Any) -> dict[str, Any]:
        """Project only user-actionable retry status to public Job surfaces.

        The durable record intentionally retains the full retry patch and raw
        failure provenance for operator audit. Browser/API consumers only need
        to know whether a bounded refinement ran, which safe issue categories
        remain, and whether a person must confirm the retained delivery.
        """

        summary = dict(value or {}) if isinstance(value, dict) else {}
        records = [dict(item) for item in summary.get("records", []) if isinstance(item, dict)]
        public_records = [
            {
                "attempt_index": int(item.get("attempt_index") or 0),
                "status": str(item.get("status") or "unknown"),
                "reason_codes": [str(code) for code in item.get("reason_codes", []) if str(code)],
            }
            for item in records
        ]
        manual_confirmation_required = any(item["status"] in {"failed", "blocked"} for item in public_records)
        return {
            "enabled": bool(summary.get("enabled")),
            "executed_count": max(0, int(summary.get("executed_count") or 0)),
            "max_attempts": max(0, int(summary.get("max_attempts") or 0)),
            "issue_codes": [str(code) for code in summary.get("issue_codes", []) if str(code)],
            "records": public_records,
            "append_only": bool(summary.get("append_only", bool(public_records))),
            "manual_confirmation_required": manual_confirmation_required,
        }

    @staticmethod
    def _public_post_generation_review(value: Any) -> dict[str, Any]:
        """Expose review outcome without provider, prompt, path, or repair internals."""

        package = dict(value or {}) if isinstance(value, dict) else {}
        inspections = []
        for item in package.get("inspections", []):
            if not isinstance(item, dict):
                continue
            issues = [
                {
                    "code": str(issue.get("code") or "review_notice"),
                    "severity": str(issue.get("severity") or "warning"),
                    "retryable": bool(issue.get("retryable")),
                    "message": str(issue.get("message") or issue.get("code") or "V3 found a review notice."),
                }
                for issue in item.get("detected_issues", [])
                if isinstance(issue, dict)
            ]
            inspections.append(
                {
                    "output_id": str(item.get("output_id") or ""),
                    "mode": str(item.get("mode") or "metadata_only"),
                    "status": str(item.get("status") or "unverified"),
                    "verification_state": str(item.get("verification_state") or "unverified"),
                    "detected_issues": issues,
                }
            )
        return {
            "user_visible_summary": [
                str(line)[:300]
                for line in package.get("user_visible_summary", [])
                if isinstance(line, str) and line.strip()
            ][:6],
            "inspections": inspections,
            "recommended_output_ids": [str(value) for value in package.get("recommended_output_ids", []) if str(value)],
            "hidden_output_ids": [str(value) for value in package.get("hidden_output_ids", []) if str(value)],
        }

    @classmethod
    def _public_metadata_projection(cls, value: Any) -> Any:
        """Remove execution-only data from nested public Job metadata.

        Capability and candidate records are intentionally verbose inside the
        durable audit ledger. Public Job responses may retain safe facts needed
        by existing project views, but must not recreate a prompt compiler,
        provider trace, storage path, or retry-execution surface.
        """

        hidden_keys = {
            "retry_patch",
            "blocked_reason",
            "file_path",
            "provider_failure_retry",
            "provider_failure_retry_exhausted",
            "provider_reason",
            "provider_response_summary",
            "runtime_transport",
            "final_provider_prompt",
        }
        if isinstance(value, dict):
            projected: dict[str, Any] = {}
            for key, nested in value.items():
                key_text = str(key)
                if key_text in hidden_keys or key_text.endswith("_retry_patch"):
                    continue
                # Capability executor stages are internal diagnostics.  A
                # literal ``retry_patch`` stage would otherwise make the
                # public response look as though it carries a retry payload.
                # Keep the safe, user-facing retry summary as the sole public
                # retry surface instead.
                if key_text == "stages" and isinstance(nested, list):
                    nested = [item for item in nested if str(item) != "retry_patch"]
                projected[key_text] = cls._public_metadata_projection(nested)
            return projected
        if isinstance(value, list):
            return [cls._public_metadata_projection(item) for item in value]
        if isinstance(value, tuple):
            return [cls._public_metadata_projection(item) for item in value]
        return value

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
                **self._ecommerce_runtime_provenance_status_metadata(record),
            },
        )

    @staticmethod
    def _ecommerce_runtime_provenance_status_metadata(record: ProductJobRecord) -> dict[str, Any]:
        scenario_id = record.scenario_resolution.manifest.scenario_id if record.scenario_resolution else None
        if scenario_id != "ecommerce":
            return {}
        provenance = record.request.metadata.get("ecommerce_runtime_provenance")
        return {"ecommerce_runtime_provenance": dict(provenance)} if isinstance(provenance, dict) else {}

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
            "ecommerce_slot_lineage",
            "photography_role_lineage",
            "capability_plan_amendment",
            "continuation_evidence_asset_ids",
            "capability_activation_plan_id",
            "capability_catalog_version",
            "capability_activation_mode",
            "remote_creative_brain_outcome",
            "provider_failure_retry",
            "provider_failure_retry_exhausted",
            "generation_lifecycle_timeout",
            "generation_lifecycle_failure",
            "background_generation_watchdog",
            "photographer_profile_binding",
            "specialized_scenario_plan_summary",
            "specialized_execution_summary",
            "review_certification",
        }
        status_metadata = {key: request_metadata[key] for key in allowed_keys if key in request_metadata}
        specialized_execution = status_metadata.get("specialized_execution_summary")
        if isinstance(specialized_execution, dict):
            status_metadata["specialized_execution_summary"] = self._public_specialized_execution_summary(
                specialized_execution
            )
            scenario_id = record.scenario_resolution.manifest.scenario_id if record.scenario_resolution else ""
            certification = request_metadata.get("review_certification") if scenario_id == "photography" else None
            if scenario_id == "photography" and not isinstance(certification, dict):
                # Explicit read-only adapter for pre-Doc116 Photography jobs.
                # It projects an already-recorded shared-review outcome; it
                # never recertifies pixels or creates a legacy execution path.
                certification = self._review_certification_from_specialized_execution(specialized_execution)
            if isinstance(certification, dict):
                status_metadata["review_certification"] = certification
        result = record.generation_result or record.planning_result
        if result is not None:
            plan = self._activation_plan_from_result(result)
            active = {
                str(item)
                for item in (plan.get("dependency_order") or plan.get("active_capability_ids") or [])
                if str(item).strip()
            }
            if active:
                friendly = []
                for capability_id, message in (
                    ("portrait_identity", "used the person reference"),
                    ("product_identity", "kept the product appearance"),
                    ("scene_continuity", "continued the scene direction"),
                    ("typography_layout", "prepared the requested layout"),
                    ("suite_direction", "planned this image set"),
                ):
                    if capability_id in active:
                        friendly.append(message)
                status_metadata["capability_summary"] = friendly
        return status_metadata

    @staticmethod
    def _public_specialized_execution_summary(execution: dict[str, Any]) -> dict[str, Any]:
        """Project-facing specialized execution state with no provider internals.

        Provider output/candidate identifiers and raw error messages remain
        append-only internal diagnostics.  Project and browser clients only
        need the frozen role contract and whether delivery is certifying.
        """

        return {
            "requested_image_count": execution.get("requested_image_count"),
            "role_keys": list(execution.get("role_keys") or []),
            "shared_execution_only": bool(execution.get("shared_execution_only")),
            "status": execution.get("status"),
            "missing_role_keys": list(execution.get("missing_role_keys") or []),
            "noncertifying_role_keys": list(execution.get("noncertifying_role_keys") or []),
            "roles": [
                {
                    "role_key": item.get("role_key"),
                    "status": item.get("status"),
                    "review_mode": item.get("review_mode"),
                    "review_status": item.get("review_status"),
                    "verification_state": item.get("verification_state"),
                    "real_pixel_certified": bool(item.get("real_pixel_certified")),
                }
                for item in execution.get("roles", [])
                if isinstance(item, dict)
            ],
            "final_delivery_withheld": bool(execution.get("final_delivery_withheld")),
            "append_only_history_preserved": bool(execution.get("append_only_history_preserved")),
        }

    @staticmethod
    def _review_certification_from_specialized_execution(execution: dict[str, Any]) -> dict[str, Any] | None:
        """Read an old Photography terminal summary without trusting it as pixels.

        This is a one-way public projection for records written before the
        explicit certification object existed.  It can withhold an old result,
        never turn an unverified one into a certified delivery.
        """

        existing = execution.get("review_certification")
        if isinstance(existing, dict):
            return dict(existing)
        raw_roles = execution.get("roles")
        if not isinstance(raw_roles, list) or not raw_roles:
            return None
        roles: list[dict[str, Any]] = []
        missing = False
        noncertifying = False
        for raw_role in raw_roles:
            if not isinstance(raw_role, dict):
                continue
            role_status = str(raw_role.get("status") or "missing").strip().lower()
            review_mode = str(raw_role.get("review_mode") or "").strip().lower() or None
            review_status = str(raw_role.get("review_status") or "").strip().lower() or None
            verified = bool(raw_role.get("real_pixel_certified")) or (
                review_mode in {"vision_model", "hybrid"} and review_status in {"pass", "warning"}
            )
            state = (
                "certified"
                if role_status == "generated" and verified
                else "manual_confirmation_required"
                if role_status == "generated" and review_mode in {"vision_model", "hybrid"} and review_status == "manual_review"
                else "blocked"
            )
            missing = missing or role_status != "generated"
            noncertifying = noncertifying or state != "certified"
            roles.append(
                {
                    "role_key": str(raw_role.get("role_key") or "").strip() or "unknown_role",
                    "state": state,
                    "review_mode": review_mode,
                    "review_status": review_status,
                    "verification_state": str(raw_role.get("verification_state") or "").strip().lower() or None,
                }
            )
        if not roles:
            return None
        state = (
            "certified"
            if not missing and not noncertifying
            else "manual_confirmation_required"
            if not missing and all(item["state"] == "manual_confirmation_required" for item in roles)
            else "blocked"
        )
        return {
            "schema_version": "v3_review_certification_v1",
            "scenario_id": "photography",
            "state": state,
            "automatic_delivery_certified": state == "certified",
            "manual_confirmation_required": state == "manual_confirmation_required",
            "final_delivery_withheld": bool(execution.get("final_delivery_withheld")) or missing or noncertifying,
            "roles": roles,
        }

    def _resolve_and_pin_photographer_profile(
        self,
        request: CreateCreativeJobRequest,
        *,
        trusted_photography_continuation: bool = False,
    ) -> None:
        """Resolve selection before Central Brain and pin it outside prompt-owned state."""

        metadata = dict(request.metadata or {})
        if "photographer_profile_binding" in metadata and not trusted_photography_continuation:
            raise PhotographerProfileSelectionError(
                "photographer_profile_binding_immutable",
                "Photographer profile bindings are server-owned.",
                status_code=409,
            )
        if "specialized_scenario_plan" in metadata and not trusted_photography_continuation:
            raise PhotographerProfileSelectionError(
                "photography_runtime_metadata_server_owned",
                "Specialized photography planning snapshots are server-owned.",
                status_code=409,
            )
        if trusted_photography_continuation:
            binding = metadata.get("photographer_profile_binding")
            specialized = metadata.get("specialized_scenario_plan")
            if not isinstance(binding, dict) or not isinstance(specialized, dict):
                raise PhotographerProfileSelectionError(
                    "photography_trusted_continuation_contract_missing",
                    "A trusted Photography continuation requires the server-pinned profile and planning snapshot.",
                    status_code=409,
                )
            return
        scenario_resolution = self.scenario_runtime.scenario_registry.resolve(request.scenario_selection)
        binding = self.photographer_profile_catalog.resolve_binding(
            scenario_id=scenario_resolution.manifest.scenario_id,
            profile_id=request.photographer_profile_id,
            selection_source=request.photographer_profile_selection_source,
            region=self._photographer_profile_region(),
        )
        if binding is None:
            return
        binding_payload = binding.model_dump(mode="json")
        metadata["photographer_profile_binding"] = binding_payload
        project_context = metadata.get("project_context_snapshot")
        if isinstance(project_context, dict):
            metadata["project_context_snapshot"] = {
                **dict(project_context),
                "photographer_profile_binding": binding_payload,
            }
        request.metadata = metadata

    def _assert_photographer_profile_binding_immutable(
        self,
        record: ProductJobRecord,
        request: GenerateJobRequest,
    ) -> None:
        binding = dict(record.request.metadata or {}).get("photographer_profile_binding")
        if not isinstance(binding, dict):
            return
        attempted = dict(request.metadata or {})
        forbidden = {
            "photographer_profile_id",
            "photographer_profile_selection_source",
            "photographer_profile_binding",
            "specialized_scenario_plan",
            "specialized_scenario_plan_summary",
        }
        if forbidden.intersection(attempted):
            raise PhotographerProfileSelectionError(
                "photographer_profile_binding_immutable",
                "Photographer profile bindings cannot be changed after a job is created.",
                status_code=409,
            )

    def _photographer_profile_region(self) -> str | None:
        value = self.photographer_profile_region_resolver()
        if value is None:
            return None
        return str(value).strip().upper() or None

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
        status = self._partial_output_recovery_status(record) or self._status_from_record(record)
        scenario_id = status.scenario.scenario_id if status.scenario else None
        scenario_label = status.scenario.display_name if status.scenario else None
        selected_preset_id = status.scenario.selected_preset_id if status.scenario else None
        selected_asset_count = len(record.selected_result.selected_asset_ids) if record.selected_result else 0
        return V3JobHistoryItem(
            job_id=record.job_id,
            status=status.status,
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
                "partial_generation_recovery": status.metadata.get("partial_generation_recovery"),
            },
        )

    def _partial_output_recovery_status(self, record: ProductJobRecord) -> ProductJobStatus | None:
        """Expose durable earlier deliveries when a later set role fails.

        The worker can persist a reviewed first output before a later role
        reaches a provider failure.  Treating the whole job as empty then made
        the browser hide a real image after refresh.  Keep the original job
        record append-only and blocked for diagnostics, while presenting the
        durable delivery as an explicitly marked partial result.
        """

        if record.status not in {ProductJobStatusValue.BLOCKED, ProductJobStatusValue.FAILED}:
            return None
        if record.generation_result is not None:
            return None
        restored = self._status_from_output_store(record.job_id)
        if restored is None:
            return None
        result = record.planning_result
        output_count = len(restored.candidates)
        partial_metadata = {
            "status": "partial_output_preserved",
            "source_record_status": record.status.value,
            "delivered_output_count": output_count,
            "remaining_roles_failed": True,
            "append_only_history_preserved": True,
        }
        warnings = list(
            dict.fromkeys(
                [
                    *record.warnings,
                    "A generated image was preserved after a later set role failed; it is available as a recoverable partial result.",
                ]
            )
        )
        return restored.model_copy(
            update={
                "brand_id": result.brand_profile.brand_id if result is not None else restored.brand_id,
                "planning_result_id": result.planning_result_id if result is not None else restored.planning_result_id,
                "asset_pack_id": result.asset_pack.asset_pack_id if result is not None else restored.asset_pack_id,
                "scenario": self._scenario_summary(record),
                "campaign": self._campaign_summary(record, result) if result is not None else restored.campaign,
                "style_continuation": self._style_continuation_summary(record, result)
                if result is not None
                else restored.style_continuation,
                "general_creative": self._general_creative_summary(record),
                "ecommerce": self._ecommerce_summary(record),
                "balance_estimate": dict(record.balance_estimate),
                "warnings": warnings,
                "metadata": {
                    **dict(restored.metadata or {}),
                    "partial_generation_recovery": partial_metadata,
                    "lifecycle": self._lifecycle_summary(record),
                    "continuation_available": True,
                    **self._project_mode_status_metadata(record),
                },
            },
            deep=True,
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
            candidate_metadata = self._public_metadata_projection(
                packaged.metadata.get("candidate_metadata", {}) if packaged else {}
            )
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
                        "asset_metadata": self._public_metadata_projection(dict(asset.metadata)),
                        "ecommerce_slot": asset.metadata.get("ecommerce_slot"),
                        **self._legacy_ecommerce_recipe_metadata(asset.metadata),
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
            candidate_metadata = self._public_metadata_projection(asset.metadata.get("candidate_metadata", {}))
            asset_metadata = self._public_metadata_projection(
                dict(asset_spec.metadata) if asset_spec else dict(asset.metadata.get("asset_metadata", {}))
            )
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
                        **self._legacy_ecommerce_recipe_metadata(asset.metadata, asset_metadata),
                        **candidate_metadata,
                    },
                )
            )
        return candidates

    def _output_preview_uri(self, fallback: str | None, metadata: dict[str, Any]) -> str | None:
        return metadata.get("thumbnail_url") or metadata.get("preview_url") or fallback

    @staticmethod
    def _legacy_ecommerce_recipe_metadata(*metadata_records: dict[str, Any]) -> dict[str, Any]:
        """Keep pre-migration recipe data readable without emitting it anew."""

        for metadata in metadata_records:
            recipe = metadata.get("ecommerce_recipe") if isinstance(metadata, dict) else None
            if isinstance(recipe, dict):
                return {"ecommerce_recipe": recipe}
        return {}

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
        output_intents = self._ecommerce_output_intents(record)
        export_package = self._ecommerce_runtime_export_package(record, pack_output)
        creative_context = dict(record.request.metadata.get("ecommerce_creative_context") or {})
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
            # Legacy consumers still receive an empty recipe list for a new
            # LLM-native job.  New E-Commerce UI reads output intents instead.
            image_recipes=[recipe.model_dump(mode="json") for recipe in pack_output.recipes],
            creative_context=creative_context,
            remote_brain_output_intents=output_intents,
            critic_checks=[dict(item) for item in pack_output.critic.checks],
            export_package=export_package,
            closure_checks=self._ecommerce_closure_checks(record, pack_output, output_intents, export_package),
            warnings=warnings,
            metadata={
                "product_language": True,
                "scenario_pack_logic": True,
                "imports_v1_v2_runtime": False,
                "external_research_used": False,
                "recipe_count": len(pack_output.recipes),
                "remote_brain_output_count": len(output_intents),
                "creative_recipe_present": False,
                "shared_capabilities": self._capability_run_summary(record.capability_run),
            },
        )

    def _ecommerce_runtime_export_package(
        self,
        record: ProductJobRecord,
        output: EcommercePackOutput,
    ) -> dict[str, Any]:
        """Bind actual provider outputs to opaque Brain-selected output IDs."""

        package = output.export_package.model_dump(mode="json")
        output_by_asset = {
            str(item.get("asset_id") or ""): item
            for item in self._generated_asset_records(record)
            if str(item.get("asset_id") or "")
        }
        files: list[dict[str, Any]] = []
        dimensions: dict[str, str] = {}
        for intent in self._ecommerce_output_intents(record):
            asset_id = str(intent.get("asset_id") or "")
            generated = output_by_asset.get(asset_id)
            if generated is None:
                continue
            output_id = str(generated.get("output_id") or "").strip()
            if not output_id:
                continue
            opaque_output_id = str(intent.get("slot_id") or output_id).strip()
            files.append(
                {
                    "opaque_output_id": opaque_output_id,
                    "filename": f"{opaque_output_id}.png",
                    "asset_id": asset_id,
                    "output_id": output_id,
                    "intent": intent.get("intent"),
                    "download_url": generated.get("download_url"),
                    "preview_url": generated.get("preview_url"),
                    "width": generated.get("width"),
                    "height": generated.get("height"),
                    "mime_type": generated.get("mime_type"),
                    "review_status": generated.get("review_status"),
                    "provider_native_complete_image": True,
                }
            )
            width, height = generated.get("width"), generated.get("height")
            if width and height:
                dimensions[opaque_output_id] = f"{width}x{height}"
        package.update(
            {
                "files": files,
                "dimensions": dimensions,
                "naming_pattern": "{opaque_output_id}.png",
                "review_status": "metadata_ready" if files else "attention",
                "metadata": {
                    **dict(package.get("metadata") or {}),
                    "source": "V3ProductApiService._ecommerce_runtime_export_package",
                    "creative_recipe_present": False,
                    "remote_brain_output_count": len(self._ecommerce_output_intents(record)),
                    "actual_provider_file_count": len(files),
                },
            }
        )
        return package

    def _ecommerce_export_manifest(
        self,
        record: ProductJobRecord,
        output: EcommercePackOutput,
        export_package: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "manifest_version": "v3_ecommerce_export_manifest_001",
            "job_id": record.job_id,
            "scenario_id": "ecommerce",
            "job_status": record.status.value,
            "package_id": export_package.get("package_id") or output.export_package.package_id,
            "platform": output.marketplace_profile.platform,
            "market": output.marketplace_profile.market,
            "source_asset_ids": list(record.request.uploaded_asset_ids),
            "uploaded_assets": self._uploaded_asset_records(record.request.uploaded_asset_ids),
            "product_truth": output.product_truth.model_dump(mode="json"),
            "commerce_brief": output.commerce_brief.model_dump(mode="json"),
            "image_recipes": [],
            "remote_brain_output_intents": self._ecommerce_output_intents(record),
            "generated_assets": self._generated_asset_records(record),
            "export_files": list(export_package.get("files") or []),
            "review_checks": [dict(item) for item in output.critic.checks],
            "warnings": self._ecommerce_public_warnings(record, output),
            "metadata": {
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "export_package_review_status": export_package.get("review_status"),
                "pixel_assets_required_before_download": dict(export_package.get("metadata") or {}).get("pixel_assets_required_before_download", True),
                "creative_recipe_present": False,
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

    def _ecommerce_output_intents(self, record: ProductJobRecord) -> list[dict[str, Any]]:
        result = record.generation_result or record.planning_result
        if result is None:
            return []
        intents: list[dict[str, Any]] = []
        for asset in result.series_plan.assets:
            metadata = dict(asset.metadata or {})
            slot_id = str(metadata.get("ecommerce_slot") or "").strip()
            if not slot_id:
                continue
            intents.append(
                {
                    "slot_id": slot_id,
                    "index": metadata.get("ecommerce_slot_index"),
                    "intent": str(metadata.get("ecommerce_creative_direction") or asset.purpose or "").strip(),
                    "source": "remote_v3_llm_brain" if metadata.get("ecommerce_llm_directed") else "legacy_record",
                    "asset_id": asset.asset_id,
                }
            )
        return intents

    def _ecommerce_closure_checks(
        self,
        record: ProductJobRecord,
        output: EcommercePackOutput,
        output_intents: list[dict[str, Any]],
        export_package: dict[str, Any],
    ) -> list[dict[str, Any]]:
        checks = [
            {
                "id": "product_truth",
                "label": "Product truth lock",
                "status": "done" if output.product_truth.immutable_attributes else "attention",
                "detail": f"{len(output.product_truth.immutable_attributes)} immutable product fact(s) will be checked.",
            },
            {
                "id": "commerce_context",
                "label": "Seller facts and evidence",
                "status": "done" if record.request.metadata.get("ecommerce_creative_context") else "attention",
                "detail": "Product facts, seller inputs, category evidence questions, and versioned platform constraints are ready for the Brain.",
            },
            {
                "id": "marketplace_profile",
                "label": "Marketplace profile",
                "status": "done" if output.marketplace_profile.metadata.get("profile_id") else "attention",
                "detail": f"{output.marketplace_profile.platform}/{output.marketplace_profile.market} profile is applied.",
            },
            {
                "id": "remote_brain_output_set",
                "label": "Central Brain output set",
                "status": "done" if output_intents else "attention",
                "detail": f"{len(output_intents)} opaque E-Commerce output intent(s) came from the remote Brain.",
            },
            {
                "id": "export_package",
                "label": "Export package",
                "status": "done" if export_package.get("files") else "attention",
                "detail": f"{len(export_package.get('files') or [])} provider output file record(s) prepared.",
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

    def _runtime_request_payload(
        self,
        request: CreateCreativeJobRequest,
        *,
        trusted_capability_plan_reuse: bool | None = None,
    ) -> dict[str, Any]:
        self._prepare_ecommerce_creative_context(request)
        metadata = self._runtime_metadata_without_retired_ecommerce_execution(request)
        scenario_selection = self._runtime_scenario_selection_without_retired_ecommerce_execution(request)
        has_frozen_plan = isinstance(metadata.get("capability_activation_plan"), dict)
        trusted_reuse = has_frozen_plan if trusted_capability_plan_reuse is None else trusted_capability_plan_reuse
        return {
            "user_input": request.user_input,
            "optional_brand_id": request.effective_brand_id,
            "scenario_selection": scenario_selection,
            "uploaded_asset_ids": list(request.uploaded_asset_ids),
            "uploaded_assets": self.asset_store.resolve_uploaded_assets(list(request.uploaded_asset_ids)),
            "product_profile": dict(request.product_profile),
            "metadata": metadata,
            "trusted_capability_plan_reuse": trusted_reuse,
        }

    def _is_ecommerce_request(self, request: CreateCreativeJobRequest) -> bool:
        resolution = self.scenario_runtime.scenario_registry.resolve(request.scenario_selection)
        return resolution.manifest.scenario_id == "ecommerce"

    @staticmethod
    def _normalise_ecommerce_execution_key(value: Any) -> str:
        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    def _retired_ecommerce_execution_fields(self, values: dict[str, Any]) -> list[str]:
        return sorted(
            str(key)
            for key in dict(values or {})
            if self._normalise_ecommerce_execution_key(key) in _ECOMMERCE_RETIRED_EXECUTION_FIELDS
        )

    def _without_retired_ecommerce_execution_fields(self, values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in dict(values or {}).items()
            if self._normalise_ecommerce_execution_key(key) not in _ECOMMERCE_RETIRED_EXECUTION_FIELDS
        }

    def _runtime_metadata_without_retired_ecommerce_execution(
        self,
        request: CreateCreativeJobRequest,
    ) -> dict[str, Any]:
        metadata = dict(request.metadata or {})
        if not self._is_ecommerce_request(request):
            return metadata
        return self._without_retired_ecommerce_execution_fields(metadata)

    def _runtime_scenario_selection_without_retired_ecommerce_execution(
        self,
        request: CreateCreativeJobRequest,
    ):
        selection = request.scenario_selection
        if selection is None or not self._is_ecommerce_request(request):
            return selection
        return selection.model_copy(
            update={
                "parameters": self._without_retired_ecommerce_execution_fields(dict(selection.parameters or {})),
            }
        )

    _SERVER_OWNED_RUNTIME_METADATA = frozenset(
        {
            "capability_activation_plan",
            "capability_activation_plan_id",
            "capability_catalog_version",
            "capability_activation_mode",
            "capability_plan_provenance",
            "capability_execution_envelope",
            "capability_execution_envelope_id",
            "normalized_v3_job_intent",
            "normalized_v3_job_intent_id",
            "template_deliverable_plan",
            "template_deliverable_plan_id",
            "resolved_constraint_ledger",
            "resolved_constraint_ledger_id",
            "frozen_remote_creative_brain",
            "v3_job_instance_id",
        }
    )

    @staticmethod
    def _bind_server_job_instance_id(request: CreateCreativeJobRequest) -> None:
        """Stamp a fresh, server-owned identity for one append-only Job.

        Prompt equality is useful for deterministic planning fixtures, but it
        is not a safe persistence identity: a user may intentionally submit
        the same request twice, and a continuation must never replace its
        parent. The identifier is deliberately opaque and is replaced even
        for a trusted continuation, while its frozen capability plan remains
        independently validated by the continuation seam.
        """

        request.metadata = {
            **dict(request.metadata or {}),
            "v3_job_instance_id": uuid4().hex,
        }

    @staticmethod
    def _bind_frozen_remote_creative_brain(
        request: CreateCreativeJobRequest,
        runtime_result: Any,
    ) -> None:
        """Persist a specialized remote creative answer with its frozen plan.

        This is a server-owned execution binding, not browser-supplied
        metadata.  ScenarioRuntime validates the exact plan/template/scenario
        linkage before generation or retry may reuse it.
        """

        resolution = getattr(runtime_result, "scenario_resolution", None)
        scenario_id = str(getattr(getattr(resolution, "manifest", None), "scenario_id", "") or "")
        if scenario_id not in {"ecommerce", "photography"}:
            return
        runtime_metadata = dict(getattr(runtime_result, "metadata", {}) or {})
        plan = runtime_metadata.get("capability_activation_plan")
        brain_result = runtime_metadata.get("llm_brain")
        if not isinstance(plan, dict) or not isinstance(brain_result, dict):
            return
        if not bool(brain_result.get("llm_used")) or bool(brain_result.get("fallback_used")):
            return
        request.metadata = {
            **dict(request.metadata or {}),
            "frozen_remote_creative_brain": {
                "schema_version": "v3_frozen_remote_creative_brain_v1",
                "template_id": str(plan.get("template_id") or ""),
                "scenario_id": str(plan.get("scenario_id") or scenario_id),
                "capability_plan_id": str(plan.get("plan_id") or ""),
                "capability_plan_fingerprint": str(plan.get("fingerprint") or ""),
                "brain_result": brain_result,
            },
        }

    def _assert_runtime_metadata_server_owned(
        self,
        request: CreateCreativeJobRequest,
        *,
        trusted_capability_plan_reuse: bool,
    ) -> None:
        """Keep browser/API metadata from impersonating a frozen runtime job."""

        supplied = set(dict(request.metadata or {})).intersection(self._SERVER_OWNED_RUNTIME_METADATA)
        if supplied and not trusted_capability_plan_reuse:
            raise ValueError(
                "runtime_metadata_server_owned: " + ", ".join(sorted(supplied))
            )

    def _validate_and_bind_trusted_capability_plan_reuse(self, request: CreateCreativeJobRequest) -> None:
        """Bind a child to a persisted parent plan or its one audited amendment."""

        metadata = dict(request.metadata or {})
        plan_payload = metadata.get("capability_activation_plan")
        source_job_id = str(metadata.get("capability_plan_reuse_source_job_id") or "").strip()
        if not isinstance(plan_payload, dict) or not source_job_id:
            raise ValueError("trusted_capability_plan_reuse_contract_missing")
        source = self.job_store.get(source_job_id)
        if source is not None:
            source_metadata = dict(source.request.metadata or {})
            source_plan = source_metadata.get("capability_activation_plan")
        else:
            # A Project Mode restart may reload the durable project store
            # before its in-memory Product API cache.  The Project service
            # supplies the immutable parent anchor only through this
            # internal method, so validate that self-contained snapshot just
            # as strictly instead of weakening the continuation contract.
            snapshot = metadata.get("capability_plan_reuse_source_snapshot")
            if not isinstance(snapshot, dict) or str(snapshot.get("job_id") or "") != source_job_id:
                raise ValueError("trusted_capability_plan_reuse_source_not_found")
            source_metadata = {
                "capability_plan_provenance": snapshot.get("capability_plan_provenance"),
            }
            source_plan = snapshot.get("capability_activation_plan")
        if not isinstance(source_plan, dict):
            raise ValueError("trusted_capability_plan_reuse_source_plan_missing")

        plan_id = str(plan_payload.get("plan_id") or "").strip()
        fingerprint = str(plan_payload.get("fingerprint") or "").strip()
        source_plan_id = str(source_plan.get("plan_id") or "").strip()
        source_fingerprint = str(source_plan.get("fingerprint") or "").strip()
        same_source_plan = plan_id == source_plan_id and fingerprint == source_fingerprint
        amendment = metadata.get("capability_plan_amendment")
        allowed_amendment = (
            isinstance(amendment, dict)
            and str(amendment.get("original_plan_id") or "") == source_plan_id
            and str(amendment.get("amended_plan_id") or "") == plan_id
            and int(amendment.get("amendment_index") or 1) == 1
        )
        if not same_source_plan and not allowed_amendment:
            raise ValueError("trusted_capability_plan_reuse_source_plan_mismatch")
        source_provenance = source_metadata.get("capability_plan_provenance")
        if isinstance(source_provenance, dict) and source_provenance:
            if (
                source_provenance.get("authority") != "v3_product_api"
                or str(source_provenance.get("issued_for_job_id") or "") != source_job_id
                or str(source_provenance.get("plan_id") or "") != source_plan_id
                or str(source_provenance.get("plan_fingerprint") or "") != source_fingerprint
            ):
                raise ValueError("trusted_capability_plan_reuse_source_provenance_mismatch")
        metadata["capability_plan_provenance"] = {
            "authority": "v3_product_api",
            "issued_for_job_id": "pending_product_job",
            "source_job_id": source_job_id,
            "source_plan_id": source_plan_id,
            "plan_id": plan_id,
            "plan_fingerprint": fingerprint,
            "reuse_kind": "amendment" if allowed_amendment and not same_source_plan else "continuation",
        }
        request.metadata = metadata

    def _bind_capability_plan_provenance(self, request: CreateCreativeJobRequest, job_id: str) -> None:
        """Persist a server-issued binding after a root or child plan is known."""

        metadata = dict(request.metadata or {})
        plan = metadata.get("capability_activation_plan")
        if not isinstance(plan, dict):
            return
        provenance = metadata.get("capability_plan_provenance")
        base = dict(provenance) if isinstance(provenance, dict) else {}
        base.update(
            {
                "authority": "v3_product_api",
                "issued_for_job_id": job_id,
                "plan_id": str(plan.get("plan_id") or ""),
                "plan_fingerprint": str(plan.get("fingerprint") or ""),
            }
        )
        if not str(base.get("source_job_id") or "").strip():
            base["source_job_id"] = job_id
            base["source_plan_id"] = str(plan.get("plan_id") or "")
            base["reuse_kind"] = "root"
        metadata["capability_plan_provenance"] = base
        request.metadata = metadata

    def _prepare_ecommerce_creative_context(self, request: CreateCreativeJobRequest) -> None:
        """Pin server-derived facts before the remote Brain sees an E-Commerce job.

        The browser cannot provide this payload as a creative recipe.  It is
        rebuilt from product-level request data and contains evidence only.
        """

        resolution = self.scenario_runtime.scenario_registry.resolve(request.scenario_selection)
        if resolution.manifest.scenario_id != "ecommerce":
            return
        selection = request.scenario_selection
        supplied_parameters = dict(selection.parameters) if selection is not None else {}
        parameters = self._without_retired_ecommerce_execution_fields(supplied_parameters)
        parameters.setdefault("mode", resolution.selected_mode_id)
        parameters.setdefault("preset", resolution.selected_preset_id)
        metadata = dict(request.metadata or {})
        ignored_fields = sorted(
            set(self._retired_ecommerce_execution_fields(metadata))
            | set(self._retired_ecommerce_execution_fields(supplied_parameters))
        )
        if ignored_fields:
            metadata["ecommerce_legacy_execution_ignored"] = {
                "source": "V3ProductApiService",
                "status": "read_compatible_not_executed",
                "fields": ignored_fields,
            }
        job_key = str(metadata.get("job_id") or "").strip() or stable_id(
            "ecommerce_context_job",
            request.user_input,
            metadata.get("project_id"),
            metadata.get("project_job_sequence"),
        )
        context = self.ecommerce_planner.build_creative_context(
            user_input=request.user_input,
            product_profile=dict(request.product_profile),
            uploaded_asset_ids=list(request.uploaded_asset_ids),
            scenario_parameters=parameters,
            platform_profile=selection.platform_profile if selection is not None else None,
            job_key=job_key,
        )
        metadata["ecommerce_creative_context"] = context.model_dump(mode="json")
        metadata["ecommerce_creative_context_server_owned"] = True
        request.metadata = metadata

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
