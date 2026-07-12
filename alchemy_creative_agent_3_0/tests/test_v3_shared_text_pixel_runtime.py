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


def _base_output(store: V3GeneratedOutputStore, color: str = "#e7e7e7"):
    image = Image.new("RGB", (800, 600), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return store.save_base64_output(
        job_id="text_pixel_job",
        candidate_id="text_pixel_candidate",
        asset_id="text_pixel_asset",
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


def _plan(*, policy: str = "required", copy: str | None = "Clear delivery text", locale: str = "en-US", color: str | None = None) -> CopyRenderPlan:
    return CopyRenderPlan(
        expected_copy=copy,
        locale=locale,
        text_policy=policy,
        normalized_safe_area=NormalizedSafeArea(x=0.1, y=0.1, w=0.8, h=0.3),
        layout_priority="headline",
        foreground_color=color,
        source_lineage=CopyRenderSourceLineage(
            capability_activation_plan_id="frozen_text_plan",
            source_job_id="text_pixel_job",
            source_asset_id="text_pixel_asset",
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
