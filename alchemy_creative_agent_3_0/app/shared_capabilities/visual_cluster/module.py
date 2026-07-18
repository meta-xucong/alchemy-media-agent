"""Unified V3 visual capability cluster module."""

from __future__ import annotations

import re
from typing import Any

from ...creative_core.prompt_language import product_language_allowed
from ...creative_core.rules import stable_id
from ..base import SharedCapabilityModule
from ..contracts import (
    AssetRole,
    CapabilityConstraint,
    CapabilityInput,
    CapabilityResult,
    CapabilityStatus,
    CapabilityTargetStage,
)
from .contracts import (
    AdaptiveReferenceSelectionPlan,
    AntiAIFaceReviewResult,
    AutoRetryDecision,
    BatchIdentityDiversityReview,
    BeautifulRealismBalanceReview,
    BoneStructureRetryPatch,
    CommercialOutputSelection,
    GeneralSuiteRolePlan,
    HumanBatchDiversityReview,
    HumanIdentityAnchorProfile,
    HumanNaturalVariationPlan,
    HumanPhotorealismGuidance,
    IdentityHeroSelectionPlan,
    IdentityDriftGuardPlan,
    IdentityRepairStrategyPlan,
    ModeQualityProfile,
    ModeDifferentiationReview,
    PortraitBoneStructureLock,
    PortraitReferenceBalancePolicy,
    PortraitReferenceBalanceRetryPatch,
    PortraitReferenceBalanceReview,
    PortraitIdentityStyleSeparationReview,
    PortraitIdentitySimilarityReview,
    PortraitReferenceInfluencePolicy,
    ResolvedReferencePolicyPackage,
    ReferenceOverinheritanceRetryPatch,
    RoleSpecificGenerationPlan,
    ProjectIdentityAnchor,
    ProjectVisualGrammarSnapshot,
    StrictVisualReviewPolicy,
    StylingDeltaPolicy,
    StrongReferenceClosurePackage,
    StrongReferenceContinuationPlan,
    StrongReferenceBinding,
    SubjectIdentityCard,
    SubjectContinuityAssetPackage,
    VisualCapabilityClusterResult,
    VisualConsistencyGuardResult,
    VisualGrammarProfile,
    VisualIdentityLockProfile,
    VisualCommercialQualityReview,
    VisualQualityReviewReport,
    VisualQualityReviewResult,
    VisualReferenceBindingProfile,
)
from .adaptive_reference import ADAPTIVE_REFERENCE_RETRIEVER_MODULE_ID, AdaptiveReferenceRetriever
from .batch_identity_review import BatchIdentityDiversityReviewer
from .commercial_quality import CommercialQualityClosureReviewer
from .doc66_closure import (
    MODE_QUALITY_PROFILE_MODULE_ID,
    STRONG_REFERENCE_CLOSURE_MODULE_ID,
    ModeQualityProfileBuilder,
    StrongReferenceClosureBuilder,
)
from .general_suite_director import GeneralSuiteDirector
from .human_photorealism import HumanPhotorealismLayer
from .human_variation import HumanNaturalVariationPolicy
from .identity_anchor import ProjectIdentityAnchorBuilder
from .identity_drift_guard import IDENTITY_DRIFT_GUARD_MODULE_ID, IdentityDriftGuard
from .identity_repair_strategy import IDENTITY_REPAIR_STRATEGY_MODULE_ID, IdentityRepairStrategyRouter
from .mode_role_director import ModeAwareRoleDirector
from .portrait_identity import (
    DOC86_IDENTITY_ISSUE_CODES,
    DOC87_REFERENCE_BOUNDARY_ISSUE_CODES,
    DOC88_REFERENCE_BALANCE_ISSUE_CODES,
    PortraitBoneStructureIdentityLayer,
)
from .reference_channel_policy import (
    REFERENCE_CHANNEL_ISSUE_CODES,
    REFERENCE_CHANNEL_POLICY_MODULE_ID,
    ReferenceChannelPolicyModule,
    reference_channel_issue_codes,
)
from .strong_reference_loop import StrongReferenceLoopPlanner
from .subject_asset_memory import SUBJECT_CONTINUITY_ASSET_PACK_MODULE_ID, SubjectContinuityAssetPackBuilder


VISUAL_CAPABILITY_CLUSTER_ID = "visual_capability_cluster"
ADVANCED_REFERENCE_PRIORITY_CONTROLS_MODULE_ID = "advanced_reference_priority_controls"
VISUAL_CLUSTER_CHILD_MODULE_IDS = {
    "asset_role_analyzer",
    "asset_binding_planner",
    "case_library_retriever",
    "visual_grammar_lock",
    "history_reference",
    "prompt_constraint_compiler",
    "output_review",
    "strong_reference_binder",
    "identity_lock_profile_builder",
    "output_quality_reviewer",
    "auto_retry_planner",
    "best_output_selector",
    "identity_anchor",
    "strong_reference_loop",
    "general_suite_director",
    "mode_role_director",
    "batch_identity_review",
    "commercial_quality_review",
    "identity_hero_selector",
    "subject_identity_card",
    "beautiful_realism_balance_review",
    "strict_visual_review_policy",
    "human_photorealism_layer",
    "anti_ai_face_review",
    "portrait_bone_structure_identity_lock",
    "portrait_reference_identity_style_separator",
    "portrait_reference_balance_policy",
    REFERENCE_CHANNEL_POLICY_MODULE_ID,
    SUBJECT_CONTINUITY_ASSET_PACK_MODULE_ID,
    ADAPTIVE_REFERENCE_RETRIEVER_MODULE_ID,
    IDENTITY_DRIFT_GUARD_MODULE_ID,
    IDENTITY_REPAIR_STRATEGY_MODULE_ID,
    ADVANCED_REFERENCE_PRIORITY_CONTROLS_MODULE_ID,
    STRONG_REFERENCE_CLOSURE_MODULE_ID,
    MODE_QUALITY_PROFILE_MODULE_ID,
}

HARD_REFERENCE_ROLES = {
    AssetRole.PRODUCT_REFERENCE.value,
    AssetRole.LOGO_REFERENCE.value,
    AssetRole.FACE_REFERENCE.value,
    AssetRole.NONHUMAN_IDENTITY_REFERENCE.value,
}
SOFT_REFERENCE_ROLES = {
    AssetRole.STYLE_REFERENCE.value,
    AssetRole.BACKGROUND_REFERENCE.value,
    AssetRole.COMPOSITION_REFERENCE.value,
    AssetRole.COLOR_REFERENCE.value,
    AssetRole.UNKNOWN_REFERENCE.value,
}
GENERAL_VISUAL_REPLACEMENTS = {
    "commercial": "polished",
    "commercially": "professionally",
    "conversion-ready": "ready to use",
    "conversion": "clear purpose",
    "product-first": "subject-first",
    "product hero": "subject hero",
    "product_or_service_content": "subject_or_scene_content",
    "brand_or_campaign_copy": "optional_external_caption_area",
    "business_offer": "optional_external_context",
    "minor_props": "minor_scene_details",
    "center product": "center subject",
    "centered product": "centered subject",
    "product": "subject",
    "headline safe area": "cover-safe clean space",
    "headline-safe top region": "cover-safe clean space",
    "clear text zones": "clean optional blank space",
    "bold headline": "strong cover rhythm",
    "cta": "clear action",
}
GENERAL_VISUAL_FORBIDDEN_TERMS = (
    "marketplace",
    "ecommerce",
    "shopping",
    "advertising prop",
    "product label",
    "product facts",
    "product identity",
    "product claims",
)

# These fields were introduced by the historical local prompt-compiler and
# retry-patch route.  They may remain readable inside old archived records,
# but a new enforced V3 capability result must not carry their locally written
# prose into the envelope that the remote Brain later signs.  Issue codes,
# binding facts and structural execution contracts remain intact.
FORWARD_LOCAL_CREATIVE_TEXT_FIELDS = frozenset(
    {
        "prompt_additions",
        "negative_additions",
        "identity_reinforcement",
        "artifact_repair",
        "reference_requirements",
        "positive_prompt_fragments",
        "negative_prompt_fragments",
        "provider_prompt_rules",
        "negative_prompt_rules",
        "prompt_guidance",
        "negative_guidance",
        "compact_negative_guidance",
    }
)


def _structured_appearance_rules() -> list[str]:
    return [
        "preserve the same structured appearance asset when styling defines the project",
        "keep silhouette, layer order, neckline or collar direction, sleeve or cuff shape, closure or sash direction, material behavior, and transparency family coherent",
        "keep pattern family, trim placement, accessory placement, and color-block relationships coherent when visible in the reference or selected frame",
    ]
ANTI_AI_FACE_ISSUE_CODES = {
    "ai_face_render",
    "plastic_skin",
    "over_smoothed_skin",
    "missing_skin_texture",
    "synthetic_beauty_filter",
    "doll_like_face",
    "template_smile",
    "over_perfect_symmetry",
    "wax_skin_highlight",
    "uncanny_eye_expression",
    "same_ai_face_repetition",
    "flat_scene_lighting",
    "airbrushed_background_texture",
    "synthetic_material_response",
    "frozen_centered_pose",
}
BEAUTIFUL_REALISM_ISSUE_CODES = {
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
}


