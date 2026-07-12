"""Prompt compiler agent."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..creative_core.prompt_language import (
    general_negated_retail_constraints,
    product_language_allowed,
    split_positive_and_negative_prompt,
    strip_negated_product_phrases,
)
from ..creative_core.rules import NO_FAKE_TEXT_PROVIDER_NOTE, RULE_VERSION, stable_id
from ..schemas import BrandProfile, CommercialBrief, CreativePlan, LayoutPlan, PromptCompilationResult


SINGLE_FRAME_HARD_CONSTRAINT = (
    "Each generated output must be one single complete image frame, not a collage, split-screen, contact sheet, "
    "storyboard, before-after comparison, or multi-panel layout."
)
SINGLE_FRAME_NEGATIVE_PARTS = [
    "collage",
    "split screen",
    "multi-panel layout",
    "contact sheet",
    "storyboard",
    "before-after comparison",
    "duplicated frames",
    "grid of separate images inside one output",
]


class PromptCompilerAgent(BaseAgent):
    agent_name = "PromptCompilerAgent"

    def compile_prompt(
        self,
        brief: CommercialBrief,
        creative_plan: CreativePlan,
        layout_plan: LayoutPlan,
        brand_profile: BrandProfile,
        llm_brain: dict | None = None,
    ) -> AgentResult[PromptCompilationResult]:
        style_notes = list(dict.fromkeys([*brief.visual_tone, *brand_profile.visual_tone]))
        brain_guidance = self._brain_prompt_guidance(llm_brain)
        raw_user_request = self._user_request_brief(brief)
        positive_user_request, explicit_negative_parts = split_positive_and_negative_prompt(raw_user_request)
        allow_product_language = product_language_allowed(
            template_id=brief.metadata.get("template_id"),
            scenario_id=brief.metadata.get("scenario_id"),
            industry=brief.industry,
            platform=layout_plan.platform,
            user_input=positive_user_request or raw_user_request,
            metadata={**brief.metadata, **layout_plan.metadata},
        )
        user_request_source = positive_user_request or raw_user_request
        user_request = user_request_source if allow_product_language else strip_negated_product_phrases(user_request_source)
        for note in brain_guidance.get("style_notes", []):
            if note and note not in style_notes:
                style_notes.append(note)
        asset_metadata = layout_plan.metadata.get("asset_metadata", {})
        if not isinstance(asset_metadata, dict):
            asset_metadata = {}
        mode_role_recipe = asset_metadata.get("mode_role_recipe")
        if not isinstance(mode_role_recipe, dict):
            mode_role_recipe = {}
        mode_execution_policy = asset_metadata.get("mode_execution_policy")
        if not isinstance(mode_execution_policy, dict):
            mode_execution_policy = {}
        ecommerce_recipe = asset_metadata.get("ecommerce_recipe")
        if not isinstance(ecommerce_recipe, dict):
            ecommerce_recipe = None
        ecommerce_prompt = self._ecommerce_recipe_prompt(ecommerce_recipe)
        general_external_copy_tone = self._general_external_copy_tone(brand_profile)
        layout_notes = [
            f"platform {layout_plan.platform}",
            f"aspect ratio {layout_plan.aspect_ratio}",
            "reserve top and bottom clean text areas" if allow_product_language else "reserve optional clean blank areas",
            f"brand layout preference: {brand_profile.layout_preference}" if brand_profile.layout_preference else "",
            f"brand typography preference: {brand_profile.typography_preference}" if brand_profile.typography_preference else "",
            layout_plan.background_strategy or "",
            *self._ecommerce_layout_notes(ecommerce_recipe),
        ]
        color_text = ", ".join(brand_profile.color_palette)
        rejected_text = ", ".join(brand_profile.rejected_style_tags)
        user_request_prefix = (
            f"User request and required subject/content: {user_request}. "
            if user_request
            else ""
        )
        if allow_product_language:
            visual_prompt = (
                f"{user_request_prefix}{creative_plan.visual_direction}. {creative_plan.composition_strategy}. "
                f"Commercial goal: {brief.business_goal}. Visual tone: {', '.join(style_notes)}. "
                f"Use brand palette: {color_text}. Copy tone: {brand_profile.copywriting_tone or brief.copy_strategy}. "
                "Keep product or service subject clear and prominent."
            )
        else:
            general_style_notes = [
                self._generalize_non_product_text(note) for note in style_notes
            ]
            visual_prompt = (
                f"{user_request_prefix}"
                f"{self._generalize_non_product_text(creative_plan.visual_direction)}. "
                f"{self._generalize_non_product_text(creative_plan.composition_strategy)}. "
                f"Output goal: {self._general_output_goal(brief.business_goal)}. Visual tone: {', '.join(style_notes)}. "
                f"Use palette as image atmosphere only: {color_text}. "
                "Keep the requested subject, scene, style, and mood clear and prominent."
                + (
                    f" External overlay tone for later non-image text: {general_external_copy_tone}."
                    if general_external_copy_tone
                    else ""
                )
            )
        if ecommerce_prompt:
            visual_prompt = f"{visual_prompt} {ecommerce_prompt}"
        role_prompt = self._mode_role_prompt(mode_role_recipe, mode_execution_policy)
        if role_prompt:
            visual_prompt = f"{visual_prompt} Role-specific output direction: {role_prompt}"
        brain_addons = [str(item).strip() for item in brain_guidance.get("visual_direction_addons", []) if str(item).strip()]
        if ecommerce_recipe:
            brain_addons = [
                item
                for item in brain_addons
                if not item.lower().startswith("planned image role")
            ]
            slot_addon = self._doc60_ecommerce_slot_addon(mode_role_recipe)
            if slot_addon:
                brain_addons.append(slot_addon)
        if not allow_product_language:
            brain_addons = [strip_negated_product_phrases(item) for item in brain_addons]
        if brain_addons:
            visual_prompt = f"{visual_prompt} V3 refined direction: {' '.join(brain_addons)}"
        negative_parts = list(
            dict.fromkeys(
                [
                    *creative_plan.negative_direction,
                    *explicit_negative_parts,
                    *brain_guidance.get("negative_prompt_addons", []),
                    *(general_negated_retail_constraints(raw_user_request) if not allow_product_language else []),
                    *SINGLE_FRAME_NEGATIVE_PARTS,
                    "fake final Chinese text",
                    "unreadable text",
                    "cluttered background",
                    *self._ecommerce_negative_parts(ecommerce_recipe),
                ]
            )
        )
        hard_constraints = [
            (
                "Use the V3-owned generation strategy selected by the product runtime."
                if allow_product_language
                else "Use the V3-owned generation strategy selected by the runtime."
            ),
            *(
                [
                    (
                        f"Generated subject, product category, scene, and mood must match the user request: {user_request}."
                        if allow_product_language
                        else f"Generated subject, scene, style, and mood must match the user request: {user_request}."
                    )
                ]
                if user_request
                else []
            ),
            (
                "Do not render final offer text inside the image model output."
                if allow_product_language
                else "Do not render any final text, captions, or UI copy inside the image model output."
            ),
            SINGLE_FRAME_HARD_CONSTRAINT,
            *self._complex_prompt_fidelity_constraints(user_request, explicit_negative_parts),
            *(
                brain_guidance.get("hard_constraints", [])
                if allow_product_language
                else [strip_negated_product_phrases(item) for item in brain_guidance.get("hard_constraints", [])]
            ),
            *self._mode_role_hard_constraints(mode_role_recipe, mode_execution_policy),
            *self._ecommerce_hard_constraints(ecommerce_recipe),
        ]
        compiled_layout_notes = [
            note
            for note in [
                *layout_notes,
                *self._mode_role_layout_notes(mode_role_recipe),
                *brain_guidance.get("layout_notes", []),
            ]
            if note
        ]
        if not allow_product_language:
            style_notes = list(dict.fromkeys(general_style_notes))
            visual_prompt = self._generalize_non_product_text(visual_prompt)
            compiled_layout_notes = [
                self._generalize_non_product_text(note) for note in compiled_layout_notes
            ]
        result = PromptCompilationResult(
            prompt_compilation_id=stable_id("prompt_compilation", layout_plan.asset_id, creative_plan.creative_plan_id),
            asset_id=layout_plan.asset_id,
            visual_prompt=visual_prompt,
            negative_prompt=", ".join(part for part in negative_parts if part),
            hard_constraints=hard_constraints,
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=style_notes,
            layout_notes=compiled_layout_notes,
            provider_notes={
                "text_overlay_required": True,
                "reserve_clean_text_areas": True,
                "avoid_fake_chinese_text": True,
                "required_note": NO_FAKE_TEXT_PROVIDER_NOTE,
                "brand_consistency": f"Preserve brand tone: {', '.join(style_notes)}. Use palette: {color_text}.",
                "negative_style_constraints": rejected_text,
                "copywriting_tone": (
                    brand_profile.copywriting_tone or brief.copy_strategy
                    if allow_product_language
                    else general_external_copy_tone or "no in-image text; optional external overlay only"
                ),
                "layout_preference": brand_profile.layout_preference,
                "asset_metadata": asset_metadata,
                "ecommerce_slot": asset_metadata.get("ecommerce_slot"),
                "ecommerce_recipe": ecommerce_recipe,
                "ecommerce_visual_scene": asset_metadata.get("ecommerce_visual_scene"),
                "mode_execution_policy": mode_execution_policy,
                "mode_role_recipe": mode_role_recipe,
                "mode_role_key": mode_role_recipe.get("role_key"),
                "mode_role_label": mode_role_recipe.get("label"),
                "model_text_forbidden": bool(ecommerce_recipe),
                "llm_brain_summary": self._brain_user_summary(llm_brain),
                "llm_brain_consistency_strategy": brain_guidance.get("consistency_strategy"),
                "llm_brain_prompt_review": self._brain_prompt_review(llm_brain),
            },
            metadata=self.metadata(
                rules_version=RULE_VERSION,
                brand_id=brand_profile.brand_id,
                brand_consistency_metadata=True,
                asset_metadata=asset_metadata,
                ecommerce_slot=asset_metadata.get("ecommerce_slot"),
                ecommerce_recipe=ecommerce_recipe,
                mode_execution_policy=mode_execution_policy,
                mode_role_recipe=mode_role_recipe,
                mode_role_key=mode_role_recipe.get("role_key"),
                mode_role_label=mode_role_recipe.get("label"),
                llm_brain_enabled=bool(llm_brain and llm_brain.get("enabled")),
                llm_brain_used=bool(llm_brain and llm_brain.get("llm_used")),
                product_language_allowed=allow_product_language,
                explicit_negative_prompt_parts=explicit_negative_parts,
                complex_prompt_fidelity=bool(self._complex_prompt_fidelity_constraints(user_request, explicit_negative_parts)),
            ),
        )
        return AgentResult(output=result, reasoning_summary="Compiled provider-neutral V3 prompt contract.")

    def _user_request_brief(self, brief: CommercialBrief) -> str:
        raw = str(brief.metadata.get("normalized_input") or "").strip()
        if not raw:
            return ""
        return " ".join(raw.split())[:1800]

    def _complex_prompt_fidelity_constraints(self, user_request: str, explicit_negative_parts: list[str]) -> list[str]:
        text = str(user_request or "")
        markers = [
            "\u673a\u4f4d",
            "\u666f\u6df1",
            "\u8272\u8c03",
            "\u955c\u5934",
            "\u6784\u56fe",
            "\u59ff\u6001",
            "\u8863\u88d9",
            "\u80cc\u666f",
            "\u706f\u5149",
            "\u80f6\u7247",
            "35mm",
            "3:4",
        ]
        is_complex = len(text) >= 260 or sum(1 for marker in markers if marker in text) >= 3 or len(explicit_negative_parts) >= 6
        if not is_complex:
            return []
        return [
            "Preserve the user's detailed scene literally: required subject or object, action or interaction, environment, camera angle, lens style, color mood, air or water atmosphere, and aspect ratio must remain visible.",
            "Do not simplify a detailed visual request into a generic stock image, unrelated studio setup, fashion poster, or arbitrary close-up.",
            "Treat the explicit negative prompt section only as things to avoid, never as desired image content.",
        ]

    def _mode_role_prompt(self, recipe: dict, policy: dict) -> str:
        if not recipe:
            return ""
        parts = [
            f"This output role is {recipe.get('label') or recipe.get('role_key')}",
            str(recipe.get("purpose") or ""),
            str(recipe.get("prompt_pressure") or ""),
            f"Shot family: {recipe.get('shot_family')}" if recipe.get("shot_family") else "",
            f"Camera distance: {recipe.get('camera_distance')}" if recipe.get("camera_distance") else "",
            f"Angle: {recipe.get('angle_rule')}" if recipe.get("angle_rule") else "",
            f"Crop/layout: {recipe.get('crop_rule')}" if recipe.get("crop_rule") else "",
            f"Scene rule: {recipe.get('scene_rule')}" if recipe.get("scene_rule") else "",
            f"Mode distance budget: {policy.get('visual_distance_budget')}" if policy.get("visual_distance_budget") else "",
        ]
        return ". ".join(part.strip().rstrip(".") for part in parts if str(part or "").strip()) + "."

    def _doc60_ecommerce_slot_addon(self, recipe: dict) -> str:
        if not recipe:
            return ""
        role_key = str(recipe.get("role_key") or "").strip()
        if not role_key:
            return ""
        index = str(recipe.get("index") or "").strip()
        pressure = str(recipe.get("prompt_pressure") or recipe.get("purpose") or "").strip()
        first_sentence = pressure.split(".")[0].strip() if pressure else str(recipe.get("label") or role_key)
        label = f"{index} " if index else ""
        return f"Planned ecommerce slot {label}({role_key}): {first_sentence}."

    def _mode_role_hard_constraints(self, recipe: dict, policy: dict) -> list[str]:
        if not recipe:
            return []
        constraints = [
            "Follow the role-specific output direction for this one image; do not repeat another planned role.",
            f"Role difference requirement: {policy.get('role_difference_requirement')}" if policy.get("role_difference_requirement") else "",
            *[str(item).strip() for item in recipe.get("must_keep_rules", []) if str(item).strip()],
            *[f"Avoid: {str(item).strip()}" for item in recipe.get("must_not_rules", []) if str(item).strip()],
        ]
        return [item for item in constraints if item]

    def _mode_role_layout_notes(self, recipe: dict) -> list[str]:
        if not recipe:
            return []
        notes = [
            f"mode role {recipe.get('role_key')}" if recipe.get("role_key") else "",
            f"shot family {recipe.get('shot_family')}" if recipe.get("shot_family") else "",
            f"camera distance {recipe.get('camera_distance')}" if recipe.get("camera_distance") else "",
            f"crop rule {recipe.get('crop_rule')}" if recipe.get("crop_rule") else "",
            f"scene rule {recipe.get('scene_rule')}" if recipe.get("scene_rule") else "",
        ]
        return [item for item in notes if item]

    def _general_output_goal(self, business_goal: str | None) -> str:
        goal = str(business_goal or "").strip()
        if not goal or goal == "improve brand recognition and commercial presentation":
            return "create a polished, directly usable image with a clear subject and atmosphere"
        return goal

    def _general_external_copy_tone(self, brand_profile: BrandProfile) -> str:
        if brand_profile.is_temporary:
            return ""
        return str(brand_profile.copywriting_tone or "").strip()

    def _generalize_non_product_text(self, text: str) -> str:
        value = str(text or "")
        replacements = {
            "commercially polished": "professionally polished",
            "commercial finish": "professional finish",
            "commercial composition": "professional composition",
            "commercial presentation": "professional presentation",
            "commercial image": "creative image",
            "commercial visual": "creative visual",
            "commercial": "polished",
            "later copy": "optional external overlay",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
        return value

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
            "Preserve the uploaded product identity, material cues, proportions, label placement, logo placement, and packaging shape.",
            "If the reference product has visible label or logo details, keep the existing label/logo readable, high-contrast, and unobscured when it remains in frame.",
            "Do not translate, rewrite, invent, crop, blur, darken, cover, or replace existing product label/logo details.",
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

    def _brain_prompt_guidance(self, llm_brain: dict | None) -> dict:
        if not isinstance(llm_brain, dict):
            return {}
        guidance = llm_brain.get("prompt_guidance")
        return guidance if isinstance(guidance, dict) else {}

    def _brain_user_summary(self, llm_brain: dict | None) -> dict:
        if not isinstance(llm_brain, dict):
            return {}
        summary = llm_brain.get("user_visible_summary")
        return summary if isinstance(summary, dict) else {}

    def _brain_prompt_review(self, llm_brain: dict | None) -> dict:
        if not isinstance(llm_brain, dict):
            return {}
        review = llm_brain.get("prompt_review")
        return review if isinstance(review, dict) else {}
