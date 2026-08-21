import base64
from io import BytesIO
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
from uuid import uuid4

from PIL import Image
import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.app_shell import (
    API_NAMESPACE,
    get_minimal_ui_contract,
    render_minimal_job_view,
)
from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.platform_adapters import V3BalanceAdapter, V3BalanceEstimate
from alchemy_creative_agent_3_0.app.product_api import (
    CreateBrandRequest,
    CreateCreativeJobRequest,
    GenerateJobRequest,
    ProductJobStatusValue,
    SelectResultRequest,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import PersistentProductJobStore
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import (
    ScenarioRuntimeResult,
    ScenarioRuntimeStatus,
)
from alchemy_creative_agent_3_0.app.schemas import IndustryCategory, Platform


_RUNTIME_ROOTS: list[Path] = []


@pytest.fixture(autouse=True)
def _cleanup_runtime_product_api_stores():
    yield
    while _RUNTIME_ROOTS:
        root = _RUNTIME_ROOTS.pop()
        shutil.rmtree(root, ignore_errors=True)


def _test_store_root(name: str) -> Path:
    root = Path(__file__).resolve().parent / "_runtime_product_api" / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True)
    _RUNTIME_ROOTS.append(root)
    return root


class TrackingBalanceAdapter(V3BalanceAdapter):
    adapter_name = "tracking_v3_balance_adapter"

    def __init__(self) -> None:
        self.estimated_asset_counts: list[int] = []
        self.checked_credits: list[int] = []

    def estimate_planning_cost(self, asset_count: int) -> V3BalanceEstimate:
        self.estimated_asset_counts.append(asset_count)
        return V3BalanceEstimate(
            credits_required=0,
            currency="credits",
            metadata={"runtime_mode": "tracking_test", "asset_count": asset_count},
        )

    def has_available_credits(self, credits_required: int) -> bool:
        self.checked_credits.append(credits_required)
        return True


def _service(name: str = "default") -> tuple[V3ProductApiService, BrandProfileService, TrackingBalanceAdapter]:
    brand_service = BrandProfileService(BrandProfileStore(_test_store_root(name)))
    balance = TrackingBalanceAdapter()
    return V3ProductApiService(brand_profile_service=brand_service, balance_adapter=balance), brand_service, balance


def _remote_finalizer_timeout_outcome() -> dict[str, object]:
    return {
        "schema_version": "v3_remote_creative_brain_outcome_v1",
        "state": "blocked",
        "reason_code": "remote_creative_brain_prompt_signoff_unavailable",
        "outcome_class": "remote_prompt_signoff_unavailable",
        "llm_used": True,
        "fallback_used": False,
        "remote_provider_available": True,
        "remote_error_class": "timeout",
        "remote_brain_stage": "provider_prompt_finalize",
        "remote_brain_transport_failure": {
            "schema_version": "v3_brain_transport_failure_v1",
            "stage": "provider_prompt_finalize",
            "transport_error_class": "timeout",
            "timeout_phase": "read_timeout",
            "timeout_seconds": 210.0,
            "elapsed_ms": 210013,
            "response_started": True,
            "first_content_observed": False,
            "complete_response_observed": False,
            "json_parse_started": False,
            "json_parse_completed": False,
            "raw_response": "secret raw response must not leak",
            "provider_url": "https://provider.invalid/private",
        },
        "remote_brain_execution_budget": {
            "logical_budget_seconds": 520.0,
            "remaining_ms": 230683,
            "state": "within_budget",
            "prompt_path": "D:/unsafe/prompt.txt",
        },
        "raw_prompt": "private prompt must not leak",
        "asset_id": "asset_internal_must_not_leak",
        "provider_payload": {"secret": True},
    }


def _remote_finalizer_request_started_outcome() -> dict[str, object]:
    return {
        "schema_version": "v3_remote_creative_brain_outcome_v1",
        "state": "blocked",
        "reason_code": "remote_creative_brain_prompt_signoff_unavailable",
        "outcome_class": "remote_prompt_signoff_unavailable",
        "llm_used": True,
        "fallback_used": False,
        "remote_provider_available": True,
        "remote_error_class": "provider_error",
        "remote_brain_stage": "provider_prompt_finalize",
        "remote_brain_request_started": True,
        "remote_brain_finalizer_lifecycle": {
            "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
            "stage": "provider_prompt_finalize",
            "provider_available": True,
            "remote_brain_request_started": True,
            "response_started": False,
            "status": "blocked",
            "failure_family": "remote_brain_signoff",
            "failure_code": "provider_error",
            "raw_prompt": "private prompt must not leak",
            "provider_url": "https://provider.invalid/private",
            "provider_payload": {"secret": True},
        },
        "remote_brain_execution_budget": {
            "logical_budget_seconds": 520.0,
            "remaining_ms": 309892,
            "state": "within_budget",
        },
        "raw_prompt": "private prompt must not leak",
        "provider_payload": {"secret": True},
    }


def _remote_finalizer_preflight_unavailable_outcome() -> dict[str, object]:
    return {
        "schema_version": "v3_remote_creative_brain_outcome_v1",
        "state": "blocked",
        "reason_code": "remote_creative_brain_prompt_signoff_unavailable",
        "outcome_class": "remote_prompt_signoff_unavailable",
        "llm_used": True,
        "fallback_used": False,
        "remote_provider_available": True,
        "remote_error_class": "provider_error",
        "remote_brain_stage": "provider_prompt_finalize",
        "remote_brain_request_started": False,
        "remote_brain_finalizer_lifecycle": {
            "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
            "stage": "provider_prompt_finalize",
            "provider_available": False,
            "remote_brain_request_started": False,
            "response_started": False,
            "status": "blocked",
            "failure_family": "remote_brain_signoff",
            "failure_code": "provider_unavailable",
            "raw_prompt": "private prompt must not leak",
            "provider_payload": {"secret": True},
        },
    }


def _malformed_remote_outcome() -> dict[str, object]:
    return {
        "schema_version": "v3_remote_creative_brain_outcome_v1",
        "state": "blocked",
        "reason_code": "unknown_unreviewed_reason",
        "remote_brain_stage": "D:/unsafe/stage.txt",
        "raw_response": "secret malformed raw response must not leak",
        "raw_prompt": "secret malformed prompt must not leak",
        "provider_url": "https://provider.invalid/malformed",
        "asset_id": "asset_malformed_internal",
        "output_id": "output_malformed_internal",
        "provider_payload": {"secret": True},
    }


def _provider_no_pixel_retry_summary() -> dict[str, object]:
    return {
        "executed_count": 0,
        "max_attempts": 1,
        "fresh_upstream_requests": 1,
        "final_status": "failed",
        "final_classification": "non_retryable_provider_failure",
        "final_failure_code": "image_edit_invalid_request_unattributed",
        "attempts": [
            {
                "attempt": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "image_edit_invalid_request_unattributed",
                "message": "OpenAI image reference generation failed. Error code: 400 - raw provider body",
                "retryable": False,
                "provider_payload": {"secret": "must not leak"},
            }
        ],
        "reference_input_execution": {
            "schema_version": "v3_reference_input_execution_v1",
            "operation": "image_edit",
            "reference_count": 1,
            "operation_outcome": "failed",
            "failure_code": "image_edit_invalid_request_unattributed",
            "safe_message": "The image-edit request was rejected before image pixels were returned.",
            "delivery_binding_id": "internal-binding-must-not-leak",
        },
    }


