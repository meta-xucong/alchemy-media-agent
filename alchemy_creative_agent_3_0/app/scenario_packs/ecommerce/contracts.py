"""V3-owned contracts for the E-Commerce Scenario Pack."""

from __future__ import annotations

from typing import Any, Literal, Mapping, get_args

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

ProfessionalEcommercePoseRole = Literal[
    "seated_poolside",
    "standing_poolside",
]

ProfessionalEcommerceStandingRequirement = Literal[
    "both_feet_weight_bearing",
    "no_kneeling",
    "no_crouched_low_support",
    "interaction_may_use_one_hand_but_body_remains_standing",
]

ProfessionalEcommerceStandingPresentationRequirement = Literal[
    "front_or_three_quarter_presentation",
    "ordinary_full_body_commercial_framing",
    "eye_level_or_standard_camera_height",
    "no_rear_facing_lookback",
]

_REQUIRED_STANDING_REQUIREMENTS = set(get_args(ProfessionalEcommerceStandingRequirement))
_REQUIRED_STANDING_PRESENTATION_REQUIREMENTS = set(
    get_args(ProfessionalEcommerceStandingPresentationRequirement)
)

ECOMMERCE_CREATIVE_RISK_ALLOWED_VALUES: dict[str, tuple[str, ...]] = {
    "contract_version": ("ecommerce_creative_risk_preflight_v1",),
    "mode": get_args(CreativeRiskMode),
    "risk_family": get_args(CreativeRiskFamily),
    "global_risks": get_args(CreativeRiskFamily),
    "primary_goal_hint": get_args(CreativeRiskPrimaryGoalHint),
    "risk_level": get_args(CreativeRiskLevel),
    "strategy_policy": get_args(CreativeRiskStrategyPolicy),
    "preferred_identity_view_kind": get_args(ProfessionalIdentityViewKind),
    "identity_strategy": get_args(ProfessionalIdentityStrategy),
    "professional_identity_hint_source": ("professional_binding_resolver",),
}


_PROFESSIONAL_VIEW_KIND_BY_SELECTOR = {
    "front": "front",
    "face_front": "front",
    "standard_front": "front",
    "front_1": "front",
    "front_three_quarter": "front_three_quarter",
    "face_front_three_quarter": "front_three_quarter",
    "three_quarter": "front_three_quarter",
    "three_quarter_1": "front_three_quarter",
    "left_front_45": "front_three_quarter",
    "right_front_45": "front_three_quarter",
    "profile": "profile",
    "face_profile": "profile",
    "profile_1": "profile",
    "side": "profile",
    "back": "back",
    "rear_head": "back",
    "face_rear_head": "back",
}


