import base64
from io import BytesIO
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "262_V3_ECOMMERCE_PRODUCT_REFERENCE_DEDUP_AND_CONTINUATION_CONTRACT.md"
DESKTOP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE_JS = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"


def _png_base64(color: tuple[int, int, int] = (212, 220, 230)) -> str:
    image = Image.new("RGB", (16, 16), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _function(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


def _ready_upload(handlers, tmp_path, *, filename: str, content: str | None = None) -> str:
    handlers.service.asset_store.storage_root = tmp_path / "v3_uploads"
    created = handlers.post_uploads(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": 256,
            "role": "product_reference",
        }
    )
    handlers.put_upload_content(
        created["asset_id"],
        {"content_base64": content or _png_base64(), "mime_type": "image/png"},
    )
    ready = handlers.post_upload_complete(created["asset_id"])
    assert ready["status"] == "ready"
    assert ready["content_sha256"]
    return created["asset_id"]


def _active_product_references(project: dict) -> list[dict]:
    return [
        item
        for item in project.get("reference_assets", [])
        if item.get("status") == "active"
        and item.get("source_type") == "uploaded"
        and item.get("use_policy") == "product"
    ]


def test_doc262_records_content_digest_authority_and_non_destructive_repair() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "product truth by image content" in text
    assert "content_sha256" in text
    assert "soft-suppressed" in text
    assert "Do not delete upload directories" in text


def test_doc262_desktop_and_mobile_clear_consumed_pending_uploads() -> None:
    desktop = DESKTOP_JS.read_text(encoding="utf-8")
    mobile = MOBILE_JS.read_text(encoding="utf-8")
    desktop_clear = _function(desktop, "clearV3PendingUploads", "handleV3ScenarioClick")
    desktop_open = _function(desktop, "openV3Project", "renderV3ProjectOpeningState")
    desktop_create = _function(desktop, "createV3Job", "completeV3GeneratedJob")
    mobile_clear = _function(mobile, "clearMobileV3PendingUploads", "handleMobileV3ReferenceFiles")
    mobile_open = _function(mobile, "openMobileV3ProjectDetail", "refreshMobileV3ProjectDetail")
    mobile_generate = _function(mobile, "generateMobileV3Job", "recoverMobileV3GeneratedJob")

    assert "v3State.files = []" in desktop_clear
    assert "v3State.uploadedAssets = []" in desktop_clear
    assert "clearV3PendingUploads({ render: true })" in desktop_open
    assert "clearV3PendingUploads({ render: true })" in desktop_create
    assert 'item?.status !== "inactive"' in desktop
    assert '"product_reference"' in desktop
    assert "mobileV3State.files = []" in mobile_clear
    assert "mobileV3State.uploadedAssets = []" in mobile_clear
    assert "clearMobileV3PendingUploads({ render: true })" in mobile_open
    assert "clearMobileV3PendingUploads({ render: true })" in mobile_generate


def test_ecommerce_saved_product_reference_reuses_existing_content_digest(tmp_path) -> None:
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service

    handlers = V3ProductRouteHandlers(service=ecommerce_test_service())
    same_product = _png_base64((200, 190, 170))
    original_id = _ready_upload(handlers, tmp_path, filename="swimwear-original.png", content=same_product)
    duplicate_id = _ready_upload(handlers, tmp_path, filename="swimwear-duplicate.png", content=same_product)
    project = handlers.post_projects(
        {
            "user_goal": "Create ecommerce images for the uploaded swimwear.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]

    first = handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": original_id, "source_type": "uploaded", "use_policy": "product"},
    )
    second = handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": duplicate_id, "source_type": "uploaded", "use_policy": "product"},
    )
    loaded = handlers.get_project(project["project_id"])
    context = loaded["context"]
    active_products = _active_product_references(loaded["project"])

    assert first["reference"]["asset_ref_id"] == original_id
    assert second["reference"]["asset_ref_id"] == original_id
    assert [item["asset_ref_id"] for item in active_products] == [original_id]
    assert [item["asset_ref_id"] for item in context["uploaded_reference_assets"]] == [original_id]
    assert context["uploaded_reference_assets"][0]["content_sha256"]


def test_ecommerce_duplicate_reference_reuses_legacy_project_create_source(tmp_path) -> None:
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service

    handlers = V3ProductRouteHandlers(service=ecommerce_test_service())
    same_product = _png_base64((170, 210, 190))
    original_id = _ready_upload(handlers, tmp_path, filename="original-create-source.png", content=same_product)
    duplicate_id = _ready_upload(handlers, tmp_path, filename="duplicate-later-source.png", content=same_product)
    project = handlers.post_projects(
        {
            "user_goal": "Create ecommerce images for the uploaded product.",
            "primary_template_id": "ecommerce_template",
            "uploaded_asset_ids": [original_id],
        }
    )["project"]

    saved = handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": duplicate_id, "source_type": "uploaded", "use_policy": "product"},
    )
    loaded = handlers.get_project(project["project_id"])

    assert saved["reference"]["asset_ref_id"] == original_id
    assert [item["asset_ref_id"] for item in _active_product_references(loaded["project"])] == [original_id]
    assert [item["asset_ref_id"] for item in loaded["context"]["uploaded_reference_assets"]] == [original_id]


def test_ecommerce_job_product_truth_pool_dedupes_reuploaded_same_bytes(tmp_path) -> None:
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service

    handlers = V3ProductRouteHandlers(service=ecommerce_test_service())
    same_product = _png_base64((120, 150, 210))
    original_id = _ready_upload(handlers, tmp_path, filename="product-view-a.png", content=same_product)
    duplicate_id = _ready_upload(handlers, tmp_path, filename="product-view-a-copy.png", content=same_product)
    project = handlers.post_projects(
        {
            "user_goal": "Create a product launch image suite.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Continue with a sunny ecommerce product image.",
            "uploaded_asset_ids": [original_id, duplicate_id],
        },
    )
    loaded = handlers.get_project(project["project_id"])

    assert job["status"] == "planned"
    assert job["ecommerce"]["product_truth"]["evidence_sources"] == [f"uploaded_asset:{original_id}"]
    assert job["metadata"]["project_context_snapshot"]["uploaded_reference_assets"][0]["asset_ref_id"] == original_id
    assert [item["asset_ref_id"] for item in _active_product_references(loaded["project"])] == [original_id]