class _RemoteFinalizerTimeoutRuntime:
    def __init__(
        self,
        base_runtime: object,
        *,
        block_stage: str,
        outcome: dict[str, object] | None = None,
    ) -> None:
        self.base_runtime = base_runtime
        self.scenario_registry = base_runtime.scenario_registry
        self.block_stage = block_stage
        self.outcome = outcome or _remote_finalizer_timeout_outcome()

    def plan_job(self, payload):  # noqa: ANN001, ANN201
        selection = payload.get("scenario_selection", {}) if isinstance(payload, dict) else {}
        resolution = self.scenario_registry.resolve(selection)
        if self.block_stage == "plan":
            return ScenarioRuntimeResult(
                status=ScenarioRuntimeStatus.BLOCKED,
                scenario_resolution=resolution,
                warnings=[
                    "capability_activation_failed: "
                    "remote_creative_brain_prompt_signoff_unavailable"
                ],
                metadata={"remote_creative_brain_outcome": self.outcome},
            )
        return self.base_runtime.plan_job(payload)

    def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
        selection = payload.get("scenario_selection", {}) if isinstance(payload, dict) else {}
        resolution = self.scenario_registry.resolve(selection)
        return ScenarioRuntimeResult(
            status=ScenarioRuntimeStatus.BLOCKED,
            scenario_resolution=resolution,
            warnings=[
                "capability_activation_failed: "
                "remote_creative_brain_prompt_signoff_unavailable"
            ],
            metadata={"remote_creative_brain_outcome": self.outcome},
        )


class _ProductApiRuntimeError:
    def __init__(self, base_runtime: object, on_call=None) -> None:  # noqa: ANN001
        self.scenario_registry = base_runtime.scenario_registry
        self._on_call = on_call

    def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
        if self._on_call is not None:
            self._on_call()
        raise RuntimeError("runtime boundary detail must not enter public state")


class _KeyboardInterruptRuntime:
    def __init__(self, base_runtime: object) -> None:
        self.scenario_registry = base_runtime.scenario_registry

    def generate_job(self, payload, **_kwargs):  # noqa: ANN001, ANN201
        raise KeyboardInterrupt()


def test_interrupted_body_resume_runtime_failure_clears_stale_remote_readback() -> None:
    service, _, _ = _service("candidate1_resume_boundary_projection")
    created = service.create_job({"user_input": "Create one neutral Character Card body view."})
    record = service.job_store.get(created.job_id)
    assert record is not None
    assert record.planning_result is not None
    record.status = ProductJobStatusValue.GENERATING
    record.request.metadata.update(
        {
            "generation_channel": "mcp",
            "mcp_operation_id": "visual_asset_hash:body_silhouette:body.front_full:1",
            "professional_character_card_preparation": True,
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": "body.front_full",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_candidate_lifecycle_checkpoints": [],
            "generation_lifecycle_failure": {
                "schema_version": "v3_generation_lifecycle_failure_v1",
                "status": "blocked",
                "owner": "v3_product_api_runtime",
                "failure_family": "remote_creative_brain",
                "failure_code": "remote_creative_brain_prompt_signoff_unavailable",
                "reason_code": "remote_creative_brain_prompt_signoff_unavailable",
                "provider_request_started": False,
            },
            "remote_creative_brain_outcome": _remote_finalizer_timeout_outcome(),
        }
    )
    service.job_store.save(record)
    service.scenario_runtime = _ProductApiRuntimeError(service.scenario_runtime)

    resumed = service.generate_job(
        created.job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_interrupted_mcp_materialization": True}},
    )
    durable = service.job_store.get(created.job_id)
    assert durable is not None

    assert resumed.status == ProductJobStatusValue.BLOCKED
    assert durable.request.metadata.get("professional_character_card_candidate_lifecycle_checkpoints") == []
    assert "remote_creative_brain_outcome" not in durable.request.metadata
    assert durable.request.metadata["generation_lifecycle_failure"]["failure_family"] == "product_api_runtime"
    assert durable.request.metadata["generation_lifecycle_failure"]["failure_code"] == "runtime_error"
    assert durable.request.metadata["generation_lifecycle_failure"]["provider_request_started"] is False
    assert durable.generation_result is None


def test_interrupted_body_resume_runtime_failure_does_not_change_acceptance_semantics() -> None:
    service, _, _ = _service("candidate1_resume_boundary_no_acceptance")
    created = service.create_job({"user_input": "Create one neutral Character Card body view."})
    record = service.job_store.get(created.job_id)
    assert record is not None
    assert record.planning_result is not None
    record.status = ProductJobStatusValue.GENERATING
    record.request.metadata.update(
        {
            "generation_channel": "mcp",
            "mcp_operation_id": "visual_asset_hash:body_silhouette:body.front_full:1",
            "professional_character_card_preparation": True,
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": "body.front_full",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_candidate_lifecycle_checkpoints": [],
        }
    )
    service.job_store.save(record)
    service.scenario_runtime = _ProductApiRuntimeError(service.scenario_runtime)

    resumed = service.generate_job(
        created.job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_interrupted_mcp_materialization": True}},
    )

    assert resumed.status == ProductJobStatusValue.BLOCKED
    assert resumed.metadata.get("pending_refresh_slots") is None
    assert resumed.metadata.get("activation") is None
    assert resumed.metadata.get("provider_failure_retry") is None
    assert service.job_store.get(created.job_id).generation_result is None


def test_blocked_body_new_attempt_clears_stale_failure_before_generating_persistence() -> None:
    service, _, _ = _service("blocked_body_new_attempt_projection")
    created = service.create_job({"user_input": "Create one neutral Character Card body view."})
    record = service.job_store.get(created.job_id)
    assert record is not None
    assert record.planning_result is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata.update(
        {
            "generation_channel": "mcp",
            "mcp_operation_id": "visual_asset_hash:body_silhouette:body.front_full:1",
            "professional_character_card_preparation": True,
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": "body.front_full",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "generation_lifecycle_failure": {
                "status": "blocked",
                "failure_family": "remote_creative_brain",
                "failure_code": "remote_brain_prompt_signoff_unavailable",
            },
            "remote_creative_brain_outcome": _remote_finalizer_timeout_outcome(),
            "provider_failure_retry": {"fresh_upstream_requests": 1},
            "provider_failure_retry_exhausted": True,
        }
    )
    service.job_store.save(record)
    observed: list[dict[str, object]] = []

    def observe_inflight_record() -> None:
        current = service.job_store.get(created.job_id)
        assert current is not None
        observed.append(dict(current.request.metadata))
        assert current.status == ProductJobStatusValue.GENERATING

    service.scenario_runtime = _ProductApiRuntimeError(service.scenario_runtime, observe_inflight_record)

    resumed = service.generate_job(
        created.job_id,
        {"quality_mode": "strict", "metadata": {"_v3_resume_interrupted_mcp_materialization": True}},
    )

    assert resumed.status == ProductJobStatusValue.BLOCKED
    assert observed
    inflight = observed[0]
    assert "generation_lifecycle_failure" not in inflight
    assert "remote_creative_brain_outcome" not in inflight
    assert "provider_failure_retry" not in inflight
    assert "provider_failure_retry_exhausted" not in inflight
    durable = service.job_store.get(created.job_id)
    assert durable is not None
    assert durable.request.metadata["generation_lifecycle_failure"]["failure_code"] == "runtime_error"


