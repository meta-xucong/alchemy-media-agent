from __future__ import annotations

import base64
from pathlib import Path

from app.config import settings
from app.repositories import repository
from app.repositories.memory import utc_now
from app.schemas import (
    AssetContentUploadRequest,
    CreateUploadedAssetRequest,
    CreateUploadedAssetResponse,
    UploadedAsset,
)
from app.services.ids import new_id
from app.services.uploaded_asset_vision import analyze_uploaded_asset


def create_uploaded_asset(request: CreateUploadedAssetRequest) -> CreateUploadedAssetResponse:
    now = utc_now()
    asset_id = new_id("asset")
    upload_url = f"/api/v2/uploads/{asset_id}/content" if _is_image_mime(request.mime_type) else ""
    asset = UploadedAsset(
        asset_id=asset_id,
        filename=_safe_filename(request.filename),
        mime_type=request.mime_type,
        size_bytes=request.size_bytes,
        status="upload_requested" if upload_url else "rejected",
        role=request.role,
        constraint_strength=request.constraint_strength,
        intended_use=request.intended_use,
        upload_url=upload_url or None,
        source_url=f"/api/v2/uploads/{asset_id}/content" if upload_url else None,
        thumbnail_url=f"/api/v2/uploads/{asset_id}/content" if upload_url else None,
        created_at=now,
        updated_at=now,
    )
    repository.save_uploaded_asset(asset)
    return CreateUploadedAssetResponse(
        asset_id=asset.asset_id,
        upload_url=upload_url,
        headers={"x-upload-mode": "json-base64"} if upload_url else {},
    )


def store_uploaded_asset_content(asset_id: str, request: AssetContentUploadRequest) -> UploadedAsset | None:
    asset = repository.get_uploaded_asset(asset_id)
    if not asset:
        return None
    if asset.status == "rejected":
        return asset
    mime_type = request.mime_type or asset.mime_type
    if not _is_image_mime(mime_type):
        failed = asset.model_copy(
            update={
                "status": "failed",
                "error": {"code": "unsupported_type", "message": "V2 uploads currently accept image MIME types only."},
                "updated_at": utc_now(),
            }
        )
        return repository.save_uploaded_asset(failed)
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (ValueError, TypeError) as exc:
        failed = asset.model_copy(
            update={
                "status": "failed",
                "error": {"code": "invalid_base64", "message": str(exc)[:200]},
                "updated_at": utc_now(),
            }
        )
        return repository.save_uploaded_asset(failed)
    path = _asset_content_path(asset)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stored = asset.model_copy(
        update={
            "status": "stored",
            "mime_type": mime_type,
            "size_bytes": len(content),
            "storage_path": str(path),
            "source_url": f"/api/v2/uploads/{asset.asset_id}/content",
            "thumbnail_url": f"/api/v2/uploads/{asset.asset_id}/content",
            "updated_at": utc_now(),
        }
    )
    return repository.save_uploaded_asset(stored)


def complete_uploaded_asset(asset_id: str) -> UploadedAsset | None:
    asset = repository.get_uploaded_asset(asset_id)
    if not asset:
        return None
    if asset.status in {"rejected", "failed"}:
        return asset
    path = uploaded_asset_path(asset_id)
    brief = analyze_uploaded_asset(asset, path)
    ready = asset.model_copy(
        update={
            "status": "ready",
            "role": asset.role or brief.role,
            "brief": brief,
            "updated_at": utc_now(),
        }
    )
    return repository.save_uploaded_asset(ready)


def get_uploaded_asset(asset_id: str) -> UploadedAsset | None:
    return repository.get_uploaded_asset(asset_id)


def read_uploaded_asset_content(asset_id: str) -> tuple[bytes, str] | None:
    asset = repository.get_uploaded_asset(asset_id)
    if not asset or not _is_image_mime(asset.mime_type):
        return None
    path = uploaded_asset_path(asset_id)
    if not path or not path.exists():
        return None
    return path.read_bytes(), asset.mime_type


def uploaded_asset_path(asset_id: str) -> Path | None:
    asset = repository.get_uploaded_asset(asset_id)
    if not asset:
        return None
    if asset.storage_path:
        return Path(asset.storage_path)
    candidate = _asset_content_path(asset)
    return candidate if candidate.exists() else None


def _asset_content_path(asset: UploadedAsset) -> Path:
    suffix = Path(asset.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = _suffix_for_mime(asset.mime_type)
    return settings.storage_dir / "uploads" / asset.asset_id / f"original{suffix}"


def _suffix_for_mime(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/webp":
        return ".webp"
    if mime_type == "image/gif":
        return ".gif"
    return ".png"


def _safe_filename(filename: str) -> str:
    name = Path(filename or "uploaded-image.png").name
    return name or "uploaded-image.png"


def _is_image_mime(mime_type: str | None) -> bool:
    return bool(mime_type and mime_type.lower().startswith("image/"))
