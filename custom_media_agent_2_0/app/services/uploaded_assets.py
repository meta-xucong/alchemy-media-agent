from __future__ import annotations

import base64
import json
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
    _save_uploaded_asset(asset)
    return CreateUploadedAssetResponse(
        asset_id=asset.asset_id,
        upload_url=upload_url,
        headers={"x-upload-mode": "json-base64"} if upload_url else {},
    )


def store_uploaded_asset_content(asset_id: str, request: AssetContentUploadRequest) -> UploadedAsset | None:
    asset = get_uploaded_asset(asset_id)
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
        return _save_uploaded_asset(failed)
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
        return _save_uploaded_asset(failed)
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
    return _save_uploaded_asset(stored)


def complete_uploaded_asset(asset_id: str) -> UploadedAsset | None:
    asset = get_uploaded_asset(asset_id)
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
    return _save_uploaded_asset(ready)


def get_uploaded_asset(asset_id: str) -> UploadedAsset | None:
    cached = repository.get_uploaded_asset(asset_id)
    if cached:
        return cached
    loaded = _load_uploaded_asset(asset_id)
    if loaded:
        return repository.save_uploaded_asset(loaded)
    return None


def read_uploaded_asset_content(asset_id: str) -> tuple[bytes, str] | None:
    asset = get_uploaded_asset(asset_id)
    if not asset or not _is_image_mime(asset.mime_type):
        return None
    path = uploaded_asset_path(asset_id)
    if not path or not path.exists():
        return None
    return path.read_bytes(), asset.mime_type


def uploaded_asset_path(asset_id: str) -> Path | None:
    asset = get_uploaded_asset(asset_id)
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


def _save_uploaded_asset(asset: UploadedAsset) -> UploadedAsset:
    saved = repository.save_uploaded_asset(asset)
    _persist_uploaded_asset(saved)
    return saved


def _asset_metadata_path(asset_id: str) -> Path:
    return settings.storage_dir / "uploads" / asset_id / "asset.json"


def _persist_uploaded_asset(asset: UploadedAsset) -> None:
    path = _asset_metadata_path(asset.asset_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(asset.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
    except Exception:
        return


def _load_uploaded_asset(asset_id: str) -> UploadedAsset | None:
    path = _asset_metadata_path(asset_id)
    if path.exists():
        try:
            return UploadedAsset.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return _recover_uploaded_asset_from_file(asset_id)


def _recover_uploaded_asset_from_file(asset_id: str) -> UploadedAsset | None:
    upload_dir = settings.storage_dir / "uploads" / asset_id
    if not upload_dir.exists():
        return None
    candidates = sorted(
        [
            item
            for item in upload_dir.iterdir()
            if item.is_file() and item.name.startswith("original") and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        ]
    )
    if not candidates:
        return None
    path = candidates[0]
    stat = path.stat()
    created = utc_now()
    mime_type = _mime_for_suffix(path.suffix.lower())
    return UploadedAsset(
        asset_id=asset_id,
        filename=path.name,
        mime_type=mime_type,
        size_bytes=stat.st_size,
        status="ready",
        role="subject_reference",
        constraint_strength="strong",
        source_url=f"/api/v2/uploads/{asset_id}/content",
        thumbnail_url=f"/api/v2/uploads/{asset_id}/content",
        storage_path=str(path),
        created_at=created,
        updated_at=created,
    )


def _suffix_for_mime(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/webp":
        return ".webp"
    if mime_type == "image/gif":
        return ".gif"
    return ".png"


def _mime_for_suffix(suffix: str) -> str:
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def _safe_filename(filename: str) -> str:
    name = Path(filename or "uploaded-image.png").name
    return name or "uploaded-image.png"


def _is_image_mime(mime_type: str | None) -> bool:
    return bool(mime_type and mime_type.lower().startswith("image/"))
