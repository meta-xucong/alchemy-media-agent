"""V3-owned contracts for the E-Commerce Scenario Pack."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ...schemas.models import V3BaseModel


class ProductFactRecord(V3BaseModel):
    """One source-aware product fact for E-Commerce planning and review."""

    fact_id: str
    label: str
    value: str
    source_type: str = "user_confirmed"
    verification: str = "verified"
    visual_channels: list[str] = Field(default_factory=lambda: ["product"])
    allowed_slot_ids: list[str] = Field(default_factory=list)
    claim_eligible: bool = False
    review_requirement: str = "none"


class ProductTruthLock(V3BaseModel):
    product_category: str = "generic_product"
    visible_attributes: list[str] = Field(default_factory=list)
    immutable_attributes: list[str] = Field(default_factory=list)
    fact_ledger: list[ProductFactRecord] = Field(default_factory=list)
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
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
