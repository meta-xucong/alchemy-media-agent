"""Contracts for the V3-native visual capability cluster."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ...schemas.models import V3BaseModel


class VisualGrammarProfile(V3BaseModel):
    profile_id: str
    scenario_id: str
    source: str = "v3_visual_capability_cluster"
    style_signals: list[str] = Field(default_factory=list)
    composition_rules: list[str] = Field(default_factory=list)
    palette_notes: list[str] = Field(default_factory=list)
    lighting_notes: list[str] = Field(default_factory=list)
    lens_notes: list[str] = Field(default_factory=list)
    layout_notes: list[str] = Field(default_factory=list)
    locked_elements: list[str] = Field(default_factory=list)
    replaceable_elements: list[str] = Field(default_factory=list)
    negative_rules: list[str] = Field(default_factory=list)
    reference_asset_ids: list[str] = Field(default_factory=list)
    selected_output_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectVisualGrammarSnapshot(V3BaseModel):
    snapshot_id: str
    project_id: str | None = None
    context_version: str | None = None
    source: str = "project_context"
    positive_anchor_output_ids: list[str] = Field(default_factory=list)
    active_reference_ids: list[str] = Field(default_factory=list)
    uploaded_reference_ids: list[str] = Field(default_factory=list)
    style_rules: list[str] = Field(default_factory=list)
    composition_rules: list[str] = Field(default_factory=list)
    lighting_rules: list[str] = Field(default_factory=list)
    palette_rules: list[str] = Field(default_factory=list)
    negative_directions: list[str] = Field(default_factory=list)
    continuity_strength: str = "weak"
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualReferenceBindingProfile(V3BaseModel):
    binding_id: str
    reference_count: int = 0
    hard_reference_ids: list[str] = Field(default_factory=list)
    soft_reference_ids: list[str] = Field(default_factory=list)
    negative_reference_ids: list[str] = Field(default_factory=list)
    provider_input_required_ids: list[str] = Field(default_factory=list)
    bindings: list[dict[str, Any]] = Field(default_factory=list)
    strong_bindings: list[dict[str, Any]] = Field(default_factory=list)
    usage_rules: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrongReferenceBinding(V3BaseModel):
    binding_id: str
    source_type: str
    source_id: str
    asset_id: str | None = None
    output_id: str | None = None
    file_path: str | None = None
    preview_url: str | None = None
    role: str = "style_reference"
    strength: str = "soft"
    use_policy: str = "style"
    lock_targets: list[str] = Field(default_factory=list)
    provider_input_required: bool = False
    prompt_only_fallback: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    user_visible_label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualIdentityLockProfile(V3BaseModel):
    lock_id: str
    project_id: str | None = None
    subject_type: str = "generic"
    lock_strength: str = "normal"
    source_binding_ids: list[str] = Field(default_factory=list)
    face_lock: dict[str, Any] = Field(default_factory=dict)
    hair_lock: dict[str, Any] = Field(default_factory=dict)
    wardrobe_lock: dict[str, Any] = Field(default_factory=dict)
    appearance_structure_lock: dict[str, Any] = Field(default_factory=dict)
    product_lock: dict[str, Any] = Field(default_factory=dict)
    brand_asset_lock: dict[str, Any] = Field(default_factory=dict)
    camera_lock: dict[str, Any] = Field(default_factory=dict)
    lighting_lock: dict[str, Any] = Field(default_factory=dict)
    keep_rules: list[str] = Field(default_factory=list)
    allowed_changes: list[str] = Field(default_factory=list)
    forbidden_drift: list[str] = Field(default_factory=list)
    prompt_constraints: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HumanIdentityAnchorProfile(V3BaseModel):
    applies: bool = False
    confidence: str = "low"
    anchor_source: str | None = None
    stable_identity_traits: list[str] = Field(default_factory=list)
    stable_body_traits: list[str] = Field(default_factory=list)
    stable_style_traits: list[str] = Field(default_factory=list)
    locked_traits: list[str] = Field(default_factory=list)
    flexible_traits: list[str] = Field(default_factory=list)
    forbidden_drift: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HumanNaturalVariationPlan(V3BaseModel):
    applies: bool = False
    variation_mode: str = "delivery_suite"
    identity_strength: str = "medium"
    diversity_strength: str = "medium"
    per_image_variation_axes: list[str] = Field(default_factory=list)
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    batch_review_rules: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HumanBatchDiversityReview(V3BaseModel):
    applies: bool = False
    status: str = "not_applicable"
    issue_codes: list[str] = Field(default_factory=list)
    observed_repetition: list[str] = Field(default_factory=list)
    preserved_identity_notes: list[str] = Field(default_factory=list)
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectIdentityAnchor(V3BaseModel):
    anchor_id: str
    project_id: str | None = None
    subject_type: str = "generic"
    source_output_ids: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)
    source_candidate_ids: list[str] = Field(default_factory=list)
    source_binding_ids: list[str] = Field(default_factory=list)
    active: bool = True
    anchor_strength: str = "medium"
    identity_keep_rules: list[str] = Field(default_factory=list)
    style_keep_rules: list[str] = Field(default_factory=list)
    allowed_variations: list[str] = Field(default_factory=list)
    forbidden_drift: list[str] = Field(default_factory=list)
    provider_reference_required: bool = False
    prompt_only_fallback: bool = False
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrongReferenceContinuationPlan(V3BaseModel):
    plan_id: str
    project_id: str | None = None
    job_id: str | None = None
    active_anchor_ids: list[str] = Field(default_factory=list)
    provider_required_reference_ids: list[str] = Field(default_factory=list)
    prompt_only_reference_ids: list[str] = Field(default_factory=list)
    lock_targets: list[str] = Field(default_factory=list)
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    reference_mode: str = "prompt_only"
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneralSuiteRole(V3BaseModel):
    role_id: str
    label: str
    purpose: str
    shot_instruction: str
    variation_axes: list[str] = Field(default_factory=list)
    keep_rules: list[str] = Field(default_factory=list)
    avoid_rules: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneralSuiteRolePlan(V3BaseModel):
    plan_id: str
    project_id: str | None = None
    job_id: str | None = None
    variation_mode: str = "delivery_suite"
    requested_image_count: int = 1
    roles: list[GeneralSuiteRole] = Field(default_factory=list)
    prompt_additions: list[str] = Field(default_factory=list)
    batch_review_rules: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModeExecutionPolicy(V3BaseModel):
    policy_id: str
    mode: str = "delivery_suite"
    mode_meaning: str = ""
    visual_distance_budget: str = "moderate"
    anchor_strength: str = "strong"
    scene_change_allowed: bool = True
    role_strategy: str = "purposeful_delivery_roles"
    role_difference_requirement: str = ""
    review_priority: str = ""
    user_visible_label: str = ""
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModeRoleRecipe(V3BaseModel):
    role_id: str
    index: int = 1
    role_key: str
    label: str
    purpose: str
    shot_family: str = ""
    camera_distance: str = ""
    angle_rule: str = ""
    crop_rule: str = ""
    scene_rule: str = ""
    variation_axes: list[str] = Field(default_factory=list)
    must_keep_rules: list[str] = Field(default_factory=list)
    must_not_rules: list[str] = Field(default_factory=list)
    prompt_pressure: str = ""
    negative_pressure: list[str] = Field(default_factory=list)
    review_checks: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoleSpecificGenerationPlan(V3BaseModel):
    plan_id: str
    project_id: str | None = None
    job_id: str | None = None
    mode: str = "delivery_suite"
    subject_type: str = "generic"
    requested_image_count: int = 1
    policy: ModeExecutionPolicy
    role_recipes: list[ModeRoleRecipe] = Field(default_factory=list)
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModeDifferentiationReview(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    mode: str = "delivery_suite"
    status: str = "planned"
    role_coverage_status: str = "planned"
    issue_codes: list[str] = Field(default_factory=list)
    role_checks: list[str] = Field(default_factory=list)
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchIdentityDiversityReview(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    status: str = "not_applicable"
    issue_codes: list[str] = Field(default_factory=list)
    identity_keep_checks: list[str] = Field(default_factory=list)
    diversity_checks: list[str] = Field(default_factory=list)
    suite_role_checks: list[str] = Field(default_factory=list)
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualConsistencyGuardResult(V3BaseModel):
    status: str = "passed"
    continuity_strength: str = "weak"
    positive_context_from_selected_outputs_only: bool = True
    unselected_candidates_excluded: bool = True
    checks: list[str] = Field(default_factory=list)
    keep_rules: list[str] = Field(default_factory=list)
    avoid_rules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualQualityReviewResult(V3BaseModel):
    status: str = "ready"
    review_mode: str = "metadata_preflight"
    checklist: list[str] = Field(default_factory=list)
    warning_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualQualityReviewReport(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    candidate_id: str | None = None
    output_id: str | None = None
    status: str = "pass"
    review_mode: str = "metadata_preflight"
    scores: dict[str, float] = Field(default_factory=dict)
    detected_issues: list[dict[str, Any]] = Field(default_factory=list)
    passed_checks: list[str] = Field(default_factory=list)
    warning_notes: list[str] = Field(default_factory=list)
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommercialQualityIssue(V3BaseModel):
    code: str
    severity: str = "watch"
    retryable: bool = True
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualCommercialQualityReview(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    status: str = "pass"
    review_mode: str = "commercial_quality_closure"
    variation_mode: str = "delivery_suite"
    subject_type: str = "generic"
    reference_continuity_status: str = "not_applicable"
    suite_role_coverage_status: str = "not_applicable"
    commercial_finish_status: str = "pass"
    artifact_cleanliness_status: str = "pass"
    human_realism_status: str = "not_applicable"
    issue_codes: list[str] = Field(default_factory=list)
    issues: list[CommercialQualityIssue] = Field(default_factory=list)
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HumanPhotorealismGuidance(V3BaseModel):
    guidance_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    subject_type: str = "generic"
    realism_level: str = "not_applicable"
    variation_mode: str = "delivery_suite"
    positive_prompt_fragments: list[str] = Field(default_factory=list)
    negative_prompt_fragments: list[str] = Field(default_factory=list)
    reference_preserve_rules: list[str] = Field(default_factory=list)
    reference_do_not_inherit_rules: list[str] = Field(default_factory=list)
    review_targets: list[str] = Field(default_factory=list)
    retry_patch_templates: dict[str, list[str]] = Field(default_factory=dict)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AntiAIFaceReviewResult(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    status: str = "not_applicable"
    issue_codes: list[str] = Field(default_factory=list)
    severity: str = "pass"
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrongReferenceClosurePackage(V3BaseModel):
    closure_id: str
    project_id: str | None = None
    job_id: str | None = None
    active: bool = False
    subject_type: str = "generic"
    reference_strength: str = "none"
    provider_reference_required_ids: list[str] = Field(default_factory=list)
    prompt_only_reference_ids: list[str] = Field(default_factory=list)
    identity_keep_rules: list[str] = Field(default_factory=list)
    style_keep_rules: list[str] = Field(default_factory=list)
    allowed_variations: list[str] = Field(default_factory=list)
    forbidden_drift: list[str] = Field(default_factory=list)
    provider_prompt_rules: list[str] = Field(default_factory=list)
    negative_prompt_rules: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModeQualityProfile(V3BaseModel):
    profile_id: str
    mode: str = "delivery_suite"
    user_visible_label: str = ""
    review_priorities: list[str] = Field(default_factory=list)
    pass_conditions: list[str] = Field(default_factory=list)
    retry_triggers: list[str] = Field(default_factory=list)
    prompt_guidance: list[str] = Field(default_factory=list)
    negative_guidance: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RealReviewCandidateSignal(V3BaseModel):
    candidate_id: str | None = None
    output_id: str | None = None
    status: str = "pass"
    issue_codes: list[str] = Field(default_factory=list)
    retryable_issue_codes: list[str] = Field(default_factory=list)
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    recommended_action: str = "keep"
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RealReviewSignalPackage(V3BaseModel):
    package_id: str
    project_id: str | None = None
    job_id: str | None = None
    candidate_signals: list[RealReviewCandidateSignal] = Field(default_factory=list)
    retryable_candidate_ids: list[str] = Field(default_factory=list)
    retryable_output_ids: list[str] = Field(default_factory=list)
    non_retryable_candidate_ids: list[str] = Field(default_factory=list)
    issue_summary: dict[str, int] = Field(default_factory=dict)
    issue_groups: list[str] = Field(default_factory=list)
    mode_quality_status: str = "not_evaluated"
    reference_continuity_status: str = "not_evaluated"
    commercial_readiness_status: str = "not_evaluated"
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneratedOutputResolution(V3BaseModel):
    resolution_id: str
    project_id: str | None = None
    job_id: str | None = None
    candidate_id: str | None = None
    asset_id: str | None = None
    output_id: str | None = None
    file_path: str | None = None
    preview_path: str | None = None
    thumbnail_path: str | None = None
    download_url: str | None = None
    preview_url: str | None = None
    thumbnail_url: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    provider: str | None = None
    model: str | None = None
    status: str = "missing"
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualInspectionReport(V3BaseModel):
    inspection_id: str
    project_id: str | None = None
    job_id: str | None = None
    candidate_id: str | None = None
    asset_id: str | None = None
    output_id: str | None = None
    mode: str = "metadata_only"
    status: str = "manual_review"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    score_card: dict[str, float] = Field(default_factory=dict)
    detected_issues: list[dict[str, Any]] = Field(default_factory=list)
    preserved_elements: list[str] = Field(default_factory=list)
    drift_warnings: list[str] = Field(default_factory=list)
    artifact_warnings: list[str] = Field(default_factory=list)
    retryable: bool = False
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PostGenerationReviewPackage(V3BaseModel):
    package_id: str
    project_id: str | None = None
    job_id: str
    resolutions: list[GeneratedOutputResolution] = Field(default_factory=list)
    inspections: list[VisualInspectionReport] = Field(default_factory=list)
    quality_review_reports: list[VisualQualityReviewReport] = Field(default_factory=list)
    auto_retry_decisions: list[dict[str, Any]] = Field(default_factory=list)
    real_review_signal_package: RealReviewSignalPackage | None = None
    recommended_output_ids: list[str] = Field(default_factory=list)
    hidden_output_ids: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutoRetryDecision(V3BaseModel):
    decision_id: str
    job_id: str | None = None
    project_id: str | None = None
    should_retry: bool = False
    retry_attempt: int = 0
    max_attempts: int = 1
    reason_codes: list[str] = Field(default_factory=list)
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    blocked_reason: str | None = None
    user_visible_reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommercialOutputSelection(V3BaseModel):
    selection_id: str
    project_id: str | None = None
    job_id: str | None = None
    best_output_id: str | None = None
    recommended_output_ids: list[str] = Field(default_factory=list)
    warning_output_ids: list[str] = Field(default_factory=list)
    hidden_failed_output_ids: list[str] = Field(default_factory=list)
    slot_fit: dict[str, str] = Field(default_factory=dict)
    user_visible_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdentityHeroSelectionPlan(V3BaseModel):
    plan_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    status: str = "not_applicable"
    subject_type: str = "generic"
    strategy: str = "none"
    primary_role_key: str | None = None
    identity_master_role_keys: list[str] = Field(default_factory=list)
    selected_output_id: str | None = None
    selected_candidate_id: str | None = None
    provider_reference_expected: bool = False
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    review_checks: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubjectIdentityCard(V3BaseModel):
    card_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    status: str = "not_applicable"
    subject_type: str = "generic"
    source_priority: str = "none"
    source_output_ids: list[str] = Field(default_factory=list)
    source_candidate_ids: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)
    source_anchor_ids: list[str] = Field(default_factory=list)
    source_binding_ids: list[str] = Field(default_factory=list)
    identity_keep_rules: list[str] = Field(default_factory=list)
    facial_feature_integrity_rules: list[str] = Field(default_factory=list)
    beautiful_realism_rules: list[str] = Field(default_factory=list)
    appearance_structure_rules: list[str] = Field(default_factory=list)
    allowed_variations: list[str] = Field(default_factory=list)
    forbidden_drift: list[str] = Field(default_factory=list)
    reference_requirements: list[str] = Field(default_factory=list)
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    review_checks: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BeautifulRealismBalanceReview(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    status: str = "planned"
    issue_codes: list[str] = Field(default_factory=list)
    severity: str = "pass"
    retry_patch: dict[str, Any] = Field(default_factory=dict)
    review_targets: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrictVisualReviewPolicy(V3BaseModel):
    policy_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    strictness: str = "standard"
    subject_type: str = "generic"
    retryable_issue_codes: list[str] = Field(default_factory=list)
    pass_conditions: list[str] = Field(default_factory=list)
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    review_focus: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualCapabilityClusterResult(V3BaseModel):
    cluster_id: str
    version: str
    scenario_id: str
    project_id: str | None = None
    context_version: str | None = None
    child_module_ids: list[str] = Field(default_factory=list)
    profile: VisualGrammarProfile
    project_snapshot: ProjectVisualGrammarSnapshot
    reference_binding_profile: VisualReferenceBindingProfile
    identity_lock_profiles: list[VisualIdentityLockProfile] = Field(default_factory=list)
    human_identity_anchor_profile: HumanIdentityAnchorProfile | None = None
    human_natural_variation_plan: HumanNaturalVariationPlan | None = None
    human_batch_diversity_review: HumanBatchDiversityReview | None = None
    project_identity_anchors: list[ProjectIdentityAnchor] = Field(default_factory=list)
    strong_reference_continuation_plan: StrongReferenceContinuationPlan | None = None
    general_suite_role_plan: GeneralSuiteRolePlan | None = None
    mode_execution_policy: ModeExecutionPolicy | None = None
    role_specific_generation_plan: RoleSpecificGenerationPlan | None = None
    mode_differentiation_review: ModeDifferentiationReview | None = None
    batch_identity_diversity_review: BatchIdentityDiversityReview | None = None
    human_photorealism_guidance: HumanPhotorealismGuidance | None = None
    anti_ai_face_review: AntiAIFaceReviewResult | None = None
    visual_commercial_quality_review: VisualCommercialQualityReview | None = None
    strong_reference_closure_package: StrongReferenceClosurePackage | None = None
    mode_quality_profile: ModeQualityProfile | None = None
    consistency_guard: VisualConsistencyGuardResult
    quality_review: VisualQualityReviewResult
    quality_review_reports: list[VisualQualityReviewReport] = Field(default_factory=list)
    auto_retry_decisions: list[AutoRetryDecision] = Field(default_factory=list)
    commercial_output_selection: CommercialOutputSelection | None = None
    identity_hero_selection_plan: IdentityHeroSelectionPlan | None = None
    subject_identity_card: SubjectIdentityCard | None = None
    beautiful_realism_balance_review: BeautifulRealismBalanceReview | None = None
    strict_visual_review_policy: StrictVisualReviewPolicy | None = None
    negative_visual_memory: list[dict[str, Any]] = Field(default_factory=list)
    template_consistency_policy: dict[str, Any] = Field(default_factory=dict)
    has_visual_evidence: bool = False
    user_visible_summary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
