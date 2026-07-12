from __future__ import annotations

import base64
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageFont

from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.text_pixel import (
    CopyRenderPlan,
    CopyRenderPlanBatch,
    CopyRenderSourceLineage,
    FontRegistry,
    LicensedFont,
    NormalizedSafeArea,
    StaticOcrEngine,
    TextPixelDeliveryRuntime,
    TextPixelRuntimeSettings,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.text_pixel.runtime import CompositionOutcome


def _font_path() -> Path:
    candidates = [
        os.getenv("V3_TEXT_PIXEL_TEST_FONT_PATH", ""),
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_file():
            continue
        try:
            ImageFont.truetype(path, size=12)
            return path
        except OSError:
            continue
    pytest.skip("No local test font is available for deterministic text-pixel tests.")


def _base_output(
    store: V3GeneratedOutputStore,
    color: str = "#e7e7e7",
    *,
    candidate_id: str = "text_pixel_candidate",
    asset_id: str = "text_pixel_asset",
):
    image = Image.new("RGB", (800, 600), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return store.save_base64_output(
        job_id="text_pixel_job",
        candidate_id=candidate_id,
        asset_id=asset_id,
        provider="test_provider",
        model="test_model",
        encoded_image=base64.b64encode(buffer.getvalue()).decode("ascii"),
    )


def _font(*, locales: tuple[str, ...] = ("en-US",)) -> LicensedFont:
    path = _font_path()
    return LicensedFont(
        font_id="test_font",
        version="test-v1",
        file_path=str(path),
        supported_locales=locales,
        license_id="test-fixture-license",
        expected_sha256=sha256(path.read_bytes()).hexdigest(),
        production_approved=False,
    )


def _plan(
    *,
    policy: str = "required",
    copy: str | None = "Clear delivery text",
    locale: str = "en-US",
    color: str | None = None,
    source_asset_id: str = "text_pixel_asset",
    activation_plan_id: str | None = "frozen_text_plan",
) -> CopyRenderPlan:
    return CopyRenderPlan(
        expected_copy=copy,
        locale=locale,
        text_policy=policy,
        normalized_safe_area=NormalizedSafeArea(x=0.1, y=0.1, w=0.8, h=0.3),
        layout_priority="headline",
        foreground_color=color,
        source_lineage=CopyRenderSourceLineage(
            capability_activation_plan_id=activation_plan_id,
            source_job_id="text_pixel_job",
            source_asset_id=source_asset_id,
        ),
    )


def _runtime(store: V3GeneratedOutputStore, ocr: StaticOcrEngine, *, font: LicensedFont | None = None, enabled: bool = True) -> TextPixelDeliveryRuntime:
    return TextPixelDeliveryRuntime(
        store,
        font_registry=FontRegistry([font or _font()]),
        ocr_engine=ocr,
        settings=TextPixelRuntimeSettings(enabled=enabled, allow_development_fonts=True),
    )


def _frozen_plan() -> dict:
    return {
        "plan_id": "frozen_text_plan",
        "activation_mode": "enforced",
        "dependency_order": ["visual_grammar", "universal_visual_quality", "text_pixel_delivery"],
    }


def test_copy_render_plan_binds_after_activation_and_preserves_geometry() -> None:
    unbound = CopyRenderPlan(
        expected_copy="One headline",
        locale="en-US",
        text_policy="required",
        normalized_safe_area=NormalizedSafeArea(x=0.1, y=0.2, w=0.7, h=0.2),
        layout_priority="headline",
        source_lineage=CopyRenderSourceLineage(source_asset_id="asset_1"),
    )
    bound = unbound.bind_to_frozen_plan("frozen_plan_1")

    assert unbound.source_lineage.capability_activation_plan_id is None
    assert bound.source_lineage.capability_activation_plan_id == "frozen_plan_1"
    assert bound.normalized_safe_area.model_dump() == unbound.normalized_safe_area.model_dump()
    assert bound.plan_id != unbound.plan_id


def test_internal_copy_plan_activates_shared_capability_without_ecommerce_metadata(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create one neutral social cover with an approved headline.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {
                "requested_image_count": 1,
                "text_pixel_delivery_internal": {
                    "copy_render_plan": {
                        "expected_copy": "One clear headline",
                        "locale": "en-US",
                        "text_policy": "required",
                        "normalized_safe_area": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.2},
                        "layout_priority": "headline",
                        "source_lineage": {"source_asset_id": "asset_001"},
                    }
                },
            },
        }
    )
    active = set(result.metadata["capability_activation_plan"]["dependency_order"])
    intent = result.metadata["capability_activation_intent"]

    assert "text_pixel_delivery" in active
    assert "ecommerce" not in str(intent).lower()
    assert "platform" not in str(intent).lower()


def test_product_api_binds_internal_plan_and_reports_gate_off_status(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.delenv("V3_TEXT_PIXEL_DELIVERY_ENABLED", raising=False)
    payload = {
        "user_input": "Create one neutral social cover with an approved headline.",
        "scenario_selection": {"scenario_id": "general_creative"},
        "metadata": {
            "requested_image_count": 1,
            "text_pixel_delivery_internal": {
                "copy_render_plan": {
                    "expected_copy": "One clear headline",
                    "locale": "en-US",
                    "text_policy": "required",
                    "normalized_safe_area": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.2},
                    "layout_priority": "headline",
                    "source_lineage": {"source_asset_id": "recipe_slot"},
                }
            },
        },
    }
    service = V3ProductApiService()
    created = service.create_job(payload)
    record = service.job_store.get(created.job_id)
    assert record is not None
    bound = record.request.metadata["text_pixel_delivery_internal"]["copy_render_plan"]
    assert bound["source_lineage"]["capability_activation_plan_id"] == record.request.metadata["capability_activation_plan_id"]
    assert "text_pixel_delivery" in record.request.metadata["capability_activation_plan"]["dependency_order"]

    generated = service.generate_job(created.job_id)
    assert generated.metadata["text_pixel_delivery"]["status"] == "planned_only"
    assert generated.metadata["text_pixel_delivery"]["rendered"] is False


def test_composes_reviews_final_pixels_and_keeps_source_append_only(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    source = _base_output(store)
    ocr = StaticOcrEngine("Clear delivery text")

    delivery = _runtime(store, ocr).deliver(
        plan=_plan(),
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
    )

    assert delivery.status == "passed"
    assert delivery.rendered is True
    assert delivery.review_passed is True
    assert delivery.current_output_id and delivery.current_output_id != source.output_id
    assert store.get_output(source.output_id) is not None
    assert store.get_output(delivery.current_output_id) is not None
    assert [attempt.stage for attempt in delivery.attempts] == ["composition", "review"]
    assert ocr.paths and Path(ocr.paths[0]).is_file()


def test_disabled_runtime_is_planned_only_and_never_claims_pixels(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    source = _base_output(store)
    delivery = _runtime(store, StaticOcrEngine("Clear delivery text"), enabled=False).deliver(
        plan=_plan(),
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
    )

    assert delivery.status == "planned_only"
    assert delivery.rendered is False
    assert delivery.review_passed is False
    assert delivery.current_output_id is None


def test_one_deterministic_repair_is_append_only_before_delivery(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    source = _base_output(store, "#777777")
    delivery = _runtime(store, StaticOcrEngine("Clear delivery text")).deliver(
        plan=_plan(color="#777777"),
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
    )

    assert delivery.status == "passed"
    assert [attempt.stage for attempt in delivery.attempts] == [
        "composition",
        "review",
        "deterministic_repair",
        "review",
    ]
    derived_ids = [
        attempt.derived_output_id
        for attempt in delivery.attempts
        if attempt.stage in {"composition", "deterministic_repair"} and attempt.derived_output_id
    ]
    assert len(derived_ids) == 2
    assert len(set(derived_ids)) == 2


def test_policy_and_ocr_failures_do_not_start_generation_retry(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    source = _base_output(store)
    blocked_claim = _plan()
    blocked_claim.claim_review_state = "blocked"
    claim_delivery = _runtime(store, StaticOcrEngine("Clear delivery text")).deliver(
        plan=blocked_claim,
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
    )
    mismatched_ocr = _runtime(store, StaticOcrEngine("wrong text")).deliver(
        plan=_plan(),
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
    )
    optional_plan = _plan(policy="optional", copy=None)
    optional_delivery = _runtime(store, StaticOcrEngine("")).deliver(
        plan=optional_plan,
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
    )

    assert claim_delivery.status == "requires_copy_correction"
    assert claim_delivery.rendered is False
    assert "generation_retry" not in claim_delivery.recovery
    assert mismatched_ocr.status == "requires_copy_correction"
    assert "ocr_text_mismatch" in mismatched_ocr.issue_codes
    assert "generation_retry" not in mismatched_ocr.recovery
    assert optional_delivery.status == "not_requested"
    assert optional_delivery.rendered is False


def test_only_one_deterministic_repair_can_request_existing_shared_retry(tmp_path) -> None:
    class AlwaysLowContrastCompositor:
        renderer_id = "test_low_contrast_compositor"

        def __init__(self) -> None:
            self.calls: list[bool] = []

        def compose(self, source_path, plan, font, *, repair=False):
            self.calls.append(repair)
            return CompositionOutcome(
                rendered=True,
                image_bytes=Path(source_path).read_bytes(),
                bounds_px={"x": 80, "y": 60, "w": 100, "h": 40},
                font_size_px=40,
                line_count=1,
                contrast_ratio=1.1,
                foreground_color="#777777",
                issue_codes=("text_low_contrast",),
            )

    store = V3GeneratedOutputStore(tmp_path / "outputs")
    source = _base_output(store, "#777777")
    compositor = AlwaysLowContrastCompositor()
    runtime = TextPixelDeliveryRuntime(
        store,
        font_registry=FontRegistry([_font()]),
        ocr_engine=StaticOcrEngine("Clear delivery text"),
        settings=TextPixelRuntimeSettings(enabled=True, allow_development_fonts=True),
        compositor=compositor,
    )
    delivery = runtime.deliver(
        plan=_plan(color="#777777"),
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
    )

    assert delivery.status == "repair_exhausted"
    assert compositor.calls == [False, True]
    assert delivery.recovery["generation_retry"]["eligible"] is True
    assert delivery.recovery["generation_retry"]["reason_codes"] == ["text_background_readability_failure"]
    assert [attempt.stage for attempt in delivery.attempts] == [
        "composition",
        "review",
        "deterministic_repair",
        "review",
        "generation_retry_signal",
    ]


def test_failed_retry_preserves_prior_text_delivery_and_appends_attempts() -> None:
    service = object.__new__(V3ProductApiService)
    base = SimpleNamespace(
        metadata={
            "text_pixel_delivery": {
                "status": "passed",
                "source_output_id": "base_source",
                "current_output_id": "base_delivery",
                "attempts": [{"attempt_id": "base", "stage": "review"}],
                "metadata": {"append_only": True},
            }
        }
    )
    retry = SimpleNamespace(
        metadata={
            "text_pixel_delivery": {
                "status": "repair_exhausted",
                "source_output_id": "retry_source",
                "current_output_id": "retry_failed_output",
                "attempts": [{"attempt_id": "retry", "stage": "deterministic_repair"}],
                "metadata": {"append_only": True},
            }
        }
    )

    merged = service._merge_text_pixel_delivery_chain(base, retry)

    assert merged["status"] == "passed"
    assert merged["current_output_id"] == "base_delivery"
    assert [item["attempt_id"] for item in merged["attempts"]] == ["base", "retry"]
    assert merged["recovery"]["retry_delivery_preserved_previous"] is True


@pytest.mark.parametrize("locale", ["zh-CN", "ru-RU"])
def test_unavailable_locale_font_blocks_without_substitution(tmp_path, locale: str) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    source = _base_output(store)
    delivery = _runtime(store, StaticOcrEngine("approved"), font=_font(locales=("en-US",))).deliver(
        plan=_plan(copy="approved", locale=locale),
        frozen_activation_plan=_frozen_plan(),
        source_output=source,
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
    )

    assert delivery.status == "blocked"
    assert "font_unavailable" in delivery.issue_codes
    assert delivery.rendered is False


def test_opaque_marker_activates_specialized_job_before_later_plan_binding(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.delenv("V3_TEXT_PIXEL_DELIVERY_ENABLED", raising=False)
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create one specialized product visual with an approved headline.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "platform_profile": "amazon_us",
                "parameters": {"requested_image_count": 1, "suite_slot_request": ["feature"]},
            },
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Adjustable shade"]},
            "metadata": {
                "template_id": "ecommerce_template",
                "requested_image_count": 1,
                "internal_copy_render_plan_present": True,
            },
        }
    )
    record = service.get_job_record(created.job_id)

    assert record is not None
    frozen = record.request.metadata["capability_activation_plan"]
    assert "text_pixel_delivery" in frozen["dependency_order"]
    asset_id = record.planning_result.series_plan.assets[0].asset_id
    record.request.metadata["text_pixel_delivery_internal"] = {
        "copy_render_plan": _plan(source_asset_id=asset_id, activation_plan_id=None).model_dump(mode="json")
    }
    service._bind_internal_copy_render_plan(record.request)
    bound = record.request.metadata["text_pixel_delivery_internal"]["copy_render_plan"]
    assert bound["source_lineage"]["capability_activation_plan_id"] == record.request.metadata["capability_activation_plan_id"]

    generated = service.generate_job(created.job_id)
    assert generated.metadata["text_pixel_delivery"]["status"] == "planned_only"
    assert generated.metadata["text_pixel_delivery"]["rendered"] is False


def test_shared_multi_plan_batch_binds_reviews_and_resolves_each_source_asset(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    source_a = _base_output(store, candidate_id="candidate_a", asset_id="asset_a")
    source_b = _base_output(store, color="#e8e8e8", candidate_id="candidate_b", asset_id="asset_b")
    plan_batch = CopyRenderPlanBatch(
        plans=[
            _plan(source_asset_id="asset_a"),
            _plan(source_asset_id="asset_b"),
        ]
    ).bind_to_frozen_plan("frozen_text_plan")
    runtime = _runtime(store, StaticOcrEngine("Clear delivery text"))

    delivery_batch = runtime.deliver_many(
        plans=plan_batch,
        frozen_activation_plan=_frozen_plan(),
        source_outputs_by_plan={
            plan_batch.plans[0].plan_id: source_a,
            plan_batch.plans[1].plan_id: source_b,
        },
        candidate_ids_by_plan={
            plan_batch.plans[0].plan_id: "candidate_a",
            plan_batch.plans[1].plan_id: "candidate_b",
        },
        asset_ids_by_plan={
            plan_batch.plans[0].plan_id: "asset_a",
            plan_batch.plans[1].plan_id: "asset_b",
        },
    )

    assert [delivery.status for delivery in delivery_batch.deliveries] == ["passed", "passed"]
    assert delivery_batch.source_asset_ids_by_plan == {
        plan_batch.plans[0].plan_id: "asset_a",
        plan_batch.plans[1].plan_id: "asset_b",
    }
    assert delivery_batch.delivery_for_source_asset("asset_a").current_output_id != source_a.output_id
    assert delivery_batch.delivery_for_source_asset("asset_b").current_output_id != source_b.output_id


def test_product_api_multi_plan_delivery_resolves_current_status_per_generated_asset(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.delenv("V3_TEXT_PIXEL_DELIVERY_ENABLED", raising=False)
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create two specialized product visuals with approved copy intent.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "platform_profile": "amazon_us",
                "parameters": {"requested_image_count": 2, "suite_slot_request": ["feature_a", "feature_b"]},
            },
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Adjustable shade"]},
            "metadata": {
                "template_id": "ecommerce_template",
                "requested_image_count": 2,
                "internal_copy_render_plan_present": True,
            },
        }
    )
    record = service.get_job_record(created.job_id)

    assert record is not None
    asset_ids = [asset.asset_id for asset in record.planning_result.series_plan.assets]
    assert len(asset_ids) == 2
    record.request.metadata["text_pixel_delivery_internal"] = {
        "copy_render_plans": [
            _plan(source_asset_id=asset_ids[0], activation_plan_id=None).model_dump(mode="json"),
            _plan(source_asset_id=asset_ids[1], activation_plan_id=None).model_dump(mode="json"),
        ]
    }
    service._bind_internal_copy_render_plan(record.request)
    bound_plans = record.request.metadata["text_pixel_delivery_internal"]["copy_render_plans"]
    assert [plan["source_lineage"]["capability_activation_plan_id"] for plan in bound_plans] == [
        record.request.metadata["capability_activation_plan_id"],
        record.request.metadata["capability_activation_plan_id"],
    ]

    generated = service.generate_job(created.job_id)
    batch = generated.metadata["text_pixel_delivery_batch"]
    assert [delivery["status"] for delivery in batch["deliveries"]] == ["planned_only", "planned_only"]
    assert record.generation_result is not None
    asset_deliveries = {
        asset.asset_id: asset.metadata["text_pixel_delivery"]
        for asset in record.generation_result.asset_pack.assets
        if "text_pixel_delivery" in asset.metadata
    }
    assert set(asset_deliveries) == set(asset_ids)
    assert all(delivery["status"] == "planned_only" for delivery in asset_deliveries.values())


def test_invalid_multi_plan_keeps_the_public_batch_result_shape(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.delenv("V3_TEXT_PIXEL_DELIVERY_ENABLED", raising=False)
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create one specialized product visual with approved copy intent.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "platform_profile": "amazon_us",
                "parameters": {"requested_image_count": 1, "suite_slot_request": ["feature"]},
            },
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Adjustable shade"]},
            "metadata": {
                "template_id": "ecommerce_template",
                "requested_image_count": 1,
                "internal_copy_render_plan_present": True,
            },
        }
    )
    record = service.get_job_record(created.job_id)

    assert record is not None
    record.request.metadata["text_pixel_delivery_internal"] = {"copy_render_plans": []}
    service._bind_internal_copy_render_plan(record.request)

    generated = service.generate_job(created.job_id)
    batch = generated.metadata["text_pixel_delivery_batch"]
    assert batch["schema_version"] == "v3_text_pixel_delivery_batch_v1"
    assert batch["metadata"]["invalid_batch"] is True
    assert len(batch["deliveries"]) == 1
    assert batch["deliveries"][0]["status"] == "blocked"
    assert batch["deliveries"][0]["issue_codes"] == ["copy_render_plan_batch_invalid"]


