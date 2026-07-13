import json

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioPackRegistry, ScenarioPackStatus
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import EcommerceScenarioPackPlanner
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


def _request(*, count: int = 2, approved_copy: str | None = None) -> dict:
    parameters = {"requested_image_count": count, "platform": "amazon_us", "market": "US"}
    if approved_copy:
        parameters["approved_literal_copy"] = approved_copy
    return {
        "user_input": "为一盏哑光黑色可调角度台灯生成高端电商图片。",
        "scenario_selection": {
            "scenario_id": "ecommerce",
            "mode_id": "one_click_product_set",
            "platform_profile": "amazon_us",
            "parameters": parameters,
        },
        "uploaded_asset_ids": ["product_lamp_front"],
        "product_profile": {
            "product_category": "desk lamp",
            "materials": ["aluminum body", "frosted diffuser"],
            "color": "matte black",
            "dimensions": "18 inch tall",
            "selling_points": ["Adjustable angle", "Stable metal base"],
            "claims": ["100% eye protection"],
        },
    }


def test_ecommerce_manifest_is_active_but_names_remote_brain_not_local_recipe_components() -> None:
    resolution = ScenarioPackRegistry().resolve({"scenario_id": "ecommerce"})

    assert resolution.status == ScenarioPackStatus.ACTIVE
    assert resolution.can_create_jobs is True
    assert "remote_v3_creative_brain" in resolution.manifest.enabled_capabilities
    assert "selling_point_to_image_planner" not in resolution.manifest.enabled_capabilities
    assert resolution.manifest.metadata["v1_v2_runtime_import"] is False


def test_planner_prepares_facts_and_questions_but_never_a_visual_recipe() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="为 Amazon 的台灯做一组图片",
        product_profile=_request()["product_profile"],
        uploaded_asset_ids=["product_lamp_front"],
        scenario_parameters={"platform": "amazon_us", "approved_literal_copy": "Adjustable warm light"},
        platform_profile=None,
        job_key="job_lamp",
    )

    assert output.marketplace_profile.platform == "amazon"
    assert output.marketplace_profile.image_slots == []
    assert output.recipes == []
    assert output.creative_context is not None
    assert output.creative_context.approved_literal_copy == "Adjustable warm light"
    assert output.creative_context.category_evidence_questions
    assert output.metadata["creative_recipe_present"] is False
    assert output.export_package.files == []
    assert output.export_package.naming_pattern == "{opaque_output_id}.png"


def test_production_service_fails_closed_when_remote_brain_is_not_available() -> None:
    status = V3ProductApiService().create_job(_request())

    assert status.status == "blocked"
    assert "remote_creative_brain_required_for_template" in " ".join(status.warnings)


def test_test_only_remote_brain_drives_opaque_outputs_and_provider_native_copy() -> None:
    service = ecommerce_test_service()
    created = service.create_job(_request(count=2, approved_copy="Adjustable warm light"))

    assert created.status == "planned"
    assert created.ecommerce is not None
    assert created.ecommerce.image_recipes == []
    assert [item.metadata["ecommerce_slot"] for item in created.asset_series] == [
        "ecommerce_output_1",
        "ecommerce_output_2",
    ]
    assert all(item.metadata["asset_metadata"]["ecommerce_llm_directed"] for item in created.asset_series)
    assert all("ecommerce_recipe" not in item.metadata for item in created.asset_series)

    generated = service.generate_job(created.job_id, {"quality_mode": "standard"})
    record = service.job_store.get(created.job_id)
    assert generated.status == "generated"
    assert record is not None and record.generation_result is not None
    prompt = record.generation_result.prompt_compilations[0]
    assert prompt.text_policy == "provider_native_text_requested"
    assert "Adjustable warm light" in prompt.visual_prompt
    assert prompt.provider_notes["text_rendering_owner"] == "image_provider"
    assert "ecommerce_recipe" not in prompt.metadata

    exported = service.export_job(created.job_id)
    assert exported.export_package is not None
    assert exported.export_package["naming_pattern"] == "{opaque_output_id}.png"
    assert [item["opaque_output_id"] for item in exported.export_package["files"]] == [
        "ecommerce_output_1",
        "ecommerce_output_2",
    ]
    assert exported.manifest is not None
    assert exported.manifest["image_recipes"] == []
    assert len(exported.manifest["remote_brain_output_intents"]) == 2


def test_general_brain_request_has_no_ecommerce_context_or_instruction() -> None:
    request = V3LLMBrainAdapter().build_request(
        user_input="给夏日饮料做一张社交媒体海报",
        stage="planning",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={},
    )
    assert "ecommerce_creative_context" not in request.metadata
    payload = json.loads(build_remote_payload(request))
    assert "ecommerce_creative_context" not in payload
    assert "ecommerce_context_instructions" not in payload


def test_ecommerce_public_api_still_rejects_low_level_controls() -> None:
    with pytest.raises(ValueError):
        V3ProductApiService().create_job(
            {
                "user_input": "Create an ecommerce set",
                "scenario_selection": {"scenario_id": "ecommerce"},
                "metadata": {"seed": 42},
            }
        )
