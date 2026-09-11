import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import alchemy_creative_agent_3_0.app.llm_brain.adapter as brain_adapter_module
from alchemy_creative_agent_3_0.app.llm_brain.adapter import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainPromptContractInvalid,
    BrainPromptRequestContractInvalid,
    BrainProviderError,
    BrainProviderUnavailable,
    BrainReferenceChannelOwnershipDecisionMissing,
    BrainSemanticPreflightMissing,
    BrainHumanNaturalnessDecisionMissing,
    BrainTransportTimeoutError,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import (
    CreateCreativeJobRequest,
    GenerateContinuation,
    GenerateJobRequest,
    ProductJobStatus,
    ProductJobStatusValue,
    SelectionResponse,
    SelectedResult,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    OutputRef,
    ProjectContextPackage,
    ProjectRecord,
)
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService


_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _save_output(
    store: V3GeneratedOutputStore,
    *,
    job_id: str,
    output_id: str,
    projection: dict,
) -> object:
    record = store.save_base64_output(
        job_id=job_id,
        candidate_id=f"candidate_{output_id[-4:]}",
        asset_id=f"asset_{output_id[-4:]}",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=_ONE_PIXEL_PNG,
        output_id=output_id,
        metadata={
            "scenario_id": "general_creative",
            "template_id": "general_template",
            "requested_image_count": 2,
            "variation_mode": "delivery_suite",
        },
    )
    envelope = {
        "activation_mode": "enforced",
        "envelope_id": "envelope_doc298",
        "execution_fingerprint": "fingerprint_doc298",
        "activation_plan": {},
        "resolved_constraint_ledger": {
            "ledger_id": "ledger_doc298",
            "provider_projection": {"capability_projection": dict(projection)},
        },
    }
    updated = store.update_metadata(record.output_id, {"capability_execution_envelope": envelope})
    assert updated is not None
    return updated


def _closure(job_id: str, records: list[object]) -> dict:
    return {
        "schema_version": "v3_output_delivery_closure_v1",
        "job_id": job_id,
        "status": "complete",
        "review_evidence_receipt_status": "complete",
        "final_delivery_status": "ready",
        "automatic_delivery_available": True,
        "eligible_output_ids": [record.output_id for record in records],
        "execution_fingerprint": "fingerprint_doc298",
        "envelope_id": "envelope_doc298",
        "ledger_id": "ledger_doc298",
        "outputs": [
            {
                "output_id": record.output_id,
                "asset_id": record.asset_id,
                "candidate_id": record.candidate_id,
                "content_sha256": record.metadata["content_sha256"],
            }
            for record in records
        ],
    }


def test_external_generate_cannot_inject_remote_brain_outcome() -> None:
    request = GenerateJobRequest(
        metadata={"remote_creative_brain_outcome": {"state": "blocked", "reason_code": "fake"}}
    )

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        V3ProductApiService._assert_external_generate_metadata_clean(request)  # noqa: SLF001


@pytest.mark.parametrize(
    "metadata",
    [
        {"_v3_resume_finalizing_review": True},
        {"_v3_background_worker_claim": True, "_v3_background_generation_attempt_id": "attempt"},
        {"vision_inspection_mode": "metadata_only"},
        {"max_visual_retry_attempts": 1},
        {"require_real_images": True},
        {"real_image_generation": True},
        {"visual_retry_patch": {"prompt_additions": ["untrusted"]}},
    ],
)
def test_external_generate_rejects_all_runtime_continuation_controls(metadata: dict[str, object]) -> None:
    request = GenerateJobRequest(metadata=metadata)

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        V3ProductApiService._assert_external_generate_metadata_clean(request)  # noqa: SLF001


def test_generate_continuation_is_strict_and_job_bound() -> None:
    with pytest.raises(ValidationError):
        GenerateContinuation(job_id="job_doc298", background_worker_claim="false")
    with pytest.raises(ValidationError):
        GenerateContinuation(
            job_id="job_doc298",
            background_worker_claim=True,
            background_generation_attempt_id="",
        )

    service = V3ProductApiService()
    created = service.create_job({"user_input": "Create one neutral image."})
    with pytest.raises(ValueError, match="generate_continuation_job_mismatch"):
        service.generate_job_with_continuation(
            created.job_id,
            {"quality_mode": "strict"},
            continuation=GenerateContinuation(job_id="job_other"),
        )


def test_generate_continuation_normalizes_legacy_visual_retry_patch_fields() -> None:
    continuation = GenerateContinuation(
        job_id="job_doc298",
        visual_retry_patch={
            "prompt_additions": "retain the intended composition",
            "negative_prompt_additions": ["watermark"],
            "reference_requirements": ("preserve the typed reference",),
            "brand_asset_reinforcement": ["preserve the supplied brand asset"],
        },
    )

    assert continuation.runtime_metadata()["visual_retry_patch"] == {
        "prompt_additions": ["retain the intended composition"],
        "negative_prompt_additions": ["watermark"],
        "reference_requirements": ["preserve the typed reference"],
        "brand_asset_reinforcement": ["preserve the supplied brand asset"],
    }


@pytest.mark.parametrize(
    "field_name",
    [
        "provider_hint_overrides",
        "provider",
        "prompt",
        "reasoning",
        "file_path",
        "asset_path",
    ],
)
def test_generate_continuation_rejects_unapproved_visual_retry_patch_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        GenerateContinuation(
            job_id="job_doc298",
            visual_retry_patch={field_name: ["untrusted continuation material"]},
        )


