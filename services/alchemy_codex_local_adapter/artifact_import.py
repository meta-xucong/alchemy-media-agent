"""Controlled materialized-file import for the Doc117 spike."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .contracts import (
    ImportedLocalCandidate,
    LocalArtifactImportRequest,
    LocalJobSpec,
    LocalModeAdapterError,
)
from .provenance import imported_artifact_provenance


class LocalArtifactImporter:
    """Import one image once, with content and source-handle binding."""

    def __init__(self, storage_root: str | Path, *, max_bytes: int = 25 * 1024 * 1024) -> None:
        self.storage_root = Path(storage_root).resolve()
        self.max_bytes = max(1, int(max_bytes))
        self._claims_path = self.storage_root / "artifact_claims.json"

    def import_candidate(
        self,
        request: LocalArtifactImportRequest,
        contract: LocalJobSpec,
    ) -> ImportedLocalCandidate:
        if request.job_id != contract.job_id:
            raise LocalModeAdapterError("codex_local_job_binding_mismatch", "Artifact job does not match the frozen contract.")
        if request.role_id not in contract.role_ids:
            raise LocalModeAdapterError("codex_local_role_binding_mismatch", "Artifact role is not frozen for this job.")

        source_path = self._materialized_file(request.artifact_path)
        size = source_path.stat().st_size
        if size <= 0:
            raise LocalModeAdapterError("codex_local_empty_artifact", "Artifact file is empty.")
        if size > self.max_bytes:
            raise LocalModeAdapterError("codex_local_artifact_too_large", "Artifact exceeds the local import limit.")

        mime_type, width, height = _inspect_image(source_path)
        if mime_type != request.declared_mime_type:
            raise LocalModeAdapterError("codex_local_mime_mismatch", "Declared image MIME type does not match file pixels.")
        digest = _sha256_file(source_path)
        source_handle_digest = _source_handle_digest(source_path)
        claims = self._load_claims()
        self._reject_existing_claim(claims, request=request, digest=digest, source_handle_digest=source_handle_digest)

        candidate_id = f"codex_local_candidate_{digest[:24]}"
        suffix = ".png" if mime_type == "image/png" else ".jpg"
        target = self.storage_root / "jobs" / request.job_id / "candidates" / f"{candidate_id}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_without_overwrite(source_path, target)
        provenance = imported_artifact_provenance(
            job_id=request.job_id,
            project_id=contract.project_id,
            role_id=request.role_id,
            sha256=digest,
            declared_origin=request.declared_origin,
            codex_run_id=request.codex_run_id,
        )
        candidate = ImportedLocalCandidate(
            candidate_id=candidate_id,
            job_id=request.job_id,
            role_id=request.role_id,
            imported_path=target,
            sha256=digest,
            mime_type=mime_type,
            width=width,
            height=height,
            provenance=provenance,
        )
        claims.append(
            {
                "job_id": request.job_id,
                "role_id": request.role_id,
                "candidate_id": candidate_id,
                "sha256": digest,
                "source_handle_digest": source_handle_digest,
                "imported_path": str(target),
            }
        )
        self._save_claims(claims)
        return candidate

    def _materialized_file(self, value: Path) -> Path:
        try:
            path = value.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise LocalModeAdapterError("codex_local_artifact_missing", "Artifact must be a readable materialized local file.") from exc
        if value.is_symlink() or not path.is_file():
            raise LocalModeAdapterError("codex_local_artifact_not_materialized", "Artifact must be a regular local file, not a link or preview.")
        return path

    def _load_claims(self) -> list[dict[str, Any]]:
        if not self._claims_path.exists():
            return []
        try:
            payload = json.loads(self._claims_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalModeAdapterError("codex_local_claim_store_unreadable", "Local artifact claim store is unreadable.") from exc
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise LocalModeAdapterError("codex_local_claim_store_unreadable", "Local artifact claim store is invalid.")
        return payload

    def _save_claims(self, claims: list[dict[str, Any]]) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        temporary = self._claims_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(claims, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self._claims_path)

    @staticmethod
    def _reject_existing_claim(
        claims: list[dict[str, Any]],
        *,
        request: LocalArtifactImportRequest,
        digest: str,
        source_handle_digest: str,
    ) -> None:
        for claim in claims:
            same_source = claim.get("source_handle_digest") == source_handle_digest
            same_content = claim.get("sha256") == digest
            if not same_source and not same_content:
                continue
            if str(claim.get("job_id") or "") != request.job_id:
                raise LocalModeAdapterError("codex_local_artifact_cross_job", "Artifact content or handle is already bound to another job.")
            raise LocalModeAdapterError("codex_local_artifact_duplicate", "Artifact is already imported for this local job.")


def _copy_without_overwrite(source: Path, target: Path) -> None:
    if target.exists():
        raise LocalModeAdapterError("codex_local_artifact_duplicate", "Target candidate already exists.")
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(target)
    except OSError as exc:
        raise LocalModeAdapterError("codex_local_artifact_copy_failed", "Artifact could not be copied into local storage.") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_handle_digest(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def _inspect_image(path: Path) -> tuple[str, int, int]:
    with path.open("rb") as handle:
        header = handle.read(64 * 1024)
    if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        return _validated_dimensions("image/png", width, height)
    if header.startswith(b"\xff\xd8"):
        dimensions = _jpeg_dimensions(header)
        if dimensions is not None:
            return _validated_dimensions("image/jpeg", *dimensions)
    raise LocalModeAdapterError("codex_local_not_an_image", "Artifact is not a supported PNG or JPEG image.")


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    position = 2
    while position + 9 < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            return None
        marker = data[position]
        position += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            return None
        segment_length = int.from_bytes(data[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > len(data):
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if segment_length < 7:
                return None
            height = int.from_bytes(data[position + 3 : position + 5], "big")
            width = int.from_bytes(data[position + 5 : position + 7], "big")
            return width, height
        position += segment_length
    return None


def _validated_dimensions(mime_type: str, width: int, height: int) -> tuple[str, int, int]:
    if width <= 0 or height <= 0 or width > 16_384 or height > 16_384:
        raise LocalModeAdapterError("codex_local_invalid_dimensions", "Artifact dimensions are outside the local safety limit.")
    return mime_type, width, height
