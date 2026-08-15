"""Phase 0 red contracts for Doc279 E-Commerce predecessor authority.

The fixtures create only local in-memory Project Mode/Product API records.
They never contact a Provider transport, MCP, ImageGen, VPS, or a live V3
 project. ``doc279_ecommerce_transparent_predecessor_receipt_v1`` is a
server-owned private runtime receipt fixture, never browser input or request
metadata authority.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.project_mode.store import PersistentProjectStore
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _save_history_output,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc278_ecommerce_opaque_provider_rejection_hold import (
    RAW_OPAQUE_ERROR,
    _create_opaque_block,
    _opaque_fixture,
    _payload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc271_provider_deliverability_closure import (
    _TerminalFailureProvider,
    _add_product_references,
    _configured_route_identity,
    _fixture,
    _ready_product_upload,
    settings,
)
from app import main as app_main


_DOC279_PRIVATE_NAMESPACE = "doc279_ecommerce_transparent_predecessor_receipts"


def _digest(value: dict[str, Any]) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _browser_repeat_payload(product_ids: list[str], *, key: str) -> dict[str, Any]:
    """Model one explicit browser click without fresh source authority."""

    payload = _payload([], key=key)
    payload["uploaded_asset_ids"] = []
    forged = {
        "schema_version": "doc279_ecommerce_transparent_predecessor_receipt_v1",
        "authority": "browser",
        "project_id": "forged-project",
        "terminal_job_id": "forged-job",
    }
    forged["receipt_digest"] = _digest(forged)
    payload["metadata"].update({
        "auto_generate": True,
        "requested_image_count": 1,
        "requested_image_size": "1024x1024",
        "selected_product_asset_ids": list(product_ids),
        "doc279_ecommerce_transparent_predecessor_evidence": forged,
    })
    return payload


def _mark_server_transparent_predecessor_failure(
    handlers,
    project: dict[str, Any],
    record,
) -> None:
    """Seed only the durable terminal Job facts, never an E33 receipt.

    A test fixture may model the historical terminal record, but it must not
    write the server-only receipt into request metadata. The runtime under test
    is responsible for emitting that receipt after it re-reads this durable
    record and verifies no Provider execution or output exists.
    """

    metadata = dict(record.request.metadata or {})
    metadata.pop("provider_failure_retry", None)
    record.request.metadata = metadata
    record.status = ProductJobStatusValue.BLOCKED
    record.planning_result = None
    record.generation_result = None
    handlers.service.job_store.save(record)


def _private_transparent_receipt(handlers, project: dict[str, Any], record) -> dict[str, Any]:
    """Build a private historical fixture from already server-issued Job facts."""

    metadata = dict(record.request.metadata or {})
    command = dict(metadata["doc271_command_binding"])
    source = dict(metadata["doc271_current_source_binding"])
    payload = {
        "schema_version": "doc279_ecommerce_transparent_predecessor_receipt_v1",
        "authority": "v3_project_mode",
        "project_id": project["project_id"],
        "terminal_job_id": record.job_id,
        "template_id": "ecommerce_template",
        "terminal_status": ProductJobStatusValue.BLOCKED.value,
        "command_binding_digest": command["command_binding_digest"],
        "current_reference_binding_digest": metadata["current_reference_binding_digest"],
        "current_source_binding_digest": source["source_binding_digest"],
        "locked_visual_asset_binding": deepcopy(metadata.get("frozen_visual_asset_binding_set") or {}),
        "selected_continuation_admissions_digest": _digest(
            handlers.project_service._doc269_selected_continuation_admissions(  # noqa: SLF001
                handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
            )
        ),
        "requested_output_count": 1,
        "provider_route_identity": _configured_route_identity(),
        "source_resolver_identity": "doc263_doc269_server_binding_v1",
        "execution_phase": "pre_provider_planning",
        "outer_request_count": 0,
        "delivered_output_count": 0,
        "terminal": True,
    }
    payload["identity_digest"] = _digest(
        {
            "project_id": payload["project_id"],
            "terminal_job_id": payload["terminal_job_id"],
            "command_binding_digest": payload["command_binding_digest"],
        }
    )
    return _reseal_private_receipt(payload)


def _reseal_private_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Model corruption with a recomputed private digest, never browser trust."""

    candidate = deepcopy(receipt)
    candidate.pop("receipt_digest", None)
    candidate["receipt_digest"] = _digest(candidate)
    return candidate


def _seed_private_transparent_receipt(handlers, project: dict[str, Any], record) -> dict[str, Any]:
    """Seed only an existing historical private-state fixture.

    Phase 0 uses this direct backing-store insertion solely to model a receipt
    written before the future E33 namespace implementation exists. Runtime
    issuance and reads are required to use the public private-record API.
    """

    receipt = _private_transparent_receipt(handlers, project, record)
    store = handlers.project_service.project_store
    store._private_records.setdefault(project["project_id"], {}).setdefault(  # noqa: SLF001
        _DOC279_PRIVATE_NAMESPACE,
        [],
    ).append(deepcopy(receipt))
    return receipt


