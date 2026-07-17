"""Public-safe contracts for the Doc130/131 canonical-prompt MCP planner."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import mimetypes
from pathlib import Path
import re
from typing import Any


NATIVE_EXECUTION_CHANNEL = "codex_native_imagegen"
NATIVE_PLANNING_AUTHORITY = "alchemy_v3_canonical_provider_materialization"
NATIVE_CREATIVE_DIRECTION_OWNER = "remote_v3_llm_brain"
NATIVE_RENDERER = "codex_builtin_imagegen"
CONVERSATION_ONLY_DELIVERY_STATE = "conversation_only_not_certified"

_ALLOWED_TOP_LEVEL_FIELDS = {
    "user_input",
    "template_id",
    "requested_image_count",
    "requested_image_size",
    "reference_inputs",
}
_SPECIALIZED_ALLOWED_TOP_LEVEL_FIELDS = {
    *_ALLOWED_TOP_LEVEL_FIELDS,
    "platform_profile",
    "photography_mode",
    "photographer_profile_id",
}
_PROFESSIONAL_ALLOWED_TOP_LEVEL_FIELDS = {
    *_ALLOWED_TOP_LEVEL_FIELDS,
    "project_id",
    "people_asset_id",
    "professional_identity_view_ids",
    "platform_profile",
    "photography_mode",
    "photographer_profile_id",
}
_ALLOWED_REFERENCE_FIELDS = {"channel", "file_path"}
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_SENSITIVE_KEY_FRAGMENTS = ("apikey", "secret", "token", "password", "authorization", "credential")
_HARD_REFERENCE_CHANNELS = frozenset(
    {"portrait_identity", "selected_identity_reference", "product_truth", "nonhuman_identity"}
)


class CodexNativeImageGenError(RuntimeError):
    """Structured, public-safe Local Mode error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class CodexNativeImageGenDisabledError(CodexNativeImageGenError):
    def __init__(self) -> None:
        super().__init__("codex_native_imagegen_mode_disabled", "Codex Native ImageGen Mode is disabled.")


class CodexNativeImageGenBlockedError(CodexNativeImageGenError):
    """A fail-closed planning decision; no image has been created."""


def _sensitive_mapping_key(value: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(value).lower())
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _reject_sensitive_structured_keys(value: Any) -> None:
    """Inspect mapping keys only; never infer secrets from normal user text."""

    if isinstance(value, dict):
        for key, nested in value.items():
            if _sensitive_mapping_key(key):
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_sensitive_field_forbidden",
                    "Credential-like structured fields are not accepted by Codex Native ImageGen Mode.",
                )
            _reject_sensitive_structured_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_structured_keys(nested)


@dataclass(frozen=True)
class NativeReferenceInput:
    """An explicitly user-authorized local image handed to V3 unchanged.

    The path is not a Codex artifact handle and is never sent to the remote
    Brain.  It is the Local Mode equivalent of a Web upload's materialized
    ``UploadedAssetInfo.file_path``.
    """

    channel: str
    file_path: str
    source_sha256: str

    @property
    def required(self) -> bool:
        """Hard truth channels are a contract, never a caller-selected flag."""

        return self.channel in _HARD_REFERENCE_CHANNELS

    @property
    def asset_id(self) -> str:
        return f"codex_local_reference_{self.source_sha256[:24]}"

    @classmethod
    def from_value(cls, value: Any) -> "NativeReferenceInput":
        if not isinstance(value, dict) or set(value) - _ALLOWED_REFERENCE_FIELDS:
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_input_invalid",
                "Reference inputs may contain only channel and a local file path.",
            )
        _reject_sensitive_structured_keys(value)
        channel = str(value.get("channel") or "").strip().lower()
        if not _IDENTIFIER.fullmatch(channel):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_input_invalid",
                "Reference input channel is invalid.",
            )
        raw_path = value.get("file_path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_path_required",
                "A reference image needs a readable local file path before V3 can admit it.",
            )
        try:
            path = Path(raw_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_path_unavailable",
                "The declared reference image is not available as a readable local file.",
            ) from None
        if not path.is_file():
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_path_unavailable",
                "The declared reference image is not available as a readable local file.",
            )
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        except OSError:
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_path_unavailable",
                "The declared reference image could not be read.",
            ) from None
        return cls(channel=channel, file_path=str(path), source_sha256=digest.hexdigest())


