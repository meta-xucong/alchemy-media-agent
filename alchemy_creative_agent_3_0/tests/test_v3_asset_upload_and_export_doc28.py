import base64
from io import BytesIO
import json

import pytest

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService, V3UploadedAssetStore
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


def _png_base64(width: int = 320, height: int = 280) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(210, 220, 232))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _webp_base64(width: int = 240, height: int = 260) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(224, 218, 206))
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=88)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _upload_ready_asset(store: V3UploadedAssetStore) -> str:
    created = store.create_upload(
        {
            "filename": "desk-lamp-product.png",
            "mime_type": "image/png",
            "size_bytes": 1024,
            "role": "product_reference",
        }
    )
    stored = store.store_content(created.asset_id, {"content_base64": _png_base64(), "mime_type": "image/png"})
    assert stored is not None
    ready = store.complete_upload(created.asset_id)
    assert ready is not None
    return ready.asset_id


def test_v3_uploaded_asset_store_lifecycle_resolves_runtime_asset(tmp_path) -> None:
    store = V3UploadedAssetStore(storage_root=tmp_path)
    asset_id = _upload_ready_asset(store)

    record = store.get_upload(asset_id)
    assert record is not None
    assert record.status == "ready"
    assert record.file_path

    content = store.read_content(asset_id)
    assert content is not None
    assert content[1] == "image/png"

    resolved = store.resolve_uploaded_assets([asset_id, asset_id, "legacy_reference_id"])
    assert len(resolved) == 2
    assert resolved[0].asset_id == asset_id
    assert resolved[0].file_path == record.file_path
    assert resolved[0].role == "product_reference"
    assert resolved[1].metadata["asset_lookup_status"] == "not_found"

    with pytest.raises(ValueError):
        store.create_upload({"filename": "notes.txt", "mime_type": "text/plain", "size_bytes": 10})


def test_v3_uploaded_asset_store_accepts_webp_reference(tmp_path) -> None:
    store = V3UploadedAssetStore(storage_root=tmp_path)
    payload = _webp_base64()
    created = store.create_upload(
        {
            "filename": "reference.webp",
            "mime_type": "image/webp",
            "size_bytes": len(base64.b64decode(payload)),
            "role": "style_reference",
        }
    )

    stored = store.store_content(created.asset_id, {"content_base64": payload, "mime_type": "image/webp"})
    assert stored is not None
    ready = store.complete_upload(created.asset_id)

    assert ready is not None
    assert ready.status == "ready"
    assert ready.mime_type == "image/webp"
    resolved = store.resolve_uploaded_assets([ready.asset_id])[0]
    assert resolved.file_path
    assert resolved.mime_type == "image/webp"


def test_product_api_uses_uploaded_asset_pixels_and_exports_manifest(tmp_path) -> None:
    store = V3UploadedAssetStore(storage_root=tmp_path)
    asset_id = _upload_ready_asset(store)
    service = ecommerce_test_service(asset_store=store)

    status = service.create_job(
        {
            "user_input": "Create a premium Amazon product image set for this desk lamp",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "amazon_us"},
            "uploaded_asset_ids": [asset_id],
            "product_profile": {
                "product_category": "desk lamp",
                "materials": ["aluminum body"],
                "selling_points": ["Adjustable angle", "Soft light"],
            },
        }
    )

    assert status.status == "planned"
    assert status.ecommerce is not None
    assert f"uploaded_asset:{asset_id}" in status.ecommerce.product_truth["evidence_sources"]

    shared = status.metadata["shared_capabilities"]
    role_result = next(result for result in shared["results"] if result["module_id"] == "asset_role_analyzer")
    analysis = role_result["facts"]["asset_analyses"][0]
    assert analysis["asset_id"] == asset_id
    assert analysis["stored"] is True
    assert analysis["width"] == 320
    assert analysis["height"] == 280

    export = service.export_job(status.job_id)
    assert export.status == "planned"
    assert export.package_id
    # Planning never invents export files from a static role map. Files appear
    # only after provider outputs exist.
    assert export.export_package["files"] == []
    assert export.manifest["uploaded_assets"][0]["stored"] is True
    assert export.manifest["metadata"]["imports_v1_v2_runtime"] is False

    download = service.export_job_download(status.job_id)
    assert download.filename.endswith(".json")
    manifest = json.loads(download.content)
    assert manifest["package_id"] == export.package_id
    assert manifest["source_asset_ids"] == [asset_id]
