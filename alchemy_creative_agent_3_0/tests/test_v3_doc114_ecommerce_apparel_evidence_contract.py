"""Doc114 Phase C E-Commerce-owned apparel-on-model evidence contracts."""

from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import EcommerceScenarioPackPlanner
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider, ecommerce_test_service


def _profile() -> dict:
    return {
        "product_category": "apparel",
        "product_name": "blue layered occasion dress",
        "apparel_construction": {
            "silhouette_and_proportion": "A-line knee-length silhouette",
            "print_or_pattern_registration": "blue floral print stays registered across bodice and skirt",
            "layer_order": ["lining", "two uneven tulle overlays"],
            "seam_hem_edge_trim_fastening": "waist seam, scalloped hem trim, back button",
            "material_weight_and_surface_response": "matte woven lining and translucent tulle",
            "fold_tension_gravity_and_drape": "soft gravity-driven folds and irregular tulle edge separation",
        },
    }


def _request(*, count: int = 4) -> dict:
    return {
        "user_input": "Create ecommerce images of a model wearing the supplied layered dress, with natural candid moments.",
        "scenario_selection": {
            "scenario_id": "ecommerce",
            "parameters": {"requested_image_count": count, "provider_max_requested_images": 7},
        },
        "uploaded_asset_ids": ["dress-reference"],
        "product_profile": _profile(),
        "metadata": {"requested_image_count": count, "provider_max_requested_images": 7},
    }


def test_ecommerce_context_declares_dimensions_not_a_static_apparel_recipe() -> None:
    context = EcommerceScenarioPackPlanner().build_creative_context(
        user_input=_request()["user_input"],
        product_profile=_profile(),
        uploaded_asset_ids=["dress-reference"],
        scenario_parameters={"requested_image_count": 4},
        platform_profile="amazon_us",
        job_key="doc114-ecommerce-context",
    )

    profile = context.apparel_on_model_evidence_profile

    assert context.source_version == "ecommerce_creative_context_v2"
    assert profile is not None and profile.applies is True
    assert profile.allowed_evidence_dimensions == [
        "product_view",
        "movement",
        "construction_proof",
        "context",
        "camera_crop",
        "expression_pose",
    ]
    assert profile.required_distinct_dimension_count == 4
    assert profile.metadata["static_recipe_present"] is False
    serialized = context.model_dump(mode="json")
    assert "slot" not in serialized
    assert "scene" not in serialized["apparel_on_model_evidence_profile"]
    assert "fixed_pose" not in serialized["apparel_on_model_evidence_profile"]


def test_remote_brain_payload_exposes_only_the_ecommerce_evidence_boundary() -> None:
    context = EcommerceScenarioPackPlanner().build_creative_context(
        user_input=_request()["user_input"],
        product_profile=_profile(),
        uploaded_asset_ids=["dress-reference"],
        scenario_parameters={"requested_image_count": 4},
        platform_profile=None,
        job_key="doc114-ecommerce-payload",
    )
    request = V3LLMBrainAdapter().build_request(
        user_input=_request()["user_input"],
        stage="plan",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        metadata={
            "requested_image_count": 4,
            "ecommerce_creative_context": context.model_dump(mode="json"),
        },
    )
    payload = json.loads(build_remote_payload(request))

    profile = payload["ecommerce_creative_context"]["apparel_on_model_evidence_profile"]

    assert profile["metadata"]["static_recipe_present"] is False
    assert "evidence_dimensions_by_output" in payload["return_schema"]["image_set_plan"]
    assert payload["return_schema"]["image_set_plan"]["image_count"] == "integer exactly equal to requested_image_count"
    assert "stock role" in payload["ecommerce_context_instructions"]


def test_ecommerce_brain_final_contract_maps_distinct_evidence_without_local_role_map(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    service = ecommerce_test_service()

    created = service.create_job(_request(count=4))
    record = service.job_store.get(created.job_id)

    assert created.status == "planned"
    assert record is not None and record.planning_result is not None
    delivery = record.planning_result.metadata["template_deliverable_plan"]
    dimensions = [item["metadata"]["brain_evidence_dimensions"] for item in delivery["deliverables"]]

    assert len(dimensions) == 4
    assert len({tuple(item) for item in dimensions}) == 4
    assert len({value for item in dimensions for value in item}) >= 4
    assert all("apparel_on_model_evidence_contract" in item["factual_acceptance"] for item in delivery["deliverables"])
    assert all("specialized_role_key" not in item["metadata"] for item in delivery["deliverables"])
    assert delivery["owner"] == "ecommerce_template"
    assert delivery["creative_direction_owner"] == "remote_v3_llm_brain"


def test_one_requested_apparel_output_remains_product_first_without_forced_diversity_contract(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    service = ecommerce_test_service()

    created = service.create_job(_request(count=1))
    record = service.job_store.get(created.job_id)

    assert created.status == "planned"
    assert record is not None and record.planning_result is not None
    deliverable = record.planning_result.metadata["template_deliverable_plan"]["deliverables"][0]
    assert deliverable["factual_acceptance"] == ["product_truth", "platform_factual_constraints"]
    assert "brain_evidence_dimensions" not in deliverable["metadata"]


class _RepeatedEvidenceRemoteBrainTestProvider(EcommerceRemoteBrainTestProvider):
    provider = "repeated_evidence_remote_brain_test_double"

    def run(self, request) -> dict:
        payload = super().run(request)
        count = request.requested_image_count
        payload["image_set_plan"]["evidence_dimensions_by_output"] = [
            {"output_index": index, "evidence_dimensions": ["product_view"]}
            for index in range(1, count + 1)
        ]
        return payload


def test_runtime_rejects_repeated_ecommerce_apparel_evidence_contract(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    context = EcommerceScenarioPackPlanner().build_creative_context(
        user_input=_request()["user_input"],
        product_profile=_profile(),
        uploaded_asset_ids=["dress-reference"],
        scenario_parameters={"requested_image_count": 4, "provider_max_requested_images": 7},
        platform_profile=None,
        job_key="doc114-repeated-evidence",
    )
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=_RepeatedEvidenceRemoteBrainTestProvider())
    )
    payload = _request(count=4)
    payload["metadata"]["ecommerce_creative_context"] = context.model_dump(mode="json")

    result = runtime.plan_job(payload)

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert "ecommerce_apparel_evidence_contract_repeated_output" in " ".join(result.warnings)
