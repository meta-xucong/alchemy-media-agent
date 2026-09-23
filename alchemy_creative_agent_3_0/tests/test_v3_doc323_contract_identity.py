"""Admission and Brain must bind the same Job before any generation begins."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.tests import test_v3_doc267_post_generation_review_closure as prior


@pytest.mark.parametrize("scenario", ["general_creative", "ecommerce", "photography"])
def test_prebrain_job_identity_is_pure_and_matches_runtime(tmp_path, monkeypatch, scenario):
    handlers, _ = prior._handlers(tmp_path)
    service = handlers.service
    request = CreateCreativeJobRequest(user_input="  Keep the exact user direction.\n",
        scenario_selection={"scenario_id": scenario}, metadata={
            "project_id": "project", "project_job_sequence": 2,
            "v3_job_instance_id": "current_server_instance"})
    before = deepcopy(request.model_dump(mode="json"))
    monkeypatch.setattr(service, "_runtime_request_payload", Mock(side_effect=AssertionError("materialized assets for an ID")))
    resolved = service.scenario_runtime.scenario_registry.resolve(request.scenario_selection)
    expected = service.scenario_runtime._runtime_job_id(ScenarioRuntimeRequest(
        user_input=request.user_input, optional_brand_id=request.effective_brand_id,
        scenario_selection=request.scenario_selection, metadata=dict(request.metadata)), resolved)
    assert service._planned_job_id_for_request(request) == expected
    assert request.model_dump(mode="json") == before

def test_product_admission_never_rebinds_after_brain_signoff(tmp_path, monkeypatch):
    handlers, catalog = prior._handlers(tmp_path)
    service = handlers.service
    provider = prior._CapturingMockGenerationProvider()
    service.scenario_runtime.generation_router = prior.GenerationRouter(provider=provider)
    project = prior._project(handlers)
    product_ids = [prior._ready_product_upload(handlers,
        filename=f"product-{i}.png", color=(80+i*20, 130, 165)) for i in range(4)]
    prior._add_product_references(handlers, project["project_id"], product_ids)
    prior._bind_locked_person_identity(handlers, catalog, project_id=project["project_id"])
    admissions = []
    build = service._build_ecommerce_product_truth_admission
    def capture(*args, **kwargs):
        result = build(*args, **kwargs)
        admissions.append(result.model_dump())
        return result
    monkeypatch.setattr(service, "_build_ecommerce_product_truth_admission", capture)
    payload = prior._job_payload(uploaded_asset_ids=product_ids, key="doc323-stable-identity")
    payload["metadata"].update({"requested_image_count": 1,
        "advanced_reference_controls": {"preserve_person_identity": False}})
    created = handlers.post_project_job(project["project_id"], payload)
    record = service.get_job_record(created["job_id"])
    assert record.planning_result is not None
    frozen = deepcopy(record.request.metadata["professional_ecommerce_product_truth_admission"])
    assert admissions
    assert {item["job_id"] for item in admissions} == {record.job_id}
    assert {item["source_binding_digest"] for item in admissions} == {frozen["source_binding_digest"]}
    handlers.post_project_job_generate(project["project_id"], created["job_id"])
    assert len(provider.requests) == 1
    assert record.request.metadata["professional_ecommerce_product_truth_admission"] == frozen
    assert "ecommerce_product_truth_selection_context_digest_mismatch" not in str(record.warnings)


@pytest.mark.parametrize("field,value", [("admission_digest", "different-admission"),
    ("expected_count", 2), ("provider_budget", {"max_product_truth_source_refs_per_output": 1})])
def test_context_digest_still_rejects_contract_drift(field, value):
    from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import ecommerce_product_truth_context_digest
    fields = {"uploaded_assets": [{"asset_id": "product", "role": "product_reference"}],
        "reference_pool": [{"asset_id": "product", "reference_channel": "product_truth", "source_type": "uploaded"}],
        "provider_budget": {"max_product_truth_source_refs_per_output": 2},
        "expected_count": 1, "admission_digest": "current-admission"}
    original = ecommerce_product_truth_context_digest(**fields)
    assert original
    assert ecommerce_product_truth_context_digest(**{**fields, field: value}) != original