@dataclass(frozen=True)
class NativeImageGenPlanRequest:
    """The entire public MCP input contract for Doc130 canonical prompt parity."""

    user_input: str
    template_id: str
    requested_image_count: int
    requested_image_size: str | None
    reference_inputs: tuple[NativeReferenceInput, ...]

    @classmethod
    def from_mcp_arguments(cls, value: Any) -> "NativeImageGenPlanRequest":
        if not isinstance(value, dict) or set(value) - _ALLOWED_TOP_LEVEL_FIELDS:
            raise CodexNativeImageGenError(
                "codex_native_imagegen_invalid_input",
                "Only the documented Codex Native ImageGen planning fields are accepted.",
            )
        if missing := (_ALLOWED_TOP_LEVEL_FIELDS - set(value)):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_invalid_input",
                f"Missing required planning fields: {', '.join(sorted(missing))}.",
            )
        _reject_sensitive_structured_keys(value)
        raw_user_input = value.get("user_input")
        if not isinstance(raw_user_input, str):
            raise CodexNativeImageGenError("codex_native_imagegen_user_input_required", "User input must be a string.")
        user_input = raw_user_input.strip()
        if not user_input:
            raise CodexNativeImageGenError("codex_native_imagegen_user_input_required", "User input is required.")
        if len(user_input) > 8_000:
            raise CodexNativeImageGenError("codex_native_imagegen_user_input_too_long", "User input exceeds the planning limit.")
        raw_template_id = value.get("template_id")
        if not isinstance(raw_template_id, str):
            raise CodexNativeImageGenError("codex_native_imagegen_template_invalid", "Template ID must be a string.")
        template_id = raw_template_id.strip()
        if not _IDENTIFIER.fullmatch(template_id):
            raise CodexNativeImageGenError("codex_native_imagegen_template_invalid", "Template ID is invalid.")
        raw_count = value.get("requested_image_count")
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            raise CodexNativeImageGenError("codex_native_imagegen_count_invalid", "Requested image count must be a positive integer.") from None
        if isinstance(raw_count, bool) or not 1 <= count <= 16:
            raise CodexNativeImageGenError("codex_native_imagegen_count_invalid", "Requested image count is outside the supported planning range.")
        raw_size = value.get("requested_image_size")
        if raw_size is not None and not isinstance(raw_size, str):
            raise CodexNativeImageGenError("codex_native_imagegen_size_invalid", "Requested image size must be a string or null.")
        size = raw_size.strip() if raw_size is not None else None
        if size == "":
            size = None
        if size is not None and (len(size) > 64 or not re.fullmatch(r"(?:auto|[1-9][0-9]{1,4}x[1-9][0-9]{1,4})", size.lower())):
            raise CodexNativeImageGenError("codex_native_imagegen_size_invalid", "Requested image size is invalid.")
        references_value = value.get("reference_inputs")
        if not isinstance(references_value, list):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_input_invalid",
                "Reference inputs must be a list.",
            )
        # A channel describes source ownership, not a one-image slot.  A
        # product's front, back, detail, or alternate angle can all be
        # product truth and must reach the normal V3 asset admission path in
        # the exact user-supplied order.  Web Mode accepts that evidence as
        # separate UploadedAssetInfo records; Local Mode must not discard it
        # merely because the evidence has one shared semantic owner.
        references = tuple(NativeReferenceInput.from_value(item) for item in references_value)
        return cls(
            user_input=user_input,
            template_id=template_id,
            requested_image_count=count,
            requested_image_size=size,
            reference_inputs=references,
        )


