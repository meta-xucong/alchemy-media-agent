"""Phase 1 contracts for Doc270 source-library reference matching.

The fixture follows the public Project Mode/Product API construction path with
local in-memory stores and the deterministic E-Commerce Brain double.  It
never dispatches a generation request, selects an app Provider, contacts MCP
or ImageGen, or writes a live project/job.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.reference_projection import (
    ProductTruthAdmission,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import V3AssetUploadStatusValue
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
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceAsset,
    ProjectReferenceSourceType,
    ProjectReferenceStatus,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
    _ecommerce_project,
)


def _fixture(tmp_path):
    handlers, catalog = _handlers(tmp_path)
    ecommerce_project = _project(handlers)
    product_ids = [
        _ready_product_upload(
            handlers,
            filename=f"doc270-source-{view}.png",
            color=(70 + index * 25, 120, 160),
        )
        for index, view in enumerate(("front", "side", "rear", "detail"))
    ]
    _add_product_references(handlers, ecommerce_project["project_id"], product_ids)
    face_output_ids = _bind_locked_person_identity(
        handlers,
        catalog,
        project_id=ecommerce_project["project_id"],
    )
    history_output = _save_history_output(
        handlers,
        job_id="doc270-history-job",
        index=71,
    )
    return handlers, ecommerce_project, product_ids, face_output_ids, history_output.output_id


def _association_id(handlers, project_id: str, asset_id: str) -> str:
    project = handlers.project_service._require_project(project_id)  # noqa: SLF001
    return next(
        reference.reference_id
        for reference in project.reference_assets
        if reference.asset_ref_id == asset_id
    )


def _assert_public_safe(value: Any) -> None:
    forbidden = (
        "sha",
        "digest",
        "path",
        "file",
        "provider",
        "brain",
        "prompt",
        "asset_id",
        "output_id",
        "profile",
        "analysis",
        "receipt",
    )
    if isinstance(value, dict):
        for key, nested in value.items():
            assert not any(fragment in str(key).lower() for fragment in forbidden)
            _assert_public_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_public_safe(nested)


def test_doc270_public_source_library_contains_only_active_project_upload_originals(tmp_path) -> None:
    handlers, project, product_ids, face_output_ids, history_output_id = _fixture(tmp_path)

    response = handlers.get_project(project["project_id"])
    library = response["metadata"]["project_source_library"]

    assert library["schema_version"] == "doc270_project_source_library_public_v1"
    assert set(library) == {"schema_version", "entries"}
    assert [entry["association_reference_id"] for entry in library["entries"]] == [
        _association_id(handlers, project["project_id"], asset_id) for asset_id in product_ids
    ]
    assert all(entry["availability_state"] == "ready_verified" for entry in library["entries"])
    assert all(entry["automatic_use_eligible"] is True for entry in library["entries"])
    assert all(entry["ecommerce_product_eligible"] is True for entry in library["entries"])
    _assert_public_safe(library)
    public_text = str(library)
    assert not any(value in public_text for value in [*face_output_ids, history_output_id, *product_ids])


def test_doc270_ecommerce_command_freezes_one_server_binding_receipt_per_output(tmp_path) -> None:
    handlers, project, product_ids, face_output_ids, _history_output_id = _fixture(tmp_path)
    payload = _job_payload(uploaded_asset_ids=product_ids, key="doc270-match-receipt")
    payload["metadata"]["requested_image_count"] = 2
    payload["user_input"] = "Create one front product presentation and one rear construction view."

    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    receipts = record.request.metadata["doc270_source_library_binding_receipts"]

    assert [receipt["output_index"] for receipt in receipts] == [1, 2]
    assert all(receipt["project_id"] == project["project_id"] for receipt in receipts)
    assert all(receipt["state"] == "bound_observe_only" for receipt in receipts)
    assert all(receipt["receipt_digest"] for receipt in receipts)
    assert all(
        receipt["selected_source_asset_ids"]
        and set(receipt["selected_source_asset_ids"]).issubset(set(product_ids))
        for receipt in receipts
    )
    assert all(
        not set(receipt["selected_source_asset_ids"]).intersection(set(face_output_ids))
        for receipt in receipts
    )
    assert record.request.metadata["professional_ecommerce_physical_product_projections"]
    assert record.request.metadata["physical_renderer_reference_plans"]
    assert record.request.metadata["doc270_project_source_library"]["snapshot_digest"]


def test_doc270_direct_ecommerce_product_api_path_keeps_legacy_contract_without_snapshot(
    tmp_path,
    monkeypatch,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers,
        filename="doc270-direct-product.png",
        color=(85, 125, 165),
    )
    _add_product_references(handlers, project["project_id"], [product_id])
    original = handlers.service._bind_doc270_source_library_binding_receipts  # noqa: SLF001

    def unexpected_doc270_binding(**_kwargs):
        raise AssertionError("Doc270 binder must not run for direct Product API create")

    monkeypatch.setattr(handlers.service, "_bind_doc270_source_library_binding_receipts", unexpected_doc270_binding)
    direct = handlers.service.create_project_ecommerce_job(
        CreateCreativeJobRequest(
            user_input="Generate a clean product image from the current project facts.",
            uploaded_asset_ids=[product_id],
            metadata={},
        ),
        canonical_product_asset_ids=[product_id],
    )
    assert direct.job_id
    assert original is not None
    record = handlers.service.get_job_record(direct.job_id)
    assert record is not None and record.planning_result is not None
    assert "doc270_source_library_binding_receipts" not in record.request.metadata
    assert "doc270_source_library_binding_receipts" not in record.planning_result.metadata
    assert all(
        "doc270_source_library_binding_receipts" not in plan.metadata
        for plan in record.planning_result.generation_plans
    )


def _binding_inputs(handlers, project_id: str, product_ids: list[str]):
    created = handlers.post_project_job(
        project_id,
        _job_payload(uploaded_asset_ids=product_ids, key="doc270-binding-verifier"),
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    metadata = deepcopy(record.request.metadata)
    admission = ProductTruthAdmission.from_mapping(
        metadata["professional_ecommerce_product_truth_admission"]
    )
    return metadata, admission, deepcopy(metadata["professional_ecommerce_physical_product_projections"])


@pytest.mark.parametrize("fault", ["profile_sha", "analysis_reference", "duplicate_reference", "missing_reference"])
def test_doc270_internal_forged_library_snapshot_fails_before_receipt_freeze(
    tmp_path,
    monkeypatch,
    fault: str,
) -> None:
    handlers, project, product_ids, _face_output_ids, _history_output_id = _fixture(tmp_path)
    metadata, admission, projections = _binding_inputs(handlers, project["project_id"], product_ids)
    forged = deepcopy(metadata["doc270_project_source_library"])
    if fault == "profile_sha":
        forged["entries"][0]["profile"]["content_sha256"] = "0" * 64
    elif fault == "analysis_reference":
        forged["entries"][0]["analysis_receipt"]["reference_id"] = "forged-reference"
    elif fault == "duplicate_reference":
        forged["entries"][1]["reference_id"] = forged["entries"][0]["reference_id"]
    else:
        forged["entries"] = forged["entries"][1:]
    metadata["doc270_project_source_library"] = forged
    monkeypatch.setattr(
        handlers.service,
        "doc270_source_library_snapshot_lookup",
        lambda _project_id: forged,
    )

    with pytest.raises(ValueError, match="doc270_source_library"):
        handlers.service._bind_doc270_source_library_binding_receipts(  # noqa: SLF001
            metadata=metadata,
            admission=admission,
            projections=projections,
        )


def test_doc270_file_drift_fails_closed_and_historical_job_receipt_is_not_recomputed(tmp_path) -> None:
    handlers, project, product_ids, _face_output_ids, _history_output_id = _fixture(tmp_path)
    metadata, admission, projections = _binding_inputs(handlers, project["project_id"], product_ids)
    before = deepcopy(metadata["doc270_source_library_binding_receipts"])
    first_record = handlers.service.get_job_record(admission.job_id)
    assert first_record is not None

    upload = handlers.service.get_uploaded_asset(product_ids[0])
    assert upload is not None
    Path(str(upload.file_path)).write_bytes(b"doc270-test-file-drift")
    current_library = handlers.project_service._doc270_project_source_library_by_id(project["project_id"])  # noqa: SLF001
    metadata["doc270_project_source_library"] = current_library
    with pytest.raises(ValueError, match="doc270_source_library_admission_mismatch"):
        handlers.service._bind_doc270_source_library_binding_receipts(  # noqa: SLF001
            metadata=metadata,
            admission=admission,
            projections=projections,
        )

    handlers.get_project(project["project_id"])
    persisted = handlers.service.get_job_record(admission.job_id)
    assert persisted is not None
    assert persisted.request.metadata["doc270_source_library_binding_receipts"] == before


def test_doc270_general_prompt_only_has_an_empty_library_but_no_ecommerce_receipt(tmp_path) -> None:
    handlers, _project_record, _product_ids, _face_output_ids, _history_output_id = _fixture(tmp_path)
    general = handlers.post_projects(
        {"user_goal": "Make a simple prompt-only scene.", "primary_template_id": "general_template"}
    )["project"]
    created = handlers.post_project_job(
        general["project_id"],
        {
            "template_id": "general_template",
            "user_input": general["user_goal"],
            "uploaded_asset_ids": [],
            "metadata": {},
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert "doc270_project_source_library" not in record.request.metadata
    assert "doc270_source_library_binding_receipts" not in record.request.metadata
    library = handlers.get_project(general["project_id"])["metadata"]["project_source_library"]
    assert library["entries"] == []


def test_doc270_general_uploaded_original_is_cataloged_while_visual_assets_and_history_are_excluded(tmp_path) -> None:
    handlers, ecommerce_project, _product_ids, _face_output_ids, _history_output_id = _fixture(tmp_path)
    general = handlers.post_projects(
        {"user_goal": "Create a scene from one original.", "primary_template_id": "general_template"}
    )["project"]
    upload_id = _ready_product_upload(
        handlers,
        filename="doc270-general-original.png",
        color=(35, 95, 155),
    )
    handlers.post_project_reference(
        general["project_id"],
        {"asset_ref_id": upload_id, "source_type": "uploaded", "use_policy": "style"},
    )
    uploaded = handlers.service.get_uploaded_asset(upload_id)
    assert uploaded is not None
    handlers.service.asset_store._save_record(  # noqa: SLF001
        uploaded.model_copy(update={"role": "general"})
    )
    people_bindings = handlers.get_project_visual_asset_bindings(ecommerce_project["project_id"])
    visual_asset_id = people_bindings["bindings"][0]["visual_asset_id"]
    handlers.post_project_visual_asset_binding(
        general["project_id"],
        {"visual_asset_id": visual_asset_id, "confirm_binding": True},
    )
    history = _save_history_output(handlers, job_id="doc270-general-history", index=72)
    record = handlers.project_service._require_project(general["project_id"])  # noqa: SLF001
    record.reference_assets.append(
        ProjectReferenceAsset(
            reference_id="doc270-general-history-reference",
            project_id=record.project_id,
            source_type=ProjectReferenceSourceType.GENERATED_SELECTED,
            asset_ref_id=history.output_id,
            preview_url=history.download_url,
            created_at="2026-08-13T00:00:00+00:00",
            status=ProjectReferenceStatus.INACTIVE,
            use_policy=ProjectReferenceUsePolicy.STYLE,
            created_from_job_id=history.job_id,
            created_from_output_id=history.output_id,
        )
    )
    handlers.project_service.project_store.save_project(record)

    library = handlers.get_project(general["project_id"])["metadata"]["project_source_library"]
    assert [entry["association_reference_id"] for entry in library["entries"]] == [
        _association_id(handlers, general["project_id"], upload_id)
    ]
    entry = library["entries"][0]
    assert entry["availability_state"] == "ready_verified"
    assert entry["automatic_use_eligible"] is True
    assert entry["ecommerce_product_eligible"] is False
    _assert_public_safe(library)
    assert history.output_id not in str(library)
    assert visual_asset_id not in str(library)

    created = handlers.post_project_job(
        general["project_id"],
        {
            "template_id": "general_template",
            "user_input": general["user_goal"],
            "uploaded_asset_ids": [upload_id],
            "metadata": {},
        },
    )
    job = handlers.service.get_job_record(created["job_id"])
    assert job is not None
    assert "doc270_source_library_binding_receipts" not in job.request.metadata


def test_doc270_cross_project_or_browser_forged_asset_never_enters_current_catalog(tmp_path) -> None:
    handlers, project, _product_ids, _face_output_ids, _history_output_id = _fixture(tmp_path)
    other = handlers.post_projects(
        {"user_goal": "A separate project.", "primary_template_id": "general_template"}
    )["project"]
    foreign_id = _ready_product_upload(
        handlers,
        filename="doc270-foreign-original.png",
        color=(45, 105, 165),
    )
    handlers.post_project_reference(
        other["project_id"],
        {"asset_ref_id": foreign_id, "source_type": "uploaded", "use_policy": "style"},
    )
    payload = _job_payload(uploaded_asset_ids=[], key="doc270-foreign-forged")
    payload["metadata"]["doc270_project_source_library"] = {
        "project_id": project["project_id"],
        "entries": [{"asset_id": foreign_id}],
    }
    handlers.post_project_job(project["project_id"], payload)

    library = handlers.get_project(project["project_id"])["metadata"]["project_source_library"]
    assert _association_id(handlers, other["project_id"], foreign_id) not in {
        item["association_reference_id"] for item in library["entries"]
    }


@pytest.mark.parametrize("fault", ["not_ready", "role_drift", "file_missing", "digest_drift"])
def test_doc270_ineligible_product_association_is_hidden_and_ecommerce_still_closes_input(
    tmp_path,
    fault: str,
) -> None:
    handlers, project, product_ids, _face_output_ids, _history_output_id = _fixture(tmp_path)
    affected_id = product_ids[0]
    record = handlers.service.get_uploaded_asset(affected_id)
    assert record is not None
    if fault == "not_ready":
        handlers.service.asset_store._save_record(  # noqa: SLF001
            record.model_copy(update={"status": V3AssetUploadStatusValue.STORED})
        )
    elif fault == "role_drift":
        handlers.service.asset_store._save_record(  # noqa: SLF001
            record.model_copy(update={"role": "face_reference"})
        )
    elif fault == "file_missing":
        Path(str(record.file_path)).unlink()
    else:
        Path(str(record.file_path)).write_bytes(b"doc270-digest-drift")

    project_view = handlers.get_project(project["project_id"])
    entries = project_view["metadata"]["project_source_library"]["entries"]
    by_association = {entry["association_reference_id"]: entry for entry in entries}
    affected_association = _association_id(handlers, project["project_id"], affected_id)
    assert affected_association in by_association
    assert by_association[affected_association]["automatic_use_eligible"] is False
    assert by_association[affected_association]["ecommerce_product_eligible"] is False
    assert by_association[affected_association]["availability_state"] in {
        "upload_not_ready",
        "file_missing",
        "content_drift",
        "role_or_channel_invalid",
    }
    assert {
        _association_id(handlers, project["project_id"], asset_id) for asset_id in product_ids[1:]
    }.issubset(by_association)

    status = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc270-ineligible-{fault}"),
    )
    assert status["status"] == "blocked"
    operation = status["metadata"]["current_operation"]
    assert operation["state"] == "needs_input"
    assert status["job_id"]


def test_doc270_browser_metadata_cannot_author_match_or_replace_channel_selection(tmp_path) -> None:
    handlers, project, product_ids, face_output_ids, history_output_id = _fixture(tmp_path)
    payload = _job_payload(uploaded_asset_ids=product_ids, key="doc270-forged-match")
    payload["metadata"].update(
        {
            "doc270_source_library_binding_receipts": [
                {
                    "output_index": 1,
                    "state": "resolved",
                    "matched_source_asset_ids": [history_output_id, face_output_ids[0]],
                    "receipt_digest": "browser-authored",
                }
            ],
            "source_evidence_profile": {"view_kind": "rear", "confidence": "certain"},
        }
    )

    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    receipt = record.request.metadata["doc270_source_library_binding_receipts"][0]

    assert receipt["authority"] == "v3_project_source_library"
    assert receipt["selected_source_asset_ids"] != [history_output_id, face_output_ids[0]]
    assert set(receipt["selected_source_asset_ids"]).issubset(set(product_ids))
    assert "source_evidence_profile" not in receipt
    assert record.request.metadata["professional_ecommerce_physical_product_projections"]


def test_doc270_general_and_inactive_photography_do_not_consume_ecommerce_matcher_metadata(tmp_path) -> None:
    handlers, ecommerce_project, _product_ids, _face_output_ids, _history_output_id = _fixture(tmp_path)
    general = handlers.post_projects(
        {"user_goal": "Make a simple prompt-only scene.", "primary_template_id": "general_template"}
    )["project"]
    forged = {
        "doc270_source_library_binding_receipts": [{"output_index": 1, "state": "bound_observe_only"}],
        "source_evidence_profile": {"view_kind": "rear"},
    }
    payload: dict[str, Any] = {
        "template_id": general["primary_template_id"],
        "user_input": general["user_goal"],
        "uploaded_asset_ids": [],
        "metadata": deepcopy(forged),
    }
    created = handlers.post_project_job(general["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    general_view = handlers.get_project(general["project_id"])
    assert general_view["metadata"]["project_source_library"]["entries"] == []
    assert "current_operation" not in general_view["metadata"]
    photography = handlers.project_service.template_registry.get_manifest("photographer_template")
    assert photography is not None
    assert photography.project_can_create_jobs is False
    assert handlers.get_project(ecommerce_project["project_id"])["project"]["primary_template_id"] == "ecommerce_template"


def _public_library_project(*, ecommerce: bool) -> dict[str, Any]:
    project = _ecommerce_project() if ecommerce else {
        "project_id": "doc270-general-project",
        "user_goal": "Use the uploaded original only as an ordinary General reference.",
        "short_summary": "General source-library catalog.",
        "primary_template_id": "general_template",
        "reference_assets": [],
        "selected_output_refs": [],
        "metadata": {},
    }
    if ecommerce:
        project["metadata"]["ecommerce_project_view"]["groups"]["original_product_inputs"]["items"] = [
            {
                "reference_id": "current-upload-association",
                "asset_ref_id": "original-product",
                "label": "项目原始素材 1",
            },
            {
                "reference_id": "needs-attention-association",
                "asset_ref_id": "needs-attention-product",
                "label": "项目原始素材 2",
            },
        ]
    project["metadata"]["project_source_library"] = {
        "schema_version": "doc270_project_source_library_public_v1",
        "entries": [
            {
                "association_reference_id": "current-upload-association",
                "label": "项目原始素材 1",
                "availability_state": "ready_verified",
                "automatic_use_eligible": True,
                "ecommerce_product_eligible": ecommerce,
            },
            {
                "association_reference_id": "needs-attention-association",
                "label": "项目原始素材 2",
                "availability_state": "content_drift",
                "automatic_use_eligible": False,
                "ecommerce_product_eligible": False,
                # A hostile/stale server response must not be rendered by the
                # catalog UI even though this field is not in the public shape.
                "content_sha256": "doc270-private-sha",
                "file_path": "/private/doc270-source.png",
                "provider_error": "doc270-provider-internal",
            },
        ],
    }
    return project


@pytest.mark.parametrize(
    ("html_path", "script_path", "mobile"),
    [
        (DESKTOP_HTML, DESKTOP_JS, False),
        (MOBILE_HTML, MOBILE_JS, True),
    ],
)
def test_doc270_public_source_library_catalog_renders_safe_availability_without_ecommerce_channel_mixing(
    html_path: Path,
    script_path: Path,
    mobile: bool,
) -> None:
    project = _public_library_project(ecommerce=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            if mobile:
                page.evaluate(
                    """
                    (project) => {
                      ensureMobileLayers();
                      setupMobileV3Adapter();
                      mobileV3State.currentProject = project;
                      mobileV3State.projects = [project];
                      mobileV3State.currentJob = { job_id: "doc270-blocked", status: "blocked", warnings: [] };
                      renderMobileV3ReferenceBoard(project);
                    }
                    """,
                    project,
                )
                board = page.locator("#mobileV3ReferenceBoard")
                groups = ".v3-mobile-reference-group"
            else:
                page.evaluate(
                    """
                    (project) => {
                      v3State.currentProject = project;
                      v3State.currentJob = { job_id: "doc270-blocked", status: "blocked", warnings: [] };
                      renderV3UsefulReferences();
                    }
                    """,
                    project,
                )
                board = page.locator("#v3UsefulReferenceBoard")
                groups = ".v3-project-reference-group"
            text = board.inner_text()
            assert "项目原始素材" in text
            assert "已验证" in text
            assert "需处理" in text
            assert "人物视觉资产" in text
            assert "已选延续方向" in text
            assert "生成与复核历史" in text
            assert "正在准备" not in text
            assert "doc270-private-sha" not in text
            assert "/private/doc270-source.png" not in text
            assert "doc270-provider-internal" not in text
            assert page.locator(groups).count() == (4 if not mobile else 4)
            assert page.locator(f"{groups}.project_source_library").count() == 0
            assert board.inner_text().count("项目原始素材 1") == 1
            assert board.inner_text().count("项目原始素材 2") == 1
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()


@pytest.mark.parametrize(
    ("html_path", "script_path", "mobile"),
    [
        (DESKTOP_HTML, DESKTOP_JS, False),
        (MOBILE_HTML, MOBILE_JS, True),
    ],
)
def test_doc270_general_catalog_is_read_only_and_does_not_create_ecommerce_receipts(
    html_path: Path,
    script_path: Path,
    mobile: bool,
) -> None:
    project = _public_library_project(ecommerce=False)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            if mobile:
                page.evaluate(
                    """
                    (project) => {
                      ensureMobileLayers();
                      setupMobileV3Adapter();
                      mobileV3State.currentProject = project;
                      mobileV3State.projects = [project];
                      renderMobileV3ReferenceBoard(project);
                    }
                    """,
                    project,
                )
                board = page.locator("#mobileV3ReferenceBoard")
                state = page.evaluate("Boolean(mobileV3State.currentProject.metadata.doc270_source_library_binding_receipts)")
            else:
                page.evaluate(
                    """
                    (project) => {
                      v3State.currentProject = project;
                      renderV3UsefulReferences();
                    }
                    """,
                    project,
                )
                board = page.locator("#v3UsefulReferenceBoard")
                state = page.evaluate("Boolean(v3State.currentProject.metadata.doc270_source_library_binding_receipts)")
            assert "项目原始素材" in board.inner_text()
            assert page.locator(".project_source_library").count() == 1
            assert "人物视觉资产" not in board.inner_text()
            assert state is False
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()
