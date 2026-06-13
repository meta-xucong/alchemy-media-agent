from __future__ import annotations

import base64
import json

from app.config import settings
from app.repositories import repository
from app.schemas import (
    Asset,
    AssetContentUploadRequest,
    CreateAssetMaskRequest,
    CreateAssetMaskResponse,
    CreateAssetUploadRequest,
    CreateAssetUploadResponse,
    MaterialBrief,
)
from app.services.asset_vision import analyze_asset_image
from app.services.utils import make_id, now_iso
from app.storage import media_store


def create_asset_upload(request: CreateAssetUploadRequest, *, veyra_user_id: int | None = None) -> CreateAssetUploadResponse:
    now = now_iso()
    asset_id = make_id("asset")
    consent = _consent_dict(request.consent)
    error = _asset_request_error(request, consent)
    if error:
        asset = Asset(
            id=asset_id,
            filename=request.filename,
            mime_type=request.mime_type,
            size_bytes=request.size_bytes,
            veyra_user_id=veyra_user_id,
            status="rejected",
            error=error,
            consent=consent,
            declared_role=request.declared_role,
            intended_use=request.intended_use,
            created_at=now,
            updated_at=now,
        )
        repository.save_asset(asset)
        return CreateAssetUploadResponse(asset_id=asset.id, upload_url="", headers={})

    upload_url = f"/v1/assets/{asset_id}/content"
    asset = Asset(
        id=asset_id,
        filename=request.filename,
        mime_type=request.mime_type,
        size_bytes=request.size_bytes,
        veyra_user_id=veyra_user_id,
        status="upload_requested",
        upload_url=upload_url,
        consent=consent,
        declared_role=request.declared_role,
        intended_use=request.intended_use,
        created_at=now,
        updated_at=now,
    )
    repository.save_asset(asset)
    return CreateAssetUploadResponse(asset_id=asset.id, upload_url=upload_url, headers={"x-upload-mode": "json-base64"})


def store_asset_content(asset_id: str, request: AssetContentUploadRequest) -> Asset | None:
    asset = repository.get_asset(asset_id)
    if not asset:
        return None
    if asset.status == "rejected":
        asset.updated_at = now_iso()
        return repository.save_asset(asset)
    if request.mime_type and not _is_image_mime(request.mime_type):
        asset.status = "failed"
        asset.updated_at = now_iso()
        return repository.save_asset(asset)
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (ValueError, TypeError):
        asset.status = "failed"
        asset.error = {"code": "invalid_base64", "message": "Asset content is not valid base64."}
        asset.updated_at = now_iso()
        return repository.save_asset(asset)
    if len(content) > settings.max_asset_upload_bytes:
        asset.status = "failed"
        asset.error = {
            "code": "asset_too_large",
            "message": f"Asset content exceeds {settings.max_asset_upload_bytes} bytes.",
        }
        asset.updated_at = now_iso()
        return repository.save_asset(asset)
    media_store.save_asset_bytes(asset_id=asset.id, filename=asset.filename, content=content)
    asset.status = "stored"
    if request.mime_type:
        asset.mime_type = request.mime_type
    asset.thumbnail_url = media_store.asset_url(asset.id) if asset.mime_type.startswith("image/") else None
    asset.normalized_url = media_store.asset_url(asset.id) if asset.mime_type.startswith("image/") else None
    asset.updated_at = now_iso()
    return repository.save_asset(asset)


def complete_asset_upload(asset_id: str) -> Asset | None:
    asset = repository.get_asset(asset_id)
    if not asset:
        return None
    now = now_iso()
    if asset.status == "rejected":
        asset.updated_at = now
        return repository.save_asset(asset)
    vision_profile = analyze_asset_image(asset)
    brief = MaterialBrief(
        asset_id=asset.id,
        asset_type=_asset_type(asset.mime_type),
        summary=vision_profile.summary or _summary_for(asset.mime_type, asset.filename),
        visual_style={
            "source": "local_material_analyzer",
            "filename": asset.filename,
            "declared_role": asset.declared_role,
            "stored": media_store.find_asset_file(asset.id) is not None,
            "vision_profile_status": vision_profile.status,
            "vision_summary": vision_profile.summary,
            "palette": vision_profile.style.get("palette", []),
            "accent_colors": vision_profile.style.get("accent_colors", []),
            "dark_accent_colors": vision_profile.style.get("dark_accent_colors", []),
            "warm_metal_colors": vision_profile.style.get("warm_metal_colors", []),
            "style_keywords": vision_profile.style.get("style_keywords", []),
            "composition": vision_profile.composition,
        },
        reference_usage=asset.declared_role or ("reference" if asset.mime_type.startswith("image/") else "context"),
        detected_roles=_detected_roles(asset, vision_profile=vision_profile),
        risks=[str(item.get("message") or item.get("code")) for item in vision_profile.risks],
    )
    asset.status = "ready"
    asset.material_brief = brief
    asset.vision_profile = vision_profile
    if asset.mime_type.startswith("image/"):
        asset.thumbnail_url = media_store.asset_url(asset.id) if media_store.find_asset_file(asset.id) else f"/v1/assets/{asset.id}"
        asset.normalized_url = asset.thumbnail_url
    asset.updated_at = now
    return repository.save_asset(asset)


def get_asset(asset_id: str) -> Asset | None:
    return repository.get_asset(asset_id)


def create_asset_mask(asset_id: str, request: CreateAssetMaskRequest) -> CreateAssetMaskResponse | None:
    asset = repository.get_asset(asset_id)
    if not asset:
        return None
    mask_id = make_id("mask")
    asset_dir = media_store.asset_root / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    mask_path = asset_dir / f"{mask_id}.json"
    mask_path.write_text(json.dumps(request.model_dump(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return CreateAssetMaskResponse(mask_id=mask_id, mask_url=f"/v1/assets/{asset_id}/masks/{mask_id}")


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
    return f"Local material brief for {asset_type} asset `{filename}`. Advanced V1 uses the user's explicit role as the source of truth."


def _detected_roles(asset: Asset, *, vision_profile=None) -> list[str]:
    roles: list[str] = []
    if asset.declared_role:
        roles.append(asset.declared_role)
    filename = asset.filename.lower()
    if asset.mime_type.startswith("image/"):
        roles.extend(["style_reference", "subject_reference", "composition_reference"])
    if "logo" in filename or "brand" in filename:
        roles.append("logo_overlay")
    if vision_profile:
        roles.extend(vision_profile.recommended_roles or [])
    return sorted(set(roles))


def _consent_dict(value) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value or {})


def _has_basic_rights(consent: dict) -> bool:
    return bool(consent.get("user_confirmed_rights") or consent.get("rights_confirmed"))


def _asset_request_error(request: CreateAssetUploadRequest, consent: dict) -> dict | None:
    if not _has_basic_rights(consent):
        return {"code": "asset_consent_required", "message": "Asset upload requires rights confirmation."}
    if not _is_image_mime(request.mime_type):
        return {"code": "unsupported_type", "message": "Advanced assets currently accept image MIME types only."}
    if int(request.size_bytes or 0) > settings.max_asset_upload_bytes:
        return {
            "code": "asset_too_large",
            "message": f"Asset upload exceeds {settings.max_asset_upload_bytes} bytes.",
        }
    return None


def _is_image_mime(mime_type: str | None) -> bool:
    return bool(mime_type and mime_type.lower().startswith("image/"))
