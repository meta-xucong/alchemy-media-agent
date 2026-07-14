import json

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioPackRegistry, ScenarioPackStatus
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import EcommerceScenarioPackPlanner
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
    ecommerce_test_service,
)


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


class _FlaggedRemoteBrainAdapter(V3LLMBrainAdapter):
    """Test-only adapter for fail-closed flag combinations."""

    def __init__(self, *, llm_used: bool, fallback_used: bool) -> None:
        super().__init__(provider=EcommerceRemoteBrainTestProvider())
        self._llm_used = llm_used
        self._fallback_used = fallback_used

    def run(self, request):
        result = super().run(request)
        result.llm_used = self._llm_used
        result.fallback_used = self._fallback_used
        return result


@pytest.mark.parametrize("count", [1, 2, 4, 7])
def test_ecommerce_exact_count_survives_plan_generation_and_export(count: int) -> None:
    service = ecommerce_test_service()
    created = service.create_job(_request(count=count))

    assert created.status == "planned"
    assert len(created.asset_series) == count
    assert created.ecommerce is not None
    assert len(created.ecommerce.remote_brain_output_intents) == count
    record = service.job_store.get(created.job_id)
    assert record is not None
    frozen = record.request.metadata["normalized_v3_job_intent"]
    delivery = record.request.metadata["template_deliverable_plan"]
    assert frozen["requested_image_count"] == frozen["effective_image_count"] == count
    assert len(delivery["deliverables"]) == count

    generated = service.generate_job(created.job_id, {"quality_mode": "standard"})
    assert generated.status == "generated"
    assert len(generated.asset_series) == count
    assert len(generated.candidates) == count

    exported = service.export_job(created.job_id)
    assert len(exported.export_package["files"]) == count
    assert [item["opaque_output_id"] for item in exported.export_package["files"]] == [
        f"ecommerce_output_{index}" for index in range(1, count + 1)
    ]


def test_ecommerce_declared_capacity_blocks_with_provenance_instead_of_truncating() -> None:
    service = ecommerce_test_service()
    payload = _request(count=7)
    payload["scenario_selection"]["parameters"]["provider_max_requested_images"] = 4
    created = service.create_job(payload)

    assert created.status == "blocked"
    assert created.asset_series == []
    provenance = created.metadata["ecommerce_runtime_provenance"]
    assert provenance["events"][-1] == {
        "stage": "planning",
        "runtime_status": "blocked",
        "fail_closed": True,
        "failure_reason_codes": ["requested_image_count_not_supported_by_declared_contract"],
    }
    record = service.job_store.get(created.job_id)
    assert record is not None and record.planning_result is None


@pytest.mark.parametrize(
    ("fault", "expected_reason"),
    [
        ("unavailable", "remote_creative_brain_required_for_template"),
        ("missing_image_set_plan", "remote_creative_brain_image_set_plan_invalid"),
        ("empty_image_set_plan", "remote_creative_brain_image_set_plan_invalid"),
        ("mismatched_image_set_plan", "remote_creative_brain_image_set_plan_invalid"),
    ],
)
def test_ecommerce_remote_brain_faults_fail_closed_without_static_outputs(
    fault: str,
    expected_reason: str,
) -> None:
    provider = EcommerceRemoteBrainTestProvider(fault=fault)
    service = ecommerce_test_service(brain_provider=provider)
    created = service.create_job(_request(count=2))

    assert created.status == "blocked"
    assert created.asset_series == []
    assert expected_reason in " ".join(created.warnings)
    provenance = created.metadata["ecommerce_runtime_provenance"]
    assert provenance["events"][-1]["failure_reason_codes"] == [expected_reason]
    assert provider.requests == [] if fault == "unavailable" else len(provider.requests) == 1


@pytest.mark.parametrize(
    ("llm_used", "fallback_used"),
    [(False, False), (True, True)],
)
def test_ecommerce_brain_flag_degradation_is_fail_closed(llm_used: bool, fallback_used: bool) -> None:
    runtime = ScenarioRuntime(
        llm_brain_adapter=_FlaggedRemoteBrainAdapter(llm_used=llm_used, fallback_used=fallback_used)
    )
    result = runtime.plan_job(_request(count=2))

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert "remote_creative_brain_required_for_template" in " ".join(result.warnings)
    assert result.planning_result is None


