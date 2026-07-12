"""Ecommerce vertical pack specialization."""

from typing import Any

from .base import VerticalAgentPack
from ..creative_core.rules import stable_id
from ..creative_core.prompt_language import contains_explicit_ecommerce_context, looks_like_human_subject_context
from ..scenario_packs.ecommerce import EcommerceScenarioPackPlanner
from ..schemas import AssetSpec, AssetType, IndustryCategory, Platform


class EcommerceAgentFamily(VerticalAgentPack):
    name = "ecommerce_agent_family"
    supported_industries = ["ecommerce_product"]
    supported_scenarios = ["new_product_promotion", "generic_promotion", "brand_or_commercial_poster"]

    def match(self, creative_job, commercial_brief=None) -> float:
        text = self._job_text(creative_job)
        template_id = str(
            (creative_job.metadata.get("template_id") if creative_job else "")
            or (getattr(creative_job, "optional_template_id", "") or "")
        ).strip().lower()
        scenario_id = str(creative_job.metadata.get("scenario_id") or "") if creative_job else ""
        explicit_ecommerce = bool(
            template_id == "ecommerce_template"
            or scenario_id == "ecommerce"
            or contains_explicit_ecommerce_context(text)
            or (
                commercial_brief
                and any(
                    platform in {Platform.TAOBAO, Platform.JD, Platform.ECOMMERCE_GENERIC}
                    for platform in commercial_brief.target_platforms
                )
            )
        )
        if looks_like_human_subject_context(text) and not explicit_ecommerce:
            return 0.0
        score = 0.8 if self._industry_value(commercial_brief) in self.supported_industries else 0.0
        if creative_job and scenario_id == "ecommerce":
            score = max(score, 1.0)
        if self._contains_any(
            text,
            (
                "淘宝",
                "天猫",
                "京东",
                "拼多多",
                "电商",
                "主图",
                "详情页",
                "商品图",
                "sku",
                "ecommerce",
                "product image",
                "main image",
            ),
        ):
            score = max(score, 0.9)
        if explicit_ecommerce and commercial_brief and any(
            platform in {Platform.TAOBAO, Platform.JD, Platform.ECOMMERCE_GENERIC}
            for platform in commercial_brief.target_platforms
        ):
            score = max(score, 0.86)
        return score

    def refine_commercial_brief(self, context):
        brief = context.commercial_brief
        if brief is None:
            return brief
        scenario_locked = self._is_ecommerce_scenario(context)
        updates = {
            "target_audience": brief.target_audience or "platform shoppers comparing product value quickly",
            "commercial_hooks": self._append_unique(
                brief.commercial_hooks,
                ["product clarity", "feature proof", "platform conversion"],
            ),
            "selling_points": self._append_unique(
                brief.selling_points,
                ["clear product hero", "visible feature benefits"],
            ),
            "visual_tone": self._append_unique(brief.visual_tone, ["product_focused", "clean", "conversion_ready"]),
            "copy_strategy": "provider-native in-image text only when the user explicitly supplies or approves it",
            "platform_notes": {
                **brief.platform_notes,
                "vertical_pack": self.name,
                "ecommerce_rule": "prioritize product truth and buyer evidence while leaving composition and typography to LLM/provider reasoning",
                "scenario_id": context.metadata.get("scenario_id"),
                "platform_profile": context.metadata.get("platform_profile"),
            },
            "metadata": self._metadata(
                brief.metadata,
                "commercial_brief",
                priorities=["product_clarity", "feature_labels"],
                scenario_locked=scenario_locked,
            ),
        }
        if scenario_locked:
            updates.update(
                {
                    "industry": IndustryCategory.ECOMMERCE_PRODUCT,
                    "scenario": "new_product_promotion",
                    "business_goal": "convert platform shoppers with a ready-to-use product image set",
                    "target_platforms": self._target_platforms_for_context(context, brief.target_platforms),
                }
            )
        return brief.model_copy(
            update=updates
        )

    def refine_creative_plan(self, context):
        plan = context.creative_plan
        if plan is None:
            return plan
        return plan.model_copy(
            update={
                "visual_direction": f"{plan.visual_direction}; product-first ecommerce hero with crisp edge definition",
            "composition_strategy": f"{plan.composition_strategy}; preserve SKU identity while allowing the LLM and image provider to choose the composition for each buyer-evidence goal",
                "materials_and_props": self._append_unique(
                    plan.materials_and_props,
                    ["SKU consistency references"],
                ),
                "negative_direction": self._append_unique(
                    plan.negative_direction,
                    ["cropped product", "ambiguous product scale", "busy marketplace clutter"],
                ),
                "metadata": self._metadata(plan.metadata, "creative_plan", priorities=["hero_product", "conversion"]),
            }
        )

    def refine_series_plan(self, context):
        series = context.series_plan
        if series is None:
            return series
        pack_output = self._scenario_pack_output(context)
        if pack_output is not None and pack_output.recipes:
            platform = self._platform_for_marketplace(pack_output.marketplace_profile.platform)
            assets: list[AssetSpec] = []
            for index, recipe in enumerate(pack_output.recipes):
                base_asset = series.assets[min(index, len(series.assets) - 1)] if series.assets else None
                asset_type = self._asset_type_for_slot(recipe.slot)
                recipe_payload = recipe.model_dump(mode="json")
                mode_role_recipe = _mode_role_recipe_for_ecommerce_recipe(
                    series_job_id=series.job_id,
                    recipe_payload=recipe_payload,
                    index=index + 1,
                )
                mode_execution_policy = _ecommerce_mode_execution_policy(series.job_id, len(pack_output.recipes))
                marketplace_payload = pack_output.marketplace_profile.model_dump(mode="json")
                product_truth_payload = pack_output.product_truth.model_dump(mode="json")
                assets.append(
                    AssetSpec(
                        asset_id=stable_id("asset", series.job_id, "ecommerce", recipe.slot, index),
                        asset_type=asset_type,
                        platform=platform,
                        aspect_ratio=self._aspect_ratio_for_slot(
                            recipe.slot,
                            dict(pack_output.marketplace_profile.canvas_rules),
                            base_asset.aspect_ratio if base_asset else "1:1",
                        ),
                        purpose=self._purpose_for_recipe(recipe),
                        priority=index + 1,
                        requires_text_overlay=False,
                        requires_brand_consistency=True,
                        metadata={
                            **self._metadata(
                                dict(base_asset.metadata) if base_asset else {},
                                "asset_spec",
                                asset_role=asset_type.value,
                                ecommerce_recipe=recipe_payload,
                                ecommerce_slot=recipe.slot,
                                ecommerce_slot_index=index + 1,
                                ecommerce_business_goal=recipe.business_goal,
                                ecommerce_selling_point=recipe.selling_point,
                                ecommerce_buyer_intent=recipe.buyer_intent,
                                ecommerce_visual_scene=recipe.visual_scene,
                                provider_native_text_requested=bool(recipe.provider_native_text),
                                mode_role_recipe=mode_role_recipe,
                                mode_role_key=mode_role_recipe["role_key"],
                                mode_role_label=mode_role_recipe["label"],
                                mode_execution_policy=mode_execution_policy,
                                marketplace_profile=marketplace_payload,
                                product_truth=product_truth_payload,
                                generated_from_ecommerce_recipe=True,
                            ),
                            "ecommerce_recipe": recipe_payload,
                            "ecommerce_slot": recipe.slot,
                            "ecommerce_slot_index": index + 1,
                            "ecommerce_business_goal": recipe.business_goal,
                            "ecommerce_selling_point": recipe.selling_point,
                            "ecommerce_buyer_intent": recipe.buyer_intent,
                            "ecommerce_visual_scene": recipe.visual_scene,
                            "provider_native_text_requested": bool(recipe.provider_native_text),
                            "mode_role_recipe": mode_role_recipe,
                            "mode_role_key": mode_role_recipe["role_key"],
                            "mode_role_label": mode_role_recipe["label"],
                            "mode_execution_policy": mode_execution_policy,
                            "marketplace_profile": marketplace_payload,
                            "product_truth": product_truth_payload,
                            "generated_from_ecommerce_recipe": True,
                        },
                    )
                )
            return series.model_copy(
                update={
                    "assets": assets,
                    "series_strategy": (
                        "ecommerce product image set: distinct buyer-evidence goals with provider-native creative direction"
                    ),
                    "metadata": {
                        **self._metadata(
                            series.metadata,
                            "series_plan",
                            asset_count=len(assets),
                            ecommerce_recipe_series=True,
                            ecommerce_recipe_count=len(pack_output.recipes),
                            marketplace_profile=pack_output.marketplace_profile.model_dump(mode="json"),
                        ),
                        "mode_execution_policy": _ecommerce_mode_execution_policy(series.job_id, len(assets)),
                        "role_specific_generation_plan": _ecommerce_role_specific_generation_plan(
                            series_job_id=series.job_id,
                            user_input=context.user_input,
                            assets=assets,
                        ),
                    },
                }
            )
        assets = []
        for index, asset in enumerate(series.assets):
            asset_type = asset.asset_type
            purpose = asset.purpose
            if asset.platform in {Platform.TAOBAO, Platform.JD, Platform.ECOMMERCE_GENERIC}:
                asset_type = AssetType.ECOMMERCE_MAIN_IMAGE if index == 0 else AssetType.PRODUCT_DETAIL_BANNER
                purpose = "ecommerce conversion asset with product clarity and feature proof"
            assets.append(
                asset.model_copy(
                    update={
                        "asset_type": asset_type,
                        "purpose": purpose,
                        "requires_text_overlay": False,
                        "requires_brand_consistency": True,
                        "metadata": self._metadata(asset.metadata, "asset_spec", asset_role=asset_type.value),
                    }
                )
            )
        return series.model_copy(
            update={
                "assets": assets,
                "series_strategy": "ecommerce sequence: product truth and distinct buyer-evidence goals",
                "metadata": self._metadata(series.metadata, "series_plan", asset_count=len(assets)),
            }
        )

    def refine_layout_plan(self, context, layout_plan):
        if layout_plan is None:
            return layout_plan
        asset_metadata = layout_plan.metadata.get("asset_metadata", {})
        recipe = asset_metadata.get("ecommerce_recipe") if isinstance(asset_metadata, dict) else None
        return layout_plan.model_copy(
            update={
                "metadata": self._metadata(
                    layout_plan.metadata,
                    "layout_plan",
                    creative_owner="llm_and_image_provider",
                    ecommerce_evidence_goal=(recipe.get("business_goal") if isinstance(recipe, dict) else None),
                ),
            }
        )

    def refine_prompt_compilation(self, context, prompt_compilation):
        if prompt_compilation is None:
            return prompt_compilation
        return prompt_compilation.model_copy(
            update={
                "visual_prompt": (
                    f"{prompt_compilation.visual_prompt} Ecommerce specialization: make the product silhouette, "
                    "materials, and key feature areas immediately readable for a platform shopper."
                ),
                "hard_constraints": self._append_unique(
                    prompt_compilation.hard_constraints,
                    ["Product shape, color, and visible functional details must remain clear."],
                ),
                "style_notes": self._append_unique(prompt_compilation.style_notes, ["product_focused", "conversion_ready"]),
                "layout_notes": self._append_unique(
                    prompt_compilation.layout_notes,
                    ["preserve product truth without prescribing a fixed crop, coordinate, text lane, or overlay"],
                ),
                "provider_notes": {
                    **prompt_compilation.provider_notes,
                    "vertical_pack": self.name,
                    "product_visibility_required": True,
                    "provider_native_complete_image": True,
                },
                "metadata": self._metadata(prompt_compilation.metadata, "prompt_compilation", prompt_bias="product_clarity"),
            }
        )

    def refine_evaluation_policy(self, context):
        return {
            **super().refine_evaluation_policy(context),
            "mode": "ecommerce_product_clarity",
            "commercial_score_delta": 0.03,
            "layout_score_delta": 0.02,
            "weighted_priorities": ["product_visibility", "feature_label_space", "platform_conversion"],
        }

    def _is_ecommerce_scenario(self, context) -> bool:
        job_metadata = context.creative_job.metadata if context.creative_job else {}
        return str(context.metadata.get("scenario_id") or job_metadata.get("scenario_id") or "") == "ecommerce"

    def _scenario_pack_output(self, context):
        if not self._is_ecommerce_scenario(context):
            return None
        parameters = dict(context.metadata.get("scenario_parameters") or {})
        planner = EcommerceScenarioPackPlanner()
        return planner.plan(
            user_input=context.user_input,
            product_profile=dict(context.metadata.get("product_profile") or {}),
            uploaded_asset_ids=list(context.metadata.get("uploaded_asset_ids") or []),
            scenario_parameters=parameters,
            platform_profile=context.metadata.get("platform_profile"),
            job_key=context.creative_job.job_id if context.creative_job else context.user_input,
        )

    def _target_platforms_for_context(self, context, fallback: list[Platform]) -> list[Platform]:
        parameters = dict(context.metadata.get("scenario_parameters") or {})
        raw = str(context.metadata.get("platform_profile") or parameters.get("platform") or parameters.get("marketplace") or "")
        platform = self._platform_for_marketplace(raw)
        return [platform] if platform else fallback

    def _platform_for_marketplace(self, value: str | None) -> Platform:
        normalized = str(value or "").lower()
        if normalized in {"taobao", "tmall"}:
            return Platform.TAOBAO
        if normalized in {"jd", "jingdong"}:
            return Platform.JD
        if normalized in {"tiktok_shop", "tiktok"}:
            return Platform.DOUYIN
        return Platform.ECOMMERCE_GENERIC

    def _asset_type_for_slot(self, slot: str) -> AssetType:
        if slot in {"main_image", "hero_image"}:
            return AssetType.ECOMMERCE_MAIN_IMAGE
        if slot in {"ad_cover", "store_banner", "collection_cover"}:
            return AssetType.CAMPAIGN_BANNER
        return AssetType.PRODUCT_DETAIL_BANNER

    def _aspect_ratio_for_slot(self, slot: str, canvas_rules: dict[str, Any], fallback: str) -> str:
        primary = str(canvas_rules.get("primary_aspect_ratio") or fallback or "1:1")
        secondary = str(canvas_rules.get("secondary_aspect_ratio") or primary)
        if slot in {"main_image", "hero_image"}:
            return primary
        if slot in {"ad_cover", "store_banner", "collection_cover"}:
            return secondary
        return primary if primary in {"1:1", "4:5"} else secondary

    def _purpose_for_recipe(self, recipe) -> str:
        return f"{recipe.slot}: {recipe.business_goal} via {recipe.selling_point}"