def test_multi_plan_batch_rejects_duplicate_source_lineage() -> None:
    with pytest.raises(ValueError, match="unique source asset/output lineage"):
        CopyRenderPlanBatch(
            plans=[
                _plan(source_asset_id="same_asset"),
                _plan(source_asset_id="same_asset", copy="A distinct plan with the same source"),
            ]
        )


def test_multi_plan_retry_history_remains_append_only_per_plan() -> None:
    service = object.__new__(V3ProductApiService)
    base = SimpleNamespace(
        metadata={
            "text_pixel_delivery_batch": {
                "batch_id": "batch_1",
                "deliveries": [
                    {"copy_render_plan_id": "plan_a", "status": "passed", "current_output_id": "delivery_a", "attempts": [{"attempt_id": "base_a"}]},
                    {"copy_render_plan_id": "plan_b", "status": "repair_exhausted", "current_output_id": "delivery_b", "attempts": [{"attempt_id": "base_b"}]},
                ],
                "source_asset_ids_by_plan": {"plan_a": "asset_a", "plan_b": "asset_b"},
            }
        }
    )
    retry = SimpleNamespace(
        metadata={
            "text_pixel_delivery_batch": {
                "batch_id": "batch_1",
                "deliveries": [
                    {"copy_render_plan_id": "plan_a", "status": "repair_exhausted", "current_output_id": "retry_a", "attempts": [{"attempt_id": "retry_a"}]},
                    {"copy_render_plan_id": "plan_b", "status": "passed", "current_output_id": "retry_b", "attempts": [{"attempt_id": "retry_b"}]},
                ],
                "source_asset_ids_by_plan": {"plan_a": "asset_a", "plan_b": "asset_b"},
            }
        }
    )

    merged = service._merge_text_pixel_delivery_chain(base, retry)
    deliveries = {item["copy_render_plan_id"]: item for item in merged["deliveries"]}

    assert deliveries["plan_a"]["current_output_id"] == "delivery_a"
    assert deliveries["plan_b"]["current_output_id"] == "retry_b"
    assert [item["attempt_id"] for item in deliveries["plan_a"]["attempts"]] == ["base_a", "retry_a"]
    assert [item["attempt_id"] for item in deliveries["plan_b"]["attempts"]] == ["base_b", "retry_b"]
