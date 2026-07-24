from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router import (
    McpMaterializationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import ProductApiAnchorPackPreparationHost
from alchemy_creative_agent_3_0.app.product_api.contracts import (
    CreateCreativeJobRequest,
    ProductJobStatus,
    ProductJobStatusValue,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import (
    PersistentProductJobStore,
    ProductJobRecord,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    expression_front_card_framing_materialization_directive,
    laugh_expression_materialization_directive,
)
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    BrandProfile,
    CommercialAssetPack,
    CommercialBrief,
    ConditionPlan,
    CreativeJob,
    CreativePlan,
    GenerationPlan,
    IndustryCategory,
    LayoutPlan,
    LayoutRegion,
    PackagedAsset,
    Platform,
    PlanningResult,
    PromptCompilationResult,
    ProviderStrategy,
    SeriesPlan,
    TextRenderingMode,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateUnavailable,
    AnchorGenerationRequest,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import CharacterCardCandidateRequest
from app.providers.base import ProviderRuntimeError


def _png_bytes(color: tuple[int, int, int] = (224, 236, 255)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 48), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _current_laugh_handoff_prompt(*, suffix: str = "") -> str:
    return (
        f"{laugh_expression_materialization_directive()} "
        f"{expression_front_card_framing_materialization_directive()} "
        f"{suffix}"
    ).strip()


def _current_expression_reference_assets() -> list[dict]:
    return [
        {
            "asset_id": "front_winner",
            "derivative_kind": "character_card_full_frame_framing_reference",
            "identity_evidence_scope": "card_framing",
            "sha256": "1" * 64,
        },
        {
            "asset_id": "front_winner::portrait_identity_crop",
            "derivative_kind": "portrait_identity_crop",
            "sha256": "2" * 64,
        },
        {
            "asset_id": "front_winner::portrait_identity_geometry_crop",
            "derivative_kind": "portrait_identity_pose_geometry_crop",
            "sha256": "3" * 64,
        },
    ]


def _stale_crop_first_expression_reference_assets() -> list[dict]:
    return [
        {
            "asset_id": "front_winner::portrait_identity_crop",
            "derivative_kind": "portrait_identity_crop",
            "sha256": "2" * 64,
        },
        {
            "asset_id": "front_winner::portrait_identity_geometry_crop",
            "derivative_kind": "portrait_identity_pose_geometry_crop",
            "sha256": "3" * 64,
        },
        {"asset_id": "front_winner", "derivative_kind": "portrait_identity", "sha256": "1" * 64},
    ]


def _request_metadata(
    *,
    operation_id: str = "doc203-operation",
    materialization: dict | None = None,
) -> dict:
    metadata = {
        "mock_profile": "balanced",
        "requested_image_size": "1024x1536",
        "generation_channel": "mcp",
        "mcp_operation_id": operation_id,
        "llm_brain": {
            "llm_used": True,
            "fallback_used": False,
            "canonical_provider_prompts": [
                {
                    "output_index": 1,
                    "prompt": "same character card portrait, clean reference-card framing",
                    "review_status": "approved",
                }
            ],
            "audit": {
                "remote_canonical_provider_prompts_received": True,
                "canonical_provider_prompt_stage": "provider_prompt_finalize",
            },
        },
    }
    if materialization is not None:
        metadata["mcp_materialization"] = materialization
    return metadata


def _minimal_request(*, metadata: dict | None = None):
    asset = AssetSpec(
        asset_id="asset_doc203",
        asset_type=AssetType.MAIN_POSTER,
        platform=Platform.XIAOHONGSHU,
        aspect_ratio="2:3",
        purpose="character card validation image",
    )
    layout = LayoutPlan(
        layout_plan_id="layout_doc203",
        asset_id=asset.asset_id,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        text_rendering=TextRenderingMode.NO_TEXT,
        visual_hierarchy=["subject"],
        product_area=LayoutRegion(name="subject_area", position="center"),
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc203",
        asset_id=asset.asset_id,
        visual_prompt="same character card portrait",
        negative_prompt="no watermark",
        text_policy="no_text",
        style_notes=[],
        layout_notes=[],
        provider_notes={},
    )
    condition = ConditionPlan(condition_plan_id="condition_doc203", asset_id=asset.asset_id)
    generation = GenerationPlan(
        generation_plan_id="generation_doc203",
        asset_id=asset.asset_id,
        provider_strategy=ProviderStrategy.MCP_MATERIALIZATION,
        candidate_count=1,
        max_refine_rounds=0,
        metadata=metadata or _request_metadata(),
    )
    return build_provider_generation_request(
        asset_spec=asset,
        layout_plan=layout,
        prompt_compilation=prompt,
        condition_plan=condition,
        generation_plan=generation,
        job_id="job_doc203",
    )


def _minimal_planning_result(job_id: str, *, asset_id: str = "asset_doc223c") -> PlanningResult:
    asset = AssetSpec(
        asset_id=asset_id,
        asset_type=AssetType.MAIN_POSTER,
        platform=Platform.XIAOHONGSHU,
        aspect_ratio="2:3",
        purpose="durable MCP resume checkpoint",
    )
    layout = LayoutPlan(
        layout_plan_id=f"layout_{job_id}",
        asset_id=asset.asset_id,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        text_rendering=TextRenderingMode.NO_TEXT,
        visual_hierarchy=["subject"],
        product_area=LayoutRegion(name="subject_area", position="center"),
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id=f"prompt_{job_id}",
        asset_id=asset.asset_id,
        visual_prompt="same character card portrait",
        negative_prompt="no watermark",
        text_policy="no_text",
    )
    condition = ConditionPlan(condition_plan_id=f"condition_{job_id}", asset_id=asset.asset_id)
    generation = GenerationPlan(
        generation_plan_id=f"generation_{job_id}",
        asset_id=asset.asset_id,
        provider_strategy=ProviderStrategy.MCP_MATERIALIZATION,
        candidate_count=1,
        max_refine_rounds=0,
    )
    packaged = PackagedAsset(
        asset_id=asset.asset_id,
        asset_type=asset.asset_type,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        purpose=asset.purpose,
        layout_plan_id=layout.layout_plan_id,
        prompt_compilation_id=prompt.prompt_compilation_id,
        metadata={},
    )
    return PlanningResult(
        planning_result_id=f"planning_{job_id}",
        creative_job=CreativeJob(job_id=job_id, raw_user_input="durable MCP resume checkpoint"),
        commercial_brief=CommercialBrief(
            brief_id=f"brief_{job_id}",
            job_id=job_id,
            industry=IndustryCategory.UNKNOWN,
            scenario="checkpoint",
            business_goal="checkpoint",
            target_platforms=[Platform.XIAOHONGSHU],
        ),
        brand_profile=BrandProfile(brand_id=f"brand_{job_id}"),
        creative_plan=CreativePlan(
            creative_plan_id=f"plan_{job_id}",
            job_id=job_id,
            brief_id=f"brief_{job_id}",
            concept="checkpoint",
            visual_direction="checkpoint",
            composition_strategy="single subject",
        ),
        series_plan=SeriesPlan(series_plan_id=f"series_{job_id}", job_id=job_id, assets=[asset]),
        layout_plans=[layout],
        prompt_compilations=[prompt],
        condition_plans=[condition],
        generation_plans=[generation],
        evaluation_reports=[],
        asset_pack=CommercialAssetPack(
            asset_pack_id=f"asset_pack_{job_id}",
            job_id=job_id,
            assets=[packaged],
            planning_only=False,
        ),
        metadata={},
    )


def _save_doc223c_noise_jobs(store: PersistentProductJobStore, count: int) -> None:
    for index in range(count):
        job_id = f"job_doc223c_noise_{index:03d}"
        store.save(
            ProductJobRecord(
                request=CreateCreativeJobRequest(
                    user_input="noise",
                    metadata={
                        "generation_channel": "mcp",
                        "mcp_operation_id": f"doc223c-noise-{index}",
                    },
                ),
                status=ProductJobStatusValue.GENERATING,
                job_id_value=job_id,
            )
        )


def _character_card_doc223c_request(
    *,
    operation_id: str,
    handoff_id: str | None = None,
) -> CharacterCardCandidateRequest:
    return CharacterCardCandidateRequest(
        project_id="project_doc223c",
        people_asset_id="people_doc223c",
        card_version_id="card_doc223c",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=handoff_id,
    )


def _anchor_doc223c_request(*, operation_id: str, handoff_id: str) -> AnchorGenerationRequest:
    return AnchorGenerationRequest(
        project_id="project_doc223c",
        people_asset_id="people_doc223c",
        pack_version_id="pack_doc223c",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="prepare front anchor",
        root_source_asset_id="root_doc223c",
        reference_evidence_ids=["root_doc223c"],
        generation_channel="mcp",
        mcp_operation_id=operation_id,
        mcp_handoff_id=handoff_id,
    )


def test_doc203_provider_request_preserves_explicit_mcp_materialization_handoff() -> None:
    explicit_handoff = {
        "handoff_id": "mcp_handoff_doc203_current",
        "status": "pending",
        "generation_channel": "mcp",
        "resume_required": True,
    }

    request = _minimal_request(
        metadata=_request_metadata(
            operation_id="doc203-explicit-operation",
            materialization=explicit_handoff,
        )
    )

    assert request.metadata["generation_channel"] == "mcp"
    assert request.metadata["mcp_operation_id"] == "doc203-explicit-operation"
    assert request.metadata["mcp_materialization"] == explicit_handoff


def test_doc203_mcp_provider_consumes_explicit_handoff_not_stale_same_operation(tmp_path: Path) -> None:
    operation_id = "doc203-same-operation"
    request = _minimal_request(metadata=_request_metadata(operation_id=operation_id))
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    app_request, _provider_name, _references = provider._build_app_request(request)
    contract = app_request.prompt_plan.variables["mcp_materialization_context"]["rendering_contract"]

    stale_prompt = "stale submitted handoff"
    current_prompt = "current explicitly requested handoff"
    stale = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=stale_prompt,
        prompt_sha256=hashlib.sha256(stale_prompt.encode()).hexdigest(),
        reference_assets=[],
        rendering_contract=contract,
    )
    current = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=current_prompt,
        prompt_sha256=hashlib.sha256(current_prompt.encode()).hexdigest(),
        reference_assets=[],
        rendering_contract=contract,
    )
    for handoff in (stale, current):
        handoffs.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=_png_bytes(),
        )

    explicit_request = _minimal_request(
        metadata=_request_metadata(
            operation_id=operation_id,
            materialization={
                "handoff_id": current["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        )
    )

    response = provider.generate(explicit_request)

    record = outputs.get_output(response.candidates[0].metadata["output_id"])
    assert record is not None
    assert record.metadata["provider_raw_summary"]["mcp_handoff_id"] == current["handoff_id"]
    assert handoffs.get(current["handoff_id"])["status"] == "output_checkpointed"
    assert handoffs.get(stale["handoff_id"])["status"] == "submitted"


def test_doc218_mcp_pending_handoff_with_stale_contract_is_superseded(tmp_path: Path) -> None:
    operation_id = "doc218-stale-pending-operation"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    provider = McpMaterializationProvider(
        output_store=V3GeneratedOutputStore(tmp_path / "outputs"),
        handoff_store=handoffs,
    )
    stale_path = tmp_path / "stale.png"
    current_path = tmp_path / "current.png"
    stale_path.write_bytes(_png_bytes())
    current_path.write_bytes(_png_bytes((255, 232, 224)))
    stale_refs = [{"asset_id": "stale_ref", "file_path": str(stale_path)}]
    current_refs = [{"asset_id": "current_ref", "file_path": str(current_path)}]
    prompt = "same frozen prompt"
    prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
    contract = {
        "size": "32x48",
        "quality": "standard",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
    }
    stale = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=stale_refs,
        rendering_contract=contract,
    )
    explicit_request = _minimal_request(
        metadata=_request_metadata(
            operation_id=operation_id,
            materialization={
                "handoff_id": stale["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        )
    )

    context = provider._existing_mcp_handoff_context(  # noqa: SLF001
        explicit_request,
        current_context={
            "operation_id": operation_id,
            "canonical_prompt": prompt,
            "prompt_sha256": prompt_sha,
        },
        current_reference_assets=current_refs,
        current_rendering_contract=contract,
    )

    assert context is None


def test_doc218_mcp_submitted_handoff_with_stale_contract_fails_closed(tmp_path: Path) -> None:
    operation_id = "doc218-stale-submitted-operation"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    provider = McpMaterializationProvider(
        output_store=V3GeneratedOutputStore(tmp_path / "outputs"),
        handoff_store=handoffs,
    )
    stale_path = tmp_path / "stale-submitted.png"
    current_path = tmp_path / "current-submitted.png"
    stale_path.write_bytes(_png_bytes())
    current_path.write_bytes(_png_bytes((255, 232, 224)))
    stale_refs = [{"asset_id": "stale_ref", "file_path": str(stale_path)}]
    current_refs = [{"asset_id": "current_ref", "file_path": str(current_path)}]
    prompt = "same frozen prompt"
    prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
    contract = {
        "size": "32x48",
        "quality": "standard",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
    }
    stale = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_sha,
        reference_assets=stale_refs,
        rendering_contract=contract,
    )
    handoffs.submit(
        stale["handoff_id"],
        nonce=stale["nonce"],
        prompt_sha256=stale["prompt_sha256"],
        reference_asset_hashes=stale["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )
    explicit_request = _minimal_request(
        metadata=_request_metadata(
            operation_id=operation_id,
            materialization={
                "handoff_id": stale["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        )
    )

    with pytest.raises(ProviderRuntimeError) as exc_info:
        provider._existing_mcp_handoff_context(  # noqa: SLF001
            explicit_request,
            current_context={
                "operation_id": operation_id,
                "canonical_prompt": prompt,
                "prompt_sha256": prompt_sha,
            },
            current_reference_assets=current_refs,
            current_rendering_contract=contract,
        )

    assert getattr(exc_info.value, "detail", {})["failure_code"] == "mcp_materialization_reference_mismatch"


def test_doc203_character_card_stage_creation_receives_explicit_mcp_handoff() -> None:
    class _Store:
        def __init__(self) -> None:
            self.record = None

        def list_recent(self, _limit):
            return []

        def list_mcp_operation_records(self, _operation_id):
            return []

        def save(self, record) -> None:
            self.record = record

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.job_store = _Store()
            self.record = None
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                }
            )

        def create_professional_character_card_stage_job(self, payload, **_kwargs):
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc203_character_card_resume",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            self.job_store.record = self.record
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):
            assert job_id == "job_doc203_character_card_resume"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc203",
        people_asset_id="people_doc203",
        card_version_id="card_doc203",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=2,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc203_current",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    materialization = service.created_payloads[0]["metadata"]["mcp_materialization"]
    assert materialization["handoff_id"] == "mcp_handoff_doc203_current"


def test_doc203_scenario_runtime_projects_explicit_mcp_handoff_to_generation_metadata() -> None:
    materialization = {
        "handoff_id": "mcp_handoff_doc203_runtime",
        "status": "pending",
        "generation_channel": "mcp",
        "resume_required": True,
    }

    metadata = ScenarioRuntime._renderer_channel_metadata(
        SimpleNamespace(
            metadata={
                "generation_channel": "mcp",
                "mcp_operation_id": "doc203-runtime-operation",
                "mcp_materialization": materialization,
            }
        )
    )

    assert metadata["generation_channel"] == "mcp"
    assert metadata["mcp_operation_id"] == "doc203-runtime-operation"
    assert metadata["mcp_materialization"] == materialization


def test_doc209_scenario_runtime_preserves_explicit_mcp_handoff_in_frozen_generation_plan() -> None:
    materialization = {
        "handoff_id": "mcp_handoff_doc209_submitted",
        "status": "submitted",
        "generation_channel": "mcp",
        "resume_required": True,
    }

    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create one character-card laugh validation portrait.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {
                "requested_image_count": 1,
                "require_real_images": True,
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc209:expression_set:expression.laugh:1:round3",
                "mcp_materialization": materialization,
            },
        }
    )

    assert result.planning_result is not None
    generation_metadata = result.planning_result.generation_plans[0].metadata
    assert generation_metadata["generation_channel"] == "mcp"
    assert generation_metadata["mcp_operation_id"] == "people_doc209:expression_set:expression.laugh:1:round3"
    assert generation_metadata["mcp_materialization"] == materialization


def test_doc205_character_card_recovers_orphan_submitted_handoff_without_replanning(tmp_path: Path) -> None:
    operation_id = "people_doc205:expression_set:expression.laugh:2:round3"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    prompt = _current_laugh_handoff_prompt()
    handoff = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    handoffs.submit(
        handoff["handoff_id"],
        nonce=handoff["nonce"],
        prompt_sha256=handoff["prompt_sha256"],
        reference_asset_hashes=handoff["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )

    class _Store:
        def __init__(self) -> None:
            self.record = None

        def list_recent(self, _limit):
            return []

        def list_mcp_operation_records(self, _operation_id):
            return []

        def save(self, record) -> None:
            self.record = record

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.job_store = _Store()
            self.record = None
            self.mcp_materialization_store = handoffs

        def create_professional_character_card_stage_job(self, payload, **_kwargs):
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc205_orphan_resume",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            self.job_store.record = self.record
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):
            assert job_id == "job_doc205_orphan_resume"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc205",
        people_asset_id="people_doc205",
        card_version_id="card_doc205",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=3,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    materialization = service.created_payloads[0]["metadata"]["mcp_materialization"]
    assert materialization["handoff_id"] == handoff["handoff_id"]
    assert [item["handoff_id"] for item in handoffs.list_unconsumed_by_operation(operation_id)] == [
        handoff["handoff_id"]
    ]


def test_doc205_character_card_orphan_handoff_recovery_fails_closed_when_ambiguous(tmp_path: Path) -> None:
    operation_id = "people_doc205:expression_set:expression.laugh:2:round3"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    for prompt in (
        _current_laugh_handoff_prompt(suffix="candidate A"),
        _current_laugh_handoff_prompt(suffix="candidate B"),
    ):
        handoffs.ensure_pending(
            operation_id=operation_id,
            prompt=prompt,
            prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            reference_assets=_current_expression_reference_assets(),
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

    service = SimpleNamespace(
        visual_asset_catalog=None,
        mcp_materialization_store=handoffs,
        job_store=SimpleNamespace(list_recent=lambda _limit: []),
    )
    request = CharacterCardCandidateRequest(
        project_id="project_doc205",
        people_asset_id="people_doc205",
        card_version_id="card_doc205",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=3,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_operation_ambiguous"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]


def test_doc207_character_card_orphan_recovery_prefers_submitted_artifact_over_pending(tmp_path: Path) -> None:
    operation_id = "people_doc207:expression_set:expression.laugh:1:round3"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    pending = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=_current_laugh_handoff_prompt(suffix="pending draft"),
        prompt_sha256=hashlib.sha256(
            _current_laugh_handoff_prompt(suffix="pending draft").encode("utf-8")
        ).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    submitted = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=_current_laugh_handoff_prompt(suffix="submitted artifact"),
        prompt_sha256=hashlib.sha256(
            _current_laugh_handoff_prompt(suffix="submitted artifact").encode("utf-8")
        ).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    handoffs.submit(
        submitted["handoff_id"],
        nonce=submitted["nonce"],
        prompt_sha256=submitted["prompt_sha256"],
        reference_asset_hashes=submitted["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return []

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return []

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.job_store = _Store()
            self.mcp_materialization_store = handoffs
            self.record = None

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc207_submitted_priority",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):  # noqa: ANN001, ANN201
            assert job_id == "job_doc207_submitted_priority"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc207",
        people_asset_id="people_doc207",
        card_version_id="card_doc207",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=3,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    selected = service.created_payloads[0]["metadata"]["mcp_materialization"]
    assert selected["handoff_id"] == submitted["handoff_id"]
    assert selected["handoff_id"] != pending["handoff_id"]


def test_doc208_character_card_request_pending_hint_cannot_override_submitted_artifact(tmp_path: Path) -> None:
    operation_id = "people_doc208:expression_set:expression.laugh:1:round3"
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    pending = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=_current_laugh_handoff_prompt(suffix="pending draft"),
        prompt_sha256=hashlib.sha256(
            _current_laugh_handoff_prompt(suffix="pending draft").encode("utf-8")
        ).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    submitted = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=_current_laugh_handoff_prompt(suffix="submitted artifact"),
        prompt_sha256=hashlib.sha256(
            _current_laugh_handoff_prompt(suffix="submitted artifact").encode("utf-8")
        ).hexdigest(),
        reference_assets=_current_expression_reference_assets(),
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "32x48",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
    )
    handoffs.submit(
        submitted["handoff_id"],
        nonce=submitted["nonce"],
        prompt_sha256=submitted["prompt_sha256"],
        reference_asset_hashes=submitted["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )
    old_pending_record = SimpleNamespace(
        job_id="job_doc208_old_pending",
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": pending["handoff_id"],
                    "status": "pending",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [old_pending_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [old_pending_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.job_store = _Store()
            self.mcp_materialization_store = handoffs
            self.record = None

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc208_submitted_resume",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):  # noqa: ANN001, ANN201
            assert job_id != "job_doc208_old_pending"
            assert job_id == "job_doc208_submitted_resume"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc208",
        people_asset_id="people_doc208",
        card_version_id="card_doc208",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=3,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=pending["handoff_id"],
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    selected = service.created_payloads[0]["metadata"]["mcp_materialization"]
    assert selected["handoff_id"] == submitted["handoff_id"]
    assert selected["handoff_id"] != pending["handoff_id"]


def test_doc215_product_api_allows_only_pre_handoff_mcp_interruption_reentry() -> None:
    base_record = SimpleNamespace(
        status=ProductJobStatusValue.GENERATING,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc215:expression_set:expression.laugh:1:round5",
            }
        ),
    )

    assert V3ProductApiService._can_resume_interrupted_mcp_materialization(base_record) is True

    for metadata_patch, field_patch in (
        ({"mcp_materialization": {"handoff_id": "mcp_handoff_existing"}}, {}),
        ({}, {"generation_result": object()}),
        ({"generation_channel": "provider"}, {}),
        ({"professional_character_card_preparation": False}, {}),
        ({"background_generation_attempt_id": "attempt_running_elsewhere"}, {}),
    ):
        metadata = {**base_record.request.metadata, **metadata_patch}
        record = SimpleNamespace(
            status=ProductJobStatusValue.GENERATING,
            planning_result=object(),
            generation_result=None,
            request=SimpleNamespace(metadata=metadata),
        )
        for name, value in field_patch.items():
            setattr(record, name, value)
        assert V3ProductApiService._can_resume_interrupted_mcp_materialization(record) is False


def test_doc215_character_card_reenters_same_interrupted_mcp_job_without_replanning() -> None:
    operation_id = "people_doc215:expression_set:expression.laugh:1:round5"
    interrupted_record = SimpleNamespace(
        job_id="job_doc215_interrupted",
        status=ProductJobStatusValue.GENERATING,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [interrupted_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [interrupted_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.generated_calls = []
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(get=lambda _handoff_id: None)

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            raise AssertionError("Doc215 must reuse the interrupted job instead of re-planning")

        def generate_job(self, job_id, request):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, request))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return interrupted_record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc215",
        people_asset_id="people_doc215",
        card_version_id="card_doc215",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert service.created_payloads == []
    assert service.generated_calls[0][0] == "job_doc215_interrupted"
    assert (
        service.generated_calls[0][1]["metadata"]["_v3_resume_interrupted_mcp_materialization"]
        is True
    )
    assert service.generated_calls[0][1]["metadata"]["disable_visual_auto_retry"] is True
    assert service.generated_calls[0][1]["metadata"]["max_visual_retry_attempts"] == 0


def test_doc215_existing_mcp_handoff_still_uses_normal_handoff_resume_not_reentry() -> None:
    operation_id = "people_doc215:expression_set:expression.laugh:1:round5"
    pending_record = SimpleNamespace(
        job_id="job_doc215_pending",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc215_existing",
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [pending_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [pending_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.generated_calls = []
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                }
            )

        def generate_job(self, job_id, request):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, request))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return pending_record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc215",
        people_asset_id="people_doc215",
        card_version_id="card_doc215",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=1,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc215_existing",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert "_v3_resume_interrupted_mcp_materialization" not in service.generated_calls[0][1]["metadata"]
    assert service.generated_calls[0][1]["metadata"]["disable_visual_auto_retry"] is True
    assert service.generated_calls[0][1]["metadata"]["max_visual_retry_attempts"] == 0


def test_doc219_host_does_not_resume_stale_crop_first_pending_expression_handoff() -> None:
    operation_id = "people_doc219:expression_set:expression.laugh:2:round5"
    pending_record = SimpleNamespace(
        job_id="job_doc219_stale_pending",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc219_stale_pending",
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [pending_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [pending_record]

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _stale_crop_first_expression_reference_assets(),
                }
            )

    request = CharacterCardCandidateRequest(
        project_id="project_doc219",
        people_asset_id="people_doc219",
        card_version_id="card_doc219",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc219_stale_pending",
    )

    resume = ProductApiAnchorPackPreparationHost(_Service())._mcp_resume_character_card_stage_job_record(  # type: ignore[arg-type]  # noqa: SLF001
        request,
        operation_id,
    )

    assert resume is None


def test_doc219_host_fails_closed_on_stale_crop_first_submitted_expression_handoff() -> None:
    operation_id = "people_doc219:expression_set:expression.laugh:2:round5"
    submitted_record = SimpleNamespace(
        job_id="job_doc219_stale_submitted",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc219_stale_submitted",
                    "status": "submitted",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [submitted_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [submitted_record]

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "submitted",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _stale_crop_first_expression_reference_assets(),
                }
            )

    request = CharacterCardCandidateRequest(
        project_id="project_doc219",
        people_asset_id="people_doc219",
        card_version_id="card_doc219",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc219_stale_submitted",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_reference_mismatch"):
        ProductApiAnchorPackPreparationHost(_Service())._mcp_resume_character_card_stage_job_record(  # type: ignore[arg-type]  # noqa: SLF001
            request,
            operation_id,
        )


def test_doc220_stale_pending_handoff_hint_is_not_copied_into_new_stage_job() -> None:
    operation_id = "people_doc220:expression_set:expression.laugh:2:round5"

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return []

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return []

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.created_payloads = []
            self.record = None
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _stale_crop_first_expression_reference_assets(),
                },
                list_unconsumed_by_operation=lambda _operation_id: [],
            )

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            self.record = SimpleNamespace(
                job_id="job_doc220_new_without_stale_hint",
                planning_result=object(),
                generation_result=None,
                request=SimpleNamespace(metadata=dict(payload.get("metadata") or {})),
            )
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, *_args, **_kwargs):  # noqa: ANN001, ANN201
            assert job_id == "job_doc220_new_without_stale_hint"
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, _job_id):  # noqa: ANN001, ANN201
            return self.record

    service = _Service()
    request = CharacterCardCandidateRequest(
        project_id="project_doc220",
        people_asset_id="people_doc220",
        card_version_id="card_doc220",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc220_stale_pending",
    )

    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert service.created_payloads
    assert "mcp_materialization" not in service.created_payloads[0]["metadata"]


def test_doc221_clean_interrupted_job_wins_over_older_stale_blocked_handoff_job() -> None:
    operation_id = "people_doc221:expression_set:expression.laugh:2:round5"
    stale_blocked_record = SimpleNamespace(
        job_id="job_doc221_stale_blocked",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_doc221_stale_pending",
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )
    clean_generating_record = SimpleNamespace(
        job_id="job_doc221_clean_generating",
        status=ProductJobStatusValue.GENERATING,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [stale_blocked_record, clean_generating_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [stale_blocked_record, clean_generating_record]

        def save(self, _record) -> None:  # noqa: ANN001
            return None

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = _Store()
            self.generated_calls = []
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _stale_crop_first_expression_reference_assets(),
                }
            )

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            assert job_id == "job_doc221_clean_generating"
            self.generated_calls.append((job_id, payload))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
                metadata={
                    "mcp_materialization": {
                        "handoff_id": "mcp_handoff_doc221_new_full_frame_first",
                        "status": "pending",
                        "generation_channel": "mcp",
                        "canonical_prompt": _current_laugh_handoff_prompt(),
                        "reference_assets": _current_expression_reference_assets(),
                    }
                },
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            if job_id == clean_generating_record.job_id:
                return clean_generating_record
            if job_id == stale_blocked_record.job_id:
                return stale_blocked_record
            return None

    request = CharacterCardCandidateRequest(
        project_id="project_doc221",
        people_asset_id="people_doc221",
        card_version_id="card_doc221",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id="mcp_handoff_doc221_stale_pending",
    )

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        ProductApiAnchorPackPreparationHost(service).generate(request)  # type: ignore[arg-type]

    assert str(exc_info.value) == "mcp_materialization_pending"
    assert exc_info.value.mcp_handoff_id == "mcp_handoff_doc221_new_full_frame_first"
    assert service.generated_calls
    assert service.generated_calls[0][0] == "job_doc221_clean_generating"
    assert service.generated_calls[0][1]["metadata"]["_v3_resume_interrupted_mcp_materialization"] is True
    assert service.generated_calls[0][1]["metadata"]["disable_visual_auto_retry"] is True


def test_doc221_current_handoff_resume_still_requires_exact_operation_and_refs() -> None:
    requested_operation = "people_doc221:expression_set:expression.laugh:2:round5"
    current_handoff = "mcp_handoff_doc221_current"
    wrong_ref_record = SimpleNamespace(
        job_id="job_doc221_wrong_refs",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["other_front"],
                "generation_channel": "mcp",
                "mcp_operation_id": requested_operation,
                "mcp_materialization": {
                    "handoff_id": current_handoff,
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )
    wrong_operation_record = SimpleNamespace(
        job_id="job_doc221_wrong_operation",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": "people_doc221:expression_set:expression.laugh:3:round5",
                "mcp_materialization": {
                    "handoff_id": current_handoff,
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )
    exact_record = SimpleNamespace(
        job_id="job_doc221_exact_current",
        status=ProductJobStatusValue.BLOCKED,
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": requested_operation,
                "mcp_materialization": {
                    "handoff_id": current_handoff,
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def list_recent(self, _limit):  # noqa: ANN001, ANN201
            return [wrong_ref_record, wrong_operation_record, exact_record]

        def list_mcp_operation_records(self, _operation_id):  # noqa: ANN001, ANN201
            return [wrong_ref_record, wrong_operation_record, exact_record]

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = _Store()
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda handoff_id: {
                    "handoff_id": handoff_id,
                    "status": "pending",
                    "canonical_prompt": _current_laugh_handoff_prompt(),
                    "reference_assets": _current_expression_reference_assets(),
                }
            )

    request = CharacterCardCandidateRequest(
        project_id="project_doc221",
        people_asset_id="people_doc221",
        card_version_id="card_doc221",
        module="expression_set",
        slot_key="expression.laugh",
        candidate_index=2,
        attempt_round=5,
        reference_output_ids=["front_winner"],
        user_intent="positive expression keyframe",
        generation_channel="mcp",
        mcp_handoff_id=current_handoff,
    )

    resume = ProductApiAnchorPackPreparationHost(_Service())._mcp_resume_character_card_stage_job_record(  # type: ignore[arg-type]  # noqa: SLF001
        request,
        requested_operation,
    )

    assert resume is exact_record


def test_doc223c_character_card_recovers_old_interrupted_job_beyond_recent_window(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:expression_set:expression.laugh:2:round5"
    store = PersistentProductJobStore(tmp_path / "jobs")
    target = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="positive expression keyframe",
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.laugh",
                "professional_character_card_reference_output_ids": ["front_winner"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
            },
        ),
        status=ProductJobStatusValue.GENERATING,
        job_id_value="job_doc223c_character_old_checkpoint",
        planning_result=_minimal_planning_result("job_doc223c_character_old_checkpoint"),
    )
    store.save(target)
    _save_doc223c_noise_jobs(store, 230)
    assert target.job_id not in {record.job_id for record in store.list_recent(200)}

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = SimpleNamespace(get=lambda _handoff_id: None)
            self.created_payloads = []
            self.generated_calls = []

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            raise AssertionError("Doc223-C must recover the durable job before creating a new Brain job")

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, payload))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            return self.job_store.get(job_id)

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(
            _character_card_doc223c_request(operation_id=operation_id)
        )  # type: ignore[arg-type]

    assert service.created_payloads == []
    assert service.generated_calls[0][0] == target.job_id
    assert len(store.list_mcp_operation_records(operation_id)) == 1


def test_doc223c_anchor_pack_recovers_old_handoff_job_beyond_recent_window(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:anchor_pack:standard_front:1"
    store = PersistentProductJobStore(tmp_path / "jobs")
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    prompt = "front anchor MCP handoff"
    handoff = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        reference_assets=[],
        rendering_contract={"size": "32x48", "output_format": "png"},
    )
    target = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="prepare front anchor",
            metadata={
                "professional_anchor_pack_preparation": True,
                "professional_reference_stage": "standard_front",
                "professional_anchor_capture_scope": "anchor_pack",
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {
                    "handoff_id": handoff["handoff_id"],
                    "status": "pending",
                    "generation_channel": "mcp",
                },
            },
        ),
        status=ProductJobStatusValue.GENERATING,
        job_id_value="job_doc223c_anchor_old_checkpoint",
        planning_result=_minimal_planning_result("job_doc223c_anchor_old_checkpoint"),
    )
    store.save(target)
    _save_doc223c_noise_jobs(store, 130)
    assert target.job_id not in {record.job_id for record in store.list_recent(100)}

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = handoffs
            self.created_payloads = []
            self.generated_calls = []

        def create_professional_anchor_preparation_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            raise AssertionError("Doc223-C must recover the durable anchor job before creating a new Brain job")

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            self.generated_calls.append((job_id, payload))
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            return self.job_store.get(job_id)

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_pending") as exc_info:
        ProductApiAnchorPackPreparationHost(service).generate(
            _anchor_doc223c_request(
                operation_id=operation_id,
                handoff_id=handoff["handoff_id"],
            )
        )  # type: ignore[arg-type]

    assert exc_info.value.mcp_handoff_id == handoff["handoff_id"]
    assert service.created_payloads == []
    assert service.generated_calls[0][0] == target.job_id
    assert len(store.list_mcp_operation_records(operation_id)) == 1


def test_doc223c_character_card_conflicting_operation_records_fail_closed(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:expression_set:expression.laugh:2:round5"
    store = PersistentProductJobStore(tmp_path / "jobs")
    for index in range(2):
        job_id = f"job_doc223c_conflict_{index}"
        store.save(
            ProductJobRecord(
                request=CreateCreativeJobRequest(
                    user_input="positive expression keyframe",
                    metadata={
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.laugh",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": operation_id,
                    },
                ),
                status=ProductJobStatusValue.GENERATING,
                job_id_value=job_id,
                planning_result=_minimal_planning_result(job_id),
            )
        )

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = SimpleNamespace(get=lambda _handoff_id: None)

    with pytest.raises(AnchorCandidateUnavailable, match="mcp_materialization_operation_ambiguous"):
        ProductApiAnchorPackPreparationHost(_Service()).generate(  # type: ignore[arg-type]
            _character_card_doc223c_request(operation_id=operation_id)
        )


def test_doc223c_character_card_wrong_reference_record_is_not_reused(
    tmp_path: Path,
) -> None:
    operation_id = "people_doc223c:expression_set:expression.laugh:2:round5"
    store = PersistentProductJobStore(tmp_path / "jobs")
    store.save(
        ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="positive expression keyframe",
                metadata={
                    "professional_character_card_preparation": True,
                    "professional_character_card_stage": "expression_set",
                    "professional_character_card_slot": "expression.laugh",
                    "professional_character_card_reference_output_ids": ["wrong_front"],
                    "generation_channel": "mcp",
                    "mcp_operation_id": operation_id,
                },
            ),
            status=ProductJobStatusValue.GENERATING,
            job_id_value="job_doc223c_wrong_reference",
            planning_result=_minimal_planning_result("job_doc223c_wrong_reference"),
        )
    )

    class _Service:
        visual_asset_catalog = None

        def __init__(self) -> None:
            self.job_store = store
            self.mcp_materialization_store = SimpleNamespace(
                get=lambda _handoff_id: None,
                list_unconsumed_by_operation=lambda _operation_id: [],
            )
            self.created_payloads = []
            self.record = ProductJobRecord(
                request=CreateCreativeJobRequest(
                    user_input="positive expression keyframe",
                    metadata={
                        "professional_character_card_preparation": True,
                        "professional_character_card_stage": "expression_set",
                        "professional_character_card_slot": "expression.laugh",
                        "professional_character_card_reference_output_ids": ["front_winner"],
                        "generation_channel": "mcp",
                        "mcp_operation_id": operation_id,
                    },
                ),
                status=ProductJobStatusValue.PLANNED,
                job_id_value="job_doc223c_new_after_wrong_reference",
                planning_result=_minimal_planning_result("job_doc223c_new_after_wrong_reference"),
            )

        def create_professional_character_card_stage_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
            self.created_payloads.append(payload)
            return ProductJobStatus(
                job_id=self.record.job_id,
                status=ProductJobStatusValue.PLANNED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def generate_job(self, job_id, payload):  # noqa: ANN001, ANN201
            assert job_id == self.record.job_id
            return ProductJobStatus(
                job_id=job_id,
                status=ProductJobStatusValue.BLOCKED,
                api_namespace="/api/v3/creative-agent",
                ui_entry_route="/",
            )

        def get_job_record(self, job_id):  # noqa: ANN001, ANN201
            if job_id == self.record.job_id:
                return self.record
            return self.job_store.get(job_id)

    service = _Service()
    with pytest.raises(AnchorCandidateUnavailable, match="character_card_candidate_generation_failed"):
        ProductApiAnchorPackPreparationHost(service).generate(
            _character_card_doc223c_request(operation_id=operation_id)
        )  # type: ignore[arg-type]

    assert service.created_payloads
    assert service.created_payloads[0]["metadata"].get("mcp_materialization") is None
