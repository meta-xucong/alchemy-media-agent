"""Doc196: Character Card positive-expression slot migrates from smile to laugh.

These tests intentionally lock the migration before fresh Provider/MCP
validation resumes.  They do not generate images.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_remote_required_result
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    ProductApiAnchorPackPreparationHost,
    _character_card_stage_mcp_prompt_current,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    CapabilityActivationPlan,
    TemplateCapabilityPolicy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    LAUGH_EXPRESSION_EVIDENCE_CODES,
    LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES,
    project_laugh_expression_review_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorReviewDecision
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    DEFAULT_EXPRESSION_KEYS,
    EXPRESSION_SLOT_KEYS,
    POSITIVE_EXPRESSION_SLOT_KEY,
    CharacterCardCandidateAttempt,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardStageResult,
    CharacterCardSlot,
    CharacterCardState,
    ExpressionPreparationRequest,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    VisualAssetLibraryCatalog,
    VisualAssetLibraryLifecycleService,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"


def _winner(slot_key: str, output_id: str = "output_winner") -> CharacterCardSlot:
    return CharacterCardSlot(
        slot_key=slot_key,  # type: ignore[arg-type]
        module=slot_key.split(".", 1)[0].replace("expression", "expression_set").replace("face", "face_identity"),
        state="winner_selected",
        output_id=output_id,
        source_candidate_ids=[f"candidate_{output_id}"],
        lineage_id=f"lineage_{output_id}",
        review_verified=True,
        prompt_reference_parity_verified=True,
        candidate_attempt_count=3,
    )


def _face_ready_card() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_doc196")
    front = card.face_slots["face.front"].model_copy(
        update={
            "state": "active",
            "output_id": "front_winner",
            "source_candidate_ids": ["front_candidate"],
            "lineage_id": "front_lineage",
            "review_verified": True,
            "prompt_reference_parity_verified": True,
            "candidate_attempt_count": 3,
        }
    )
    return card.model_copy(
        update={
            "face_identity_status": "active",
            "face_slots": {**card.face_slots, "face.front": front},
        }
    )


def _pass_review(*, evidence_codes: set[str] | None = None, issue_codes: list[str] | None = None) -> AnchorReviewDecision:
    return AnchorReviewDecision(
        status="pass",
        identity_scores=IdentityScoreSummary(
            same_face_score=0.92,
            distinctive_feature_score=0.90,
            human_realism_score=0.91,
            visual_quality_score=0.93,
            pose_compliance_score=0.92,
            evidence_codes=sorted(evidence_codes or set()),
        ),
        issue_codes=list(issue_codes or []),
    )


class _OneSlotGenerator:
    def __init__(self) -> None:
        self.requests: list[CharacterCardCandidateRequest] = []

    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        self.requests.append(request)
        token = f"{request.slot_key}_{request.candidate_index}".replace(".", "_")
        return CharacterCardCandidateResult(
            candidate_id=f"candidate_{token}",
            output_id=f"output_{token}",
            module=request.module,
            slot_key=request.slot_key,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"candidate_{token}"],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash=f"sha256:{token}",
            prompt_compilation_id=f"compile_{token}",
            prompt_reference_parity_verified=True,
        )


class _StaticReviewer:
    def __init__(self, decision: AnchorReviewDecision) -> None:
        self.decision = decision

    def review(self, _candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
        return self.decision


def test_doc196_new_character_cards_default_positive_slot_to_laugh_not_smile() -> None:
    card = CharacterCardState.initial(card_version_id="card_doc196")

    assert tuple(card.expression_slots) == EXPRESSION_SLOT_KEYS
    assert POSITIVE_EXPRESSION_SLOT_KEY == "expression.laugh"
    assert DEFAULT_EXPRESSION_KEYS == ("laugh", "anger", "sad")
    assert "expression.smile" not in card.expression_slots


def test_doc196_legacy_smile_cards_remain_readable_but_stale() -> None:
    card = CharacterCardState.initial(card_version_id="card_doc196_legacy")
    data = card.model_dump(mode="python")
    data["expression_slots"].pop("expression.laugh")
    data["expression_slots"]["expression.smile"] = CharacterCardSlot(
        slot_key="expression.smile",
        module="expression_set",
        state="winner_selected",
        output_id="old_smile_output",
        source_candidate_ids=["old_smile_candidate"],
        lineage_id="old_smile_lineage",
        review_verified=True,
        prompt_reference_parity_verified=True,
        candidate_attempt_count=3,
    ).model_dump(mode="python")

    restored = CharacterCardState.model_validate(data)

    assert restored.expression_slots["expression.laugh"].state == "empty"
    assert restored.expression_slots["expression.smile"].state == "stale"
    assert restored.expression_slots["expression.smile"].output_id == "old_smile_output"


def test_doc196_legacy_smile_winner_cannot_activate_current_laugh_slot() -> None:
    card = _face_ready_card()
    slots = {
        **card.expression_slots,
        "expression.neutral": CharacterCardSlot(
            slot_key="expression.neutral",
            module="expression_set",
            state="active",
            is_alias=True,
            alias_of="face.front",
            review_verified=True,
            prompt_reference_parity_verified=True,
        ),
        "expression.anger": _winner("expression.anger", "anger_output"),
        "expression.sad": _winner("expression.sad", "sad_output"),
        "expression.smile": CharacterCardSlot(
            slot_key="expression.smile",
            module="expression_set",
            state="stale",
            output_id="old_smile_output",
            source_candidate_ids=["old_smile_candidate"],
            lineage_id="old_smile_lineage",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
        ),
    }
    reviewing = card.model_copy(
        update={"expression_set_status": "reviewing", "expression_slots": slots}
    )

    with pytest.raises(ValueError, match="unreviewed slot"):
        CharacterCardPreparationService.activate_module(
            reviewing,
            module="expression_set",
            confirmed=True,
        )


def test_doc196_explicit_user_smile_remains_a_valid_nondefault_expression_request() -> None:
    request = ExpressionPreparationRequest(
        expression="smile",
        front_output_id="front_winner",
        user_intent="user explicitly requested a low intensity natural smile",
    )
    candidate_request = CharacterCardCandidateRequest(
        project_id="project_doc196",
        people_asset_id="people_doc196",
        card_version_id="card_doc196",
        module="expression_set",
        slot_key="expression.smile",
        candidate_index=1,
        reference_output_ids=["front_winner"],
        user_intent=request.user_intent,
    )

    assert request.reference_output_ids == ["front_winner"]
    assert candidate_request.slot_key == "expression.smile"
    assert _character_card_stage_mcp_prompt_current(
        "expression.smile",
        "Same person in the approved front-card framing with a natural smile.",
    )


def test_doc196_explicit_user_smile_has_callable_service_path_but_cannot_satisfy_laugh() -> None:
    service = CharacterCardPreparationService(
        generator=_OneSlotGenerator(),
        reviewer=_StaticReviewer(_pass_review()),
    )

    result = service.prepare_expression_slot(
        _face_ready_card(),
        expression="smile",
        front_output_id="front_winner",
        user_intent="user explicitly requested a low intensity natural smile",
    )

    assert result.status == "review"
    assert result.card.expression_set_status == "partial"
    assert result.card.expression_slots["expression.smile"].output_id
    assert result.card.expression_slots["expression.laugh"].state == "empty"
    with pytest.raises(ValueError, match="unreviewed slot"):
        CharacterCardPreparationService.activate_module(
            result.card,
            module="expression_set",
            confirmed=True,
        )


class _ExplicitSmileStageHost:
    production_shared_runtime = True

    def __init__(self) -> None:
        self.expression = None
        self.generation_channel = None

    @staticmethod
    def _receipt() -> CharacterCardSharedRuntimeReceipt:
        return CharacterCardSharedRuntimeReceipt(
            final_winner_selection_verified=True,
            prompt_reference_parity_verified=True,
        )

    def prepare_expression_slot(self, *, asset, card, expression, generation_channel="provider"):
        self.expression = expression
        self.generation_channel = generation_channel
        smile_slot = CharacterCardSlot(
            slot_key="expression.smile",
            module="expression_set",
            state="winner_selected",
            output_id="smile_output",
            source_candidate_ids=["smile_candidate"],
            lineage_id="smile_lineage",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
        )
        return CharacterCardStageResult(
            status="review",
            card=card.model_copy(
                update={
                    "expression_set_status": "partial",
                    "expression_slots": {**card.expression_slots, "expression.smile": smile_slot},
                }
            ),
            winner_output_ids={"expression.smile": "smile_output"},
            shared_runtime_receipt=self._receipt(),
        )


def _doc196_catalog_asset(catalog: VisualAssetLibraryCatalog):
    return catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Doc196 explicit smile",
            root_source_asset_id="root_doc196_smile",
            consent_reference="consent_doc196_smile",
            preparation_intent="authorized neutral identity evidence capture",
        ),
    )


def test_doc196_lifecycle_routes_explicit_smile_to_single_slot_host_without_defaulting_smile() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _doc196_catalog_asset(catalog)
    active_card = _face_ready_card()
    catalog.save(asset.model_copy(update={"character_card": active_card}))
    host = _ExplicitSmileStageHost()
    lifecycle = VisualAssetLibraryLifecycleService(catalog, character_card_stage_host=host)

    updated = lifecycle.prepare_character_card_stage(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        stage="expression_set",
        expression="smile",
        generation_channel="mcp",
    )

    assert host.expression == "smile"
    assert host.generation_channel == "mcp"
    assert updated.character_card.expression_slots["expression.smile"].output_id == "smile_output"
    assert updated.character_card.expression_slots["expression.laugh"].state == "empty"


def test_doc196_default_expression_prepare_emits_laugh_before_other_slots() -> None:
    generator = _OneSlotGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_StaticReviewer(_pass_review(evidence_codes=LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES)),
    )

    result = service.prepare_expression_set(
        _face_ready_card(),
        front_output_id="front_winner",
        user_intents={
            "laugh": "medium amused laugh keyframe",
            "anger": "mild serious expression",
            "sad": "quiet sad expression",
        },
    )

    assert result.status == "review"
    assert generator.requests[0].slot_key == "expression.laugh"
    assert "expression.smile" not in result.winner_output_ids
    assert result.card.expression_slots["expression.laugh"].output_id


def test_doc196_laugh_pass_requires_expression_evidence_not_visual_score_only() -> None:
    service = CharacterCardPreparationService(
        generator=_OneSlotGenerator(),
        reviewer=_StaticReviewer(_pass_review()),
    )

    result = service.prepare_expression_set(
        _face_ready_card(),
        front_output_id="front_winner",
        user_intents={
            "laugh": "medium amused laugh keyframe",
            "anger": "mild serious expression",
            "sad": "quiet sad expression",
        },
    )

    assert result.status == "blocked"
    assert result.card.last_failed_slot_key == "expression.laugh"


@pytest.mark.parametrize("issue_code", ["mouth_only_smile", "detached_gaze", "neutral_expression_collapse"])
def test_doc196_laugh_blocks_mouth_only_or_neutral_collapse_issue_codes(issue_code: str) -> None:
    service = CharacterCardPreparationService(
        generator=_OneSlotGenerator(),
        reviewer=_StaticReviewer(
            _pass_review(evidence_codes=LAUGH_EXPRESSION_EVIDENCE_CODES, issue_codes=[issue_code])
        ),
    )

    result = service.prepare_expression_set(
        _face_ready_card(),
        front_output_id="front_winner",
        user_intents={
            "laugh": "medium amused laugh keyframe",
            "anger": "mild serious expression",
            "sad": "quiet sad expression",
        },
    )

    assert result.status == "blocked"
    assert result.card.last_failed_slot_key == "expression.laugh"


def test_doc196_host_default_intents_and_mcp_prompt_contract_use_laugh_not_smile() -> None:
    intents = ProductApiAnchorPackPreparationHost._character_card_expression_slot_intents(
        "authorized identity preparation intent"
    )

    assert set(intents) == {"laugh", "anger", "sad"}
    assert "Expression slot target: expression.laugh." in intents["laugh"]
    assert "expression.smile" not in "\n".join(intents.values())
    assert _character_card_stage_mcp_prompt_current(
        "expression.laugh",
        "Same person in a medium-arousal amused laugh keyframe.",
    )
    assert not _character_card_stage_mcp_prompt_current(
        "expression.laugh",
        "Same person with a gentle genuine smile.",
    )


def test_doc196_character_card_expression_context_carries_framing_and_laugh_contract_only_for_stage() -> None:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="expression_set",
        slot_key="expression.laugh",
    )
    expression_contract = stage_metadata["professional_face_identity_quality_contract"]
    body_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.front_full",
        source_class="brain_inferred",
    )

    assert expression_contract["positive_expression_default"] == "laugh"
    assert expression_contract["expression_framing_contract"]["baseline"] == "active_face_front_winner"
    assert expression_contract["laugh_intent_contract"]["video_motion_hint"]
    assert "laugh_intent_contract" not in body_metadata["professional_face_identity_quality_contract"]


def test_doc196_brain_prompt_contract_receives_laugh_and_framing_only_for_character_card() -> None:
    planning = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="expression_set",
        slot_key="expression.laugh",
    )
    context = {
        "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        "professional_face_identity_quality_contract": planning[
            "professional_face_identity_quality_contract"
        ],
        "reference_led_slot_delta_decision": {
            **planning["reference_led_slot_delta_contract"],
            "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        },
        "character_card_slot_delta_target": {
            "stage": "expression_set",
            "slot_key": "expression.laugh",
            "expression": "laugh",
        },
        "character_card_slot_framing_contract": {
            "baseline": "active_face_front_winner",
            "format": "1024x1536_vertical_2_3",
        },
        "character_card_laugh_intent_contract": {
            "emotion": "laugh",
            "video_motion_hint": "positive keyframe",
        },
        "provider_admission_decision": {
            "required": True,
            "contract_version": "v3_provider_admission_decision_v1",
            "provider_admission_status": "admitted",
            "prompt_language_mode": "concise_positive_renderer_direction",
            "safety_sensitive_prompt_normalized": "applied",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        },
    }
    payload = json.loads(
        build_remote_payload(
            BrainRunRequest(
                user_input="Prepare the positive Character Card expression slot.",
                stage="provider_prompt_finalize",
                scenario_id="general_creative",
                template_id="general_template",
                requested_image_count=1,
                metadata={"canonical_prompt_context": context},
            )
        )
    )
    ordinary = json.loads(
        build_remote_payload(
            BrainRunRequest(
                user_input="ordinary image",
                stage="provider_prompt_finalize",
                scenario_id="general_creative",
                template_id="general_template",
                requested_image_count=1,
                metadata={"canonical_prompt_context": {}},
            )
        )
    )

    assert "expression.laugh" in payload["remote_response_contract"]
    assert "medium-arousal amused keyframe" in payload["remote_response_contract"]
    assert "front-card head/neck/upper-shoulder" in payload["remote_response_contract"]
    assert "expression.laugh" not in ordinary["remote_response_contract"]
    assert "front-card head/neck/upper-shoulder" not in ordinary["remote_response_contract"]


class _OutputStore:
    def __init__(self, output: SimpleNamespace) -> None:
        self.output = output

    def list_by_job(self, _job_id: str) -> list[SimpleNamespace]:
        return [self.output]

    def get_output(self, output_id: str) -> SimpleNamespace | None:
        return self.output if output_id == self.output.output_id else None


class _ReviewService:
    visual_asset_catalog = None

    def __init__(self, inspection: dict[str, object]) -> None:
        self.output = SimpleNamespace(
            output_id="output_laugh",
            candidate_id="candidate_laugh",
            file_path="unused.png",
            metadata={
                "provider_prompt_sha256": "sha256:laugh",
                "prompt_compilation_id": "compile_laugh",
                "provider_reference_image_count": 2,
            },
        )
        self.output_store = _OutputStore(self.output)
        self.record = SimpleNamespace(
            planning_result_id="planning_laugh",
            generation_result=SimpleNamespace(
                metadata={"post_generation_review_package": {"inspections": [inspection]}}
            ),
        )

    def get_job_record(self, _job_id: str) -> SimpleNamespace:
        return self.record


def _laugh_request(
    *,
    project_id: str = "project_doc196",
    people_asset_id: str = "people_doc196",
    user_intent: str = "medium amused laugh keyframe",
    generation_channel: str = "provider",
    mcp_handoff_id: str | None = None,
) -> CharacterCardCandidateRequest:
    return CharacterCardCandidateRequest(
        project_id=project_id,
        people_asset_id=people_asset_id,
        card_version_id="card_doc196",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        reference_output_ids=["front_winner"],
        user_intent=user_intent,
        generation_channel=generation_channel,  # type: ignore[arg-type]
        mcp_handoff_id=mcp_handoff_id,
    )


def _laugh_inspection(
    *,
    issue_codes: list[str] | None = None,
    score_overrides: dict[str, float] | None = None,
) -> dict[str, object]:
    score_card = {
        "same_person_readability": 0.92,
        "distinctive_feature_readability": 0.90,
        "human_realism": 0.91,
        "visual_quality": 0.93,
        "overall": 0.93,
        "mouth_eye_coherence": 0.90,
        "gaze_engagement": 0.88,
        "periocular_affect": 0.86,
        "cheek_jaw_coupling": 0.86,
        "jaw_relaxation": 0.82,
        "arousal_intensity_coherence": 0.86,
        "spontaneity_asymmetry": 0.78,
        "expression_age_coherence": 0.87,
        "expression_identity_preservation": 0.90,
        "expression_framing_parity": 0.90,
        "face_area_delta_from_front": 0.03,
        "top_margin_delta_from_front": 0.018,
        "bottom_margin_delta_from_front": 0.020,
        "eye_line_delta_from_front": 0.016,
        "center_x_delta_from_front": 0.014,
        "shoulder_span_delta_from_front": 0.035,
        "head_yaw_delta_from_front": 0.030,
        "head_pitch_delta_from_front": 0.020,
    }
    score_card.update(score_overrides or {})
    return {
        "output_id": "output_laugh",
        "mode": "hybrid",
        "verification_state": "verified",
        "status": "pass",
        "issue_codes": list(issue_codes or []),
        "score_card": score_card,
    }


def test_doc196_host_projects_laugh_score_dimensions_into_shared_evidence_codes() -> None:
    host = ProductApiAnchorPackPreparationHost(_ReviewService(_laugh_inspection()))  # type: ignore[arg-type]

    _candidate, review = host._character_card_candidate_and_review("job_laugh", _laugh_request())  # noqa: SLF001

    assert review.status == "pass"
    assert LAUGH_EXPRESSION_EVIDENCE_CODES.issubset(set(review.identity_scores.evidence_codes))
    assert "shared_affective_expression_review_receipt_verified" in review.identity_scores.evidence_codes
    assert "front_card_framing_parity_verified" in review.identity_scores.evidence_codes
    assert "front_card_framing_delta_receipt_verified" in review.identity_scores.evidence_codes
    assert review.shared_review_receipts[0]["owner"] == "v3_shared_visual_cluster"
    assert review.shared_review_receipts[0]["contract_version"] == "v3_affective_expression_review_receipt_v1"
    assert review.shared_review_receipts[0]["status"] == "pass"
    assert review.shared_review_receipts[0]["framing_baseline"] == "face.front"
    assert "mouth_eye_coherence" in review.shared_review_receipts[0]["score_dimensions"]
    assert "eye_line_delta_from_front" in review.shared_review_receipts[0]["framing_delta_dimensions"]


def test_doc196_structured_expression_receipt_round_trips_from_review_to_stage_receipt() -> None:
    host = ProductApiAnchorPackPreparationHost(_ReviewService(_laugh_inspection()))  # type: ignore[arg-type]
    candidate, review = host._character_card_candidate_and_review("job_laugh", _laugh_request())  # noqa: SLF001
    result = CharacterCardStageResult(
        status="review",
        card=_face_ready_card(),
        attempts=[
            CharacterCardCandidateAttempt(
                request=_laugh_request(),
                candidate=candidate,
                review=review,
            )
        ],
        winner_output_ids={"expression.laugh": candidate.output_id},
    )

    attached = host._attach_character_card_receipt(
        result,
        asset=type("Asset", (), {"visual_asset_id": "asset_doc196"})(),
        stage="expression_set",
    )  # noqa: SLF001

    assert attached.shared_runtime_receipt is not None
    receipt = attached.shared_runtime_receipt.shared_review_receipts[0]
    assert receipt == review.shared_review_receipts[0]
    assert receipt["status"] == "pass"
    assert receipt["score_dimensions"]
    assert receipt["framing_delta_dimensions"]


def test_doc196_host_rejects_neutral_collapse_even_when_prompt_review_was_approved() -> None:
    inspection = _laugh_inspection(issue_codes=["neutral_expression_collapse"])
    inspection["prompt_review"] = {"status": "approved"}
    host = ProductApiAnchorPackPreparationHost(_ReviewService(inspection))  # type: ignore[arg-type]

    _candidate, review = host._character_card_candidate_and_review("job_laugh", _laugh_request())  # noqa: SLF001

    assert review.status == "fail"
    assert "neutral_expression_collapse" in review.issue_codes


@pytest.mark.parametrize(
    ("case_label", "user_intent", "score_overrides"),
    [
        (
            "adult_male",
            "restrained natural laugh keyframe for an adult male identity",
            {
                "same_person_readability": 0.91,
                "mouth_eye_coherence": 0.84,
                "expression_age_coherence": 0.86,
                "head_yaw_delta_from_front": 0.04,
            },
        ),
        (
            "adult_female",
            "warm commercial laugh keyframe for an adult female identity",
            {
                "same_person_readability": 0.93,
                "periocular_affect": 0.83,
                "expression_identity_preservation": 0.88,
                "shoulder_span_delta_from_front": 0.04,
            },
        ),
        (
            "child",
            "medium amused laugh keyframe for a child identity with age coherence",
            {
                "same_person_readability": 0.90,
                "cheek_jaw_coupling": 0.84,
                "expression_age_coherence": 0.88,
                "eye_line_delta_from_front": 0.018,
            },
        ),
    ],
)
def test_doc196_laugh_calibration_uses_one_foundation_receipt_across_age_cases(
    case_label: str,
    user_intent: str,
    score_overrides: dict[str, float],
) -> None:
    host = ProductApiAnchorPackPreparationHost(
        _ReviewService(_laugh_inspection(score_overrides=score_overrides))
    )  # type: ignore[arg-type]

    _candidate, review = host._character_card_candidate_and_review(
        f"job_laugh_{case_label}",
        _laugh_request(
            project_id=f"project_{case_label}",
            people_asset_id=f"people_{case_label}",
            user_intent=user_intent,
        ),
    )  # noqa: SLF001

    evidence = set(review.identity_scores.evidence_codes)
    assert review.status == "pass"
    assert LAUGH_EXPRESSION_EVIDENCE_CODES.issubset(evidence)
    assert "shared_affective_expression_review_receipt_verified" in evidence
    assert "front_card_framing_delta_receipt_verified" in evidence
    assert all(not item.startswith("child_") for item in evidence)


def test_doc196_laugh_framing_delta_receipt_blocks_over_tolerance_drift() -> None:
    inspection = _laugh_inspection(score_overrides={"eye_line_delta_from_front": 0.10})
    host = ProductApiAnchorPackPreparationHost(_ReviewService(inspection))  # type: ignore[arg-type]

    _candidate, review = host._character_card_candidate_and_review("job_laugh", _laugh_request())  # noqa: SLF001

    assert review.status == "fail"
    assert "shared_affective_expression_framing_drift" in review.issue_codes
    assert "front_card_framing_delta_receipt_verified" not in review.identity_scores.evidence_codes


def test_doc196_laugh_framing_delta_receipt_missing_fails_closed() -> None:
    inspection = _laugh_inspection()
    score_card = dict(inspection["score_card"])  # type: ignore[arg-type]
    score_card.pop("top_margin_delta_from_front")
    inspection["score_card"] = score_card
    host = ProductApiAnchorPackPreparationHost(_ReviewService(inspection))  # type: ignore[arg-type]

    _candidate, review = host._character_card_candidate_and_review("job_laugh", _laugh_request())  # noqa: SLF001

    assert review.status == "fail"
    assert "shared_affective_expression_framing_receipt_missing" in review.issue_codes
    assert "front_card_framing_delta_receipt_verified" not in review.identity_scores.evidence_codes


def test_doc196_provider_and_mcp_materialization_paths_consume_same_foundation_receipt() -> None:
    reviews: dict[str, AnchorReviewDecision] = {}
    for channel in ("provider", "mcp"):
        host = ProductApiAnchorPackPreparationHost(_ReviewService(_laugh_inspection()))  # type: ignore[arg-type]
        _candidate, review = host._character_card_candidate_and_review(
            f"job_laugh_{channel}",
            _laugh_request(
                generation_channel=channel,
                mcp_handoff_id="mcp_handoff_doc196" if channel == "mcp" else None,
            ),
        )  # noqa: SLF001
        reviews[channel] = review

    assert reviews["provider"].status == "pass"
    assert reviews["mcp"].status == "pass"
    assert reviews["provider"].identity_scores.evidence_codes == reviews["mcp"].identity_scores.evidence_codes
    assert reviews["provider"].issue_codes == reviews["mcp"].issue_codes
    assert reviews["provider"].shared_review_receipts == reviews["mcp"].shared_review_receipts


def test_doc196_expression_review_gate_lives_in_foundation_not_character_card_or_host() -> None:
    character_card_source = (ROOT / "alchemy_creative_agent_3_0" / "app" / "visual_assets" / "character_card.py").read_text(
        encoding="utf-8"
    )
    host_source = (
        ROOT / "alchemy_creative_agent_3_0" / "app" / "product_api" / "anchor_pack_host.py"
    ).read_text(encoding="utf-8")
    foundation_source = (
        ROOT
        / "alchemy_creative_agent_3_0"
        / "app"
        / "shared_capabilities"
        / "visual_cluster"
        / "expression_review.py"
    ).read_text(encoding="utf-8")

    assert "LAUGH_EXPRESSION_SCORE_FLOORS" in foundation_source
    assert "EXPRESSION_FRAMING_DELTA_MAX" in foundation_source
    assert "LAUGH_EXPRESSION_SCORE_FLOORS" not in character_card_source
    assert "EXPRESSION_FRAMING_DELTA_MAX" not in character_card_source
    assert "_CHARACTER_CARD_LAUGH_EVIDENCE_FLOORS" not in host_source
    assert "_character_card_laugh_expression_receipt" not in host_source
    assert "project_laugh_expression_review_receipt" in host_source


def test_doc196_frontend_uses_laugh_as_current_positive_slot_and_keeps_smile_out_of_default_card() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert '["expression.laugh", "开心笑"]' in source
    expression_meta_start = source.index("expression_set: {")
    expression_meta_end = source.index("body_silhouette: {", expression_meta_start)
    expression_meta = source[expression_meta_start:expression_meta_end]
    assert "expression.smile" not in expression_meta


def _expression_slot_delta_runtime_request(slot_key: str = "expression.laugh") -> ScenarioRuntimeRequest:
    return ScenarioRuntimeRequest(
        user_input="Prepare one Character Card expression slot from the approved face.front winner.",
        scenario_selection={"scenario_id": "general_creative"},
        metadata={
            "project_id": "project_doc197_expression_recovery",
            "requested_image_count": 1,
            "require_real_images": True,
            "professional_mode": True,
            "professional_character_card_preparation": True,
            "professional_character_card_stage": "expression_set",
            "professional_character_card_slot": slot_key,
            "professional_planning_metadata": ProfessionalModeRuntimeBridge.character_card_stage_metadata(
                stage="expression_set",
                slot_key=slot_key,
            ),
            "professional_anchor_reference_assets": [
                {
                    "asset_id": "front_winner_output",
                    "output_id": "front_winner_output",
                    "role": "face_reference",
                    "source_type": "selected_output",
                    "use_policy": "identity",
                    "strength": "hard",
                    "provider_input_required": True,
                }
            ],
            "generation_channel": "mcp",
            "mcp_operation_id": f"asset_doc197:expression_set:{slot_key}:1",
        },
    )


def _remote_required_expression_brain_result(slot_key: str = "expression.laugh"):
    return build_remote_required_result(
        BrainRunRequest(
            user_input=f"Prepare one Character Card {slot_key} slot.",
            stage="scenario_runtime",
            scenario_id="general_creative",
            template_id="general_template",
            requested_image_count=1,
            requested_image_size="1024x1536",
            metadata=_expression_slot_delta_runtime_request(slot_key).metadata,
        ),
        "Remote Brain timed out before the Character Card expression slot prompt.",
    )


def test_doc197_laugh_brain_timeout_uses_bounded_expression_slot_delta_recovery() -> None:
    runtime = ScenarioRuntime()
    request = _expression_slot_delta_runtime_request("expression.laugh")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_expression_brain_result("expression.laugh"),
    )

    assert recovered.canonical_provider_prompts
    canonical = recovered.canonical_provider_prompts[0]
    assert "medium-arousal naturally amused laugh keyframe" in canonical.prompt
    assert "same face.front card framing" in canonical.prompt
    assert canonical.reference_led_slot_delta_decision is not None
    assert canonical.reference_led_slot_delta_decision.slot_delta_type == "expression"
    assert canonical.provider_admission_decision is not None
    assert canonical.provider_admission_decision.provider_admission_status == "admitted"
    assert recovered.audit["character_card_slot_delta_recovery_prompts_received"] is True
    assert recovered.audit["character_card_slot_delta_recovery_scope"] == "professional_character_card_expression_set"
    assert recovered.audit["character_card_slot_delta_recovery_slot_key"] == "expression.laugh"
    assert recovered.visual_task_profile is not None
    assert recovered.visual_task_profile.allowed_changes == [
        "facial_expression_only",
        "small_natural_head_shoulder_energy",
    ]

    runtime._require_remote_creative_brain(  # noqa: SLF001
        request,
        TemplateCapabilityPolicy(requires_remote_creative_brain=True),
        recovered,
    )
    runtime._require_brain_signed_provider_prompts(  # noqa: SLF001
        request,
        TemplateCapabilityPolicy(requires_remote_creative_brain=True),
        recovered,
        CapabilityActivationPlan(
            plan_id="plan_doc197_expression_recovery",
            fingerprint="fp_doc197_expression_recovery",
            job_id="job_doc197_expression_recovery",
            task_profile_id="profile_doc197_expression_recovery",
            template_id="general_template",
            scenario_id="general_creative",
        ),
    )


def test_doc197_explicit_smile_can_recover_but_does_not_become_laugh() -> None:
    runtime = ScenarioRuntime()
    request = _expression_slot_delta_runtime_request("expression.smile")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_expression_brain_result("expression.smile"),
    )

    assert recovered.canonical_provider_prompts
    prompt = recovered.canonical_provider_prompts[0].prompt
    assert "lower-intensity natural smile" in prompt
    assert "medium-arousal naturally amused laugh keyframe" not in prompt
    assert recovered.audit["character_card_slot_delta_recovery_slot_key"] == "expression.smile"
    assert recovered.audit["character_card_slot_delta_recovery_expression"] == "smile"


def test_doc197_expression_slot_delta_transport_timeout_is_character_card_only() -> None:
    runtime = ScenarioRuntime()

    assert runtime._character_card_slot_delta_transport_timeout_seconds(  # noqa: SLF001
        _expression_slot_delta_runtime_request("expression.laugh")
    ) == 28.0
    assert runtime._character_card_slot_delta_transport_timeout_seconds(  # noqa: SLF001
        ScenarioRuntimeRequest(
            user_input="ordinary image",
            scenario_selection={"scenario_id": "general_creative"},
            metadata={"requested_image_count": 1},
        )
    ) is None


def test_doc197_expression_recovery_requires_one_front_reference() -> None:
    runtime = ScenarioRuntime()
    request = _expression_slot_delta_runtime_request("expression.laugh")
    request = request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                "professional_anchor_reference_assets": [],
            }
        },
        deep=True,
    )

    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_expression_brain_result("expression.laugh"),
    )

    assert not recovered.canonical_provider_prompts
    assert "character_card_slot_delta_recovery_prompts_received" not in recovered.audit
