"""Doc290: offline HTTP captures through the normal Project Mode entry.

Only transport responses are simulated. The real runtime, adapter, payload
builders, stream collector and validators run unchanged. Existing deterministic
Brain response fixtures are not evidence of upstream creativity or image quality.
Raw requests stay in memory; printed measurements contain no prompts or keys.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
import socket
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers
from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS,
    build_remote_payload,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
from alchemy_creative_agent_3_0.app.product_api.service import PersistentProductJobStore
from alchemy_creative_agent_3_0.app.project_mode.contracts import CreateProjectJobRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.physical_renderer_reference_plan import (
    PhysicalRendererReferencePlan,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    VariationExecutionContract,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc269_ecommerce_physical_renderer_reference_plan import (
    _apparel_on_model_payload,
    _ecommerce_fixture,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import (
    _general_payload,
    _general_project,
    _replace_general_service,
    _selection_registry,
)


BASELINE_SHA = "00de0734ae22c1d5c37eb641af73aa04622a24a0"
CASES = ("general_single", "general_multi", "professional_ecommerce")
INPUT_MODELS = (CreateProjectJobRequest, CreateCreativeJobRequest, ScenarioRuntimeRequest, BrainRunRequest)
RAW_INPUTS = (' \n  Keep two  spaces.\n ', 'Keep\tA\t\tB.', '\r\n"A & B"\r\nSecond line.\t \r\n')
# Measured at HTTP dispatch, not BrainRunRequest.model_dump. These are fixed
# comparison observations, not truncation ceilings or upstream token estimates.
# Each tuple is (system bytes, user JSON bytes, HTTP body bytes, schema SHA256).
GATE_A_BASELINE = {
    "general_single": {
        "plan": (21480, 13039, 38789, "445c229005a7ff089dff5d32a9f0f90eae0dcfa3b6f788c5b5a6b554842586eb"),
        "provider_prompt_finalize": (5359, 29721, 50459, "e4dfac5dc14e6530531d3688b1463ef675f700c9afc0b6fab21c8941e44dc29d"),
    },
    "general_multi": {
        "plan": (21480, 14997, 40889, "445c229005a7ff089dff5d32a9f0f90eae0dcfa3b6f788c5b5a6b554842586eb"),
        "provider_prompt_finalize": (5359, 65281, 88469, "78895211b672218b07c4440705148b8c9522ab6e30b2a6f00a7783928b6894e7"),
    },
    "professional_ecommerce": {
        "plan": (21480, 21210, 47495, "5c485b5493ae3538fe006292cf296adde4e1a3d464fd01d0964c7dab33badd5b"),
        "provider_prompt_finalize": (5359, 82486, 106797, "925ef671fe72a676adaa3ad4b070c1654fb89d3904e9c51877d3821077625704"),
    },
}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _bytes(value: str) -> int:
    return len(value.encode("utf-8"))


def _user_input(case: str) -> str:
    directions = {
        "general_single": "Create one quiet moonlit lake image, cool low-key light, no people.",
        "general_multi": "Create three images of the same person with distinct viewpoints and actions, fresh daylight.",
        "professional_ecommerce": "Create one apparel-on-model listing image using the supplied product and locked person.",
    }
    return (
        directions[case]
        + '\nLiteral copy: "A & B"; keep the line break.\n'
        + "\u4fdd\u7559\u539f\u610f\uff0c\u4e0d\u6539\u6c1b\u56f4\u548c\u4e3b\u8272\u3002\n" * 90
        + '\nFinal hard conditions: 1024x1536; no collage; text "END-290" exactly.'
    )


def _measure(capture: dict) -> dict:
    user = capture["user"]
    system = capture["system"]
    body = capture["body"]
    field_bytes = {key: _bytes(_json(value)) for key, value in user.items()}
    framework_keys = [
        key for key in user
        if key.endswith("_instructions")
        or (key.endswith("_contract") and isinstance(user[key], str))
        or key == "return_schema"
    ]
    framework_bytes = _bytes(system) + sum(field_bytes[key] for key in framework_keys)
    schema = user["return_schema"]
    output_schema = (
        schema.get("canonical_provider_prompts")
        or schema.get("image_set_plan", {}).get("evidence_dimensions_by_output")
        or []
    )
    return {
        "baseline_sha": BASELINE_SHA,
        "case": capture["case"],
        "stage": user["stage"],
        "attempt": capture["attempt"],
        "model": body["model"],
        "transport": "openai_chat_completions_mock_http_transport",
        "max_tokens": body["max_tokens"],
        "system_bytes": _bytes(system),
        "system_chars": len(system),
        "user_json_bytes": _bytes(capture["user_text"]),
        "user_json_chars": len(capture["user_text"]),
        "http_body_bytes": len(capture["raw_body"]),
        "http_body_chars": len(capture["raw_body"].decode("utf-8")),
        "http_body_delta_from_gate_a": len(capture["raw_body"]) - GATE_A_BASELINE[capture["case"]][user["stage"]][2],
        "request_sha256": hashlib.sha256(capture["raw_body"]).hexdigest(),
        "field_json_value_bytes": field_bytes,
        "explicit_framework_and_schema_bytes": framework_bytes,
        "explicit_framework_ratio": round(framework_bytes / (_bytes(system) + _bytes(capture["user_text"])), 4),
        "per_output_schema_bytes": _bytes(_json(output_schema)),
        "return_schema_sha256": hashlib.sha256(_json(schema).encode("utf-8")).hexdigest(),
        "required_prompt_fields": sorted(schema.get("canonical_provider_prompts", [{}])[0]),
        "response_json_bytes": _bytes(_json(capture["response"])),
        "tokens": None,
        "tokens_note": "No tokenizer or upstream usage; bytes are measured, tokens are not estimated.",
        "framework_note": "System plus top-level instructions/contracts/schema only; contextual facts excluded.",
    }


@pytest.fixture
def offline_transport(monkeypatch, tmp_path):
    """No real credentials, sockets, image generation, or production stores."""
    for name in tuple(os.environ):
        if name.startswith(("V3_LLM_BRAIN_", "V3_BRAIN_", "ALCHEMY_DOC281_")):
            monkeypatch.delenv(name)
    for name in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
        "DEEPSEEK_API_KEY", "LAB_OPENAI_API_KEY", "LAB_KIMI_API_KEY",
    ):
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("CODEX_AUTH_FILE", str(tmp_path / "missing_auth.json"))
    monkeypatch.setenv("CLAUDE_SETTINGS_FILE", str(tmp_path / "missing_claude_settings.json"))
    monkeypatch.setenv("MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS", "false")
    monkeypatch.setenv("LLM_PROMPT_PLANNING_ENABLED", "false")
    monkeypatch.setenv("MEDIA_AGENT_MODE", "mock")
    monkeypatch.setenv("MOCK_IMAGE_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("ALCHEMY_V3_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ALCHEMY_V3_MCP_MATERIALIZATION_ROOT", str(tmp_path / "handoffs"))
    monkeypatch.setenv("ALCHEMY_V3_JOB_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_PROVIDER", "deepseek")
    monkeypatch.setenv("V3_LLM_BRAIN_API_KEY", "doc290-offline-not-a-key")
    monkeypatch.setenv("V3_LLM_BRAIN_BASE_URL", "https://doc290.invalid/v1")
    monkeypatch.setattr(brain_providers, "_settings_value", lambda _name: None)

    from app.config import settings

    for name in type(settings).model_fields:
        if name.endswith(("api_key", "auth_token")):
            monkeypatch.setattr(settings, name, "")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Doc290 Gate A forbids sockets and image generation")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(GenerationRouter, "generate", forbidden)

    state = SimpleNamespace(
        captures=[], requests=[], responses=[], budgets=[], failures=[],
        provider=brain_providers.V3LLMBrainProvider(),
        reply_fixture=EcommerceRemoteBrainTestProvider(visible_ecommerce_person=True),
        case=None, active_request=None, response_script=[], clock=None,
    )
    real_run = state.provider.run

    def observe_run(request):
        state.active_request = request.model_copy(deep=True)
        state.requests.append(state.active_request)
        state.budgets.append(brain_providers._ACTIVE_EXECUTION_BUDGET.get())
        try:
            result = real_run(request)
        except brain_providers.BrainProviderError as exc:
            state.failures.append(exc)
            raise
        state.responses.append(deepcopy(result))
        return result

    monkeypatch.setattr(state.provider, "run", observe_run)

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://doc290.invalid/v1/chat/completions"
        raw_body = request.read()
        body = json.loads(raw_body)
        assert [item["role"] for item in body["messages"]] == ["system", "user"]
        user_text = body["messages"][1]["content"]
        user = json.loads(user_text)
        assert user["stage"] == state.active_request.stage
        # Reuse the legal response fixture, but never replace provider.run or
        # adapter validation with that double. The response crosses real SSE.
        response = state.reply_fixture.run(state.active_request)
        if state.response_script:
            response = state.response_script.pop(0)(response)
        budget = brain_providers._ACTIVE_EXECUTION_BUDGET.get()
        state.captures.append({
            "case": state.case,
            "attempt": len(state.captures) + 1,
            "raw_body": raw_body,
            "body": body,
            "system": body["messages"][0]["content"],
            "user_text": user_text,
            "user": user,
            "response": deepcopy(response),
            "budget": budget,
            "deadline": budget.started_at + budget.total_seconds if budget else None,
            "remaining": budget.remaining_seconds() if budget else None,
            "timeout": dict(request.extensions.get("timeout", {})),
        })
        if state.clock is not None:
            state.clock.now += state.clock.step
        content = response if isinstance(response, str) else _json(response)
        event = {"choices": [{"delta": {"content": content}, "finish_reason": None}]}
        finish = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=f"data: {_json(event)}\n\ndata: {_json(finish)}\n\ndata: [DONE]\n\n".encode("utf-8"),
        )

    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", lambda _self, request: transport.handle_request(request))
    return state


@pytest.fixture(params=CASES)
def captured_entry(request, tmp_path, offline_transport):
    state = _capture_entry(tmp_path, offline_transport, request.param)
    assert state.created["status"] == "planned", state.created
    assert [item["user"]["stage"] for item in state.captures] == ["plan", "provider_prompt_finalize"]
    return state


def _capture_entry(tmp_path, state, case, *, original=None):
    state.case = case
    original = _user_input(case) if original is None else original
    source_calls = {}
    if state.case == "professional_ecommerce":
        handlers, image_capture, project, product_ids, identity_ids = _ecommerce_fixture(tmp_path)
        payload = _apparel_on_model_payload(product_ids=product_ids, key="doc290-gate-a")
        payload["user_input"] = original
        payload["metadata"]["requested_image_count"] = 1
        state.product_ids = product_ids
        state.identity_ids = identity_ids
        state.image_capture = image_capture
    elif state.case == "general_multi":
        handlers, project, asset_ids, snapshot = _general_project(tmp_path)
        _replace_general_service(
            handlers,
            _selection_registry(snapshot, target_asset_id=asset_ids[0], calls=source_calls),
        )
        payload = _general_payload(user_input=original, metadata={
            "requested_image_count": 3, "variation_mode": "delivery_suite",
        })
        state.source_ids = [asset_ids[0]]
        state.source_snapshot = snapshot
    else:
        handlers, _catalog = _handlers(tmp_path)
        project = handlers.post_projects({
            "user_goal": "Create a quiet night landscape.",
            "primary_template_id": "general_template",
        })["project"]
        payload = _general_payload(user_input=original)
    payload["metadata"]["require_real_images"] = True
    handlers.service.scenario_runtime.llm_brain_adapter = V3LLMBrainAdapter(provider=state.provider)
    created = handlers.post_project_job(project["project_id"], payload)
    state.created = created
    state.handlers = handlers
    state.project = project
    state.record = handlers.service.get_job_record(created["job_id"])
    state.original = original
    state.source_calls = source_calls
    assert state.record is not None
    return state


def test_doc290_normal_entry_dispatch_baseline(captured_entry):
    state = captured_entry
    for capture in state.captures:
        metrics = _measure(capture)
        print("DOC290_METRICS " + _json(metrics))
        assert metrics["return_schema_sha256"] == GATE_A_BASELINE[state.case][capture["user"]["stage"]][3]
        # Exact original-to-dispatch fidelity has a separate red regression.
        assert capture["user"]["user_input"] == state.requests[capture["attempt"] - 1].user_input
        assert capture["body"]["model"] == "deepseek-v4-pro"
        assert capture["body"]["max_tokens"] == 8000
        assert capture["body"]["stream"] is True
        assert capture["body"]["response_format"] == {"type": "json_object"}
    assert state.provider.timeout == 300
    assert state.provider.execution_budget_seconds == 520
    assert len(state.budgets) == 2
    assert state.budgets[0] is state.budgets[1] and state.budgets[0] is not None
    planning = state.requests[0]
    assert planning.capability_catalog["capabilities"]
    assert planning.pre_activation_capabilities
    assert planning.template_capability_policy.policy_id
    catalog_ids = {item["capability_id"] for item in planning.capability_catalog["capabilities"]}
    assert "human_realism" in catalog_ids
    assert {item["capability_id"] for item in state.captures[0]["user"]["capability_catalog"]["capabilities"]} == catalog_ids
    assert planning.project_id == state.project["project_id"]
    assert planning.job_id == state.requests[1].job_id
    assert planning.template_capability_policy == state.requests[1].template_capability_policy
    assert state.captures[0]["user"]["template_capability_policy"]["policy_id"] == planning.template_capability_policy.policy_id
    assert state.captures[0]["user"]["template_capability_policy"]["deliverable_role_owner"] == planning.template_capability_policy.deliverable_role_owner
    assert state.record.request.metadata["capability_activation_mode"] == "enforced"
    audit = state.record.planning_result.metadata["llm_brain"]
    assert audit["llm_used"] is True and audit["fallback_used"] is False
    assert all(brain_providers.pop_transport_receipt(deepcopy(item))["attempts"] == 1 for item in state.responses)
    finalizer = state.captures[1]["user"]
    assert finalizer["protected_user_direction"] == finalizer["user_input"]
    context = finalizer["frozen_render_context"]
    assert context == state.requests[1].metadata["canonical_prompt_context"]
    metadata = state.record.request.metadata
    binding = context["frozen_binding"]
    assert binding["ledger_id"] == metadata["resolved_constraint_ledger"]["ledger_id"]
    assert binding["envelope_id"] == metadata["capability_execution_envelope"]["envelope_id"]
    assert binding["execution_fingerprint"] == metadata["capability_execution_envelope"]["execution_fingerprint"]
    assert context["active_shared_capability_ids"] == metadata["capability_activation_plan"]["dependency_order"]
    assert state.record.request.user_input == state.original
    if state.case == "professional_ecommerce":
        assert state.image_capture.requests == []
    if state.case == "general_multi":
        assert state.source_calls == {"brain": 1}


def test_doc290_original_user_input_is_lossless_at_dispatch(captured_entry):
    """Gate A red: BrainRunRequest currently folds meaningful whitespace."""
    state = captured_entry
    assert state.record.request.user_input == state.original
    for capture in state.captures:
        actual_digest = hashlib.sha256(capture["user"]["user_input"].encode("utf-8")).hexdigest()
        expected_digest = hashlib.sha256(state.original.encode("utf-8")).hexdigest()
        assert actual_digest == expected_digest, "BrainRunRequest folds original whitespace before HTTP dispatch"
    assert state.captures[1]["user"]["protected_user_direction"] == state.original


def test_doc290_bound_contracts_survive_both_stages(captured_entry):
    state = captured_entry
    plan, finalizer = [item["user"] for item in state.captures]
    context = finalizer["frozen_render_context"]
    schema = finalizer["return_schema"]["canonical_provider_prompts"][0]
    prompts = state.captures[1]["response"]["canonical_provider_prompts"]
    count = 3 if state.case == "general_multi" else 1
    assert len(prompts) == len(context["deliverables"]) == count
    assert [item["output_index"] for item in prompts] == list(range(1, count + 1))
    for prompt in prompts:
        assert set(schema) <= set(prompt)
        assert prompt["review_status"] == "approved"
        assert prompt["user_direction_integrity"] == {
            "contract_version": "v3_user_direction_integrity_v1",
            "owner": "remote_v3_llm_brain",
            "status": "preserved",
        }
        for key in (
            "human_naturalness_decision", "reference_channel_ownership_decision",
            "human_developmental_age_decision", "human_developmental_presence_decision",
        ):
            requirement = context.get(key, {})
            if requirement.get("required") is True:
                assert prompt[key]["owner"] == requirement["owner"]
                assert prompt[key]["contract_version"] == requirement["contract_version"]
                assert requirement["frozen_binding"] == context["frozen_binding"]

    metadata = state.record.request.metadata
    if state.case == "general_multi":
        contract = VariationExecutionContract.model_validate(context["variation_execution_contract"])
        assert contract.computed_digest() == contract.contract_digest
        assert context["frozen_binding"]["variation_execution_contract"] == {
            "contract_version": contract.contract_version,
            "contract_digest": contract.contract_digest,
        }
        assert plan["variation_execution_contract"] == context["variation_execution_contract"]
        assert context["variation_execution_contract_required"] is True
        for prompt in prompts:
            assert prompt["variation_execution_receipt"] == {
                "contract_version": contract.contract_version,
                "contract_digest": contract.contract_digest,
                "output_index": prompt["output_index"],
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            }
        projection = metadata["doc270_general_original_source_projection"]
        assert [item["asset_id"] for item in projection["sources"]] == state.source_ids
        assert metadata["doc270_general_source_activation_receipts"][0]["state"] == "activated_resolved"
        assert metadata["doc270_general_command_identity"]
        assert len(metadata["doc281_general_output_source_bindings_v1"]) == count
        output_bindings = metadata["doc281_general_output_source_bindings_v1"]
        assert [item["output_index"] for item in output_bindings] == list(range(1, count + 1))
        assert len({item["output_nonce"] for item in output_bindings}) == count
        assert all(len(item["output_binding_digest"]) == 64 for item in output_bindings)
        source = projection["sources"][0]
        original_source = next(item for item in state.source_snapshot["entries"] if item["asset_id"] == state.source_ids[0])
        assert source["content_sha256"] == original_source["content_sha256"]
        assert source["reference_id"] == original_source["reference_id"]
        assert metadata["doc270_general_source_activation_receipts"][0]["source_library_snapshot_digest"] == state.source_snapshot["snapshot_digest"]
        assert [item["asset_id"] for item in plan["uploaded_assets"]] == state.source_ids
        assert [item["asset_id"] for item in context["reference_bindings"]] == state.source_ids
    else:
        assert "variation_execution_receipt" not in schema
        assert "variation_execution_contract" not in plan

    if state.case == "professional_ecommerce":
        assert plan["ecommerce_creative_context"] == context["ecommerce_creative_context"]
        physical_plan = metadata["physical_renderer_reference_plans"]["1"]
        assert PhysicalRendererReferencePlan.model_validate(physical_plan).model_dump(mode="json") == physical_plan
        selected_ids = context["deliverables"][0]["metadata"]["selected_product_truth_asset_ids"]
        assert physical_plan["reference_image_asset_ids"] == [*selected_ids, *state.identity_ids]
        assert set(selected_ids) <= set(state.product_ids)
        assert physical_plan["reference_image_count"] == 4
        assert physical_plan["job_id"] == state.record.job_id
        assert physical_plan["output_index"] == 1
        assert physical_plan["projection_digest"] == metadata["professional_ecommerce_physical_product_projections"]["1"]["projection_digest"]
        for item in physical_plan["references"]:
            from pathlib import Path

            assert hashlib.sha256(Path(item["file_path"]).read_bytes()).hexdigest() == item["content_sha256"]
        assert "product_truth_selection_role" in plan["return_schema"]["image_set_plan"]["evidence_dimensions_by_output"][0]
        assert "human_realism" in context["active_shared_capability_ids"]
    else:
        assert "ecommerce_creative_context" not in plan
        assert "ecommerce_creative_context" not in context
        assert "ecommerce_context_instructions" not in finalizer
    ownership = context.get("reference_channel_ownership_decision")
    if ownership:
        owners = metadata["resolved_constraint_ledger"]["provider_projection"]["capability_projection"]["resolved_reference_policy_package"]["effective_channel_owners"]
        assert ownership["reference_owned_channels"] == sorted(key for key, owner in owners.items() if owner.startswith("reference:"))
        assert ownership["current_request_owned_channels"] == sorted(key for key, owner in owners.items() if owner in {"current_prompt", "current_prompt_or_defaults"})


def test_doc290_expression_authority_survives_in_system_and_finalizer(captured_entry):
    plan = captured_entry.captures[0]
    rule = HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS
    assert plan["system"].count(rule) == 1
    assert captured_entry.captures[1]["user"]["human_expression_authenticity_instructions"] == rule
    print("DOC290_DUPLICATE " + _json({
        "case": captured_entry.case,
        "stage": "plan",
        "remove_candidate": "user.human_expression_authenticity_instructions",
        "retain": "system.HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS",
        "identical_text_bytes": _bytes(rule),
    }))


def test_doc290_plan_expression_rule_has_one_authoritative_copy(captured_entry):
    """Gate A red target for the bounded plan-only deletion, not finalization."""
    plan = captured_entry.captures[0]
    rule = HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS
    copies = plan["system"].count(rule) + plan["user_text"].count(rule)
    assert copies == 1


def test_doc290_paired_redundancy_preserves_all_other_payload_fields(captured_entry):
    """Reconstruct only the old duplicate in the same captured HTTP body."""
    for capture in captured_entry.captures:
        user = capture["user"]
        if user["stage"] == "plan":
            remove = "human_expression_authenticity_instructions"
            duplicate = HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS
            assert duplicate in capture["system"]
            retained = "system.HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS"
        elif captured_entry.case == "professional_ecommerce":
            remove = "ecommerce_creative_context"
            duplicate = user["frozen_render_context"][remove]
            retained = "user.frozen_render_context.ecommerce_creative_context"
        else:
            continue
        assert remove not in user
        duplicated = {**deepcopy(user), remove: duplicate}
        assert set(duplicated) - set(user) == {remove}
        assert all(duplicated[key] == user[key] for key in user)
        assert duplicated["return_schema"] == user["return_schema"]
        body = deepcopy(capture["body"])
        body["messages"][1]["content"] = _json(duplicated)
        simulated = httpx.Request("POST", "https://doc290.invalid/v1/chat/completions", json=body).content
        assert len(simulated) > len(capture["raw_body"])
        assert json.loads(simulated)["messages"][0] == capture["body"]["messages"][0]
        print("DOC290_PAIRED_REDUNDANCY " + _json({
            "case": captured_entry.case,
            "stage": user["stage"],
            "remove_candidate": "user." + remove,
            "retain": retained,
            "user_json_bytes_saved": _bytes(_json(duplicated)) - _bytes(capture["user_text"]),
            "http_body_bytes_saved": len(simulated) - len(capture["raw_body"]),
            "schema_unchanged": True,
            "all_other_fields_unchanged": True,
        }))


@pytest.mark.parametrize("model", INPUT_MODELS, ids=lambda model: model.__name__)
@pytest.mark.parametrize("original", RAW_INPUTS)
def test_doc290_four_model_user_input_fidelity(model, original):
    request = model(user_input=original)
    assert request.user_input.encode("utf-8") == original.encode("utf-8")
    assert model.model_validate_json(request.model_dump_json()).user_input == original
    request.user_input = original + '\r\n"Assigned"\t '
    assert request.user_input == original + '\r\n"Assigned"\t '


@pytest.mark.parametrize("model", INPUT_MODELS, ids=lambda model: model.__name__)
@pytest.mark.parametrize("invalid", ("", " \t\r\n ", 1, [], {}))
def test_doc290_four_model_rejects_blank_and_wrong_type(model, invalid):
    with pytest.raises(ValidationError):
        model(user_input=invalid)


def test_doc290_project_optional_input_and_template_normalization_are_unchanged():
    for payload in ({}, {"user_input": None}):
        request = CreateProjectJobRequest(**payload, template_id=" \tgeneral_template\r\n")
        assert request.user_input is None
        assert request.template_id == "general_template"
    with pytest.raises(ValidationError):
        CreateProjectJobRequest(template_id=" \t\r\n")
    for model in INPUT_MODELS[1:]:
        for payload in ({}, {"user_input": None}):
            with pytest.raises(ValidationError):
                model(**payload)
        assert model.model_json_schema()["properties"]["user_input"] == {"title": "User Input", "type": "string"}


@pytest.mark.parametrize("case", CASES)
def test_doc290_normal_entry_preserves_outer_whitespace(tmp_path, offline_transport, case):
    original = ' \r\n\t' + _user_input(case) + '\r\n"A\tB"\n  '
    state = _capture_entry(tmp_path, offline_transport, case, original=original)
    assert state.created["status"] == "planned"
    assert state.record.request.user_input == original
    assert [item.user_input for item in state.requests] == [original, original]
    for capture in state.captures:
        assert capture["user"]["user_input"].encode("utf-8") == original.encode("utf-8")
    assert state.captures[-1]["user"]["protected_user_direction"] == original
    store_root = tmp_path / "reload"
    PersistentProductJobStore(storage_root=store_root).save(state.record)
    restored = PersistentProductJobStore(storage_root=store_root).get(state.record.job_id)
    assert restored is not None
    assert restored.request.user_input == original
    assert restored.request.metadata["frozen_remote_creative_brain"] == state.record.request.metadata["frozen_remote_creative_brain"]
    assert restored.request.metadata["capability_plan_provenance"] == state.record.request.metadata["capability_plan_provenance"]


@pytest.mark.parametrize("nested", (None, {}, "old_invalid_context", {"product": "frozen"}))
def test_doc290_ecommerce_finalizer_dedup_keeps_metadata_only_history(nested):
    context = {"deliverables": [{"output_index": 1}], "frozen_binding": {"ledger_id": "old-ledger"}}
    if nested is not None:
        context["ecommerce_creative_context"] = nested
    metadata_context = {"product": "metadata-only history"}
    request = BrainRunRequest(
        user_input="Keep the product truth.", stage="provider_prompt_finalize",
        metadata={"canonical_prompt_context": context, "ecommerce_creative_context": metadata_context},
    )
    payload = json.loads(build_remote_payload(request))
    assert payload["frozen_render_context"] == context
    if isinstance(nested, dict):
        assert "ecommerce_creative_context" not in payload
        assert ("ecommerce_context_instructions" in payload) is bool(nested)
    else:
        assert payload["ecommerce_creative_context"] == metadata_context
        assert "ecommerce_context_instructions" in payload


def _combined_recovery_script():
    return [
        lambda _response: "{invalid json",
        lambda response: {key: value for key, value in response.items() if key != "visual_task_profile"},
        lambda _response: "{invalid json",
        lambda response: response,
        lambda _response: "{invalid json",
        lambda response: {**response, "canonical_provider_prompts": []},
        lambda _response: "{invalid json",
        lambda response: response,
    ]


@pytest.mark.parametrize("step, expected_calls", ((60.0, 8), (110.0, 5)))
def test_doc290_combined_recovery_uses_one_deadline(tmp_path, monkeypatch, offline_transport, step, expected_calls):
    state = offline_transport
    state.clock = SimpleNamespace(now=1000.0, step=step)
    monkeypatch.setattr(brain_providers, "time", SimpleNamespace(perf_counter=lambda: state.clock.now))
    state.response_script = _combined_recovery_script()
    original = ' \r\nCreate one quiet landscape.\tCopy "A & B".\n  '
    state = _capture_entry(tmp_path, state, "general_single", original=original)
    assert len(state.captures) == expected_calls
    assert [item["user"]["stage"] for item in state.captures] == ["plan"] * 4 + ["provider_prompt_finalize"] * (expected_calls - 4)
    assert all(item is state.budgets[0] for item in state.budgets)
    assert all(item["budget"] is state.budgets[0] for item in state.captures)
    assert {item["deadline"] for item in state.captures} == {1520.0}
    remaining = [520.0 - step * index for index in range(expected_calls)]
    assert [item["remaining"] for item in state.captures] == remaining
    assert [item["timeout"]["read"] for item in state.captures] == [min(300.0, value) for value in remaining]
    assert all(item["user"]["user_input"] == original for item in state.captures)
    assert all(item.user_input == original for item in state.requests)
    for start in (0, 2, 4, 6):
        if start + 1 < expected_calls:
            assert state.captures[start]["user"] == state.captures[start + 1]["user"]
    first, recovered = state.requests[:2]
    assert recovered.model_dump(exclude={"metadata"}) == first.model_dump(exclude={"metadata"})
    assert recovered.metadata["remote_semantic_contract_recovery"]["same_frozen_request"] is True
    assert all(recovered.metadata[key] == value for key, value in first.metadata.items())
    if expected_calls == 8:
        assert state.created["status"] == "planned"
        assert state.response_script == []
        assert state.failures == []
        assert len(state.requests) == 4
        assert state.requests[2].metadata["canonical_prompt_context"] == state.requests[3].metadata["canonical_prompt_context"]
        assert state.requests[3].metadata["canonical_prompt_signoff_recovery"]["same_frozen_context"] is True
        assert [brain_providers.pop_transport_receipt(deepcopy(item))["attempts"] for item in state.responses] == [2, 2, 2, 2]
        audit = state.record.planning_result.metadata["llm_brain"]
        assert audit["llm_used"] is True and audit["fallback_used"] is False
    else:
        assert state.created["status"] == "blocked"
        assert len(state.requests) == 3
        assert state.record.planning_result is None
        outcome = state.record.request.metadata["remote_creative_brain_outcome"]
        assert outcome["state"] == "blocked"
        assert len(state.failures) == 1
        assert isinstance(state.failures[0], brain_providers.BrainExecutionBudgetExceeded)
        assert outcome["remote_brain_execution_budget"]["remaining_ms"] == 0
    print("DOC290_RECOVERY " + _json({
        "http_attempts": len(state.captures), "provider_runs": len(state.requests),
        "stage": [item["user"]["stage"] for item in state.captures],
        "deadline": 1520.0, "remaining_seconds": remaining, "status": state.created["status"],
    }))


def test_doc290_historical_frozen_plan_reload_requires_exact_saved_text(tmp_path, monkeypatch, offline_transport):
    """Historical normalized text stays usable, but is never a fuzzy match."""
    state = offline_transport
    state.case = "historical_anchor"
    handlers, _catalog = _handlers(tmp_path)
    service = handlers.service
    asset_id = _ready_product_upload(handlers, filename="historical-root.png", color=(184, 140, 120))
    asset = service.get_uploaded_asset(asset_id)
    service.asset_store._save_record(asset.model_copy(update={"role": "face_reference"}))
    service.scenario_runtime.llm_brain_adapter = V3LLMBrainAdapter(provider=state.provider)
    old_text = 'Prepare one straight-on Face Identity anchor of this same person. Copy "A & B".'
    payload = {
        "user_input": old_text,
        "scenario_selection": {"scenario_id": "general_creative"},
        "uploaded_asset_ids": [asset_id],
        "metadata": {"project_id": "project_doc290_history", "requested_image_count": 1, "require_real_images": True},
    }
    first = service.create_professional_anchor_preparation_job(payload, view_role="standard_front")
    assert first.status.value == "planned"
    assert [item["user"]["stage"] for item in state.captures] == ["plan", "provider_prompt_finalize"]
    source = service.get_job_record(first.job_id)
    frozen = deepcopy(source.request.metadata["frozen_remote_creative_brain"])
    provenance = deepcopy(source.request.metadata["capability_plan_provenance"])
    store_root = tmp_path / "history"
    PersistentProductJobStore(storage_root=store_root).save(source)
    service.job_store = PersistentProductJobStore(storage_root=store_root)
    reloaded = service.get_job_record(first.job_id)
    assert reloaded is not None and reloaded.request.user_input == old_text
    assert reloaded.request.metadata["frozen_remote_creative_brain"] == frozen
    assert reloaded.request.metadata["capability_plan_provenance"] == provenance

    def no_resign(_request):
        raise AssertionError("Historical frozen reuse must not call Brain again")

    monkeypatch.setattr(state.provider, "run", no_resign)
    continuation = service.create_professional_anchor_preparation_job(
        deepcopy(payload), view_role="standard_front", reference_evidence_ids=[asset_id],
        stage_plan_source_job_id=first.job_id,
    )
    assert continuation.status.value == "planned"
    continued = service.get_job_record(continuation.job_id)
    assert continued.request.user_input == old_text
    assert continued.request.metadata["capability_plan_provenance"]["source_job_id"] == first.job_id
    reused = continued.request.metadata["frozen_remote_creative_brain"]
    for key in ("capability_plan_id", "capability_plan_fingerprint", "template_id", "scenario_id"):
        assert reused[key] == frozen[key]
    assert reused["brain_result"]["canonical_provider_prompts"] == frozen["brain_result"]["canonical_provider_prompts"]
    assert reused["brain_result"]["audit"]["frozen_execution_reuse"] is True
    for different in (' ' + old_text + ' ', '\r\n' + old_text + '\r\n', old_text.replace("one", "one\t")):
        with pytest.raises(ValueError, match="^professional_anchor_stage_plan_source_mismatch$"):
            service.create_professional_anchor_preparation_job(
                {**deepcopy(payload), "user_input": different}, view_role="standard_front",
                reference_evidence_ids=[asset_id], stage_plan_source_job_id=first.job_id,
            )
    unchanged = service.get_job_record(first.job_id)
    assert unchanged.request.user_input == old_text
    assert unchanged.request.metadata["frozen_remote_creative_brain"] == frozen
    assert len(state.captures) == 2
