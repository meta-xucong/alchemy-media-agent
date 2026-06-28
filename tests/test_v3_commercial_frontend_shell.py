import base64
from io import BytesIO
import json

from fastapi.testclient import TestClient

from alchemy_creative_agent_3_0.app.product_api import V3GeneratedOutputStore, V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.service import InMemoryProductJobStore
from app import main as app_main
from app.main import app, v3_route_handlers


def _png_base64(width: int = 320, height: int = 280) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(220, 224, 230))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_v3_commercial_shell_is_in_desktop_product_navigation() -> None:
    client = TestClient(app)

    index = client.get("/")
    assert index.status_code == 200
    assert 'data-tab="v3"' in index.text
    assert "生图 V3.0 特调 Agent" in index.text
    assert 'id="v3Tab"' in index.text
    assert 'id="v3HomeView"' in index.text
    assert 'id="v3WorkspaceView" class="v3-workspace-view" hidden' in index.text
    assert 'id="v3ScenarioGrid"' in index.text
    assert 'id="v3HistoryList"' in index.text
    assert "选择你要做的图" in index.text
    assert "上传商品图，一键生成套图" in index.text
    assert 'data-v3-placeholder="true"' in index.text
    assert "返回 V3 首页" in index.text
    assert "生成创意图" in index.text
    assert "重新生成创意图" in index.text
    assert "v3ClosureList" in index.text
    assert "v3WarningList" in index.text
    assert "v3GeneralPresetRow" in index.text
    assert "v3EcommercePresetRow" in index.text
    assert "v3EcommerceAdvanced" in index.text
    assert "v3EcommerceFields" in index.text
    assert "one_click_product_set" in index.text
    assert "这次 V3 帮你完成了" in index.text
    assert "生成后的图片会显示在这里" in index.text
    assert "V3 理解结果" not in index.text
    assert "Truth:" not in index.text
    assert "Selling point:" not in index.text

    v3_section = index.text[index.text.find('id="v3Tab"') : index.text.find('id="videoTab"')]
    assert "Provider" not in v3_section
    assert "Seed" not in v3_section
    assert "ControlNet" not in v3_section
    assert "ComfyUI" not in v3_section
    assert "IP-Adapter" not in v3_section

    v3_page = client.get("/creative-agent-v3/ecommerce")
    assert v3_page.status_code == 200
    assert v3_page.headers["cache-control"] == "no-store"
    assert 'id="v3Tab"' in v3_page.text

    h5 = client.get("/h5")
    assert h5.status_code == 200
    assert 'href="/creative-agent-v3"' in h5.text
    assert "v3-link-tab" in h5.text


def test_v3_frontend_assets_use_v3_namespace_and_card_module_styles() -> None:
    client = TestClient(app)

    styles = client.get("/static/styles.css")
    mobile_styles = client.get("/mobile-static/mobile.css")
    script = client.get("/static/app.js")

    assert styles.status_code == 200
    assert ".v3-scenario-grid" in styles.text
    assert ".v3-scenario-card" in styles.text
    assert ".v3-home-view" in styles.text
    assert ".v3-history-list" in styles.text
    assert ".v3-history-card" in styles.text
    assert ".v3-workspace-grid" in styles.text
    assert ".v3-result-board" in styles.text
    assert ".v3-result-preview" in styles.text
    assert ".v3-preset-row[hidden]" in styles.text
    assert ".v3-optional-details" in styles.text
    assert "grid-template-columns: repeat(5, minmax(150px, 1fr))" in styles.text
    assert mobile_styles.status_code == 200
    assert ".tab.v3-link-tab" in mobile_styles.text

    assert script.status_code == 200
    assert "const v3ApiBase" in script.text
    assert "const v3HistoryStorageKey" in script.text
    assert "/api/v3/creative-agent" in script.text
    assert "/history?limit=24" in script.text
    assert "function openV3Home" in script.text
    assert "function openV3ScenarioWorkspace" in script.text
    assert "function loadV3History" in script.text
    assert "function renderV3History" in script.text
    assert "function buildV3JobPayload" in script.text
    assert "async function uploadV3Files" in script.text
    assert "uploadedAssets.map((asset) => asset.asset_id)" in script.text
    assert "/uploads" in script.text
    assert "function renderV3GeneralSummary" in script.text
    assert "function renderV3EcommerceSummary" in script.text
    assert "function v3ScenarioWorkspaceCopy" in script.text
    assert "function renderV3OutcomeItems" in script.text
    assert "function v3PlainWarningText" in script.text
    assert "生成电商套图" in script.text
    assert "适合商品主图、卖点图、详情页配图" in script.text
    assert "function renderV3ClosureChecks" in script.text
    assert "require_real_images: true" in script.text
    assert "function v3OutputImageCandidates" in script.text
    assert "function v3MediaUrl" in script.text
    assert "asset_series: Array.isArray(job.asset_series)" in script.text
    assert "candidates: Array.isArray(job.candidates)" in script.text
    assert "function v3JobFromHistorySnapshot" in script.text
    assert "function v3MergeHistorySnapshotIntoJob" in script.text
    assert "已从本地历史快照恢复生成图片" in script.text
    assert "v3-result-preview" in script.text
    assert "scenario_id: v3State.selectedScenario" in script.text
    assert "frontend_reference_" not in script.text
    assert "v3SafeAssetToken" not in script.text
    assert "v3Placeholder" in script.text
    assert "Product truth lock" not in script.text
    assert "Selling point:" not in script.text
    assert "Truth:" not in script.text
    switch_v3_block = script.text[script.text.find('} else if (tabName === "v3")') : script.text.find('} else if (tabName === "account")')]
    assert "state.historyItems" not in switch_v3_block
    assert 'renderHeroHistory([], { source: "v3" })' in switch_v3_block
    v3_block = script.text[script.text.find("async function initV3Shell") : script.text.find("function setLabStyleLibraryOpen")]
    assert "/api/v2" not in v3_block
    assert "/api/lab" not in v3_block
    assert "seed" not in v3_block.lower()
    assert "sampler" not in v3_block.lower()
    assert "controlnet" not in v3_block.lower()