def _private_receipts(handlers, project_id: str) -> list[dict[str, Any]]:
    """Read only an injected historical fixture; never a runtime API model."""

    return [
        deepcopy(item)
        for item in handlers.project_service.project_store._private_records.get(  # noqa: SLF001
            project_id,
            {},
        ).get(_DOC279_PRIVATE_NAMESPACE, [])
    ]


def _replace_private_receipt(handlers, project_id: str, receipt: dict[str, Any]) -> None:
    """Replace only the test's historical private fixture."""

    handlers.project_service.project_store._private_records[project_id][  # noqa: SLF001
        _DOC279_PRIVATE_NAMESPACE
    ] = [deepcopy(receipt)]


def _opaque_with_transparent_newer_planning_failure(
    tmp_path,
    monkeypatch,
    *,
    seed_private_receipt: bool = True,
    run_background_worker: bool = True,
):
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _old, historical = _create_opaque_block(handlers, provider, project, product_ids)
    original_gate = handlers.project_service._doc278_matching_opaque_provider_hold  # noqa: SLF001
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        lambda *_args, **_kwargs: None,
    )
    newer = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-create-transparent-successor"),
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        original_gate,
    )
    newer_record = handlers.service.get_job_record(newer["job_id"])
    assert newer_record is not None
    _mark_server_transparent_predecessor_failure(handlers, project, newer_record)
    if seed_private_receipt:
        _seed_private_transparent_receipt(handlers, project, newer_record)
    if run_background_worker:
        operation = handlers.begin_project_planning_operation(
            project["project_id"],
            _browser_repeat_payload([], key="doc279-server-planning-operation"),
        )
        original_post = handlers.post_project_job
        monkeypatch.setattr(
            handlers,
            "post_project_job",
            lambda *_args, **_kwargs: {
                "job_id": newer_record.job_id,
                "status": ProductJobStatusValue.BLOCKED.value,
            },
        )
        monkeypatch.setattr(app_main, "v3_route_handlers", handlers)
        app_main._run_v3_project_planning_background(
            project["project_id"],
            operation["operation_id"],
            _browser_repeat_payload([], key="doc279-worker-blocked-response"),
            None,
        )
        monkeypatch.setattr(handlers, "post_project_job", original_post)
        worker_view = handlers.get_project(project["project_id"])
        assert newer_record.job_id in worker_view["project"]["job_ids"]
        assert worker_view["metadata"]["current_operation"]["state"] == "ambiguous_provider_request_hold"
        assert handlers.service.output_store.list_by_job(newer_record.job_id) == []
    return handlers, project, product_ids, provider, historical, newer_record


def _assert_e32_not_held(handlers, project: dict[str, Any], product_ids: list[str], *, key: str) -> dict[str, Any]:
    created = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key=key),
    )
    assert created.get("job_id")
    assert created["metadata"].get("current_operation", {}).get("state") != "ambiguous_provider_request_hold"
    return created


def test_doc279_official_private_receipt_namespace_freezes_persists_and_reloads(
    tmp_path,
) -> None:
    """E33 runtime records must use the store API, never private dict access."""

    project_id = "project_doc279_private_store"
    root = tmp_path / "doc279-private-store"
    store = PersistentProjectStore(root)
    receipt = {
        "schema_version": "doc279_ecommerce_transparent_predecessor_receipt_v1",
        "authority": "v3_project_mode",
        "project_id": project_id,
        "terminal_job_id": "job_doc279_private_store",
        "identity_digest": "doc279-private-store-identity",
        "receipt_digest": "doc279-private-store-receipt",
        "nested": {"binding": {"values": ["frozen"]}},
    }

    appended = store.append_private_record(
        project_id,
        _DOC279_PRIVATE_NAMESPACE,
        receipt,
    )
    appended["nested"]["binding"]["values"].append("mutated-return")
    listed = store.list_private_records(project_id, _DOC279_PRIVATE_NAMESPACE)
    assert listed == [receipt]
    listed[0]["nested"]["binding"]["values"].append("mutated-list")
    assert store.list_private_records(project_id, _DOC279_PRIVATE_NAMESPACE) == [receipt]
    assert (
        store.append_private_record(project_id, _DOC279_PRIVATE_NAMESPACE, receipt)
        == receipt
    )
    assert PersistentProjectStore(root).list_private_records(
        project_id,
        _DOC279_PRIVATE_NAMESPACE,
    ) == [receipt]


