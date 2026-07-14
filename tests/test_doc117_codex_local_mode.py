from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from services.alchemy_codex_local_adapter import (
    CodexLocalExecutionFacade,
    LOCAL_CREATIVE_DIRECTION_OWNER,
    LOCAL_EXECUTION_CHANNEL,
    LOCAL_RENDERER,
    LocalJobSpec,
    LocalModeAdapterError,
    LocalModeDisabledError,
    PLATFORM_OPENAI_GPT_IMAGE_2_MODEL,
    PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER,
    PlatformImageRenderer,
)
from services.alchemy_codex_local_adapter.artifact_import import LocalArtifactImporter
from services.alchemy_codex_local_adapter.contracts import PlatformRenderedImage
from services.alchemy_codex_local_adapter.mcp_server import TOOL_SCHEMAS, dispatch
from services.alchemy_codex_local_adapter.platform_renderer import (
    IMAGE_GENERATIONS_PATH,
    LOCAL_IMAGE_API_KEY_FILE_ENV,
    OFFICIAL_PLATFORM_API_BASE,
    PlatformHttpResponse,
)


ROOT = Path(__file__).resolve().parents[1]
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL+XQAAAABJRU5ErkJggg=="
)
ONE_PIXEL_JPEG = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"
TEST_KEY = "local-contract-test-key-0123456789"


