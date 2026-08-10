"""Phase 1 red contracts for Doc263 E-Commerce project recovery surfaces.

These tests exercise public Project Mode/Product API responses only. They do
not invoke a provider, MCP, ImageGen, or browser runtime.
"""

from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    ProjectVisualAssetBindingService,
    VisualAssetLibraryCatalog,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


def _png_base64(color: tuple[int, int, int]) -> str:
    image = Image.new("RGB", (24, 24), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _handlers(tmp_path) -> tuple[V3ProductRouteHandlers, VisualAssetLibraryCatalog]:
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    service = ecommerce_test_service(output_store=output_store)
    service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "uploads")
    catalog = VisualAssetLibraryCatalog()
    bindings = ProjectVisualAssetBindingService(catalog)
    return (
        V3ProductRouteHandlers(
            service=service,
            project_store=InMemoryProjectStore(),
            visual_asset_library_catalog=catalog,
            project_visual_asset_binding_service=bindings,
        ),
        catalog,
    )


def _ready_product_upload(
    handlers: V3ProductRouteHandlers,
    *,
    filename: str,
    color: tuple[int, int, int],
) -> str:
    content = _png_base64(color)
    created = handlers.post_uploads(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(content)),
            "role": "product_reference",
        }
    )
    handlers.put_upload_content(
        created["asset_id"],
        {"content_base64": content, "mime_type": "image/png"},
    )
    ready = handlers.post_upload_complete(created["asset_id"])
    assert ready["status"] == "ready"
    return str(created["asset_id"])


def _ecommerce_project(handlers: V3ProductRouteHandlers, *, goal: str = "Create an ecommerce product image.") -> dict:
    return handlers.post_projects(
        {
            "user_goal": goal,
            "primary_template_id": "ecommerce_template",
        }
    )["project"]


def _job(
    handlers: V3ProductRouteHandlers,
    project_id: str,
    *,
    product_id: str,
    key: str,
) -> dict:
    return handlers.post_project_job(
        project_id,
        {
            "template_id": "ecommerce_template",
            "user_input": "Create one clear ecommerce product image.",
            "uploaded_asset_ids": [product_id],
            "metadata": {"idempotency_key": key},
        },
    )


def _save_output(
    handlers: V3ProductRouteHandlers,
    *,
    job_id: str,
    name: str,
    color: tuple[int, int, int],
):
    return handlers.service.output_store.save_base64_output(
        job_id=job_id,
        candidate_id=f"candidate_{name}",
        asset_id=f"asset_{name}",
        provider="fixture",
        model="fixture-model",
        encoded_image=_png_base64(color),
        mime_type="image/png",
        output_format="png",
        metadata={"requested_image_count": 1},
    )


def _delivery_status(base, *, output_id: str, ready: bool):
    return base.model_copy(
        update={
            "status": ProductJobStatusValue.GENERATED,
            "metadata": {
                **dict(base.metadata or {}),
                "post_generation_review": {
                    "inspections": [
                        {
                            "output_id": output_id,
                            "mode": "hybrid",
                            "status": "pass" if ready else "manual_review",
                            "verification_state": "verified",
                        }
                    ]
                },
                "final_delivery": {
                    "final_delivery_status": "ready" if ready else "withheld_manual_confirmation",
                    "automatic_delivery_available": ready,
                    "manual_confirmation_required": not ready,
                    "delivery_gate_applies": True,
                },
            },
        }
    )


def test_doc263_ecommerce_project_view_keeps_four_groups_separate_and_never_promotes_outputs(tmp_path) -> None:
    handlers, catalog = _handlers(tmp_path)
    original_id = _ready_product_upload(
        handlers,
        filename="original.png",
        color=(155, 95, 70),
    )
    duplicate_id = _ready_product_upload(
        handlers,
        filename="duplicate.png",
        color=(155, 95, 70),
    )
    project = _ecommerce_project(handlers)
    project_id = project["project_id"]
    handlers.post_project_reference(
        project_id,
        {"asset_ref_id": original_id, "source_type": "uploaded", "use_policy": "product"},
    )
    duplicate = handlers.post_project_reference(
        project_id,
        {"asset_ref_id": duplicate_id, "source_type": "uploaded", "use_policy": "product"},
    )
    job = _job(handlers, project_id, product_id=original_id, key="doc263-ui-groups")
    output = _save_output(
        handlers,
        job_id=job["job_id"],
        name="selected_direction",
        color=(90, 130, 180),
    )
    generated_reference = handlers.post_project_reference(
        project_id,
        {
            "asset_ref_id": output.output_id,
            "source_type": "generated_selected",
            "use_policy": "product",
        },
    )
    person = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Locked person",
            asset_type="people",
            root_source_asset_id="fixture_person_root",
            consent_reference="fixture-consent",
            preparation_intent="Reusable locked person identity.",
        ),
    )
    person = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=person.visual_asset_id,
        version_id="fixture_person_v1",
        approved_evidence_ids=[output.output_id],
    )
    handlers.post_project_visual_asset_binding(
        project_id,
        {
            "visual_asset_id": person.visual_asset_id,
            "selected_version_id": person.active_version_id,
            "confirm_binding": True,
        },
    )

    payload = handlers.get_project(project_id)
    view = payload["metadata"].get("ecommerce_project_view")

    assert duplicate["reference"]["asset_ref_id"] == original_id
    assert generated_reference["reference"]["source_type"] == "generated_selected"
    assert view is not None, "Doc263 requires one public E-Commerce project view."
    assert view["schema_version"] == "doc263_ecommerce_project_view_v1"
    assert set(view["groups"]) == {
        "original_product_inputs",
        "locked_person_identity",
        "selected_continuation_directions",
        "generated_and_review_history",
    }
    assert [item["asset_ref_id"] for item in view["groups"]["original_product_inputs"]["items"]] == [original_id]
    assert [item["visual_asset_id"] for item in view["groups"]["locked_person_identity"]["items"]] == [
        person.visual_asset_id
    ]
    assert [item["output_id"] for item in view["groups"]["selected_continuation_directions"]["items"]] == [
        output.output_id
    ]
    assert output.output_id not in {
        item["asset_ref_id"] for item in view["groups"]["original_product_inputs"]["items"]
    }