def test_generate_continuation_rejects_non_string_visual_retry_patch_content() -> None:
    with pytest.raises(ValidationError):
        GenerateContinuation(
            job_id="job_doc298",
            visual_retry_patch={"artifact_repair": [{"prompt": "untrusted nested material"}]},
        )


def test_create_cannot_inject_server_owned_brain_receipt() -> None:
    service = V3ProductApiService()
    request = CreateCreativeJobRequest(
        user_input="Create one neutral image.",
        metadata={"remote_creative_brain_outcome": {"state": "blocked"}},
    )

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service._assert_runtime_metadata_server_owned(  # noqa: SLF001
            request,
            trusted_capability_plan_reuse=False,
        )


def test_transport_call_entry_without_response_is_unknown_not_dispatched() -> None:
    failure = BrainTransportTimeoutError(
        stage="plan",
        timeout_seconds=7,
        elapsed_ms=7000,
        timeout_phase="connect_timeout",
        request_call_entered=True,
    )

    assert failure.request_acceptance == "unknown"
    assert failure.request_dispatched is False
    assert failure.safe_metadata()["request_acceptance"] == "unknown"


def test_finalizer_contract_failure_keeps_upstream_response_lifecycle(monkeypatch) -> None:
    class InvalidResponseProvider:
        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request: BrainRunRequest) -> dict:
            return {"canonical_provider_prompts": []}

    adapter = V3LLMBrainAdapter(provider=InvalidResponseProvider())
    monkeypatch.setattr(brain_adapter_module, "_enabled", lambda: True)
    monkeypatch.setattr(adapter, "_activation_scope_enabled", lambda request: True)
    request = BrainRunRequest(user_input="Create one neutral image.", requested_image_count=1)

    with pytest.raises(BrainPromptContractInvalid) as caught:
        adapter.finalize_canonical_provider_prompts(request)

    lifecycle = getattr(caught.value, "_remote_brain_finalizer_lifecycle")
    assert lifecycle == {
        "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
        "stage": "provider_prompt_finalize",
        "provider_available": True,
        "remote_brain_request_started": True,
        "response_started": True,
        "status": "blocked",
        "failure_family": "remote_brain_signoff",
        "failure_code": "invalid_response",
        "remote_brain_request_acceptance": "dispatched",
    }


def test_finalizer_contract_failure_without_transport_receipt_keeps_response_acceptance(monkeypatch) -> None:
    class LegacyResponseProvider:
        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request: BrainRunRequest) -> dict:
            return {"canonical_provider_prompts": []}

    adapter = V3LLMBrainAdapter(provider=LegacyResponseProvider())
    monkeypatch.setattr(brain_adapter_module, "_enabled", lambda: True)
    monkeypatch.setattr(adapter, "_activation_scope_enabled", lambda request: True)
    request = BrainRunRequest(user_input="Create one neutral image.", requested_image_count=1)

    with pytest.raises(BrainPromptContractInvalid) as caught:
        adapter.finalize_canonical_provider_prompts(request)

    audit = adapter.provider_failure_audit(caught.value, stage=request.stage)
    assert "remote_brain_transport_attempt" not in audit
    assert audit["remote_brain_request_acceptance"] == "dispatched"
    assert audit["remote_brain_request_started"] is True
    lifecycle = audit["remote_brain_finalizer_lifecycle"]
    assert lifecycle["remote_brain_request_acceptance"] == "dispatched"
    assert lifecycle["remote_brain_request_started"] is True
    assert lifecycle["response_started"] is True


def test_malformed_finalizer_request_is_local_and_never_retried(monkeypatch) -> None:
    calls = {"available": 0, "run": 0}

    class Provider:
        def available(self, *, force: bool = False) -> bool:
            calls["available"] += 1
            return True

        def run(self, request: BrainRunRequest) -> dict:
            calls["run"] += 1
            return {}

    adapter = V3LLMBrainAdapter(provider=Provider())
    monkeypatch.setattr(brain_adapter_module, "_enabled", lambda: True)
    monkeypatch.setattr(adapter, "_activation_scope_enabled", lambda request: True)
    request = BrainRunRequest(
        user_input="Create one real-camera portrait.",
        requested_image_count=1,
        metadata={
            "canonical_prompt_context": {
                "human_developmental_age_decision": "malformed"
            }
        },
    )

    with pytest.raises(BrainPromptRequestContractInvalid) as caught:
        adapter.finalize_canonical_provider_prompts(request)

    assert calls == {"available": 0, "run": 0}
    assert isinstance(caught.value.__cause__, brain_adapter_module.BrainDevelopmentalAgeDecisionMissing)
    audit = adapter.provider_failure_audit(caught.value, stage=request.stage)
    assert audit["remote_provider_error_class"] == "request_contract_invalid"
    assert audit["remote_brain_request_acceptance"] == "not_started"
    assert audit["remote_brain_finalizer_lifecycle"]["failure_code"] == "request_contract_invalid"


