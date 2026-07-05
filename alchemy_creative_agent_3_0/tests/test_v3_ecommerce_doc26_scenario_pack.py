import json

import pytest

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioPackRegistry, ScenarioPackStatus
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import EcommerceScenarioPackPlanner


def test_ecommerce_scenario_pack_is_active_with_one_click_default() -> None:
    registry = ScenarioPackRegistry()

    resolution = registry.resolve({"scenario_id": "ecommerce"})

    assert resolution.status == ScenarioPackStatus.ACTIVE
    assert resolution.can_create_jobs is True
    assert resolution.selected_mode_id == "one_click_product_set"
    assert "one_click_product_set" in resolution.manifest.supported_mode_ids
    assert "product_truth_lock" in resolution.manifest.enabled_capabilities
    assert resolution.manifest.metadata["v1_v2_runtime_import"] is False


def test_ecommerce_planner_builds_truth_brief_recipes_and_export_package() -> None:
    planner = EcommerceScenarioPackPlanner()

    output = planner.plan(
        user_input="Create a premium Amazon image set for this desk lamp",
        product_profile={
            "product_category": "desk lamp",
            "materials": ["aluminum body", "frosted diffuser"],
            "color": "matte black",
            "dimensions": "18 inch tall",
            "selling_points": ["Adjustable angle", "Soft eye-comfort light", "Stable metal base"],
            "keywords": ["desk lamp for home office", "adjustable led lamp"],
            "claims": ["100% eye protection"],
        },
        uploaded_asset_ids=["product_lamp_front"],
        scenario_parameters={"platform": "amazon_us", "market": "US"},
        platform_profile=None,
        job_key="job_lamp",
    )

    assert output.product_truth.product_category == "desk_lamp"
    assert "product shape and proportions" in output.product_truth.immutable_attributes
    assert any("Claim needs evidence" in warning for warning in output.warnings)
    assert output.marketplace_profile.platform == "amazon"
    assert output.marketplace_profile.metadata["live_policy_lookup"] is False
    assert len(output.recipes) >= 7
    assert output.recipes[0].slot == "main_image"
    assert output.recipes[0].overlay_text is None
    assert output.recipes[1].selling_point == "Adjustable angle"
    assert output.critic.status == "attention"
    assert output.export_package.files[0]["filename"].endswith("_amazon.png")


def test_ecommerce_planner_unifies_requested_count_and_lifestyle_slots() -> None:
    planner = EcommerceScenarioPackPlanner()

    output = planner.plan(
        user_input="Create two realistic lifestyle marketplace images for this summer drink bottle",
        product_profile={
            "product_category": "drink",
            "materials": ["clear bottle", "paper label"],
            "selling_points": ["Fresh summer refreshment", "Portable bottle"],
        },
        uploaded_asset_ids=["product_bottle_front"],
        scenario_parameters={
            "platform": "amazon_us",
            "requested_image_count": 2,
            "suite_slot_request": ["main_image", "scenario_image", "ad_cover"],
        },
        platform_profile=None,
        job_key="job_lifestyle_count",
    )

    assert len(output.recipes) == 2
    assert [recipe.slot for recipe in output.recipes] == ["main_image", "scenario_image"]
    assert output.marketplace_profile.metadata["requested_image_count"] == 2
    assert output.metadata["selected_image_slots"] == ["main_image", "scenario_image"]
    scenario_recipe = output.recipes[1]
    assert scenario_recipe.metadata["lifestyle_realism_required"] is True
    assert scenario_recipe.metadata["lifestyle_scene_category"] == "drink_summer"
    assert "Real outdoor or cafe summer refreshment moment" in scenario_recipe.visual_scene


def test_ecommerce_planner_respects_explicit_slots_without_extra_fill() -> None:
    planner = EcommerceScenarioPackPlanner()

    output = planner.plan(
        user_input="Create the requested ecommerce slots only",
        product_profile={"product_category": "desk lamp", "selling_points": ["Adjustable angle"]},
        uploaded_asset_ids=["product_lamp_front"],
        scenario_parameters={
            "platform": "amazon_us",
            "suite_slot_request": ["main_image", "scenario_image"],
        },
        platform_profile=None,
        job_key="job_explicit_slots_only",
    )

    assert [recipe.slot for recipe in output.recipes] == ["main_image", "scenario_image"]
    assert output.marketplace_profile.metadata["slot_count_unified_with_requested_count"] is False


