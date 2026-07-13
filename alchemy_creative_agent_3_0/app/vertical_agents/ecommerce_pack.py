"""LLM-native specialization boundary for the E-Commerce template.

This pack owns factual product-commerce context and the presentation of an
already-decided Brain output.  It must not manufacture a marketplace slot,
camera, crop, scene, selling point, or promotional copy for a new job.
"""

from __future__ import annotations

from typing import Any

from .base import VerticalAgentPack
from ..creative_core.rules import stable_id
from ..schemas import AssetSpec, IndustryCategory


class EcommerceCreativeDirectionRequired(ValueError):
    """Raised when a new E-Commerce job lacks a real Brain output set."""


class EcommerceAgentFamily(VerticalAgentPack):
    name = "ecommerce_agent_family"
    supported_industries = ["ecommerce_product"]
    supported_scenarios = ["ecommerce"]

    def match(self, creative_job, commercial_brief=None) -> float:
        """Never infer E-Commerce from general product language.

        General Template may create a product image.  Only an explicit
        E-Commerce template/scenario is allowed to receive this specialization.
        """

        metadata = dict(getattr(creative_job, "metadata", {}) or {})
        template_id = str(
            metadata.get("template_id")
            or getattr(creative_job, "optional_template_id", "")
            or ""
        ).strip().lower()
        scenario_id = str(metadata.get("scenario_id") or "").strip().lower()
        if template_id == "ecommerce_template" or scenario_id == "ecommerce":
            return 1.0
        return 0.0

    def refine_commercial_brief(self, context):
        brief = context.commercial_brief
        if brief is None or not self._is_ecommerce_scenario(context):
            return brief
        return brief.model_copy(
            update={
                "industry": IndustryCategory.ECOMMERCE_PRODUCT,
                "scenario": "new_product_promotion",
                "copy_strategy": "provider-native literal copy only when explicitly approved by the user",
                "platform_notes": {
                    **dict(brief.platform_notes),
                    "vertical_pack": self.name,
                    "creative_owner": "remote_llm_and_image_provider",
                    "ecommerce_context_id": self._context_id(context),
                },
                "metadata": self._metadata(
                    brief.metadata,
                    "commercial_brief",
                    creative_owner="remote_llm_and_image_provider",
                    ecommerce_context_id=self._context_id(context),
                ),
            }
        )

    def refine_creative_plan(self, context):
        plan = context.creative_plan
        if plan is None or not self._is_ecommerce_scenario(context):
            return plan
        return plan.model_copy(
            update={
                "metadata": self._metadata(
                    plan.metadata,
                    "creative_plan",
                    creative_owner="remote_llm_and_image_provider",
                    ecommerce_context_id=self._context_id(context),
                )
            }
        )

    def refine_series_plan(self, context):
        series = context.series_plan
        if series is None or not self._is_ecommerce_scenario(context):
            return series

        directions = self._brain_output_directions(context)
        requested_count = self._requested_count(context, fallback=len(series.assets))
        if len(directions) != requested_count:
            raise EcommerceCreativeDirectionRequired(
                "ecommerce_remote_brain_output_count_mismatch"
            )

        context_payload = self._context_payload(context)
        product_truth = dict(context_payload.get("product_truth") or {})
        approved_copy = context_payload.get("approved_literal_copy")
        slot_ids = self._output_slot_ids(context, len(directions))
        assets: list[AssetSpec] = []
        for index, (slot_id, direction) in enumerate(zip(slot_ids, directions), 1):
            base_asset = series.assets[min(index - 1, len(series.assets) - 1)]
            role = self._llm_role_contract(
                series_job_id=series.job_id,
                slot_id=slot_id,
                index=index,
                direction=direction,
                product_truth=product_truth,
            )
            metadata = self._without_legacy_recipe_metadata(base_asset.metadata)
            metadata = self._metadata(metadata, "asset_spec")
            metadata.update(
                {
                    "ecommerce_slot": slot_id,
                    "ecommerce_slot_index": index,
                    "ecommerce_llm_directed": True,
                    "ecommerce_creative_direction": direction,
                    "ecommerce_context_id": self._context_id(context),
                    "ecommerce_approved_literal_copy": approved_copy,
                    "mode_role_recipe": role,
                    "mode_role_key": slot_id,
                    "mode_role_label": f"Output {index}",
                    "generated_from_ecommerce_recipe": False,
                    "generated_from_remote_brain": True,
                }
            )
            assets.append(
                base_asset.model_copy(
                    update={
                        "asset_id": stable_id("asset", series.job_id, "ecommerce_llm", slot_id),
                        "purpose": direction,
                        "priority": index,
                        "requires_text_overlay": False,
                        "requires_brand_consistency": True,
                        "metadata": metadata,
                    }
                )
            )

        execution_plan = self._execution_plan(series.job_id, context.user_input, assets)
        return series.model_copy(
            update={
                "assets": assets,
                "series_strategy": "remote-LLM-directed ecommerce image set",
                "metadata": {
                    **self._metadata(
                        series.metadata,
                        "series_plan",
                        asset_count=len(assets),
                        ecommerce_llm_directed=True,
                        ecommerce_context_id=self._context_id(context),
                        ecommerce_recipe_series=False,
                    ),
                    "role_specific_generation_plan": execution_plan,
                    "mode_execution_policy": dict(execution_plan["policy"]),
                },
            }
        )

    def refine_layout_plan(self, context, layout_plan):
        if layout_plan is None or not self._is_ecommerce_scenario(context):
            return layout_plan
        asset_metadata = layout_plan.metadata.get("asset_metadata", {})
        direction = asset_metadata.get("ecommerce_creative_direction") if isinstance(asset_metadata, dict) else None
        return layout_plan.model_copy(
            update={
                "metadata": self._metadata(
                    layout_plan.metadata,
                    "layout_plan",
                    creative_owner="remote_llm_and_image_provider",
                    ecommerce_creative_direction=direction,
                )
            }
        )

    def refine_prompt_compilation(self, context, prompt_compilation):
        if prompt_compilation is None or not self._is_ecommerce_scenario(context):
            return prompt_compilation
        return prompt_compilation.model_copy(
            update={
                "provider_notes": {
                    **dict(prompt_compilation.provider_notes),
                    "vertical_pack": self.name,
                    "provider_native_complete_image": True,
                    "creative_owner": "remote_llm_and_image_provider",
                },
                "metadata": self._metadata(
                    prompt_compilation.metadata,
                    "prompt_compilation",
                    ecommerce_llm_directed=True,
                    ecommerce_context_id=self._context_id(context),
                ),
            }
        )

    def refine_evaluation_policy(self, context):
        return {
            **super().refine_evaluation_policy(context),
            "mode": "ecommerce_llm_directed",
            "weighted_priorities": [
                "product_truth",
                "approved_claims",
                "remote_brain_output_intent",
            ],
        }

    def _brain_output_directions(self, context) -> list[str]:
        brain = context.metadata.get("llm_brain")
        if not isinstance(brain, dict) or not bool(brain.get("llm_used")):
            raise EcommerceCreativeDirectionRequired("ecommerce_remote_brain_required")
        image_plan = brain.get("image_set_plan")
        if not isinstance(image_plan, dict):
            raise EcommerceCreativeDirectionRequired("ecommerce_remote_brain_image_set_missing")
        directions = [str(item).strip() for item in image_plan.get("shot_plan", []) if str(item).strip()]
        if not directions:
            raise EcommerceCreativeDirectionRequired("ecommerce_remote_brain_image_set_missing")
        return directions

    def _requested_count(self, context, *, fallback: int) -> int:
        parameters = context.metadata.get("scenario_parameters")
        raw = context.metadata.get("requested_image_count")
        if raw in (None, "") and isinstance(parameters, dict):
            raw = parameters.get("requested_image_count")
        if raw in (None, ""):
            brain = context.metadata.get("llm_brain")
            image_plan = brain.get("image_set_plan") if isinstance(brain, dict) else None
            if isinstance(image_plan, dict):
                raw = image_plan.get("image_count")
        try:
            return max(1, min(4, int(raw or fallback or 1)))
        except (TypeError, ValueError):
            return max(1, min(4, fallback or 1))

    def _context_payload(self, context) -> dict[str, Any]:
        payload = context.metadata.get("ecommerce_creative_context")
        return dict(payload) if isinstance(payload, dict) else {}

    def _context_id(self, context) -> str | None:
        return str(self._context_payload(context).get("context_id") or "").strip() or None

    def _output_slot_ids(self, context, count: int) -> list[str]:
        """Keep a requested Doc105 continuation attached to its opaque root ID."""

        lineage = context.metadata.get("ecommerce_slot_lineage")
        if isinstance(lineage, dict):
            parent_slot = str(lineage.get("parent_slot_id") or "").strip()
            if parent_slot:
                if count != 1:
                    raise EcommerceCreativeDirectionRequired("ecommerce_continuation_requires_one_remote_output")
                return [parent_slot]
        return [f"ecommerce_output_{index}" for index in range(1, count + 1)]

    def _is_ecommerce_scenario(self, context) -> bool:
        job_metadata = context.creative_job.metadata if context.creative_job else {}
        return str(context.metadata.get("scenario_id") or job_metadata.get("scenario_id") or "").strip().lower() == "ecommerce"

    def _llm_role_contract(
        self,
        *,
        series_job_id: str,
        slot_id: str,
        index: int,
        direction: str,
        product_truth: dict[str, Any],
    ) -> dict[str, Any]:
        immutable_facts = [str(item).strip() for item in product_truth.get("immutable_attributes", []) if str(item).strip()]
        return {
            "role_id": stable_id("ecommerce_remote_brain_output", series_job_id, slot_id),
            "index": index,
            "role_key": slot_id,
            "label": f"Output {index}",
            "purpose": direction,
            "shot_family": "remote-LLM-selected complete image",
            "camera_distance": "",
            "angle_rule": "",
            "crop_rule": "",
            "scene_rule": "",
            "variation_axes": [],
            "must_keep_rules": immutable_facts,
            "must_not_rules": [],
            "prompt_pressure": direction,
            "negative_pressure": [],
            "review_checks": ["product truth", "approved claims", "remote Brain output intent"],
            "user_visible_summary": [direction],
            "metadata": {
                "owner": "remote_v3_llm_brain",
                "ecommerce_llm_directed": True,
                "fixed_camera_or_crop": False,
            },
        }

    def _execution_plan(self, series_job_id: str, user_input: str, assets: list[AssetSpec]) -> dict[str, Any]:
        roles = [dict(asset.metadata["mode_role_recipe"]) for asset in assets]
        policy = {
            "policy_id": stable_id("ecommerce_remote_brain_execution", series_job_id, len(roles)),
            "mode": "delivery_suite",
            "mode_meaning": "remote-LLM-directed ecommerce output set",
            "visual_distance_budget": "remote_llm_decided",
            "anchor_strength": "product_truth_and_user_references",
            "scene_change_allowed": True,
            "role_strategy": "remote_llm_output_intents",
            "role_difference_requirement": "the remote Brain decides output differences for this request",
            "review_priority": "product truth, approved claims, and output intent",
            "user_visible_label": "Product image set",
            "user_visible_summary": ["Prepared the E-Commerce outputs from the Central Brain's product-specific direction."],
            "metadata": {"owner": "remote_v3_llm_brain", "ecommerce_llm_directed": True},
        }
        return {
            "plan_id": stable_id("ecommerce_remote_brain_output_plan", series_job_id, user_input, *[role["role_id"] for role in roles]),
            "project_id": None,
            "job_id": series_job_id,
            "mode": "delivery_suite",
            "subject_type": "product",
            "requested_image_count": len(roles),
            "policy": policy,
            "role_recipes": roles,
            "prompt_additions": [role["prompt_pressure"] for role in roles],
            "negative_additions": [],
            "user_visible_summary": list(policy["user_visible_summary"]),
            "metadata": {"owner": "remote_v3_llm_brain", "ecommerce_llm_directed": True},
        }

    def _without_legacy_recipe_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        result = dict(metadata or {})
        for key in (
            "ecommerce_recipe",
            "ecommerce_business_goal",
            "ecommerce_selling_point",
            "ecommerce_buyer_intent",
            "ecommerce_visual_scene",
            "marketplace_profile",
            "product_truth",
            "mode_execution_policy",
            "mode_role_recipe",
            "mode_role_key",
            "mode_role_label",
        ):
            result.pop(key, None)
        return result