@pytest.mark.parametrize(
    ("context", "cause_type"),
    [
        (
            {"final_prompt_semantic_preflight": "malformed"},
            BrainSemanticPreflightMissing,
        ),
        (
            {
                "final_prompt_semantic_preflight": {
                    "required": True,
                    "owner": "remote_v3_llm_brain",
                    "scope": "whole_image_human_photographic_plausibility",
                    "revision_mode": "rewrite_complete_canonical_prompt",
                },
                "human_naturalness_decision": "malformed",
            },
            BrainHumanNaturalnessDecisionMissing,
        ),
        (
            {"reference_channel_ownership_decision": "malformed"},
            BrainReferenceChannelOwnershipDecisionMissing,
        ),
    ],
)
def test_malformed_required_finalizer_objects_fail_before_provider(
    monkeypatch,
    context,
    cause_type,
) -> None:
    calls = {"available": 0, "run": 0}

    class Provider:
        def available(self, *, force: bool = False) -> bool:
            calls["available"] += 1
            return True

        def run(self, request: BrainRunRequest) -> dict:
            calls["run"] += 1
            return {}

    adapter = V3LLMBrainAdapter(provider=Provider())
    monkeypatch.setattr(brain_adapter_module, "_enabled", lambda: True)
    monkeypatch.setattr(adapter, "_activation_scope_enabled", lambda request: True)
    request = BrainRunRequest(
        user_input="Create one real-camera portrait.",
        requested_image_count=1,
        metadata={"canonical_prompt_context": context},
    )

    with pytest.raises(BrainPromptRequestContractInvalid) as caught:
        adapter.finalize_canonical_provider_prompts(request)

    assert isinstance(caught.value.__cause__, cause_type)
    assert calls == {"available": 0, "run": 0}


@pytest.mark.parametrize("available_error", [BrainProviderUnavailable("missing"), RuntimeError("probe failed")])
def test_finalizer_preflight_failure_never_claims_request_dispatch(monkeypatch, available_error) -> None:
    calls = {"run": 0}

    class BrokenPreflightProvider:
        def available(self, *, force: bool = False) -> bool:
            raise available_error

        def run(self, request: BrainRunRequest) -> dict:
            calls["run"] += 1
            return {}

    adapter = V3LLMBrainAdapter(provider=BrokenPreflightProvider())
    monkeypatch.setattr(brain_adapter_module, "_enabled", lambda: True)
    monkeypatch.setattr(adapter, "_activation_scope_enabled", lambda request: True)
    request = BrainRunRequest(user_input="Create one neutral image.", requested_image_count=1)

    expected_error = BrainProviderUnavailable if isinstance(available_error, BrainProviderUnavailable) else BrainProviderError
    with pytest.raises(expected_error) as caught:
        adapter.finalize_canonical_provider_prompts(request)

    lifecycle = getattr(caught.value, "_remote_brain_finalizer_lifecycle")
    assert lifecycle["provider_available"] is False
    assert lifecycle["remote_brain_request_started"] is False
    assert lifecycle["response_started"] is False
    assert lifecycle["remote_brain_request_acceptance"] == "not_started"
    assert calls["run"] == 0


def test_finalizer_contract_failure_keeps_successful_transport_attempt_receipt_and_trace(
    monkeypatch,
    tmp_path,
) -> None:
    trace_file = tmp_path / "brain-stage-trace.jsonl"
    monkeypatch.setenv("V3_BRAIN_STAGE_TRACE_FILE", str(trace_file))

    class InvalidResponseProvider:
        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request: BrainRunRequest) -> dict:
            return {
                "canonical_provider_prompts": [],
                "_alchemy_brain_transport": {
                    "attempts": 1,
                    "json_serialization_recovery_attempted": False,
                    "json_serialization_recovery_succeeded": False,
                    "transport_attempt": {
                        "schema_version": "v3_brain_transport_attempt_v1",
                        "stage": "generate",
                        "request_acceptance": "dispatched",
                        "request_dispatched": True,
                        "protocol_fallback_attempted": True,
                        "response_started": True,
                        "first_content_observed": True,
                        "complete_response_observed": True,
                        "json_parse_started": True,
                        "json_parse_completed": True,
                        "json_recovery": False,
                    },
                },
            }

    adapter = V3LLMBrainAdapter(provider=InvalidResponseProvider())
    monkeypatch.setattr(brain_adapter_module, "_enabled", lambda: True)
    monkeypatch.setattr(adapter, "_activation_scope_enabled", lambda request: True)
    request = BrainRunRequest(user_input="Create one neutral image.", requested_image_count=1)

    with pytest.raises(BrainPromptContractInvalid) as caught:
        adapter.finalize_canonical_provider_prompts(request)

    audit = adapter.provider_failure_audit(caught.value, stage=request.stage)
    attempt = audit["remote_brain_transport_attempt"]
    assert attempt["attempts"] == 1
    assert attempt["request_acceptance"] == "dispatched"
    assert attempt["response_started"] is True
    assert attempt["json_parse_completed"] is True
    from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import _safe_remote_brain_transport_attempt

    assert _safe_remote_brain_transport_attempt(attempt)["request_acceptance"] == "dispatched"
    events = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]
    names = [event["event"] for event in events]
    returned = names.index("canonical_finalizer_provider_returned")
    validation_started = names.index("canonical_finalizer_schema_validation_started")
    validation_failed = names.index("canonical_finalizer_schema_validation_failed")
    assert returned < validation_started < validation_failed
    assert "canonical_finalizer_schema_validated" not in names
    failed_event = events[validation_failed]
    assert failed_event["request_acceptance"] == "dispatched"
    assert failed_event["protocol_fallback_attempted"] is True
    assert "provider_payload" not in failed_event
    assert "provider_url" not in failed_event


def test_finalizer_receipt_matchers_reject_non_integer_output_index() -> None:
    from alchemy_creative_agent_3_0.app.llm_brain.adapter import _matches_human_semantic_preflight_receipts

    assert not _matches_human_semantic_preflight_receipts(
        [{"output_index": "abc", "semantic_preflight_status": "approved"}],
        expected_count=1,
    )


