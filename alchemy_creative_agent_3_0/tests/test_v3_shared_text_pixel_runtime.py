from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image

from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.text_pixel import (
    CopyRenderPlan,
    CopyRenderPlanBatch,
    CopyRenderSourceLineage,
    NormalizedSafeArea,
    TextPixelDeliveryRuntime,
)


def _base_output(store: V3GeneratedOutputStore, *, asset_id: str = "text_pixel_asset"):
    image = Image.new("RGB", (96, 72), "#d9d9d9")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return store.save_base64_output(
        job_id="text_pixel_job",
        candidate_id=f"candidate_{asset_id}",
        asset_id=asset_id,
        provider="test_provider",
        model="test_model",
        encoded_image=base64.b64encode(buffer.getvalue()).decode("ascii"),
    )


def _plan(asset_id: str = "text_pixel_asset") -> CopyRenderPlan:
    return CopyRenderPlan(
        expected_copy="Approved headline",
        locale="en-US",
        text_policy="required",
        normalized_safe_area=NormalizedSafeArea(x=0.1, y=0.1, w=0.8, h=0.2),
        layout_priority="headline",
        source_lineage=CopyRenderSourceLineage(
            capability_activation_plan_id="frozen_text_plan",
            source_job_id="text_pixel_job",
            source_asset_id=asset_id,
        ),
    )


def _frozen_plan() -> dict:
    return {
        "plan_id": "frozen_text_plan",
        "dependency_order": ["visual_grammar", "universal_visual_quality", "text_pixel_delivery"],
    }


def test_legacy_copy_render_plan_remains_readable_and_bindable() -> None:
    plan = _plan().model_copy(
        update={"source_lineage": CopyRenderSourceLineage(source_asset_id="text_pixel_asset")}
    )

    bound = plan.bind_to_frozen_plan("frozen_text_plan")

    assert bound.source_lineage.capability_activation_plan_id == "frozen_text_plan"
    assert bound.normalized_safe_area.model_dump() == plan.normalized_safe_area.model_dump()


def test_direct_legacy_runtime_never_composes_or_replaces_provider_pixels(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    source = _base_output(store)

    delivery = TextPixelDeliveryRuntime(store).deliver(
        plan=_plan(),
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="candidate",
        asset_id="text_pixel_asset",
    )

    assert delivery.status == "provider_native_required"
    assert delivery.rendered is False
    assert delivery.current_output_id is None
    assert delivery.issue_codes == ["deterministic_text_pixel_delivery_retired"]
    assert store.get_output(source.output_id) is not None


def test_legacy_multi_plan_runtime_never_iterates_a_local_renderer(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    first, second = _base_output(store, asset_id="asset_a"), _base_output(store, asset_id="asset_b")
    plans = CopyRenderPlanBatch(plans=[_plan("asset_a"), _plan("asset_b")])

    delivery = TextPixelDeliveryRuntime(store).deliver_many(
        plans=plans,
        frozen_activation_plan=_frozen_plan(),
        source_outputs_by_plan={plans.plans[0].plan_id: first, plans.plans[1].plan_id: second},
        candidate_ids_by_plan={plans.plans[0].plan_id: "candidate_a", plans.plans[1].plan_id: "candidate_b"},
        asset_ids_by_plan={plans.plans[0].plan_id: "asset_a", plans.plans[1].plan_id: "asset_b"},
    )

    assert [item.status for item in delivery.deliveries] == ["provider_native_required", "provider_native_required"]
    assert all(item.rendered is False for item in delivery.deliveries)


def test_legacy_marker_cannot_activate_deterministic_capability(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create one image with an approved headline.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"internal_copy_render_plan_present": True},
        }
    )

    assert "text_pixel_delivery" not in result.metadata["capability_activation_plan"]["dependency_order"]


def test_product_api_returns_provider_native_required_for_historical_envelope(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create a single image with approved text.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"text_pixel_delivery_internal": {"copy_render_plan": _plan().model_dump(mode="json")}},
        }
    )

    generated = service.generate_job(created.job_id)
    record = service.job_store.get(created.job_id)

    assert generated.metadata["text_pixel_delivery"]["status"] == "provider_native_required"
    assert record is not None
    assert record.request.metadata["text_pixel_delivery_internal"]["binding_skipped_reason"] == "deterministic_text_pixel_delivery_retired"
