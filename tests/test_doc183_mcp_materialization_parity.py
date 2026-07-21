from __future__ import annotations

import base64
from io import BytesIO
import hashlib
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.generation_router import (
    McpMaterializationProvider,
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationError,
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from app.providers.base import ProviderRuntimeError
from services.alchemy_codex_local_adapter.mcp_server import TOOL_SCHEMAS

from tests.test_doc130_codex_native_prompt_parity import _canonical_runtime_result


def _png_bytes() -> bytes:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (24, 24), color=(220, 235, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _provider_request() -> object:
    runtime_result = _canonical_runtime_result()
    plan = runtime_result.planning_result
    return build_provider_generation_request(
        asset_spec=plan.series_plan.assets[0],
        layout_plan=plan.layout_plans[0],
        prompt_compilation=plan.prompt_compilations[0],
        condition_plan=plan.condition_plans[0],
        generation_plan=plan.generation_plans[0],
        job_id=plan.creative_job.job_id,
    )


def test_handoff_is_nonce_hash_reference_and_one_time_safe(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "Remote Brain final prompt"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    contract = {"renderer": "codex_builtin_imagegen", "model": "gpt-image-2", "output_format": "png", "count": 1}
    pending = store.ensure_pending(
        operation_id="project:face.front:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[],
        rendering_contract=contract,
    )
    assert pending["status"] == "pending"
    assert store.public_view(pending["handoff_id"])["canonical_prompt"] == prompt
    with pytest.raises(McpMaterializationError, match="nonce"):
        store.submit(
            pending["handoff_id"],
            nonce="wrong",
            prompt_sha256=prompt_hash,
            reference_asset_hashes=[],
            artifact_bytes=_png_bytes(),
        )
    submitted = store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_hash,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
    )
    assert submitted["status"] == "submitted"
    artifact = store.consume(pending["handoff_id"])
    assert artifact["artifact_format"] == "png"
    assert store.get(pending["handoff_id"])["status"] == "consumed"
    with pytest.raises(McpMaterializationError, match="pending"):
        store.consume(pending["handoff_id"])


def test_handoff_rejects_format_and_reference_mismatch(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "same prompt"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    pending = store.ensure_pending(
        operation_id="op-2",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[{"asset_id": "root", "sha256": "a" * 64}],
        rendering_contract={"output_format": "png"},
    )
    with pytest.raises(McpMaterializationError, match="reference"):
        store.submit(
            pending["handoff_id"],
            nonce=pending["nonce"],
            prompt_sha256=prompt_hash,
            reference_asset_hashes=["b" * 64],
            artifact_bytes=_png_bytes(),
        )
    with pytest.raises(McpMaterializationError, match="readable"):
        store.submit(
            pending["handoff_id"],
            nonce=pending["nonce"],
            prompt_sha256=prompt_hash,
            reference_asset_hashes=["a" * 64],
            artifact_bytes=b"not-an-image",
        )


def test_mcp_and_provider_materializers_share_prompt_reference_and_rendering_contract() -> None:
    request = _provider_request()
    web = ProductionImageGenerationProvider(output_store=object())
    mcp = McpMaterializationProvider(output_store=object(), handoff_store=McpMaterializationHandoffStore())
    web_materialization = web.materialize_final_prompt(request)
    mcp_request = request.model_copy(
        update={"metadata": {**request.metadata, "generation_channel": "mcp", "mcp_operation_id": "parity-op"}}
    )
    mcp_app_request, _provider_name, _references = mcp._build_app_request(mcp_request)
    variables = mcp_app_request.prompt_plan.variables
    assert variables["generation_prompt"] == web_materialization.generation_prompt
    assert variables["provider_prompt_sha256"] == web_materialization.prompt_sha256
    assert variables["mcp_materialization_context"]["rendering_contract"] == {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": mcp_app_request.prompt_plan.size,
        "quality": mcp_app_request.prompt_plan.quality,
        "output_format": mcp_app_request.prompt_plan.output_format,
        "count": 1,
        "api_operation": "image_generate",
        "input_fidelity": None,
        "input_fidelity_required": False,
    }


def test_mcp_pending_is_not_a_provider_retry_and_success_uses_shared_output_store(tmp_path: Path) -> None:
    request = _provider_request().model_copy(
        update={"metadata": {**_provider_request().metadata, "generation_channel": "mcp", "mcp_operation_id": "resume-op"}}
    )
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    with pytest.raises(ProviderRuntimeError) as caught:
        provider.generate(request)
    assert caught.value.detail["failure_code"] == "mcp_materialization_pending"
    assert provider._classify_provider_failure(caught.value) == "non_retryable_provider_failure"
    handoff_id = caught.value.detail["handoff_id"]
    handoff = handoffs.public_view(handoff_id)
    artifact = _png_bytes()
    handoffs.submit(
        handoff_id,
        nonce=handoff["nonce"],
        prompt_sha256=handoff["prompt_sha256"],
        reference_asset_hashes=handoff["reference_asset_hashes"],
        artifact_bytes=artifact,
    )
    response = provider.generate(request)
    assert len(response.candidates) == 1
    record = outputs.get_output(response.candidates[0].metadata["output_id"])
    assert record is not None
    assert record.metadata["generation_channel"] == "mcp"
    assert record.provider == "codex_builtin_imagegen"
    assert record.metadata["provider_prompt_sha256"] == handoff["prompt_sha256"]


def test_mcp_tools_expose_explicit_handoff_without_web_credentials() -> None:
    names = [tool["name"] for tool in TOOL_SCHEMAS]
    assert names[:2] == ["prepare_shared_mcp_materialization", "submit_shared_mcp_materialization"]
    submit = TOOL_SCHEMAS[1]["inputSchema"]
    assert "api_key" not in submit["properties"]
    assert "cookie" not in submit["properties"]
    assert "provider_id" not in submit["properties"]


def test_character_card_frontend_exposes_channel_switch_without_creating_a_second_flow() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "src_skeleton" / "app" / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="v3CharacterCardGenerationChannelInput"' in html
    assert 'value="provider"' in html and 'value="mcp"' in html
    assert "generation_channel" in javascript
    assert "mcp_materialization" not in javascript
