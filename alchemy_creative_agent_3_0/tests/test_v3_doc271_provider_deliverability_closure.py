"""Phase 0 red contracts for a Provider deliverability closure receipt.

The tests use Project Mode/Product API in-memory stores, a deterministic
Remote-Brain test double, and local browser transports only. They never select
an app Provider, call MCP/ImageGen, contact a remote endpoint, or mutate a
live project/job.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter
from alchemy_creative_agent_3_0.app.generation_router.providers import (
    GenerationProvider,
    ProductionImageGenerationProvider,
    configured_provider_execution_identity,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.provider_deliverability_closure import (
    _terminal_job_receipt as _runtime_terminal_job_receipt,
    _normalized_final_policy_evidence,
    verified_provider_deliverability_closure_receipt,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectRecord,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _png_base64,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
    _bind_locked_person_identity,
    _job_payload,
)
from app.config import settings
from app.providers.base import ProviderRuntimeError


PROJECT_ID = "doc271-project"
POLICY_JOB_ID = "job-659-policy-closure"
RAW_POLICY_TEXT = "content_policy_violation private-route /srv/provider sha256:secret"
EXECUTION_AUDIT = {
    "schema_version": "v3_provider_execution_audit_v1",
    "authority": "v3_generation_router",
    "provider_capability_id": "doc271-local-provider:hard_input_image_edit_v1",
    "provider_name": "doc271-local-provider",
    "model": "doc271-model-a",
    "operation": "image_edit",
    "route_identity": "configured:doc271-local-provider:doc271-model-a:openai-standard",
}


def _configured_route_identity() -> str:
    """Model the server configuration identity that Phase 1 must resolve."""

    return "configured:{provider}:{model}:{profile}".format(
        provider=settings.default_image_provider,
        model=settings.default_image_model,
        profile=settings.openai_image_transport_profile,
    )


class _TerminalFailureProvider(GenerationProvider):
    """Deterministic local no-pixel Provider failure; no network transport."""

    provider_name = "doc271-local-provider"

    def __init__(
        self,
        *,
        failure_code: str = "provider_policy_blocked",
        upstream_code: str = "content_policy_violation",
    ) -> None:
        self.calls = 0
        self.failure_code = failure_code
        self.upstream_code = upstream_code

    def execution_identity(self, *, operation: str) -> dict[str, str]:
        return configured_provider_execution_identity(
            provider_name=self.provider_name,
            model=str(settings.default_image_model),
            operation=operation,
            transport_profile=str(settings.openai_image_transport_profile),
        )

    def generate(self, request):  # noqa: ANN001, ANN201
        self.calls += 1
        error = ProviderRuntimeError(
            RAW_POLICY_TEXT,
            provider=self.provider_name,
            detail={"code": self.upstream_code, "operation": "image_edit"},
        )
        error.provider_failure_retry = {
            "executed_count": 0,
            "max_attempts": 1,
            "fresh_upstream_requests": 1,
            "final_status": "failed",
            "final_classification": "non_retryable_provider_failure",
            "final_failure_code": self.failure_code,
            "attempts": [
                {
                    "attempt": 1,
                    "output_index": 1,
                    "status": "failed",
                    "classification": "non_retryable_provider_failure",
                    "failure_code": self.failure_code,
                    "retryable": False,
                    "upstream_code": self.upstream_code,
                    "role_output_index": 1,
                    "execution_audit": self.execution_identity(operation="image_edit"),
                }
            ],
            "reference_input_execution": {
                "operation": "image_edit",
                "reference_count": 4,
                "failure_code": self.failure_code,
            },
            "execution_audit": self.execution_identity(operation="image_edit"),
            "terminal_receipt_source": "provider_failure_retry.execution_audit",
        }
        raise error


def _fixture(tmp_path, *, provider: GenerationProvider | None = None):
    handlers, catalog = _handlers(tmp_path)
    provider = provider or _TerminalFailureProvider()
    handlers.service.scenario_runtime.generation_router = GenerationRouter(provider=provider)
    project = _project(handlers)
    project_record = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    project_record.user_goal = _payload([], key="doc271-current-goal")["user_input"]
    project_record.short_summary = project_record.user_goal
    handlers.project_service.project_store.save_project(project_record)
    project["user_goal"] = project_record.user_goal
    product_ids = [
        _ready_product_upload(
            handlers,
            filename=f"doc271-product-{index}.png",
            color=(80 + index * 20, 135, 165),
        )
        for index in range(4)
    ]
    _add_product_references(handlers, project["project_id"], product_ids)
    face_output_ids = _bind_locked_person_identity(
        handlers,
        catalog,
        project_id=project["project_id"],
    )
    return handlers, provider, project, product_ids, face_output_ids


def _payload(product_ids: list[str], *, key: str, user_input: str | None = None) -> dict[str, Any]:
    payload = _job_payload(uploaded_asset_ids=product_ids, key=key)
    payload["user_input"] = "Generate an apparel-on-model listing image with the supplied product."
    payload["commerce_profile_patch"] = {
        "product_category": "apparel",
        "apparel_construction": {
            "silhouette": "short-sleeve garment",
            "material": "soft knit fabric",
        },
    }
    payload["metadata"]["requested_image_count"] = 1
    if user_input is not None:
        payload["user_input"] = user_input
    return payload


def _create_policy_block(handlers, provider, project, product_ids) -> tuple[dict[str, Any], Any]:
    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-first-policy-command"),
    )
    status = handlers.post_project_job_generate(project["project_id"], created["job_id"])
    record = handlers.service.get_job_record(created["job_id"])
    assert status["status"] == ProductJobStatusValue.BLOCKED.value
    assert record is not None
    assert provider.calls == 1
    assert record.request.metadata["provider_failure_retry"]["final_failure_code"] == "provider_policy_blocked"
    return created, record


def _closure(record) -> dict[str, Any]:
    return record.request.metadata["provider_deliverability_closure_receipt"]


def _terminal_job_receipt(record) -> dict[str, Any] | None:
    failure = record.request.metadata["provider_failure_retry"]
    attempts = [
        {
            "attempt": int(item["attempt"]),
            "output_index": int(item["output_index"]) if item.get("output_index") is not None else None,
            "status": str(item.get("status") or ""),
            "classification": str(item.get("classification") or ""),
            "failure_code": str(item.get("failure_code") or ""),
            "upstream_code": str(item.get("upstream_code") or ""),
            "role_key": str(item.get("role_key") or ""),
            "role_output_index": item.get("role_output_index"),
            "execution_audit": dict(item.get("execution_audit") or {}),
        }
        for item in failure["attempts"]
    ]
    final_evidence = _normalized_final_policy_evidence(
        failure["attempts"],
        execution_audit=failure["execution_audit"],
    )
    persisted_final_evidence = failure.get("doc271_per_output_policy_evidence")
    if (
        final_evidence is None
        or (
            persisted_final_evidence is not None
            and persisted_final_evidence != final_evidence
        )
    ):
        return None
    payload = {
        "schema_version": "doc271_terminal_job_receipt_v1",
        "project_id": str(record.request.metadata["project_id"]),
        "terminal_job_id": record.job_id,
        "terminal_status": record.status.value,
        "provider_failure_code": str(failure["final_failure_code"]),
        "provider_failure_classification": str(failure["final_classification"]),
        "policy_evidence_code": "content_policy_violation",
        "provider_attempt_evidence": attempts,
        "provider_attempt_evidence_digest": hashlib.sha256(
            json.dumps(attempts, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "per_output_policy_evidence": final_evidence,
        "per_output_policy_evidence_digest": hashlib.sha256(
            json.dumps(final_evidence, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "execution_audit": dict(failure["execution_audit"]),
        "terminal_receipt_source": str(failure["terminal_receipt_source"]),
        "created_at": str(failure["terminal_created_at"]),
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return {
        **payload,
        "receipt_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _seed_pre_doc271_terminal_record(
    handlers,
    project,
    product_ids: list[str],
    *,
    failure_code: str = "provider_policy_blocked",
    upstream_code: str = "content_policy_violation",
    missing: str | None = None,
):
    """Persist an old terminal Job without a Doc271 receipt or Provider call."""

    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key=f"doc271-pre-doc271-{missing or failure_code}"),
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata = {
        **dict(record.request.metadata),
        "provider_failure_retry": {
            "executed_count": 0,
            "max_attempts": 1,
            "fresh_upstream_requests": 1,
            "final_status": "failed",
            "final_classification": "non_retryable_provider_failure",
            "final_failure_code": failure_code,
            "attempts": [
                {
                    "attempt": 1,
                    "output_index": 1,
                    "status": "failed",
                    "classification": "non_retryable_provider_failure",
                    "failure_code": failure_code,
                    "retryable": False,
                    "upstream_code": upstream_code,
                    "role_output_index": 1,
                    "execution_audit": handlers.service.scenario_runtime.generation_router.provider.execution_identity(
                        operation="image_edit"
                    ),
                }
            ],
            "reference_input_execution": {
                "operation": "image_edit",
                "reference_count": 4,
                "failure_code": failure_code,
            },
            # A verified historical terminal record carries the exact generic
            # execution identity that is still configured for this project.
            "execution_audit": handlers.service.scenario_runtime.generation_router.provider.execution_identity(
                operation="image_edit"
            ),
            "terminal_receipt_source": "provider_failure_retry.execution_audit",
            # A pre-Doc271 terminal fact can be read only when it already has
            # a durable, immutable terminal timestamp.
            "terminal_created_at": "2026-08-12T00:00:00+00:00",
        },
    }
    terminal_receipt = _terminal_job_receipt(record)
    if terminal_receipt is not None:
        record.request.metadata["doc271_terminal_job_receipt"] = terminal_receipt
    if missing == "canonical_goal":
        record.request.metadata.pop("doc271_command_binding", None)
    elif missing == "source_sha_role_channel_order":
        record.request.metadata["physical_renderer_reference_plans"]["1"]["references"][0].pop("content_sha256")
    elif missing == "locked_binding":
        record.request.metadata.pop("frozen_visual_asset_binding_set", None)
    elif missing == "provider_route":
        record.request.metadata["provider_failure_retry"]["execution_audit"].pop("route_identity", None)
    elif missing == "final_physical_plan":
        record.request.metadata.pop("physical_renderer_reference_plans", None)
    elif missing == "terminal_project_linkage":
        record.request.metadata.pop("project_id", None)
    elif missing == "terminal_job_receipt":
        record.request.metadata.pop("doc271_terminal_job_receipt", None)
    elif missing == "terminal_job_receipt_digest_mismatch":
        record.request.metadata["doc271_terminal_job_receipt"]["receipt_digest"] = "0" * 64
    elif missing == "terminal_created_at":
        record.request.metadata["provider_failure_retry"].pop("terminal_created_at", None)
    record.warnings = ["V3 real image generation failed (provider_policy_blocked)."]
    record.lifecycle = handlers.service._build_lifecycle(record)  # noqa: SLF001
    handlers.service.job_store.save(record)
    return created, record


def _install_local_production_policy_provider(handlers, monkeypatch, *, retry_first: bool = False):
    """Exercise the actual renderer retry and role-execution path locally."""

    provider = ProductionImageGenerationProvider(output_store=handlers.service.output_store)
    calls: list[str] = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        calls.append(provider_name)
        if retry_first and len(calls) == 1:
            raise ProviderRuntimeError(
                "temporary upstream timeout",
                provider=provider_name,
                detail={"code": "gateway_timeout", "error_type": "TimeoutError"},
            )
        raise ProviderRuntimeError(
            "explicit content policy refusal",
            provider=provider_name,
            detail={"code": "content_policy_violation", "operation": "image_edit"},
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    monkeypatch.setattr(settings, "openai_api_key", "doc271-local-test-key")
    monkeypatch.setattr(settings, "default_image_provider", "openai_gpt_image")
    monkeypatch.setattr(settings, "openai_image_gateway_managed_failover", False)
    monkeypatch.setattr(settings, "openai_image_edit_transient_cooldown_seconds", 0.0)
    handlers.service.scenario_runtime.generation_router = GenerationRouter(production_provider=provider)
    return provider, calls


def _seed_multi_output_policy_block(
    handlers,
    project,
    product_ids: list[str],
    *,
    attempts: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], Any]:
    """Seed an all-no-pixel two-output terminal record from real Doc269 plans."""

    payload = _payload(product_ids, key="doc271-multi-output-policy-command")
    payload["metadata"]["requested_image_count"] = 2
    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert set(record.request.metadata["physical_renderer_reference_plans"]) == {"1", "2"}
    if attempts is None:
        attempts = [
            {
                "attempt": 1,
                "output_index": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "content_policy_violation",
                "role_output_index": 1,
            },
            {
                "attempt": 2,
                "output_index": 2,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "content_policy_violation",
                "role_output_index": 2,
            },
        ]
    execution_audit = handlers.service.scenario_runtime.generation_router.provider.execution_identity(
        operation="image_edit"
    )
    attempts = [
        {
            **item,
            "role_output_index": item.get("role_output_index", item.get("output_index")),
            "execution_audit": dict(item.get("execution_audit") or execution_audit),
        }
        for item in attempts
    ]
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata = {
        **dict(record.request.metadata),
        "provider_failure_retry": {
            "executed_count": 0,
            "max_attempts": len(attempts),
            "fresh_upstream_requests": len(attempts),
            "final_status": "failed",
            "final_classification": "non_retryable_provider_failure",
            "final_failure_code": "provider_policy_blocked",
            "attempts": attempts,
            "reference_input_execution": {
                "operation": "image_edit",
                "reference_count": 4,
                "failure_code": "provider_policy_blocked",
            },
            "execution_audit": execution_audit,
            "terminal_receipt_source": "provider_failure_retry.execution_audit",
            "terminal_created_at": "2026-08-12T00:00:00+00:00",
        },
    }
    terminal_receipt = _terminal_job_receipt(record)
    if terminal_receipt is not None:
        record.request.metadata["doc271_terminal_job_receipt"] = terminal_receipt
    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001
    record.lifecycle = handlers.service._build_lifecycle(record)  # noqa: SLF001
    handlers.service.job_store.save(record)
    return created, record


def _rehashed_doc269_plan(raw_plan: dict[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(raw_plan)
    digest_payload = {
        key: candidate[key]
        for key in (
            "schema_version",
            "job_id",
            "output_index",
            "projection_digest",
            "maximum_reference_images",
            "references",
            "reference_image_asset_ids",
            "reference_image_count",
        )
    }
    candidate["plan_digest"] = hashlib.sha256(
        json.dumps(digest_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return candidate


def test_doc271_explicit_policy_failure_writes_one_exact_server_owned_closure(tmp_path) -> None:
    handlers, provider, project, product_ids, face_output_ids = _fixture(tmp_path)
    created, record = _create_policy_block(handlers, provider, project, product_ids)

    receipt = _closure(record)
    assert receipt["authority"] == "v3_provider_deliverability_closure"
    assert receipt["project_id"] == project["project_id"]
    assert receipt["terminal_job_id"] == created["job_id"]
    assert receipt["terminal_job_receipt_digest"] == _terminal_job_receipt(record)["receipt_digest"]
    assert receipt["created_at"] == record.request.metadata["provider_failure_retry"]["terminal_created_at"]
    assert receipt["terminal_job_receipt_source"] == "specialized_role_execution.provider_failure"
    assert receipt["policy_evidence_class"] == "explicit_content_policy_violation"
    expected_execution_identity = provider.execution_identity(operation="image_edit")
    assert receipt["provider_capability_id"] == expected_execution_identity["provider_capability_id"]
    assert receipt["provider_name"] == expected_execution_identity["provider_name"]
    assert receipt["provider_model"] == expected_execution_identity["model"]
    assert receipt["provider_operation"] == expected_execution_identity["operation"]
    assert receipt["provider_route_identity"] == expected_execution_identity["route_identity"]
    bindings = receipt["per_output_reference_bindings"]
    assert [item["output_index"] for item in bindings] == [1]
    assert bindings[0]["reference_binding"]["ordered_reference_channels"] == [
        "product_truth",
        "people_identity",
        "people_identity",
        "people_identity",
    ]
    projection = record.request.metadata["professional_ecommerce_physical_product_projections"]["1"]
    assert bindings[0]["reference_binding"]["ordered_reference_ids"] == [
        projection["selected_product_asset_ids"][0],
        *face_output_ids,
    ]
    assert bindings[0]["reference_binding"]["locked_face_output_ids"] == face_output_ids
    status = handlers.service.get_job(created["job_id"]).model_dump(mode="json")
    project_view = handlers.get_project(project["project_id"])
    public_operation = project_view["metadata"]["current_operation"]
    public_text = str({"status": status, "operation": public_operation})
    for private_value in (
        RAW_POLICY_TEXT,
        record.request.user_input,
        "/srv/provider",
        "sha256:secret",
        receipt["terminal_job_receipt_digest"],
        receipt["provider_capability_id"],
        receipt["provider_name"],
        receipt["provider_model"],
        receipt["provider_operation"],
        receipt["provider_route_identity"],
        receipt["current_project_source_binding_digest"],
    ):
        assert private_value not in public_text
    for private_field in (
        "provider_deliverability_closure_receipt",
        "terminal_job_id",
        "terminal_job_receipt_digest",
        "terminal_job_receipt_source",
        "created_at",
        "provider_capability_id",
        "provider_name",
        "provider_model",
        "provider_operation",
        "provider_route_identity",
        "canonical_goal_prompt_digest",
        "doc271_command_binding",
        "doc271_project_goal_snapshot",
        "goal_snapshot_id",
        "goal_snapshot_digest",
        "current_project_source_binding_digest",
        "ordered_reference_ids",
        "physical_plan_digests",
        "per_output_reference_bindings",
    ):
        assert private_field not in public_text
    assert created["job_id"] not in str(public_operation)


def test_doc271_product_only_policy_closure_replays_without_people_binding(tmp_path, monkeypatch) -> None:
    handlers, provider, project, product_ids, face_output_ids = _fixture(tmp_path)
    product_only = (
        "Product-only flat lay. No person wearing it, no model, no child, and no face."
    )
    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-product-only-policy", user_input=product_only),
    )
    status = handlers.post_project_job_generate(project["project_id"], created["job_id"])
    record = handlers.service.get_job_record(created["job_id"])

    assert status["status"] == ProductJobStatusValue.BLOCKED.value
    assert record is not None
    binding = _closure(record)["per_output_reference_bindings"][0]["reference_binding"]
    assert binding["ordered_reference_channels"] == ["product_truth"]
    assert binding["locked_face_output_ids"] == []
    assert set(face_output_ids).isdisjoint(binding["ordered_reference_ids"])
    before_job_ids = list(handlers.get_project(project["project_id"])["project"]["job_ids"])

    def unexpected_provider(_request):  # noqa: ANN001
        raise AssertionError("product-only closure reached Provider")

    monkeypatch.setattr(provider, "generate", unexpected_provider)
    closed = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-product-only-replay", user_input=product_only),
    )

    assert closed["status"] == ProductJobStatusValue.BLOCKED.value
    assert not closed.get("job_id")
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == before_job_ids


def test_doc271_same_exact_closed_binding_stops_before_new_job_brain_or_provider(tmp_path, monkeypatch) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    _closure(record)
    before_job_ids = list(handlers.get_project(project["project_id"])["project"]["job_ids"])
    before_metadata = deepcopy(
        handlers.project_service._require_project(project["project_id"]).metadata  # noqa: SLF001
    )
    planning_calls: list[object] = []

    def unexpected_plan(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        planning_calls.append((args, kwargs))
        raise AssertionError("Doc271 exact closure reached Brain planning")

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", unexpected_plan)
    closed = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-repeat-exact-policy-command"),
    )

    assert closed["status"] == "blocked"
    assert closed["metadata"]["current_operation"]["state"] == "delivery_route_unavailable"
    assert not closed.get("job_id")
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == before_job_ids
    assert handlers.project_service._require_project(project["project_id"]).metadata == before_metadata  # noqa: SLF001
    assert planning_calls == []
    assert provider.calls == 1


def test_doc271_complete_two_output_policy_closure_stops_exact_repeat_before_job_brain_or_provider(
    tmp_path,
    monkeypatch,
) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    created, record = _seed_multi_output_policy_block(handlers, project, product_ids)

    receipt = _closure(record)
    assert [item["output_index"] for item in receipt["per_output_reference_bindings"]] == [1, 2]
    assert receipt["physical_plan_digests"] == [
        record.request.metadata["physical_renderer_reference_plans"][key]["plan_digest"]
        for key in ("1", "2")
    ]
    planning_calls: list[object] = []

    def unexpected_plan(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        planning_calls.append((args, kwargs))
        raise AssertionError("Doc271 exact multi-output closure reached Brain planning")

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", unexpected_plan)
    closed = handlers.post_project_job(
        project["project_id"],
        {
            **_payload(product_ids, key="doc271-repeat-two-output-policy-command"),
            "metadata": {
                **_payload(product_ids, key="doc271-repeat-two-output-policy-command")["metadata"],
                "requested_image_count": 2,
            },
        },
    )

    assert closed["status"] == "blocked"
    assert not closed.get("job_id")
    assert closed["metadata"]["current_operation"]["state"] == "delivery_route_unavailable"
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == [created["job_id"]]
    assert planning_calls == []
    assert provider.calls == 0


def test_doc271_real_two_output_executor_persists_exact_policy_evidence_and_closes_repeat(
    tmp_path,
    monkeypatch,
) -> None:
    handlers, _provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    production, calls = _install_local_production_policy_provider(handlers, monkeypatch)
    payload = _payload(product_ids, key="doc271-real-two-output-policy")
    payload["metadata"].update({"requested_image_count": 2, "require_real_images": True})
    created = handlers.post_project_job(project["project_id"], payload)
    status = handlers.post_project_job_generate(project["project_id"], created["job_id"])
    record = handlers.service.get_job_record(created["job_id"])

    assert status["status"] == "blocked"
    assert record is not None
    assert len(calls) == 2
    assert handlers.service.output_store.list_by_job(created["job_id"]) == []
    assert record.generation_result is not None
    assert record.generation_result.asset_pack.assets  # planned roles are not delivered pixels
    failure = record.request.metadata["provider_failure_retry"]
    evidence = failure["doc271_per_output_policy_evidence"]
    assert [item["output_index"] for item in evidence] == [1, 2]
    assert [item["role_output_index"] for item in evidence] == [1, 2]
    assert all(item["classification"] == "non_retryable_provider_failure" for item in evidence)
    assert all(item["upstream_code"] == "content_policy_violation" for item in evidence)
    assert failure["terminal_created_at"]
    assert failure["terminal_receipt_source"] == "specialized_role_execution.provider_failure"
    assert _closure(record)["terminal_job_receipt_digest"] == _terminal_job_receipt(record)["receipt_digest"]
    assert _closure(record)["terminal_role_execution_plan_digest"]

    before_jobs = list(handlers.get_project(project["project_id"])["project"]["job_ids"])
    closed = handlers.post_project_job(
        project["project_id"],
        {
            **_payload(product_ids, key="doc271-real-two-output-repeat"),
            "metadata": {
                **_payload(product_ids, key="doc271-real-two-output-repeat")["metadata"],
                "requested_image_count": 2,
            },
        },
    )
    assert closed["metadata"]["current_operation"]["state"] == "delivery_route_unavailable"
    assert not closed.get("job_id")
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == before_jobs
    assert len(calls) == 2
    assert production._last_provider_failure_retry_summary["final_failure_code"] == "provider_policy_blocked"  # noqa: SLF001


def test_doc271_retry_then_terminal_policy_uses_final_normalized_evidence_and_authenticates_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    handlers, _provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _production, calls = _install_local_production_policy_provider(handlers, monkeypatch, retry_first=True)
    created = handlers.post_project_job(
        project["project_id"],
        {
            **_payload(product_ids, key="doc271-retry-then-policy"),
            "metadata": {
                **_payload(product_ids, key="doc271-retry-then-policy")["metadata"],
                "require_real_images": True,
            },
        },
    )
    status = handlers.post_project_job_generate(project["project_id"], created["job_id"])
    record = handlers.service.get_job_record(created["job_id"])

    assert status["status"] == "blocked"
    assert record is not None
    assert len(calls) == 2
    failure = record.request.metadata["provider_failure_retry"]
    assert failure["attempts"][0]["upstream_code"] == "gateway_timeout"
    assert failure["attempts"][-1]["upstream_code"] == "content_policy_violation"
    assert failure["doc271_per_output_policy_evidence"] == [
        {
            "output_index": 1,
            "role_output_index": 1,
            "status": "failed",
            "classification": "non_retryable_provider_failure",
            "failure_code": "provider_policy_blocked",
            "upstream_code": "content_policy_violation",
            "execution_audit": failure["execution_audit"],
        }
    ]
    terminal_before = _terminal_job_receipt(record)
    assert terminal_before is not None
    failure["doc271_per_output_policy_evidence"][0]["upstream_code"] = "tampered"
    assert _terminal_job_receipt(record) is None
    assert "provider_deliverability_closure_receipt" in record.request.metadata


@pytest.mark.parametrize(
    "attempts",
    [
        [
            {
                "attempt": 1,
                "output_index": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "content_policy_violation",
            }
        ],
        [
            {
                "attempt": 1,
                "output_index": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "content_policy_violation",
            },
            {
                "attempt": 2,
                "output_index": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "content_policy_violation",
            },
        ],
        [
            {
                "attempt": 1,
                "output_index": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "content_policy_violation",
            },
            {
                "attempt": 2,
                "output_index": 3,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "content_policy_violation",
            },
        ],
        [
            {
                "attempt": 1,
                "output_index": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "content_policy_violation",
            },
            {
                "attempt": 2,
                "output_index": 2,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "retryable": False,
                "upstream_code": "different_failure",
            },
        ],
    ],
)
def test_doc271_incomplete_or_ambiguous_two_output_policy_evidence_fails_open(
    tmp_path,
    attempts: list[dict[str, Any]],
) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _seed_multi_output_policy_block(handlers, project, product_ids, attempts=attempts)

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    next_job = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-invalid-two-output-policy-evidence"),
    )
    assert next_job["status"] == "planned"
    assert next_job["job_id"] != record.job_id
    assert provider.calls == 0


@pytest.mark.parametrize("mutation", ["plan_sha", "file_sha", "projection_mismatch", "cross_output_plan"])
def test_doc271_any_two_output_plan_or_projection_drift_fails_open(tmp_path, mutation: str) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _seed_multi_output_policy_block(handlers, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    plans = record.request.metadata["physical_renderer_reference_plans"]
    projections = record.request.metadata["professional_ecommerce_physical_product_projections"]
    if mutation == "plan_sha":
        plans["2"]["references"][0]["content_sha256"] = "0" * 64
        plans["2"] = _rehashed_doc269_plan(plans["2"])
    elif mutation == "file_sha":
        path = plans["2"]["references"][0]["file_path"]
        with open(path, "ab") as handle:
            handle.write(b"doc271-file-drift")
    elif mutation == "projection_mismatch":
        plans["2"]["projection_digest"] = projections["1"]["projection_digest"]
        plans["2"] = _rehashed_doc269_plan(plans["2"])
    else:
        plans["2"] = deepcopy(plans["1"])
        plans["2"]["output_index"] = 2
        plans["2"] = _rehashed_doc269_plan(plans["2"])
    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001
    handlers.service.job_store.save(record)

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    if mutation != "file_sha":
        next_job = handlers.post_project_job(
            project["project_id"],
            {
                **_payload(product_ids, key=f"doc271-two-output-{mutation}"),
                "metadata": {
                    **_payload(product_ids, key=f"doc271-two-output-{mutation}")["metadata"],
                    "requested_image_count": 2,
                },
            },
        )
        assert next_job["status"] == "planned"
        assert next_job["job_id"] != record.job_id
    assert provider.calls == 0


@pytest.mark.parametrize("mutation", ["role_key", "output_index", "policy", "job_id"])
def test_doc271_frozen_specialized_execution_plan_mutation_fails_open(tmp_path, mutation: str) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    frozen_plan = record.request.metadata["specialized_role_execution_plan"]
    if mutation == "role_key":
        frozen_plan["role_recipes"][0]["role_key"] = "forged_output_role"
    elif mutation == "output_index":
        frozen_plan["role_recipes"][0]["output_index"] = 2
    elif mutation == "policy":
        frozen_plan["policy"]["mode"] = "forged_execution_policy"
    else:
        frozen_plan["job_id"] = "job_forged_execution_plan"

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001
    handlers.service.job_store.save(record)
    view = handlers.get_project(project["project_id"])

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    assert view["metadata"]["current_operation"]["state"] != "delivery_route_unavailable"
    assert provider.calls == 1


@pytest.mark.parametrize(
    ("change", "expected_field"),
    [
        ("goal", "canonical_goal_prompt_digest"),
        ("reference", "per_output_reference_bindings_digest"),
        ("locked_visual", "locked_visual_asset_binding_digest"),
        ("provider_model_operation", "provider_route_identity"),
    ],
)
def test_doc271_changed_binding_dimension_does_not_reuse_closure(
    tmp_path,
    change: str,
    expected_field: str,
    monkeypatch,
) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    if change == "provider_model_operation":
        monkeypatch.setattr(settings, "default_image_provider", provider.provider_name)
        monkeypatch.setattr(settings, "default_image_model", "doc271-model-a")
        monkeypatch.setattr(settings, "openai_image_transport_profile", "openai-standard")
        assert _configured_route_identity() == provider.execution_identity(operation="image_edit")["route_identity"]
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    receipt = _closure(record)
    assert receipt[expected_field]
    immutable_receipt = deepcopy(receipt)

    next_payload = _payload(product_ids, key=f"doc271-changed-{change}")
    if change == "goal":
        next_payload["user_input"] = "Create a faithful product image with a different explicitly requested scene."
    elif change == "reference":
        projection = record.request.metadata["professional_ecommerce_physical_product_projections"]["1"]
        selected_id = projection["selected_product_asset_ids"][0]
        before_pool = [
            item["asset_ref_id"]
            for item in handlers.get_project(project["project_id"])["project"]["reference_assets"]
            if item["status"] == "active" and item["use_policy"] == "product"
        ]
        selected_reference = next(
            item
            for item in handlers.get_project(project["project_id"])["project"]["reference_assets"]
            if item["asset_ref_id"] == selected_id and item["status"] == "active"
        )
        replacement = _ready_product_upload(
            handlers,
            filename="doc271-replacement-product.png",
            color=(210, 120, 100),
        )
        handlers.post_project_reference_remove(
            project["project_id"],
            selected_reference["reference_id"],
            {"plain_text": "Use the newly added current product original."},
        )
        _add_product_references(handlers, project["project_id"], [replacement])
        after_pool = [
            item["asset_ref_id"]
            for item in handlers.get_project(project["project_id"])["project"]["reference_assets"]
            if item["status"] == "active" and item["use_policy"] == "product"
        ]
        assert selected_id in before_pool
        assert selected_id not in after_pool
        assert replacement in after_pool
        assert after_pool != before_pool
        next_payload["uploaded_asset_ids"] = [replacement]
    elif change == "locked_visual":
        bindings = handlers.get_project_visual_asset_bindings(project["project_id"])["bindings"]
        assert len(bindings) == 1
        handlers.delete_project_visual_asset_binding(
            project["project_id"],
            bindings[0]["binding_id"],
            {"confirm_removal": True},
        )
    else:
        monkeypatch.setattr(settings, "default_image_provider", "doc271-other-configured-provider")
        monkeypatch.setattr(settings, "default_image_model", "doc271-model-b")
        monkeypatch.setattr(settings, "openai_image_transport_profile", "hard-inputs-v2")
        assert _configured_route_identity() != receipt["provider_route_identity"]
        assert receipt["provider_route_identity"] != _configured_route_identity()

    next_job = handlers.post_project_job(project["project_id"], next_payload)
    assert next_job["job_id"] != record.job_id
    assert next_job["status"] == "planned"
    assert provider.calls == 1
    assert _closure(record) == immutable_receipt


def test_doc271_browser_policy_fields_cannot_author_or_override_a_closure(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    before = handlers.get_project(project["project_id"])["project"]["job_ids"]
    forged = _payload(product_ids, key="doc271-forged-browser-policy")
    forged["metadata"].update(
        {
            "provider_deliverability_closure_receipt": {
                "project_id": project["project_id"],
                "terminal_job_id": POLICY_JOB_ID,
                "policy_evidence_class": "explicit_content_policy_violation",
            },
            "provider_policy_blocked": True,
            "provider_failure_retry": {"final_failure_code": "provider_policy_blocked"},
        }
    )

    created = handlers.post_project_job(project["project_id"], forged)
    record = handlers.service.get_job_record(created["job_id"])

    assert record is not None
    assert created["status"] == "planned"
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == [*before, created["job_id"]]
    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    assert "provider_failure_retry" not in record.request.metadata
    assert provider.calls == 0


def test_doc271_malformed_persisted_closure_fails_open_without_repair(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata = {
        **dict(record.request.metadata),
        "provider_deliverability_closure_receipt": {
            "authority": "v3_provider_deliverability_closure",
            "project_id": project["project_id"],
            "terminal_job_id": created["job_id"],
            "terminal_job_receipt_digest": "malformed-not-a-canonical-digest",
        },
    }
    handlers.service.job_store.save(record)
    before_receipt = deepcopy(record.request.metadata["provider_deliverability_closure_receipt"])

    next_job = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-malformed-persisted-closure"),
    )
    reloaded = handlers.service.get_job_record(created["job_id"])

    assert next_job["status"] == "planned"
    assert next_job["job_id"] != created["job_id"]
    assert provider.calls == 1
    assert reloaded is not None
    assert reloaded.request.metadata["provider_deliverability_closure_receipt"] == before_receipt


@pytest.mark.parametrize("mutation", ["missing", "mismatched"])
def test_doc271_persisted_closure_timestamp_is_immutable_or_fails_open(
    tmp_path,
    mutation: str,
) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    corrupted = deepcopy(_closure(record))
    if mutation == "missing":
        corrupted.pop("created_at", None)
    else:
        corrupted["created_at"] = "2026-08-12T09:00:00+00:00"
    record.request.metadata = {
        **dict(record.request.metadata),
        "provider_deliverability_closure_receipt": corrupted,
    }
    handlers.service.job_store.save(record)

    next_job = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key=f"doc271-corrupt-created-at-{mutation}"),
    )
    reloaded = handlers.service.get_job_record(record.job_id)

    assert next_job["status"] == "planned"
    assert next_job["job_id"] != record.job_id
    assert provider.calls == 1
    assert reloaded is not None
    assert reloaded.request.metadata["provider_deliverability_closure_receipt"] == corrupted


def test_doc271_newer_planned_job_and_changed_source_do_not_project_old_closure(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    old_closure = deepcopy(_closure(record))
    projection = record.request.metadata["professional_ecommerce_physical_product_projections"]["1"]
    selected_id = projection["selected_product_asset_ids"][0]
    selected_reference = next(
        item
        for item in handlers.get_project(project["project_id"])["project"]["reference_assets"]
        if item["asset_ref_id"] == selected_id and item["status"] == "active"
    )
    replacement = _ready_product_upload(
        handlers,
        filename="doc271-current-operation-replacement.png",
        color=(220, 150, 90),
    )
    handlers.post_project_reference_remove(
        project["project_id"],
        selected_reference["reference_id"],
        {"plain_text": "Use the current product original."},
    )
    _add_product_references(handlers, project["project_id"], [replacement])
    planned = handlers.post_project_job(
        project["project_id"],
        _payload(
            [replacement],
            key="doc271-newer-planned-command",
            user_input="Create a faithful product image with a changed current direction.",
        ),
    )
    operation = handlers.get_project(project["project_id"])["metadata"].get("current_operation")

    assert planned["status"] == "planned"
    assert operation is None or operation["state"] in {"planning", "queued_or_generating"}
    assert operation is None or operation["state"] != "delivery_route_unavailable"
    assert _closure(record) == old_closure
    assert provider.calls == 1


def test_doc271_newer_real_job_suppresses_old_exact_closure_at_create_and_view(tmp_path, monkeypatch) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    original_gate = handlers.project_service._doc271_matching_provider_deliverability_closure  # noqa: SLF001
    # Seed a later ordinary command through the public API.  The temporary
    # seam models a pre-Doc271 command already persisted after the old closure;
    # the assertion below exercises the real gate after it is restored.
    monkeypatch.setattr(
        handlers.project_service,
        "_doc271_matching_provider_deliverability_closure",
        lambda *_args, **_kwargs: None,
    )
    newer = handlers.post_project_job(project["project_id"], _payload(product_ids, key="doc271-newer-planned-authority"))
    monkeypatch.setattr(
        handlers.project_service,
        "_doc271_matching_provider_deliverability_closure",
        original_gate,
    )
    repeated = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-after-newer-equivalent"),
    )
    operation = handlers.get_project(project["project_id"])["metadata"].get("current_operation")

    assert newer["status"] == "planned"
    assert repeated["status"] == "planned"
    assert repeated["job_id"] not in {record.job_id, ""}
    assert repeated.get("metadata", {}).get("current_operation", {}).get("state") != "delivery_route_unavailable"
    assert operation is None or operation["state"] in {"planning", "queued_or_generating"}
    assert provider.calls == 1


def test_doc271_project_goal_change_without_new_job_suppresses_old_closure_view(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    project_record = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    project_record.user_goal = "Create a different current product direction."
    project_record.short_summary = project_record.user_goal
    handlers.project_service.project_store.save_project(project_record)

    operation = handlers.get_project(project["project_id"])["metadata"].get("current_operation")

    assert operation is None or operation["state"] != "delivery_route_unavailable"
    assert provider.calls == 1


def test_doc271_changed_project_goal_cannot_reuse_old_command_direction_at_create(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    historical_direction = record.request.user_input
    project_record = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    project_record.user_goal = "Create a different server-owned product delivery direction."
    project_record.short_summary = project_record.user_goal
    handlers.project_service.project_store.save_project(project_record)

    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-old-direction-after-goal-change", user_input=historical_direction),
    )

    assert created["status"] == "planned"
    assert created["job_id"] != record.job_id
    assert created.get("metadata", {}).get("current_operation", {}).get("state") != "delivery_route_unavailable"
    assert provider.calls == 1


def test_doc271_existing_malformed_receipt_is_never_overwritten_at_terminal_persistence(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    malformed = {"schema_version": "malformed", "created_at": "not-a-receipt"}
    record.request.metadata = {
        **dict(record.request.metadata),
        "provider_deliverability_closure_receipt": malformed,
    }

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001

    assert record.request.metadata["provider_deliverability_closure_receipt"] == malformed


def test_doc271_self_consistent_forged_command_binding_cannot_create_or_project_closure(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    forged = deepcopy(record.request.metadata["doc271_command_binding"])
    forged["command_direction"] = "Forged internal direction that was never issued by Project Mode."
    forged["command_binding_digest"] = hashlib.sha256(
        json.dumps(
            {
                "template_id": forged["template_id"],
                "project_id": forged["project_id"],
                "command_attempt_id": forged["command_attempt_id"],
                "goal_snapshot_id": forged["goal_snapshot_id"],
                "goal_snapshot_digest": forged["goal_snapshot_digest"],
                "command_direction": forged["command_direction"],
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    record.request.metadata["doc271_command_binding"] = forged

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001
    status = handlers.service.get_job(record.job_id).model_dump(mode="json")
    project_view = handlers.get_project(project["project_id"])

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    assert project_view["metadata"]["current_operation"]["state"] == "failed_no_delivery"
    assert "doc271_command_binding" not in json.dumps(status, sort_keys=True)
    assert "goal_snapshot_id" not in json.dumps(status, sort_keys=True)
    assert provider.calls == 1


def test_doc271_command_binding_cannot_replay_a_different_server_goal_snapshot(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    project_record = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    other_snapshot = handlers.project_service._issue_doc271_project_goal_snapshot(  # noqa: SLF001
        project_record,
        template_id="ecommerce_template",
    )
    forged = deepcopy(record.request.metadata["doc271_command_binding"])
    forged["goal_snapshot_id"] = other_snapshot["snapshot_id"]
    forged["goal_snapshot_digest"] = other_snapshot["snapshot_digest"]
    forged["command_binding_digest"] = hashlib.sha256(
        json.dumps(
            {
                "template_id": forged["template_id"],
                "project_id": forged["project_id"],
                "command_attempt_id": forged["command_attempt_id"],
                "goal_snapshot_id": forged["goal_snapshot_id"],
                "goal_snapshot_digest": forged["goal_snapshot_digest"],
                "command_direction": forged["command_direction"],
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    record.request.metadata["doc271_command_binding"] = forged

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    assert provider.calls == 1


def test_doc271_abandoned_attempt_snapshot_does_not_block_changed_goal_retry(tmp_path, monkeypatch) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    original_create = handlers.service.create_project_ecommerce_job

    def fail_before_project_link(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("deterministic create failure before project link")

    monkeypatch.setattr(handlers.service, "create_project_ecommerce_job", fail_before_project_link)
    with pytest.raises(RuntimeError, match="before project link"):
        handlers.post_project_job(
            project["project_id"],
            _payload(product_ids, key="doc271-abandoned-attempt"),
        )
    project_record = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    abandoned = deepcopy(project_record.metadata["doc271_project_goal_snapshots"])
    assert len(abandoned) == 1
    assert project_record.metadata.get("doc271_command_attempt_job_associations") in (None, {})
    assert project_record.job_ids == []

    project_record.user_goal = "Create a changed project goal after the abandoned command."
    project_record.short_summary = project_record.user_goal
    handlers.project_service.project_store.save_project(project_record)
    monkeypatch.setattr(handlers.service, "create_project_ecommerce_job", original_create)
    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-after-abandoned-attempt"),
    )
    record = handlers.service.get_job_record(created["job_id"])
    refreshed = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001

    assert created["status"] == "planned"
    assert record is not None
    assert len(refreshed.metadata["doc271_project_goal_snapshots"]) == 2
    assert abandoned.items() <= refreshed.metadata["doc271_project_goal_snapshots"].items()
    current_attempt = record.request.metadata["doc271_command_binding"]["command_attempt_id"]
    assert current_attempt not in {
        snapshot["command_attempt_id"] for snapshot in abandoned.values()
    }
    association = refreshed.metadata["doc271_command_attempt_job_associations"][current_attempt]
    assert association["job_id"] == created["job_id"]
    assert provider.calls == 0


def test_doc271_policy_failure_after_persisted_pixel_cannot_create_closure(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    handlers.service.output_store.save_base64_output(
        job_id=created["job_id"],
        candidate_id="doc271-already-delivered-candidate",
        asset_id="doc271-already-delivered-asset",
        provider="doc271-local-provider",
        model="doc271-model-a",
        encoded_image=_png_base64((40, 80, 120)),
    )

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001

    assert "provider_deliverability_closure_receipt" not in record.request.metadata


def test_doc271_planned_generation_assets_without_output_pixels_can_create_closure(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    assert record.planning_result is not None
    assert record.planning_result.asset_pack.assets
    record.generation_result = record.planning_result

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001

    assert "provider_deliverability_closure_receipt" in record.request.metadata
    assert provider.calls == 1


def test_doc271_corrupt_terminal_receipt_source_fails_open_without_historical_replay(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata["provider_failure_retry"]["terminal_receipt_source"] = "forged.client.source"
    handlers.service.job_store.save(record)

    assert verified_provider_deliverability_closure_receipt(
        record,
        uploaded_asset_lookup=handlers.service.get_uploaded_asset,
        generated_output_lookup=handlers.service.output_store.get_output,
        source_job_lookup=handlers.service.get_job_record,
        project_goal_snapshot_lookup=handlers.project_service._doc271_project_goal_snapshot,  # noqa: SLF001
        command_attempt_association_lookup=handlers.project_service._doc271_command_attempt_association,  # noqa: SLF001
    ) is None
    view = handlers.get_project(project["project_id"])
    assert view["metadata"]["current_operation"]["state"] != "delivery_route_unavailable"

    repeated = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc271-corrupt-terminal-source-repeat"),
    )
    assert repeated["status"] == "planned"
    assert repeated["job_id"] != record.job_id
    assert provider.calls == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("final_status", "completed"),
        ("final_classification", "retryable_provider_failure"),
    ],
)
def test_doc271_corrupt_terminal_summary_fails_open_without_historical_replay(
    tmp_path,
    field: str,
    value: str,
) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata["provider_failure_retry"][field] = value
    handlers.service.job_store.save(record)

    assert verified_provider_deliverability_closure_receipt(
        record,
        uploaded_asset_lookup=handlers.service.get_uploaded_asset,
        generated_output_lookup=handlers.service.output_store.get_output,
        source_job_lookup=handlers.service.get_job_record,
        project_goal_snapshot_lookup=handlers.project_service._doc271_project_goal_snapshot,  # noqa: SLF001
        command_attempt_association_lookup=handlers.project_service._doc271_command_attempt_association,  # noqa: SLF001
    ) is None
    view = handlers.get_project(project["project_id"])
    assert view["metadata"]["current_operation"]["state"] != "delivery_route_unavailable"

    repeated = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key=f"doc271-corrupt-{field}-repeat"),
    )
    assert repeated["status"] == "planned"
    assert repeated["job_id"] != record.job_id
    assert provider.calls == 1


def test_doc271_forged_internal_source_marker_cannot_create_or_project_closure(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    forged = deepcopy(record.request.metadata["doc271_current_source_binding"])
    forged["sources"][0]["persisted_role"] = "forged_product_role"
    payload = {
        "schema_version": forged["schema_version"],
        "project_id": forged["project_id"],
        "sources": forged["sources"],
    }
    forged["source_binding_digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    record.request.metadata["doc271_current_source_binding"] = forged

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    assert handlers.get_project(project["project_id"])["metadata"]["current_operation"]["state"] != "delivery_route_unavailable"


def test_doc271_forged_generated_selected_source_cannot_self_authenticate(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    forged = deepcopy(record.request.metadata["doc271_current_source_binding"])
    forged["sources"].append(
        {
            "ordinal": len(forged["sources"]) + 1,
            "asset_id": "v3_output_forged_doc271",
            "content_sha256": "1" * 64,
            "source_type": "generated_selected",
            "use_policy": "style",
            "persisted_role": "generated_output",
            "reference_channel": "generated_selected",
            "continuation_role": "selected_continuation_reference",
            "continuation_channel": "generated_selected",
        }
    )
    payload = {
        "schema_version": forged["schema_version"],
        "project_id": forged["project_id"],
        "sources": forged["sources"],
    }
    forged["source_binding_digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    record.request.metadata["doc271_current_source_binding"] = forged

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    assert provider.calls == 1


def test_doc271_multi_output_plan_cannot_close_from_only_its_first_plan(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    plans = record.request.metadata["physical_renderer_reference_plans"]
    projections = record.request.metadata["professional_ecommerce_physical_product_projections"]
    plans["2"] = deepcopy(plans["1"])
    projections["2"] = deepcopy(projections["1"])

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    assert provider.calls == 1


@pytest.mark.parametrize("marker_field", ["persisted_role", "reference_channel"])
def test_doc271_unselected_uploaded_marker_must_match_durable_role_and_channel(
    tmp_path,
    marker_field: str,
) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    record.request.metadata.pop("provider_deliverability_closure_receipt", None)
    selected_id = record.request.metadata["professional_ecommerce_physical_product_projections"]["1"]["selected_product_asset_ids"][0]
    forged = deepcopy(record.request.metadata["doc271_current_source_binding"])
    source = next(item for item in forged["sources"] if item["asset_id"] != selected_id)
    source[marker_field] = "subject_reference" if marker_field == "persisted_role" else "uploaded_reference"
    payload = {
        "schema_version": forged["schema_version"],
        "project_id": forged["project_id"],
        "sources": forged["sources"],
    }
    forged["source_binding_digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    record.request.metadata["doc271_current_source_binding"] = forged

    handlers.service._persist_doc271_provider_deliverability_closure(record)  # noqa: SLF001

    assert "provider_deliverability_closure_receipt" not in record.request.metadata
    assert provider.calls == 1


def test_doc271_unselected_active_product_role_or_channel_drift_fails_open(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    old_closure = deepcopy(_closure(record))
    selected_id = record.request.metadata["professional_ecommerce_physical_product_projections"]["1"][
        "selected_product_asset_ids"
    ][0]
    drift_id = next(asset_id for asset_id in product_ids if asset_id != selected_id)
    project_record = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    upload = handlers.service.get_uploaded_asset(drift_id)
    assert upload is not None and upload.role == "product_reference"
    handlers.service.asset_store._save_record(  # noqa: SLF001
        upload.model_copy(update={"role": "subject_reference"})
    )
    role_drift_binding = handlers.project_service._doc271_current_source_binding(  # noqa: SLF001
        project_record,
        selected_continuation_admissions=handlers.project_service._doc269_selected_continuation_admissions(project_record),  # noqa: SLF001
    )
    assert role_drift_binding["source_binding_digest"] != old_closure["current_project_source_binding_digest"]
    assert handlers.project_service._doc271_current_binding_matches(  # noqa: SLF001
        project_record,
        receipt=old_closure,
        user_input=_payload(product_ids, key="doc271-unselected-role-drift")["user_input"],
        selected_continuation_admissions=handlers.project_service._doc269_selected_continuation_admissions(project_record),  # noqa: SLF001
        current_source_binding=role_drift_binding,
    ) is False
    handlers.service.asset_store._save_record(upload)
    drift_reference = next(
        item
        for item in project_record.reference_assets
        if item.asset_ref_id == drift_id and item.status.value == "active"
    )
    # This is an authoritative persisted channel drift on an unselected
    # original. The original remains active project evidence, but no longer
    # belongs to the current product-truth pool.
    drift_reference.use_policy = ProjectReferenceUsePolicy.PRODUCT_IDENTITY
    handlers.project_service.project_store.save_project(project_record)
    current_binding = handlers.project_service._doc271_current_source_binding(  # noqa: SLF001
        project_record,
        selected_continuation_admissions=handlers.project_service._doc269_selected_continuation_admissions(project_record),  # noqa: SLF001
    )
    assert current_binding["source_binding_digest"] != old_closure["current_project_source_binding_digest"]
    assert handlers.project_service._doc271_current_binding_matches(  # noqa: SLF001
        project_record,
        receipt=old_closure,
        user_input=_payload(product_ids, key="doc271-unselected-role-drift")["user_input"],
        selected_continuation_admissions=handlers.project_service._doc269_selected_continuation_admissions(project_record),  # noqa: SLF001
        current_source_binding=current_binding,
    ) is False

    next_job = handlers.post_project_job(
        project["project_id"],
        _payload([], key="doc271-unselected-role-drift"),
    )

    assert next_job["status"] == "planned"
    assert next_job["job_id"] != record.job_id
    assert provider.calls == 1
    assert _closure(record) == old_closure


@pytest.mark.parametrize("failure_code", ["image_edit_invalid_request_unattributed", "provider_timeout"])
def test_doc271_non_explicit_policy_failures_do_not_create_a_closure_at_initial_persistence(
    tmp_path,
    failure_code: str,
) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _seed_pre_doc271_terminal_record(
        handlers,
        project,
        product_ids,
        failure_code=failure_code,
        upstream_code="invalid_request_error" if failure_code.startswith("image_edit") else "timeout",
    )
    before_metadata = deepcopy(record.request.metadata)

    handlers.get_project(project["project_id"])
    loaded = handlers.service.get_job_record(record.job_id)

    assert loaded is not None
    assert "provider_deliverability_closure_receipt" not in loaded.request.metadata
    assert loaded.request.metadata == before_metadata
    assert provider.calls == 0


def test_doc271_legacy_verifiable_policy_record_is_recognized_read_only_without_replay(tmp_path) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _seed_pre_doc271_terminal_record(handlers, project, product_ids)
    before_metadata = deepcopy(record.request.metadata)
    before_warnings = list(record.warnings)

    project_view = handlers.get_project(project["project_id"])
    operation = project_view["metadata"]["current_operation"]
    reloaded = handlers.service.get_job_record(record.job_id)

    assert operation["state"] == "delivery_route_unavailable"
    assert operation["closure_receipt_id"]
    assert "closure_receipt_job_id" not in operation
    assert "terminal_job_id" not in operation
    assert record.job_id not in str(operation)
    assert provider.calls == 0
    assert reloaded is not None
    assert reloaded.request.metadata == before_metadata
    assert reloaded.warnings == before_warnings


@pytest.mark.parametrize(
    "missing",
    [
        "canonical_goal",
        "source_sha_role_channel_order",
        "locked_binding",
        "provider_route",
        "final_physical_plan",
        "terminal_project_linkage",
        "terminal_job_receipt",
        "terminal_job_receipt_digest_mismatch",
        "terminal_created_at",
    ],
)
def test_doc271_incomplete_legacy_policy_evidence_cannot_create_or_project_a_closure(tmp_path, missing: str) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _seed_pre_doc271_terminal_record(
        handlers,
        project,
        product_ids,
        missing=missing,
    )
    before_metadata = deepcopy(record.request.metadata)

    view = handlers.get_project(project["project_id"])
    loaded = handlers.service.get_job_record(record.job_id)

    assert view["metadata"]["current_operation"]["state"] == "failed_no_delivery"
    assert loaded is not None
    assert "provider_deliverability_closure_receipt" not in loaded.request.metadata
    assert loaded.request.metadata == before_metadata
    assert provider.calls == 0


def _closure_project() -> dict[str, Any]:
    return {
        "project_id": PROJECT_ID,
        "user_goal": "Create the existing requested image without changing hard facts.",
        "short_summary": "Create the existing requested image without changing hard facts.",
        "primary_template_id": "ecommerce_template",
        "job_ids": [],
        "reference_assets": [],
        "metadata": {
            "current_operation": {
                "state": "delivery_route_unavailable",
                "terminal": True,
                "pending": False,
                "closure_receipt_id": "doc271-closure-receipt",
                "next_actions": [{"id": "review_delivery_options"}],
            },
            "ecommerce_project_view": {
                "schema_version": "doc263_ecommerce_project_view_v1",
                "groups": {
                    "original_product_inputs": {"items": []},
                    "locked_person_identity": {"items": []},
                    "selected_continuation_directions": {"items": []},
                    "generated_and_review_history": {"delivered_outputs": [], "review_withheld_outputs": [], "failed_attempts": []},
                },
            },
        },
    }


def _install_closure_transport(page, project: dict) -> None:  # noqa: ANN001
    page.evaluate(
        """
        (project) => {
          window.__doc271Requests = [];
          window.fetch = async (input, init = {}) => {
            const url = String(input);
            const method = String(init.method || 'GET').toUpperCase();
            window.__doc271Requests.push({ url, method });
            return new Response(JSON.stringify({ project }), { status: 200, headers: { 'Content-Type': 'application/json' } });
          };
        }
        """,
        project,
    )


@pytest.mark.parametrize(("html", "script", "setup"), [
    (DESKTOP_HTML, DESKTOP_JS, """
      v3State.currentProject = project;
      v3State.currentJob = { job_id: 'job-659-policy-closure', status: 'blocked', warnings: ['content_policy_violation /secret/path sha256:bad'], metadata: { project_id: project.project_id } };
      v3State.ecommerceSubmissionReceipt = null;
      v3State.selectedScenario = 'ecommerce';
      v3State.templateCatalogStatus = 'ready';
      v3State.templates = [{ template_id: 'ecommerce_template', project_can_create_jobs: true }];
      setV3Busy(true); setV3Progress('planning', '正在准备生成');
      renderV3ScenarioState(); renderV3Job(v3State.currentJob);
    """),
    (MOBILE_HTML, MOBILE_JS, """
      ensureMobileLayers(); setupMobileV3Adapter();
      mobileV3State.currentProject = project;
      mobileV3State.currentJob = { job_id: 'job-659-policy-closure', status: 'blocked', warnings: ['content_policy_violation /secret/path sha256:bad'], metadata: { project_id: project.project_id } };
      mobileV3State.ecommerceSubmissionReceipt = null;
      mobileV3State.selectedTemplate = 'ecommerce_template';
      setMobileV3Busy(true); setMobileV3Progress('planning', '正在准备生成');
      renderMobileV3ProjectCurrentOperation(project);
    """),
])
def test_doc271_browser_closure_is_terminal_safe_and_never_auto_posts(html, script, setup) -> None:
    project = _closure_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html, script_path=script)
            _install_closure_transport(page, project)
            page.evaluate("(args) => { const { project, setup } = args; eval(setup); }", {"project": project, "setup": setup})
            public_text = page.locator("body").inner_text()
            assert "content_policy_violation" not in public_text
            assert "/secret/path" not in public_text
            assert "sha256:bad" not in public_text
            assert POLICY_JOB_ID not in public_text
            assert "正在准备生成" not in public_text
            assert "生成中" not in public_text
            if html == DESKTOP_HTML:
                assert page.evaluate("v3State.loading === false && v3State.progressStageKey === 'failed' && v3State.progressTimer === null && v3State.recoverPollTimer === null") is True
                assert page.evaluate("document.querySelector('#v3ProjectNextActions').hidden === false") is True
            else:
                assert page.evaluate("mobileV3State.busy === false") is True
                assert page.locator("#mobileV3ProgressElapsed").inner_text() == "已结束"
            action = page.locator("[data-v3-project-action='review_delivery_options'], [data-mobile-v3-project-action='review_delivery_options']")
            assert action.count() == 1
            action.click()
            assert page.evaluate("window.__doc271Requests.filter((item) => item.method === 'POST').length") == 0
            if html == DESKTOP_HTML:
                assert page.evaluate("v3State.loading === false && v3State.progressStageKey === 'failed' && v3State.progressTimer === null && v3State.recoverPollTimer === null") is True
                assert page.evaluate("document.body.dataset.v3DeliveryOptionsSurface === 'open'") is True
            else:
                assert page.evaluate("mobileV3State.busy === false") is True
                assert page.locator("#mobileV3ProgressElapsed").inner_text() == "已结束"
                assert page.evaluate("document.body.dataset.mobileV3DeliveryOptionsSurface === 'open'") is True
            assert page.evaluate("window.__doc271Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()


def test_doc271_general_and_photography_do_not_receive_ecommerce_closure_behavior(tmp_path) -> None:
    handlers, _provider, _project_record, _product_ids, _face_output_ids = _fixture(tmp_path)
    for template_id in ("general_template", "photographer_template"):
        project = ProjectRecord.model_validate(
            {
                "project_id": f"doc271-{template_id}",
                "title": "Isolation fixture",
                "primary_template_id": template_id,
                "allowed_template_ids": [template_id],
                "user_goal": "Keep this template unchanged.",
                "short_summary": "Keep this template unchanged.",
                "created_at": "2026-08-12T00:00:00+00:00",
                "updated_at": "2026-08-12T00:00:00+00:00",
                "metadata": {
                    "provider_deliverability_closure_receipt": {
                        "policy_evidence_class": "explicit_content_policy_violation",
                    }
                },
            }
        )
        assert handlers.project_service._ecommerce_current_operation(project) is None  # noqa: SLF001
