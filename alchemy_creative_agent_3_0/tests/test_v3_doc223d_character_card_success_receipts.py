"""Doc223-D successful Character Card shared receipt persistence contracts."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    EXPRESSION_FRAMING_DELTA_MAX,
    LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES,
    project_laugh_expression_review_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorReviewDecision
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardCandidateAttempt,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardSlot,
    CharacterCardStageResult,
    CharacterCardState,
    project_character_card_slot_success_receipt,
    validate_character_card_slot_success_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    PersistentVisualAssetLibraryCatalog,
    VisualAssetLibraryCatalog,
    VisualAssetLibraryLifecycleService,
)


def _laugh_shared_review_receipt() -> dict[str, object]:
    score_card = {
        "mouth_eye_coherence": 0.91,
        "gaze_engagement": 0.90,
        "periocular_affect": 0.89,
        "cheek_jaw_coupling": 0.90,
        "jaw_relaxation": 0.84,
        "arousal_intensity_coherence": 0.88,
        "spontaneity_asymmetry": 0.80,
        "expression_age_coherence": 0.91,
        "expression_identity_preservation": 0.88,
        "expression_framing_parity": 0.93,
    }
    for dimension in EXPRESSION_FRAMING_DELTA_MAX:
        score_card[dimension] = 0.01
    return project_laugh_expression_review_receipt(
        score_card=score_card,
        issue_codes=[],
    ).to_public_dict()


def _generic_shared_review_receipt() -> dict[str, object]:
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
        "status": "pass",
        "evidence_codes": ["shared_visual_review_verified"],
        "issue_codes": [],
        "score_dimensions": ["identity_fidelity", "visual_quality"],
        "framing_delta_dimensions": [],
    }


def _stage_receipt(shared_review_receipts: list[dict[str, object]]) -> CharacterCardSharedRuntimeReceipt:
    return CharacterCardSharedRuntimeReceipt(
        retry_count=0,
        final_winner_selection_verified=True,
        prompt_reference_parity_verified=True,
        shared_review_receipts=shared_review_receipts,
    )


def _face_ready_card() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_doc223d")
    front = CharacterCardSlot(
        slot_key="face.front",
        module="face_identity",
        state="active",
        output_id="front_winner",
        source_candidate_ids=["front_candidate"],
        lineage_id="lineage_front",
        review_verified=True,
        prompt_reference_parity_verified=True,
        candidate_attempt_count=3,
    )
    return card.model_copy(
        update={
            "face_identity_status": "active",
            "face_slots": {**card.face_slots, "face.front": front},
        }
    )


def _catalog_asset(catalog: VisualAssetLibraryCatalog):
    return catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Doc223-D receipt asset",
            root_source_asset_id="root_doc223d",
            consent_reference="consent_doc223d",
            preparation_intent="authorized neutral identity evidence capture",
        ),
    )


def _attempt(
    *,
    slot_key: str,
    output_id: str,
    module: str = "expression_set",
    shared_review_receipts: list[dict[str, object]] | None = None,
) -> CharacterCardCandidateAttempt:
    shared_review_receipts = list(shared_review_receipts or [_laugh_shared_review_receipt()])
    request = CharacterCardCandidateRequest(
        project_id="project_doc223d",
        people_asset_id="people_doc223d",
        card_version_id="card_doc223d",
        module=module,  # type: ignore[arg-type]
        slot_key=slot_key,  # type: ignore[arg-type]
        candidate_index=1,
        reference_output_ids=["front_winner"] if module == "expression_set" else ["front", "profile", "rear"],
        user_intent="shared-runtime-owned character-card slot intent",
        source_class=None if module == "expression_set" else "brain_inferred",
    )
    candidate = CharacterCardCandidateResult(
        candidate_id=f"candidate_{slot_key.replace('.', '_')}",
        output_id=output_id,
        module=module,  # type: ignore[arg-type]
        slot_key=slot_key,
        candidate_index=1,
        source_candidate_ids=[f"candidate_{slot_key.replace('.', '_')}"],
        source_output_ids=list(request.reference_output_ids),
        canonical_prompt_hash=f"sha256:{slot_key}",
        prompt_compilation_id=f"compile_{slot_key}",
        prompt_reference_parity_verified=True,
    )
    review = AnchorReviewDecision(
        status="pass",
        identity_scores=IdentityScoreSummary(
            same_face_score=0.9,
            distinctive_feature_score=0.9,
            human_realism_score=0.9,
            visual_quality_score=0.9,
            evidence_codes=sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES)
            if slot_key == "expression.laugh"
            else ["shared_visual_review_verified"],
        ),
        shared_review_receipts=shared_review_receipts,
    )
    return CharacterCardCandidateAttempt(request=request, candidate=candidate, review=review)


class _SuccessfulExpressionHost:
    production_shared_runtime = True

    def prepare_expression_set(self, *, asset, card, generation_channel="provider"):  # noqa: ANN001, ANN201
        receipt = _laugh_shared_review_receipt()
        output_id = "output_laugh_doc223d"
        slot = CharacterCardSlot(
            slot_key="expression.laugh",
            module="expression_set",
            state="winner_selected",
            output_id=output_id,
            source_candidate_ids=["candidate_expression_laugh"],
            lineage_id="lineage_expression_laugh",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
        )
        return CharacterCardStageResult(
            status="review",
            card=card.model_copy(
                update={
                    "expression_set_status": "partial",
                    "expression_slots": {**card.expression_slots, "expression.laugh": slot},
                    "last_shared_runtime_failure": None,
                }
            ),
            attempts=[
                _attempt(
                    slot_key="expression.laugh",
                    output_id=output_id,
                    shared_review_receipts=[receipt],
                )
            ],
            winner_output_ids={"expression.laugh": output_id},
            shared_runtime_receipt=_stage_receipt([receipt]),
        )


def test_doc223d_prepare_persists_slot_success_receipt_across_catalog_reload(tmp_path) -> None:
    catalog = PersistentVisualAssetLibraryCatalog(tmp_path)
    asset = _catalog_asset(catalog)
    catalog.save(asset.model_copy(update={"character_card": _face_ready_card()}))
    lifecycle = VisualAssetLibraryLifecycleService(
        catalog,
        character_card_stage_host=_SuccessfulExpressionHost(),
    )

    updated = lifecycle.prepare_character_card_stage(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        stage="expression_set",
    )

    slot = updated.character_card.expression_slots["expression.laugh"]
    assert slot.shared_runtime_receipt is not None
    assert slot.shared_runtime_receipt["slot_key"] == "expression.laugh"
    assert slot.shared_runtime_receipt["output_id"] == "output_laugh_doc223d"
    assert slot.shared_runtime_receipt["shared_review_receipts"][0]["status"] == "pass"
    assert "mouth_eye_coherence" in slot.shared_runtime_receipt["shared_review_receipts"][0]["score_dimensions"]
    assert "eye_line_delta_from_front" in slot.shared_runtime_receipt["shared_review_receipts"][0]["framing_delta_dimensions"]

    reopened = PersistentVisualAssetLibraryCatalog(tmp_path)
    restored = reopened.get(owner_scope="local_default", visual_asset_id=asset.visual_asset_id)

    assert restored is not None
    restored_slot = restored.character_card.expression_slots["expression.laugh"]
    assert restored_slot.shared_runtime_receipt == slot.shared_runtime_receipt
    validate_character_card_slot_success_receipt(
        restored_slot.shared_runtime_receipt,
        module="expression_set",
        slot_key="expression.laugh",
        output_id="output_laugh_doc223d",
    )


def test_doc223d_public_projection_exposes_only_safe_success_receipt_summary(tmp_path) -> None:
    catalog = PersistentVisualAssetLibraryCatalog(tmp_path)
    asset = _catalog_asset(catalog)
    catalog.save(asset.model_copy(update={"character_card": _face_ready_card()}))
    updated = VisualAssetLibraryLifecycleService(
        catalog,
        character_card_stage_host=_SuccessfulExpressionHost(),
    ).prepare_character_card_stage(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        stage="expression_set",
    )

    public = V3ProductRouteHandlers._visual_asset_public_record(updated)
    slot_public = public["character_card"]["slots"]["expression.laugh"]
    receipt_public = slot_public["shared_runtime_receipt"]

    assert slot_public["shared_runtime_receipt_verified"] is True
    assert receipt_public["slot_key"] == "expression.laugh"
    assert receipt_public["output_id"] == "output_laugh_doc223d"
    assert receipt_public["shared_review_receipts"][0]["owner"] == "v3_shared_visual_cluster"
    text = json.dumps(receipt_public, ensure_ascii=False).lower()
    for forbidden in (
        "canonical_prompt",
        "final_provider_prompt",
        "prompt_text",
        "file_path",
        "raw_response",
        "provider_response",
        "mcp_handoff",
        "artifact",
        "token",
    ):
        assert forbidden not in text


def test_doc223d_public_projection_marks_corrupt_success_receipt_inconsistent_without_leak() -> None:
    corrupt_slot = SimpleNamespace(
        state="winner_selected",
        output_id="output_corrupt",
        slot_key="expression.laugh",
        module="expression_set",
        shared_runtime_receipt={
            "owner": "v3_character_card_shared_runtime",
            "receipt_version": "unknown_future_or_corrupt_version",
            "module": "expression_set",
            "slot_key": "expression.laugh",
            "output_id": "output_corrupt",
            "canonical_prompt": "must not leak",
            "file_path": "C:/secret/original.png",
            "raw_provider_response": {"private": True},
        },
    )
    card = SimpleNamespace(
        face_identity_status="active",
        expression_set_status="reviewing",
        body_silhouette_status="empty",
        face_identity_base_active=True,
        face_identity_complete=True,
        resume_available=False,
        last_failed_module=None,
        last_failed_slot_key=None,
        last_failure_code=None,
        last_failure_attempt_count=0,
        last_shared_runtime_failure=None,
        face_slots={},
        expression_slots={"expression.laugh": corrupt_slot},
        body_slots={},
        pending_mcp_handoff_ids=[],
    )
    asset = SimpleNamespace(
        visual_asset_id="visual_asset_corrupt",
        display_name="Corrupt receipt asset",
        asset_type="people",
        lifecycle_status="review",
        active_version_id=None,
        versions=[],
        active_version=lambda: None,
        character_card=card,
    )

    public = V3ProductRouteHandlers._visual_asset_public_record(asset)
    slot_public = public["character_card"]["slots"]["expression.laugh"]

    assert slot_public["shared_runtime_receipt_verified"] is False
    assert slot_public["shared_runtime_receipt_status"] == "inconsistent"
    assert "shared_runtime_receipt" not in slot_public
    text = json.dumps(slot_public, ensure_ascii=False).lower()
    assert "canonical_prompt" not in text
    assert "file_path" not in text
    assert "raw_provider_response" not in text


def test_doc223d_legacy_boolean_winner_without_success_receipt_cannot_activate() -> None:
    card = _face_ready_card()
    expression_slots = dict(card.expression_slots)
    expression_slots["expression.neutral"] = CharacterCardSlot(
        slot_key="expression.neutral",
        module="expression_set",
        state="active",
        is_alias=True,
        alias_of="face.front",
        review_verified=True,
        prompt_reference_parity_verified=True,
    )
    for key in ("expression.laugh", "expression.anger", "expression.sad"):
        expression_slots[key] = CharacterCardSlot(
            slot_key=key,  # type: ignore[arg-type]
            module="expression_set",
            state="winner_selected",
            output_id=f"output_{key}",
            source_candidate_ids=[f"candidate_{key}"],
            lineage_id=f"lineage_{key}",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
        )
    reviewing = card.model_copy(
        update={"expression_set_status": "reviewing", "expression_slots": expression_slots}
    )

    with pytest.raises(ValueError, match="persisted shared runtime receipt"):
        CharacterCardPreparationService.activate_module(
            reviewing,
            module="expression_set",
            confirmed=True,
        )


def test_doc223d_activation_accepts_only_slot_owned_success_receipts() -> None:
    card = _face_ready_card()
    expression_slots = dict(card.expression_slots)
    expression_slots["expression.neutral"] = CharacterCardSlot(
        slot_key="expression.neutral",
        module="expression_set",
        state="active",
        is_alias=True,
        alias_of="face.front",
        review_verified=True,
        prompt_reference_parity_verified=True,
    )
    for key in ("expression.laugh", "expression.anger", "expression.sad"):
        output_id = f"output_{key}"
        review_receipts = [_laugh_shared_review_receipt()] if key == "expression.laugh" else [_generic_shared_review_receipt()]
        receipt = project_character_card_slot_success_receipt(
            _stage_receipt(review_receipts),
            module="expression_set",
            slot_key=key,
            output_id=output_id,
            shared_review_receipts=review_receipts,
        )
        expression_slots[key] = CharacterCardSlot(
            slot_key=key,  # type: ignore[arg-type]
            module="expression_set",
            state="winner_selected",
            output_id=output_id,
            source_candidate_ids=[f"candidate_{key}"],
            lineage_id=f"lineage_{key}",
            review_verified=True,
            prompt_reference_parity_verified=True,
            shared_runtime_receipt=receipt,
            candidate_attempt_count=3,
        )
    reviewing = card.model_copy(
        update={
            "expression_set_status": "reviewing",
            "expression_set_version_id": "expression_doc223d",
            "expression_slots": expression_slots,
        }
    )

    activated = CharacterCardPreparationService.activate_module(
        reviewing,
        module="expression_set",
        confirmed=True,
    )

    assert activated.expression_set_status == "active"
    assert activated.expression_slots["expression.laugh"].state == "active"
    assert activated.expression_slots["expression.laugh"].shared_runtime_receipt["slot_key"] == "expression.laugh"


def test_doc223d_success_receipt_mismatch_and_incomplete_dimensions_fail_closed() -> None:
    review_receipt = _laugh_shared_review_receipt()
    receipt = project_character_card_slot_success_receipt(
        _stage_receipt([review_receipt]),
        module="expression_set",
        slot_key="expression.laugh",
        output_id="output_laugh",
        shared_review_receipts=[review_receipt],
    )
    with pytest.raises(ValueError, match="output mismatch"):
        validate_character_card_slot_success_receipt(
            {**receipt, "output_id": "output_wrong"},
            module="expression_set",
            slot_key="expression.laugh",
            output_id="output_laugh",
        )
    with pytest.raises(ValueError, match="ownership mismatch"):
        validate_character_card_slot_success_receipt(
            {**receipt, "slot_key": "expression.anger"},
            module="expression_set",
            slot_key="expression.laugh",
            output_id="output_laugh",
        )
    with pytest.raises(ValueError, match="unsafe fields"):
        validate_character_card_slot_success_receipt(
            {**receipt, "canonical_prompt": "do not persist me"},
            module="expression_set",
            slot_key="expression.laugh",
            output_id="output_laugh",
        )
    incomplete_review = {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_affective_expression_review_receipt_v1",
        "status": "pass",
        "expression": "laugh",
        "evidence_codes": sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES),
        "issue_codes": [],
        "score_dimensions": [],
        "framing_delta_dimensions": ["eye_line_delta_from_front"],
    }
    with pytest.raises(ValueError, match="dimensions"):
        project_character_card_slot_success_receipt(
            _stage_receipt([review_receipt]),
            module="expression_set",
            slot_key="expression.laugh",
            output_id="output_laugh",
            shared_review_receipts=[incomplete_review],
        )


def test_doc223d_prepare_fails_closed_when_success_receipt_cannot_be_projected(tmp_path) -> None:
    class _IncompleteHost(_SuccessfulExpressionHost):
        def prepare_expression_set(self, *, asset, card, generation_channel="provider"):  # noqa: ANN001, ANN201
            result = super().prepare_expression_set(asset=asset, card=card, generation_channel=generation_channel)
            attempt = result.attempts[0]
            bad_review = AnchorReviewDecision(
                status="pass",
                identity_scores=IdentityScoreSummary(
                    same_face_score=0.9,
                    distinctive_feature_score=0.9,
                    human_realism_score=0.9,
                    visual_quality_score=0.9,
                    evidence_codes=sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES),
                ),
                shared_review_receipts=[],
            )
            return result.model_copy(
                update={
                    "attempts": [attempt.model_copy(update={"review": bad_review})],
                    "shared_runtime_receipt": CharacterCardSharedRuntimeReceipt(
                        final_winner_selection_verified=True,
                        prompt_reference_parity_verified=True,
                        shared_review_receipts=[],
                    ),
                }
            )

    catalog = PersistentVisualAssetLibraryCatalog(tmp_path)
    asset = _catalog_asset(catalog)
    catalog.save(asset.model_copy(update={"character_card": _face_ready_card()}))
    lifecycle = VisualAssetLibraryLifecycleService(
        catalog,
        character_card_stage_host=_IncompleteHost(),
    )

    with pytest.raises(ValueError, match="dimensions"):
        lifecycle.prepare_character_card_stage(
            owner_scope="local_default",
            visual_asset_id=asset.visual_asset_id,
            stage="expression_set",
        )


def test_doc223d_resume_preserves_existing_slot_receipt_without_copying_stage_receipt(tmp_path) -> None:
    laugh_review = _laugh_shared_review_receipt()
    laugh_receipt = project_character_card_slot_success_receipt(
        _stage_receipt([laugh_review]),
        module="expression_set",
        slot_key="expression.laugh",
        output_id="output_laugh_existing",
        shared_review_receipts=[laugh_review],
    )
    card = _face_ready_card()
    expression_slots = dict(card.expression_slots)
    expression_slots["expression.laugh"] = CharacterCardSlot(
        slot_key="expression.laugh",
        module="expression_set",
        state="winner_selected",
        output_id="output_laugh_existing",
        source_candidate_ids=["candidate_laugh_existing"],
        lineage_id="lineage_laugh_existing",
        review_verified=True,
        prompt_reference_parity_verified=True,
        shared_runtime_receipt=laugh_receipt,
        candidate_attempt_count=3,
    )
    partial_card = card.model_copy(
        update={"expression_set_status": "partial", "expression_slots": expression_slots}
    )

    class _ResumeHost:
        production_shared_runtime = True

        def prepare_expression_set(self, *, asset, card, generation_channel="provider"):  # noqa: ANN001, ANN201
            anger_output = "output_anger_new"
            anger_slot = CharacterCardSlot(
                slot_key="expression.anger",
                module="expression_set",
                state="winner_selected",
                output_id=anger_output,
                source_candidate_ids=["candidate_anger_new"],
                lineage_id="lineage_anger_new",
                review_verified=True,
                prompt_reference_parity_verified=True,
                candidate_attempt_count=3,
            )
            generic = _generic_shared_review_receipt()
            return CharacterCardStageResult(
                status="review",
                card=card.model_copy(
                    update={
                        "expression_slots": {**card.expression_slots, "expression.anger": anger_slot},
                        "expression_set_status": "partial",
                    }
                ),
                attempts=[
                    _attempt(
                        slot_key="expression.anger",
                        output_id=anger_output,
                        shared_review_receipts=[generic],
                    )
                ],
                winner_output_ids={
                    "expression.laugh": "output_laugh_existing",
                    "expression.anger": anger_output,
                },
                shared_runtime_receipt=_stage_receipt([generic]),
            )

    catalog = PersistentVisualAssetLibraryCatalog(tmp_path)
    asset = _catalog_asset(catalog)
    catalog.save(asset.model_copy(update={"character_card": partial_card}))

    updated = VisualAssetLibraryLifecycleService(
        catalog,
        character_card_stage_host=_ResumeHost(),
    ).prepare_character_card_stage(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        stage="expression_set",
    )

    assert updated.character_card.expression_slots["expression.laugh"].shared_runtime_receipt == laugh_receipt
    assert updated.character_card.expression_slots["expression.anger"].shared_runtime_receipt["slot_key"] == "expression.anger"
