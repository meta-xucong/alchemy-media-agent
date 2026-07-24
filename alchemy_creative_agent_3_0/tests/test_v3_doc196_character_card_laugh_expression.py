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
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    CapabilityActivationPlan,
    TemplateCapabilityPolicy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    LAUGH_EXPRESSION_EVIDENCE_CODES,
    LAUGH_EXPRESSION_INTENT_CONTRACT_VERSION,
    LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES,
    expression_front_card_framing_materialization_directive,
    laugh_expression_intent_contract,
    laugh_expression_materialization_directive,
    project_laugh_expression_review_receipt,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateUnavailable,
    AnchorReviewDecision,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    DEFAULT_EXPRESSION_KEYS,
    EXPRESSION_SLOT_KEYS,
    POSITIVE_EXPRESSION_SLOT_KEY,
    CharacterCardCandidateAttempt,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardFailureEvent,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeFailureReceipt,
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


def test_doc214_expression_laugh_mcp_prompt_current_requires_full_frame_framing_authority() -> None:
    old_soft_prompt = (
        "Same person as the approved face.front Character Card winner, preserving front-card framing, "
        "head-top margin and eye-line placement. Render a clearly readable joyful laugh."
    )
    current_prompt = (
        f"{laugh_expression_materialization_directive()} "
        f"{expression_front_card_framing_materialization_directive()}"
    )

    assert not _character_card_stage_mcp_prompt_current("expression.laugh", old_soft_prompt)
    assert _character_card_stage_mcp_prompt_current("expression.laugh", current_prompt)


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
    directive = laugh_expression_materialization_directive(laugh_expression_intent_contract())
    framing_directive = expression_front_card_framing_materialization_directive()

    assert set(intents) == {"laugh", "anger", "sad"}
    assert "Expression slot target: expression.laugh." in intents["laugh"]
    assert directive in intents["laugh"]
    assert framing_directive in intents["laugh"]
    assert "clearly readable joyful laugh keyframe" in intents["laugh"]
    assert "not merely a polite open-mouth smile" in intents["laugh"]
    assert "engaged, lively gaze as expression evidence only" in intents["laugh"]
    assert "bright engaged gaze" not in intents["laugh"]
    assert "expression.smile" not in "\n".join(intents.values())
    assert _character_card_stage_mcp_prompt_current(
        "expression.laugh",
        f"{directive} {framing_directive}",
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
    laugh_contract = expression_contract["laugh_intent_contract"]
    assert laugh_contract["contract_version"] == LAUGH_EXPRESSION_INTENT_CONTRACT_VERSION
    assert laugh_contract["owner"] == "v3_shared_visual_cluster"
    assert laugh_contract["intensity_band"] == "medium_to_medium_high"
    assert laugh_contract["arousal_band"] == "medium_to_medium_high"
    assert laugh_contract["phase"] == "onset_to_peak_static_keyframe"
    assert laugh_contract["style_channel_policy"] == (
        "inherit_prompt_owned_face_front_channels_without_lighting_or_complexion_override"
    )
    assert "lower_lid_periocular_participation" in laugh_contract["participation_channels"]
    assert "visible_eye_cheek_coupling" in laugh_contract["participation_channels"]
    assert "upper_cheek_lift" in laugh_contract["participation_channels"]
    assert laugh_contract["video_motion_hint"]
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
        "character_card_laugh_intent_contract": laugh_expression_intent_contract(),
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
    assert LAUGH_EXPRESSION_INTENT_CONTRACT_VERSION in payload["remote_response_contract"]
    assert "intensity_band=medium_to_medium_high" in payload["remote_response_contract"]
    assert "arousal_band=medium_to_medium_high" in payload["remote_response_contract"]
    assert "phase=onset_to_peak_static_keyframe" in payload["remote_response_contract"]
    assert "lower_lid_periocular_participation" in payload["remote_response_contract"]
    assert "visible_eye_cheek_coupling" in payload["remote_response_contract"]
    assert "engaged/lively gaze as facial affect evidence only" in payload["remote_response_contract"]
    assert "medium-arousal amused keyframe" not in payload["remote_response_contract"]
    assert "bright lighting" not in payload["remote_response_contract"]
    assert "front-card head/neck/upper-shoulder" in payload["remote_response_contract"]
    assert "expression.laugh" not in ordinary["remote_response_contract"]
    assert "front-card head/neck/upper-shoulder" not in ordinary["remote_response_contract"]


def _expression_review_metadata_for_vision() -> dict[str, object]:
    stage_metadata = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="expression_set",
        slot_key="expression.laugh",
    )
    return {
        "project_id": "project_doc199_expression_review",
        "capability_execution_envelope": {
            "activation_plan": {
                "plan_id": "plan_doc199_expression_review",
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


def test_doc199_active_review_contract_exposes_laugh_expression_dimensions_to_shared_vision() -> None:
    contract = active_review_contract(_expression_review_metadata_for_vision())

    assert contract["professional_identity_quality"]["expression_review"]["applies"] is True
    scores = set(contract["score_dimensions"])
    issues = set(contract["issue_codes"])
    assert {
        "mouth_eye_coherence",
        "gaze_engagement",
        "periocular_affect",
        "cheek_jaw_coupling",
        "jaw_relaxation",
        "arousal_intensity_coherence",
        "spontaneity_asymmetry",
        "expression_age_coherence",
        "expression_identity_preservation",
        "expression_framing_parity",
        "face_area_delta_from_front",
        "eye_line_delta_from_front",
    }.issubset(scores)
    assert {
        "mouth_only_smile",
        "detached_gaze",
        "frozen_periocular_region",
        "neutral_expression_collapse",
        "shared_affective_laugh_evidence_below_bar",
        "shared_affective_expression_framing_receipt_missing",
    }.issubset(issues)


def test_doc199_enforced_inspection_prompt_distinguishes_laugh_affect_from_pose_failure() -> None:
    prompt = _inspection_prompt(_expression_review_metadata_for_vision())

    assert "Character Card expression review" in prompt
    assert "mouth_eye_coherence" in prompt
    assert "periocular_affect" in prompt
    assert "cheek_jaw_coupling" in prompt
    assert "natural mouth opening" in prompt
    assert "do not mark them as pose failure" in prompt
    assert "face.front scale" in prompt


class _OutputStore:
    def __init__(self, output: SimpleNamespace) -> None:
        self.output = output

    def list_by_job(self, _job_id: str) -> list[SimpleNamespace]:
        return [self.output]

    def get_output(self, output_id: str) -> SimpleNamespace | None:
        return self.output if output_id == self.output.output_id else None


class _ReviewService:
    visual_asset_catalog = None

    def __init__(
        self,
        inspection: dict[str, object],
        *,
        reference_count: int = 3,
        operation_id: str = "people_doc196:expression_set:expression.laugh:1",
        reference_output_ids: list[str] | None = None,
    ) -> None:
        reference_output_ids = list(reference_output_ids or ["front_winner"])
        self.output = SimpleNamespace(
            output_id="output_laugh",
            candidate_id="candidate_laugh",
            file_path="unused.png",
            metadata={
                "provider_prompt_sha256": "sha256:laugh",
                "prompt_compilation_id": "compile_laugh",
                "provider_reference_image_count": reference_count,
                "reference_asset_count": reference_count,
                "provider_reference_assets": [
                    {"asset_id": f"front_reference_{index}", "role": "portrait_identity"}
                    for index in range(1, reference_count + 1)
                ],
                "reference_asset_ids": [
                    f"front_reference_{index}" for index in range(1, reference_count + 1)
                ],
                "reference_input_execution": {
                    "schema_version": "v3_reference_input_execution_v1",
                    "reference_count": reference_count,
                    "operation_outcome": "pixels_received",
                },
            },
        )
        self.output_store = _OutputStore(self.output)
        self.record = SimpleNamespace(
            job_id="job_laugh",
            planning_result=object(),
            request=SimpleNamespace(
                metadata={
                    "professional_character_card_preparation": True,
                    "professional_character_card_stage": "expression_set",
                    "professional_character_card_slot": "expression.laugh",
                    "professional_character_card_reference_output_ids": reference_output_ids,
                    "generation_channel": "mcp",
                    "mcp_operation_id": operation_id,
                }
            ),
            planning_result_id="planning_laugh",
            generation_result=SimpleNamespace(
                metadata={"post_generation_review_package": {"inspections": [inspection]}}
            ),
        )
        self.job_store = SimpleNamespace(list_recent=lambda _limit: [self.record])

    def get_job_record(self, _job_id: str) -> SimpleNamespace:
        return self.record


def _laugh_request(
    *,
    project_id: str = "project_doc196",
    people_asset_id: str = "people_doc196",
    candidate_index: int = 1,
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
        candidate_index=candidate_index,
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


def test_doc198_expression_candidate_parity_accepts_front_crop_geometry_and_full_frame_package() -> None:
    host = ProductApiAnchorPackPreparationHost(
        _ReviewService(_laugh_inspection(), reference_count=3)  # type: ignore[arg-type]
    )

    candidate, review = host._character_card_candidate_and_review("job_laugh", _laugh_request())  # noqa: SLF001

    assert candidate.prompt_reference_parity_verified is True
    assert review.status == "pass"


def test_doc198_expression_candidate_parity_mismatch_fails_closed_without_candidate_validation_crash() -> None:
    service = _ReviewService(_laugh_inspection(), reference_count=3)
    service.output.metadata["reference_asset_count"] = 2
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        host._character_card_candidate_and_review("job_laugh", _laugh_request())  # noqa: SLF001

    assert getattr(exc_info.value, "failure_code", "") == (
        "professional_character_card_prompt_reference_parity_unverified"
    )


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


def test_doc211_blocked_expression_stage_preserves_reviewed_laugh_receipt() -> None:
    host = ProductApiAnchorPackPreparationHost(_ReviewService(_laugh_inspection()))  # type: ignore[arg-type]
    candidate, review = host._character_card_candidate_and_review("job_laugh", _laugh_request())  # noqa: SLF001
    result = CharacterCardStageResult(
        status="blocked",
        card=_face_ready_card().model_copy(
            update={
                "expression_set_status": "blocked",
                "last_failed_module": "expression_set",
                "last_failed_slot_key": "expression.laugh",
                "last_failure_code": "mcp_materialization_operation_ambiguous",
                "last_failure_attempt_count": 2,
                "resume_available": True,
            }
        ),
        attempts=[
            CharacterCardCandidateAttempt(
                request=_laugh_request(candidate_index=1),
                candidate=candidate,
                review=review,
            )
        ],
        failures=[
            CharacterCardFailureEvent(
                module="expression_set",
                slot_key="expression.laugh",
                candidate_index=2,
                attempt_round=3,
                failure_code="mcp_materialization_operation_ambiguous",
            )
        ],
    )

    attached = host._attach_character_card_receipt(
        result,
        asset=type("Asset", (), {"visual_asset_id": "asset_doc211"})(),
        stage="expression_set",
    )  # noqa: SLF001

    assert attached.shared_runtime_failure is not None
    assert attached.shared_runtime_failure.reviewed_attempt_count == 1
    assert attached.shared_runtime_failure.prompt_reference_parity_verified is True
    receipt = attached.shared_runtime_failure.shared_review_receipts[0]
    assert receipt == review.shared_review_receipts[0]
    assert receipt["status"] == "pass"
    assert "mouth_eye_coherence" in receipt["score_dimensions"]
    assert "periocular_affect" in receipt["score_dimensions"]
    assert "cheek_jaw_coupling" in receipt["score_dimensions"]
    assert "expression_age_coherence" in receipt["score_dimensions"]
    assert "expression_identity_preservation" in receipt["score_dimensions"]
    assert "eye_line_delta_from_front" in receipt["framing_delta_dimensions"]


def test_doc212_host_reprojects_existing_reviewed_candidate_into_blocked_stage_receipt() -> None:
    operation_id = "people_doc196:expression_set:expression.laugh:1:round3"
    host = ProductApiAnchorPackPreparationHost(
        _ReviewService(_laugh_inspection(), operation_id=operation_id)  # type: ignore[arg-type]
    )
    blocked_card = _face_ready_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_operation_ambiguous",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "slot_retry_rounds": {"expression.laugh": 3},
            "last_shared_runtime_failure": None,
        }
    )

    recovered = host.recover_character_card_blocked_stage_receipt(
        asset=SimpleNamespace(visual_asset_id="people_doc196"),
        card=blocked_card,
        stage="expression_set",
    )

    receipt = recovered.last_shared_runtime_failure
    assert isinstance(receipt, dict)
    assert receipt["reviewed_attempt_count"] == 1
    assert receipt["prompt_reference_parity_verified"] is True
    assert receipt["shared_review_receipts"][0]["owner"] == "v3_shared_visual_cluster"
    assert receipt["shared_review_receipts"][0]["status"] == "pass"
    assert "mouth_eye_coherence" in receipt["shared_review_receipts"][0]["score_dimensions"]


class _Doc212RecoverBeforeRetryHost:
    production_shared_runtime = True

    def __init__(self) -> None:
        self.recover_called = False
        self.received_retry_card: CharacterCardState | None = None

    def recover_character_card_blocked_stage_receipt(self, *, asset, card, stage):  # noqa: ANN001, ANN201
        self.recover_called = True
        receipt = CharacterCardSharedRuntimeFailureReceipt(
            failure_count=2,
            reviewed_attempt_count=1,
            prompt_reference_parity_verified=True,
            shared_review_receipts=[
                project_laugh_expression_review_receipt(
                    score_card=_laugh_inspection()["score_card"],
                    issue_codes=[],
                ).to_public_dict()
            ],
        )
        return card.model_copy(update={"last_shared_runtime_failure": receipt.model_dump(mode="json")})

    def prepare_expression_set(self, *, asset, card, generation_channel="provider"):  # noqa: ANN001, ANN201
        self.received_retry_card = card
        blocked = card.model_copy(
            update={
                "expression_set_status": "blocked",
                "last_failed_module": "expression_set",
                "last_failed_slot_key": "expression.laugh",
                "last_failure_code": "mcp_materialization_pending",
                "last_failure_attempt_count": 1,
                "resume_available": True,
            }
        )
        return CharacterCardStageResult(
            status="blocked",
            card=blocked,
            failures=[
                CharacterCardFailureEvent(
                    module="expression_set",
                    slot_key="expression.laugh",
                    candidate_index=1,
                    attempt_round=4,
                    failure_code="mcp_materialization_pending",
                )
            ],
            shared_runtime_failure=CharacterCardSharedRuntimeFailureReceipt(failure_count=1),
        )


def test_doc212_lifecycle_reprojects_missing_receipt_before_confirmed_ambiguous_retry() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _doc196_catalog_asset(catalog)
    blocked_card = _face_ready_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_operation_ambiguous",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "slot_retry_rounds": {"expression.laugh": 3},
            "last_shared_runtime_failure": None,
        }
    )
    catalog.save(asset.model_copy(update={"character_card": blocked_card}))
    host = _Doc212RecoverBeforeRetryHost()
    lifecycle = VisualAssetLibraryLifecycleService(catalog, character_card_stage_host=host)

    updated = lifecycle.prepare_character_card_stage(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        stage="expression_set",
        generation_channel="mcp",
        retry_failed_slot=True,
        confirm_retry=True,
    )

    assert host.recover_called is True
    assert host.received_retry_card is not None
    assert host.received_retry_card.slot_retry_rounds["expression.laugh"] == 4
    assert host.received_retry_card.last_shared_runtime_failure is None
    assert updated.character_card.last_failure_code == "mcp_materialization_pending"


