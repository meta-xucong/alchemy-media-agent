from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from app.config import settings
from app.services.alchemy_lab_asset_vision import analyze_lab_uploaded_asset
from app.services.alchemy_lab_uploads_models import (
    LAB_REFERENCE_FEATURE_ID,
    CreateLabUploadRequest,
    CreateLabUploadResponse,
    LabAssetConsent,
    LabAssetContentUploadRequest,
    LabUploadedAsset,
)
from app.services.utils import make_id, now_iso


MAX_LAB_REFERENCE_ASSET_BYTES = 12 * 1024 * 1024
MAX_LAB_REFERENCE_ASSET_COUNT = 4
ACCEPTED_LAB_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


def create_lab_upload(request: CreateLabUploadRequest, *, veyra_user_id: int | None = None) -> CreateLabUploadResponse:
    now = now_iso()
    asset_id = make_id("lab_asset")
    consent = _consent_model(request.consent)
    error = _upload_request_error(request, consent)
    upload_url = f"/api/lab/uploads/{asset_id}/content" if not error else ""
    asset = LabUploadedAsset(
        asset_id=asset_id,
        feature_id=request.feature_id or LAB_REFERENCE_FEATURE_ID,
        filename=_safe_filename(request.filename),
        mime_type=request.mime_type,
        size_bytes=request.size_bytes,
        veyra_user_id=veyra_user_id,
        status="upload_requested" if upload_url else "rejected",
        role=request.role,
        constraint_strength=request.constraint_strength,
        intended_use=request.intended_use,
        consent=consent,
        upload_url=upload_url or None,
        source_url=f"/api/lab/uploads/{asset_id}/content" if upload_url else None,
        thumbnail_url=f"/api/lab/uploads/{asset_id}/content" if upload_url else None,
        error=error,
        created_at=now,
        updated_at=now,
    )
    _save_lab_asset(asset)
    return CreateLabUploadResponse(
        asset_id=asset.asset_id,
        upload_url=upload_url,
        headers={"x-upload-mode": "json-base64"} if upload_url else {},
    )


