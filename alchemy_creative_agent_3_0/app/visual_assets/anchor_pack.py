"""Bounded Face Identity anchor-pack preparation orchestration.

The service coordinates injected generation and review adapters. It never
creates prompt prose or calls a Provider itself; the injected generator must
already be backed by the shared Brain-owned canonical-prompt path.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .contracts import (
    AnchorAuxiliaryReference,
    AnchorCandidateFailureReceipt,
    AnchorView,
    FACE_AUXILIARY_BRIDGE_ROLES,
    FaceViewRole,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)
from .formal_slot_acceptance import (
    FORMAL_SLOT_SHARED_REVIEW_CONTRACT_VERSION,
    FORMAL_SLOT_SHARED_REVIEW_OWNER,
    FormalSlotAcceptanceCore,
    FormalSlotCandidateSummary,
    FormalSlotReceipt,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
    mark_formal_slot_receipt_reload_public_projection_verified,
    validate_formal_slot_receipt_for_activation,
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
        if self.view_role == "standard_front":
            expected_reference_count = 1 + len(supplemental)
        elif self.capture_scope != "character_card_face_identity":
            expected_reference_count = {
                "three_quarter": 2,
                "profile": 3,
            }[self.view_role]
        else:
            expected_reference_count = {
                "left_front_25": 2,
                "three_quarter": 3,
                "profile": 3,
                "right_front_25": 3,
                "reverse_three_quarter": 4,
                "rear_head": 4,
            }[self.view_role]
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
    shared_review_receipts: list[dict[str, Any]] = Field(default_factory=list)


class AnchorCandidateAttempt(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    stage: Literal["front", "supplementary"]
    request: AnchorGenerationRequest
    candidate: AnchorCandidateResult
    review: AnchorReviewDecision


AnchorCandidateFailure = AnchorCandidateFailureReceipt


class AnchorCandidateUnavailable(RuntimeError):
    """Expected fail-closed terminal state for one bounded materialization."""

    def __init__(
        self,
        failure_code: str,
        *,
        mcp_handoff_id: str | None = None,
        output_id: str | None = None,
        candidate_id: str | None = None,
    ) -> None:
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.mcp_handoff_id = mcp_handoff_id
        self.output_id = output_id
        self.candidate_id = candidate_id


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
        "left_front_25",
        "three_quarter",
        "profile",
        "right_front_25",
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
        self.acceptance_core = FormalSlotAcceptanceCore()

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
        front_attempts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]] = []
        prior_views = self._resume_views(request, resume_from_pack)
        prior_auxiliary_references = self._resume_auxiliary_references(request, resume_from_pack)
        prior_failures_by_key = {
            (item.view_role, item.candidate_index): item
            for item in self._resume_failures(request, resume_from_pack)
        }
        views = list(prior_views)
        auxiliary_references = list(prior_auxiliary_references)
        selected_evidence_ids = [
            request.root_source_provenance.source_asset_id,
            *[view.output_id for view in prior_views],
            *[reference.output_id for reference in prior_auxiliary_references],
        ]
        front_view = next((view for view in prior_views if view.view_role == "standard_front"), None)
        winner_candidate_id = front_view.source_candidate_ids[0] if front_view is not None else None

        if front_view is None:
            for candidate_index in range(1, self.FRONT_CANDIDATE_COUNT + 1):
                prior_failure = prior_failures_by_key.get(("standard_front", candidate_index))
                resumable_handoff_id = self._resumable_mcp_handoff_id(request, prior_failure)
                if (
                    prior_failure is not None
                    and not resumable_handoff_id
                    and self._has_later_resumable_mcp_failure(
                        request,
                        prior_failures_by_key,
                        "standard_front",
                        candidate_index,
                        self.FRONT_CANDIDATE_COUNT,
                    )
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
                    mcp_handoff_id=resumable_handoff_id,
                )
                try:
                    candidate, review = self._generate_and_review(generation_request)
                except AnchorCandidateUnavailable as exc:
                    failure = AnchorCandidateFailure(
                        stage="front",
                        view_role="standard_front",
                        candidate_index=candidate_index,
                        failure_code=exc.failure_code,
                        mcp_handoff_id=exc.mcp_handoff_id,
                        output_id=exc.output_id,
                        candidate_id=exc.candidate_id,
                    )
                    generation_failures.append(failure)
                    if (
                        request.generation_channel == "mcp"
                        and exc.failure_code in {"mcp_materialization_pending", "mcp_review_pending"}
                    ):
                        pack = self._pack(
                            request,
                            pack_version_id,
                            views,
                            "failed",
                            auxiliary_references=auxiliary_references,
                            candidate_failures=generation_failures,
                        )
                        self._persist(pack, "fail")
                        return AnchorPackPreparationResult(
                            status="blocked",
                            pack=pack,
                            attempts=attempts,
                            generation_failures=generation_failures,
                            failure_codes=[exc.failure_code],
                            mcp_handoff_ids=self._mcp_handoff_ids_for_view(
                                generation_failures,
                                "standard_front",
                            ),
                        )
                    continue
                attempts.append(
                    AnchorCandidateAttempt(stage="front", request=generation_request, candidate=candidate, review=review)
                )
                front_attempts.append((candidate, review))
                if review.status == "pass":
                    pass
                else:
                    generation_failures.append(
                        AnchorCandidateFailure(
                            stage="front",
                            view_role="standard_front",
                            candidate_index=candidate_index,
                            failure_code=self._failure_code_from_review(review),
                            output_id=candidate.output_id,
                            candidate_id=candidate.candidate_id,
                        )
                    )

            if len(front_attempts) != self.FRONT_CANDIDATE_COUNT:
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    auxiliary_references=auxiliary_references,
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    failure_codes=["formal_face_view_requires_three_reviewed_candidates"],
                    mcp_handoff_ids=self._mcp_handoff_ids_for_view(
                        generation_failures,
                        "standard_front",
                    ),
                )

            try:
                self._validate_formal_attempt_shared_review_authority(front_attempts)
            except ValueError as exc:
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    auxiliary_references=auxiliary_references,
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    failure_codes=[self._formal_acceptance_failure_code(exc)],
                    mcp_handoff_ids=[],
                )

            if not any(review.status == "pass" for _, review in front_attempts):
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    auxiliary_references=auxiliary_references,
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    failure_codes=["no_passing_front_candidate"],
                    mcp_handoff_ids=self._mcp_handoff_ids_for_view(
                        generation_failures,
                        "standard_front",
                    ),
                )

            try:
                front_view = self._formal_view_from_attempts("standard_front", front_attempts)
            except ValueError as exc:
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    auxiliary_references=auxiliary_references,
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    failure_codes=[self._formal_acceptance_failure_code(exc)],
                    mcp_handoff_ids=[],
                )
            views.append(front_view)
            selected_evidence_ids = [request.root_source_provenance.source_asset_id, front_view.output_id]
            winner_candidate_id = (
                front_view.formal_slot_receipt.winner_candidate_id
                if front_view.formal_slot_receipt is not None
                else front_view.source_candidate_ids[0]
            )
            self._persist_resume_checkpoint(
                request,
                pack_version_id,
                views,
                auxiliary_references=auxiliary_references,
                candidate_failures=generation_failures,
            )

        supplementary_roles = (
            self.CHARACTER_CARD_SUPPLEMENTARY_ROLES
            if request.face_view_scope == "character_card"
            else self.SUPPLEMENTARY_ROLES
        )
        for role in supplementary_roles:
            if any(view.view_role == role for view in views) or any(
                reference.reference_role == role for reference in auxiliary_references
            ):
                continue
            supplementary_attempts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]] = []
            candidate_total = (
                1
                if request.face_view_scope == "character_card" and role in FACE_AUXILIARY_BRIDGE_ROLES
                else self.SUPPLEMENTARY_CANDIDATE_COUNT
            )
            for candidate_index in range(1, candidate_total + 1):
                prior_failure = prior_failures_by_key.get((role, candidate_index))
                resumable_handoff_id = self._resumable_mcp_handoff_id(request, prior_failure)
                if (
                    prior_failure is not None
                    and not resumable_handoff_id
                    and self._has_later_resumable_mcp_failure(
                        request,
                        prior_failures_by_key,
                        role,
                        candidate_index,
                        candidate_total,
                    )
                ):
                    generation_failures.append(prior_failure)
                    continue
                generation_request = self._generation_request(
                    request=request,
                    pack_version_id=pack_version_id,
                    view_role=role,
                    candidate_index=candidate_index,
                    reference_evidence_ids=self._reference_evidence_ids_for_view(
                        request,
                        views,
                        auxiliary_references,
                        role,
                    ),
                    mcp_handoff_id=resumable_handoff_id,
                )
                try:
                    candidate, review = self._generate_and_review(generation_request)
                except AnchorCandidateUnavailable as exc:
                    failure = AnchorCandidateFailure(
                        stage="supplementary",
                        view_role=role,
                        candidate_index=candidate_index,
                        failure_code=exc.failure_code,
                        mcp_handoff_id=exc.mcp_handoff_id,
                        output_id=exc.output_id,
                        candidate_id=exc.candidate_id,
                    )
                    generation_failures.append(failure)
                    if (
                        request.generation_channel == "mcp"
                        and exc.failure_code in {"mcp_materialization_pending", "mcp_review_pending"}
                    ):
                        pack = self._pack(
                            request,
                            pack_version_id,
                            views,
                            "failed",
                            auxiliary_references=auxiliary_references,
                            candidate_failures=generation_failures,
                        )
                        self._persist(pack, "fail")
                        return AnchorPackPreparationResult(
                            status="blocked",
                            pack=pack,
                            attempts=attempts,
                            generation_failures=generation_failures,
                            winner_candidate_id=winner_candidate_id,
                            failure_codes=[exc.failure_code],
                            mcp_handoff_ids=self._mcp_handoff_ids_for_view(
                                generation_failures,
                                role,
                            ),
                        )
                    continue
                attempts.append(
                    AnchorCandidateAttempt(
                        stage="supplementary", request=generation_request, candidate=candidate, review=review
                    )
                )
                supplementary_attempts.append((candidate, review))
                if review.status == "pass":
                    pass
                else:
                    generation_failures.append(
                        AnchorCandidateFailure(
                            stage="supplementary",
                            view_role=role,
                            candidate_index=candidate_index,
                            failure_code=self._failure_code_from_review(review),
                            output_id=candidate.output_id,
                            candidate_id=candidate.candidate_id,
                        )
                    )

            if len(supplementary_attempts) != candidate_total:
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    auxiliary_references=auxiliary_references,
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    winner_candidate_id=winner_candidate_id,
                    failure_codes=[
                        "auxiliary_bridge_requires_one_reviewed_candidate"
                        if role in FACE_AUXILIARY_BRIDGE_ROLES
                        else "formal_face_view_requires_three_reviewed_candidates"
                    ],
                    mcp_handoff_ids=self._mcp_handoff_ids_for_view(
                        generation_failures,
                        role,
                    ),
                )

            try:
                self._validate_formal_attempt_shared_review_authority(supplementary_attempts)
            except ValueError as exc:
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    auxiliary_references=auxiliary_references,
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    winner_candidate_id=winner_candidate_id,
                    failure_codes=[self._formal_acceptance_failure_code(exc)],
                    mcp_handoff_ids=[],
                )

            if not any(review.status == "pass" for _, review in supplementary_attempts):
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    auxiliary_references=auxiliary_references,
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
                    mcp_handoff_ids=self._mcp_handoff_ids_for_view(
                        generation_failures,
                        role,
                    ),
                )

            if request.face_view_scope == "character_card" and role in FACE_AUXILIARY_BRIDGE_ROLES:
                try:
                    auxiliary_references.append(self._auxiliary_reference_from_attempts(role, supplementary_attempts))
                except ValueError as exc:
                    pack = self._pack(
                        request,
                        pack_version_id,
                        views,
                        "failed",
                        auxiliary_references=auxiliary_references,
                        candidate_failures=generation_failures,
                    )
                    self._persist(pack, "fail")
                    return AnchorPackPreparationResult(
                        status="blocked",
                        pack=pack,
                        attempts=attempts,
                        generation_failures=generation_failures,
                        winner_candidate_id=winner_candidate_id,
                        failure_codes=[self._formal_acceptance_failure_code(exc)],
                        mcp_handoff_ids=[],
                    )
            else:
                try:
                    views.append(self._formal_view_from_attempts(role, supplementary_attempts))
                except ValueError as exc:
                    pack = self._pack(
                        request,
                        pack_version_id,
                        views,
                        "failed",
                        auxiliary_references=auxiliary_references,
                        candidate_failures=generation_failures,
                    )
                    self._persist(pack, "fail")
                    return AnchorPackPreparationResult(
                        status="blocked",
                        pack=pack,
                        attempts=attempts,
                        generation_failures=generation_failures,
                        winner_candidate_id=winner_candidate_id,
                        failure_codes=[self._formal_acceptance_failure_code(exc)],
                        mcp_handoff_ids=[],
                    )
            selected_evidence_ids = [
                request.root_source_provenance.source_asset_id,
                *[view.output_id for view in views],
                *[reference.output_id for reference in auxiliary_references],
            ]
            self._persist_resume_checkpoint(
                request,
                pack_version_id,
                views,
                auxiliary_references=auxiliary_references,
                candidate_failures=generation_failures,
            )
            if (
                request.generation_channel == "mcp"
                and request.face_view_scope == "character_card"
                and role != supplementary_roles[-1]
            ):
                pack = self._pack(
                    request,
                    pack_version_id,
                    views,
                    "failed",
                    auxiliary_references=auxiliary_references,
                    candidate_failures=generation_failures,
                )
                self._persist(pack, "fail")
                return AnchorPackPreparationResult(
                    status="blocked",
                    pack=pack,
                    attempts=attempts,
                    generation_failures=generation_failures,
                    winner_candidate_id=winner_candidate_id,
                    failure_codes=["mcp_character_card_slot_checkpoint_ready"],
                    mcp_handoff_ids=[],
                )

        pack = self._pack(
            request,
            pack_version_id,
            views,
            "review",
            auxiliary_references=auxiliary_references,
            candidate_failures=generation_failures,
        )
        pack = self._persist_review_pack_with_verified_projection(pack)
        return AnchorPackPreparationResult(
            status="review",
            pack=pack,
            attempts=attempts,
            generation_failures=generation_failures,
            winner_candidate_id=winner_candidate_id,
            mcp_handoff_ids=[],
        )

    @staticmethod
    def _reference_evidence_ids_for_view(
        request: AnchorPackPreparationRequest,
        views: list[AnchorView],
        auxiliary_references: list[AnchorAuxiliaryReference],
        view_role: FaceViewRole,
    ) -> list[str]:
        root = request.root_source_provenance.source_asset_id
        by_role = {view.view_role: view.output_id for view in views if view.active}
        by_role.update({reference.reference_role: reference.output_id for reference in auxiliary_references if reference.active})

        if request.face_view_scope != "character_card":
            return [root, *[view.output_id for view in views if view.active]]
        if view_role == "left_front_25":
            return [root, by_role["standard_front"]]
        if view_role == "three_quarter":
            return [root, by_role["standard_front"], by_role["left_front_25"]]
        if view_role == "profile":
            return [root, by_role["standard_front"], by_role["three_quarter"]]
        if view_role == "right_front_25":
            return [root, by_role["standard_front"], by_role["profile"]]
        if view_role == "reverse_three_quarter":
            # For the final right/front 45° slot, the side-profile card is the
            # pose-depth authority and the right_front_25 bridge is only the
            # same-side identity/framing bridge.  Keep front first so the
            # shared materializer still uses it as the card-family framing
            # reference, then put profile before the 25° bridge so the renderer
            # does not collapse back into a shallow near-front view.
            return [root, by_role["standard_front"], by_role["profile"], by_role["right_front_25"]]
        if view_role == "rear_head":
            return [root, by_role["standard_front"], by_role["profile"], by_role["reverse_three_quarter"]]
        return [root, *[view.output_id for view in views if view.active]]

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
    def _mcp_handoff_ids_for_view(
        failures: list[AnchorCandidateFailure],
        view_role: FaceViewRole,
    ) -> list[str]:
        return AnchorPackPreparationService._mcp_handoff_ids(
            [item for item in failures if item.view_role == view_role]
        )

    @staticmethod
    def _resumable_mcp_handoff_id(
        request: AnchorPackPreparationRequest,
        failure: AnchorCandidateFailure | None,
    ) -> str | None:
        if request.generation_channel != "mcp" or failure is None:
            return None
        handoff_id = str(failure.mcp_handoff_id or "").strip()
        if not handoff_id:
            return None
        # Older failed pack versions may carry a handoff id even when the
        # public failure code has already advanced to shared_visual_review_failed.
        # In MCP mode that handoff is the only durable resume handle; consume it
        # once through the shared Product API/Vision path, then the new review
        # result will persist a plain visual-review failure if the pixels still
        # do not pass.
        return handoff_id

    @classmethod
    def _has_later_resumable_mcp_failure(
        cls,
        request: AnchorPackPreparationRequest,
        failures_by_key: dict[tuple[str, int], AnchorCandidateFailure],
        view_role: str,
        candidate_index: int,
        max_candidate_index: int,
    ) -> bool:
        if request.generation_channel != "mcp":
            return False
        for later_index in range(candidate_index + 1, max_candidate_index + 1):
            if cls._resumable_mcp_handoff_id(
                request,
                failures_by_key.get((view_role, later_index)),
            ):
                return True
        return False

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
            ("standard_front", "three_quarter", "profile", "reverse_three_quarter", "rear_head")
            if request.face_view_scope == "character_card"
            else ("standard_front", *AnchorPackPreparationService.SUPPLEMENTARY_ROLES)
        )
        views = [
            view
            for view in resume_from_pack.anchor_views
            if view.active and view.view_role not in FACE_AUXILIARY_BRIDGE_ROLES
        ]
        view_roles = [view.view_role for view in views]
        if len(view_roles) != len(set(view_roles)) or tuple(view_roles) != roles[: len(view_roles)]:
            raise ValueError("character_card_resume_checkpoint_invalid")
        return views

    @staticmethod
    def _resume_auxiliary_references(
        request: AnchorPackPreparationRequest,
        resume_from_pack: IdentityAnchorPackVersion | None,
    ) -> list[AnchorAuxiliaryReference]:
        if resume_from_pack is None:
            return []
        if request.face_view_scope != "character_card":
            return []
        if resume_from_pack.status != "failed":
            return []
        references = [reference for reference in getattr(resume_from_pack, "auxiliary_references", []) if reference.active]
        roles = [reference.reference_role for reference in references]
        if len(roles) != len(set(roles)):
            raise ValueError("character_card_resume_auxiliary_checkpoint_invalid")
        if any(role not in FACE_AUXILIARY_BRIDGE_ROLES for role in roles):
            raise ValueError("character_card_resume_auxiliary_checkpoint_invalid")
        return references

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
                failure.failure_code in {"mcp_materialization_pending", "mcp_review_pending"}
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

    def _persist_review_pack_with_verified_projection(
        self,
        pack: IdentityAnchorPackVersion,
    ) -> IdentityAnchorPackVersion:
        if self.catalog is None:
            return pack
        self._persist(pack, "review")
        reloaded = self._reload_pack(pack)
        verified = self._mark_formal_receipts_after_projection(reloaded)
        self._persist(verified, "review")
        reloaded_verified = self._reload_pack(verified)
        for view in reloaded_verified.anchor_views:
            if view.active and view.formal_slot_receipt is not None:
                view.formal_slot_public_summary()
                validate_formal_slot_receipt_for_activation(view.formal_slot_receipt)
        for reference in reloaded_verified.auxiliary_references:
            if reference.active:
                reference.formal_slot_public_summary()
        return reloaded_verified

    def _reload_pack(self, pack: IdentityAnchorPackVersion) -> IdentityAnchorPackVersion:
        if self.catalog is None or not hasattr(self.catalog, "get_pack"):
            raise ValueError("formal Face Identity receipt verification requires a reloadable catalog")
        reloaded = self.catalog.get_pack(  # type: ignore[attr-defined]
            pack.root_source_provenance.project_id,
            pack.people_asset_id,
            pack.pack_version_id,
        )
        if reloaded is None:
            raise ValueError("formal Face Identity receipt verification failed to reload pack")
        return reloaded

    @staticmethod
    def _mark_formal_receipts_after_projection(pack: IdentityAnchorPackVersion) -> IdentityAnchorPackVersion:
        views: list[AnchorView] = []
        for view in pack.anchor_views:
            receipt = view.formal_slot_receipt
            views.append(
                view.model_copy(
                    update={
                        "formal_slot_receipt": mark_formal_slot_receipt_reload_public_projection_verified(receipt)
                        if receipt is not None
                        else None
                    }
                )
            )
        auxiliary_references: list[AnchorAuxiliaryReference] = []
        for reference in pack.auxiliary_references:
            auxiliary_references.append(
                reference.model_copy(
                    update={
                        "formal_slot_receipt": mark_formal_slot_receipt_reload_public_projection_verified(
                            reference.formal_slot_receipt
                        )
                    }
                )
            )
        return pack.model_copy(update={"anchor_views": views, "auxiliary_references": auxiliary_references})

    def _persist_resume_checkpoint(
        self,
        request: AnchorPackPreparationRequest,
        pack_version_id: str,
        views: list[AnchorView],
        *,
        auxiliary_references: list[AnchorAuxiliaryReference] | None = None,
        candidate_failures: list[AnchorCandidateFailure] | None = None,
    ) -> None:
        if self.catalog is None:
            return
        if request.face_view_scope != "character_card":
            return
        checkpoint = self._pack(
            request,
            pack_version_id,
            list(views),
            "failed",
            auxiliary_references=list(auxiliary_references or []),
            candidate_failures=candidate_failures,
        )
        self._persist(checkpoint, "fail")

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
                else None
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
    def _failure_code_from_review(review: AnchorReviewDecision) -> str:
        """Expose the first safe review gate code instead of a misleading generic code."""

        for code in review.issue_codes:
            safe_code = str(code or "").strip()
            if safe_code:
                return safe_code
        return "shared_visual_review_failed"

    @staticmethod
    def _formal_acceptance_failure_code(error: ValueError) -> str:
        message = str(error)
        if "status mismatch" in message or "multiple canonical shared Vision receipts" in message:
            return "formal_face_view_shared_review_receipt_mismatch"
        if "canonical shared Vision receipt" in message:
            return "formal_face_view_shared_review_receipt_missing"
        if "reload/public projection" in message:
            return "formal_face_view_reload_public_projection_missing"
        if "standard_three_candidate" in message or "exactly three" in message:
            return "formal_face_view_three_candidate_contract_failed"
        if "auxiliary_first_pass_reference" in message or "bridge" in message:
            return "formal_face_auxiliary_reference_contract_failed"
        return "formal_face_view_acceptance_contract_failed"

    def _formal_view_from_attempts(
        self,
        view_role: FaceViewRole,
        attempts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]],
    ) -> AnchorView:
        receipt = self._formal_receipt_for_attempts(
            view_role=view_role,
            attempts=attempts,
            acceptance_mode="standard_three_candidate",
        )
        winner_candidate, winner_review = self._candidate_by_id(attempts, receipt.winner_candidate_id)
        return AnchorView(
            view_id=winner_candidate.view_id,
            view_role=winner_candidate.view_role,
            output_id=winner_candidate.output_id,
            source_candidate_ids=[candidate.candidate_id for candidate, _ in attempts],
            identity_scores=winner_review.identity_scores,
            formal_slot_receipt=receipt,
        )

    def _auxiliary_reference_from_attempts(
        self,
        view_role: FaceViewRole,
        attempts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]],
    ) -> AnchorAuxiliaryReference:
        receipt = self._formal_receipt_for_attempts(
            view_role=view_role,
            attempts=attempts,
            acceptance_mode="auxiliary_first_pass_reference",
        )
        winner_candidate, winner_review = self._candidate_by_id(attempts, receipt.winner_candidate_id)
        return AnchorAuxiliaryReference(
            reference_id=f"aux_{winner_candidate.view_id}",
            reference_role=winner_candidate.view_role,
            output_id=winner_candidate.output_id,
            source_candidate_ids=[candidate.candidate_id for candidate, _ in attempts],
            identity_scores=winner_review.identity_scores,
            formal_slot_receipt=receipt,
        )

    def _formal_receipt_for_attempts(
        self,
        *,
        view_role: FaceViewRole,
        attempts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]],
        acceptance_mode: Literal["standard_three_candidate", "auxiliary_first_pass_reference"],
    ) -> FormalSlotReceipt:
        score_by_candidate_id = {
            candidate.candidate_id: review.identity_scores.selection_key()
            for candidate, review in attempts
        }
        slot_key = (
            f"face_identity_bridge.{view_role}"
            if acceptance_mode == "auxiliary_first_pass_reference"
            else f"face_identity.{view_role}"
        )
        return self.acceptance_core.accept(
            module="face_identity",
            slot_key=slot_key,
            acceptance_mode=acceptance_mode,
            candidates=[
                self._formal_candidate_summary(candidate, review)
                for candidate, review in attempts
            ],
            framing_summary=self._formal_requirement_summary("framing", attempts),
            parity_summary=self._formal_requirement_summary("parity", attempts),
            identity_summary=self._formal_requirement_summary("identity", attempts),
            ranking_key=(
                (lambda candidate: score_by_candidate_id[candidate.candidate_id])
                if acceptance_mode == "standard_three_candidate"
                else None
            ),
        )

    @staticmethod
    def _candidate_by_id(
        attempts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]],
        candidate_id: str | None,
    ) -> tuple[AnchorCandidateResult, AnchorReviewDecision]:
        for candidate, review in attempts:
            if candidate.candidate_id == candidate_id:
                return candidate, review
        raise ValueError("formal Face Identity winner does not match reviewed candidates")

    def _formal_candidate_summary(
        self,
        candidate: AnchorCandidateResult,
        review: AnchorReviewDecision,
    ) -> FormalSlotCandidateSummary:
        return FormalSlotCandidateSummary(
            candidate_index=candidate.candidate_index,
            candidate_id=candidate.candidate_id,
            output_id=candidate.output_id,
            reviewed=True,
            shared_review=self._formal_shared_review_summary(review),
        )

    def _validate_formal_attempt_shared_review_authority(
        self,
        attempts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]],
    ) -> None:
        for _, review in attempts:
            self._formal_shared_review_summary(review)

    @staticmethod
    def _formal_shared_review_summary(review: AnchorReviewDecision) -> FormalSlotSharedReviewSummary:
        canonical_receipts: list[FormalSlotSharedReviewSummary] = []
        for receipt in review.shared_review_receipts:
            if not isinstance(receipt, dict):
                continue
            if (
                receipt.get("owner") != FORMAL_SLOT_SHARED_REVIEW_OWNER
                or receipt.get("contract_version") != FORMAL_SLOT_SHARED_REVIEW_CONTRACT_VERSION
            ):
                continue
            canonical_receipts.append(FormalSlotSharedReviewSummary.model_validate(receipt))
        if len(canonical_receipts) > 1:
            raise ValueError("formal Face Identity candidates cannot carry multiple canonical shared Vision receipts")
        if canonical_receipts:
            summary = canonical_receipts[0]
            if review.status == "pass" and not summary.passed:
                raise ValueError("formal Face Identity shared Vision receipt status mismatch")
            if review.status == "fail" and summary.passed:
                raise ValueError("formal Face Identity shared Vision receipt status mismatch")
            return summary
        raise ValueError("formal Face Identity candidates require canonical shared Vision receipt")

    @staticmethod
    def _formal_requirement_summary(
        requirement: Literal["framing", "parity", "identity"],
        attempts: list[tuple[AnchorCandidateResult, AnchorReviewDecision]],
    ) -> FormalSlotRequirementSummary:
        passing_reviews = [review for _, review in attempts if review.status == "pass"]
        all_parity_verified = all(candidate.prompt_reference_parity_verified for candidate, _ in attempts)
        if requirement == "parity":
            return FormalSlotRequirementSummary(
                status="pass" if all_parity_verified else "fail",
                evidence_codes=["face_identity_reference_parity_verified"] if all_parity_verified else [],
                dimensions={"reference_parity": 1.0 if all_parity_verified else 0.0} if all_parity_verified else {},
            )
        if requirement == "framing":
            best_pose_score = max(
                (review.identity_scores.pose_compliance_score for review in passing_reviews),
                default=0.0,
            )
            return FormalSlotRequirementSummary(
                status="pass" if passing_reviews else "fail",
                evidence_codes=["face_identity_view_profile_reviewed"] if passing_reviews else [],
                dimensions={"pose_compliance_score": best_pose_score} if passing_reviews else {},
            )
        best_same_face_score = max(
            (review.identity_scores.same_face_score for review in passing_reviews),
            default=0.0,
        )
        evidence_codes = sorted(
            {
                code
                for review in passing_reviews
                for code in review.identity_scores.evidence_codes
                if str(code or "").strip()
            }
        )
        if passing_reviews and not evidence_codes:
            evidence_codes = ["face_identity_shared_identity_review_verified"]
        return FormalSlotRequirementSummary(
            status="pass" if passing_reviews else "fail",
            evidence_codes=evidence_codes,
            dimensions={"same_face_score": best_same_face_score} if passing_reviews else {},
        )

    @staticmethod
    def _pack(
        request: AnchorPackPreparationRequest,
        pack_version_id: str,
        views: list[AnchorView],
        status: Literal["review", "failed"],
        *,
        auxiliary_references: list[AnchorAuxiliaryReference] | None = None,
        candidate_failures: list[AnchorCandidateFailure] | None = None,
    ) -> IdentityAnchorPackVersion:
        return IdentityAnchorPackVersion(
            pack_version_id=pack_version_id,
            people_asset_id=request.asset.people_asset_id,
            status=status,
            anchor_views=views,
            auxiliary_references=list(auxiliary_references or []),
            candidate_failures=list(candidate_failures or []),
            root_source_provenance=request.root_source_provenance,
            user_activation_confirmed=False,
        )