def test_doc211_public_character_card_projects_blocked_stage_review_receipt() -> None:
    inspection = _laugh_inspection()
    receipt = project_laugh_expression_review_receipt(
        score_card=inspection["score_card"],
        issue_codes=[],
    )
    catalog = VisualAssetLibraryCatalog()
    asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Doc211 public failure receipt asset",
            root_source_asset_id="root_doc211",
            consent_reference="consent_doc211",
            preparation_intent="neutral identity evidence capture",
        ),
    )
    card = _face_ready_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_operation_ambiguous",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "last_shared_runtime_failure": {
                "review_owner": "v3_shared_vision",
                "retry_owner": "v3_shared_visual_retry",
                "candidate_count": 3,
                "failure_count": 1,
                "resume_available": True,
                "reviewed_attempt_count": 1,
                "prompt_reference_parity_verified": True,
                "shared_review_receipts": [receipt.to_public_dict()],
            },
        }
    )

    public = V3ProductRouteHandlers._visual_asset_public_record(asset.model_copy(update={"character_card": card}))

    projected = public["character_card"]["last_shared_runtime_failure"]
    assert projected["reviewed_attempt_count"] == 1
    assert projected["prompt_reference_parity_verified"] is True
    assert projected["shared_review_receipts"][0]["status"] == "pass"
    assert "mouth_eye_coherence" in projected["shared_review_receipts"][0]["score_dimensions"]
    public_text = json.dumps(projected, ensure_ascii=False).lower()
    assert "canonical_prompt" not in public_text
    assert "final_provider_prompt" not in public_text
    assert "file_path" not in public_text
    assert "raw_response" not in public_text


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
    assert laugh_expression_materialization_directive(laugh_expression_intent_contract()) in canonical.prompt
    assert "clearly readable joyful laugh keyframe" in canonical.prompt
    assert "not merely a polite open-mouth smile" in canonical.prompt
    assert "engaged, lively gaze as expression evidence only" in canonical.prompt
    assert "clearly visible eye-cheek coupling" in canonical.prompt
    assert "upper cheeks lift into the lower eyelids" in canonical.prompt
    assert "slightly narrower joyful crescent arcs" in canonical.prompt
    assert "must synchronize with cheek lift and periocular affect" in canonical.prompt
    assert "onset to peak static keyframe" in canonical.prompt
    assert "bright engaged gaze" not in canonical.prompt
    assert "bright lighting" not in canonical.prompt
    assert "inheriting the face.front card framing" in canonical.prompt
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


