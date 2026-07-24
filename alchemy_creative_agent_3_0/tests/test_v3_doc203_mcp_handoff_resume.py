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
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatus, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    expression_front_card_framing_materialization_directive,
    laugh_expression_materialization_directive,
)
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    LayoutPlan,
    LayoutRegion,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
    TextRenderingMode,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorCandidateUnavailable
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
    assert handoffs.get(current["handoff_id"])["status"] == "consumed"
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
        reference_assets=[],
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
            reference_assets=[],
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
        reference_assets=[],
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
        reference_assets=[],
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
        reference_assets=[],
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
        reference_assets=[],
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
