"""Doc182 bounded failure pause and explicit resume contracts."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from pathlib import Path
import hashlib

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationError,
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.generation_router.providers import McpMaterializationProvider
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    ProductApiAnchorPackPreparationHost,
    _character_card_face_identity_mcp_prompt_current,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatus, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES,
    expression_front_card_framing_materialization_directive,
    laugh_expression_materialization_directive,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateResult,
    AnchorCandidateFailure,
    AnchorCandidateUnavailable,
    AnchorGenerationRequest,
    AnchorPackPreparationResult,
    AnchorPackPreparationRequest,
    AnchorPackPreparationService,
    AnchorReviewDecision,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeFailureReceipt,
    CharacterCardStageResult,
    CharacterCardState,
    apply_face_identity_pack_to_card,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    AnchorCandidateFailureReceipt,
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    VisualAssetVersion,
    VisualAssetLibraryCatalog,
    VisualAssetLibraryLifecycleService,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest


def _current_laugh_handoff_prompt(*, suffix: str = "") -> str:
    return (
        f"{laugh_expression_materialization_directive()} "
        f"{expression_front_card_framing_materialization_directive()} "
        f"{suffix}"
    ).strip()


def _face_card() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_doc182")
    return card.model_copy(
        update={
            "face_identity_status": "active",
            "face_slots": {
                **card.face_slots,
                "face.front": card.face_slots["face.front"].model_copy(
                    update={
                        "state": "active",
                        "output_id": "front_winner",
                        "source_candidate_ids": ["front_candidate"],
                        "lineage_id": "front_lineage",
                        "review_verified": True,
                        "prompt_reference_parity_verified": True,
                        "candidate_attempt_count": 3,
                    }
                ),
            },
        }
    )


def _face_anchor_view(role: str, output_id: str) -> AnchorView:
    return AnchorView(
        view_id=f"view_{output_id}",
        view_role=role,  # type: ignore[arg-type]
        output_id=output_id,
        source_candidate_ids=[f"candidate_{output_id}"],
        identity_scores=IdentityScoreSummary(
            same_face_score=0.91,
            distinctive_feature_score=0.9,
            human_realism_score=0.92,
            visual_quality_score=0.93,
            pose_compliance_score=0.92,
        ),
    )


def _character_candidate(request) -> CharacterCardCandidateResult:
    token = f"{request.slot_key.replace('.', '_')}_{request.candidate_index}"
    return CharacterCardCandidateResult(
        candidate_id=f"candidate_{token}",
        output_id=f"output_{token}",
        module=request.module,
        slot_key=request.slot_key,
        candidate_index=request.candidate_index,
        source_candidate_ids=[f"source_{token}"],
        source_output_ids=list(request.reference_output_ids),
        canonical_prompt_hash=f"sha256:{token}",
        prompt_compilation_id=f"compile_{token}",
        prompt_reference_parity_verified=True,
    )


class _ExpressionGenerator:
    def __init__(self, *, failing_slots: set[str] | None = None, handoff_ids: dict[str, str] | None = None) -> None:
        self.failing_slots = set(failing_slots or set())
        self.handoff_ids = dict(handoff_ids or {})
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if request.slot_key in self.failing_slots:
            raise AnchorCandidateUnavailable(
                "character_card_candidate_provider_failed",
                mcp_handoff_id=self.handoff_ids.get(request.slot_key),
            )
        return _character_candidate(request)


class _PassReviewer:
    def review(self, candidate):
        return AnchorReviewDecision(
            status="pass",
            identity_scores=IdentityScoreSummary(
                same_face_score=0.9,
                distinctive_feature_score=0.9,
                human_realism_score=0.9,
                visual_quality_score=0.9,
                evidence_codes=sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES)
                if getattr(candidate, "slot_key", "") == "expression.laugh"
                else [],
            ),
        )


class _FailReviewer:
    def review(self, candidate):
        return AnchorReviewDecision(
            status="fail",
            identity_scores=IdentityScoreSummary(
                same_face_score=0.4,
                distinctive_feature_score=0.4,
                human_realism_score=0.4,
                visual_quality_score=0.4,
            ),
            issue_codes=["shared_visual_review_failed"],
        )


def test_doc193_anchor_pack_failure_receipt_prefers_specific_review_gate_code() -> None:
    review = AnchorReviewDecision(
        status="fail",
        identity_scores=IdentityScoreSummary(
            same_face_score=0.9,
            distinctive_feature_score=0.9,
            human_realism_score=0.9,
            visual_quality_score=0.9,
        ),
        issue_codes=[
            "professional_face_card_view_angle_too_shallow",
            "shared_visual_review_failed",
        ],
    )

    assert (
        AnchorPackPreparationService._failure_code_from_review(review)  # noqa: SLF001
        == "professional_face_card_view_angle_too_shallow"
    )


def test_doc182_three_failures_pause_without_unhandled_exception() -> None:
    service = CharacterCardPreparationService(
        generator=_ExpressionGenerator(failing_slots={"expression.laugh"}),
        reviewer=_PassReviewer(),
    )
    result = service.prepare_expression_set(
        _face_card(),
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
    )

    assert result.status == "blocked"
    assert result.card.expression_set_status == "blocked"
    assert result.card.resume_available is True
    assert result.card.last_failed_slot_key == "expression.laugh"
    assert result.card.last_failure_attempt_count == 3
    assert len(result.failures) == 3
    assert result.card.expression_slots["expression.laugh"].state == "empty"

    receipt = CharacterCardSharedRuntimeFailureReceipt(failure_count=len(result.failures))
    assert receipt.resume_available is True
    assert receipt.review_owner == "v3_shared_vision"


def test_doc183_character_card_failure_exposes_only_resumable_mcp_handoff() -> None:
    service = CharacterCardPreparationService(
        generator=_ExpressionGenerator(
            failing_slots={"expression.laugh"},
            handoff_ids={"expression.laugh": "mcp_handoff_expression_laugh"},
        ),
        reviewer=_PassReviewer(),
    )
    result = service.prepare_expression_set(
        _face_card(),
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
        generation_channel="mcp",
    )

    assert result.status == "blocked"
    assert result.mcp_handoff_ids == ["mcp_handoff_expression_laugh"]
    assert result.card.pending_mcp_handoff_ids == ["mcp_handoff_expression_laugh"]
    assert result.failures[0].mcp_handoff_id == "mcp_handoff_expression_laugh"
    public_card = result.card.model_dump_json()
    assert "provider_id" not in public_card
    assert "canonical_prompt" not in public_card
    assert "file_path" not in public_card


def test_doc195_mcp_stage_pauses_after_first_pending_handoff() -> None:
    class _PendingMcpGenerator:
        def __init__(self) -> None:
            self.requests = []

        def generate(self, request):  # noqa: ANN001, ANN201
            self.requests.append(request)
            raise AnchorCandidateUnavailable(
                "mcp_materialization_pending",
                mcp_handoff_id=f"mcp_handoff_{request.slot_key}_{request.candidate_index}",
            )

    generator = _PendingMcpGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_PassReviewer(),
    )
    result = service.prepare_expression_set(
        _face_card(),
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
        generation_channel="mcp",
    )

    assert result.status == "blocked"
    assert [request.candidate_index for request in generator.requests] == [1]
    assert result.card.last_failed_slot_key == "expression.laugh"
    assert result.card.last_failure_attempt_count == 1
    assert result.mcp_handoff_ids == ["mcp_handoff_expression.laugh_1"]
    assert result.card.pending_mcp_handoff_ids == ["mcp_handoff_expression.laugh_1"]
    assert result.card.resume_available is True


def test_doc191_character_card_stage_surfaces_remote_brain_unavailable() -> None:
    class _BlockedStageService:
        visual_asset_catalog = None

        def create_professional_character_card_stage_job(self, *_args, **_kwargs):
            return ProductJobStatus(
                job_id="job_doc191_brain_blocked",
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return SimpleNamespace(
                request=SimpleNamespace(
                    metadata={
                        "remote_creative_brain_outcome": {
                            "reason_code": "remote_brain_unavailable",
                        }
                    }
                )
            )

    host = ProductApiAnchorPackPreparationHost(_BlockedStageService())  # type: ignore[arg-type]
    request = CharacterCardCandidateRequest(
        project_id="project_doc191",
        people_asset_id="people_doc191",
        card_version_id="card_doc191",
        module="expression_set",
        slot_key="expression.smile",
        candidate_index=1,
        reference_output_ids=["front_winner"],
        user_intent="authorized expression-set intent",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        host.generate(request)

    assert exc_info.value.failure_code == "remote_brain_unavailable"


def test_doc191_character_card_mcp_stage_resumes_existing_handoff_job() -> None:
    class _OutputStore:
        def list_by_job(self, job_id):  # noqa: ANN001, ANN201
            assert job_id == "job_doc191_existing_mcp"
            return [
                SimpleNamespace(
                    output_id="output_expression_smile_1",
                    candidate_id="candidate_expression_smile_1",
                    metadata={
                        "provider_prompt_sha256": "sha256:expression_smile",
                        "prompt_compilation_id": "compile_expression_smile",
                        "provider_reference_image_count": 2,
                    },
                )
            ]

    class _JobStore:
        def __init__(self, record) -> None:  # noqa: ANN001
            self.record = record

        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [self.record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [self.record]

        def save(self, record):  # noqa: ANN001, ANN201
            self.record = record
            return record

    class _ResumeStageService:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created = 0
            self.record = SimpleNamespace(
                job_id="job_doc191_existing_mcp",
                planning_result=SimpleNamespace(
                    result_id="planning_doc191",
                    generation_plans=[
                        SimpleNamespace(
                            metadata={
                                "professional_character_card_preparation": True,
                                "professional_character_card_stage": "expression_set",
                                "professional_character_card_slot": "expression.smile",
                                "professional_character_card_source_class": None,
                                "professional_character_card_attempt_round": 1,
                                "professional_character_card_reference_output_ids": ["front_winner"],
                                "professional_identity_reference_strategy": "character_card_shared_identity_v1",
                                "professional_reference_stage": "character_card_expression_set",
                                "generation_channel": "mcp",
                                "mcp_operation_id": "people_doc191:expression_set:expression.smile:1",
                                "professional_anchor_reference_assets": [
                                    {
                                        "asset_id": "front_winner",
                                        "derivative_kind": "character_card_full_frame_framing_reference",
                                        "identity_evidence_scope": "card_framing",
                                    },
                                    {"asset_id": "front_winner::portrait_identity_crop"},
                                    {"asset_id": "front_winner::portrait_identity_geometry_crop"},
                                ],
                            }
                        )
                    ],
                ),
                generation_result=None,
                request=SimpleNamespace(
                    metadata={
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.smile",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": (
                            "people_doc191:expression_set:expression.smile:1"
                        ),
                        "mcp_materialization": {
                            "handoff_id": "mcp_handoff_expression_smile_1",
                            "status": "pending",
                        },
                    }
                ),
            )
            self.job_store = _JobStore(self.record)
            self.output_store = _OutputStore()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": "same character card face with a gentle smile",
                    "reference_assets": [
                        {
                            "asset_id": "front_winner",
                            "derivative_kind": "character_card_full_frame_framing_reference",
                            "identity_evidence_scope": "card_framing",
                        },
                        {"asset_id": "front_winner::portrait_identity_crop"},
                        {"asset_id": "front_winner::portrait_identity_geometry_crop"},
                    ],
                }
            )

        def create_professional_character_card_stage_job(self, *_args, **_kwargs):
            self.created += 1
            raise AssertionError("resume must not create a second Brain planning job")

        def generate_job(self, job_id, request):  # noqa: ANN001, ANN201
            assert job_id == "job_doc191_existing_mcp"
            assert request["metadata"]["_v3_resume_finalizing_review"] is True
            self.record.generation_result = SimpleNamespace(
                metadata={
                    "visual_auto_retry": {"executed_count": 0},
                    "post_generation_review_package": {
                        "inspections": [
                            {
                                "output_id": "output_expression_smile_1",
                                "mode": "hybrid",
                                "verification_state": "verified",
                                "status": "pass",
                                "score_card": {
                                    "same_person_readability": 0.9,
                                    "visual_quality": 0.9,
                                    "distinctive_feature_readability": 0.9,
                                    "human_realism": 0.9,
                                    "pose_compliance": 0.9,
                                    "overall": 0.9,
                                },
                                "issue_codes": [],
                            }
                        ]
                    },
                }
            )
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.GENERATED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            assert job_id == "job_doc191_existing_mcp"
            return self.record

    service = _ResumeStageService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    request = CharacterCardCandidateRequest(
        project_id="project_doc191",
        people_asset_id="people_doc191",
        card_version_id="card_doc191",
        module="expression_set",
        slot_key="expression.smile",
        candidate_index=1,
        reference_output_ids=["front_winner"],
        user_intent="authorized expression-set intent",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_expression_smile_1",
    )

    candidate = host.generate(request)

    assert service.created == 0
    assert candidate.output_id == "output_expression_smile_1"


def test_doc183_mcp_channel_survives_runtime_plan_boundary() -> None:
    runtime = ScenarioRuntime()
    request = ScenarioRuntimeRequest(
        user_input="resume the trusted character-card materialization through MCP",
        metadata={
            "generation_channel": "mcp",
            "mcp_operation_id": "mcp_doc183_channel_boundary",
        },
    )

    assert runtime._renderer_channel_metadata(request) == {
        "generation_channel": "mcp",
        "mcp_operation_id": "mcp_doc183_channel_boundary",
    }

    provider_request = ScenarioRuntimeRequest(
        user_input="ordinary provider materialization",
        metadata={},
    )
    assert runtime._renderer_channel_metadata(provider_request) == {}


def test_doc183_central_brain_keeps_mcp_channel_on_materialization_plan() -> None:
    result = CentralCreativeBrain().run_generation_loop(
        user_input="Prepare one trusted character-card identity capture.",
        provider_strategy=ProviderStrategy.MOCK_GENERATION,
        runtime_metadata={
            "generation_channel": "mcp",
            "mcp_operation_id": "mcp_doc183_brain_plan",
            "requested_image_count": 1,
        },
    )

    metadata = result.generation_plans[0].metadata
    assert metadata["generation_channel"] == "mcp"
    assert metadata["mcp_operation_id"] == "mcp_doc183_brain_plan"


def test_doc182_resume_keeps_winner_and_starts_at_failed_slot() -> None:
    first_generator = _ExpressionGenerator(failing_slots={"expression.anger"})
    service = CharacterCardPreparationService(generator=first_generator, reviewer=_PassReviewer())
    first = service.prepare_expression_set(
        _face_card(),
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
    )
    assert first.status == "blocked"
    assert first.card.expression_slots["expression.laugh"].output_id
    assert [request.slot_key for request in first_generator.requests] == [
        "expression.laugh",
        "expression.laugh",
        "expression.laugh",
        "expression.anger",
        "expression.anger",
        "expression.anger",
    ]

    second_generator = _ExpressionGenerator()
    resumed = CharacterCardPreparationService(generator=second_generator, reviewer=_PassReviewer()).prepare_expression_set(
        first.card,
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
    )
    assert resumed.status == "review"
    assert [request.slot_key for request in second_generator.requests] == [
        "expression.anger",
        "expression.anger",
        "expression.anger",
        "expression.sad",
        "expression.sad",
        "expression.sad",
    ]
    assert resumed.card.expression_slots["expression.laugh"].output_id == first.card.expression_slots["expression.laugh"].output_id


def test_doc202_confirmed_failed_expression_slot_retry_starts_new_round_without_losing_winners() -> None:
    first_generator = _ExpressionGenerator(failing_slots={"expression.anger"})
    service = CharacterCardPreparationService(generator=first_generator, reviewer=_PassReviewer())
    first = service.prepare_expression_set(
        _face_card(),
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
    )

    assert first.status == "blocked"
    assert first.card.last_failed_slot_key == "expression.anger"
    assert first.card.last_failure_attempt_count == 3

    with pytest.raises(ValueError, match="confirmation"):
        first.card.begin_failed_slot_retry(module="expression_set", confirmed=False)

    retry_card = first.card.begin_failed_slot_retry(module="expression_set", confirmed=True)
    assert retry_card.slot_retry_rounds["expression.anger"] == 2
    assert retry_card.expression_slots["expression.laugh"].output_id == first.card.expression_slots["expression.laugh"].output_id
    assert retry_card.resume_available is False
    assert retry_card.pending_mcp_handoff_ids == []

    second_generator = _ExpressionGenerator()
    resumed = CharacterCardPreparationService(generator=second_generator, reviewer=_PassReviewer()).prepare_expression_set(
        retry_card,
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
    )

    assert resumed.status == "review"
    assert resumed.card.expression_slots["expression.laugh"].output_id == first.card.expression_slots["expression.laugh"].output_id
    assert [
        (request.slot_key, request.candidate_index, request.attempt_round)
        for request in second_generator.requests
    ] == [
        ("expression.anger", 1, 2),
        ("expression.anger", 2, 2),
        ("expression.anger", 3, 2),
        ("expression.sad", 1, 1),
        ("expression.sad", 2, 1),
        ("expression.sad", 3, 1),
    ]


def test_doc202_failed_slot_retry_cannot_supersede_pending_mcp_handoff() -> None:
    card = _face_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_pending",
            "last_failure_attempt_count": 1,
            "resume_available": True,
            "pending_mcp_handoff_ids": ["mcp_handoff_expression_laugh_1"],
        }
    )

    with pytest.raises(ValueError, match="pending MCP handoff"):
        card.begin_failed_slot_retry(module="expression_set", confirmed=True)


def test_doc210_confirmed_retry_can_supersede_ambiguous_mcp_operation_without_exhausted_budget() -> None:
    card = _face_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_operation_ambiguous",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "pending_mcp_handoff_ids": [],
            "last_shared_runtime_failure": {
                "review_owner": "v3_shared_vision",
                "retry_owner": "v3_shared_visual_retry",
                "candidate_count": 3,
                "failure_count": 1,
                "resume_available": True,
                "reviewed_attempt_count": 1,
                "prompt_reference_parity_verified": True,
                "shared_review_receipts": [
                    {
                        "owner": "v3_shared_visual_cluster",
                        "contract_version": "v3_affective_expression_review_receipt_v1",
                        "expression": "laugh",
                        "framing_baseline": "face.front",
                        "status": "pass",
                        "evidence_codes": ["shared_affective_expression_review_receipt_verified"],
                        "issue_codes": [],
                        "score_dimensions": ["mouth_eye_coherence"],
                        "framing_delta_dimensions": ["eye_line_delta_from_front"],
                    }
                ],
            },
        }
    )

    retry_card = card.begin_failed_slot_retry(module="expression_set", confirmed=True)

    assert retry_card.slot_retry_rounds["expression.laugh"] == 2
    assert retry_card.expression_slots["expression.laugh"].state == "empty"
    assert retry_card.resume_available is False
    assert retry_card.pending_mcp_handoff_ids == []


def test_doc211_ambiguous_mcp_retry_requires_shared_runtime_failure_receipt() -> None:
    card = _face_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_operation_ambiguous",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "pending_mcp_handoff_ids": [],
        }
    )

    with pytest.raises(ValueError, match="shared runtime failure receipt"):
        card.begin_failed_slot_retry(module="expression_set", confirmed=True)


def test_doc210_ambiguous_mcp_retry_still_cannot_supersede_pending_handoff() -> None:
    card = _face_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_operation_ambiguous",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "pending_mcp_handoff_ids": ["mcp_handoff_doc210_pending"],
        }
    )

    with pytest.raises(ValueError, match="pending MCP handoff"):
        card.begin_failed_slot_retry(module="expression_set", confirmed=True)


def test_doc202_mcp_character_card_operation_id_is_round_scoped_after_confirmed_retry() -> None:
    class _RoundService:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_kwargs = None

        def create_professional_character_card_stage_job(self, *_args, **kwargs):
            self.created_kwargs = dict(kwargs)
            return ProductJobStatus(
                job_id="job_doc202_round2",
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, _request):  # noqa: ANN001, ANN201
            assert job_id == "job_doc202_round2"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
                metadata={
                    "mcp_materialization": {
                        "handoff_id": "mcp_handoff_expression_laugh_round2_1",
                        "status": "pending",
                        "canonical_prompt": _current_laugh_handoff_prompt(),
                    }
                },
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return None

    service = _RoundService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    request = CharacterCardCandidateRequest(
        project_id="project_doc202",
        people_asset_id="people_doc202",
        card_version_id="card_doc202",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=2,
        reference_output_ids=["front_winner"],
        user_intent="authorized expression-set intent",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        host.generate(request)

    assert service.created_kwargs["mcp_operation_id"] == "people_doc202:expression_set:expression.laugh:1:round2"
    assert service.created_kwargs["attempt_round"] == 2


def test_doc217_mcp_reviewed_failure_checkpoints_before_next_candidate() -> None:
    class _RecordingGenerator:
        def __init__(self) -> None:
            self.requests = []

        def generate(self, request):  # noqa: ANN001, ANN201
            self.requests.append(request)
            return _character_candidate(request)

    generator = _RecordingGenerator()
    result = CharacterCardPreparationService(
        generator=generator,
        reviewer=_FailReviewer(),
    ).prepare_expression_set(
        _face_card(),
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
        generation_channel="mcp",
    )

    assert result.status == "blocked"
    assert [request.candidate_index for request in generator.requests] == [1]
    assert len(result.attempts) == 1
    assert result.card.last_failed_slot_key == "expression.laugh"
    assert result.card.last_failure_code == "character_card_shared_review_failed"
    assert result.card.last_failure_attempt_count == 1
    assert result.card.pending_mcp_handoff_ids == []
    assert result.card.resume_available is True


def test_doc217_mcp_resume_after_reviewed_failure_moves_to_next_candidate() -> None:
    class _CandidateTwoPendingGenerator:
        def __init__(self) -> None:
            self.requests = []

        def generate(self, request):  # noqa: ANN001, ANN201
            self.requests.append(request)
            if request.slot_key == "expression.laugh" and request.candidate_index == 2:
                raise AnchorCandidateUnavailable(
                    "mcp_materialization_pending",
                    mcp_handoff_id="mcp_handoff_expression_laugh_candidate2",
                )
            return _character_candidate(request)

    card = _face_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "character_card_shared_review_failed",
            "last_failure_attempt_count": 1,
            "resume_available": True,
            "pending_mcp_handoff_ids": [],
        }
    )

    generator = _CandidateTwoPendingGenerator()
    result = CharacterCardPreparationService(
        generator=generator,
        reviewer=_PassReviewer(),
    ).prepare_expression_set(
        card,
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
        generation_channel="mcp",
    )

    assert result.status == "blocked"
    assert [
        (request.candidate_index, request.mcp_handoff_id)
        for request in generator.requests
    ] == [(2, None)]
    assert result.card.last_failed_slot_key == "expression.laugh"
    assert result.card.last_failure_attempt_count == 2
    assert result.card.pending_mcp_handoff_ids == ["mcp_handoff_expression_laugh_candidate2"]


def test_doc203_character_card_mcp_resume_passes_pending_handoff_only_to_matching_candidate() -> None:
    class _RecordingGenerator:
        def __init__(self) -> None:
            self.requests = []

        def generate(self, request):  # noqa: ANN001, ANN201
            self.requests.append(request)
            return _character_candidate(request)

    card = _face_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_pending",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "pending_mcp_handoff_ids": ["mcp_handoff_expression_laugh_candidate2"],
        }
    )
    generator = _RecordingGenerator()

    result = CharacterCardPreparationService(generator=generator, reviewer=_PassReviewer()).prepare_expression_set(
        card,
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
        generation_channel="mcp",
    )

    laugh_requests = [request for request in generator.requests if request.slot_key == "expression.laugh"]
    assert result.status == "review"
    assert [
        (request.candidate_index, request.mcp_handoff_id)
        for request in laugh_requests
    ] == [
        (2, "mcp_handoff_expression_laugh_candidate2"),
        (3, None),
    ]


def test_doc206_character_card_mcp_ambiguous_operation_pauses_without_next_candidate() -> None:
    class _AmbiguousCandidateTwoGenerator:
        def __init__(self) -> None:
            self.requests = []

        def generate(self, request):  # noqa: ANN001, ANN201
            self.requests.append(request)
            if request.slot_key == "expression.laugh" and request.candidate_index == 2:
                raise AnchorCandidateUnavailable(
                    "mcp_materialization_operation_ambiguous",
                )
            return _character_candidate(request)

    card = _face_card().model_copy(
        update={
            "expression_set_status": "blocked",
            "last_failed_module": "expression_set",
            "last_failed_slot_key": "expression.laugh",
            "last_failure_code": "mcp_materialization_pending",
            "last_failure_attempt_count": 2,
            "resume_available": True,
            "pending_mcp_handoff_ids": ["mcp_handoff_expression_laugh_candidate2"],
        }
    )
    generator = _AmbiguousCandidateTwoGenerator()

    result = CharacterCardPreparationService(generator=generator, reviewer=_PassReviewer()).prepare_expression_set(
        card,
        front_output_id="front_winner",
        user_intents={"laugh": "natural laugh", "anger": "quietly serious", "sad": "subtle sadness"},
        generation_channel="mcp",
    )

    laugh_requests = [request for request in generator.requests if request.slot_key == "expression.laugh"]
    assert result.status == "blocked"
    assert result.card.last_failure_code == "mcp_materialization_operation_ambiguous"
    assert result.card.last_failure_attempt_count == 2
    assert [
        (request.candidate_index, request.mcp_handoff_id)
        for request in laugh_requests
    ] == [
        (2, "mcp_handoff_expression_laugh_candidate2"),
    ]


class _AnchorGenerator:
    def __init__(self, *, failing_roles: set[str] | None = None, handoff_ids: dict[tuple[str, int], str] | None = None) -> None:
        self.failing_roles = set(failing_roles or set())
        self.handoff_ids = dict(handoff_ids or {})
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if request.view_role in self.failing_roles:
            raise AnchorCandidateUnavailable(
                "anchor_candidate_provider_failed",
                mcp_handoff_id=self.handoff_ids.get((request.view_role, request.candidate_index)),
            )
        token = f"{request.view_role}_{request.candidate_index}"
        return AnchorCandidateResult(
            candidate_id=f"candidate_{token}",
            view_id=f"view_{token}",
            output_id=f"output_{token}",
            view_role=request.view_role,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"candidate_{token}"],
            source_asset_ids=list(request.reference_evidence_ids),
            brain_plan_id=f"brain_{token}",
            canonical_prompt_hash=f"sha256:{token}",
            prompt_compilation_id=f"compile_{token}",
            prompt_reference_parity_verified=True,
        )


def _anchor_request() -> AnchorPackPreparationRequest:
    intent = "neutral identity evidence capture"
    asset = PeopleAsset(
        people_asset_id="people_doc182",
        project_id="project_doc182",
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(module_id="face_doc182", people_asset_id="people_doc182"),
        preparation_intent=intent,
    )
    return AnchorPackPreparationRequest(
        project_id="project_doc182",
        asset=asset,
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="root_doc182",
            project_id="project_doc182",
        ),
        preparation_intent=intent,
        face_view_scope="character_card",
    )


def _mcp_anchor_request() -> AnchorPackPreparationRequest:
    return _anchor_request().model_copy(update={"generation_channel": "mcp"})


def test_doc192_character_card_reverse_45_uses_profile_before_right25_bridge() -> None:
    generator = _AnchorGenerator()
    result = AnchorPackPreparationService(
        generator=generator,
        reviewer=_PassReviewer(),
    ).prepare(_anchor_request())

    assert result.status == "review"
    selected_by_role = {
        view.view_role: view.output_id
        for view in result.pack.anchor_views
    }
    assert [view.view_role for view in result.pack.anchor_views] == [
        "standard_front",
        "left_front_25",
        "three_quarter",
        "profile",
        "right_front_25",
        "reverse_three_quarter",
        "rear_head",
    ]
    reverse_requests = [
        request
        for request in generator.requests
        if request.view_role == "reverse_three_quarter"
    ]
    assert reverse_requests
    assert all(
        request.reference_evidence_ids
        == [
            "root_doc182",
            selected_by_role["standard_front"],
            selected_by_role["profile"],
            selected_by_role["right_front_25"],
        ]
        for request in reverse_requests
    )


def test_doc190_character_card_persists_each_face_slot_winner_as_resume_checkpoint() -> None:
    class _Catalog:
        def __init__(self) -> None:
            self.records = []

        def save_pack(self, pack, *, project_id=None, event_type="review"):  # noqa: ANN001, ANN202
            self.records.append(
                (
                    event_type,
                    pack.status,
                    [view.view_role for view in pack.anchor_views],
                )
            )
            return pack

    catalog = _Catalog()
    result = AnchorPackPreparationService(
        generator=_AnchorGenerator(),
        reviewer=_PassReviewer(),
        catalog=catalog,
    ).prepare(_anchor_request())

    assert result.status == "review"
    assert ("fail", "failed", ["standard_front"]) in catalog.records
    assert ("fail", "failed", ["standard_front", "left_front_25"]) in catalog.records
    assert (
        "fail",
        "failed",
        [
            "standard_front",
            "left_front_25",
            "three_quarter",
            "profile",
            "right_front_25",
            "reverse_three_quarter",
        ],
    ) in catalog.records
    assert catalog.records[-1] == (
        "review",
        "review",
        [
            "standard_front",
            "left_front_25",
            "three_quarter",
            "profile",
            "right_front_25",
            "reverse_three_quarter",
            "rear_head",
        ],
    )


class _McpHandoffGenerator:
    def __init__(self, *, submitted: set[str] | None = None) -> None:
        self.submitted = set(submitted or set())
        self.requests = []

    @staticmethod
    def _handoff_id(request) -> str:
        return (
            str(request.mcp_handoff_id or "").strip()
            or f"mcp_handoff_{request.view_role}_{request.candidate_index}"
        )

    def generate(self, request):
        self.requests.append(request)
        handoff_id = self._handoff_id(request)
        if handoff_id not in self.submitted:
            raise AnchorCandidateUnavailable(
                "mcp_materialization_pending",
                mcp_handoff_id=handoff_id,
            )
        token = f"{request.view_role}_{request.candidate_index}"
        return AnchorCandidateResult(
            candidate_id=f"candidate_{token}",
            view_id=f"view_{token}",
            output_id=f"output_{token}",
            view_role=request.view_role,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"candidate_{token}"],
            source_asset_ids=list(request.reference_evidence_ids),
            brain_plan_id=f"brain_{token}",
            canonical_prompt_hash=f"sha256:{token}",
            prompt_compilation_id=f"compile_{token}",
            prompt_reference_parity_verified=True,
        )


def test_doc182_face_resume_skips_completed_views_and_creates_new_pack() -> None:
    first_generator = _AnchorGenerator(failing_roles={"profile"})
    first_service = AnchorPackPreparationService(generator=first_generator, reviewer=_PassReviewer())
    first = first_service.prepare(_anchor_request())
    assert first.status == "blocked"
    assert [view.view_role for view in first.pack.anchor_views] == [
        "standard_front",
        "left_front_25",
        "three_quarter",
    ]
    assert len(first.generation_failures) == 3

    second_generator = _AnchorGenerator()
    second_service = AnchorPackPreparationService(generator=second_generator, reviewer=_PassReviewer())
    resumed = second_service.prepare(_anchor_request(), resume_from_pack=first.pack)
    assert resumed.status == "review"
    assert resumed.pack.pack_version_id != first.pack.pack_version_id
    assert [request.view_role for request in second_generator.requests[:3]] == ["profile"] * 3
    assert all(
        request.view_role not in {"standard_front", "left_front_25", "three_quarter"}
        for request in second_generator.requests
    )
    assert first.pack.status == "failed"


def test_doc183_anchor_failure_persists_opaque_mcp_handoffs_for_resume() -> None:
    service = AnchorPackPreparationService(
        generator=_AnchorGenerator(
            failing_roles={"standard_front"},
            handoff_ids={
                ("standard_front", 1): "mcp_handoff_front_1",
                ("standard_front", 2): "mcp_handoff_front_2",
                ("standard_front", 3): "mcp_handoff_front_3",
            },
        ),
        reviewer=_PassReviewer(),
    )
    result = service.prepare(_anchor_request())

    assert result.status == "blocked"
    assert result.mcp_handoff_ids == [
        "mcp_handoff_front_1",
        "mcp_handoff_front_2",
        "mcp_handoff_front_3",
    ]
    assert all(item.mcp_handoff_id for item in result.generation_failures)


def test_doc187_mcp_face_resume_consumes_handoff_by_frozen_candidate_index() -> None:
    first_generator = _McpHandoffGenerator()
    first_service = AnchorPackPreparationService(generator=first_generator, reviewer=_PassReviewer())
    first = first_service.prepare(_mcp_anchor_request())

    assert first.status == "blocked"
    assert first.mcp_handoff_ids == ["mcp_handoff_standard_front_1"]
    assert [
        (item.view_role, item.candidate_index, item.failure_code, item.mcp_handoff_id)
        for item in first.pack.candidate_failures
    ] == [
        ("standard_front", 1, "mcp_materialization_pending", "mcp_handoff_standard_front_1"),
    ]

    second_generator = _McpHandoffGenerator(submitted={"mcp_handoff_standard_front_1"})
    second_service = AnchorPackPreparationService(generator=second_generator, reviewer=_FailReviewer())
    resumed = second_service.prepare(_mcp_anchor_request(), resume_from_pack=first.pack)

    assert resumed.status == "blocked"
    assert [
        (request.view_role, request.candidate_index, request.mcp_handoff_id)
        for request in second_generator.requests
    ] == [
        ("standard_front", 1, "mcp_handoff_standard_front_1"),
        ("standard_front", 2, None),
    ]
    assert resumed.mcp_handoff_ids == ["mcp_handoff_standard_front_2"]
    assert [
        (item.view_role, item.candidate_index, item.failure_code, item.mcp_handoff_id)
        for item in resumed.pack.candidate_failures
    ] == [
        ("standard_front", 1, "shared_visual_review_failed", None),
        ("standard_front", 2, "mcp_materialization_pending", "mcp_handoff_standard_front_2"),
    ]


def test_doc190_mcp_resume_consumes_legacy_review_failure_when_handoff_id_exists() -> None:
    first = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(),
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request())
    legacy_pack = first.pack.model_copy(
        update={
            "candidate_failures": [
                failure.model_copy(update={"failure_code": "shared_visual_review_failed"})
                for failure in first.pack.candidate_failures
            ]
        }
    )

    generator = _McpHandoffGenerator(submitted={"mcp_handoff_standard_front_1"})
    resumed = AnchorPackPreparationService(
        generator=generator,
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=legacy_pack)

    assert [
        (request.view_role, request.candidate_index, request.mcp_handoff_id)
        for request in generator.requests[:3]
    ] == [
        ("standard_front", 1, "mcp_handoff_standard_front_1"),
        ("left_front_25", 1, None),
    ]
    assert [view.view_role for view in resumed.pack.anchor_views] == ["standard_front"]
    assert resumed.pack.anchor_views[0].output_id == "output_standard_front_1"
    assert resumed.mcp_handoff_ids == ["mcp_handoff_left_front_25_1"]


def test_doc193_mcp_resume_skips_non_resumable_failure_before_pending_handoff() -> None:
    request = _mcp_anchor_request()
    prior_pack = IdentityAnchorPackVersion(
        pack_version_id="pack_doc193_mcp_specific_failure",
        people_asset_id=request.asset.people_asset_id,
        status="failed",
        root_source_provenance=request.root_source_provenance,
        candidate_failures=[
            AnchorCandidateFailureReceipt(
                stage="front",
                view_role="standard_front",
                candidate_index=1,
                failure_code="provider_timeout",
                output_id="output_front_1_timeout",
                candidate_id="candidate_front_1_timeout",
            ),
            AnchorCandidateFailureReceipt(
                stage="front",
                view_role="standard_front",
                candidate_index=2,
                failure_code="mcp_review_pending",
                mcp_handoff_id="mcp_handoff_standard_front_2",
                output_id="output_front_2_review_pending",
                candidate_id="candidate_front_2_review_pending",
            ),
        ],
    )

    generator = _McpHandoffGenerator(submitted={"mcp_handoff_standard_front_2"})
    resumed = AnchorPackPreparationService(
        generator=generator,
        reviewer=_PassReviewer(),
    ).prepare(request, resume_from_pack=prior_pack)

    assert [
        (item.view_role, item.candidate_index, item.failure_code, item.mcp_handoff_id)
        for item in resumed.pack.candidate_failures
    ] == [
        ("standard_front", 1, "provider_timeout", None),
        ("left_front_25", 1, "mcp_materialization_pending", "mcp_handoff_left_front_25_1"),
    ]
    assert [
        (item.view_role, item.candidate_index, item.mcp_handoff_id)
        for item in generator.requests
    ] == [
        ("standard_front", 2, "mcp_handoff_standard_front_2"),
        ("left_front_25", 1, None),
    ]
    assert [view.view_role for view in resumed.pack.anchor_views] == ["standard_front"]
    assert resumed.pack.anchor_views[0].output_id == "output_standard_front_2"
    assert resumed.mcp_handoff_ids == ["mcp_handoff_left_front_25_1"]


def test_doc187_mcp_face_resume_does_not_create_new_handoffs_after_three_review_failures() -> None:
    first = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(),
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request())
    second = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(
            submitted={
                "mcp_handoff_standard_front_1",
            }
        ),
        reviewer=_FailReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=first.pack)

    third = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(submitted={"mcp_handoff_standard_front_2"}),
        reviewer=_FailReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=second.pack)
    fourth_generator = _McpHandoffGenerator(submitted={"mcp_handoff_standard_front_3"})
    fourth = AnchorPackPreparationService(
        generator=fourth_generator,
        reviewer=_FailReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=third.pack)

    assert second.status == "blocked"
    assert second.mcp_handoff_ids == ["mcp_handoff_standard_front_2"]
    assert third.status == "blocked"
    assert third.mcp_handoff_ids == ["mcp_handoff_standard_front_3"]
    assert fourth.status == "blocked"
    assert fourth.mcp_handoff_ids == []
    assert [
        (request.view_role, request.candidate_index, request.mcp_handoff_id)
        for request in fourth_generator.requests
    ] == [
        ("standard_front", 3, "mcp_handoff_standard_front_3"),
    ]
    assert [item.failure_code for item in fourth.pack.candidate_failures] == [
        "shared_visual_review_failed",
        "shared_visual_review_failed",
        "shared_visual_review_failed",
    ]


def test_doc189_mcp_resume_does_not_reuse_front_handoffs_for_next_face_view() -> None:
    first = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(),
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request())

    generator = _McpHandoffGenerator(submitted={"mcp_handoff_standard_front_1"})
    resumed = AnchorPackPreparationService(
        generator=generator,
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=first.pack)

    assert resumed.status == "blocked"
    assert [view.view_role for view in resumed.pack.anchor_views] == ["standard_front"]
    assert [
        (request.view_role, request.candidate_index, request.mcp_handoff_id)
        for request in generator.requests
    ] == [
        ("standard_front", 1, "mcp_handoff_standard_front_1"),
        ("left_front_25", 1, None),
    ]
    assert resumed.mcp_handoff_ids == ["mcp_handoff_left_front_25_1"]
    assert all(
        item.view_role == "left_front_25"
        for item in resumed.generation_failures
        if item.mcp_handoff_id in resumed.mcp_handoff_ids
    )


def test_doc192_mcp_character_card_pauses_after_each_supplementary_slot_checkpoint() -> None:
    first = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(),
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request())
    second = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(submitted={"mcp_handoff_standard_front_1"}),
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=first.pack)
    assert second.mcp_handoff_ids == ["mcp_handoff_left_front_25_1"]

    generator = _McpHandoffGenerator(
        submitted={
            "mcp_handoff_standard_front_1",
            "mcp_handoff_left_front_25_1",
        }
    )
    third = AnchorPackPreparationService(
        generator=generator,
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=second.pack)

    assert third.status == "blocked"
    assert third.failure_codes == ["mcp_character_card_slot_checkpoint_ready"]
    assert third.mcp_handoff_ids == []
    assert [view.view_role for view in third.pack.anchor_views] == [
        "standard_front",
        "left_front_25",
    ]
    assert [
        (request.view_role, request.candidate_index, request.mcp_handoff_id)
        for request in generator.requests
    ] == [
        ("left_front_25", 1, "mcp_handoff_left_front_25_1"),
    ]


def test_doc183_face_anchor_mcp_pending_handoff_survives_status_projection_gap() -> None:
    class _Service:
        visual_asset_catalog = None

        def create_professional_anchor_preparation_job(self, *_args, **_kwargs):
            return ProductJobStatus(
                job_id="job_doc183_mcp_pending",
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, *_args, **_kwargs):
            return ProductJobStatus(
                job_id="job_doc183_mcp_pending",
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return SimpleNamespace(
                request=SimpleNamespace(
                    metadata={
                        "mcp_materialization": {
                            "handoff_id": "mcp_handoff_doc183_anchor",
                            "status": "pending",
                            "failure_code": "mcp_materialization_pending",
                        }
                    }
                ),
                generation_result=None,
            )

    request = AnchorGenerationRequest(
        project_id="project_doc183",
        people_asset_id="people_doc183",
        pack_version_id="pack_doc183",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="neutral identity evidence capture",
        root_source_asset_id="root_doc183",
        reference_evidence_ids=["root_doc183"],
        generation_channel="mcp",
        mcp_operation_id="people_doc183:standard_front:1",
    )

    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        ProductApiAnchorPackPreparationHost(_Service()).generate(request)

    assert exc_info.value.failure_code == "mcp_materialization_pending"
    assert exc_info.value.mcp_handoff_id == "mcp_handoff_doc183_anchor"


def test_doc183_face_anchor_mcp_resume_reuses_planned_handoff_job_before_brain() -> None:
    request = AnchorGenerationRequest(
        project_id="project_doc183",
        people_asset_id="people_doc183",
        pack_version_id="pack_doc183",
        view_role="rear_head",
        candidate_index=1,
        preparation_intent="neutral identity evidence capture",
        root_source_asset_id="root_doc183",
        reference_evidence_ids=["root_doc183", "front", "profile", "reverse"],
        generation_channel="mcp",
        mcp_operation_id="people_doc183:rear_head:1",
        mcp_handoff_id="mcp_handoff_doc183_rear",
        capture_scope="character_card_face_identity",
    )
    planned_record = SimpleNamespace(
        job_id="job_doc183_prior_planned",
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc183:rear_head:1",
                "professional_anchor_pack_preparation": True,
                "professional_reference_stage": "rear_head",
                "professional_anchor_capture_scope": "character_card_face_identity",
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc183_rear",
                    "status": "pending",
                    "failure_code": "mcp_materialization_pending",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):
            return [planned_record]

        def list_mcp_operation_records(self, _operation_id):
            return [planned_record]

    class _Service:
        visual_asset_catalog = None
        job_store = _Store()
        generated_job_ids = []

        def create_professional_anchor_preparation_job(self, *_args, **_kwargs):
            raise AssertionError("resume must not re-plan or call Brain")

        def generate_job(self, job_id, *_args, **_kwargs):
            self.generated_job_ids.append(job_id)
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return planned_record

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        ProductApiAnchorPackPreparationHost(service).generate(request)

    assert service.generated_job_ids == ["job_doc183_prior_planned"]
    assert exc_info.value.failure_code == "mcp_materialization_pending"
    assert exc_info.value.mcp_handoff_id == "mcp_handoff_doc183_rear"


def test_doc190_face_anchor_mcp_resume_rejects_stale_reverse45_prompt_contract(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    operation_id = "people_doc190:reverse_three_quarter:3"
    old_handoff = store.ensure_pending(
        operation_id=operation_id,
        prompt=(
            "Reverse three-quarter portrait leaning into a rear/back view, "
            "back of head dominant, same vertical crop boundaries."
        ),
        prompt_sha256="b" * 64,
        reference_assets=[],
        rendering_contract={
            "size": "1024x1536",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    request = AnchorGenerationRequest(
        project_id="project_doc190",
        people_asset_id="people_doc190",
        pack_version_id="pack_doc190",
        view_role="reverse_three_quarter",
        candidate_index=3,
        preparation_intent="neutral identity evidence capture",
        root_source_asset_id="root_doc190",
        reference_evidence_ids=["root_doc190", "front", "right25", "profile"],
        generation_channel="mcp",
        mcp_operation_id=operation_id,
        mcp_handoff_id=str(old_handoff["handoff_id"]),
        capture_scope="character_card_face_identity",
    )
    planned_record = SimpleNamespace(
        job_id="job_doc190_stale",
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "professional_anchor_pack_preparation": True,
                "professional_reference_stage": "reverse_three_quarter",
                "professional_anchor_capture_scope": "character_card_face_identity",
                "mcp_materialization": {
                    "handoff_id": old_handoff["handoff_id"],
                    "status": "pending",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):
            return [planned_record]

        def list_mcp_operation_records(self, _operation_id):
            return [planned_record]

    class _Service:
        visual_asset_catalog = None
        job_store = _Store()
        mcp_materialization_store = store

        def __init__(self) -> None:
            self.created_payloads = []

        def create_professional_anchor_preparation_job(self, payload, **_kwargs):
            self.created_payloads.append(payload)
            return ProductJobStatus(
                job_id="job_doc190_new",
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):
            assert job_id == "job_doc190_new"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return None

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        ProductApiAnchorPackPreparationHost(service).generate(request)

    assert exc_info.value.failure_code == "professional_anchor_candidate_generation_failed"
    assert service.created_payloads
    assert "mcp_materialization" not in service.created_payloads[0]["metadata"]


def test_doc183_face_anchor_mcp_resume_reuses_existing_generation_result_without_reconsuming() -> None:
    request = AnchorGenerationRequest(
        project_id="project_doc183",
        people_asset_id="people_doc183",
        pack_version_id="pack_doc183",
        view_role="three_quarter",
        candidate_index=1,
        preparation_intent="neutral identity evidence capture",
        root_source_asset_id="root_doc183",
        reference_evidence_ids=["root_doc183", "front_winner", "left25_winner"],
        generation_channel="mcp",
        mcp_operation_id="people_doc183:three_quarter:1",
        mcp_handoff_id="mcp_handoff_doc183_three_quarter",
        capture_scope="character_card_face_identity",
    )
    planned_record = SimpleNamespace(
        job_id="job_doc183_existing_generation",
        planning_result=object(),
        generation_result=SimpleNamespace(metadata={}),
        request=SimpleNamespace(
            metadata={
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc183:three_quarter:1",
                "professional_anchor_pack_preparation": True,
                "professional_reference_stage": "three_quarter",
                "professional_anchor_capture_scope": "character_card_face_identity",
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc183_three_quarter",
                    "status": "consumed",
                    "failure_code": "mcp_materialization_pending",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):
            return [planned_record]

        def list_mcp_operation_records(self, _operation_id):
            return [planned_record]

    class _Service:
        visual_asset_catalog = None
        job_store = _Store()

        def create_professional_anchor_preparation_job(self, *_args, **_kwargs):
            raise AssertionError("resume must not re-plan or call Brain")

        def generate_job(self, *_args, **_kwargs):
            raise AssertionError("submitted MCP artifacts must not be consumed twice")

        def get_job_record(self, _job_id):
            return planned_record

    class _Host(ProductApiAnchorPackPreparationHost):
        def _candidate_and_review(self, job_id, generation_request):
            assert job_id == "job_doc183_existing_generation"
            assert generation_request.mcp_handoff_id == "mcp_handoff_doc183_three_quarter"
            return (
                AnchorCandidateResult(
                    candidate_id="candidate_doc183_existing",
                    view_id="view_doc183_existing",
                    output_id="output_doc183_existing",
                    view_role="three_quarter",
                    candidate_index=1,
                    source_candidate_ids=["candidate_doc183_existing"],
                    source_asset_ids=["root_doc183", "front_winner"],
                    brain_plan_id="brain_doc183_existing",
                    canonical_prompt_hash="a" * 64,
                    prompt_compilation_id="compilation_doc183_existing",
                    prompt_reference_parity_verified=True,
                ),
                AnchorReviewDecision(
                    status="pass",
                    identity_scores=IdentityScoreSummary(
                        same_face_score=0.95,
                        visual_quality_score=0.95,
                        distinctive_feature_score=0.9,
                        human_realism_score=0.94,
                        pose_compliance_score=0.92,
                        ai_overperfection_penalty=0.0,
                    ),
                ),
            )

    candidate = _Host(_Service()).generate(request)

    assert candidate.output_id == "output_doc183_existing"


def test_doc193_face_anchor_mcp_resume_recovers_consumed_generated_record_without_handoff_metadata() -> None:
    request = AnchorGenerationRequest(
        project_id="project_doc193",
        people_asset_id="people_doc193",
        pack_version_id="pack_doc193",
        view_role="profile",
        candidate_index=1,
        preparation_intent="neutral identity evidence capture",
        root_source_asset_id="root_doc193",
        reference_evidence_ids=["root_doc193", "front_winner", "left45_winner"],
        generation_channel="mcp",
        mcp_operation_id="people_doc193:profile:1",
        mcp_handoff_id="mcp_handoff_doc193_profile",
        capture_scope="character_card_face_identity",
    )
    generated_record = SimpleNamespace(
        job_id="job_doc193_generated_without_handoff_metadata",
        planning_result=object(),
        generation_result=SimpleNamespace(metadata={}),
        request=SimpleNamespace(
            metadata={
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc193:profile:1",
                "professional_anchor_pack_preparation": True,
                "professional_reference_stage": "profile",
                "professional_anchor_capture_scope": "character_card_face_identity",
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):
            return [generated_record]

        def list_mcp_operation_records(self, _operation_id):
            return [generated_record]

    class _McpStore:
        def get(self, handoff_id):
            assert handoff_id == "mcp_handoff_doc193_profile"
            return {
                "handoff_id": "mcp_handoff_doc193_profile",
                "status": "consumed",
                "canonical_prompt": (
                    "same camera distance same head size head-neck-upper-shoulders "
                    "approved front card framing upper-shoulders cutoff"
                ),
            }

    class _Service:
        visual_asset_catalog = None
        job_store = _Store()
        mcp_materialization_store = _McpStore()

        def create_professional_anchor_preparation_job(self, *_args, **_kwargs):
            raise AssertionError("resume must reuse the generated MCP job")

        def generate_job(self, *_args, **_kwargs):
            raise AssertionError("consumed MCP artifacts must not be regenerated")

        def get_job_record(self, _job_id):
            return generated_record

    class _Host(ProductApiAnchorPackPreparationHost):
        def _candidate_and_review(self, job_id, generation_request):
            assert job_id == "job_doc193_generated_without_handoff_metadata"
            assert generation_request.mcp_handoff_id == "mcp_handoff_doc193_profile"
            return (
                AnchorCandidateResult(
                    candidate_id="candidate_doc193_existing",
                    view_id="view_doc193_existing",
                    output_id="output_doc193_existing",
                    view_role="profile",
                    candidate_index=1,
                    source_candidate_ids=["candidate_doc193_existing"],
                    source_asset_ids=["root_doc193", "front_winner", "left45_winner"],
                    brain_plan_id="brain_doc193_existing",
                    canonical_prompt_hash="b" * 64,
                    prompt_compilation_id="compilation_doc193_existing",
                    prompt_reference_parity_verified=True,
                ),
                AnchorReviewDecision(
                    status="pass",
                    identity_scores=IdentityScoreSummary(
                        same_face_score=0.82,
                        visual_quality_score=0.93,
                        distinctive_feature_score=0.84,
                        human_realism_score=0.90,
                        pose_compliance_score=0.96,
                        ai_overperfection_penalty=0.16,
                    ),
                ),
            )

    candidate = _Host(_Service()).generate(request)

    assert candidate.output_id == "output_doc193_existing"


def test_doc193_character_card_prompt_current_accepts_equivalent_card_scale_terms() -> None:
    prompt = (
        "Strict 90-degree side profile portrait. Match the approved front card "
        "modeling scale: same camera distance, same head size, vertical 2:3 "
        "head-neck-upper-shoulders crop with upper-shoulders cutoff."
    )

    assert _character_card_face_identity_mcp_prompt_current("profile", prompt)


def test_doc193_character_card_prompt_current_accepts_equivalent_25_degree_terms() -> None:
    prompt = (
        "Right-front shallow three-quarter transition portrait, a natural "
        "right-front transition target around 25 to 30 degrees toward "
        "image-left, visually shallower than the final 45-degree card. "
        "The right/opposite ear begins to show and this is not a horizontal "
        "flip. Match the approved front card framing and scale: same camera "
        "distance and head size, vertical 2:3 head-neck-upper-shoulders crop "
        "with upper-shoulders cutoff."
    )

    assert _character_card_face_identity_mcp_prompt_current("right_front_25", prompt)


def test_doc190_mcp_resume_reenters_finalizing_review_for_submitted_artifact() -> None:
    request = AnchorGenerationRequest(
        project_id="project_doc190",
        people_asset_id="people_doc190",
        pack_version_id="pack_doc190",
        view_role="reverse_three_quarter",
        candidate_index=1,
        preparation_intent="neutral identity evidence capture",
        root_source_asset_id="root_doc190",
        reference_evidence_ids=["root_doc190", "front_winner", "right25_winner", "profile_winner"],
        generation_channel="mcp",
        mcp_operation_id="people_doc190:reverse_three_quarter:1",
        mcp_handoff_id="mcp_handoff_doc190_reverse",
        capture_scope="character_card_face_identity",
    )
    planned_record = SimpleNamespace(
        job_id="job_doc190_finalizing_resume",
        planning_result=object(),
        generation_result=SimpleNamespace(metadata={}),
        request=SimpleNamespace(
            metadata={
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc190:reverse_three_quarter:1",
                "professional_anchor_pack_preparation": True,
                "professional_reference_stage": "reverse_three_quarter",
                "professional_anchor_capture_scope": "character_card_face_identity",
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc190_reverse",
                    "status": "consumed",
                    "failure_code": "mcp_materialization_pending",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):
            return [planned_record]

        def list_mcp_operation_records(self, _operation_id):
            return [planned_record]

    class _Service:
        visual_asset_catalog = None
        job_store = _Store()

        def __init__(self) -> None:
            self.generate_requests = []

        def create_professional_anchor_preparation_job(self, *_args, **_kwargs):
            raise AssertionError("resume must not re-plan or call Brain")

        def generate_job(self, job_id, request_payload):
            self.generate_requests.append((job_id, request_payload))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.GENERATED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return planned_record

    class _Host(ProductApiAnchorPackPreparationHost):
        def __init__(self, service):
            super().__init__(service)
            self.review_attempts = 0

        def _candidate_and_review(self, job_id, generation_request):
            self.review_attempts += 1
            if self.review_attempts == 1:
                raise RuntimeError("professional_anchor_real_pixel_review_missing")
            assert job_id == "job_doc190_finalizing_resume"
            assert generation_request.mcp_handoff_id == "mcp_handoff_doc190_reverse"
            return (
                AnchorCandidateResult(
                    candidate_id="candidate_doc190_reverse",
                    view_id="view_doc190_reverse",
                    output_id="output_doc190_reverse",
                    view_role="reverse_three_quarter",
                    candidate_index=1,
                    source_candidate_ids=["candidate_doc190_reverse"],
                    source_asset_ids=["root_doc190", "front_winner", "profile_winner", "right25_winner"],
                    brain_plan_id="brain_doc190_reverse",
                    canonical_prompt_hash="b" * 64,
                    prompt_compilation_id="compilation_doc190_reverse",
                    prompt_reference_parity_verified=True,
                ),
                AnchorReviewDecision(
                    status="pass",
                    identity_scores=IdentityScoreSummary(
                        same_face_score=0.95,
                        visual_quality_score=0.95,
                        distinctive_feature_score=0.9,
                        human_realism_score=0.94,
                        pose_compliance_score=0.92,
                        ai_overperfection_penalty=0.0,
                    ),
                ),
            )

    service = _Service()
    candidate = _Host(service).generate(request)

    assert candidate.output_id == "output_doc190_reverse"
    assert service.generate_requests == [
        (
            "job_doc190_finalizing_resume",
            {
                "quality_mode": "strict",
                "metadata": {
                    "max_visual_retry_attempts": 1,
                    "_v3_resume_finalizing_review": True,
                },
            },
        )
    ]


def test_doc183_mcp_resume_uses_existing_frozen_handoff_prompt(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    old_prompt = "frozen rear-head renderer prompt"
    old_hash = hashlib.sha256(old_prompt.encode("utf-8")).hexdigest()
    references = [{"asset_id": "ref_1", "sha256": "a" * 64, "role": "portrait_identity"}]
    contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
    }
    handoff = store.ensure_pending(
        operation_id="people_doc183:rear_head:1",
        prompt=old_prompt,
        prompt_sha256=old_hash,
        reference_assets=references,
        rendering_contract=contract,
    )
    provider = McpMaterializationProvider(handoff_store=store)

    context = provider._existing_mcp_handoff_context(
        SimpleNamespace(
            metadata={
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc183:rear_head:1",
                "mcp_materialization": {
                    "handoff_id": handoff["handoff_id"],
                    "status": "pending",
                },
            }
        ),
        current_context={
            "operation_id": "people_doc183:rear_head:1",
            "canonical_prompt": "new brain prompt that must not replace the frozen handoff",
            "prompt_sha256": hashlib.sha256(b"new").hexdigest(),
        },
        current_reference_assets=references,
        current_rendering_contract=contract,
    )

    assert context is not None
    assert context["canonical_prompt"] == old_prompt
    assert context["prompt_sha256"] == old_hash
    assert context["handoff_id"] == handoff["handoff_id"]


def _png_bytes(size: tuple[int, int], color: tuple[int, int, int] = (240, 240, 240)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_doc188_mcp_submit_normalizes_artifact_to_frozen_rendering_size(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "frozen face identity prompt"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    references = [{"asset_id": "ref_doc188", "sha256": "a" * 64, "role": "portrait_identity"}]
    handoff = store.ensure_pending(
        operation_id="people_doc188:standard_front:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "1024x1536",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
            "size_normalization": "white_matte_contain_to_contract_size",
        },
    )

    public = store.submit(
        handoff["handoff_id"],
        nonce=handoff["nonce"],
        prompt_sha256=prompt_hash,
        reference_asset_hashes=["a" * 64],
        artifact_bytes=_png_bytes((1254, 1254)),
    )
    record = store.get(handoff["handoff_id"])

    assert public["status"] == "submitted"
    assert record is not None
    assert record["artifact_width"] == 1024
    assert record["artifact_height"] == 1536
    assert record["artifact_size_normalization"]["original_width"] == 1254
    assert record["artifact_size_normalization"]["original_height"] == 1254
    with Image.open(record["artifact_file"]) as image:
        assert image.size == (1024, 1536)


def test_doc192_mcp_consumed_handoff_replan_creates_new_revision(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "frozen left-front 25 character-card prompt"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    references = [{"asset_id": "ref_doc192", "sha256": "b" * 64, "role": "portrait_identity"}]
    contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
        "size_normalization": "white_matte_contain_to_contract_size",
    }
    first = store.ensure_pending(
        operation_id="people_doc192:left_front_25:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract=contract,
    )
    same_pending = store.ensure_pending(
        operation_id="people_doc192:left_front_25:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract=contract,
    )
    store.submit(
        first["handoff_id"],
        nonce=first["nonce"],
        prompt_sha256=prompt_hash,
        reference_asset_hashes=["b" * 64],
        artifact_bytes=_png_bytes((1024, 1536)),
    )
    store.consume(first["handoff_id"])
    consumed_record = store.get(first["handoff_id"])
    second = store.ensure_pending(
        operation_id="people_doc192:left_front_25:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract=contract,
    )

    assert same_pending["handoff_id"] == first["handoff_id"]
    assert consumed_record is not None
    assert consumed_record["status"] == "consumed_uncheckpointed"
    assert second["handoff_id"] == first["handoff_id"]
    assert second["status"] == "consumed_uncheckpointed"
    assert second["operation_id"] == first["operation_id"]
    assert second["revision"] == 1


def test_doc188_mcp_submit_rejects_size_mismatch_without_policy(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "frozen face identity prompt"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    references = [{"asset_id": "ref_doc188", "sha256": "a" * 64, "role": "portrait_identity"}]
    handoff = store.ensure_pending(
        operation_id="people_doc188:standard_front:2",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "1024x1536",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )

    with pytest.raises(McpMaterializationError, match="mcp_materialization_output_size_mismatch"):
        store.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=prompt_hash,
            reference_asset_hashes=["a" * 64],
            artifact_bytes=_png_bytes((1254, 1254)),
        )


def test_doc190_mcp_handoff_id_changes_when_reference_contract_changes(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "frozen right 45 character-card prompt"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    rendering_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
    }
    first = store.ensure_pending(
        operation_id="people_doc190:reverse_three_quarter:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[
            {"asset_id": "left45::portrait_identity_crop", "sha256": "a" * 64, "role": "portrait_identity"},
            {
                "asset_id": "left45::portrait_identity_pose_geometry_crop",
                "sha256": "b" * 64,
                "role": "portrait_identity",
            },
        ],
        rendering_contract=rendering_contract,
    )
    same = store.ensure_pending(
        operation_id="people_doc190:reverse_three_quarter:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[
            {"asset_id": "left45::portrait_identity_crop", "sha256": "a" * 64, "role": "portrait_identity"},
            {
                "asset_id": "left45::portrait_identity_pose_geometry_crop",
                "sha256": "b" * 64,
                "role": "portrait_identity",
            },
        ],
        rendering_contract=rendering_contract,
    )
    changed = store.ensure_pending(
        operation_id="people_doc190:reverse_three_quarter:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[
            {"asset_id": "left45::portrait_identity_crop", "sha256": "a" * 64, "role": "portrait_identity"},
            {
                "asset_id": "left45::character_card_full_frame_framing_reference",
                "sha256": "c" * 64,
                "role": "portrait_identity",
            },
        ],
        rendering_contract=rendering_contract,
    )

    assert same["handoff_id"] == first["handoff_id"]
    assert changed["handoff_id"] != first["handoff_id"]
    assert changed["reference_asset_hashes"] == ["a" * 64, "c" * 64]


def test_doc182_resume_route_is_explicit_and_non_boolean_flag_is_rejected() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Doc182 route asset",
            root_source_asset_id="root_doc182_route",
            consent_reference="consent_doc182_route",
            preparation_intent="neutral identity evidence capture",
        ),
    )
    captured = {}

    class _Lifecycle:
        def prepare_character_card_face(self, **kwargs):
            captured.update(kwargs)
            return asset

    handlers = V3ProductRouteHandlers(service=V3ProductApiService(), visual_asset_library_catalog=catalog)
    handlers.visual_asset_library_service = _Lifecycle()
    handlers.post_visual_asset_character_card_prepare(
        asset.visual_asset_id,
        {"stage": "face_identity", "resume": True},
    )
    assert captured["resume"] is True
    with pytest.raises(ValueError, match="resume_flag_invalid"):
        handlers.post_visual_asset_character_card_prepare(
            asset.visual_asset_id,
            {"stage": "face_identity", "resume": "true"},
        )


def test_doc182_public_projection_contains_checkpoint_without_internal_details() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Doc182 public asset",
            root_source_asset_id="root_doc182_public",
            consent_reference="consent_doc182_public",
            preparation_intent="neutral identity evidence capture",
        ),
    )
    card = asset.character_card.model_copy(
        update={
            "face_identity_status": "blocked",
            "last_failed_module": "face_identity",
            "last_failed_slot_key": "face.front",
            "last_failure_code": "character_card_face_prepare_paused",
            "last_failure_attempt_count": 3,
            "resume_available": True,
        }
    )
    public = V3ProductRouteHandlers._visual_asset_public_record(asset.model_copy(update={"character_card": card}))
    projected = public["character_card"]
    assert projected["resume_available"] is True
    assert projected["last_failure_attempt_count"] == 3
    assert "prompt" not in str(projected).lower()
    assert "provider" not in str(projected).lower()


def test_doc193_face_prepare_projects_current_mcp_checkpoint_to_character_card() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Doc193 face checkpoint asset",
            root_source_asset_id="root_doc193_face_checkpoint",
            consent_reference="consent_doc193_face_checkpoint",
            preparation_intent="neutral identity evidence capture",
        ),
    )

    class _Host:
        def prepare_character_card(self, **kwargs):
            root = kwargs["root_source_provenance"]
            pack = IdentityAnchorPackVersion(
                pack_version_id="pack_doc193_face_checkpoint",
                people_asset_id=asset.visual_asset_id,
                status="failed",
                root_source_provenance=root,
                anchor_views=[
                    _face_anchor_view("standard_front", "front_winner"),
                    _face_anchor_view("left_front_25", "left25_winner"),
                    _face_anchor_view("three_quarter", "left45_winner"),
                    _face_anchor_view("profile", "profile_winner"),
                    _face_anchor_view("right_front_25", "right25_winner"),
                ],
                candidate_failures=[
                    AnchorCandidateFailure(
                        stage="supplementary",
                        view_role="reverse_three_quarter",
                        candidate_index=1,
                        failure_code="professional_pose_noncompliance",
                        output_id="v3_output_reverse45_too_shallow",
                        candidate_id="candidate_reverse45_too_shallow",
                    ),
                    AnchorCandidateFailure(
                        stage="supplementary",
                        view_role="reverse_three_quarter",
                        candidate_index=2,
                        failure_code="mcp_materialization_pending",
                        mcp_handoff_id="mcp_handoff_reverse45_next",
                    ),
                ],
            )
            return AnchorPackPreparationResult(
                status="blocked",
                pack=pack,
                generation_failures=list(pack.candidate_failures),
                failure_codes=["mcp_materialization_pending"],
                mcp_handoff_ids=["mcp_handoff_reverse45_next"],
            )

    lifecycle = VisualAssetLibraryLifecycleService(catalog, anchor_pack_host=_Host())
    updated = lifecycle.prepare_character_card_face(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        generation_channel="mcp",
    )
    card = updated.character_card

    assert card.face_identity_status == "partial"
    assert card.last_failed_slot_key == "face.reverse_three_quarter"
    assert card.last_failure_code == "mcp_materialization_pending"
    assert card.pending_mcp_handoff_ids == ["mcp_handoff_reverse45_next"]
    assert updated.versions[-1].failure_code == "mcp_materialization_pending"
    assert updated.versions[-1].mcp_handoff_ids == ["mcp_handoff_reverse45_next"]


def test_doc192_public_projection_keeps_failed_candidate_history_for_all_history_panel() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Doc192 history asset",
            root_source_asset_id="root_doc192_history",
            consent_reference="consent_doc192_history",
            preparation_intent="neutral identity evidence capture",
        ),
    )
    pack = IdentityAnchorPackVersion(
        pack_version_id="pack_doc192_history",
        people_asset_id="person_doc192_history",
        status="failed",
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="root_doc192_history",
            project_id="project_doc192_history",
            consent_reference="authorized",
        ),
        anchor_views=[_face_anchor_view("standard_front", "front_winner")],
        candidate_failures=[
            AnchorCandidateFailureReceipt(
                stage="supplementary",
                view_role="left_front_25",
                candidate_index=1,
                failure_code="shared_visual_review_failed",
                output_id="v3_output_failed_left25",
                candidate_id="candidate_failed_left25",
            ),
            AnchorCandidateFailureReceipt(
                stage="supplementary",
                view_role="left_front_25",
                candidate_index=2,
                failure_code="mcp_materialization_pending",
                mcp_handoff_id="mcp_handoff_next_left25",
            ),
        ],
    )
    prior_pack = IdentityAnchorPackVersion(
        pack_version_id="pack_doc192_history_prior",
        people_asset_id="person_doc192_history",
        status="failed",
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="root_doc192_history",
            project_id="project_doc192_history",
            consent_reference="authorized",
        ),
        anchor_views=[_face_anchor_view("standard_front", "front_winner")],
        candidate_failures=[
            AnchorCandidateFailureReceipt(
                stage="supplementary",
                view_role="left_front_25",
                candidate_index=1,
                failure_code="professional_face_card_25_angle_too_shallow",
                output_id="v3_output_prior_left25",
                candidate_id="candidate_prior_left25",
            )
        ],
    )
    prior_version = VisualAssetVersion(
        version_id="version_doc192_history_prior",
        visual_asset_id=asset.visual_asset_id,
        lifecycle_status="failed",
        immutable_source_provenance=asset.root_source_provenance,
        anchor_pack=prior_pack,
        failure_code="professional_face_card_25_angle_too_shallow",
        failure_attempt_count=1,
        generation_channel="mcp",
    )
    version = VisualAssetVersion(
        version_id="version_doc192_history",
        visual_asset_id=asset.visual_asset_id,
        lifecycle_status="failed",
        immutable_source_provenance=asset.root_source_provenance,
        anchor_pack=pack,
        failure_code="shared_visual_review_failed",
        failure_attempt_count=2,
        generation_channel="mcp",
        mcp_handoff_ids=["mcp_handoff_next_left25"],
    )

    public = V3ProductRouteHandlers._visual_asset_public_record(
        asset.model_copy(update={"versions": [prior_version, version]})
    )

    latest = public["latest_preparation"]
    history = latest["candidate_history"]
    all_history = public["preparation_history"]
    assert [item["version_id"] for item in all_history] == [
        "version_doc192_history_prior",
        "version_doc192_history",
    ]
    assert all_history[0]["candidate_history"][0]["output_id"] == "v3_output_prior_left25"
    assert all_history[1]["candidate_history"] == history
    assert latest["failure_attempt_count"] == 2
    assert latest["mcp_handoff_ids"] == ["mcp_handoff_next_left25"]
    assert history[0] == {
        "stage": "supplementary",
        "view_role": "left_front_25",
        "candidate_index": 1,
        "failure_code": "shared_visual_review_failed",
        "output_id": "v3_output_failed_left25",
        "preview_url": "/api/v3/creative-agent/outputs/v3_output_failed_left25/preview",
        "download_url": "/api/v3/creative-agent/outputs/v3_output_failed_left25/download",
        "candidate_id": "candidate_failed_left25",
    }
    assert history[1] == {
        "stage": "supplementary",
        "view_role": "left_front_25",
        "candidate_index": 2,
        "failure_code": "mcp_materialization_pending",
        "mcp_handoff_id": "mcp_handoff_next_left25",
    }
    slots = public["character_card"]["slots"]
    assert slots["face.front"]["available"] is False
    assert "v3_output_failed_left25" not in str(slots)
    public_text = str(public).lower()
    assert "prompt" not in public_text
    assert "provider" not in public_text
    assert ".png" not in public_text


def test_doc190_face_pack_projection_clears_stale_downstream_slots() -> None:
    empty = CharacterCardState.initial(card_version_id="card_doc190_empty")
    card = CharacterCardState.initial(card_version_id="card_doc190_stale").model_copy(
        update={
            "face_slots": {
                **empty.face_slots,
                "face.front": empty.face_slots["face.front"].model_copy(
                    update={"state": "winner_selected", "output_id": "old_front"}
                ),
                "face.profile": empty.face_slots["face.profile"].model_copy(
                    update={"state": "winner_selected", "output_id": "stale_profile"}
                ),
            }
        }
    )
    pack = IdentityAnchorPackVersion(
        pack_version_id="pack_doc190_partial",
        people_asset_id="person_doc190",
        status="failed",
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="root_doc190",
            project_id="project_doc190",
            consent_reference="authorized",
        ),
        anchor_views=[
            _face_anchor_view("standard_front", "new_front"),
            _face_anchor_view("left_front_25", "new_left25"),
            _face_anchor_view("three_quarter", "new_left45"),
        ],
    )

    projected = apply_face_identity_pack_to_card(card, pack)

    assert projected.face_slots["face.front"].output_id == "new_front"
    assert projected.face_slots["face.left_front_25"].output_id == "new_left25"
    assert projected.face_slots["face.front_three_quarter"].output_id == "new_left45"
    assert projected.face_slots["face.profile"].state == "empty"
    assert projected.face_slots["face.profile"].output_id is None
    assert projected.last_failed_slot_key == "face.profile"


def test_doc182_host_attaches_shared_failure_receipt() -> None:
    host = ProductApiAnchorPackPreparationHost(V3ProductApiService())
    card = _face_card()
    result = CharacterCardStageResult(
        status="blocked",
        card=card.model_copy(
            update={
                "expression_set_status": "blocked",
                "last_failed_module": "expression_set",
                "last_failed_slot_key": "expression.laugh",
                "last_failure_code": "character_card_candidate_provider_failed",
                "last_failure_attempt_count": 3,
                "resume_available": True,
            }
        ),
        failure_codes=["character_card_candidate_provider_failed"],
    )
    attached = host._attach_character_card_receipt(result, asset=SimpleNamespace(visual_asset_id="asset_doc182"), stage="expression_set")
    assert attached.shared_runtime_failure is not None
    assert attached.shared_runtime_failure.failure_count == 3


def test_doc182_frontend_exposes_explicit_resume_action() -> None:
    source = (
        Path(__file__).parents[2] / "src_skeleton" / "app" / "static" / "app.js"
    ).read_text(encoding="utf-8")
    assert 'status === "partial"' in source
    assert 'payload.resume = true' in source
    assert "const resumeFace = Boolean" in source
    assert "...(resumeFace ? { resume: true } : {})" in source
    assert "从断点继续" in source