def store_lab_upload_content(asset_id: str, request: LabAssetContentUploadRequest) -> LabUploadedAsset | None:
    asset = get_lab_upload(asset_id)
    if not asset:
        return None
    if asset.status == "rejected":
        return asset
    mime_type = (request.mime_type or asset.mime_type or "").lower()
    if mime_type not in ACCEPTED_LAB_IMAGE_MIME_TYPES:
        return _fail_asset(asset, "unsupported_type", "Alchemy Lab reference images accept PNG, JPEG, or WebP only.")
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (ValueError, TypeError) as exc:
        return _fail_asset(asset, "invalid_base64", str(exc)[:200])
    if len(content) > MAX_LAB_REFERENCE_ASSET_BYTES:
        return _fail_asset(asset, "asset_too_large", f"Reference image exceeds {MAX_LAB_REFERENCE_ASSET_BYTES} bytes.")
    validation_error = _validate_image_content(content)
    if validation_error:
        return _fail_asset(asset, "invalid_image_content", validation_error)
    path = _asset_content_path(asset, mime_type=mime_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stored = asset.model_copy(
        update={
            "status": "stored",
            "mime_type": mime_type,
            "size_bytes": len(content),
            "storage_path": str(path),
            "source_url": f"/api/lab/uploads/{asset.asset_id}/content",
            "thumbnail_url": f"/api/lab/uploads/{asset.asset_id}/content",
            "updated_at": now_iso(),
        }
    )
    return _save_lab_asset(stored)


def complete_lab_upload(asset_id: str) -> LabUploadedAsset | None:
    asset = get_lab_upload(asset_id)
    if not asset:
        return None
    if asset.status in {"rejected", "failed", "deleted"}:
        return asset
    path = lab_uploaded_asset_path(asset_id)
    if not path or not path.exists():
        return _fail_asset(asset, "asset_file_missing", "Reference image content is missing.")
    try:
        validation_error = _validate_image_content(path.read_bytes())
    except OSError as exc:
        validation_error = str(exc)[:200]
    if validation_error:
        return _fail_asset(asset, "invalid_image_content", validation_error)
    brief = analyze_lab_uploaded_asset(asset, path)
    if not brief.get("usable_as_input_image", True) and "asset_file_missing" in set(brief.get("warnings") or []):
        return _fail_asset(asset, "asset_analysis_failed", "Reference image could not be used as an input image.", brief=brief)
    ready = asset.model_copy(
        update={
            "status": "ready",
            "role": asset.role,
            "brief": brief,
            "updated_at": now_iso(),
        }
    )
    return _save_lab_asset(ready)


def get_lab_upload(asset_id: str) -> LabUploadedAsset | None:
    path = _asset_metadata_path(asset_id)
    if not path.exists():
        return None
    try:
        return LabUploadedAsset.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_lab_upload_content(asset_id: str) -> tuple[bytes, str] | None:
    asset = get_lab_upload(asset_id)
    if not asset or asset.status not in {"stored", "ready"}:
        return None
    path = lab_uploaded_asset_path(asset_id)
    if not path or not path.exists():
        return None
    return path.read_bytes(), asset.mime_type


def lab_uploaded_asset_path(asset_id: str) -> Path | None:
    asset = get_lab_upload(asset_id)
    if not asset:
        return None
    if asset.storage_path:
        path = Path(asset.storage_path)
        return path if path.exists() else None
    upload_dir = _asset_dir(asset_id)
    if not upload_dir.exists():
        return None
    for path in upload_dir.iterdir():
        if path.is_file() and path.name.startswith("original"):
            return path
    return None


def require_lab_upload_visible(asset_id: str, *, veyra_user_id: int | None, is_admin: bool = False) -> LabUploadedAsset:
    asset = get_lab_upload(asset_id)
    if not asset:
        raise ValueError("asset_not_found")
    if settings.veyra_auth_enabled and not is_admin and asset.veyra_user_id not in {None, veyra_user_id}:
        raise PermissionError("lab_asset_forbidden")
    return asset


def public_lab_asset_summary(asset: LabUploadedAsset) -> dict:
    brief = asset.brief or {}
    return {
        "role": asset.role or (brief.get("role") if isinstance(brief, dict) else None),
        "constraint_strength": asset.constraint_strength,
        "brief": brief.get("visual_summary") if isinstance(brief, dict) else None,
    }


def _save_lab_asset(asset: LabUploadedAsset) -> LabUploadedAsset:
    path = _asset_metadata_path(asset.asset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(asset.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return asset


def _fail_asset(asset: LabUploadedAsset, code: str, message: str, *, brief: dict | None = None) -> LabUploadedAsset:
    return _save_lab_asset(
        asset.model_copy(
            update={
                "status": "failed",
                "error": {"code": code, "message": message},
                "brief": brief or asset.brief,
                "updated_at": now_iso(),
            }
        )
    )


def _upload_request_error(request: CreateLabUploadRequest, consent: LabAssetConsent) -> dict | None:
    if request.feature_id and request.feature_id != LAB_REFERENCE_FEATURE_ID:
        return {"code": "unsupported_lab_feature", "message": "This Lab upload feature is not available yet."}
    if not consent.has_basic_rights():
        return {"code": "asset_consent_required", "message": "Reference image upload requires rights confirmation."}
    if (request.mime_type or "").lower() not in ACCEPTED_LAB_IMAGE_MIME_TYPES:
        return {"code": "unsupported_type", "message": "Alchemy Lab reference images accept PNG, JPEG, or WebP only."}
    if int(request.size_bytes or 0) > MAX_LAB_REFERENCE_ASSET_BYTES:
        return {"code": "asset_too_large", "message": f"Reference image exceeds {MAX_LAB_REFERENCE_ASSET_BYTES} bytes."}
    return None


def _validate_image_content(content: bytes) -> str | None:
    try:
        from PIL import Image
        from io import BytesIO

        with Image.open(BytesIO(content)) as image:
            image.verify()
        return None
    except Exception as exc:
        return str(exc)[:200]


def _consent_model(value) -> LabAssetConsent:
    if isinstance(value, LabAssetConsent):
        return value
    if hasattr(value, "model_dump"):
        return LabAssetConsent.model_validate(value.model_dump())
    return LabAssetConsent.model_validate(dict(value or {}))


def _asset_dir(asset_id: str) -> Path:
    return settings.media_storage_root / "lab_uploads" / asset_id


def _asset_metadata_path(asset_id: str) -> Path:
    return _asset_dir(asset_id) / "asset.json"


def _asset_content_path(asset: LabUploadedAsset, *, mime_type: str | None = None) -> Path:
    suffix = Path(asset.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = _suffix_for_mime(mime_type or asset.mime_type)
    return _asset_dir(asset.asset_id) / f"original{suffix}"


def _suffix_for_mime(mime_type: str | None) -> str:
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/webp":
        return ".webp"
    return ".png"


def _safe_filename(filename: str) -> str:
    stem = Path(filename or "reference.png").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return cleaned or "reference.png"
