"""Professional Character Card contracts and shared-stage orchestration.

Doc178 deliberately keeps Character Card as an additive state machine.  This
module owns slot/state/dependency contracts and calls injected candidate
generator/reviewer seams; it never authors prompt prose or implements a second
provider, review, retry, selector, or image store.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from ..shared_capabilities.visual_cluster.expression_review import laugh_expression_receipt_allows_slot
from ..shared_capabilities.visual_cluster.review_repair import (
    shared_review_repair_context_from_decision,
)


FACE_SLOT_KEYS = (
    "face.front",
    "face.left_front_25",
    "face.front_three_quarter",
    "face.profile",
    "face.right_front_25",
    # Historical key kept for persisted cards.  User-facing meaning is the
    # opposite front-side 45-degree face view, not a rear/back-of-head view.
    "face.reverse_three_quarter",
    "face.rear_head",
)
EXPRESSION_SLOT_KEYS = ("expression.neutral", "expression.laugh", "expression.anger", "expression.sad")
LEGACY_EXPRESSION_SLOT_KEYS = ("expression.smile",)
ALL_EXPRESSION_SLOT_KEYS = (*EXPRESSION_SLOT_KEYS, *LEGACY_EXPRESSION_SLOT_KEYS)
POSITIVE_EXPRESSION_SLOT_KEY = "expression.laugh"
DEFAULT_EXPRESSION_KEYS = ("laugh", "anger", "sad")
BODY_SLOT_KEYS = ("body.front_full", "body.side_full", "body.rear_full")
BODY_SOURCE_CLASSES = ("observed", "user_described", "brain_inferred")
EXPRESSION_LABELS = {
    "expression.neutral": "中性",
    "expression.laugh": "开心笑",
    "expression.anger": "愤怒",
    "expression.sad": "悲伤",
    "expression.smile": "微笑（旧版）",
}
CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_VERSION = "v3_character_card_slot_success_receipt_v1"
_CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_OWNER = "v3_character_card_shared_runtime"
_SAFE_SHARED_REVIEW_RECEIPT_KEYS = (
    "owner",
    "contract_version",
    "status",
    "expression",
    "framing_baseline",
    "evidence_codes",
    "issue_codes",
    "score_dimensions",
    "framing_delta_dimensions",
)
_CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_KEYS = {
    "owner",
    "receipt_version",
    "module",
    "slot_key",
    "output_id",
    "review_owner",
    "retry_owner",
    "candidate_count",
    "max_bounded_repair_count",
    "bounded_repair_count",
    "final_winner_selection_verified",
    "prompt_reference_parity_verified",
    "shared_review_receipts",
}

CharacterCardSlotKey = Literal[
    "face.front",
    "face.left_front_25",
    "face.front_three_quarter",
    "face.profile",
    "face.right_front_25",
    "face.reverse_three_quarter",
    "face.rear_head",
    "expression.neutral",
    "expression.laugh",
    "expression.smile",
    "expression.anger",
    "expression.sad",
    "body.front_full",
    "body.side_full",
    "body.rear_full",
]
CharacterCardModule = Literal["face_identity", "expression_set", "body_silhouette"]
CharacterCardSlotState = Literal[
    "empty",
    "preparing",
    "reviewing",
    "winner_selected",
    "active",
    "stale",
    "blocked",
]
CharacterCardModuleStatus = Literal[
    "empty",
    "preparing",
    "reviewing",
    "partial",
    "active",
    "stale",
    "blocked",
]
BodySourceClass = Literal["observed", "user_described", "brain_inferred"]
ExpressionKey = Literal["laugh", "smile", "anger", "sad"]
BodySlotKey = Literal["body.front_full", "body.side_full", "body.rear_full"]


class _CharacterCardModel(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")


class CharacterCardRuntimeUnavailable(RuntimeError):
    """A safe, non-provider error for an unconfigured shared stage host."""

    code = "character_card_shared_runtime_unavailable"


class BodySilhouettePublicRequest(_CharacterCardModel):
    """The only body facts a browser may submit for a Character Card stage.

    Asset IDs are resolved server-side.  Natural-language facts remain user
    authored; callers cannot submit paths, prompt fragments, or a structured
    body recipe.
    """

    source_class: BodySourceClass
    body_reference_asset_id: str | None = None
    body_facts: str | None = Field(default=None, max_length=2000)

    @field_validator("body_reference_asset_id")
    @classmethod
    def validate_reference_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or "/" in cleaned or "\\" in cleaned or ":" in cleaned:
            raise ValueError("body reference must be an asset identifier")
        return cleaned

    @field_validator("body_facts")
    @classmethod
    def validate_user_facts(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("body facts must be natural-language text")
        return cleaned

    @model_validator(mode="after")
    def enforce_source_truth(self) -> "BodySilhouettePublicRequest":
        if self.source_class == "observed":
            if not self.body_reference_asset_id or self.body_facts is not None:
                raise ValueError("observed Body Silhouette requires one authorized full-body asset")
        elif self.source_class == "user_described":
            if self.body_reference_asset_id is not None or not self.body_facts:
                raise ValueError("user_described Body Silhouette requires natural-language facts")
        elif self.body_reference_asset_id is not None or self.body_facts is not None:
            raise ValueError("brain_inferred Body Silhouette accepts no observed body facts")
        return self


class CharacterCardSlot(_CharacterCardModel):
    """One independent slot and its reviewed-materialization state."""

    slot_key: CharacterCardSlotKey
    module: CharacterCardModule
    state: CharacterCardSlotState = "empty"
    output_id: str | None = None
    source_candidate_ids: list[str] = Field(default_factory=list)
    source_class: BodySourceClass | None = None
    consent_provenance_id: str | None = None
    lineage_id: str | None = None
    dependency_version_ids: list[str] = Field(default_factory=list)
    review_verified: bool = False
    prompt_reference_parity_verified: bool = False
    # Doc223-D: sanitized success proof for this exact slot/output.  It is
    # projected from the shared runtime receipt and contains no prompts, raw
    # provider/MCP response, local path, image bytes or artifact identifiers.
    shared_runtime_receipt: dict[str, Any] | None = None
    candidate_attempt_count: int = Field(default=0, ge=0, le=4)
    bounded_repair_count: int = Field(default=0, ge=0, le=1)
    explicitly_left_empty: bool = False
    is_alias: bool = False
    alias_of: str | None = None

    @field_validator("source_candidate_ids", "dependency_version_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Character Card provenance IDs must be unique")
        return cleaned

    @model_validator(mode="after")
    def enforce_slot_contract(self) -> "CharacterCardSlot":
        expected_module = self.slot_key.split(".", 1)[0]
        expected_module = {
            "face": "face_identity",
            "expression": "expression_set",
            "body": "body_silhouette",
        }[expected_module]
        if self.module != expected_module:
            raise ValueError("Character Card slot module does not match slot key")
        if self.state == "empty":
            if any(
                (
                    self.output_id,
                    self.source_candidate_ids,
                    self.lineage_id,
                    self.review_verified,
                    self.prompt_reference_parity_verified,
                    self.shared_runtime_receipt,
                    self.is_alias,
                )
            ):
                raise ValueError("empty Character Card slots cannot contain materialized evidence")
            if self.candidate_attempt_count or self.bounded_repair_count:
                raise ValueError("empty Character Card slots cannot contain generation attempts")
        elif self.state in {"winner_selected", "active"}:
            if not self.is_alias and not self.output_id:
                raise ValueError("reviewed Character Card winners require an output")
            if not self.review_verified or not self.prompt_reference_parity_verified:
                raise ValueError("Character Card winners require shared review and prompt/reference parity")
            if self.shared_runtime_receipt is not None:
                validate_character_card_slot_success_receipt(
                    self.shared_runtime_receipt,
                    module=self.module,
                    slot_key=self.slot_key,
                    output_id=str(self.output_id or ""),
                )
        if self.is_alias:
            if self.slot_key != "expression.neutral" or self.alias_of != "face.front":
                raise ValueError("only expression.neutral may alias face.front")
            if self.output_id or self.candidate_attempt_count or self.bounded_repair_count:
                raise ValueError("expression.neutral alias cannot create a generation job")
            if self.shared_runtime_receipt is not None:
                raise ValueError("expression.neutral alias cannot contain a generated-slot receipt")
        elif self.slot_key == "expression.neutral" and self.state != "empty":
            raise ValueError("expression.neutral must alias face.front")
        if self.module == "body_silhouette" and self.state != "empty" and self.source_class is None:
            raise ValueError("body Character Card slots require an explicit source class")
        if self.module == "body_silhouette" and self.state != "empty" and self.source_class == "observed":
            if not str(self.consent_provenance_id or "").strip():
                raise ValueError("observed Body Silhouette winners require consent provenance")
        if self.module != "body_silhouette" and self.source_class is not None:
            raise ValueError("body source class is only valid for Body Silhouette slots")
        if self.module != "body_silhouette" and self.consent_provenance_id is not None:
            raise ValueError("body consent provenance is only valid for Body Silhouette slots")
        if self.bounded_repair_count > self.candidate_attempt_count:
            raise ValueError("bounded repair cannot exceed candidate attempts")
        return self


class CharacterCardState(_CharacterCardModel):
    """The visible, resumable state of all three sibling modules."""

    mode: Literal["professional"] = "professional"
    card_version_id: str
    face_identity_status: CharacterCardModuleStatus = "empty"
    expression_set_status: CharacterCardModuleStatus = "empty"
    body_silhouette_status: CharacterCardModuleStatus = "empty"
    face_identity_version_id: str | None = None
    expression_set_version_id: str | None = None
    body_silhouette_version_id: str | None = None
    face_slots: dict[str, CharacterCardSlot] = Field(default_factory=dict)
    expression_slots: dict[str, CharacterCardSlot] = Field(default_factory=dict)
    body_slots: dict[str, CharacterCardSlot] = Field(default_factory=dict)
    active_version_id: str | None = None
    user_activation_confirmed: bool = False
    expression_activation_confirmed: bool = False
    body_activation_confirmed: bool = False
    append_only_revision: int = Field(default=0, ge=0)
    last_failed_module: CharacterCardModule | None = None
    last_failed_slot_key: CharacterCardSlotKey | None = None
    last_failure_code: str | None = None
    last_failure_attempt_count: int = Field(default=0, ge=0, le=3)
    resume_available: bool = False
    # Sanitized proof from the shared runtime when a stage pauses after one or
    # more reviewed candidates.  It never contains prompts, provider paths,
    # raw responses, or local artifacts; it only preserves review ownership,
    # parity and public receipt dimensions so a later resume cannot erase
    # already-reviewed pixels.
    last_shared_runtime_failure: dict[str, Any] | None = None
    # Sanitized repair evidence from the latest reviewed-but-failed candidate.
    # This is produced by the shared visual-cluster repair projection and is
    # used only to inform the next candidate in the same slot/round.
    last_review_repair_context: dict[str, Any] | None = None
    # Opaque local-MCP receipts for a blocked stage.  They are cleared by a
    # successful stage and never carry prompt, path, provider or artifact data.
    pending_mcp_handoff_ids: list[str] = Field(default_factory=list)
    # Per-slot retry round for user-confirmed continuations after the current
    # three-candidate budget is exhausted.  Round one is the implicit default;
    # later rounds only isolate durable operation ids and never increase the
    # per-round candidate budget.
    slot_retry_rounds: dict[str, int] = Field(default_factory=dict)

    @field_validator("pending_mcp_handoff_ids")
    @classmethod
    def unique_mcp_handoffs(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Character Card MCP handoff IDs must be unique")
        return cleaned

    @field_validator("slot_retry_rounds")
    @classmethod
    def validate_slot_retry_rounds(cls, value: dict[str, int]) -> dict[str, int]:
        cleaned: dict[str, int] = {}
        allowed = {*ALL_EXPRESSION_SLOT_KEYS, *BODY_SLOT_KEYS}
        for key, round_value in dict(value or {}).items():
            slot_key = str(key).strip()
            if slot_key not in allowed:
                raise ValueError("Character Card retry round slot is invalid")
            parsed = int(round_value)
            if parsed < 1:
                raise ValueError("Character Card retry round must be positive")
            cleaned[slot_key] = parsed
        return cleaned

    @classmethod
    def initial(cls, *, card_version_id: str) -> "CharacterCardState":
        return cls(
            card_version_id=card_version_id,
            face_slots={
                key: CharacterCardSlot(slot_key=key, module="face_identity") for key in FACE_SLOT_KEYS
            },
            expression_slots={
                key: CharacterCardSlot(slot_key=key, module="expression_set") for key in EXPRESSION_SLOT_KEYS
            },
            body_slots={
                key: CharacterCardSlot(slot_key=key, module="body_silhouette") for key in BODY_SLOT_KEYS
            },
        )

    @model_validator(mode="before")
    @classmethod
    def hydrate_new_slots_and_legacy_expression_slots(cls, data: Any) -> Any:
        """Keep historical cards readable after slot-map migrations."""

        if not isinstance(data, dict):
            return data
        face_slots = data.get("face_slots")
        if isinstance(face_slots, dict):
            hydrated = dict(face_slots)
            for slot_key in FACE_SLOT_KEYS:
                hydrated.setdefault(
                    slot_key,
                    CharacterCardSlot(slot_key=slot_key, module="face_identity").model_dump(
                        mode="python"
                    ),
                )
            data = {**data, "face_slots": hydrated}
        expression_slots = data.get("expression_slots")
        if isinstance(expression_slots, dict):
            hydrated = dict(expression_slots)
            for slot_key in EXPRESSION_SLOT_KEYS:
                hydrated.setdefault(
                    slot_key,
                    CharacterCardSlot(slot_key=slot_key, module="expression_set").model_dump(
                        mode="python"
                    ),
                )
            legacy = hydrated.get("expression.smile")
            if legacy is not None:
                if isinstance(legacy, CharacterCardSlot):
                    if legacy.state != "empty":
                        hydrated["expression.smile"] = legacy.model_copy(update={"state": "stale"})
                elif isinstance(legacy, dict) and str(legacy.get("state") or "empty") != "empty":
                    hydrated["expression.smile"] = {**legacy, "state": "stale"}
            data = {**data, "expression_slots": hydrated}
        return data

    @model_validator(mode="after")
    def validate_slots_and_order(self) -> "CharacterCardState":
        if set(self.face_slots) != set(FACE_SLOT_KEYS):
            raise ValueError("Character Card must expose all five Face Identity slots")
        expression_keys = set(self.expression_slots)
        if not set(EXPRESSION_SLOT_KEYS).issubset(expression_keys) or not expression_keys.issubset(
            set(ALL_EXPRESSION_SLOT_KEYS)
        ):
            raise ValueError("Character Card must expose all Expression Set slots")
        if set(self.body_slots) != set(BODY_SLOT_KEYS):
            raise ValueError("Character Card must expose all Body Silhouette slots")
        if self.expression_set_status in {"preparing", "reviewing", "partial", "active"} and self.face_identity_status != "active":
            raise ValueError("Expression Set requires an active Face Identity module")
        if self.body_silhouette_status in {"preparing", "reviewing", "partial", "active"}:
            if self.face_identity_status != "active":
                raise ValueError("Body Silhouette requires an active Face Identity module")
            if self.expression_set_status != "active":
                raise ValueError("Body Silhouette requires an active Expression Set")
        if self.active_version_id and not self.user_activation_confirmed:
            raise ValueError("active Character Card versions require explicit user activation")
        if self.resume_available:
            if (
                self.last_failed_module is None
                or self.last_failed_slot_key is None
                or not str(self.last_failure_code or "").strip()
                or self.last_failure_attempt_count < 1
            ):
                raise ValueError("resumable Character Card state requires a safe failure checkpoint")
        return self

    def all_slots(self) -> list[CharacterCardSlot]:
        return [*self.face_slots.values(), *self.expression_slots.values(), *self.body_slots.values()]

    @property
    def face_identity_base_active(self) -> bool:
        """The historical three-view activation state."""

        return self.face_identity_status == "active"

    @property
    def face_identity_complete(self) -> bool:
        """Five-view completeness, independent from the historical base pack."""

        return all(
            slot.state in {"active", "winner_selected"} or slot.explicitly_left_empty
            for slot in self.face_slots.values()
        )

    def slot(self, slot_key: str) -> CharacterCardSlot:
        for slot in self.all_slots():
            if slot.slot_key == slot_key:
                return slot
        raise KeyError("character_card_slot_not_found")

    def begin_failed_slot_retry(
        self,
        *,
        module: Literal["expression_set", "body_silhouette"],
        confirmed: bool,
    ) -> "CharacterCardState":
        """Start a new user-confirmed retry round for the failed slot.

        This is deliberately not an automatic retry.  It only advances the
        durable slot round after the previous three-candidate budget has been
        exhausted and no MCP handoff is still waiting for materialization.
        """

        if not confirmed:
            raise ValueError("explicit Character Card failed-slot retry confirmation is required")
        if not self.resume_available or self.last_failed_module != module or self.last_failed_slot_key is None:
            raise ValueError("Character Card failed-slot retry requires the matching failed checkpoint")
        if self.pending_mcp_handoff_ids:
            raise ValueError("Character Card failed-slot retry cannot supersede a pending MCP handoff")
        transport_ambiguity = self.last_failure_code == "mcp_materialization_operation_ambiguous"
        if transport_ambiguity:
            failure_receipt = self.last_shared_runtime_failure
            if not isinstance(failure_receipt, dict) or not failure_receipt.get("resume_available"):
                raise ValueError("Character Card ambiguous MCP retry requires shared runtime failure receipt")
            reviewed_attempt_count = int(failure_receipt.get("reviewed_attempt_count") or 0)
            if reviewed_attempt_count > 0 and not failure_receipt.get("shared_review_receipts"):
                raise ValueError("Character Card ambiguous MCP retry requires reviewed candidate receipt")
        if self.last_failure_attempt_count < 3 and not transport_ambiguity:
            raise ValueError("Character Card failed-slot retry requires exhausted candidate budget")

        slot_key = str(self.last_failed_slot_key)
        if module == "expression_set":
            slots = dict(self.expression_slots)
            status_field = "expression_set_status"
            slots_field = "expression_slots"
        else:
            slots = dict(self.body_slots)
            status_field = "body_silhouette_status"
            slots_field = "body_slots"
        if slot_key not in slots:
            raise ValueError("Character Card failed-slot retry slot is missing")
        slot = slots[slot_key]
        if slot.state in {"winner_selected", "active"}:
            raise ValueError("Character Card failed-slot retry cannot replace a reviewed winner")
        slots[slot_key] = CharacterCardSlot(slot_key=slot.slot_key, module=slot.module)
        retry_rounds = dict(self.slot_retry_rounds)
        retry_rounds[slot_key] = int(retry_rounds.get(slot_key, 1)) + 1
        return self.model_copy(
            update={
                status_field: "partial",
                slots_field: slots,
                "slot_retry_rounds": retry_rounds,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
                "append_only_revision": self.append_only_revision + 1,
            }
        )

    def mark_face_version_stale(self, *, new_face_version_id: str) -> "CharacterCardState":
        """Create an append-only state revision without deleting old evidence."""

        stale_expression = {
            key: slot.model_copy(update={"state": "stale"})
            if slot.state != "empty"
            else slot
            for key, slot in self.expression_slots.items()
        }
        stale_body = {
            key: slot.model_copy(update={"state": "stale"})
            if slot.state != "empty"
            else slot
            for key, slot in self.body_slots.items()
        }
        return self.model_copy(
            update={
                "card_version_id": f"card_{uuid4().hex}",
                "face_identity_version_id": new_face_version_id,
                "expression_set_status": "stale" if self.expression_set_status != "empty" else "empty",
                "body_silhouette_status": "stale" if self.body_silhouette_status != "empty" else "empty",
                "expression_slots": stale_expression,
                "body_slots": stale_body,
                "active_version_id": None,
                "user_activation_confirmed": False,
                "expression_activation_confirmed": False,
                "body_activation_confirmed": False,
                "append_only_revision": self.append_only_revision + 1,
            }
        )


class CharacterCardCandidateRequest(_CharacterCardModel):
    """Opaque shared-runtime request; prompt prose is intentionally absent."""

    project_id: str
    people_asset_id: str
    card_version_id: str
    module: Literal["expression_set", "body_silhouette"]
    slot_key: Literal[
        "expression.laugh",
        "expression.smile",
        "expression.anger",
        "expression.sad",
        "body.front_full",
        "body.side_full",
        "body.rear_full",
    ]
    candidate_index: int = Field(ge=1, le=3)
    attempt_round: int = Field(default=1, ge=1)
    reference_output_ids: list[str] = Field(min_length=1)
    user_intent: str
    source_class: BodySourceClass | None = None
    consent_provenance_id: str | None = None
    generation_channel: Literal["provider", "mcp"] = "provider"
    mcp_handoff_id: str | None = None
    prior_review_repair: dict[str, Any] | None = None
    review_only_resume: bool = False
    candidate_count: Literal[3] = 3

    @field_validator("project_id", "people_asset_id", "card_version_id", "user_intent")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Character Card request text is required")
        return value

    @field_validator("reference_output_ids")
    @classmethod
    def unique_references(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Character Card references must be unique")
        return cleaned

    @model_validator(mode="after")
    def enforce_module_slot(self) -> "CharacterCardCandidateRequest":
        if self.module == "expression_set":
            if self.slot_key not in {"expression.laugh", "expression.smile", "expression.anger", "expression.sad"}:
                raise ValueError("Expression Set request has an invalid slot")
            if len(self.reference_output_ids) != 1:
                raise ValueError("Expression Set requests must use only face.front winner")
            if self.source_class is not None:
                raise ValueError("Expression Set does not accept a body source class")
        else:
            if not self.slot_key.startswith("body."):
                raise ValueError("Body Silhouette request has an invalid slot")
            if len(self.reference_output_ids) != 3:
                raise ValueError("Body Silhouette requests require three face continuity references")
            if self.source_class is None:
                raise ValueError("Body Silhouette request requires a source class")
            if self.source_class == "observed" and not str(self.consent_provenance_id or "").strip():
                raise ValueError("observed Body Silhouette request requires consent provenance")
        return self


class CharacterCardCandidateResult(_CharacterCardModel):
    candidate_id: str
    output_id: str
    module: Literal["expression_set", "body_silhouette"]
    slot_key: str
    candidate_index: int = Field(ge=1, le=3)
    source_candidate_ids: list[str] = Field(min_length=1)
    source_output_ids: list[str] = Field(min_length=1)
    canonical_prompt_hash: str
    prompt_compilation_id: str
    prompt_reference_parity_verified: bool

    @model_validator(mode="after")
    def require_parity(self) -> "CharacterCardCandidateResult":
        if not self.prompt_reference_parity_verified:
            raise ValueError("Character Card candidate prompt/reference parity is required")
        return self


class CharacterCardCandidateAttempt(_CharacterCardModel):
    request: CharacterCardCandidateRequest
    candidate: CharacterCardCandidateResult
    review: Any


class CharacterCardFailureEvent(_CharacterCardModel):
    """Safe per-candidate failure evidence retained for manual continuation."""

    module: CharacterCardModule
    slot_key: CharacterCardSlotKey
    candidate_index: int = Field(ge=1, le=3)
    attempt_round: int = Field(default=1, ge=1)
    failure_code: str
    mcp_handoff_id: str | None = None
    review_repair_context: dict[str, Any] | None = None


class CharacterCardStageResult(_CharacterCardModel):
    status: Literal["review", "blocked"]
    card: CharacterCardState
    attempts: list[CharacterCardCandidateAttempt] = Field(default_factory=list)
    winner_output_ids: dict[str, str] = Field(default_factory=dict)
    failure_codes: list[str] = Field(default_factory=list)
    failures: list[CharacterCardFailureEvent] = Field(default_factory=list)
    # Production hosts must return a receipt proving that the existing shared
    # review/retry/final-winner path handled this stage.  The offline contract
    # service below intentionally leaves it empty and is never a route host.
    shared_runtime_receipt: "CharacterCardSharedRuntimeReceipt | None" = None
    shared_runtime_failure: "CharacterCardSharedRuntimeFailureReceipt | None" = None
    mcp_handoff_ids: list[str] = Field(default_factory=list)


class CharacterCardSharedRuntimeReceipt(_CharacterCardModel):
    """Opaque proof that a stage used the shared V3 execution chain."""

    review_owner: Literal["v3_shared_vision"] = "v3_shared_vision"
    retry_owner: Literal["v3_shared_visual_retry"] = "v3_shared_visual_retry"
    candidate_count: Literal[3] = 3
    max_bounded_repair_count: Literal[1] = 1
    retry_count: int = Field(default=0, ge=0, le=1)
    final_winner_selection_verified: bool = False
    prompt_reference_parity_verified: bool = False
    shared_review_receipts: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_shared_acceptance(self) -> "CharacterCardSharedRuntimeReceipt":
        if not self.final_winner_selection_verified or not self.prompt_reference_parity_verified:
            raise ValueError("shared Character Card runtime receipt is incomplete")
        for receipt in self.shared_review_receipts:
            if not isinstance(receipt, dict) or str(receipt.get("owner") or "") != "v3_shared_visual_cluster":
                raise ValueError("shared Character Card runtime receipt contains an invalid review receipt")
        return self


class CharacterCardSharedRuntimeFailureReceipt(_CharacterCardModel):
    """Proof that a blocked stage used shared generation/review before pausing."""

    review_owner: Literal["v3_shared_vision"] = "v3_shared_vision"
    retry_owner: Literal["v3_shared_visual_retry"] = "v3_shared_visual_retry"
    candidate_count: Literal[3] = 3
    failure_count: int = Field(ge=1, le=3)
    resume_available: Literal[True] = True
    reviewed_attempt_count: int = Field(default=0, ge=0, le=3)
    prompt_reference_parity_verified: bool = False
    shared_review_receipts: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_public_review_receipts(self) -> "CharacterCardSharedRuntimeFailureReceipt":
        for receipt in self.shared_review_receipts:
            if not isinstance(receipt, dict) or str(receipt.get("owner") or "") != "v3_shared_visual_cluster":
                raise ValueError("shared Character Card failure receipt contains an invalid review receipt")
        return self


def _safe_receipt_token(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    return token[:160]


def _safe_receipt_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    cleaned = [_safe_receipt_token(item) for item in value]
    return list(dict.fromkeys(item for item in cleaned if item))


def _sanitize_shared_review_receipt(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ValueError("Character Card shared review receipt must be a public dictionary")
    public: dict[str, Any] = {}
    for key in _SAFE_SHARED_REVIEW_RECEIPT_KEYS:
        if key not in receipt:
            continue
        value = receipt.get(key)
        if key in {
            "evidence_codes",
            "issue_codes",
            "score_dimensions",
            "framing_delta_dimensions",
        }:
            public[key] = _safe_receipt_list(value)
        else:
            public[key] = _safe_receipt_token(value)
    if public.get("owner") != "v3_shared_visual_cluster":
        raise ValueError("Character Card shared review receipt owner is invalid")
    if public.get("status") != "pass":
        raise ValueError("Character Card success receipt requires a passing shared review")
    if not public.get("contract_version"):
        raise ValueError("Character Card shared review receipt contract version is required")
    if not public.get("score_dimensions"):
        raise ValueError("Character Card shared review receipt dimensions are required")
    public.setdefault("evidence_codes", [])
    public.setdefault("issue_codes", [])
    public.setdefault("framing_delta_dimensions", [])
    return public


def project_character_card_slot_success_receipt(
    receipt: CharacterCardSharedRuntimeReceipt | dict[str, Any],
    *,
    module: CharacterCardModule,
    slot_key: str,
    output_id: str,
    shared_review_receipts: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Build the persisted, per-slot success receipt from a shared stage receipt.

    The stage host owns review/retry/final-winner evidence.  This function only
    projects that proof onto the exact winner slot/output and strips everything
    that is not safe for durable catalog/public status readback.
    """

    output_id = _safe_receipt_token(output_id)
    if not output_id:
        raise ValueError("Character Card slot success receipt requires an output")
    stage_receipt = (
        receipt
        if isinstance(receipt, CharacterCardSharedRuntimeReceipt)
        else CharacterCardSharedRuntimeReceipt.model_validate(receipt)
    )
    if not stage_receipt.final_winner_selection_verified:
        raise ValueError("Character Card slot success receipt requires winner selection")
    if not stage_receipt.prompt_reference_parity_verified:
        raise ValueError("Character Card slot success receipt requires prompt/reference parity")
    slot_reviews = [_sanitize_shared_review_receipt(item) for item in shared_review_receipts]
    if not slot_reviews:
        raise ValueError("Character Card slot success receipt requires shared review dimensions")
    if slot_key == POSITIVE_EXPRESSION_SLOT_KEY:
        laugh_receipts = [
            item
            for item in slot_reviews
            if item.get("expression") == "laugh"
            and item.get("contract_version") == "v3_affective_expression_review_receipt_v1"
        ]
        if not laugh_receipts:
            raise ValueError("Character Card laugh slot requires shared affective expression receipt")
        if not any(
            laugh_expression_receipt_allows_slot(
                evidence_codes=item.get("evidence_codes", []),
                issue_codes=item.get("issue_codes", []),
            )
            and bool(item.get("framing_delta_dimensions"))
            for item in laugh_receipts
        ):
            raise ValueError("Character Card laugh slot receipt lacks affect/framing evidence")
    return {
        "owner": _CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_OWNER,
        "receipt_version": CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_VERSION,
        "module": module,
        "slot_key": slot_key,
        "output_id": output_id,
        "review_owner": stage_receipt.review_owner,
        "retry_owner": stage_receipt.retry_owner,
        "candidate_count": int(stage_receipt.candidate_count),
        "max_bounded_repair_count": int(stage_receipt.max_bounded_repair_count),
        "bounded_repair_count": int(stage_receipt.retry_count),
        "final_winner_selection_verified": bool(stage_receipt.final_winner_selection_verified),
        "prompt_reference_parity_verified": bool(stage_receipt.prompt_reference_parity_verified),
        "shared_review_receipts": slot_reviews,
    }


