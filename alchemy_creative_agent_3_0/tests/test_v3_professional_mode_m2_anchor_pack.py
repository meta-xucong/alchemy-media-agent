from __future__ import annotations

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateResult,
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


def _asset() -> PeopleAsset:
    return PeopleAsset(
        people_asset_id="person_1",
        project_id="project_1",
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id="face_module_1",
            people_asset_id="person_1",
        ),
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
        brain_plan_id="brain_plan_1",
        canonical_prompt_hash="sha256:prompt_1",
    )


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
        )


class FakeReviewer:
    def __init__(self, failing_roles: set[str] | None = None) -> None:
        self.failing_roles = failing_roles or set()
        self.reviews: list[AnchorCandidateResult] = []

    def review(self, candidate: AnchorCandidateResult) -> AnchorReviewDecision:
        self.reviews.append(candidate)
        score = {1: 0.80, 2: 0.96, 3: 0.88}.get(candidate.candidate_index, 0.90)
        if candidate.view_role in self.failing_roles:
            return AnchorReviewDecision(
                status="fail",
                identity_scores=IdentityScoreSummary(
                    same_face_score=0.40,
                    visual_quality_score=0.90,
                    evidence_codes=["same_face_failed"],
                ),
                issue_codes=["identity_gate_failed"],
            )
        return AnchorReviewDecision(
            status="pass",
            identity_scores=IdentityScoreSummary(
                same_face_score=score,
                visual_quality_score=0.91,
                evidence_codes=["same_face_passed"],
            ),
        )


def test_m2_generates_three_front_candidates_then_two_supplementary_views() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    result = AnchorPackPreparationService(generator=generator, reviewer=reviewer).prepare(_request())

    assert result.status == "review"
    assert result.winner_candidate_id == "candidate_standard_front_2"
    assert [request.view_role for request in generator.requests] == [
        "standard_front",
        "standard_front",
        "standard_front",
        "three_quarter",
        "profile",
    ]
    assert len(result.attempts) == 5
    assert result.pack is not None
    assert {view.view_role for view in result.pack.anchor_views} == {"standard_front", "three_quarter", "profile"}


def test_m2_supplementary_requests_reference_the_winning_front() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    AnchorPackPreparationService(generator=generator, reviewer=reviewer).prepare(_request())

    supplementary = generator.requests[3:]
    assert all("output_standard_front_2" in request.reference_evidence_ids for request in supplementary)
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


def test_m2_supplementary_failure_blocks_activation() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer(failing_roles={"profile"})
    result = AnchorPackPreparationService(generator=generator, reviewer=reviewer).prepare(_request())

    assert result.status == "blocked"
    assert result.failure_codes == ["required_supplementary_view_failed"]
    with pytest.raises(ValueError, match="complete reviewed"):
        AnchorPackPreparationService(generator=generator, reviewer=reviewer).activate(result.pack, confirmed=True)


def test_m2_activation_requires_explicit_user_confirmation() -> None:
    generator = FakeGenerator()
    reviewer = FakeReviewer()
    service = AnchorPackPreparationService(generator=generator, reviewer=reviewer)
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
            brain_plan_id="",
            canonical_prompt_hash="",
        )


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
        "activate",
    ]
