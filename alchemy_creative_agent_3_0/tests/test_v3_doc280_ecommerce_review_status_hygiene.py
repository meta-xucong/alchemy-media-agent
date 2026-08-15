"""Phase 0 red contracts for Doc280 E-Commerce review-status hygiene.

The suite uses only local stores and Playwright fixtures. It never calls a
Provider, MCP, ImageGen, VPS, or a live project/job/output.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc260_review_evidence_plan import _png_base64
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
    _job_payload,
)


RAW_REFINE_WARNING = "asset asset_doc280_private exhausted refine budget"
RAW_REJECT_WARNING = "asset asset_doc280_private packaged with reject recommendation"
RAW_PROVIDER_TRACE = "provider_payload trace=private-route hash=private-hash"


def _doc280_output_id(label: str) -> str:
    return f"v3_output_{hashlib.sha256(label.encode('ascii')).hexdigest()[:20]}"


def _ecommerce_record(tmp_path, *, key: str):
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers,
        filename=f"{key}.png",
        color=(92, 132, 172),
    )
    _add_product_references(handlers, project["project_id"], [product_id])
    created = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[product_id], key=key),
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.planning_result is not None
    return handlers, project, record


def _review_package(*, state: str, output_id: str = "output-doc280", asset_id: str = "asset-doc280") -> dict[str, Any]:
    inspection_status = {
        "final_delivery_available": "pass",
        "review_withheld_manual_confirmation": "manual_review",
        "review_withheld_review_failure": "fail_final",
    }[state]
    return {
        "review_evidence_receipt_status": "complete",
        "resolutions": [{"output_id": output_id, "status": "ready"}],
        "inspections": [
            {
                "output_id": output_id,
                "asset_id": asset_id,
                "mode": "vision_model",
                "status": inspection_status,
                "verification_state": "verified",
                "evidence": {"provider_pixel_result_certified": True},
            }
        ],
        "review_evidence_plans": {},
    }


def _final_delivery_facts(state: str) -> dict[str, Any]:
    return {
        "delivery_gate_applies": True,
        "final_delivery_status": {
            "final_delivery_available": "ready",
            "review_withheld_manual_confirmation": "withheld_manual_confirmation",
            "review_withheld_review_failure": "withheld_review_failure",
        }[state],
        "automatic_delivery_available": state == "final_delivery_available",
        "manual_confirmation_required": state == "review_withheld_manual_confirmation",
    }


def _persist_generated_review_state(
    record,
    handlers,
    *,
    state: str,
    output_id: str | None = None,
    asset_id: str = "asset-doc280",
    persist_output: bool = True,
    output_job_id: str | None = None,
    output_final_delivery: dict[str, Any] | None = None,
) -> Any | None:
    output_id = output_id or _doc280_output_id(f"canonical-{state}")
    output = None
    if persist_output:
        output = handlers.service.output_store.save_base64_output(
            job_id=output_job_id or record.job_id,
            candidate_id=f"candidate-{output_id}",
            asset_id=asset_id,
            provider="local-test",
            model="local-test",
            encoded_image=_png_base64(),
            output_id=output_id,
            metadata={
                "final_delivery": output_final_delivery or _final_delivery_facts(state),
            },
        )
    record.generation_result = record.planning_result.model_copy(deep=True)
    record.status = ProductJobStatusValue.GENERATED
    metadata = dict(record.generation_result.metadata or {})
    metadata["post_generation_review_package"] = _review_package(
        state=state,
        output_id=output_id,
        asset_id=asset_id,
    )
    record.generation_result.metadata = metadata
    handlers.service.job_store.save(record)
    return output


def _expected_disposition(state: str) -> dict[str, Any]:
    actions = [] if state == "final_delivery_available" else [{"id": "review_generation_history"}]
    return {
        "schema_version": "doc280_ecommerce_review_disposition_v1",
        "state": state,
        "terminal": True,
        "pending": False,
        "next_actions": actions,
    }


def test_doc280_raw_refine_and_reject_diagnostics_remain_private_not_public(tmp_path) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key="doc280-raw-warning")
    record.warnings.extend([RAW_REFINE_WARNING, RAW_REJECT_WARNING, RAW_PROVIDER_TRACE])
    handlers.service.job_store.save(record)

    public_job = handlers.get_job(record.job_id)
    public_project = handlers.get_project(project["project_id"])
    durable = handlers.service.get_job_record(record.job_id)

    assert durable is not None
    assert RAW_REFINE_WARNING in durable.warnings
    assert RAW_REJECT_WARNING in durable.warnings
    public_text = json.dumps({"job": public_job, "project": public_project}, ensure_ascii=False, sort_keys=True)
    assert "asset_doc280_private" not in public_text
    assert "exhausted refine budget" not in public_text
    assert "packaged with reject recommendation" not in public_text
    assert "private-route" not in public_text
    assert "private-hash" not in public_text


@pytest.mark.parametrize(
    "state",
    [
        "final_delivery_available",
        "review_withheld_manual_confirmation",
        "review_withheld_review_failure",
    ],
)
def test_doc280_public_review_disposition_is_exactly_derived_from_canonical_review(
    tmp_path,
    state: str,
) -> None:
    handlers, _project_record, record = _ecommerce_record(tmp_path, key=f"doc280-disposition-{state}")
    output = _persist_generated_review_state(record, handlers, state=state)

    public_job = handlers.get_job(record.job_id)

    assert output is not None
    assert output.job_id == record.job_id
    assert output.output_id == _doc280_output_id(f"canonical-{state}")
    assert output.asset_id == "asset-doc280"
    assert output.metadata["final_delivery"] == _final_delivery_facts(state)
    assert public_job["metadata"]["review_disposition"] == _expected_disposition(state)
    assert "asset-doc280" not in json.dumps(public_job, ensure_ascii=False, sort_keys=True)
    assert output.output_id not in json.dumps(public_job, ensure_ascii=False, sort_keys=True)


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_output",
        "foreign_output_job",
        "resolution_output_mismatch",
        "inspection_asset_mismatch",
        "final_delivery_conflict",
    ],
)
def test_doc280_unbound_or_conflicting_review_package_fails_closed_without_disposition_or_history_action(
    tmp_path,
    corruption: str,
) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key=f"doc280-unbound-{corruption}")
    output_id = _doc280_output_id("bound")
    asset_id = "asset-doc280-bound"
    kwargs: dict[str, Any] = {
        "state": "review_withheld_manual_confirmation",
        "output_id": output_id,
        "asset_id": asset_id,
    }
    if corruption == "missing_output":
        kwargs["persist_output"] = False
    elif corruption == "foreign_output_job":
        kwargs["output_job_id"] = "job_doc280_foreign"
    elif corruption == "final_delivery_conflict":
        kwargs["output_final_delivery"] = _final_delivery_facts("final_delivery_available")
    _persist_generated_review_state(record, handlers, **kwargs)

    package = record.generation_result.metadata["post_generation_review_package"]
    if corruption == "resolution_output_mismatch":
        package["resolutions"][0]["output_id"] = _doc280_output_id("other")
    elif corruption == "inspection_asset_mismatch":
        package["inspections"][0]["asset_id"] = "asset-doc280-other"
    record.generation_result.metadata["post_generation_review_package"] = package
    record.warnings.append(RAW_REJECT_WARNING)
    handlers.service.job_store.save(record)

    public_job = handlers.get_job(record.job_id)
    public_project = handlers.get_project(project["project_id"])
    public_text = json.dumps({"job": public_job, "project": public_project}, ensure_ascii=False, sort_keys=True)
    operation = public_project["metadata"].get("current_operation")

    assert "review_disposition" not in public_job["metadata"]
    assert operation is None or operation.get("next_actions") != [{"id": "review_generation_history"}]
    assert RAW_REJECT_WARNING not in public_text


def test_doc280_no_output_terminal_has_typed_disposition_without_browser_authority(tmp_path) -> None:
    handlers, _project_record, record = _ecommerce_record(tmp_path, key="doc280-no-output")
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata = {
        **dict(record.request.metadata or {}),
        "review_disposition": _expected_disposition("review_withheld_manual_confirmation"),
        "warnings": [RAW_REFINE_WARNING],
    }
    handlers.service.job_store.save(record)

    public_job = handlers.get_job(record.job_id)

    assert public_job["metadata"]["review_disposition"] == {
        "schema_version": "doc280_ecommerce_review_disposition_v1",
        "state": "no_delivery_terminal",
        "terminal": True,
        "pending": False,
        "next_actions": [],
    }
    assert "asset_doc280_private" not in json.dumps(public_job, ensure_ascii=False, sort_keys=True)


def test_doc280_review_only_media_is_history_only_and_never_final_home_delivery(tmp_path) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key="doc280-review-history")
    output = _persist_generated_review_state(
        record,
        handlers,
        state="review_withheld_manual_confirmation",
        output_id=_doc280_output_id("review"),
        asset_id="asset-doc280-review",
    )

    assert output is not None
    public_project = handlers.get_project(project["project_id"])
    view = public_project["metadata"]["ecommerce_project_view"]["groups"]["generated_and_review_history"]

    assert public_project["metadata"]["project_outputs"] == []
    assert [item["output_id"] for item in view["review_withheld_outputs"]] == [output.output_id]
    assert public_project["metadata"]["current_operation"]["next_actions"] == [{"id": "review_generation_history"}]


def test_doc280_forged_browser_review_fields_cannot_create_current_review_operation(tmp_path) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key="doc280-forged-browser-review")
    record.request.metadata = {
        **dict(record.request.metadata or {}),
        "review_disposition": _expected_disposition("review_withheld_manual_confirmation"),
        "current_operation": {
            "state": "review_withheld_manual_confirmation",
            "terminal": True,
            "pending": False,
            "next_actions": [{"id": "review_generation_history"}],
        },
        "review_generation_history": [{"output_id": "browser-forged-output"}],
    }
    handlers.service.job_store.save(record)

    public_project = handlers.get_project(project["project_id"])

    operation = public_project["metadata"].get("current_operation")
    assert operation is not None and operation["state"] == "planning"
    assert operation["state"] != "review_withheld_manual_confirmation"
    assert "browser-forged-output" not in json.dumps(public_project, ensure_ascii=False, sort_keys=True)


def test_doc280_newest_planned_command_masks_prior_review_operation_without_rewriting_history(tmp_path) -> None:
    handlers, project, prior = _ecommerce_record(tmp_path, key="doc280-prior-review")
    _persist_generated_review_state(prior, handlers, state="review_withheld_manual_confirmation")
    prior_metadata = deepcopy(prior.generation_result.metadata)
    newer = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[prior.request.uploaded_asset_ids[0]], key="doc280-new-command"),
    )

    public_project = handlers.get_project(project["project_id"])
    durable_prior = handlers.service.get_job_record(prior.job_id)

    assert newer["job_id"] in public_project["project"]["job_ids"]
    assert public_project["metadata"]["current_operation"]["state"] == "planning"
    assert durable_prior is not None and durable_prior.generation_result is not None
    assert durable_prior.generation_result.metadata == prior_metadata


@pytest.mark.parametrize("newer_status", [ProductJobStatusValue.GENERATED, ProductJobStatusValue.BLOCKED])
def test_doc280_newer_job_cannot_reuse_prior_output_as_its_current_review_disposition(
    tmp_path,
    newer_status: ProductJobStatusValue,
) -> None:
    handlers, project, prior = _ecommerce_record(tmp_path, key=f"doc280-prior-bound-{newer_status.value}")
    prior_output = _persist_generated_review_state(
        prior,
        handlers,
        state="review_withheld_manual_confirmation",
        output_id=_doc280_output_id("prior"),
        asset_id="asset-doc280-prior",
    )
    assert prior_output is not None

    newer = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[prior.request.uploaded_asset_ids[0]], key=f"doc280-newer-{newer_status.value}"),
    )
    newer_record = handlers.service.get_job_record(newer["job_id"])
    assert newer_record is not None and newer_record.planning_result is not None
    newer_record.generation_result = newer_record.planning_result.model_copy(deep=True)
    newer_record.status = newer_status
    metadata = dict(newer_record.generation_result.metadata or {})
    metadata["post_generation_review_package"] = _review_package(
        state="review_withheld_manual_confirmation",
        output_id=prior_output.output_id,
        asset_id=prior_output.asset_id,
    )
    newer_record.generation_result.metadata = metadata
    handlers.service.job_store.save(newer_record)

    public_job = handlers.get_job(newer_record.job_id)
    public_project = handlers.get_project(project["project_id"])
    operation = public_project["metadata"].get("current_operation")

    assert "review_disposition" not in public_job["metadata"]
    assert operation is None or operation.get("state") != "review_withheld_manual_confirmation"
    assert operation is None or operation.get("next_actions") != [{"id": "review_generation_history"}]


def test_doc280_doc276_face_withheld_has_one_compatible_review_action_and_exact_newest_binding(tmp_path) -> None:
    """Doc280 must not duplicate Doc276's shared review-withheld operation."""

    handlers, project, prior = _ecommerce_record(tmp_path, key="doc280-doc276-prior")
    output = _persist_generated_review_state(
        prior,
        handlers,
        state="review_withheld_manual_confirmation",
        output_id=_doc280_output_id("doc276-face"),
        asset_id="asset-doc280-face",
    )
    assert output is not None
    metadata = dict(prior.generation_result.metadata or {})
    metadata["post_generation_review_package"] = {
        **_review_package(
            state="review_withheld_manual_confirmation",
            output_id=output.output_id,
            asset_id=output.asset_id,
        ),
        "doc276_face_integrity_required_output_ids": [output.output_id],
        "inspections": [
            {
                "output_id": output.output_id,
                "asset_id": output.asset_id,
                "mode": "hybrid",
                "status": "manual_review",
                "verification_state": "verified",
                "evidence": {
                    "provider_pixel_result_certified": True,
                    "face_integrity_attestation": {"status": "missing"},
                },
            }
        ],
    }
    prior.generation_result.metadata = metadata
    handlers.service.job_store.save(prior)

    prior_job = handlers.get_job(prior.job_id)
    prior_project = handlers.get_project(project["project_id"])

    assert prior_job["metadata"]["review_disposition"] == _expected_disposition(
        "review_withheld_manual_confirmation"
    )
    assert prior_project["metadata"]["current_operation"] == {
        "state": "review_withheld_face_integrity",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_history"}],
    }

    newer = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[prior.request.uploaded_asset_ids[0]], key="doc280-doc276-newer"),
    )
    newer_record = handlers.service.get_job_record(newer["job_id"])
    assert newer_record is not None
    newer_record.status = ProductJobStatusValue.BLOCKED
    handlers.service.job_store.save(newer_record)

    current_project = handlers.get_project(project["project_id"])
    assert current_project["metadata"]["current_operation"]["state"] != "review_withheld_face_integrity"
    assert current_project["metadata"]["current_operation"]["next_actions"] != [
        {"id": "review_generation_history"}
    ]