def test_terminal_provider_error_class_wins_over_first_retry_timeout() -> None:
    from alchemy_creative_agent_3_0.app.llm_brain.adapter import _remote_provider_error_class

    first_timeout = BrainTransportTimeoutError(
        stage="plan",
        timeout_seconds=3,
        elapsed_ms=3000,
        timeout_phase="read_timeout",
        request_acceptance="dispatched",
        response_started=True,
    )
    terminal = BrainProviderError("remote brain provider failed: HTTP status code: 401")
    terminal.__cause__ = first_timeout

    assert _remote_provider_error_class(terminal) == "upstream_http_error"


def test_responses_protocol_fallback_does_not_hide_missing_model() -> None:
    from alchemy_creative_agent_3_0.app.llm_brain.providers import _is_unsupported_brain_protocol_error

    class NotFoundError(RuntimeError):
        status_code = 404

    assert _is_unsupported_brain_protocol_error(NotFoundError("model deepseek-v4-pro not found")) is False
    assert _is_unsupported_brain_protocol_error(NotFoundError("Responses endpoint not found")) is True


def test_responses_protocol_fallback_accepts_bare_404_for_responses_url() -> None:
    from alchemy_creative_agent_3_0.app.llm_brain.providers import _is_unsupported_brain_protocol_error

    class Request:
        url = "https://brain.example.test/v1/responses"

    class Response:
        status_code = 404
        request = Request()

    class BareNotFoundError(RuntimeError):
        status_code = 404
        response = Response()

    assert _is_unsupported_brain_protocol_error(BareNotFoundError("404 Not Found")) is True


def test_transport_acceptance_is_monotonic_across_protocol_fallback() -> None:
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    trace = providers_module._new_transport_trace(stage="plan", json_recovery=False)
    token = providers_module._ACTIVE_TRANSPORT_TRACE.set(trace)
    try:
        providers_module._set_transport_acceptance(trace, "dispatched")
        providers_module._mark_transport_event("protocol_fallback")
        providers_module._set_transport_acceptance(trace, "unknown")
    finally:
        providers_module._ACTIVE_TRANSPORT_TRACE.reset(token)

    assert trace["request_acceptance"] == "dispatched"
    assert trace["request_dispatched"] is True
    assert trace["protocol_fallback_attempted"] is True


@pytest.mark.parametrize(
    "mutations",
    [
        {"response_started": True, "request_acceptance": "unknown"},
        {"complete_response_observed": True, "response_started": False},
        {"json_parse_completed": True, "json_parse_started": False, "response_started": True},
    ],
)
def test_public_transport_receipts_reject_impossible_temporal_facts(mutations) -> None:
    from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
    from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import _safe_remote_brain_transport_attempt

    base = {
        "schema_version": "v3_brain_transport_attempt_v1",
        "stage": "plan",
        "attempts": 1,
        "request_acceptance": "unknown",
        "request_dispatched": False,
        "response_started": False,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
        "json_recovery": False,
        "json_serialization_recovery_attempted": False,
        "transient_recovery_attempted": False,
    }
    base.update(mutations)

    assert _safe_remote_brain_transport_attempt(base) == {}
    assert V3ProductApiService._public_remote_brain_transport_attempt(base) == {}


@pytest.mark.parametrize(
    "mutations",
    [
        {
            "schema_version": "v3_brain_truncated_response_v1",
            "transport_error_class": "truncated_response",
            "error_family": "output_truncated",
            "json_failure_kind": "output_truncated",
            "json_parse_started": True,
        },
        {"json_serialization_recovery_attempted": True},
        {
            "attempts": 2,
            "json_serialization_recovery_attempted": True,
            "json_serialization_recovery_succeeded": True,
        },
    ],
)
def test_brain_serialization_projections_reject_terminal_inconsistent_receipts(mutations) -> None:
    from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import (
        _safe_remote_brain_serialization_failure,
    )

    valid = {
        "schema_version": "v3_brain_serialization_failure_v1",
        "stage": "provider_prompt_finalize",
        "transport_error_class": "invalid_json_response",
        "error_family": "json_decode",
        "json_failure_kind": "malformed_json",
        "attempts": 1,
        "json_serialization_recovery_attempted": False,
        "json_serialization_recovery_succeeded": False,
        "json_parse_started": False,
        "json_parse_completed": False,
    }
    malformed = {**valid, **mutations}

    assert _safe_remote_brain_serialization_failure(malformed) == {}
    assert V3ProductApiService._public_remote_brain_serialization_failure(malformed) == {}


def test_brain_transport_attempt_zero_is_preflight_only() -> None:
    from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import (
        _safe_remote_brain_transport_attempt,
    )

    valid = {
        "schema_version": "v3_brain_transport_attempt_v1",
        "stage": "plan",
        "attempts": 0,
        "request_acceptance": "not_started",
        "request_dispatched": False,
        "response_started": False,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
        "json_recovery": False,
        "json_serialization_recovery_attempted": False,
        "transient_recovery_attempted": False,
    }

    assert _safe_remote_brain_transport_attempt(valid)
    assert V3ProductApiService._public_remote_brain_transport_attempt(valid)

    for mutations in (
        {"request_acceptance": "dispatched", "request_dispatched": True},
        {"request_acceptance": None, "response_started": True},
    ):
        malformed = {**valid, **mutations}
        assert _safe_remote_brain_transport_attempt(malformed) == {}
        assert V3ProductApiService._public_remote_brain_transport_attempt(malformed) == {}


