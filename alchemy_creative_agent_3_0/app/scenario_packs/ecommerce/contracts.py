"""V3-owned contracts for the E-Commerce Scenario Pack."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, StrictInt, field_validator, model_validator

from ...schemas.models import V3BaseModel
from ...shared_capabilities.apparel_construction import ApparelConstructionFacts


CreativeRiskFamily = Literal[
    "composition_reference_identity_contamination",
    "unselected_reference_role_leak",
    "identity_angle_mismatch",
    "pasted_face",
    "over_twisted_head",
    "template_expression",
    "dynamic_action_identity_clarity_conflict",
    "product_visibility_tradeoff",
    "product_detail_context_loss",
    "back_structure_occlusion",
    "head_body_scale_mismatch",
    "stiff_catalogue_card_direction",
    "ai_polish_or_plasticity",
]

CreativeRiskPrimaryGoalHint = Literal[
    "emotion_hero",
    "playful_interaction",
    "walking_or_lookback",
    "back_or_structure",
    "product_detail",
    "balanced_lifestyle_product",
    "safe_static_product_proof",
]

CreativeRiskLevel = Literal["low", "medium", "high"]

CreativeRiskStrategyPolicy = Literal[
    "action_triggered_expression",
    "avoid_static_presenter_grin",
    "coherent_secondary_turn",
    "avoid_over_twisted_head",
    "prefer_body_led_motion",
    "keep_face_secondary_when_back_or_profile",
    "preserve_product_truth_readability",
    "separate_composition_reference_from_identity",
    "preserve_environment_integration",
    "use_detail_role_for_close_product_evidence",
    "fail_closed_if_reference_roles_conflict",
]

CreativeRiskFailClosedReason = Literal[
    "unsafe_or_unrepresentable_reference_mix",
    "missing_required_professional_binding",
    "missing_approved_identity_view",
    "identity_strategy_unavailable",
    "reference_role_conflict",
    "product_truth_selection_contract_conflict",
    "provider_reference_capacity_unrepresentable",
    "exact_count_contract_conflict",
    "unknown_or_invalid_preflight_enum",
    "internal_field_leak_risk",
]

ProfessionalIdentityViewKind = Literal[
    "front",
    "front_three_quarter",
    "profile",
    "back",
    "none",
]

ProfessionalIdentityStrategy = Literal[
    "front_primary",
    "profile_primary",
    "secondary_face",
    "identity_not_primary",
]

CreativeRiskMode = Literal["standard", "professional"]


class EcommerceProfessionalIdentityRiskHint(V3BaseModel):
    """Professional-only identity strategy hint for E-Commerce preflight.

    It intentionally carries only resolved view kinds and strategy enums. Raw
    asset identifiers, paths, hashes, provider payloads, and prompt fragments
    are not part of this schema.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    preferred_identity_view_kind: ProfessionalIdentityViewKind
    identity_strategy: ProfessionalIdentityStrategy
    source: Literal["professional_binding_resolver"] = "professional_binding_resolver"


