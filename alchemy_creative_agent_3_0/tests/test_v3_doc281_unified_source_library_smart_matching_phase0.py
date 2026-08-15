"""Phase 0 red contracts for Doc281 unified source-library activation.

These tests use only local in-memory stores and deterministic uploaded image
fixtures. They intentionally assert the next server-owned behavior before its
runtime implementation exists. They never select a live Provider, contact MCP
or ImageGen, write a real Job, or deploy a service.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api.contracts import V3AssetUploadStatusValue
from alchemy_creative_agent_3_0.app.project_mode import source_library
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceSourceType,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _project,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
    _job_payload,
    _save_history_output,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_phase3_general_activation_contract import (
    _general_payload,
    _general_project,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_phase2_shadow_matcher_contract import (
    _entry as _shadow_entry,
    _evidence as _shadow_evidence,
    _requirement as _shadow_requirement,
    _resolve as _shadow_resolve,
    _server_context as _shadow_server_context,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_phase4_ecommerce_view_activation_contract import (
    _count_planning_and_dispatch,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_project_source_library_reference_matching import (
    _public_library_project,
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
    _ready_product_upload,
)


def _public_safe(value: Any) -> None:
    forbidden = (
        "asset_id",
        "reference_id",
        "sha",
        "digest",
        "path",
        "file",
        "prompt",
        "provider",
        "exception",
        "traceback",
    )
    if isinstance(value, dict):
        for key, nested in value.items():
            assert not any(fragment in str(key).lower() for fragment in forbidden)
            _public_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _public_safe(nested)


def _general_server_held_match(
    handlers: Any,
    project: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    asset_id: str,
    kind: str,
    affordance: str,
    view_kind: str,
    subject_kind: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build trusted test evidence and prove its matcher selection before activation."""

    candidate = _shadow_entry(snapshot, asset_id)
    requirement = _shadow_requirement(
        project_id=project["project_id"],
        output_index=1,
        kind=kind,
        source_snapshot_digest=snapshot["snapshot_digest"],
    )
    evidence = {
        candidate["reference_id"]: _shadow_evidence(
            candidate,
            project_id=project["project_id"],
            affordance=affordance,
            view_kind=view_kind,
            subject_kind=subject_kind,
        )
    }
    context = _shadow_server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference=evidence,
    )
    receipt = _shadow_resolve(server_context=context)
    assert receipt["state"] == "resolved"
    assert [item["asset_id"] for item in receipt["matched_references"]] == [asset_id]
    # Phase 6 must consume these private server lookups, never request metadata.
    handlers.project_service.doc281_general_trusted_match_context = context  # type: ignore[attr-defined]
    handlers.project_service.doc281_general_expected_receipt = receipt  # type: ignore[attr-defined]
    return candidate, receipt


@pytest.mark.parametrize(
    ("user_input", "asset_index", "kind", "affordance", "view_kind", "subject_kind"),
    [
        ("Create an object image that needs the detail original.", 0, "object_rear_structure", "object_back_or_structure", "rear", "object_or_product"),
        ("Create a person image with optional environment inspiration.", 1, "person_environment_context", "environment", "environment_wide", "person"),
        ("Create a scene image using a brand or graphic source.", 2, "brand_scene_material", "logo_or_mark", "packaging", "brand_or_graphic"),
    ],
)
def test_doc281_general_command_freezes_the_server_held_smart_match_across_domains(
    tmp_path,
    user_input: str,
    asset_index: int,
    kind: str,
    affordance: str,
    view_kind: str,
    subject_kind: str,
) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    candidate, receipt = _general_server_held_match(
        handlers,
        project,
        snapshot,
        asset_id=asset_ids[asset_index],
        kind=kind,
        affordance=affordance,
        view_kind=view_kind,
        subject_kind=subject_kind,
    )

    created = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": user_input,
            "metadata": {
                "selected_original_asset_ids": ["browser-never-selects"],
                "source_evidence_profile": {"view_kind": "browser-never-certifies"},
            },
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    activation = record.request.metadata["doc270_general_source_activation_receipts"][0]
    assert activation["state"] == "activated_resolved"
    assert activation["source_receipt_digest"] == receipt["receipt_digest"]
    projection = record.request.metadata["doc270_general_original_source_projection"]
    assert [item["reference_id"] for item in projection["sources"]] == [candidate["reference_id"]]
    assert record.request.uploaded_asset_ids == [candidate["asset_id"]]
    assert "browser-never-selects" not in record.request.uploaded_asset_ids


