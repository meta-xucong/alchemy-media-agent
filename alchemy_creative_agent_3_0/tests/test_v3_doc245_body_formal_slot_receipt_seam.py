"""Doc245 / Task7 Body Silhouette formal-slot receipt seam contracts."""

from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorReviewDecision
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS,
    project_generic_visual_review_receipt,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BODY_SLOT_KEYS,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardSlot,
    CharacterCardState,
    character_card_formal_slot_receipt_public_summary,
    project_character_card_slot_success_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary
from alchemy_creative_agent_3_0.app.visual_assets.library import VisualAssetLibraryLifecycleService
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge


def _generic_body_shared_receipt(*, status: str = "pass") -> dict[str, object]:
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
        "status": status,
        "evidence_codes": [
            "shared_visual_review_verified",
            "shared_visual_review_status_pass",
            "body_silhouette_framing_reviewed",
        ]
        if status == "pass"
        else ["shared_visual_review_unverified"],
        "issue_codes": [] if status == "pass" else ["shared_visual_review_rejected"],
        "score_dimensions": ["generic_visual_quality", "identity_or_subject_consistency"],
        "framing_delta_dimensions": ["body_scale_delta", "ground_contact_delta"],
    }


def _body_review_metadata_for_vision(slot_key: str = "body.front_full") -> dict[str, object]:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key=slot_key,
    )
    return {
        "project_id": "project_doc245_body_review",
        "capability_execution_envelope": {
            "activation_plan": {
                "plan_id": "plan_doc245_body_review",
                "activation_mode": "enforced",
                "active_capability_ids": ["human_realism"],
                "dependency_order": ["human_realism"],
                "metadata": {
                    "professional_face_identity_quality_contract": stage_metadata[
                        "professional_face_identity_quality_contract"
                    ],
                },
            },
            "resolved_constraint_ledger": {
                "hard_semantic_contract": True,
                "review_contracts": [],
                "provider_projection": {},
            },
        },
        "professional_planning_metadata": stage_metadata,
    }


def test_doc245_body_review_contract_exposes_framing_dimensions_to_shared_vision() -> None:
    contract = active_review_contract(_body_review_metadata_for_vision())

    professional_quality = contract["professional_identity_quality"]
    assert professional_quality["body_silhouette_review"]["applies"] is True
    assert set(BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS).issubset(
        set(professional_quality["body_silhouette_review"]["framing_delta_dimensions"])
    )
    assert set(BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS).issubset(set(contract["score_dimensions"]))


def test_doc245_body_review_contract_carries_body_only_wardrobe_contract() -> None:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.front_full",
    )

    quality_contract = stage_metadata["professional_face_identity_quality_contract"]
    wardrobe_contract = quality_contract["body_silhouette_wardrobe_contract"]

    assert wardrobe_contract["scope"] == "body_silhouette_only"
    assert wardrobe_contract["top"] == "simple_white_short_sleeve_top"
    assert wardrobe_contract["bottom"] == "plain_solid_shorts"
    assert wardrobe_contract["feet"] == "barefoot"
    assert set(wardrobe_contract["forbidden"]) == {
        "long_pants",
        "socks",
        "shoes",
        "skirt_or_dress",
    }

    review_contract = active_review_contract(_body_review_metadata_for_vision("body.front_full"))
    body_review = review_contract["professional_identity_quality"]["body_silhouette_review"]

    assert body_review["wardrobe_contract"] == wardrobe_contract
    assert "body_silhouette_wardrobe_contract_drift" in body_review["issue_codes"]


def test_doc245_body_review_contract_carries_reference_driven_hair_continuity_without_fixed_style() -> None:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.side_full",
    )

    quality_contract = stage_metadata["professional_face_identity_quality_contract"]
    hair_contract = quality_contract["body_silhouette_hair_continuity_contract"]

    assert hair_contract["scope"] == "body_silhouette_only"
    assert hair_contract["source"] == "current_project_confirmed_face_identity_references"
    assert hair_contract["fixed_hairstyle_text"] is None
    assert set(hair_contract["required_continuity"]) == {
        "same_hairstyle_category",
        "same_hair_length_tier",
        "same_bangs_or_parting_pattern",
        "same_overall_hair_outline",
    }
    assert "view_angle" in hair_contract["allowed_variation"]
    assert "natural_body_view_movement" in hair_contract["allowed_variation"]
    assert "obvious_hair_length_tier_change" in hair_contract["forbidden"]

    serialized = str(hair_contract).lower()
    assert "long straight" not in serialized
    assert "long hair" not in serialized

    review_contract = active_review_contract(_body_review_metadata_for_vision("body.side_full"))
    body_review = review_contract["professional_identity_quality"]["body_silhouette_review"]

    assert body_review["hair_continuity_contract"] == hair_contract
    assert "body_silhouette_hair_continuity_drift" in body_review["issue_codes"]


