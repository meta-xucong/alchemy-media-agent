"""Doc162: strict semantic recovery stays remote-only and bounded."""

from __future__ import annotations

import json

from PIL import Image
import pytest

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainPromptContractInvalid,
    BrainProviderError,
    BrainTransportTimeoutError,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    active_review_contract,
    inspection_reference_paths,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _complete_profile() -> dict:
    return {
        "rendering_intent": {
            "rendering_mode": "photoreal",
            "stylization_scope": "none",
            "decision_owner": "remote_brain",
        },
        "developmental_age_intent": "not_applicable",
        "reference_channel_ownership_intent": {
            "applicability": "not_applicable",
            "decision_owner": "remote_brain",
            "reference_owned_channels": [],
            "current_request_owned_channels": [],
            "evidence_ids": [],
            "confidence": 0.95,
        },
        "subject_entities": [],
        "visual_intent_tags": ["photographic_observation"],
        "unknown_requirements": [],
        "confidence": 0.95,
        "evidence": [],
    }


def _complete_activation() -> dict:
    return {
        "requested_capabilities": [],
        "rejected_capabilities": [],
        "unresolved_signals": [],
        "confidence": 0.95,
    }


class _SequencedSemanticProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, *, recover: bool) -> None:
        super().__init__()
        self.recover = recover

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage != "plan":
            return payload
        if len(self.requests) == 1 or not self.recover:
            payload["visual_task_profile"] = {
                "rendering_intent": _complete_profile()["rendering_intent"],
            }
        else:
            payload["visual_task_profile"] = _complete_profile()
        payload["capability_activation_intent"] = _complete_activation()
        return payload


class _CompactPlanOnlyProvider(EcommerceRemoteBrainTestProvider):
    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        payload.pop("canonical_provider_prompts", None)
        return payload


class _InvalidPlanPromptDraftProvider(EcommerceRemoteBrainTestProvider):
    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "plan":
            payload["canonical_provider_prompts"] = [
                {
                    "output_index": 1,
                    "prompt": "Invalid one-output draft for a larger frozen set.",
                    "review_status": "approved",
                }
            ]
        return payload


class _TimeoutAfterInvalidPlanPromptDraftProvider(_InvalidPlanPromptDraftProvider):
    def run(self, request):  # noqa: ANN001
        if len(self.requests) >= 1 and request.stage == "plan":
            self.requests.append(request.model_dump(mode="json"))
            raise BrainTransportTimeoutError(
                stage=request.stage,
                timeout_seconds=210.0,
                elapsed_ms=210015,
                timeout_phase="read_timeout",
                response_started=True,
                first_content_observed=False,
                complete_response_observed=False,
                json_parse_started=False,
                json_parse_completed=False,
            )
        return super().run(request)


class _InvalidImageSetCardinalityProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, *, mode: str = "shot_plan_count") -> None:
        super().__init__()
        self.mode = mode

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "plan":
            if self.mode == "not_dict":
                payload["image_set_plan"] = "secret path C:/do/not/leak"
            else:
                payload["image_set_plan"] = {
                    "set_goal": "Invalid cardinality fixture",
                    "image_count": (
                        request.requested_image_count - 1
                        if self.mode == "wrong_image_count"
                        else request.requested_image_count
                    ),
                    "size": request.requested_image_size,
                    "shot_plan": ["secret shot text must not appear in trace"],
                    "composition_rules": [],
                    "quality_bar": [],
                }
            payload.pop("canonical_provider_prompts", None)
        return payload


class _InvalidImageSetSchemaProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, *, malformed_field: str = "selected_product_truth_asset_ids") -> None:
        super().__init__()
        self.malformed_field = malformed_field

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "plan":
            evidence_entry = {
                "output_index": 1,
                "evidence_dimensions": ["front_apparel_truth"],
                "selected_product_truth_asset_ids": ["product_truth_front"],
            }
            if self.malformed_field == "selected_product_truth_asset_ids":
                evidence_entry["selected_product_truth_asset_ids"] = (
                    "secret_product_truth_id_must_not_leak"
                )
            elif self.malformed_field == "evidence_dimensions":
                evidence_entry["evidence_dimensions"] = "secret_dimension_must_not_leak"
            payload["image_set_plan"] = {
                "set_goal": "Schema fixture with valid cardinality",
                "image_count": request.requested_image_count,
                "size": request.requested_image_size,
                "shot_plan": [
                    f"safe fixture direction {index}"
                    for index in range(1, request.requested_image_count + 1)
                ],
                "evidence_dimensions_by_output": [evidence_entry],
                "composition_rules": [],
                "quality_bar": [],
            }
            payload.pop("canonical_provider_prompts", None)
        return payload


