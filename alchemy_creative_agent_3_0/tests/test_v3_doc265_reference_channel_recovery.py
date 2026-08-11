"""Phase 0 red contracts for Doc265 reference-channel recovery.

These tests use only local stores and the public Project/Product route seam.
They must not call Provider, MCP, ImageGen, a remote service, or VPS.
"""

from __future__ import annotations

import json

import pytest

from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    LEGACY_VISUAL_ASSET_NAME,
    _handlers,
    _png_base64,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import LibraryVisualAssetCreateRequest


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
        _save_history_output(handlers, job_id=f"history-job-{index}", index=index)
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
    historical = _save_history_output(handlers, job_id="doc265-text-history-job", index=13)

    created = handlers.post_project_job(
        project["project_id"],
        _job_payload(
            uploaded_asset_ids=[historical.output_id],
            key="doc265-history-no-product",
        ),
    )

    assert created["metadata"]["ecommerce_text_to_image_fallback"] is True
    assert created["metadata"]["has_product_reference"] is False