def test_doc279_same_fact_transparent_predecessor_reveals_older_exact_e32_hold(
    tmp_path,
    monkeypatch,
) -> None:
    handlers, project, product_ids, provider, historical, newer = (
        _opaque_with_transparent_newer_planning_failure(tmp_path, monkeypatch)
    )
    before_jobs = list(handlers.get_project(project["project_id"])["project"]["job_ids"])
    product_creates: list[object] = []
    brain_plans: list[object] = []
    physical_materializations: list[object] = []

    def unexpected_create(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        product_creates.append((args, kwargs))
        raise AssertionError("Doc279 transparent predecessor reached Product API create")

    def unexpected_plan(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        brain_plans.append((args, kwargs))
        raise AssertionError("Doc279 transparent predecessor reached Brain planning")

    def unexpected_physical(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        physical_materializations.append((args, kwargs))
        raise AssertionError("Doc279 transparent predecessor materialized a new physical plan")

    monkeypatch.setattr(handlers.service, "create_project_ecommerce_job", unexpected_create)
    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", unexpected_plan)
    monkeypatch.setattr(handlers.service, "_bind_ecommerce_physical_projections", unexpected_physical)

    held = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-repeat-after-transparent-failure"),
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
    assert product_creates == [] and brain_plans == [] and physical_materializations == []
    assert provider.calls == 1
    public_text = str({"response": held})
    for private in (historical.job_id, newer.job_id, RAW_OPAQUE_ERROR, "provider_error"):
        assert private not in public_text


def test_doc279_browser_metadata_cannot_author_transparent_predecessor_receipt(
    tmp_path,
    monkeypatch,
) -> None:
    """A browser-shaped self-digest never becomes private E33 authority."""

    handlers, project, product_ids, _provider, _historical, newer = (
        _opaque_with_transparent_newer_planning_failure(
            tmp_path,
            monkeypatch,
            seed_private_receipt=False,
            run_background_worker=False,
        )
    )
    persisted = dict(newer.request.metadata or {}).get(
        "doc279_ecommerce_transparent_predecessor_evidence"
    )
    assert isinstance(persisted, dict)
    assert persisted["receipt_digest"] == _digest({
        key: value for key, value in persisted.items() if key != "receipt_digest"
    })
    assert _private_receipts(handlers, project["project_id"]) == []

    created = _assert_e32_not_held(
        handlers,
        project,
        product_ids,
        key="doc279-browser-private-receipt-forgery",
    )

    assert created["job_id"] not in {newer.job_id, ""}
    assert _private_receipts(handlers, project["project_id"]) == []


def test_doc279_background_blocked_job_issues_private_receipt_only_after_durable_recheck(
    tmp_path,
    monkeypatch,
) -> None:
    """The Product API -> Doc277 worker path owns future private receipt issuance.

    The worker calls the real Project Mode/Product API create boundary. A
    deterministic local terminal wrapper models its actual ``job_id +
    blocked`` result without any Provider dispatch. The test deliberately
    leaves the E33 receipt absent and requires the future server-only terminal
    writer to append it only after re-reading the durable Job.
    """

    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _create_opaque_block(handlers, provider, project, product_ids)
    original_gate = handlers.project_service._doc278_matching_opaque_provider_hold  # noqa: SLF001
    original_post = handlers.post_project_job
    created_job_ids: list[str] = []

    def blocked_product_api_response(project_id, payload):  # noqa: ANN001, ANN202
        """Use real Product API creation, then model its local blocked result."""

        created = original_post(project_id, payload)
        record = handlers.service.get_job_record(created["job_id"])
        assert record is not None
        _mark_server_transparent_predecessor_failure(handlers, project, record)
        created_job_ids.append(record.job_id)
        return {
            "job_id": record.job_id,
            "status": ProductJobStatusValue.BLOCKED.value,
        }

    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(handlers, "post_project_job", blocked_product_api_response)
    worker_payload = _browser_repeat_payload(
        product_ids,
        key="doc279-worker-product-api-blocked",
    )
    browser_claim = deepcopy(
        worker_payload["metadata"]["doc279_ecommerce_transparent_predecessor_evidence"]
    )
    operation = handlers.begin_project_planning_operation(
        project["project_id"],
        worker_payload,
    )
    assert _private_receipts(handlers, project["project_id"]) == []
    monkeypatch.setattr(app_main, "v3_route_handlers", handlers)
    app_main._run_v3_project_planning_background(
        project["project_id"],
        operation["operation_id"],
        worker_payload,
        None,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        original_gate,
    )

    assert len(created_job_ids) == 1
    newer = handlers.service.get_job_record(created_job_ids[0])
    assert newer is not None and newer.status == ProductJobStatusValue.BLOCKED
    assert handlers.service.output_store.list_by_job(newer.job_id) == []
    assert "provider_failure_retry" not in dict(newer.request.metadata or {})
    assert (
        newer.request.metadata["doc279_ecommerce_transparent_predecessor_evidence"]
        == browser_claim
    )

    receipts = _private_receipts(handlers, project["project_id"])
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["authority"] == "v3_project_mode"
    assert receipt["terminal_job_id"] == newer.job_id
    assert receipt["project_id"] == project["project_id"]
    assert receipt["outer_request_count"] == 0
    assert receipt["delivered_output_count"] == 0
    assert receipt["command_binding_digest"] == newer.request.metadata[
        "doc271_command_binding"
    ]["command_binding_digest"]
    assert receipt["current_source_binding_digest"] == newer.request.metadata[
        "doc271_current_source_binding"
    ]["source_binding_digest"]
    assert receipt["receipt_digest"] != browser_claim["receipt_digest"]
    assert receipt["receipt_digest"] == _digest({
        key: value for key, value in receipt.items() if key != "receipt_digest"
    })


def test_doc279_http_background_no_job_e32_hold_outranks_private_planning_failure(
    tmp_path,
    monkeypatch,
) -> None:
    """The browser worker keeps Doc277 history but must project the E32 hold."""

    handlers, project, product_ids, _provider, _historical, _newer = (
        _opaque_with_transparent_newer_planning_failure(tmp_path, monkeypatch)
    )
    before_jobs = list(handlers.get_project(project["project_id"])["project"]["job_ids"])
    queued: list[tuple[object, tuple[object, ...]]] = []
    monkeypatch.setattr(app_main, "v3_route_handlers", handlers)
    monkeypatch.setattr(
        app_main._v3_planning_executor,
        "submit",
        lambda fn, *args: queued.append((fn, args)),
    )
    monkeypatch.setattr(
        handlers,
        "post_project_job",
        lambda *_args, **_kwargs: {
            "job_id": "",
            "status": ProductJobStatusValue.BLOCKED.value,
            "metadata": {
                "current_operation": {
                    "state": "ambiguous_provider_request_hold",
                    "terminal": True,
                    "pending": False,
                    "next_actions": [{"id": "review_generation_conditions"}],
                }
            },
        },
    )
    payload = _browser_repeat_payload(product_ids, key="doc279-http-repeat-after-transparent")
    payload["auto_generate"] = {
        "quality_mode": "standard",
        "metadata": {"require_real_images": True},
    }
    client = TestClient(app_main.app)

    started = client.post(
        f"/api/v3/creative-agent/projects/{project['project_id']}/jobs",
        json=payload,
    )

    assert started.status_code == 200
    assert started.json()["status"] == "planning"
    assert len(queued) == 1
    worker, arguments = queued.pop()
    worker(*arguments)

    public = client.get(f"/api/v3/creative-agent/projects/{project['project_id']}").json()
    assert public["project"]["job_ids"] == before_jobs
    assert public["metadata"]["current_operation"] == {
        "state": "ambiguous_provider_request_hold",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_conditions"}],
    }
    history = handlers.project_service.project_store.list_private_records(
        project["project_id"],
        "doc277_project_planning_operations",
    )
    assert any(
        item.get("record_kind") == "failed"
        and item.get("failure_code") == "planning_preflight_blocked"
        for item in history
    )


def test_doc279_http_background_direct_e32_no_job_hold_preserves_doc277_history(
    tmp_path,
    monkeypatch,
) -> None:
    """A direct server E32 response outranks only its own failed Doc277 operation."""

    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _create_opaque_block(handlers, provider, project, product_ids)
    before_jobs = list(handlers.get_project(project["project_id"])["project"]["job_ids"])
    product_creates: list[object] = []
    brain_plans: list[object] = []
    physical_materializations: list[object] = []
    queued: list[tuple[object, tuple[object, ...]]] = []

    def unexpected_create(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        product_creates.append((args, kwargs))
        raise AssertionError("direct E32 no-job hold reached Product API create")

    def unexpected_plan(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        brain_plans.append((args, kwargs))
        raise AssertionError("direct E32 no-job hold reached Brain planning")

    def unexpected_physical(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        physical_materializations.append((args, kwargs))
        raise AssertionError("direct E32 no-job hold materialized a physical plan")

    monkeypatch.setattr(handlers.service, "create_project_ecommerce_job", unexpected_create)
    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", unexpected_plan)
    monkeypatch.setattr(handlers.service, "_bind_ecommerce_physical_projections", unexpected_physical)
    monkeypatch.setattr(app_main, "v3_route_handlers", handlers)
    monkeypatch.setattr(
        app_main._v3_planning_executor,
        "submit",
        lambda fn, *args: queued.append((fn, args)),
    )
    client = TestClient(app_main.app)
    payload = _browser_repeat_payload(product_ids, key="doc279-http-direct-e32-no-job")
    payload["auto_generate"] = {
        "quality_mode": "standard",
        "metadata": {"require_real_images": True},
    }

    started = client.post(
        f"/api/v3/creative-agent/projects/{project['project_id']}/jobs",
        json=payload,
    )

    assert started.status_code == 200
    assert started.json()["status"] == "planning"
    assert len(queued) == 1
    worker, arguments = queued.pop()
    worker(*arguments)

    public = client.get(f"/api/v3/creative-agent/projects/{project['project_id']}").json()
    assert public["project"]["job_ids"] == before_jobs
    assert public["metadata"]["current_operation"] == {
        "state": "ambiguous_provider_request_hold",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_conditions"}],
    }
    history = handlers.project_service.project_store.list_private_records(
        project["project_id"],
        "doc277_project_planning_operations",
    )
    assert any(
        item.get("record_kind") == "failed"
        and item.get("failure_code") == "planning_preflight_blocked"
        and isinstance(item.get("doc279_e32_no_job_operation_projection"), dict)
        for item in history
    )
    assert product_creates == [] and brain_plans == [] and physical_materializations == []
    assert provider.calls == 1


@pytest.mark.parametrize(("html", "script", "setup"), [
    (
        DESKTOP_HTML,
        DESKTOP_JS,
        """
          v3State.currentProject = project; v3State.currentJob = { job_id: 'transparent-planning-job', status: 'blocked' };
          v3State.ecommerceSubmissionReceipt = null; v3State.selectedScenario = 'ecommerce'; v3State.templateCatalogStatus = 'ready';
          v3State.templates = [{ template_id: 'ecommerce_template', project_can_create_jobs: true }];
          setV3Busy(true); setV3Progress('planning', 'Preparing'); renderV3ScenarioState(); renderV3Job(v3State.currentJob);
        """,
    ),
    (
        MOBILE_HTML,
        MOBILE_JS,
        """
          ensureMobileLayers(); setupMobileV3Adapter(); mobileV3State.currentProject = project;
          mobileV3State.currentJob = { job_id: 'transparent-planning-job', status: 'blocked' };
          mobileV3State.ecommerceSubmissionReceipt = null; mobileV3State.selectedTemplate = 'ecommerce_template';
          setMobileV3Busy(true); setMobileV3Progress('planning', 'Preparing'); renderMobileV3ProjectCurrentOperation(project);
        """,
    ),
])
def test_doc279_transparent_predecessor_projects_e32_terminal_ui(
    tmp_path,
    monkeypatch,
    html,
    script,
    setup,
) -> None:
    handlers, project, product_ids, _provider, _historical, _newer = (
        _opaque_with_transparent_newer_planning_failure(tmp_path, monkeypatch)
    )
    view = handlers.get_project(project["project_id"])
    assert view["metadata"]["current_operation"] == {
        "state": "ambiguous_provider_request_hold",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_conditions"}],
    }
    browser_project = view["project"]
    browser_project["metadata"] = {"current_operation": view["metadata"]["current_operation"]}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html, script_path=script)
            page.evaluate(
                """() => {
                  window.__doc279Requests = [];
                  window.fetch = async (_input, init = {}) => {
                    window.__doc279Requests.push(String(init.method || "GET").toUpperCase());
                    return new Response("{}", { status: 200 });
                  };
                }"""
            )
            page.evaluate(
                "(args) => { const { project, setup } = args; eval(setup); }",
                {"project": browser_project, "setup": setup},
            )
            body = page.locator("body").inner_text()
            assert "Preparing" not in body and "Generating" not in body
            if html == DESKTOP_HTML:
                assert page.evaluate(
                    "v3State.loading === false && v3State.progressStageKey === 'failed' "
                    "&& v3State.progressTimer === null && v3State.recoverPollTimer === null "
                    "&& v3State.recoverPollAttempt === 0"
                ) is True
            else:
                assert page.evaluate(
                    "mobileV3State.busy === false && mobileV3State.progressTimer === null"
                ) is True
                assert page.locator("#mobileV3ProgressElapsed").inner_text() == "已结束"
            action = page.locator(
                "[data-v3-project-action='review_generation_conditions'], "
                "[data-mobile-v3-project-action='review_generation_conditions']"
            )
            assert action.count() == 1
            action.click()
            assert page.evaluate("window.__doc279Requests.filter((method) => method === 'POST').length") == 0
        finally:
            browser.close()


@pytest.mark.parametrize(("html", "script", "setup", "selector"), [
    (
        DESKTOP_HTML,
        DESKTOP_JS,
        """
          v3State.currentProject = project; v3State.currentJob = { job_id: 'planning-job', status: 'blocked' };
          v3State.selectedScenario = 'ecommerce'; v3State.templateCatalogStatus = 'ready';
          v3State.templates = [{ template_id: 'ecommerce_template', project_can_create_jobs: true }];
          setV3Busy(true); setV3Progress('planning', 'Preparing'); renderV3ProjectNextActions();
        """,
        "#v3ProjectNextActions",
    ),
    (
        MOBILE_HTML,
        MOBILE_JS,
        """
          ensureMobileLayers(); setupMobileV3Adapter(); mobileV3State.currentProject = project;
          mobileV3State.currentJob = { job_id: 'planning-job', status: 'blocked' };
          mobileV3State.selectedTemplate = 'ecommerce_template';
          setMobileV3Busy(true); setMobileV3Progress('planning', 'Preparing'); renderMobileV3ProjectCurrentOperation(project);
        """,
        "#mobileV3ProjectCurrentOperation",
    ),
])
def test_doc279_ordinary_planning_failure_never_claims_no_job_was_created(
    html,
    script,
    setup,
    selector,
) -> None:
    project = {
        "project_id": "doc279-ordinary-planning-failure",
        "primary_template_id": "ecommerce_template",
        "job_ids": ["job_durable_planning_failure"],
        "metadata": {
            "current_operation": {
                "operation_id": "server-operation",
                "state": "planning_failed",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_project_request"}],
            }
        },
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html, script_path=script)
            page.evaluate(
                """() => {
                  window.__doc279PlanningRequests = [];
                  window.fetch = async (_input, init = {}) => {
                    window.__doc279PlanningRequests.push(String(init.method || "GET").toUpperCase());
                    return new Response("{}", { status: 200 });
                  };
                }"""
            )
            page.evaluate(
                "(args) => { const { project, setup } = args; eval(setup); }",
                {"project": project, "setup": setup},
            )
            text = page.locator(selector).inner_text()
            assert "没有创建新的生成任务" not in text
            assert "尚未发送图像请求" in text
            assert "项目历史已保留" in text
            assert "Preparing" not in page.locator("body").inner_text()
            if html == DESKTOP_HTML:
                assert page.evaluate(
                    "v3State.loading === false && v3State.progressStageKey === 'failed' "
                    "&& v3State.progressTimer === null && v3State.recoverPollTimer === null "
                    "&& v3State.recoverPollAttempt === 0"
                ) is True
            else:
                assert page.evaluate(
                    "mobileV3State.busy === false && mobileV3State.progressTimer === null"
                ) is True
                assert page.locator("#mobileV3ProgressElapsed").inner_text() == "已结束"
            assert page.locator(
                "[data-v3-project-action='review_project_request'], "
                "[data-mobile-v3-project-action='review_project_request']"
            ).count() == 1
            page.locator(
                "[data-v3-project-action='review_project_request'], "
                "[data-mobile-v3-project-action='review_project_request']"
            ).click()
            assert page.evaluate(
                "window.__doc279PlanningRequests.filter((method) => method === 'POST').length"
            ) == 0
        finally:
            browser.close()


def test_doc279_newer_verified_provider_execution_suppresses_old_e32_hold(
    tmp_path,
    monkeypatch,
) -> None:
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _old, historical = _create_opaque_block(handlers, provider, project, product_ids)
    original_gate = handlers.project_service._doc278_matching_opaque_provider_hold  # noqa: SLF001
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        lambda *_args, **_kwargs: None,
    )
    newer = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-newer-executed-command"),
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        original_gate,
    )
    newer_record = handlers.service.get_job_record(newer["job_id"])
    assert newer_record is not None
    failure = deepcopy(historical.request.metadata["provider_failure_retry"])
    failure["final_failure_code"] = "background_generation_request_invalid"
    failure["attempts"][0]["failure_code"] = "background_generation_request_invalid"
    failure["reference_input_execution"]["failure_code"] = "background_generation_request_invalid"
    newer_record.request.metadata["provider_failure_retry"] = failure
    newer_record.status = ProductJobStatusValue.BLOCKED
    handlers.service.job_store.save(newer_record)

    created = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-after-executed-successor"),
    )

    assert created.get("job_id")
    assert created["metadata"].get("current_operation", {}).get("state") != "ambiguous_provider_request_hold"


def test_doc279_newer_current_job_suppresses_old_e32_hold(tmp_path, monkeypatch) -> None:
    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _create_opaque_block(handlers, provider, project, product_ids)
    original_gate = handlers.project_service._doc278_matching_opaque_provider_hold  # noqa: SLF001
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        lambda *_args, **_kwargs: None,
    )
    newer = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-newer-current-command"),
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        original_gate,
    )

    assert newer["status"] == ProductJobStatusValue.PLANNED.value
    repeated = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-after-current-successor"),
    )

    assert repeated.get("job_id")
    assert repeated["metadata"].get("current_operation", {}).get("state") != "ambiguous_provider_request_hold"
    assert provider.calls == 1


