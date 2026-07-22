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
    AnchorCandidateFailureReceipt,
    AnchorView,
    FaceViewRole,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)


class AnchorGenerationRequest(V3BaseModel):
    """Typed evidence request; prompt content is deliberately not a field.

    The reference list is a serial identity chain, not an arbitrary bag of
    images: front uses the root plus at most one declared supplementary source,
    three-quarter uses the root plus the winning front, and profile uses the
    root plus both prior winners.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    project_id: str
    people_asset_id: str
    pack_version_id: str
    view_role: FaceViewRole
    candidate_index: int = Field(ge=1, le=3)
    preparation_intent: str
    root_source_asset_id: str
    reference_evidence_ids: list[str] = Field(default_factory=list)
    initial_supplementary_source_asset_ids: list[str] = Field(default_factory=list, max_length=1)
    # The actual plan/hash do not exist until the Remote Brain and canonical
    # materializer finish this candidate.  They are therefore optional on the
    # pre-generation request and mandatory on ``AnchorCandidateResult``.
    brain_plan_id: str | None = None
    canonical_prompt_hash: str | None = None
    reference_strategy: Literal["serial_anchor_pack_root_reuse_v1"] = "serial_anchor_pack_root_reuse_v1"
    generation_channel: Literal["provider", "mcp"] = "provider"
    mcp_operation_id: str | None = None
    mcp_handoff_id: str | None = None
    # The shared execution path needs to know which geometric contract owns
    # this capture. Character Card face views are face/head evidence only;
    # the ordinary Anchor Pack keeps its historical whole-person contract.
    capture_scope: Literal["anchor_pack", "character_card_face_identity"] = "anchor_pack"

    @field_validator(
        "brain_plan_id",
        "canonical_prompt_hash",
        "preparation_intent",
        "root_source_asset_id",
    )
    @classmethod
    def require_nonempty_evidence(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Brain plan, canonical prompt hash, and root evidence are required")
        return value

    @model_validator(mode="after")
    def enforce_serial_reference_chain(self) -> "AnchorGenerationRequest":
        references = self.reference_evidence_ids
        if not references or references[0] != self.root_source_asset_id:
            raise ValueError("anchor generation references must start with the root source asset")
        if len(references) != len(set(references)):
            raise ValueError("anchor generation references must be unique")

        supplemental = [str(item or "").strip() for item in self.initial_supplementary_source_asset_ids]
        if any(not item for item in supplemental):
            raise ValueError("supplementary identity source IDs must be nonempty")
        if self.root_source_asset_id in supplemental or len(supplemental) != len(set(supplemental)):
            raise ValueError("supplementary identity sources must be unique and cannot repeat the root")
        expected_reference_count = (
            1 + len(supplemental)
            if self.view_role == "standard_front"
            else {
                "three_quarter": 2,
                "profile": 3,
                "reverse_three_quarter": 4,
                "rear_head": 5,
            }[self.view_role]
        )
        if len(references) != expected_reference_count:
            raise ValueError(
                f"{self.view_role} requires the serial identity chain with "
                f"{expected_reference_count} reference evidence IDs"
            )
        if self.view_role == "standard_front" and references[1:] != supplemental:
            raise ValueError("front supplementary evidence must match immutable source provenance")
        return self


class AnchorPackPreparationRequest(V3BaseModel):
    """Preparation input before a pack version is user-activated."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    project_id: str
    asset: PeopleAsset
    root_source_provenance: RootSourceProvenance
    preparation_intent: str
    brain_plan_id: str | None = None
    canonical_prompt_hash: str | None = None
    face_view_scope: Literal["base", "character_card"] = "base"
    generation_channel: Literal["provider", "mcp"] = "provider"
    pending_mcp_handoff_ids: list[str] = Field(default_factory=list)

    @field_validator("brain_plan_id", "canonical_prompt_hash", "preparation_intent")
    @classmethod
    def require_brain_contract(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Brain plan and canonical prompt hash are required before generation")
        return value

    @model_validator(mode="after")
    def same_project(self) -> "AnchorPackPreparationRequest":
        if self.project_id != self.asset.project_id or self.project_id != self.root_source_provenance.project_id:
            raise ValueError("asset, root evidence, and preparation request must belong to the same project")
        if self.asset.preparation_intent is None:
            raise ValueError("People Asset preparation intent is required")
        if self.preparation_intent != self.asset.preparation_intent:
            raise ValueError("preparation intent must match the immutable People Asset intent")
        return self


class AnchorCandidateResult(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    candidate_id: str
    view_id: str
    output_id: str
    view_role: FaceViewRole
    candidate_index: int = Field(ge=1, le=3)
    source_candidate_ids: list[str] = Field(min_length=1)
    source_asset_ids: list[str] = Field(min_length=1)
    brain_plan_id: str
    canonical_prompt_hash: str
    prompt_compilation_id: str
    prompt_reference_parity_verified: bool

    @field_validator("brain_plan_id", "canonical_prompt_hash", "prompt_compilation_id")
    @classmethod
    def require_actual_candidate_provenance(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("actual per-candidate Brain and canonical prompt provenance is required")
        return value

    @model_validator(mode="after")
    def require_materialization_parity(self) -> "AnchorCandidateResult":
        if not self.prompt_reference_parity_verified:
            raise ValueError("anchor candidate prompt/reference parity must be verified")
        return self


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


AnchorCandidateFailure = AnchorCandidateFailureReceipt


class AnchorCandidateUnavailable(RuntimeError):
    """Expected fail-closed terminal state for one bounded materialization."""

    def __init__(self, failure_code: str, *, mcp_handoff_id: str | None = None) -> None:
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.mcp_handoff_id = mcp_handoff_id


class AnchorPackPreparationResult(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: Literal["review", "blocked"]
    pack: IdentityAnchorPackVersion
    attempts: list[AnchorCandidateAttempt] = Field(default_factory=list)
    generation_failures: list[AnchorCandidateFailure] = Field(default_factory=list)
    winner_candidate_id: str | None = None
    failure_codes: list[str] = Field(default_factory=list)
    # Public-safe discovery for an explicit MCP continuation.  The list is
    # intentionally opaque and append-only; submitting an artifact still
    # requires the per-handoff nonce/hash contract in the shared router.
    mcp_handoff_ids: list[str] = Field(default_factory=list)


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
    CHARACTER_CARD_SUPPLEMENTARY_ROLES = (
        "three_quarter",
        "profile",
        "reverse_three_quarter",
        "rear_head",
    )

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

    def prepare(
        self,
        request: AnchorPackPreparationRequest,
        *,
        resume_from_pack: IdentityAnchorPackVersion | None = None,
    ) -> AnchorPackPreparationResult:
        """Prepare a pack, or continue a failed pack from its last good view.

        Each missing view receives the existing three-candidate bounded budget.
        A failed operation is persisted as a failed pack; an explicit later
        resume creates a new append-only pack version and reuses only the
        already reviewed views from that failed version.
        """

        pack_version_id = f"pack_{uuid4().hex}"
        attempts: list[AnchorCandidateAttempt] = []
        generation_failures: list[AnchorCandidateFailure] = []
        passing_fronts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]] = []
        prior_views = self._resume_views(request, resume_from_pack)
        prior_failures_by_key = {
            (item.view_role, item.candidate_index): item
            for item in self._resume_failures(request, resume_from_pack)
        }
        views = list(prior_views)
        selected_evidence_ids = [
            request.root_source_provenance.source_asset_id,
            *[view.output_id for view in prior_views],
        ]
        front_view = next((view for view in prior_views if view.view_role == "standard_front"), None)
        winner_candidate_id = front_view.source_candidate_ids[0] if front_view is not None else None

        if front_view is None:
            for candidate_index in range(1, self.FRONT_CANDIDATE_COUNT + 1):
                prior_failure = prior_failures_by_key.get(("standard_front", candidate_index))
                if prior_failure is not None and prior_failure.failure_code == "shared_visual_review_failed":
                    generation_failures.append(prior_failure)
                    continue
                if (
                    prior_failure is not None
                    and prior_failure.failure_code == "mcp_materialization_pending"
                    and not str(prior_failure.mcp_handoff_id or "").strip()
                ):
                    generation_failures.append(prior_failure)
                    continue
                generation_request = self._generation_request(
                    request=request,
                    pack_version_id=pack_version_id,
                    view_role="standard_front",
                    candidate_index=candidate_index,
                    reference_evidence_ids=[
                        request.root_source_provenance.source_asset_id,
                        *request.root_source_provenance.supplementary_source_asset_ids,
                    ],
                    mcp_handoff_id=(
                        str(prior_failure.mcp_handoff_id).strip()
                        if prior_failure is not None
                        and prior_failure.failure_code == "mcp_materialization_pending"
                        and str(prior_failure.mcp_handoff_id or "").strip()
                        else None
                    ),
                )
                try:
                    candidate, review = self._generate_and_review(generation_request)
                except AnchorCandidateUnavailable as exc:
                    generation_failures.append(
                        AnchorCandidateFailure(
                            stage="front",
                            view_role="standard_front",
                            candidate_index=candidate_index,
                            failure_code=exc.failure_code,
                            mcp_handoff_id=exc.mcp_handoff_id,
                        )
                    )
                    continue
                attempts.append(
                    AnchorCandidateAttempt(stage="front", request=generation_request, candidate=candidate, review=review)
                )
                if review.status == "pass":
                    passing_fronts.append((candidate, review))
                else:
                    generation_failures.append(
                        AnchorCandidateFailure(
                            stage="front",
                            view_role="standard_front",
                            candidate_index=candidate_index,
                            failure_code="shared_visual_review_failed",
                        )
                    )

            if not passing_fronts:
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    failure_codes=["no_passing_front_candidate"],
                    mcp_handoff_ids=self._mcp_handoff_ids(generation_failures),
                )

            winner, winner_review = self._select_winner(passing_fronts)
            views.append(self._view(winner, winner_review))
            selected_evidence_ids = [request.root_source_provenance.source_asset_id, winner.output_id]
            winner_candidate_id = winner.candidate_id

        supplementary_roles = (
            self.CHARACTER_CARD_SUPPLEMENTARY_ROLES
            if request.face_view_scope == "character_card"
            else self.SUPPLEMENTARY_ROLES
        )
        for role in supplementary_roles:
            if any(view.view_role == role for view in views):
                continue
            passing_supplementary: list[tuple[AnchorCandidateResult, AnchorReviewDecision]] = []
            for candidate_index in range(1, self.SUPPLEMENTARY_CANDIDATE_COUNT + 1):
                prior_failure = prior_failures_by_key.get((role, candidate_index))
                if prior_failure is not None and prior_failure.failure_code == "shared_visual_review_failed":
                    generation_failures.append(prior_failure)
                    continue
                if (
                    prior_failure is not None
                    and prior_failure.failure_code == "mcp_materialization_pending"
                    and not str(prior_failure.mcp_handoff_id or "").strip()
                ):
                    generation_failures.append(prior_failure)
                    continue
                generation_request = self._generation_request(
                    request=request,
                    pack_version_id=pack_version_id,
                    view_role=role,
                    candidate_index=candidate_index,
                    reference_evidence_ids=list(selected_evidence_ids),
                    mcp_handoff_id=(
                        str(prior_failure.mcp_handoff_id).strip()
                        if prior_failure is not None
                        and prior_failure.failure_code == "mcp_materialization_pending"
                        and str(prior_failure.mcp_handoff_id or "").strip()
                        else None
                    ),
                )
                try:
                    candidate, review = self._generate_and_review(generation_request)
                except AnchorCandidateUnavailable as exc:
                    generation_failures.append(
                        AnchorCandidateFailure(
                            stage="supplementary",
                            view_role=role,
                            candidate_index=candidate_index,
                            failure_code=exc.failure_code,
                            mcp_handoff_id=exc.mcp_handoff_id,
                        )
                    )
                    continue
                attempts.append(
                    AnchorCandidateAttempt(
                        stage="supplementary", request=generation_request, candidate=candidate, review=review
                    )
                )
                if review.status == "pass":
                    passing_supplementary.append((candidate, review))
                else:
                    generation_failures.append(
                        AnchorCandidateFailure(
                            stage="supplementary",
                            view_role=role,
                            candidate_index=candidate_index,
                            failure_code="shared_visual_review_failed",
                        )
                    )

            if not passing_supplementary:
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    winner_candidate_id=winner_candidate_id,
                    failure_codes=["required_supplementary_view_failed"],
                    mcp_handoff_ids=self._mcp_handoff_ids(generation_failures),
                )

            supplementary_winner, supplementary_review = self._select_winner(passing_supplementary)
            views.append(self._view(supplementary_winner, supplementary_review))
            selected_evidence_ids.append(supplementary_winner.output_id)

        pack = self._pack(request, pack_version_id, views, "review", candidate_failures=generation_failures)
        self._persist(pack, "review")
        return AnchorPackPreparationResult(
            status="review",
            pack=pack,
            attempts=attempts,
            generation_failures=generation_failures,
            winner_candidate_id=winner_candidate_id,
            mcp_handoff_ids=self._mcp_handoff_ids(generation_failures),
        )

    @staticmethod
    def _mcp_handoff_ids(failures: list[AnchorCandidateFailure]) -> list[str]:
        return list(
            dict.fromkeys(
                str(item.mcp_handoff_id).strip()
                for item in failures
                if str(item.mcp_handoff_id or "").strip()
            )
        )

    @staticmethod
    def _resume_views(
        request: AnchorPackPreparationRequest,
        resume_from_pack: IdentityAnchorPackVersion | None,
    ) -> list[AnchorView]:
        if resume_from_pack is None:
            return []
        if resume_from_pack.status != "failed":
            raise ValueError("only a failed Character Card pack can be resumed")
        if (
            resume_from_pack.people_asset_id != request.asset.people_asset_id
            or resume_from_pack.root_source_provenance.source_asset_id
            != request.root_source_provenance.source_asset_id
        ):
            raise ValueError("character_card_resume_binding_mismatch")
        roles = (
            ("standard_front", *AnchorPackPreparationService.CHARACTER_CARD_SUPPLEMENTARY_ROLES)
            if request.face_view_scope == "character_card"
            else ("standard_front", *AnchorPackPreparationService.SUPPLEMENTARY_ROLES)
        )
        views = [view for view in resume_from_pack.anchor_views if view.active]
        view_roles = [view.view_role for view in views]
        if len(view_roles) != len(set(view_roles)) or tuple(view_roles) != roles[: len(view_roles)]:
            raise ValueError("character_card_resume_checkpoint_invalid")
        return views

    @staticmethod
    def _resume_failures(
        request: AnchorPackPreparationRequest,
        resume_from_pack: IdentityAnchorPackVersion | None,
    ) -> list[AnchorCandidateFailure]:
        if resume_from_pack is None:
            return []
        if request.face_view_scope != "character_card":
            return []
        if resume_from_pack.status != "failed":
            return []
        allowed_roles = {
            "standard_front",
            *AnchorPackPreparationService.CHARACTER_CARD_SUPPLEMENTARY_ROLES,
        }
        failures: list[AnchorCandidateFailure] = []
        seen: set[tuple[str, int]] = set()
        for failure in getattr(resume_from_pack, "candidate_failures", []) or []:
            role = str(failure.view_role)
            key = (role, int(failure.candidate_index))
            if role not in allowed_roles or key in seen:
                raise ValueError("character_card_resume_failure_checkpoint_invalid")
            if not str(failure.failure_code or "").strip():
                raise ValueError("character_card_resume_failure_checkpoint_invalid")
            if (
                failure.failure_code == "mcp_materialization_pending"
                and not str(failure.mcp_handoff_id or "").strip()
            ):
                raise ValueError("character_card_resume_failure_checkpoint_invalid")
            failures.append(failure)
            seen.add(key)
        return failures

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
        view_role: FaceViewRole,
        candidate_index: int,
        reference_evidence_ids: list[str],
        mcp_handoff_id: str | None = None,
    ) -> AnchorGenerationRequest:
        return AnchorGenerationRequest(
            project_id=request.project_id,
            people_asset_id=request.asset.people_asset_id,
            pack_version_id=pack_version_id,
            view_role=view_role,
            candidate_index=candidate_index,
            preparation_intent=request.preparation_intent,
            root_source_asset_id=request.root_source_provenance.source_asset_id,
            reference_evidence_ids=reference_evidence_ids,
            initial_supplementary_source_asset_ids=list(
                request.root_source_provenance.supplementary_source_asset_ids
            ),
            brain_plan_id=request.brain_plan_id,
            canonical_prompt_hash=request.canonical_prompt_hash,
            reference_strategy="serial_anchor_pack_root_reuse_v1",
            generation_channel=request.generation_channel,
            mcp_operation_id=(
                f"{request.asset.people_asset_id}:{view_role}:{candidate_index}"
                if request.generation_channel == "mcp"
                else None
            ),
            mcp_handoff_id=(
                str(mcp_handoff_id).strip()
                if request.generation_channel == "mcp" and str(mcp_handoff_id or "").strip()
                else (
                    str(request.pending_mcp_handoff_ids[candidate_index - 1]).strip()
                    if request.generation_channel == "mcp"
                    and 0 <= candidate_index - 1 < len(request.pending_mcp_handoff_ids)
                    and str(request.pending_mcp_handoff_ids[candidate_index - 1] or "").strip()
                    else None
                )
            ),
            capture_scope=(
                "character_card_face_identity"
                if request.face_view_scope == "character_card"
                else "anchor_pack"
            ),
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
        *,
        candidate_failures: list[AnchorCandidateFailure] | None = None,
    ) -> IdentityAnchorPackVersion:
        return IdentityAnchorPackVersion(
            pack_version_id=pack_version_id,
            people_asset_id=request.asset.people_asset_id,
            status=status,
            anchor_views=views,
            candidate_failures=list(candidate_failures or []),
            root_source_provenance=request.root_source_provenance,
            user_activation_confirmed=False,
        )
