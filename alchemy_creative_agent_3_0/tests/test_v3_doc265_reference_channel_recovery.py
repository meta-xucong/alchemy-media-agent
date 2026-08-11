"""Phase 0 red contracts for Doc265 reference-channel recovery.

These tests use only local stores and the public Project/Product route seam.
They must not call Provider, MCP, ImageGen, a remote service, or VPS.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    LEGACY_VISUAL_ASSET_NAME,
    _forbid_planning_and_dispatch,
    _handlers,
    _png_base64,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import LibraryVisualAssetCreateRequest
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceAsset,
    ProjectReferenceSourceType,
    ProjectReferenceStatus,
    ProjectReferenceUsePolicy,
)


def _output_id(index: int) -> str:
    return f"v3_output_{index:020x}"


def _save_history_output(handlers, *, job_id: str, index: int):
    return handlers.service.output_store.save_base64_output(
        job_id=job_id,
        candidate_id=f"candidate_history_{index}",
        asset_id=f"asset_history_{index}",
        provider="fixture",
        model="fixture",
        encoded_image=_png_base64((80 + index * 20, 110, 150)),
        output_id=_output_id(index),
    )


def _save_project_history_output(handlers, *, project_id: str, key: str, index: int):
    job = handlers.post_project_job(
        project_id,
        _job_payload(uploaded_asset_ids=[], key=key),
    )
    return _save_history_output(handlers, job_id=job["job_id"], index=index)


def _doc265_reference_operation() -> dict:
    return {
        "state": "continuation_reference_unavailable",
        "terminal": True,
        "pending": False,
        "channel": "selected_continuation_directions",
        "next_actions": [{"id": "review_selected_references"}],
    }


def _add_product_references(handlers, project_id: str, asset_ids: list[str]) -> None:
    for asset_id in asset_ids:
        handlers.post_project_reference(
            project_id,
            {
                "asset_ref_id": asset_id,
                "source_type": "uploaded",
                "use_policy": "product",
            },
        )


def _job_payload(*, uploaded_asset_ids: list[str], key: str) -> dict:
    return {
        "template_id": "ecommerce_template",
        "user_input": "Generate a clean product image from the current project facts.",
        "uploaded_asset_ids": uploaded_asset_ids,
        "metadata": {"idempotency_key": key},
    }


def test_doc265_legacy_mixed_uploaded_list_recovers_product_truth_only(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    products = [
        _ready_product_upload(
            handlers,
            filename=f"doc265-product-{index}.png",
            color=(70 + index * 20, 120, 160),
        )
        for index in range(4)
    ]
    _add_product_references(handlers, project["project_id"], products)
    historical_outputs = [
        _save_project_history_output(
            handlers,
            project_id=project["project_id"],
            key=f"doc265-history-owned-{index}",
            index=index,
        )
        for index in range(1, 4)
    ]

    created = handlers.post_project_job(
        project["project_id"],
        _job_payload(
            uploaded_asset_ids=products + [item.output_id for item in historical_outputs],
            key="doc265-mixed-legacy-input",
        ),
    )
    record = handlers.service.get_job_record(created["job_id"])

    assert record is not None
    assert record.request.uploaded_asset_ids == products
    admission = record.request.metadata["professional_ecommerce_product_truth_admission"]
    assert admission["canonical_asset_ids"] == products
    assert not set(item.output_id for item in historical_outputs).intersection(
        record.request.uploaded_asset_ids
    )


def test_doc265_legacy_output_asset_and_candidate_ids_are_history_only(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product = _ready_product_upload(
        handlers,
        filename="doc265-product-with-output-aliases.png",
        color=(90, 140, 170),
    )
    _add_product_references(handlers, project["project_id"], [product])
    historical = _save_project_history_output(
        handlers,
        project_id=project["project_id"],
        key="doc265-history-alias-owned",
        index=14,
    )

    created = handlers.post_project_job(
        project["project_id"],
        _job_payload(
            uploaded_asset_ids=[product, historical.asset_id, historical.candidate_id],
            key="doc265-history-aliases",
        ),
    )
    record = handlers.service.get_job_record(created["job_id"])

    assert record is not None
    assert record.request.uploaded_asset_ids == [product]
    recovery = record.request.metadata["doc265_reference_channel_recovery"]
    assert recovery["legacy_uploaded_output_ids"] == [historical.output_id]
    assert recovery["recovered_product_asset_ids"] == [product]


@pytest.mark.parametrize("selector_kind", ["foreign", "unknown"])
def test_doc265_legacy_foreign_or_unknown_output_selector_fails_closed(
    tmp_path,
    monkeypatch,
    selector_kind: str,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    target = _project(handlers)
    product = _ready_product_upload(
        handlers,
        filename=f"doc265-{selector_kind}-selector-product.png",
        color=(120, 150, 175),
    )
    _add_product_references(handlers, target["project_id"], [product])
    if selector_kind == "foreign":
        source = _project(handlers)
        source_job = handlers.post_project_job(
            source["project_id"],
            _job_payload(uploaded_asset_ids=[], key="doc265-foreign-source"),
        )
        selector = _save_history_output(handlers, job_id=source_job["job_id"], index=18).output_id
    else:
        selector = _output_id(999)
    before_job_ids = handlers.get_project(target["project_id"])["project"]["job_ids"]
    calls = _forbid_planning_and_dispatch(monkeypatch, handlers)

    with pytest.raises(ValueError, match="reference channel"):
        handlers.post_project_job(
            target["project_id"],
            _job_payload(
                uploaded_asset_ids=[product, selector],
                key=f"doc265-{selector_kind}-legacy-list",
            ),
        )

    public = handlers.get_project(target["project_id"])
    assert public["project"]["job_ids"] == before_job_ids
    assert public["metadata"]["current_operation"] == _doc265_reference_operation()
    assert selector not in json.dumps(public, sort_keys=True)
    assert calls == {"plan": 0, "dispatch": 0}


def test_doc265_legacy_ambiguous_output_alias_fails_closed(tmp_path, monkeypatch) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product = _ready_product_upload(
        handlers,
        filename="doc265-ambiguous-selector-product.png",
        color=(130, 160, 185),
    )
    _add_product_references(handlers, project["project_id"], [product])
    jobs = [
        handlers.post_project_job(
            project["project_id"],
            _job_payload(uploaded_asset_ids=[], key=f"doc265-ambiguous-source-{index}"),
        )
        for index in range(2)
    ]
    collision_candidate_id = "doc265-candidate-collision"
    for index, job in enumerate(jobs):
        handlers.service.output_store.save_base64_output(
            job_id=job["job_id"],
            candidate_id=collision_candidate_id,
            asset_id=f"doc265-collision-asset-{index}",
            provider="fixture",
            model="fixture",
            encoded_image=_png_base64((140 + index * 10, 120, 160)),
        )
    before_job_ids = handlers.get_project(project["project_id"])["project"]["job_ids"]
    calls = _forbid_planning_and_dispatch(monkeypatch, handlers)

    with pytest.raises(ValueError, match="reference channel"):
        handlers.post_project_job(
            project["project_id"],
            _job_payload(
                uploaded_asset_ids=[product, collision_candidate_id],
                key="doc265-ambiguous-legacy-list",
            ),
        )

    public = handlers.get_project(project["project_id"])
    assert public["project"]["job_ids"] == before_job_ids
    assert public["metadata"]["current_operation"] == _doc265_reference_operation()
    assert collision_candidate_id not in json.dumps(public["metadata"]["current_operation"], sort_keys=True)
    assert calls == {"plan": 0, "dispatch": 0}


def test_doc265_unselected_generated_output_stays_history_not_active_reference(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product = _ready_product_upload(
        handlers,
        filename="doc265-history-product.png",
        color=(100, 140, 180),
    )
    _add_product_references(handlers, project["project_id"], [product])
    job = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key="doc265-history-only"),
    )
    output = _save_history_output(handlers, job_id=job["job_id"], index=10)

    view = handlers.get_project(project["project_id"])["metadata"]["ecommerce_project_view"]
    groups = view["groups"]
    assert [item["asset_ref_id"] for item in groups["original_product_inputs"]["items"]] == [product]
    assert groups["selected_continuation_directions"]["items"] == []
    history_ids = {
        item["output_id"]
        for item in groups["generated_and_review_history"]["delivered_outputs"]
    }
    assert output.output_id in history_ids
    assert output.output_id not in json.dumps(groups["original_product_inputs"], sort_keys=True)


def test_doc265_explicit_generated_selection_is_continuation_only(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    job = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key="doc265-selection-source"),
    )
    output = _save_history_output(handlers, job_id=job["job_id"], index=11)

    selected = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": output.output_id,
            "source_type": "generated_selected",
            "created_from_job_id": job["job_id"],
            "created_from_output_id": output.output_id,
            "use_policy": "style",
        },
    )
    view = handlers.get_project(project["project_id"])["metadata"]["ecommerce_project_view"]
    directions = view["groups"]["selected_continuation_directions"]["items"]

    assert selected["reference"]["source_type"] == "generated_selected"
    assert [item["output_id"] for item in directions] == [output.output_id]
    assert output.output_id not in {
        item["asset_ref_id"]
        for item in view["groups"]["original_product_inputs"]["items"]
    }


def test_doc265_initial_generated_selection_requires_sha256_fingerprint(tmp_path, monkeypatch) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    source_job = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key="doc265-initial-integrity-source"),
    )
    output = _save_history_output(handlers, job_id=source_job["job_id"], index=23)
    monkeypatch.setattr(handlers.project_service, "_file_content_fingerprint", lambda _path: "")

    with pytest.raises(ValueError, match="continuation|reference|output"):
        handlers.post_project_reference(
            project["project_id"],
            {
                "asset_ref_id": output.output_id,
                "source_type": "generated_selected",
                "created_from_job_id": source_job["job_id"],
                "created_from_output_id": output.output_id,
                "use_policy": "style",
            },
        )

    operation = handlers.get_project(project["project_id"])["metadata"]["current_operation"]
    assert operation == _doc265_reference_operation()
    assert output.output_id not in json.dumps(operation, sort_keys=True)


@pytest.mark.parametrize("mutation", ["drift", "delete"])
def test_doc265_selected_output_is_revalidated_before_new_job(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    source_job = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc265-integrity-source-{mutation}"),
    )
    output = _save_history_output(handlers, job_id=source_job["job_id"], index=21)
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": output.output_id,
            "source_type": "generated_selected",
            "created_from_job_id": source_job["job_id"],
            "created_from_output_id": output.output_id,
            "use_policy": "style",
        },
    )
    output_path = Path(output.file_path)
    if mutation == "drift":
        output_path.write_bytes(output_path.read_bytes() + b"doc265-drift")
    else:
        output_path.unlink()

    before_job_ids = handlers.get_project(project["project_id"])["project"]["job_ids"]
    calls = _forbid_planning_and_dispatch(monkeypatch, handlers)
    with pytest.raises(ValueError, match="continuation|reference|output"):
        handlers.post_project_job(
            project["project_id"],
            _job_payload(uploaded_asset_ids=[], key=f"doc265-integrity-reject-{mutation}"),
        )

    public = handlers.get_project(project["project_id"])
    assert public["project"]["job_ids"] == before_job_ids
    operation = public["metadata"]["current_operation"]
    assert operation == _doc265_reference_operation()
    assert output.output_id not in json.dumps(operation, sort_keys=True)
    assert str(output_path) not in json.dumps(operation, sort_keys=True)
    assert calls == {"plan": 0, "dispatch": 0}


def test_doc265_persisted_cross_project_selected_output_is_revalidated_before_new_job(
    tmp_path, monkeypatch
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    target = _project(handlers)
    source = _project(handlers)
    source_job = handlers.post_project_job(
        source["project_id"],
        _job_payload(uploaded_asset_ids=[], key="doc265-persisted-cross-project-source"),
    )
    output = _save_history_output(handlers, job_id=source_job["job_id"], index=22)
    output_digest = hashlib.sha256(Path(output.file_path).read_bytes()).hexdigest()
    target_record = handlers.project_service.project_store.get_project(target["project_id"])
    assert target_record is not None
    target_record.reference_assets.append(
        ProjectReferenceAsset(
            reference_id="doc265-legacy-cross-project-reference",
            project_id=target["project_id"],
            source_type=ProjectReferenceSourceType.GENERATED_SELECTED,
            asset_ref_id=output.output_id,
            created_at="2026-08-11T00:00:00Z",
            created_from_job_id=source_job["job_id"],
            created_from_output_id=output.output_id,
            status=ProjectReferenceStatus.ACTIVE,
            use_policy=ProjectReferenceUsePolicy.STYLE,
            metadata={
                "canonical_output_binding": True,
                "source_integrity_id": f"sha256:{output_digest}",
            },
        )
    )
    handlers.project_service.project_store.save_project(target_record)

    before_job_ids = handlers.get_project(target["project_id"])["project"]["job_ids"]
    calls = _forbid_planning_and_dispatch(monkeypatch, handlers)
    with pytest.raises(ValueError, match="continuation|reference|output"):
        handlers.post_project_job(
            target["project_id"],
            _job_payload(uploaded_asset_ids=[], key="doc265-persisted-cross-project-reject"),
        )

    public = handlers.get_project(target["project_id"])
    assert public["project"]["job_ids"] == before_job_ids
    operation = public["metadata"]["current_operation"]
    assert operation == _doc265_reference_operation()
    assert output.output_id not in json.dumps(operation, sort_keys=True)
    assert source_job["job_id"] not in json.dumps(operation, sort_keys=True)
    assert calls == {"plan": 0, "dispatch": 0}


@pytest.mark.parametrize("selector_kind", ["unknown", "cross_project"])
def test_doc265_invalid_generated_selector_fails_closed(tmp_path, selector_kind: str) -> None:
    handlers, _catalog = _handlers(tmp_path)
    target = _project(handlers)
    source = _project(handlers)
    source_job = handlers.post_project_job(
        source["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc265-selector-{selector_kind}"),
    )
    output = _save_history_output(handlers, job_id=source_job["job_id"], index=12)
    if selector_kind == "unknown":
        output_id = _output_id(999)
        job_id = source_job["job_id"]
    else:
        output_id = output.output_id
        job_id = source_job["job_id"]

    with pytest.raises(ValueError, match="continuation|reference|output"):
        handlers.post_project_reference(
            target["project_id"],
            {
                "asset_ref_id": output_id,
                "source_type": "generated_selected",
                "created_from_job_id": job_id,
                "created_from_output_id": output_id,
                "use_policy": "style",
            },
        )
    public = handlers.get_project(target["project_id"])
    assert public["metadata"]["current_operation"] == _doc265_reference_operation()
    assert output_id not in json.dumps(
        public["metadata"]["ecommerce_project_view"]["groups"]["selected_continuation_directions"],
        sort_keys=True,
    )


def test_doc265_unreadable_generated_selector_fails_closed(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    job = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key="doc265-unreadable-selector"),
    )
    output = _save_history_output(handlers, job_id=job["job_id"], index=15)
    Path(output.file_path).unlink()

    with pytest.raises(ValueError, match="continuation|reference|output"):
        handlers.post_project_reference(
            project["project_id"],
            {
                "asset_ref_id": output.output_id,
                "source_type": "generated_selected",
                "created_from_job_id": job["job_id"],
                "created_from_output_id": output.output_id,
                "use_policy": "style",
            },
        )

    public = handlers.get_project(project["project_id"])
    assert public["metadata"]["current_operation"] == _doc265_reference_operation()


def test_doc265_unscoped_generated_selector_without_client_job_fails_closed(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    output = _save_history_output(handlers, job_id="doc265-unscoped-output-job", index=19)

    with pytest.raises(ValueError, match="continuation|reference|output"):
        handlers.post_project_reference(
            project["project_id"],
            {
                "asset_ref_id": output.output_id,
                "source_type": "generated_selected",
                "use_policy": "style",
            },
        )

    public = handlers.get_project(project["project_id"])
    assert public["metadata"]["current_operation"] == _doc265_reference_operation()
    assert output.output_id not in json.dumps(
        public["metadata"]["ecommerce_project_view"]["groups"]["selected_continuation_directions"],
        sort_keys=True,
    )


def test_doc265_foreign_generated_selector_without_client_job_fails_closed(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    target = _project(handlers)
    source = _project(handlers)
    source_job = handlers.post_project_job(
        source["project_id"],
        _job_payload(uploaded_asset_ids=[], key="doc265-foreign-unscoped-source"),
    )
    output = _save_history_output(handlers, job_id=source_job["job_id"], index=20)

    with pytest.raises(ValueError, match="continuation|reference|output"):
        handlers.post_project_reference(
            target["project_id"],
            {
                "asset_ref_id": output.output_id,
                "source_type": "generated_selected",
                "use_policy": "style",
            },
        )

    public = handlers.get_project(target["project_id"])
    assert public["metadata"]["current_operation"] == _doc265_reference_operation()
    assert output.output_id not in json.dumps(
        public["metadata"]["ecommerce_project_view"]["groups"]["selected_continuation_directions"],
        sort_keys=True,
    )


def test_doc265_valid_generated_selection_clears_prior_recovery_state(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    target = _project(handlers)
    source = _project(handlers)
    source_job = handlers.post_project_job(
        source["project_id"],
        _job_payload(uploaded_asset_ids=[], key="doc265-clear-source"),
    )
    source_output = _save_history_output(handlers, job_id=source_job["job_id"], index=16)
    with pytest.raises(ValueError, match="continuation|reference|output"):
        handlers.post_project_reference(
            target["project_id"],
            {
                "asset_ref_id": source_output.output_id,
                "source_type": "generated_selected",
                "created_from_job_id": source_job["job_id"],
                "created_from_output_id": source_output.output_id,
                "use_policy": "style",
            },
        )
    assert handlers.get_project(target["project_id"])["metadata"]["current_operation"] == _doc265_reference_operation()

    target_job = handlers.post_project_job(
        target["project_id"],
        _job_payload(uploaded_asset_ids=[], key="doc265-clear-target"),
    )
    record = handlers.service.get_job_record(target_job["job_id"])
    assert record is not None
    record.status = ProductJobStatusValue.GENERATED
    handlers.service.job_store.save(record)
    target_output = _save_history_output(handlers, job_id=target_job["job_id"], index=17)
    handlers.post_project_reference(
        target["project_id"],
        {
            "asset_ref_id": target_output.output_id,
            "source_type": "generated_selected",
            "created_from_job_id": target_job["job_id"],
            "created_from_output_id": target_output.output_id,
            "use_policy": "style",
        },
    )

    public = handlers.get_project(target["project_id"])
    assert public["metadata"].get("current_operation") is None
    assert [
        item["output_id"]
        for item in public["metadata"]["ecommerce_project_view"]["groups"][
            "selected_continuation_directions"
        ]["items"]
    ] == [target_output.output_id]


def test_doc265_locked_person_identity_never_enters_product_truth(tmp_path) -> None:
    handlers, catalog = _handlers(tmp_path)
    draft = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name=LEGACY_VISUAL_ASSET_NAME,
            asset_type="people",
            root_source_asset_id="doc265-person-root",
            consent_reference="doc265-person-consent",
            preparation_intent="Locked person identity for E-Commerce.",
        ),
    )
    active = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=draft.visual_asset_id,
        version_id="doc265-person-version",
        approved_evidence_ids=["doc265-person-evidence"],
    )
    project = _project(handlers)
    handlers.post_project_visual_asset_binding(
        project["project_id"],
        {
            "visual_asset_id": draft.visual_asset_id,
            "selected_version_id": active.active_version_id,
            "confirm_binding": True,
        },
    )
    product = _ready_product_upload(
        handlers,
        filename="doc265-person-product.png",
        color=(125, 135, 145),
    )
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": product,
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )
    view = handlers.get_project(project["project_id"])["metadata"]["ecommerce_project_view"]

    assert view["groups"]["locked_person_identity"]["items"][0]["display_name"] == draft.display_name
    assert view["groups"]["original_product_inputs"]["items"][0]["asset_ref_id"] == product


def test_doc265_only_history_keeps_no_product_text_to_image_path(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    historical = _save_project_history_output(
        handlers,
        project_id=project["project_id"],
        key="doc265-text-history-owned",
        index=13,
    )

    created = handlers.post_project_job(
        project["project_id"],
        _job_payload(
            uploaded_asset_ids=[historical.output_id],
            key="doc265-history-no-product",
        ),
    )

    assert created["metadata"]["ecommerce_text_to_image_fallback"] is True
    assert created["metadata"]["has_product_reference"] is False