class FakeTransport:
    def __init__(self, responses: list[PlatformHttpResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def post_json(self, *, url: str, headers: object, payload: object, timeout_s: float) -> PlatformHttpResponse:
        self.calls.append({"url": url, "headers": dict(headers), "payload": dict(payload), "timeout_s": timeout_s})
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _api_response(image_bytes: bytes, *, status: int = 200) -> PlatformHttpResponse:
    body = json.dumps({"data": [{"b64_json": base64.b64encode(image_bytes).decode("ascii")}]}).encode("utf-8")
    return PlatformHttpResponse(status_code=status, headers={"x-request-id": "req_doc117"}, body=body)


def _spec(job_id: str, role_ids: tuple[str, ...] = ("output_1",)) -> LocalJobSpec:
    return LocalJobSpec(
        job_id=job_id,
        project_id="project_doc117",
        template_id="general_template",
        scenario_id="general_creative",
        protected_user_intent="Create one natural whole-image study from the permitted reference.",
        role_ids=role_ids,
        normalized_intent={"requested_image_count": len(role_ids), "prompt_text": "api_key is ordinary user text here"},
        capability_execution_envelope={"envelope_id": "envelope_doc117", "constraints": {"safe": True}},
        resolved_constraint_ledger={"ledger_id": "ledger_doc117", "accepted": ["preserve product truth"]},
        permitted_reference_files=("reference/product.png",),
    )


def _prepare_job(adapter: CodexLocalExecutionFacade, spec: LocalJobSpec) -> None:
    adapter.create_local_job(spec)
    for role_id in spec.role_ids:
        adapter.record_creative_direction(spec.job_id, role_id, f"Natural whole-image direction for {role_id}.")


def _contract_renderer(transport: FakeTransport) -> PlatformImageRenderer:
    return PlatformImageRenderer(transport=transport, contract_test_mode=True)


def _write_key_file(tmp_path: Path, *, name: str = "dedicated-key.txt") -> tuple[Path, Path]:
    user_home = tmp_path / "user-home"
    user_home.mkdir()
    key_path = user_home / name
    key_path.write_text(TEST_KEY, encoding="utf-8")
    return user_home, key_path


def test_disabled_mode_has_no_local_job_path_or_web_runtime_import() -> None:
    adapter = CodexLocalExecutionFacade("ignored", enabled=False)
    with pytest.raises(LocalModeDisabledError) as exc_info:
        adapter.create_local_job(_spec("job_doc117_disabled"))
    assert exc_info.value.code == "codex_local_mode_disabled"

    web_runtime = ROOT / "alchemy_creative_agent_3_0" / "app"
    assert not any("alchemy_codex_local_adapter" in path.read_text(encoding="utf-8") for path in web_runtime.rglob("*.py"))


def test_local_job_rejects_nested_credential_key_before_persistence(tmp_path: Path) -> None:
    sensitive_envelope = {"envelope_id": "valid", "nested": {"API-Key": "must-not-persist"}}
    with pytest.raises(LocalModeAdapterError) as failure:
        LocalJobSpec(
            **{
                **_spec("job_doc117_sensitive").storage_record(),
                "capability_execution_envelope": sensitive_envelope,
            }
        )
    assert failure.value.code == "codex_local_sensitive_structured_field_forbidden"
    assert not (tmp_path / "local-store" / "local_jobs.json").exists()


def test_local_job_rejects_credential_key_in_constraint_ledger() -> None:
    with pytest.raises(LocalModeAdapterError) as failure:
        LocalJobSpec(
            **{
                **_spec("job_doc117_ledger_sensitive").storage_record(),
                "resolved_constraint_ledger": {"rule": {"provider_token": "must-not-persist"}},
            }
        )
    assert failure.value.code == "codex_local_sensitive_structured_field_forbidden"


def test_mcp_rejects_credential_key_before_creating_a_local_job(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    arguments = _spec("job_doc117_mcp_sensitive").storage_record()
    arguments["capability_execution_envelope"] = {"nested": {"credential": "must-not-persist"}}
    response = dispatch(
        adapter,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "create_local_job", "arguments": arguments},
        },
    )
    assert response is not None
    assert response["result"]["isError"] is True
    assert "codex_local_sensitive_structured_field_forbidden" in response["result"]["content"][0]["text"]
    assert not (tmp_path / "local-store" / "local_jobs.json").exists()


def test_normal_contract_persists_and_recovers_without_sensitive_data(tmp_path: Path) -> None:
    storage = tmp_path / "local-store"
    adapter = CodexLocalExecutionFacade(storage, enabled=True)
    spec = _spec("job_doc117_persist")
    adapter.create_local_job(spec)

    on_disk = (storage / "local_jobs.json").read_text(encoding="utf-8")
    assert "envelope_doc117" in on_disk
    assert "ledger_doc117" in on_disk
    assert "must-not-persist" not in on_disk
    assert '"api_key"' not in on_disk.lower()
    assert '"provider_token"' not in on_disk.lower()

    contract = CodexLocalExecutionFacade(storage, enabled=True).get_render_contract(spec.job_id)
    assert contract["capability_execution_envelope"] == {"envelope_id": "envelope_doc117", "constraints": {"safe": True}}
    assert contract["resolved_constraint_ledger"] == {"ledger_id": "ledger_doc117", "accepted": ["preserve product truth"]}
    assert contract["normalized_intent"]["prompt_text"] == "api_key is ordinary user text here"


def test_historical_local_job_json_is_scrubbed_before_recovery(tmp_path: Path) -> None:
    storage = tmp_path / "local-store"
    storage.mkdir()
    legacy = {
        "job_doc117_legacy": {
            "contract": {
                **_spec("job_doc117_legacy").storage_record(),
                "capability_execution_envelope": {"envelope_id": "legacy", "api_key": "legacy-secret-value"},
                "resolved_constraint_ledger": {"ledger_id": "legacy", "provider_token": "legacy-token-value"},
            },
            "provenance": {"execution_channel": "codex_local", "authorization": "legacy-auth-value"},
            "creative_directions": [],
            "candidates": [],
            "status": "awaiting_creative_direction",
        }
    }
    jobs_path = storage / "local_jobs.json"
    jobs_path.write_text(json.dumps(legacy), encoding="utf-8")

    adapter = CodexLocalExecutionFacade(storage, enabled=True)
    contract = adapter.get_render_contract("job_doc117_legacy")
    status = adapter.get_local_job_status("job_doc117_legacy")
    scrubbed = jobs_path.read_text(encoding="utf-8")
    assert contract["capability_execution_envelope"] == {"envelope_id": "legacy"}
    assert contract["resolved_constraint_ledger"] == {"ledger_id": "legacy"}
    assert status["provenance"] == {"execution_channel": "codex_local"}
    assert "legacy-secret-value" not in scrubbed
    assert "legacy-token-value" not in scrubbed
    assert "legacy-auth-value" not in scrubbed
    assert '"api_key":' not in scrubbed.lower()
    assert '"provider_token":' not in scrubbed.lower()
    assert '"authorization":' not in scrubbed.lower()


def test_dedicated_key_reader_does_not_inherit_web_provider_environment() -> None:
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    with pytest.raises(LocalModeAdapterError) as failure:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            transport=transport,
            environment={"OPENAI_API_KEY": "web-key", "OPENAI_BASE_URL": "https://web.invalid/v1"},
            user_home=ROOT.parent,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert failure.value.code == "codex_local_platform_renderer_key_missing"
    assert transport.calls == []


def test_live_render_requires_explicit_opt_in_before_transport(tmp_path: Path) -> None:
    user_home, key_path = _write_key_file(tmp_path)
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    with pytest.raises(LocalModeAdapterError) as failure:
        PlatformImageRenderer(
            transport=transport,
            environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(key_path)},
            user_home=user_home,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert failure.value.code == "codex_local_platform_renderer_disabled"
    assert transport.calls == []


def test_live_render_missing_key_file_blocks_before_transport(tmp_path: Path) -> None:
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    with pytest.raises(LocalModeAdapterError) as failure:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            transport=transport,
            environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(tmp_path / "not-there.txt")},
            user_home=tmp_path,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert failure.value.code == "codex_local_platform_renderer_key_file_unreadable"
    assert transport.calls == []