def test_doc281_general_optional_uncertainty_is_prompt_only_and_never_needs_input(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a prompt-only General image without project originals.",
            "primary_template_id": "general_template",
        }
    )["project"]

    created = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": "Use an optional uncertain scene original when appropriate.",
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert record.request.metadata.get("doc270_general_source_activation_receipts") == [
        {"state": "prompt_only"}
    ]
    assert created["status"] == "planned"
    assert "current_operation" not in created["metadata"]


@pytest.mark.parametrize("mutation", ["forged_requirement", "cross_project", "stale_snapshot", "wrong_evidence"])
def test_doc281_general_activation_rejects_forged_server_boundary_inputs(tmp_path, mutation: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    candidate, receipt = _general_server_held_match(
        handlers, project, snapshot, asset_id=asset_ids[0], kind="object_rear_structure",
        affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product",
    )
    hostile = deepcopy(receipt)
    if mutation == "forged_requirement":
        hostile["requirement_digest"] = "f" * 64
    elif mutation == "cross_project":
        hostile["project_id"] = "project-other"
    elif mutation == "stale_snapshot":
        hostile["source_library_snapshot_digest"] = "e" * 64
    else:
        hostile["matched_references"][0]["content_sha256"] = "d" * 64
    hostile["receipt_digest"] = source_library.canonical_digest(
        {key: value for key, value in hostile.items() if key != "receipt_digest"}
    )
    handlers.project_service.doc281_general_expected_receipt = hostile  # type: ignore[attr-defined]

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert record.request.metadata.get("doc270_general_source_activation_receipts") == [
        {"state": "receipt_invalid"}
    ]
    assert record.request.uploaded_asset_ids == []
    assert "doc270_general_original_source_projection" not in record.request.metadata
    assert candidate["asset_id"] not in str(handlers.get_job(created["job_id"]))


@pytest.mark.parametrize(
    ("html_path", "script_path", "mobile"),
    [(DESKTOP_HTML, DESKTOP_JS, False), (MOBILE_HTML, MOBILE_JS, True)],
)
def test_doc281_terminal_ui_clears_stale_progress_and_discloses_only_safe_used_sources(
    html_path: Path,
    script_path: Path,
    mobile: bool,
) -> None:
    project = _public_library_project(ecommerce=True)
    project["metadata"]["current_operation"] = {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    project["metadata"]["doc281_used_source_disclosures"] = [{
        "output_label": "Output 1",
        "sources": [{"category": "project_original", "label": "Selected original"}],
    }]
    created = {"job_id": "", "status": "blocked", "metadata": {"current_operation": project["metadata"]["current_operation"]}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            if mobile:
                page.evaluate(
                    """({ project, created }) => {
                      ensureMobileLayers(); setupMobileV3Adapter();
                      mobileV3State.currentProject = project; mobileV3State.currentJob = created;
                      mobileV3State.projects = [project]; mobileV3State.selectedTemplate = 'ecommerce_template';
                      mobileV3State.busy = true; mobileV3State.progressStageKey = 'planning';
                      mobileV3State.progressTimer = window.setTimeout(() => {}, 1000);
                      renderMobileV3ProjectCurrentOperation(project); renderMobileV3ReferenceBoard(project);
                    }""",
                    {"project": project, "created": created},
                )
                terminal = page.locator("#mobileV3ProjectCurrentOperation")
                board = page.locator("#mobileV3ReferenceBoard")
                action = "[data-mobile-v3-project-action='review_product_inputs']"
                cleared = "mobileV3State.busy === false && mobileV3State.progressTimer === null"
            else:
                page.evaluate(
                    """({ project, created }) => {
                      v3State.currentProject = project; v3State.currentJob = created;
                      v3State.loading = true; v3State.progressStageKey = 'planning';
                      v3State.progressTimer = window.setTimeout(() => {}, 1000);
                      renderV3ProjectDetail(); renderV3UsefulReferences();
                    }""",
                    {"project": project, "created": created},
                )
                terminal = page.locator("#v3ProjectNextActions")
                board = page.locator("#v3UsefulReferenceBoard")
                action = "[data-v3-project-action='review_product_inputs']"
                cleared = "v3State.loading === false && v3State.progressTimer === null"
            assert page.locator(action).count() == 1
            assert "准备" not in terminal.inner_text()
            assert page.evaluate(cleared) is True
            text = board.inner_text()
            assert "项目原始素材" in text and "人物视觉资产" in text
            assert "已选延续方向" in text and "生成与复核历史" in text
            assert "Selected original" in text
            assert all(token not in text.lower() for token in ("asset_id", "digest", "path", "prompt", "provider"))
        finally:
            browser.close()


@pytest.mark.parametrize("fault", ["not_ready", "role_drift", "file_missing", "digest_drift"])
def test_doc281_active_historical_product_drift_closes_once_with_sanitized_terminal_operation(
    tmp_path,
    fault: str,
    monkeypatch,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers,
        filename=f"doc281-product-{fault}.png",
        color=(95, 125, 165),
    )
    _add_product_references(handlers, project["project_id"], [product_id])
    upload = handlers.service.get_uploaded_asset(product_id)
    assert upload is not None
    if fault == "not_ready":
        handlers.service.asset_store._save_record(  # noqa: SLF001
            upload.model_copy(update={"status": V3AssetUploadStatusValue.STORED})
        )
    elif fault == "role_drift":
        handlers.service.asset_store._save_record(  # noqa: SLF001
            upload.model_copy(update={"role": "face_reference"})
        )
    if fault == "file_missing":
        Path(str(upload.file_path)).unlink()
    elif fault == "digest_drift":
        Path(str(upload.file_path)).write_bytes(b"doc281-current-sha-drift")

    before_job_ids = list(handlers.project_service._require_project(project["project_id"]).job_ids)  # noqa: SLF001
    calls = _count_planning_and_dispatch(monkeypatch, handlers)
    first = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc281-drift-{fault}"),
    )
    second = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc281-drift-{fault}"),
    )
    assert first.get("job_id") in (None, "")
    assert second.get("job_id") in (None, "")
    assert first["status"] == "blocked"
    assert handlers.project_service._require_project(project["project_id"]).job_ids == before_job_ids  # noqa: SLF001
    assert calls == {"plan": 0, "dispatch": 0}
    operation = first["metadata"]["current_operation"]
    assert operation["state"] == "needs_input"
    assert operation["terminal"] is True
    assert operation == second["metadata"]["current_operation"]
    assert handlers.get_project(project["project_id"])["metadata"]["current_operation"] == operation
    _public_safe(operation)


def test_doc281_explicit_continuation_and_history_never_enter_general_original_match_projection(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    _general_server_held_match(
        handlers, project, snapshot, asset_id=asset_ids[1], kind="object_rear_structure",
        affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product",
    )
    history = _save_history_output(handlers, job_id="doc281-history", index=281)
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": history.output_id,
            "source_type": "generated_selected",
            "created_from_job_id": "doc281-history",
            "created_from_output_id": history.output_id,
            "use_policy": "style",
        },
    )

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    projection = record.request.metadata["doc270_general_original_source_projection"]
    selected = [item["asset_id"] for item in projection["sources"]]
    assert set(selected).issubset(set(asset_ids))
    assert history.output_id not in selected
    assert all(
        reference.source_type != ProjectReferenceSourceType.GENERATED_SELECTED
        or reference.asset_ref_id != history.output_id
        or reference.use_policy == ProjectReferenceUsePolicy.STYLE
        for reference in handlers.project_service._require_project(project["project_id"]).reference_assets  # noqa: SLF001
    )


