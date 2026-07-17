"""Doc133: conversation-only frozen specialist-plan relay regressions.

The fixtures invoke the normal specialized ScenarioRuntime path with its
existing remote-Brain test doubles.  They deliberately never build an upstream
client, create a project/job record, or use an image/review/retry/delivery
path.
"""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.generation_router import (
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
from alchemy_creative_agent_3_0.tests.photography_test_support import PhotographyRemoteBrainTestProvider
from services.alchemy_codex_local_adapter.contracts import (
    CodexNativeImageGenError,
    NativeImageGenPlanRequest,
    NativeSpecializedImageGenPlanRequest,
)
from services.alchemy_codex_local_adapter.facade import CodexNativeImageGenFacade
from services.alchemy_codex_local_adapter.mcp_server import TOOL_SCHEMAS, dispatch
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


class _CapturingRuntime:
    def __init__(self, runtime: ScenarioRuntime) -> None:
        self.runtime = runtime
        self.payloads: list[dict[str, Any]] = []
        self.last_result = None

    def plan_job(self, payload: dict[str, Any]):
        self.payloads.append(deepcopy(payload))
        self.last_result = self.runtime.plan_job(payload)
        return self.last_result


def _write_png(path: Path, color: tuple[int, int, int] = (52, 125, 206)) -> Path:
    from PIL import Image

    Image.new("RGB", (32, 24), color=color).save(path, format="PNG")
    return path


def _arguments(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "user_input": "Create a truthful, natural image using only the supplied factual requirements.",
        "template_id": "ecommerce_template",
        "requested_image_count": 1,
        "requested_image_size": "1024x1536",
        "reference_inputs": [],
        "platform_profile": "generic",
        "photography_mode": None,
        "photographer_profile_id": None,
    }
    values.update(overrides)
    return values


def _provider_materializations(runtime_result) -> list[Any]:
    plan = runtime_result.planning_result
    assert plan is not None
    assets = {item.asset_id: item for item in plan.series_plan.assets}
    layouts = {item.asset_id: item for item in plan.layout_plans}
    prompts = {item.asset_id: item for item in plan.prompt_compilations}
    conditions = {item.asset_id: item for item in plan.condition_plans}
    generations = {item.asset_id: item for item in plan.generation_plans}
    materializer = ProductionImageGenerationProvider(output_store=object())
    return [
        materializer.materialize_final_prompt(
            build_provider_generation_request(
                asset_spec=asset,
                layout_plan=layouts[asset.asset_id],
                prompt_compilation=prompts[asset.asset_id],
                condition_plan=conditions[asset.asset_id],
                generation_plan=generations[asset.asset_id],
                job_id=plan.creative_job.job_id,
            )
        )
        for asset in plan.series_plan.assets
    ]


def _forbid_project_side_effect(*_args: Any, **_kwargs: Any) -> None:
    """Make any accidental Local-MCP Project Mode mutation fail loudly."""

    raise AssertionError("Codex Native ImageGen relay must not create or mutate Project Mode state")


@pytest.mark.parametrize("count", [1, 2, 4, 7])
def test_ecommerce_specialized_relay_projects_exact_brain_count_and_canonical_provider_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
) -> None:
    reference = _write_png(tmp_path / "product.png")
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    planner = CodexNativeImageGenPlanner(runtime_factory=lambda: capturing)

    def must_not_select_provider(*_args, **_kwargs):
        raise AssertionError("Local MCP must not select an upstream image provider")

    monkeypatch.setattr(ProductionImageGenerationProvider, "_select_provider", must_not_select_provider)
    monkeypatch.setattr(V3ProjectModeService, "create_project", _forbid_project_side_effect)
    monkeypatch.setattr(V3ProjectModeService, "create_project_job", _forbid_project_side_effect)
    monkeypatch.setattr(V3ProjectModeService, "generate_project_job", _forbid_project_side_effect)
    monkeypatch.setattr(V3ProjectModeService, "create_ecommerce_slot_continuation", _forbid_project_side_effect)
    monkeypatch.setattr(V3ProjectModeService, "create_photography_role_continuation", _forbid_project_side_effect)
    result = planner.prepare_frozen_specialized_native_imagegen_plan(
        NativeSpecializedImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                requested_image_count=count,
                user_input="Create family-friendly whole images of the supplied blue dress; preserve the product facts and use no visible marketing copy.",
                reference_inputs=[{"channel": "product_truth", "file_path": str(reference)}],
            )
        )
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["requested_output_count"] == count
    assert len(result["outputs"]) == count
    assert result["provenance"]["template_id"] == "ecommerce_template"
    assert result["provenance"]["scenario_id"] == "ecommerce"
    assert result["provenance"]["delivery_state"] == "conversation_only_not_certified"
    assert brain.requests and brain.requests[0]["scenario_id"] == "ecommerce"
    assert "photographer_profile_binding" not in brain.requests[0]["metadata"]

    # Every output is one remote-Brain whole-image intent.  E-Commerce's
    # internal ecommerce_output_N binding is intentionally opaque lineage:
    # the relay neither interprets it nor projects any slot/recipe/role field.
    frozen = capturing.last_result.metadata["template_deliverable_plan"]
    assert len(frozen["deliverables"]) == count
    assert all(item["source"] == "remote_v3_llm_brain" for item in frozen["deliverables"])
    public_shape = json.dumps(
        [{key: value for key, value in output.items() if key != "imagegen_prompt"} for output in result["outputs"]]
    ).lower()
    for forbidden in ("ecommerce_slot", "recipe", "one_click_product_set", "overlay", "suite", "photography_lineage_role"):
        assert forbidden not in public_shape

    expected = _provider_materializations(capturing.last_result)
    assert len(expected) == count
    for output, materialization in zip(result["outputs"], expected, strict=True):
        assert output["imagegen_prompt"] == materialization.generation_prompt
        assert output["provider_prompt_sha256"] == materialization.prompt_sha256
        assert output["provider_prompt_sha256"] == hashlib.sha256(output["imagegen_prompt"].encode("utf-8")).hexdigest()


