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
        normalized_intent={"requested_image_count": len(role_ids)},
        capability_execution_envelope={"envelope_id": "envelope_doc117", "api_key": "must-not-leak"},
        resolved_constraint_ledger={"ledger_id": "ledger_doc117", "provider_token": "must-not-leak"},
        permitted_reference_files=("reference/product.png",),
    )


def _prepare_job(adapter: CodexLocalExecutionFacade, spec: LocalJobSpec) -> None:
    adapter.create_local_job(spec)
    for role_id in spec.role_ids:
        adapter.record_creative_direction(spec.job_id, role_id, f"Natural whole-image direction for {role_id}.")


def test_disabled_mode_has_no_local_job_path_or_web_runtime_import() -> None:
    adapter = CodexLocalExecutionFacade("ignored", enabled=False)
    with pytest.raises(LocalModeDisabledError) as exc_info:
        adapter.create_local_job(_spec("job_doc117_disabled"))
    assert exc_info.value.code == "codex_local_mode_disabled"

    web_runtime = ROOT / "alchemy_creative_agent_3_0" / "app"
    assert not any(
        "alchemy_codex_local_adapter" in path.read_text(encoding="utf-8")
        for path in web_runtime.rglob("*.py")
    )


def test_platform_renderer_live_gate_key_file_and_base_override_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(LocalModeAdapterError) as disabled:
        PlatformImageRenderer().render(direction="One image.", role_id="output_1")
    assert disabled.value.code == "codex_local_platform_renderer_disabled"

    with pytest.raises(LocalModeAdapterError) as missing:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            environment={},
            user_home=tmp_path,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert missing.value.code == "codex_local_platform_renderer_key_missing"

    with pytest.raises(LocalModeAdapterError) as unreadable:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(tmp_path / "missing-key.txt")},
            user_home=tmp_path,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert unreadable.value.code == "codex_local_platform_renderer_key_file_unreadable"

    empty_key = tmp_path / "empty-key.txt"
    empty_key.write_text("\n", encoding="utf-8")
    with pytest.raises(LocalModeAdapterError) as invalid:
        PlatformImageRenderer(
            live_platform_opt_in=True,
            environment={LOCAL_IMAGE_API_KEY_FILE_ENV: str(empty_key)},
            user_home=tmp_path,
            repository_root=ROOT,
        ).render(direction="One image.", role_id="output_1")
    assert invalid.value.code == "codex_local_platform_renderer_key_file_invalid"

    with pytest.raises(LocalModeAdapterError) as override:
        PlatformImageRenderer(base_url="https://example.invalid/v1")
    assert override.value.code == "codex_local_platform_renderer_base_url_forbidden"


def test_mock_platform_success_materializes_hash_binds_role_and_stays_not_certified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "web-provider-key-must-not-be-read")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://web-gateway.invalid/v1")
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    _prepare_job(adapter, _spec("job_doc117_happy"))
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG)])
    candidate = adapter.render_platform_candidate(
        "job_doc117_happy",
        "output_1",
        renderer=PlatformImageRenderer(transport=transport),
    )

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

    reopened = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    status = reopened.get_local_job_status("job_doc117_happy")
    assert status["candidates"][0]["sha256"] == candidate.sha256
    assert status["certified_delivery"] is False
    assert status["final_deliveries"] == []
    with pytest.raises(LocalModeAdapterError) as finalization:
        reopened.finalize_local_job("job_doc117_happy")
    assert finalization.value.code == "codex_local_shared_runtime_integration_pending"


def test_missing_untrusted_duplicate_and_cross_job_artifacts_fail_closed(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    first = _spec("job_doc117_one")
    _prepare_job(adapter, first)
    with pytest.raises(LocalModeAdapterError) as untrusted:
        adapter.import_generated_candidate(tmp_path / "arbitrary-system-file.png")
    assert untrusted.value.code == "codex_local_external_artifact_import_forbidden"

    importer = LocalArtifactImporter(tmp_path / "missing-store")
    rendered = PlatformRenderedImage(image_bytes=ONE_PIXEL_PNG, request_summary={}, response_summary={})
    staged = importer.stage_platform_response(rendered)
    staged.source_path.unlink()
    with pytest.raises(LocalModeAdapterError) as missing:
        importer.import_staged_platform_candidate(job_id=first.job_id, role_id="output_1", contract=first, staged=staged)
    assert missing.value.code == "codex_local_artifact_missing"

    same_image = FakeTransport([_api_response(ONE_PIXEL_PNG), _api_response(ONE_PIXEL_PNG), _api_response(ONE_PIXEL_PNG)])
    renderer = PlatformImageRenderer(transport=same_image)
    adapter.render_platform_candidate(first.job_id, "output_1", renderer=renderer)
    with pytest.raises(LocalModeAdapterError) as duplicate:
        adapter.render_platform_candidate(first.job_id, "output_1", renderer=renderer)
    assert duplicate.value.code == "codex_local_artifact_duplicate"

    second = _spec("job_doc117_two")
    _prepare_job(adapter, second)
    with pytest.raises(LocalModeAdapterError) as cross_job:
        adapter.render_platform_candidate(second.job_id, "output_1", renderer=renderer)
    assert cross_job.value.code == "codex_local_artifact_cross_job"


def test_platform_failures_are_structured_and_do_not_retry_or_fallback(tmp_path: Path) -> None:
    cases = [
        (FakeTransport([PlatformHttpResponse(status_code=502, headers={}, body=b"{}")]), "codex_local_platform_renderer_upstream_502"),
        (FakeTransport([TimeoutError()]), "codex_local_platform_renderer_timeout"),
        (FakeTransport([PlatformHttpResponse(status_code=200, headers={}, body=b'{"data":[]}')]), "codex_local_platform_renderer_empty_response"),
        (FakeTransport([_api_response(ONE_PIXEL_JPEG)]), "codex_local_platform_renderer_mime_mismatch"),
    ]
    for index, (transport, expected_code) in enumerate(cases):
        adapter = CodexLocalExecutionFacade(tmp_path / f"store-{index}", enabled=True)
        spec = _spec(f"job_doc117_failure_{index}")
        _prepare_job(adapter, spec)
        with pytest.raises(LocalModeAdapterError) as failure:
            adapter.render_platform_candidate(spec.job_id, "output_1", renderer=PlatformImageRenderer(transport=transport))
        assert failure.value.code == expected_code
        assert len(transport.calls) == 1
        assert adapter.get_local_job_status(spec.job_id)["candidates"] == []


def test_each_explicit_role_makes_one_bounded_platform_request(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    spec = _spec("job_doc117_multi", ("output_1", "output_2"))
    _prepare_job(adapter, spec)
    transport = FakeTransport([_api_response(ONE_PIXEL_PNG + b"a"), _api_response(ONE_PIXEL_PNG + b"b")])
    candidates = adapter.render_platform_candidates(
        spec.job_id,
        ["output_1", "output_2"],
        renderer=PlatformImageRenderer(transport=transport),
    )
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


def test_mcp_is_stdio_only_and_has_no_web_provider_or_cli_fallback(tmp_path: Path) -> None:
    names = {item["name"] for item in TOOL_SCHEMAS}
    assert {"create_local_job", "render_platform_candidate", "finalize_local_job"}.issubset(names)
    assert "import_generated_candidate" not in names
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