def validate_character_card_slot_success_receipt(
    receipt: Any,
    *,
    module: CharacterCardModule,
    slot_key: str,
    output_id: str,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ValueError("Character Card slot shared runtime receipt is required")
    if set(receipt) - _CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_KEYS:
        raise ValueError("Character Card slot shared runtime receipt contains unsafe fields")
    if receipt.get("owner") != _CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_OWNER:
        raise ValueError("Character Card slot shared runtime receipt owner is invalid")
    if receipt.get("receipt_version") != CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_VERSION:
        raise ValueError("Character Card slot shared runtime receipt version is invalid")
    if receipt.get("module") != module or receipt.get("slot_key") != slot_key:
        raise ValueError("Character Card slot shared runtime receipt ownership mismatch")
    if receipt.get("output_id") != output_id:
        raise ValueError("Character Card slot shared runtime receipt output mismatch")
    if receipt.get("review_owner") != "v3_shared_vision":
        raise ValueError("Character Card slot shared runtime receipt review owner is invalid")
    if receipt.get("retry_owner") != "v3_shared_visual_retry":
        raise ValueError("Character Card slot shared runtime receipt retry owner is invalid")
    if int(receipt.get("candidate_count") or 0) != 3:
        raise ValueError("Character Card slot shared runtime receipt candidate budget is invalid")
    if int(receipt.get("max_bounded_repair_count") or -1) != 1:
        raise ValueError("Character Card slot shared runtime receipt repair budget is invalid")
    if int(receipt.get("bounded_repair_count") or 0) < 0 or int(receipt.get("bounded_repair_count") or 0) > 1:
        raise ValueError("Character Card slot shared runtime receipt repair count is invalid")
    if receipt.get("final_winner_selection_verified") is not True:
        raise ValueError("Character Card slot shared runtime receipt winner selection is missing")
    if receipt.get("prompt_reference_parity_verified") is not True:
        raise ValueError("Character Card slot shared runtime receipt prompt/reference parity is missing")
    sanitized_reviews = [
        _sanitize_shared_review_receipt(item)
        for item in receipt.get("shared_review_receipts", [])
    ]
    if not sanitized_reviews:
        raise ValueError("Character Card slot shared runtime receipt review dimensions are missing")
    if slot_key == POSITIVE_EXPRESSION_SLOT_KEY:
        if not any(
            item.get("expression") == "laugh"
            and item.get("contract_version") == "v3_affective_expression_review_receipt_v1"
            and bool(item.get("framing_delta_dimensions"))
            and laugh_expression_receipt_allows_slot(
                evidence_codes=item.get("evidence_codes", []),
                issue_codes=item.get("issue_codes", []),
            )
            for item in sanitized_reviews
        ):
            raise ValueError("Character Card laugh slot shared runtime receipt is incomplete")
    return {
        **receipt,
        "shared_review_receipts": sanitized_reviews,
    }


def character_card_slot_success_receipt_public_summary(
    slot: CharacterCardSlot,
) -> dict[str, Any] | None:
    if slot.shared_runtime_receipt is None or not slot.output_id:
        return None
    receipt = validate_character_card_slot_success_receipt(
        slot.shared_runtime_receipt,
        module=slot.module,
        slot_key=slot.slot_key,
        output_id=slot.output_id,
    )
    return {
        "verified": True,
        "owner": receipt["owner"],
        "receipt_version": receipt["receipt_version"],
        "module": receipt["module"],
        "slot_key": receipt["slot_key"],
        "output_id": receipt["output_id"],
        "review_owner": receipt["review_owner"],
        "retry_owner": receipt["retry_owner"],
        "candidate_count": receipt["candidate_count"],
        "max_bounded_repair_count": receipt["max_bounded_repair_count"],
        "bounded_repair_count": receipt["bounded_repair_count"],
        "final_winner_selection_verified": receipt["final_winner_selection_verified"],
        "prompt_reference_parity_verified": receipt["prompt_reference_parity_verified"],
        "shared_review_receipts": receipt["shared_review_receipts"],
    }


class ExpressionPreparationRequest(_CharacterCardModel):
    expression: ExpressionKey
    front_output_id: str
    reference_output_ids: list[str] = Field(default_factory=list)
    user_intent: str
    candidate_count: Literal[3] = 3

    @field_validator("front_output_id", "user_intent")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Expression Set requires front winner and user intent")
        return value

    @model_validator(mode="after")
    def enforce_front_only_reference(self) -> "ExpressionPreparationRequest":
        if not self.reference_output_ids:
            self.reference_output_ids = [self.front_output_id]
        if self.reference_output_ids != [self.front_output_id]:
            raise ValueError("Expression Set references must use only the face.front winner")
        return self


class BodyPreparationRequest(_CharacterCardModel):
    source_class: BodySourceClass
    face_reference_output_ids: list[str] = Field(default_factory=list)
    body_evidence_ids: list[str] = Field(default_factory=list)
    consent_provenance_id: str | None = None
    candidate_count: Literal[3] = 3
    wardrobe_lock: Literal[False] = False

    @field_validator("face_reference_output_ids", "body_evidence_ids")
    @classmethod
    def clean_ids(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Body Silhouette evidence IDs must be unique")
        return cleaned

    @model_validator(mode="after")
    def require_face_continuity_references(self) -> "BodyPreparationRequest":
        if len(self.face_reference_output_ids) != 3:
            raise ValueError("Body Silhouette requires Face Identity front, profile, and rear references")
        if self.source_class == "observed":
            if not self.body_evidence_ids:
                raise ValueError("observed Body Silhouette requires an authorized full-body reference")
            if not str(self.consent_provenance_id or "").strip():
                raise ValueError("observed Body Silhouette requires consent provenance")
        return self

    @property
    def reference_output_ids(self) -> list[str]:
        return list(self.face_reference_output_ids)

    @property
    def observed_truth(self) -> bool:
        return self.source_class == "observed"


class CharacterCardCandidateGenerator(Protocol):
    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        ...


class CharacterCardCandidateReviewer(Protocol):
    def review(self, candidate: CharacterCardCandidateResult) -> Any:
        ...


class CharacterCardStageHost(Protocol):
    """Host contract for the existing shared runtime, never a local fallback."""

    production_shared_runtime: bool

    def prepare_expression_set(
        self, *, asset: Any, card: CharacterCardState, generation_channel: str = "provider"
    ) -> CharacterCardStageResult:
        ...

    def prepare_expression_slot(
        self, *, asset: Any, card: CharacterCardState, expression: ExpressionKey, generation_channel: str = "provider"
    ) -> CharacterCardStageResult:
        ...

    def prepare_body_silhouette(
        self, *, asset: Any, card: CharacterCardState,
        request: BodySilhouettePublicRequest | None = None,
        generation_channel: str = "provider",
    ) -> CharacterCardStageResult:
        ...


class CharacterCardPreparationService:
    """Offline contract helper; never a production stage host.

    Its injected generator/reviewer seams are useful for deterministic contract
    tests only.  Production HTTP routes require a host advertising
    ``production_shared_runtime`` and a shared-runtime receipt, so this class
    cannot become a second provider/review/retry path.
    """

    production_shared_runtime = False
    execution_mode = "offline_contract"

    CANDIDATE_COUNT = 3
    MAX_BOUNDED_REPAIR_COUNT = 1

    def __init__(
        self,
        *,
        generator: CharacterCardCandidateGenerator | None,
        reviewer: CharacterCardCandidateReviewer | None,
    ) -> None:
        self.generator = generator
        self.reviewer = reviewer

    @staticmethod
    def prepare_face_identity_extension(
        anchor_pack_service: Any,
        request: Any,
    ) -> Any:
        """Run the existing Face Identity host with the two Doc178 slots.

        The import is deliberately runtime-only: the established
        ``AnchorPackPreparationService`` remains the sole face generator and
        reviewer coordinator.  No local prompt or alternate Provider is
        introduced here.
        """

        from .anchor_pack import AnchorPackPreparationRequest

        if not isinstance(request, AnchorPackPreparationRequest):
            raise TypeError("face identity extension requires AnchorPackPreparationRequest")
        extended = request.model_copy(update={"face_view_scope": "character_card"})
        return anchor_pack_service.prepare(extended)

    def prepare_expression_set(
        self,
        card: CharacterCardState,
        *,
        front_output_id: str,
        project_id: str = "project",
        people_asset_id: str = "people_asset",
        user_intents: Mapping[ExpressionKey, str] | None = None,
        generation_channel: Literal["provider", "mcp"] = "provider",
    ) -> CharacterCardStageResult:
        self._require_face_active(card, front_output_id)
        if self.generator is None or self.reviewer is None:
            raise RuntimeError("shared Character Card candidate/review seam is unavailable")
        if not user_intents or any(not str(user_intents.get(key) or "").strip() for key in DEFAULT_EXPRESSION_KEYS):
            raise ValueError("Expression Set requires Brain/user-owned expression intent for every slot")
        intents = user_intents
        attempts: list[CharacterCardCandidateAttempt] = []
        winners: dict[str, str] = {}
        failures: list[CharacterCardFailureEvent] = []
        slots = dict(card.expression_slots)
        neutral = CharacterCardSlot(
            slot_key="expression.neutral",
            module="expression_set",
            state="active",
            is_alias=True,
            alias_of="face.front",
            review_verified=True,
            prompt_reference_parity_verified=True,
        )
        slots["expression.neutral"] = neutral
        for expression in DEFAULT_EXPRESSION_KEYS:
            slot_key = f"expression.{expression}"
            existing = slots[slot_key]
            if existing.state in {"winner_selected", "active"} and existing.output_id:
                winners[slot_key] = existing.output_id
                continue
            request = ExpressionPreparationRequest(
                expression=expression,
                front_output_id=front_output_id,
                user_intent=str(intents.get(expression) or expression),
            )
            winner, expression_attempts, slot_failures = self._prepare_slot(
                card=card,
                module="expression_set",
                slot_key=slot_key,
                project_id=project_id,
                people_asset_id=people_asset_id,
                reference_output_ids=request.reference_output_ids,
                user_intent=request.user_intent,
                source_class=None,
                generation_channel=generation_channel,
                attempts=attempts,
            )
            attempts.extend(expression_attempts)
            failures.extend(slot_failures)
            if winner is None:
                failure_code = slot_failures[-1].failure_code if slot_failures else f"{slot_key}_review_failed"
                failed_card = self._blocked_card(
                    card,
                    module="expression_set",
                    slot_key=slot_key,
                    failure_code=failure_code,
                    failure_attempt_count=self._failure_attempt_count(slot_failures),
                    slots=slots,
                    status_field="expression_set_status",
                )
                blocked_updates: dict[str, Any] = {
                    "pending_mcp_handoff_ids": self._mcp_handoff_ids(slot_failures)
                }
                if failure_code == "character_card_shared_review_failed":
                    blocked_updates["last_review_repair_context"] = self._failure_review_repair_context(
                        slot_failures
                    )
                return CharacterCardStageResult(
                    status="blocked",
                    card=failed_card.model_copy(update=blocked_updates),
                    attempts=attempts,
                    winner_output_ids=winners,
                    failure_codes=list(dict.fromkeys([f"{slot_key}_no_reviewed_winner", *[item.failure_code for item in slot_failures]])),
                    failures=failures,
                    mcp_handoff_ids=self._mcp_handoff_ids(failures),
                )
            slots[slot_key] = self._winner_slot(
                module="expression_set", slot_key=slot_key, winner=winner
            )
            winners[slot_key] = winner.output_id
        updated = card.model_copy(
            update={
                "expression_slots": slots,
                "expression_set_status": "reviewing",
                "expression_set_version_id": f"expression_{uuid4().hex}",
                "expression_activation_confirmed": False,
                "append_only_revision": card.append_only_revision + 1,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
            }
        )
        return CharacterCardStageResult(status="review", card=updated, attempts=attempts, winner_output_ids=winners, failures=failures)

    def prepare_expression_slot(
        self,
        card: CharacterCardState,
        *,
        expression: ExpressionKey,
        front_output_id: str,
        user_intent: str,
        project_id: str = "project",
        people_asset_id: str = "people_asset",
        generation_channel: Literal["provider", "mcp"] = "provider",
        review_only_resume: bool = False,
    ) -> CharacterCardStageResult:
        """Prepare one explicit expression slot outside the default set.

        This preserves Doc196 compatibility: a user may explicitly request a
        lower-intensity ``expression.smile`` card, but the default Professional
        positive deliverable remains ``expression.laugh`` and activation still
        depends on the current required slots only.
        """

        self._require_face_active(card, front_output_id)
        if self.generator is None or self.reviewer is None:
            raise RuntimeError("shared Character Card candidate/review seam is unavailable")
        request = ExpressionPreparationRequest(
            expression=expression,
            front_output_id=front_output_id,
            user_intent=user_intent,
        )
        slot_key = f"expression.{expression}"
        slots = dict(card.expression_slots)
        slots.setdefault(slot_key, CharacterCardSlot(slot_key=slot_key, module="expression_set"))  # type: ignore[arg-type]
        attempts: list[CharacterCardCandidateAttempt] = []
        winner, expression_attempts, slot_failures = self._prepare_slot(
            card=card,
            module="expression_set",
            slot_key=slot_key,
            project_id=project_id,
            people_asset_id=people_asset_id,
            reference_output_ids=request.reference_output_ids,
            user_intent=request.user_intent,
            source_class=None,
            generation_channel=generation_channel,
            review_only_resume=review_only_resume,
            attempts=attempts,
        )
        attempts.extend(expression_attempts)
        if winner is None:
            failure_code = slot_failures[-1].failure_code if slot_failures else f"{slot_key}_review_failed"
            if slot_key not in EXPRESSION_SLOT_KEYS:
                slots[slot_key] = CharacterCardSlot(slot_key=slot_key, module="expression_set", state="blocked")  # type: ignore[arg-type]
                failed_card = card.model_copy(
                    update={
                        "expression_slots": slots,
                        "expression_set_status": card.expression_set_status if card.expression_set_status == "active" else "partial",
                        "last_failed_module": "expression_set",
                        "last_failed_slot_key": slot_key,
                        "last_failure_code": failure_code,
                        "last_failure_attempt_count": self._failure_attempt_count(slot_failures),
                        "resume_available": True,
                        "append_only_revision": card.append_only_revision + 1,
                    }
                )
            else:
                failed_card = self._blocked_card(
                    card,
                    module="expression_set",
                    slot_key=slot_key,
                    failure_code=failure_code,
                    failure_attempt_count=self._failure_attempt_count(slot_failures),
                    slots=slots,
                    status_field="expression_set_status",
                )
            blocked_updates = {"pending_mcp_handoff_ids": self._mcp_handoff_ids(slot_failures)}
            if failure_code == "character_card_shared_review_failed":
                blocked_updates["last_review_repair_context"] = self._failure_review_repair_context(slot_failures)
            return CharacterCardStageResult(
                status="blocked",
                card=failed_card.model_copy(update=blocked_updates),
                attempts=attempts,
                winner_output_ids={},
                failure_codes=list(dict.fromkeys([f"{slot_key}_no_reviewed_winner", *[item.failure_code for item in slot_failures]])),
                failures=slot_failures,
                mcp_handoff_ids=self._mcp_handoff_ids(slot_failures),
            )
        slots[slot_key] = self._winner_slot(
            module="expression_set",
            slot_key=slot_key,
            winner=winner,
        )
        next_status = card.expression_set_status if card.expression_set_status == "active" else "partial"
        updated = card.model_copy(
            update={
                "expression_slots": slots,
                "expression_set_status": next_status,
                "append_only_revision": card.append_only_revision + 1,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
            }
        )
        return CharacterCardStageResult(
            status="review",
            card=updated,
            attempts=attempts,
            winner_output_ids={slot_key: winner.output_id},
            failures=slot_failures,
        )

    def prepare_body_silhouette(
        self,
        card: CharacterCardState,
        *,
        face_reference_output_ids: list[str],
        source_class: BodySourceClass,
        project_id: str = "project",
        people_asset_id: str = "people_asset",
        body_evidence_ids: list[str] | None = None,
        consent_provenance_id: str | None = None,
        user_intent: str | None = None,
        generation_channel: Literal["provider", "mcp"] = "provider",
    ) -> CharacterCardStageResult:
        if card.face_identity_status != "active":
            raise ValueError("Body Silhouette requires an active Face Identity module")
        if card.expression_set_status != "active":
            raise ValueError("Body Silhouette requires an active Expression Set")
        request = BodyPreparationRequest(
            source_class=source_class,
            face_reference_output_ids=face_reference_output_ids,
            body_evidence_ids=list(body_evidence_ids or []),
            consent_provenance_id=consent_provenance_id,
        )
        if self.generator is None or self.reviewer is None:
            raise RuntimeError("shared Character Card candidate/review seam is unavailable")
        if not str(user_intent or "").strip():
            raise ValueError("Body Silhouette requires Brain/user-owned body preparation intent")
        attempts: list[CharacterCardCandidateAttempt] = []
        winners: dict[str, str] = {}
        failures: list[CharacterCardFailureEvent] = []
        slots = dict(card.body_slots)
        for slot_key in BODY_SLOT_KEYS:
            existing = slots[slot_key]
            if existing.state in {"winner_selected", "active"} and existing.output_id:
                winners[slot_key] = existing.output_id
                continue
            winner, slot_attempts, slot_failures = self._prepare_slot(
                card=card,
                module="body_silhouette",
                slot_key=slot_key,
                project_id=project_id,
                people_asset_id=people_asset_id,
                reference_output_ids=request.reference_output_ids,
                user_intent=user_intent,
                source_class=source_class,
                consent_provenance_id=consent_provenance_id,
                generation_channel=generation_channel,
                attempts=attempts,
            )
            attempts.extend(slot_attempts)
            failures.extend(slot_failures)
            if winner is None:
                failure_code = slot_failures[-1].failure_code if slot_failures else f"{slot_key}_review_failed"
                return CharacterCardStageResult(
                    status="blocked",
                    card=self._blocked_card(
                        card,
                        module="body_silhouette",
                        slot_key=slot_key,
                        failure_code=failure_code,
                        failure_attempt_count=self._failure_attempt_count(slot_failures),
                        slots=slots,
                        status_field="body_silhouette_status",
                    ).model_copy(
                        update={"pending_mcp_handoff_ids": self._mcp_handoff_ids(slot_failures)}
                    ),
                    attempts=attempts,
                    winner_output_ids=winners,
                    failure_codes=list(dict.fromkeys([f"{slot_key}_no_reviewed_winner", *[item.failure_code for item in slot_failures]])),
                    failures=failures,
                    mcp_handoff_ids=self._mcp_handoff_ids(failures),
                )
            slots[slot_key] = self._winner_slot(
                module="body_silhouette",
                slot_key=slot_key,
                winner=winner,
                source_class=source_class,
                consent_provenance_id=consent_provenance_id,
            )
            winners[slot_key] = winner.output_id
        updated = card.model_copy(
            update={
                "body_slots": slots,
                "body_silhouette_status": "reviewing",
                "body_silhouette_version_id": f"body_{uuid4().hex}",
                "body_activation_confirmed": False,
                "append_only_revision": card.append_only_revision + 1,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
            }
        )
        return CharacterCardStageResult(status="review", card=updated, attempts=attempts, winner_output_ids=winners, failures=failures)

    def _prepare_slot(
        self,
        *,
        card: CharacterCardState,
        module: Literal["expression_set", "body_silhouette"],
        slot_key: str,
        project_id: str,
        people_asset_id: str,
        reference_output_ids: list[str],
        user_intent: str,
        source_class: BodySourceClass | None,
        consent_provenance_id: str | None = None,
        generation_channel: Literal["provider", "mcp"] = "provider",
        review_only_resume: bool = False,
        attempts: list[CharacterCardCandidateAttempt],
    ) -> tuple[
        CharacterCardCandidateResult | None,
        list[CharacterCardCandidateAttempt],
        list[CharacterCardFailureEvent],
    ]:
        from .anchor_pack import AnchorCandidateUnavailable

        slot_attempts: list[CharacterCardCandidateAttempt] = []
        slot_failures: list[CharacterCardFailureEvent] = []
        passing: list[tuple[CharacterCardCandidateResult, Any]] = []
        attempt_round = int(card.slot_retry_rounds.get(slot_key, 1))
        start_candidate_index = self._candidate_start_index(
            card,
            module=module,
            slot_key=slot_key,
            generation_channel=generation_channel,
            review_only_resume=review_only_resume,
        )
        prior_review_repair: dict[str, Any] | None = self._resumable_review_repair_context(
            card,
            module=module,
            slot_key=slot_key,
            generation_channel=generation_channel,
            start_candidate_index=start_candidate_index,
        )
        if start_candidate_index > self.CANDIDATE_COUNT:
            return (
                None,
                slot_attempts,
                [
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=self.CANDIDATE_COUNT,
                        attempt_round=attempt_round,
                        failure_code=str(card.last_failure_code or "character_card_shared_review_failed"),
                    )
                ],
            )
        for candidate_index in range(start_candidate_index, self.CANDIDATE_COUNT + 1):
            request = CharacterCardCandidateRequest(
                project_id=project_id,
                people_asset_id=people_asset_id,
                card_version_id=card.card_version_id,
                module=module,
                slot_key=slot_key,  # type: ignore[arg-type]
                candidate_index=candidate_index,
                attempt_round=attempt_round,
                reference_output_ids=list(reference_output_ids),
                user_intent=user_intent,
                source_class=source_class,
                consent_provenance_id=consent_provenance_id,
                generation_channel=generation_channel,
                mcp_handoff_id=self._resumable_mcp_handoff_id(
                    card,
                    module=module,
                    slot_key=slot_key,
                    candidate_index=candidate_index,
                    review_only_resume=review_only_resume,
                ),
                prior_review_repair=prior_review_repair,
                review_only_resume=review_only_resume,
            )
            try:
                candidate = self.generator.generate(request)
            except AnchorCandidateUnavailable as exc:
                slot_failures.append(
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=candidate_index,
                        attempt_round=attempt_round,
                        failure_code=exc.failure_code,
                        mcp_handoff_id=exc.mcp_handoff_id,
                    )
                )
                if generation_channel == "mcp" and exc.failure_code in {
                    "mcp_materialization_pending",
                    "mcp_review_pending",
                    "mcp_materialization_operation_ambiguous",
                    "mcp_materialization_checkpoint_mismatch",
                    "mcp_materialization_projection_unavailable",
                }:
                    return None, slot_attempts, slot_failures
                continue
            review = self.reviewer.review(candidate)
            attempt = CharacterCardCandidateAttempt(request=request, candidate=candidate, review=review)
            slot_attempts.append(attempt)
            if getattr(review, "status", None) == "pass" and self._review_allows_slot(slot_key, review):
                passing.append((candidate, review))
            else:
                repair_context = shared_review_repair_context_from_decision(
                    candidate_id=candidate.candidate_id,
                    output_id=candidate.output_id,
                    issue_codes=getattr(review, "issue_codes", []) or [],
                    shared_review_receipts=getattr(review, "shared_review_receipts", []) or [],
                )
                if repair_context:
                    prior_review_repair = repair_context
                if generation_channel == "mcp":
                    slot_failures.append(
                        CharacterCardFailureEvent(
                            module=module,
                            slot_key=slot_key,  # type: ignore[arg-type]
                            candidate_index=candidate_index,
                            attempt_round=attempt_round,
                            failure_code="character_card_shared_review_failed",
                            review_repair_context=repair_context,
                        )
                    )
                    return None, slot_attempts, slot_failures
        if not passing:
            if not slot_failures:
                slot_failures = [
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=index,
                        attempt_round=attempt_round,
                        failure_code="character_card_shared_review_failed",
                    )
                    for index in range(1, self.CANDIDATE_COUNT + 1)
                ]
            return None, slot_attempts, slot_failures
        selected = max(passing, key=lambda item: self._selection_key(item[1]))
        return selected[0], slot_attempts, slot_failures

    @staticmethod
    def _failure_review_repair_context(
        failures: list[CharacterCardFailureEvent],
    ) -> dict[str, Any] | None:
        for failure in reversed(failures):
            repair = failure.review_repair_context
            if isinstance(repair, dict) and repair.get("owner") == "v3_shared_visual_cluster":
                return dict(repair)
        return None

    @staticmethod
    def _resumable_review_repair_context(
        card: CharacterCardState,
        *,
        module: CharacterCardModule,
        slot_key: str,
        generation_channel: Literal["provider", "mcp"],
        start_candidate_index: int,
    ) -> dict[str, Any] | None:
        if generation_channel != "mcp":
            return None
        if card.last_failed_module != module or card.last_failed_slot_key != slot_key:
            return None
        if card.last_failure_code != "character_card_shared_review_failed":
            return None
        if int(card.last_failure_attempt_count or 0) != start_candidate_index - 1:
            return None
        repair = card.last_review_repair_context
        if not isinstance(repair, dict) or repair.get("owner") != "v3_shared_visual_cluster":
            return None
        return dict(repair)

    @classmethod
    def _candidate_start_index(
        cls,
        card: CharacterCardState,
        *,
        module: CharacterCardModule,
        slot_key: str,
        generation_channel: Literal["provider", "mcp"],
        review_only_resume: bool = False,
    ) -> int:
        if generation_channel != "mcp":
            return 1
        if card.last_failed_module != module or card.last_failed_slot_key != slot_key:
            return 1
        failure_count = int(card.last_failure_attempt_count or 0)
        if failure_count < 1:
            return 1
        if review_only_resume and card.last_failure_code in {
            "mcp_review_pending",
            "mcp_materialization_checkpoint_mismatch",
            "mcp_materialization_projection_unavailable",
        }:
            return min(cls.CANDIDATE_COUNT, max(1, failure_count))
        if card.last_failure_code in {"mcp_materialization_pending", "mcp_review_pending"}:
            return min(cls.CANDIDATE_COUNT, max(1, failure_count))
        if card.last_failure_code == "character_card_shared_review_failed":
            return failure_count + 1
        return 1

    @staticmethod
    def _mcp_handoff_ids(failures: list[CharacterCardFailureEvent]) -> list[str]:
        return list(
            dict.fromkeys(
                str(item.mcp_handoff_id).strip()
                for item in failures
                if str(item.mcp_handoff_id or "").strip()
            )
        )

    @staticmethod
    def _failure_attempt_count(failures: list[CharacterCardFailureEvent]) -> int:
        if not failures:
            return 1
        return min(3, max(1, max(int(item.candidate_index or 1) for item in failures)))

    @staticmethod
    def _resumable_mcp_handoff_id(
        card: CharacterCardState,
        *,
        module: CharacterCardModule,
        slot_key: str,
        candidate_index: int,
        review_only_resume: bool = False,
    ) -> str | None:
        if card.last_failed_module != module or card.last_failed_slot_key != slot_key:
            return None
        if review_only_resume and card.last_failure_code != "mcp_review_pending":
            return None
        if not review_only_resume and card.last_failure_code not in {"mcp_materialization_pending", "mcp_review_pending"}:
            return None
        if int(card.last_failure_attempt_count or 0) != int(candidate_index):
            return None
        handoff_ids = [str(item).strip() for item in card.pending_mcp_handoff_ids if str(item).strip()]
        if len(handoff_ids) != 1:
            return None
        return handoff_ids[0]

    @staticmethod
    def _blocked_card(
        card: CharacterCardState,
        *,
        module: CharacterCardModule,
        slot_key: str,
        failure_code: str,
        failure_attempt_count: int,
        slots: dict[str, CharacterCardSlot],
        status_field: Literal["expression_set_status", "body_silhouette_status"],
    ) -> CharacterCardState:
        return card.model_copy(
            update={
                status_field: "blocked",
                "expression_slots" if module == "expression_set" else "body_slots": slots,
                "last_failed_module": module,
                "last_failed_slot_key": slot_key,
                "last_failure_code": failure_code,
                "last_failure_attempt_count": min(3, max(1, failure_attempt_count)),
                "resume_available": True,
                "append_only_revision": card.append_only_revision + 1,
            }
        )

    @staticmethod
    def _selection_key(review: Any) -> tuple[Any, ...]:
        scores = getattr(review, "identity_scores", None)
        if scores is not None and hasattr(scores, "selection_key"):
            return tuple(scores.selection_key())
        return (0,)

    @staticmethod
    def _review_allows_slot(slot_key: str, review: Any) -> bool:
        if slot_key != POSITIVE_EXPRESSION_SLOT_KEY:
            return True
        scores = getattr(review, "identity_scores", None)
        return laugh_expression_receipt_allows_slot(
            evidence_codes=getattr(scores, "evidence_codes", []) or [],
            issue_codes=getattr(review, "issue_codes", []) or [],
        )

    @staticmethod
    def _winner_slot(
        *,
        module: CharacterCardModule,
        slot_key: str,
        winner: CharacterCardCandidateResult,
        source_class: BodySourceClass | None = None,
        consent_provenance_id: str | None = None,
    ) -> CharacterCardSlot:
        review_verified = True
        return CharacterCardSlot(
            slot_key=slot_key,  # type: ignore[arg-type]
            module=module,
            state="winner_selected",
            output_id=winner.output_id,
            source_candidate_ids=list(winner.source_candidate_ids),
            source_class=source_class,
            consent_provenance_id=consent_provenance_id,
            lineage_id=f"lineage_{winner.candidate_id}",
            review_verified=review_verified,
            prompt_reference_parity_verified=winner.prompt_reference_parity_verified,
            candidate_attempt_count=3,
        )

    @staticmethod
    def _require_face_active(card: CharacterCardState, front_output_id: str) -> None:
        if card.face_identity_status != "active":
            raise ValueError("Expression Set requires an active Face Identity module")
        front = card.face_slots.get("face.front")
        if front is None or front.output_id != front_output_id or front.state != "active":
            raise ValueError("Expression Set requires the active face.front winner")

    @staticmethod
    def _require_slot_success_receipt(slot: CharacterCardSlot) -> None:
        if slot.is_alias:
            return
        if slot.state not in {"winner_selected", "active"} or not slot.output_id:
            raise ValueError("Character Card contains an unreviewed slot")
        if slot.shared_runtime_receipt is None:
            raise ValueError("Character Card slot activation requires persisted shared runtime receipt")
        validate_character_card_slot_success_receipt(
            slot.shared_runtime_receipt,
            module=slot.module,
            slot_key=slot.slot_key,
            output_id=slot.output_id,
        )

    @staticmethod
    def activate_module(
        card: CharacterCardState,
        *,
        module: Literal["expression_set", "body_silhouette"],
        confirmed: bool,
    ) -> CharacterCardState:
        """Explicitly activate a reviewed module; preparation never auto-activates."""

        if not confirmed:
            raise ValueError("explicit Character Card module activation confirmation is required")
        if module == "expression_set":
            if card.expression_set_status not in {"reviewing", "partial"}:
                raise ValueError("Expression Set is not ready for activation")
            slots = dict(card.expression_slots)
            if any(
                slot.state not in {"winner_selected", "active"}
                for key, slot in slots.items()
                if key in EXPRESSION_SLOT_KEYS and key != "expression.neutral"
            ):
                raise ValueError("Expression Set contains an unreviewed slot")
            for key, slot in slots.items():
                if key in EXPRESSION_SLOT_KEYS and key != "expression.neutral":
                    CharacterCardPreparationService._require_slot_success_receipt(slot)
            slots = {
                key: slot.model_copy(update={"state": "active"})
                if slot.state == "winner_selected"
                else slot
                for key, slot in slots.items()
            }
            return card.model_copy(
                update={
                    "expression_slots": slots,
                    "expression_set_status": "active",
                    "expression_activation_confirmed": True,
                    "user_activation_confirmed": True,
                    "active_version_id": card.expression_set_version_id,
                    "append_only_revision": card.append_only_revision + 1,
                }
            )
        if card.body_silhouette_status not in {"reviewing", "partial"}:
            raise ValueError("Body Silhouette is not ready for activation")
        if any(slot.state not in {"winner_selected", "active"} for slot in card.body_slots.values()):
            raise ValueError("Body Silhouette contains an unreviewed slot")
        for slot in card.body_slots.values():
            CharacterCardPreparationService._require_slot_success_receipt(slot)
        slots = {
            key: slot.model_copy(update={"state": "active"})
            if slot.state == "winner_selected"
            else slot
            for key, slot in card.body_slots.items()
        }
        return card.model_copy(
            update={
                "body_slots": slots,
                "body_silhouette_status": "active",
                "body_activation_confirmed": True,
                "user_activation_confirmed": True,
                "active_version_id": card.body_silhouette_version_id,
                "append_only_revision": card.append_only_revision + 1,
            }
        )