def test_product_transport_failure_projection_requires_runtime_core_fields() -> None:
    from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import (
        _safe_remote_brain_transport_failure,
    )

    valid = {
        "schema_version": "v3_brain_transport_failure_v1",
        "stage": "plan",
        "transport_error_class": "timeout",
        "timeout_phase": "read_timeout",
        "timeout_seconds": 7.0,
        "elapsed_ms": 7000,
        "response_started": False,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
    }

    assert _safe_remote_brain_transport_failure(valid)
    assert V3ProductApiService._public_remote_brain_transport_failure(valid)
    for field, value in (
        ("schema_version", "wrong_schema"),
        ("stage", None),
        ("transport_error_class", "connection_error"),
        ("timeout_phase", None),
        ("timeout_seconds", None),
        ("elapsed_ms", None),
    ):
        malformed = {**valid, field: value}
        assert _safe_remote_brain_transport_failure(malformed) == {}
        assert V3ProductApiService._public_remote_brain_transport_failure(malformed) == {}


def test_product_lifecycle_rejects_invalid_acceptance_and_cross_receipt_drift() -> None:
    base = {
        "schema_version": "v3_remote_creative_brain_outcome_v1",
        "state": "blocked",
        "reason_code": "remote_creative_brain_prompt_signoff_unavailable",
        "outcome_class": "remote_prompt_signoff_unavailable",
        "remote_brain_finalizer_lifecycle": {
            "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
            "stage": "provider_prompt_finalize",
            "provider_available": True,
            "remote_brain_request_started": True,
            "remote_brain_request_acceptance": "dispatched",
            "response_started": False,
            "status": "blocked",
            "failure_family": "remote_brain_signoff",
            "failure_code": "provider_error",
        },
    }

    assert V3ProductApiService._public_remote_brain_lifecycle_outcome(
        {**base, "remote_brain_request_acceptance": "bogus"}
    ) == {}

    attempt_without_dispatch = {
        "schema_version": "v3_brain_transport_attempt_v1",
        "stage": "provider_prompt_finalize",
        "attempts": 1,
        "request_acceptance": "not_started",
        "request_dispatched": False,
        "response_started": False,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
        "json_recovery": False,
        "json_serialization_recovery_attempted": False,
        "transient_recovery_attempted": False,
    }
    assert V3ProductApiService._public_remote_brain_lifecycle_outcome(
        {**base, "remote_brain_transport_attempt": attempt_without_dispatch}
    ) == {}

    response_failure = {
        "schema_version": "v3_brain_transport_failure_v1",
        "stage": "provider_prompt_finalize",
        "transport_error_class": "timeout",
        "timeout_phase": "read_timeout",
        "timeout_seconds": 7.0,
        "elapsed_ms": 7000,
        "request_acceptance": "dispatched",
        "response_started": True,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
    }
    assert V3ProductApiService._public_remote_brain_lifecycle_outcome(
        {**base, "remote_brain_transport_failure": response_failure, "remote_brain_transport_attempt": attempt_without_dispatch}
    ) == {}

    earlier_retry_attempt = {**attempt_without_dispatch, "request_acceptance": "dispatched", "request_dispatched": True}
    earlier_retry_projection = V3ProductApiService._public_remote_brain_lifecycle_outcome(
        {
            **base,
            "remote_brain_finalizer_lifecycle": {
                **base["remote_brain_finalizer_lifecycle"],
                "remote_brain_request_started": False,
                "remote_brain_request_acceptance": "not_started",
            },
            "remote_brain_transport_attempt": earlier_retry_attempt,
        }
    )
    assert earlier_retry_projection["remote_brain_transport_attempt"]["request_dispatched"] is True


@pytest.mark.parametrize(
    "field",
    [
        "json_serialization_recovery_attempted",
        "json_serialization_recovery_succeeded",
        "json_parse_started",
        "json_parse_completed",
    ],
)
def test_brain_serialization_projections_reject_non_boolean_flags(field: str) -> None:
    from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import _safe_remote_brain_serialization_failure

    valid = {
        "schema_version": "v3_brain_serialization_failure_v1",
        "stage": "provider_prompt_finalize",
        "transport_error_class": "invalid_json_response",
        "error_family": "json_decode",
        "json_failure_kind": "malformed_json",
        "attempts": 1,
        "json_serialization_recovery_attempted": False,
        "json_serialization_recovery_succeeded": False,
        "json_parse_started": True,
        "json_parse_completed": False,
    }
    malformed = {**valid, field: "false"}

    assert _safe_remote_brain_serialization_failure(malformed) == {}
    assert V3ProductApiService._public_remote_brain_serialization_failure(malformed) == {}


def test_brain_serialization_projections_reject_impossible_parse_progression() -> None:
    from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import _safe_remote_brain_serialization_failure

    malformed = {
        "schema_version": "v3_brain_serialization_failure_v1",
        "stage": "provider_prompt_finalize",
        "transport_error_class": "invalid_json_response",
        "error_family": "json_decode",
        "json_failure_kind": "malformed_json",
        "attempts": 1,
        "json_serialization_recovery_attempted": False,
        "json_serialization_recovery_succeeded": True,
        "json_parse_started": False,
        "json_parse_completed": True,
    }

    assert _safe_remote_brain_serialization_failure(malformed) == {}
    assert V3ProductApiService._public_remote_brain_serialization_failure(malformed) == {}