class EcommerceCreativeRiskItem(V3BaseModel):
    """One output-level E-Commerce creative risk preflight item."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    output_index: StrictInt = Field(ge=1)
    risk_family: list[CreativeRiskFamily] = Field(default_factory=list)
    primary_goal_hint: CreativeRiskPrimaryGoalHint
    risk_level: CreativeRiskLevel
    strategy_policy: list[CreativeRiskStrategyPolicy] = Field(default_factory=list)
    stop: bool = False
    fail_closed_reason: CreativeRiskFailClosedReason | None = None
    professional_identity_hint: EcommerceProfessionalIdentityRiskHint | None = None

    @field_validator("risk_family", "strategy_policy")
    @classmethod
    def _dedupe_non_empty_lists(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("empty_enum_list")
        if len(value) != len(set(value)):
            raise ValueError("duplicate_enum_value")
        return value

    @model_validator(mode="after")
    def _validate_stop_reason(self) -> "EcommerceCreativeRiskItem":
        if self.stop and self.fail_closed_reason is None:
            raise ValueError("fail_closed_reason_required_when_stop_true")
        if not self.stop and self.fail_closed_reason is not None:
            raise ValueError("fail_closed_reason_requires_stop_true")
        return self


class EcommerceCreativeRiskPreflight(V3BaseModel):
    """Typed E-Commerce-only creative risk preflight contract.

    Phase A only defines and validates this contract. It does not integrate the
    object into Brain payloads, provider materialization, review, storage, slot
    receipts, activation, or UI.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    contract_version: Literal["ecommerce_creative_risk_preflight_v1"] = (
        "ecommerce_creative_risk_preflight_v1"
    )
    owner: Literal["ecommerce_specialized_preflight"] = "ecommerce_specialized_preflight"
    applies_to: Literal["ecommerce"] = "ecommerce"
    mode: CreativeRiskMode
    risk_items_by_output: list[EcommerceCreativeRiskItem] = Field(default_factory=list)
    global_risks: list[CreativeRiskFamily] = Field(default_factory=list)

    @field_validator("global_risks")
    @classmethod
    def _dedupe_global_risks(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate_global_risk")
        return value

    @model_validator(mode="after")
    def _validate_professional_hint_scope(self) -> "EcommerceCreativeRiskPreflight":
        if self.mode == "standard":
            for item in self.risk_items_by_output:
                if item.professional_identity_hint is not None:
                    raise ValueError("professional_identity_hint_not_allowed_for_standard")
        return self

    def planning_gate(self, *, requested_image_count: int) -> dict[str, Any]:
        """Return the exact-N gate implied by this preflight without mutation."""

        reasons: list[str] = []
        for item in self.risk_items_by_output:
            if item.stop and item.fail_closed_reason:
                reason = str(item.fail_closed_reason)
                if reason not in reasons:
                    reasons.append(reason)
        return {
            "status": "blocked" if reasons else "ready",
            "requested_image_count": requested_image_count,
            "output_indexes_preserved": list(range(1, requested_image_count + 1)),
            "deleted_output_indexes": [],
            "split_allowed": False,
            "fallback_allowed": False,
            "prompt_patch_allowed": False,
            "fail_closed_reasons": reasons,
        }

    def authority_invariants(self) -> dict[str, Any]:
        """Document unchanged authorities guarded by the typed preflight."""

        return {
            "product_truth_selection_owner": "remote_brain_image_set_plan",
            "provider_reference_cap_owner": "provider_materializer_contract",
            "exact_n_owner": "runtime_exact_count_validation",
            "prompt_authority_owner": "remote_brain_provider_prompt_finalize",
            "preflight_may_select_product_truth": False,
            "preflight_may_change_provider_cap": False,
            "preflight_may_change_output_count": False,
            "preflight_may_author_provider_prompt": False,
        }


def validate_ecommerce_creative_risk_preflight_payload(
    payload: dict[str, Any],
    *,
    scenario_id: str,
    mode: str,
    requested_image_count: int,
    approved_identity_view_kinds: set[str] | None = None,
) -> EcommerceCreativeRiskPreflight:
    """Validate an E-Commerce creative risk preflight payload in isolation.

    This is a deterministic Phase A contract helper. It performs no Brain,
    provider, storage, receipt, slot, activation, or UI work.
    """

    if scenario_id != "ecommerce":
        raise ValueError("creative_risk_preflight_not_allowed")
    if mode not in {"standard", "professional"}:
        raise ValueError("creative_risk_preflight_mode_invalid")
    if requested_image_count < 1:
        raise ValueError("requested_image_count_invalid")

    preflight = EcommerceCreativeRiskPreflight.model_validate(payload)
    if preflight.mode != mode:
        raise ValueError("creative_risk_preflight_mode_mismatch")

    seen_indexes: set[int] = set()
    for item in preflight.risk_items_by_output:
        if item.output_index in seen_indexes:
            raise ValueError("duplicate_output_index")
        seen_indexes.add(item.output_index)
        if item.output_index > requested_image_count:
            raise ValueError("output_index_out_of_range")
        hint = item.professional_identity_hint
        if hint is None:
            continue
        if mode != "professional":
            raise ValueError("professional_identity_hint_not_allowed")
        if approved_identity_view_kinds is None:
            raise ValueError("professional_binding_views_required")
        preferred_view = str(hint.preferred_identity_view_kind)
        if preferred_view != "none" and preferred_view not in approved_identity_view_kinds:
            raise ValueError("preferred_identity_view_not_approved")
    return preflight


class ProductTruthLock(V3BaseModel):
    product_category: str = "generic_product"
    apparel_construction: ApparelConstructionFacts | None = None
    visible_attributes: list[str] = Field(default_factory=list)
    immutable_attributes: list[str] = Field(default_factory=list)
    allowed_scene_changes: list[str] = Field(default_factory=list)
    forbidden_transformations: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
    review_obligations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApparelOnModelEvidenceProfile(V3BaseModel):
    """E-Commerce evidence boundary for a Brain-directed apparel-on-model set.

    This is intentionally not an image recipe: it never names a slot, scene,
    pose, camera, crop, or output order.  The remote Brain maps the available
    dimensions to the requested outputs and the runtime freezes that result.
    """

    applies: bool = False
    source_evidence: list[str] = Field(default_factory=list)
    allowed_evidence_dimensions: list[str] = Field(default_factory=list)
    required_distinct_dimension_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommerceIntelligenceBrief(V3BaseModel):
    target_audience: list[str] = Field(default_factory=list)
    buying_motivations: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    trust_drivers: list[str] = Field(default_factory=list)
    keyword_intent_map: list[dict[str, str]] = Field(default_factory=list)
    competitor_patterns: list[str] = Field(default_factory=list)
    differentiated_selling_points: list[str] = Field(default_factory=list)
    visual_strategy: list[str] = Field(default_factory=list)
    claim_risk_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketplaceRuleProfile(V3BaseModel):
    platform: str = "generic"
    market: str = "global"
    image_slots: list[str] = Field(default_factory=list)
    canvas_rules: dict[str, Any] = Field(default_factory=dict)
    content_rules: list[str] = Field(default_factory=list)
    export_rules: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcommerceCreativeContext(V3BaseModel):
    """Factual, versioned input to the remote Brain for a new job.

    This is deliberately not an image recipe.  It contains no slot order,
    camera, crop, scene, typography, or renderer instruction.
    """

    context_id: str
    source_version: str = "ecommerce_creative_context_v2"
    product_truth: ProductTruthLock
    apparel_on_model_evidence_profile: ApparelOnModelEvidenceProfile | None = None
    platform_constraints: dict[str, Any] = Field(default_factory=dict)
    category_evidence_questions: list[str] = Field(default_factory=list)
    seller_inputs: dict[str, Any] = Field(default_factory=dict)
    approved_literal_copy: str | None = None
    copy_locale: str | None = None
    claim_risk_warnings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcommerceAssetRecipe(V3BaseModel):
    slot: str
    business_goal: str
    selling_point: str
    buyer_intent: str
    required_product_facts: list[str] = Field(default_factory=list)
    visual_scene: str
    # Retained for historical payload reads only. New recipes leave it empty;
    # approved copy is a provider-native request, never an overlay operation.
    overlay_text: str | None = None
    provider_native_text: str | None = None
    reference_bindings: list[str] = Field(default_factory=list)
    review_checks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommerceCriticReport(V3BaseModel):
    status: str = "ready"
    checks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcommerceExportPackage(V3BaseModel):
    package_id: str
    platform: str
    market: str
    files: list[dict[str, Any]] = Field(default_factory=list)
    naming_pattern: str
    dimensions: dict[str, str] = Field(default_factory=dict)
    review_status: str = "metadata_ready"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcommercePackOutput(V3BaseModel):
    product_truth: ProductTruthLock
    commerce_brief: CommerceIntelligenceBrief
    marketplace_profile: MarketplaceRuleProfile
    recipes: list[EcommerceAssetRecipe] = Field(default_factory=list)
    critic: CommerceCriticReport
    export_package: EcommerceExportPackage
    creative_context: EcommerceCreativeContext | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
