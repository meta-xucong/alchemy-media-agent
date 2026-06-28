import json

from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas import BrandProfile, IndustryCategory


def _service(tmp_path) -> V3ProductApiService:
    brand_service = BrandProfileService(BrandProfileStore(tmp_path / "brand_memory"))
    return V3ProductApiService(brand_profile_service=brand_service)


def _summary_text(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False).lower()


def test_general_creative_preset_exposes_product_language_visual_grammar_summary(tmp_path) -> None:
    service = _service(tmp_path)

    created = service.create_job(
        {
            "user_input": "Create a bright launch poster for a tea shop.",
            "scenario_selection": {"scenario_id": "general_creative", "preset_id": "campaign_poster"},
        }
    )

    assert created.status == ProductJobStatusValue.PLANNED
    assert created.general_creative is not None
    assert created.general_creative.enabled is True
    assert created.general_creative.selected_preset_id == "campaign_poster"
    assert created.general_creative.visual_grammar
    assert any(check["id"] == "visual_grammar" and check["status"] == "done" for check in created.general_creative.closure_checks)

    public_summary = created.general_creative.model_dump(mode="json")
    text = _summary_text(public_summary)
    assert "asset_role_analyzer" not in text
    assert "visual_grammar_lock" not in text
    assert "prompt_constraint_compiler" not in text
    assert "amazon" not in text
    assert "marketplace" not in text
    assert "seo" not in text
    assert "competitor" not in text


def test_general_creative_summarizes_reference_binding_and_fact_preservation(tmp_path) -> None:
    service = _service(tmp_path)

    created = service.create_job(
        {
            "user_input": "Create a clean product-style hero visual, keep the supplied launch text.",
            "scenario_selection": {"scenario_id": "general_creative", "preset_id": "product_style_hero"},
            "uploaded_asset_ids": ["front_product_reference"],
            "product_profile": {
                "required_text": ["Summer Launch"],
                "facts": ["matte green bottle"],
                "claims": ["100% guaranteed result"],
            },
        }
    )

    assert created.status == ProductJobStatusValue.PLANNED
    assert created.scenario is not None
    assert created.scenario.selected_preset_id == "product_style_hero"
    summary = created.general_creative
    assert summary is not None
    assert summary.reference_understanding
    assert summary.reference_bindings
    assert any("Summer Launch" in item for item in summary.information_integrity)
    assert any("matte green bottle" in item for item in summary.information_integrity)
    assert any("100% guaranteed result" in item for item in summary.information_integrity)
    assert any("Claim requires evidence" in item for item in summary.warnings)
    assert any(check["id"] == "reference_understanding" and check["status"] in {"done", "attention"} for check in summary.closure_checks)
    assert any(check["id"] == "information_integrity" and check["status"] == "attention" for check in summary.closure_checks)


def test_general_creative_history_continuation_is_brand_scoped(tmp_path) -> None:
    brand_service = BrandProfileService(BrandProfileStore(tmp_path / "brand_memory"))
    brand_service.save_profile(
        BrandProfile(
            brand_id="brand_doc25",
            brand_name="Doc25 Tea",
            industry=IndustryCategory.BEVERAGE,
            visual_tone=["fresh", "minimal"],
            rejected_style_tags=["dark clutter"],
            successful_asset_ids=["asset_previous"],
        )
    )
    service = V3ProductApiService(brand_profile_service=brand_service)

    created = service.create_job(
        {
            "user_input": "Continue the prior fresh style for a social cover.",
            "continue_style_from_brand_id": "brand_doc25",
            "scenario_selection": {"scenario_id": "general_creative", "preset_id": "social_cover"},
        }
    )

    summary = created.general_creative
    assert summary is not None
    assert summary.history_continuation
    assert any("brand_doc25" in item for item in summary.history_continuation)
    assert any("fresh" in item for item in summary.history_continuation)
    assert any("dark clutter" in item for item in summary.history_continuation)
    assert any(check["id"] == "history_continuation" and check["status"] == "done" for check in summary.closure_checks)


def test_general_creative_summary_is_not_used_for_active_ecommerce(tmp_path) -> None:
    service = _service(tmp_path)

    ecommerce = service.create_job(
        {
            "user_input": "Create an e-commerce listing set.",
            "scenario_selection": {"scenario_id": "ecommerce"},
        }
    )

    assert ecommerce.status == ProductJobStatusValue.PLANNED
    assert ecommerce.general_creative is None
    assert ecommerce.ecommerce is not None
