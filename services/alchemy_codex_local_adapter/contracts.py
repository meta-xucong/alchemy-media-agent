"""Small, local-only contracts for the Doc117 technical spike.

These models intentionally do not import the V3 Web application.  A future
Phase C bridge may construct them from a frozen V3 envelope, but doing so is
not required to import, test, or remove this sidecar package.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any


LOCAL_EXECUTION_CHANNEL = "codex_local"
LOCAL_CREATIVE_DIRECTION_OWNER = "codex_local_agent"
PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER = "platform_openai_gpt_image_2"
PLATFORM_OPENAI_GPT_IMAGE_2_MODEL = "gpt-image-2"
# Kept only to make historical Phase A records readable.  Phase B2 never emits
# this value because no supported Codex Desktop artifact handoff exists.
LEGACY_CODEX_IMAGEGEN_RENDERER = "codex_imagegen"
LOCAL_RENDERER = PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER
LOCAL_EVIDENCE_SCOPE = "codex_local_development_evidence"

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class LocalModeAdapterError(RuntimeError):
    """Structured, public-safe failure from the local adapter."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class LocalModeDisabledError(LocalModeAdapterError):
    def __init__(self) -> None:
        super().__init__("codex_local_mode_disabled", "Codex Local Mode is disabled.")


def require_identifier(value: str, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not _IDENTIFIER.fullmatch(cleaned):
        raise LocalModeAdapterError("codex_local_invalid_identifier", f"Invalid {field_name}.")
    return cleaned


def _clean_direction(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise LocalModeAdapterError("codex_local_direction_required", "Creative direction is required.")
    if len(cleaned) > 8_000:
        raise LocalModeAdapterError("codex_local_direction_too_long", "Creative direction exceeds the local limit.")
    return cleaned


@dataclass(frozen=True)
class LocalJobSpec:
    """An already-frozen Local Mode job supplied by an explicit caller."""

    job_id: str
    project_id: str
    template_id: str
    scenario_id: str
    protected_user_intent: str
    role_ids: tuple[str, ...]
    normalized_intent: dict[str, Any]
    capability_execution_envelope: dict[str, Any]
    resolved_constraint_ledger: dict[str, Any]
    permitted_reference_files: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", require_identifier(self.job_id, "job_id"))
        object.__setattr__(self, "project_id", require_identifier(self.project_id, "project_id"))
        object.__setattr__(self, "template_id", require_identifier(self.template_id, "template_id"))
        object.__setattr__(self, "scenario_id", require_identifier(self.scenario_id, "scenario_id"))
        roles = tuple(require_identifier(item, "role_id") for item in self.role_ids)
        if not roles or len(roles) != len(set(roles)):
            raise LocalModeAdapterError("codex_local_invalid_role_binding", "Frozen roles must be non-empty and unique.")
        if not str(self.protected_user_intent or "").strip():
            raise LocalModeAdapterError("codex_local_protected_intent_required", "Protected user intent is required.")
        object.__setattr__(self, "role_ids", roles)

    def safe_render_contract(self) -> dict[str, Any]:
        """Expose only frozen, caller-owned data and never credentials."""

        return {
            "job_id": self.job_id,
            "project_id": self.project_id,
            "template_id": self.template_id,
            "scenario_id": self.scenario_id,
            "protected_user_intent": self.protected_user_intent,
            "role_ids": list(self.role_ids),
            "requested_output_count": len(self.role_ids),
            "normalized_intent": _public_copy(self.normalized_intent),
            "capability_execution_envelope": _public_copy(self.capability_execution_envelope),
            "resolved_constraint_ledger": _public_copy(self.resolved_constraint_ledger),
            "permitted_reference_files": list(self.permitted_reference_files),
        }

    def storage_record(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_storage_record(cls, value: dict[str, Any]) -> "LocalJobSpec":
        return cls(
            job_id=str(value.get("job_id") or ""),
            project_id=str(value.get("project_id") or ""),
            template_id=str(value.get("template_id") or ""),
            scenario_id=str(value.get("scenario_id") or ""),
            protected_user_intent=str(value.get("protected_user_intent") or ""),
            role_ids=tuple(value.get("role_ids") or ()),
            normalized_intent=dict(value.get("normalized_intent") or {}),
            capability_execution_envelope=dict(value.get("capability_execution_envelope") or {}),
            resolved_constraint_ledger=dict(value.get("resolved_constraint_ledger") or {}),
            permitted_reference_files=tuple(value.get("permitted_reference_files") or ()),
        )


FrozenLocalJobContract = LocalJobSpec


@dataclass(frozen=True)
class PlatformRenderedImage:
    """A final API image response before controlled local materialization."""

    image_bytes: bytes = field(repr=False)
    mime_type: str = "image/png"
    request_summary: dict[str, Any] = field(default_factory=dict)
    response_summary: dict[str, Any] = field(default_factory=dict)
    renderer: str = PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER
    renderer_model: str = PLATFORM_OPENAI_GPT_IMAGE_2_MODEL


@dataclass(frozen=True)
class ImportedLocalCandidate:
    candidate_id: str
    job_id: str
    role_id: str
    imported_path: Path
    sha256: str
    mime_type: str
    width: int
    height: int
    provenance: dict[str, Any] = field(default_factory=dict)

    def storage_record(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["imported_path"] = str(self.imported_path)
        return payload

    @classmethod
    def from_storage_record(cls, value: dict[str, Any]) -> "ImportedLocalCandidate":
        return cls(
            candidate_id=str(value.get("candidate_id") or ""),
            job_id=str(value.get("job_id") or ""),
            role_id=str(value.get("role_id") or ""),
            imported_path=Path(str(value.get("imported_path") or "")),
            sha256=str(value.get("sha256") or ""),
            mime_type=str(value.get("mime_type") or ""),
            width=int(value.get("width") or 0),
            height=int(value.get("height") or 0),
            provenance=dict(value.get("provenance") or {}),
        )


def _public_copy(value: Any) -> Any:
    """Redact credential-like fields even if an invalid caller supplied them."""

    sensitive_fragments = ("api_key", "apikey", "secret", "token", "password", "authorization", "credential")
    if isinstance(value, dict):
        return {
            str(key): _public_copy(item)
            for key, item in value.items()
            if not any(fragment in str(key).lower() for fragment in sensitive_fragments)
        }
    if isinstance(value, list):
        return [_public_copy(item) for item in value]
    if isinstance(value, tuple):
        return [_public_copy(item) for item in value]
    return value
