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


FACE_SLOT_KEYS = (
    "face.front",
    "face.front_three_quarter",
    "face.profile",
    "face.reverse_three_quarter",
    "face.rear_head",
)
EXPRESSION_SLOT_KEYS = ("expression.neutral", "expression.smile", "expression.anger", "expression.sad")
BODY_SLOT_KEYS = ("body.front_full", "body.side_full", "body.rear_full")
BODY_SOURCE_CLASSES = ("observed", "user_described", "brain_inferred")
EXPRESSION_LABELS = {
    "expression.neutral": "中性",
    "expression.smile": "微笑",
    "expression.anger": "愤怒",
    "expression.sad": "悲伤",
}

CharacterCardSlotKey = Literal[
    "face.front",
    "face.front_three_quarter",
    "face.profile",
    "face.reverse_three_quarter",
    "face.rear_head",
    "expression.neutral",
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
ExpressionKey = Literal["smile", "anger", "sad"]
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
        if self.is_alias:
            if self.slot_key != "expression.neutral" or self.alias_of != "face.front":
                raise ValueError("only expression.neutral may alias face.front")
            if self.output_id or self.candidate_attempt_count or self.bounded_repair_count:
                raise ValueError("expression.neutral alias cannot create a generation job")
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

    @model_validator(mode="after")
    def validate_slots_and_order(self) -> "CharacterCardState":
        if set(self.face_slots) != set(FACE_SLOT_KEYS):
            raise ValueError("Character Card must expose all five Face Identity slots")
        if set(self.expression_slots) != set(EXPRESSION_SLOT_KEYS):
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
        "expression.smile",
        "expression.anger",
        "expression.sad",
        "body.front_full",
        "body.side_full",
        "body.rear_full",
    ]
    candidate_index: int = Field(ge=1, le=3)
    reference_output_ids: list[str] = Field(min_length=1)
    user_intent: str
    source_class: BodySourceClass | None = None
    consent_provenance_id: str | None = None
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
            if self.slot_key not in {"expression.smile", "expression.anger", "expression.sad"}:
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


class CharacterCardStageResult(_CharacterCardModel):
    status: Literal["review", "blocked"]
    card: CharacterCardState
    attempts: list[CharacterCardCandidateAttempt] = Field(default_factory=list)
    winner_output_ids: dict[str, str] = Field(default_factory=dict)
    failure_codes: list[str] = Field(default_factory=list)
    # Production hosts must return a receipt proving that the existing shared
    # review/retry/final-winner path handled this stage.  The offline contract
    # service below intentionally leaves it empty and is never a route host.
    shared_runtime_receipt: "CharacterCardSharedRuntimeReceipt | None" = None


