"""Doc132 E-Commerce provider-independent code-closure evidence.

These tests deliberately use the shared deterministic Product API/Project
Mode fixture.  They prove only Alchemy-owned planning, projection, persistence
and UI truth; they do not call an upstream image Provider or claim a pixel
release gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
    ecommerce_test_service,
)


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"


def _handlers(tmp_path: Path, *, provider: EcommerceRemoteBrainTestProvider | None = None) -> V3ProductRouteHandlers:
    return V3ProductRouteHandlers(
        service=ecommerce_test_service(brain_provider=provider),
        project_store=PersistentProjectStore(tmp_path / "projects"),
    )


def _job_payload(*, count: int, legacy_mode: str | None = None) -> dict:
    metadata = {"requested_image_count": count}
    if legacy_mode:
        metadata["selected_preset_id"] = legacy_mode
        metadata["selected_mode_id"] = legacy_mode
    return {
        "template_id": "ecommerce_template",
        "user_input": "Create product images from the supplied product facts and the user-requested buyer need.",
        "commerce_profile_patch": {
            "product_category": "desk lamp",
            "target_platform": "amazon_us",
            "must_keep_facts": ["matte black aluminum body"],
            "core_selling_points": [],
            "metadata": {"approved_literal_copy": None},
        },
        "metadata": metadata,
    }


def _new_project_job(
    handlers: V3ProductRouteHandlers,
    *,
    count: int,
    legacy_mode: str | None = None,
) -> tuple[dict, dict]:
    project = handlers.post_projects({"user_goal": "Create product images that faithfully show the supplied desk lamp."})[
        "project"
    ]
    job = handlers.post_project_job(project["project_id"], _job_payload(count=count, legacy_mode=legacy_mode))
    return project, job


@pytest.mark.parametrize("count", [1, 2, 4, 7])
def test_doc132_shared_fixture_keeps_exact_brain_count_and_project_aggregation(
    tmp_path: Path,
    count: int,
) -> None:
    """One shared deterministic generation path projects exactly N opaque outputs."""

    provider = EcommerceRemoteBrainTestProvider()
    handlers = _handlers(tmp_path, provider=provider)
    project, job = _new_project_job(handlers, count=count)

    assert job["status"] == "planned"
    assert job["scenario"]["selected_mode_id"] is None
    assert job["scenario"]["selected_preset_id"] is None
    output_intents = job["ecommerce"]["remote_brain_output_intents"]
    assert [item["index"] for item in output_intents] == list(range(1, count + 1))
    assert all(item["output_id"].startswith("template_deliverable_") for item in output_intents)
    assert all("slot_id" not in item for item in output_intents)
    assert len(provider.requests) == 2

    brain_request = provider.requests[0]
    brain_metadata = brain_request["metadata"]
    assert "ecommerce_creative_context" in brain_metadata
    assert brain_metadata["ecommerce_creative_context"]["product_truth"]
    assert "scenario_mode_id" not in brain_metadata
    assert "scenario_preset_id" not in brain_metadata
    serialized_brain_request = json.dumps(brain_request, ensure_ascii=False)
    for legacy_value in ("one_click_product_set", "marketplace_listing_set", "style_recreation_set"):
        assert legacy_value not in serialized_brain_request
    assert provider.requests[1]["stage"] == "provider_prompt_finalize"

    generated = handlers.post_project_job_generate(
        project["project_id"],
        job["job_id"],
        {"quality_mode": "standard"},
    )
    assert generated["status"] == "generated"
    assert len(generated["candidates"]) == count
    assert len(generated["ecommerce"]["remote_brain_output_intents"]) == count

    outputs = handlers.get_project_outputs(project_id=project["project_id"], limit=10, compact=True)["items"]
    assert len(outputs) == count
    assert {item["metadata"]["delivery_requested_image_count"] for item in outputs} == {count}


def test_doc132_legacy_preset_is_read_compatible_but_stripped_before_brain_and_delivery(tmp_path: Path) -> None:
    provider = EcommerceRemoteBrainTestProvider()
    handlers = _handlers(tmp_path, provider=provider)
    project, job = _new_project_job(handlers, count=2, legacy_mode="marketplace_listing_set")

    assert job["status"] == "planned"
    assert job["scenario"]["selected_mode_id"] is None
    assert job["scenario"]["selected_preset_id"] is None
    record = handlers.service.get_job_record(job["job_id"])
    assert record is not None
    ignored = record.request.metadata["ecommerce_legacy_execution_ignored"]
    assert ignored["status"] == "read_compatible_not_executed"
    assert {"selected_mode_id", "selected_preset_id"}.issubset(ignored["fields"])
    assert "marketplace_listing_set" not in json.dumps(provider.requests, ensure_ascii=False)

    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    assert generated["status"] == "generated"
    prompt = handlers.service.get_job_record(job["job_id"]).generation_result.prompt_compilations[0]
    assert "marketplace_listing_set" not in prompt.visual_prompt
    assert "ecommerce_recipe" not in prompt.metadata


def test_doc132_refresh_reopen_preserves_final_project_aggregation(tmp_path: Path) -> None:
    provider = EcommerceRemoteBrainTestProvider()
    handlers = _handlers(tmp_path, provider=provider)
    project, job = _new_project_job(handlers, count=2)
    handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    before = handlers.get_project_outputs(project_id=project["project_id"], limit=10, compact=True)["items"]

    reopened = V3ProductRouteHandlers(
        service=handlers.service,
        project_store=PersistentProjectStore(tmp_path / "projects"),
    )
    detail = reopened.get_project(project["project_id"])["project"]
    after = reopened.get_project_outputs(project_id=project["project_id"], limit=10, compact=True)["items"]

    assert detail["primary_template_id"] == "ecommerce_template"
    assert [item["output_id"] for item in after] == [item["output_id"] for item in before]
    assert len(after) == 2


def test_doc132_child_continuation_is_append_only_and_blocked_parent_has_no_delivery(tmp_path: Path) -> None:
    handlers = _handlers(tmp_path)
    project, root = _new_project_job(handlers, count=2)
    output_id = root["ecommerce"]["remote_brain_output_intents"][0]["output_id"]
    continuation = handlers.post_project_ecommerce_slot_continuation(
        project["project_id"],
        root["job_id"],
        output_id,
        {"correction_note": "Keep the same product truth while improving the requested direction."},
    )
    child = handlers.post_project_job_generate(
        project["project_id"], continuation["child_job_id"], {"quality_mode": "standard"}
    )
    delivery = handlers.get_project_ecommerce_slot_delivery(project["project_id"], root["job_id"], output_id)

    assert child["status"] == "generated"
    assert continuation["child_job_id"] != root["job_id"]
    assert delivery["current_delivery"]["job_id"] == continuation["child_job_id"]
    assert [item["job_id"] for item in delivery["attempts"]] == [root["job_id"], continuation["child_job_id"]]

    blocked_handlers = _handlers(tmp_path / "blocked", provider=EcommerceRemoteBrainTestProvider(fault="mismatched_image_set_plan"))
    blocked_project, blocked = _new_project_job(blocked_handlers, count=2)
    assert blocked["status"] == "blocked"
    assert blocked_handlers.get_project_outputs(project_id=blocked_project["project_id"], limit=10, compact=True)["items"] == []


def test_doc132_held_shared_delivery_is_not_projected_as_a_final_result(tmp_path: Path, monkeypatch) -> None:
    handlers = _handlers(tmp_path)
    project, job = _new_project_job(handlers, count=1)
    handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    original_get_job = handlers.service.get_job
    base_status = original_get_job(job["job_id"])
    held_status = base_status.model_copy(
        update={
            "status": ProductJobStatusValue.GENERATED,
            "metadata": {
                **dict(base_status.metadata or {}),
                "post_generation_review": {
                    "inspections": [
                        {
                            "output_id": base_status.candidates[0].candidate_id,
                            "mode": "hybrid",
                            "status": "manual_review",
                            "verification_state": "verified",
                        }
                    ]
                },
                "final_delivery": {
                    "final_delivery_status": "withheld_manual_confirmation",
                    "automatic_delivery_available": False,
                    "manual_confirmation_required": True,
                    "delivery_gate_applies": True,
                },
            },
        }
    )
    monkeypatch.setattr(
        handlers.service,
        "get_job",
        lambda job_id: held_status if job_id == job["job_id"] else original_get_job(job_id),
    )

    assert handlers.get_project_outputs(project_id=project["project_id"], limit=10, compact=True)["items"] == []


def test_doc132_browser_surface_has_no_executable_ecommerce_preset_or_fixed_suite_promise() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    script = APP_JS.read_text(encoding="utf-8")

    for legacy_value in ("one_click_product_set", "marketplace_listing_set", "style_recreation_set"):
        assert legacy_value not in html
        assert legacy_value not in script
    for fixed_promise in ("主图、卖点、场景、信任背书", "主图、卖点图、场景图、细节图和信任图"):
        assert fixed_promise not in html
    assert "中枢大脑会根据本次商品事实、用户需求及已验证的平台证据" in html
    assert 'if (scenarioId === "ecommerce") return null;' in script
    assert 'selected_mode_id: scenarioId === "ecommerce" ? undefined : v3State.selectedPreset' in script