def test_product_api_exposes_ecommerce_product_language_summary() -> None:
    service = V3ProductApiService()

    status = service.create_job(
        {
            "user_input": "Upload product image and make a premium marketplace listing image set",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "mode_id": "one_click_product_set",
                "platform_profile": "amazon_us",
                "parameters": {
                    "keywords": ["desk lamp for office", "black metal lamp"],
                    "competitor_references": ["clean white-background hero with detail callouts"],
                },
            },
            "uploaded_asset_ids": ["product_reference_lamp"],
            "product_profile": {
                "product_category": "desk lamp",
                "materials": ["metal", "frosted diffuser"],
                "selling_points": ["Adjustable arm", "Soft desk lighting", "Minimal footprint"],
            },
        }
    )

    assert status.status == "planned"
    assert status.scenario is not None
    assert status.scenario.scenario_id == "ecommerce"
    assert status.scenario.can_create_jobs is True
    assert status.general_creative is None
    assert status.ecommerce is not None
    assert status.ecommerce.platform == "amazon"
    assert status.ecommerce.product_truth["product_category"] == "desk_lamp"
    assert status.ecommerce.selling_points[:3] == ["Adjustable arm", "Soft desk lighting", "Minimal footprint"]
    assert status.ecommerce.image_recipes[0]["slot"] == "main_image"
    assert status.ecommerce.closure_checks
    assert status.ecommerce.export_package["files"]
    assert status.ecommerce.metadata["imports_v1_v2_runtime"] is False
    summary_text = json.dumps(status.ecommerce.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "seed" not in summary_text
    assert "controlnet" not in summary_text
    assert "comfyui" not in summary_text


def test_ecommerce_generate_and_select_flow_remains_on_v3_runtime() -> None:
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create a clean ecommerce product set for wireless earbuds",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "shopify"},
            "uploaded_asset_ids": ["product_earbuds"],
            "product_profile": {"product_category": "headphones", "selling_points": ["Compact case", "Comfortable fit"]},
        }
    )

    generated = service.generate_job(created.job_id, {"quality_mode": "standard"})
    selected = service.select_result(created.job_id, {"apply_memory_update": False})

    assert generated.status == "generated"
    assert generated.ecommerce is not None
    assert generated.ecommerce.platform == "shopify"
    assert generated.asset_series
    assert selected.status == "selected"
    assert selected.job_status.ecommerce is not None
    assert selected.job_status.metadata["v3_independent_product_api"] is True


def test_ecommerce_scenario_recipes_drive_generated_asset_series() -> None:
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Premium natural-light product image set with clean blank space",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "mode_id": "one_click_product_set",
                "platform_profile": "amazon_us",
            },
            "uploaded_asset_ids": ["product_bottle_front", "product_bottle_side"],
            "product_profile": {
                "product_category": "drink",
                "materials": ["clear bottle", "paper label"],
                "selling_points": ["Fresh natural taste", "Portable bottle", "Clean ingredient feel"],
            },
        }
    )

    slots = [item.metadata.get("ecommerce_slot") for item in created.asset_series]

    assert created.status == "planned"
    assert len(created.asset_series) >= 5
    assert slots[:3] == ["main_image", "feature_image_1", "feature_image_2"]
    assert created.asset_series[0].asset_type == "ecommerce_main_image"
    assert created.asset_series[0].metadata["ecommerce_recipe"]["business_goal"] == "click"
    assert created.metadata["selected_vertical_pack"] == "ecommerce_agent_family"

    generated = service.generate_job(created.job_id, {"quality_mode": "standard"})
    record = service.job_store.get(created.job_id)
    prompt = record.generation_result.prompt_compilations[0]

    assert generated.status == "generated"
    assert len(generated.asset_series) == len(created.asset_series)
    assert len(generated.candidates) == len(generated.asset_series)
    assert all(item.selected_candidate_id for item in generated.asset_series)
    assert generated.candidates[0].metadata["ecommerce_slot"] == "main_image"
    assert generated.candidates[0].metadata["ecommerce_recipe"]["selling_point"] == "Clear product identity"
    assert prompt.metadata["ecommerce_slot"] == "main_image"
    assert "selling point to express visually without text" in prompt.visual_prompt
    assert any("Do not add in-image text" in item for item in prompt.hard_constraints)