def test_direct_sync_generation_does_not_swallow_keyboard_interrupt() -> None:
    service, _, _ = _service("candidate1_resume_boundary_keyboard_interrupt")
    created = service.create_job({"user_input": "Create one neutral Character Card body view."})
    service.scenario_runtime = _KeyboardInterruptRuntime(service.scenario_runtime)

    with pytest.raises(KeyboardInterrupt):
        service.generate_job(created.job_id, {"quality_mode": "strict"})


def test_v3_product_api_creates_and_retrieves_creative_job_status() -> None:
    service, _, balance = _service("create_job")

    created = service.create_job(
        {"user_input": "帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。"}
    )
    fetched = service.get_job(created.job_id)

    assert created.status == ProductJobStatusValue.PLANNED
    assert fetched.job_id == created.job_id
    assert fetched.api_namespace == "/api/v3/creative-agent"
    assert fetched.routes["create_job"] == "/api/v3/creative-agent/jobs"
    assert fetched.routes["create_creative_job"] == "/v3/creative-jobs"
    assert fetched.routes["create_product_brand"] == "/v3/brands"
    assert fetched.campaign is not None
    assert fetched.campaign.business_goal
    assert fetched.asset_series
    assert fetched.style_continuation is not None
    assert fetched.style_continuation.enabled is False
    assert fetched.balance_estimate["metadata"]["adapter"] == "tracking_v3_balance_adapter"
    assert balance.estimated_asset_counts == [len(fetched.asset_series)]
    assert fetched.metadata["v3_independent_product_api"] is True


def test_repeated_root_create_is_append_only_and_preserves_the_first_terminal_record() -> None:
    service, _, _ = _service("append_only_root_job_identity")
    request = {"user_input": "Create one clean still-life image."}

    first = service.create_job(request)
    service.mark_job_generating(
        first.job_id,
        background_attempt_id="first_attempt",
        background_timeout_seconds=675,
    )
    first_terminal = service.mark_job_generation_worker_failed(
        first.job_id,
        background_attempt_id="first_attempt",
        failure_code="background_generation_request_invalid",
    )
    second = service.create_job(request)

    assert first.job_id != second.job_id
    assert first_terminal.status == ProductJobStatusValue.BLOCKED
    assert service.get_job(first.job_id).status == ProductJobStatusValue.BLOCKED
    assert service.get_job(second.job_id).status == ProductJobStatusValue.PLANNED
    assert service.job_store.count() == 2
    first_record = service.job_store.get(first.job_id)
    second_record = service.job_store.get(second.job_id)
    assert first_record is not None and second_record is not None
    assert (
        first_record.request.metadata["v3_job_instance_id"]
        != second_record.request.metadata["v3_job_instance_id"]
    )


def test_root_job_instance_id_is_server_owned() -> None:
    service, _, _ = _service("server_owned_root_job_instance")

    with pytest.raises(ValueError, match="runtime_metadata_server_owned: v3_job_instance_id"):
        service.create_job(
            {
                "user_input": "Create one clean still-life image.",
                "metadata": {"v3_job_instance_id": "browser-supplied"},
            }
        )


def test_public_review_projection_hides_retry_prompt_and_upstream_failure_details() -> None:
    raw_retry = {
        "enabled": True,
        "executed_count": 0,
        "max_attempts": 1,
        "issue_codes": ["plastic_skin"],
        "records": [
            {
                "attempt_index": 1,
                "status": "failed",
                "reason_codes": ["plastic_skin"],
                "retry_patch": {"negative_additions": ["internal retry prompt"]},
                "blocked_reason": "upstream access forbidden",
            }
        ],
    }
    raw_review = {
        "user_visible_summary": ["V3 checked the generated image."],
        "inspections": [
            {
                "output_id": "output_safe",
                "mode": "hybrid",
                "status": "fail_retryable",
                "verification_state": "verified",
                "file_path": "D:/internal/output.png",
                "retry_patch": {"prompt_additions": ["internal repair instruction"]},
                "detected_issues": [
                    {
                        "code": "plastic_skin",
                        "severity": "medium",
                        "retryable": True,
                        "message": "Skin may look too smooth.",
                        "provider_reason": "internal provider detail",
                    }
                ],
            }
        ],
        "recommended_output_ids": ["output_safe"],
    }

    public_retry = V3ProductApiService._public_visual_auto_retry_summary(raw_retry)
    public_review = V3ProductApiService._public_post_generation_review(raw_review)

    assert public_retry["manual_confirmation_required"] is False
    assert public_retry["records"] == [
        {"attempt_index": 1, "status": "failed", "reason_codes": ["plastic_skin"]}
    ]
    assert "retry_patch" not in public_retry["records"][0]
    assert "blocked_reason" not in public_retry["records"][0]
    inspection = public_review["inspections"][0]
    assert inspection["mode"] == "hybrid"
    assert inspection["detected_issues"] == [
        {
            "code": "plastic_skin",
            "severity": "medium",
            "retryable": True,
            "message": "Skin may look too smooth.",
        }
    ]
    assert "file_path" not in inspection
    assert "retry_patch" not in inspection

    retained_delivery_retry = V3ProductApiService._public_visual_auto_retry_summary(
        raw_retry,
        manual_confirmation_required=True,
    )
    assert retained_delivery_retry["manual_confirmation_required"] is True


def test_public_job_status_redacts_nested_retry_execution_data_but_keeps_durable_audit() -> None:
    service, _, _ = _service("public_retry_redaction")
    created = service.create_job({"user_input": "Create one clean still-life image."})

    public_status = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "force_visual_retry_issue_codes": ["visible_text_artifact"],
                "max_visual_retry_attempts": 1,
            },
        },
    )
    public_payload = public_status.model_dump_json()
    record = service.job_store.get(created.job_id)

    assert record is not None and record.generation_result is not None
    assert "retry_patch" in str(record.generation_result.metadata["visual_auto_retry"])
    assert "retry_patch" not in public_payload
    assert "blocked_reason" not in public_payload
    assert "file_path" not in public_payload
    assert public_status.metadata["visual_auto_retry"]["append_only"] is True