def _strict_request(adapter: V3LLMBrainAdapter, *, count: int = 1):  # noqa: ANN201
    return adapter.build_request(
        user_input="Create one factual studio photograph of a ceramic vessel with no person visible.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"requested_image_count": count, "require_real_images": True},
    )


def test_doc162_one_remote_schema_reanswer_recovers_same_frozen_request(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _SequencedSemanticProvider(recover=True)
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter))

    assert result.audit["remote_semantic_contract_recovery_attempted"] is True
    assert result.audit["remote_semantic_contract_recovery_succeeded"] is True
    assert result.audit["remote_semantic_contract_recovery_initial_rejected_sections"] == [
        "visual_task_profile"
    ]
    assert result.audit["remote_semantic_contract_recovery_final_rejected_sections"] == []
    assert len(provider.requests) == 2
    first, second = provider.requests
    assert first["user_input"] == second["user_input"]
    assert first["requested_image_count"] == second["requested_image_count"] == 1
    assert "remote_semantic_contract_recovery" not in first["metadata"]
    assert second["metadata"]["remote_semantic_contract_recovery"] == {
        "contract_version": "v3_remote_semantic_contract_recovery_v1",
        "attempt": 1,
        "rejected_sections": ["visual_task_profile"],
        "same_frozen_request": True,
    }


def test_doc162_two_invalid_semantic_answers_fail_closed_after_exactly_two_calls(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _SequencedSemanticProvider(recover=False)
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter))

    assert len(provider.requests) == 2
    assert result.audit["remote_contract_partial_fallback"] is True
    assert result.audit["remote_contract_rejected_sections"] == ["visual_task_profile"]
    assert result.audit["remote_semantic_contract_recovery_attempted"] is True
    assert result.audit["remote_semantic_contract_recovery_succeeded"] is False
    assert result.audit["remote_semantic_contract_recovery_final_rejected_sections"] == [
        "visual_task_profile"
    ]


def test_doc259_compact_plan_does_not_require_finalizer_only_canonical_prompts(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _CompactPlanOnlyProvider()
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter, count=6))

    assert len(provider.requests) == 1
    assert result.audit["remote_semantic_contract_recovery_attempted"] is False
    assert "remote_contract_rejected_sections" not in result.audit
    assert result.image_set_plan.image_count == 6
    assert len(result.image_set_plan.shot_plan) == 6


def test_doc259_invalid_plan_prompt_draft_is_still_rejected_and_traced(
    monkeypatch,
    tmp_path,
) -> None:
    trace_file = tmp_path / "brain-stage-trace.jsonl"
    monkeypatch.setenv("V3_BRAIN_STAGE_TRACE_FILE", str(trace_file))
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _InvalidPlanPromptDraftProvider()
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter, count=6))

    assert len(provider.requests) == 2
    assert result.audit["remote_contract_rejected_sections"] == ["canonical_provider_prompts"]
    assert result.audit["remote_semantic_contract_recovery_attempted"] is True
    trace_events = [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rejected_events = [
        event
        for event in trace_events
        if event.get("event") in {"semantic_plan_schema_validated", "semantic_recovery_provider_call"}
    ]
    assert rejected_events
    assert all(
        event.get("remote_contract_rejected_sections") == ["canonical_provider_prompts"]
        for event in rejected_events
        if event.get("remote_contract_rejected_count") == 1
    )
    serialized = "\n".join(json.dumps(event, sort_keys=True) for event in trace_events)
    assert "invalid one-output draft" not in serialized
    assert str(tmp_path).replace("\\", "\\\\") not in serialized


def test_doc259_timeout_after_contract_reanswer_preserves_initial_rejected_section(
    monkeypatch,
) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _TimeoutAfterInvalidPlanPromptDraftProvider()
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter, count=6))
    error = ScenarioRuntime._remote_creative_brain_block(
        "remote_creative_brain_required_for_template",
        result,
    )
    outcome = getattr(error, "remote_creative_brain_outcome")

    assert len(provider.requests) == 2
    assert result.fallback_used is True
    assert result.audit["remote_semantic_contract_recovery_initial_rejected_sections"] == [
        "canonical_provider_prompts"
    ]
    assert outcome["remote_contract_rejected_sections"] == ["canonical_provider_prompts"]
    assert outcome["remote_brain_transport_failure"]["timeout_seconds"] == 210.0
    assert outcome["remote_brain_transport_failure"]["response_started"] is True
    assert outcome["remote_brain_transport_failure"]["first_content_observed"] is False