@pytest.mark.parametrize(
    ("scenario_id", "template_id"),
    [
        ("general_creative", "general_template"),
        ("photography", "photographer_template"),
    ],
)
def test_non_ecommerce_brain_requests_never_receive_ecommerce_context(
    scenario_id: str,
    template_id: str,
) -> None:
    request = V3LLMBrainAdapter().build_request(
        user_input="Create a commercial image for a supplied product.",
        stage="planning",
        scenario_id=scenario_id,
        template_id=template_id,
        metadata={
            "ecommerce_creative_context": {"product_truth": {"immutable_attributes": ["should not leak"]}},
        },
    )

    assert "ecommerce_creative_context" not in request.metadata
    assert "ecommerce" not in build_remote_payload(request).lower()


def test_general_product_keywords_do_not_activate_ecommerce_or_send_its_context() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    service = ecommerce_test_service(brain_provider=provider)
    created = service.create_job(
        {
            "user_input": "Create an Amazon-style product visual for this lamp, but keep this in General Template.",
            "scenario_selection": {"scenario_id": "general_creative", "parameters": {"requested_image_count": 1}},
            "product_profile": {"product_category": "desk lamp", "platform": "amazon_us"},
        }
    )

    assert created.status == "planned"
    assert created.ecommerce is None
    assert provider.requests
    assert all("ecommerce_creative_context" not in request["metadata"] for request in provider.requests)


def test_legacy_recipe_and_overlay_values_are_read_compatible_but_never_replayed() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    service = ecommerce_test_service(brain_provider=provider)
    legacy_marker = "LEGACY_RECIPE_MUST_NOT_REACH_BRAIN"
    payload = _request(count=2)
    payload["metadata"] = {
        "ecommerce_recipe": {"visual_scene": legacy_marker},
        "overlay_copy": legacy_marker,
        "copy_render_plan": {"text": legacy_marker},
        "text_pixel_delivery_internal": {"copy_render_plans": [{"text": legacy_marker}]},
        "role_specific_generation_plan": {"role_recipes": [{"camera": legacy_marker}]},
    }
    payload["scenario_selection"]["parameters"].update(
        {
            "suite_slots_requested": [legacy_marker],
            "overlay_text": legacy_marker,
            "mode_role_recipe": {"scene": legacy_marker},
        }
    )

    created = service.create_job(payload)
    assert created.status == "planned"
    record = service.job_store.get(created.job_id)
    assert record is not None
    ignored = record.request.metadata["ecommerce_legacy_execution_ignored"]
    assert ignored["status"] == "read_compatible_not_executed"
    assert {"ecommerce_recipe", "overlay_copy", "copy_render_plan", "suite_slots_requested"}.issubset(ignored["fields"])
    assert all(legacy_marker not in json.dumps(request, ensure_ascii=False) for request in provider.requests)

    generated = service.generate_job(created.job_id, {"quality_mode": "standard"})
    assert generated.status == "generated"
    record = service.job_store.get(created.job_id)
    assert record is not None and record.generation_result is not None
    assert all(
        legacy_marker not in json.dumps(prompt.model_dump(mode="json"), ensure_ascii=False)
        for prompt in record.generation_result.prompt_compilations
    )


def test_ecommerce_factual_context_and_failure_state_have_queryable_provenance() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    service = ecommerce_test_service(brain_provider=provider)
    payload = _request(count=1)
    payload["product_profile"]["evidence"] = ["seller test certificate"]
    payload["scenario_selection"]["parameters"]["target_audience"] = ["home-office buyers"]
    created = service.create_job(payload)

    provenance = created.metadata["ecommerce_runtime_provenance"]
    factual = provenance["factual_context"]
    assert factual["context_id"]
    assert factual["source_version"] == "ecommerce_creative_context_v2"
    assert factual["platform_profile_id"] == "ecommerce_amazon_us"
    assert factual["platform_profile_version"]
    assert "claim evidence" in factual["product_evidence_sources"]
    assert "target_audience" in factual["seller_input_fields"]
    assert provenance["events"][-1]["runtime_status"] == "planned"
