"""Public-safe contracts for the Doc130 canonical-prompt MCP planner."""

from __future__ import annotations

from dataclasses import dataclass
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
    "reference_declarations",
}
_ALLOWED_REFERENCE_FIELDS = {"channel", "attached_in_current_codex_conversation"}
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_SENSITIVE_KEY_FRAGMENTS = ("apikey", "secret", "token", "password", "authorization", "credential")
_HARD_REFERENCE_CHANNELS = frozenset({"portrait_identity", "product_truth", "nonhuman_identity"})


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
class NativeReferenceDeclaration:
    """A declaration about a Codex-conversation attachment, never a file handle."""

    channel: str
    attached_in_current_codex_conversation: bool

    @property
    def required(self) -> bool:
        """Hard truth channels are a contract, never a caller-selected flag."""

        return self.channel in _HARD_REFERENCE_CHANNELS

    @classmethod
    def from_value(cls, value: Any) -> "NativeReferenceDeclaration":
        if not isinstance(value, dict) or set(value) - _ALLOWED_REFERENCE_FIELDS:
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_declaration_invalid",
                "Reference declarations may contain only channel and attachment state.",
            )
        _reject_sensitive_structured_keys(value)
        channel = str(value.get("channel") or "").strip().lower()
        if not _IDENTIFIER.fullmatch(channel):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_declaration_invalid",
                "Reference declaration channel is invalid.",
            )
        attached = value.get("attached_in_current_codex_conversation")
        if not isinstance(attached, bool):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_declaration_invalid",
                "Reference declaration attachment state must be boolean.",
            )
        return cls(channel=channel, attached_in_current_codex_conversation=attached)


@dataclass(frozen=True)
class NativeImageGenPlanRequest:
    """The entire public MCP input contract for Doc130 canonical prompt parity."""

    user_input: str
    template_id: str
    requested_image_count: int
    requested_image_size: str | None
    reference_declarations: tuple[NativeReferenceDeclaration, ...]

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
        declarations_value = value.get("reference_declarations")
        if not isinstance(declarations_value, list):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_declaration_invalid",
                "Reference declarations must be a list.",
            )
        declarations = tuple(NativeReferenceDeclaration.from_value(item) for item in declarations_value)
        if len({item.channel for item in declarations}) != len(declarations):
            raise CodexNativeImageGenError(
                "codex_native_imagegen_reference_declaration_invalid",
                "Reference declaration channels must be unique.",
            )
        return cls(
            user_input=user_input,
            template_id=template_id,
            requested_image_count=count,
            requested_image_size=size,
            reference_declarations=declarations,
        )


def public_reference_instructions(declarations: tuple[NativeReferenceDeclaration, ...]) -> list[str]:
    """Tell Codex how to use conversation attachments without exposing paths."""

    if not declarations:
        return ["No conversation reference was declared; do not invent or substitute a reference attachment."]
    instructions: list[str] = []
    for declaration in declarations:
        if declaration.attached_in_current_codex_conversation:
            instructions.append(
                f"Use the exact current-conversation attachment declared for {declaration.channel} in the native image tool call; preserve that channel and do not substitute another image."
            )
        elif declaration.required:
            instructions.append(f"The required {declaration.channel} reference is absent; do not create an image.")
        else:
            instructions.append(f"No {declaration.channel} attachment was declared; do not infer or substitute one.")
    return instructions