def test_photography_specialized_relay_preserves_only_existing_lineage_roles_and_provider_prompt_parity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    reference = _write_png(tmp_path / "portrait-reference.png", color=(146, 95, 76))
    brain = PhotographyRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    result = CodexNativeImageGenPlanner(runtime_factory=lambda: capturing).prepare_frozen_specialized_native_imagegen_plan(
        NativeSpecializedImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                template_id="photographer_template",
                requested_image_count=3,
                platform_profile=None,
                photography_mode="professional_set",
                photographer_profile_id="general_photography",
                user_input="Create a restrained documentary portrait session of the same adult ceramic artist at work.",
                reference_inputs=[{"channel": "portrait_identity", "file_path": str(reference)}],
            )
        )
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["provenance"]["template_id"] == "photographer_template"
    assert result["provenance"]["scenario_id"] == "photography"
    assert [output["photography_lineage_role"] for output in result["outputs"]] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]
    assert brain.requests and brain.requests[0].scenario_id == "photography"
    assert "ecommerce_creative_context" not in brain.requests[0].metadata
    assert capturing.payloads[0]["metadata"]["photographer_profile_binding"]["profile_id"] == "general_photography"
    assert capturing.payloads[0]["metadata"]["photographer_profile_binding"]["binding_mode"] == "general"

    expected = _provider_materializations(capturing.last_result)
    for output, materialization in zip(result["outputs"], expected, strict=True):
        assert output["imagegen_prompt"] == materialization.generation_prompt
        assert output["provider_prompt_sha256"] == materialization.prompt_sha256
        assert output["reference_image_paths"] == [item["file_path"] for item in materialization.reference_assets]
        assert output["reference_input_contract"]["admitted_reference_count"] == len(materialization.reference_assets)
        assert set(output) - {
            "output_index", "output_binding_id", "imagegen_prompt", "provider_prompt_sha256", "rendering_contract",
            "reference_image_paths", "reference_input_contract", "photography_lineage_role",
        } == set()