def test_live_render_invalid_key_file_blocks_before_transport(tmp_path: Path) -> None:
    user_home = tmp_path / "user-home"
    user_home.mkdir()
    key_path = user_home / "empty-key.txt"
    key_path.write_text("\n", encoding="utf-8")
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    with pytest.raises(LocalModeAdapterError) as failure:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            transport=transport,
            environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(key_path)},
            user_home=user_home,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert failure.value.code == "codex_local_platform_renderer_key_file_invalid"
    assert transport.calls == []


def test_key_file_must_be_below_user_home(tmp_path: Path) -> None:
    user_home = tmp_path / "user-home"
    user_home.mkdir()
    external = tmp_path / "external-key.txt"
    external.write_text(TEST_KEY, encoding="utf-8")
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    with pytest.raises(LocalModeAdapterError) as failure:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            transport=transport,
            environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(external)},
            user_home=user_home,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert failure.value.code == "codex_local_platform_renderer_key_file_invalid"
    assert transport.calls == []


def test_key_file_must_be_outside_repository(tmp_path: Path) -> None:
    user_home = tmp_path / "user-home"
    repository = user_home / "repository"
    repository.mkdir(parents=True)
    key_path = repository / "dedicated-key.txt"
    key_path.write_text(TEST_KEY, encoding="utf-8")
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    with pytest.raises(LocalModeAdapterError) as failure:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            transport=transport,
            environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(key_path)},
            user_home=user_home,
            repository_root=repository,
        ).render(direction="One image.", role_id="output_1")
    assert failure.value.code == "codex_local_platform_renderer_key_file_invalid"
    assert transport.calls == []


def test_key_file_must_not_be_a_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_home, key_path = _write_key_file(tmp_path)
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda candidate: candidate == key_path or original_is_symlink(candidate))
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    with pytest.raises(LocalModeAdapterError) as failure:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            transport=transport,
            environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(key_path)},
            user_home=user_home,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert failure.value.code == "codex_local_platform_renderer_key_file_invalid"
    assert transport.calls == []


def test_base_url_override_is_forbidden() -> None:
    with pytest.raises(LocalModeAdapterError) as failure:
        PlatformImageRenderer(base_url="https://example.invalid/v1")
    assert failure.value.code == "codex_local_platform_renderer_base_url_forbidden"


