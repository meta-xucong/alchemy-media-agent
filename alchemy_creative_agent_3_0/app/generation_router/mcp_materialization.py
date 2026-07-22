"""Shared, explicit MCP image handoff storage for V3.

The legacy Codex relay is intentionally conversation-only.  This module is
the separate opt-in materialized channel: V3 freezes the canonical renderer
contract, a local MCP client submits the resulting image bytes, and the
ordinary V3 provider adapter consumes those bytes.  It never writes a V3
candidate or delivery record by itself.
"""

from __future__ import annotations

import base64
from io import BytesIO
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
from typing import Any

from ..creative_core.rules import stable_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_image(content: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            return image.size
    except Exception as exc:
        raise ValueError("MCP artifact is not a valid image") from exc


def _parse_size(value: object) -> tuple[int, int] | None:
    raw = str(value or "").strip().lower()
    if not raw or raw == "auto" or "x" not in raw:
        return None
    left, right = raw.split("x", 1)
    try:
        width = int(left)
        height = int(right)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _normalize_image_size(
    content: bytes,
    *,
    image_format: str,
    target_size: tuple[int, int],
) -> bytes:
    """Fit an MCP image into the frozen rendering size on a white matte canvas.

    This is a transport parity operation, not a creative edit: it never invents
    pixels for the subject and never crops the submitted image.  It only scales
    the submitted artifact down/up to fit inside the Provider-equivalent canvas.
    """

    try:
        from PIL import Image

        target_width, target_height = target_size
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        with Image.open(BytesIO(content)) as image:
            source = image.convert("RGBA")
        source.thumbnail((target_width, target_height), resampling)
        canvas = Image.new("RGBA", (target_width, target_height), (255, 255, 255, 255))
        offset = ((target_width - source.width) // 2, (target_height - source.height) // 2)
        canvas.alpha_composite(source, offset)
        output = BytesIO()
        if image_format == "jpeg":
            canvas.convert("RGB").save(output, format="JPEG", quality=95)
        elif image_format == "webp":
            canvas.save(output, format="WEBP", quality=95)
        else:
            canvas.save(output, format="PNG")
        return output.getvalue()
    except Exception as exc:
        raise ValueError("MCP artifact could not be normalized to the rendering size") from exc


def _default_root() -> Path:
    configured = os.getenv("ALCHEMY_V3_MCP_MATERIALIZATION_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / ".media_storage" / "v3_mcp_materializations"


class McpMaterializationError(ValueError):
    """Safe local handoff contract failure."""

    def __init__(self, code: str, message: str | None = None, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.detail = dict(detail or {})


class McpMaterializationHandoffStore:
    """Append-only-ish pending handoffs; one artifact may be consumed once."""

    schema_version = "v3_mcp_materialization_handoff_v1"
    max_artifact_bytes = 50 * 1024 * 1024

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self.storage_root = Path(storage_root) if storage_root else _default_root()
        self._lock = threading.RLock()

    def ensure_pending(
        self,
        *,
        operation_id: str,
        prompt: str,
        prompt_sha256: str,
        reference_assets: list[dict[str, Any]],
        rendering_contract: dict[str, Any],
    ) -> dict[str, Any]:
        operation = str(operation_id or "").strip()
        prompt_hash = str(prompt_sha256 or "").strip().lower()
        if not operation or not prompt_hash or not str(prompt or "").strip():
            raise McpMaterializationError("mcp_materialization_contract_incomplete")
        handoff_id = stable_id("mcp_handoff", operation, prompt_hash)
        path = self._record_path(handoff_id)
        with self._lock:
            existing = self._read(handoff_id)
            if existing is not None:
                if str(existing.get("prompt_sha256") or "") != prompt_hash:
                    raise McpMaterializationError("mcp_materialization_prompt_mismatch")
                if existing.get("reference_asset_hashes") != self._reference_hashes(reference_assets):
                    raise McpMaterializationError("mcp_materialization_reference_mismatch")
                return existing
            hashes = self._reference_hashes(reference_assets)
            payload = {
                "schema_version": self.schema_version,
                "handoff_id": handoff_id,
                "operation_id": operation,
                "status": "pending",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "nonce": secrets.token_urlsafe(24),
                "canonical_prompt": str(prompt),
                "prompt_sha256": prompt_hash,
                "reference_assets": self._safe_reference_contract(reference_assets, hashes),
                "reference_asset_hashes": hashes,
                "rendering_contract": self._safe_rendering_contract(rendering_contract),
                "artifact_file": None,
                "artifact_sha256": None,
                "artifact_format": None,
                "artifact_mime_type": None,
                "consumed_at": None,
            }
            self._write(path, payload)
            return payload

    def get(self, handoff_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._read(handoff_id)

    def public_view(self, handoff_id: str) -> dict[str, Any]:
        payload = self.get(handoff_id)
        if payload is None:
            raise McpMaterializationError("mcp_materialization_not_found")
        # The endpoint is local-only, but still return only the fields Codex
        # needs to call ImageGen and submit one image.  No raw response or
        # internal Provider credentials are part of this contract.
        return {
            "schema_version": "v3_mcp_materialization_public_v1",
            "handoff_id": payload["handoff_id"],
            "operation_id": payload["operation_id"],
            "status": payload["status"],
            "nonce": payload["nonce"],
            "canonical_prompt": payload["canonical_prompt"],
            "prompt_sha256": payload["prompt_sha256"],
            "reference_assets": payload["reference_assets"],
            "reference_asset_hashes": payload["reference_asset_hashes"],
            "rendering_contract": payload["rendering_contract"],
            "artifact_sha256": payload.get("artifact_sha256"),
            "artifact_format": payload.get("artifact_format"),
        }

    def submit(
        self,
        handoff_id: str,
        *,
        nonce: str,
        prompt_sha256: str,
        reference_asset_hashes: list[str],
        artifact_bytes: bytes,
    ) -> dict[str, Any]:
        with self._lock:
            payload = self._read(handoff_id)
            if payload is None:
                raise McpMaterializationError("mcp_materialization_not_found")
            if str(nonce or "") != str(payload.get("nonce") or ""):
                raise McpMaterializationError("mcp_materialization_nonce_invalid")
            if str(prompt_sha256 or "").strip().lower() != str(payload.get("prompt_sha256") or ""):
                raise McpMaterializationError("mcp_materialization_prompt_mismatch")
            expected_refs = list(payload.get("reference_asset_hashes") or [])
            if list(reference_asset_hashes or []) != expected_refs:
                raise McpMaterializationError("mcp_materialization_reference_mismatch")
            if payload.get("status") == "consumed":
                raise McpMaterializationError("mcp_materialization_already_consumed")
            if payload.get("status") == "submitted":
                return self.public_view(handoff_id)
            content = bytes(artifact_bytes or b"")
            if not content or len(content) > self.max_artifact_bytes:
                raise McpMaterializationError("mcp_materialization_artifact_invalid")
            try:
                width, height = _validate_image(content)
            except Exception as exc:
                raise McpMaterializationError(
                    "mcp_materialization_artifact_invalid",
                    "The submitted artifact is not a readable image.",
                ) from exc
            image_format, mime_type = self._image_format(content)
            expected_format = str((payload.get("rendering_contract") or {}).get("output_format") or "png").lower()
            if image_format != expected_format:
                raise McpMaterializationError("mcp_materialization_output_format_mismatch")
            contract = dict(payload.get("rendering_contract") or {})
            expected_size = _parse_size(contract.get("size"))
            original_width, original_height = width, height
            original_sha256 = _sha256(content)
            size_normalization: dict[str, Any] | None = None
            if expected_size is not None and (width, height) != expected_size:
                policy = str(contract.get("size_normalization") or "").strip()
                if policy != "white_matte_contain_to_contract_size":
                    raise McpMaterializationError(
                        "mcp_materialization_output_size_mismatch",
                        detail={
                            "expected_width": expected_size[0],
                            "expected_height": expected_size[1],
                            "artifact_width": width,
                            "artifact_height": height,
                        },
                    )
                try:
                    content = _normalize_image_size(
                        content,
                        image_format=image_format,
                        target_size=expected_size,
                    )
                    width, height = _validate_image(content)
                except Exception as exc:
                    raise McpMaterializationError(
                        "mcp_materialization_output_size_normalization_failed",
                        "The submitted artifact could not be normalized to the frozen rendering size.",
                    ) from exc
                size_normalization = {
                    "policy": policy,
                    "original_width": original_width,
                    "original_height": original_height,
                    "target_width": expected_size[0],
                    "target_height": expected_size[1],
                    "result_width": width,
                    "result_height": height,
                }
            artifact_path = self._artifact_path(str(payload["handoff_id"]), image_format)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(content)
            updated = {
                **payload,
                "status": "submitted",
                "updated_at": _now_iso(),
                "artifact_file": str(artifact_path),
                "artifact_sha256": _sha256(content),
                "artifact_format": image_format,
                "artifact_mime_type": mime_type,
                "artifact_width": width,
                "artifact_height": height,
                **(
                    {
                        "artifact_original_sha256": original_sha256,
                        "artifact_size_normalization": size_normalization,
                    }
                    if size_normalization is not None
                    else {}
                ),
            }
            self._write(self._record_path(str(payload["handoff_id"])), updated)
            return self.public_view(handoff_id)

    def consume(self, handoff_id: str) -> dict[str, Any]:
        with self._lock:
            payload = self._read(handoff_id)
            if payload is None:
                raise McpMaterializationError("mcp_materialization_not_found")
            if payload.get("status") != "submitted":
                raise McpMaterializationError("mcp_materialization_pending")
            artifact_file = Path(str(payload.get("artifact_file") or ""))
            if not artifact_file.is_file():
                raise McpMaterializationError("mcp_materialization_artifact_missing")
            content = artifact_file.read_bytes()
            if _sha256(content) != str(payload.get("artifact_sha256") or ""):
                raise McpMaterializationError("mcp_materialization_artifact_changed")
            updated = {**payload, "status": "consumed", "updated_at": _now_iso(), "consumed_at": _now_iso()}
            self._write(self._record_path(str(payload["handoff_id"])), updated)
            return {
                "artifact_base64": base64.b64encode(content).decode("ascii"),
                "artifact_format": payload.get("artifact_format") or "png",
                "artifact_mime_type": payload.get("artifact_mime_type") or "image/png",
                "artifact_sha256": payload.get("artifact_sha256"),
            }

    def _record_path(self, handoff_id: str) -> Path:
        value = str(handoff_id or "")
        if not value.startswith("mcp_handoff_") or "/" in value or "\\" in value:
            raise McpMaterializationError("mcp_materialization_id_invalid")
        return self.storage_root / f"{value}.json"

    def _artifact_path(self, handoff_id: str, image_format: str) -> Path:
        suffix = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[image_format]
        return self.storage_root / f"{handoff_id}.artifact{suffix}"

    def _read(self, handoff_id: str) -> dict[str, Any] | None:
        path = self._record_path(handoff_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) and payload.get("schema_version") == self.schema_version else None

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    @staticmethod
    def _reference_hashes(reference_assets: list[dict[str, Any]]) -> list[str]:
        hashes: list[str] = []
        for item in reference_assets:
            data = dict(item or {})
            declared = str(data.get("sha256") or data.get("content_sha256") or "").strip().lower()
            path = str(data.get("file_path") or data.get("storage_path") or "").strip()
            if not declared and path and Path(path).is_file():
                declared = _sha256(Path(path).read_bytes())
            if not declared:
                raise McpMaterializationError("mcp_materialization_reference_hash_missing")
            hashes.append(declared)
        return hashes

    @staticmethod
    def _safe_reference_contract(reference_assets: list[dict[str, Any]], hashes: list[str]) -> list[dict[str, Any]]:
        safe: list[dict[str, Any]] = []
        for index, item in enumerate(reference_assets):
            data = dict(item or {})
            safe.append(
                {
                    "asset_id": str(data.get("asset_id") or data.get("output_id") or ""),
                    "file_path": str(data.get("file_path") or data.get("storage_path") or ""),
                    "sha256": hashes[index],
                    "role": str(data.get("role") or data.get("source_type") or "reference"),
                }
            )
        return safe

    @staticmethod
    def _safe_rendering_contract(contract: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "renderer",
            "model",
            "size",
            "quality",
            "output_format",
            "count",
            "api_operation",
            "input_fidelity",
            "input_fidelity_required",
            "size_normalization",
        }
        return {key: value for key, value in dict(contract or {}).items() if key in allowed}

    @staticmethod
    def _image_format(content: bytes) -> tuple[str, str]:
        try:
            from PIL import Image
            from io import BytesIO

            with Image.open(BytesIO(content)) as image:
                raw = str(image.format or "").lower()
        except Exception as exc:
            raise McpMaterializationError("mcp_materialization_artifact_invalid") from exc
        if raw == "jpg":
            raw = "jpeg"
        if raw not in {"png", "jpeg", "webp"}:
            raise McpMaterializationError("mcp_materialization_artifact_format_invalid")
        return raw, {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}[raw]
