"""Prompt compiler agent."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..creative_core.rules import NO_FAKE_TEXT_PROVIDER_NOTE, RULE_VERSION, stable_id
from ..schemas import BrandProfile, CommercialBrief, CreativePlan, LayoutPlan, PromptCompilationResult


class PromptCompilerAgent(BaseAgent):
    agent_name = "PromptCompilerAgent"

    def compile_prompt(
        self,
        brief: CommercialBrief,
        creative_plan: CreativePlan,
        layout_plan: LayoutPlan,
        brand_profile: BrandProfile,
    ) -> AgentResult[PromptCompilationResult]:
        style_notes = list(dict.fromkeys([*brief.visual_tone, *brand_profile.visual_tone]))
        layout_notes = [
            f"platform {layout_plan.platform}",
            f"aspect ratio {layout_plan.aspect_ratio}",
            "reserve top and bottom clean text areas",
            f"brand layout preference: {brand_profile.layout_preference}" if brand_profile.layout_preference else "",
            f"brand typography preference: {brand_profile.typography_preference}" if brand_profile.typography_preference else "",
            layout_plan.background_strategy or "",
        ]
        color_text = ", ".join(brand_profile.color_palette)
        rejected_text = ", ".join(brand_profile.rejected_style_tags)
        visual_prompt = (
            f"{creative_plan.visual_direction}. {creative_plan.composition_strategy}. "
            f"Commercial goal: {brief.business_goal}. Visual tone: {', '.join(style_notes)}. "
            f"Use brand palette: {color_text}. Copy tone: {brand_profile.copywriting_tone or brief.copy_strategy}. "
            "Keep product or service subject clear and prominent."
        )
        negative_parts = list(dict.fromkeys([*creative_plan.negative_direction, "fake final Chinese text", "unreadable text", "cluttered background"]))
        result = PromptCompilationResult(
            prompt_compilation_id=stable_id("prompt_compilation", layout_plan.asset_id, creative_plan.creative_plan_id),
            asset_id=layout_plan.asset_id,
            visual_prompt=visual_prompt,
            negative_prompt=", ".join(part for part in negative_parts if part),
            hard_constraints=[
                "Use V3 planning-only provider strategy in foundation phase.",
                "Do not render final offer text inside the image model output.",
            ],
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=style_notes,
            layout_notes=[note for note in layout_notes if note],
            provider_notes={
                "text_overlay_required": True,
                "reserve_clean_text_areas": True,
                "avoid_fake_chinese_text": True,
                "required_note": NO_FAKE_TEXT_PROVIDER_NOTE,
                "brand_consistency": f"Preserve brand tone: {', '.join(style_notes)}. Use palette: {color_text}.",
                "negative_style_constraints": rejected_text,
                "copywriting_tone": brand_profile.copywriting_tone or brief.copy_strategy,
                "layout_preference": brand_profile.layout_preference,
            },
            metadata=self.metadata(
                rules_version=RULE_VERSION,
                brand_id=brand_profile.brand_id,
                brand_consistency_metadata=True,
            ),
        )
        return AgentResult(output=result, reasoning_summary="Compiled provider-neutral V3 prompt contract.")
