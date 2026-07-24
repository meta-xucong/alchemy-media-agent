"""Internal contracts for the first Professional Mode asset module.

These contracts describe reviewed identity evidence and lifecycle state. They
do not contain provider prompts, provider controls, biometric vectors, or
scenario-specific delivery fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .character_card import CharacterCardState
from .formal_slot_acceptance import (
    FormalSlotReceipt,
    project_formal_slot_public_summary,
    validate_formal_slot_receipt_for_activation,
)


FaceViewRole = Literal[
    "standard_front",
    "left_front_25",
    "three_quarter",
    "profile",
    "right_front_25",
    # Historical serialized key.  In Character Card Face Identity this means
    # the opposite front-side 45-degree card, not a rear/back-of-head view.
    "reverse_three_quarter",
    "rear_head",
]
PackStatus = Literal["preparing", "review", "active", "failed", "superseded"]
AssetStatus = Literal["draft", "active", "superseded", "blocked"]
ModuleStatus = Literal["draft", "active", "blocked", "superseded"]

FACE_IDENTITY_CHANNELS = (
    "face_geometry",
    "face_feature_relationships",
)
REQUIRED_FACE_VIEW_ROLES = frozenset({"standard_front", "three_quarter", "profile"})
FACE_AUXILIARY_BRIDGE_ROLES = frozenset({"left_front_25", "right_front_25"})
FORMAL_FACE_VIEW_ROLES = frozenset(
    {
        "standard_front",
        "three_quarter",
        "profile",
        "reverse_three_quarter",
        "rear_head",
    }
)
CHARACTER_CARD_FACE_VIEW_ROLES = frozenset(
    {
        "standard_front",
        "left_front_25",
        "three_quarter",
        "profile",
        "right_front_25",
        "reverse_three_quarter",
        "rear_head",
    }
)


class _StrictVisualAssetModel(V3BaseModel):
    """Prevent prompt/provider/vertical fields from entering asset contracts."""

    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
    )


class RootSourceProvenance(_StrictVisualAssetModel):
    source_type: Literal["uploaded_portrait", "generated_character"]
    source_asset_id: str
    project_id: str
    consent_reference: str | None = None
    # The root remains the immutable primary identity source.  One optional
    # supplementary source may calibrate the first neutral capture only; it
    # must never turn later serial stages into an unbounded reference bag.
    supplementary_source_asset_ids: list[str] = Field(default_factory=list, max_length=1)

    @model_validator(mode="after")
    def validate_supplementary_sources(self) -> "RootSourceProvenance":
        primary = self.source_asset_id.strip()
        supplemental = [str(item or "").strip() for item in self.supplementary_source_asset_ids]
        if not primary or any(not item for item in supplemental):
            raise ValueError("root source provenance requires nonempty source IDs")
        if primary in supplemental or len(supplemental) != len(set(supplemental)):
            raise ValueError("supplementary source evidence must be unique and cannot repeat the root")
        return self


class IdentityScoreSummary(_StrictVisualAssetModel):
    """Review summary for selecting an identity anchor candidate.

    ``same_face_score`` is the first-principles likeness score.  It must judge
    the person's distinctive feature relationships rather than generic beauty,
    symmetry, or polish.  The remaining fields are supporting signals only:
    human realism prevents an AI-averaged face from winning a close decision,
    while pose/framing is intentionally last because a small head tilt does
    not materially reduce future identity continuity.
    """

    same_face_score: float = Field(ge=0.0, le=1.0)
    visual_quality_score: float = Field(ge=0.0, le=1.0)
    distinctive_feature_score: float | None = Field(default=None, ge=0.0, le=1.0)
    human_realism_score: float | None = Field(default=None, ge=0.0, le=1.0)
    pose_compliance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    ai_overperfection_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_codes")
    @classmethod
    def unique_evidence_codes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("identity evidence codes must be unique")
        return value

    @property
    def effective_distinctive_feature_score(self) -> float:
        """Use legacy same-face evidence when an old record lacks this field."""

        return (
            self.same_face_score
            if self.distinctive_feature_score is None
            else self.distinctive_feature_score
        )

    @property
    def effective_human_realism_score(self) -> float:
        """Keep old persisted records readable without inventing a new signal."""

        return self.same_face_score if self.human_realism_score is None else self.human_realism_score

    def selection_key(self) -> tuple[float, float, float, float, float, float]:
        """Return a likeness-first, deterministic candidate ordering key.

        The tuple is deliberately lexicographic: no amount of generic polish
        or perfect framing may outrank a candidate that is more recognizably
        the same person.  Human realism and an anti-overperfection penalty
        resolve close likeness decisions; pose is the final, lowest-priority
        signal so ordinary head tilt remains usable.
        """

        return (
            self.same_face_score,
            self.effective_distinctive_feature_score,
            self.effective_human_realism_score,
            1.0 - self.ai_overperfection_penalty,
            self.visual_quality_score,
            self.pose_compliance_score,
        )


class AnchorView(_StrictVisualAssetModel):
    view_id: str
    view_role: FaceViewRole
    output_id: str
    source_candidate_ids: list[str] = Field(min_length=1)
    identity_scores: IdentityScoreSummary
    formal_slot_receipt: FormalSlotReceipt | None = None
    active: bool = True

    @model_validator(mode="after")
    def validate_formal_view_receipt(self) -> "AnchorView":
        if self.formal_slot_receipt is not None:
            if self.view_role in FACE_AUXILIARY_BRIDGE_ROLES:
                raise ValueError("25-35 degree bridge references cannot carry formal AnchorView receipts")
            receipt = self.formal_slot_receipt
            if receipt.module != "face_identity":
                raise ValueError("Face Identity AnchorView receipt must belong to face_identity")
            if receipt.slot_key != f"face_identity.{self.view_role}":
                raise ValueError("Face Identity AnchorView receipt slot does not match view role")
            if receipt.winner_output_id != self.output_id:
                raise ValueError("Face Identity AnchorView receipt output does not match view output")
            if self.source_candidate_ids and receipt.winner_candidate_id not in self.source_candidate_ids:
                raise ValueError("Face Identity AnchorView receipt winner is not in source candidates")
        return self

    def formal_slot_public_summary(self) -> dict[str, object] | None:
        if self.formal_slot_receipt is None:
            return None
        return project_formal_slot_public_summary(self.formal_slot_receipt)


class AnchorAuxiliaryReference(_StrictVisualAssetModel):
    reference_id: str
    reference_role: FaceViewRole
    output_id: str
    source_candidate_ids: list[str] = Field(min_length=1)
    identity_scores: IdentityScoreSummary
    formal_slot_receipt: FormalSlotReceipt
    active: bool = True

    @model_validator(mode="after")
    def validate_auxiliary_reference_receipt(self) -> "AnchorAuxiliaryReference":
        if self.reference_role not in FACE_AUXILIARY_BRIDGE_ROLES:
            raise ValueError("only 25-35 degree bridge roles may be auxiliary references")
        receipt = self.formal_slot_receipt
        if receipt.module != "face_identity":
            raise ValueError("Face Identity auxiliary receipt must belong to face_identity")
        if receipt.slot_key != f"face_identity_bridge.{self.reference_role}":
            raise ValueError("Face Identity auxiliary receipt slot does not match bridge role")
        if receipt.acceptance_mode != "auxiliary_first_pass_reference" or receipt.slot_scope != "auxiliary_reference":
            raise ValueError("Face Identity bridge requires auxiliary_first_pass_reference receipt")
        if receipt.winner_output_id != self.output_id:
            raise ValueError("Face Identity auxiliary receipt output does not match bridge output")
        if self.source_candidate_ids and receipt.winner_candidate_id not in self.source_candidate_ids:
            raise ValueError("Face Identity auxiliary receipt winner is not in source candidates")
        return self

    def formal_slot_public_summary(self) -> dict[str, object]:
        return project_formal_slot_public_summary(self.formal_slot_receipt)


class AnchorCandidateFailureReceipt(_StrictVisualAssetModel):
    """Public-safe failed-candidate checkpoint for resumable preparation.

    This receipt intentionally stores only stage/view/candidate identity plus a
    safe failure code and optional opaque MCP handoff id. It never contains a
    prompt, path, provider body, reviewer prose, or pixel evidence.
    """

    stage: Literal["front", "supplementary"]
    view_role: FaceViewRole
    candidate_index: int = Field(ge=1, le=3)
    failure_code: str
    mcp_handoff_id: str | None = None
    output_id: str | None = None
    candidate_id: str | None = None


class FaceIdentityModule(_StrictVisualAssetModel):
    module_id: str
    people_asset_id: str
    active_version_id: str | None = None
    status: ModuleStatus = "draft"
    owned_channels: tuple[str, ...] = FACE_IDENTITY_CHANNELS

    @model_validator(mode="after")
    def enforce_face_only_scope(self) -> "FaceIdentityModule":
        if set(self.owned_channels) != set(FACE_IDENTITY_CHANNELS):
            raise ValueError("Face Identity Module may own face channels only")
        if self.status == "active" and not self.active_version_id:
            raise ValueError("active Face Identity Module requires an active pack version")
        return self


class IdentityAnchorPackVersion(_StrictVisualAssetModel):
    pack_version_id: str
    people_asset_id: str
    status: PackStatus = "preparing"
    anchor_views: list[AnchorView] = Field(default_factory=list)
    auxiliary_references: list[AnchorAuxiliaryReference] = Field(default_factory=list)
    candidate_failures: list[AnchorCandidateFailureReceipt] = Field(default_factory=list)
    root_source_provenance: RootSourceProvenance
    user_activation_confirmed: bool = False

    @model_validator(mode="after")
    def validate_pack_activation(self) -> "IdentityAnchorPackVersion":
        view_ids = [item.view_id for item in self.anchor_views]
        if len(view_ids) != len(set(view_ids)):
            raise ValueError("anchor view IDs must be unique")
        auxiliary_ids = [item.reference_id for item in self.auxiliary_references]
        if len(auxiliary_ids) != len(set(auxiliary_ids)):
            raise ValueError("auxiliary reference IDs must be unique")
        failure_keys = [
            (item.view_role, item.candidate_index, item.mcp_handoff_id or "")
            for item in self.candidate_failures
        ]
        if len(failure_keys) != len(set(failure_keys)):
            raise ValueError("anchor candidate failure receipts must be unique")
        if self.status == "active":
            roles = {item.view_role for item in self.anchor_views if item.active}
            missing = REQUIRED_FACE_VIEW_ROLES - roles
            if not self.user_activation_confirmed:
                raise ValueError("active pack requires user activation")
            if missing:
                raise ValueError(f"active pack is missing required face views: {sorted(missing)}")
            for view in self.anchor_views:
                if view.active:
                    if view.view_role in FACE_AUXILIARY_BRIDGE_ROLES:
                        raise ValueError("active Face Identity packs cannot activate 25-35 degree bridge references")
                    if view.formal_slot_receipt is None:
                        raise ValueError("active Face Identity views require formal slot receipts")
                    validate_formal_slot_receipt_for_activation(view.formal_slot_receipt)
        return self


class PeopleAsset(_StrictVisualAssetModel):
    people_asset_id: str
    project_id: str
    subject_kind: Literal["human_person", "fictional_character"]
    face_identity_module: FaceIdentityModule
    # The immutable root declaration is retained with the project asset so a
    # restart can resume formal pack preparation without trusting raw request
    # metadata.  Pixel bytes remain in the existing uploaded-asset store.
    root_source_provenance: RootSourceProvenance | None = None
    # A single immutable natural-language statement of what the user wants the
    # anchor pack to represent.  It is not a renderer prompt or a structured
    # visual recipe: Remote Brain remains the only final prompt author.  The
    # optional type keeps historical catalog records readable; formal
    # preparation fails closed when a legacy asset has no intent.
    preparation_intent: str | None = None
    active_pack_version_id: str | None = None
    status: AssetStatus = "draft"
    # Additive Doc178 state.  Historical records without this field are
    # hydrated with a visible empty template; the original Face Identity pack
    # lifecycle remains independently valid.
    character_card: CharacterCardState = Field(default_factory=lambda: CharacterCardState.initial(card_version_id="card_pending"))

    @field_validator("preparation_intent")
    @classmethod
    def normalize_preparation_intent(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("People Asset preparation intent cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_active_asset(self) -> "PeopleAsset":
        if self.face_identity_module.people_asset_id != self.people_asset_id:
            raise ValueError("Face Identity Module must belong to the People Asset")
        if self.status == "active" and not self.active_pack_version_id:
            raise ValueError("active People Asset requires an active pack version")
        return self


class ProfessionalModeBinding(_StrictVisualAssetModel):
    """Sanitized per-job binding passed to the shared semantic planning path."""

    mode: str = "professional"
    job_id: str
    project_id: str
    people_asset_id: str
    face_module_id: str
    pack_version_id: str
    identity_view_ids: list[str] = Field(min_length=1, max_length=3)

    @field_validator("mode")
    @classmethod
    def require_explicit_professional_mode(cls, value: str) -> str:
        if value != "professional":
            raise ValueError("an explicit Professional Mode selection is required")
        return value

    @field_validator("identity_view_ids")
    @classmethod
    def unique_identity_views(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("identity view IDs must be unique")
        return value

    def to_brain_evidence(self) -> dict[str, object]:
        """Return typed identity evidence, never creative/provider instructions."""

        return {
            "mode": self.mode,
            "people_asset_id": self.people_asset_id,
            "pack_version_id": self.pack_version_id,
            "face_module_id": self.face_module_id,
            "identity_view_ids": list(self.identity_view_ids),
            "identity_channels": list(FACE_IDENTITY_CHANNELS),
        }
