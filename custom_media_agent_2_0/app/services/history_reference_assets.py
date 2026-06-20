from __future__ import annotations

from pathlib import Path

from app.schemas import FavoriteReferenceAssetRequest, UploadedAsset
from app.services.image_history import get_image_history_item
from app.services.output_storage import read_output_content
from app.services.uploaded_assets import create_uploaded_asset_from_bytes


def create_reference_asset_from_history_output(
    output_id: str,
    request: FavoriteReferenceAssetRequest | None = None,
) -> UploadedAsset | None:
    clean_output_id = str(output_id or "").strip()
    if not clean_output_id:
        return None
    history_item = get_image_history_item(clean_output_id)
    if not history_item:
        return None
    content = read_output_content(clean_output_id)
    if not content:
        return None
    image_bytes, mime_type = content
    body = request or FavoriteReferenceAssetRequest()
    return create_uploaded_asset_from_bytes(
        filename=_reference_filename(clean_output_id, mime_type),
        mime_type=mime_type,
        content=image_bytes,
        role=body.role,
        constraint_strength=body.constraint_strength,
        intended_use=body.intended_use or "continue_modifying_selected_favorite_image",
    )


def _reference_filename(output_id: str, mime_type: str) -> str:
    return f"favorite-reference-{output_id}{_suffix_for_mime(mime_type)}"


def _suffix_for_mime(mime_type: str) -> str:
    normalized = str(mime_type or "").lower()
    if "jpeg" in normalized or "jpg" in normalized:
        return ".jpg"
    if "webp" in normalized:
        return ".webp"
    if "gif" in normalized:
        return ".gif"
    suffix = Path(normalized).suffix
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return suffix
    return ".png"
