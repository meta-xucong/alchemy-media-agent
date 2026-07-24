from __future__ import annotations

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateResult,
    AnchorCandidateUnavailable,
    AnchorGenerationRequest,
    AnchorPackPreparationRequest,
    AnchorPackPreparationService,
    AnchorReviewDecision,
)
from alchemy_creative_agent_3_0.app.visual_assets.catalog import PersistentVisualAssetCatalog
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    FaceIdentityModule,
    PeopleAsset,
    RootSourceProvenance,
    IdentityScoreSummary,
)
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotSharedReviewSummary,
)


PREPARATION_INTENT = (
    "Prepare a coherent professional identity anchor pack for the same person while "
    "letting the current request own presentation and capture treatment."
)


def _asset() -> PeopleAsset:
    return PeopleAsset(
        people_asset_id="person_1",
        project_id="project_1",
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id="face_module_1",
            people_asset_id="person_1",
        ),
        preparation_intent=PREPARATION_INTENT,
    )


def _request() -> AnchorPackPreparationRequest:
    return AnchorPackPreparationRequest(
        project_id="project_1",
        asset=_asset(),
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="asset_root_1",
            project_id="project_1",
        ),
        preparation_intent=PREPARATION_INTENT,
        brain_plan_id="brain_plan_1",
        canonical_prompt_hash="sha256:prompt_1",
    )


def _character_card_request() -> AnchorPackPreparationRequest:
    return _request().model_copy(update={"face_view_scope": "character_card"})


class FakeGenerator:
    def __init__(self) -> None:
        self.requests: list[AnchorGenerationRequest] = []

    def generate(self, request: AnchorGenerationRequest) -> AnchorCandidateResult:
        self.requests.append(request)
        token = f"{request.view_role}_{request.candidate_index}"
        return AnchorCandidateResult(
            candidate_id=f"candidate_{token}",
            view_id=f"view_{token}",
            output_id=f"output_{token}",
            view_role=request.view_role,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"candidate_{token}"],
            source_asset_ids=["asset_root_1"],
            brain_plan_id=f"brain_{token}",
            canonical_prompt_hash=f"sha256:{token}",
            prompt_compilation_id=f"prompt_{token}",
            prompt_reference_parity_verified=True,
        )


class FakeReviewer:
    def __init__(self, failing_roles: set[str] | None = None) -> None:
        self.failing_roles = failing_roles or set()
        self.reviews: list[AnchorCandidateResult] = []

    @staticmethod
    def _shared_receipt(status: str) -> dict[str, object]:
        return FormalSlotSharedReviewSummary(
            status=status,  # type: ignore[arg-type]
            evidence_codes=["shared_visual_review_verified"] if status == "pass" else [],
            issue_codes=[] if status == "pass" else ["shared_visual_review_failed"],
            score_dimensions=["identity_or_subject_consistency", "generic_visual_quality"] if status == "pass" else [],
            framing_delta_dimensions=["face_identity_view_framing_delta"] if status == "pass" else [],
        ).model_dump(mode="json")

    def review(self, candidate: AnchorCandidateResult) -> AnchorReviewDecision:
        self.reviews.append(candidate)
        # Candidate 3 is the most recognizable person even though it has a
        # small tilt. Candidate 2 is polished but intentionally genericized.
        score = {1: 0.91, 2: 0.89, 3: 0.97}.get(candidate.candidate_index, 0.88)
        distinctive = {1: 0.93, 2: 0.68, 3: 0.94}.get(candidate.candidate_index, 0.86)
        realism = {1: 0.88, 2: 0.52, 3: 0.86}.get(candidate.candidate_index, 0.84)
        pose = {1: 1.00, 2: 1.00, 3: 0.78}.get(candidate.candidate_index, 0.90)
        overperfection = {1: 0.04, 2: 0.40, 3: 0.03}.get(candidate.candidate_index, 0.05)
        if candidate.view_role in self.failing_roles:
            return AnchorReviewDecision(
                status="fail",
                identity_scores=IdentityScoreSummary(
                    same_face_score=0.40,
                    visual_quality_score=0.90,
                    distinctive_feature_score=0.40,
                    human_realism_score=0.40,
                    pose_compliance_score=pose,
                    ai_overperfection_penalty=0.0,
                    evidence_codes=["same_face_failed"],
                ),
                issue_codes=["identity_gate_failed"],
                shared_review_receipts=[self._shared_receipt("fail")],
            )
        return AnchorReviewDecision(
            status="pass",
            identity_scores=IdentityScoreSummary(
                same_face_score=score,
                visual_quality_score=0.99 if candidate.candidate_index == 2 else 0.92,
                distinctive_feature_score=distinctive,
                human_realism_score=realism,
                pose_compliance_score=pose,
                ai_overperfection_penalty=overperfection,
                evidence_codes=["same_face_passed", "distinctive_features_reviewed"],
            ),
            shared_review_receipts=[self._shared_receipt("pass")],
        )


