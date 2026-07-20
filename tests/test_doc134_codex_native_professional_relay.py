"""Doc134: Professional frozen-plan MCP relay contracts for M5 acceptance.

The relay is a conversation-only projection of the existing V3 planning path.
It never owns a catalog, Provider, candidate/review/retry store, or delivery
record.  The resolver supplied by an embedding host is the only trusted seam
for server-owned People Asset bindings; a default relay without that seam
must fail closed.
"""

from __future__ import annotations

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
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets import (
    InMemoryVisualAssetCatalog,
    bind_professional_mode,
)
from alchemy_creative_agent_3_0.tests.professional_mode_test_support import (
    catalog_with_active_face_identity_pack,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
from services.alchemy_codex_local_adapter.contracts import (
    CodexNativeImageGenError,
    NativeProfessionalImageGenPlanRequest,
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
        self.payloads.append(payload)
        self.last_result = self.runtime.plan_job(payload)
        return self.last_result


def _write_png(path: Path) -> Path:
    from PIL import Image

    Image.new("RGB", (32, 32), color=(129, 91, 77)).save(path, format="PNG")
    return path


def _resolver(catalog: InMemoryVisualAssetCatalog):
    def resolve(*, project_id: str, people_asset_id: str, job_id: str, reference_view_ids: list[str]):
        asset = catalog.get(project_id, people_asset_id)
        if asset is None or not asset.active_pack_version_id:
            return None
        pack = catalog.get_pack(project_id, people_asset_id, asset.active_pack_version_id)
        if pack is None:
            return None
        return bind_professional_mode(
            job_id=job_id,
            project_id=project_id,
            asset=asset,
            module=asset.face_identity_module,
            pack=pack,
            reference_view_ids=reference_view_ids,
        )

    return resolve


def _arguments(reference: Path, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "user_input": "Create a natural, realistic portrait of the selected person in a quiet studio.",
        "template_id": "general_template",
        "requested_image_count": 1,
        "requested_image_size": "1024x1024",
        "reference_inputs": [{"channel": "portrait_identity", "file_path": str(reference)}],
        "project_id": "project_professional",
        "people_asset_id": "person_1",
        "professional_identity_view_ids": ["front_1", "three_quarter_1", "profile_1"],
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


def test_professional_relay_requires_server_owned_binding_and_projects_existing_frozen_plan(tmp_path: Path) -> None:
    reference = _write_png(tmp_path / "root.png")
    catalog = catalog_with_active_face_identity_pack()
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=_resolver(catalog),
    )

    parsed_request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(_arguments(reference))
    result = planner.prepare_frozen_professional_native_imagegen_plan(parsed_request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["requested_output_count"] == 1
    assert result["provenance"]["professional_mode"] is True
    assert result["provenance"]["professional_binding"]["pack_version_id"] == "pack_1"
    assert result["provenance"]["professional_reference_stage"] == "standard_front"
    assert result["provenance"]["professional_identity_reference_strategy"] == "serial_anchor_pack_root_reuse_v1"
    assert result["provenance"]["professional_serial_intent_sha256"] == hashlib.sha256(
        parsed_request.user_input.encode("utf-8")
    ).hexdigest()
    assert result["provenance"]["delivery_state"] == "conversation_only_not_certified"
    frozen = capturing.last_result.metadata["capability_activation_plan"]
    assert frozen["metadata"]["professional_mode"] is True
    assert "portrait_identity" in frozen["dependency_order"]
    assert brain.requests and brain.requests[0]["metadata"].get("professional_mode_binding_record") is None

    expected = _provider_materializations(capturing.last_result)
    output = result["outputs"][0]
    assert output["imagegen_prompt"] == expected[0].generation_prompt
    assert output["provider_prompt_sha256"] == expected[0].prompt_sha256
    assert output["provider_prompt_sha256"] == hashlib.sha256(output["imagegen_prompt"].encode("utf-8")).hexdigest()
    assert output["reference_image_paths"] == [item["file_path"] for item in expected[0].reference_assets]
    assert output["reference_input_contract"]["source_sha256"] == [parsed_request.reference_inputs[0].source_sha256]


def test_professional_relay_does_not_downgrade_explicit_specialist_template(tmp_path: Path) -> None:
    reference = _write_png(tmp_path / "root.png")
    catalog = catalog_with_active_face_identity_pack()
    brain = EcommerceRemoteBrainTestProvider()
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)),
        professional_binding_resolver=_resolver(catalog),
    )
    result = planner.prepare_frozen_professional_native_imagegen_plan(
        NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                reference,
                template_id="ecommerce_template",
                platform_profile="generic",
                user_input="Create the selected person's factual product portrait without visible copy.",
            )
        )
    )
    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["provenance"]["scenario_id"] == "ecommerce"
    assert brain.requests and brain.requests[0]["scenario_id"] == "ecommerce"


def test_professional_relay_without_resolver_and_mcp_unknown_fields_fail_closed(tmp_path: Path) -> None:
    reference = _write_png(tmp_path / "root.png")
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(_arguments(reference))
    blocked = CodexNativeImageGenPlanner(runtime_factory=ScenarioRuntime).prepare_frozen_professional_native_imagegen_plan(request)
    assert blocked["status"] == "blocked"
    assert blocked["code"] == "codex_native_imagegen_professional_binding_unavailable"

    with pytest.raises(CodexNativeImageGenError) as exc:
        NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(reference, professional_mode_binding_record={"mode": "professional"})
        )
    assert exc.value.code == "codex_native_imagegen_invalid_input"


