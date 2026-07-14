from __future__ import annotations

import base64
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
from alchemy_creative_agent_3_0.app.project_mode.service import EcommerceSlotContinuationError
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service
from app.main import app


ROOT = Path(__file__).resolve().parents[2]


def _handlers(*, project_store=None) -> V3ProductRouteHandlers:
    """Slot lineage tests use an explicit remote-Brain contract fixture."""

    return V3ProductRouteHandlers(service=ecommerce_test_service(), project_store=project_store)


def _png_base64() -> str:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(184, 194, 210)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _ready_product_upload(handlers: V3ProductRouteHandlers, *, filename: str) -> str:
    created = handlers.post_uploads(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": 256,
            "role": "product_reference",
        }
    )
    handlers.put_upload_content(created["asset_id"], {"content_base64": _png_base64(), "mime_type": "image/png"})
    assert handlers.post_upload_complete(created["asset_id"])["status"] == "ready"
    return created["asset_id"]


def _ecommerce_root(handlers: V3ProductRouteHandlers) -> tuple[dict, dict]:
    project = handlers.post_projects({"user_goal": "Create a clean desk-lamp marketplace suite"})["project"]
    root = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create a distinct marketplace image suite for an adjustable desk lamp.",
            "commerce_profile_patch": {
                "product_category": "desk lamp",
                "target_platform": "amazon_us",
                "core_selling_points": ["Adjustable metal shade"],
            },
            "metadata": {"requested_image_count": 3},
        },
    )
    assert root["status"] == "planned"
    assert root["metadata"]["ecommerce_slot_lineage"]["continuation_kind"] == "ecommerce_root"
    return project, root


def test_slot_continuation_creates_append_only_child_with_exact_frozen_plan() -> None:
    handlers = _handlers()
    project, root = _ecommerce_root(handlers)
    root_record = handlers.service.get_job_record(root["job_id"])
    assert root_record is not None
    parent_metadata = deepcopy(root_record.request.metadata)

    continuation = handlers.post_project_ecommerce_slot_continuation(
        project["project_id"],
        root["job_id"],
        "ecommerce_output_2",
        {"correction_note": "Make the feature angle cleaner and more legible.", "metadata": {"source": "ecommerce_workspace"}},
    )

    child_record = handlers.service.get_job_record(continuation["child_job_id"])
    assert child_record is not None
    assert continuation["child_job_id"] != root["job_id"]
    assert continuation["lineage"]["root_job_id"] == root["job_id"]
    assert continuation["lineage"]["parent_job_id"] == root["job_id"]
    assert continuation["lineage"]["parent_slot_id"] == "ecommerce_output_2"
    assert child_record.request.metadata["capability_activation_plan"] == parent_metadata["capability_activation_plan"]
    assert "capability_plan_amendment" not in child_record.request.metadata
    assert root_record.request.metadata == parent_metadata
    assert continuation["metadata"]["generation_route"].endswith(f"/jobs/{continuation['child_job_id']}/generate")


def test_slot_continuation_preserves_durable_real_execution_controls() -> None:
    """An E-Commerce redo must not weaken a parent real-provider/review contract."""

    handlers = _handlers()
    project, root = _ecommerce_root(handlers)
    root_record = handlers.service.get_job_record(root["job_id"])
    assert root_record is not None
    root_record.request.metadata.update(
        {
            "require_real_images": True,
            "requested_image_size": "1536x1024",
            "vision_inspection_mode": "hybrid",
            "vision_inspection_max_attempts": 1,
            "max_visual_retry_attempts": 1,
        }
    )
    handlers.service.job_store.save(root_record)

    continuation = handlers.post_project_ecommerce_slot_continuation(
        project["project_id"],
        root["job_id"],
        "ecommerce_output_2",
        {"correction_note": "Regenerate this one selected delivery."},
    )
    child_record = handlers.service.get_job_record(continuation["child_job_id"])
    assert child_record is not None
    assert child_record.request.metadata["require_real_images"] is True
    assert child_record.request.metadata["requested_image_size"] == "1536x1024"
    assert child_record.request.metadata["vision_inspection_mode"] == "hybrid"
    assert child_record.request.metadata["vision_inspection_max_attempts"] == 1
    assert child_record.request.metadata["max_visual_retry_attempts"] == 1
    assert child_record.request.metadata["requested_image_count"] == 1