def test_doc245_body_rear_review_uses_rear_continuity_instead_of_visible_face() -> None:
    metadata = _body_review_metadata_for_vision("body.rear_full")
    contract = active_review_contract(metadata)

    body_review = contract["professional_identity_quality"]["body_silhouette_review"]
    assert body_review["applies"] is True

    prompt = _inspection_prompt(metadata)

    assert "Body rear-full evidence rule" in prompt
    assert "visible face or facial landmarks are not required" in prompt
    assert "rear-head and hair outline" in prompt
    assert "full-body containment" in prompt


def test_doc245_generic_projector_preserves_body_framing_dimensions_only_when_allowed() -> None:
    score_card = {
        "generic_visual_quality": 0.96,
        "identity_or_subject_consistency": 0.94,
        "body_scale_delta": 0.02,
        "ground_contact_delta": 0.01,
        "raw_untrusted_body_private_dimension": 0.99,
    }

    missing_allowlist = project_generic_visual_review_receipt(
        score_card=score_card,
        issue_codes=[],
        verified=True,
        raw_status="pass",
    )
    assert missing_allowlist.status == "pass"
    assert missing_allowlist.framing_delta_dimensions == ()

    body_receipt = project_generic_visual_review_receipt(
        score_card=score_card,
        issue_codes=[],
        verified=True,
        raw_status="pass",
        framing_dimension_allowlist=BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS,
    )

    assert set(body_receipt.framing_delta_dimensions) == {"body_scale_delta", "ground_contact_delta"}
    assert "raw_untrusted_body_private_dimension" not in body_receipt.framing_delta_dimensions


def _legacy_body_slot_success_receipt(slot_key: str, output_id: str) -> dict[str, object]:
    shared_reviews = [_generic_body_shared_receipt()]
    return project_character_card_slot_success_receipt(
        CharacterCardSharedRuntimeReceipt(
            reviewed_candidate_count=3,
            acceptance_mode="standard_three_candidate",
            final_winner_selection_verified=True,
            prompt_reference_parity_verified=True,
            shared_review_receipts=shared_reviews,
        ),
        module="body_silhouette",
        slot_key=slot_key,
        output_id=output_id,
        shared_review_receipts=shared_reviews,
    )


def _scores(index: int, *, body_eligible: bool = True) -> IdentityScoreSummary:
    evidence_codes = ["body_candidate_reviewed"]
    if body_eligible:
        evidence_codes.append("body_silhouette_profile_eligible")
    return IdentityScoreSummary(
        same_face_score=0.80 + index / 100,
        visual_quality_score=0.70 + index / 100,
        evidence_codes=evidence_codes,
    )


def _review(index: int, *, status: str = "pass", body_eligible: bool = True) -> AnchorReviewDecision:
    issue_codes = [] if status == "pass" else ["candidate_failed"]
    if not body_eligible:
        issue_codes.append("body_silhouette_profile_rejected")
    return AnchorReviewDecision(
        status=status,  # type: ignore[arg-type]
        identity_scores=_scores(index, body_eligible=body_eligible),
        issue_codes=issue_codes,
        shared_review_receipts=[_generic_body_shared_receipt(status=status)],
    )


def _generic_pass_review_without_body_profile_evidence(index: int) -> AnchorReviewDecision:
    return AnchorReviewDecision(
        status="pass",
        identity_scores=IdentityScoreSummary(
            same_face_score=0.80 + index / 100,
            visual_quality_score=0.70 + index / 100,
            evidence_codes=[
                "shared_real_pixel_review_verified",
                "shared_visual_review_verified",
                "shared_visual_review_status_pass",
            ],
        ),
        issue_codes=[],
        shared_review_receipts=[_generic_body_shared_receipt(status="pass")],
    )


