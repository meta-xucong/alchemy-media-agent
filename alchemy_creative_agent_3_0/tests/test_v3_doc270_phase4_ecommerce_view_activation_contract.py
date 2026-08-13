"""Phase 4A red contracts for Doc270 E-Commerce view-aware activation.

The fixtures use local Project Mode/Product API planning only.  They never
select a Provider, generate pixels, contact MCP, or mutate live records.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.project_mode import source_library
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceSourceType,
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
    _save_history_output,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    MOBILE_HTML,
    MOBILE_JS,
    DESKTOP_HTML,
    DESKTOP_JS,
    _browser_page,
    _needs_input_job,
    _needs_input_project,
)


_CAPABILITY = {
    "schema_version": "doc270_ecommerce_view_activation_capability_v1",
    "issuer": "v3_doc270_ecommerce_activation_registry",
    "capability_id": "doc270_ecommerce_view_activation",
    "capability_version": "doc270_phase4_ecommerce_view_activation_v1",
    "template_id": "ecommerce_template",
    "enabled": True,
}


def _fixture(tmp_path, *, count: int = 3):
    handlers, catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_ids = [
        _ready_product_upload(
            handlers,
            filename=f"phase4-source-{index}.png",
            color=(50 + 35 * index, 105 + 10 * index, 150 - 10 * index),
        )
        for index in range(count)
    ]
    _add_product_references(handlers, project["project_id"], product_ids)
    return handlers, catalog, project, product_ids


def _snapshot(handlers: Any, project_id: str) -> dict[str, Any]:
    project = handlers.project_service._require_project(project_id)  # noqa: SLF001
    return source_library.build_project_source_library(
        project_id=project.project_id,
        references=project.reference_assets,
        upload_lookup=handlers.service.get_uploaded_asset,
    )


def _association_id(handlers: Any, project_id: str, asset_id: str) -> str:
    project = handlers.project_service._require_project(project_id)  # noqa: SLF001
    return next(item.reference_id for item in project.reference_assets if item.asset_ref_id == asset_id)


def _identity(project_id: str, *, command_id: str = "phase4-command-1") -> dict[str, str]:
    value = {
        "schema_version": "doc270_ecommerce_command_identity_v1",
        "issuer": "v3_project_mode_ecommerce_command_registry",
        "capability_id": _CAPABILITY["capability_id"],
        "capability_version": _CAPABILITY["capability_version"],
        "project_id": project_id,
        "template_id": "ecommerce_template",
        "command_id": command_id,
        "command_plan_binding_digest": f"phase4-plan-{command_id}",
        "coalescing_nonce": f"phase4-nonce-{command_id}",
    }
    value["identity_digest"] = source_library.canonical_digest(value)
    return value


def _entry(
    *,
    project_id: str,
    snapshot: dict[str, Any],
    identity: dict[str, Any],
    selections: list[tuple[int, str, str]],
) -> dict[str, Any]:
    receipts: list[dict[str, Any]] = []
    for output_index, reference_id, asset_id in selections:
        source = next(item for item in snapshot["entries"] if item["reference_id"] == reference_id)
        receipt = {
            "schema_version": "doc270_reference_resolution_receipt_v1",
            "issuer": "v3_doc270_shadow_matcher",
            "project_id": project_id,
            "command_identity": deepcopy(identity),
            "command_plan_binding_digest": identity["command_plan_binding_digest"],
            "output_index": output_index,
            "output_identity": f"phase4-output-{output_index}",
            "requirement_nonce": f"phase4-nonce-{output_index}",
            "requirement_digest": f"phase4-requirement-{output_index}",
            "source_library_snapshot_digest": snapshot["snapshot_digest"],
            "state": "resolved",
            "maximum_sources": 1,
            "matched_references": [{
                "reference_id": reference_id,
                "asset_id": asset_id,
                "content_sha256": source["content_sha256"],
                "profile_digest": f"phase4-profile-{output_index}",
            }],
            "evidence_profile_digests": [f"phase4-profile-{output_index}"],
            "requirement_kind": {1: "object_front_presentation", 2: "object_rear_structure", 3: "object_detail"}.get(
                output_index,
                "object_rear_structure",
            ),
            "evidence_profile": {
                "subject_kind": "object_or_product",
                "view_kind": {1: "front", 2: "rear", 3: "detail_or_macro"}.get(output_index, "rear"),
                "affordances": [
                    {1: "object_shape", 2: "object_back_or_structure", 3: "object_detail"}.get(
                        output_index,
                        "object_back_or_structure",
                    )
                ],
            },
            "shadow_only": True,
        }
        receipt["receipt_digest"] = source_library.canonical_digest(receipt)
        receipts.append(receipt)
    value = {
        "schema_version": "doc270_ecommerce_phase4_registry_entry_v1",
        "issuer": "v3_doc270_ecommerce_view_registry",
        "capability_id": _CAPABILITY["capability_id"],
        "capability_version": _CAPABILITY["capability_version"],
        "project_id": project_id,
        "template_id": "ecommerce_template",
        "command_identity": deepcopy(identity),
        "source_library_snapshot_digest": snapshot["snapshot_digest"],
        "receipts": receipts,
    }
    value["registry_entry_digest"] = source_library.canonical_digest(value)
    return value


def _install_future_gate(monkeypatch, handlers: Any, value: dict[str, Any], identity: dict[str, Any]) -> None:
    """Future private seams; Phase 4A deliberately leaves them unconsumed."""

    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_view_activation_capability_lookup",
        lambda: deepcopy(_CAPABILITY),
        raising=False,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_command_identity_lookup",
        lambda **_kwargs: deepcopy(identity),
        raising=False,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_phase2_receipt_registry_lookup",
        lambda **_kwargs: deepcopy(value),
        raising=False,
    )


def _payload(product_ids: list[str], *, key: str, count: int = 1, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _job_payload(uploaded_asset_ids=product_ids, key=key)
    payload["metadata"] = {
        **payload["metadata"],
        "requested_image_count": count,
        **(metadata or {}),
    }
    return payload


def _admitted_ids(record: Any) -> list[str]:
    return [item["asset_id"] for item in record.request.metadata["professional_ecommerce_product_truth_admission"]["sources"]]


def test_doc270_phase4_absent_gate_preserves_complete_doc263_admission(tmp_path) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)

    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-no-gate"))
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert _admitted_ids(record) == product_ids
    assert "doc270_ecommerce_view_activation_receipts" not in record.request.metadata


def test_doc270_phase4_resolved_views_freeze_one_product_per_output_without_reducing_pool(tmp_path, monkeypatch) -> None:
    handlers, catalog, project, product_ids = _fixture(tmp_path)
    face_ids = _bind_locked_person_identity(handlers, catalog, project_id=project["project_id"])
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"])
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[
            (1, _association_id(handlers, project["project_id"], product_ids[0]), product_ids[0]),
            (2, _association_id(handlers, project["project_id"], product_ids[1]), product_ids[1]),
            (3, _association_id(handlers, project["project_id"], product_ids[2]), product_ids[2]),
        ],
    )
    _install_future_gate(monkeypatch, handlers, value, identity)

    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-front-rear-detail", count=3))
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert _admitted_ids(record) == product_ids
    receipts = record.request.metadata["doc270_ecommerce_view_activation_receipts"]
    assert [item["output_index"] for item in receipts] == [1, 2, 3]
    projections = record.request.metadata["professional_ecommerce_physical_product_projections"]
    assert projections["1"]["selected_product_asset_ids"] == [product_ids[0]]
    assert projections["2"]["selected_product_asset_ids"] == [product_ids[1]]
    assert projections["3"]["selected_product_asset_ids"] == [product_ids[2]]
    plans = record.request.metadata["physical_renderer_reference_plans"]
    assert plans["1"]["reference_image_asset_ids"][0] == product_ids[0]
    assert plans["2"]["reference_image_asset_ids"][0] == product_ids[1]
    assert plans["3"]["reference_image_asset_ids"][0] == product_ids[2]
    assert all(face_id not in str(receipts) for face_id in face_ids)


@pytest.mark.parametrize("mutation", ["stale_sha", "missing_file", "generated", "cross_project", "duplicate_output"])
def test_doc270_phase4_invalid_hard_receipt_closes_before_job_or_plan(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"])
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[0]), product_ids[0])],
    )
    if mutation == "stale_sha":
        value["receipts"][0]["matched_references"][0]["content_sha256"] = "f" * 64
    elif mutation == "missing_file":
        upload = handlers.service.get_uploaded_asset(product_ids[0])
        assert upload is not None
        Path(upload.file_path).unlink()
    elif mutation == "generated":
        value["receipts"][0]["matched_references"][0]["asset_id"] = "generated-review-output"
    elif mutation == "cross_project":
        value["project_id"] = "project_other"
    else:
        value["receipts"].append(deepcopy(value["receipts"][0]))
    _install_future_gate(monkeypatch, handlers, value, identity)

    before = list(handlers.project_service._require_project(project["project_id"]).job_ids)  # noqa: SLF001
    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key=f"phase4-invalid-{mutation}", metadata={
            "doc270_ecommerce_view_activation": True,
            "doc270_reference_resolution_receipts": value,
        }),
    )
    assert created["status"] == "blocked"
    assert created["metadata"]["current_operation"] == {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    assert handlers.project_service._require_project(project["project_id"]).job_ids == before  # noqa: SLF001
    public_text = str(created)
    for private in [product_ids[0], "f" * 64, "generated-review-output", "project_other"]:
        assert private not in public_text


def test_doc270_phase4_browser_fields_cannot_author_view_activation(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"], command_id="phase4-browser-forgery")
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[0]), product_ids[0])],
    )
    _install_future_gate(monkeypatch, handlers, value, identity)
    created = handlers.post_project_job(
        project["project_id"],
        _payload(
            product_ids,
            key="phase4-browser-forgery",
            metadata={
                "doc270_ecommerce_view_activation": True,
                "doc270_reference_resolution_receipts": {"asset_id": "browser-forged-asset"},
                "selected_product_asset_ids": ["browser-forged-asset"],
            },
        ),
    )
    assert created["status"] == "planned"
    public_text = str(created)
    assert "browser-forged-asset" not in public_text


def test_doc270_phase4_same_identity_returns_one_frozen_job_without_rematch(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"])
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[2]), product_ids[2])],
    )
    calls = {"registry": 0}
    _install_future_gate(monkeypatch, handlers, value, identity)
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_phase2_receipt_registry_lookup",
        lambda **_kwargs: calls.__setitem__("registry", calls["registry"] + 1) or deepcopy(value),
        raising=False,
    )

    first = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-replay"))
    second = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-replay", metadata={"forged_selected_product_ids": product_ids[:2]}))
    assert second["job_id"] == first["job_id"]
    assert calls["registry"] == 1
    handlers.get_project(project["project_id"])
    handlers.get_job(first["job_id"])
    assert calls["registry"] == 1


def test_doc270_phase4_keeps_generated_continuation_separate_and_no_product_prompt_only(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    initial = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-history"))
    output = _save_history_output(handlers, job_id=initial["job_id"], index=41)
    selected = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": output.output_id,
            "source_type": ProjectReferenceSourceType.GENERATED_SELECTED,
            "created_from_job_id": initial["job_id"],
            "created_from_output_id": output.output_id,
            "use_policy": "style",
        },
    )

    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"], command_id="phase4-continuation")
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[1]), product_ids[1])],
    )
    _install_future_gate(monkeypatch, handlers, value, identity)
    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-continuation"))
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert selected["reference"]["source_type"] == "generated_selected"
    assert output.output_id not in str(record.request.metadata.get("doc270_ecommerce_view_activation_receipts", []))
    assert initial["job_id"] in handlers.project_service._require_project(project["project_id"]).job_ids  # noqa: SLF001

    empty_project = _project(handlers)
    prompt_only = handlers.post_project_job(empty_project["project_id"], _payload([], key="phase4-no-product"))
    assert prompt_only["status"] == "planned"
    assert prompt_only["metadata"].get("ecommerce_text_to_image_fallback") is True


def test_doc270_phase4_non_apparel_typed_view_evidence_selects_only_matching_original(tmp_path, monkeypatch) -> None:
    """A non-apparel object uses typed view evidence, never category heuristics."""

    handlers, _catalog, project, product_ids = _fixture(tmp_path, count=3)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"], command_id="phase4-mug-rear")
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[1]), product_ids[1])],
    )
    value["receipts"][0]["requirement_kind"] = "object_rear_structure"
    value["receipts"][0]["evidence_profile"] = {
        "subject_kind": "object_or_product",
        "view_kind": "rear",
        "affordances": ["object_back_or_structure"],
        "semantic_domain": "ceramic_mug",
    }
    value["receipts"][0]["receipt_digest"] = source_library.canonical_digest(
        {key: item for key, item in value["receipts"][0].items() if key != "receipt_digest"}
    )
    value["registry_entry_digest"] = source_library.canonical_digest(
        {key: item for key, item in value.items() if key != "registry_entry_digest"}
    )
    _install_future_gate(monkeypatch, handlers, value, identity)

    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-mug-rear"))
    assert created["status"] == "planned"
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    receipts = record.request.metadata.get("doc270_ecommerce_view_activation_receipts")
    assert receipts is not None
    assert receipts[0]["matched_references"][0]["asset_id"] == product_ids[1]
    assert receipts[0]["evidence_profile"]["subject_kind"] == "object_or_product"
    assert receipts[0]["evidence_profile"]["view_kind"] == "rear"
    assert product_ids[0] not in str(receipts)
    assert product_ids[2] not in str(receipts)


def test_doc270_phase4_desktop_terminal_product_review_action_is_local_and_not_preparing() -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                ({ project, created }) => {
                  window.__doc263ServerProject = project;
                  window.__doc263CreateJobResponse = created;
                  v3State.currentProject = project;
                  v3State.currentJob = created;
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                  renderV3ProjectDetail();
                  document.querySelectorAll('[hidden]').forEach((node) => { node.hidden = false; });
                }
                """,
                {"project": project, "created": created},
            )
            assert page.locator("[data-v3-project-action='review_product_inputs']").count() == 1
            text_content = page.locator("#v3ProjectNextActions").inner_text()
            assert "准备生成" not in text_content
            assert "生成中" not in text_content
            page.locator("[data-v3-project-action='review_product_inputs']").click()
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
            assert page.evaluate("document.body.dataset.v3ActiveSurface || ''") != ""
        finally:
            browser.close()


def test_doc270_phase4_mobile_terminal_product_review_action_is_local_and_not_preparing() -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                ({ project, created }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  window.__doc263ServerProject = project;
                  window.__doc263CreateJobResponse = created;
                  mobileV3State.currentProject = project;
                  mobileV3State.currentJob = created;
                  mobileV3State.projects = [project];
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [];
                  mobileV3State.outputsLoaded = true;
                  renderMobileV3ProjectCurrentOperation(project);
                  openMobileSurface("v3-project-detail");
                }
                """,
                {"project": project, "created": created},
            )
            assert page.locator("[data-mobile-v3-project-action='review_product_inputs']").count() == 1
            text_content = page.locator("#mobileV3ProjectCurrentOperation").inner_text()
            assert "准备中" not in text_content
            assert "进行中" not in text_content
            page.locator("[data-mobile-v3-project-action='review_product_inputs']").click()
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
            assert page.evaluate("document.body.dataset.mobileActiveSurface || ''") != ""
        finally:
            browser.close()
