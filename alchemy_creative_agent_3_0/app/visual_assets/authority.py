"""Professional Mode asset-channel authority and reference admission.

The module validates Brain/shared-evidence output. It does not classify user
language, author prompts, call a Provider, or perform pixel editing.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .contracts import FACE_IDENTITY_CHANNELS, ProfessionalModeBinding


_CHANNEL_TOKEN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_EVIDENCE_REPRESENTATIONS = frozenset(
    {"channel_isolated", "verified_non_person_derivative"}
)
_PROTECTED_FACE_ALIASES = {
    "face_identity": frozenset((*FACE_IDENTITY_CHANNELS, "same_person_continuity")),
    "same_face_identity": frozenset((*FACE_IDENTITY_CHANNELS, "same_person_continuity")),
}


def _validate_tokens(values: list[str], field_name: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique values")
    if any(not value or not _CHANNEL_TOKEN.fullmatch(value) for value in values):
        raise ValueError(f"{field_name} contains an invalid channel token")
    return values


class AssetChannelClaim(V3BaseModel):
    """One active Visual Asset's typed channel authority claim."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    project_id: str
    asset_type: str
    asset_id: str
    asset_version_id: str
    owned_channels: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    active: bool = True

    @field_validator("project_id", "asset_type", "asset_id", "asset_version_id")
    @classmethod
    def require_nonempty_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("asset channel claim identifiers must be non-empty")
        return value

    @field_validator("owned_channels")
    @classmethod
    def unique_owned_channels(cls, value: list[str]) -> list[str]:
        return _validate_tokens(value, "owned_channels")

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("asset channel claim evidence IDs must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("asset channel claim evidence IDs must be non-empty")
        return value

    def to_provenance(self) -> dict[str, object]:
        """Return the safe claim subset used by the frozen planning ledger."""

        return {
            "project_id": self.project_id,
            "asset_type": self.asset_type,
            "asset_id": self.asset_id,
            "asset_version_id": self.asset_version_id,
            "owned_channels": list(self.owned_channels),
            "evidence_ids": list(self.evidence_ids),
        }


class VisualAssetBindingSet(V3BaseModel):
    """All selected active asset claims for one Professional Mode job."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    mode: Literal["professional"] = "professional"
    project_id: str
    job_id: str
    claims: list[AssetChannelClaim] = Field(min_length=1)
    contract_version: Literal["visual_asset_authority_v1"] = "visual_asset_authority_v1"

    @model_validator(mode="after")
    def enforce_project_and_channel_ownership(self) -> "VisualAssetBindingSet":
        if not self.project_id.strip() or not self.job_id.strip():
            raise ValueError("Professional asset binding requires project and job IDs")
        owned_channels: dict[str, str] = {}
        for claim in self.claims:
            if claim.project_id != self.project_id:
                raise ValueError("all asset channel claims must belong to the job project")
            if not claim.active:
                raise ValueError("inactive asset claims cannot enter a Professional job")
            for channel in claim.owned_channels:
                canonical_channels = _PROTECTED_FACE_ALIASES.get(channel, frozenset({channel}))
                for canonical in canonical_channels:
                    previous = owned_channels.get(canonical)
                    if previous and previous != claim.asset_id:
                        raise ValueError("active asset claims overlap on an owned channel")
                    owned_channels[canonical] = claim.asset_id
        return self

    @classmethod
    def from_professional_binding(cls, binding: ProfessionalModeBinding) -> "VisualAssetBindingSet":
        """Adapt the first-release People Asset binding to the generic set."""

        return cls(
            project_id=binding.project_id,
            job_id=binding.job_id,
            claims=[
                AssetChannelClaim(
                    project_id=binding.project_id,
                    asset_type="people",
                    asset_id=binding.people_asset_id,
                    asset_version_id=binding.pack_version_id,
                    owned_channels=[*FACE_IDENTITY_CHANNELS, "same_person_continuity"],
                    evidence_ids=list(binding.identity_view_ids),
                )
            ],
        )

    def to_provenance(self) -> dict[str, object]:
        """Return safe claim metadata without raw paths or creative content."""

        return {
            "contract_version": self.contract_version,
            "project_id": self.project_id,
            "job_id": self.job_id,
            "claims": [claim.to_provenance() for claim in self.claims],
        }


ReferenceRepresentation = Literal[
    "channel_isolated",
    "verified_non_person_derivative",
    "full_frame",
]


class ReferenceChannelEvidence(V3BaseModel):
    """Evidence descriptor for one semantic reference channel."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    channel: str
    evidence_ids: list[str] = Field(min_length=1)
    representation: ReferenceRepresentation

    @field_validator("channel")
    @classmethod
    def valid_channel(cls, value: str) -> str:
        return _validate_tokens([value], "reference channel")[0]

    @field_validator("evidence_ids")
    @classmethod
    def valid_evidence_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("reference channel evidence IDs must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("reference channel evidence IDs must be non-empty")
        return value


class ReferenceChannelPlan(V3BaseModel):
    """Brain/shared-evidence channel plan; no raw input or Prompt body."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    project_id: str
    job_id: str
    reference_id: str
    declared_channels: list[str] = Field(min_length=1)
    channel_evidence: list[ReferenceChannelEvidence] = Field(min_length=1)
    source_kind: Literal["uploaded_image", "prompt_declared_object", "project_reference"] = "uploaded_image"

    @field_validator("project_id", "job_id", "reference_id")
    @classmethod
    def require_reference_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reference project, job, and ID fields must be non-empty")
        return value

    @field_validator("declared_channels")
    @classmethod
    def unique_declared_channels(cls, value: list[str]) -> list[str]:
        return _validate_tokens(value, "declared_channels")

    @model_validator(mode="after")
    def match_evidence_to_declared_channels(self) -> "ReferenceChannelPlan":
        evidence_channels = [item.channel for item in self.channel_evidence]
        if len(evidence_channels) != len(set(evidence_channels)):
            raise ValueError("reference channel evidence must contain one item per channel")
        if set(evidence_channels) != set(self.declared_channels):
            raise ValueError("every declared reference channel needs typed evidence")
        return self


class ReferenceAdmissionDecision(V3BaseModel):
    """Safe result for one reference; IDs only, never raw paths or payloads."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    reference_id: str
    status: Literal["admitted", "partial", "blocked"]
    admitted_channels: list[str] = Field(default_factory=list)
    suppressed_channels: list[str] = Field(default_factory=list)
    admitted_evidence_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_decision_state(self) -> "ReferenceAdmissionDecision":
        if self.status == "admitted" and self.suppressed_channels:
            raise ValueError("an admitted reference cannot have suppressed channels")
        if self.status == "partial" and not self.admitted_channels:
            raise ValueError("a partial reference must admit at least one channel")
        if self.status == "blocked" and not self.reason_codes:
            raise ValueError("a blocked reference requires reason codes")
        return self


class ReferenceEvidencePacket(V3BaseModel):
    """The exact admitted evidence IDs shared by Provider and Reviewer."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    evidence_ids: list[str] = Field(default_factory=list)
    provider_evidence_ids: list[str] = Field(default_factory=list)
    reviewer_evidence_ids: list[str] = Field(default_factory=list)
    contract_version: Literal["visual_asset_reference_evidence_packet_v1"] = (
        "visual_asset_reference_evidence_packet_v1"
    )

    @field_validator("evidence_ids", "provider_evidence_ids", "reviewer_evidence_ids")
    @classmethod
    def unique_packet_evidence_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("reference evidence packet IDs must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("reference evidence packet IDs must be non-empty")
        return value

    @model_validator(mode="after")
    def provider_reviewer_parity(self) -> "ReferenceEvidencePacket":
        expected = set(self.evidence_ids)
        if set(self.provider_evidence_ids) != expected or set(self.reviewer_evidence_ids) != expected:
            raise ValueError("Provider and Reviewer must receive identical admitted evidence IDs")
        return self


class ReferenceAdmissionResult(V3BaseModel):
    """Batch admission result used before Professional Provider execution."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: Literal["admitted", "blocked"]
    decisions: list[ReferenceAdmissionDecision] = Field(default_factory=list)
    contract_version: Literal["visual_asset_reference_admission_v1"] = (
        "visual_asset_reference_admission_v1"
    )

    @model_validator(mode="after")
    def no_hidden_blocked_decisions(self) -> "ReferenceAdmissionResult":
        if self.status == "admitted" and any(item.status == "blocked" for item in self.decisions):
            raise ValueError("an admitted batch cannot contain a blocked reference")
        return self

    def to_provenance(self) -> dict[str, object]:
        """Return safe metadata for the planning/review evidence ledger."""

        packet = self.to_evidence_packet() if self.status == "admitted" else None
        return {
            "reference_admission_contract_version": self.contract_version,
            "reference_admission_status": self.status,
            "reference_evidence_packet_contract_version": packet.contract_version if packet else None,
            "admitted_evidence_ids": packet.evidence_ids if packet else [],
            "reference_admission_decisions": [item.model_dump(mode="json") for item in self.decisions],
        }

    def to_evidence_packet(self) -> ReferenceEvidencePacket:
        if self.status != "admitted":
            raise ValueError("blocked reference admission cannot create an evidence packet")
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for decision in self.decisions
                for evidence_id in decision.admitted_evidence_ids
            )
        )
        return ReferenceEvidencePacket(
            evidence_ids=evidence_ids,
            provider_evidence_ids=list(evidence_ids),
            reviewer_evidence_ids=list(evidence_ids),
        )