def test_doc259_image_set_plan_rejection_records_only_safe_cardinality_numbers(
    monkeypatch,
    tmp_path,
) -> None:
    trace_file = tmp_path / "brain-stage-trace.jsonl"
    monkeypatch.setenv("V3_BRAIN_STAGE_TRACE_FILE", str(trace_file))
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _InvalidImageSetCardinalityProvider()
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter, count=6))
    error = ScenarioRuntime._remote_creative_brain_block(
        "remote_creative_brain_image_set_plan_invalid",
        result,
        rejected_sections=result.audit["remote_contract_rejected_sections"],
    )
    outcome = getattr(error, "remote_creative_brain_outcome")

    assert result.audit["remote_contract_rejected_sections"] == ["image_set_plan"]
    assert result.audit["remote_image_set_cardinality_audit"] == {
        "expected_image_count": 6,
        "remote_image_count": 6,
        "remote_shot_plan_count": 1,
        "cardinality_valid": False,
    }
    assert outcome["remote_image_set_cardinality_audit"] == {
        "expected_image_count": 6,
        "remote_image_count": 6,
        "remote_shot_plan_count": 1,
        "cardinality_valid": False,
    }
    trace_events = [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rejected = [
        event
        for event in trace_events
        if event.get("event") == "semantic_plan_schema_validated"
        and event.get("remote_contract_rejected_sections") == ["image_set_plan"]
    ]
    assert rejected
    assert rejected[0]["expected_image_count"] == 6
    assert rejected[0]["remote_image_count"] == 6
    assert rejected[0]["remote_shot_plan_count"] == 1
    assert rejected[0]["cardinality_valid"] is False
    serialized = "\n".join(json.dumps(event, sort_keys=True) for event in trace_events)
    assert "secret shot text" not in serialized
    assert str(tmp_path).replace("\\", "\\\\") not in serialized


@pytest.mark.parametrize(
    ("malformed_field", "expected_path"),
    [
        (
            "selected_product_truth_asset_ids",
            "image_set_plan.evidence_dimensions_by_output.item.selected_product_truth_asset_ids",
        ),
        (
            "evidence_dimensions",
            "image_set_plan.evidence_dimensions_by_output.item.evidence_dimensions",
        ),
    ],
)
def test_doc259_image_set_plan_validation_failure_records_only_safe_field_paths(
    monkeypatch,
    tmp_path,
    malformed_field,
    expected_path,
) -> None:
    trace_file = tmp_path / "brain-stage-trace.jsonl"
    monkeypatch.setenv("V3_BRAIN_STAGE_TRACE_FILE", str(trace_file))
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _InvalidImageSetSchemaProvider(malformed_field=malformed_field)
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter, count=6))
    error = ScenarioRuntime._remote_creative_brain_block(
        "remote_creative_brain_image_set_plan_invalid",
        result,
        rejected_sections=result.audit["remote_contract_rejected_sections"],
    )
    outcome = getattr(error, "remote_creative_brain_outcome")

    assert result.audit["remote_contract_rejected_sections"] == ["image_set_plan"]
    assert result.audit["remote_image_set_cardinality_audit"] == {
        "expected_image_count": 6,
        "remote_image_count": 6,
        "remote_shot_plan_count": 6,
        "cardinality_valid": True,
    }
    validation_audit = result.audit["remote_image_set_validation_audit"]
    assert validation_audit["validation_error_count"] >= 1
    assert expected_path in validation_audit["validation_error_paths"]
    assert validation_audit["validation_error_types"]
    assert outcome["remote_image_set_validation_audit"]["validation_error_paths"] == (
        validation_audit["validation_error_paths"]
    )
    trace_events = [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rejected = [
        event
        for event in trace_events
        if event.get("event") == "semantic_plan_schema_validated"
        and event.get("remote_contract_rejected_sections") == ["image_set_plan"]
    ]
    assert rejected
    assert rejected[0]["cardinality_valid"] is True
    assert expected_path in rejected[0]["validation_error_paths"]
    assert rejected[0]["validation_error_types"]
    serialized = "\n".join(json.dumps(event, sort_keys=True) for event in trace_events)
    assert "secret_product_truth_id" not in serialized
    assert "secret_dimension" not in serialized
    assert "safe fixture direction" not in serialized
    assert str(tmp_path).replace("\\", "\\\\") not in serialized


@pytest.mark.parametrize(
    ("mode", "expected_audit"),
    [
        (
            "not_dict",
            {
                "expected_image_count": 6,
                "remote_image_count": None,
                "remote_shot_plan_count": 0,
                "cardinality_valid": False,
            },
        ),
        (
            "wrong_image_count",
            {
                "expected_image_count": 6,
                "remote_image_count": 5,
                "remote_shot_plan_count": 1,
                "cardinality_valid": False,
            },
        ),
    ],
)
def test_doc259_image_set_plan_numeric_audit_handles_non_dict_and_wrong_count(
    monkeypatch,
    tmp_path,
    mode,
    expected_audit,
) -> None:
    trace_file = tmp_path / "brain-stage-trace.jsonl"
    monkeypatch.setenv("V3_BRAIN_STAGE_TRACE_FILE", str(trace_file))
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _InvalidImageSetCardinalityProvider(mode=mode)
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter, count=6))

    assert result.audit["remote_contract_rejected_sections"] == ["image_set_plan"]
    assert result.audit["remote_image_set_cardinality_audit"] == expected_audit
    trace_events = [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rejected = [
        event
        for event in trace_events
        if event.get("event") == "semantic_plan_schema_validated"
        and event.get("remote_contract_rejected_sections") == ["image_set_plan"]
    ]
    assert rejected
    for key, value in expected_audit.items():
        assert rejected[0][key] == value
    serialized = "\n".join(json.dumps(event, sort_keys=True) for event in trace_events)
    assert "secret path" not in serialized
    assert "secret shot text" not in serialized
    assert str(tmp_path).replace("\\", "\\\\") not in serialized


def test_doc259_finalizer_still_requires_complete_canonical_provider_prompts(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _CompactPlanOnlyProvider()
    adapter = V3LLMBrainAdapter(provider=provider)
    request = _strict_request(adapter, count=6).model_copy(
        update={"stage": "provider_prompt_finalize"},
        deep=True,
    )

    with pytest.raises(BrainPromptContractInvalid):
        adapter.finalize_canonical_provider_prompts(request)


def test_doc162_recovery_payload_requests_complete_reanswer_not_patch(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=_SequencedSemanticProvider(recover=True))
    request = _strict_request(adapter)
    recovery_request = request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                "remote_semantic_contract_recovery": {
                    "contract_version": "v3_remote_semantic_contract_recovery_v1",
                    "attempt": 1,
                    "rejected_sections": ["visual_task_profile"],
                    "same_frozen_request": True,
                },
            }
        },
        deep=True,
    )

    payload = json.loads(build_remote_payload(recovery_request))

    assert payload["semantic_contract_recovery"]["same_frozen_request"] is True
    assert payload["semantic_contract_recovery"]["rejected_sections"] == ["visual_task_profile"]
    assert "Re-author the complete compact contract" in payload["remote_response_contract"]
    assert "do not return a patch" in payload["remote_response_contract"]