def test_gateway_managed_background_timeout_is_terminal_and_stale_worker_cannot_reopen_it() -> None:
    service, _, _ = _service("gateway_background_timeout")
    created = service.create_job({"user_input": "Create one clean still-life image."})

    pending = service.mark_job_generating(
        created.job_id,
        background_attempt_id="attempt_one",
        background_timeout_seconds=675,
    )
    stale_watchdog = service.mark_job_generation_timed_out(
        created.job_id,
        background_attempt_id="different_attempt",
        timeout_seconds=675,
    )
    timed_out = service.mark_job_generation_timed_out(
        created.job_id,
        background_attempt_id="attempt_one",
        timeout_seconds=675,
    )
    late_worker = service.generate_job(
        created.job_id,
        {
            "metadata": {
                "_v3_background_worker_claim": True,
                "_v3_background_generation_attempt_id": "attempt_one",
            }
        },
    )

    assert pending.status == ProductJobStatusValue.GENERATING
    assert pending.metadata["background_generation_watchdog"]["timeout_seconds"] == 675
    assert stale_watchdog.status == ProductJobStatusValue.GENERATING
    assert timed_out.status == ProductJobStatusValue.BLOCKED
    assert timed_out.metadata["provider_failure_retry"]["fresh_upstream_requests"] == 1
    assert timed_out.metadata["generation_lifecycle_timeout"]["timeout_seconds"] == 675
    assert "gateway_managed_lifecycle_timeout" in " ".join(timed_out.warnings)
    assert late_worker.status == ProductJobStatusValue.BLOCKED


def test_direct_provider_background_timeout_is_terminal_and_stale_worker_cannot_reopen_it() -> None:
    service, _, _ = _service("direct_provider_background_timeout")
    created = service.create_job({"user_input": "Create one clean still-life image."})

    pending = service.mark_job_generating(
        created.job_id,
        background_attempt_id="direct_attempt_one",
        background_timeout_seconds=255,
        background_timeout_owner="direct_provider",
    )
    timed_out = service.mark_job_generation_timed_out(
        created.job_id,
        background_attempt_id="direct_attempt_one",
        timeout_seconds=255,
    )
    late_worker = service.generate_job(
        created.job_id,
        {
            "metadata": {
                "_v3_background_worker_claim": True,
                "_v3_background_generation_attempt_id": "direct_attempt_one",
            }
        },
    )

    assert pending.status == ProductJobStatusValue.GENERATING
    assert pending.metadata["background_generation_watchdog"]["timeout_owner"] == "direct_provider"
    assert timed_out.status == ProductJobStatusValue.BLOCKED
    assert timed_out.metadata["provider_failure_retry"]["final_classification"] == "direct_provider_lifecycle_timeout"
    assert timed_out.metadata["generation_lifecycle_timeout"]["budget_owner"] == "direct_provider"
    assert "direct_provider_lifecycle_timeout" in " ".join(timed_out.warnings)
    assert late_worker.status == ProductJobStatusValue.BLOCKED


def test_background_worker_failure_is_terminal_without_claiming_a_provider_timeout() -> None:
    service, _, _ = _service("background_worker_failure")
    created = service.create_job({"user_input": "Create one clean still-life image."})
    service.mark_job_generating(
        created.job_id,
        background_attempt_id="invalid_request_attempt",
        background_timeout_seconds=675,
    )

    failed = service.mark_job_generation_worker_failed(
        created.job_id,
        background_attempt_id="invalid_request_attempt",
        failure_code="background_generation_request_invalid",
    )
    late_worker = service.generate_job(
        created.job_id,
        {
            "metadata": {
                "_v3_background_worker_claim": True,
                "_v3_background_generation_attempt_id": "invalid_request_attempt",
            }
        },
    )

    assert failed.status == ProductJobStatusValue.BLOCKED
    assert failed.metadata["generation_lifecycle_failure"] == {
        "background_attempt_id": "invalid_request_attempt",
        "failure_code": "background_generation_request_invalid",
        "status": "terminal_failure",
        "owner": "v3_background_generation_worker",
    }
    assert "provider_failure_retry" not in failed.metadata
    assert "background_generation_request_invalid" in " ".join(failed.warnings)
    assert late_worker.status == ProductJobStatusValue.BLOCKED


def test_background_process_restart_is_terminal_without_fabricating_provider_outcome() -> None:
    service, _, _ = _service("background_process_restart")
    created = service.create_job({"user_input": "Create one clean still-life image."})
    service.mark_job_generating(
        created.job_id,
        background_attempt_id="interrupted_attempt",
        background_timeout_seconds=675,
        background_runtime_id="previous_runtime",
    )

    failed = service.mark_job_generation_worker_failed(
        created.job_id,
        background_attempt_id="interrupted_attempt",
        failure_code="background_generation_process_restarted",
    )

    assert failed.status == ProductJobStatusValue.BLOCKED
    assert failed.metadata["generation_lifecycle_failure"] == {
        "background_attempt_id": "interrupted_attempt",
        "failure_code": "background_generation_process_restarted",
        "status": "terminal_failure",
        "owner": "v3_background_generation_recovery",
        "automatic_replay": False,
        "provider_outcome": "unknown",
    }
    assert "provider_failure_retry" not in failed.metadata
    assert "background_generation_process_restarted" in " ".join(failed.warnings)


def test_no_pixel_provider_failure_has_safe_reference_execution_projection() -> None:
    service, _, _ = _service("doc117_safe_provider_execution")
    created = service.create_job({"user_input": "Create one realistic person wearing the supplied garment."})
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata["provider_failure_retry"] = {
        "executed_count": 0,
        "max_attempts": 1,
        "fresh_upstream_requests": 1,
        "final_status": "failed",
        "final_classification": "non_retryable_provider_failure",
        "final_failure_code": "image_edit_invalid_request_unattributed",
        "attempts": [
            {
                "attempt": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "image_edit_invalid_request_unattributed",
                "message": "upstream private explanation must not be exposed",
                "retryable": False,
            }
        ],
        "reference_input_execution": {
            "schema_version": "v3_reference_input_execution_v1",
            "delivery_binding_id": "internal-binding-must-not-leak",
            "operation": "image_edit",
            "reference_count": 1,
            "operation_outcome": "failed",
            "failure_code": "image_edit_invalid_request_unattributed",
            "safe_message": "The image-edit request was rejected before image pixels were returned.",
        },
    }
    service.job_store.save(record)

    status = service.get_job(created.job_id)

    assert status.status == ProductJobStatusValue.BLOCKED
    assert all(item.selected_candidate_id is None for item in status.asset_series)
    assert status.candidates == []
    assert status.metadata["provider_execution"] == {
        "operation_count": 1,
        "automatic_delivery_available": False,
        "manual_confirmation_required": False,
        "operations": [
            {
                "operation": "image_edit",
                "reference_execution_state": "blocked",
                "reference_count": 1,
                "automatic_delivery_available": False,
                "manual_confirmation_required": False,
                "safe_reason_code": "image_edit_invalid_request_unattributed",
            }
        ],
    }
    public_payload = status.model_dump_json()
    assert "internal-binding-must-not-leak" not in public_payload
    assert "upstream private explanation" not in public_payload
    assert "image_edit_invalid_request_unattributed" in public_payload
    assert "generation_lifecycle_failure" not in status.metadata
    assert service._public_metadata_projection(  # noqa: SLF001
        {"reference_input_execution": {"delivery_binding_id": "internal-binding-must-not-leak"}}
    ) == {}