def test_finalizer_source_projection_is_validated_before_provider_availability(monkeypatch) -> None:
    calls = {"available": 0, "run": 0}

    class Provider:
        def available(self, *, force: bool = False) -> bool:
            calls["available"] += 1
            return True

        def run(self, request: BrainRunRequest) -> dict:
            calls["run"] += 1
            return {}

    adapter = V3LLMBrainAdapter(provider=Provider())
    monkeypatch.setattr(brain_adapter_module, "_enabled", lambda: True)
    monkeypatch.setattr(adapter, "_activation_scope_enabled", lambda request: True)
    request = BrainRunRequest(
        user_input="Create one neutral image.",
        requested_image_count=1,
        metadata={
            "brain_source_projection_required": True,
            "brain_source_projection_contract_version": "v3_brain_source_projection_v1",
            "brain_source_projection_digest": "0" * 64,
            "brain_source_projection_binding_digest": "1" * 64,
        },
    )

    with pytest.raises(BrainPromptRequestContractInvalid):
        adapter.finalize_canonical_provider_prompts(request)

    assert calls == {"available": 0, "run": 0}


def test_malformed_naturalness_receipt_is_not_hidden_by_disabled_semantic_preflight(monkeypatch) -> None:
    calls = {"available": 0, "run": 0}

    class Provider:
        def available(self, *, force: bool = False) -> bool:
            calls["available"] += 1
            return True

        def run(self, request: BrainRunRequest) -> dict:
            calls["run"] += 1
            return {}

    adapter = V3LLMBrainAdapter(provider=Provider())
    monkeypatch.setattr(brain_adapter_module, "_enabled", lambda: True)
    monkeypatch.setattr(adapter, "_activation_scope_enabled", lambda request: True)
    request = BrainRunRequest(
        user_input="Create one neutral image.",
        requested_image_count=1,
        metadata={"canonical_prompt_context": {"human_naturalness_decision": "malformed"}},
    )

    with pytest.raises(BrainPromptRequestContractInvalid) as caught:
        adapter.finalize_canonical_provider_prompts(request)

    assert isinstance(caught.value.__cause__, BrainHumanNaturalnessDecisionMissing)
    assert calls == {"available": 0, "run": 0}


def test_brain_availability_explains_disabled_and_missing_credentials(monkeypatch) -> None:
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    provider = providers_module.V3LLMBrainProvider.__new__(providers_module.V3LLMBrainProvider)
    provider.provider = "deepseek"
    provider.model = "deepseek-v4-pro"
    provider.reasoning_effort = None
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "false")
    assert provider.availability()["reason_code"] == "remote_disabled"

    monkeypatch.delenv("V3_LLM_BRAIN_REMOTE_ENABLED")
    monkeypatch.delenv("V3_LLM_BRAIN_API_KEY", raising=False)
    monkeypatch.setattr(providers_module, "_settings_value", lambda name: None)
    monkeypatch.setattr(providers_module, "_remote_enabled", lambda force=False: True)
    assert provider.availability()["reason_code"] == "missing_credentials"


def test_finalizer_lifecycle_rejects_started_unknown_acceptance() -> None:
    from alchemy_creative_agent_3_0.app.llm_brain.finalizer_lifecycle import (
        safe_remote_brain_finalizer_lifecycle,
    )

    assert safe_remote_brain_finalizer_lifecycle(
        {
            "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
            "stage": "provider_prompt_finalize",
            "provider_available": True,
            "remote_brain_request_started": True,
            "remote_brain_request_acceptance": "unknown",
            "response_started": False,
            "status": "blocked",
            "failure_family": "remote_brain_signoff",
            "failure_code": "provider_error",
        }
    ) == {}

    valid = {
        "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
        "stage": "provider_prompt_finalize",
        "provider_available": True,
        "remote_brain_request_started": False,
        "remote_brain_request_acceptance": "not_started",
        "response_started": False,
        "status": "blocked",
        "failure_family": "remote_brain_signoff",
        "failure_code": "provider_error",
    }
    missing_schema = dict(valid)
    missing_schema.pop("schema_version")
    assert safe_remote_brain_finalizer_lifecycle(missing_schema) == {}
    missing_acceptance = dict(valid)
    missing_acceptance.pop("remote_brain_request_acceptance")
    assert safe_remote_brain_finalizer_lifecycle(missing_acceptance) == {}


def test_product_projection_cross_checks_and_completes_finalizer_lifecycle() -> None:
    base = {
        "schema_version": "v3_remote_creative_brain_outcome_v1",
        "state": "blocked",
        "reason_code": "remote_creative_brain_prompt_signoff_unavailable",
        "outcome_class": "remote_prompt_signoff_unavailable",
        "remote_brain_finalizer_lifecycle": {
            "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
            "stage": "provider_prompt_finalize",
            "provider_available": True,
            "remote_brain_request_started": True,
            "remote_brain_request_acceptance": "dispatched",
            "response_started": False,
            "status": "blocked",
            "failure_family": "remote_brain_signoff",
            "failure_code": "provider_error",
        },
    }

    projected = V3ProductApiService._public_remote_brain_lifecycle_outcome(base)
    assert projected["remote_brain_request_started"] is True
    assert projected["remote_brain_request_acceptance"] == "dispatched"
    assert projected["remote_brain_finalizer_lifecycle"]["remote_brain_request_acceptance"] == "dispatched"

    isolated_started = {
        key: value
        for key, value in base.items()
        if key != "remote_brain_finalizer_lifecycle"
    }
    isolated_started["remote_brain_request_started"] = True
    assert V3ProductApiService._public_remote_brain_lifecycle_outcome(isolated_started) == {}

    contradictory = {
        **base,
        "remote_brain_request_started": False,
    }
    assert V3ProductApiService._public_remote_brain_lifecycle_outcome(contradictory) == {}

    incomplete_nested = {
        **base,
        "remote_brain_finalizer_lifecycle": {
            key: value
            for key, value in base["remote_brain_finalizer_lifecycle"].items()
            if key != "remote_brain_request_acceptance"
        },
    }
    incomplete_projection = V3ProductApiService._public_remote_brain_lifecycle_outcome(
        incomplete_nested
    )
    assert "remote_brain_finalizer_lifecycle" not in incomplete_projection