def test_doc259_compact_schema_and_recovery_payload_preserve_exact_requested_count(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=_SequencedSemanticProvider(recover=True))
    request = _strict_request(adapter, count=6)
    payload = json.loads(build_remote_payload(request))

    assert payload["requested_image_count"] == 6
    assert payload["return_schema"]["image_set_plan"]["image_count"] == (
        "integer exactly equal to requested_image_count"
    )
    assert payload["return_schema"]["image_set_plan"]["shot_plan"] == [
        "one original whole-image natural-language direction per requested output"
    ]

    recovery_request = request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                "remote_semantic_contract_recovery": {
                    "contract_version": "v3_remote_semantic_contract_recovery_v1",
                    "attempt": 1,
                    "rejected_sections": ["image_set_plan"],
                    "same_frozen_request": True,
                },
            }
        },
        deep=True,
    )
    recovery_payload = json.loads(build_remote_payload(recovery_request))
    assert recovery_payload["requested_image_count"] == 6
    assert recovery_payload["semantic_contract_recovery"]["same_frozen_request"] is True
    assert recovery_payload["semantic_contract_recovery"]["rejected_sections"] == ["image_set_plan"]


def test_doc162_transport_failure_does_not_trigger_semantic_recovery(monkeypatch) -> None:
    class _FailingProvider:
        provider = "remote_test"
        model = "remote_test_v1"

        def __init__(self) -> None:
            self.calls = 0

        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request):  # noqa: ANN001
            self.calls += 1
            raise BrainProviderError("remote brain provider failed: request timed out")

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _FailingProvider()
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter))

    assert provider.calls == 1
    assert result.llm_used is False
    assert result.audit["remote_semantic_contract_recovery_attempted"] is False


