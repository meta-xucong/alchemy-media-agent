"""Ecommerce vertical pack specialization."""

from typing import Any

from .base import VerticalAgentPack
from ..creative_core.rules import stable_id
from ..scenario_packs.ecommerce import EcommerceScenarioPackPlanner
from ..schemas import AssetSpec, AssetType, IndustryCategory, Platform


class EcommerceAgentFamily(VerticalAgentPack):
    name = "ecommerce_agent_family"
    supported_industries = ["ecommerce_product"]
    supported_scenarios = ["new_product_promotion", "generic_promotion", "brand_or_commercial_poster"]

    def match(self, creative_job, commercial_brief=None) -> float:
        score = 0.8 if self._industry_value(commercial_brief) in self.supported_industries else 0.0
        if creative_job and str(creative_job.metadata.get("scenario_id") or "") == "ecommerce":
            score = max(score, 1.0)
        text = self._job_text(creative_job)
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
        if commercial_brief and any(
            platform
            in {
                Platform.TAOBAO,
                Platform.JD,
                Platform.ECOMMERCE_GENERIC,
            }
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
            "copy_strategy": "short feature-led product copy with clear benefit labels and purchase cue",
            "platform_notes": {
                **brief.platform_notes,
                "vertical_pack": self.name,
                "ecommerce_rule": "prioritize main image clarity, SKU consistency, and feature callout space",
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
                "composition_strategy": (
                    f"{plan.composition_strategy}; center the product, preserve empty feature-callout lanes, "
                    "and keep SKU identity consistent across assets"
                ),
                "materials_and_props": self._append_unique(
                    plan.materials_and_props,
                    ["feature callout panels", "clean platform background", "SKU consistency references"],
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
                        requires_text_overlay=bool(recipe.overlay_text),
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
                        "ecommerce one-click product image set: main image, benefit/detail proof, "
                        "scenario context, trust/comparison support, and optional traffic cover"
                    ),
                    "metadata": self._metadata(
                        series.metadata,
                        "series_plan",
                        asset_count=len(assets),
                        ecommerce_recipe_series=True,
                        ecommerce_recipe_count=len(pack_output.recipes),
                        marketplace_profile=pack_output.marketplace_profile.model_dump(mode="json"),
                    ),
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
                        "requires_text_overlay": True,
                        "requires_brand_consistency": True,
                        "metadata": self._metadata(asset.metadata, "asset_spec", asset_role=asset_type.value),
                    }
                )
            )
        return series.model_copy(
            update={
                "assets": assets,
                "series_strategy": "ecommerce sequence: main product hero followed by feature-led conversion support",
                "metadata": self._metadata(series.metadata, "series_plan", asset_count=len(assets)),
            }
        )

    def refine_layout_plan(self, context, layout_plan):
        if layout_plan is None:
            return layout_plan
        asset_metadata = layout_plan.metadata.get("asset_metadata", {})
        recipe = asset_metadata.get("ecommerce_recipe") if isinstance(asset_metadata, dict) else None
        slot = str(asset_metadata.get("ecommerce_slot") or (recipe.get("slot") if isinstance(recipe, dict) else "") or "")
        product_box = self._product_box_for_slot(slot)
        hierarchy = self._visual_hierarchy_for_slot(slot)
        product_area = layout_plan.product_area.model_copy(
            update={
                "position": self._product_position_for_slot(slot),
                "priority": 1,
                "relative_box": product_box,
                "notes": self._product_area_notes_for_slot(slot, recipe),
                "metadata": self._metadata(layout_plan.product_area.metadata, "layout_region", region="product_area"),
            }
        )
        reserved_regions = list(layout_plan.reserved_text_regions)
        if layout_plan.headline_area:
            reserved_regions = [layout_plan.headline_area, *[region for region in reserved_regions if region.name != "headline_area"]]
        return layout_plan.model_copy(
            update={
                "product_area": product_area,
                "visual_hierarchy": hierarchy,
                "reserved_text_regions": reserved_regions,
                "background_strategy": self._background_strategy_for_slot(slot, recipe),
                "metadata": self._metadata(
                    layout_plan.metadata,
                    "layout_plan",
                    layout_bias="product_hero",
                    ecommerce_slot=slot or None,
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
                    ["large centered product hero", "clean feature callout lanes", "no clutter over product"],
                ),
                "provider_notes": {
                    **prompt_compilation.provider_notes,
                    "vertical_pack": self.name,
                    "product_visibility_required": True,
                    "feature_callout_space_required": True,
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

    def _product_position_for_slot(self, slot: str) -> str:
        if slot == "detail_image":
            return "macro_detail_product_anchor"
        if slot == "scenario_image":
            return "scene_integrated_product_anchor"
        if slot in {"size_spec_image", "trust_comparison_image"}:
            return "center_product_with_comparison_space"
        return "center_product_hero"

    def _product_box_for_slot(self, slot: str) -> dict[str, float]:
        if slot == "detail_image":
            return {"x": 0.12, "y": 0.18, "w": 0.76, "h": 0.60}
        if slot == "scenario_image":
            return {"x": 0.18, "y": 0.22, "w": 0.56, "h": 0.48}
        if slot in {"size_spec_image", "trust_comparison_image"}:
            return {"x": 0.12, "y": 0.22, "w": 0.58, "h": 0.48}
        return {"x": 0.16, "y": 0.22, "w": 0.68, "h": 0.50}

    def _visual_hierarchy_for_slot(self, slot: str) -> list[str]:
        if slot == "detail_image":
            return ["product_detail", "proof_area", "external_label_space", "brand_mark"]
        if slot == "scenario_image":
            return ["use_scene", "product_identity", "benefit_context", "brand_mark"]
        if slot in {"size_spec_image", "trust_comparison_image"}:
            return ["product_identity", "comparison_space", "trust_cue", "brand_mark"]
        if slot in {"ad_cover", "store_banner", "collection_cover"}:
            return ["traffic_hook_visual", "product_family", "external_headline_space", "brand_mark"]
        return ["product_hero", "benefit_space", "external_label_space", "brand_mark"]

    def _product_area_notes_for_slot(self, slot: str, recipe: dict[str, Any] | None) -> str:
        scene = recipe.get("visual_scene") if isinstance(recipe, dict) else None
        selling_point = recipe.get("selling_point") if isinstance(recipe, dict) else None
        return "large unobstructed product hero; " + "; ".join(
            part for part in [str(scene or "").strip(), f"selling point: {selling_point}" if selling_point else ""] if part
        )

    def _background_strategy_for_slot(self, slot: str, recipe: dict[str, Any] | None) -> str:
        scene = recipe.get("visual_scene") if isinstance(recipe, dict) else None
        if slot == "scenario_image":
            return f"realistic clean usage scene; {scene}; keep product identity central"
        if slot == "detail_image":
            return f"premium macro/detail background; {scene}; leave clean proof-label space"
        if slot in {"size_spec_image", "trust_comparison_image"}:
            return f"clean comparison-ready ecommerce background; {scene}; leave blank external annotation lanes"
        if slot in {"ad_cover", "store_banner", "collection_cover"}:
            return f"traffic-ready branded ecommerce background; {scene}; keep blank headline area"
        return f"clean ecommerce background with low clutter and no rendered text; {scene or 'product-first hero'}"