def apply_face_identity_pack_to_card(card: CharacterCardState, pack: Any) -> CharacterCardState:
    """Project an explicitly activated shared Face Identity pack into slots."""

    pack_version_id = str(pack.pack_version_id)
    if card.face_identity_version_id and card.face_identity_version_id != pack_version_id:
        card = card.mark_face_version_stale(new_face_version_id=pack_version_id)

    role_to_slot = {
        "standard_front": "face.front",
        "left_front_25": "face.left_front_25",
        "three_quarter": "face.front_three_quarter",
        "profile": "face.profile",
        "right_front_25": "face.right_front_25",
        "reverse_three_quarter": "face.reverse_three_quarter",
        "rear_head": "face.rear_head",
    }
    pack_status = str(getattr(pack, "status", "") or "")
    slot_state: Literal["winner_selected", "active"] = (
        "active" if pack_status == "active" else "winner_selected"
    )
    face_slots = {
        slot_key: CharacterCardSlot(slot_key=slot_key, module="face_identity")
        for slot_key in FACE_SLOT_KEYS
    }
    for view in getattr(pack, "anchor_views", []):
        slot_key = role_to_slot.get(str(getattr(view, "view_role", "")))
        if slot_key is None or not getattr(view, "active", False):
            continue
        face_slots[slot_key] = CharacterCardSlot(
            slot_key=slot_key,
            module="face_identity",
            state=slot_state,
            output_id=str(view.output_id),
            source_candidate_ids=list(view.source_candidate_ids),
            lineage_id=f"lineage_{view.view_id}",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
        )
    active_view_count = sum(1 for view in getattr(pack, "anchor_views", []) if getattr(view, "active", False))
    missing_slot = next(
        (
            slot_key
            for role, slot_key in role_to_slot.items()
            if not any(
                getattr(view, "active", False) and str(getattr(view, "view_role", "")) == role
                for view in getattr(pack, "anchor_views", [])
            )
        ),
        "face.front",
    )
    update = {
        "face_identity_status": "active" if pack_status == "active" else (
            "reviewing" if pack_status == "review" else ("partial" if active_view_count else "blocked")
        ),
        "face_identity_version_id": pack_version_id,
        "face_slots": face_slots,
        "card_version_id": f"card_{pack_version_id}",
        "active_version_id": None,
        "user_activation_confirmed": False,
        "append_only_revision": card.append_only_revision + 1,
    }
    if pack_status == "failed":
        update.update(
            {
                "last_failed_module": "face_identity",
                "last_failed_slot_key": missing_slot,
                "last_failure_code": "character_card_face_prepare_paused",
                "last_failure_attempt_count": 3,
                "resume_available": True,
            }
        )
    else:
        update.update(
            {
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_attempt_count": 0,
                "resume_available": False,
            }
        )
    return card.model_copy(
        update=update
    )


__all__ = [
    "BODY_SOURCE_CLASSES",
    "BODY_SLOT_KEYS",
    "EXPRESSION_SLOT_KEYS",
    "EXPRESSION_LABELS",
    "FACE_SLOT_KEYS",
    "CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_VERSION",
    "BodyPreparationRequest",
    "CharacterCardCandidateAttempt",
    "CharacterCardCandidateRequest",
    "CharacterCardCandidateResult",
    "CharacterCardPreparationService",
    "CharacterCardFailureEvent",
    "CharacterCardStageHost",
    "CharacterCardSharedRuntimeFailureReceipt",
    "CharacterCardSharedRuntimeReceipt",
    "CharacterCardSlot",
    "CharacterCardState",
    "CharacterCardStageResult",
    "ExpressionPreparationRequest",
    "apply_face_identity_pack_to_card",
    "character_card_slot_success_receipt_public_summary",
    "project_character_card_slot_success_receipt",
    "validate_character_card_slot_success_receipt",
]
