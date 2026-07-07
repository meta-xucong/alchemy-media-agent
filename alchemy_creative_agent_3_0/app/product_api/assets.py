"""V3-owned uploaded asset lifecycle for Product API workflows."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from ..shared_capabilities import AssetRole, UploadedAssetInfo
from .contracts import (
    V3AssetContentUploadRequest,
    V3AssetUploadCreateRequest,
    V3AssetUploadStatusValue,
    V3UploadedAssetRecord,
)


ACCEPTED_V3_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_V3_UPLOADED_ASSET_BYTES = 12 * 1024 * 1024
_ASSET_ID_PATTERN = re.compile(r"^v3_asset_[a-f0-9]{16}$")
_ROLE_ALIASES = {
    "subject_reference": AssetRole.PRODUCT_REFERENCE,
    "product_reference": AssetRole.PRODUCT_REFERENCE,
    "style_reference": AssetRole.STYLE_REFERENCE,
    "style_material_reference": AssetRole.STYLE_REFERENCE,
    "logo_reference": AssetRole.LOGO_REFERENCE,
    "face_reference": AssetRole.FACE_REFERENCE,
    "portrait_identity": AssetRole.FACE_REFERENCE,
    "identity_reference": AssetRole.FACE_REFERENCE,
    "character_reference": AssetRole.FACE_REFERENCE,
    "background_reference": AssetRole.BACKGROUND_REFERENCE,
    "composition_reference": AssetRole.COMPOSITION_REFERENCE,
    "color_reference": AssetRole.COLOR_REFERENCE,
    "negative_reference": AssetRole.NEGATIVE_REFERENCE,
    "unknown_reference": AssetRole.UNKNOWN_REFERENCE,
}


class V3UploadedAssetStore:
    """Persistent local upload store owned by the V3 Product API boundary."""

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self.storage_root = Path(storage_root) if storage_root else _default_storage_root()

    def create_upload(self, request: V3AssetUploadCreateRequest | dict) -> V3UploadedAssetRecord:
        create_request = self._coerce_create_request(request)
        mime_type = create_request.mime_type.lower()
        self._validate_mime_type(mime_type)
        if create_request.size_bytes > MAX_V3_UPLOADED_ASSET_BYTES:
            raise ValueError(f"Uploaded image exceeds {MAX_V3_UPLOADED_ASSET_BYTES} bytes.")
        if create_request.role and create_request.role not in _ROLE_ALIASES:
            raise ValueError("Unsupported V3 asset role.")

        asset_id = f"v3_asset_{uuid4().hex[:16]}"
        now = _now_iso()
        record = V3UploadedAssetRecord(
            asset_id=asset_id,
            filename=_safe_filename(create_request.filename),
            mime_type=mime_type,
            size_bytes=create_request.size_bytes,
            role=create_request.role,
            status=V3AssetUploadStatusValue.UPLOAD_REQUESTED,
            upload_url=_content_route(asset_id),
            content_url=_content_route(asset_id),
            created_at=now,
            updated_at=now,
            metadata={
                **create_request.metadata,
                "source": "V3UploadedAssetStore",
                "v3_owned_upload": True,
                "max_size_bytes": MAX_V3_UPLOADED_ASSET_BYTES,
            },
        )
        return self._save_record(record)

    def store_content(
        self,
        asset_id: str,
        request: V3AssetContentUploadRequest | dict,
    ) -> V3UploadedAssetRecord | None:
        record = self.get_upload(asset_id)
        if record is None:
            return None
        upload_request = self._coerce_content_request(request)
        mime_type = (upload_request.mime_type or record.mime_type).lower()
        self._validate_mime_type(mime_type)
        try:
            content = base64.b64decode(upload_request.content_base64, validate=True)
        except (TypeError, ValueError) as exc:
            failed = self._fail_record(record, "invalid_base64", str(exc)[:200])
            raise ValueError(failed.error["message"] if failed.error else "Asset content is not valid base64.") from exc
        if not content:
            failed = self._fail_record(record, "empty_content", "Uploaded image content is empty.")
            raise ValueError(failed.error["message"] if failed.error else "Uploaded image content is empty.")
        if len(content) > MAX_V3_UPLOADED_ASSET_BYTES:
            failed = self._fail_record(record, "asset_too_large", f"Uploaded image exceeds {MAX_V3_UPLOADED_ASSET_BYTES} bytes.")
            raise ValueError(failed.error["message"] if failed.error else "Uploaded image is too large.")
        validation_error = _validate_image_content(content)
        if validation_error:
            failed = self._fail_record(record, "invalid_image_content", validation_error)
            raise ValueError(failed.error["message"] if failed.error else "Uploaded image content is invalid.")

        path = self._content_path(record.asset_id, record.filename, mime_type)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        stored = record.model_copy(
            update={
                "status": V3AssetUploadStatusValue.STORED,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "file_path": str(path),
                "content_url": _content_route(record.asset_id),
                "updated_at": _now_iso(),
                "error": None,
                "metadata": {**record.metadata, **upload_request.metadata, "content_stored": True},
            }
        )
        return self._save_record(stored)

    def complete_upload(self, asset_id: str) -> V3UploadedAssetRecord | None:
        record = self.get_upload(asset_id)
        if record is None:
            return None
        if record.status == V3AssetUploadStatusValue.FAILED:
            return record
        path = Path(record.file_path) if record.file_path else None
        if path is None or not path.exists():
            failed = self._fail_record(record, "asset_file_missing", "Uploaded image content is missing.")
            raise ValueError(failed.error["message"] if failed.error else "Uploaded image content is missing.")
        try:
            validation_error = _validate_image_content(path.read_bytes())
        except OSError as exc:
            validation_error = str(exc)[:200]
        if validation_error:
            failed = self._fail_record(record, "invalid_image_content", validation_error)
            raise ValueError(failed.error["message"] if failed.error else "Uploaded image content is invalid.")
        ready = record.model_copy(
            update={
                "status": V3AssetUploadStatusValue.READY,
                "updated_at": _now_iso(),
                "metadata": {**record.metadata, "ready_for_v3_runtime": True},
            }
        )
        return self._save_record(ready)

    def get_upload(self, asset_id: str) -> V3UploadedAssetRecord | None:
        if not _valid_asset_id(asset_id):
            return None
        path = self._metadata_path(asset_id)
        if not path.exists():
            return None
        try:
            return V3UploadedAssetRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def read_content(self, asset_id: str) -> tuple[bytes, str] | None:
        record = self.get_upload(asset_id)
        if record is None or record.status not in {V3AssetUploadStatusValue.STORED, V3AssetUploadStatusValue.READY}:
            return None
        path = Path(record.file_path) if record.file_path else None
        if path is None or not path.exists():
            return None
        return path.read_bytes(), record.mime_type

    def resolve_uploaded_assets(self, asset_ids: list[str]) -> list[UploadedAssetInfo]:
        resolved: list[UploadedAssetInfo] = []
        seen: set[str] = set()
        for asset_id in asset_ids:
            clean_id = str(asset_id or "").strip()
            if not clean_id or clean_id in seen:
                continue
            seen.add(clean_id)
            record = self.get_upload(clean_id)
            if record is None:
                resolved.append(UploadedAssetInfo(asset_id=clean_id, metadata={"asset_lookup_status": "not_found"}))
                continue
            resolved.append(self.to_uploaded_asset_info(record))
        return resolved

    def to_uploaded_asset_info(self, record: V3UploadedAssetRecord) -> UploadedAssetInfo:
        role = _coerce_asset_role(record.role)
        has_local_file = record.status in {V3AssetUploadStatusValue.STORED, V3AssetUploadStatusValue.READY} and bool(record.file_path)
        return UploadedAssetInfo(
            asset_id=record.asset_id,
            role=role,
            file_path=record.file_path if has_local_file else None,
            uri=record.content_url,
            filename=record.filename,
            mime_type=record.mime_type,
            metadata={
                **record.metadata,
                "upload_status": record.status.value,
                "uploaded_filename": record.filename,
                "content_url": record.content_url,
                "v3_owned_upload": True,
            },
        )

    def _save_record(self, record: V3UploadedAssetRecord) -> V3UploadedAssetRecord:
        path = self._metadata_path(record.asset_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        return record

    def _fail_record(self, record: V3UploadedAssetRecord, code: str, message: str) -> V3UploadedAssetRecord:
        return self._save_record(
            record.model_copy(
                update={
                    "status": V3AssetUploadStatusValue.FAILED,
                    "error": {"code": code, "message": message},
                    "updated_at": _now_iso(),
                }
            )
        )

    def _metadata_path(self, asset_id: str) -> Path:
        return self.storage_root / asset_id / "asset.json"

    def _content_path(self, asset_id: str, filename: str, mime_type: str) -> Path:
        suffix = Path(filename).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            suffix = _suffix_for_mime(mime_type)
        return self.storage_root / asset_id / f"original{suffix}"

    def _coerce_create_request(self, request: V3AssetUploadCreateRequest | dict) -> V3AssetUploadCreateRequest:
        if isinstance(request, V3AssetUploadCreateRequest):
            return request
        return V3AssetUploadCreateRequest.model_validate(request)

    def _coerce_content_request(self, request: V3AssetContentUploadRequest | dict) -> V3AssetContentUploadRequest:
        if isinstance(request, V3AssetContentUploadRequest):
            return request
        return V3AssetContentUploadRequest.model_validate(request)

    def _validate_mime_type(self, mime_type: str) -> None:
        if mime_type not in ACCEPTED_V3_IMAGE_MIME_TYPES:
            raise ValueError("V3 uploaded assets accept PNG, JPEG, or WebP images only.")


def _default_storage_root() -> Path:
    configured = os.getenv("ALCHEMY_V3_UPLOAD_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / ".media_storage" / "v3_uploads"


def _content_route(asset_id: str) -> str:
    return f"/api/v3/creative-agent/uploads/{asset_id}/content"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_filename(filename: str) -> str:
    stem = Path(filename or "reference.png").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return cleaned or "reference.png"


def _suffix_for_mime(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/webp":
        return ".webp"
    return ".png"


def _validate_image_content(content: bytes) -> str | None:
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            image.verify()
        return None
    except Exception as exc:
        return str(exc)[:200]


def _coerce_asset_role(value: str | None) -> AssetRole | None:
    if not value:
        return None
    return _ROLE_ALIASES.get(value, AssetRole.UNKNOWN_REFERENCE)


def _valid_asset_id(asset_id: str) -> bool:
    return bool(_ASSET_ID_PATTERN.match(str(asset_id or "")))