def test_v3_product_api_routes_are_mounted_for_frontend_shell() -> None:
    client = TestClient(app)

    scenarios = client.get("/api/v3/creative-agent/scenarios")
    assert scenarios.status_code == 200
    scenario_payload = scenarios.json()
    assert scenario_payload["default_scenario_id"] == "general_creative"
    assert "general_creative" in scenario_payload["active_scenario_ids"]
    assert "ecommerce" in scenario_payload["active_scenario_ids"]
    assert "ecommerce" not in scenario_payload["placeholder_scenario_ids"]

    empty_history = client.get("/api/v3/creative-agent/history")
    assert empty_history.status_code == 200
    assert empty_history.json()["api_namespace"] == "/api/v3/creative-agent"

    created = client.post(
        "/api/v3/creative-agent/jobs",
        json={
            "user_input": "帮我做一组清爽高级的夏季饮料宣传图，适合社媒封面和店铺活动页",
            "scenario_selection": {"scenario_id": "general_creative", "preset_id": "campaign_poster"},
            "product_profile": {"brand_or_project_name": "Mint Lab"},
        },
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["status"] == "planned"
    assert created_payload["api_namespace"] == "/api/v3/creative-agent"
    assert created_payload["scenario"]["scenario_id"] == "general_creative"
    assert created_payload["general_creative"]["scenario_id"] == "general_creative"
    assert created_payload["general_creative"]["closure_checks"]
    summary_text = json.dumps(created_payload["general_creative"], ensure_ascii=False).lower()
    assert "asset_role_analyzer" not in summary_text
    assert "visual_grammar_lock" not in summary_text
    assert "amazon" not in summary_text
    assert "marketplace" not in summary_text

    history = client.get("/api/v3/creative-agent/history?limit=5")
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["route"] == "/api/v3/creative-agent/history"
    assert history_payload["items"][0]["job_id"] == created_payload["job_id"]
    assert history_payload["items"][0]["scenario_id"] == "general_creative"
    assert history_payload["items"][0]["metadata"]["imports_v1_v2_runtime"] is False

    generated = client.post(f"/api/v3/creative-agent/jobs/{created_payload['job_id']}/generate", json={"quality_mode": "standard"})
    assert generated.status_code == 200
    generated_payload = generated.json()
    assert generated_payload["status"] == "generated"
    assert generated_payload["asset_series"]

    selected = client.post(f"/api/v3/creative-agent/jobs/{created_payload['job_id']}/select", json={"apply_memory_update": True})
    assert selected.status_code == 200
    assert selected.json()["status"] == "selected"


def test_v3_routes_reject_low_level_controls_and_run_ecommerce_pack() -> None:
    client = TestClient(app)

    low_level = client.post(
        "/api/v3/creative-agent/jobs",
        json={"user_input": "做一张活动图", "metadata": {"seed": 123}},
    )
    assert low_level.status_code == 400
    assert low_level.json()["detail"]["code"] == "invalid_v3_request"

    ecommerce = client.post(
        "/api/v3/creative-agent/jobs",
        json={
            "user_input": "传一张产品图，生成可直接用于电商的成熟套图",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "amazon_us"},
            "uploaded_asset_ids": ["product_reference"],
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Adjustable angle"]},
        },
    )
    assert ecommerce.status_code == 200
    ecommerce_payload = ecommerce.json()
    assert ecommerce_payload["status"] == "planned"
    assert ecommerce_payload["scenario"]["scenario_id"] == "ecommerce"
    assert ecommerce_payload["scenario"]["can_create_jobs"] is True
    assert ecommerce_payload["ecommerce"]["platform"] == "amazon"
    assert ecommerce_payload["ecommerce"]["image_recipes"]
    assert ecommerce_payload["ecommerce"]["export_package"]["files"]


