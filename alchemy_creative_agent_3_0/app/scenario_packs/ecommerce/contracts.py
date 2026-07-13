"""V3-owned contracts for the E-Commerce Scenario Pack."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ...schemas.models import V3BaseModel


class ProductTruthLock(V3BaseModel):
    product_category: str = "generic_product"
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
    source_version: str = "ecommerce_creative_context_v1"
    product_truth: ProductTruthLock
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