def _professional_review_metadata() -> dict:
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="profile"
    )
    return {
        "capability_execution_envelope": {
            "activation_plan": {
                "activation_mode": "enforced",
                "metadata": {
                    "professional_face_identity_quality_contract": planning[
                        "professional_face_identity_quality_contract"
                    ]
                },
            },
            "resolved_constraint_ledger": {
                "hard_semantic_contract": True,
                "review_contracts": [],
                "provider_projection": {},
            },
        },
        "professional_planning_metadata": planning,
        "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
        "professional_reference_stage": "profile",
    }


def test_doc162_professional_quality_contract_projects_typed_shared_vision_dimensions() -> None:
    contract = active_review_contract(_professional_review_metadata())

    assert contract["professional_identity_quality"]["applies"] is True
    assert "same_person_readability" in contract["score_dimensions"]
    assert "distinctive_feature_readability" in contract["score_dimensions"]
    assert "prompt_owned_channel_obedience" in contract["score_dimensions"]
    assert "professional_ai_overperfection" in contract["issue_codes"]


def test_doc162_professional_profile_review_keeps_three_original_sources(tmp_path) -> None:
    metadata = _professional_review_metadata()
    references = []
    for index, source_type in enumerate(("uploaded", "selected_output", "selected_output"), start=1):
        path = tmp_path / f"reference-{index}.png"
        Image.new("RGB", (32, 32), (index * 20, 40, 60)).save(path)
        references.append(
            {
                "asset_id": f"source_{index}",
                "file_path": str(path),
                "source_type": source_type,
                "role": "face_reference",
                "use_policy": "identity",
            }
        )
    metadata["reference_assets"] = references

    assert inspection_reference_paths(metadata) == [
        tmp_path / "reference-1.png",
        tmp_path / "reference-2.png",
        tmp_path / "reference-3.png",
    ]


def test_doc162_ordinary_review_still_caps_reference_sources_at_two(tmp_path) -> None:
    metadata = _professional_review_metadata()
    metadata.pop("professional_identity_reference_strategy")
    references = []
    for index in range(1, 4):
        path = tmp_path / f"ordinary-{index}.png"
        Image.new("RGB", (32, 32), (index * 20, 40, 60)).save(path)
        references.append({"asset_id": f"ordinary_{index}", "file_path": str(path)})
    metadata["reference_assets"] = references

    assert len(inspection_reference_paths(metadata)) == 2
