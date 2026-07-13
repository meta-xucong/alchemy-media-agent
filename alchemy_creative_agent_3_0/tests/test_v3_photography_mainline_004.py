from __future__ import annotations

from copy import deepcopy
import base64
from io import BytesIO
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
from alchemy_creative_agent_3_0.app.project_mode.service import PhotographyRoleContinuationError
from alchemy_creative_agent_3_0.app.scenario_packs.photography import (
    PhotographerProfile,
    PhotographerProfileAvailability,
    PhotographerProfileCatalog,
    PhotographerProfileKind,
    PhotographerProfileRightsStatus,
    PhotographyScenarioPackPlanner,
    PhotographyTechniquePackage,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_runtime.specialized_planning import PhotographyScenarioPlanningAdapter


def _project_and_root(
    handlers: V3ProductRouteHandlers,
    *,
    profile: dict | None = None,
    mode_id: str = "professional_set",
) -> tuple[dict, dict]:
    project = handlers.post_projects(
        {
            "primary_template_id": "photographer_template",
            "user_goal": "Create a professional portrait session of a ceramic artist in her studio.",
        }
    )["project"]
    root = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "photographer_template",
            "user_input": "Create a professional portrait session of a ceramic artist in her studio.",
            "photographer_profile_id": profile.get("profile_id") if profile else None,
            "photographer_profile_selection_source": profile.get("selection_source") if profile else None,
            "metadata": {"selected_mode_id": mode_id, "scene_domain": "portrait"},
        },
    )
    assert root["status"] == "planned"
    return project, root


def _ready_nonhuman_identity_upload(handlers: V3ProductRouteHandlers, *, filename: str) -> str:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(170, 142, 96)).save(buffer, format="PNG")
    created = handlers.post_uploads(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": len(buffer.getvalue()),
            "role": "nonhuman_identity_reference",
        }
    )
    handlers.put_upload_content(
        created["asset_id"],
        {"content_base64": base64.b64encode(buffer.getvalue()).decode("ascii"), "mime_type": "image/png"},
    )
    assert handlers.post_upload_complete(created["asset_id"])["status"] == "ready"
    return created["asset_id"]


def test_professional_set_executes_three_frozen_roles_and_resolves_one_winner_per_role(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers()
    project, root = _project_and_root(handlers)
    record = handlers.service.get_job_record(root["job_id"])
    assert record is not None
    specialized = record.request.metadata["specialized_scenario_plan"]
    assert specialized["execution_plan"]["metadata"]["professional_set"] is True
    assert [item["role_key"] for item in specialized["execution_plan"]["role_recipes"]] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]

    generated = handlers.post_project_job_generate(project["project_id"], root["job_id"], {"quality_mode": "standard"})
    assert generated["status"] == "generated"
    assert len(generated["asset_series"]) == 3
    assert [item["metadata"]["asset_metadata"]["mode_role_key"] for item in generated["asset_series"]] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]
    assert len(generated["metadata"]["post_generation_review"]["inspections"]) == 3

    for role_id in ("session_hero", "environmental_context", "detail_or_moment"):
        delivery = handlers.get_project_photography_role_delivery(project["project_id"], root["job_id"], role_id)
        assert delivery["current_delivery"]["job_id"] == root["job_id"]
        assert delivery["current_delivery"]["role_id"] == role_id
        assert delivery["metadata"]["final_role_winner_only"] is True