def test_local_input_contract_failure_message_does_not_claim_provider_outage() -> None:
    message = V3ProductApiService._safe_generation_failure_message(  # noqa: SLF001
        provider_strategy=None,
        provider_failure_retry={
            "final_classification": "non_retryable_input_contract_failure",
            "final_failure_code": "ecommerce_product_truth_pool_mismatch",
            "fresh_upstream_requests": 0,
        },
        fallback_code="provider_unavailable",
    )

    assert "provider failure" not in message.lower()
    assert "image request" in message.lower()
    assert "product" in message.lower()


def test_public_projection_repairs_legacy_local_reference_failure_without_mutating_record() -> None:
    raw = {
        "executed_count": 0,
        "max_attempts": 0,
        "fresh_upstream_requests": 0,
        "final_status": "failed",
        "final_classification": "non_retryable_provider_failure",
        "final_failure_code": "provider_unavailable",
        "attempts": [
            {
                "attempt": 0,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_unavailable",
                "error_type": "ReferenceInputAdmissionError",
                "message": "Professional E-Commerce product truth pool does not match bound product references.",
                "retryable": False,
            }
        ],
        "reference_input_execution": {
            "operation": "image_edit",
            "operation_outcome": "failed",
            "outer_request_count": 0,
            "failure_code": "provider_unavailable",
        },
    }

    projected = V3ProductApiService._public_provider_failure_retry(raw)  # noqa: SLF001

    assert projected["final_classification"] == "non_retryable_input_contract_failure"
    assert projected["final_failure_code"] == "ecommerce_product_truth_pool_mismatch"
    assert projected["fresh_upstream_requests"] == 0
    assert projected["attempts"][0]["failure_code"] == "ecommerce_product_truth_pool_mismatch"
    assert raw["final_failure_code"] == "provider_unavailable"


def test_empty_job_status_sanitizes_provider_failure_warnings() -> None:
    service, _, _ = _service("empty_status_warning_sanitizer")
    created = service.create_job({"user_input": "Create one neutral product image."})
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.job_id_value = created.job_id
    record.status = ProductJobStatusValue.BLOCKED
    record.planning_result = None
    record.generation_result = None
    record.request.metadata["provider_failure_retry"] = _provider_no_pixel_retry_summary()
    record.warnings.append(
        "OpenAI image reference generation failed. Error code: 400 - raw provider body"
    )
    service.job_store.save(record)

    status = service.get_job(created.job_id)

    assert status.status == ProductJobStatusValue.BLOCKED
    joined = " ".join(status.warnings)
    assert "image_edit_invalid_request_unattributed" in joined
    payload = status.model_dump_json()
    assert "raw provider body" not in payload
    assert "OpenAI image reference generation failed" not in payload
    assert "internal-binding-must-not-leak" not in payload
    assert "provider_payload" not in payload


def test_remote_finalizer_timeout_block_has_closed_lifecycle_failure_on_create_and_generate() -> None:
    create_service, _, _ = _service("remote_finalizer_timeout_create")
    create_service.scenario_runtime = _RemoteFinalizerTimeoutRuntime(
        create_service.scenario_runtime,
        block_stage="plan",
    )

    planning_blocked = create_service.create_job({"user_input": "Create one neutral Character Card body view."})

    generate_service, _, _ = _service("remote_finalizer_timeout_generate")
    generated_candidate = generate_service.create_job({"user_input": "Create one neutral Character Card body view."})
    generate_service.scenario_runtime = _RemoteFinalizerTimeoutRuntime(
        generate_service.scenario_runtime,
        block_stage="generate",
    )
    generation_blocked = generate_service.generate_job(
        generated_candidate.job_id,
        {"quality_mode": "strict"},
    )

    assert planning_blocked.status == ProductJobStatusValue.BLOCKED
    assert generation_blocked.status == ProductJobStatusValue.BLOCKED
    assert (
        planning_blocked.metadata["generation_lifecycle_failure"]
        == generation_blocked.metadata["generation_lifecycle_failure"]
    )
    failure = planning_blocked.metadata["generation_lifecycle_failure"]
    assert failure == {
        "schema_version": "v3_generation_lifecycle_failure_v1",
        "status": "blocked",
        "owner": "v3_product_api_runtime",
        "failure_family": "remote_creative_brain",
        "failure_code": "remote_creative_brain_prompt_signoff_unavailable",
        "reason_code": "remote_creative_brain_prompt_signoff_unavailable",
        "provider_request_started": False,
        "remote_creative_brain_outcome": {
            "schema_version": "v3_remote_creative_brain_outcome_v1",
            "state": "blocked",
            "reason_code": "remote_creative_brain_prompt_signoff_unavailable",
            "outcome_class": "remote_prompt_signoff_unavailable",
            "remote_error_class": "timeout",
            "remote_brain_stage": "provider_prompt_finalize",
            "remote_brain_transport_failure": {
                "schema_version": "v3_brain_transport_failure_v1",
                "stage": "provider_prompt_finalize",
                "transport_error_class": "timeout",
                "timeout_phase": "read_timeout",
                "timeout_seconds": 210.0,
                "elapsed_ms": 210013,
                "response_started": True,
                "first_content_observed": False,
                "complete_response_observed": False,
                "json_parse_started": False,
                "json_parse_completed": False,
            },
            "remote_brain_execution_budget": {
                "logical_budget_seconds": 520.0,
                "remaining_ms": 230683,
                "state": "within_budget",
            },
            "llm_used": True,
            "fallback_used": False,
            "remote_provider_available": True,
        },
    }
    for status in (planning_blocked, generation_blocked):
        payload = status.model_dump_json()
        assert status.metadata["remote_creative_brain_outcome"] == failure[
            "remote_creative_brain_outcome"
        ]
        assert "provider_failure_retry" not in status.metadata
        assert "raw response" not in payload
        assert "private prompt" not in payload
        assert "provider.invalid" not in payload
        assert "D:/unsafe" not in payload
        assert "asset_internal_must_not_leak" not in payload
    for service, status in (
        (create_service, planning_blocked),
        (generate_service, generation_blocked),
    ):
        record = service.job_store.get(status.job_id)
        assert record is not None
        durable_payload = record.request.model_dump_json()
        assert record.request.metadata["remote_creative_brain_outcome"] == failure[
            "remote_creative_brain_outcome"
        ]
        assert record.request.metadata["generation_lifecycle_failure"] == failure
        assert "raw response" not in durable_payload
        assert "private prompt" not in durable_payload
        assert "provider.invalid" not in durable_payload
        assert "D:/unsafe" not in durable_payload
        assert "asset_internal_must_not_leak" not in durable_payload