def test_doc281_new_general_command_replaces_old_terminal_presentation_without_history_reselection(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    _general_server_held_match(
        handlers, project, snapshot, asset_id=asset_ids[0], kind="object_rear_structure",
        affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product",
    )
    first = handlers.post_project_job(project["project_id"], _general_payload())
    first_record = handlers.service.get_job_record(first["job_id"])
    assert first_record is not None
    first_projection = deepcopy(first_record.request.metadata["doc270_general_original_source_projection"])

    second = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": "Create a distinct new image from the current request only.",
        },
    )
    second_record = handlers.service.get_job_record(second["job_id"])
    assert second_record is not None
    assert second["job_id"] != first["job_id"]
    assert handlers.get_project(project["project_id"])["metadata"].get("current_operation") is None
    second_projection = second_record.request.metadata["doc270_general_original_source_projection"]
    assert first_projection["state"] == "activated_resolved"
    assert second_projection["state"] == "activated_resolved"
    assert set(item["asset_id"] for item in second_projection["sources"]).issubset(set(asset_ids))


def test_doc281_phase0_contract_keeps_runtime_and_provider_code_unchanged() -> None:
    """Guard the Phase 0 scope: this test module must not imply a provider call."""

    assert Path(__file__).name == "test_v3_doc281_unified_source_library_smart_matching_phase0.py"