def test_mock_platform_success_materializes_hash_binds_role_and_stays_not_certified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "web-provider-key-must-not-be-read")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://web-gateway.invalid/v1")
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    _prepare_job(adapter, _spec("job_doc117_happy"))
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    candidate = adapter.render_platform_candidate("job_doc117_happy", "output_1", renderer=_contract_renderer(transport))

    assert candidate.imported_path.exists()
    assert candidate.sha256 == hashlib.sha256(ONE_PIXEL_PNG).hexdigest()
    assert candidate.provenance["execution_channel"] == LOCAL_EXECUTION_CHANNEL
    assert candidate.provenance["creative_direction_owner"] == LOCAL_CREATIVE_DIRECTION_OWNER
    assert candidate.provenance["renderer"] == PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER == LOCAL_RENDERER
    assert candidate.provenance["renderer_model"] == PLATFORM_OPENAI_GPT_IMAGE_2_MODEL
    assert candidate.provenance["fallback_used"] is False
    assert candidate.provenance["certification_state"] == "not_certified_development_artifact"
    serialized = json.dumps(candidate.provenance)
    assert "web-provider-key-must-not-be-read" not in serialized
    assert "Natural whole-image direction" not in serialized

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == f"{OFFICIAL_PLATFORM_API_BASE}{IMAGE_GENERATIONS_PATH}"
    assert call["payload"] == {
        "model": "gpt-image-2",
        "prompt": "Natural whole-image direction for output_1.",
        "n": 1,
        "size": "auto",
        "quality": "auto",
        "background": "auto",
        "output_format": "png",
    }
    assert "web-provider-key-must-not-be-read" not in str(call["headers"])
    staging = tmp_path / "local-store" / "_controlled_staging" / "platform"
    assert not list(staging.glob("*"))

    status = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True).get_local_job_status("job_doc117_happy")
    assert status["candidates"][0]["sha256"] == candidate.sha256
    assert status["certified_delivery"] is False
    assert status["final_deliveries"] == []
    with pytest.raises(LocalModeAdapterError) as finalization:
        CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True).finalize_local_job("job_doc117_happy")
    assert finalization.value.code == "codex_local_shared_runtime_integration_pending"


def test_live_key_file_can_reach_only_injected_transport(tmp_path: Path) -> None:
    user_home, key_path = _write_key_file(tmp_path)
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    rendered = PlatformImageRenderer(
        live_platform_opt_in=True,
        transport=transport,
        environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(key_path)},
        user_home=user_home,
        repository_root=ROOT,
    ).render(direction="One image.", role_id="output_1")
    assert rendered.renderer == PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER
    assert len(transport.calls) == 1
    assert transport.calls[0]["url"] == f"{OFFICIAL_PLATFORM_API_BASE}{IMAGE_GENERATIONS_PATH}"


def test_platform_502_is_bounded_and_has_no_fallback(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "store", enabled=True)
    spec = _spec("job_doc117_502")
    _prepare_job(adapter, spec)
    transport = FakeTransport([PlatformHttpResponse(status_code=502, headers={}, body=b"{}")])
    with pytest.raises(LocalModeAdapterError) as failure:
        adapter.render_platform_candidate(spec.job_id, "output_1", renderer=_contract_renderer(transport))
    assert failure.value.code == "codex_local_platform_renderer_upstream_502"
    assert len(transport.calls) == 1
    assert adapter.get_local_job_status(spec.job_id)["candidates"] == []


def test_platform_timeout_is_bounded_and_has_no_fallback(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "store", enabled=True)
    spec = _spec("job_doc117_timeout")
    _prepare_job(adapter, spec)
    transport = FakeTransport([TimeoutError()])
    with pytest.raises(LocalModeAdapterError) as failure:
        adapter.render_platform_candidate(spec.job_id, "output_1", renderer=_contract_renderer(transport))
    assert failure.value.code == "codex_local_platform_renderer_timeout"
    assert len(transport.calls) == 1


def test_platform_empty_response_is_bounded_and_has_no_fallback(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "store", enabled=True)
    spec = _spec("job_doc117_empty")
    _prepare_job(adapter, spec)
    transport = FakeTransport([PlatformHttpResponse(status_code=200, headers={}, body=b'{"data":[]}')])
    with pytest.raises(LocalModeAdapterError) as failure:
        adapter.render_platform_candidate(spec.job_id, "output_1", renderer=_contract_renderer(transport))
    assert failure.value.code == "codex_local_platform_renderer_empty_response"
    assert len(transport.calls) == 1


def test_platform_mime_mismatch_is_bounded_and_has_no_fallback(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "store", enabled=True)
    spec = _spec("job_doc117_mime")
    _prepare_job(adapter, spec)
    transport = FakeTransport([_api_response(ONE_PIXEL_JPEG)])
    with pytest.raises(LocalModeAdapterError) as failure:
        adapter.render_platform_candidate(spec.job_id, "output_1", renderer=_contract_renderer(transport))
    assert failure.value.code == "codex_local_platform_renderer_mime_mismatch"
    assert len(transport.calls) == 1


