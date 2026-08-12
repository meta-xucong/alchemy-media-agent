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
from alchemy_creative_agent_3_0.app.generation_router.providers import GenerationProvider
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
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
    "schema_version": "doc271_provider_execution_audit_v1",
    "authority": "v3_provider_execution_audit",
    "provider_capability_id": "doc271-capability-image-edit-hard-inputs-v1",
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
                    "status": "failed",
                    "classification": "non_retryable_provider_failure",
                    "failure_code": self.failure_code,
                    "retryable": False,
                    "upstream_code": self.upstream_code,
                }
            ],
            "reference_input_execution": {
                "operation": "image_edit",
                "reference_count": 4,
                "failure_code": self.failure_code,
            },
            "execution_audit": dict(EXECUTION_AUDIT),
            "terminal_receipt_source": "provider_failure_retry.execution_audit",
        }
        raise error


def _fixture(tmp_path, *, provider: GenerationProvider | None = None):
    handlers, catalog = _handlers(tmp_path)
    provider = provider or _TerminalFailureProvider()
    handlers.service.scenario_runtime.generation_router = GenerationRouter(provider=provider)
    project = _project(handlers)
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


def _terminal_job_receipt(record) -> dict[str, str]:
    failure = record.request.metadata["provider_failure_retry"]
    payload = {
        "schema_version": "doc271_terminal_job_receipt_v1",
        "project_id": str(record.request.metadata["project_id"]),
        "terminal_job_id": record.job_id,
        "terminal_status": record.status.value,
        "provider_failure_code": str(failure["final_failure_code"]),
        "provider_failure_classification": str(failure["final_classification"]),
        "policy_evidence_code": str(failure["attempts"][0]["upstream_code"]),
        "execution_audit": dict(failure["execution_audit"]),
        "terminal_receipt_source": str(failure["terminal_receipt_source"]),
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
                    "status": "failed",
                    "classification": "non_retryable_provider_failure",
                    "failure_code": failure_code,
                    "retryable": False,
                    "upstream_code": upstream_code,
                }
            ],
            "reference_input_execution": {
                "operation": "image_edit",
                "reference_count": 4,
                "failure_code": failure_code,
            },
            "doc271_legacy_provider_execution": {
                "provider_capability_id": "legacy-capability-image-edit-hard-inputs-v1",
                "provider_name": "legacy-image-provider",
                "model": "legacy-image-model",
                "operation": "image_edit",
                "route_identity": "legacy-configured-image-edit-route",
            },
            "execution_audit": {
                "schema_version": "doc271_provider_execution_audit_v1",
                "authority": "v3_provider_execution_audit",
                "provider_capability_id": "legacy-capability-image-edit-hard-inputs-v1",
                "provider_name": "legacy-image-provider",
                "model": "legacy-image-model",
                "operation": "image_edit",
                "route_identity": "legacy-configured-image-edit-route",
            },
            "terminal_receipt_source": "provider_failure_retry.execution_audit",
        },
    }
    record.request.metadata["doc271_terminal_job_receipt"] = _terminal_job_receipt(record)
    if missing == "canonical_goal":
        record.request = record.request.model_copy(update={"user_input": ""})
    elif missing == "source_sha_role_channel_order":
        record.request.metadata["physical_renderer_reference_plans"]["1"]["references"][0].pop("content_sha256")
    elif missing == "locked_binding":
        record.request.metadata.pop("frozen_visual_asset_binding_set", None)
    elif missing == "provider_route":
        record.request.metadata["provider_failure_retry"].pop("doc271_legacy_provider_execution", None)
    elif missing == "final_physical_plan":
        record.request.metadata.pop("physical_renderer_reference_plans", None)
    elif missing == "terminal_project_linkage":
        record.request.metadata.pop("project_id", None)
    elif missing == "terminal_job_receipt":
        record.request.metadata.pop("doc271_terminal_job_receipt", None)
    elif missing == "terminal_job_receipt_digest_mismatch":
        record.request.metadata["doc271_terminal_job_receipt"]["receipt_digest"] = "0" * 64
    record.warnings = ["V3 real image generation failed (provider_policy_blocked)."]
    record.lifecycle = handlers.service._build_lifecycle(record)  # noqa: SLF001
    handlers.service.job_store.save(record)
    return created, record


def test_doc271_explicit_policy_failure_writes_one_exact_server_owned_closure(tmp_path) -> None:
    handlers, provider, project, product_ids, face_output_ids = _fixture(tmp_path)
    created, record = _create_policy_block(handlers, provider, project, product_ids)

    receipt = _closure(record)
    assert receipt["authority"] == "v3_provider_deliverability_closure"
    assert receipt["project_id"] == project["project_id"]
    assert receipt["terminal_job_id"] == created["job_id"]
    assert receipt["terminal_job_receipt_digest"] == _terminal_job_receipt(record)["receipt_digest"]
    assert receipt["terminal_job_receipt_source"] == "provider_failure_retry.execution_audit"
    assert receipt["policy_evidence_class"] == "explicit_content_policy_violation"
    assert receipt["provider_capability_id"] == EXECUTION_AUDIT["provider_capability_id"]
    assert receipt["provider_name"] == EXECUTION_AUDIT["provider_name"]
    assert receipt["provider_model"] == EXECUTION_AUDIT["model"]
    assert receipt["provider_operation"] == EXECUTION_AUDIT["operation"]
    assert receipt["provider_route_identity"] == EXECUTION_AUDIT["route_identity"]
    assert receipt["reference_binding"]["ordered_reference_channels"] == [
        "product_truth",
        "people_identity",
        "people_identity",
        "people_identity",
    ]
    projection = record.request.metadata["professional_ecommerce_physical_product_projections"]["1"]
    assert receipt["reference_binding"]["ordered_reference_ids"] == [
        projection["selected_product_asset_ids"][0],
        *face_output_ids,
    ]
    assert receipt["reference_binding"]["locked_face_output_ids"] == face_output_ids
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
    ):
        assert private_value not in public_text
    for private_field in (
        "provider_deliverability_closure_receipt",
        "terminal_job_id",
        "terminal_job_receipt_digest",
        "terminal_job_receipt_source",
        "provider_capability_id",
        "provider_name",
        "provider_model",
        "provider_operation",
        "provider_route_identity",
        "canonical_goal_prompt_digest",
        "reference_binding",
        "physical_plan_digest",
    ):
        assert private_field not in public_text
    assert created["job_id"] not in str(public_operation)


def test_doc271_same_exact_closed_binding_stops_before_new_job_brain_or_provider(tmp_path, monkeypatch) -> None:
    handlers, provider, project, product_ids, _face_output_ids = _fixture(tmp_path)
    _created, record = _create_policy_block(handlers, provider, project, product_ids)
    _closure(record)
    before_job_ids = list(handlers.get_project(project["project_id"])["project"]["job_ids"])
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
    assert planning_calls == []
    assert provider.calls == 1


@pytest.mark.parametrize(
    ("change", "expected_field"),
    [
        ("goal", "canonical_goal_prompt_digest"),
        ("reference", "reference_binding_digest"),
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
        assert _configured_route_identity() == EXECUTION_AUDIT["route_identity"]
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
        assert receipt["provider_route_identity"] == EXECUTION_AUDIT["route_identity"]

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
