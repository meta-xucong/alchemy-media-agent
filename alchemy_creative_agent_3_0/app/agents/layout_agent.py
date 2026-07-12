"""Layout planning agent."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..creative_core.prompt_language import product_language_allowed
from ..creative_core.rules import RULE_VERSION, extract_explicit_chinese_text, stable_id
from ..schemas import AssetSpec, BrandProfile, CommercialBrief, CreativeJob, CreativePlan, LayoutPlan, LayoutRegion, TextRenderingMode


class LayoutAgent(BaseAgent):
    agent_name = "LayoutAgent"

    def create_layout_plan(
        self,
        job: CreativeJob,
        asset: AssetSpec,
        brief: CommercialBrief,
        creative_plan: CreativePlan,
        brand_profile: BrandProfile,
    ) -> AgentResult[LayoutPlan]:
        allow_product_language = product_language_allowed(
            template_id=job.optional_template_id,
            scenario_id=job.metadata.get("scenario_id"),
            industry=brief.industry,
            asset_type=asset.asset_type,
            platform=asset.platform,
            user_input=job.raw_user_input,
            metadata={**brief.metadata, **job.metadata, **asset.metadata},
        )
        explicit_text = extract_explicit_chinese_text(job.raw_user_input)
        native_text = [value for value in [explicit_text.headline, explicit_text.cta] if value]
        product_area = LayoutRegion(
            name="product_area" if allow_product_language else "subject_area",
            position="provider_directed",
            priority=1,
            notes=creative_plan.composition_strategy,
        )
        layout = LayoutPlan(
            layout_plan_id=stable_id("layout_plan", asset.asset_id, asset.platform, asset.aspect_ratio),
            asset_id=asset.asset_id,
            platform=asset.platform,
            aspect_ratio=asset.aspect_ratio,
            text_rendering=TextRenderingMode.MODEL_TEXT_ALLOWED if native_text else TextRenderingMode.NO_TEXT,
            visual_hierarchy=["main_subject", "scene_atmosphere", *( ["provider_native_text"] if native_text else [] )],
            product_area=product_area,
            typography_strategy="provider-native typography" if native_text else None,
            background_strategy="Let the LLM and image provider choose the composition that best serves the requested subject and intent.",
            metadata=self.metadata(
                rules_version=RULE_VERSION,
                provider_native_text_requested=bool(native_text),
                provider_native_literal_text=native_text,
                layout_preference_used=brand_profile.layout_preference,
                product_language_allowed=allow_product_language,
                asset_metadata=dict(asset.metadata),
            ),
        )
        return AgentResult(output=layout, reasoning_summary="Created a provider-native image brief without external text regions.")