class ReferenceAdmissionResolver:
    """Validate Brain/shared-evidence plans against active asset authority."""

    safe_representations = _SAFE_EVIDENCE_REPRESENTATIONS

    def resolve(
        self,
        binding_set: VisualAssetBindingSet,
        plans: list[ReferenceChannelPlan],
    ) -> ReferenceAdmissionResult:
        reference_ids = [plan.reference_id for plan in plans]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("reference channel plans must have unique reference IDs")

        owned_channels: set[str] = set()
        for claim in binding_set.claims:
            for channel in claim.owned_channels:
                owned_channels.update(_PROTECTED_FACE_ALIASES.get(channel, frozenset({channel})))

        decisions: list[ReferenceAdmissionDecision] = []
        for plan in plans:
            if plan.project_id != binding_set.project_id or plan.job_id != binding_set.job_id:
                raise ValueError("reference channel plan project/job does not match the Professional job")
            admitted_channels: list[str] = []
            suppressed_channels: list[str] = []
            admitted_evidence_ids: list[str] = []
            reason_codes: list[str] = []
            unsafe_channels: list[str] = []

            for evidence in plan.channel_evidence:
                canonical = _PROTECTED_FACE_ALIASES.get(evidence.channel, frozenset({evidence.channel}))
                if canonical & owned_channels:
                    suppressed_channels.append(evidence.channel)
                    reason_codes.append("owned_channel_suppressed")
                    continue
                if evidence.representation not in self.safe_representations:
                    unsafe_channels.append(evidence.channel)
                    reason_codes.append("unsafe_full_frame_reference")
                    continue
                admitted_channels.append(evidence.channel)
                admitted_evidence_ids.extend(evidence.evidence_ids)

            admitted_evidence_ids = list(dict.fromkeys(admitted_evidence_ids))
            if unsafe_channels:
                status: Literal["admitted", "partial", "blocked"] = "blocked"
                reason_codes.append("channel_isolation_unproven")
            elif not admitted_channels:
                status = "blocked"
                reason_codes.append(
                    "reference_owned_channel_conflict"
                    if suppressed_channels
                    else "no_safe_admitted_reference_channel"
                )
            elif suppressed_channels:
                status = "partial"
            else:
                status = "admitted"

            decisions.append(
                ReferenceAdmissionDecision(
                    reference_id=plan.reference_id,
                    status=status,
                    admitted_channels=admitted_channels,
                    suppressed_channels=suppressed_channels,
                    admitted_evidence_ids=admitted_evidence_ids,
                    reason_codes=list(dict.fromkeys(reason_codes)),
                )
            )

        if any(item.status == "blocked" for item in decisions):
            return ReferenceAdmissionResult(status="blocked", decisions=decisions)
        return ReferenceAdmissionResult(status="admitted", decisions=decisions)