def _body_attempt(
    index: int,
    *,
    slot_key: str = "body.front_full",
    source_class: str = "brain_inferred",
    reference_output_ids: list[str] | None = None,
    consent_provenance_id: str | None = None,
    review: AnchorReviewDecision | None = None,
) -> object:
    refs = list(reference_output_ids or ["face_front_output", "face_profile_output", "face_rear_output"])
    request = CharacterCardCandidateRequest(
        project_id="visual_asset_body",
        people_asset_id="people_body",
        card_version_id="card_body_formal",
        module="body_silhouette",
        slot_key=slot_key,  # type: ignore[arg-type]
        candidate_index=index,
        reference_output_ids=refs,
        user_intent="neutral body silhouette profile",
        source_class=source_class,  # type: ignore[arg-type]
        consent_provenance_id=consent_provenance_id,
    )
    candidate = CharacterCardCandidateResult(
        candidate_id=f"candidate_{slot_key}_{index}",
        output_id=f"output_{slot_key}_{index}",
        module="body_silhouette",
        slot_key=slot_key,
        candidate_index=index,
        source_candidate_ids=[f"source_{slot_key}_{index}"],
        source_output_ids=refs,
        canonical_prompt_hash=f"prompt_hash_{slot_key}_{index}",
        prompt_compilation_id=f"prompt_compilation_{slot_key}_{index}",
        prompt_reference_parity_verified=True,
    )
    from alchemy_creative_agent_3_0.app.visual_assets.character_card import CharacterCardCandidateAttempt

    return CharacterCardCandidateAttempt(
        request=request,
        candidate=candidate,
        review=review or _generic_pass_review_without_body_profile_evidence(index),
    )


class _BodyGenerator:
    def __init__(self) -> None:
        self.requests: list[CharacterCardCandidateRequest] = []

    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        self.requests.append(request)
        return CharacterCardCandidateResult(
            candidate_id=f"candidate_{request.slot_key}_{request.candidate_index}",
            output_id=f"output_{request.slot_key}_{request.candidate_index}",
            module=request.module,
            slot_key=request.slot_key,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"source_{request.slot_key}_{request.candidate_index}"],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash=f"prompt_hash_{request.slot_key}_{request.candidate_index}",
            prompt_compilation_id=f"prompt_compilation_{request.slot_key}_{request.candidate_index}",
            prompt_reference_parity_verified=True,
        )


class _BodyReviewer:
    def __init__(
        self,
        *,
        failing_indexes: set[int] | None = None,
        enhanced_failing_indexes: set[int] | None = None,
    ) -> None:
        self.failing_indexes = set(failing_indexes or set())
        self.enhanced_failing_indexes = set(enhanced_failing_indexes or set())

    def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
        return _review(
            candidate.candidate_index,
            status="fail" if candidate.candidate_index in self.failing_indexes else "pass",
            body_eligible=candidate.candidate_index not in self.enhanced_failing_indexes,
        )


def _card_ready_for_body() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_body_formal")
    face_slots = dict(card.face_slots)
    for slot_key, output_id in {
        "face.front": "face_front_output",
        "face.profile": "face_profile_output",
        "face.rear_head": "face_rear_output",
    }.items():
        face_slots[slot_key] = CharacterCardSlot.model_construct(
            slot_key=slot_key,
            module="face_identity",
            state="active",
            output_id=output_id,
            review_verified=True,
            prompt_reference_parity_verified=True,
        )
    expression_slots = dict(card.expression_slots)
    for slot_key in ("expression.laugh", "expression.anger", "expression.sad"):
        expression_slots[slot_key] = CharacterCardSlot.model_construct(
            slot_key=slot_key,
            module="expression_set",
            state="active",
            output_id=f"{slot_key}_output",
            review_verified=True,
            prompt_reference_parity_verified=True,
        )
    expression_slots["expression.neutral"] = CharacterCardSlot.model_construct(
        slot_key="expression.neutral",
        module="expression_set",
        state="active",
        is_alias=True,
        alias_of="face.front",
        review_verified=True,
        prompt_reference_parity_verified=True,
    )
    return card.model_copy(
        update={
            "face_identity_status": "active",
            "expression_set_status": "active",
            "face_slots": face_slots,
            "expression_slots": expression_slots,
        }
    )


def test_doc245_body_slot_result_carries_per_slot_formal_receipt_after_three_reviewed_candidates() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert [request.slot_key for request in generator.requests] == [
        "body.front_full",
        "body.front_full",
        "body.front_full",
        "body.side_full",
        "body.side_full",
        "body.side_full",
        "body.rear_full",
        "body.rear_full",
        "body.rear_full",
    ]
    assert set(result.winner_output_ids) == set(BODY_SLOT_KEYS)
    assert set(result.formal_slot_receipts) == set(BODY_SLOT_KEYS)
    receipt = result.formal_slot_receipts["body.front_full"]
    assert receipt.module == "body_silhouette"
    assert receipt.slot_key == "body.front_full"
    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.winner_output_id == "output_body.front_full_3"
    assert receipt.activation_eligible is False


