"""Doc118 N1 regression tests for the conversation-only native ImageGen plan."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntimeStatus
from services.alchemy_codex_local_adapter.contracts import CodexNativeImageGenError, NativeImageGenPlanRequest
from services.alchemy_codex_local_adapter.facade import CodexNativeImageGenFacade
from services.alchemy_codex_local_adapter.mcp_server import TOOL_SCHEMAS, dispatch
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


ROOT = Path(__file__).resolve().parents[1]


def _arguments(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "user_input": "Create a calm botanical still life with a cream ceramic vase.",
        "template_id": "general_template",
        "requested_image_count": 2,
        "requested_image_size": "1024x1024",
        "reference_declarations": [],
    }
    value.update(overrides)
    return value


@pytest.fixture(autouse=True)
def _isolated_general_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    """General planning may use its existing non-remote planning fallback only."""

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")


def _call_tool(adapter: CodexNativeImageGenFacade, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = dispatch(
        adapter,
        {
            "jsonrpc": "2.0",
            "id": 118,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert response is not None
    return response["result"]


def _load_plugin_launcher() -> Any:
    path = ROOT / "plugins" / "alchemy-codex-local-mode" / "scripts" / "start_mcp.py"
    spec = importlib.util.spec_from_file_location("doc118_start_mcp", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_disabled_mode_has_no_web_runtime_import_or_provider_behavior() -> None:
    adapter = CodexNativeImageGenFacade(enabled=False)
    with pytest.raises(CodexNativeImageGenError) as failure:
        adapter.prepare_native_imagegen_plan(NativeImageGenPlanRequest.from_mcp_arguments(_arguments()))
    assert failure.value.code == "codex_native_imagegen_mode_disabled"

    web_runtime = ROOT / "alchemy_creative_agent_3_0" / "app"
    assert not any("alchemy_codex_local_adapter" in path.read_text(encoding="utf-8") for path in web_runtime.rglob("*.py"))


def test_mcp_exposes_only_native_planning_and_rejects_retired_b2_tool() -> None:
    assert [tool["name"] for tool in TOOL_SCHEMAS] == ["prepare_native_imagegen_plan"]
    schema = TOOL_SCHEMAS[0]["inputSchema"]
    assert set(schema["properties"]) == {
        "user_input",
        "template_id",
        "requested_image_count",
        "requested_image_size",
        "reference_declarations",
    }
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]["reference_declarations"]["items"]["properties"]) == {
        "channel",
        "attached_in_current_codex_conversation",
    }

    result = _call_tool(CodexNativeImageGenFacade(enabled=True), "render_platform_candidate", _arguments())
    assert result["isError"] is True
    assert "codex_native_imagegen_unknown_tool" in result["content"][0]["text"]


def test_general_plan_has_exact_frozen_count_and_conversation_only_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    import alchemy_creative_agent_3_0.app.generation_router.router as generation_router

    class _ProductionProviderMustNotBeConstructed:
        def __init__(self, *_: object, **__: object) -> None:
            raise AssertionError("Doc118 planning must not construct a production image provider")

    monkeypatch.setattr(generation_router, "ProductionImageGenerationProvider", _ProductionProviderMustNotBeConstructed)
    result = CodexNativeImageGenFacade(enabled=True).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments())
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["execution_channel"] == "codex_native_imagegen"
    assert result["requested_output_count"] == 2
    assert len(result["outputs"]) == 2
    assert len({item["role_lineage"] for item in result["outputs"]}) == 2
    assert all(item["role_lineage"].startswith("template_deliverable_") for item in result["outputs"])
    assert all(item["imagegen_prompt"] and item["hard_constraints"] for item in result["outputs"])
    assert result["provenance"] == {
        **result["provenance"],
        "planner": "alchemy_v3_planning_only",
        "creative_direction_owner": "alchemy_v3_planning_only",
        "execution_channel": "codex_native_imagegen",
        "renderer": "codex_builtin_imagegen",
        "delivery_state": "conversation_only_not_certified",
    }
    serialized = json.dumps(result, ensure_ascii=False)
    assert "candidate" not in serialized.lower()
    assert "artifact" not in serialized.lower()
    assert "final_delivery" not in serialized.lower()
    assert "ecommerce_creative_context" not in serialized
    assert "copy_render_plan" not in serialized
    assert "photography" not in serialized.lower()


def test_native_planning_never_constructs_or_calls_the_web_remote_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    import alchemy_creative_agent_3_0.app.llm_brain.adapter as brain_adapter

    class _DefaultProviderMustNotBeConstructed:
        def __init__(self, *_: object, **__: object) -> None:
            raise AssertionError("Doc118 must not construct Web Mode's default remote Brain provider")

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    monkeypatch.setattr(brain_adapter, "V3LLMBrainProvider", _DefaultProviderMustNotBeConstructed)

    result = CodexNativeImageGenFacade(enabled=True).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments(requested_image_count=1))
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["provenance"]["fallback_used"] is True


def test_native_plan_does_not_create_files_or_a_delivery_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CodexNativeImageGenFacade(enabled=True).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments(requested_image_count=1))
    )
    assert result["provenance"]["delivery_state"] == "conversation_only_not_certified"
    assert list(tmp_path.iterdir()) == []
    assert not hasattr(CodexNativeImageGenFacade(enabled=True), "storage_root")


def test_required_reference_missing_blocks_before_v3_planning(monkeypatch: pytest.MonkeyPatch) -> None:
    def _must_not_start_runtime() -> object:
        raise AssertionError("missing hard reference must block before runtime planning")

    planner = CodexNativeImageGenPlanner(runtime_factory=_must_not_start_runtime)
    result = planner.prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                requested_image_count=1,
                reference_declarations=[
                    {"channel": "portrait_identity", "attached_in_current_codex_conversation": False}
                ],
            )
        )
    )
    assert result == {
        "status": "blocked",
        "code": "codex_native_imagegen_required_reference_missing",
        "message": "A required reference is not attached in the current Codex conversation.",
        "execution_channel": "codex_native_imagegen",
        "delivery_state": "no_image_created",
    }


def test_invalid_template_and_specialized_template_gates_fail_closed() -> None:
    adapter = CodexNativeImageGenFacade(enabled=True)
    invalid = adapter.prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(_arguments(template_id="unknown_template", requested_image_count=1))
    )
    ecommerce = adapter.prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                template_id="ecommerce_template",
                requested_image_count=1,
                reference_declarations=[{"channel": "product_truth", "attached_in_current_codex_conversation": True}],
            )
        )
    )
    photography = adapter.prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                template_id="photographer_template",
                requested_image_count=1,
                reference_declarations=[{"channel": "portrait_identity", "attached_in_current_codex_conversation": True}],
            )
        )
    )
    assert invalid["code"] == "codex_native_imagegen_template_invalid"
    assert ecommerce["status"] == photography["status"] == "blocked"
    assert ecommerce["code"] == photography["code"] == "codex_native_imagegen_template_not_enabled"


def test_general_role_count_mismatch_blocks_instead_of_silently_truncating() -> None:
    prompt = SimpleNamespace(visual_prompt="One whole-image native prompt.", hard_constraints=["Preserve declared truth."], text_policy="provider_native_text_forbidden")
    planned_result = SimpleNamespace(prompt_compilations=[prompt])
    runtime_result = SimpleNamespace(
        status=ScenarioRuntimeStatus.PLANNED,
        planning_result=planned_result,
        metadata={
            "template_deliverable_plan": {"deliverables": [{"role": "first"}]},
            "resolved_constraint_ledger": {"ledger_id": "ledger_n1"},
            "capability_execution_envelope": {"envelope_id": "envelope_n1"},
            "normalized_v3_job_intent": {"effective_image_count": 2},
        },
    )
    runtime = SimpleNamespace(plan_job=lambda _: runtime_result)
    planner = CodexNativeImageGenPlanner(runtime_factory=lambda: runtime)
    result = planner.prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(
            _arguments(template_id="general_template", requested_image_count=2)
        )
    )
    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_role_count_mismatch"


def test_public_contract_rejects_private_paths_jobs_provider_metadata_and_structured_secrets() -> None:
    forbidden_inputs = [
        {"job_id": "job_118"},
        {"provider_metadata": {"provider": "not-accepted"}},
        {"base_url": "https://not-accepted.invalid"},
        {"reference_declarations": [{"channel": "product_truth", "attached_in_current_codex_conversation": True, "path": "C:/private.png"}]},
        {"reference_declarations": [{"channel": "product_truth", "attached_in_current_codex_conversation": True, "api_key": "must-not-leak"}]},
        {"reference_declarations": [{"channel": "portrait_identity", "attached_in_current_codex_conversation": False, "required": False}]},
    ]
    for extra in forbidden_inputs:
        with pytest.raises(CodexNativeImageGenError) as failure:
            NativeImageGenPlanRequest.from_mcp_arguments(_arguments(requested_image_count=1, **extra))
        assert "must-not-leak" not in failure.value.message


def test_public_contract_requires_all_schema_fields_even_when_called_without_schema_validation() -> None:
    for missing_field in (
        "user_input",
        "template_id",
        "requested_image_count",
        "requested_image_size",
        "reference_declarations",
    ):
        arguments = _arguments()
        arguments.pop(missing_field)
        with pytest.raises(CodexNativeImageGenError) as failure:
            NativeImageGenPlanRequest.from_mcp_arguments(arguments)
        assert failure.value.code == "codex_native_imagegen_invalid_input"

    for field, invalid_value in (("user_input", ["not a string"]), ("template_id", 123), ("requested_image_count", True), ("requested_image_size", 1024)):
        arguments = _arguments(requested_image_count=1)
        arguments[field] = invalid_value
        with pytest.raises(CodexNativeImageGenError):
            NativeImageGenPlanRequest.from_mcp_arguments(arguments)


def test_plain_user_text_is_not_secret_scanned_but_nested_secret_keys_are_rejected() -> None:
    request = NativeImageGenPlanRequest.from_mcp_arguments(
        _arguments(requested_image_count=1, user_input="Make an image about the literal phrase api_key in a programming textbook.")
    )
    assert request.user_input.endswith("api_key in a programming textbook.")

    with pytest.raises(CodexNativeImageGenError) as failure:
        NativeImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                requested_image_count=1,
                reference_declarations=[
                    {"channel": "product_truth", "attached_in_current_codex_conversation": True, "provider_token": "must-not-leak"}
                ],
            )
        )
    assert failure.value.code == "codex_native_imagegen_sensitive_field_forbidden"
    assert "must-not-leak" not in failure.value.message


def test_reference_instructions_are_attachment_only_and_never_local_paths() -> None:
    result = CodexNativeImageGenFacade(enabled=True).prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                requested_image_count=1,
                reference_declarations=[{"channel": "product_truth", "attached_in_current_codex_conversation": True}],
            )
        )
    )
    instruction = result["outputs"][0]["reference_instructions"][0]
    assert "current-conversation attachment" in instruction
    assert "path" not in instruction.lower()
    assert "file" not in instruction.lower()


def test_active_native_source_has_no_b2_renderer_or_web_control_path() -> None:
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
        "platform_openai_gpt_image_2",
        "CodexLocalExecutionFacade",
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
    assert not (ROOT / "tests" / "test_doc117_codex_local_mode.py").exists()
    assert ".codex-local-mode-storage/" not in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_plugin_launcher_uses_an_explicit_non_secret_repository_root_and_cache_safe_config(tmp_path: Path) -> None:
    launcher = _load_plugin_launcher()
    resolved = launcher.resolve_repository_root(
        environ={"ALCHEMY_CODEX_LOCAL_REPO_ROOT": str(ROOT)},
        cwd=tmp_path,
    )
    assert resolved == ROOT
    with pytest.raises(RuntimeError, match="ALCHEMY_CODEX_LOCAL_REPO_ROOT"):
        launcher.resolve_repository_root(environ={}, cwd=tmp_path)

    config = json.loads((ROOT / "plugins" / "alchemy-codex-local-mode" / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["alchemy_local_mode"]
    assert server["args"] == ["scripts/start_mcp.py", "--enable-native-imagegen"]
    assert server["cwd"] == "."
    assert server["env_vars"] == ["ALCHEMY_CODEX_LOCAL_REPO_ROOT"]