@dataclass(frozen=True)
class NativeSpecializedImageGenPlanRequest:
    """Public, conversation-only admission for one frozen specialist plan.

    This deliberately is not an extension of the General tool.  E-Commerce
    requires an explicit platform-evidence selector, while Photography needs
    an explicit structural delivery mode and an immutable profile decision.
    The adapter may only pin the existing General Photography default; named
    profiles remain a Project/API-owned binding and therefore fail closed
    here instead of being imitated by a local selector.
    """

    user_input: str
    template_id: str
    requested_image_count: int
    requested_image_size: str | None
    reference_inputs: tuple[NativeReferenceInput, ...]
    platform_profile: str | None
    photography_mode: str | None
    photographer_profile_id: str | None

    @classmethod
    def from_mcp_arguments(cls, value: Any) -> "NativeSpecializedImageGenPlanRequest":
        if not isinstance(value, dict) or set(value) - _SPECIALIZED_ALLOWED_TOP_LEVEL_FIELDS:
            raise CodexNativeImageGenError(
                "codex_native_imagegen_invalid_input",
                "Only the documented frozen specialized-plan fields are accepted.",
            )
        if missing := (_SPECIALIZED_ALLOWED_TOP_LEVEL_FIELDS - set(value)):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_invalid_input",
                f"Missing required planning fields: {', '.join(sorted(missing))}.",
            )

        # Reuse the stable General request parser for every shared field.  It
        # also keeps sensitive-field rejection and reference hashing exactly
        # identical between the two public MCP tools.
        common = NativeImageGenPlanRequest.from_mcp_arguments(
            {key: value[key] for key in _ALLOWED_TOP_LEVEL_FIELDS}
        )

        def optional_identifier(field: str) -> str | None:
            raw = value.get(field)
            if raw is None:
                return None
            if not isinstance(raw, str):
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_specialized_input_invalid",
                    f"{field} must be a string or null.",
                )
            cleaned = raw.strip()
            if not cleaned or not _IDENTIFIER.fullmatch(cleaned):
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_specialized_input_invalid",
                    f"{field} is invalid.",
                )
            return cleaned

        request = cls(
            user_input=common.user_input,
            template_id=common.template_id,
            requested_image_count=common.requested_image_count,
            requested_image_size=common.requested_image_size,
            reference_inputs=common.reference_inputs,
            platform_profile=optional_identifier("platform_profile"),
            photography_mode=optional_identifier("photography_mode"),
            photographer_profile_id=optional_identifier("photographer_profile_id"),
        )
        if request.template_id == "ecommerce_template":
            if request.platform_profile is None:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_platform_profile_required",
                    "E-Commerce Local Mode requires an explicit platform profile as factual evidence.",
                )
            if request.photography_mode is not None or request.photographer_profile_id is not None:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_specialized_input_invalid",
                    "Photography controls are not accepted for E-Commerce Local Mode.",
                )
        elif request.template_id == "photographer_template":
            if request.platform_profile is not None:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_specialized_input_invalid",
                    "Platform controls are not accepted for Photography Local Mode.",
                )
            if request.photography_mode not in {"single_hero", "reference_reshoot", "professional_set"}:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_photography_mode_required",
                    "Photography Local Mode requires single_hero, reference_reshoot, or professional_set.",
                )
            expected_count = 3 if request.photography_mode == "professional_set" else 1
            if request.requested_image_count != expected_count:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_count_mismatch",
                    "The requested Photography output count does not match its frozen structural delivery mode.",
                )
            if request.photographer_profile_id not in {None, "general_photography"}:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_named_profile_project_binding_required",
                    "A named Photography profile requires the existing Project/API immutable binding and is unavailable in Local Mode.",
                )
        else:
            raise CodexNativeImageGenError(
                "codex_native_imagegen_template_invalid",
                "Frozen specialized Local Mode supports only E-Commerce or Photography templates.",
            )
        return request


