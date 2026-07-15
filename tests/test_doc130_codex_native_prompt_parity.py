"""Doc130 regression tests for canonical Provider Prompt parity in Local Mode."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.generation_router import (
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.llm_brain.prompts import _compact_specialized_assets
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from services.alchemy_codex_local_adapter.contracts import CodexNativeImageGenError, NativeImageGenPlanRequest
from services.alchemy_codex_local_adapter.facade import CodexNativeImageGenFacade
from services.alchemy_codex_local_adapter.mcp_server import TOOL_SCHEMAS, dispatch
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


ROOT = Path(__file__).resolve().parents[1]


def _arguments(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "user_input": "Create a calm botanical still life with a cream ceramic vase.",
        "template_id": "general_template",
        "requested_image_count": 1,
        "requested_image_size": "1024x1024",
        "reference_inputs": [],
    }
    value.update(overrides)
    return value


@pytest.fixture(autouse=True)
def _isolated_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")


def _canonical_runtime_result(*, count: int = 1, uploaded_assets: list[Any] | None = None) -> SimpleNamespace:
    """Create an otherwise real V3 planned result with a frozen remote answer.

    Network is deliberately not involved in unit tests. The Local Mode planner
    receives exactly the planning shape it requires in production, including a
    valid remote Brain provenance record and its same-count image directions.
    """

    planned = ScenarioRuntime().plan_job(
        {
            "user_input": _arguments()["user_input"],
            "scenario_selection": {
                "scenario_id": "general_creative",
                "parameters": {"requested_image_count": count},
            },
            "uploaded_assets": uploaded_assets or [],
            "metadata": {
                "template_id": "general_template",
                "requested_image_count": count,
                "requested_image_size": "1024x1024",
            },
        }
    )
    assert planned.status == ScenarioRuntimeStatus.PLANNED
    result = copy.deepcopy(planned)
    directions = [f"Remote Brain whole-image direction {index}." for index in range(1, count + 1)]
    remote_brain = {
        "llm_used": True,
        "fallback_used": False,
        "provider": "remote_test_brain",
        "model": "remote-test-model",
        "image_set_plan": {"image_count": count, "shot_plan": directions},
    }
    result.metadata["llm_brain"] = remote_brain
    for plan in result.planning_result.generation_plans:
        plan.metadata = {
            **plan.metadata,
            "llm_brain": remote_brain,
            "require_real_images": True,
            "real_image_generation": True,
            "requested_image_count": count,
            "requested_image_size": "1024x1024",
        }
    return SimpleNamespace(
        status=ScenarioRuntimeStatus.PLANNED,
        planning_result=result.planning_result,
        metadata=result.metadata,
    )


def _planner_for(result: SimpleNamespace) -> CodexNativeImageGenPlanner:
    return CodexNativeImageGenPlanner(runtime_factory=lambda: SimpleNamespace(plan_job=lambda _: result))


def _call_tool(adapter: CodexNativeImageGenFacade, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = dispatch(
        adapter,
        {
            "jsonrpc": "2.0",
            "id": 130,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert response is not None
    return response["result"]


def _load_plugin_launcher() -> Any:
    path = ROOT / "plugins" / "alchemy-codex-local-mode" / "scripts" / "start_mcp.py"
    spec = importlib.util.spec_from_file_location("doc130_start_mcp", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plugin_launcher_exposes_only_canonical_prompt_tool() -> None:
    launcher = ROOT / "plugins" / "alchemy-codex-local-mode" / "scripts" / "start_mcp.py"
    requests = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        ]
    ) + "\n"
    completed = subprocess.run(
        [sys.executable, str(launcher), "--enable-native-imagegen"],
        cwd=ROOT,
        env={**os.environ, "ALCHEMY_CODEX_LOCAL_REPO_ROOT": str(ROOT)},
        input=requests,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert responses[0]["result"]["serverInfo"]["version"] == "0.6.0-doc131-reference-parity"
    assert [tool["name"] for tool in responses[1]["result"]["tools"]] == ["prepare_native_imagegen_plan"]


def test_mcp_schema_exposes_no_provider_or_artifact_controls() -> None:
    assert [tool["name"] for tool in TOOL_SCHEMAS] == ["prepare_native_imagegen_plan"]
    schema = TOOL_SCHEMAS[0]["inputSchema"]
    assert set(schema["properties"]) == {
        "user_input",
        "template_id",
        "requested_image_count",
        "requested_image_size",
        "reference_inputs",
    }
    result = _call_tool(CodexNativeImageGenFacade(enabled=True), "render_platform_candidate", _arguments())
    assert result["isError"] is True
    assert "codex_native_imagegen_unknown_tool" in result["content"][0]["text"]


def test_local_mode_projects_the_exact_web_provider_final_prompt_and_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_result = _canonical_runtime_result()
    result = _planner_for(runtime_result).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments())
    )
    assert result["status"] == "planned_for_codex_native_imagegen"
    output = result["outputs"][0]

    plan = runtime_result.planning_result
    asset = plan.series_plan.assets[0]
    request = build_provider_generation_request(
        asset_spec=asset,
        layout_plan=plan.layout_plans[0],
        prompt_compilation=plan.prompt_compilations[0],
        condition_plan=plan.condition_plans[0],
        generation_plan=plan.generation_plans[0],
        job_id=plan.creative_job.job_id,
    )
    provider = ProductionImageGenerationProvider(output_store=object())
    expected = provider.materialize_final_prompt(request)
    monkeypatch.setattr(provider, "_select_provider", lambda _: "openai_gpt_image")
    app_request, _provider_name, _references = provider._build_app_request(request)

    assert output["imagegen_prompt"] == expected.generation_prompt
    assert output["imagegen_prompt"] == app_request.prompt_plan.variables["generation_prompt"]
    assert output["provider_prompt_sha256"] == expected.prompt_sha256
    assert output["provider_prompt_sha256"] == app_request.prompt_plan.variables["provider_prompt_sha256"]
    assert output["provider_prompt_sha256"] == hashlib.sha256(output["imagegen_prompt"].encode("utf-8")).hexdigest()
    assert output["rendering_contract"] == {
        "model": "gpt-image-2",
        "size": app_request.prompt_plan.size,
        "quality": app_request.prompt_plan.quality,
        "output_format": app_request.prompt_plan.output_format,
    }


def test_local_mode_uses_the_same_generation_request_factory_as_web_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_result = _canonical_runtime_result()
    seen: list[dict[str, Any]] = []
    original = ProductionImageGenerationProvider.materialize_final_prompt

    def _observe(self: ProductionImageGenerationProvider, request: Any):
        seen.append(dict(request.metadata))
        return original(self, request)

    monkeypatch.setattr(ProductionImageGenerationProvider, "materialize_final_prompt", _observe)
    result = _planner_for(runtime_result).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments())
    )
    assert result["status"] == "planned_for_codex_native_imagegen"
    assert len(seen) == 1
    assert seen[0]["capability_execution_envelope"]
    assert seen[0]["resolved_constraint_ledger"]
    assert seen[0]["require_real_images"] is True
    assert seen[0]["llm_brain"]["fallback_used"] is False


def test_local_mode_never_selects_or_calls_an_upstream_image_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_result = _canonical_runtime_result()

    def _must_not_select(self: ProductionImageGenerationProvider, _: Any) -> str:
        raise AssertionError("canonical Local Mode must not select an upstream provider")

    def _must_not_create_client(self: ProductionImageGenerationProvider, _: Any) -> Any:
        raise AssertionError("canonical Local Mode must not construct an upstream client")

    monkeypatch.setattr(ProductionImageGenerationProvider, "_select_provider", _must_not_select)
    monkeypatch.setattr(ProductionImageGenerationProvider, "_app_provider", _must_not_create_client)
    result = _planner_for(runtime_result).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments())
    )
    assert result["status"] == "planned_for_codex_native_imagegen"


def test_remote_brain_fallback_blocks_before_prompt_projection() -> None:
    runtime_result = _canonical_runtime_result()
    runtime_result.metadata["llm_brain"] = {"llm_used": False, "fallback_used": True}
    result = _planner_for(runtime_result).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments())
    )
    assert result["code"] == "codex_native_imagegen_remote_brain_required"


def test_count_mismatch_blocks_without_silent_truncation() -> None:
    runtime_result = _canonical_runtime_result()
    runtime_result.metadata["normalized_v3_job_intent"]["effective_image_count"] = 2
    result = _planner_for(runtime_result).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments(requested_image_count=1))
    )
    assert result["code"] == "codex_native_imagegen_count_mismatch"


def _write_png(path: Path, *, color: tuple[int, int, int] = (31, 99, 181)) -> Path:
    from PIL import Image

    Image.new("RGB", (24, 18), color=color).save(path, format="PNG")
    return path


def test_reference_path_reuses_web_uploaded_asset_admission_and_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _write_png(tmp_path / "blue-reference.png")
    captured: dict[str, Any] = {}

    class _CapturingRuntime:
        def plan_job(self, payload: dict[str, Any]) -> SimpleNamespace:
            captured.update(payload)
            runtime_result = _canonical_runtime_result(uploaded_assets=list(payload["uploaded_assets"]))
            captured["runtime_result"] = runtime_result
            return runtime_result

    result = CodexNativeImageGenPlanner(runtime_factory=_CapturingRuntime).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(
            _arguments(reference_inputs=[{"channel": "product_truth", "file_path": str(source)}])
        )
    )
    assert result["status"] == "planned_for_codex_native_imagegen"
    assert captured["uploaded_assets"][0].file_path == str(source.resolve())
    assert captured["uploaded_assets"][0].metadata["provider_input_required"] is True

    plan = captured["runtime_result"].planning_result
    asset = plan.series_plan.assets[0]
    request = build_provider_generation_request(
        asset_spec=asset,
        layout_plan=plan.layout_plans[0],
        prompt_compilation=plan.prompt_compilations[0],
        condition_plan=plan.condition_plans[0],
        generation_plan=plan.generation_plans[0],
        job_id=plan.creative_job.job_id,
    )
    provider = ProductionImageGenerationProvider(output_store=object())
    expected = provider.materialize_final_prompt(request)
    output = result["outputs"][0]
    assert output["imagegen_prompt"] == expected.generation_prompt
    assert output["provider_prompt_sha256"] == expected.prompt_sha256
    assert output["reference_image_paths"] == [item["file_path"] for item in expected.reference_assets]
    assert output["reference_input_contract"] == {
        "operation": "image_edit",
        "declared_reference_count": 1,
        "admitted_reference_count": 1,
        "source_sha256": [hashlib.sha256(source.read_bytes()).hexdigest()],
    }


def test_multiple_same_channel_references_preserve_web_asset_order_and_prompt_parity(tmp_path: Path) -> None:
    front = _write_png(tmp_path / "product-front.png")
    back = _write_png(tmp_path / "product-back.png", color=(181, 99, 31))
    captured: dict[str, Any] = {}

    class _CapturingRuntime:
        def plan_job(self, payload: dict[str, Any]) -> SimpleNamespace:
            captured.update(payload)
            return _canonical_runtime_result(uploaded_assets=list(payload["uploaded_assets"]))

    request = NativeImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            reference_inputs=[
                {"channel": "product_truth", "file_path": str(front)},
                {"channel": "product_truth", "file_path": str(back)},
            ]
        )
    )
    result = CodexNativeImageGenPlanner(runtime_factory=_CapturingRuntime).prepare_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert [item.file_path for item in captured["uploaded_assets"]] == [str(front.resolve()), str(back.resolve())]
    assert [item.role.value for item in captured["uploaded_assets"]] == ["product_reference", "product_reference"]
    assert result["outputs"][0]["reference_input_contract"] == {
        "operation": "image_edit",
        "declared_reference_count": 2,
        "admitted_reference_count": 2,
        "source_sha256": [
            hashlib.sha256(front.read_bytes()).hexdigest(),
            hashlib.sha256(back.read_bytes()).hexdigest(),
        ],
    }
    assert result["outputs"][0]["reference_image_paths"] == [str(front.resolve()), str(back.resolve())]


def test_reference_path_is_not_sent_to_remote_brain_compact_payload(tmp_path: Path) -> None:
    source = _write_png(tmp_path / "brain-private.png")
    request = NativeImageGenPlanRequest.from_mcp_arguments(
        _arguments(reference_inputs=[{"channel": "portrait_identity", "file_path": str(source)}])
    )
    asset = CodexNativeImageGenPlanner._uploaded_assets(request)[0].model_dump(mode="json")
    compact = _compact_specialized_assets([asset])
    assert str(source.resolve()) not in json.dumps(compact)
    assert compact[0]["asset_id"] == asset["asset_id"]
    assert compact[0]["role"] == "face_reference"


def test_missing_or_corrupt_reference_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(CodexNativeImageGenError) as failure:
        NativeImageGenPlanRequest.from_mcp_arguments(
            _arguments(reference_inputs=[{"channel": "product_truth", "file_path": str(tmp_path / "missing.png")}])
        )
    assert failure.value.code == "codex_native_imagegen_reference_path_unavailable"

    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")
    corrupt_request = NativeImageGenPlanRequest.from_mcp_arguments(
        _arguments(reference_inputs=[{"channel": "product_truth", "file_path": str(corrupt)}])
    )
    result = _planner_for(
        _canonical_runtime_result(uploaded_assets=CodexNativeImageGenPlanner._uploaded_assets(corrupt_request))
    ).prepare_native_imagegen_plan(corrupt_request)
    assert result["code"] == "codex_native_imagegen_canonical_prompt_unavailable"


def test_general_only_template_gate_is_preserved() -> None:
    adapter = CodexNativeImageGenFacade(enabled=True)
    for template_id in ("ecommerce_template", "photographer_template"):
        result = adapter.prepare_native_imagegen_plan(
            NativeImageGenPlanRequest.from_mcp_arguments(_arguments(template_id=template_id))
        )
        assert result["code"] == "codex_native_imagegen_template_not_enabled"


def test_disabled_mode_never_imports_web_runtime() -> None:
    adapter = CodexNativeImageGenFacade(enabled=False)
    with pytest.raises(CodexNativeImageGenError) as failure:
        adapter.prepare_native_imagegen_plan(NativeImageGenPlanRequest.from_mcp_arguments(_arguments()))
    assert failure.value.code == "codex_native_imagegen_mode_disabled"
    web_runtime = ROOT / "alchemy_creative_agent_3_0" / "app"
    assert not any("alchemy_codex_local_adapter" in path.read_text(encoding="utf-8") for path in web_runtime.rglob("*.py"))


def test_public_contract_rejects_private_paths_provider_metadata_and_secrets() -> None:
    for extra in (
        {"job_id": "job_130"},
        {"provider_metadata": {"provider": "not-accepted"}},
        {"base_url": "https://not-accepted.invalid"},
        {"reference_inputs": [{"channel": "product_truth", "file_path": "C:/private.png", "path": "C:/private.png"}]},
        {"reference_inputs": [{"channel": "product_truth", "file_path": "C:/private.png", "api_key": "must-not-leak"}]},
    ):
        with pytest.raises(CodexNativeImageGenError) as failure:
            NativeImageGenPlanRequest.from_mcp_arguments(_arguments(**extra))
        assert "must-not-leak" not in failure.value.message


def test_local_mode_creates_no_files_or_delivery_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = _planner_for(_canonical_runtime_result()).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments())
    )
    assert result["provenance"]["delivery_state"] == "conversation_only_not_certified"
    assert result["provenance"]["canonical_provider_prompt_projected"] is True
    assert list(tmp_path.iterdir()) == []


def test_plugin_skill_requires_verbatim_canonical_prompt() -> None:
    skill = (ROOT / "plugins" / "alchemy-codex-local-mode" / "skills" / "alchemy-local-run" / "SKILL.md").read_text(encoding="utf-8")
    assert "imagegen_prompt" in skill
    assert "verbatim" in skill
    assert "creative_direction_brief" not in skill
    assert "author exactly" not in skill


def test_active_source_has_no_platform_api_web_fallback_or_artifact_import() -> None:
    executable_paths = [
        *(ROOT / "services" / "alchemy_codex_local_adapter").glob("*.py"),
        ROOT / "plugins" / "alchemy-codex-local-mode" / ".codex-plugin" / "plugin.json",
        ROOT / "plugins" / "alchemy-codex-local-mode" / ".mcp.json",
        ROOT / "plugins" / "alchemy-codex-local-mode" / "scripts" / "start_mcp.py",
    ]
    active_source = "\n".join(path.read_text(encoding="utf-8") for path in executable_paths)
    for forbidden in (
        "api.openai.com",
        "OPENAI_API_KEY",
        "ALCHEMY_CODEX_LOCAL_IMAGE_API_KEY_FILE",
        "Aiself",
        "PlatformImageRenderer",
        "subprocess",
        "selenium",
        "playwright",
        "browser",
        "session",
        "cache",
    ):
        assert forbidden not in active_source
    assert not (ROOT / "services" / "alchemy_codex_local_adapter" / "platform_renderer.py").exists()
    assert not (ROOT / "services" / "alchemy_codex_local_adapter" / "artifact_import.py").exists()


def test_plugin_launcher_requires_a_non_secret_checkout_root(tmp_path: Path) -> None:
    launcher = _load_plugin_launcher()
    assert launcher.resolve_repository_root(environ={"ALCHEMY_CODEX_LOCAL_REPO_ROOT": str(ROOT)}, cwd=tmp_path) == ROOT
    with pytest.raises(RuntimeError, match="ALCHEMY_CODEX_LOCAL_REPO_ROOT"):
        launcher.resolve_repository_root(environ={}, cwd=tmp_path)


def test_plugin_launcher_loads_only_an_explicit_existing_environment_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _load_plugin_launcher()
    env_file = tmp_path / "brain.env"
    env_file.write_text("V3_LLM_BRAIN_REMOTE_ENABLED=true\n", encoding="utf-8")
    monkeypatch.delenv("V3_LLM_BRAIN_REMOTE_ENABLED", raising=False)
    monkeypatch.setenv("ALCHEMY_CODEX_LOCAL_ENV_FILE", str(env_file))
    launcher.load_runtime_environment()
    assert os.environ["V3_LLM_BRAIN_REMOTE_ENABLED"] == "true"

    monkeypatch.setenv("ALCHEMY_CODEX_LOCAL_ENV_FILE", str(tmp_path / "missing.env"))
    with pytest.raises(RuntimeError, match="ALCHEMY_CODEX_LOCAL_ENV_FILE"):
        launcher.load_runtime_environment()
