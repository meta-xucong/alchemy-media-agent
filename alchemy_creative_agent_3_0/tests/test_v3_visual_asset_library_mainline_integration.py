from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _standard_request() -> dict[str, object]:
    return {
        "user_input": "Create a calm editorial portrait in a neutral room.",
        "scenario_selection": {"scenario_id": "general_creative"},
        "metadata": {
            "project_id": "project_visual_asset_library",
            "template_id": "general_template",
            "requested_image_count": 1,
            "require_real_images": True,
        },
    }


def test_public_job_rejects_legacy_professional_selection_before_brain() -> None:
    service = V3ProductApiService()
    request = {
        **_standard_request(),
        "professional_mode": "professional",
        "people_asset_id": "legacy_person",
    }

    with pytest.raises(ValueError, match="legacy_professional_mode_forward_write_forbidden"):
        service.create_job(request)


def test_public_job_rejects_legacy_professional_metadata_before_brain() -> None:
    service = V3ProductApiService()
    request = _standard_request()
    request["metadata"] = {
        **request["metadata"],
        "professional_mode_binding": {"people_asset_id": "legacy_person"},
    }

    with pytest.raises(ValueError, match="legacy_professional_mode_forward_write_forbidden"):
        service.create_job(request)


def test_unbound_project_keeps_standard_generation_path_without_legacy_metadata() -> None:
    service = V3ProductApiService(
        scenario_runtime=ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider()))
    )

    status = service.create_job(_standard_request())

    assert status.status == ProductJobStatusValue.PLANNED
    record = service.get_job_record(status.job_id)
    assert record is not None
    assert "professional_mode" not in record.request.metadata
    assert "people_asset_id" not in record.request.metadata
    assert "frozen_visual_asset_binding_set" not in record.request.metadata


def test_library_bound_jobs_are_covered_by_doc173_server_owned_snapshot_contract() -> None:
    # The concrete library -> frozen Job -> Brain transport is deliberately
    # exercised in test_v3_doc173_visual_asset_library_first.  Keep this
    # integration file focused on the public boundary: callers cannot select
    # legacy project-scoped Professional state to bypass that contract.
    service = V3ProductApiService()
    request = _standard_request()
    request["people_asset_id"] = "legacy_person"

    with pytest.raises(ValueError, match="People Asset selection requires explicit Professional Mode"):
        service.create_job(request)