@dataclass(frozen=True)
class NativeProfessionalImageGenPlanRequest:
    """Public Professional Mode selectors for one frozen canonical plan.

    ``project_id`` and ``people_asset_id`` are selectors only.  The MCP
    caller cannot provide the binding, pack version, job id, prompt, provider
    metadata, or any storage handle; an embedding host must resolve those
    server-owned records through the planner's trusted resolver seam.
    """

    user_input: str
    template_id: str
    requested_image_count: int
    requested_image_size: str | None
    reference_inputs: tuple[NativeReferenceInput, ...]
    project_id: str
    people_asset_id: str
    professional_identity_view_ids: tuple[str, ...]
    platform_profile: str | None = None
    photography_mode: str | None = None
    photographer_profile_id: str | None = None

    @classmethod
    def from_mcp_arguments(cls, value: Any) -> "NativeProfessionalImageGenPlanRequest":
        if not isinstance(value, dict) or set(value) - _PROFESSIONAL_ALLOWED_TOP_LEVEL_FIELDS:
            raise CodexNativeImageGenError(
                "codex_native_imagegen_invalid_input",
                "Only the documented Professional frozen-plan fields are accepted.",
            )
        required = {
            *_ALLOWED_TOP_LEVEL_FIELDS,
            "project_id",
            "people_asset_id",
            "professional_identity_view_ids",
        }
        if missing := (required - set(value)):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_invalid_input",
                f"Missing required Professional planning fields: {', '.join(sorted(missing))}.",
            )
        _reject_sensitive_structured_keys(value)
        common = NativeImageGenPlanRequest.from_mcp_arguments(
            {key: value[key] for key in _ALLOWED_TOP_LEVEL_FIELDS}
        )

        def identifier(field: str) -> str:
            raw = value.get(field)
            if not isinstance(raw, str) or not _IDENTIFIER.fullmatch(raw.strip()):
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_professional_input_invalid",
                    f"{field} must be a valid identifier.",
                )
            return raw.strip()

        raw_view_ids = value.get("professional_identity_view_ids")
        if not isinstance(raw_view_ids, list) or not 1 <= len(raw_view_ids) <= 3:
            raise CodexNativeImageGenError(
                "codex_native_imagegen_professional_views_invalid",
                "Professional Mode requires one to three selected active identity view IDs.",
            )
        view_ids: list[str] = []
        for raw_view_id in raw_view_ids:
            if not isinstance(raw_view_id, str) or not _IDENTIFIER.fullmatch(raw_view_id.strip()):
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_professional_views_invalid",
                    "Professional identity view IDs must be valid identifiers.",
                )
            view_id = raw_view_id.strip()
            if view_id in view_ids:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_professional_views_invalid",
                    "Professional identity view IDs must be unique.",
                )
            view_ids.append(view_id)

        def optional_identifier(field: str) -> str | None:
            raw = value.get(field)
            if raw is None:
                return None
            if not isinstance(raw, str) or not _IDENTIFIER.fullmatch(raw.strip()):
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_professional_input_invalid",
                    f"{field} must be a valid identifier or null.",
                )
            return raw.strip()

        platform_profile = optional_identifier("platform_profile")
        photography_mode = optional_identifier("photography_mode")
        photographer_profile_id = optional_identifier("photographer_profile_id")
        if common.template_id == "ecommerce_template":
            if platform_profile is None:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_platform_profile_required",
                    "Professional E-Commerce planning requires an explicit platform profile.",
                )
            if photography_mode is not None or photographer_profile_id is not None:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_professional_input_invalid",
                    "Photography controls are not accepted for E-Commerce Professional planning.",
                )
        elif common.template_id == "photographer_template":
            if platform_profile is not None:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_professional_input_invalid",
                    "Platform controls are not accepted for Photography Professional planning.",
                )
            if photography_mode not in {"single_hero", "reference_reshoot", "professional_set"}:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_photography_mode_required",
                    "Professional Photography planning requires an explicit photography mode.",
                )
            expected_count = 3 if photography_mode == "professional_set" else 1
            if common.requested_image_count != expected_count:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_count_mismatch",
                    "The requested Photography output count does not match its frozen structural mode.",
                )
            if photographer_profile_id not in {None, "general_photography"}:
                raise CodexNativeImageGenError(
                    "codex_native_imagegen_named_profile_project_binding_required",
                    "A named Photography profile requires the existing Project/API immutable binding.",
                )
        elif common.template_id != "general_template":
            raise CodexNativeImageGenError(
                "codex_native_imagegen_template_invalid",
                "Professional frozen planning supports only the existing General, E-Commerce, or Photography templates.",
            )
        elif any(item is not None for item in (platform_profile, photography_mode, photographer_profile_id)):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_professional_input_invalid",
                "Specialized controls are not accepted for General Professional planning.",
            )

        return cls(
            user_input=common.user_input,
            template_id=common.template_id,
            requested_image_count=common.requested_image_count,
            requested_image_size=common.requested_image_size,
            reference_inputs=common.reference_inputs,
            project_id=identifier("project_id"),
            people_asset_id=identifier("people_asset_id"),
            professional_identity_view_ids=tuple(view_ids),
            platform_profile=platform_profile,
            photography_mode=photography_mode,
            photographer_profile_id=photographer_profile_id,
        )


def reference_role_for_channel(channel: str) -> str:
    """Map only input provenance channels to existing V3 asset roles."""

    return {
        "portrait_identity": "face_reference",
        # Professional M5 serial stages use this existing face-reference role
        # for reviewed generated winners.  The channel name keeps the source
        # ownership explicit without inventing a new shared asset enum.
        "selected_identity_reference": "face_reference",
        "product_truth": "product_reference",
        "nonhuman_identity": "nonhuman_identity_reference",
        "style_reference": "style_reference",
        "background_reference": "background_reference",
        "composition_reference": "composition_reference",
        "color_reference": "color_reference",
        "negative_reference": "negative_reference",
    }.get(channel, "unknown_reference")


def reference_mime_type(file_path: str) -> str | None:
    """File extension is only descriptive; V3 performs real image admission."""

    return mimetypes.guess_type(file_path)[0]
