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
    LocalArtifactImportRequest,
    LocalJobSpec,
    LocalModeAdapterError,
    LocalModeDisabledError,
)
from services.alchemy_codex_local_adapter.mcp_server import TOOL_SCHEMAS, dispatch


ROOT = Path(__file__).resolve().parents[1]
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL+XQAAAABJRU5ErkJggg=="
)


def _spec(job_id: str) -> LocalJobSpec:
    return LocalJobSpec(
        job_id=job_id,
        project_id="project_doc117",
        template_id="general_template",
        scenario_id="general_creative",
        protected_user_intent="Create one natural whole-image study from the permitted reference.",
        role_ids=("output_1",),
        normalized_intent={"requested_image_count": 1},
        capability_execution_envelope={"envelope_id": "envelope_doc117", "api_key": "must-not-leak"},
        resolved_constraint_ledger={"ledger_id": "ledger_doc117", "provider_token": "must-not-leak"},
        permitted_reference_files=("reference/product.png",),
    )


def _write_png(directory: Path, name: str = "artifact.png") -> Path:
    path = directory / name
    path.write_bytes(ONE_PIXEL_PNG)
    return path


def _expect_code(code: str):
    return pytest.raises(LocalModeAdapterError, match=".")


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


def test_contract_is_frozen_public_safe_and_local_provenance_is_explicit(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    adapter.create_local_job(_spec("job_doc117_happy"))

    contract = adapter.get_render_contract("job_doc117_happy")
    serialized = json.dumps(contract)
    assert "must-not-leak" not in serialized
    assert "api_key" not in serialized
    assert contract["role_ids"] == ["output_1"]

    direction = "Create a natural whole-image product study with faithful material and lighting."
    adapter.record_creative_direction("job_doc117_happy", "output_1", direction)
    source = _write_png(tmp_path)
    candidate = adapter.import_generated_candidate(
        LocalArtifactImportRequest(
            job_id="job_doc117_happy",
            role_id="output_1",
            artifact_path=source,
            declared_mime_type="image/png",
        )
    )

    assert candidate.imported_path.exists()
    assert candidate.sha256 == hashlib.sha256(ONE_PIXEL_PNG).hexdigest()
    assert candidate.provenance["execution_channel"] == LOCAL_EXECUTION_CHANNEL
    assert candidate.provenance["creative_direction_owner"] == LOCAL_CREATIVE_DIRECTION_OWNER
    assert candidate.provenance["renderer"] == LOCAL_RENDERER
    assert candidate.provenance["fallback_used"] is False
    assert candidate.provenance["certification_state"] == "not_certified_phase_a_b"
    assert "renderer_model" not in candidate.provenance

    reopened = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    status = reopened.get_local_job_status("job_doc117_happy")
    assert status["candidates"][0]["sha256"] == candidate.sha256
    assert status["certified_delivery"] is False
    assert status["final_deliveries"] == []
    with pytest.raises(LocalModeAdapterError) as exc_info:
        reopened.finalize_local_job("job_doc117_happy")
    assert exc_info.value.code == "codex_local_shared_runtime_integration_pending"


def test_artifact_missing_duplicate_and_cross_job_fail_closed(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    adapter.create_local_job(_spec("job_doc117_one"))
    adapter.record_creative_direction("job_doc117_one", "output_1", "One whole image.")

    with pytest.raises(LocalModeAdapterError) as missing:
        adapter.import_generated_candidate(
            LocalArtifactImportRequest(
                job_id="job_doc117_one",
                role_id="output_1",
                artifact_path=tmp_path / "does-not-exist.png",
                declared_mime_type="image/png",
            )
        )
    assert missing.value.code == "codex_local_artifact_missing"

    source = _write_png(tmp_path)
    request = LocalArtifactImportRequest(
        job_id="job_doc117_one",
        role_id="output_1",
        artifact_path=source,
        declared_mime_type="image/png",
    )
    adapter.import_generated_candidate(request)
    with pytest.raises(LocalModeAdapterError) as duplicate:
        adapter.import_generated_candidate(request)
    assert duplicate.value.code == "codex_local_artifact_duplicate"

    adapter.create_local_job(_spec("job_doc117_two"))
    adapter.record_creative_direction("job_doc117_two", "output_1", "A separate whole image.")
    with pytest.raises(LocalModeAdapterError) as cross_job:
        adapter.import_generated_candidate(
            LocalArtifactImportRequest(
                job_id="job_doc117_two",
                role_id="output_1",
                artifact_path=source,
                declared_mime_type="image/png",
            )
        )
    assert cross_job.value.code == "codex_local_artifact_cross_job"


def test_role_binding_and_deprecated_local_rendering_direction_are_rejected(tmp_path: Path) -> None:
    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    adapter.create_local_job(_spec("job_doc117_role"))
    with pytest.raises(LocalModeAdapterError) as role_error:
        adapter.record_creative_direction("job_doc117_role", "not_a_frozen_role", "One image.")
    assert role_error.value.code == "codex_local_role_binding_mismatch"
    with pytest.raises(LocalModeAdapterError) as structure_error:
        adapter.record_creative_direction("job_doc117_role", "output_1", "Use a canvas overlay after rendering.")
    assert structure_error.value.code == "codex_local_deprecated_direction_structure"


def test_mcp_is_stdio_contract_only_and_has_no_web_provider_fallback(tmp_path: Path) -> None:
    names = {item["name"] for item in TOOL_SCHEMAS}
    assert {"create_local_job", "import_generated_candidate", "finalize_local_job"}.issubset(names)
    source = (ROOT / "services" / "alchemy_codex_local_adapter" / "mcp_server.py").read_text(encoding="utf-8")
    assert "FastAPI" not in source
    assert "httpx" not in source
    assert "subprocess" not in source
    assert "openai_gpt_image" not in source
    assert "gpt-image-2" not in source

    adapter = CodexLocalExecutionFacade(tmp_path / "local-store", enabled=True)
    response = dispatch(adapter, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "unknown"}})
    assert response is not None
    assert response["result"]["isError"] is True
    assert "codex_local_unknown_tool" in response["result"]["content"][0]["text"]