def test_professional_relay_accepts_exact_persisted_timestamp_identifiers(tmp_path: Path) -> None:
    reference = _write_png(tmp_path / "root.png")
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            reference,
            project_id="project_doc165_20260718T133110Z",
            people_asset_id="person_78c335f8908848b6",
        )
    )

    assert request.project_id == "project_doc165_20260718T133110Z"
    assert request.people_asset_id == "person_78c335f8908848b6"


def test_professional_serial_reference_stage_requires_root_then_reviewed_winners(tmp_path: Path) -> None:
    root = _write_png(tmp_path / "root.png")
    winner = _write_png(tmp_path / "front-winner.png")
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            root,
            reference_inputs=[
                {"channel": "portrait_identity", "file_path": str(root)},
                {"channel": "selected_identity_reference", "file_path": str(winner)},
            ],
            professional_reference_stage="three_quarter",
        )
    )
    assert request.professional_reference_stage == "three_quarter"

    with pytest.raises(CodexNativeImageGenError) as exc:
        NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                root,
                reference_inputs=[
                    {"channel": "portrait_identity", "file_path": str(root)},
                    {"channel": "portrait_identity", "file_path": str(winner)},
                ],
                professional_reference_stage="three_quarter",
            )
        )
    assert exc.value.code == "codex_native_imagegen_professional_reference_chain_invalid"


def test_professional_serial_stage_reaches_canonical_materializer_with_bounded_reference_count(tmp_path: Path) -> None:
    from PIL import Image

    root = _write_png(tmp_path / "root.png")
    front = tmp_path / "front-winner.png"
    three_quarter = tmp_path / "three-quarter-winner.png"
    Image.new("RGB", (32, 32), color=(120, 92, 80)).save(front, format="PNG")
    Image.new("RGB", (32, 32), color=(121, 92, 80)).save(three_quarter, format="PNG")
    catalog = catalog_with_active_face_identity_pack()
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=_resolver(catalog),
    )

    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            root,
            reference_inputs=[
                {"channel": "portrait_identity", "file_path": str(root)},
                {"channel": "selected_identity_reference", "file_path": str(front)},
                {"channel": "selected_identity_reference", "file_path": str(three_quarter)},
            ],
            professional_reference_stage="profile",
        )
    )
    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    output = result["outputs"][0]
    assert len(output["reference_image_paths"]) == 5
    assert output["reference_input_contract"]["admitted_reference_count"] == 5
    finalizer = [request for request in brain.requests if request["stage"] == "provider_prompt_finalize"][-1]
    reference_bindings = finalizer["metadata"]["canonical_prompt_context"]["reference_bindings"]
    assert [item["professional_anchor_lineage_role"] for item in reference_bindings] == [
        "identity_root",
        "prior_view_winner",
        "prior_view_winner",
    ]
    assert [request["stage"] for request in brain.requests] == [
        "plan",
        "provider_prompt_finalize",
        "provider_prompt_professional_capture_resign",
    ]
    assert result["provenance"]["canonical_prompt_signing"]["stages"] == [
        "provider_prompt_finalize",
        "provider_prompt_professional_capture_resign",
    ]


def test_professional_serial_relay_uses_the_formal_neutral_anchor_preparation_contract(tmp_path: Path) -> None:
    root = _write_png(tmp_path / "root.png")
    catalog = catalog_with_active_face_identity_pack()
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=_resolver(catalog),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(
        NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(root, professional_reference_stage="standard_front")
        )
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    metadata = capturing.payloads[0]["metadata"]
    assert metadata["professional_anchor_pack_preparation"] is True
    planning = metadata["professional_planning_metadata"]
    assert planning["professional_reference_stage"] == "standard_front"
    assert planning["professional_face_identity_quality_contract"]["capture_presentation"] == (
        "neutral_identity_evidence_capture"
    )
    finalizer = [request for request in brain.requests if request["stage"] == "provider_prompt_finalize"][-1]
    context = finalizer["metadata"]["canonical_prompt_context"]
    assert context["professional_anchor_view_decision"]["capture_presentation"] == (
        "neutral_identity_evidence_capture"
    )


def test_professional_mcp_schema_and_dispatch_are_explicit_and_safe(tmp_path: Path) -> None:
    names = [tool["name"] for tool in TOOL_SCHEMAS]
    assert names == [
        "prepare_native_imagegen_plan",
        "prepare_frozen_specialized_native_imagegen_plan",
        "prepare_frozen_professional_native_imagegen_plan",
    ]
    schema = TOOL_SCHEMAS[2]
    assert schema["inputSchema"]["additionalProperties"] is False
    assert "professional_mode_binding_record" not in schema["inputSchema"]["properties"]
    assert "pack_version_id" not in schema["inputSchema"]["properties"]
    assert "job_id" not in schema["inputSchema"]["properties"]

    adapter = CodexNativeImageGenFacade(enabled=True)
    response = dispatch(
        adapter,
        {
            "jsonrpc": "2.0",
            "id": 134,
            "method": "tools/call",
            "params": {
                "name": "prepare_frozen_professional_native_imagegen_plan",
                "arguments": _arguments(tmp_path / "missing.png"),
            },
        },
    )
    assert response is not None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["code"] == "codex_native_imagegen_reference_path_unavailable"