class CharacterCardSharedRuntimeReceipt(_CharacterCardModel):
    """Opaque proof that a stage used the shared V3 execution chain."""

    review_owner: Literal["v3_shared_vision"] = "v3_shared_vision"
    retry_owner: Literal["v3_shared_visual_retry"] = "v3_shared_visual_retry"
    candidate_count: Literal[3] = 3
    max_bounded_repair_count: Literal[1] = 1
    retry_count: int = Field(default=0, ge=0, le=1)
    final_winner_selection_verified: bool = False
    prompt_reference_parity_verified: bool = False

    @model_validator(mode="after")
    def require_shared_acceptance(self) -> "CharacterCardSharedRuntimeReceipt":
        if not self.final_winner_selection_verified or not self.prompt_reference_parity_verified:
            raise ValueError("shared Character Card runtime receipt is incomplete")
        return self


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
        self, *, asset: Any, card: CharacterCardState
    ) -> CharacterCardStageResult:
        ...

    def prepare_body_silhouette(
        self, *, asset: Any, card: CharacterCardState,
        request: BodySilhouettePublicRequest | None = None,
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
    ) -> CharacterCardStageResult:
        self._require_face_active(card, front_output_id)
        if self.generator is None or self.reviewer is None:
            raise RuntimeError("shared Character Card candidate/review seam is unavailable")
        if not user_intents or any(not str(user_intents.get(key) or "").strip() for key in ("smile", "anger", "sad")):
            raise ValueError("Expression Set requires Brain/user-owned expression intent for every slot")
        intents = user_intents
        attempts: list[CharacterCardCandidateAttempt] = []
        winners: dict[str, str] = {}
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
        for expression in ("smile", "anger", "sad"):
            request = ExpressionPreparationRequest(
                expression=expression,
                front_output_id=front_output_id,
                user_intent=str(intents.get(expression) or expression),
            )
            winner, expression_attempts = self._prepare_slot(
                card=card,
                module="expression_set",
                slot_key=f"expression.{expression}",
                project_id=project_id,
                people_asset_id=people_asset_id,
                reference_output_ids=request.reference_output_ids,
                user_intent=request.user_intent,
                source_class=None,
                attempts=attempts,
            )
            attempts.extend(expression_attempts)
            if winner is None:
                return CharacterCardStageResult(
                    status="blocked",
                    card=card.model_copy(
                        update={"expression_set_status": "blocked", "expression_slots": slots}
                    ),
                    attempts=attempts,
                    winner_output_ids=winners,
                    failure_codes=[f"expression_{expression}_no_reviewed_winner"],
                )
            slots[f"expression.{expression}"] = self._winner_slot(
                module="expression_set", slot_key=f"expression.{expression}", winner=winner
            )
            winners[f"expression.{expression}"] = winner.output_id
        updated = card.model_copy(
            update={
                "expression_slots": slots,
                "expression_set_status": "reviewing",
                "expression_set_version_id": f"expression_{uuid4().hex}",
                "expression_activation_confirmed": False,
                "append_only_revision": card.append_only_revision + 1,
            }
        )
        return CharacterCardStageResult(status="review", card=updated, attempts=attempts, winner_output_ids=winners)

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
        slots = dict(card.body_slots)
        for slot_key in BODY_SLOT_KEYS:
            winner, slot_attempts = self._prepare_slot(
                card=card,
                module="body_silhouette",
                slot_key=slot_key,
                project_id=project_id,
                people_asset_id=people_asset_id,
                reference_output_ids=request.reference_output_ids,
                user_intent=user_intent,
                source_class=source_class,
                consent_provenance_id=consent_provenance_id,
                attempts=attempts,
            )
            attempts.extend(slot_attempts)
            if winner is None:
                return CharacterCardStageResult(
                    status="blocked",
                    card=card.model_copy(
                        update={"body_silhouette_status": "blocked", "body_slots": slots}
                    ),
                    attempts=attempts,
                    winner_output_ids=winners,
                    failure_codes=[f"{slot_key}_no_reviewed_winner"],
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
            }
        )
        return CharacterCardStageResult(status="review", card=updated, attempts=attempts, winner_output_ids=winners)

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
        attempts: list[CharacterCardCandidateAttempt],
    ) -> tuple[CharacterCardCandidateResult | None, list[CharacterCardCandidateAttempt]]:
        slot_attempts: list[CharacterCardCandidateAttempt] = []
        passing: list[tuple[CharacterCardCandidateResult, Any]] = []
        for candidate_index in range(1, self.CANDIDATE_COUNT + 1):
            request = CharacterCardCandidateRequest(
                project_id=project_id,
                people_asset_id=people_asset_id,
                card_version_id=card.card_version_id,
                module=module,
                slot_key=slot_key,  # type: ignore[arg-type]
                candidate_index=candidate_index,
                reference_output_ids=list(reference_output_ids),
                user_intent=user_intent,
                source_class=source_class,
                consent_provenance_id=consent_provenance_id,
            )
            candidate = self.generator.generate(request)
            review = self.reviewer.review(candidate)
            attempt = CharacterCardCandidateAttempt(request=request, candidate=candidate, review=review)
            slot_attempts.append(attempt)
            if getattr(review, "status", None) == "pass":
                passing.append((candidate, review))
        if not passing:
            return None, slot_attempts
        selected = max(passing, key=lambda item: self._selection_key(item[1]))
        return selected[0], slot_attempts

    @staticmethod
    def _selection_key(review: Any) -> tuple[Any, ...]:
        scores = getattr(review, "identity_scores", None)
        if scores is not None and hasattr(scores, "selection_key"):
            return tuple(scores.selection_key())
        return (0,)

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
                if key != "expression.neutral"
            ):
                raise ValueError("Expression Set contains an unreviewed slot")
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
        "three_quarter": "face.front_three_quarter",
        "profile": "face.profile",
        "reverse_three_quarter": "face.reverse_three_quarter",
        "rear_head": "face.rear_head",
    }
    slot_state: Literal["winner_selected", "active"] = (
        "active" if str(getattr(pack, "status", "")) == "active" else "winner_selected"
    )
    face_slots = dict(card.face_slots)
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
    return card.model_copy(
        update={
            "face_identity_status": "active" if slot_state == "active" else "reviewing",
            "face_identity_version_id": pack_version_id,
            "face_slots": face_slots,
            "card_version_id": f"card_{pack_version_id}",
            "active_version_id": None,
            "user_activation_confirmed": False,
            "append_only_revision": card.append_only_revision + 1,
        }
    )


__all__ = [
    "BODY_SOURCE_CLASSES",
    "BODY_SLOT_KEYS",
    "EXPRESSION_SLOT_KEYS",
    "EXPRESSION_LABELS",
    "FACE_SLOT_KEYS",
    "BodyPreparationRequest",
    "CharacterCardCandidateAttempt",
    "CharacterCardCandidateRequest",
    "CharacterCardCandidateResult",
    "CharacterCardPreparationService",
    "CharacterCardStageHost",
    "CharacterCardSlot",
    "CharacterCardState",
    "CharacterCardStageResult",
    "ExpressionPreparationRequest",
    "apply_face_identity_pack_to_card",
]