def test_doc245_body_preparation_does_not_require_whole_expression_set_activation() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    card = _card_ready_for_body().model_copy(update={"expression_set_status": "partial"})

    result = service.prepare_body_silhouette(
        card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "review"
    assert result.winner_output_ids["body.front_full"] == "output_body.front_full_3"
    assert result.formal_slot_receipts["body.front_full"].acceptance_mode == "standard_three_candidate"


def test_doc245_body_formal_core_filters_enhanced_ineligible_candidate_before_ranking() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_BodyReviewer(enhanced_failing_indexes={3}),
    )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    receipt = result.formal_slot_receipts["body.front_full"]
    assert receipt.winner_candidate_id == "candidate_body.front_full_2"
    assert receipt.candidates[2].shared_review.passed is True
    assert receipt.candidates[2].enhanced_proof is not None
    assert receipt.candidates[2].enhanced_proof.eligible is False


def test_doc245_body_adapter_projects_brain_inferred_source_scope_into_candidate_enhanced_proof() -> None:
    attempts = [_body_attempt(index) for index in (1, 2, 3)]

    receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.front_full",
        attempts=attempts,  # type: ignore[arg-type]
    )

    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.candidate_eligibility_required is True
    assert receipt.winner_output_id == "output_body.front_full_3"
    assert all(candidate.enhanced_proof is not None for candidate in receipt.candidates)
    assert all(candidate.enhanced_proof.eligible for candidate in receipt.candidates if candidate.enhanced_proof)
    assert {
        "body_silhouette_profile_eligible",
        "body_source_class_brain_inferred",
        "body_face_reference_scope_verified",
    }.issubset(set(receipt.candidates[0].enhanced_proof.evidence_codes))  # type: ignore[union-attr]


def test_doc245_rear_body_no_visible_face_issue_does_not_block_rear_role_evidence() -> None:
    rear_attempts = [
        _body_attempt(
            index,
            slot_key="body.rear_full",
            review=_review(index).model_copy(update={"issue_codes": ["output_face_not_detected"]}),
        )
        for index in (1, 2, 3)
    ]

    receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.rear_full",
        attempts=rear_attempts,  # type: ignore[arg-type]
    )

    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.winner_output_id == "output_body.rear_full_3"
    assert all(candidate.enhanced_proof is not None for candidate in receipt.candidates)
    assert all(candidate.enhanced_proof.eligible for candidate in receipt.candidates if candidate.enhanced_proof)


def test_doc245_rear_body_missing_rear_evidence_still_fails_closed() -> None:
    rear_attempts = [_body_attempt(index, slot_key="body.rear_full") for index in (1, 2, 3)]
    rear_attempts[1] = _body_attempt(
        2,
        slot_key="body.rear_full",
        review=_review(2, status="fail", body_eligible=False),
    )

    receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.rear_full",
        attempts=rear_attempts,  # type: ignore[arg-type]
    )

    assert receipt.winner_candidate_id == "candidate_body.rear_full_3"
    rejected = receipt.candidates[1]
    assert rejected.shared_review.passed is False
    assert rejected.enhanced_proof is not None
    assert rejected.enhanced_proof.eligible is False


def test_doc245_body_adapter_rejects_observed_without_consent_or_reference_scope_mismatch() -> None:
    observed_missing_consent = [
        _body_attempt(index, source_class="observed", consent_provenance_id="consent_123")
        for index in (1, 2, 3)
    ]
    observed_missing_consent[0] = observed_missing_consent[0].model_copy(
        update={
            "request": observed_missing_consent[0].request.model_construct(
                **{
                    **observed_missing_consent[0].request.model_dump(mode="python"),
                    "source_class": "observed",
                    "consent_provenance_id": None,
                }
            )
        }
    )

    with pytest.raises(ValueError, match="Body formal slot enhanced proof contract mismatch"):
        CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
            slot_key="body.front_full",
            attempts=observed_missing_consent,  # type: ignore[arg-type]
        )

    mismatched_refs = [_body_attempt(index) for index in (1, 2, 3)]
    mismatched_refs[1] = mismatched_refs[1].model_copy(
        update={
            "request": mismatched_refs[1].request.model_copy(
                update={"reference_output_ids": ["face_front_output", "face_profile_output", "wrong_rear_output"]}
            )
        }
    )
    with pytest.raises(ValueError, match="Body formal slot enhanced proof contract mismatch"):
        CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
            slot_key="body.front_full",
            attempts=mismatched_refs,  # type: ignore[arg-type]
        )


