"""Controlled API-response import for the Doc117 Phase B2 spike.

The importer deliberately has no public path-based import method.  Only a
``PlatformRenderedImage`` returned by the local renderer can enter its private
staging directory, then be copied into durable Local Mode storage.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import secrets
import shutil
from typing import Any

from .contracts import (
    ImportedLocalCandidate,
    LocalJobSpec,
    LocalModeAdapterError,
    PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER,
    PlatformRenderedImage,
    redact_sensitive_structured_fields,
)
from .provenance import imported_artifact_provenance


@dataclass(frozen=True)
class StagedPlatformArtifact:
    """An in-memory capability proving importer-owned API materialization."""

    control_token: str
    source_path: Path
    mime_type: str
    rendered: PlatformRenderedImage


class LocalArtifactImporter:
    """Import a renderer-materialized image once, with content/job/role binding."""

    def __init__(self, storage_root: str | Path, *, max_bytes: int = 25 * 1024 * 1024) -> None:
        self.storage_root = Path(storage_root).resolve()
        self.max_bytes = max(1, int(max_bytes))
        self._claims_path = self.storage_root / "artifact_claims.json"
        self._staging_root = self.storage_root / "_controlled_staging" / "platform"
        self._staged_artifacts: dict[str, StagedPlatformArtifact] = {}

    def stage_platform_response(self, rendered: PlatformRenderedImage) -> StagedPlatformArtifact:
        """Write API bytes into importer-owned staging; never accept caller paths."""

        if rendered.renderer != PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER:
            raise LocalModeAdapterError("codex_local_platform_renderer_origin_invalid", "Only the official Platform renderer may stage an artifact.")
        if rendered.mime_type not in {"image/png", "image/jpeg"}:
            raise LocalModeAdapterError("codex_local_platform_renderer_mime_mismatch", "Platform response MIME type is unsupported.")
        if not rendered.image_bytes:
            raise LocalModeAdapterError("codex_local_platform_renderer_empty_response", "Platform response did not contain image bytes.")
        if len(rendered.image_bytes) > self.max_bytes:
            raise LocalModeAdapterError("codex_local_artifact_too_large", "Platform image exceeds the local import limit.")

        # Never retain a credential-like key from a mocked or future transport
        # summary in the staging object that later feeds durable provenance.
        rendered = PlatformRenderedImage(
            image_bytes=rendered.image_bytes,
            mime_type=rendered.mime_type,
            request_summary=redact_sensitive_structured_fields(rendered.request_summary),
            response_summary=redact_sensitive_structured_fields(rendered.response_summary),
            renderer=rendered.renderer,
            renderer_model=rendered.renderer_model,
        )

        self._staging_root.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(24)
        suffix = ".png" if rendered.mime_type == "image/png" else ".jpg"
        source_path = self._staging_root / f"platform_{token}{suffix}"
        temporary = source_path.with_suffix(f"{suffix}.tmp")
        try:
            temporary.write_bytes(rendered.image_bytes)
            temporary.replace(source_path)
            detected_mime, _, _ = _inspect_image(source_path)
        except LocalModeAdapterError:
            source_path.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)
            raise
        except OSError as exc:
            source_path.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)
            raise LocalModeAdapterError("codex_local_platform_renderer_materialization_failed", "Platform image could not be materialized locally.") from exc
        if detected_mime != rendered.mime_type:
            source_path.unlink(missing_ok=True)
            raise LocalModeAdapterError("codex_local_platform_renderer_mime_mismatch", "Platform response pixels did not match the requested output format.")

        staged = StagedPlatformArtifact(
            control_token=token,
            source_path=source_path,
            mime_type=detected_mime,
            rendered=rendered,
        )
        self._staged_artifacts[token] = staged
        return staged

    def import_staged_platform_candidate(
        self,
        *,
        job_id: str,
        role_id: str,
        contract: LocalJobSpec,
        staged: StagedPlatformArtifact,
    ) -> ImportedLocalCandidate:
        """Bind one controlled staging file to exactly one frozen job role."""

        if job_id != contract.job_id:
            raise LocalModeAdapterError("codex_local_job_binding_mismatch", "Artifact job does not match the frozen contract.")
        if role_id not in contract.role_ids:
            raise LocalModeAdapterError("codex_local_role_binding_mismatch", "Artifact role is not frozen for this job.")
        registered = self._staged_artifacts.get(staged.control_token)
        if registered != staged:
            raise LocalModeAdapterError("codex_local_external_artifact_import_forbidden", "Only importer-controlled API materializations may be imported.")

        try:
            try:
                source_path = staged.source_path.resolve(strict=True)
            except (FileNotFoundError, OSError) as exc:
                raise LocalModeAdapterError("codex_local_artifact_missing", "Controlled staged artifact is no longer available.") from exc
            if self._staging_root.resolve() not in source_path.parents or not source_path.is_file():
                raise LocalModeAdapterError("codex_local_external_artifact_import_forbidden", "Artifact is outside controlled Platform staging.")
            size = source_path.stat().st_size
            if size <= 0:
                raise LocalModeAdapterError("codex_local_empty_artifact", "Artifact file is empty.")
            if size > self.max_bytes:
                raise LocalModeAdapterError("codex_local_artifact_too_large", "Artifact exceeds the local import limit.")
            mime_type, width, height = _inspect_image(source_path)
            if mime_type != staged.mime_type:
                raise LocalModeAdapterError("codex_local_platform_renderer_mime_mismatch", "Staged artifact MIME type changed before import.")
            digest = _sha256_file(source_path)
            source_handle_digest = _source_handle_digest(source_path)
            claims = self._load_claims()
            self._reject_existing_claim(claims, job_id=job_id, digest=digest, source_handle_digest=source_handle_digest)

            candidate_id = f"codex_local_candidate_{digest[:24]}"
            suffix = ".png" if mime_type == "image/png" else ".jpg"
            target = self.storage_root / "jobs" / job_id / "candidates" / f"{candidate_id}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_without_overwrite(source_path, target)
            provenance = imported_artifact_provenance(
                job_id=job_id,
                project_id=contract.project_id,
                role_id=role_id,
                sha256=digest,
                renderer=staged.rendered.renderer,
                renderer_model=staged.rendered.renderer_model,
                request_summary=staged.rendered.request_summary,
                response_summary=staged.rendered.response_summary,
            )
            candidate = ImportedLocalCandidate(
                candidate_id=candidate_id,
                job_id=job_id,
                role_id=role_id,
                imported_path=target,
                sha256=digest,
                mime_type=mime_type,
                width=width,
                height=height,
                provenance=provenance,
            )
            claims.append(
                {
                    "job_id": job_id,
                    "role_id": role_id,
                    "candidate_id": candidate_id,
                    "sha256": digest,
                    "source_handle_digest": source_handle_digest,
                    "imported_path": str(target),
                }
            )
            self._save_claims(claims)
            return candidate
        finally:
            self._staged_artifacts.pop(staged.control_token, None)
            staged.source_path.unlink(missing_ok=True)

    @staticmethod
    def reject_uncontrolled_external_import() -> None:
        raise LocalModeAdapterError(
            "codex_local_external_artifact_import_forbidden",
            "Callers cannot import arbitrary system files as Local Mode artifacts.",
        )

    def _load_claims(self) -> list[dict[str, Any]]:
        if not self._claims_path.exists():
            return []
        try:
            payload = json.loads(self._claims_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalModeAdapterError("codex_local_claim_store_unreadable", "Local artifact claim store is unreadable.") from exc
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise LocalModeAdapterError("codex_local_claim_store_unreadable", "Local artifact claim store is invalid.")
        clean_payload = redact_sensitive_structured_fields(payload)
        if clean_payload != payload:
            self._save_claims(clean_payload)
        return clean_payload

    def _save_claims(self, claims: list[dict[str, Any]]) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        temporary = self._claims_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(redact_sensitive_structured_fields(claims), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self._claims_path)

    @staticmethod
    def _reject_existing_claim(
        claims: list[dict[str, Any]],
        *,
        job_id: str,
        digest: str,
        source_handle_digest: str,
    ) -> None:
        for claim in claims:
            same_source = claim.get("source_handle_digest") == source_handle_digest
            same_content = claim.get("sha256") == digest
            if not same_source and not same_content:
                continue
            if str(claim.get("job_id") or "") != job_id:
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
        temporary.unlink(missing_ok=True)
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