class MissingSharedReceiptReviewer(FakeReviewer):
    def review(self, candidate: AnchorCandidateResult) -> AnchorReviewDecision:
        decision = super().review(candidate)
        return decision.model_copy(update={"shared_review_receipts": []})


def test_m2_generates_three_candidates_per_view_in_serial_identity_order() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    result = AnchorPackPreparationService(generator=generator, reviewer=reviewer).prepare(_request())

    assert result.status == "review"
    assert result.winner_candidate_id == "candidate_standard_front_3"
    assert [request.view_role for request in generator.requests] == [
        "standard_front",
        "standard_front",
        "standard_front",
        "three_quarter",
        "three_quarter",
        "three_quarter",
        "profile",
        "profile",
        "profile",
    ]
    assert len(result.attempts) == 9
    assert result.pack is not None
    assert {view.view_role for view in result.pack.anchor_views} == {"standard_front", "three_quarter", "profile"}
    assert [view.output_id for view in result.pack.anchor_views] == [
        "output_standard_front_3",
        "output_three_quarter_3",
        "output_profile_3",
    ]
    assert all(view.formal_slot_receipt is not None for view in result.pack.anchor_views)
    assert all(view.formal_slot_receipt.acceptance_mode == "standard_three_candidate" for view in result.pack.anchor_views)
    assert all(view.formal_slot_receipt.reviewed_candidate_count == 3 for view in result.pack.anchor_views)
    assert all(view.formal_slot_receipt.reload_public_projection_verified is False for view in result.pack.anchor_views)


def test_m2_without_catalog_cannot_activate_unverified_formal_receipts() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    service = AnchorPackPreparationService(generator=generator, reviewer=reviewer)
    result = service.prepare(_request())

    assert result.status == "review"
    assert all(view.formal_slot_receipt is not None for view in result.pack.anchor_views)
    assert all(view.formal_slot_receipt.activation_eligible is False for view in result.pack.anchor_views)
    with pytest.raises(ValueError, match="standard_three_candidate receipt"):
        service.activate(result.pack, confirmed=True)


def test_m2_catalog_reload_verifies_formal_receipts_before_activation(tmp_path) -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    catalog = PersistentVisualAssetCatalog(tmp_path)
    service = AnchorPackPreparationService(generator=generator, reviewer=reviewer, catalog=catalog)
    result = service.prepare(_request())

    assert result.status == "review"
    reloaded = catalog.get_pack("project_1", "person_1", result.pack.pack_version_id)
    assert reloaded is not None
    assert all(view.formal_slot_receipt is not None for view in reloaded.anchor_views)
    assert all(view.formal_slot_receipt.reload_public_projection_verified is True for view in reloaded.anchor_views)
    assert all(view.formal_slot_public_summary()["activation_eligible"] is True for view in reloaded.anchor_views)
    active = service.activate(reloaded, confirmed=True)
    assert active.status == "active"


def test_m2_missing_shared_review_receipt_blocks_formal_face_slot() -> None:
    generator = FakeGenerator()
    result = AnchorPackPreparationService(
        generator=generator,
        reviewer=MissingSharedReceiptReviewer(),
    ).prepare(_request())

    assert result.status == "blocked"
    assert result.failure_codes == ["formal_face_view_shared_review_receipt_missing"]
    assert [request.view_role for request in generator.requests] == [
        "standard_front",
        "standard_front",
        "standard_front",
    ]


def test_m2_character_card_bridge_is_auxiliary_and_formal_views_still_use_three_candidates(tmp_path) -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    catalog = PersistentVisualAssetCatalog(tmp_path)
    service = AnchorPackPreparationService(generator=generator, reviewer=reviewer, catalog=catalog)
    result = service.prepare(_character_card_request())

    assert result.status == "review"
    assert [request.view_role for request in generator.requests] == [
        "standard_front",
        "standard_front",
        "standard_front",
        "left_front_25",
        "three_quarter",
        "three_quarter",
        "three_quarter",
        "profile",
        "profile",
        "profile",
        "right_front_25",
        "reverse_three_quarter",
        "reverse_three_quarter",
        "reverse_three_quarter",
        "rear_head",
        "rear_head",
        "rear_head",
    ]
    assert {view.view_role for view in result.pack.anchor_views} == {
        "standard_front",
        "three_quarter",
        "profile",
        "reverse_three_quarter",
        "rear_head",
    }
    assert {reference.reference_role for reference in result.pack.auxiliary_references} == {
        "left_front_25",
        "right_front_25",
    }
    assert all(
        view.formal_slot_receipt is not None
        and view.formal_slot_receipt.acceptance_mode == "standard_three_candidate"
        and view.formal_slot_receipt.reviewed_candidate_count == 3
        and view.formal_slot_receipt.activation_eligible is True
        for view in result.pack.anchor_views
    )
    assert all(
        reference.formal_slot_receipt.acceptance_mode == "auxiliary_first_pass_reference"
        and reference.formal_slot_receipt.slot_scope == "auxiliary_reference"
        and reference.formal_slot_receipt.reviewed_candidate_count == 1
        and reference.formal_slot_receipt.activation_eligible is False
        for reference in result.pack.auxiliary_references
    )
    active = service.activate(result.pack, confirmed=True)
    assert active.status == "active"