def test_doc263_homepage_carousel_excludes_review_withheld_output_but_project_history_keeps_it(
    tmp_path,
    monkeypatch,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    product_id = _ready_product_upload(handlers, filename="product.png", color=(110, 155, 95))
    project = _ecommerce_project(handlers)
    project_id = project["project_id"]
    delivered_job = _job(handlers, project_id, product_id=product_id, key="doc263-home-delivered")
    delivered = _save_output(
        handlers,
        job_id=delivered_job["job_id"],
        name="delivered",
        color=(100, 140, 190),
    )
    withheld_job = _job(handlers, project_id, product_id=product_id, key="doc263-home-withheld")
    withheld = _save_output(
        handlers,
        job_id=withheld_job["job_id"],
        name="withheld",
        color=(190, 120, 100),
    )
    original_get_job = handlers.service.get_job
    delivered_status = _delivery_status(
        original_get_job(delivered_job["job_id"]),
        output_id=delivered.output_id,
        ready=True,
    )
    withheld_status = _delivery_status(
        original_get_job(withheld_job["job_id"]),
        output_id=withheld.output_id,
        ready=False,
    )

    def _get_job(job_id: str):
        if job_id == delivered_job["job_id"]:
            return delivered_status
        if job_id == withheld_job["job_id"]:
            return withheld_status
        return original_get_job(job_id)

    monkeypatch.setattr(handlers.service, "get_job", _get_job)

    history = handlers.get_project_outputs(project_id=project_id, compact=True)
    homepage = handlers.get_projects(limit=10)["projects"]
    summary = next(item for item in homepage if item["project_id"] == project_id)

    assert [item["output_id"] for item in history["items"]] == [delivered.output_id]
    assert [item["output_id"] for item in history["review_items"]] == [withheld.output_id]
    assert summary["latest_thumbnail_urls"] == [delivered.thumbnail_url]


def test_doc263_public_project_operation_replaces_terminal_preparing_with_one_continue_action(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    product_id = _ready_product_upload(handlers, filename="product.png", color=(85, 120, 165))
    project = _ecommerce_project(handlers)
    job = _job(handlers, project["project_id"], product_id=product_id, key="doc263-terminal-operation")
    record = handlers.service.get_job_record(job["job_id"])
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.warnings.append("reference_projection_drift: C:\\private\\product.png sha256:secret")
    record.lifecycle = handlers.service._build_lifecycle(record)  # noqa: SLF001
    handlers.service.job_store.save(record)

    first = handlers.get_project(project["project_id"])
    reloaded = handlers.get_project(project["project_id"])
    operation = first["metadata"].get("current_operation")

    assert operation is not None, "Doc263 requires a server-owned public operation surface."
    assert operation == {
        "job_id": job["job_id"],
        "state": "failed_no_delivery",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "continue"}],
    }
    assert reloaded["metadata"]["current_operation"] == operation
    assert "preparing" not in str(operation).lower()
    assert "C:\\private\\product.png" not in str(operation)
    assert "sha256:secret" not in str(operation)


def test_doc263_project_view_keeps_review_output_and_failed_attempt_in_history(tmp_path, monkeypatch) -> None:
    handlers, _catalog = _handlers(tmp_path)
    product_id = _ready_product_upload(handlers, filename="product.png", color=(130, 110, 190))
    project = _ecommerce_project(handlers)
    project_id = project["project_id"]
    review_job = _job(handlers, project_id, product_id=product_id, key="doc263-history-review")
    review_output = _save_output(
        handlers,
        job_id=review_job["job_id"],
        name="review_history",
        color=(190, 145, 105),
    )
    failed_job = _job(handlers, project_id, product_id=product_id, key="doc263-history-failed")
    failed_record = handlers.service.get_job_record(failed_job["job_id"])
    assert failed_record is not None
    failed_record.status = ProductJobStatusValue.FAILED
    failed_record.warnings.append("provider payload should never be public")
    failed_record.lifecycle = handlers.service._build_lifecycle(failed_record)  # noqa: SLF001
    handlers.service.job_store.save(failed_record)
    original_get_job = handlers.service.get_job
    review_status = _delivery_status(
        original_get_job(review_job["job_id"]),
        output_id=review_output.output_id,
        ready=False,
    )

    def _get_job(job_id: str):
        if job_id == review_job["job_id"]:
            return review_status
        return original_get_job(job_id)

    monkeypatch.setattr(handlers.service, "get_job", _get_job)

    payload = handlers.get_project(project_id)
    view = payload["metadata"].get("ecommerce_project_view")

    assert view is not None, "Doc263 history must be reachable from the project view."
    history = view["groups"]["generated_and_review_history"]
    assert [item["output_id"] for item in history["review_withheld_outputs"]] == [review_output.output_id]
    assert [item["job_id"] for item in history["failed_attempts"]] == [failed_job["job_id"]]
    assert "provider payload should never be public" not in str(history)