class VisualCapabilityClusterModule(SharedCapabilityModule):
    """Collect visual child modules into one V3-owned reusable capability result."""

    module_id = VISUAL_CAPABILITY_CLUSTER_ID
    version = "v3_visual_capability_cluster_002_doc97"
    order = 990

    def __init__(
        self,
        human_variation_policy: HumanNaturalVariationPolicy | None = None,
        identity_anchor_builder: ProjectIdentityAnchorBuilder | None = None,
        strong_reference_planner: StrongReferenceLoopPlanner | None = None,
        suite_director: GeneralSuiteDirector | None = None,
        mode_role_director: ModeAwareRoleDirector | None = None,
        batch_reviewer: BatchIdentityDiversityReviewer | None = None,
        human_photorealism_layer: HumanPhotorealismLayer | None = None,
        commercial_quality_reviewer: CommercialQualityClosureReviewer | None = None,
        strong_reference_closure_builder: StrongReferenceClosureBuilder | None = None,
        mode_quality_profile_builder: ModeQualityProfileBuilder | None = None,
        portrait_identity_layer: PortraitBoneStructureIdentityLayer | None = None,
        reference_channel_policy_module: ReferenceChannelPolicyModule | None = None,
        identity_drift_guard: IdentityDriftGuard | None = None,
        subject_asset_pack_builder: SubjectContinuityAssetPackBuilder | None = None,
        adaptive_reference_retriever: AdaptiveReferenceRetriever | None = None,
        identity_repair_strategy_router: IdentityRepairStrategyRouter | None = None,
    ) -> None:
        self.human_variation_policy = human_variation_policy or HumanNaturalVariationPolicy()
        self.identity_anchor_builder = identity_anchor_builder or ProjectIdentityAnchorBuilder()
        self.strong_reference_planner = strong_reference_planner or StrongReferenceLoopPlanner()
        self.mode_role_director = mode_role_director or ModeAwareRoleDirector()
        self.suite_director = suite_director or GeneralSuiteDirector(mode_role_director=self.mode_role_director)
        self.batch_reviewer = batch_reviewer or BatchIdentityDiversityReviewer()
        self.human_photorealism_layer = human_photorealism_layer or HumanPhotorealismLayer()
        self.commercial_quality_reviewer = commercial_quality_reviewer or CommercialQualityClosureReviewer()
        self.strong_reference_closure_builder = strong_reference_closure_builder or StrongReferenceClosureBuilder()
        self.mode_quality_profile_builder = mode_quality_profile_builder or ModeQualityProfileBuilder()
        self.portrait_identity_layer = portrait_identity_layer or PortraitBoneStructureIdentityLayer()
        self.reference_channel_policy_module = reference_channel_policy_module or ReferenceChannelPolicyModule()
        self.identity_drift_guard = identity_drift_guard or IdentityDriftGuard()
        self.subject_asset_pack_builder = subject_asset_pack_builder or SubjectContinuityAssetPackBuilder()
        self.adaptive_reference_retriever = adaptive_reference_retriever or AdaptiveReferenceRetriever()
        self.identity_repair_strategy_router = identity_repair_strategy_router or IdentityRepairStrategyRouter()

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        cluster = self._build_cluster(capability_input)
        if self._is_brain_owned_forward_execution(capability_input):
            cluster = self._quarantine_forward_local_creative_language(cluster)
        constraints = self._constraints(cluster)
        activation_plan = self._activation_plan(capability_input)
        status = CapabilityStatus.SUCCESS if cluster.has_visual_evidence else CapabilityStatus.SKIPPED
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=status,
            confidence=cluster.profile.confidence,
            facts={
                "visual_capability_cluster": cluster.model_dump(mode="json"),
                "visual_grammar_profile": cluster.profile.model_dump(mode="json"),
                "project_visual_grammar_snapshot": cluster.project_snapshot.model_dump(mode="json"),
                "advanced_reference_controls": dict(cluster.metadata.get("advanced_reference_controls") or {}),
                "visual_reference_binding_profile": cluster.reference_binding_profile.model_dump(mode="json"),
                "strong_reference_bindings": list(cluster.reference_binding_profile.strong_bindings),
                "visual_identity_lock_profiles": [item.model_dump(mode="json") for item in cluster.identity_lock_profiles],
                "human_identity_anchor_profile": (
                    cluster.human_identity_anchor_profile.model_dump(mode="json")
                    if cluster.human_identity_anchor_profile is not None
                    else {}
                ),
                "human_natural_variation_plan": (
                    cluster.human_natural_variation_plan.model_dump(mode="json")
                    if cluster.human_natural_variation_plan is not None
                    else {}
                ),
                "human_batch_diversity_review": (
                    cluster.human_batch_diversity_review.model_dump(mode="json")
                    if cluster.human_batch_diversity_review is not None
                    else {}
                ),
                "project_identity_anchors": [item.model_dump(mode="json") for item in cluster.project_identity_anchors],
                "strong_reference_continuation_plan": (
                    cluster.strong_reference_continuation_plan.model_dump(mode="json")
                    if cluster.strong_reference_continuation_plan is not None
                    else {}
                ),
                "general_suite_role_plan": (
                    cluster.general_suite_role_plan.model_dump(mode="json")
                    if cluster.general_suite_role_plan is not None
                    else {}
                ),
                "mode_execution_policy": (
                    cluster.mode_execution_policy.model_dump(mode="json")
                    if cluster.mode_execution_policy is not None
                    else {}
                ),
                "role_specific_generation_plan": (
                    cluster.role_specific_generation_plan.model_dump(mode="json")
                    if cluster.role_specific_generation_plan is not None
                    else {}
                ),
                "mode_differentiation_review": (
                    cluster.mode_differentiation_review.model_dump(mode="json")
                    if cluster.mode_differentiation_review is not None
                    else {}
                ),
                "batch_identity_diversity_review": (
                    cluster.batch_identity_diversity_review.model_dump(mode="json")
                    if cluster.batch_identity_diversity_review is not None
                    else {}
                ),
                "human_photorealism_guidance": (
                    cluster.human_photorealism_guidance.model_dump(mode="json")
                    if cluster.human_photorealism_guidance is not None
                    else {}
                ),
                "human_realism_plugin": dict(cluster.metadata.get("human_realism_plugin") or {}),
                "strong_reference_closure_package": (
                    cluster.strong_reference_closure_package.model_dump(mode="json")
                    if cluster.strong_reference_closure_package is not None
                    else {}
                ),
                "resolved_reference_policy_package": (
                    cluster.resolved_reference_policy_package.model_dump(mode="json")
                    if cluster.resolved_reference_policy_package is not None
                    else {}
                ),
                "subject_continuity_asset_package": (
                    cluster.subject_continuity_asset_package.model_dump(mode="json")
                    if cluster.subject_continuity_asset_package is not None
                    else {}
                ),
                "adaptive_reference_selection_plan": (
                    cluster.adaptive_reference_selection_plan.model_dump(mode="json")
                    if cluster.adaptive_reference_selection_plan is not None
                    else {}
                ),
                "identity_drift_guard_plan": (
                    cluster.identity_drift_guard_plan.model_dump(mode="json")
                    if cluster.identity_drift_guard_plan is not None
                    else {}
                ),
                "identity_repair_strategy_plan": (
                    cluster.identity_repair_strategy_plan.model_dump(mode="json")
                    if cluster.identity_repair_strategy_plan is not None
                    else {}
                ),
                "mode_quality_profile": (
                    cluster.mode_quality_profile.model_dump(mode="json")
                    if cluster.mode_quality_profile is not None
                    else {}
                ),
                "anti_ai_face_review": (
                    cluster.anti_ai_face_review.model_dump(mode="json")
                    if cluster.anti_ai_face_review is not None
                    else {}
                ),
                "visual_commercial_quality_review": (
                    cluster.visual_commercial_quality_review.model_dump(mode="json")
                    if cluster.visual_commercial_quality_review is not None
                    else {}
                ),
                "identity_hero_selection_plan": (
                    cluster.identity_hero_selection_plan.model_dump(mode="json")
                    if cluster.identity_hero_selection_plan is not None
                    else {}
                ),
                "strict_visual_review_policy": (
                    cluster.strict_visual_review_policy.model_dump(mode="json")
                    if cluster.strict_visual_review_policy is not None
                    else {}
                ),
                "portrait_bone_structure_lock": (
                    cluster.portrait_bone_structure_lock.model_dump(mode="json")
                    if cluster.portrait_bone_structure_lock is not None
                    else {}
                ),
                "styling_delta_policy": (
                    cluster.styling_delta_policy.model_dump(mode="json")
                    if cluster.styling_delta_policy is not None
                    else {}
                ),
                "portrait_identity_similarity_review": (
                    cluster.portrait_identity_similarity_review.model_dump(mode="json")
                    if cluster.portrait_identity_similarity_review is not None
                    else {}
                ),
                "bone_structure_retry_patch": (
                    cluster.bone_structure_retry_patch.model_dump(mode="json")
                    if cluster.bone_structure_retry_patch is not None
                    else {}
                ),
                "visual_consistency_guard": cluster.consistency_guard.model_dump(mode="json"),
                "visual_quality_review": cluster.quality_review.model_dump(mode="json"),
                "visual_quality_review_reports": [item.model_dump(mode="json") for item in cluster.quality_review_reports],
                "auto_retry_decisions": [item.model_dump(mode="json") for item in cluster.auto_retry_decisions],
                "commercial_output_selection": (
                    cluster.commercial_output_selection.model_dump(mode="json")
                    if cluster.commercial_output_selection is not None
                    else {}
                ),
                "negative_visual_memory": list(cluster.negative_visual_memory),
                "template_consistency_policy": dict(cluster.template_consistency_policy),
                "capability_activation_plan_summary": (
                    {
                        "plan_id": activation_plan.get("plan_id"),
                        "active_capability_ids": list(activation_plan.get("dependency_order") or []),
                        "activation_mode": activation_plan.get("activation_mode"),
                    }
                    if activation_plan
                    else {}
                ),
            },
            constraints=constraints,
            audit_trail=[
                "collected V3 visual child capabilities into a single cluster result",
                f"child modules: {', '.join(cluster.child_module_ids) or 'none'}",
            ],
            metadata={
                "cluster_id": cluster.cluster_id,
                "child_module_ids": cluster.child_module_ids,
                "project_id": cluster.project_id,
                "context_version": cluster.context_version,
                "v3_native_visual_capability_cluster": True,
                "advanced_reference_controls": dict(cluster.metadata.get("advanced_reference_controls") or {}),
                "reference_policy_package_id": cluster.metadata.get("reference_policy_package_id"),
                "capability_activation_plan_id": activation_plan.get("plan_id") if activation_plan else None,
                "active_capability_ids": list(activation_plan.get("dependency_order") or []) if activation_plan else [],
            },
        )

    @staticmethod
    def _is_brain_owned_forward_execution(capability_input: CapabilityInput) -> bool:
        metadata = capability_input.metadata if isinstance(capability_input.metadata, dict) else {}
        plan = metadata.get("capability_activation_plan")
        return bool(
            metadata.get("brain_owned_forward_execution")
            and isinstance(plan, dict)
            and str(plan.get("activation_mode") or "").lower() == "enforced"
            and not bool(metadata.get("legacy_prompt_compatibility_record"))
        )

    @classmethod
    def _quarantine_forward_local_creative_language(
        cls,
        cluster: VisualCapabilityClusterResult,
    ) -> VisualCapabilityClusterResult:
        """Remove retired local prompt prose without erasing review evidence.

        The canonical finalizer receives facts, opaque bindings and normalized
        issue codes.  It must never see a second local phrase catalogue from a
        capability result.  Keep this at the capability boundary so a future
        caller cannot accidentally re-enable the old route by reading a
        metadata field that happens to survive downstream filtering.
        """

        payload = cls._strip_forward_local_creative_text(cluster.model_dump(mode="json"))
        metadata = dict(payload.get("metadata") or {})
        metadata["forward_local_creative_language_quarantined"] = True
        metadata["forward_prompt_owner"] = "remote_v3_llm_brain"
        payload["metadata"] = metadata
        return VisualCapabilityClusterResult.model_validate(payload)

    @classmethod
    def _strip_forward_local_creative_text(cls, value: Any, *, parent_key: str | None = None) -> Any:
        if isinstance(value, list):
            return [cls._strip_forward_local_creative_text(item, parent_key=parent_key) for item in value]
        if not isinstance(value, dict):
            return value

        sanitized: dict[str, Any] = {}
        for raw_key, nested in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if lowered in FORWARD_LOCAL_CREATIVE_TEXT_FIELDS:
                sanitized[key] = []
            elif lowered == "retry_patch_templates" or (lowered == "templates" and parent_key == "retry"):
                sanitized[key] = {}
            elif lowered == "retry_patch":
                # Keep the shape auditable, but never retain local repair
                # language.  Review reason codes live beside this field.
                sanitized[key] = {"evidence_only": True} if nested else {}
            else:
                sanitized[key] = cls._strip_forward_local_creative_text(nested, parent_key=lowered)
        return sanitized

    def _build_cluster(self, capability_input: CapabilityInput) -> VisualCapabilityClusterResult:
        human_realism_active = self._capability_active(capability_input, "human_realism")
        portrait_identity_active = self._capability_active(capability_input, "portrait_identity")
        product_identity_active = self._capability_active(capability_input, "product_identity")
        reference_policy_active = self._capability_active(capability_input, "reference_channel_policy")
        suite_direction_active = self._capability_active(capability_input, "suite_direction")
        subject_continuity_active = portrait_identity_active or product_identity_active
        result_map = {result.module_id: result for result in capability_input.prior_results}
        child_ids = [module_id for module_id in result_map if module_id in VISUAL_CLUSTER_CHILD_MODULE_IDS]
        project_context = _as_dict(capability_input.metadata.get("project_context_snapshot"))
        selected_outputs = _dict_list(project_context.get("selected_output_assets"))
        selected_references = _dict_list(project_context.get("selected_reference_assets"))
        uploaded_references = _dict_list(project_context.get("uploaded_reference_assets"))
        negative_notes = _dedupe(
            [
                *_string_list(project_context.get("rejected_style_tags")),
                *_string_list(project_context.get("negative_direction_notes")),
            ]
        )

        asset_analyses = _dict_list(_fact(result_map, "asset_role_analyzer", "asset_analyses", []))
        binding_plan = _as_dict(_fact(result_map, "asset_binding_planner", "asset_binding_plan", {}))
        bindings = _dict_list(binding_plan.get("bindings"))
        selected_cases = _dict_list(_fact(result_map, "case_library_retriever", "selected_cases", []))
        grammar_lock = _as_dict(_fact(result_map, "visual_grammar_lock", "visual_grammar_lock", {}))
        history_reference = _as_dict(_fact(result_map, "history_reference", "history_reference", {}))
        compiled_constraints = _as_dict(_fact(result_map, "prompt_constraint_compiler", "compiled_constraints", {}))
        output_review = _as_dict(_fact(result_map, "output_review", "output_review", {}))
        allow_product_language = self._allow_product_language(
            capability_input=capability_input,
            project_context=project_context,
            selected_references=selected_references,
            uploaded_references=uploaded_references,
        )
        template_policy = self._template_consistency_policy(
            template_id=str(project_context.get("template_id") or capability_input.metadata.get("template_id") or ""),
            scenario_id=capability_input.scenario_id,
            user_input=capability_input.user_input,
            allow_product_language=allow_product_language,
        )
        strong_bindings = self._strong_reference_bindings(
            capability_input=capability_input,
            selected_outputs=selected_outputs,
            selected_references=selected_references,
            uploaded_references=uploaded_references,
            template_policy=template_policy,
            allow_product_language=allow_product_language,
        )
        subject_type = self._subject_type_from_policy(template_policy, allow_product_language=allow_product_language)
        project_id = str(project_context.get("project_id") or "") or None
        if subject_continuity_active:
            identity_drift_guard = self.identity_drift_guard.build(
                project_id=project_id,
                job_id=capability_input.job_id,
                subject_type=subject_type,
                strong_bindings=strong_bindings,
                selected_outputs=selected_outputs,
            )
            subject_asset_package = self.subject_asset_pack_builder.build(
                project_id=project_id,
                job_id=capability_input.job_id,
                subject_type=subject_type,
                strong_bindings=strong_bindings,
                drift_guard=identity_drift_guard,
            )
            adaptive_reference_plan = self.adaptive_reference_retriever.build(
                project_id=project_id,
                job_id=capability_input.job_id,
                user_input=capability_input.user_input,
                package=subject_asset_package,
            )
            strong_bindings = self.adaptive_reference_retriever.order_bindings(
                strong_bindings,
                adaptive_reference_plan,
            )
        else:
            identity_drift_guard = IdentityDriftGuardPlan(
                plan_id=stable_id("inactive_identity_drift_guard", capability_input.job_id),
                project_id=project_id,
                job_id=capability_input.job_id,
                metadata={"inactive_reason": "subject_identity_capability_not_active"},
            )
            subject_asset_package = SubjectContinuityAssetPackage(
                package_id=stable_id("inactive_subject_asset_package", capability_input.job_id),
                project_id=project_id,
                job_id=capability_input.job_id,
                metadata={"inactive_reason": "subject_identity_capability_not_active"},
            )
            adaptive_reference_plan = AdaptiveReferenceSelectionPlan(
                plan_id=stable_id("inactive_adaptive_reference", capability_input.job_id),
                project_id=project_id,
                job_id=capability_input.job_id,
                metadata={"inactive_reason": "subject_identity_capability_not_active"},
            )
        repair_strategy_metadata = {
            **_as_dict(project_context.get("metadata")),
            **dict(capability_input.metadata or {}),
        }
        identity_repair_strategy = (
            self.identity_repair_strategy_router.build(
                project_id=project_id,
                job_id=capability_input.job_id,
                package=subject_asset_package,
                metadata=repair_strategy_metadata,
            )
            if portrait_identity_active
            else IdentityRepairStrategyPlan(
                plan_id=stable_id("inactive_identity_repair", capability_input.job_id),
                project_id=project_id,
                job_id=capability_input.job_id,
                metadata={"inactive_reason": "portrait_identity_not_active"},
            )
        )
        advanced_reference_controls = self._advanced_reference_controls(
            capability_input=capability_input,
            project_context=project_context,
            strong_bindings=strong_bindings,
            subject_type=subject_type,
        )
        reference_policy_package = (
            self.reference_channel_policy_module.resolve(
                project_id=str(project_context.get("project_id") or "") or None,
                job_id=capability_input.job_id,
                user_input=capability_input.user_input,
                subject_type=subject_type,
                template_id=str(project_context.get("template_id") or capability_input.metadata.get("template_id") or ""),
                strong_bindings=strong_bindings,
                selected_outputs=selected_outputs,
                advanced_reference_controls=advanced_reference_controls,
                metadata=capability_input.metadata,
            )
            if reference_policy_active
            else ResolvedReferencePolicyPackage(
                package_id=stable_id("inactive_reference_policy", capability_input.job_id),
                project_id=project_id,
                job_id=capability_input.job_id,
                metadata={"inactive_reason": "reference_channel_policy_not_active"},
            )
        )
        effective_asset_analyses = self._asset_analyses_for_reference_policy(
            asset_analyses,
            reference_policy_package,
        )

        selected_output_ids = _dedupe(_identity(item, "output_id", "asset_id", "candidate_id") for item in selected_outputs)
        context_reference_ids = _dedupe(
            _identity(item, "asset_ref_id", "asset_id", "output_id", "reference_id")
            for item in [*selected_references, *uploaded_references]
        )
        binding_reference_ids = _dedupe(str(item.get("asset_id") or "") for item in bindings)
        reference_asset_ids = _dedupe([*context_reference_ids, *binding_reference_ids])

        style_signals = self._style_signals(
            capability_input=capability_input,
            project_context=project_context,
            selected_cases=selected_cases,
            grammar_lock=grammar_lock,
            history_reference=history_reference,
            asset_analyses=effective_asset_analyses,
        )
        style_signals = _sanitize_general_visual_terms(style_signals, allow_product_language=allow_product_language)
        composition_rules = _sanitize_general_visual_terms(
            self._composition_rules(selected_cases, grammar_lock, compiled_constraints),
            allow_product_language=allow_product_language,
        )
        layout_notes = _sanitize_general_visual_terms(
            self._layout_notes(grammar_lock, compiled_constraints),
            allow_product_language=allow_product_language,
        )
        negative_rules = _sanitize_general_visual_terms(
            self._negative_rules(negative_notes, history_reference, compiled_constraints, bindings),
            allow_product_language=allow_product_language,
        )
        profile = VisualGrammarProfile(
            profile_id=stable_id(
                "visual_grammar_profile",
                capability_input.scenario_id,
                capability_input.user_input,
                ",".join(selected_output_ids),
                ",".join(reference_asset_ids),
            ),
            scenario_id=capability_input.scenario_id,
            style_signals=style_signals,
            composition_rules=composition_rules,
            palette_notes=self._palette_notes(effective_asset_analyses, project_context),
            lighting_notes=self._lighting_notes(style_signals, capability_input.user_input),
            lens_notes=self._lens_notes(capability_input.user_input, selected_cases),
            layout_notes=layout_notes,
            locked_elements=_sanitize_general_visual_terms(
                _string_list(grammar_lock.get("locked_visual_grammar")),
                allow_product_language=allow_product_language,
            ),
            replaceable_elements=_sanitize_general_visual_terms(
                _string_list(grammar_lock.get("replaceable_semantic_content")),
                allow_product_language=allow_product_language,
            ),
            negative_rules=negative_rules,
            reference_asset_ids=reference_asset_ids,
            selected_output_ids=selected_output_ids,
            confidence=self._confidence(
                selected_outputs=selected_outputs,
                references=[*selected_references, *uploaded_references],
                child_ids=child_ids,
                style_signals=style_signals,
            ),
            metadata={
                "case_count": len(selected_cases),
                "uploaded_asset_analysis_count": len(asset_analyses),
                "reference_authorized_style_analysis_count": len(effective_asset_analyses),
                "binding_count": len(bindings),
                "selected_output_count": len(selected_outputs),
                "commerce_terms_allowed": allow_product_language,
            },
        )
        snapshot = self._project_snapshot(
            project_context=project_context,
            selected_output_ids=selected_output_ids,
            selected_references=selected_references,
            uploaded_references=uploaded_references,
            profile=profile,
        )
        binding_profile = self._binding_profile(bindings, selected_references, uploaded_references, strong_bindings)
        identity_locks = self._identity_lock_profiles(
            capability_input=capability_input,
            project_context=project_context,
            profile=profile,
            strong_bindings=strong_bindings,
            template_policy=template_policy,
            allow_product_language=allow_product_language,
            reference_policy_package=reference_policy_package,
        ) if subject_continuity_active else []
        human_anchor, human_variation = self._human_variation_profiles(
            capability_input=capability_input,
            project_context=project_context,
            selected_outputs=selected_outputs,
            selected_references=selected_references,
            uploaded_references=uploaded_references,
            identity_locks=identity_locks,
            reference_policy_package=reference_policy_package,
        ) if (human_realism_active or portrait_identity_active) else (None, None)
        project_identity_anchors = self.identity_anchor_builder.build(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            selected_outputs=selected_outputs,
            strong_bindings=strong_bindings,
            identity_locks=identity_locks,
            template_policy=template_policy,
            reference_policy_package=reference_policy_package,
        ) if subject_continuity_active else []
        strong_reference_plan = self.strong_reference_planner.build(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            anchors=project_identity_anchors,
            strong_bindings=strong_bindings,
        ) if subject_continuity_active else None
        requested_count = self._requested_image_count(capability_input, project_context)
        variation_mode = self._effective_variation_mode(capability_input, project_context)
        human_photorealism = (
            self.human_photorealism_layer.build(
                project_id=str(project_context.get("project_id") or "") or None,
                job_id=capability_input.job_id,
                scenario_id=capability_input.scenario_id,
                template_id=str(project_context.get("template_id") or capability_input.metadata.get("template_id") or ""),
                user_input=capability_input.user_input,
                subject_type=subject_type,
                variation_mode=variation_mode,
                has_identity_reference=bool(project_identity_anchors or strong_bindings),
                metadata=self._human_realism_plugin_metadata(
                    capability_input=capability_input,
                    project_context=project_context,
                    template_policy=template_policy,
                    subject_type=subject_type,
                    variation_mode=variation_mode,
                ),
            )
            if human_realism_active
            else None
        )
        strong_reference_plan = self._apply_human_photorealism_to_reference_plan(
            strong_reference_plan,
            human_photorealism,
        )
        strong_reference_closure = self.strong_reference_closure_builder.build(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            subject_type=subject_type,
            continuation_plan=strong_reference_plan,
            anchors=project_identity_anchors,
            identity_locks=identity_locks,
            human_photorealism=human_photorealism,
            reference_policy_package=reference_policy_package,
        ) if subject_continuity_active else StrongReferenceClosurePackage(
            closure_id=stable_id("inactive_strong_reference_closure", capability_input.job_id),
            project_id=project_id,
            job_id=capability_input.job_id,
            metadata={"inactive_reason": "subject_identity_capability_not_active"},
        )
        strong_reference_closure = self._apply_advanced_reference_controls_to_closure(
            strong_reference_closure,
            advanced_reference_controls,
        )
        mode_quality_profile = self.mode_quality_profile_builder.build(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            mode=variation_mode,
            subject_type=subject_type,
        )
        suite_role_plan = (
            self.suite_director.build(
                project_id=str(project_context.get("project_id") or "") or None,
                job_id=capability_input.job_id,
                user_input=capability_input.user_input,
                variation_mode=variation_mode,
                requested_image_count=requested_count,
                has_identity_anchor=bool(project_identity_anchors),
                subject_type=subject_type,
                scenario_id=capability_input.scenario_id,
                template_id=str(project_context.get("template_id") or capability_input.metadata.get("template_id") or ""),
            )
            if suite_direction_active
            else self._inactive_suite_role_plan(capability_input, project_id, variation_mode, requested_count)
        )
        role_specific_plan = self._role_specific_generation_plan_from_suite(suite_role_plan)
        role_specific_plan = self._apply_human_photorealism_to_role_plan(role_specific_plan, human_photorealism)
        role_specific_plan = self._apply_strong_reference_closure_to_role_plan(
            role_specific_plan,
            strong_reference_closure,
        )
        role_specific_plan = self._apply_reference_channel_policy_to_role_plan(
            role_specific_plan,
            reference_policy_package,
        )
        role_specific_plan = self._apply_mode_quality_profile_to_role_plan(role_specific_plan, mode_quality_profile)
        identity_hero_plan = self._identity_hero_selection_plan(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            subject_type=subject_type,
            requested_count=requested_count,
            role_specific_plan=role_specific_plan,
            selected_outputs=selected_outputs,
            strong_bindings=strong_bindings,
            project_identity_anchors=project_identity_anchors,
        ) if subject_continuity_active else None
        role_specific_plan = self._apply_identity_hero_selection_to_role_plan(
            role_specific_plan,
            identity_hero_plan,
        )
        subject_identity_card = self._subject_identity_card(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            subject_type=subject_type,
            user_input=capability_input.user_input,
            requested_count=requested_count,
            selected_outputs=selected_outputs,
            strong_bindings=strong_bindings,
            project_identity_anchors=project_identity_anchors,
            identity_hero_plan=identity_hero_plan,
            human_photorealism=human_photorealism,
            reference_policy_package=reference_policy_package,
        ) if subject_continuity_active else None
        subject_identity_card = self._apply_advanced_reference_controls_to_subject_identity_card(
            subject_identity_card,
            advanced_reference_controls,
        )
        if portrait_identity_active:
            portrait_bone_lock = self.portrait_identity_layer.build_lock(
                project_id=str(project_context.get("project_id") or "") or None,
                job_id=capability_input.job_id,
                subject_type=subject_type,
                subject_identity_card=subject_identity_card,
                strong_bindings=strong_bindings,
            )
            styling_delta_policy = self.portrait_identity_layer.build_styling_policy(
                project_id=str(project_context.get("project_id") or "") or None,
                job_id=capability_input.job_id,
                user_input=capability_input.user_input,
                lock=portrait_bone_lock,
            )
            portrait_reference_policy = self.portrait_identity_layer.build_reference_influence_policy(
                project_id=str(project_context.get("project_id") or "") or None,
                job_id=capability_input.job_id,
                lock=portrait_bone_lock,
                styling_policy=styling_delta_policy,
                reference_policy_package=reference_policy_package,
            )
            portrait_balance_policy = self.portrait_identity_layer.build_reference_balance_policy(
                project_id=str(project_context.get("project_id") or "") or None,
                job_id=capability_input.job_id,
                user_input=capability_input.user_input,
                selected_outputs=selected_outputs,
                lock=portrait_bone_lock,
                reference_policy=portrait_reference_policy,
            )
        else:
            portrait_bone_lock = None
            styling_delta_policy = None
            portrait_reference_policy = None
            portrait_balance_policy = None
        role_specific_plan = self._apply_subject_identity_card_to_role_plan(
            role_specific_plan,
            subject_identity_card,
        )
        role_specific_plan = self._apply_portrait_bone_structure_to_role_plan(
            role_specific_plan,
            portrait_bone_lock,
            styling_delta_policy,
            portrait_reference_policy,
            portrait_balance_policy,
        )
        role_specific_plan = self._apply_advanced_reference_controls_to_role_plan(
            role_specific_plan,
            advanced_reference_controls,
        )
        beautiful_realism_review = self._beautiful_realism_balance_review(
            capability_input=capability_input,
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            subject_type=subject_type,
            subject_identity_card=subject_identity_card,
            human_photorealism=human_photorealism,
        ) if human_realism_active else None
        strict_review_policy = self._strict_visual_review_policy(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            subject_type=subject_type,
            variation_mode=variation_mode,
            identity_hero_plan=identity_hero_plan,
            subject_identity_card=subject_identity_card,
            portrait_bone_lock=portrait_bone_lock,
            styling_delta_policy=styling_delta_policy,
            portrait_reference_policy=portrait_reference_policy,
            beautiful_realism_review=beautiful_realism_review,
            human_photorealism=human_photorealism,
            role_specific_plan=role_specific_plan,
            advanced_reference_controls=advanced_reference_controls,
            reference_policy_package=reference_policy_package,
        )
        role_specific_plan = self._apply_strict_visual_review_policy_to_role_plan(
            role_specific_plan,
            strict_review_policy,
        )
        mode_review = self.mode_role_director.review(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            role_plan=role_specific_plan,
            generated_candidates=self._candidate_payloads(capability_input),
        ) if suite_direction_active else ModeDifferentiationReview(
            review_id=stable_id("inactive_mode_review", capability_input.job_id),
            project_id=project_id,
            job_id=capability_input.job_id,
            status="not_applicable",
            metadata={"inactive_reason": "suite_direction_not_active"},
        )
        batch_review = self.batch_reviewer.build(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            anchors=project_identity_anchors,
            suite_role_plan=suite_role_plan,
            human_variation_plan=human_variation,
            generated_candidates=self._candidate_payloads(capability_input),
        ) if (human_realism_active or portrait_identity_active) else BatchIdentityDiversityReview(
            review_id=stable_id("inactive_batch_identity_review", capability_input.job_id),
            project_id=project_id,
            job_id=capability_input.job_id,
            status="not_applicable",
            metadata={"inactive_reason": "human_and_portrait_capabilities_not_active"},
        )
        consistency_guard = self._consistency_guard(
            project_context=project_context,
            snapshot=snapshot,
            profile=profile,
            binding_profile=binding_profile,
            strong_reference_plan=strong_reference_plan,
            suite_role_plan=suite_role_plan,
            batch_review=batch_review,
        )
        quality_review = self._quality_review(output_review, compiled_constraints, consistency_guard)
        anti_ai_face_review = self.human_photorealism_layer.review(
            guidance=human_photorealism,
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            issue_codes=self._anti_ai_face_issue_codes(capability_input),
        ) if human_photorealism is not None else None
        portrait_similarity_review = self.portrait_identity_layer.build_review(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            output_id=self._first_candidate_output_id(capability_input),
            lock=portrait_bone_lock,
            styling_policy=styling_delta_policy,
            issue_codes=self._doc86_identity_issue_codes(capability_input),
            confidence=self._doc86_review_confidence(capability_input),
        ) if portrait_identity_active else None
        portrait_style_review = self.portrait_identity_layer.build_style_separation_review(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            output_id=self._first_candidate_output_id(capability_input),
            lock=portrait_bone_lock,
            reference_policy=portrait_reference_policy,
            issue_codes=self._doc87_reference_boundary_issue_codes(capability_input),
            confidence=self._doc86_review_confidence(capability_input),
        ) if portrait_identity_active else None
        portrait_balance_review = self.portrait_identity_layer.build_balance_review(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            output_id=self._first_candidate_output_id(capability_input),
            balance_policy=portrait_balance_policy,
            issue_codes=self._doc88_reference_balance_issue_codes(capability_input),
            confidence=self._doc86_review_confidence(capability_input),
        ) if portrait_identity_active else None
        bone_retry_patch = (
            BoneStructureRetryPatch.model_validate(portrait_similarity_review.retry_patch)
            if portrait_similarity_review
            and portrait_similarity_review.retry_patch
            and portrait_similarity_review.status == "fail_retryable"
            else None
        )
        reference_retry_patch = (
            ReferenceOverinheritanceRetryPatch.model_validate(portrait_style_review.retry_patch)
            if portrait_style_review
            and portrait_style_review.retry_patch
            and portrait_style_review.status == "fail_retryable"
            else None
        )
        balance_retry_patch = (
            PortraitReferenceBalanceRetryPatch.model_validate(portrait_balance_review.retry_patch)
            if portrait_balance_review
            and portrait_balance_review.retry_patch
            and portrait_balance_review.status == "fail_retryable"
            else None
        )
        quality_reports = self._quality_review_reports(
            capability_input=capability_input,
            quality_review=quality_review,
            consistency_guard=consistency_guard,
            identity_locks=identity_locks,
            anti_ai_face_review=anti_ai_face_review,
            beautiful_realism_review=beautiful_realism_review,
            strict_review_policy=strict_review_policy,
            portrait_identity_review=portrait_similarity_review,
            portrait_style_review=portrait_style_review,
            portrait_balance_review=portrait_balance_review,
            bone_structure_retry_patch=bone_retry_patch,
            reference_overinheritance_retry_patch=reference_retry_patch,
            portrait_reference_balance_retry_patch=balance_retry_patch,
        )
        retry_decisions = self._auto_retry_decisions(capability_input, quality_reports)
        commercial_quality_review = self.commercial_quality_reviewer.build(
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            variation_mode=variation_mode,
            subject_type=subject_type,
            quality_reports=quality_reports,
            mode_review=mode_review,
            batch_review=batch_review,
            strong_reference_plan=strong_reference_plan,
            role_specific_plan=role_specific_plan,
            human_photorealism=human_photorealism,
            anti_ai_face_review=anti_ai_face_review,
        )
        commercial_selection = self._commercial_output_selection(
            capability_input,
            quality_reports,
            identity_hero_plan=identity_hero_plan,
        )
        negative_memory = self._negative_visual_memory(project_context, quality_reports)
        has_evidence = bool(
            child_ids
            or selected_output_ids
            or reference_asset_ids
            or style_signals
            or negative_notes
            or capability_input.uploaded_assets
        )
        active_child_ids = _dedupe(
            [
                *child_ids,
                "human_photorealism_layer" if human_photorealism and human_photorealism.applies else "",
                STRONG_REFERENCE_CLOSURE_MODULE_ID if strong_reference_closure.active else "",
                MODE_QUALITY_PROFILE_MODULE_ID,
                "identity_hero_selector" if identity_hero_plan and identity_hero_plan.applies else "",
                "subject_identity_card" if subject_identity_card and subject_identity_card.applies else "",
                "beautiful_realism_balance_review" if beautiful_realism_review and beautiful_realism_review.applies else "",
                "strict_visual_review_policy" if strict_review_policy and strict_review_policy.applies else "",
                "portrait_bone_structure_identity_lock" if portrait_bone_lock and portrait_bone_lock.applies else "",
                "portrait_reference_identity_style_separator"
                if portrait_reference_policy and portrait_reference_policy.applies
                else "",
                "portrait_reference_balance_policy"
                if portrait_balance_policy and portrait_balance_policy.applies
                else "",
                ADVANCED_REFERENCE_PRIORITY_CONTROLS_MODULE_ID
                if advanced_reference_controls.get("applies")
                else "",
                REFERENCE_CHANNEL_POLICY_MODULE_ID if reference_policy_package.applies else "",
                SUBJECT_CONTINUITY_ASSET_PACK_MODULE_ID if subject_asset_package.applies else "",
                ADAPTIVE_REFERENCE_RETRIEVER_MODULE_ID if adaptive_reference_plan.applies else "",
                IDENTITY_DRIFT_GUARD_MODULE_ID if identity_drift_guard.applies else "",
                IDENTITY_REPAIR_STRATEGY_MODULE_ID if identity_repair_strategy.applies else "",
                "anti_ai_face_review" if anti_ai_face_review and anti_ai_face_review.applies else "",
                "commercial_quality_review",
            ]
        )
        return VisualCapabilityClusterResult(
            cluster_id=stable_id(
                VISUAL_CAPABILITY_CLUSTER_ID,
                capability_input.job_id,
                snapshot.snapshot_id,
                profile.profile_id,
            ),
            version=self.version,
            scenario_id=capability_input.scenario_id,
            project_id=snapshot.project_id,
            context_version=snapshot.context_version,
            child_module_ids=active_child_ids,
            profile=profile,
            project_snapshot=snapshot,
            reference_binding_profile=binding_profile,
            identity_lock_profiles=identity_locks,
            human_identity_anchor_profile=human_anchor,
            human_natural_variation_plan=human_variation,
            human_batch_diversity_review=HumanBatchDiversityReview(applies=bool(human_variation and human_variation.applies)),
            project_identity_anchors=project_identity_anchors,
            strong_reference_continuation_plan=strong_reference_plan,
            general_suite_role_plan=suite_role_plan,
            mode_execution_policy=role_specific_plan.policy,
            role_specific_generation_plan=role_specific_plan,
            mode_differentiation_review=mode_review,
            batch_identity_diversity_review=batch_review,
            human_photorealism_guidance=human_photorealism,
            strong_reference_closure_package=strong_reference_closure,
            mode_quality_profile=mode_quality_profile,
            anti_ai_face_review=anti_ai_face_review,
            visual_commercial_quality_review=commercial_quality_review,
            consistency_guard=consistency_guard,
            quality_review=quality_review,
            quality_review_reports=quality_reports,
            auto_retry_decisions=retry_decisions,
            commercial_output_selection=commercial_selection,
            identity_hero_selection_plan=identity_hero_plan,
            subject_identity_card=subject_identity_card,
            beautiful_realism_balance_review=beautiful_realism_review,
            strict_visual_review_policy=strict_review_policy,
            portrait_bone_structure_lock=portrait_bone_lock,
            styling_delta_policy=styling_delta_policy,
            portrait_reference_influence_policy=portrait_reference_policy,
            portrait_reference_balance_policy=portrait_balance_policy,
            portrait_identity_similarity_review=portrait_similarity_review,
            portrait_identity_style_separation_review=portrait_style_review,
            portrait_reference_balance_review=portrait_balance_review,
            bone_structure_retry_patch=bone_retry_patch,
            reference_overinheritance_retry_patch=reference_retry_patch,
            portrait_reference_balance_retry_patch=balance_retry_patch,
            resolved_reference_policy_package=reference_policy_package,
            subject_continuity_asset_package=subject_asset_package,
            adaptive_reference_selection_plan=adaptive_reference_plan,
            identity_drift_guard_plan=identity_drift_guard,
            identity_repair_strategy_plan=identity_repair_strategy,
            negative_visual_memory=negative_memory,
            template_consistency_policy=template_policy,
            has_visual_evidence=has_evidence,
            user_visible_summary=self._user_visible_summary(snapshot, profile, consistency_guard),
            mode_role_plan_reconciled_to_series=True,
            mode_role_plan_series_asset_count=requested_count,
            metadata={
                "positive_context_from_selected_outputs_only": consistency_guard.positive_context_from_selected_outputs_only,
                "unselected_candidates_excluded": consistency_guard.unselected_candidates_excluded,
                "project_context_present": bool(project_context),
                "strong_reference_binding_count": len(strong_bindings),
                "identity_lock_count": len(identity_locks),
                "project_identity_anchor_count": len(project_identity_anchors),
                "strong_reference_plan_active": strong_reference_plan is not None,
                "general_suite_role_count": len(suite_role_plan.roles) if suite_role_plan else 0,
                "mode_role_director_active": True,
                "mode_differentiation_status": mode_review.status,
                "batch_identity_diversity_status": batch_review.status if batch_review else None,
                "human_natural_variation_applies": bool(human_variation and human_variation.applies),
                "human_photorealism_applies": bool(human_photorealism and human_photorealism.applies),
                "human_realism_plugin": (
                    dict(human_photorealism.metadata.get("human_realism_plugin") or {})
                    if human_photorealism
                    else {}
                ),
                "strong_reference_closure_active": strong_reference_closure.active,
                "mode_quality_profile_id": mode_quality_profile.profile_id,
                "anti_ai_face_review_status": anti_ai_face_review.status if anti_ai_face_review else None,
                "commercial_quality_status": commercial_quality_review.status if commercial_quality_review else None,
                "identity_hero_selector_status": identity_hero_plan.status if identity_hero_plan else None,
                "subject_identity_card_status": subject_identity_card.status if subject_identity_card else None,
                "beautiful_realism_balance_status": beautiful_realism_review.status if beautiful_realism_review else None,
                "strict_visual_review_policy_active": bool(strict_review_policy and strict_review_policy.applies),
                "portrait_bone_structure_lock_active": bool(portrait_bone_lock and portrait_bone_lock.applies),
                "portrait_reference_influence_policy_active": bool(
                    portrait_reference_policy and portrait_reference_policy.applies
                ),
                "portrait_identity_similarity_status": portrait_similarity_review.status if portrait_similarity_review else None,
                "portrait_identity_style_separation_status": portrait_style_review.status if portrait_style_review else None,
                "portrait_reference_balance_status": portrait_balance_review.status if portrait_balance_review else None,
                "quality_review_report_count": len(quality_reports),
                "auto_retry_decision_count": len(retry_decisions),
                "advanced_reference_controls": advanced_reference_controls,
                "doc90_advanced_reference_controls": bool(advanced_reference_controls.get("applies")),
                "doc93_reference_channel_policy": bool(reference_policy_package.applies),
                "reference_policy_package_id": reference_policy_package.package_id,
                "subject_continuity_asset_package_id": subject_asset_package.package_id,
                "adaptive_reference_selection_plan_id": adaptive_reference_plan.plan_id,
                "identity_drift_guard_status": identity_drift_guard.status,
                "identity_repair_strategy": identity_repair_strategy.strategy,
                "doc67_default_role_count_aligned": True,
                "capability_activation_enforced": self._activation_mode(capability_input) == "enforced",
                "active_capability_ids": self._active_capability_ids(capability_input),
            },
        )

    def _activation_plan(self, capability_input: CapabilityInput) -> dict[str, Any]:
        value = capability_input.metadata.get("capability_activation_plan")
        return dict(value) if isinstance(value, dict) else {}

    def _activation_mode(self, capability_input: CapabilityInput) -> str:
        plan = self._activation_plan(capability_input)
        return str(plan.get("activation_mode") or "legacy").lower()

    def _active_capability_ids(self, capability_input: CapabilityInput) -> list[str]:
        plan = self._activation_plan(capability_input)
        return [str(item) for item in plan.get("dependency_order", []) if str(item).strip()]

    def _capability_active(self, capability_input: CapabilityInput, capability_id: str) -> bool:
        if self._activation_mode(capability_input) != "enforced":
            return True
        return capability_id in self._active_capability_ids(capability_input)

    def _capability_profile(self, capability_input: CapabilityInput, capability_id: str) -> str | None:
        for item in self._activation_plan(capability_input).get("active_capabilities", []):
            if isinstance(item, dict) and item.get("capability_id") == capability_id:
                return str(item.get("selected_profile") or "balanced")
        return None

    def _inactive_suite_role_plan(
        self,
        capability_input: CapabilityInput,
        project_id: str | None,
        variation_mode: str,
        requested_count: int,
    ) -> GeneralSuiteRolePlan:
        return GeneralSuiteRolePlan(
            plan_id=stable_id("inactive_suite_direction", capability_input.job_id),
            project_id=project_id,
            job_id=capability_input.job_id,
            variation_mode=variation_mode,
            requested_image_count=requested_count,
            metadata={"applies": False, "inactive_reason": "not_in_activation_plan"},
        )

    def _allow_product_language(
        self,
        *,
        capability_input: CapabilityInput,
        project_context: dict[str, Any],
        selected_references: list[dict[str, Any]],
        uploaded_references: list[dict[str, Any]],
    ) -> bool:
        metadata = {
            **capability_input.metadata,
            "scenario_id": capability_input.scenario_id,
            "user_input": capability_input.user_input,
        }
        if project_context.get("template_id"):
            metadata["template_id"] = project_context.get("template_id")
        return product_language_allowed(
            template_id=metadata.get("template_id"),
            scenario_id=capability_input.scenario_id,
            industry=metadata.get("industry"),
            user_input=capability_input.user_input,
            metadata=metadata,
            uploaded_assets=capability_input.uploaded_assets,
            reference_assets=[*selected_references, *uploaded_references],
        )

    def _style_signals(
        self,
        *,
        capability_input: CapabilityInput,
        project_context: dict[str, Any],
        selected_cases: list[dict[str, Any]],
        grammar_lock: dict[str, Any],
        history_reference: dict[str, Any],
        asset_analyses: list[dict[str, Any]],
    ) -> list[str]:
        signals: list[str] = []
        signals.extend(_string_list(project_context.get("confirmed_visual_tone")))
        signals.extend(_string_list(history_reference.get("visual_tone")))
        for case in selected_cases:
            signals.extend(_string_list(case.get("style_tags")))
            signals.extend(_string_list(case.get("visual_signals")))
        signals.extend(_string_list(grammar_lock.get("visual_signal_brief")))
        for analysis in asset_analyses:
            signals.extend(_string_list(analysis.get("style_signals")))
        text = capability_input.user_input.lower()
        human_style_context = _looks_like_human_prompt(capability_input.user_input)
        for keyword, label in [
            ("summer", "bright summer atmosphere"),
            ("portrait", "portrait-led subject treatment"),
            ("fresh", "fresh clean mood"),
            ("premium", "premium real-camera portrait finish" if human_style_context else "premium polished finish"),
            ("clean", "clean refined composition"),
        ]:
            if keyword in text:
                signals.append(label)
        for keyword, label in [
            ("夏", "bright summer atmosphere"),
            ("清凉", "cool fresh mood"),
            ("清爽", "fresh clean mood"),
            ("高级", "premium polished finish"),
            ("美女", "portrait-led subject treatment"),
            ("写真", "editorial portrait photography"),
        ]:
            if keyword in capability_input.user_input:
                signals.append(label)
        for keyword, label in [
            ("\u590f", "bright summer atmosphere"),
            ("\u6e05\u51c9", "cool fresh mood"),
            ("\u6e05\u723d", "fresh clean mood"),
            ("\u9ad8\u7ea7", "premium real-camera portrait finish" if human_style_context else "premium polished finish"),
            ("\u7f8e\u5973", "portrait-led subject treatment"),
            ("\u5199\u771f", "natural editorial portrait photography"),
        ]:
            if keyword in capability_input.user_input:
                signals.append(label)
        if human_style_context and "premium real-camera portrait finish" in signals:
            signals = [signal for signal in signals if signal != "premium polished finish"]
        return _dedupe(signals)[:14]

    def _asset_analyses_for_reference_policy(
        self,
        asset_analyses: list[dict[str, Any]],
        package: ResolvedReferencePolicyPackage | None,
    ) -> list[dict[str, Any]]:
        if package is None or not package.applies:
            return asset_analyses
        policies_by_asset = {policy.source_asset_id: policy for policy in package.policies}
        effective: list[dict[str, Any]] = []
        for analysis in asset_analyses:
            asset_id = _identity(analysis, "asset_id", "asset_ref_id", "source_id")
            policy = policies_by_asset.get(asset_id)
            if policy is None:
                role = str(analysis.get("role") or "").lower()
                policy = next(
                    (
                        item
                        for item in package.policies
                        if ("face" in role and item.source_role == "portrait_identity_reference")
                        or ("product" in role and item.source_role == "product_identity_reference")
                    ),
                    None,
                )
            if policy is None:
                effective.append(analysis)
                continue
            style_authorized = any(
                getattr(policy, channel) in {"hard", "medium", "soft"}
                for channel in (
                    "lighting_color",
                    "scene_background",
                    "camera_composition",
                    "mood_art_direction",
                    "style_finish",
                )
            )
            if style_authorized:
                effective.append(analysis)
        return effective

    def _composition_rules(
        self,
        selected_cases: list[dict[str, Any]],
        grammar_lock: dict[str, Any],
        compiled_constraints: dict[str, Any],
    ) -> list[str]:
        rules: list[str] = []
        for case in selected_cases:
            rules.extend(_string_list(case.get("composition_tags")))
        if grammar_lock:
            rules.append("preserve the reusable visual grammar while changing only requested subject details")
        for item in _dict_list(compiled_constraints.get("layout_constraints")):
            rules.append(str(item.get("constraint_type") or "").replace("_", " "))
        return _dedupe(rules)[:10]

    def _palette_notes(self, asset_analyses: list[dict[str, Any]], project_context: dict[str, Any]) -> list[str]:
        notes = _string_list(project_context.get("confirmed_color_logic"))
        for analysis in asset_analyses:
            palette = _dict_list(analysis.get("palette"))
            if palette:
                notes.append("dominant palette " + ", ".join(str(item.get("hex")) for item in palette[:3] if item.get("hex")))
        return _dedupe(notes)[:8]

    def _lighting_notes(self, style_signals: list[str], user_input: str) -> list[str]:
        notes = [item for item in style_signals if "light" in item.lower() or "bright" in item.lower()]
        if "清凉" in user_input or "清爽" in user_input:
            notes.append("cool bright daylight feeling")
        if "夏" in user_input:
            notes.append("summer daylight freshness")
        return _dedupe(notes)[:8]

    def _lens_notes(self, user_input: str, selected_cases: list[dict[str, Any]]) -> list[str]:
        notes: list[str] = []
        text = user_input.lower()
        if any(token in text for token in ["portrait", "girl", "woman"]) or any(token in user_input for token in ["美女", "写真", "人像"]):
            notes.extend(["natural portrait lens feel", "clear face and upper-body subject priority"])
        for case in selected_cases:
            if "cover" in _string_list(case.get("use_case_tags")):
                notes.append("cover-safe framing")
        return _dedupe(notes)[:6]

    def _layout_notes(self, grammar_lock: dict[str, Any], compiled_constraints: dict[str, Any]) -> list[str]:
        notes: list[str] = []
        notes.extend(_string_list(grammar_lock.get("locked_visual_grammar")))
        for item in _dict_list(compiled_constraints.get("prompt_constraints")):
            constraint_type = str(item.get("constraint_type") or "").replace("_", " ")
            if constraint_type:
                notes.append(constraint_type)
        return _dedupe(notes)[:10]

    def _negative_rules(
        self,
        negative_notes: list[str],
        history_reference: dict[str, Any],
        compiled_constraints: dict[str, Any],
        bindings: list[dict[str, Any]],
    ) -> list[str]:
        rules = list(negative_notes)
        rules.extend(_string_list(history_reference.get("rejected_style_tags")))
        for item in _dict_list(compiled_constraints.get("negative_constraints")):
            value = item.get("value")
            rules.append(str(value if value is not None else item.get("constraint_type")))
        for binding in bindings:
            rules.extend(_string_list(binding.get("forbidden_transformations")))
        return _dedupe(rules)[:12]

    def _project_snapshot(
        self,
        *,
        project_context: dict[str, Any],
        selected_output_ids: list[str],
        selected_references: list[dict[str, Any]],
        uploaded_references: list[dict[str, Any]],
        profile: VisualGrammarProfile,
    ) -> ProjectVisualGrammarSnapshot:
        selected_reference_ids = _dedupe(
            _identity(item, "asset_ref_id", "asset_id", "output_id", "reference_id")
            for item in selected_references
        )
        uploaded_reference_ids = _dedupe(
            _identity(item, "asset_ref_id", "asset_id", "reference_id")
            for item in uploaded_references
        )
        continuity_strength = "strong" if selected_output_ids else "medium" if selected_reference_ids or uploaded_reference_ids else "weak"
        return ProjectVisualGrammarSnapshot(
            snapshot_id=stable_id(
                "project_visual_grammar_snapshot",
                project_context.get("project_id"),
                project_context.get("context_version"),
                ",".join(selected_output_ids),
                ",".join(selected_reference_ids),
                ",".join(uploaded_reference_ids),
            ),
            project_id=str(project_context.get("project_id") or "") or None,
            context_version=str(project_context.get("context_version") or "") or None,
            positive_anchor_output_ids=selected_output_ids,
            active_reference_ids=selected_reference_ids,
            uploaded_reference_ids=uploaded_reference_ids,
            style_rules=_dedupe([*_string_list(project_context.get("confirmed_visual_tone")), *profile.style_signals])[:10],
            composition_rules=_dedupe([*_string_list(project_context.get("confirmed_layout_logic")), *profile.composition_rules])[:10],
            lighting_rules=profile.lighting_notes,
            palette_rules=_dedupe([*_string_list(project_context.get("confirmed_color_logic")), *profile.palette_notes])[:8],
            negative_directions=_dedupe([*profile.negative_rules, *_string_list(project_context.get("negative_direction_notes"))])[:12],
            continuity_strength=continuity_strength,
            metadata={
                "positive_context_from_selected_outputs_only": bool(
                    _as_dict(project_context.get("metadata")).get("positive_context_from_selected_outputs_only", True)
                ),
                "unselected_candidates_excluded": bool(
                    _as_dict(project_context.get("metadata")).get("unselected_candidates_excluded", True)
                ),
            },
        )

    def _template_consistency_policy(
        self,
        *,
        template_id: str,
        scenario_id: str,
        user_input: str,
        allow_product_language: bool,
    ) -> dict[str, Any]:
        text = f"{template_id} {scenario_id} {user_input}".lower()
        # Character identity is expensive and must have positive evidence.  In
        # particular, do not let terms such as ``fair-faced concrete`` or
        # ``atmospheric perspective`` promote an otherwise non-person General
        # request into the portrait execution path.
        portrait_like = _contains_latin_terms(text, ["portrait", "woman", "girl", "person", "model", "face"]) or any(
            token in user_input for token in ["人像", "写真", "美女", "人物", "脸", "发型"]
        )
        if allow_product_language:
            return {
                "policy_id": "product_truth",
                "primary_priority": "product_identity",
                "strong_reference_default": "hard",
                "identity_lock_default": "product",
                "review_focus": ["product_identity_drift", "unrelated_product_or_object", "visible_text_artifact"],
            }
        if _contains_latin_terms(text, ["photographer"]) or portrait_like:
            return {
                "policy_id": "portrait_identity",
                "primary_priority": "character_identity",
                "strong_reference_default": "hard",
                "identity_lock_default": "character",
                "review_focus": ["identity_drift", "hair_or_outfit_drift", "camera_lighting_drift"],
            }
        return {
            "policy_id": "general_visual_grammar",
            "primary_priority": "style_and_visual_grammar",
            "strong_reference_default": "medium",
            "identity_lock_default": "generic",
            "review_focus": ["style_drift", "composition_mismatch", "visible_text_artifact"],
        }

    def _subject_type_from_policy(self, template_policy: dict[str, Any], *, allow_product_language: bool) -> str:
        if allow_product_language:
            return "product"
        lock_default = str(template_policy.get("identity_lock_default") or "").strip().lower()
        if lock_default == "product":
            return "product"
        if lock_default == "character":
            return "character"
        return "generic"

    def _human_realism_plugin_metadata(
        self,
        *,
        capability_input: CapabilityInput,
        project_context: dict[str, Any],
        template_policy: dict[str, Any],
        subject_type: str,
        variation_mode: str,
    ) -> dict[str, Any]:
        uploaded_asset_roles = []
        for asset in capability_input.uploaded_assets:
            role = asset.role.value if hasattr(asset.role, "value") else asset.role
            uploaded_asset_roles.append(
                {
                    "asset_id": asset.asset_id,
                    "role": role,
                    "filename": asset.filename,
                    "mime_type": asset.mime_type,
                    "metadata": dict(asset.metadata or {}),
                }
            )
        activation_plan = self._activation_plan(capability_input)
        frozen_profile = capability_input.metadata.get("visual_task_profile")
        frozen_profile = dict(frozen_profile) if isinstance(frozen_profile, dict) else {}
        rendering_intent = frozen_profile.get("rendering_intent")
        rendering_intent = dict(rendering_intent) if isinstance(rendering_intent, dict) else {}
        developmental_age_intent = str(
            frozen_profile.get("developmental_age_intent") or "ambiguous"
        ).strip()
        active_capability_ids = {
            str(item).strip()
            for item in activation_plan.get("dependency_order", [])
            if str(item).strip()
        }
        return {
            **dict(capability_input.metadata or {}),
            "doc91_human_realism_plugin": True,
            "subject_type": subject_type,
            "variation_mode": variation_mode,
            "template_policy": dict(template_policy or {}),
            "product_profile": dict(capability_input.product_profile or {}),
            "uploaded_asset_roles": uploaded_asset_roles,
            # This is a frozen semantic/activation binding, not a local
            # request to compose Human Realism words into a provider prompt.
            "human_realism_execution_required": "human_realism" in active_capability_ids,
            "frozen_rendering_intent": rendering_intent,
            "frozen_developmental_age_intent": developmental_age_intent,
            "project_context_summary": {
                "project_id": project_context.get("project_id"),
                "template_id": project_context.get("template_id"),
                "selected_output_count": len(project_context.get("selected_output_assets") or []),
                "selected_reference_count": len(project_context.get("selected_references") or []),
                "uploaded_reference_count": len(project_context.get("uploaded_references") or []),
            },
        }

    def _role_specific_generation_plan_from_suite(
        self,
        suite_role_plan: GeneralSuiteRolePlan,
    ) -> RoleSpecificGenerationPlan:
        payload = suite_role_plan.metadata.get("role_specific_generation_plan")
        if isinstance(payload, dict):
            try:
                return RoleSpecificGenerationPlan.model_validate(payload)
            except Exception:
                pass
        return self.mode_role_director.build(
            project_id=suite_role_plan.project_id,
            job_id=suite_role_plan.job_id,
            user_input="",
            mode=suite_role_plan.variation_mode,
            requested_image_count=suite_role_plan.requested_image_count,
            subject_type="generic",
            scenario_id=None,
            template_id=None,
            has_identity_anchor=False,
        )

    def _apply_human_photorealism_to_reference_plan(
        self,
        plan: StrongReferenceContinuationPlan | None,
        guidance: HumanPhotorealismGuidance | None,
    ) -> StrongReferenceContinuationPlan | None:
        if plan is None or guidance is None or not guidance.applies:
            return plan
        if bool(guidance.metadata.get("brain_owned_forward_execution")):
            # Doc136: the frozen semantic contract reaches Brain sign-off
            # directly.  Do not even construct a local reference/prompt
            # overlay in a new enforced path.
            return plan.model_copy(
                update={
                    "metadata": {
                        **dict(plan.metadata),
                        "human_photorealism_layer": guidance.guidance_id,
                        "human_photorealism_forward_semantic_contract": True,
                    }
                }
            )
        return plan.model_copy(
            update={
                "prompt_additions": _dedupe(
                    [
                        *plan.prompt_additions,
                        "Human Realism may improve skin, eyes, expression, proportion, and camera response, but it must not expand which reference channels are inherited.",
                    ]
                )[:12],
                "negative_additions": _dedupe(
                    [
                        *plan.negative_additions,
                        *guidance.reference_do_not_inherit_rules,
                        *guidance.negative_prompt_fragments,
                    ]
                )[:18],
                "metadata": {
                    **dict(plan.metadata),
                    "human_photorealism_layer": guidance.guidance_id,
                    "anti_ai_face_do_not_inherit": True,
                },
            }
        )

    def _apply_human_photorealism_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        guidance: HumanPhotorealismGuidance | None,
    ) -> RoleSpecificGenerationPlan:
        if guidance is None or not guidance.applies:
            return plan
        if bool(guidance.metadata.get("brain_owned_forward_execution")):
            # A role plan may retain opaque lineage, but cannot acquire a
            # second Human Realism prompt language path after Brain ownership
            # has been frozen.
            return plan.model_copy(
                update={
                    "metadata": {
                        **dict(plan.metadata),
                        "human_photorealism_layer": guidance.guidance_id,
                        "human_photorealism_forward_semantic_contract": True,
                    }
                }
            )
        return plan.model_copy(
            update={
                "prompt_additions": _dedupe([*plan.prompt_additions, *guidance.positive_prompt_fragments])[:16],
                "negative_additions": _dedupe([*plan.negative_additions, *guidance.negative_prompt_fragments])[:18],
                "metadata": {
                    **dict(plan.metadata),
                    "human_photorealism_layer": guidance.guidance_id,
                    "human_photorealism_applies": True,
                },
            }
        )

    def _apply_strong_reference_closure_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        closure: StrongReferenceClosurePackage | None,
    ) -> RoleSpecificGenerationPlan:
        if closure is None or not closure.active:
            return plan
        prompt_additions = _dedupe(
            [
                *plan.prompt_additions,
                *closure.provider_prompt_rules,
                *closure.identity_keep_rules[:4],
                *closure.style_keep_rules[:3],
            ]
        )[:20]
        negative_additions = _dedupe(
            [
                *plan.negative_additions,
                *closure.negative_prompt_rules,
                *closure.forbidden_drift[:5],
            ]
        )[:24]
        return plan.model_copy(
            update={
                "prompt_additions": prompt_additions,
                "negative_additions": negative_additions,
                "metadata": {
                    **dict(plan.metadata),
                    "strong_reference_closure_package": closure.closure_id,
                    "strong_reference_reference_strength": closure.reference_strength,
                    "strong_reference_provider_required_ids": list(closure.provider_reference_required_ids),
                    "strong_reference_prompt_only_ids": list(closure.prompt_only_reference_ids),
                },
            }
        )

    def _apply_reference_channel_policy_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        package: ResolvedReferencePolicyPackage | None,
    ) -> RoleSpecificGenerationPlan:
        if package is None or not package.applies:
            return plan
        updated_recipes = []
        for recipe in plan.role_recipes:
            updated_recipes.append(
                recipe.model_copy(
                    update={
                        "must_keep_rules": _dedupe([*recipe.must_keep_rules, *package.provider_prompt_rules[:5]]),
                        "must_not_rules": _dedupe([*recipe.must_not_rules, *package.provider_negative_rules[:8]]),
                        "review_checks": _dedupe([*recipe.review_checks, *package.review_targets[:6]]),
                        "metadata": {
                            **dict(recipe.metadata),
                            "doc93_reference_channel_policy": True,
                            "reference_policy_package_id": package.package_id,
                        },
                    }
                )
            )
        return plan.model_copy(
            update={
                "role_recipes": updated_recipes,
                "prompt_additions": _dedupe([*plan.prompt_additions, *package.provider_prompt_rules])[:36],
                "negative_additions": _dedupe([*plan.negative_additions, *package.provider_negative_rules])[:44],
                "metadata": {
                    **dict(plan.metadata),
                    "doc93_reference_channel_policy": True,
                    "resolved_reference_policy_package": package.model_dump(mode="json"),
                },
            }
        )

    def _apply_mode_quality_profile_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        profile: ModeQualityProfile | None,
    ) -> RoleSpecificGenerationPlan:
        if profile is None:
            return plan
        return plan.model_copy(
            update={
                "prompt_additions": _dedupe([*plan.prompt_additions, *profile.prompt_guidance])[:22],
                "negative_additions": _dedupe([*plan.negative_additions, *profile.negative_guidance])[:26],
                "metadata": {
                    **dict(plan.metadata),
                    "mode_quality_profile": profile.profile_id,
                    "mode_quality_label": profile.user_visible_label,
                    "mode_review_priorities": list(profile.review_priorities),
                    "mode_pass_conditions": list(profile.pass_conditions),
                    "mode_retry_triggers": list(profile.retry_triggers),
                },
            }
        )

    def _identity_hero_selection_plan(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        requested_count: int,
        role_specific_plan: RoleSpecificGenerationPlan,
        selected_outputs: list[dict[str, Any]],
        strong_bindings: list[StrongReferenceBinding],
        project_identity_anchors: list[ProjectIdentityAnchor],
    ) -> IdentityHeroSelectionPlan:
        applies = bool(subject_type == "character" and requested_count >= 2)
        if not applies:
            return IdentityHeroSelectionPlan(
                plan_id=stable_id("identity_hero_selection_plan", project_id, job_id, subject_type, "not_applicable"),
                project_id=project_id,
                job_id=job_id,
                subject_type=subject_type,
            )
        role_keys = [recipe.role_key for recipe in role_specific_plan.role_recipes]
        primary_role_key = next(
            (
                key
                for key in ("cover_hero", "candidate_best_frame", "subject_focus", "hero_subject")
                if key in role_keys
            ),
            role_keys[0] if role_keys else None,
        )
        selected = selected_outputs[0] if selected_outputs else {}
        selected_output_id = _identity(selected, "output_id", "asset_id", "candidate_id") if selected else None
        selected_candidate_id = str(selected.get("candidate_id") or "") or None if selected else None
        has_user_anchor = bool(selected_outputs or strong_bindings or project_identity_anchors)
        strategy = "use_user_selected_identity_master" if has_user_anchor else "first_output_identity_master_then_expand"
        status = "user_anchor_ready" if has_user_anchor else "planned_first_output_anchor"
        prompt_additions = [
            "Identity hero selection: before expanding the suite, establish one clear identity master frame for the person.",
            "The identity master must show a readable real face, natural head/body proportion, broad face shape, eye spacing, nose-mouth relationship, jawline direction, and age impression; styling channels remain governed separately.",
            (
                "Use the user-selected identity/reference image as the strongest identity master; do not override it with an automatic anchor."
                if has_user_anchor
                else "For text-only multi-image human suites, treat the first generated portrait as the temporary identity master for later outputs in this job."
            ),
            "Later suite images must preserve the identity master while changing role-specific pose, expression, camera distance, angle, crop, or scene depth.",
        ]
        negative_additions = [
            "identity master with hidden or unreadable face",
            "identity master with distorted face or body proportion",
            "identity drift after the master frame",
            "face swapped between suite images",
            "same exact master still copied into every role",
            "over-retouched identity master",
            "beauty-app identity master",
        ]
        review_checks = [
            "one image is usable as the identity master",
            "identity master has readable face and natural proportions",
            "later images keep face geometry, feature relationships, age direction, and body identity from the identity master",
            "suite roles vary without replacing the person",
        ]
        return IdentityHeroSelectionPlan(
            plan_id=stable_id("identity_hero_selection_plan", project_id, job_id, strategy, primary_role_key, selected_output_id),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            status=status,
            subject_type=subject_type,
            strategy=strategy,
            primary_role_key=primary_role_key,
            identity_master_role_keys=[key for key in [primary_role_key, "subject_focus"] if key],
            selected_output_id=selected_output_id,
            selected_candidate_id=selected_candidate_id,
            provider_reference_expected=not has_user_anchor,
            prompt_additions=prompt_additions,
            negative_additions=negative_additions,
            review_checks=review_checks,
            user_visible_summary=[
                "V3 will first lock one clear person direction.",
                "Then it will make the rest of the set follow that person without copying the exact same frame.",
            ],
            metadata={
                "doc": "75",
                "has_user_anchor": has_user_anchor,
                "selected_output_count": len(selected_outputs),
                "strong_binding_count": len(strong_bindings),
                "project_identity_anchor_count": len(project_identity_anchors),
            },
        )

    def _apply_identity_hero_selection_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        identity_plan: IdentityHeroSelectionPlan | None,
    ) -> RoleSpecificGenerationPlan:
        if identity_plan is None or not identity_plan.applies:
            return plan
        updated_recipes = []
        for recipe in plan.role_recipes:
            is_primary = recipe.role_key == identity_plan.primary_role_key
            metadata = {
                **dict(recipe.metadata),
                "identity_hero_candidate": is_primary,
                "identity_hero_selection_plan_id": identity_plan.plan_id,
            }
            prompt_pressure = recipe.prompt_pressure
            must_keep = list(recipe.must_keep_rules)
            must_not = list(recipe.must_not_rules)
            if is_primary:
                prompt_pressure = (
                    f"{prompt_pressure} Identity master frame: make the person readable, attractive, real-camera, "
                    "and stable enough to guide the rest of the suite."
                )
                must_keep = _dedupe(
                    [
                        *must_keep,
                        "readable real face for identity master selection",
                        "natural head, neck, shoulder, and body proportion",
                    ]
                )
            else:
                must_keep = _dedupe(
                    [
                        *must_keep,
                        "preserve the identity master face geometry, feature relationships, age direction, and body identity",
                        "vary only the role-specific expression, pose, camera, crop, or scene depth",
                    ]
                )
                must_not = _dedupe([*must_not, "replace the identity master with a different person"])
            updated_recipes.append(
                recipe.model_copy(
                    update={
                        "prompt_pressure": prompt_pressure,
                        "must_keep_rules": must_keep,
                        "must_not_rules": must_not,
                        "negative_pressure": _dedupe([*recipe.negative_pressure, *identity_plan.negative_additions[:5]]),
                        "review_checks": _dedupe([*recipe.review_checks, *identity_plan.review_checks[:4]]),
                        "metadata": metadata,
                    }
                )
            )
        return plan.model_copy(
            update={
                "role_recipes": updated_recipes,
                "prompt_additions": _dedupe([*plan.prompt_additions, *identity_plan.prompt_additions])[:28],
                "negative_additions": _dedupe([*plan.negative_additions, *identity_plan.negative_additions])[:32],
                "metadata": {
                    **dict(plan.metadata),
                    "doc75_identity_hero_selection": True,
                    "identity_hero_selection_plan": identity_plan.model_dump(mode="json"),
                },
            }
        )

    def _subject_identity_card(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        user_input: str,
        requested_count: int,
        selected_outputs: list[dict[str, Any]],
        strong_bindings: list[StrongReferenceBinding],
        project_identity_anchors: list[ProjectIdentityAnchor],
        identity_hero_plan: IdentityHeroSelectionPlan | None,
        human_photorealism: HumanPhotorealismGuidance | None,
        reference_policy_package: ResolvedReferencePolicyPackage | None = None,
    ) -> SubjectIdentityCard:
        applies = subject_type == "character"
        source_output_ids: list[str] = []
        source_candidate_ids: list[str] = []
        source_asset_ids: list[str] = []
        source_anchor_ids: list[str] = []
        source_binding_ids: list[str] = []
        uploaded_identity_bindings = [
            binding
            for binding in strong_bindings
            if binding.use_policy == "identity" and binding.source_type not in {"selected_output", "generated_selected"}
        ]
        if uploaded_identity_bindings:
            source_priority = "strong_reference_binding"
            source_binding_ids = [binding.binding_id for binding in uploaded_identity_bindings]
            source_asset_ids = _dedupe(binding.asset_id for binding in uploaded_identity_bindings if binding.asset_id)
            source_output_ids = _dedupe(binding.output_id for binding in uploaded_identity_bindings if binding.output_id)
            status = "strong_reference_identity_ready"
        elif selected_outputs:
            source_priority = "user_selected_output"
            source_output_ids = _dedupe(_identity(item, "output_id", "asset_id") for item in selected_outputs)
            source_candidate_ids = _dedupe(_identity(item, "candidate_id") for item in selected_outputs)
            source_asset_ids = _dedupe(_identity(item, "asset_id") for item in selected_outputs)
            status = "user_selected_identity_ready"
        elif strong_bindings:
            source_priority = "strong_reference_binding"
            source_binding_ids = [binding.binding_id for binding in strong_bindings]
            source_asset_ids = _dedupe(binding.asset_id for binding in strong_bindings if binding.asset_id)
            source_output_ids = _dedupe(binding.output_id for binding in strong_bindings if binding.output_id)
            status = "strong_reference_identity_ready"
        elif project_identity_anchors:
            source_priority = "project_identity_anchor"
            source_anchor_ids = [anchor.anchor_id for anchor in project_identity_anchors]
            source_output_ids = _dedupe(
                output_id
                for anchor in project_identity_anchors
                for output_id in anchor.source_output_ids
            )
            source_asset_ids = _dedupe(
                asset_id
                for anchor in project_identity_anchors
                for asset_id in anchor.source_asset_ids
            )
            status = "project_identity_card_ready"
        elif identity_hero_plan and identity_hero_plan.applies:
            source_priority = "planned_first_output_anchor"
            source_output_ids = _dedupe([identity_hero_plan.selected_output_id])
            source_candidate_ids = _dedupe([identity_hero_plan.selected_candidate_id])
            status = "planned_from_identity_hero"
        else:
            source_priority = "none"
            status = "not_applicable"
            applies = False
        structured_appearance = _reference_channel_is_locked(reference_policy_package, "wardrobe_structure")
        hair_locked = _reference_channel_is_locked(reference_policy_package, "hair_direction")

        identity_keep_rules = [
            "preserve broad face shape, face width/length ratio, age impression, and individual facial temperament",
            "preserve eye shape and spacing, eyelid direction, eyebrow shape, eyebrow thickness/arc, and awake eye expression",
            "preserve nose-mouth relationship, lip shape, jawline direction, chin scale, cheek volume, and neck/shoulder balance",
            "preserve body type and natural head-to-body proportion",
        ]
        if hair_locked:
            identity_keep_rules.append("preserve the explicitly assigned hair direction")
        appearance_structure_rules = _structured_appearance_rules() if structured_appearance else []
        facial_feature_integrity_rules = [
            "preserve the reference person's existing facial proportions, individual feature design, and own attractiveness; realism or styling must not redesign the face",
            "present the reference eyebrow, eye, eyelid, nose-mouth, and lip relationships attractively through prompt-owned makeup, expression, camera, and light rather than replacing their base geometry",
            "keep soft facial contour without face-slimming distortion, enlarged beauty-filter eyes, or a perfect V-shaped chin",
            "protect the selected person's beautiful feature relationships instead of replacing them with a generic AI face",
        ]
        beautiful_realism_rules = [
            "the reference person's own attractiveness is identity-owned; realism is the rendering method and must not optimize facial geometry",
            "use skin texture, natural light/shadow, real hair strands, fabric folds, and camera texture as realism evidence",
            "preserve reference or explicitly requested complexion through prompt-consistent light and color without demographic defaults",
            "avoid ugly realism: dark muddy skin, tired expression, harsh unflattering shadow, or degraded facial proportions",
        ]
        allowed_variations = [
            "expression",
            "gaze",
            "head angle",
            "pose",
            "gesture",
            "camera distance",
            "camera angle",
            "scene",
            "lighting micro-variation",
            "hair movement",
            "small fabric motion",
        ]
        forbidden_drift = [
            "identity feature drift",
            "ugly eyebrow shape",
            "eye shape or spacing drift",
            "nose-mouth relationship drift",
            "jaw or chin direction drift",
            "realism that makes the subject less attractive",
            "beauty-filter face replacement",
            "generic AI influencer identity",
        ]
        if structured_appearance:
            forbidden_drift.extend(
                [
                    "appearance asset replacement",
                    "garment structure drift",
                    "pattern family drift",
                    "layering drift",
                    "trim or accessory placement drift",
                ]
            )
        prompt_additions = [
            "Subject identity card: preserve identity-critical traits while allowing new expression, pose, camera angle, crop, scene, and hair movement.",
            "Facial-feature aesthetic integrity: preserve the reference person's eye shape/spacing, eyebrow base design, eyelid direction, nose-mouth relationship, jaw/chin direction, cheek volume, and own attractiveness; improve presentation without redesigning geometry.",
            "Beautiful realism balance: keep the reference person's own facial design; create beauty through prompt-owned makeup, expression, camera, light, skin texture, hair, fabric, and natural asymmetry, never facial remodeling.",
        ]
        if structured_appearance:
            prompt_additions.append(
                "Structured appearance lock: keep the same appearance asset structure across the batch; vary pose, camera, expression, crop, and scene without redesigning the garment or styling system."
            )
        if human_photorealism and human_photorealism.applies:
            prompt_additions.append(
                "Human Realism improves rendering quality only and must not expand source-reference inheritance."
            )
        negative_additions = [
            "ugly realism",
            "flattened facial attractiveness",
            "ugly eyebrow shape",
            "drooping or mismatched brows",
            "random eyebrow thickness drift",
            "asymmetric eyes caused by rendering failure",
            "sleepy or dull eye expression",
            "unflattering nose or mouth drift",
            "jaw/chin direction drift",
            "generic AI influencer face",
            "beauty-filter face replacement",
        ]
        if structured_appearance:
            negative_additions.extend(
                [
                    "appearance asset redesign",
                    "new garment cut or layer architecture",
                    "new pattern family",
                    "new trim placement",
                    "unrequested accessory relocation",
                ]
            )
        review_checks = [
            "same-person recognizability remains strong",
            "eyes, eyebrows, nose-mouth relationship, jaw/chin direction, and face ratio remain attractive",
            "skin and light feel real without making the subject look dull, dark, tired, or rough",
            "pose, expression, head angle, and camera angle vary without replacing identity",
        ]
        if structured_appearance:
            review_checks.append("structured appearance asset stays coherent across the set")
        return SubjectIdentityCard(
            card_id=stable_id(
                "subject_identity_card",
                project_id,
                job_id,
                subject_type,
                source_priority,
                ",".join(source_output_ids + source_asset_ids + source_anchor_ids + source_binding_ids),
            ),
            project_id=project_id,
            job_id=job_id,
            applies=applies,
            status=status,
            subject_type=subject_type,
            source_priority=source_priority,
            source_output_ids=source_output_ids,
            source_candidate_ids=source_candidate_ids,
            source_asset_ids=source_asset_ids,
            source_anchor_ids=source_anchor_ids,
            source_binding_ids=source_binding_ids,
            identity_keep_rules=_dedupe(identity_keep_rules),
            facial_feature_integrity_rules=_dedupe(facial_feature_integrity_rules),
            beautiful_realism_rules=_dedupe(beautiful_realism_rules),
            appearance_structure_rules=_dedupe(appearance_structure_rules),
            allowed_variations=_dedupe(allowed_variations),
            forbidden_drift=_dedupe(forbidden_drift),
            reference_requirements=_dedupe(source_asset_ids + source_output_ids + source_binding_ids + source_anchor_ids),
            prompt_additions=_dedupe(prompt_additions),
            negative_additions=_dedupe(negative_additions),
            review_checks=_dedupe(review_checks),
            user_visible_summary=[
                "V3 will keep this person's look consistent.",
                "V3 can still change pose, angle, expression, and scene.",
                "V3 will keep the face attractive and realistic.",
            ],
            metadata={
                "doc": "78",
                "doc84_structured_appearance_lock": structured_appearance,
                "doc93_reference_channel_policy": bool(reference_policy_package and reference_policy_package.applies),
                "reference_policy_package_id": reference_policy_package.package_id if reference_policy_package else None,
                "uploaded_identity_truth_priority": bool(uploaded_identity_bindings),
                "requested_count": requested_count,
                "identity_hero_plan_id": identity_hero_plan.plan_id if identity_hero_plan else None,
                "user_reference_priority": bool(selected_outputs),
            },
        )

    def _apply_subject_identity_card_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        card: SubjectIdentityCard | None,
    ) -> RoleSpecificGenerationPlan:
        if card is None or not card.applies:
            return plan
        updated_recipes = []
        for recipe in plan.role_recipes:
            metadata = {
                **dict(recipe.metadata),
                "subject_identity_card_id": card.card_id,
                "doc78_subject_identity_card": True,
            }
            must_keep = _dedupe(
                [
                    *recipe.must_keep_rules,
                    *card.identity_keep_rules[:3],
                    *card.facial_feature_integrity_rules[:3],
                    *card.appearance_structure_rules[:3],
                ]
            )
            must_not = _dedupe([*recipe.must_not_rules, *card.forbidden_drift[:5]])
            review_checks = _dedupe([*recipe.review_checks, *card.review_checks[:4]])
            updated_recipes.append(
                recipe.model_copy(
                    update={
                        "must_keep_rules": must_keep,
                        "must_not_rules": must_not,
                        "negative_pressure": _dedupe([*recipe.negative_pressure, *card.negative_additions[:6]]),
                        "review_checks": review_checks,
                        "metadata": metadata,
                    }
                )
            )
        return plan.model_copy(
            update={
                "role_recipes": updated_recipes,
                "prompt_additions": _dedupe([*plan.prompt_additions, *card.prompt_additions])[:42],
                "negative_additions": _dedupe([*plan.negative_additions, *card.negative_additions])[:52],
                "metadata": {
                    **dict(plan.metadata),
                    "doc78_subject_identity_card": True,
                    "subject_identity_card": card.model_dump(mode="json"),
                },
            }
        )

    def _apply_portrait_bone_structure_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        lock: PortraitBoneStructureLock | None,
        styling_policy: StylingDeltaPolicy | None,
        reference_policy: PortraitReferenceInfluencePolicy | None,
        balance_policy: PortraitReferenceBalancePolicy | None = None,
    ) -> RoleSpecificGenerationPlan:
        if lock is None or not lock.applies:
            return plan
        prompt_additions = _dedupe(
            [
                *(
                    balance_policy.current_prompt_truth_rules
                    if balance_policy and balance_policy.applies
                    else []
                ),
                *lock.prompt_rules,
                *(styling_policy.prompt_rules if styling_policy and styling_policy.applies else []),
                *(reference_policy.prompt_rules if reference_policy and reference_policy.applies else []),
                *(
                    balance_policy.uploaded_identity_truth_rules
                    if balance_policy and balance_policy.applies
                    else []
                ),
                *(
                    balance_policy.approved_visual_anchor_rules
                    if balance_policy and balance_policy.applies
                    else []
                ),
                *(
                    balance_policy.prompt_ordering_rules
                    if balance_policy and balance_policy.applies
                    else []
                ),
            ]
        )
        negative_additions = _dedupe(
            [
                *(
                    balance_policy.compact_negative_guidance
                    if balance_policy and balance_policy.applies
                    else []
                ),
                *lock.forbidden_geometry_drift[:6],
                *(styling_policy.disallowed_identity_changes if styling_policy and styling_policy.applies else []),
                *(reference_policy.blocked_reference_channels[:6] if reference_policy and reference_policy.applies else []),
            ]
        )
        updated_recipes = []
        for recipe in plan.role_recipes:
            updated_recipes.append(
                recipe.model_copy(
                    update={
                        "must_keep_rules": _dedupe(
                            [
                                *recipe.must_keep_rules,
                                *lock.stable_bone_traits[:4],
                                *lock.stable_feature_relationships[:4],
                            ]
                        ),
                        "must_not_rules": _dedupe([*recipe.must_not_rules, *negative_additions[:8]]),
                        "review_checks": _dedupe([*recipe.review_checks, *lock.review_checks[:4]]),
                        "metadata": {
                            **dict(recipe.metadata),
                            "doc86_portrait_bone_structure_lock": True,
                            "doc87_portrait_reference_identity_style_separation": bool(
                                reference_policy and reference_policy.applies
                            ),
                            "doc88_portrait_reference_balance_policy": bool(
                                balance_policy and balance_policy.applies
                            ),
                            "portrait_bone_structure_lock_id": lock.lock_id,
                            "styling_delta_policy_id": styling_policy.policy_id
                            if styling_policy and styling_policy.applies
                            else None,
                            "portrait_reference_influence_policy_id": reference_policy.policy_id
                            if reference_policy and reference_policy.applies
                            else None,
                            "portrait_reference_balance_policy_id": balance_policy.policy_id
                            if balance_policy and balance_policy.applies
                            else None,
                        },
                    }
                )
            )
        return plan.model_copy(
            update={
                "role_recipes": updated_recipes,
                "prompt_additions": _dedupe([*plan.prompt_additions, *prompt_additions])[:52],
                "negative_additions": _dedupe([*plan.negative_additions, *negative_additions])[:60],
                "metadata": {
                    **dict(plan.metadata),
                    "doc86_portrait_bone_structure_lock": True,
                    "portrait_bone_structure_lock": lock.model_dump(mode="json"),
                    "styling_delta_policy": styling_policy.model_dump(mode="json")
                    if styling_policy and styling_policy.applies
                    else {},
                    "doc87_portrait_reference_identity_style_separation": bool(
                        reference_policy and reference_policy.applies
                    ),
                    "portrait_reference_influence_policy": reference_policy.model_dump(mode="json")
                    if reference_policy and reference_policy.applies
                    else {},
                    "doc88_portrait_reference_balance_policy": bool(balance_policy and balance_policy.applies),
                    "portrait_reference_balance_policy": balance_policy.model_dump(mode="json")
                    if balance_policy and balance_policy.applies
                    else {},
                },
            }
        )

    def _beautiful_realism_balance_review(
        self,
        *,
        capability_input: CapabilityInput,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        subject_identity_card: SubjectIdentityCard | None,
        human_photorealism: HumanPhotorealismGuidance | None,
    ) -> BeautifulRealismBalanceReview:
        applies = subject_type == "character"
        issue_codes = self._beautiful_realism_issue_codes(capability_input)
        retry_patch = self._beautiful_realism_retry_patch(
            issue_codes=issue_codes,
            subject_identity_card=subject_identity_card,
            human_photorealism=human_photorealism,
        )
        review_targets = [
            "same-person identity remains recognizable over time",
            "facial features remain beautiful and harmonious",
            "eyebrow, eye, nose-mouth, jaw/chin, and face-ratio design do not degrade",
            "realism comes from skin/light/hair/fabric/camera texture, not making the face less attractive",
            "beauty does not become AI-filtered, poreless, or generic",
        ]
        return BeautifulRealismBalanceReview(
            review_id=stable_id("beautiful_realism_balance_review", project_id, job_id, ",".join(issue_codes)),
            project_id=project_id,
            job_id=job_id,
            applies=applies,
            status="retry_recommended" if issue_codes else "planned",
            issue_codes=issue_codes,
            severity="medium" if issue_codes else "pass",
            retry_patch=retry_patch if issue_codes else {},
            review_targets=review_targets,
            user_visible_summary=(
                ["V3 will retry with a prettier real-photo balance."]
                if issue_codes
                else ["V3 will keep the face attractive and realistic."]
            ),
            metadata={
                "doc": "78",
                "subject_identity_card_id": subject_identity_card.card_id
                if subject_identity_card and subject_identity_card.applies
                else None,
            },
        )

    def _strict_visual_review_policy(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        variation_mode: str,
        identity_hero_plan: IdentityHeroSelectionPlan | None,
        subject_identity_card: SubjectIdentityCard | None,
        portrait_bone_lock: PortraitBoneStructureLock | None,
        styling_delta_policy: StylingDeltaPolicy | None,
        portrait_reference_policy: PortraitReferenceInfluencePolicy | None,
        beautiful_realism_review: BeautifulRealismBalanceReview | None,
        human_photorealism: HumanPhotorealismGuidance | None,
        role_specific_plan: RoleSpecificGenerationPlan,
        advanced_reference_controls: dict[str, Any] | None = None,
        reference_policy_package: ResolvedReferencePolicyPackage | None = None,
    ) -> StrictVisualReviewPolicy:
        applies = bool(role_specific_plan.role_recipes)
        portrait_identity_applies = any(
            item is not None and item.applies
            for item in (
                identity_hero_plan,
                subject_identity_card,
                portrait_bone_lock,
                styling_delta_policy,
                portrait_reference_policy,
            )
        )
        human_subject_applies = subject_type == "character" or bool(
            human_photorealism and human_photorealism.applies
        )
        retryable = [
            "mode_role_duplication",
            "delivery_suite_role_collapse",
            "role_collapse",
            "low_commercial_finish",
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
            *(
                sorted(reference_channel_issue_codes(reference_policy_package))
                if reference_policy_package and reference_policy_package.applies
                else []
            ),
        ]
        prompt_additions = [
            "Strict visual review closure: do not accept outputs that look generic, role-collapsed, weakly composed, or unsuitable for direct use.",
            "Every output must pass subject truth when evidence is present, role usefulness, and a real-camera or intentionally art-directed finish.",
            "Foundation aesthetic stability: keep one clear subject, intentional framing, balanced exposure, stable color grade, natural contrast, believable depth, and direct-use polish.",
            "Reject technically valid but weak images when they look generic, flat, washed out, muddy, overprocessed, or visually accidental.",
            "If a result has visible marks, incorrect geometry or anatomy when relevant, reference-truth drift, or duplicated role duty, prepare a bounded retry instead of treating it as final.",
        ]
        negative_additions = [
            "generic stock photo finish",
            "weak aesthetic finish",
            "flat low-contrast image",
            "washed-out exposure",
            "muddy underexposed frame",
            "unstable color grade",
            "unclear subject readability",
            "weak depth separation",
            "accidental composition balance",
            "overprocessed HDR finish",
            "synthetic micro detail",
            "strong HDR",
            "over-sharpening",
            "anime",
            "illustration",
            "CG",
            "3D render",
        ]
        if portrait_identity_applies:
            retryable.extend(
                [
                    "identity_drift",
                    "hair_or_outfit_drift",
                    "camera_distance_drift",
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
                    *sorted(DOC86_IDENTITY_ISSUE_CODES),
                    *sorted(DOC87_REFERENCE_BOUNDARY_ISSUE_CODES),
                ]
            )
            prompt_additions.extend(
                [
                    "Beautiful realism rule: the reference person's own attractiveness is identity-owned; render it through real texture, prompt-owned styling, camera, and light without facial optimization or degradation.",
                    "Facial-feature integrity: preserve attractive eyes, eyebrow shape/arc, eyelid direction, nose-mouth relationship, jaw/chin direction, cheek volume, face ratio, and neck/shoulder balance.",
                    "Doc86 portrait identity rule: makeup, wardrobe, styling, lighting, pose, expression, and scene may change, but bone structure and facial-feature relationships must still read as the same person when a portrait reference exists.",
                ]
            )
            negative_additions.extend(
                [
                    "generic AI beauty identity",
                    "ugly realism",
                    "realism made face less attractive",
                    "ugly eyebrow shape",
                    "drooping or mismatched brows",
                    "random eyebrow thickness drift",
                    "sleepy or dull eye expression",
                    "unflattering nose or mouth drift",
                    "jaw or chin direction drift",
                    "facial feature degradation",
                    "same type but different person",
                    "style changed face geometry",
                    "archetype overrode reference identity",
                    "age impression drift",
                ]
            )
        if human_subject_applies:
            retryable.extend(["bad_hands_or_body", "face_artifact"])
            negative_additions.extend(
                [
                    "distorted fingers",
                    "distorted human proportions",
                ]
            )
        if subject_type == "character":
            retryable.extend(
                [
                    "ai_face_render",
                    "plastic_skin",
                    "over_smoothed_skin",
                    "missing_skin_texture",
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
                    "beautified_facial_geometry",
                    "generic_ai_beauty_identity",
                    "suppressed_fair_complexion",
                    "forced_tan_or_bronze_cast",
                    "gray_brown_skin_cast",
                    "head_body_proportion_distortion",
                    "oversized_head",
                    "compressed_neck_shoulders",
                    "unflattering_face_drift",
                    "complexion_direction_drift",
                    "unintended_skin_darkening",
                    "unintended_skin_lightening",
                    "unflattering_skin_color_cast",
                    "age_identity_drift",
                    "age_inappropriate_rendering",
                    "same_expression_repetition",
                    "same_head_angle_repetition",
                    "same_pose_repetition",
                ]
            )
            prompt_additions.extend(
                [
                    "For human portraits, keep the person attractive through real light, expression, styling, and color balance rather than face reshaping, wax skin, or poreless beauty filtering.",
                    "Preserve the reference or explicitly requested complexion and age direction; exposure, color grading, and commercial polish must not impose demographic lightness, tanning, age drift, or beauty-template geometry.",
                ]
            )
            # The retry assembler retains the first strict negatives. Keep the
            # human-only high-signal terms first, but only inside the explicit
            # character branch so generic scenes receive none of them.
            negative_additions = [
                "generic AI beauty identity",
                "poreless glass-like skin",
                "oily shiny face",
                "nose-tip highlight",
                "silicone face",
                "over-smoothed skin",
                "role-collapsed portrait set",
                "same exact expression repeated",
                "same exact head angle repeated",
                "same exact pose repeated",
                "heavy makeup",
                "plastic texture",
                "wrong dress structure",
                *negative_additions,
            ]
        if identity_hero_plan and identity_hero_plan.applies:
            prompt_additions.extend(identity_hero_plan.review_checks[:3])
        if subject_identity_card and subject_identity_card.applies:
            prompt_additions.extend(subject_identity_card.prompt_additions[:4])
            negative_additions.extend(subject_identity_card.negative_additions[:10])
        if portrait_bone_lock and portrait_bone_lock.applies:
            prompt_additions.extend(portrait_bone_lock.prompt_rules[:4])
            negative_additions.extend(portrait_bone_lock.forbidden_geometry_drift[:8])
        if styling_delta_policy and styling_delta_policy.applies:
            prompt_additions.extend(styling_delta_policy.prompt_rules[:3])
            negative_additions.extend(styling_delta_policy.disallowed_identity_changes[:6])
        if portrait_reference_policy and portrait_reference_policy.applies:
            prompt_additions.extend(portrait_reference_policy.prompt_rules[:4])
            negative_additions.extend(portrait_reference_policy.blocked_reference_channels[:8])
        if reference_policy_package and reference_policy_package.applies:
            prompt_additions.extend(reference_policy_package.review_targets[:6])
            prompt_additions.extend(reference_policy_package.provider_prompt_rules[:5])
            negative_additions.extend(reference_policy_package.provider_negative_rules[:10])
        if beautiful_realism_review and beautiful_realism_review.applies:
            prompt_additions.extend(beautiful_realism_review.review_targets[:4])
            negative_additions.extend(_string_list(beautiful_realism_review.retry_patch.get("negative_additions"))[:8])
        if human_photorealism and human_photorealism.applies:
            prompt_additions.extend(human_photorealism.review_targets[:4])
            negative_additions.extend(human_photorealism.negative_prompt_fragments[:8])
        advanced_reference_controls = dict(advanced_reference_controls or {})
        if advanced_reference_controls.get("preserve_person_identity"):
            retryable.extend(
                [
                    "beauty_archetype_overrode_reference",
                    "same_type_but_different_person",
                    "prompt_face_description_replaced_reference_geometry",
                    "generic_sweet_model_replaced_reference",
                ]
            )
            prompt_additions.extend(
                [
                    "Doc90 person priority check: prompt beauty-archetype wording must not replace the uploaded person's facial geometry.",
                    "If the result is merely the same type of attractive person but not the uploaded person, treat it as identity drift.",
                ]
            )
            negative_additions.extend(
                [
                    "beauty archetype overrode reference identity",
                    "same type but different person",
                    "prompt face description replaced uploaded face geometry",
                    "generic sweet model replacing the reference person",
                ]
            )
        if advanced_reference_controls.get("preserve_product_appearance"):
            retryable.extend(
                [
                    "product_silhouette_drift",
                    "label_or_pattern_drift",
                    "material_structure_drift",
                    "generic_product_replacement",
                ]
            )
            prompt_additions.append("Doc90 product priority check: referenced object appearance must not be replaced by a generic product.")
            negative_additions.extend(["product silhouette drift", "label or pattern drift", "material structure drift"])
        if advanced_reference_controls.get("preserve_scene_consistency"):
            retryable.extend(
                [
                    "scene_identity_drift",
                    "background_space_drift",
                    "camera_mood_drift",
                    "reference_scene_replaced",
                ]
            )
            prompt_additions.append("Doc90 scene priority check: referenced background and space continuity must not be replaced.")
            negative_additions.extend(["scene identity drift", "background space drift", "camera mood drift", "reference scene replaced"])
        review_focus = [
            "suite role separation",
            "artifact cleanliness",
            "aesthetic stability",
            "direct-use finish",
        ]
        user_visible_summary = [
            "V3 will preserve a clear usable visual direction.",
            "V3 will reject visible marks, weak finish, or repeated roles.",
        ]
        if portrait_identity_applies:
            review_focus.extend(
                [
                    "identity master selection",
                    "long-term identity continuity",
                    "facial-feature aesthetic integrity",
                    "portrait bone-structure identity",
                    "beautiful realism balance",
                ]
            )
            user_visible_summary[0] = "V3 will preserve the selected identity direction."
        if human_subject_applies:
            review_focus.append("real-camera human realism")
        if subject_type == "character":
            user_visible_summary[1] = "V3 will reject obvious AI-face, repeated clones, or weak suite roles."
        pass_conditions = [
            "declared reference truth is respected when reference evidence exists",
            "suite roles are visually distinguishable for the selected mode",
            "one clear subject reads immediately with intentional framing",
            "exposure, color grade, contrast, depth, and texture feel stable and directed",
            "each reference influences only the visual channels assigned by the resolved reference policy",
            "no visible AI mark, watermark, random text, or fake label",
            "outputs remain directly usable as a polished creative visual set",
        ]
        if portrait_identity_applies:
            pass_conditions.extend(
                [
                    "identity-critical facial feature relationships remain consistent and attractive",
                    "portrait reference outputs preserve the same underlying bone structure while allowing styling changes",
                    "portrait references provide identity truth but do not override prompt-owned lighting, color, scene, camera, wardrobe, or art direction",
                    "artifact cleanup cannot replace the face with a cleaner but less recognizable person",
                ]
            )
        if human_subject_applies:
            pass_conditions.extend(
                [
                    "realism improves skin, light, hair, fabric, and camera texture without degrading beauty",
                    "human subjects avoid plastic skin, beauty-app geometry, and cloned expressions",
                ]
            )
        if advanced_reference_controls.get("preserve_person_identity"):
            pass_conditions.append("prompt face archetypes guide styling only and do not replace uploaded facial geometry")
        if advanced_reference_controls.get("preserve_product_appearance"):
            pass_conditions.append("referenced object/product appearance remains recognizable when product preservation is enabled")
        if advanced_reference_controls.get("preserve_scene_consistency"):
            pass_conditions.append("reference scene continuity remains recognizable when scene preservation is enabled")
        return StrictVisualReviewPolicy(
            policy_id=stable_id("strict_visual_review_policy", project_id, job_id, subject_type, variation_mode),
            project_id=project_id,
            job_id=job_id,
            applies=applies,
            strictness="commercial_strict" if subject_type in {"character", "product"} else "balanced_strict",
            subject_type=subject_type,
            retryable_issue_codes=_dedupe(retryable),
            pass_conditions=pass_conditions,
            prompt_additions=_dedupe(prompt_additions)[:24],
            negative_additions=_dedupe(negative_additions)[:60],
            review_focus=_dedupe(review_focus),
            user_visible_summary=_dedupe(user_visible_summary),
            metadata={
                "doc": "77",
                "extends": ["53", "58", "59", "64", "65", "73", "74", "75", "76", "77", "78", "90", "93"],
                "identity_hero_plan_id": identity_hero_plan.plan_id if identity_hero_plan else None,
                "subject_identity_card_id": subject_identity_card.card_id
                if subject_identity_card and subject_identity_card.applies
                else None,
                "portrait_bone_structure_lock_id": portrait_bone_lock.lock_id
                if portrait_bone_lock and portrait_bone_lock.applies
                else None,
                "styling_delta_policy_id": styling_delta_policy.policy_id
                if styling_delta_policy and styling_delta_policy.applies
                else None,
                "portrait_reference_influence_policy_id": portrait_reference_policy.policy_id
                if portrait_reference_policy and portrait_reference_policy.applies
                else None,
                "doc90_advanced_reference_controls": bool(advanced_reference_controls.get("applies")),
                "advanced_reference_controls": advanced_reference_controls,
                "doc93_reference_channel_policy": bool(reference_policy_package and reference_policy_package.applies),
                "reference_policy_package_id": reference_policy_package.package_id if reference_policy_package else None,
            },
        )

    def _apply_strict_visual_review_policy_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        policy: StrictVisualReviewPolicy | None,
    ) -> RoleSpecificGenerationPlan:
        if policy is None or not policy.applies:
            return plan
        return plan.model_copy(
            update={
                "prompt_additions": _dedupe([*plan.prompt_additions, *policy.prompt_additions])[:36],
                "negative_additions": _dedupe([*plan.negative_additions, *policy.negative_additions])[:44],
                "metadata": {
                    **dict(plan.metadata),
                    "doc75_strict_visual_review": True,
                    "strict_visual_review_policy": policy.model_dump(mode="json"),
                },
            }
        )

    def _strong_reference_bindings(
        self,
        *,
        capability_input: CapabilityInput,
        selected_outputs: list[dict[str, Any]],
        selected_references: list[dict[str, Any]],
        uploaded_references: list[dict[str, Any]],
        template_policy: dict[str, Any],
        allow_product_language: bool,
    ) -> list[StrongReferenceBinding]:
        bindings: list[StrongReferenceBinding] = []
        policy_lock = str(template_policy.get("identity_lock_default") or "generic")
        selected_role = "product_identity_reference" if allow_product_language else (
            "generated_identity_reference" if policy_lock == "character" else "style_reference"
        )
        selected_use_policy = "product_identity" if allow_product_language else ("identity" if policy_lock == "character" else "style")
        for item in selected_outputs:
            source_id = _identity(item, "output_id", "asset_id", "candidate_id", "output_ref_id")
            if not source_id:
                continue
            file_path = str(item.get("file_path") or item.get("metadata", {}).get("file_path") or "").strip() or None
            bindings.append(
                StrongReferenceBinding(
                    binding_id=stable_id("strong_reference_binding", capability_input.job_id, source_id, selected_role),
                    source_type="selected_output",
                    source_id=source_id,
                    asset_id=str(item.get("asset_id") or source_id),
                    output_id=str(item.get("output_id") or source_id),
                    file_path=file_path,
                    preview_url=item.get("preview_url") or item.get("thumbnail_url") or item.get("download_url"),
                    role=selected_role,
                    strength="medium",
                    use_policy=selected_use_policy,
                    lock_targets=self._lock_targets_for_policy(policy_lock, allow_product_language=allow_product_language),
                    provider_input_required=bool(file_path),
                    prompt_only_fallback=not bool(file_path),
                    confidence=0.82 if file_path else 0.58,
                    user_visible_label="已选图片会作为后续强参考" if file_path else "已选图片会作为后续方向参考",
                    metadata={"template_policy": template_policy.get("policy_id"), "selected_output_anchor": True},
                )
            )
        for item in [*selected_references, *uploaded_references]:
            source_id = _identity(item, "asset_ref_id", "asset_id", "output_id", "reference_id")
            if not source_id:
                continue
            role = str(item.get("role") or item.get("use_policy") or "style")
            file_path = str(item.get("file_path") or "").strip() or None
            use_policy = self._reference_use_policy(role, allow_product_language=allow_product_language, policy_lock=policy_lock)
            strength = "hard" if use_policy in {"identity", "product_identity", "brand_asset"} else "medium"
            bindings.append(
                StrongReferenceBinding(
                    binding_id=stable_id("strong_reference_binding", capability_input.job_id, source_id, use_policy),
                    source_type=str(item.get("source_type") or "project_reference"),
                    source_id=source_id,
                    asset_id=str(item.get("asset_id") or item.get("asset_ref_id") or source_id),
                    output_id=item.get("output_id") or item.get("created_from_output_id"),
                    file_path=file_path,
                    preview_url=item.get("preview_url") or item.get("uri") or item.get("download_url"),
                    role=self._reference_role_for_policy(use_policy),
                    strength=strength,
                    use_policy=use_policy,
                    lock_targets=self._lock_targets_for_policy(policy_lock, allow_product_language=allow_product_language),
                    provider_input_required=bool(file_path and strength == "hard"),
                    prompt_only_fallback=not bool(file_path),
                    confidence=0.86 if file_path else 0.54,
                    user_visible_label="项目参考图会参与后续一致性",
                    metadata={"template_policy": template_policy.get("policy_id"), "raw_role": role},
                )
            )
        return self._dedupe_strong_bindings(bindings)

    def _reference_use_policy(self, role: str, *, allow_product_language: bool, policy_lock: str) -> str:
        normalized = str(role or "").lower()
        if "nonhuman_identity_reference" in normalized or "nonhuman_subject_identity" in normalized:
            return "nonhuman_subject_identity"
        if allow_product_language or "product" in normalized:
            return "product_identity"
        if "logo" in normalized or "brand" in normalized:
            return "brand_asset"
        if "composition" in normalized:
            return "composition"
        if "light" in normalized:
            return "lighting"
        if "style" in normalized or "mood" in normalized or "scene" in normalized or "background" in normalized:
            return "style"
        if "face" in normalized or "portrait" in normalized or "identity" in normalized:
            return "identity"
        if policy_lock == "character":
            return "identity"
        return "style"

    def _reference_role_for_policy(self, use_policy: str) -> str:
        return {
            "identity": "generated_identity_reference",
            "nonhuman_subject_identity": "nonhuman_subject_identity_reference",
            "product_identity": "product_identity_reference",
            "brand_asset": "brand_asset_reference",
            "composition": "composition_reference",
            "lighting": "lighting_reference",
        }.get(use_policy, "style_reference")

    def _lock_targets_for_policy(self, policy_lock: str, *, allow_product_language: bool) -> list[str]:
        if allow_product_language or policy_lock == "product":
            return ["shape", "material", "color", "logo_or_label_position", "proportions"]
        if policy_lock == "character":
            return ["face_identity", "body_identity_direction", "natural_complexion_direction"]
        return ["style", "composition", "palette", "lighting"]

    def _dedupe_strong_bindings(self, bindings: list[StrongReferenceBinding]) -> list[StrongReferenceBinding]:
        seen: set[str] = set()
        unique: list[StrongReferenceBinding] = []
        for binding in bindings:
            key = f"{binding.source_type}:{binding.source_id}:{binding.use_policy}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(binding)
        return unique

    def _identity_lock_profiles(
        self,
        *,
        capability_input: CapabilityInput,
        project_context: dict[str, Any],
        profile: VisualGrammarProfile,
        strong_bindings: list[StrongReferenceBinding],
        template_policy: dict[str, Any],
        allow_product_language: bool,
        reference_policy_package: ResolvedReferencePolicyPackage | None = None,
    ) -> list[VisualIdentityLockProfile]:
        if not strong_bindings and not profile.style_signals:
            return []
        policy_lock = str(template_policy.get("identity_lock_default") or "generic")
        structured_appearance = _reference_channel_is_locked(reference_policy_package, "wardrobe_structure")
        hair_locked = _reference_channel_is_locked(reference_policy_package, "hair_direction")
        wardrobe_locked = _reference_channel_is_locked(reference_policy_package, "wardrobe_structure")
        camera_locked = _reference_channel_is_locked(reference_policy_package, "camera_composition")
        lighting_locked = _reference_channel_is_locked(reference_policy_package, "lighting_color")
        if allow_product_language or policy_lock == "product":
            subject_type = "product"
            keep_rules = [
                "preserve product shape, material, color, and proportions",
                "do not invent extra products or unsupported labels",
            ]
            forbidden = ["product identity drift", "unrelated product object", "distorted material or logo"]
            product_lock = {"source": "selected_reference_or_project_context", "priority": "product truth"}
            appearance_structure_lock = {}
        elif policy_lock == "character":
            subject_type = "character"
            keep_rules = [
                "preserve the same person's recognizable face geometry, facial-feature relationships, age direction, and body identity direction",
                "follow the current prompt for hair, makeup, wardrobe, lighting, scene, camera, mood, and style unless a channel is explicitly locked",
            ]
            forbidden = ["face identity drift", "same beauty type but different person"]
            if hair_locked:
                keep_rules.append("keep the explicitly assigned hair direction")
                forbidden.append("locked hair direction drift")
            if wardrobe_locked:
                keep_rules.append("keep the explicitly assigned wardrobe direction")
                forbidden.append("locked wardrobe direction drift")
            product_lock = {}
            appearance_structure_lock = (
                {
                    "preserve": True,
                    "level": "structured_asset",
                    "confidence": 0.74,
                    "preserve_specific_design": True,
                    "preserve_layering": True,
                    "preserve_material_behavior": True,
                    "preserve_pattern_family": True,
                    "preserve_accessory_placement": True,
                }
                if structured_appearance
                else {}
            )
            if structured_appearance:
                keep_rules.append(
                    "keep the same appearance asset structure: silhouette, layer order, neckline/collar, sleeve/cuff, closure or sash, material behavior, pattern family, trim placement, and accessory placement coherent"
                )
                forbidden.extend(
                    [
                        "appearance asset replacement",
                        "garment structure drift",
                        "pattern family drift",
                        "trim or accessory placement drift",
                    ]
                )
        else:
            subject_type = "generic"
            keep_rules = [
                "preserve selected visual style and composition language",
                "keep palette and lighting coherent across the project",
            ]
            forbidden = ["style drift", "unrelated object drift", "composition mismatch"]
            product_lock = {}
            appearance_structure_lock = {}
        binding_ids = [binding.binding_id for binding in strong_bindings]
        prompt_constraints = _dedupe(
            [
                *keep_rules,
                *(profile.composition_rules[:3] if subject_type != "character" or camera_locked else []),
                *(profile.lighting_notes[:3] if subject_type != "character" or lighting_locked else []),
            ]
        )
        negative_constraints = _dedupe([*forbidden, *profile.negative_rules[:4]])
        return [
            VisualIdentityLockProfile(
                lock_id=stable_id(
                    "visual_identity_lock",
                    project_context.get("project_id"),
                    capability_input.job_id,
                    subject_type,
                    ",".join(binding_ids),
                ),
                project_id=str(project_context.get("project_id") or "") or None,
                subject_type=subject_type,
                lock_strength="strong" if any(binding.strength == "hard" for binding in strong_bindings) else "normal",
                source_binding_ids=binding_ids,
                face_lock={"preserve": subject_type == "character", "confidence": 0.62 if subject_type == "character" else 0.0},
                hair_lock={"preserve": subject_type == "character" and hair_locked, "confidence": 0.7 if hair_locked else 0.0},
                wardrobe_lock={"preserve": subject_type == "character" and wardrobe_locked, "confidence": 0.7 if wardrobe_locked else 0.0},
                appearance_structure_lock=appearance_structure_lock,
                product_lock=product_lock,
                camera_lock={"rules": profile.lens_notes[:4] if camera_locked or subject_type != "character" else []},
                lighting_lock={"rules": profile.lighting_notes[:4] if lighting_locked or subject_type != "character" else []},
                keep_rules=keep_rules,
                allowed_changes=["new scene details requested by the user", "fresh but compatible composition variants"],
                forbidden_drift=forbidden,
                prompt_constraints=prompt_constraints,
                negative_constraints=negative_constraints,
                user_visible_summary=self._identity_lock_user_summary(subject_type),
                confidence=0.74 if strong_bindings else 0.48,
                metadata={
                    "template_policy": template_policy,
                    "visual_cluster_profile_id": profile.profile_id,
                    "doc93_reference_channel_policy": bool(reference_policy_package and reference_policy_package.applies),
                    "reference_policy_package_id": reference_policy_package.package_id if reference_policy_package else None,
                },
            )
        ]

    def _identity_lock_user_summary(self, subject_type: str) -> list[str]:
        if subject_type == "character":
            return ["会保持同一个人的长相", "造型、光线和场景按这次要求变化"]
        if subject_type == "product":
            return ["会保持商品形状、材质、颜色和比例", "会避免无关商品和错误标签"]
        return ["会保持已选视觉风格、构图、色彩和光感"]

    def _advanced_reference_controls(
        self,
        *,
        capability_input: CapabilityInput,
        project_context: dict[str, Any],
        strong_bindings: list[StrongReferenceBinding],
        subject_type: str,
    ) -> dict[str, Any]:
        template_id = str(project_context.get("template_id") or capability_input.metadata.get("template_id") or "")
        scenario_parameters = _as_dict(capability_input.metadata.get("scenario_parameters"))
        project_metadata = _as_dict(project_context.get("metadata"))
        raw_controls: dict[str, Any] = {}
        for source in (
            project_metadata.get("advanced_reference_controls"),
            scenario_parameters.get("advanced_reference_controls"),
            capability_input.metadata.get("advanced_reference_controls"),
        ):
            raw_controls.update(_clean_advanced_reference_controls(source))
        has_identity_binding = any(self._binding_is_person_identity(binding) for binding in strong_bindings)
        has_any_binding = bool(strong_bindings)
        defaults = {
            "preserve_person_identity": bool(has_identity_binding or (subject_type == "character" and has_any_binding)),
            "preserve_product_appearance": bool(subject_type == "product" and has_any_binding),
            "preserve_scene_consistency": False,
        }
        controls = {
            key: bool(raw_controls[key]) if key in raw_controls else default
            for key, default in defaults.items()
        }
        applies = bool(has_any_binding and any(controls.values()))
        return {
            **controls,
            "applies": applies,
            "template_scope": template_id,
            "doc": "90",
            "source": "manual" if raw_controls else "generic_reference_defaults",
            "has_reference_binding": has_any_binding,
            "has_identity_binding": has_identity_binding,
            "subject_type": subject_type,
        }

    def _binding_is_person_identity(self, binding: StrongReferenceBinding) -> bool:
        role = str(binding.role or "").lower()
        use_policy = str(binding.use_policy or "").lower()
        lock_targets = {str(item or "").lower() for item in binding.lock_targets}
        return bool(
            use_policy == "identity"
            or role in {"identity_reference", "portrait_identity", "face_reference"}
            or {"face_identity", "portrait_identity"} & lock_targets
        )

    def _apply_advanced_reference_controls_to_closure(
        self,
        closure: StrongReferenceClosurePackage,
        controls: dict[str, Any],
    ) -> StrongReferenceClosurePackage:
        if not controls.get("applies"):
            return closure
        prompt_rules, negative_rules, keep_rules = self._advanced_reference_control_rules(controls)
        return closure.model_copy(
            update={
                "identity_keep_rules": _dedupe([*closure.identity_keep_rules, *keep_rules])[:18],
                "provider_prompt_rules": _dedupe([*prompt_rules, *closure.provider_prompt_rules])[:14],
                "negative_prompt_rules": _dedupe([*closure.negative_prompt_rules, *negative_rules])[:24],
                "forbidden_drift": _dedupe([*closure.forbidden_drift, *negative_rules])[:18],
                "metadata": {
                    **dict(closure.metadata),
                    "doc90_advanced_reference_controls": True,
                    "advanced_reference_controls": controls,
                },
            }
        )

    def _apply_advanced_reference_controls_to_subject_identity_card(
        self,
        card: SubjectIdentityCard | None,
        controls: dict[str, Any],
    ) -> SubjectIdentityCard | None:
        if card is None or not controls.get("applies") or not controls.get("preserve_person_identity"):
            return card
        prompt_rules, negative_rules, keep_rules = self._advanced_reference_control_rules(controls)
        review_checks = [
            "uploaded face remains the first identity source when prompt face wording conflicts",
            "beauty archetype words affect styling only, not facial geometry",
        ]
        return card.model_copy(
            update={
                "identity_keep_rules": _dedupe([*keep_rules, *card.identity_keep_rules])[:12],
                "prompt_additions": _dedupe([*prompt_rules, *card.prompt_additions])[:12],
                "negative_additions": _dedupe([*card.negative_additions, *negative_rules])[:18],
                "review_checks": _dedupe([*card.review_checks, *review_checks])[:10],
                "metadata": {
                    **dict(card.metadata),
                    "doc90_advanced_reference_controls": True,
                    "advanced_reference_controls": controls,
                },
            }
        )

    def _apply_advanced_reference_controls_to_role_plan(
        self,
        plan: RoleSpecificGenerationPlan,
        controls: dict[str, Any],
    ) -> RoleSpecificGenerationPlan:
        if not controls.get("applies"):
            return plan
        prompt_rules, negative_rules, keep_rules = self._advanced_reference_control_rules(controls)
        updated_recipes = []
        for recipe in plan.role_recipes:
            updated_recipes.append(
                recipe.model_copy(
                    update={
                        "must_keep_rules": _dedupe([*recipe.must_keep_rules, *keep_rules])[:16],
                        "must_not_rules": _dedupe([*recipe.must_not_rules, *negative_rules])[:18],
                        "review_checks": _dedupe(
                            [
                                *recipe.review_checks,
                                "Doc90 priority controls are respected when reference and prompt conflict",
                            ]
                        )[:14],
                        "metadata": {
                            **dict(recipe.metadata),
                            "doc90_advanced_reference_controls": True,
                        },
                    }
                )
            )
        return plan.model_copy(
            update={
                "role_recipes": updated_recipes,
                "prompt_additions": _dedupe([*prompt_rules, *plan.prompt_additions])[:40],
                "metadata": {
                    **dict(plan.metadata),
                    "doc90_advanced_reference_controls": True,
                    "advanced_reference_controls": controls,
                    "doc90_batch_review_rules": [
                        "Doc90 advanced reference priority controls must be honored across the set."
                    ],
                },
            }
        )

    def _advanced_reference_control_rules(
        self,
        controls: dict[str, Any],
    ) -> tuple[list[str], list[str], list[str]]:
        prompt_rules: list[str] = []
        negative_rules: list[str] = []
        keep_rules: list[str] = []
        if controls.get("preserve_person_identity"):
            prompt_rules.extend(
                [
                    "Doc90 person priority: use the uploaded or selected person as the exact identity source when the prompt describes a human subject.",
                    "Doc90 conflict rule: prompt face-archetype words such as oval face, sweet style, young woman, or generic beauty type may guide makeup, styling, expression, and mood only; they must not replace the reference person's facial geometry.",
                    "Doc90 identity geometry: preserve face width/length relationship, eye spacing and eye-shape direction, nose-mouth relationship, cheek-jaw-chin direction, age direction, and recognizable same-person impression.",
                ]
            )
            keep_rules.extend(
                [
                    "uploaded person identity has highest priority over generic prompt face descriptions",
                    "prompt person descriptors guide styling and mood only, not face geometry",
                    "preserve same-person bone structure and facial feature relationships",
                ]
            )
            negative_rules.extend(
                [
                    "beauty archetype overrode reference identity",
                    "same type but different person",
                    "prompt face description replaced uploaded face geometry",
                    "generic sweet model replacing the reference person",
                ]
            )
        if controls.get("preserve_product_appearance"):
            prompt_rules.append(
                "Doc90 product priority: preserve the uploaded object's silhouette, proportions, material direction, pattern family, label area, and distinctive structure; prompt product-category words must not replace the referenced object."
            )
            keep_rules.append("uploaded object or product appearance has priority over generic prompt product wording")
            negative_rules.extend(
                [
                    "product silhouette drift",
                    "label or pattern drift",
                    "material structure drift",
                    "generic product replacement",
                ]
            )
        if controls.get("preserve_scene_consistency"):
            prompt_rules.append(
                "Doc90 scene priority: preserve the reference background, spatial layout, camera mood, and scene continuity; new prompt wording may refine the same world but should not replace the environment."
            )
            keep_rules.append("uploaded scene and space continuity have priority over unrelated environment changes")
            negative_rules.extend(
                [
                    "scene identity drift",
                    "background space drift",
                    "camera mood drift",
                    "reference scene replaced",
                ]
            )
        return _dedupe(prompt_rules), _dedupe(negative_rules), _dedupe(keep_rules)

    def _human_variation_profiles(
        self,
        *,
        capability_input: CapabilityInput,
        project_context: dict[str, Any],
        selected_outputs: list[dict[str, Any]],
        selected_references: list[dict[str, Any]],
        uploaded_references: list[dict[str, Any]],
        identity_locks: list[VisualIdentityLockProfile],
        reference_policy_package: ResolvedReferencePolicyPackage | None = None,
    ) -> tuple[HumanIdentityAnchorProfile, HumanNaturalVariationPlan]:
        scenario_parameters = _as_dict(capability_input.metadata.get("scenario_parameters"))
        project_metadata = _as_dict(project_context.get("metadata"))
        requested_count = self._safe_int(
            capability_input.metadata.get("requested_image_count")
            or scenario_parameters.get("requested_image_count")
            or project_metadata.get("requested_image_count"),
            default=1,
        )
        variation_mode = (
            capability_input.metadata.get("effective_variation_mode")
            or scenario_parameters.get("effective_variation_mode")
            or capability_input.metadata.get("variation_mode")
            or scenario_parameters.get("variation_mode")
            or "delivery_suite"
        )
        return self.human_variation_policy.build(
            user_input=capability_input.user_input,
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            requested_image_count=requested_count,
            variation_mode=str(variation_mode),
            selected_outputs=selected_outputs,
            selected_references=selected_references,
            uploaded_references=uploaded_references,
            identity_lock_profiles=[item.model_dump(mode="json") for item in identity_locks],
            reference_policy_package=reference_policy_package,
        )

    def _requested_image_count(self, capability_input: CapabilityInput, project_context: dict[str, Any]) -> int:
        scenario_parameters = _as_dict(capability_input.metadata.get("scenario_parameters"))
        project_metadata = _as_dict(project_context.get("metadata"))
        explicit_count = (
            capability_input.metadata.get("requested_image_count")
            or scenario_parameters.get("requested_image_count")
            or project_metadata.get("requested_image_count")
        )
        if explicit_count not in {None, ""}:
            return self._safe_int(explicit_count, default=1)
        default_by_mode = {
            "selection_candidates": 3,
            "delivery_suite": 3,
            "creative_exploration": 3,
            "format_layout_adaptation": 2,
        }
        mode = self._effective_variation_mode(capability_input, project_context)
        return self._safe_int(default_by_mode.get(mode, 1), default=1)

    def _effective_variation_mode(self, capability_input: CapabilityInput, project_context: dict[str, Any]) -> str:
        scenario_parameters = _as_dict(capability_input.metadata.get("scenario_parameters"))
        project_metadata = _as_dict(project_context.get("metadata"))
        value = (
            capability_input.metadata.get("effective_variation_mode")
            or scenario_parameters.get("effective_variation_mode")
            or project_metadata.get("effective_variation_mode")
            or capability_input.metadata.get("variation_mode")
            or scenario_parameters.get("variation_mode")
            or project_metadata.get("variation_mode")
            or "delivery_suite"
        )
        value = str(value or "").strip()
        if value == "format_adaptation":
            value = "format_layout_adaptation"
        return value if value in {"selection_candidates", "delivery_suite", "creative_exploration", "format_layout_adaptation"} else "delivery_suite"

    def _binding_profile(
        self,
        bindings: list[dict[str, Any]],
        selected_references: list[dict[str, Any]],
        uploaded_references: list[dict[str, Any]],
        strong_bindings: list[StrongReferenceBinding],
    ) -> VisualReferenceBindingProfile:
        hard: list[str] = []
        soft: list[str] = []
        negative: list[str] = []
        provider_required: list[str] = []
        usage_rules: list[str] = []
        strong_payloads = [binding.model_dump(mode="json") for binding in strong_bindings]
        for binding in strong_bindings:
            asset_id = str(binding.asset_id or binding.output_id or binding.source_id or "")
            if not asset_id:
                continue
            if binding.strength == "hard" or binding.use_policy in {"identity", "product_identity", "brand_asset"}:
                hard.append(asset_id)
            else:
                soft.append(asset_id)
            if binding.provider_input_required:
                provider_required.append(asset_id)
            if binding.user_visible_label:
                usage_rules.append(binding.user_visible_label)
            if binding.lock_targets:
                usage_rules.append("lock " + ", ".join(binding.lock_targets[:4]))
        for binding in bindings:
            asset_id = str(binding.get("asset_id") or "")
            role = str(binding.get("role") or "")
            if not asset_id:
                continue
            if role in HARD_REFERENCE_ROLES:
                hard.append(asset_id)
            elif role == AssetRole.NEGATIVE_REFERENCE.value:
                negative.append(asset_id)
            else:
                soft.append(asset_id)
            if binding.get("provider_input_required"):
                provider_required.append(asset_id)
            usage_rules.extend(_string_list(binding.get("review_expectations")))
        for reference in selected_references:
            ref_id = _identity(reference, "asset_ref_id", "asset_id", "output_id", "reference_id")
            if ref_id:
                soft.append(ref_id)
                usage_rules.append("use selected project image only for its resolved reference channels")
        for reference in uploaded_references:
            ref_id = _identity(reference, "asset_ref_id", "asset_id", "reference_id")
            if ref_id:
                soft.append(ref_id)
                usage_rules.append("use active uploaded project reference when compatible")
        all_ids = _dedupe([*hard, *soft, *negative])
        return VisualReferenceBindingProfile(
            binding_id=stable_id("visual_reference_binding_profile", ",".join(all_ids), len(bindings)),
            reference_count=len(all_ids),
            hard_reference_ids=_dedupe(hard),
            soft_reference_ids=_dedupe(soft),
            negative_reference_ids=_dedupe(negative),
            provider_input_required_ids=_dedupe(provider_required),
            bindings=bindings,
            strong_bindings=strong_payloads,
            usage_rules=_dedupe(usage_rules)[:10],
            metadata={"binding_count": len(bindings), "strong_binding_count": len(strong_bindings)},
        )

    def _consistency_guard(
        self,
        *,
        project_context: dict[str, Any],
        snapshot: ProjectVisualGrammarSnapshot,
        profile: VisualGrammarProfile,
        binding_profile: VisualReferenceBindingProfile,
        strong_reference_plan: StrongReferenceContinuationPlan | None,
        suite_role_plan: GeneralSuiteRolePlan | None,
        batch_review: BatchIdentityDiversityReview | None,
    ) -> VisualConsistencyGuardResult:
        metadata = _as_dict(project_context.get("metadata"))
        positive_only = bool(metadata.get("positive_context_from_selected_outputs_only", True))
        unselected_excluded = bool(metadata.get("unselected_candidates_excluded", True))
        warnings: list[str] = []
        if not positive_only:
            warnings.append("project context does not explicitly enforce selected-output-only positive anchors")
        if not unselected_excluded:
            warnings.append("project context does not explicitly exclude unselected candidates")
        if snapshot.continuity_strength == "weak" and project_context:
            warnings.append("no selected project image is available yet; use project goal as the first style anchor")
        checks = [
            "read project visual context",
            "use selected outputs as positive anchors only",
            "keep active references separate from rejected directions",
            "carry lighting, palette, framing, and layout as reusable visual rules",
        ]
        if strong_reference_plan is not None:
            checks.append("apply selected-output strong reference continuation plan")
        if suite_role_plan is not None and suite_role_plan.roles:
            checks.append("plan purposeful roles for this image set")
        if batch_review is not None and batch_review.applies:
            checks.append("check identity drift and over-cloned repetition at batch level")
        keep_rules = _dedupe(
            [
                *snapshot.style_rules[:4],
                *profile.lighting_notes[:3],
                *binding_profile.usage_rules[:3],
                *(strong_reference_plan.prompt_additions[:4] if strong_reference_plan else []),
                *(suite_role_plan.prompt_additions[:4] if suite_role_plan else []),
            ]
        )[:14]
        avoid_rules = _dedupe(
            [
                *snapshot.negative_directions,
                *(strong_reference_plan.negative_additions[:5] if strong_reference_plan else []),
                *(batch_review.retry_patch.get("negative_additions", [])[:5] if batch_review else []),
            ]
        )[:14]
        return VisualConsistencyGuardResult(
            status="warning" if warnings else "passed",
            continuity_strength=snapshot.continuity_strength,
            positive_context_from_selected_outputs_only=positive_only,
            unselected_candidates_excluded=unselected_excluded,
            checks=checks,
            keep_rules=keep_rules,
            avoid_rules=avoid_rules,
            warnings=warnings,
            metadata={
                "selected_anchor_count": len(snapshot.positive_anchor_output_ids),
                "reference_count": binding_profile.reference_count,
                "strong_reference_plan": strong_reference_plan.plan_id if strong_reference_plan else None,
                "suite_role_plan": suite_role_plan.plan_id if suite_role_plan else None,
                "batch_identity_diversity_review": batch_review.review_id if batch_review else None,
            },
        )

    def _quality_review(
        self,
        output_review: dict[str, Any],
        compiled_constraints: dict[str, Any],
        consistency_guard: VisualConsistencyGuardResult,
    ) -> VisualQualityReviewResult:
        checklist = [
            "subject is clear and recognizable",
            "lighting and palette match the project direction",
            "composition is clean and usable",
            "no random visible text is generated",
            "continuation keeps selected project anchors when present",
        ]
        evaluation_checks = _dict_list(compiled_constraints.get("evaluation_checks"))
        if evaluation_checks:
            checklist.append(f"check {len(evaluation_checks)} evaluation obligation(s)")
        issues = _dict_list(output_review.get("issues"))
        warnings = [str(item.get("message") or item.get("code") or "") for item in issues if item]
        warnings.extend(consistency_guard.warnings)
        return VisualQualityReviewResult(
            status="review_needed" if warnings else "ready",
            checklist=_dedupe(checklist),
            warning_notes=_dedupe(warnings)[:8],
            metadata={"evaluation_check_count": len(evaluation_checks)},
        )

    def _quality_review_reports(
        self,
        *,
        capability_input: CapabilityInput,
        quality_review: VisualQualityReviewResult,
        consistency_guard: VisualConsistencyGuardResult,
        identity_locks: list[VisualIdentityLockProfile],
        anti_ai_face_review: AntiAIFaceReviewResult | None = None,
        beautiful_realism_review: BeautifulRealismBalanceReview | None = None,
        strict_review_policy: StrictVisualReviewPolicy | None = None,
        portrait_identity_review: PortraitIdentitySimilarityReview | None = None,
        portrait_style_review: PortraitIdentityStyleSeparationReview | None = None,
        portrait_balance_review: PortraitReferenceBalanceReview | None = None,
        bone_structure_retry_patch: BoneStructureRetryPatch | None = None,
        reference_overinheritance_retry_patch: ReferenceOverinheritanceRetryPatch | None = None,
        portrait_reference_balance_retry_patch: PortraitReferenceBalanceRetryPatch | None = None,
    ) -> list[VisualQualityReviewReport]:
        project_context = _as_dict(capability_input.metadata.get("project_context_snapshot"))
        candidates = self._candidate_payloads(capability_input)
        if not candidates:
            candidates = [{"candidate_id": "pre_generation", "output_id": None, "metadata": {"preflight": True}}]

        reports: list[VisualQualityReviewReport] = []
        for candidate in candidates[:8]:
            candidate_id = str(candidate.get("candidate_id") or candidate.get("id") or candidate.get("output_id") or "")
            output_id = candidate.get("output_id") or candidate.get("asset_id")
            detected_issues: list[dict[str, Any]] = []
            warning_notes = list(quality_review.warning_notes)
            if consistency_guard.status != "passed":
                detected_issues.append(
                    {
                        "code": "project_continuity_warning",
                        "severity": "medium",
                        "message": "Project continuity needs extra checking before final delivery.",
                        "retryable": True,
                    }
                )
            for note in warning_notes[:6]:
                detected_issues.append(
                    {
                        "code": "quality_warning",
                        "severity": "medium",
                        "message": note,
                        "retryable": True,
                    }
                )
            if anti_ai_face_review and anti_ai_face_review.issue_codes:
                for code in anti_ai_face_review.issue_codes:
                    detected_issues.append(
                        {
                            "code": code,
                            "severity": anti_ai_face_review.severity,
                            "message": code.replace("_", " "),
                            "retryable": True,
                        }
                    )
            if beautiful_realism_review and beautiful_realism_review.issue_codes:
                for code in beautiful_realism_review.issue_codes:
                    detected_issues.append(
                        {
                            "code": code,
                            "severity": beautiful_realism_review.severity,
                            "message": code.replace("_", " "),
                            "retryable": True,
                        }
                    )
            if portrait_identity_review and portrait_identity_review.issue_codes:
                for code in portrait_identity_review.issue_codes:
                    detected_issues.append(
                        {
                            "code": code,
                            "severity": "high",
                            "message": code.replace("_", " "),
                            "retryable": portrait_identity_review.status == "fail_retryable",
                        }
                    )
            if portrait_style_review and portrait_style_review.issue_codes:
                for code in portrait_style_review.issue_codes:
                    detected_issues.append(
                        {
                            "code": code,
                            "severity": "high"
                            if code in {
                                "reference_used_as_style_when_identity_only",
                                "retry_repaired_artifact_but_changed_identity",
                            }
                            else "medium",
                            "message": code.replace("_", " "),
                            "retryable": portrait_style_review.status == "fail_retryable",
                        }
                    )
            if portrait_balance_review and portrait_balance_review.issue_codes:
                for code in portrait_balance_review.issue_codes:
                    detected_issues.append(
                        {
                            "code": code,
                            "severity": "high"
                            if code
                            in {
                                "prompt_mood_regression",
                                "prompt_color_tone_regression",
                                "identity_repair_damaged_prompt_direction",
                            }
                            else "medium",
                            "message": code.replace("_", " "),
                            "retryable": portrait_balance_review.status == "fail_retryable",
                        }
                    )
            strict_issue_codes = self._strict_review_issue_codes(
                capability_input,
                strict_review_policy,
                candidate,
            )
            strict_retryable = set(strict_review_policy.retryable_issue_codes if strict_review_policy else [])
            for code in strict_issue_codes:
                detected_issues.append(
                    {
                        "code": code,
                        "severity": "high" if code in {"identity_drift", "role_collapse", "generic_ai_beauty_identity"} else "medium",
                        "message": code.replace("_", " "),
                        "retryable": code in strict_retryable,
                    }
                )

            identity_score = 0.88 if identity_locks else 0.62
            if portrait_identity_review and portrait_identity_review.bone_structure_identity_score is not None:
                identity_score = min(
                    identity_score,
                    max(0.0, float(portrait_identity_review.bone_structure_identity_score) / 100.0),
                )
            style_score = 0.86 if consistency_guard.continuity_strength in {"medium", "strong"} else 0.68
            text_score = 0.92 if not warning_notes else 0.74
            usability_score = 0.86 if not detected_issues else 0.68
            scores = {
                "identity_consistency": round(identity_score, 2),
                "style_consistency": round(style_score, 2),
                "text_artifact_safety": round(text_score, 2),
                "commercial_usability": round(usability_score, 2),
            }
            if portrait_identity_review and portrait_identity_review.status != "not_applicable":
                scores["bone_structure_identity"] = round(
                    float(portrait_identity_review.bone_structure_identity_score or 0) / 100.0,
                    2,
                )
                scores["same_person_readability"] = round(
                    float(portrait_identity_review.same_person_readability_score or 0) / 100.0,
                    2,
                )
            if portrait_style_review and portrait_style_review.status != "not_applicable":
                scores["prompt_style_obedience"] = round(
                    float(portrait_style_review.prompt_style_obedience_score or 0) / 100.0,
                    2,
                )
                scores["lighting_color_scene_obedience"] = round(
                    float(portrait_style_review.lighting_color_scene_obedience_score or 0) / 100.0,
                    2,
                )
            if portrait_balance_review and portrait_balance_review.status != "not_applicable":
                scores["prompt_mood_preservation"] = round(
                    float(portrait_balance_review.prompt_mood_preservation_score or 0) / 100.0,
                    2,
                )
                scores["identity_prompt_balance"] = round(
                    float(portrait_balance_review.identity_prompt_balance_score or 0) / 100.0,
                    2,
                )
            hard_issue = any(str(issue.get("severity")) == "high" for issue in detected_issues)
            status = "fail" if hard_issue else "retry_recommended" if detected_issues else "pass"
            prompt_additions = _dedupe(
                [
                    *[rule for lock in identity_locks for rule in lock.prompt_constraints[:4]],
                    *consistency_guard.keep_rules[:4],
                ]
            )[:8]
            negative_additions = _dedupe(
                [
                    *[rule for lock in identity_locks for rule in lock.negative_constraints[:4]],
                    *consistency_guard.avoid_rules[:4],
                    *(
                        _string_list(anti_ai_face_review.retry_patch.get("negative_additions"))
                        if anti_ai_face_review
                        else []
                    ),
                    *(
                        _string_list(beautiful_realism_review.retry_patch.get("negative_additions"))
                        if beautiful_realism_review
                        else []
                    ),
                    *(
                        bone_structure_retry_patch.negative_additions
                        if bone_structure_retry_patch and bone_structure_retry_patch.applies
                        else []
                    ),
                    *(
                        reference_overinheritance_retry_patch.negative_additions
                        if reference_overinheritance_retry_patch and reference_overinheritance_retry_patch.applies
                        else []
                    ),
                    *(
                        portrait_reference_balance_retry_patch.negative_additions
                        if portrait_reference_balance_retry_patch and portrait_reference_balance_retry_patch.applies
                        else []
                    ),
                    "visible text artifacts",
                    "watermark or signature",
                ]
            )[:10]
            prompt_additions = _dedupe(
                [
                    *(
                        reference_overinheritance_retry_patch.prompt_additions
                        if reference_overinheritance_retry_patch and reference_overinheritance_retry_patch.applies
                        else []
                    ),
                    *(
                        portrait_reference_balance_retry_patch.prompt_additions
                        if portrait_reference_balance_retry_patch and portrait_reference_balance_retry_patch.applies
                        else []
                    ),
                    *prompt_additions,
                    *(
                        _string_list(anti_ai_face_review.retry_patch.get("prompt_additions"))
                        if anti_ai_face_review
                        else []
                    ),
                    *(
                        _string_list(beautiful_realism_review.retry_patch.get("prompt_additions"))
                        if beautiful_realism_review
                        else []
                    ),
                    *(
                        _string_list(beautiful_realism_review.retry_patch.get("identity_reinforcement"))
                        if beautiful_realism_review
                        else []
                    ),
                    *(
                        strict_review_policy.prompt_additions[:6]
                        if strict_review_policy and strict_review_policy.applies
                        else []
                    ),
                    *(
                        bone_structure_retry_patch.prompt_additions
                        if bone_structure_retry_patch and bone_structure_retry_patch.applies
                        else []
                    ),
                ]
            )[:16]
            negative_additions = _dedupe(
                [
                    *negative_additions,
                    *(
                        strict_review_policy.negative_additions[:12]
                        if strict_review_policy and strict_review_policy.applies
                        else []
                    ),
                    *(
                        _string_list(beautiful_realism_review.retry_patch.get("artifact_repair"))
                        if beautiful_realism_review
                        else []
                    ),
                    *(
                        bone_structure_retry_patch.identity_reinforcement
                        if bone_structure_retry_patch and bone_structure_retry_patch.applies
                        else []
                    ),
                    *(
                        reference_overinheritance_retry_patch.identity_reinforcement
                        if reference_overinheritance_retry_patch and reference_overinheritance_retry_patch.applies
                        else []
                    ),
                    *(
                        portrait_reference_balance_retry_patch.identity_reinforcement
                        if portrait_reference_balance_retry_patch and portrait_reference_balance_retry_patch.applies
                        else []
                    ),
                ]
            )[:20]
            reports.append(
                VisualQualityReviewReport(
                    review_id=stable_id(
                        "visual_quality_review_report",
                        project_context.get("project_id"),
                        capability_input.job_id,
                        candidate_id,
                        output_id,
                    ),
                    project_id=str(project_context.get("project_id") or "") or None,
                    job_id=capability_input.job_id,
                    candidate_id=candidate_id or None,
                    output_id=str(output_id) if output_id else None,
                    status=status,
                    review_mode=quality_review.review_mode,
                    scores=scores,
                    detected_issues=detected_issues,
                    passed_checks=[
                        "project context read",
                        "selected references kept separate from rejected directions",
                        "visible text and watermark risk checked",
                    ],
                    warning_notes=warning_notes[:8],
                    retry_patch={
                        "prompt_additions": prompt_additions,
                        "negative_additions": negative_additions,
                        "reference_requirements": [
                            binding_id
                            for lock in identity_locks
                            for binding_id in lock.source_binding_ids[:4]
                        ],
                        "identity_reinforcement": (
                            _dedupe(
                                [
                                    *(
                                        bone_structure_retry_patch.identity_reinforcement
                                        if bone_structure_retry_patch and bone_structure_retry_patch.applies
                                        else []
                                    ),
                                    *(
                                        reference_overinheritance_retry_patch.identity_reinforcement
                                        if reference_overinheritance_retry_patch
                                        and reference_overinheritance_retry_patch.applies
                                        else []
                                    ),
                                    *(
                                        portrait_reference_balance_retry_patch.identity_reinforcement
                                        if portrait_reference_balance_retry_patch
                                        and portrait_reference_balance_retry_patch.applies
                                        else []
                                    ),
                                ]
                            )
                        ),
                        "reduce_archetype_language": bool(
                            bone_structure_retry_patch and bone_structure_retry_patch.reduce_archetype_language
                        ),
                        "block_source_style_channels": (
                            reference_overinheritance_retry_patch.block_source_style_channels
                            if reference_overinheritance_retry_patch and reference_overinheritance_retry_patch.applies
                            else []
                        ),
                        "preserve_prompt_mood": bool(
                            portrait_reference_balance_retry_patch
                            and portrait_reference_balance_retry_patch.preserve_prompt_mood
                        ),
                        "preserve_approved_visual_anchor": bool(
                            portrait_reference_balance_retry_patch
                            and portrait_reference_balance_retry_patch.preserve_approved_visual_anchor
                        ),
                        "shorten_overconstrained_identity_guidance": bool(
                            portrait_reference_balance_retry_patch
                            and portrait_reference_balance_retry_patch.shorten_overconstrained_identity_guidance
                        ),
                    },
                    user_visible_summary=self._review_user_summary(status, identity_locks),
                    metadata={
                        "pre_generation": bool(candidate.get("metadata", {}).get("preflight")),
                        "mode_role_key": self._candidate_role_key(candidate),
                        "strict_visual_review_policy_id": strict_review_policy.policy_id
                        if strict_review_policy and strict_review_policy.applies
                        else None,
                        "beautiful_realism_balance_review_id": beautiful_realism_review.review_id
                        if beautiful_realism_review and beautiful_realism_review.applies
                        else None,
                        "portrait_identity_similarity_review_id": portrait_identity_review.review_id
                        if portrait_identity_review and portrait_identity_review.status != "not_applicable"
                        else None,
                        "doc86_bone_structure_review_status": portrait_identity_review.status
                        if portrait_identity_review
                        else None,
                        "portrait_reference_balance_review_id": portrait_balance_review.review_id
                        if portrait_balance_review and portrait_balance_review.status != "not_applicable"
                        else None,
                        "doc88_portrait_reference_balance_status": portrait_balance_review.status
                        if portrait_balance_review
                        else None,
                    },
                )
            )
        return reports

    def _strict_review_issue_codes(
        self,
        capability_input: CapabilityInput,
        strict_review_policy: StrictVisualReviewPolicy | None,
        candidate: dict[str, Any],
    ) -> list[str]:
        if strict_review_policy is None or not strict_review_policy.applies:
            return []
        values: list[str] = []
        for key in (
            "force_strict_visual_review_issue_codes",
            "strict_visual_review_issue_codes",
            "force_visual_retry_issue_codes",
            "post_generation_fake_issue_codes",
        ):
            values.extend(_string_list(capability_input.metadata.get(key)))
        metadata = _as_dict(candidate.get("metadata"))
        for key in (
            "strict_visual_review_issue_codes",
            "detected_issue_codes",
            "issue_codes",
            "post_generation_fake_issue_codes",
        ):
            values.extend(_string_list(metadata.get(key)))
        allowed = set(strict_review_policy.retryable_issue_codes)
        return [code for code in _dedupe(values) if code in allowed]

    def _doc86_identity_issue_codes(self, capability_input: CapabilityInput) -> list[str]:
        values: list[str] = []
        for key in (
            "force_portrait_identity_issue_codes",
            "portrait_identity_issue_codes",
            "bone_structure_issue_codes",
            "force_strict_visual_review_issue_codes",
            "strict_visual_review_issue_codes",
            "force_visual_retry_issue_codes",
            "post_generation_fake_issue_codes",
        ):
            values.extend(_string_list(capability_input.metadata.get(key)))
        for candidate in self._candidate_payloads(capability_input):
            metadata = _as_dict(candidate.get("metadata"))
            for key in (
                "portrait_identity_issue_codes",
                "bone_structure_issue_codes",
                "detected_issue_codes",
                "issue_codes",
                "post_generation_fake_issue_codes",
            ):
                values.extend(_string_list(metadata.get(key)))
        return [code for code in _dedupe(values) if code in DOC86_IDENTITY_ISSUE_CODES]

    def _doc87_reference_boundary_issue_codes(self, capability_input: CapabilityInput) -> list[str]:
        values: list[str] = []
        for key in (
            "force_portrait_style_boundary_issue_codes",
            "portrait_style_boundary_issue_codes",
            "reference_boundary_issue_codes",
            "force_strict_visual_review_issue_codes",
            "strict_visual_review_issue_codes",
            "force_visual_retry_issue_codes",
            "post_generation_fake_issue_codes",
        ):
            values.extend(_string_list(capability_input.metadata.get(key)))
        for candidate in self._candidate_payloads(capability_input):
            metadata = _as_dict(candidate.get("metadata"))
            for key in (
                "portrait_style_boundary_issue_codes",
                "reference_boundary_issue_codes",
                "strict_visual_review_issue_codes",
                "issue_codes",
                "post_generation_fake_issue_codes",
            ):
                values.extend(_string_list(metadata.get(key)))
        return [code for code in _dedupe(values) if code in DOC87_REFERENCE_BOUNDARY_ISSUE_CODES]

    def _doc88_reference_balance_issue_codes(self, capability_input: CapabilityInput) -> list[str]:
        values: list[str] = []
        for key in (
            "force_portrait_balance_issue_codes",
            "portrait_balance_issue_codes",
            "reference_balance_issue_codes",
            "force_strict_visual_review_issue_codes",
            "strict_visual_review_issue_codes",
            "force_visual_retry_issue_codes",
            "post_generation_fake_issue_codes",
        ):
            values.extend(_string_list(capability_input.metadata.get(key)))
        for candidate in self._candidate_payloads(capability_input):
            metadata = _as_dict(candidate.get("metadata"))
            for key in (
                "portrait_balance_issue_codes",
                "reference_balance_issue_codes",
                "strict_visual_review_issue_codes",
                "detected_issue_codes",
                "issue_codes",
                "post_generation_fake_issue_codes",
            ):
                values.extend(_string_list(metadata.get(key)))
        return [code for code in _dedupe(values) if code in DOC88_REFERENCE_BALANCE_ISSUE_CODES]

    def _doc86_review_confidence(self, capability_input: CapabilityInput) -> float:
        try:
            confidence = float(capability_input.metadata.get("portrait_identity_review_confidence") or 0.9)
        except (TypeError, ValueError):
            confidence = 0.9
        return max(0.0, min(1.0, confidence))

    def _first_candidate_output_id(self, capability_input: CapabilityInput) -> str | None:
        for candidate in self._candidate_payloads(capability_input):
            value = candidate.get("output_id") or candidate.get("asset_id")
            if value:
                return str(value)
        return None

    def _candidate_role_key(self, candidate: dict[str, Any]) -> str:
        metadata = _as_dict(candidate.get("metadata"))
        recipe = candidate.get("mode_role_recipe") or metadata.get("mode_role_recipe")
        if isinstance(recipe, dict):
            role_key = str(recipe.get("role_key") or "").strip()
            if role_key:
                return role_key
        return str(candidate.get("mode_role_key") or metadata.get("mode_role_key") or "").strip()

    def _candidate_payloads(self, capability_input: CapabilityInput) -> list[dict[str, Any]]:
        for key in ("output_candidates", "generated_candidates", "candidates"):
            raw = capability_input.metadata.get(key)
            if isinstance(raw, list):
                return [_as_dict(item) for item in raw if _as_dict(item)]
        return []

    def _anti_ai_face_issue_codes(self, capability_input: CapabilityInput) -> list[str]:
        values: list[str] = []
        for key in (
            "force_anti_ai_face_issue_codes",
            "anti_ai_face_issue_codes",
            "post_generation_fake_issue_codes",
            "force_visual_retry_issue_codes",
        ):
            values.extend(_string_list(capability_input.metadata.get(key)))
        for candidate in self._candidate_payloads(capability_input):
            metadata = _as_dict(candidate.get("metadata"))
            for key in ("anti_ai_face_issue_codes", "issue_codes", "detected_issue_codes"):
                values.extend(_string_list(metadata.get(key)))
        return [code for code in _dedupe(values) if code in ANTI_AI_FACE_ISSUE_CODES]

    def _beautiful_realism_issue_codes(self, capability_input: CapabilityInput) -> list[str]:
        values: list[str] = []
        for key in (
            "force_beautiful_realism_issue_codes",
            "beautiful_realism_issue_codes",
            "facial_feature_issue_codes",
            "identity_card_issue_codes",
            "post_generation_fake_issue_codes",
            "force_visual_retry_issue_codes",
        ):
            values.extend(_string_list(capability_input.metadata.get(key)))
        for candidate in self._candidate_payloads(capability_input):
            metadata = _as_dict(candidate.get("metadata"))
            for key in (
                "beautiful_realism_issue_codes",
                "facial_feature_issue_codes",
                "identity_card_issue_codes",
                "detected_issue_codes",
                "issue_codes",
                "post_generation_fake_issue_codes",
            ):
                values.extend(_string_list(metadata.get(key)))
        return [code for code in _dedupe(values) if code in BEAUTIFUL_REALISM_ISSUE_CODES]

    def _beautiful_realism_retry_patch(
        self,
        *,
        issue_codes: list[str],
        subject_identity_card: SubjectIdentityCard | None,
        human_photorealism: HumanPhotorealismGuidance | None,
    ) -> dict[str, list[str]]:
        if not issue_codes:
            return {}
        prompt_additions = [
            "Doc78 beautiful realism repair: keep the person beautiful first, and make realism come from photographed skin texture, light, hair, fabric, camera depth, and natural expression.",
            "Preserve flattering facial feature design: attractive eyebrow shape/arc, awake eye shape and spacing, natural eyelids, harmonious nose-mouth relationship, jaw/chin direction, cheek volume, and face ratio.",
            "Use soft flattering real-camera light and healthy clean complexion; do not make the subject darker, tired, harsh, or less attractive just to look realistic.",
        ]
        negative_additions = [
            "ugly realism",
            "realism made face less attractive",
            "ugly eyebrow shape",
            "drooping eyebrows",
            "mismatched brows",
            "random eyebrow thickness drift",
            "sleepy dull eyes",
            "unflattering nose-mouth drift",
            "jaw or chin direction drift",
            "flattened facial attractiveness",
            "pretty but poreless AI filter",
            "over-smoothed beauty face",
            "dull complexion",
            "muddy skin tone",
        ]
        identity_reinforcement: list[str] = []
        artifact_repair = [
            "repair the face toward a flattering real photograph: natural skin texture and tiny asymmetry, but keep beautiful proportions and clean facial-feature design",
        ]
        if subject_identity_card and subject_identity_card.applies:
            identity_reinforcement.extend(subject_identity_card.identity_keep_rules[:5])
            identity_reinforcement.extend(subject_identity_card.facial_feature_integrity_rules[:4])
            prompt_additions.extend(subject_identity_card.prompt_additions[:3])
            negative_additions.extend(subject_identity_card.negative_additions[:8])
        if human_photorealism and human_photorealism.applies:
            prompt_additions.extend(human_photorealism.positive_prompt_fragments[:4])
            negative_additions.extend(human_photorealism.negative_prompt_fragments[:8])
        if any(
            code
            in {
                "identity_card_missing",
                "identity_card_not_applied",
                "identity_feature_drift",
                "eyebrow_shape_drift",
                "eye_shape_or_spacing_drift",
                "nose_mouth_relationship_drift",
                "jaw_chin_direction_drift",
            }
            for code in issue_codes
        ):
            identity_reinforcement.append(
                "use the selected image or project identity card as the truth source for facial-feature relationships; vary pose and scene, not identity-critical face design"
            )
            artifact_repair.append(
                "restore the same-person facial structure before improving style: eyebrows, eyes, nose-mouth spacing, jaw/chin, cheek volume, neck, and shoulder balance must stay recognizable"
            )
        if any(code in {"pretty_but_too_ai_filtered", "skin_texture_beauty_balance_failure"} for code in issue_codes):
            prompt_additions.append(
                "add visible but subtle photographed skin texture, eyelid detail, loose hair strands, fabric texture, real shadow transitions, and lens depth without beauty-filter reshaping"
            )
        if any(code in {"real_but_unflattering", "realism_made_subject_less_attractive", "unflattering_feature_degradation"} for code in issue_codes):
            prompt_additions.append(
                "recover flattering beauty with soft directional light, a clean luminous complexion, relaxed facial muscles, graceful eyebrow design, and a camera angle that keeps the face harmonious"
            )
            negative_additions.extend(
                [
                    "real but ugly face",
                    "harsh documentary ugliness",
                    "unflattering face angle",
                    "tired facial muscles",
                    "bad eyebrow design",
                ]
            )
        return {
            "prompt_additions": _dedupe(prompt_additions),
            "negative_additions": _dedupe(negative_additions),
            "identity_reinforcement": _dedupe(identity_reinforcement),
            "artifact_repair": _dedupe(artifact_repair),
        }

    def _review_user_summary(
        self,
        status: str,
        identity_locks: list[VisualIdentityLockProfile],
    ) -> list[str]:
        if status == "pass":
            summary = ["Ready to use"]
        elif status == "retry_recommended":
            summary = ["Worth one cleaner retry"]
        else:
            summary = ["Not recommended yet"]
        if identity_locks:
            summary.append("Checked selected-reference consistency")
        summary.append("Checked clutter, text artifacts, and visual drift")
        return summary[:3]

    def _auto_retry_decisions(
        self,
        capability_input: CapabilityInput,
        reports: list[VisualQualityReviewReport],
    ) -> list[AutoRetryDecision]:
        project_context = _as_dict(capability_input.metadata.get("project_context_snapshot"))
        retry_attempt = self._safe_int(capability_input.metadata.get("retry_attempt"), default=0)
        max_attempts = self._safe_int(capability_input.metadata.get("max_visual_retry_attempts"), default=1)
        retryable_reports = [
            report
            for report in reports
            if report.status in {"retry_recommended", "fail"}
            and any(bool(issue.get("retryable", True)) for issue in report.detected_issues)
        ]
        if retry_attempt >= max_attempts and retryable_reports:
            return [
                AutoRetryDecision(
                    decision_id=stable_id("visual_auto_retry_decision", capability_input.job_id, "blocked", retry_attempt),
                    job_id=capability_input.job_id,
                    project_id=str(project_context.get("project_id") or "") or None,
                    should_retry=False,
                    retry_attempt=retry_attempt,
                    max_attempts=max_attempts,
                    reason_codes=self._issue_codes(retryable_reports),
                    blocked_reason="max_retry_attempts_reached",
                    user_visible_reason="Already tried the safe retry limit.",
                    metadata={"retryable_report_count": len(retryable_reports)},
                )
            ]
        if not retryable_reports:
            return [
                AutoRetryDecision(
                    decision_id=stable_id("visual_auto_retry_decision", capability_input.job_id, "pass"),
                    job_id=capability_input.job_id,
                    project_id=str(project_context.get("project_id") or "") or None,
                    should_retry=False,
                    retry_attempt=retry_attempt,
                    max_attempts=max_attempts,
                    user_visible_reason="No automatic retry is needed.",
                    metadata={"retryable_report_count": 0},
                )
            ]
        merged_patch = {
            "prompt_additions": _dedupe(
                addition
                for report in retryable_reports
                for addition in _string_list(report.retry_patch.get("prompt_additions"))
            )[:10],
            "negative_additions": _dedupe(
                addition
                for report in retryable_reports
                for addition in _string_list(report.retry_patch.get("negative_additions"))
            )[:12],
            "identity_reinforcement": _dedupe(
                addition
                for report in retryable_reports
                for addition in _string_list(report.retry_patch.get("identity_reinforcement"))
            )[:10],
            "artifact_repair": _dedupe(
                addition
                for report in retryable_reports
                for addition in _string_list(report.retry_patch.get("artifact_repair"))
            )[:10],
            "reference_requirements": _dedupe(
                addition
                for report in retryable_reports
                for addition in _string_list(report.retry_patch.get("reference_requirements"))
            )[:8],
            "preserve_prompt_mood": any(
                bool(report.retry_patch.get("preserve_prompt_mood")) for report in retryable_reports
            ),
            "preserve_approved_visual_anchor": any(
                bool(report.retry_patch.get("preserve_approved_visual_anchor")) for report in retryable_reports
            ),
            "shorten_overconstrained_identity_guidance": any(
                bool(report.retry_patch.get("shorten_overconstrained_identity_guidance"))
                for report in retryable_reports
            ),
        }
        return [
            AutoRetryDecision(
                decision_id=stable_id("visual_auto_retry_decision", capability_input.job_id, "retry", retry_attempt),
                job_id=capability_input.job_id,
                project_id=str(project_context.get("project_id") or "") or None,
                should_retry=True,
                retry_attempt=retry_attempt,
                max_attempts=max_attempts,
                reason_codes=self._issue_codes(retryable_reports),
                retry_patch=merged_patch,
                user_visible_reason="A cleaner retry can better preserve the selected direction.",
                metadata={"retryable_report_count": len(retryable_reports)},
            )
        ]

    def _commercial_output_selection(
        self,
        capability_input: CapabilityInput,
        reports: list[VisualQualityReviewReport],
        *,
        identity_hero_plan: IdentityHeroSelectionPlan | None = None,
    ) -> CommercialOutputSelection:
        project_context = _as_dict(capability_input.metadata.get("project_context_snapshot"))
        ranked = sorted(reports, key=self._report_score, reverse=True)
        recommended = [report for report in ranked if report.status == "pass"] or ranked[:1]
        warning = [report for report in ranked if report.status == "retry_recommended"]
        failed = [report for report in ranked if report.status == "fail"]
        hero_role_key = identity_hero_plan.primary_role_key if identity_hero_plan and identity_hero_plan.applies else None
        hero_candidates = [
            report
            for report in ranked
            if hero_role_key and report.metadata.get("mode_role_key") == hero_role_key and report.status != "fail"
        ]
        best = hero_candidates[0] if hero_candidates else recommended[0] if recommended else None
        return CommercialOutputSelection(
            selection_id=stable_id("commercial_output_selection", project_context.get("project_id"), capability_input.job_id),
            project_id=str(project_context.get("project_id") or "") or None,
            job_id=capability_input.job_id,
            best_output_id=best.output_id if best else None,
            recommended_output_ids=[report.output_id for report in recommended if report.output_id],
            warning_output_ids=[report.output_id for report in warning if report.output_id],
            hidden_failed_output_ids=[report.output_id for report in failed if report.output_id],
            slot_fit={
                str(report.output_id or report.candidate_id or index): "primary" if index == 0 else "usable"
                for index, report in enumerate(recommended[:4])
            },
            user_visible_reasons=[
                "Best option keeps the project direction most clearly.",
                "Risky options stay visible for review instead of replacing old results.",
            ],
            metadata={
                "review_count": len(reports),
                "pre_generation_selection": not any(report.output_id for report in reports),
                "identity_hero_selection_plan_id": identity_hero_plan.plan_id
                if identity_hero_plan and identity_hero_plan.applies
                else None,
                "identity_hero_role_key": hero_role_key,
                "identity_hero_output_id": best.output_id if hero_candidates and best else None,
                "identity_hero_candidate_id": best.candidate_id if hero_candidates and best else None,
            },
        )

    def _negative_visual_memory(
        self,
        project_context: dict[str, Any],
        reports: list[VisualQualityReviewReport],
    ) -> list[dict[str, Any]]:
        notes = _dedupe(
            [
                *_string_list(project_context.get("negative_direction_notes")),
                *_string_list(project_context.get("negative_visual_directions")),
            ]
        )
        memory: list[dict[str, Any]] = [
            {"source": "project_feedback", "code": "negative_direction", "message": note, "severity": "medium"}
            for note in notes[:8]
        ]
        for report in reports:
            for issue in report.detected_issues:
                message = str(issue.get("message") or issue.get("code") or "").strip()
                if not message:
                    continue
                memory.append(
                    {
                        "source": "visual_quality_review",
                        "code": str(issue.get("code") or "quality_warning"),
                        "message": message,
                        "severity": str(issue.get("severity") or "medium"),
                        "candidate_id": report.candidate_id,
                        "output_id": report.output_id,
                    }
                )
        return memory[:16]

    def _issue_codes(self, reports: list[VisualQualityReviewReport]) -> list[str]:
        return _dedupe(
            str(issue.get("code") or "quality_warning")
            for report in reports
            for issue in report.detected_issues
        )[:10]

    def _report_score(self, report: VisualQualityReviewReport) -> float:
        if not report.scores:
            return 0.0
        return sum(float(value) for value in report.scores.values()) / max(1, len(report.scores))

    def _safe_int(self, value: Any, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _constraints(self, cluster: VisualCapabilityClusterResult) -> list[CapabilityConstraint]:
        constraints = [
            CapabilityConstraint(
                target_stage=CapabilityTargetStage.PROMPT_COMPILATION,
                constraint_type="visual_capability_cluster_prompt_context",
                strength="strong" if cluster.project_snapshot.continuity_strength == "strong" else "medium",
                value={
                    "profile_id": cluster.profile.profile_id,
                    "snapshot_id": cluster.project_snapshot.snapshot_id,
                    "style_signals": cluster.profile.style_signals[:8],
                    "composition_rules": cluster.profile.composition_rules[:6],
                    "negative_rules": cluster.profile.negative_rules[:8],
                    "continuity_strength": cluster.project_snapshot.continuity_strength,
                    "project_identity_anchors": [anchor.model_dump(mode="json") for anchor in cluster.project_identity_anchors],
                    "strong_reference_continuation_plan": (
                        cluster.strong_reference_continuation_plan.model_dump(mode="json")
                        if cluster.strong_reference_continuation_plan is not None
                        else {}
                    ),
                    "general_suite_role_plan": (
                        cluster.general_suite_role_plan.model_dump(mode="json")
                        if cluster.general_suite_role_plan is not None
                        else {}
                    ),
                    "mode_execution_policy": (
                        cluster.mode_execution_policy.model_dump(mode="json")
                        if cluster.mode_execution_policy is not None
                        else {}
                    ),
                    "role_specific_generation_plan": (
                        cluster.role_specific_generation_plan.model_dump(mode="json")
                        if cluster.role_specific_generation_plan is not None
                        else {}
                    ),
                    "portrait_bone_structure_lock": (
                        cluster.portrait_bone_structure_lock.model_dump(mode="json")
                        if cluster.portrait_bone_structure_lock is not None
                        else {}
                    ),
                    "styling_delta_policy": (
                        cluster.styling_delta_policy.model_dump(mode="json")
                        if cluster.styling_delta_policy is not None
                        else {}
                    ),
                    "portrait_reference_influence_policy": (
                        cluster.portrait_reference_influence_policy.model_dump(mode="json")
                        if cluster.portrait_reference_influence_policy is not None
                        else {}
                    ),
                    "portrait_reference_balance_policy": (
                        cluster.portrait_reference_balance_policy.model_dump(mode="json")
                        if cluster.portrait_reference_balance_policy is not None
                        else {}
                    ),
                    "portrait_reference_balance_review": (
                        cluster.portrait_reference_balance_review.model_dump(mode="json")
                        if cluster.portrait_reference_balance_review is not None
                        else {}
                    ),
                    "resolved_reference_policy_package": (
                        cluster.resolved_reference_policy_package.model_dump(mode="json")
                        if cluster.resolved_reference_policy_package is not None
                        else {}
                    ),
                    "subject_continuity_asset_package": (
                        cluster.subject_continuity_asset_package.model_dump(mode="json")
                        if cluster.subject_continuity_asset_package is not None
                        else {}
                    ),
                    "adaptive_reference_selection_plan": (
                        cluster.adaptive_reference_selection_plan.model_dump(mode="json")
                        if cluster.adaptive_reference_selection_plan is not None
                        else {}
                    ),
                    "identity_drift_guard_plan": (
                        cluster.identity_drift_guard_plan.model_dump(mode="json")
                        if cluster.identity_drift_guard_plan is not None
                        else {}
                    ),
                    "identity_repair_strategy_plan": (
                        cluster.identity_repair_strategy_plan.model_dump(mode="json")
                        if cluster.identity_repair_strategy_plan is not None
                        else {}
                    ),
                    "mode_differentiation_review": (
                        cluster.mode_differentiation_review.model_dump(mode="json")
                        if cluster.mode_differentiation_review is not None
                        else {}
                    ),
                },
                source=self.module_id,
            ),
            CapabilityConstraint(
                target_stage=CapabilityTargetStage.EVALUATION,
                constraint_type="visual_capability_cluster_quality_review",
                strength="medium",
                value=cluster.quality_review.model_dump(mode="json"),
                source=self.module_id,
            ),
        ]
        return constraints if cluster.has_visual_evidence else []

    def _confidence(
        self,
        *,
        selected_outputs: list[dict[str, Any]],
        references: list[dict[str, Any]],
        child_ids: list[str],
        style_signals: list[str],
    ) -> float:
        score = 0.42
        score += 0.18 if selected_outputs else 0.0
        score += 0.12 if references else 0.0
        score += min(0.16, len(child_ids) * 0.025)
        score += min(0.12, len(style_signals) * 0.015)
        return round(min(score, 0.92), 3)

    def _user_visible_summary(
        self,
        snapshot: ProjectVisualGrammarSnapshot,
        profile: VisualGrammarProfile,
        consistency_guard: VisualConsistencyGuardResult,
    ) -> list[str]:
        summary = ["organized reusable visual direction"]
        if snapshot.positive_anchor_output_ids:
            summary.append("kept selected project images as strong anchors")
        if profile.lighting_notes or profile.palette_notes:
            summary.append("locked lighting and color cues")
        if consistency_guard.metadata.get("suite_role_plan"):
            summary.append("planned distinct image roles for this set")
        if consistency_guard.avoid_rules:
            summary.append("kept rejected directions out of continuation")
        return summary[:4]


def _fact(result_map: dict[str, CapabilityResult], module_id: str, key: str, default: Any) -> Any:
    result = result_map.get(module_id)
    if result is None:
        return default
    return result.facts.get(key, default)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            return {}
    return dict(value) if isinstance(value, dict) else {}


def _clean_advanced_reference_controls(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "preserve_person_identity",
        "preserve_product_appearance",
        "preserve_scene_consistency",
    }
    return {key: bool(value[key]) for key in allowed if key in value}


def _reference_channel_is_locked(
    package: ResolvedReferencePolicyPackage | None,
    channel: str,
) -> bool:
    if package is None or not package.applies:
        return False
    owner = str(package.effective_channel_owners.get(channel) or "")
    return owner.startswith("reference:") and owner.rsplit(":", 1)[-1] in {"hard", "medium"}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_as_dict(item) for item in value if _as_dict(item)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _identity(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _looks_like_human_prompt(value: str) -> bool:
    text = str(value or "").lower()
    english_terms = (
        "portrait",
        "person",
        "woman",
        "girl",
        "man",
        "model",
        "face",
        "beauty photo",
        "editorial photo",
        "fashion photo",
    )
    chinese_terms = (
        "\u4eba\u50cf",
        "\u771f\u4eba",
        "\u5199\u771f",
        "\u6444\u5f71",
        "\u6a21\u7279",
        "\u7f8e\u5973",
        "\u4eba\u7269",
        "\u5973\u751f",
        "\u5973\u5b69",
        "\u8138",
    )
    return _contains_latin_terms(text, english_terms) or any(term in value for term in chinese_terms)


def _contains_latin_terms(text: str, terms: tuple[str, ...] | list[str]) -> bool:
    """Match Latin intent terms as words, without changing CJK matching rules.

    The General foundation uses intent classification to decide whether
    character-only suite, identity, and review behavior may run.  A raw
    substring match made ordinary architecture language (for example,
    ``fair-faced concrete``) look like an explicit human-face request.  Keep
    multi-word terms usable while requiring non-alphanumeric boundaries.
    """

    lowered = str(text or "").lower()
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(str(term).lower())}(?![a-z0-9])", lowered)
        for term in terms
        if str(term).strip()
    )


def _sanitize_general_visual_terms(values: list[str], *, allow_product_language: bool) -> list[str]:
    if allow_product_language:
        return _dedupe(values)
    sanitized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        lowered = text.lower()
        for source, replacement in sorted(GENERAL_VISUAL_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
            lowered = lowered.replace(source, replacement)
        if any(term in lowered for term in GENERAL_VISUAL_FORBIDDEN_TERMS):
            continue
        sanitized.append(lowered)
    return _dedupe(sanitized)