def test_photography_project_summary_and_terminal_delivery_keep_the_photographer_binding(monkeypatch) -> None:
    """A Photography project must never be summarized as General after a terminal job."""

    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers()
    project, root = _project_and_root(handlers, mode_id="single_hero")

    assert project["primary_template_id"] == "photographer_template"
    assert project["memory_summary"]["active_template_label"] == "摄影师模板"
    assert root["scenario"]["scenario_id"] == "photography"
    assert root["metadata"]["template_id"] == "photographer_template"

    generated = handlers.post_project_job_generate(project["project_id"], root["job_id"], {"quality_mode": "standard"})
    assert generated["status"] == "generated"
    assert generated["scenario"]["scenario_id"] == "photography"
    assert len(generated["asset_series"]) == 1
    assert all(item["output_id"] for item in generated["asset_series"])

    reopened = handlers.get_project(project["project_id"])["project"]
    recent = handlers.get_projects(limit=10)
    summary = next(item for item in recent["projects"] if item["project_id"] == project["project_id"])
    terminal = handlers.get_job(root["job_id"])
    timeline = handlers.get_project_timeline(project["project_id"])["items"]

    assert reopened["primary_template_id"] == "photographer_template"
    assert reopened["memory_summary"]["active_template_label"] == "摄影师模板"
    assert summary["active_template_label"] == "摄影师模板"
    assert terminal["status"] == "generated"
    assert terminal["scenario"]["scenario_id"] == "photography"
    assert len(terminal["asset_series"]) == 1
    assert terminal["asset_series"][0]["output_id"]
    assert terminal["asset_series"][0]["preview_url"]
    assert any(item["item_type"] == "job_generated" and item["job_id"] == root["job_id"] for item in timeline)