@pytest.mark.parametrize(
    "change",
    ["goal", "direction", "requested_count", "source", "locked_people", "route"],
)
def test_doc279_transparent_successor_changed_current_fact_fails_open(
    tmp_path,
    monkeypatch,
    change: str,
) -> None:
    handlers, project, product_ids, provider, historical, _newer = (
        _opaque_with_transparent_newer_planning_failure(tmp_path, monkeypatch)
    )
    payload = _browser_repeat_payload(product_ids, key=f"doc279-changed-after-transparent-{change}")

    if change == "goal":
        project_record = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
        project_record.user_goal = "Create a changed server-owned product direction."
        project_record.short_summary = project_record.user_goal
        handlers.project_service.project_store.save_project(project_record)
        payload["user_input"] = project_record.user_goal
    elif change == "direction":
        payload["user_input"] = "Keep the project goal but use a different explicit direction."
    elif change == "requested_count":
        payload["metadata"]["requested_image_count"] = 2
    elif change == "source":
        selected_id = historical.request.metadata[
            "professional_ecommerce_physical_product_projections"
        ]["1"]["selected_product_asset_ids"][0]
        selected_reference = next(
            item
            for item in handlers.get_project(project["project_id"])["project"]["reference_assets"]
            if item["asset_ref_id"] == selected_id and item["status"] == "active"
        )
        replacement = _ready_product_upload(
            handlers,
            filename="doc279-replacement-product.png",
            color=(110, 180, 210),
        )
        handlers.post_project_reference_remove(
            project["project_id"],
            selected_reference["reference_id"],
            {"plain_text": "Use the current server-admitted product original."},
        )
        _add_product_references(handlers, project["project_id"], [replacement])
    elif change == "locked_people":
        bindings = handlers.get_project_visual_asset_bindings(project["project_id"])["bindings"]
        assert len(bindings) == 1
        handlers.delete_project_visual_asset_binding(
            project["project_id"],
            bindings[0]["binding_id"],
            {"confirm_removal": True},
        )
    else:
        monkeypatch.setattr(settings, "default_image_provider", "doc279-other-provider")
        monkeypatch.setattr(settings, "default_image_model", "doc279-other-model")
        monkeypatch.setattr(settings, "openai_image_transport_profile", "hard-inputs-v2")
        assert (
            _configured_route_identity()
            != historical.request.metadata["provider_failure_retry"]["execution_audit"]["route_identity"]
        )

    created = handlers.post_project_job(project["project_id"], payload)

    assert created.get("job_id")
    assert created["status"] == ProductJobStatusValue.PLANNED.value
    assert created["metadata"].get("current_operation", {}).get("state") != "ambiguous_provider_request_hold"
    assert provider.calls == 1