def test_remote_finalizer_lifecycle_distinguishes_brain_request_from_image_provider_start() -> None:
    service, _, _ = _service("remote_finalizer_request_started_projection")
    service.scenario_runtime = _RemoteFinalizerTimeoutRuntime(
        service.scenario_runtime,
        block_stage="plan",
        outcome=_remote_finalizer_request_started_outcome(),
    )

    blocked = service.create_job({"user_input": "Create one neutral Character Card body view."})

    assert blocked.status == ProductJobStatusValue.BLOCKED
    failure = blocked.metadata["generation_lifecycle_failure"]
    assert failure["provider_request_started"] is False
    assert failure["remote_brain_request_started"] is True
    outcome = failure["remote_creative_brain_outcome"]
    assert outcome["remote_brain_request_started"] is True
    assert outcome["remote_brain_finalizer_lifecycle"] == {
        "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
        "stage": "provider_prompt_finalize",
        "provider_available": True,
        "remote_brain_request_started": True,
        "response_started": False,
        "status": "blocked",
        "failure_family": "remote_brain_signoff",
        "failure_code": "provider_error",
    }
    assert "provider_failure_retry" not in blocked.metadata
    payload = blocked.model_dump_json()
    assert "private prompt" not in payload
    assert "provider.invalid" not in payload
    assert "provider_payload" not in payload


def test_remote_finalizer_preflight_false_does_not_claim_brain_request_started() -> None:
    service, _, _ = _service("remote_finalizer_preflight_projection")
    service.scenario_runtime = _RemoteFinalizerTimeoutRuntime(
        service.scenario_runtime,
        block_stage="plan",
        outcome=_remote_finalizer_preflight_unavailable_outcome(),
    )

    blocked = service.create_job({"user_input": "Create one neutral Character Card body view."})

    assert blocked.status == ProductJobStatusValue.BLOCKED
    failure = blocked.metadata["generation_lifecycle_failure"]
    assert failure["provider_request_started"] is False
    assert failure["remote_brain_request_started"] is False
    lifecycle = failure["remote_creative_brain_outcome"]["remote_brain_finalizer_lifecycle"]
    assert lifecycle["provider_available"] is False
    assert lifecycle["remote_brain_request_started"] is False
    assert lifecycle["failure_code"] == "provider_unavailable"
    payload = blocked.model_dump_json()
    assert "private prompt" not in payload
    assert "provider_payload" not in payload


def test_malformed_remote_outcome_is_not_persisted_when_runtime_blocks_without_result() -> None:
    create_service, _, _ = _service("malformed_remote_outcome_create")
    create_service.scenario_runtime = _RemoteFinalizerTimeoutRuntime(
        create_service.scenario_runtime,
        block_stage="plan",
        outcome=_malformed_remote_outcome(),
    )

    planning_blocked = create_service.create_job({"user_input": "Create one neutral Character Card body view."})

    generate_service, _, _ = _service("malformed_remote_outcome_generate")
    generated_candidate = generate_service.create_job({"user_input": "Create one neutral Character Card body view."})
    generate_service.scenario_runtime = _RemoteFinalizerTimeoutRuntime(
        generate_service.scenario_runtime,
        block_stage="generate",
        outcome=_malformed_remote_outcome(),
    )
    generation_blocked = generate_service.generate_job(
        generated_candidate.job_id,
        {"quality_mode": "strict"},
    )

    for service, status in (
        (create_service, planning_blocked),
        (generate_service, generation_blocked),
    ):
        assert status.status == ProductJobStatusValue.BLOCKED
        assert "remote_creative_brain_outcome" not in status.metadata
        assert "generation_lifecycle_failure" not in status.metadata
        public_payload = status.model_dump_json()
        record = service.job_store.get(status.job_id)
        assert record is not None
        durable_payload = record.request.model_dump_json()
        for payload in (public_payload, durable_payload):
            assert "unknown_unreviewed_reason" not in payload
            assert "secret malformed raw response" not in payload
            assert "secret malformed prompt" not in payload
            assert "provider.invalid" not in payload
            assert "D:/unsafe" not in payload
            assert "asset_malformed_internal" not in payload
            assert "output_malformed_internal" not in payload
            assert "provider_payload" not in payload


def test_partial_persisted_output_remains_visible_when_a_later_role_blocks_the_job() -> None:
    output_store = V3GeneratedOutputStore(storage_root=_test_store_root("partial_output") / "outputs")
    brand_service = BrandProfileService(BrandProfileStore(_test_store_root("partial_output_brand")))
    service = V3ProductApiService(
        brand_profile_service=brand_service,
        balance_adapter=TrackingBalanceAdapter(),
        output_store=output_store,
    )
    created = service.create_job(
        {
            "user_input": "Create a two-image clean glass still-life set.",
            "metadata": {"requested_image_count": 2},
        }
    )
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.warnings.append("later_role_provider_failure")
    record.warnings.append(
        "OpenAI image reference generation failed. Error code: 400 - raw provider body"
    )
    record.request.metadata["provider_failure_retry"] = _provider_no_pixel_retry_summary()
    service.job_store.save(record)

    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=(190, 210, 220)).save(buffer, format="PNG")
    persisted = output_store.save_base64_output(
        job_id=created.job_id,
        candidate_id="candidate_partial_first_role",
        asset_id="asset_partial_first_role",
        provider="test_provider",
        model="gpt-image-2",
        encoded_image=base64.b64encode(buffer.getvalue()).decode("ascii"),
        mime_type="image/png",
        output_format="png",
    )

    recovered = service.get_job(created.job_id)
    history = service.list_history()

    assert recovered.status == ProductJobStatusValue.GENERATED
    assert [candidate.output_id for candidate in recovered.candidates] == [persisted.output_id]
    assert recovered.metadata["partial_generation_recovery"] == {
        "status": "partial_output_preserved",
        "source_record_status": "blocked",
        "requested_image_count": 2,
        "delivered_output_count": 1,
        "missing_output_count": 1,
        "remaining_roles_failed": True,
        "append_only_history_preserved": True,
    }
    assert any("recoverable partial result" in warning for warning in recovered.warnings)
    assert any("image_edit_invalid_request_unattributed" in warning for warning in recovered.warnings)
    recovered_payload = recovered.model_dump_json()
    assert "raw provider body" not in recovered_payload
    assert "OpenAI image reference generation failed" not in recovered_payload
    assert "internal-binding-must-not-leak" not in recovered_payload
    assert "provider_payload" not in recovered_payload
    assert history.items[0].status == ProductJobStatusValue.GENERATED
    assert history.items[0].candidate_count == 1


def test_job_polling_closes_an_expired_background_watchdog_when_timer_delivery_is_lost() -> None:
    service, _, _ = _service("gateway_background_polling_timeout")
    created = service.create_job({"user_input": "Create one clean still-life image."})
    service.mark_job_generating(
        created.job_id,
        background_attempt_id="polling_attempt",
        background_timeout_seconds=5,
    )
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.request.metadata["background_generation_watchdog"]["started_at"] = "2000-01-01T00:00:00+00:00"

    expired = service.get_job(created.job_id)

    assert expired.status == ProductJobStatusValue.BLOCKED
    assert expired.metadata["generation_lifecycle_timeout"]["owner"] == "v3_background_generation_watchdog"