def test_role_continuation_is_append_only_and_reuses_the_exact_frozen_plan(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers()
    project, root = _project_and_root(handlers)
    handlers.post_project_job_generate(project["project_id"], root["job_id"], {"quality_mode": "standard"})
    root_record = handlers.service.get_job_record(root["job_id"])
    assert root_record is not None
    frozen_parent_metadata = deepcopy(root_record.request.metadata)

    continuation = handlers.post_project_photography_role_continuation(
        project["project_id"],
        root["job_id"],
        "environmental_context",
        {"correction_note": "Show more of the working studio while keeping the same color finish."},
    )
    child_record = handlers.service.get_job_record(continuation["child_job_id"])
    assert child_record is not None
    assert continuation["lineage"]["root_job_id"] == root["job_id"]
    assert continuation["lineage"]["parent_role_id"] == "environmental_context"
    assert child_record.request.metadata["capability_activation_plan"] == frozen_parent_metadata["capability_activation_plan"]
    child_execution = child_record.request.metadata["specialized_scenario_plan"]["execution_plan"]
    assert child_execution["requested_image_count"] == 1
    assert [item["role_key"] for item in child_execution["role_recipes"]] == ["environmental_context"]
    assert root_record.request.metadata == frozen_parent_metadata

    child = handlers.post_project_job_generate(project["project_id"], continuation["child_job_id"], {"quality_mode": "standard"})
    assert child["status"] == "generated"
    assert len(child["asset_series"]) == 1
    delivery = handlers.get_project_photography_role_delivery(project["project_id"], root["job_id"], "environmental_context")
    assert delivery["current_delivery"]["job_id"] == continuation["child_job_id"]
    assert [attempt["job_id"] for attempt in delivery["attempts"]] == [root["job_id"], continuation["child_job_id"]]


def test_named_profile_continuation_requires_exact_explicit_reconfirmation(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    operator_catalog = PhotographerProfileCatalog(
        profiles=[
            PhotographerProfile(
                profile_id="licensed_session_v1",
                profile_version="2026.07",
                profile_kind=PhotographerProfileKind.NAMED_PHOTOGRAPHER,
                public_display_name="Licensed Session Profile",
                supported_scene_ids=["portrait"],
                supported_commission_ids=["single_hero", "professional_session"],
                technique_package=PhotographyTechniquePackage(
                    composition=["deliberate environmental portrait hierarchy"],
                    lighting=["soft directional window light"],
                ),
                rights_status=PhotographerProfileRightsStatus.APPROVED,
                availability_status=PhotographerProfileAvailability.ACTIVE,
                allowed_regions=["CN"],
            )
        ],
        catalog_version="mainline-004-test",
    )
    runtime = ScenarioRuntime(
        specialized_planning_adapters=[
            PhotographyScenarioPlanningAdapter(
                planner=PhotographyScenarioPackPlanner(
                    profile_catalog=operator_catalog,
                    named_profiles_enabled=True,
                )
            )
        ]
    )
    service = V3ProductApiService(
        scenario_runtime=runtime,
        photographer_profile_catalog=operator_catalog.shared_catalog(),
        photographer_profile_region_resolver=lambda: "CN",
    )
    handlers = V3ProductRouteHandlers(service=service)
    project, root = _project_and_root(
        handlers,
        profile={"profile_id": "licensed_session_v1", "selection_source": "user_explicit_ui"},
    )
    with pytest.raises(PhotographyRoleContinuationError, match="named_profile_continuation_requires_explicit_ui_reconfirmation"):
        handlers.post_project_photography_role_continuation(
            project["project_id"], root["job_id"], "session_hero", {"correction_note": "Use a calmer expression."}
        )
    binding = service.photographer_profile_binding_for_job(root["job_id"])
    assert binding is not None
    continuation = handlers.post_project_photography_role_continuation(
        project["project_id"],
        root["job_id"],
        "session_hero",
        {
            "correction_note": "Use a calmer expression.",
            "profile_selection_source": "user_explicit_ui",
            "reconfirmed_profile_id": binding.profile_id,
            "reconfirmed_profile_version": binding.profile_version,
            "reconfirmed_technique_package_checksum": binding.technique_package_checksum,
        },
    )
    child_binding = service.photographer_profile_binding_for_job(continuation["child_job_id"])
    assert child_binding is not None
    assert child_binding.model_dump(mode="json") == binding.model_dump(mode="json")


def test_role_lineage_survives_project_store_reload_and_general_is_rejected(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    store_root = Path(tmp_path) / "projects"
    first = V3ProductRouteHandlers(project_store=PersistentProjectStore(store_root))
    project, root = _project_and_root(first)
    restarted = V3ProductRouteHandlers(project_store=PersistentProjectStore(store_root))
    continuation = restarted.post_project_photography_role_continuation(
        project["project_id"], root["job_id"], "detail_or_moment", {"correction_note": "Emphasize the hands and clay detail."}
    )
    delivery = restarted.get_project_photography_role_delivery(project["project_id"], root["job_id"], "detail_or_moment")
    assert continuation["child_status"] == "planned"
    assert [item["job_id"] for item in delivery["attempts"]] == [root["job_id"], continuation["child_job_id"]]

    general = first.post_projects({"user_goal": "Create an abstract book cover"})["project"]
    general_job = first.post_project_job(general["project_id"], {"user_input": "Create an abstract book cover"})
    with pytest.raises(PhotographyRoleContinuationError) as unsupported:
        first.post_project_photography_role_continuation(
            general["project_id"], general_job["job_id"], "session_hero", {}
        )
    assert unsupported.value.code == "photography_role_continuation_not_supported"


def test_new_animal_identity_evidence_is_renegotiated_and_blocks_without_shared_native_support(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers()
    original_reference = _ready_nonhuman_identity_upload(handlers, filename="dog-original.png")
    project = handlers.post_projects(
        {
            "primary_template_id": "photographer_template",
            "user_goal": "Professionally reshoot the same dog running through a forest.",
            "uploaded_asset_ids": [original_reference],
        }
    )["project"]
    root = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "photographer_template",
            "user_input": "Professionally reshoot the same dog running through a forest.",
            "uploaded_asset_ids": [original_reference],
            "metadata": {
                "selected_mode_id": "professional_set",
                "scene_domain": "animal",
                "preserve_nonhuman_identity": True,
            },
        },
    )
    root_record = handlers.service.get_job_record(root["job_id"])
    assert root_record is not None
    assert "nonhuman_subject_identity" in root_record.request.metadata["capability_activation_plan"]["dependency_order"]
    new_reference = _ready_nonhuman_identity_upload(handlers, filename="dog-new-angle.png")
    handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": new_reference, "use_policy": "identity", "label": "new dog identity view"},
    )
    preview_calls: list[dict] = []

    def unavailable(payload: dict):
        preview_calls.append(payload)
        raise RuntimeError("native high-fidelity identity support unavailable")

    monkeypatch.setattr(handlers.service, "preview_capability_activation", unavailable)
    with pytest.raises(PhotographyRoleContinuationError) as blocked:
        handlers.post_project_photography_role_continuation(
            project["project_id"],
            root["job_id"],
            "session_hero",
            {"new_reference_asset_ids": [new_reference]},
        )
    assert blocked.value.code == "photography_role_plan_amendment_unavailable"
    assert preview_calls and new_reference in preview_calls[0]["uploaded_asset_ids"]
    assert preview_calls[0]["scenario_selection"]["scenario_id"] == "photography"