def test_output_store_restore_requires_complete_immutable_closure(tmp_path) -> None:
    job_id = "job_doc298_restore"
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = _save_output(
        store,
        job_id=job_id,
        output_id="v3_output_00000000000000000001",
        projection={"effective_variation_mode": "delivery_suite"},
    )
    service = V3ProductApiService(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))

    before_closure = service._status_from_output_store(job_id)  # noqa: SLF001
    assert before_closure is not None
    assert before_closure.status == ProductJobStatusValue.BLOCKED
    assert before_closure.metadata["output_store_restore_state"] == "needs_recovery"

    closure = _closure(job_id, [record])
    store.save_job_closure(job_id, closure)
    restored = service._status_from_output_store(job_id)  # noqa: SLF001
    history = service.list_history(limit=5)

    assert restored is not None
    assert restored.status == ProductJobStatusValue.GENERATED
    assert restored.metadata["output_store_restore_state"] == "closed"
    assert restored.metadata["effective_variation_mode"] == "delivery_suite"
    assert history.items[0].status == ProductJobStatusValue.GENERATED

    with pytest.raises(ValueError, match="immutable"):
        store.save_job_closure(
            job_id,
            {**closure, "final_delivery_status": "not_evaluated", "automatic_delivery_available": False},
        )


def test_output_store_restore_never_projects_private_prompt_material(tmp_path) -> None:
    job_id = "job_doc298_public_projection"
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id=job_id,
        candidate_id="candidate_public_projection",
        asset_id="asset_public_projection",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=_ONE_PIXEL_PNG,
        output_id="v3_output_00000000000000000006",
        metadata={
            "final_provider_prompt": "PRIVATE_PROVIDER_PROMPT_SENTINEL",
            "compiled_visual_direction": "PRIVATE_COMPILED_DIRECTION_SENTINEL",
            "optimized_direction": "PRIVATE_OPTIMIZED_DIRECTION_SENTINEL",
            "llm_brain_summary": {"headline": "A safe user-facing summary"},
        },
    )
    store.save_job_closure(job_id, _closure(job_id, [record]))

    restored = V3ProductApiService(
        output_store=V3GeneratedOutputStore(tmp_path / "outputs")
    )._status_from_output_store(job_id)  # noqa: SLF001

    assert restored is not None
    public_text = json.dumps(restored.model_dump(mode="json"), ensure_ascii=False)
    assert "PRIVATE_PROVIDER_PROMPT_SENTINEL" not in public_text
    assert "PRIVATE_COMPILED_DIRECTION_SENTINEL" not in public_text
    assert "PRIVATE_OPTIMIZED_DIRECTION_SENTINEL" not in public_text
    assert "final_provider_prompt" not in public_text
    assert "compiled_visual_direction" not in public_text
    assert restored.metadata["workflow_artifacts"]["llm_brain_summary"]["headline"] == "A safe user-facing summary"
    assert restored.metadata["workflow_artifacts"]["final_prompt_available"] is False


def test_output_store_restore_aggregates_mode_projection_beyond_first_output(tmp_path) -> None:
    job_id = "job_doc298_projection"
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    first = _save_output(
        store,
        job_id=job_id,
        output_id="v3_output_00000000000000000001",
        projection={},
    )
    second = _save_output(
        store,
        job_id=job_id,
        output_id="v3_output_00000000000000000002",
        projection={
            "effective_variation_mode": "creative_exploration",
            "variation_execution_mode": "creative_exploration",
        },
    )
    store.save_job_closure(job_id, _closure(job_id, [first, second]))

    restored = V3ProductApiService(
        output_store=V3GeneratedOutputStore(tmp_path / "outputs")
    )._status_from_output_store(job_id)  # noqa: SLF001

    assert restored is not None
    assert restored.status == ProductJobStatusValue.GENERATED
    assert restored.metadata["effective_variation_mode"] == "creative_exploration"


