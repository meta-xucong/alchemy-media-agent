"""Doc213: Character Card prior review repair reaches the next handoff.

These tests do not generate images.  They lock the handoff-resolution contract
that failed during controlled MCP validation: once shared Vision gives a
retryable Doc93/channel repair signal, the next candidate must not repeat an
identical prompt context.
"""

from __future__ import annotations

from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    ProductApiAnchorPackPreparationHost,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorReviewDecision
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSlot,
    CharacterCardState,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary


def _face_ready_card() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_doc213")
    front = CharacterCardSlot(
        slot_key="face.front",
        module="face_identity",
        state="active",
        output_id="front_winner",
        source_candidate_ids=["front_candidate"],
        lineage_id="front_lineage",
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


def _candidate(request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
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


class _RecordingGenerator:
    def __init__(self) -> None:
        self.requests: list[CharacterCardCandidateRequest] = []

    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        self.requests.append(request)
        return _candidate(request)


class _FirstLaughCandidateNeedsDoc93RepairReviewer:
    def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
        if candidate.slot_key == "expression.laugh" and candidate.candidate_index == 1:
            return AnchorReviewDecision(
                status="fail",
                identity_scores=IdentityScoreSummary(
                    same_face_score=0.84,
                    distinctive_feature_score=0.84,
                    human_realism_score=0.86,
                    visual_quality_score=0.88,
                    evidence_codes=[],
                ),
                issue_codes=["source_hair_overinherited", "professional_ai_overperfection"],
                shared_review_receipts=[
                    {
                        "owner": "v3_shared_visual_cluster",
                        "contract_version": "v3_affective_expression_review_receipt_v1",
                        "status": "pass",
                        "issue_codes": [],
                        "evidence_codes": sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES),
                    }
                ],
            )
        return AnchorReviewDecision(
            status="pass",
            identity_scores=IdentityScoreSummary(
                same_face_score=0.92,
                distinctive_feature_score=0.9,
                human_realism_score=0.91,
                visual_quality_score=0.93,
                evidence_codes=(
                    sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES)
                    if candidate.slot_key == "expression.laugh"
                    else []
                ),
            ),
        )


def test_doc213_failed_character_card_candidate_projects_review_repair_to_next_request() -> None:
    generator = _RecordingGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_FirstLaughCandidateNeedsDoc93RepairReviewer(),
    )

    result = service.prepare_expression_set(
        _face_ready_card(),
        front_output_id="front_winner",
        user_intents={
            "laugh": "medium laugh keyframe",
            "anger": "quiet controlled anger",
            "sad": "subtle sadness",
        },
        generation_channel="mcp",
    )

    laugh_requests = [request for request in generator.requests if request.slot_key == "expression.laugh"]
    assert result.status == "review"
    assert laugh_requests[0].prior_review_repair is None
    assert laugh_requests[1].prior_review_repair is not None
    assert "source_hair_overinherited" in laugh_requests[1].prior_review_repair["issue_codes"]
    assert laugh_requests[1].prior_review_repair["owner"] == "v3_shared_visual_cluster"
    assert laugh_requests[1].prior_review_repair["observed_review_evidence"]


def test_doc213_host_projects_prior_repair_to_standard_retry_evidence_without_raw_leakage() -> None:
    request = CharacterCardCandidateRequest(
        project_id="project_doc213",
        people_asset_id="asset_doc213",
        card_version_id="card_doc213",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=4,
        reference_output_ids=["front_winner"],
        user_intent="medium laugh keyframe",
        generation_channel="mcp",
        prior_review_repair={
            "contract_version": "v3_shared_review_repair_context_v1",
            "owner": "v3_shared_visual_cluster",
            "source": "prior_candidate_shared_review",
            "retry_evidence_only": True,
            "target_candidate_id": "candidate_1",
            "target_output_id": "output_1",
            "issue_codes": ["source_hair_overinherited", "professional_ai_overperfection"],
            "observed_review_evidence": [
                "Shared review observed that source hair from the identity reference was copied into a prompt-owned hair channel.",
                "Shared review observed over-polished or artificial human material finish.",
            ],
        },
    )

    metadata = ProductApiAnchorPackPreparationHost._character_card_prior_review_repair_metadata(request)

    assert metadata["visual_retry_reason_codes"] == [
        "source_hair_overinherited",
        "professional_ai_overperfection",
    ]
    provenance = metadata["resolved_retry_provenance"]
    assert provenance["authority"] == "v3_product_api"
    assert provenance["prompt_owner"] == "remote_v3_llm_brain"
    assert provenance["observed_review_evidence"]
    public_text = str(metadata)
    assert "canonical_prompt" not in public_text
    assert "provider_response" not in public_text
    assert "C:\\" not in public_text
    assert "raw_reference" not in public_text


def test_doc213_expression_slot_delta_recovery_consumes_repair_context_without_repeating_prompt() -> None:
    repair_context = {
        "contract_version": "v3_shared_review_repair_context_v1",
        "owner": "v3_shared_visual_cluster",
        "source": "prior_candidate_shared_review",
        "retry_evidence_only": True,
        "issue_codes": ["source_hair_overinherited"],
        "observed_review_evidence": [
            "Shared review observed that source hair from the identity reference was copied into a prompt-owned hair channel."
        ],
    }

    baseline = ScenarioRuntime._character_card_expression_slot_delta_recovery_prompt("laugh")
    repaired = ScenarioRuntime._character_card_expression_slot_delta_recovery_prompt(
        "laugh",
        repair_context=repair_context,
    )

    assert baseline != repaired
    assert "clearly readable joyful laugh keyframe" in repaired
    assert "face.front Character Card winner" in repaired
    assert "prompt-owned hair channel" in repaired
    assert "source_hair_overinherited" not in repaired