def test_missing_controlled_staging_artifact_fails_closed(tmp_path: Path) -> None:
    spec = _spec("job_doc117_missing")
    importer = LocalArtifactImporter(tmp_path / "missing-store")
    staged = importer.stage_platform_response(PlatformRenderedImage(image_bytes=ONE_PIXEL_PNG, request_summary={}, response_summary={}))
    staged.source_path.unlink()
    with pytest.raises(LocalModeAdapterError) as failure:
        importer.import_staged_platform_candidate(job_id=spec.job_id, role_id="output_1", contract=spec, staged=staged)
    assert failure.value.code == "codex_local_artifact_missing"


def test_duplicate_artifact_fails_closed(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    spec = _spec("job_doc117_duplicate")
    _prepare_job(adapter, spec)
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG), _api_response(ONE_PIXEL_PNG)])
    adapter.render_platform_candidate(spec.job_id, "output_1", renderer=_contract_renderer(transport))
    with pytest.raises(LocalModeAdapterError) as failure:
        adapter.render_platform_candidate(spec.job_id, "output_1", renderer=_contract_renderer(transport))
    assert failure.value.code == "codex_local_artifact_duplicate"


def test_cross_job_artifact_fails_closed(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    first = _spec("job_doc117_one")
    second = _spec("job_doc117_two")
    _prepare_job(adapter, first)
    _prepare_job(adapter, second)
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG), _api_response(ONE_PIXEL_PNG)])
    adapter.render_platform_candidate(first.job_id, "output_1", renderer=_contract_renderer(transport))
    with pytest.raises(LocalModeAdapterError) as failure:
        adapter.render_platform_candidate(second.job_id, "output_1", renderer=_contract_renderer(transport))
    assert failure.value.code == "codex_local_artifact_cross_job"


def test_each_explicit_role_makes_one_bounded_platform_request(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    spec = _spec("job_doc117_multi", ("output_1", "output_2"))
    _prepare_job(adapter, spec)
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG + b"a"), _api_response(ONE_PIXEL_PNG + b"b")])
    candidates = adapter.render_platform_candidates(spec.job_id, ["output_1", "output_2"], renderer=_contract_renderer(transport))
    assert [candidate.role_id for candidate in candidates] == ["output_1", "output_2"]
    assert len(transport.calls) == 2
    assert all(call["payload"]["n"] == 1 for call in transport.calls)
    assert all(call["payload"]["model"] == "gpt-image-2" for call in transport.calls)


def test_role_bound_direction_and_local_rendering_recipes_are_rejected(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    adapter.create_local_job(_spec("job_doc117_role"))
    with pytest.raises(LocalModeAdapterError) as role_error:
        adapter.record_creative_direction("job_doc117_role", "not_a_frozen_role", "One image.")
    assert role_error.value.code == "codex_local_role_binding_mismatch"
    with pytest.raises(LocalModeAdapterError) as structure_error:
        adapter.record_creative_direction("job_doc117_role", "output_1", "Use a canvas overlay after rendering.")
    assert structure_error.value.code == "codex_local_deprecated_direction_structure"


def test_raw_local_file_import_is_not_an_mcp_tool_and_fails_closed(tmp_path: Path) -> None:
    names = {item["name"] for item in TOOL_SCHEMAS}
    assert "import_generated_candidate" not in names
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    with pytest.raises(LocalModeAdapterError) as failure:
        adapter.import_generated_candidate(tmp_path / "arbitrary-system-file.png")
    assert failure.value.code == "codex_local_external_artifact_import_forbidden"


def test_mcp_is_stdio_only_and_has_no_web_provider_or_cli_fallback(tmp_path: Path) -> None:
    names = {item["name"] for item in TOOL_SCHEMAS}
    assert {"create_local_job", "render_platform_candidate", "finalize_local_job"}.issubset(names)
    source = (ROOT / "services" / "alchemy_codex_local_adapter" / "mcp_server.py").read_text(encoding="utf-8")
    renderer_source = (ROOT / "services" / "alchemy_codex_local_adapter" / "platform_renderer.py").read_text(encoding="utf-8")
    for forbidden in ("FastAPI", "httpx", "subprocess", "openai_gpt_image", "aiself", "OPENAI_API_KEY", "OPENAI_BASE_URL"):
        assert forbidden not in source
        assert forbidden not in renderer_source

    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    response = dispatch(adapter, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "unknown"}})
    assert response is not None
    assert response["result"]["isError"] is True
    assert "codex_local_unknown_tool" in response["result"]["content"][0]["text"]