def test_specialized_relay_fails_closed_for_disabled_templates_named_profiles_and_count_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", raising=False)
    disabled = CodexNativeImageGenPlanner(runtime_factory=ScenarioRuntime).prepare_frozen_specialized_native_imagegen_plan(
        NativeSpecializedImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                template_id="photographer_template",
                requested_image_count=1,
                platform_profile=None,
                photography_mode="single_hero",
                photographer_profile_id="general_photography",
            )
        )
    )
    assert disabled["status"] == "blocked"
    assert disabled["delivery_state"] == "no_image_created"

    with pytest.raises(CodexNativeImageGenError) as named:
        NativeSpecializedImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                template_id="photographer_template",
                requested_image_count=1,
                platform_profile=None,
                photography_mode="single_hero",
                photographer_profile_id="named_profile_not_local",
            )
        )
    assert named.value.code == "codex_native_imagegen_named_profile_project_binding_required"

    with pytest.raises(CodexNativeImageGenError) as count:
        NativeSpecializedImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                template_id="photographer_template",
                requested_image_count=2,
                platform_profile=None,
                photography_mode="professional_set",
                photographer_profile_id="general_photography",
            )
        )
    assert count.value.code == "codex_native_imagegen_count_mismatch"


def test_specialized_mcp_tool_is_explicit_and_general_contract_remains_compatible() -> None:
    assert [tool["name"] for tool in TOOL_SCHEMAS] == [
        "prepare_native_imagegen_plan",
        "prepare_frozen_specialized_native_imagegen_plan",
        "prepare_frozen_professional_native_imagegen_plan",
    ]
    unavailable_runtime = _CapturingRuntime(
        ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider(fault="unavailable")))
    )
    adapter = CodexNativeImageGenFacade(
        enabled=True,
        planner=CodexNativeImageGenPlanner(runtime_factory=lambda: unavailable_runtime),
    )
    general_to_specialist = adapter.prepare_native_imagegen_plan(
        # Existing General tool preserves its historical public block code.
        NativeImageGenPlanRequest.from_mcp_arguments(
            {
                "user_input": "No downgrade.",
                "template_id": "ecommerce_template",
                "requested_image_count": 1,
                "requested_image_size": "1024x1024",
                "reference_inputs": [],
            }
        )
    )
    assert general_to_specialist["code"] == "codex_native_imagegen_template_not_enabled"

    response = dispatch(
        adapter,
        {
            "jsonrpc": "2.0",
            "id": 133,
            "method": "tools/call",
            "params": {
                "name": "prepare_frozen_specialized_native_imagegen_plan",
                "arguments": _arguments(),
            },
        },
    )
    assert response is not None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["status"] == "blocked"  # unavailable remote Brain, before any image path
    assert payload["delivery_state"] == "no_image_created"


def test_specialized_relay_source_has_no_project_or_delivery_persistence_write_surface() -> None:
    """The conversation-only relay must never gain an indirect write path.

    This source-level guard complements the behavioral Project Mode tripwires
    in the E-Commerce parity test.  It permits normal in-memory planning and
    canonical materialization, but forbids importing or calling any project,
    candidate, review, retry, or delivery persistence surface.
    """

    repository_root = Path(__file__).resolve().parents[1]
    adapter_sources = [
        repository_root / "services" / "alchemy_codex_local_adapter" / filename
        for filename in ("contracts.py", "facade.py", "mcp_server.py", "native_planner.py", "provenance.py")
    ]
    forbidden_modules = {
        "alchemy_creative_agent_3_0.app.product_api",
        "alchemy_creative_agent_3_0.app.project_mode",
        "alchemy_creative_agent_3_0.app.project_store",
        "alchemy_creative_agent_3_0.app.review",
        "alchemy_creative_agent_3_0.app.retry",
    }
    forbidden_constructors = {
        "V3ProductApiService",
        "ProjectModeService",
        "ProjectStore",
        "CandidateStore",
        "ReviewStore",
        "RetryStore",
        "DeliveryStore",
    }
    forbidden_write_calls = {
        "create_project",
        "update_project",
        "save_project",
        "create_job",
        "update_job",
        "save_job",
        "create_candidate",
        "store_candidate",
        "record_review",
        "record_retry",
        "record_delivery",
        "write_text",
        "write_bytes",
    }

    for source_path in adapter_sources:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not (imported_modules & forbidden_modules), source_path

        call_names = {
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert not (call_names & forbidden_constructors), source_path
        assert not (call_names & forbidden_write_calls), source_path