def test_doc201_provider_and_mcp_recovery_prompts_project_the_same_structured_laugh_contract() -> None:
    runtime = ScenarioRuntime()
    prompts: dict[str, str] = {}
    for channel in ("provider", "mcp"):
        request = _expression_slot_delta_runtime_request("expression.laugh")
        request = request.model_copy(
            update={
                "metadata": {
                    **request.metadata,
                    "generation_channel": channel,
                    **({"mcp_operation_id": "asset_doc201:expression_set:expression.laugh:1"} if channel == "mcp" else {}),
                }
            }
        )
        recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
            request,
            _remote_required_expression_brain_result("expression.laugh"),
        )
        prompts[channel] = recovered.canonical_provider_prompts[0].prompt

    directive = laugh_expression_materialization_directive(laugh_expression_intent_contract())
    assert prompts["provider"] == prompts["mcp"]
    assert directive in prompts["provider"]
    assert "engaged, lively gaze as expression evidence only" in prompts["provider"]
    assert "bright engaged gaze" not in prompts["provider"]
    assert "bright lighting" not in prompts["provider"]


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
    assert "clearly readable joyful laugh keyframe" not in prompt
    assert "captured laugh phase from onset toward peak" not in prompt
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


@pytest.mark.parametrize(
    "case_label,user_input",
    [
        (
            "adult_male_low_key",
            "Prepare a restrained laugh slot for an adult male card whose approved front card is low-key and warm-toned.",
        ),
        (
            "adult_female_editorial",
            "Prepare a joyful laugh slot for an adult female card whose approved front card is editorial and soft-matte.",
        ),
        (
            "child_clean_reference",
            "Prepare a medium laugh slot for a child card whose approved front card is clean and high-key.",
        ),
    ],
)
def test_doc197_expression_recovery_inherits_style_channels_without_case_specific_skin_or_lighting(
    case_label: str,
    user_input: str,
) -> None:
    runtime = ScenarioRuntime()
    request = _expression_slot_delta_runtime_request("expression.laugh").model_copy(
        update={
            "user_input": user_input,
            "metadata": {
                **_expression_slot_delta_runtime_request("expression.laugh").metadata,
                "doc197_style_fixture": case_label,
            },
        },
        deep=True,
    )

    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_expression_brain_result("expression.laugh"),
    )

    assert recovered.canonical_provider_prompts
    prompt = recovered.canonical_provider_prompts[0].prompt
    assert "complexion channel" in prompt
    assert "lighting direction" in prompt
    assert "wardrobe/style channel" in prompt
    assert "camera-observed skin/material texture" in prompt
    forbidden = (
        "cool fair",
        "fair skin",
        "same bright clean lighting",
        "bright clean lighting",
        "bright even lighting",
        "adult styling",
        "same child",
        "child head proportions",
        "commercial clean photo finish",
    )
    assert not any(fragment in prompt for fragment in forbidden)


def test_doc197_face_slot_delta_recovery_prompts_are_style_neutral_and_person_generic() -> None:
    forbidden = (
        "cool fair",
        "fair skin",
        "bright clean lighting",
        "bright even lighting",
        "same child",
        "child head proportions",
        "commercial clean finish",
        "commercial clean photo finish",
    )
    for view_role in (
        "left_front_25",
        "three_quarter",
        "profile",
        "right_front_25",
        "reverse_three_quarter",
        "rear_head",
    ):
        prompt = ScenarioRuntime._character_card_slot_delta_recovery_prompt(view_role)  # noqa: SLF001
        assert "same person" in prompt
        assert "background treatment" in prompt
        assert "lighting direction" in prompt
        assert "wardrobe/style channel" in prompt
        assert "visual finish" in prompt
        assert not any(fragment in prompt for fragment in forbidden)