def test_ecommerce_requested_slots_survive_doc60_role_reconciliation() -> None:
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create an Aqua Tea marketplace set with main image, freshness feature image, and real summer cafe scene",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "mode_id": "one_click_product_set",
                "platform_profile": "amazon_us",
                "parameters": {
                    "requested_image_count": 3,
                    "suite_slot_request": ["main_image", "feature_image_1", "scenario_image"],
                },
            },
            "uploaded_asset_ids": ["product_aqua_tea_can"],
            "product_profile": {
                "product_category": "drink",
                "materials": ["turquoise aluminum can", "printed lime mint label"],
                "selling_points": ["Cold lime mint refreshment", "Portable summer drink"],
            },
            "metadata": {
                "requested_image_count": 3,
                "variation_mode": "delivery_suite",
            },
        }
    )

    generated = service.generate_job(
        created.job_id,
        {"quality_mode": "standard", "metadata": {"requested_image_count": 3}},
    )
    record = service.job_store.get(created.job_id)
    visual_cluster = generated.metadata.get("visual_cluster") or generated.metadata["shared_capabilities"]["visual_cluster"]
    role_plan = visual_cluster["role_specific_generation_plan"]
    candidate_role_keys = [candidate.metadata["mode_role_recipe"]["role_key"] for candidate in generated.candidates]
    asset_slots = [item.metadata["asset_metadata"]["ecommerce_slot"] for item in generated.asset_series]
    prompt_text = record.generation_result.prompt_compilations[1].visual_prompt
    hard_constraints = " ".join(record.generation_result.prompt_compilations[1].hard_constraints)

    assert [item.metadata.get("ecommerce_slot") for item in created.asset_series] == [
        "main_image",
        "feature_image_1",
        "scenario_image",
    ]
    assert role_plan["metadata"]["doc"] == "60"
    assert role_plan["metadata"]["ecommerce_recipe_aligned"] is True
    assert [recipe["role_key"] for recipe in role_plan["role_recipes"]] == [
        "main_image",
        "feature_image_1",
        "scenario_image",
    ]
    assert candidate_role_keys == ["main_image", "feature_image_1", "scenario_image"]
    assert asset_slots == candidate_role_keys
    assert "feature_image_1" in prompt_text
    assert "Planned ecommerce slot 2 (feature_image_1)" in prompt_text
    assert "Planned image role 3 (detail_image)" not in prompt_text
    assert "existing product label/logo" in hard_constraints
    assert generated.metadata["post_generation_review"]["metadata"]["mode_differentiation_review"]["status"] == "pass"


def test_general_creative_does_not_receive_ecommerce_summary() -> None:
    service = V3ProductApiService()

    status = service.create_job(
        {
            "user_input": "Create a social campaign poster for a summer drink",
            "scenario_selection": {"scenario_id": "general_creative", "preset_id": "campaign_poster"},
            "product_profile": {"brand_or_project_name": "Mint Lab"},
        }
    )

    assert status.status == "planned"
    assert status.scenario is not None
    assert status.scenario.scenario_id == "general_creative"
    assert status.general_creative is not None
    assert status.ecommerce is None


def test_ecommerce_public_api_still_rejects_low_level_controls() -> None:
    service = V3ProductApiService()

    with pytest.raises(ValueError):
        service.create_job(
            {
                "user_input": "Create an ecommerce set",
                "scenario_selection": {"scenario_id": "ecommerce"},
                "metadata": {"seed": 42},
            }
        )
