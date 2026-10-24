"""Native configured cloud continuation with mocked transport, never paid calls."""
import base64
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_render_bridge_native_facade import target_fixture  # noqa: F401
from test_render_bridge_native_registration import native_fixture, _png_bytes, _receipt  # noqa: F401
from alchemy_creative_agent_3_0.app.generation_router.providers import ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.render_bridge_native import NativeRenderBridgeGateway
from alchemy_creative_agent_3_0.app.product_api.render_bridge_facade import BridgeNativeFacadeError


@pytest.fixture
def cloud(native_fixture, monkeypatch):
    f = native_fixture
    monkeypatch.setattr(ProductionImageGenerationProvider, "_select_provider", lambda self, refs: "openai_gpt_image")
    transport = Mock(return_value=SimpleNamespace(provider="openai_gpt_image", model="configured-image-model",
        outputs=[{"b64_json": base64.b64encode(_png_bytes()).decode(), "mime_type": "image/png",
                  "format": "png", "width": 1024, "height": 1024}], raw_response_summary={}))
    monkeypatch.setattr(ProductionImageGenerationProvider, "_run_app_provider_with_timeout_retry", transport)
    frozen = f.gateway.prepare(7, f.target)
    return f, transport, {"frozen_request_id": frozen["frozen_request_id"], "execution_key": "cloud-1"}


def test_configured_native_transport_same_plan_and_review_only(cloud):
    f, transport, args = cloud
    assert f.gateway.cloud_admission(7, f.target, frozen_request_id=args["frozen_request_id"])["status"] == "ready"
    assert transport.call_count == 0
    result = f.gateway.cloud_execute(7, f.target, **args)
    assert result["status"] == "registered", result
    assert result["formal_delivery"] is False
    assert result["billing"]["upstream_may_charge"] is True
    assert transport.call_count == 1
    assert f.review_only_calls == [True]
    record = f.jobs.get(f.target.job_id)
    assert "render_bridge_native_plan" in record.request.metadata
    projection, _, _ = f.service._public_final_delivery_projection(record.generation_result)
    assert projection["final_delivery_status"] == "withheld_bridge_development"
    assert f.gateway.cloud_execute(7, f.target, **args)["native_registration_ref"] == result["native_registration_ref"]
    assert transport.call_count == 1
    assert len(f.outputs.list_by_job(f.target.job_id)) == 1


def test_unknown_never_regenerates_even_after_restart(cloud):
    f, transport, args = cloud
    transport.side_effect = TimeoutError("response lost")
    assert f.gateway.cloud_execute(7, f.target, **args)["status"] == "cloud_unknown"
    gateway = NativeRenderBridgeGateway(facade=f.facade, service=f.service, journal_root=f.journal_root, enabled=True)
    assert gateway.cloud_status(7, f.target, **args)["status"] == "cloud_unknown"
    assert gateway.cloud_execute(7, f.target, **args)["status"] == "cloud_unknown"
    assert transport.call_count == 1
    with pytest.raises(BridgeNativeFacadeError, match="native_target_conflict"):
        gateway.register_receipt(7, f.target, **_receipt(f))


def test_output_checkpoint_recovers_without_transport(cloud, monkeypatch):
    f, transport, args = cloud
    project = f.service._project_frozen_provider_candidate
    monkeypatch.setattr(f.service, "_project_frozen_provider_candidate", Mock(side_effect=RuntimeError("crash after output")))
    assert f.gateway.cloud_execute(7, f.target, **args)["status"] == "cloud_unknown"
    assert len(f.outputs.list_by_job(f.target.job_id)) == 1
    monkeypatch.setattr(f.service, "_project_frozen_provider_candidate", project)
    assert f.gateway.cloud_status(7, f.target, **args)["status"] == "registered"
    assert transport.call_count == 1


def test_changed_frozen_options_and_balance_block_before_transport(cloud, monkeypatch):
    f, transport, args = cloud
    monkeypatch.setattr(f.service.balance_adapter, "has_available_credits", lambda amount: False)
    admission = f.gateway.cloud_admission(7, f.target, frozen_request_id=args["frozen_request_id"])
    assert admission["status"] == "blocked"
    assert transport.call_count == 0


def test_no_config_blocks_admission(cloud, monkeypatch):
    f, transport, args = cloud
    monkeypatch.setattr(ProductionImageGenerationProvider, "_select_provider", Mock(side_effect=ValueError("no key")))
    assert f.gateway.cloud_admission(7, f.target, frozen_request_id=args["frozen_request_id"])["status"] == "blocked"
    assert transport.call_count == 0