def test_slot_delivery_uses_latest_successful_child_and_keeps_parent_history() -> None:
    handlers = _handlers()
    project, root = _ecommerce_root(handlers)
    continuation = handlers.post_project_ecommerce_slot_continuation(
        project["project_id"], root["job_id"], "ecommerce_output_2", {"correction_note": "Use a closer product detail."}
    )

    generated_child = handlers.post_project_job_generate(
        project["project_id"], continuation["child_job_id"], {"quality_mode": "standard"}
    )
    delivery = handlers.get_project_ecommerce_slot_delivery(project["project_id"], root["job_id"], "ecommerce_output_2")

    assert generated_child["status"] == "generated"
    assert delivery["current_delivery"]["job_id"] == continuation["child_job_id"]
    assert delivery["current_delivery"]["candidate_id"] in {
        candidate["candidate_id"] for candidate in generated_child["candidates"]
    }
    attempts = {item["job_id"]: item for item in delivery["attempts"]}
    assert root["job_id"] in attempts
    assert attempts[continuation["child_job_id"]]["is_current_delivery"] is True
    assert delivery["metadata"]["append_only_history"] is True


def test_slot_continuation_lineage_survives_project_store_reload(tmp_path) -> None:
    store_root = tmp_path / "projects"
    first = _handlers(project_store=PersistentProjectStore(store_root))
    project, root = _ecommerce_root(first)

    restarted = _handlers(project_store=PersistentProjectStore(store_root))
    continuation = restarted.post_project_ecommerce_slot_continuation(
        project["project_id"], root["job_id"], "ecommerce_output_1", {"correction_note": "Keep the same product but improve framing."}
    )
    delivery = restarted.get_project_ecommerce_slot_delivery(project["project_id"], root["job_id"], "ecommerce_output_1")

    assert continuation["lineage"]["root_job_id"] == root["job_id"]
    assert continuation["child_status"] == "planned"
    assert [item["job_id"] for item in delivery["attempts"]] == [root["job_id"], continuation["child_job_id"]]


def test_slot_amendment_requires_new_authorized_evidence_and_is_bounded(monkeypatch) -> None:
    handlers = _handlers()
    project, root = _ecommerce_root(handlers)
    later_evidence = _ready_product_upload(handlers, filename="later-evidence.png")
    handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": later_evidence, "use_policy": "product", "label": "new product evidence"},
    )
    root_record = handlers.service.get_job_record(root["job_id"])
    assert root_record is not None
    parent_plan = root_record.request.metadata["capability_activation_plan"]
    active = list(parent_plan["active_capabilities"])
    order = list(parent_plan["dependency_order"])
    assert len(active) > 1
    amended_plan = {
        **parent_plan,
        "plan_id": "plan_ecommerce_slot_amended",
        "fingerprint": "fingerprint_ecommerce_slot_amended",
        "active_capabilities": active[:-1],
        "dependency_order": order[:-1],
    }

    monkeypatch.setenv("V3_CAPABILITY_PLAN_AMENDMENT_ENABLED", "true")
    monkeypatch.setattr(
        handlers.service,
        "preview_capability_activation",
        lambda _payload: {
            "capability_activation_plan": amended_plan,
            "capability_activation_plan_id": amended_plan["plan_id"],
        },
    )
    amended = handlers.post_project_ecommerce_slot_continuation(
        project["project_id"],
        root["job_id"],
        "ecommerce_output_2",
        {"new_evidence_asset_ids": [later_evidence]},
    )

    assert amended["metadata"]["plan_amendment_applied"] is True
    assert amended["lineage"]["plan_amendment_id"]
    newer_evidence = _ready_product_upload(handlers, filename="newer-evidence.png")
    handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": newer_evidence, "use_policy": "product", "label": "newer product evidence"},
    )
    with pytest.raises(EcommerceSlotContinuationError) as exhausted:
        handlers.post_project_ecommerce_slot_continuation(
            project["project_id"],
            root["job_id"],
            "ecommerce_output_2",
            {"new_evidence_asset_ids": [newer_evidence]},
        )
    assert exhausted.value.code == "slot_plan_amendment_exhausted"


def test_general_and_legacy_jobs_cannot_call_ecommerce_slot_continuation() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a clean portrait cover"})["project"]
    general = handlers.post_project_job(project["project_id"], {"user_input": "Create a clean portrait cover"})

    with pytest.raises(EcommerceSlotContinuationError) as unsupported:
        handlers.post_project_ecommerce_slot_continuation(
            project["project_id"], general["job_id"], "main_image", {"correction_note": "Redo it"}
        )
    assert unsupported.value.code == "slot_continuation_not_supported"


def test_public_route_is_namespaced_while_general_frontend_stays_slot_free() -> None:
    main_source = (ROOT / "src_skeleton" / "app" / "main.py").read_text(encoding="utf-8")
    app_source = (ROOT / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")

    assert "/ecommerce-slots/{slot_id}/continuations" in main_source
    assert "/ecommerce-slots/{slot_id}/delivery" in main_source
    assert "ecommerce-slots" not in app_source
    routes = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/v3/creative-agent/projects/{project_id}/jobs/{parent_job_id}/ecommerce-slots/{slot_id}/continuations" in routes
    assert "/api/v3/creative-agent/projects/{project_id}/jobs/{root_job_id}/ecommerce-slots/{slot_id}/delivery" in routes