def _ecommerce_mode_execution_policy(series_job_id: str, count: int) -> dict[str, Any]:
    return {
        "policy_id": stable_id("ecommerce_mode_execution_policy", series_job_id, count),
        "mode": "delivery_suite",
        "mode_meaning": "ecommerce product image set with distinct listing roles",
        "visual_distance_budget": "moderate",
        "anchor_strength": "product_truth_lock",
        "scene_change_allowed": True,
        "role_strategy": "ecommerce_buyer_evidence_goals",
        "role_difference_requirement": "each output must answer a different buyer question without forcing a fixed visual recipe",
        "review_priority": "product truth, buyer-evidence coverage, label/logo fidelity, commercial finish",
        "user_visible_label": "Product image set",
        "user_visible_summary": [
            "Main product, feature/detail, and scene images keep the same product while serving different purposes."
        ],
        "metadata": {"doc": "60", "doc67_boundary_cleanup": True, "ecommerce_recipe_aligned": True},
    }


def _ecommerce_role_specific_generation_plan(
    *,
    series_job_id: str,
    user_input: str,
    assets: list[AssetSpec],
) -> dict[str, Any]:
    recipes = [
        dict(asset.metadata.get("mode_role_recipe"))
        for asset in assets
        if isinstance(asset.metadata.get("mode_role_recipe"), dict)
    ]
    policy = _ecommerce_mode_execution_policy(series_job_id, len(recipes) or len(assets))
    return {
        "plan_id": stable_id(
            "ecommerce_role_specific_generation_plan",
            series_job_id,
            user_input,
            ",".join(str(recipe.get("role_key") or "") for recipe in recipes),
        ),
        "project_id": None,
        "job_id": series_job_id,
        "mode": "delivery_suite",
        "subject_type": "product",
        "requested_image_count": len(recipes) or len(assets),
        "policy": policy,
        "role_recipes": recipes,
        "prompt_additions": [
            f"Output {recipe.get('index')} should satisfy the buyer-evidence goal '{recipe.get('purpose')}' while the LLM and image provider choose the composition: {recipe.get('prompt_pressure')}"
            for recipe in recipes
        ],
        "negative_additions": _dedupe_strings(
            rule
            for recipe in recipes
            for rule in recipe.get("negative_pressure", [])
        ),
        "user_visible_summary": [
            "Prepared an ecommerce image set from distinct buyer-evidence goals.",
            f"{len(recipes) or len(assets)} ecommerce creative directions planned.",
        ],
        "metadata": {
            "doc": "60",
            "extends": "60",
            "scenario_id": "ecommerce",
            "template_id": "ecommerce",
            "mode_role_director": False,
            "doc67_boundary_cleanup": True,
            "owned_by": "ecommerce_vertical_pack",
            "ecommerce_recipe_aligned": True,
            "ecommerce_role_keys": [recipe.get("role_key") for recipe in recipes],
        },
    }