def test_expired_failure_is_hidden_before_weekly_storage_cleanup() -> None:
    service, _, _ = _service("expired_failure_projection")
    created = service.create_job({"user_input": "Create one clean still-life image."})
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.updated_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    service.job_store._records[created.job_id] = record

    expired = service.get_job(created.job_id)
    assert expired.status == ProductJobStatusValue.NOT_FOUND
    assert expired.metadata["expired_failure_artifact"] is True
    assert all(item.job_id != created.job_id for item in service.list_history().items)


def test_persistent_job_store_does_not_resurrect_a_removed_failure_record() -> None:
    root = _test_store_root("expired_failure_persistent")
    job_root = root / "jobs"
    service = V3ProductApiService(job_store=PersistentProductJobStore(job_root))
    created = service.create_job({"user_input": "Create one clean still-life image."})
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.updated_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    service.job_store.save(record)
    record_path = job_root / f"{created.job_id}.json"
    assert record_path.exists()
    record_path.unlink()

    assert service.job_store.get(created.job_id) is None
    assert all(item.job_id != created.job_id for item in service.list_history().items)


def test_project_timeout_handler_records_one_safe_terminal_timeline_item() -> None:
    service, _, _ = _service("project_gateway_background_timeout")
    handlers = V3ProductRouteHandlers(service)
    project = handlers.post_projects({"user_goal": "Create one clean still-life image."})
    created = handlers.post_project_job(
        project["project"]["project_id"],
        {"template_id": "general_template", "user_input": "Create one clean still-life image."},
    )

    pending = handlers.mark_project_job_generating(
        project["project"]["project_id"],
        created["job_id"],
        background_attempt_id="project_attempt_one",
    )
    timed_out = handlers.mark_project_job_generation_timed_out(
        project["project"]["project_id"],
        created["job_id"],
        background_attempt_id="project_attempt_one",
        timeout_seconds=675,
    )
    timeline = handlers.get_project_timeline(project["project"]["project_id"])

    assert pending["status"] == "generating"
    assert timed_out["status"] == "blocked"
    assert timed_out["metadata"]["generation_lifecycle_timeout"]["owner"] == "v3_background_generation_watchdog"
    assert any(
        item["related_job_id"] == created["job_id"] and item["item_type"] == "job_blocked"
        for item in timeline["items"]
    )


def test_project_background_worker_failure_records_one_safe_terminal_timeline_item() -> None:
    service, _, _ = _service("project_background_worker_failure")
    handlers = V3ProductRouteHandlers(service)
    project = handlers.post_projects({"user_goal": "Create one clean still-life image."})
    created = handlers.post_project_job(
        project["project"]["project_id"],
        {"template_id": "general_template", "user_input": "Create one clean still-life image."},
    )

    handlers.mark_project_job_generating(
        project["project"]["project_id"],
        created["job_id"],
        background_attempt_id="project_invalid_request",
    )
    failed = handlers.mark_project_job_generation_worker_failed(
        project["project"]["project_id"],
        created["job_id"],
        background_attempt_id="project_invalid_request",
        failure_code="background_generation_request_invalid",
    )
    timeline = handlers.get_project_timeline(project["project"]["project_id"])

    assert failed["status"] == "blocked"
    assert failed["metadata"]["generation_lifecycle_failure"]["owner"] == "v3_background_generation_worker"
    blocked_items = [
        item
        for item in timeline["items"]
        if item["related_job_id"] == created["job_id"] and item["item_type"] == "job_blocked"
    ]
    assert len(blocked_items) == 1
    assert blocked_items[0]["metadata"]["failure_code"] == "background_generation_request_invalid"


def test_persistent_product_job_store_restores_project_job_contract_after_restart() -> None:
    root = _test_store_root("persistent_product_job_store")
    job_root = root / "jobs"
    project_root = root / "projects"
    first_service = V3ProductApiService(job_store=PersistentProductJobStore(job_root))
    first_handlers = V3ProductRouteHandlers(
        service=first_service,
        project_store=PersistentProjectStore(project_root),
    )
    project = first_handlers.post_projects({"user_goal": "Create one clean still-life image."})
    created = first_handlers.post_project_job(
        project["project"]["project_id"],
        {"template_id": "general_template", "user_input": "Create one clean still-life image."},
    )
    first_service.mark_job_generating(
        created["job_id"],
        background_attempt_id="persistent_attempt",
        background_timeout_seconds=675,
    )

    restarted_service = V3ProductApiService(job_store=PersistentProductJobStore(job_root))
    restarted_handlers = V3ProductRouteHandlers(
        service=restarted_service,
        project_store=PersistentProjectStore(project_root),
    )
    restored = restarted_handlers.get_job(created["job_id"])
    restored_project = restarted_handlers.get_project(project["project"]["project_id"])

    assert restored["status"] == "generating"
    assert restored["metadata"]["background_generation_watchdog"]["background_attempt_id"] == "persistent_attempt"
    assert created["job_id"] in restored_project["project"]["job_ids"]


def test_persistent_job_store_refreshes_a_cached_lifecycle_after_background_terminal_write() -> None:
    """Polling must not preserve a stale ``generating`` state across workers."""

    root = _test_store_root("persistent_product_job_refresh")
    job_root = root / "jobs"
    writer = V3ProductApiService(job_store=PersistentProductJobStore(job_root))
    created = writer.create_job({"user_input": "Create one clean still-life image."})
    writer.mark_job_generating(
        created.job_id,
        background_attempt_id="writer_attempt",
        background_timeout_seconds=675,
    )

    polling_service = V3ProductApiService(job_store=PersistentProductJobStore(job_root))
    assert polling_service.get_job(created.job_id).status == ProductJobStatusValue.GENERATING

    writer.mark_job_generation_worker_failed(
        created.job_id,
        background_attempt_id="writer_attempt",
        failure_code="background_generation_worker_error",
    )

    refreshed = polling_service.get_job(created.job_id)
    assert refreshed.status == ProductJobStatusValue.BLOCKED
    assert refreshed.metadata["generation_lifecycle_failure"]["failure_code"] == "background_generation_worker_error"


def test_persistent_job_store_retries_a_transient_windows_replace_lock(monkeypatch) -> None:
    """A poller's short-lived file handle must not abort a background Job."""

    root = _test_store_root("persistent_product_job_store_replace_retry")
    store = PersistentProductJobStore(root / "jobs")
    service = V3ProductApiService(job_store=store)
    created = service.create_job({"user_input": "Create one natural still-life photograph."})
    record = store.get(created.job_id)
    assert record is not None
    record.warnings.append("persist after a simulated polling read")

    original_replace = Path.replace
    attempts = {"count": 0}

    def transiently_locked_replace(self, target):
        if self.name == f"{created.job_id}.json.tmp":
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise PermissionError(5, "access denied", str(target))
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", transiently_locked_replace)
    store.save(record)

    assert attempts["count"] == 3
    restored = store.get(created.job_id)
    assert restored is not None
    assert restored.warnings[-1] == "persist after a simulated polling read"


