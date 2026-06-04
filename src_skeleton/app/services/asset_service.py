from __future__ import annotations

from app.repositories import repository
from app.schemas import Asset, CreateAssetUploadRequest, CreateAssetUploadResponse, MaterialBrief
from app.services.utils import make_id, now_iso


def create_asset_upload(request: CreateAssetUploadRequest) -> CreateAssetUploadResponse:
    now = now_iso()
    asset_id = make_id("asset")
    if not request.consent:
        asset = Asset(
            id=asset_id,
            filename=request.filename,
            mime_type=request.mime_type,
            size_bytes=request.size_bytes,
            status="rejected",
            consent=request.consent,
            created_at=now,
            updated_at=now,
        )
        repository.save_asset(asset)
        return CreateAssetUploadResponse(asset_id=asset.id, upload_url="", headers={})

    upload_url = f"memory://uploads/{asset_id}/{request.filename}"
    asset = Asset(
        id=asset_id,
        filename=request.filename,
        mime_type=request.mime_type,
        size_bytes=request.size_bytes,
        status="uploaded",
        upload_url=upload_url,
        consent=request.consent,
        created_at=now,
        updated_at=now,
    )
    repository.save_asset(asset)
    return CreateAssetUploadResponse(asset_id=asset.id, upload_url=upload_url, headers={"x-mock-upload": "true"})


def complete_asset_upload(asset_id: str) -> Asset | None:
    asset = repository.get_asset(asset_id)
    if not asset:
        return None
    now = now_iso()
    if asset.status == "rejected":
        asset.updated_at = now
        return repository.save_asset(asset)
    brief = MaterialBrief(
        asset_id=asset.id,
        asset_type=_asset_type(asset.mime_type),
        summary=_summary_for(asset.mime_type, asset.filename),
        visual_style={"source": "mock_material_analyzer"},
        reference_usage="reference" if asset.mime_type.startswith("image/") else "context",
        risks=[],
    )
    asset.status = "ready"
    asset.material_brief = brief
    asset.thumbnail_url = f"/v1/assets/{asset.id}"
    asset.updated_at = now
    return repository.save_asset(asset)


def get_asset(asset_id: str) -> Asset | None:
    return repository.get_asset(asset_id)


def _asset_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type == "application/pdf":
        return "pdf"
    if "presentation" in mime_type:
        return "presentation"
    if "word" in mime_type or "document" in mime_type:
        return "document"
    if "sheet" in mime_type or "csv" in mime_type:
        return "spreadsheet"
    return "file"


def _summary_for(mime_type: str, filename: str) -> str:
    asset_type = _asset_type(mime_type)
    return f"Mock material brief for {asset_type} asset `{filename}`. Replace with extractor output before production."