def _mode_role_recipe_for_ecommerce_recipe(
    *,
    series_job_id: str,
    recipe_payload: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    slot = str(recipe_payload.get("slot") or f"slot_{index}").strip()
    lane = _ecommerce_slot_lane(slot)
    selling_point = str(recipe_payload.get("selling_point") or "").strip()
    buyer_intent = str(recipe_payload.get("buyer_intent") or "").strip()
    scene = str(recipe_payload.get("visual_scene") or "").strip()
    purpose = str(recipe_payload.get("business_goal") or lane["purpose"]).strip()
    pressure = " ".join(
        item
        for item in [
            "Use the product facts and buyer-evidence goal, then let the LLM and image provider choose a non-template composition, camera, typography, and scene treatment.",
            f"Selling point to communicate: {selling_point}." if selling_point else "",
            f"Buyer intent: {buyer_intent}." if buyer_intent else "",
            f"Requested scene direction: {scene}." if scene else "",
        ]
        if item
    )
    recipe = {
        "role_id": stable_id("ecommerce_mode_role_recipe", series_job_id, slot, index),
        "index": index,
        "role_key": slot,
        "label": lane["label"],
        "purpose": purpose or lane["purpose"],
        "shot_family": "LLM-selected product image treatment",
        "camera_distance": "",
        "angle_rule": "",
        "crop_rule": "",
        "scene_rule": scene,
        "variation_axes": ["buyer evidence", "creative concept", "provider-selected composition"],
        "must_keep_rules": [
            "preserve product shape, color, material cues, label/logo placement, and packaging silhouette",
            "make the product and the intended buyer evidence understandable",
        ],
        "must_not_rules": [
            "do not invent a different product",
            "do not hide, rewrite, translate, blur, or cover visible label/logo details",
            "do not add unsupported claims, watermarks, or AI-generated marks",
        ],
        "prompt_pressure": pressure,
        "negative_pressure": [
            "wrong product identity",
            "missing or distorted label/logo",
            "busy clutter over product",
            "fake product claims",
            "watermark or AI-generated mark",
        ],
        "review_checks": [
            "product identity preserved",
            "buyer-evidence goal is visually distinct from the other outputs",
            "commercial finish is publish-ready",
        ],
        "user_visible_summary": [lane["summary"]],
        "metadata": {
            "doc": "60",
            "extends": "60",
            "doc67_boundary_cleanup": True,
            "owned_by": "ecommerce_vertical_pack",
            "ecommerce_recipe_aligned": True,
            "ecommerce_slot": slot,
            "creative_owner": "llm_and_image_provider",
            "clone_avoidance_rule": "make this buyer-evidence goal visibly distinct while preserving product truth",
        },
    }
    return recipe


def _ecommerce_slot_lane(slot: str) -> dict[str, Any]:
    normalized = slot.lower()
    if normalized in {"main_image", "hero_image"}:
        return {
            "label": "Main product image",
            "purpose": "make the product instantly clear and desirable",
            "summary": "Clear main product image",
        }
    if normalized in {"scenario_image", "lifestyle_image", "ad_cover", "store_banner", "collection_cover"}:
        return {
            "label": "Lifestyle scene image",
            "purpose": "show the product in a believable use or atmosphere scene",
            "summary": "Lifestyle context image",
        }
    if normalized in {"detail_image", "feature_image_1", "feature_image_2", "benefit_image", "benefit_hook", "size_spec_image"}:
        return {
            "label": "Feature/detail image",
            "purpose": "make a key feature or material detail easy to understand",
            "summary": "Feature/detail image",
        }
    return {
        "label": "Product support image",
        "purpose": "support the product listing with a distinct commercial angle",
        "summary": "Product support image",
    }


def _dedupe_strings(values) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))
