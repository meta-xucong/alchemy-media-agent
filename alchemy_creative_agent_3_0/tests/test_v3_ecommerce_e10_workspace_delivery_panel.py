from pathlib import Path

from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"


def test_project_mode_ecommerce_summary_exposes_factual_export_checks_not_planned_slots() -> None:
    status = ecommerce_test_service().create_job(
        {
            "user_input": "Create two Ozon listing images for this bottled tea",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "ozon", "parameters": {"requested_image_count": 2}},
            "uploaded_asset_ids": ["tea_front"],
            "product_profile": {"product_category": "drink"},
        }
    )
    assert status.ecommerce is not None
    export_metadata = status.ecommerce.export_package["metadata"]
    assert export_metadata["publish_checks"]
    assert export_metadata["marketplace_profile_id"] == "ecommerce_ozon_ru"
    assert export_metadata["copy_locale"] == "ru-RU"
    assert status.ecommerce.image_recipes == []
    assert len(status.ecommerce.remote_brain_output_intents) == 2


def test_ecommerce_workspace_collects_facts_and_approved_copy_without_fixed_suite_controls() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'option value="ozon"' in html
    assert 'option value="pinduoduo"' in html
    assert 'id="v3EcommerceCategoryInput"' in html
    assert 'id="v3EcommerceApprovedCopyInput"' in html
    assert 'id="v3EcommerceSuiteScopeInput"' not in html
    assert 'id="v3EcommerceOverlayCopyInput"' not in html
    assert 'v3EcommerceApprovedCopyInput: document.querySelector("#v3EcommerceApprovedCopyInput")' in script
    assert 'approved_literal_copy: approvedLiteralCopy || null' in script
    assert 'suite_slots_requested:' not in script
    assert 'suite_slot_request' not in script
    assert 'overlay_copy' not in script
    assert 'renderV3EcommerceSuiteScopeHint' not in script


def test_ecommerce_workspace_renders_remote_output_intents_and_opaque_delivery_ids() -> None:
    script = APP_JS.read_text(encoding="utf-8")

    assert "function renderV3EcommercePlanList(summary)" in script
    assert "remote_brain_output_intents" in script
    assert "function v3EcommerceOutputLabel(outputId, fallbackIndex)" in script
    assert "ecommerce_output_(\\d+)" in script
    assert "function renderV3EcommerceExportList(summary)" in script
    assert "provider_native_complete_image" in script
    assert "v3EcommerceSlotLabel" not in script
    assert "v3EcommerceRecipeForItem" not in script


def test_ecommerce_workspace_explains_fail_closed_recovery_and_production_gate() -> None:
    script = APP_JS.read_text(encoding="utf-8")

    assert "function v3EcommerceFailureMessage(job)" in script
    assert "ecommerce_runtime_provenance" in script
    assert "requested_image_count_not_supported_by_declared_contract" in script
    assert "remote_creative_brain_image_set_plan_invalid" in script
    assert "production_ready" in script
    assert "renderV3EcommerceSummary(job?.ecommerce || null, job?.metadata, job)" in script
