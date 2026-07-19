"""Provider-independent Doc132 closure for the Photography public contract.

These fixtures deliberately reuse the shared V3 generation, review, retry and
project-result projection seams.  They do not add a Photography renderer,
reviewer, selector or a local-MCP substitute for the specialised template.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
from alchemy_creative_agent_3_0.tests.photography_test_support import photography_test_service


ROLE_IDS = ["session_hero", "environmental_context", "detail_or_moment"]


def _create_photography_root(
    handlers: V3ProductRouteHandlers,
    *,
    mode_id: str,
) -> tuple[dict, dict]:
    project = handlers.post_projects(
        {
            "primary_template_id": "photographer_template",
            "user_goal": "Create a natural, restrained portrait session of an artist at work.",
        }
    )["project"]
    root = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "photographer_template",
            "user_input": "Create a natural, restrained portrait session of an artist at work.",
            "metadata": {"selected_mode_id": mode_id, "scene_domain": "portrait"},
        },
    )
    return project, root


@pytest.mark.parametrize(
    ("mode_id", "expected_role_ids"),
    [
        ("single_hero", ["hero_photograph"]),
        ("professional_set", ROLE_IDS),
    ],
)
def test_doc132_shared_fixture_keeps_frozen_role_lineage_and_current_winners_after_reopen(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode_id: str,
    expected_role_ids: list[str],
) -> None:
    """Both modes use shared execution; the set cannot collapse to one image."""

    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    project_store_root = tmp_path / "projects"
    service = photography_test_service()
    handlers = V3ProductRouteHandlers(
        service=service,
        project_store=PersistentProjectStore(project_store_root),
    )
    project, root = _create_photography_root(handlers, mode_id=mode_id)

    generated = handlers.post_project_job_generate(
        project["project_id"],
        root["job_id"],
        {"quality_mode": "standard"},
    )

    assert generated["status"] == "generated"
    summary = generated["metadata"]["specialized_execution_summary"]
    assert [role["role_key"] for role in summary["roles"]] == expected_role_ids
    assert len(generated["asset_series"]) == len(expected_role_ids)
    assert generated["metadata"]["final_delivery"]["final_delivery_output_count"] == len(expected_role_ids)

    # Role-delivery continuation is intentionally a professional-set surface.
    # Single-hero still uses the same shared execution/final-delivery result,
    # but must not grow specialist continuation UI.
    role_delivery_ids = ROLE_IDS if mode_id == "professional_set" else []
    for role_id in role_delivery_ids:
        delivery = handlers.get_project_photography_role_delivery(project["project_id"], root["job_id"], role_id)
        assert delivery["current_delivery"]["job_id"] == root["job_id"]
        assert delivery["current_delivery"]["role_id"] == role_id
        assert delivery["metadata"]["final_role_winner_only"] is True
        # Root execution remains in history even after the final winner is projected.
        assert [attempt["job_id"] for attempt in delivery["attempts"]] == [root["job_id"]]

    # Recreate only the public project projection boundary.  The shared service
    # retains its append-only job history, while the project summary is read
    # from the durable store exactly as a refresh/reopen surface does.
    reopened_handlers = V3ProductRouteHandlers(
        service=service,
        project_store=PersistentProjectStore(project_store_root),
    )
    recent = reopened_handlers.get_projects(limit=10)
    recent_summary = next(item for item in recent["projects"] if item["project_id"] == project["project_id"])
    reopened = reopened_handlers.get_project(project["project_id"])["project"]

    assert recent_summary["primary_template_id"] == "photographer_template"
    assert recent_summary["scenario_id"] == "photography"
    assert reopened["primary_template_id"] == "photographer_template"
    assert len(reopened_handlers.get_project_outputs(project_id=project["project_id"])["items"]) == len(expected_role_ids)


def test_doc132_browser_contract_keeps_photography_selected_and_set_count_structural_only() -> None:
    """The browser shell maps the persisted template ID, never a General fallback."""

    source = (Path(__file__).resolve().parents[2] / "src_skeleton" / "app" / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert 'if (templateId === "photographer_template") return "photography";' in source
    assert 'if (scenarioId === "photography") return "photographer_template";' in source
    assert 'const canonicalId = String(project?.primary_template_id || project?.template_id || "").trim();' in source
    assert '"摄影师模板": "photographer_template"' in source
    assert 'v3State.selectedPreset === "professional_set" ? 3 : 1' in source


def test_p14_browser_contract_uses_trusted_catalog_and_visible_photo_role_state() -> None:
    """Desktop/mobile UX must fail closed instead of silently becoming General."""

    root = Path(__file__).resolve().parents[2] / "src_skeleton" / "app"
    desktop = (root / "static" / "app.js").read_text(encoding="utf-8")
    mobile = (root / "mobile_static" / "mobile.js").read_text(encoding="utf-8")
    desktop_html = (root / "static" / "index.html").read_text(encoding="utf-8")
    mobile_html = (root / "mobile_static" / "index.html").read_text(encoding="utf-8")

    assert "templatesLoaded: false" in desktop
    assert "templatesError" in desktop
    assert "v3State.selectedPhotographyReferenceRole" in desktop
    assert "nonhuman_identity_reference" in desktop
    assert "function renderV3PhotographyRoleBoard" in desktop
    assert "final_delivery_withheld" in desktop
    assert "continue_photography" in desktop
    assert 'setV3Scenario("general_creative")' not in desktop[desktop.find("function handleV3ProjectActionClick"):desktop.find("function handleV3ProjectActionClick") + 1800]
    assert 'id="v3PhotographyRoleBoard"' in desktop_html
    assert 'data-v3-photography-scene="animal"' in desktop_html

    assert "templatesLoaded: false" in mobile
    assert "templatesError" in mobile
    assert 'if (templateId === "photographer_template") return "photography";' in mobile
    assert 'if (scenarioId === "photography") return "photographer_template";' in mobile
    assert "selectedPhotographyReferenceRole" in mobile
    assert "function renderMobileV3PhotographyRoleBoard" in mobile
    assert 'id="mobileV3PhotographyRoleBoard"' in mobile_html
    assert 'id="mobileV3PhotographerProfileInput"' in mobile_html


def test_p14_photography_next_actions_do_not_hide_shared_template_actions() -> None:
    """Photography owns only its branch; General/E-Commerce keep E23 actions."""

    source = (Path(__file__).resolve().parents[2] / "src_skeleton" / "app" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    start = source.index("function renderV3ProjectNextActions()")
    end = source.index("function renderV3BrandMemoryPanel()", start)
    body = source[start:end]

    assert 'if (projectScenario === "photography")' in body
    assert 'data-v3-project-action="continue_photography"' in body
    assert "Photography owns only the branch above" in body
    assert 'els.v3ProjectNextActions.hidden = false;' in body
    assert 'const hasSelectedRefs = v3UsefulReferenceItems(project).length > 0;' in body
    assert 'els.v3ProjectNextActions.hidden = true;\n  return;\n  const hasSelectedRefs' not in body


def test_doc132_metadata_only_professional_set_is_held_not_a_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-certifying review preserves all role truth but cannot become P10 success."""

    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers(service=photography_test_service())
    project, root = _create_photography_root(handlers, mode_id="professional_set")

    blocked = handlers.post_project_job_generate(
        project["project_id"],
        root["job_id"],
        {"quality_mode": "standard", "metadata": {"vision_inspection_mode": "metadata_only"}},
    )

    assert blocked["status"] == "blocked"
    summary = blocked["metadata"]["specialized_execution_summary"]
    assert [role["role_key"] for role in summary["roles"]] == ROLE_IDS
    assert summary["final_delivery_withheld"] is True
    certification = blocked["metadata"]["review_certification"]
    assert certification["state"] == "blocked"
    assert certification["automatic_delivery_certified"] is False
    assert [role["role_key"] for role in certification["roles"]] == ROLE_IDS
    assert all(role["review_mode"] == "metadata_only" for role in certification["roles"])
    assert handlers.get_project_outputs(project_id=project["project_id"])["items"] == []