def test_doc279_selected_continuation_change_fails_open_without_replaying_history(
    tmp_path,
    monkeypatch,
) -> None:
    """Doc265's explicit channel is a current create fact, never E33 metadata."""

    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    seed = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-continuation-seed"),
    )
    seed_output = _save_history_output(handlers, job_id=seed["job_id"], index=279)
    handlers.get_project(project["project_id"])
    continuation = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": seed_output.output_id,
            "source_type": "generated_selected",
            "use_policy": "style",
            "created_from_job_id": seed["job_id"],
            "created_from_output_id": seed_output.output_id,
        },
    )["reference"]
    _old, historical = _create_opaque_block(handlers, provider, project, product_ids)
    original_gate = handlers.project_service._doc278_matching_opaque_provider_hold  # noqa: SLF001
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        lambda *_args, **_kwargs: None,
    )
    newer = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-continuation-transparent-successor"),
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        original_gate,
    )
    newer_record = handlers.service.get_job_record(newer["job_id"])
    assert newer_record is not None
    _mark_server_transparent_predecessor_failure(handlers, project, newer_record)
    receipt = _seed_private_transparent_receipt(handlers, project, newer_record)
    assert receipt["selected_continuation_admissions_digest"] != _digest([])
    before = handlers.project_service._doc269_selected_continuation_admissions(  # noqa: SLF001
        handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    )
    assert len(before) == 1

    handlers.post_project_reference_remove(
        project["project_id"],
        continuation["reference_id"],
        {"plain_text": "Deliberately remove the selected continuation."},
    )
    after = handlers.project_service._doc269_selected_continuation_admissions(  # noqa: SLF001
        handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    )
    assert after == []
    created = _assert_e32_not_held(
        handlers,
        project,
        product_ids,
        key="doc279-after-selected-continuation-change",
    )

    assert created["job_id"] not in {historical.job_id, newer_record.job_id, ""}
    assert provider.calls == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "recomputed_private_digest_tamper",
        "foreign_terminal_job",
        "foreign_project",
        "outer_request_count",
        "terminal_attempt_audit",
    ],
)
def test_doc279_private_transparent_receipt_or_durable_execution_guard_fails_open(
    tmp_path,
    monkeypatch,
    mutation: str,
) -> None:
    handlers, project, product_ids, _provider, _historical, newer = (
        _opaque_with_transparent_newer_planning_failure(tmp_path, monkeypatch)
    )
    receipt = _private_receipts(handlers, project["project_id"])[0]
    if mutation == "recomputed_private_digest_tamper":
        receipt["command_binding_digest"] = "forged-but-recomputed-command-digest"
        receipt = _reseal_private_receipt(receipt)
    elif mutation == "foreign_terminal_job":
        receipt["terminal_job_id"] = "job_foreign_doc279_receipt"
        receipt = _reseal_private_receipt(receipt)
    elif mutation == "foreign_project":
        receipt["project_id"] = "project_foreign_doc279_receipt"
        receipt = _reseal_private_receipt(receipt)
    else:
        metadata = dict(newer.request.metadata or {})
        metadata["provider_failure_retry"] = {
            "reference_input_execution": {
                "operation": "image_edit",
                "outer_request_count": 1 if mutation == "outer_request_count" else 0,
            },
            "execution_audit": (
                _configured_route_identity() if mutation == "terminal_attempt_audit" else None
            ),
            "attempts": (
                [{
                    "attempt": 1,
                    "output_index": 1,
                    "status": "failed",
                    "classification": "non_retryable_provider_failure",
                    "failure_code": "planning_preflight_blocked",
                    "upstream_code": "provider_error",
                    "execution_audit": _configured_route_identity(),
                }]
                if mutation == "terminal_attempt_audit"
                else []
            ),
        }
        newer.request.metadata = metadata
        handlers.service.job_store.save(newer)
        receipt["outer_request_count"] = 1 if mutation == "outer_request_count" else 0
        receipt = _reseal_private_receipt(receipt)
    _replace_private_receipt(
        handlers,
        project["project_id"],
        receipt,
    )

    created = _assert_e32_not_held(
        handlers,
        project,
        product_ids,
        key=f"doc279-private-guard-{mutation}",
    )

    assert created["job_id"] not in {newer.job_id, ""}


