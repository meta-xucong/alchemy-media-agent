"""Generation routing agent for V3.0 planning-only mode."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..condition_engine.providers import (
    NoopIdentityConditionProvider,
    NoopLayoutConditionProvider,
    NoopProductConditionProvider,
    NoopStyleConditionProvider,
    RuleBasedLayoutMapProvider,
    IdentityConditionRequest,
    SimpleReferenceStyleProvider,
    ProductConditionRequest,
    LayoutConditionProvider,
    LayoutConditionRequest,
    StyleConditionProvider,
    StyleConditionRequest,
)
from ..creative_core.rules import RULE_VERSION, stable_id
from ..schemas import (
    AssetSpec,
    BrandProfile,
    ConditionPlan,
    CreativePlan,
    GenerationPlan,
    LayoutPlan,
    PromptCompilationResult,
    ProviderStrategy,
)


class GenerationRouterAgent(BaseAgent):
    agent_name = "GenerationRouterAgent"

    def __init__(
        self,
        style_provider: StyleConditionProvider | None = None,
        layout_provider: LayoutConditionProvider | None = None,
        enable_reference_conditioning: bool = True,
        enable_layout_conditioning: bool = True,
    ) -> None:
        self.style_provider = style_provider
        self.layout_provider = layout_provider
        self.enable_reference_conditioning = enable_reference_conditioning
        self.enable_layout_conditioning = enable_layout_conditioning
        self.identity_provider = NoopIdentityConditionProvider()
        self.product_provider = NoopProductConditionProvider()

    def create_generation_contracts(
        self,
        asset: AssetSpec,
        brand_profile: BrandProfile,
        prompt: PromptCompilationResult,
        provider_strategy: ProviderStrategy = ProviderStrategy.PLANNING_ONLY,
        layout_plan: LayoutPlan | None = None,
        creative_plan: CreativePlan | None = None,
    ) -> AgentResult[tuple[ConditionPlan, GenerationPlan]]:
        style_provider = self._select_style_provider(brand_profile)
        layout_provider = self._select_layout_provider(layout_plan)
        style_response = style_provider.build_style_condition(
            StyleConditionRequest(
                brand_profile=brand_profile,
                asset_spec=asset,
                creative_plan=creative_plan,
                reference_assets=brand_profile.reference_assets,
                metadata={"prompt_compilation_id": prompt.prompt_compilation_id},
            )
        )
        layout_response = layout_provider.build_layout_condition(
            LayoutConditionRequest(
                asset_spec=asset,
                layout_plan=layout_plan,
                creative_plan=creative_plan,
                metadata={"prompt_compilation_id": prompt.prompt_compilation_id},
            )
        )
        style_spec = style_response.condition_spec
        layout_spec = layout_response.condition_spec
        identity_response = self.identity_provider.build_identity_condition(
            IdentityConditionRequest(
                brand_profile=brand_profile,
                asset_spec=asset,
                creative_plan=creative_plan,
                reference_assets=brand_profile.reference_assets,
                metadata={"prompt_compilation_id": prompt.prompt_compilation_id},
            )
        )
        product_response = self.product_provider.build_product_condition(
            ProductConditionRequest(
                brand_profile=brand_profile,
                asset_spec=asset,
                creative_plan=creative_plan,
                reference_assets=brand_profile.reference_assets,
                metadata={"prompt_compilation_id": prompt.prompt_compilation_id},
            )
        )
        identity_spec = identity_response.condition_spec
        product_spec = product_response.condition_spec
        provider_warnings = list(
            dict.fromkeys(
                [
                    *style_response.warnings,
                    *layout_response.warnings,
                    *identity_response.warnings,
                    *product_response.warnings,
                ]
            )
        )
        condition_plan = ConditionPlan(
            condition_plan_id=stable_id("condition_plan", asset.asset_id, brand_profile.brand_id),
            asset_id=asset.asset_id,
            style_condition=style_spec,
            layout_condition=layout_spec,
            identity_condition=identity_spec,
            product_condition=product_spec,
            metadata=self.metadata(
                rules_version=RULE_VERSION,
                provider_strategy=provider_strategy.value,
                prompt_compilation_id=prompt.prompt_compilation_id,
                provider_routing={
                    "style_provider": style_spec.provider,
                    "layout_provider": layout_spec.provider,
                    "identity_provider": identity_spec.provider,
                    "product_provider": product_spec.provider,
                    "style_condition_enabled": style_spec.enabled,
                    "layout_condition_enabled": layout_spec.enabled,
                    "identity_condition_enabled": identity_spec.enabled,
                    "product_condition_enabled": product_spec.enabled,
                    "optional_sidecars": True,
                },
                provider_warnings=provider_warnings,
            ),
        )
        generation_plan = GenerationPlan(
            generation_plan_id=stable_id("generation_plan", asset.asset_id, prompt.prompt_compilation_id),
            asset_id=asset.asset_id,
            provider_strategy=provider_strategy,
            candidate_count=4,
            quality_threshold=0.78,
            max_refine_rounds=2,
            scorers=["mock_scoring_provider"] if provider_strategy == ProviderStrategy.MOCK_GENERATION else ["rule_based_planning_scorer"],
            rendering_required=asset.requires_text_overlay,
            metadata=self.metadata(
                rules_version=RULE_VERSION,
                condition_plan_id=condition_plan.condition_plan_id,
                provider_strategy=provider_strategy.value,
                routed_condition_providers={
                    "style": style_spec.provider,
                    "layout": layout_spec.provider,
                    "identity": identity_spec.provider,
                    "product": product_spec.provider,
                },
            ),
        )
        summary = (
            "Selected mock generation route for closed-loop candidate evaluation."
            if provider_strategy == ProviderStrategy.MOCK_GENERATION
            else "Selected planning-only generation route."
        )
        return AgentResult(output=(condition_plan, generation_plan), reasoning_summary=summary)

    def _select_style_provider(self, brand_profile: BrandProfile) -> StyleConditionProvider:
        if self.style_provider is not None:
            return self.style_provider
        if self.enable_reference_conditioning and brand_profile.reference_assets:
            return SimpleReferenceStyleProvider()
        return NoopStyleConditionProvider()

    def _select_layout_provider(self, layout_plan: LayoutPlan | None) -> LayoutConditionProvider:
        if self.layout_provider is not None:
            return self.layout_provider
        if self.enable_layout_conditioning and layout_plan is not None:
            return RuleBasedLayoutMapProvider()
        return NoopLayoutConditionProvider()
