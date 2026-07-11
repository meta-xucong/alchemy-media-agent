from pathlib import Path

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"


def test_project_mode_ecommerce_summary_exposes_publish_checks_for_workspace_consumption() -> None:
    status = V3ProductApiService().create_job(
        {
            "user_input": "Create two Ozon listing images for this bottled tea",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "platform_profile": "ozon",
                "parameters": {"requested_image_count": 2},
            },
            "uploaded_asset_ids": ["tea_front"],
            "product_profile": {
                "product_category": "drink",
                "selling_points": ["Fresh summer refreshment"],
            },
        }
    )

    assert status.ecommerce is not None
    export_metadata = status.ecommerce.export_package["metadata"]
    assert export_metadata["publish_checks"]
    assert export_metadata["marketplace_profile_id"] == "ecommerce_ozon_ru"
    assert export_metadata["copy_locale"] == "ru-RU"


def test_ecommerce_workspace_renders_export_preparation_and_supported_platforms() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'option value="ozon"' in html
    assert 'option value="pinduoduo"' in html
    assert "function renderV3EcommerceExportList(summary)" in script
    assert "metadata.publish_checks" in script
    assert "导出准备" in script
    assert "发布前检查" in script
    assert "category_evidence_targets" in script
    assert 'confirmed_style_chips: project.confirmed_style_summary' in script
    assert 'v3TemplatePlainLabel(project.primary_template_id || "general_template")' in script


def test_ecommerce_workspace_exposes_category_choice_to_the_existing_profile_patch() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="v3EcommerceCategoryInput"' in html
    assert 'option value="electronics"' in html
    assert 'option value="food_beverage"' in html
    assert 'v3EcommerceCategoryInput: document.querySelector("#v3EcommerceCategoryInput")' in script
    assert 'product_category: (els.v3EcommerceCategoryInput?.value || "").trim() || null' in script
    assert 'els.v3EcommerceCategoryInput.value = ""' in script