def test_m2_supplementary_requests_reference_the_winning_front() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    AnchorPackPreparationService(generator=generator, reviewer=reviewer).prepare(_request())

    supplementary = generator.requests[3:]
    assert all("output_standard_front_3" in request.reference_evidence_ids for request in supplementary)
    three_quarter = supplementary[:3]
    profile = supplementary[3:]
    assert all("output_three_quarter_3" not in request.reference_evidence_ids for request in three_quarter)
    assert all("output_three_quarter_3" in request.reference_evidence_ids for request in profile)
    assert all(not hasattr(request, "prompt") for request in generator.requests)


def test_m2_front_failure_blocks_before_supplementary_generation() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer(failing_roles={"standard_front"})
    result = AnchorPackPreparationService(generator=generator, reviewer=reviewer).prepare(_request())

    assert result.status == "blocked"
    assert result.pack is not None
    assert result.pack.status == "failed"
    assert len(generator.requests) == 3
    assert result.failure_codes == ["no_passing_front_candidate"]


def test_m2_one_provider_terminal_failure_does_not_abort_remaining_bounded_candidates_but_blocks_formal_receipt() -> None:
    class PartiallyUnavailableGenerator(FakeGenerator):
        def generate(self, request: AnchorGenerationRequest) -> AnchorCandidateResult:
            self.requests.append(request)
            if request.view_role == "standard_front" and request.candidate_index == 2:
                raise AnchorCandidateUnavailable("provider_policy_blocked")
            # Avoid appending a second time in the base fake.
            self.requests.pop()
            return super().generate(request)

    generator = PartiallyUnavailableGenerator()
    result = AnchorPackPreparationService(generator=generator, reviewer=FakeReviewer()).prepare(_request())

    assert result.status == "blocked"
    assert len(generator.requests) == 3
    assert result.failure_codes == ["formal_face_view_requires_three_reviewed_candidates"]
    assert [(item.view_role, item.candidate_index, item.failure_code) for item in result.generation_failures] == [
        ("standard_front", 2, "provider_policy_blocked")
    ]
    assert len(result.attempts) == 2


def test_m2_supplementary_failure_blocks_activation() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer(failing_roles={"profile"})
    result = AnchorPackPreparationService(generator=generator, reviewer=reviewer).prepare(_request())

    assert result.status == "blocked"
    assert result.failure_codes == ["required_supplementary_view_failed"]
    assert len(generator.requests) == 9
    with pytest.raises(ValueError, match="complete reviewed"):
        AnchorPackPreparationService(generator=generator, reviewer=reviewer).activate(result.pack, confirmed=True)


def test_m2_failed_three_quarter_stage_does_not_generate_profile_candidates() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer(failing_roles={"three_quarter"})
    result = AnchorPackPreparationService(generator=generator, reviewer=reviewer).prepare(_request())

    assert result.status == "blocked"
    assert result.failure_codes == ["required_supplementary_view_failed"]
    assert len(generator.requests) == 6
    assert all(request.view_role != "profile" for request in generator.requests)


@pytest.mark.parametrize(
    ("view_role", "reference_evidence_ids"),
    [
        ("standard_front", ["asset_root_1", "output_front_1"]),
        ("three_quarter", ["asset_root_1"]),
        ("profile", ["asset_root_1", "output_front_1"]),
        ("profile", ["asset_root_1", "output_front_1", "output_three_quarter_1", "extra"]),
        ("profile", ["output_front_1", "asset_root_1", "output_three_quarter_1"]),
    ],
)
def test_m2_generation_contract_rejects_non_serial_reference_chains(
    view_role: str, reference_evidence_ids: list[str]
) -> None:
    with pytest.raises(ValidationError, match="serial identity chain|root source asset|unique"):
        AnchorGenerationRequest(
            project_id="project_1",
            people_asset_id="person_1",
            pack_version_id="pack_1",
            view_role=view_role,
            candidate_index=1,
            preparation_intent=PREPARATION_INTENT,
            root_source_asset_id="asset_root_1",
            reference_evidence_ids=reference_evidence_ids,
            brain_plan_id="brain_plan_1",
            canonical_prompt_hash="sha256:prompt_1",
        )