def test_doc245_body_formal_core_blocks_when_all_enhanced_profiles_fail() -> None:
    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_BodyReviewer(enhanced_failing_indexes={1, 2, 3}),
    )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.winner_output_ids == {}
    assert result.formal_slot_receipts == {}
    assert result.failures[-1].failure_code == "character_card_formal_slot_receipt_invalid"


def test_doc245_body_stage_level_runtime_receipt_cannot_replace_per_slot_formal_receipts() -> None:
    card = _card_ready_for_body()
    body_slots = {}
    for slot_key in BODY_SLOT_KEYS:
        body_slots[slot_key] = CharacterCardSlot(
            slot_key=slot_key,
            module="body_silhouette",
            state="winner_selected",
            output_id=f"output_{slot_key}_3",
            source_candidate_ids=[f"candidate_{slot_key}_3"],
            source_class="brain_inferred",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
            shared_runtime_receipt=_legacy_body_slot_success_receipt(slot_key, f"output_{slot_key}_3"),
        )
    card = card.model_copy(update={"body_silhouette_status": "reviewing", "body_slots": body_slots})

    with pytest.raises(ValueError, match="formal"):
        CharacterCardPreparationService.activate_module(card, module="body_silhouette", confirmed=True)


def test_doc245_body_source_class_and_consent_contract_still_apply() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())

    with pytest.raises(ValueError, match="consent"):
        service.prepare_body_silhouette(
            _card_ready_for_body(),
            face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            source_class="observed",
            body_evidence_ids=["body_reference_asset"],
            user_intent="observed body silhouette profile",
        )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_reference_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )
    assert result.card.body_slots["body.front_full"].source_class == "observed"
    assert result.card.body_slots["body.front_full"].consent_provenance_id == "consent_123"


def test_doc245_body_formal_receipt_becomes_public_safe_only_after_projection_verification() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())
    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    shared_runtime = CharacterCardSharedRuntimeReceipt(
        reviewed_candidate_count=3,
        acceptance_mode="standard_three_candidate",
        final_winner_selection_verified=True,
        prompt_reference_parity_verified=True,
        shared_review_receipts=[_generic_body_shared_receipt()],
    )
    attached = result.model_copy(update={"shared_runtime_receipt": shared_runtime})

    persisted = VisualAssetLibraryLifecycleService._persist_character_card_success_receipts(
        attached,
        stage="body_silhouette",
    )
    slot = persisted.body_slots["body.front_full"]

    assert slot.formal_slot_receipt is not None
    assert slot.formal_slot_receipt.reload_public_projection_verified is False
    assert slot.formal_slot_receipt.activation_eligible is False
    with pytest.raises(ValueError, match="standard_three_candidate"):
        character_card_formal_slot_receipt_public_summary(slot)

    verified = VisualAssetLibraryLifecycleService._mark_formal_receipts_after_projection(
        persisted,
        stage="body_silhouette",
    )
    verified_slot = verified.body_slots["body.front_full"]
    summary = character_card_formal_slot_receipt_public_summary(verified_slot)
    assert summary is not None
    assert summary["activation_eligible"] is True
    assert summary["acceptance_mode"] == "standard_three_candidate"
    assert summary["reviewed_candidate_count"] == 3


def test_doc245_body_set_carries_existing_formal_receipts_during_partial_resume() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    base_card = _card_ready_for_body()
    existing_result = service.prepare_body_silhouette(
        base_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    existing_front = existing_result.card.body_slots["body.front_full"]
    assert existing_front.formal_slot_receipt is not None
    card_with_existing_front = base_card.model_copy(
        update={
            "body_silhouette_status": "reviewing",
            "body_slots": {
                **base_card.body_slots,
                "body.front_full": existing_front,
            },
        }
    )

    generator.requests.clear()
    result = service.prepare_body_silhouette(
        card_with_existing_front,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "review"
    assert result.winner_output_ids["body.front_full"] == existing_front.output_id
    assert "body.front_full" in result.formal_slot_receipts
    assert result.formal_slot_receipts["body.front_full"].winner_output_id == existing_front.output_id
    assert [request.slot_key for request in generator.requests] == [
        "body.side_full",
        "body.side_full",
        "body.side_full",
        "body.rear_full",
        "body.rear_full",
        "body.rear_full",
    ]