def test_doc279_newer_doc271_policy_closure_has_precedence_over_old_e32(
    tmp_path,
    monkeypatch,
) -> None:
    """A policy closure is never transparent E33 history."""

    provider = _TerminalFailureProvider(
        failure_code="image_edit_invalid_request_unattributed",
        upstream_code="provider_error",
    )
    handlers, provider, project, product_ids, _faces = _fixture(tmp_path, provider=provider)
    _old, historical = _create_opaque_block(handlers, provider, project, product_ids)
    provider.failure_code = "provider_policy_blocked"
    provider.upstream_code = "content_policy_violation"
    original_gate = handlers.project_service._doc278_matching_opaque_provider_hold  # noqa: SLF001
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        lambda *_args, **_kwargs: None,
    )
    policy_job = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-newer-policy-closure"),
    )
    terminal = handlers.post_project_job_generate(project["project_id"], policy_job["job_id"])
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        original_gate,
    )
    assert terminal["status"] == ProductJobStatusValue.BLOCKED.value
    policy_record = handlers.service.get_job_record(policy_job["job_id"])
    assert policy_record is not None
    assert "provider_deliverability_closure_receipt" in policy_record.request.metadata

    held = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-policy-precedence-after-e32"),
    )

    assert not held.get("job_id")
    assert held["metadata"]["current_operation"]["state"] == "delivery_route_unavailable"
    assert historical.job_id != policy_record.job_id