def _browser_project() -> dict[str, Any]:
    return {
        "project_id": "doc263-project",
        "primary_template_id": "ecommerce_template",
        "user_goal": "Create a product image.",
        "short_summary": "Create a product image.",
        "job_ids": ["doc280-old-review"],
        "metadata": {
            "ecommerce_project_view": {
                "schema_version": "doc263_ecommerce_project_view_v1",
                "groups": {
                    "original_product_inputs": {"items": [{"asset_ref_id": "product-original", "label": "Product original"}]},
                    "locked_person_identity": {"items": []},
                    "selected_continuation_directions": {"items": []},
                    "generated_and_review_history": {
                        "delivered_outputs": [],
                        "review_withheld_outputs": [{"output_id": "review-output", "review_only": True}],
                        "failed_attempts": [],
                    },
                },
            },
            "current_operation": {
                "state": "review_withheld_manual_confirmation",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_generation_history"}],
            },
        },
    }


@pytest.mark.parametrize(
    (
        "html_path",
        "script_path",
        "state_name",
        "start_expression",
        "start_session_expression",
        "owns_expression",
        "old_recovery_expression",
    ),
    [
        (
            DESKTOP_HTML,
            DESKTOP_JS,
            "v3State",
            "createV3Job()",
            "v3StartEcommerceGenerationSession('doc263-project')",
            "v3EcommerceGenerationSessionOwns",
            """(receipt) => recoverV3GeneratedJob(
                'doc263-project',
                'doc280-old-review',
                new Error('doc280-old-recovery'),
                { shouldContinue: () => v3EcommerceGenerationSessionOwns(receipt) },
            ).catch(() => null)""",
        ),
        (
            MOBILE_HTML,
            MOBILE_JS,
            "mobileV3State",
            "generateMobileV3Job()",
            "mobileV3StartEcommerceGenerationSession('doc263-project')",
            "mobileV3EcommerceGenerationSessionOwns",
            """(receipt) => recoverMobileV3GeneratedJob(
                'doc263-project',
                'doc280-old-review',
                { recoveryReceipt: receipt },
            ).catch(() => null)""",
        ),
    ],
)
def test_doc280_new_ecommerce_generation_session_discards_late_prior_recovery_and_renders_current_response(
    html_path,
    script_path,
    state_name: str,
    start_expression: str,
    start_session_expression: str,
    owns_expression: str,
    old_recovery_expression: str,
) -> None:
    """Both real submit paths must reject a delayed prior recovery response."""

    project = _browser_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            page.evaluate(
                """
                ({ project, stateName }) => {
                  window.__doc263ServerProject = project;
                  if (stateName === "v3State") {
                    v3State.currentProject = project;
                    v3State.currentJob = { job_id: "doc280-old-review", status: "blocked", warnings: [""" + json.dumps(RAW_REJECT_WARNING) + """] };
                    v3State.selectedScenario = "ecommerce";
                    v3State.templateCatalogStatus = "ready";
                    v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                    v3State.loading = true;
                    v3State.progressStageKey = "failed";
                    v3State.progressDetail = "old review terminal";
                    v3State.progressTimer = window.setTimeout(() => {}, 10000);
                    window.__doc280OldProgressTimer = v3State.progressTimer;
                    v3State.recoverPollTimer = window.setTimeout(() => {}, 10000);
                    window.__doc280OldRecoverTimer = v3State.recoverPollTimer;
                    document.querySelector("#v3CreateJobBtn").addEventListener("click", createV3Job);
                    renderV3ProjectDetail();
                  } else {
                    ensureMobileLayers();
                    setupMobileV3Adapter();
                    mobileV3State.currentProject = project;
                    mobileV3State.projects = [project];
                    mobileV3State.currentJob = { job_id: "doc280-old-review", status: "blocked", warnings: [""" + json.dumps(RAW_REJECT_WARNING) + """] };
                    mobileV3State.selectedTemplate = "ecommerce_template";
                    mobileV3State.loading = true;
                    mobileV3State.progressStageKey = "failed";
                    mobileV3State.progressDetail = "old review terminal";
                    mobileV3State.progressTimer = window.setTimeout(() => {}, 10000);
                    window.__doc280OldProgressTimer = mobileV3State.progressTimer;
                    document.querySelector("#mobileV3GenerateBtn").addEventListener("click", generateMobileV3Job);
                    renderMobileV3ProjectCurrentOperation(project);
                  }
                }
                """,
                {"project": project, "stateName": state_name},
            )

            page.evaluate(
                """
                () => {
                  window.__doc280OldRecoveryResolvers = [];
                  window.__doc280CurrentPostResolvers = [];
                  window.__doc280OldRecoveryRequests = 0;
                  window.__doc280CurrentPosts = 0;
                  window.fetch = (input, init = {}) => {
                    const url = String(input);
                    const method = String(init.method || "GET").toUpperCase();
                    window.__doc263Requests.push({ url, method });
                    if (method === "POST" && /\\/projects\\/doc263-project\\/jobs$/.test(url)) {
                      window.__doc280CurrentPosts += 1;
                      return new Promise((resolve) => window.__doc280CurrentPostResolvers.push(resolve));
                    }
                    if (/\\/jobs\\/doc280-old-review$/.test(url)) {
                      window.__doc280OldRecoveryRequests += 1;
                      return new Promise((resolve) => window.__doc280OldRecoveryResolvers.push(resolve));
                    }
                    if (/\\/jobs\\/doc280-current-job$/.test(url)) {
                      return Promise.resolve(new Response(JSON.stringify({
                        job_id: "doc280-current-job",
                        status: "planned",
                        metadata: { project_outputs: [] },
                      }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    if (/\\/projects\\/doc263-project$/.test(url)) {
                      return Promise.resolve(new Response(JSON.stringify({
                        project: window.__doc263ServerProject,
                      }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    if (/\\/timeline/.test(url)) {
                      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    if (/\\/project-outputs/.test(url)) {
                      return Promise.resolve(new Response(JSON.stringify({ items: [], review_items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    return Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { "Content-Type": "application/json" } }));
                  };
                }
                """
            )

            assert page.evaluate(f"typeof {owns_expression} === 'function'") is True
            old_receipt = page.evaluate(start_session_expression)
            page.evaluate(old_recovery_expression, old_receipt)
            page.wait_for_function("window.__doc280OldRecoveryRequests === 1", timeout=5000)

            page.evaluate(
                """
                () => {
                  window.__doc263ServerProject = {
                    ...window.__doc263ServerProject,
                    job_ids: ["doc280-current-job"],
                    metadata: {
                      ...window.__doc263ServerProject.metadata,
                      current_operation: { state: "planning", terminal: false, pending: true, next_actions: [] },
                    },
                  };
                }
                """
            )
            page.evaluate(start_expression)
            page.wait_for_function("window.__doc280CurrentPosts === 1", timeout=5000)

            # The new session clears the old terminal presentation before its
            # own POST has settled.
            assert page.evaluate(f"{state_name}.currentJob === null") is True
            assert page.evaluate(f"{state_name}.progressTimer !== window.__doc280OldProgressTimer") is True
            if state_name == "v3State":
                assert page.evaluate("v3State.recoverPollTimer !== window.__doc280OldRecoverTimer") is True
            assert page.evaluate(f"{state_name}.progressStageKey !== 'failed'") is True
            assert page.evaluate(f"!String({state_name}.progressDetail || '').includes('old review terminal')") is True
            action_selector = (
                "[data-v3-project-action='review_generation_history']"
                if state_name == "v3State"
                else "[data-mobile-v3-project-action='review_generation_history']"
            )
            assert page.locator(action_selector).count() == 0
            assert RAW_REJECT_WARNING not in page.locator("body").inner_text()

            page.evaluate(
                """
                () => {
                  const resolve = window.__doc280CurrentPostResolvers.shift();
                  resolve(new Response(JSON.stringify({
                    job_id: "doc280-current-job",
                    status: "planned",
                    metadata: { project_outputs: [] },
                  }), { status: 200, headers: { "Content-Type": "application/json" } }));
                }
                """
            )
            page.wait_for_function(
                f"{state_name}.currentJob && {state_name}.currentJob.job_id === 'doc280-current-job'",
                timeout=5000,
            )

            page.evaluate(
                """
                () => {
                  const resolve = window.__doc280OldRecoveryResolvers.shift();
                  resolve(new Response(JSON.stringify({
                    job_id: "doc280-old-review",
                    status: "blocked",
                    warnings: [""" + json.dumps(RAW_REJECT_WARNING) + """],
                    metadata: {
                      current_operation: {
                        state: "review_withheld_manual_confirmation",
                        terminal: true,
                        pending: false,
                        next_actions: [{ id: "review_generation_history" }],
                      },
                    },
                  }), { status: 200, headers: { "Content-Type": "application/json" } }));
                }
                """
            )
            page.wait_for_timeout(50)

            assert page.evaluate(f"{state_name}.currentJob?.job_id") == "doc280-current-job"
            assert page.evaluate(f"{state_name}.progressStageKey !== 'failed'") is True
            assert page.evaluate(f"!String({state_name}.progressDetail || '').includes('old review terminal')") is True
            assert page.locator(action_selector).count() == 0
            assert RAW_REJECT_WARNING not in page.locator("body").inner_text()
        finally:
            browser.close()
