"""A no-pixel Brain outage is a transport outcome, never a quality verdict."""
from types import SimpleNamespace
import pytest
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.tests.test_v3_product_api_minimal_ux import _remote_finalizer_timeout_outcome


@pytest.mark.parametrize("error,available,expected", [
    ("timeout", True, "brain_timeout"),
    ("provider_unavailable", False, "provider_unavailable"),
    ("provider_error", True, "brain_provider_error"),
])
def test_no_pixel_brain_failure_has_transport_category(error, available, expected):
    outcome = _remote_finalizer_timeout_outcome()
    outcome["remote_error_class"] = error
    outcome["remote_provider_available"] = available
    if error != "timeout":
        outcome.pop("remote_brain_transport_failure")
    failure = V3ProductApiService._generation_lifecycle_failure_from_runtime_result(
        SimpleNamespace(metadata={"remote_creative_brain_outcome": outcome}))
    assert failure["failure_category"] == expected
    assert failure["quality_failure"] is False
    assert failure["quality_assessment"] == "not_assessed"
    assert failure["provider_request_started"] is False
    assert "evaluation_reports" not in failure
    assert "private prompt" not in str(failure)
    assert "provider.invalid" not in str(failure)

def test_activation_block_does_not_masquerade_as_quality_failure():
    failure = V3ProductApiService._generation_lifecycle_failure_from_runtime_result(
        SimpleNamespace(metadata={"capability_activation_error_code": "general_variation_suite_direction_not_active"}))
    assert failure is not None
    assert failure["quality_failure"] is False
    assert failure["quality_assessment"] == "not_assessed"


def test_timeout_preserves_project_and_does_not_create_empty_rejection(tmp_path, monkeypatch):
    from alchemy_creative_agent_3_0.tests.test_v3_product_api_minimal_ux import _RemoteFinalizerTimeoutRuntime
    from alchemy_creative_agent_3_0.tests.test_v3_post_generation_vision_review import _service
    monkeypatch.setenv("ALCHEMY_V3_JOB_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("ALCHEMY_V3_OUTPUT_DIR", str(tmp_path / "outputs"))
    service = _service(tmp_path)
    service.scenario_runtime = _RemoteFinalizerTimeoutRuntime(service.scenario_runtime, block_stage="plan")
    status = service.create_job({"user_input": "CELISIA product-only silver jar on white, no people.",
        "metadata": {"project_id": "project_timeout_retained"}})
    failure = status.metadata["generation_lifecycle_failure"]
    assert failure["failure_category"] == "brain_timeout"
    assert failure["quality_failure"] is False
    record = service.get_job_record(status.job_id)
    assert record.request.metadata["project_id"] == "project_timeout_retained"
    assert record.generation_result is None
    assert record.planning_result is None
    assert service.output_store.list_by_job(status.job_id) == []
    assert not status.candidates
