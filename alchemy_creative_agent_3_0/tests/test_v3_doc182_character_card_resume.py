"""Doc182 bounded failure pause and explicit resume contracts."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import hashlib

import pytest

from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import McpMaterializationHandoffStore
from alchemy_creative_agent_3_0.app.generation_router.providers import McpMaterializationProvider
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import ProductApiAnchorPackPreparationHost
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatus, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateResult,
    AnchorCandidateUnavailable,
    AnchorGenerationRequest,
    AnchorPackPreparationRequest,
    AnchorPackPreparationService,
    AnchorReviewDecision,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeFailureReceipt,
    CharacterCardStageResult,
    CharacterCardState,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    FaceIdentityModule,
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    VisualAssetLibraryCatalog,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest


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


def test_doc182_three_failures_pause_without_unhandled_exception() -> None:
    service = CharacterCardPreparationService(
        generator=_ExpressionGenerator(failing_slots={"expression.smile"}),
        reviewer=_PassReviewer(),
    )
    result = service.prepare_expression_set(
        _face_card(),
        front_output_id="front_winner",
        user_intents={"smile": "natural smile", "anger": "quietly serious", "sad": "subtle sadness"},
    )

    assert result.status == "blocked"
    assert result.card.expression_set_status == "blocked"
    assert result.card.resume_available is True
    assert result.card.last_failed_slot_key == "expression.smile"
    assert result.card.last_failure_attempt_count == 3
    assert len(result.failures) == 3
    assert result.card.expression_slots["expression.smile"].state == "empty"

    receipt = CharacterCardSharedRuntimeFailureReceipt(failure_count=len(result.failures))
    assert receipt.resume_available is True
    assert receipt.review_owner == "v3_shared_vision"


def test_doc183_character_card_failure_exposes_only_resumable_mcp_handoff() -> None:
    service = CharacterCardPreparationService(
        generator=_ExpressionGenerator(
            failing_slots={"expression.smile"},
            handoff_ids={"expression.smile": "mcp_handoff_expression_smile"},
        ),
        reviewer=_PassReviewer(),
    )
    result = service.prepare_expression_set(
        _face_card(),
        front_output_id="front_winner",
        user_intents={"smile": "natural smile", "anger": "quietly serious", "sad": "subtle sadness"},
        generation_channel="mcp",
    )

    assert result.status == "blocked"
    assert result.mcp_handoff_ids == ["mcp_handoff_expression_smile"]
    assert result.card.pending_mcp_handoff_ids == ["mcp_handoff_expression_smile"]
    assert result.failures[0].mcp_handoff_id == "mcp_handoff_expression_smile"
    public_card = result.card.model_dump_json()
    assert "provider_id" not in public_card
    assert "canonical_prompt" not in public_card
    assert "file_path" not in public_card


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
        user_intents={"smile": "natural smile", "anger": "quietly serious", "sad": "subtle sadness"},
    )
    assert first.status == "blocked"
    assert first.card.expression_slots["expression.smile"].output_id
    assert [request.slot_key for request in first_generator.requests] == [
        "expression.smile",
        "expression.smile",
        "expression.smile",
        "expression.anger",
        "expression.anger",
        "expression.anger",
    ]

    second_generator = _ExpressionGenerator()
    resumed = CharacterCardPreparationService(generator=second_generator, reviewer=_PassReviewer()).prepare_expression_set(
        first.card,
        front_output_id="front_winner",
        user_intents={"smile": "natural smile", "anger": "quietly serious", "sad": "subtle sadness"},
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
    assert resumed.card.expression_slots["expression.smile"].output_id == first.card.expression_slots["expression.smile"].output_id


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
    assert [view.view_role for view in first.pack.anchor_views] == ["standard_front", "three_quarter"]
    assert len(first.generation_failures) == 3

    second_generator = _AnchorGenerator()
    second_service = AnchorPackPreparationService(generator=second_generator, reviewer=_PassReviewer())
    resumed = second_service.prepare(_anchor_request(), resume_from_pack=first.pack)
    assert resumed.status == "review"
    assert resumed.pack.pack_version_id != first.pack.pack_version_id
    assert [request.view_role for request in second_generator.requests[:3]] == ["profile"] * 3
    assert all(request.view_role not in {"standard_front", "three_quarter"} for request in second_generator.requests)
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
    assert first.mcp_handoff_ids == [
        "mcp_handoff_standard_front_1",
        "mcp_handoff_standard_front_2",
        "mcp_handoff_standard_front_3",
    ]
    assert [
        (item.view_role, item.candidate_index, item.failure_code, item.mcp_handoff_id)
        for item in first.pack.candidate_failures
    ] == [
        ("standard_front", 1, "mcp_materialization_pending", "mcp_handoff_standard_front_1"),
        ("standard_front", 2, "mcp_materialization_pending", "mcp_handoff_standard_front_2"),
        ("standard_front", 3, "mcp_materialization_pending", "mcp_handoff_standard_front_3"),
    ]

    second_generator = _McpHandoffGenerator(submitted={"mcp_handoff_standard_front_2"})
    second_service = AnchorPackPreparationService(generator=second_generator, reviewer=_FailReviewer())
    resumed = second_service.prepare(_mcp_anchor_request(), resume_from_pack=first.pack)

    assert resumed.status == "blocked"
    assert [
        (request.view_role, request.candidate_index, request.mcp_handoff_id)
        for request in second_generator.requests
    ] == [
        ("standard_front", 1, "mcp_handoff_standard_front_1"),
        ("standard_front", 2, "mcp_handoff_standard_front_2"),
        ("standard_front", 3, "mcp_handoff_standard_front_3"),
    ]
    assert resumed.mcp_handoff_ids == [
        "mcp_handoff_standard_front_1",
        "mcp_handoff_standard_front_3",
    ]
    assert [
        (item.view_role, item.candidate_index, item.failure_code, item.mcp_handoff_id)
        for item in resumed.pack.candidate_failures
    ] == [
        ("standard_front", 1, "mcp_materialization_pending", "mcp_handoff_standard_front_1"),
        ("standard_front", 2, "shared_visual_review_failed", None),
        ("standard_front", 3, "mcp_materialization_pending", "mcp_handoff_standard_front_3"),
    ]


def test_doc187_mcp_face_resume_does_not_create_new_handoffs_after_three_review_failures() -> None:
    first = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(),
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request())
    second = AnchorPackPreparationService(
        generator=_McpHandoffGenerator(
            submitted={
                "mcp_handoff_standard_front_1",
                "mcp_handoff_standard_front_2",
                "mcp_handoff_standard_front_3",
            }
        ),
        reviewer=_FailReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=first.pack)

    third_generator = _McpHandoffGenerator()
    third = AnchorPackPreparationService(
        generator=third_generator,
        reviewer=_PassReviewer(),
    ).prepare(_mcp_anchor_request(), resume_from_pack=second.pack)

    assert second.status == "blocked"
    assert second.mcp_handoff_ids == []
    assert third.status == "blocked"
    assert third.mcp_handoff_ids == []
    assert third_generator.requests == []
    assert [item.failure_code for item in third.pack.candidate_failures] == [
        "shared_visual_review_failed",
        "shared_visual_review_failed",
        "shared_visual_review_failed",
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
        reference_evidence_ids=["root_doc183", "front", "three_quarter", "profile", "reverse"],
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


def test_doc182_host_attaches_shared_failure_receipt() -> None:
    host = ProductApiAnchorPackPreparationHost(V3ProductApiService())
    card = _face_card()
    result = CharacterCardStageResult(
        status="blocked",
        card=card.model_copy(
            update={
                "expression_set_status": "blocked",
                "last_failed_module": "expression_set",
                "last_failed_slot_key": "expression.smile",
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
