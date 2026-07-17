"""Bounded Face Identity anchor-pack preparation orchestration.

The service coordinates injected generation and review adapters. It never
creates prompt prose or calls a Provider itself; the injected generator must
already be backed by the shared Brain-owned canonical-prompt path.
"""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import uuid4

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .contracts import (
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)


class AnchorGenerationRequest(V3BaseModel):
    """Typed evidence request; prompt content is deliberately not a field.

    The reference list is a serial identity chain, not an arbitrary bag of
    images: front uses only the root, three-quarter uses root plus the winning
    front, and profile uses root plus both prior winners.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    project_id: str
    people_asset_id: str
    pack_version_id: str
    view_role: Literal["standard_front", "three_quarter", "profile"]
    candidate_index: int = Field(ge=1, le=3)
    root_source_asset_id: str
    reference_evidence_ids: list[str] = Field(default_factory=list)
    brain_plan_id: str
    canonical_prompt_hash: str
    reference_strategy: Literal["serial_anchor_pack_root_reuse_v1"] = "serial_anchor_pack_root_reuse_v1"

    @field_validator("brain_plan_id", "canonical_prompt_hash", "root_source_asset_id")
    @classmethod
    def require_nonempty_evidence(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Brain plan, canonical prompt hash, and root evidence are required")
        return value

    @model_validator(mode="after")
    def enforce_serial_reference_chain(self) -> "AnchorGenerationRequest":
        references = self.reference_evidence_ids
        if not references or references[0] != self.root_source_asset_id:
            raise ValueError("anchor generation references must start with the root source asset")
        if len(references) != len(set(references)):
            raise ValueError("anchor generation references must be unique")

        expected_reference_count = {
            "standard_front": 1,
            "three_quarter": 2,
            "profile": 3,
        }[self.view_role]
        if len(references) != expected_reference_count:
            raise ValueError(
                f"{self.view_role} requires the serial identity chain with "
                f"{expected_reference_count} reference evidence IDs"
            )
        return self


class AnchorPackPreparationRequest(V3BaseModel):
    """Preparation input before a pack version is user-activated."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    project_id: str
    asset: PeopleAsset
    root_source_provenance: RootSourceProvenance
    brain_plan_id: str
    canonical_prompt_hash: str

    @field_validator("brain_plan_id", "canonical_prompt_hash")
    @classmethod
    def require_brain_contract(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Brain plan and canonical prompt hash are required before generation")
        return value

    @model_validator(mode="after")
    def same_project(self) -> "AnchorPackPreparationRequest":
        if self.project_id != self.asset.project_id or self.project_id != self.root_source_provenance.project_id:
            raise ValueError("asset, root evidence, and preparation request must belong to the same project")
        return self


class AnchorCandidateResult(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    candidate_id: str
    view_id: str
    output_id: str
    view_role: Literal["standard_front", "three_quarter", "profile"]
    candidate_index: int = Field(ge=1, le=3)
    source_candidate_ids: list[str] = Field(min_length=1)
    source_asset_ids: list[str] = Field(min_length=1)


class AnchorReviewDecision(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: Literal["pass", "fail"]
    identity_scores: IdentityScoreSummary
    issue_codes: list[str] = Field(default_factory=list)


class AnchorCandidateAttempt(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    stage: Literal["front", "supplementary"]
    request: AnchorGenerationRequest
    candidate: AnchorCandidateResult
    review: AnchorReviewDecision


class AnchorPackPreparationResult(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: Literal["review", "blocked"]
    pack: IdentityAnchorPackVersion
    attempts: list[AnchorCandidateAttempt] = Field(default_factory=list)
    winner_candidate_id: str | None = None
    failure_codes: list[str] = Field(default_factory=list)


class AnchorCandidateGenerator(Protocol):
    def generate(self, request: AnchorGenerationRequest) -> AnchorCandidateResult:
        ...


class AnchorCandidateReviewer(Protocol):
    def review(self, candidate: AnchorCandidateResult) -> AnchorReviewDecision:
        ...


class AnchorPackCatalog(Protocol):
    def save_pack(
        self,
        pack: IdentityAnchorPackVersion,
        *,
        project_id: str | None = None,
        event_type: Literal["prepare", "review", "activate", "supersede", "fail"] = "review",
    ) -> IdentityAnchorPackVersion:
        ...


class AnchorPackPreparationService:
    """Run the bounded front-winner and supplementary-view workflow."""

    FRONT_CANDIDATE_COUNT = 3
    SUPPLEMENTARY_CANDIDATE_COUNT = 3
    SUPPLEMENTARY_ROLES = ("three_quarter", "profile")

    def __init__(
        self,
        *,
        generator: AnchorCandidateGenerator,
        reviewer: AnchorCandidateReviewer,
        catalog: AnchorPackCatalog | None = None,
    ) -> None:
        self.generator = generator
        self.reviewer = reviewer
        self.catalog = catalog

    def prepare(self, request: AnchorPackPreparationRequest) -> AnchorPackPreparationResult:
        pack_version_id = f"pack_{uuid4().hex}"
        attempts: list[AnchorCandidateAttempt] = []
        passing_fronts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]] = []

        for candidate_index in range(1, self.FRONT_CANDIDATE_COUNT + 1):
            generation_request = self._generation_request(
                request=request,
                pack_version_id=pack_version_id,
                view_role="standard_front",
                candidate_index=candidate_index,
                reference_evidence_ids=[request.root_source_provenance.source_asset_id],
            )
            candidate, review = self._generate_and_review(generation_request)
            attempts.append(
                AnchorCandidateAttempt(stage="front", request=generation_request, candidate=candidate, review=review)
            )
            if review.status == "pass":
                passing_fronts.append((candidate, review))

        if not passing_fronts:
            pack = self._pack(request, pack_version_id, [], "failed")
            self._persist(pack, "fail")
            return AnchorPackPreparationResult(
                status="blocked",
                pack=pack,
                attempts=attempts,
                failure_codes=["no_passing_front_candidate"],
            )

        winner, winner_review = self._select_winner(passing_fronts)
        views = [self._view(winner, winner_review)]
        selected_evidence_ids = [request.root_source_provenance.source_asset_id, winner.output_id]
        for role in self.SUPPLEMENTARY_ROLES:
            passing_supplementary: list[tuple[AnchorCandidateResult, AnchorReviewDecision]] = []
            for candidate_index in range(1, self.SUPPLEMENTARY_CANDIDATE_COUNT + 1):
                generation_request = self._generation_request(
                    request=request,
                    pack_version_id=pack_version_id,
                    view_role=role,
                    candidate_index=candidate_index,
                    reference_evidence_ids=list(selected_evidence_ids),
                )
                candidate, review = self._generate_and_review(generation_request)
                attempts.append(
                    AnchorCandidateAttempt(
                        stage="supplementary", request=generation_request, candidate=candidate, review=review
                    )
                )
                if review.status == "pass":
                    passing_supplementary.append((candidate, review))

            if not passing_supplementary:
                pack = self._pack(request, pack_version_id, views, "failed")
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    winner_candidate_id=winner.candidate_id,
                    failure_codes=["required_supplementary_view_failed"],
                )

            supplementary_winner, supplementary_review = self._select_winner(passing_supplementary)
            views.append(self._view(supplementary_winner, supplementary_review))
            selected_evidence_ids.append(supplementary_winner.output_id)

        pack = self._pack(request, pack_version_id, views, "review")
        self._persist(pack, "review")
        return AnchorPackPreparationResult(
            status="review",
            pack=pack,
            attempts=attempts,
            winner_candidate_id=winner.candidate_id,
        )

    def activate(self, pack: IdentityAnchorPackVersion, *, confirmed: bool) -> IdentityAnchorPackVersion:
        if pack.status != "review":
            raise ValueError("only a complete reviewed pack can be activated")
        if not confirmed:
            raise ValueError("explicit user confirmation is required to activate the face pack")
        payload = pack.model_dump(mode="python")
        payload.update({"status": "active", "user_activation_confirmed": True})
        active_pack = IdentityAnchorPackVersion.model_validate(payload)
        self._persist(active_pack, "activate")
        return active_pack

    def _persist(
        self,
        pack: IdentityAnchorPackVersion,
        event_type: Literal["review", "activate", "fail"],
    ) -> None:
        if self.catalog is not None:
            self.catalog.save_pack(pack, project_id=pack.root_source_provenance.project_id, event_type=event_type)

    def _generation_request(
        self,
        *,
        request: AnchorPackPreparationRequest,
        pack_version_id: str,
        view_role: Literal["standard_front", "three_quarter", "profile"],
        candidate_index: int,
        reference_evidence_ids: list[str],
    ) -> AnchorGenerationRequest:
        return AnchorGenerationRequest(
            project_id=request.project_id,
            people_asset_id=request.asset.people_asset_id,
            pack_version_id=pack_version_id,
            view_role=view_role,
            candidate_index=candidate_index,
            root_source_asset_id=request.root_source_provenance.source_asset_id,
            reference_evidence_ids=reference_evidence_ids,
            brain_plan_id=request.brain_plan_id,
            canonical_prompt_hash=request.canonical_prompt_hash,
            reference_strategy="serial_anchor_pack_root_reuse_v1",
        )

    def _generate_and_review(
        self, request: AnchorGenerationRequest
    ) -> tuple[AnchorCandidateResult, AnchorReviewDecision]:
        candidate = self.generator.generate(request)
        if candidate.view_role != request.view_role or candidate.candidate_index != request.candidate_index:
            raise ValueError("generator returned a candidate that does not match the frozen view request")
        review = self.reviewer.review(candidate)
        return candidate, review

    @staticmethod
    def _select_winner(
        passing_candidates: list[tuple[AnchorCandidateResult, AnchorReviewDecision]],
    ) -> tuple[AnchorCandidateResult, AnchorReviewDecision]:
        """Select one winner without allowing polish or pose to outrank likeness."""

        return max(
            passing_candidates,
            key=lambda item: (*item[1].identity_scores.selection_key(), item[0].candidate_id),
        )

    @staticmethod
    def _view(candidate: AnchorCandidateResult, review: AnchorReviewDecision) -> AnchorView:
        return AnchorView(
            view_id=candidate.view_id,
            view_role=candidate.view_role,
            output_id=candidate.output_id,
            source_candidate_ids=list(candidate.source_candidate_ids),
            identity_scores=review.identity_scores,
        )

    @staticmethod
    def _pack(
        request: AnchorPackPreparationRequest,
        pack_version_id: str,
        views: list[AnchorView],
        status: Literal["review", "failed"],
    ) -> IdentityAnchorPackVersion:
        return IdentityAnchorPackVersion(
            pack_version_id=pack_version_id,
            people_asset_id=request.asset.people_asset_id,
            status=status,
            anchor_views=views,
            root_source_provenance=request.root_source_provenance,
            user_activation_confirmed=False,
        )