class EcommerceProfessionalIdentityRiskHint(V3BaseModel):
    """Professional-only identity strategy hint for E-Commerce preflight.

    It intentionally carries only resolver-selected view kinds and strategy
    enums. Raw asset identifiers, paths, hashes, provider payloads, and prompt
    fragments are not part of this schema.
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

    This model owns only the typed schema and deterministic validation. Brain
    payload allowlisting and pre-Brain fail-closed gates are owned by the
    adapter/runtime layers. The model itself still does not own provider
    materialization, review, storage, slot receipts, activation, or UI.
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
        item_risks = {
            risk
            for item in self.risk_items_by_output
            for risk in item.risk_family
        }
        if not set(self.global_risks).issubset(item_risks):
            raise ValueError("global_risks_must_be_subset_of_output_risk_family")
        return self

    def planning_gate(self, *, requested_image_count: int) -> dict[str, Any]:
        """Return the exact-N gate implied by this preflight without mutation."""

        reasons: list[str] = []
        if requested_image_count < 1:
            reasons.append("requested_image_count_invalid")

        seen_indexes: set[int] = set()
        for item in self.risk_items_by_output:
            if item.output_index in seen_indexes and "duplicate_output_index" not in reasons:
                reasons.append("duplicate_output_index")
            seen_indexes.add(item.output_index)
            if (
                requested_image_count >= 1
                and item.output_index > requested_image_count
                and "output_index_out_of_range" not in reasons
            ):
                reasons.append("output_index_out_of_range")
            if item.stop and item.fail_closed_reason:
                reason = str(item.fail_closed_reason)
                if reason not in reasons:
                    reasons.append(reason)
        output_indexes_preserved = (
            list(range(1, requested_image_count + 1))
            if requested_image_count >= 1
            else []
        )
        return {
            "status": "blocked" if reasons else "ready",
            "requested_image_count": requested_image_count,
            "output_indexes_preserved": output_indexes_preserved,
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

    def shared_human_realism_review_context(
        self,
        *,
        requested_image_count: int,
    ) -> dict[str, Any]:
        """Project E-Commerce risk context into shared Human Realism review.

        The projection is intentionally not a Provider prompt, retry patch,
        image metric, or local reviewer decision.  It carries only typed,
        public-safe risk context so the shared Human Realism/review owner can
        decide post-generation quality without E-Commerce taking ownership of
        pixel gates.
        """

        gate = self.planning_gate(requested_image_count=requested_image_count)
        if gate.get("status") == "blocked":
            raise ValueError("creative_risk_preflight_blocked")
        items: list[dict[str, Any]] = []
        for item in self.risk_items_by_output:
            payload = {
                "output_index": item.output_index,
                "risk_family": list(item.risk_family),
                "primary_goal_hint": item.primary_goal_hint,
                "risk_level": item.risk_level,
                "strategy_policy": list(item.strategy_policy),
            }
            if item.professional_identity_hint is not None:
                payload["professional_identity_hint"] = (
                    item.professional_identity_hint.model_dump(mode="json")
                )
            items.append(payload)
        return {
            "contract_version": "ecommerce_human_realism_review_context_v1",
            "owner": "shared_human_realism_review",
            "source": "ecommerce_creative_risk_preflight",
            "source_contract_version": self.contract_version,
            "applies_to": "ecommerce",
            "mode": self.mode,
            "requested_image_count": requested_image_count,
            "risk_items_by_output": items,
            "global_risks": list(self.global_risks),
            "post_review_authority": "shared_human_realism_review",
            "retry_authority": "shared_human_realism_review",
            "ecommerce_may_score_pixels": False,
            "ecommerce_may_trigger_retry": False,
        }


def professional_identity_view_kinds_from_selectors(
    view_selectors: list[str] | tuple[str, ...] | set[str],
) -> set[str]:
    """Project server-owned view selectors into the public E24 view-kind enum."""

    kinds: set[str] = set()
    for selector in view_selectors:
        cleaned = str(selector or "").strip().lower()
        kind = _PROFESSIONAL_VIEW_KIND_BY_SELECTOR.get(cleaned)
        if kind:
            kinds.add(kind)
    return kinds


def build_professional_ecommerce_identity_preflight(
    *,
    requested_image_count: int,
    professional_identity_hints_by_output: Mapping[int, dict[str, Any] | EcommerceProfessionalIdentityRiskHint],
    approved_identity_view_kinds: set[str],
) -> EcommerceCreativeRiskPreflight:
    """Build the Phase 4 Professional-only identity coherence preflight.

    The contributor emits only closed risk enums and explicit view-kind/strategy
    hints already chosen by the Professional binding resolver. It validates
    those hints against approved binding views, but it never ranks, chooses, or
    substitutes from an approved view set.
    """

    if not isinstance(requested_image_count, int) or isinstance(requested_image_count, bool):
        raise ValueError("requested_image_count_invalid")
    if requested_image_count < 1:
        raise ValueError("requested_image_count_invalid")
    expected_indexes = set(range(1, requested_image_count + 1))
    actual_indexes: set[int] = set()
    hints_by_output: dict[int, EcommerceProfessionalIdentityRiskHint] = {}
    for raw_index, raw_hint in professional_identity_hints_by_output.items():
        if not isinstance(raw_index, int) or isinstance(raw_index, bool):
            raise ValueError("professional_identity_hint_output_index_invalid") from None
        output_index = raw_index
        if output_index in actual_indexes:
            raise ValueError("professional_identity_hint_output_index_duplicate")
        actual_indexes.add(output_index)
        if output_index < 1 or output_index > requested_image_count:
            raise ValueError("professional_identity_hint_output_index_out_of_range")
        hint = (
            raw_hint
            if isinstance(raw_hint, EcommerceProfessionalIdentityRiskHint)
            else EcommerceProfessionalIdentityRiskHint.model_validate(raw_hint)
        )
        preferred_view = str(hint.preferred_identity_view_kind)
        if preferred_view != "none" and preferred_view not in approved_identity_view_kinds:
            raise ValueError("preferred_identity_view_not_approved")
        hints_by_output[output_index] = hint
    if actual_indexes != expected_indexes:
        raise ValueError("professional_identity_hint_missing")
    return EcommerceCreativeRiskPreflight(
        mode="professional",
        global_risks=[
            "identity_angle_mismatch",
            "pasted_face",
            "head_body_scale_mismatch",
        ],
        risk_items_by_output=[
            EcommerceCreativeRiskItem(
                output_index=index,
                risk_family=[
                    "identity_angle_mismatch",
                    "pasted_face",
                    "head_body_scale_mismatch",
                ],
                primary_goal_hint="balanced_lifestyle_product",
                risk_level="medium",
                strategy_policy=[
                    "coherent_secondary_turn",
                    "avoid_over_twisted_head",
                    "prefer_body_led_motion",
                    "separate_composition_reference_from_identity",
                ],
                professional_identity_hint=hints_by_output[index],
            )
            for index in range(1, requested_image_count + 1)
        ],
    )


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


def ecommerce_human_realism_review_context_from_preflight_payload(
    payload: dict[str, Any],
    *,
    scenario_id: str,
    mode: str,
    requested_image_count: int,
    approved_identity_view_kinds: set[str] | None = None,
) -> dict[str, Any]:
    """Validate and project E24 context for the shared review owner only."""

    preflight = validate_ecommerce_creative_risk_preflight_payload(
        payload,
        scenario_id=scenario_id,
        mode=mode,
        requested_image_count=requested_image_count,
        approved_identity_view_kinds=approved_identity_view_kinds,
    )
    return preflight.shared_human_realism_review_context(
        requested_image_count=requested_image_count
    )


class ProfessionalEcommercePoseContractItem(V3BaseModel):
    """One output-level Professional E-Commerce pose acceptance requirement.

    It is a deliverable contract, not renderer prose. The Remote Brain must
    return the same closed role in `image_set_plan`, and native planning can
    reject a host-bound output before rendering when the role is missing or
    contradictory.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    output_index: StrictInt = Field(ge=1)
    pose_role: ProfessionalEcommercePoseRole
    standing_requirements: list[ProfessionalEcommerceStandingRequirement] = Field(default_factory=list)
    standing_presentation_requirements: list[ProfessionalEcommerceStandingPresentationRequirement] = Field(
        default_factory=list
    )

    @field_validator("standing_requirements")
    @classmethod
    def _dedupe_standing_requirements(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate_standing_requirement")
        return value

    @field_validator("standing_presentation_requirements")
    @classmethod
    def _dedupe_standing_presentation_requirements(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate_standing_presentation_requirement")
        return value

    @model_validator(mode="after")
    def _validate_pose_requirements(self) -> "ProfessionalEcommercePoseContractItem":
        if self.pose_role == "standing_poolside":
            if set(self.standing_requirements) != _REQUIRED_STANDING_REQUIREMENTS:
                raise ValueError("standing_requirements_incomplete")
            if set(self.standing_presentation_requirements) != _REQUIRED_STANDING_PRESENTATION_REQUIREMENTS:
                raise ValueError("standing_presentation_requirements_incomplete")
        elif self.standing_requirements:
            raise ValueError("standing_requirements_only_for_standing_pose")
        elif self.standing_presentation_requirements:
            raise ValueError("standing_presentation_requirements_only_for_standing_pose")
        return self


class ProfessionalEcommercePoseContract(V3BaseModel):
    """Closed Professional E-Commerce deliverable pose acceptance contract.

    This may be produced only by the server-side Professional E-Commerce
    planning layer after explicit deliverable coverage requirements are known.
    It carries no raw IDs, paths, hashes, provider payloads, or prompt
    fragments.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    contract_version: Literal["professional_ecommerce_pose_contract_v2"] = (
        "professional_ecommerce_pose_contract_v2"
    )
    owner: Literal["professional_ecommerce_deliverable_pose_acceptance"] = (
        "professional_ecommerce_deliverable_pose_acceptance"
    )
    source: Literal["explicit_user_pose_coverage_request"] = "explicit_user_pose_coverage_request"
    required_pose_by_output: list[ProfessionalEcommercePoseContractItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_indexes(self) -> "ProfessionalEcommercePoseContract":
        indexes = [item.output_index for item in self.required_pose_by_output]
        if not indexes:
            raise ValueError("pose_contract_empty")
        if len(indexes) != len(set(indexes)):
            raise ValueError("duplicate_pose_contract_output_index")
        return self


def build_professional_ecommerce_poolside_pose_contract(
    *,
    requested_image_count: int,
) -> ProfessionalEcommercePoseContract:
    """Build the explicit exact-N=2 seated/standing poolside contract."""

    if type(requested_image_count) is not int or requested_image_count != 2:
        raise ValueError("poolside_pose_contract_requires_exact_two")
    return ProfessionalEcommercePoseContract(
        required_pose_by_output=[
            ProfessionalEcommercePoseContractItem(
                output_index=1,
                pose_role="seated_poolside",
            ),
            ProfessionalEcommercePoseContractItem(
                output_index=2,
                pose_role="standing_poolside",
                standing_requirements=sorted(_REQUIRED_STANDING_REQUIREMENTS),
                standing_presentation_requirements=sorted(_REQUIRED_STANDING_PRESENTATION_REQUIREMENTS),
            ),
        ]
    )


def validate_professional_ecommerce_pose_contract_payload(
    payload: Any,
    *,
    requested_image_count: int,
) -> ProfessionalEcommercePoseContract:
    if type(requested_image_count) is not int or requested_image_count < 1:
        raise ValueError("pose_contract_requested_image_count_invalid")
    contract = ProfessionalEcommercePoseContract.model_validate(payload)
    indexes = [item.output_index for item in contract.required_pose_by_output]
    if sorted(indexes) != list(range(1, requested_image_count + 1)):
        raise ValueError("pose_contract_exact_n_mismatch")
    return contract


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
    provider_reference_budget: dict[str, int] = Field(default_factory=dict)
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
