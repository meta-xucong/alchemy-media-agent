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
        asset_metadata = layout_plan.metadata.get("asset_metadata", {})
        if not isinstance(asset_metadata, dict):
            asset_metadata = {}
        ecommerce_recipe = asset_metadata.get("ecommerce_recipe")
        if not isinstance(ecommerce_recipe, dict):
            ecommerce_recipe = None
        ecommerce_prompt = self._ecommerce_recipe_prompt(ecommerce_recipe)
        layout_notes = [
            f"platform {layout_plan.platform}",
            f"aspect ratio {layout_plan.aspect_ratio}",
            "reserve top and bottom clean text areas",
            f"brand layout preference: {brand_profile.layout_preference}" if brand_profile.layout_preference else "",
            f"brand typography preference: {brand_profile.typography_preference}" if brand_profile.typography_preference else "",
            layout_plan.background_strategy or "",
            *self._ecommerce_layout_notes(ecommerce_recipe),
        ]
        color_text = ", ".join(brand_profile.color_palette)
        rejected_text = ", ".join(brand_profile.rejected_style_tags)
        visual_prompt = (
            f"{creative_plan.visual_direction}. {creative_plan.composition_strategy}. "
            f"Commercial goal: {brief.business_goal}. Visual tone: {', '.join(style_notes)}. "
            f"Use brand palette: {color_text}. Copy tone: {brand_profile.copywriting_tone or brief.copy_strategy}. "
            "Keep product or service subject clear and prominent."
        )
        if ecommerce_prompt:
            visual_prompt = f"{visual_prompt} {ecommerce_prompt}"
        negative_parts = list(
            dict.fromkeys(
                [
                    *creative_plan.negative_direction,
                    "fake final Chinese text",
                    "unreadable text",
                    "cluttered background",
                    *self._ecommerce_negative_parts(ecommerce_recipe),
                ]
            )
        )
        hard_constraints = [
            "Use the V3-owned generation strategy selected by the product runtime.",
            "Do not render final offer text inside the image model output.",
            *self._ecommerce_hard_constraints(ecommerce_recipe),
        ]
        result = PromptCompilationResult(
            prompt_compilation_id=stable_id("prompt_compilation", layout_plan.asset_id, creative_plan.creative_plan_id),
            asset_id=layout_plan.asset_id,
            visual_prompt=visual_prompt,
            negative_prompt=", ".join(part for part in negative_parts if part),
            hard_constraints=hard_constraints,
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
                "asset_metadata": asset_metadata,
                "ecommerce_slot": asset_metadata.get("ecommerce_slot"),
                "ecommerce_recipe": ecommerce_recipe,
                "ecommerce_visual_scene": asset_metadata.get("ecommerce_visual_scene"),
                "model_text_forbidden": bool(ecommerce_recipe),
            },
            metadata=self.metadata(
                rules_version=RULE_VERSION,
                brand_id=brand_profile.brand_id,
                brand_consistency_metadata=True,
                asset_metadata=asset_metadata,
                ecommerce_slot=asset_metadata.get("ecommerce_slot"),
                ecommerce_recipe=ecommerce_recipe,
            ),
        )
        return AgentResult(output=result, reasoning_summary="Compiled provider-neutral V3 prompt contract.")

    def _ecommerce_recipe_prompt(self, recipe: dict | None) -> str:
        if not recipe:
            return ""
        facts = ", ".join(str(item) for item in recipe.get("required_product_facts", [])[:6])
        parts = [
            f"E-commerce slot: {recipe.get('slot')}",
            f"business goal: {recipe.get('business_goal')}",
            f"buyer intent: {recipe.get('buyer_intent')}",
            f"selling point to express visually without text: {recipe.get('selling_point')}",
            f"visual scene: {recipe.get('visual_scene')}",
            f"required product facts to preserve: {facts}" if facts else "",
        ]
        return ". ".join(str(part).strip() for part in parts if str(part or "").strip()) + "."

    def _ecommerce_layout_notes(self, recipe: dict | None) -> list[str]:
        if not recipe:
            return []
        notes = [
            f"ecommerce slot {recipe.get('slot')}",
            f"business goal {recipe.get('business_goal')}",
            "communicate the selling point through composition, lighting, props, and product scale",
            "leave blank space for external overlay text only",
        ]
        return [note for note in notes if note]

    def _ecommerce_hard_constraints(self, recipe: dict | None) -> list[str]:
        if not recipe:
            return []
        return [
            "Do not add in-image text, icons, badges, seals, charts, footer strips, or unsupported claims.",
            "Any planned ecommerce copy must be treated as an external overlay layer, not rendered pixels.",
            "Preserve the uploaded product identity, material cues, proportions, label placement, and packaging shape.",
            "Do not invent product functions, certifications, awards, ingredients, compatibility, or performance claims.",
        ]

    def _ecommerce_negative_parts(self, recipe: dict | None) -> list[str]:
        if not recipe:
            return []
        return [
            "generated typography",
            "feature icons",
            "claim badges",
            "comparison text",
            "fake certification seals",
            "invented product labels",
        ]