def test_output_store_rejects_conflicting_canonical_content_hashes(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = _save_output(
        store,
        job_id="job_doc298_hash_conflict",
        output_id="v3_output_00000000000000000003",
        projection={},
    )
    output_path = Path(record.file_path).parent / "output.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    payload["metadata"]["source_integrity_id"] = "sha256:" + ("0" * 64)
    output_path.write_text(json.dumps(payload), encoding="utf-8")

    assert V3GeneratedOutputStore(tmp_path / "outputs").file_for_variant(
        record.output_id,
        "download",
    ) is None


def test_project_mode_recovery_uses_store_integrity_resolver(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = _save_output(
        store,
        job_id="job_doc298_project_integrity",
        output_id="v3_output_00000000000000000005",
        projection={},
    )
    output_path = Path(record.file_path).parent / "output.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    payload["metadata"]["content_sha256"] = "0" * 64
    output_path.write_text(json.dumps(payload), encoding="utf-8")

    service = V3ProductApiService(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    loaded = service.output_store.get_output(record.output_id)
    assert loaded is not None
    project_service = V3ProjectModeService(product_service=service)
    assert project_service._output_record_is_renderable(loaded) is False  # noqa: SLF001
    assert service.output_store.file_for_variant(record.output_id, "download") is None


def test_project_mode_output_selector_stays_exact_and_skips_product_selector_contract(
    tmp_path,
    monkeypatch,
) -> None:
    job_id = "job_doc298_output_selector"
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    first = _save_output(
        store,
        job_id=job_id,
        output_id="v3_output_00000000000000000011",
        projection={},
    )
    second = _save_output(
        store,
        job_id=job_id,
        output_id="v3_output_00000000000000000012",
        projection={},
    )
    product_service = V3ProductApiService(output_store=store)
    status = ProductJobStatus(
        job_id=job_id,
        status=ProductJobStatusValue.GENERATED,
        api_namespace="v3_product_api",
        ui_entry_route="/v3",
    )
    monkeypatch.setattr(product_service, "get_job", lambda requested_job_id: status)
    monkeypatch.setattr(
        product_service,
        "select_result",
        lambda *_args, **_kwargs: pytest.fail("output selector must not enter Product API selection"),
    )
    service = V3ProjectModeService(product_service=product_service)
    project = ProjectRecord(
        project_id="project_doc298_output_selector",
        title="Output selector",
        user_goal="Keep one exact output",
        short_summary="Keep one exact output",
        job_ids=[job_id],
        created_at="2026-09-11T00:00:00+00:00",
        updated_at="2026-09-11T00:00:00+00:00",
    )
    service.project_store.save_project(project)
    monkeypatch.setattr(service, "_template_id_for_project_job", lambda *_args: "general_template")
    monkeypatch.setattr(service, "_refresh_project_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_append_timeline", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_set_output_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_upsert_generated_reference", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_project_output_items", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        service,
        "_public_project_record",
        lambda *_args, **_kwargs: SimpleNamespace(model_dump=lambda **_dump_kwargs: {}),
    )

    response = service.select_project_job(
        project.project_id,
        job_id,
        {"selected_output_id": second.output_id},
    )

    assert response["selected_result"]["selected_asset_ids"] == [second.asset_id]
    assert response["selected_result"]["selected_candidate_ids"] == [second.candidate_id]
    assert [ref.output_id for ref in project.selected_output_refs] == [second.output_id]
    assert first.output_id not in [ref.output_id for ref in project.selected_output_refs]


def test_project_mode_mixed_output_selector_holds_atomically(tmp_path, monkeypatch) -> None:
    job_id = "job_doc298_mixed_output_selector"
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    first = _save_output(
        store,
        job_id=job_id,
        output_id="v3_output_00000000000000000021",
        projection={},
    )
    product_service = V3ProductApiService(output_store=store)
    status = ProductJobStatus(
        job_id=job_id,
        status=ProductJobStatusValue.GENERATED,
        api_namespace="v3_product_api",
        ui_entry_route="/v3",
    )
    monkeypatch.setattr(product_service, "get_job", lambda requested_job_id: status)
    monkeypatch.setattr(
        product_service,
        "select_result",
        lambda *_args, **_kwargs: pytest.fail("unresolved mixed output selectors must hold"),
    )
    service = V3ProjectModeService(product_service=product_service)
    project = ProjectRecord(
        project_id="project_doc298_mixed_output_selector",
        title="Mixed output selector",
        user_goal="Keep exact outputs",
        short_summary="Keep exact outputs",
        job_ids=[job_id],
        created_at="2026-09-11T00:00:00+00:00",
        updated_at="2026-09-11T00:00:00+00:00",
    )
    service.project_store.save_project(project)
    monkeypatch.setattr(service, "_template_id_for_project_job", lambda *_args: "general_template")
    monkeypatch.setattr(
        service,
        "_refresh_project_context",
        lambda *_args, **_kwargs: ProjectContextPackage(
            project_id=project.project_id,
            context_version="context_doc298_mixed_output_selector",
            goal_summary=project.short_summary,
            created_at="2026-09-11T00:00:00+00:00",
        ),
    )
    monkeypatch.setattr(service, "_project_output_items", lambda *_args, **_kwargs: [])

    response = service.select_project_job(
        project.project_id,
        job_id,
        {"selected_output_ids": [first.output_id, "v3_output_ffffffffffffffffffff"]},
    )

    assert response["metadata"]["selection_held"] is True
    assert response["metadata"]["unresolved_selected_outputs"]
    assert project.selected_output_refs == []


def test_project_mode_recovery_fails_closed_without_canonical_variant_resolver(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = _save_output(
        store,
        job_id="job_doc298_missing_resolver",
        output_id="v3_output_00000000000000000013",
        projection={},
    )
    product_service = V3ProductApiService(output_store=store)
    loaded = product_service.output_store.get_output(record.output_id)
    assert loaded is not None
    product_service.output_store = SimpleNamespace()
    service = V3ProjectModeService(product_service=product_service)

    assert service._output_record_is_renderable(loaded) is False  # noqa: SLF001


def test_output_store_closure_freezes_new_output_index_metadata(tmp_path) -> None:
    job_id = "job_doc298_closed_index"
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = _save_output(
        store,
        job_id=job_id,
        output_id="v3_output_00000000000000000004",
        projection={},
    )
    store.save_job_closure(job_id, _closure(job_id, [record]))

    with pytest.raises(ValueError, match="closed_output_metadata_immutable:output_index"):
        store.update_metadata(record.output_id, {"output_index": 2})
