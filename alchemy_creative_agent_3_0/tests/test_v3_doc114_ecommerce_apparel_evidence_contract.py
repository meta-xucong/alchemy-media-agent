"""Doc114 Phase C E-Commerce-owned apparel-on-model evidence contracts."""

from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import EcommerceScenarioPackPlanner
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


def test_ecommerce_context_exposes_apparel_facts_without_locally_classifying_target_subjects() -> None:
    context = EcommerceScenarioPackPlanner().build_creative_context(
        user_input=_request()["user_input"],
        product_profile=_profile(),
        uploaded_asset_ids=["dress-reference"],
        scenario_parameters={"requested_image_count": 4},
        platform_profile="amazon_us",
        job_key="doc114-ecommerce-context",
    )

    assert context.source_version == "ecommerce_creative_context_v2"
    serialized = context.model_dump(mode="json")
    assert "slot" not in serialized
    assert "apparel_on_model_evidence_profile" not in serialized
    assert serialized["product_truth"]["apparel_construction"]["facts"]
    assert serialized["metadata"]["target_subject_decision_owner"] == "remote_brain"


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

    assert "apparel_on_model_evidence_profile" not in payload["ecommerce_creative_context"]
    assert "evidence_dimensions_by_output" in payload["return_schema"]["image_set_plan"]
    assert payload["return_schema"]["image_set_plan"]["image_count"] == "integer exactly equal to requested_image_count"
    assert "sole semantic declaration" in payload["ecommerce_context_instructions"]


def test_ecommerce_brain_owns_visible_person_semantics_without_local_role_map(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    service = ecommerce_test_service(
        brain_provider=EcommerceRemoteBrainTestProvider(visible_ecommerce_person=True)
    )

    created = service.create_job(_request(count=4))
    record = service.job_store.get(created.job_id)

    assert created.status == "planned"
    assert record is not None and record.planning_result is not None
    delivery = record.planning_result.metadata["template_deliverable_plan"]

    assert record.request.metadata["visual_task_profile"]["subject_entities"] == [
        {
            "entity_id": "test_remote_brain_visible_person",
            "entity_type": "person",
            "role": "subject",
            "source_asset_ids": [],
            "visible_in_target": True,
            "preservation_level": "balanced",
            "confidence": 0.98,
            "attributes": {},
        }
    ]
    assert all(
        item["factual_acceptance"] == ["product_truth", "platform_factual_constraints"]
        for item in delivery["deliverables"]
    )
    assert all("brain_evidence_dimensions" not in item["metadata"] for item in delivery["deliverables"])
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