def test_v3_upload_routes_feed_ecommerce_export_manifest(tmp_path) -> None:
    v3_route_handlers.service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads")
    v3_route_handlers.service.job_store = InMemoryProductJobStore()
    client = TestClient(app)

    created_upload = client.post(
        "/api/v3/creative-agent/uploads",
        json={"filename": "desk-lamp.png", "mime_type": "image/png", "size_bytes": 1024, "role": "product_reference"},
    )
    assert created_upload.status_code == 200
    upload_payload = created_upload.json()
    assert upload_payload["asset_id"].startswith("v3_asset_")
    assert upload_payload["upload_url"].endswith("/content")

    stored_upload = client.put(
        upload_payload["upload_url"],
        json={"content_base64": _png_base64(), "mime_type": "image/png"},
    )
    assert stored_upload.status_code == 200
    assert stored_upload.json()["status"] == "stored"

    ready_upload = client.post(f"/api/v3/creative-agent/uploads/{upload_payload['asset_id']}/complete")
    assert ready_upload.status_code == 200
    assert ready_upload.json()["status"] == "ready"

    image_content = client.get(f"/api/v3/creative-agent/uploads/{upload_payload['asset_id']}/content")
    assert image_content.status_code == 200
    assert image_content.headers["content-type"] == "image/png"

    created_job = client.post(
        "/api/v3/creative-agent/jobs",
        json={
            "user_input": "Create a direct-to-use ecommerce image set for this desk lamp",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "amazon_us"},
            "uploaded_asset_ids": [upload_payload["asset_id"]],
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Adjustable angle"]},
        },
    )
    assert created_job.status_code == 200
    job_payload = created_job.json()
    assert job_payload["ecommerce"]["product_truth"]["evidence_sources"] == [f"uploaded_asset:{upload_payload['asset_id']}"]

    export = client.get(f"/api/v3/creative-agent/jobs/{job_payload['job_id']}/export")
    assert export.status_code == 200
    export_payload = export.json()
    assert export_payload["package_id"]
    assert export_payload["manifest"]["uploaded_assets"][0]["stored"] is True

    download = client.get(f"/api/v3/creative-agent/jobs/{job_payload['job_id']}/export/download")
    assert download.status_code == 200
    assert download.headers["content-disposition"].endswith('.json"')
    manifest = download.json()
    assert manifest["source_asset_ids"] == [upload_payload["asset_id"]]


def test_v3_output_routes_serve_v3_owned_generated_files(tmp_path) -> None:
    old_store = app_main.v3_output_store
    store = V3GeneratedOutputStore(storage_root=tmp_path / "v3_outputs")
    app_main.v3_output_store = store
    client = TestClient(app)
    try:
        record = store.save_base64_output(
            job_id="job_route_output",
            candidate_id="candidate_route_output",
            asset_id="asset_route_output",
            provider="test_provider",
            model="test-model",
            encoded_image=_png_base64(),
            mime_type="image/png",
            output_format="png",
        )

        thumbnail = client.get(record.thumbnail_url)
        preview = client.get(record.preview_url)
        download = client.get(record.download_url)
    finally:
        app_main.v3_output_store = old_store

    assert thumbnail.status_code == 200
    assert thumbnail.headers["content-type"] == "image/png"
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
