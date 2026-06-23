"""Creative direction agent."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..creative_core.rules import RULE_VERSION, creative_defaults, stable_id
from ..schemas import BrandProfile, CommercialBrief, CreativeJob, CreativePlan


class CreativeDirectorAgent(BaseAgent):
    agent_name = "CreativeDirectorAgent"

    def create_plan(
        self,
        job: CreativeJob,
        brief: CommercialBrief,
        brand_profile: BrandProfile,
    ) -> AgentResult[CreativePlan]:
        defaults = creative_defaults(brief.industry)
        tones = list(dict.fromkeys([*brand_profile.visual_tone, *brief.visual_tone]))
        colors = brand_profile.color_palette or []
        negative = list(dict.fromkeys([*brand_profile.rejected_style_tags, *brief.risks, *defaults.get("negative", [])]))
        scenario_label = brief.scenario.replace("_", " ")
        brand_tone_text = ", ".join(tones) if tones else "commercial"
        color_text = ", ".join(colors) if colors else "industry default palette"
        layout_preference = brand_profile.layout_preference or "platform-first commercial hierarchy"
        copywriting_tone = brand_profile.copywriting_tone or brief.copy_strategy
        plan = CreativePlan(
            creative_plan_id=stable_id("creative_plan", job.job_id, brief.brief_id, brand_profile.brand_id),
            job_id=job.job_id,
            brief_id=brief.brief_id,
            brand_id=brand_profile.brand_id,
            concept=f"{scenario_label} with clear commercial conversion structure",
            visual_direction=f"{defaults['visual_direction']} while preserving brand tone: {brand_tone_text}",
            composition_strategy=f"{defaults['composition']}; follow brand layout preference: {layout_preference}",
            lighting_strategy=str(defaults.get("lighting")),
            color_strategy=colors,
            materials_and_props=list(defaults.get("materials", [])),
            copy_strategy=copywriting_tone,
            consistency_strategy=f"Preserve brand tone: {brand_tone_text}. Use palette: {color_text}.",
            negative_direction=negative,
            metadata=self.metadata(
                rules_version=RULE_VERSION,
                brand_tone_used=tones,
                brand_color_palette_used=colors,
                brand_layout_preference_used=layout_preference,
                brand_copywriting_tone_used=copywriting_tone,
                selected_vertical_pack=job.metadata.get("selected_vertical_pack"),
            ),
        )
        return AgentResult(output=plan, reasoning_summary="Created commercial art direction from brief and brand profile.")
