"""Condition provider contracts and optional V3.4 sidecar adapters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..schemas import AssetSpec, BrandProfile, ConditionSpec, CreativePlan, LayoutPlan, ReferenceAsset


class ProviderCapabilities(BaseModel):
    name: str
    version: str
    supports_generation: bool = False
    supports_style_conditioning: bool = False
    supports_layout_conditioning: bool = False
    supports_identity_conditioning: bool = False
    supports_product_conditioning: bool = False
    supports_scoring: bool = False
    supports_text_rendering: bool = False
    supports_batch: bool = False
    requires_gpu: bool = False
    requires_network: bool = False
    is_deterministic: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseNoopProvider:
    provider_name = "noop_provider"
    provider_version = "v3.0-foundation"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(name=self.provider_name, version=self.provider_version)

    def is_available(self) -> bool:
        return True

    def health_check(self) -> dict[str, Any]:
        return {"provider_name": self.provider_name, "available": True, "runtime_mode": "planning_only"}


class StyleConditionRequest(BaseModel):
    brand_profile: BrandProfile
    asset_spec: AssetSpec
    creative_plan: CreativePlan | None = None
    reference_assets: list[ReferenceAsset] = Field(default_factory=list)
    strength: float = 0.65
    metadata: dict[str, Any] = Field(default_factory=dict)


class StyleConditionResponse(BaseModel):
    condition_spec: ConditionSpec
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutConditionRequest(BaseModel):
    asset_spec: AssetSpec
    layout_plan: LayoutPlan | None = None
    creative_plan: CreativePlan | None = None
    strength: float = 0.55
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutConditionResponse(BaseModel):
    condition_spec: ConditionSpec
    layout_map: dict[str, Any] | None = None
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdentityConditionRequest(BaseModel):
    brand_profile: BrandProfile
    asset_spec: AssetSpec
    creative_plan: CreativePlan | None = None
    reference_assets: list[ReferenceAsset] = Field(default_factory=list)
    strength: float = 0.6
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdentityConditionResponse(BaseModel):
    condition_spec: ConditionSpec
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductConditionRequest(BaseModel):
    brand_profile: BrandProfile
    asset_spec: AssetSpec
    creative_plan: CreativePlan | None = None
    reference_assets: list[ReferenceAsset] = Field(default_factory=list)
    strength: float = 0.7
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductConditionResponse(BaseModel):
    condition_spec: ConditionSpec
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StyleConditionProvider(BaseNoopProvider):
    provider_name = "style_condition_provider"
    provider_version = "v3.4-reference-conditioning-sidecars"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_style_conditioning=True,
            supports_batch=False,
            requires_gpu=False,
            requires_network=False,
            is_deterministic=True,
            metadata={"provider_family": "style_condition"},
        )

    def build_style_condition(self, request: StyleConditionRequest) -> StyleConditionResponse:
        raise NotImplementedError


class LayoutConditionProvider(BaseNoopProvider):
    provider_name = "layout_condition_provider"
    provider_version = "v3.4-reference-conditioning-sidecars"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_layout_conditioning=True,
            supports_batch=False,
            requires_gpu=False,
            requires_network=False,
            is_deterministic=True,
            metadata={"provider_family": "layout_condition"},
        )

    def build_layout_condition(self, request: LayoutConditionRequest) -> LayoutConditionResponse:
        raise NotImplementedError


class IdentityConditionProvider(BaseNoopProvider):
    provider_name = "identity_condition_provider"
    provider_version = "v3.4-reference-conditioning-sidecars"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_identity_conditioning=True,
            supports_batch=False,
            requires_gpu=False,
            requires_network=False,
            is_deterministic=True,
            metadata={"provider_family": "identity_condition"},
        )

    def build_identity_condition(self, request: IdentityConditionRequest) -> IdentityConditionResponse:
        raise NotImplementedError


class ProductConditionProvider(BaseNoopProvider):
    provider_name = "product_condition_provider"
    provider_version = "v3.4-reference-conditioning-sidecars"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_product_conditioning=True,
            supports_batch=False,
            requires_gpu=False,
            requires_network=False,
            is_deterministic=True,
            metadata={"provider_family": "product_condition"},
        )

    def build_product_condition(self, request: ProductConditionRequest) -> ProductConditionResponse:
        raise NotImplementedError


def _unique_reference_assets(reference_assets: list[ReferenceAsset]) -> list[ReferenceAsset]:
    unique: dict[str, ReferenceAsset] = {}
    for reference in reference_assets:
        unique.setdefault(reference.asset_id, reference)
    return list(unique.values())


def _select_reference_assets(reference_assets: list[ReferenceAsset], limit: int = 4) -> list[ReferenceAsset]:
    scored = sorted(
        _unique_reference_assets(reference_assets),
        key=lambda asset: (asset.score if asset.score is not None else 0.5, asset.asset_id),
        reverse=True,
    )
    return scored[:limit]


def _select_reference_assets_by_keywords(
    reference_assets: list[ReferenceAsset], keywords: set[str], limit: int = 4
) -> list[ReferenceAsset]:
    matched: list[ReferenceAsset] = []
    for asset in _unique_reference_assets(reference_assets):
        haystack = " ".join(
            [
                asset.asset_type,
                asset.purpose or "",
                " ".join(asset.style_tags),
                str(asset.metadata.get("condition_role", "")),
            ]
        ).lower()
        if any(keyword in haystack for keyword in keywords):
            matched.append(asset)
    return _select_reference_assets(matched, limit=limit)


def _clamp_strength(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


class NoopStyleConditionProvider(StyleConditionProvider):
    provider_name = "noop_style_condition_provider"
    provider_version = "v3.0-foundation"

    def build_style_condition(self, request: StyleConditionRequest) -> StyleConditionResponse:
        refs = [asset.asset_id for asset in request.reference_assets]
        condition = ConditionSpec(
            enabled=bool(refs),
            provider=self.provider_name if refs else "noop_style_condition_provider",
            reference_asset_ids=refs,
            strength=request.strength if refs else None,
            notes="Style conditioning reserved for reference assets." if refs else "No reference assets; style condition disabled.",
            metadata={
                "provider_version": self.provider_version,
                "asset_id": request.asset_spec.asset_id,
                "runtime_mode": "noop",
            },
        )
        return StyleConditionResponse(
            condition_spec=condition,
            provider_payload={},
            warnings=[] if refs else ["No reference assets were available for style conditioning."],
            metadata={"provider_name": self.provider_name, "provider_version": self.provider_version},
        )

    def build_condition(self, brand_profile: BrandProfile, asset_spec: AssetSpec) -> ConditionSpec:
        return self.build_style_condition(
            StyleConditionRequest(
                brand_profile=brand_profile,
                asset_spec=asset_spec,
                reference_assets=brand_profile.reference_assets,
            )
        ).condition_spec


class SimpleReferenceStyleProvider(StyleConditionProvider):
    provider_name = "simple_reference_style_provider"
    provider_version = "v3.4-reference-conditioning-sidecars"

    def build_style_condition(self, request: StyleConditionRequest) -> StyleConditionResponse:
        selected = _select_reference_assets(request.reference_assets)
        if not selected:
            return NoopStyleConditionProvider().build_style_condition(request)

        reference_ids = [asset.asset_id for asset in selected]
        style_tags = list(dict.fromkeys(tag for asset in selected for tag in asset.style_tags))
        strength = _clamp_strength(request.strength)
        provider_payload = {
            "reference_assets": [
                {
                    "asset_id": asset.asset_id,
                    "source": asset.source,
                    "purpose": asset.purpose,
                    "style_tags": asset.style_tags,
                    "file_path": asset.file_path,
                    "uri": asset.uri,
                    "score": asset.score,
                }
                for asset in selected
            ],
            "brand_visual_tone": request.brand_profile.visual_tone,
            "brand_palette": request.brand_profile.color_palette,
            "style_tags": style_tags,
            "conditioning_goal": "preserve reference style, palette, and commercial visual rhythm without copying content",
        }
        condition = ConditionSpec(
            enabled=True,
            provider=self.provider_name,
            reference_asset_ids=reference_ids,
            strength=strength,
            notes="Reference assets selected for deterministic style conditioning.",
            metadata={
                "provider_version": self.provider_version,
                "asset_id": request.asset_spec.asset_id,
                "runtime_mode": "optional_sidecar_interface",
                "capabilities_used": ["style_conditioning"],
                "reference_asset_count": len(reference_ids),
                "style_tags": style_tags,
                "provider_payload": provider_payload,
            },
        )
        return StyleConditionResponse(
            condition_spec=condition,
            provider_payload=provider_payload,
            metadata={
                "provider_name": self.provider_name,
                "provider_version": self.provider_version,
                "selected_reference_asset_ids": reference_ids,
            },
        )


class NoopLayoutConditionProvider(LayoutConditionProvider):
    provider_name = "noop_layout_condition_provider"
    provider_version = "v3.0-foundation"

    def build_layout_condition(self, request: LayoutConditionRequest) -> LayoutConditionResponse:
        condition = ConditionSpec(
            enabled=False,
            provider=self.provider_name,
            notes="Layout conditioning disabled in V3.0 foundation; LayoutPlan remains provider-neutral.",
            metadata={
                "provider_version": self.provider_version,
                "asset_id": request.asset_spec.asset_id,
                "runtime_mode": "noop",
            },
        )
        return LayoutConditionResponse(
            condition_spec=condition,
            layout_map=None,
            provider_payload={},
            metadata={"provider_name": self.provider_name, "provider_version": self.provider_version},
        )

    def build_condition(self, asset_spec: AssetSpec) -> ConditionSpec:
        return self.build_layout_condition(LayoutConditionRequest(asset_spec=asset_spec)).condition_spec


class RuleBasedLayoutMapProvider(LayoutConditionProvider):
    provider_name = "rule_based_layout_map_provider"
    provider_version = "v3.4-reference-conditioning-sidecars"

    def build_layout_condition(self, request: LayoutConditionRequest) -> LayoutConditionResponse:
        if request.layout_plan is None:
            disabled = NoopLayoutConditionProvider().build_layout_condition(request)
            disabled.warnings.append("LayoutPlan was missing; layout conditioning stayed disabled.")
            return disabled

        layout_map = {
            "asset_id": request.asset_spec.asset_id,
            "aspect_ratio": request.layout_plan.aspect_ratio,
            "visual_hierarchy": request.layout_plan.visual_hierarchy,
            # This sidecar is advisory only.  It deliberately has no text
            # lanes, overlay regions, or fixed copy coordinates: typography,
            # when requested, belongs to the image provider's complete frame.
            "creative_focus": {
                "subject_area": _region_payload(request.layout_plan.product_area),
                "composition_owner": "llm_and_image_provider",
            },
            "reserved_text_regions": [],
        }
        strength = _clamp_strength(request.strength)
        condition = ConditionSpec(
            enabled=True,
            provider=self.provider_name,
            reference_asset_ids=[],
            strength=strength,
            notes="LayoutPlan converted to an advisory, provider-neutral creative-focus map.",
            metadata={
                "provider_version": self.provider_version,
                "asset_id": request.asset_spec.asset_id,
                "runtime_mode": "optional_sidecar_interface",
                "capabilities_used": ["layout_conditioning"],
                "layout_plan_id": request.layout_plan.layout_plan_id,
                "layout_map": layout_map,
            },
        )
        return LayoutConditionResponse(
            condition_spec=condition,
            layout_map=layout_map,
            provider_payload={"layout_map": layout_map, "conditioning_goal": "preserve requested subject visibility without fixed text geometry"},
            metadata={
                "provider_name": self.provider_name,
                "provider_version": self.provider_version,
                "layout_plan_id": request.layout_plan.layout_plan_id,
            },
        )


class NoopIdentityConditionProvider(IdentityConditionProvider):
    provider_name = "noop_identity_condition_provider"
    provider_version = "v3.0-foundation"

    def build_identity_condition(self, request: IdentityConditionRequest) -> IdentityConditionResponse:
        selected = _select_reference_assets_by_keywords(
            request.reference_assets,
            {"identity", "face", "person", "spokesperson", "character", "model"},
        )
        reference_ids = [asset.asset_id for asset in selected]
        condition = ConditionSpec(
            enabled=False,
            provider=self.provider_name,
            reference_asset_ids=reference_ids,
            notes="Identity conditioning has no active sidecar in core tests; selected identity references are recorded only.",
            metadata={
                "provider_version": self.provider_version,
                "asset_id": request.asset_spec.asset_id,
                "runtime_mode": "noop",
                "reference_asset_count": len(reference_ids),
                "privacy_guard": "explicit user assets required before real identity conditioning",
            },
        )
        warnings = (
            ["Identity reference assets were recorded, but no identity sidecar is configured."]
            if reference_ids
            else ["No identity reference assets were available for identity conditioning."]
        )
        return IdentityConditionResponse(
            condition_spec=condition,
            provider_payload={},
            warnings=warnings,
            metadata={"provider_name": self.provider_name, "provider_version": self.provider_version},
        )

    def build_condition(
        self, asset_spec: AssetSpec, brand_profile: BrandProfile | None = None
    ) -> ConditionSpec:
        return self.build_identity_condition(
            IdentityConditionRequest(
                brand_profile=brand_profile or BrandProfile(brand_id="temp_brand_no_identity_context"),
                asset_spec=asset_spec,
                reference_assets=brand_profile.reference_assets if brand_profile else [],
            )
        ).condition_spec


class NoopProductConditionProvider(ProductConditionProvider):
    provider_name = "noop_product_condition_provider"
    provider_version = "v3.0-foundation"

    def build_product_condition(self, request: ProductConditionRequest) -> ProductConditionResponse:
        selected = _select_reference_assets_by_keywords(
            request.reference_assets,
            {"product", "packaging", "sku", "dish", "menu_item", "bottle", "device"},
        )
        reference_ids = [asset.asset_id for asset in selected]
        condition = ConditionSpec(
            enabled=False,
            provider=self.provider_name,
            reference_asset_ids=reference_ids,
            notes="Product conditioning has no active sidecar in core tests; selected product references are recorded only.",
            metadata={
                "provider_version": self.provider_version,
                "asset_id": request.asset_spec.asset_id,
                "runtime_mode": "noop",
                "reference_asset_count": len(reference_ids),
            },
        )
        warnings = (
            ["Product reference assets were recorded, but no product sidecar is configured."]
            if reference_ids
            else ["No product reference assets were available for product conditioning."]
        )
        return ProductConditionResponse(
            condition_spec=condition,
            provider_payload={},
            warnings=warnings,
            metadata={"provider_name": self.provider_name, "provider_version": self.provider_version},
        )

    def build_condition(
        self, asset_spec: AssetSpec, brand_profile: BrandProfile | None = None
    ) -> ConditionSpec:
        return self.build_product_condition(
            ProductConditionRequest(
                brand_profile=brand_profile or BrandProfile(brand_id="temp_brand_no_product_context"),
                asset_spec=asset_spec,
                reference_assets=brand_profile.reference_assets if brand_profile else [],
            )
        ).condition_spec


class NoopRendererProvider(BaseNoopProvider):
    provider_name = "noop_renderer_provider"

    def capabilities(self) -> ProviderCapabilities:
        data = super().capabilities()
        data.supports_text_rendering = True
        return data

    def render_spec(self, asset_spec: AssetSpec) -> dict[str, Any]:
        return {"provider": self.provider_name, "asset_id": asset_spec.asset_id, "runtime_mode": "no_render"}


class OptionalUnavailableProvider(BaseNoopProvider):
    provider_version = "v3.4-reference-conditioning-sidecars"
    capability_metadata: dict[str, Any] = {}
    required_capabilities: dict[str, bool] = {}

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_generation=self.required_capabilities.get("supports_generation", False),
            supports_style_conditioning=self.required_capabilities.get("supports_style_conditioning", False),
            supports_layout_conditioning=self.required_capabilities.get("supports_layout_conditioning", False),
            supports_identity_conditioning=self.required_capabilities.get("supports_identity_conditioning", False),
            supports_product_conditioning=self.required_capabilities.get("supports_product_conditioning", False),
            supports_scoring=self.required_capabilities.get("supports_scoring", False),
            supports_batch=self.required_capabilities.get("supports_batch", False),
            requires_gpu=self.required_capabilities.get("requires_gpu", True),
            requires_network=self.required_capabilities.get("requires_network", False),
            is_deterministic=False,
            metadata={**self.capability_metadata, "optional": True, "runtime_mode": "sidecar_unavailable"},
        )

    def is_available(self) -> bool:
        return False

    def health_check(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "provider_version": self.provider_version,
            "available": False,
            "runtime_mode": "sidecar_unavailable",
            "warnings": ["Optional sidecar is not configured; V3 core remains usable."],
        }

    def unavailable_condition(self, asset_spec: AssetSpec, capability: str) -> ConditionSpec:
        return ConditionSpec(
            enabled=False,
            provider=self.provider_name,
            notes=f"Optional {capability} sidecar is unavailable; fallback provider should be used.",
            metadata={
                "provider_version": self.provider_version,
                "asset_id": asset_spec.asset_id,
                "runtime_mode": "sidecar_unavailable",
                "provider_failure": {
                    "code": "provider_unavailable",
                    "severity": "warning",
                    "fallback_required": True,
                },
            },
        )


class IPAdapterProvider(OptionalUnavailableProvider):
    provider_name = "ip_adapter_provider"
    capability_metadata = {"provider_family": "reference_style", "conditioning_role": "style_or_product_reference"}
    required_capabilities = {"supports_style_conditioning": True, "requires_gpu": True}


class InstantStyleProvider(OptionalUnavailableProvider):
    provider_name = "instant_style_provider"
    capability_metadata = {"provider_family": "reference_style", "conditioning_role": "style_reference"}
    required_capabilities = {"supports_style_conditioning": True, "requires_gpu": True}


class ControlNetProvider(OptionalUnavailableProvider):
    provider_name = "control_net_provider"
    capability_metadata = {"provider_family": "layout_condition", "conditioning_role": "spatial_structure"}
    required_capabilities = {"supports_layout_conditioning": True, "requires_gpu": True}


class PhotoMakerProvider(OptionalUnavailableProvider):
    provider_name = "photo_maker_provider"
    capability_metadata = {"provider_family": "identity_condition", "conditioning_role": "person_identity"}
    required_capabilities = {"supports_identity_conditioning": True, "requires_gpu": True}


class InstantIDProvider(OptionalUnavailableProvider):
    provider_name = "instant_id_provider"
    capability_metadata = {"provider_family": "identity_condition", "conditioning_role": "face_identity"}
    required_capabilities = {"supports_identity_conditioning": True, "requires_gpu": True}


class ReferenceProductProvider(OptionalUnavailableProvider):
    provider_name = "reference_product_provider"
    capability_metadata = {"provider_family": "product_condition", "conditioning_role": "product_appearance"}
    required_capabilities = {
        "supports_style_conditioning": True,
        "supports_product_conditioning": True,
        "requires_gpu": True,
    }


class ComfyUISidecarProvider(OptionalUnavailableProvider):
    provider_name = "comfyui_sidecar_provider"
    capability_metadata = {"provider_family": "workflow_sidecar", "sidecar_type": "workflow"}
    required_capabilities = {
        "supports_generation": True,
        "supports_style_conditioning": True,
        "supports_layout_conditioning": True,
        "supports_product_conditioning": True,
        "supports_batch": True,
        "requires_gpu": True,
    }


class DiffusersProvider(OptionalUnavailableProvider):
    provider_name = "diffusers_provider"
    capability_metadata = {"provider_family": "workflow_sidecar", "sidecar_type": "python_pipeline"}
    required_capabilities = {
        "supports_generation": True,
        "supports_style_conditioning": True,
        "supports_layout_conditioning": True,
        "supports_product_conditioning": True,
        "requires_gpu": True,
    }


def _region_payload(region: Any) -> dict[str, Any] | None:
    if region is None:
        return None
    return {
        "name": region.name,
        "position": region.position,
        "priority": region.priority,
        "relative_box": region.relative_box,
        "notes": region.notes,
    }
