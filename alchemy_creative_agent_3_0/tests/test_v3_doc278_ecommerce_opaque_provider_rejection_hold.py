"""Phase 0 red contracts for Doc278 opaque E-Commerce provider rejection holds.

All fixtures use local in-memory Project Mode/Product API stores and a
deterministic no-pixel provider. No external Provider, MCP, ImageGen, or VPS
action is possible from this module.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

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
    _png_base64,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc271_provider_deliverability_closure import (
    _TerminalFailureProvider,
    _create_policy_block,
    _fixture,
    _payload,
)
from app.providers.base import ProviderRuntimeError


RAW_OPAQUE_ERROR = "provider_error image_edit invalid /private/route sha256:opaque"


class _OpaqueImageEditFailureProvider(_TerminalFailureProvider):
    """One local opaque no-pixel image-edit failure, never a policy claim."""

    def __init__(self) -> None:
        super().__init__(
            failure_code="image_edit_invalid_request_unattributed",
            upstream_code="provider_error",
        )

    def generate(self, request):  # noqa: ANN001, ANN201
        self.calls += 1
        error = ProviderRuntimeError(
            RAW_OPAQUE_ERROR,
            provider=self.provider_name,
            detail={"code": "provider_error", "operation": "image_edit"},
        )
        error.provider_failure_retry = {
            "executed_count": 0,
            "max_attempts": 1,
            "fresh_upstream_requests": 1,
            "final_status": "failed",
            "final_classification": "non_retryable_provider_failure",
            "final_failure_code": "image_edit_invalid_request_unattributed",
            "attempts": [{
                "attempt": 1,
                "output_index": 1,
                "role_output_index": 1,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "image_edit_invalid_request_unattributed",
                "retryable": False,
                "upstream_code": "provider_error",
                "execution_audit": self.execution_identity(operation="image_edit"),
            }],
            "reference_input_execution": {
                "operation": "image_edit",
                "reference_count": 4,
                "failure_code": "image_edit_invalid_request_unattributed",
            },
            "execution_audit": self.execution_identity(operation="image_edit"),
            "terminal_receipt_source": "provider_failure_retry.execution_audit",
        }
        raise error


def _opaque_fixture(tmp_path):
    provider = _OpaqueImageEditFailureProvider()
    return (*_fixture(tmp_path, provider=provider), provider)


def _create_opaque_block(handlers, provider, project, product_ids):
    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc278-first-opaque-command"),
    )
    terminal = handlers.post_project_job_generate(project["project_id"], created["job_id"])
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert terminal["status"] == ProductJobStatusValue.BLOCKED.value
    assert provider.calls == 1
    assert record.request.metadata["provider_failure_retry"]["final_failure_code"] == "image_edit_invalid_request_unattributed"
    assert record.request.metadata["provider_failure_retry"]["attempts"][0]["upstream_code"] == "provider_error"
    assert handlers.service.output_store.list_by_job(created["job_id"]) == []
    return created, record


def test_doc278_opaque_failure_is_not_reclassified_as_doc271_policy(tmp_path) -> None:
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _created, record = _create_opaque_block(handlers, provider, project, product_ids)

    metadata = record.request.metadata
    assert "provider_deliverability_closure_receipt" not in metadata
    assert metadata["provider_failure_retry"]["final_failure_code"] != "provider_policy_blocked"
    assert metadata["provider_failure_retry"]["attempts"][0]["upstream_code"] != "content_policy_violation"


def test_doc278_exact_opaque_repeat_stops_before_job_brain_or_provider(tmp_path, monkeypatch) -> None:
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _created, record = _create_opaque_block(handlers, provider, project, product_ids)
    before_jobs = list(handlers.get_project(project["project_id"])["project"]["job_ids"])
    before_metadata = deepcopy(record.request.metadata)
    planning_calls: list[object] = []

    def unexpected_plan(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        planning_calls.append((args, kwargs))
        raise AssertionError("Doc278 exact opaque hold reached Brain planning")

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", unexpected_plan)
    held = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc278-repeat-opaque-command"),
    )

    assert held["status"] == ProductJobStatusValue.BLOCKED.value
    assert not held.get("job_id")
    assert held["metadata"]["current_operation"] == {
        "state": "ambiguous_provider_request_hold",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_conditions"}],
    }
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == before_jobs
    assert record.request.metadata == before_metadata
    assert planning_calls == []
    assert provider.calls == 1
    public_text = str({"held": held, "project": handlers.get_project(project["project_id"])})
    for private in (RAW_OPAQUE_ERROR, record.job_id, "provider_error", "sha256:opaque"):
        assert private not in public_text


def test_doc278_relevant_goal_change_allows_one_new_command(tmp_path) -> None:
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _create_opaque_block(handlers, provider, project, product_ids)
    project_record = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    project_record.user_goal = "A materially changed server-owned product direction."
    project_record.short_summary = project_record.user_goal
    handlers.project_service.project_store.save_project(project_record)

    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc278-goal-change", user_input=project_record.user_goal),
    )

    assert created.get("job_id")
    assert created["metadata"].get("current_operation", {}).get("state") != "ambiguous_provider_request_hold"


def test_doc278_browser_forged_hold_fields_cannot_author_or_change_exact_hold(tmp_path, monkeypatch) -> None:
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _created, record = _create_opaque_block(handlers, provider, project, product_ids)
    before_metadata = deepcopy(record.request.metadata)

    def unexpected_plan(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("browser metadata reached Doc278 planning")

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", unexpected_plan)
    payload = _payload(product_ids, key="doc278-browser-forged-repeat")
    payload["metadata"].update({
        "ambiguous_provider_request_hold_receipt": {"authority": "browser", "selected_asset_ids": ["forged"]},
        "provider_failure_retry": {"final_failure_code": "provider_policy_blocked"},
        "selected_product_asset_ids": ["forged"],
    })
    held = handlers.post_project_job(project["project_id"], payload)

    assert held["metadata"]["current_operation"]["state"] == "ambiguous_provider_request_hold"
    assert not held.get("job_id")
    assert record.request.metadata == before_metadata
    assert provider.calls == 1


def test_doc278_complete_historical_opaque_failure_projects_read_only_hold(tmp_path) -> None:
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    created, record = _create_opaque_block(handlers, provider, project, product_ids)
    before_metadata = deepcopy(record.request.metadata)
    before_jobs = list(handlers.get_project(project["project_id"])["project"]["job_ids"])

    view = handlers.get_project(project["project_id"])

    operation = view["metadata"]["current_operation"]
    assert operation == {
        "state": "ambiguous_provider_request_hold",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_conditions"}],
    }
    loaded = handlers.service.get_job_record(created["job_id"])
    assert loaded is not None and loaded.request.metadata == before_metadata
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == before_jobs
    assert provider.calls == 1


def test_doc278_doc271_policy_closure_has_precedence(tmp_path) -> None:
    handlers, provider, project, product_ids, _faces = _fixture(tmp_path)
    _created, _record = _create_policy_block(handlers, provider, project, product_ids)

    closed = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc278-policy-precedence"),
    )

    assert closed["metadata"]["current_operation"]["state"] == "delivery_route_unavailable"


def test_doc278_partial_pixels_and_incomplete_legacy_evidence_fail_open(tmp_path) -> None:
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    created, record = _create_opaque_block(handlers, provider, project, product_ids)
    handlers.service.output_store.save_base64_output(
        job_id=created["job_id"],
        candidate_id="doc278-partial-candidate",
        asset_id="doc278-partial-asset",
        provider="fixture",
        model="fixture",
        encoded_image=_png_base64((90, 130, 170)),
        output_id="v3_output_27800000000000000001",
    )
    record.request.metadata["provider_failure_retry"].pop("execution_audit")

    created_again = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="doc278-partial-fails-open"),
    )
    assert created_again.get("job_id")
    assert created_again["metadata"].get("current_operation", {}).get("state") != "ambiguous_provider_request_hold"


@pytest.mark.parametrize(("html", "script", "setup"), [
    (DESKTOP_HTML, DESKTOP_JS, """
      v3State.currentProject = project; v3State.currentJob = { job_id: 'old-job', status: 'blocked', warnings: ['provider_error /private/route sha256:opaque'] };
      v3State.selectedScenario = 'ecommerce'; setV3Busy(true); setV3Progress('planning', 'Preparing'); renderV3Job(v3State.currentJob);
    """),
    (MOBILE_HTML, MOBILE_JS, """
      ensureMobileLayers(); setupMobileV3Adapter(); mobileV3State.currentProject = project; mobileV3State.currentJob = { job_id: 'old-job', status: 'blocked', warnings: ['provider_error /private/route sha256:opaque'] };
      mobileV3State.selectedTemplate = 'ecommerce_template'; setMobileV3Busy(true); setMobileV3Progress('planning', 'Preparing'); renderMobileV3ProjectCurrentOperation(project);
    """),
])
def test_doc278_browser_hold_is_terminal_safe_and_review_action_never_posts(html, script, setup) -> None:
    project = {
        "project_id": "doc278-project",
        "primary_template_id": "ecommerce_template",
        "job_ids": [],
        "metadata": {"current_operation": {
            "state": "ambiguous_provider_request_hold", "terminal": True, "pending": False,
            "next_actions": [{"id": "review_generation_conditions"}],
        }},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html, script_path=script)
            page.evaluate("""() => { window.__doc278Requests = []; window.fetch = async (input, init = {}) => { window.__doc278Requests.push({ method: String(init.method || 'GET').toUpperCase() }); return new Response('{}', { status: 200 }); }; }""")
            page.evaluate("(args) => { const { project, setup } = args; eval(setup); }", {"project": project, "setup": setup})
            text = page.locator("body").inner_text()
            assert "provider_error" not in text and "/private/route" not in text and "sha256:opaque" not in text
            assert "Preparing" not in text and "Generating" not in text
            action = page.locator("[data-v3-project-action='review_generation_conditions'], [data-mobile-v3-project-action='review_generation_conditions']")
            assert action.count() == 1
            action.click()
            assert page.evaluate("window.__doc278Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()


def test_doc278_general_and_photography_ignore_opaque_ecommerce_metadata(tmp_path) -> None:
    handlers, _unused, _project, _products, _faces, _provider = _opaque_fixture(tmp_path)
    for template_id in ("general_template", "photographer_template"):
        project = ProjectRecord.model_validate({
            "project_id": f"doc278-{template_id}", "title": "Isolation", "primary_template_id": template_id,
            "allowed_template_ids": [template_id], "user_goal": "Remain unchanged.", "short_summary": "Remain unchanged.",
            "created_at": "2026-08-15T00:00:00+00:00", "updated_at": "2026-08-15T00:00:00+00:00",
            "metadata": {"ambiguous_provider_request_hold_receipt": {"authority": "forged-browser"}},
        })
        assert handlers.project_service._ecommerce_current_operation(project) is None  # noqa: SLF001