def test_v3_product_api_accepts_campaign_and_style_continuation_product_concepts() -> None:
    service, _, _ = _service("campaign")
    brand = service.create_brand(
        {
            "brand_id": "brand_product_api_campaign",
            "brand_name": "Campaign Tea",
            "industry": IndustryCategory.BEVERAGE,
            "visual_tone": ["fresh", "precise"],
            "color_palette": ["mint green"],
        }
    )

    created = service.create_job(
        {
            "user_input": "沿用品牌风格，做一组新品上市图。",
            "continue_style_from_brand_id": brand.brand.brand_id,
            "campaign": {
                "campaign_id": "campaign_summer_launch",
                "campaign_name": "Summer launch",
                "business_goal": "new product launch",
                "platforms": [Platform.XIAOHONGSHU],
            },
        }
    )

    assert created.campaign.campaign_id == "campaign_summer_launch"
    assert created.campaign.campaign_name == "Summer launch"
    assert created.campaign.business_goal == "new product launch"
    assert created.campaign.target_platforms == [Platform.XIAOHONGSHU]
    assert created.style_continuation.enabled is True
    assert created.style_continuation.source_brand_id == "brand_product_api_campaign"
    assert "seed" not in created.model_dump_json()
    assert "sampler" not in created.model_dump_json()


def test_v3_product_api_generates_selects_and_applies_brand_memory_update() -> None:
    service, brand_service, balance = _service("select")
    brand_response = service.create_brand(
        {
            "brand_id": "brand_product_api",
            "brand_name": "Test Tea",
            "industry": IndustryCategory.BEVERAGE,
            "visual_tone": ["fresh", "clean"],
            "color_palette": ["mint green", "cream white"],
            "platform_history": [Platform.XIAOHONGSHU],
        }
    )

    created = service.create_job(
        {
            "user_input": "沿用上次风格，帮我做一组奶茶店端午节活动图，适合小红书。",
            "continue_style_from_brand_id": brand_response.brand.brand_id,
        }
    )
    generated = service.generate_job(created.job_id)
    selected = service.select_result(generated.job_id)
    updated = brand_service.load_profile("brand_product_api")

    assert generated.status == ProductJobStatusValue.GENERATED
    assert generated.candidates
    assert selected.status == ProductJobStatusValue.SELECTED
    assert selected.selected_result.selected_candidate_ids
    assert selected.selected_result.memory_update_applied is True
    assert updated is not None
    assert updated.successful_asset_ids
    assert balance.checked_credits == [0]


def test_v3_product_api_does_not_accept_low_level_generation_controls() -> None:
    with pytest.raises(ValidationError):
        CreateCreativeJobRequest.model_validate({"user_input": "做一个活动图", "seed": 123})
    with pytest.raises(ValidationError):
        CreateCreativeJobRequest.model_validate({"user_input": "做一个活动图", "metadata": {"sampler": "hidden"}})
    with pytest.raises(ValidationError):
        GenerateJobRequest.model_validate({"quality_mode": "standard", "metadata": {"adapter scale": 0.8}})
    with pytest.raises(ValidationError):
        SelectResultRequest.model_validate({"metadata": {"node graph": {"name": "internal"}}})
    with pytest.raises(ValidationError):
        CreateBrandRequest.model_validate({"brand_name": "Hidden", "metadata": {"LoRA": "internal"}})

    service, _, _ = _service("product_only")
    status = service.create_job({"user_input": "做一个活动宣传图，适合小红书。"})
    payload = status.model_dump_json()

    assert "seed" not in payload
    assert "sampler" not in payload
    assert "node graph" not in payload


def test_public_provider_failure_keeps_runtime_budget_without_transport_details() -> None:
    projected = V3ProductApiService._public_provider_failure_retry(  # noqa: SLF001
        {
            "executed_count": 0,
            "max_attempts": 1,
            "fresh_upstream_requests": 1,
            "final_status": "failed",
            "final_classification": "retryable_provider_failure",
            "final_failure_code": "provider_timeout",
            "attempts": [
                {
                    "attempt": 1,
                    "status": "failed",
                    "classification": "retryable_provider_failure",
                    "failure_code": "provider_timeout",
                    "retryable": True,
                    "message": "private provider body",
                    "runtime_transport": {"endpoint": "https://private.invalid"},
                }
            ],
            "execution_audit": {
                "gateway_managed_failover": True,
                "gateway_managed_failover_timeout_seconds": 600.0,
                "outer_timeout_seconds": 605.0,
                "outer_max_attempts": 1,
                "provider_prompt_chars": 4000,
                "provider_account_id": "private-account",
            },
        }
    )

    assert projected["runtime_budget"] == {
        "gateway_managed_failover": True,
        "gateway_budget_seconds": 600.0,
        "outer_timeout_seconds": 605.0,
        "outer_max_attempts": 1,
    }
    assert "private provider body" not in str(projected)
    assert "private.invalid" not in str(projected)
    assert "private-account" not in str(projected)
    assert "provider_prompt_chars" not in str(projected)


def test_minimal_ui_contract_uses_semantic_controls_and_v3_routes() -> None:
    service, _, _ = _service("ui")
    status = service.create_job({"user_input": "帮我做一个活动宣传图，适合小红书。"})
    contract = get_minimal_ui_contract()
    html = render_minimal_job_view(status.model_dump(mode="json"))

    assert contract["entry_route"] == "/creative-agent-v3"
    assert contract["api_namespace"] == API_NAMESPACE
    assert contract["calls_only_v3_api_namespace"] == API_NAMESPACE
    assert any(control["element"] == "textarea" and control["label"] == "Creative request" for control in contract["semantic_controls"])
    assert 'aria-label="Create creative job"' in html
    assert 'name="user_input"' in html
    assert 'id="v3-job-status"' in html
    assert status.job_id in html


def test_framework_neutral_route_handlers_return_product_status_payloads() -> None:
    service, _, _ = _service("routes")
    handlers = V3ProductRouteHandlers(service)

    created = handlers.post_jobs({"user_input": "帮我做一张清爽活动海报，适合小红书。"})
    generated = handlers.post_generate(created["job_id"])
    selected = handlers.post_select(created["job_id"])

    assert created["api_namespace"] == "/api/v3/creative-agent"
    assert generated["status"] == "generated"
    assert generated["asset_series"]
    assert selected["selected_result"]["selected_asset_ids"]


def test_framework_neutral_route_handlers_support_v37_product_aliases() -> None:
    service, _, _ = _service("route_aliases")
    handlers = V3ProductRouteHandlers(service)

    brand = handlers.post_product_brands(
        {
            "brand_id": "brand_product_api_alias",
            "brand_name": "Alias Tea",
            "industry": IndustryCategory.BEVERAGE,
        }
    )
    created = handlers.post_creative_jobs(
        {
            "user_input": "帮我做一组茶饮新品发布图，适合社交平台。",
            "brand_id": brand["brand"]["brand_id"],
        }
    )
    fetched = handlers.get_creative_job(created["job_id"])
    generated = handlers.post_creative_job_generate(created["job_id"], {"quality_mode": "strict"})
    selected = handlers.post_creative_job_select(created["job_id"])

    assert brand["route"] == "/api/v3/creative-agent/brands"
    assert fetched["routes"]["get_creative_job"] == "/v3/creative-jobs/{job_id}"
    assert generated["status"] == "generated"
    assert selected["status"] == "selected"