def test_absent_status_is_not_started_and_never_calls_transport(cloud):
    f, transport, args = cloud
    assert f.gateway.cloud_status(7, f.target, **args)["status"] == "not_started"
    assert transport.call_count == 0


def test_canceled_completed_checkpoint_remains_queryable_without_review(cloud):
    f, transport, args = cloud
    result = f.gateway.cloud_execute(7, f.target, **args)
    record = f.jobs.get(f.target.job_id)
    record.request.metadata["cancel_requested"] = True
    f.jobs.save(record)
    before = len(f.review_only_calls)
    assert f.gateway.cloud_status(7, f.target, **args)["native_registration_ref"] == result["native_registration_ref"]
    assert len(f.review_only_calls) == before
    assert transport.call_count == 1


def test_owner_and_execution_key_cannot_cross_bindings(cloud):
    f, transport, args = cloud
    assert f.gateway.cloud_execute(7, f.target, **args)["status"] == "registered"
    with pytest.raises(BridgeNativeFacadeError, match="target_not_found"):
        f.gateway.cloud_status(8, f.target, **args)
    with pytest.raises(BridgeNativeFacadeError, match="binding_conflict"):
        f.gateway.cloud_status(7, f.target, **{**args, "execution_key": "another"})
    assert transport.call_count == 1


def test_native_cloud_cannot_select_export_or_ordinary_regenerate(cloud):
    from alchemy_creative_agent_3_0.app.product_api.contracts import SelectResultRequest
    import json
    f, transport, args = cloud
    result = f.gateway.cloud_execute(7, f.target, **args)
    selected = f.service.select_result(f.target.job_id, SelectResultRequest())
    assert selected.metadata["selection_held"] is True
    assert f.jobs.get(f.target.job_id).selected_result is None
    assert result["native_registration_ref"] not in json.dumps(f.service.export_job(f.target.job_id).manifest)
    f.service.generate_asset_series(f.target.job_id)
    assert transport.call_count == 1


def test_frozen_prompt_mismatch_blocks_native_provider(cloud):
    from alchemy_creative_agent_3_0.app.generation_router.render_bridge_provider import RenderBridgeCloudContinuation
    f, transport, args = cloud
    frozen = f.gateway.prepare(7, f.target)
    frozen["prompt"] = "A different creative intent is forbidden"
    binding = RenderBridgeCloudContinuation("cloud-1", frozen)
    with pytest.raises(ValueError, match="frozen_contract_mismatch"):
        f.service.admit_render_bridge_cloud(binding, assert_current=lambda: None)
    assert transport.call_count == 0


def test_target_revision_changed_before_execute_blocks_transport(cloud):
    f, transport, args = cloud
    record = f.jobs.get(f.target.job_id)
    record.request.user_input += " changed"
    f.jobs.save(record)
    with pytest.raises(BridgeNativeFacadeError, match="frozen_request_changed"):
        f.gateway.cloud_execute(7, f.target, **args)
    assert transport.call_count == 0


from test_render_bridge_native_planning import planning_fixture, _upload_reference, _create, _new_target  # noqa: E402,F401


def test_cloud_preserves_two_ordered_originals_and_single_brain_plan(planning_fixture, monkeypatch):
    f = planning_fixture
    ids = [_upload_reference(f, color=color).asset_id for color in ("red", "blue")]
    f = _new_target(f, _create(f, uploaded_asset_ids=ids))
    frozen = f.gateway.prepare(7, f.target)
    seen = []
    monkeypatch.setattr(ProductionImageGenerationProvider, "_select_provider", lambda self, refs: "openai_gpt_image")
    def transport(provider, app_request, references, **kwargs):
        seen.append([ref["asset_id"] for ref in references])
        assert app_request.prompt_plan.variables["generation_prompt"] == frozen["prompt"]
        return SimpleNamespace(provider=provider, model="mock-transport", outputs=[{
            "b64_json": base64.b64encode(_png_bytes()).decode(), "mime_type": "image/png",
            "format": "png", "width": 1024, "height": 1024}], raw_response_summary={})
    monkeypatch.setattr(ProductionImageGenerationProvider, "_run_app_provider_with_timeout_retry", staticmethod(transport))
    result = f.gateway.cloud_execute(7, f.target, frozen_request_id=frozen["frozen_request_id"], execution_key="references")
    assert result["status"] == "registered", result
    assert seen == [ids]
    assert len(f.planning_calls) == 1