def test_m2_generation_contract_accepts_the_serial_profile_chain() -> None:
    request = AnchorGenerationRequest(
        project_id="project_1",
        people_asset_id="person_1",
        pack_version_id="pack_1",
        view_role="profile",
        candidate_index=3,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="asset_root_1",
        reference_evidence_ids=["asset_root_1", "output_front_3", "output_three_quarter_2"],
        brain_plan_id="brain_plan_1",
        canonical_prompt_hash="sha256:prompt_1",
    )

    assert request.reference_evidence_ids == ["asset_root_1", "output_front_3", "output_three_quarter_2"]


def test_m2_activation_requires_explicit_user_confirmation(tmp_path) -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    service = AnchorPackPreparationService(
        generator=generator,
        reviewer=reviewer,
        catalog=PersistentVisualAssetCatalog(tmp_path),
    )
    result = service.prepare(_request())

    with pytest.raises(ValueError, match="explicit user confirmation"):
        service.activate(result.pack, confirmed=False)
    active = service.activate(result.pack, confirmed=True)
    assert active.status == "active"
    assert active.user_activation_confirmed is True


def test_m2_requires_brain_plan_and_canonical_prompt_hash_before_generation() -> None:
    with pytest.raises(ValidationError):
        AnchorPackPreparationRequest(
            project_id="project_1",
            asset=_asset(),
            root_source_provenance=RootSourceProvenance(
                source_type="uploaded_portrait",
                source_asset_id="asset_root_1",
                project_id="project_1",
            ),
            preparation_intent=PREPARATION_INTENT,
            brain_plan_id="",
            canonical_prompt_hash="",
        )


def test_m2_rejects_preparation_intent_that_differs_from_frozen_people_asset() -> None:
    with pytest.raises(ValidationError, match="immutable People Asset intent"):
        AnchorPackPreparationRequest(
            project_id="project_1",
            asset=_asset(),
            root_source_provenance=RootSourceProvenance(
                source_type="uploaded_portrait",
                source_asset_id="asset_root_1",
                project_id="project_1",
            ),
            preparation_intent="A different late-bound direction.",
            brain_plan_id="brain_plan_1",
            canonical_prompt_hash="sha256:prompt_1",
        )


def test_m2_likeness_is_primary_over_polish_and_small_pose_defects() -> None:
    reviewer = FakeReviewer()
    candidate_scores = {
        1: reviewer.review(
            AnchorCandidateResult(
                candidate_id="candidate_1",
                view_id="view_1",
                output_id="output_1",
                view_role="standard_front",
                candidate_index=1,
                source_candidate_ids=["candidate_1"],
                source_asset_ids=["asset_root_1"],
                brain_plan_id="brain_1",
                canonical_prompt_hash="sha256:1",
                prompt_compilation_id="prompt_1",
                prompt_reference_parity_verified=True,
            )
        ).identity_scores,
        2: reviewer.review(
            AnchorCandidateResult(
                candidate_id="candidate_2",
                view_id="view_2",
                output_id="output_2",
                view_role="standard_front",
                candidate_index=2,
                source_candidate_ids=["candidate_2"],
                source_asset_ids=["asset_root_1"],
                brain_plan_id="brain_2",
                canonical_prompt_hash="sha256:2",
                prompt_compilation_id="prompt_2",
                prompt_reference_parity_verified=True,
            )
        ).identity_scores,
        3: reviewer.review(
            AnchorCandidateResult(
                candidate_id="candidate_3",
                view_id="view_3",
                output_id="output_3",
                view_role="standard_front",
                candidate_index=3,
                source_candidate_ids=["candidate_3"],
                source_asset_ids=["asset_root_1"],
                brain_plan_id="brain_3",
                canonical_prompt_hash="sha256:3",
                prompt_compilation_id="prompt_3",
                prompt_reference_parity_verified=True,
            )
        ).identity_scores,
    }

    assert max(candidate_scores, key=lambda index: candidate_scores[index].selection_key()) == 3
    assert candidate_scores[2].visual_quality_score > candidate_scores[3].visual_quality_score
    assert candidate_scores[3].pose_compliance_score < candidate_scores[1].pose_compliance_score


def test_m2_persists_review_and_activation_history_when_catalog_is_injected(tmp_path) -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    catalog = PersistentVisualAssetCatalog(tmp_path)
    service = AnchorPackPreparationService(generator=generator, reviewer=reviewer, catalog=catalog)

    result = service.prepare(_request())
    assert result.pack.status == "review"
    assert catalog.get_pack("project_1", "person_1", result.pack.pack_version_id).status == "review"

    active = service.activate(result.pack, confirmed=True)
    assert active.status == "active"
    assert [item.event_type for item in catalog.list_pack_history("project_1", "person_1")] == [
        "review",
        "review",
        "activate",
    ]