def test_doc279_newer_delivered_job_suppresses_old_e32_hold(
    tmp_path,
    monkeypatch,
) -> None:
    """A later persisted pixel is authoritative even when its Job is not final."""

    handlers, _unused, project, product_ids, _faces, provider = _opaque_fixture(tmp_path)
    _old, historical = _create_opaque_block(handlers, provider, project, product_ids)
    original_gate = handlers.project_service._doc278_matching_opaque_provider_hold  # noqa: SLF001
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        lambda *_args, **_kwargs: None,
    )
    delivered = handlers.post_project_job(
        project["project_id"],
        _browser_repeat_payload(product_ids, key="doc279-newer-delivered-job"),
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc278_matching_opaque_provider_hold",
        original_gate,
    )
    output = _save_history_output(handlers, job_id=delivered["job_id"], index=280)
    assert handlers.service.output_store.get_output(output.output_id) is not None
    delivered_record = handlers.service.get_job_record(delivered["job_id"])
    assert delivered_record is not None
    delivered_record.status = ProductJobStatusValue.GENERATED
    handlers.service.job_store.save(delivered_record)

    created = _assert_e32_not_held(
        handlers,
        project,
        product_ids,
        key="doc279-after-newer-delivered-job",
    )

    assert created["job_id"] not in {historical.job_id, delivered["job_id"], ""}
