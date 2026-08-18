from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore, V3ProjectModeService
from alchemy_creative_agent_3_0.app.product_api.contracts import (
    CreateCreativeJobRequest,
    ProductJobStatusValue,
)
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import ProductJobRecord, V3ProductApiService
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from app import main as app_main


def _service() -> V3ProjectModeService:
    return V3ProjectModeService(
        product_service=V3ProductApiService(),
        project_store=InMemoryProjectStore(),
    )


def test_doc277_pending_planning_is_project_durable_and_idempotent() -> None:
    service = _service()
    project = service.create_project(
        {
            "user_goal": "Create one clean commercial portrait.",
            "primary_template_id": "general_template",
        }
    ).project
    payload = {
        "user_input": "Create one clean commercial portrait.",
        "template_id": "general_template",
        "metadata": {"require_real_images": True, "requested_image_count": 1},
    }

    first = service.begin_project_planning_operation(project.project_id, payload)
    replay = service.begin_project_planning_operation(project.project_id, payload)
    conflict = service.begin_project_planning_operation(
        project.project_id,
        {
            **payload,
            "user_input": "Create a different commercial portrait.",
        },
    )

    assert first["state"] == "planning"
    assert first["pending"] is True
    assert first["terminal"] is False
    assert replay == first
    assert conflict == first
    response = service.get_project(project.project_id)
    assert response.metadata["current_operation"] == first
    assert response.project.job_ids == []


def test_doc277_planning_completion_binds_one_job_and_failure_is_safe_terminal() -> None:
    service = _service()
    project = service.create_project(
        {
            "user_goal": "Create one clean commercial portrait.",
            "primary_template_id": "general_template",
        }
    ).project
    operation = service.begin_project_planning_operation(
        project.project_id,
        {
            "user_input": "Create one clean commercial portrait.",
            "template_id": "general_template",
        },
    )

    completed = service.complete_project_planning_operation(
        project.project_id,
        operation["operation_id"],
        job_id="job_doc277",
    )
    assert completed["job_id"] == "job_doc277"
    assert "current_operation" not in service.get_project(project.project_id).metadata

    next_operation = service.begin_project_planning_operation(
        project.project_id,
        {
            "user_input": "Create another clean commercial portrait.",
            "template_id": "general_template",
        },
    )
    failed = service.fail_project_planning_operation(
        project.project_id,
        next_operation["operation_id"],
        failure_code="planning_unavailable",
    )
    assert failed == {
        "operation_id": next_operation["operation_id"],
        "state": "planning_failed",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_project_request"}],
    }
    assert service.get_project(project.project_id).metadata["current_operation"] == failed


def test_doc277_terminal_job_overrides_stale_planning_projection() -> None:
    """A terminal Job must not leave the project UI stuck in planning."""

    service = _service()
    project = service.create_project(
        {
            "user_goal": "Create one clean commercial portrait.",
            "primary_template_id": "general_template",
        }
    ).project
    operation = service.begin_project_planning_operation(
        project.project_id,
        {
            "user_input": "Create one clean commercial portrait.",
            "template_id": "general_template",
        },
    )
    job_id = "job_doc277_terminal_projection"
    current_project = service.project_store.get_project(project.project_id)
    job_created_at = datetime.now(timezone.utc) + timedelta(seconds=1)
    service.product_service.job_store.save(
        ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="Create one clean commercial portrait.",
                metadata={"project_id": project.project_id},
            ),
            status=ProductJobStatusValue.BLOCKED,
            job_id_value=job_id,
            created_at=job_created_at.astimezone(timezone.utc).isoformat(),
        )
    )
    current_project.job_ids.append(job_id)
    service.project_store.save_project(current_project)

    response = service.get_project(project.project_id)

    assert response.project.job_ids == [job_id]
    assert response.metadata["current_operation"] == {
        "state": "failed_no_delivery",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "continue"}],
    }


def test_doc277_restart_closes_pending_operation_without_replaying_or_creating_a_job() -> None:
    service = _service()
    project = service.create_project(
        {
            "user_goal": "Create one clean commercial portrait.",
            "primary_template_id": "general_template",
        }
    ).project
    operation = service.begin_project_planning_operation(
        project.project_id,
        {
            "user_input": "Create one clean commercial portrait.",
            "template_id": "general_template",
        },
    )

    assert service.close_interrupted_project_planning_operations() == 1
    response = service.get_project(project.project_id)
    assert response.project.job_ids == []
    assert response.metadata["current_operation"] == {
        "operation_id": operation["operation_id"],
        "state": "planning_failed",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_project_request"}],
    }


def test_doc277_restart_recovery_closes_pending_operation_beyond_public_project_list_limit() -> None:
    service = _service()
    interrupted = service.create_project(
        {
            "user_goal": "Create one clean commercial portrait.",
            "primary_template_id": "general_template",
        }
    ).project
    operation = service.begin_project_planning_operation(
        interrupted.project_id,
        {
            "user_input": "Create one clean commercial portrait.",
            "template_id": "general_template",
        },
    )
    for index in range(100):
        service.create_project(
            {
                "user_goal": f"Later project {index}.",
                "primary_template_id": "general_template",
            }
        )

    assert len(service.list_projects(limit=100).projects) == 100
    assert service.close_interrupted_project_planning_operations() == 1
    response = service.get_project(interrupted.project_id)
    assert response.project.job_ids == []
    assert response.metadata["current_operation"] == {
        "operation_id": operation["operation_id"],
        "state": "planning_failed",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_project_request"}],
    }


def test_doc277_browser_cannot_forge_a_current_planning_operation() -> None:
    service = _service()
    project = service.create_project(
        {
            "user_goal": "Create one clean commercial portrait.",
            "primary_template_id": "general_template",
            "metadata": {
                "doc277_planning_current_operation": {
                    "operation_id": "forged",
                    "state": "planning",
                    "terminal": False,
                    "pending": True,
                }
            },
        }
    ).project

    assert "current_operation" not in service.get_project(project.project_id).metadata


def test_doc277_http_planning_returns_promptly_and_coalesces_one_background_start(monkeypatch) -> None:
    handlers = V3ProductRouteHandlers(
        service=V3ProductApiService(),
        project_store=InMemoryProjectStore(),
    )
    monkeypatch.setattr(app_main, "v3_route_handlers", handlers)
    queued: list[tuple[object, tuple[object, ...]]] = []
    monkeypatch.setattr(
        app_main._v3_planning_executor,
        "submit",
        lambda fn, *args: queued.append((fn, args)),
    )

    client = TestClient(app_main.app)
    project_id = client.post(
        "/api/v3/creative-agent/projects",
        json={"user_goal": "Create one clean commercial portrait."},
    ).json()["project"]["project_id"]
    payload = {
        "user_input": "Create one clean commercial portrait.",
        "template_id": "general_template",
        "auto_generate": {"quality_mode": "standard", "metadata": {"require_real_images": True}},
    }
    first = client.post(f"/api/v3/creative-agent/projects/{project_id}/jobs", json=payload)
    replay = client.post(f"/api/v3/creative-agent/projects/{project_id}/jobs", json=payload)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["status"] == "planning"
    assert replay.json()["status"] == "planning"
    assert first.json()["metadata"]["current_operation"] == replay.json()["metadata"]["current_operation"]
    assert len(queued) == 1
    operation_id = first.json()["metadata"]["current_operation"]["operation_id"]
    with app_main._v3_background_planning_operations_lock:
        app_main._v3_background_planning_operations.pop(f"{project_id}:{operation_id}", None)


def test_doc277_background_planning_failure_closes_without_creating_a_job(monkeypatch) -> None:
    handlers = V3ProductRouteHandlers(
        service=V3ProductApiService(),
        project_store=InMemoryProjectStore(),
    )
    monkeypatch.setattr(app_main, "v3_route_handlers", handlers)
    queued: list[tuple[object, tuple[object, ...]]] = []
    monkeypatch.setattr(
        app_main._v3_planning_executor,
        "submit",
        lambda fn, *args: queued.append((fn, args)),
    )
    monkeypatch.setattr(
        handlers,
        "post_project_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("planner unavailable")),
    )

    client = TestClient(app_main.app)
    project_id = client.post(
        "/api/v3/creative-agent/projects",
        json={"user_goal": "Create one clean commercial portrait."},
    ).json()["project"]["project_id"]
    response = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/jobs",
        json={
            "user_input": "Create one clean commercial portrait.",
            "template_id": "general_template",
            "auto_generate": {"quality_mode": "standard", "metadata": {"require_real_images": True}},
        },
    )
    assert response.status_code == 200
    assert len(queued) == 1

    worker, arguments = queued.pop()
    worker(*arguments)

    project = client.get(f"/api/v3/creative-agent/projects/{project_id}").json()
    operation = project["metadata"]["current_operation"]
    assert operation["state"] == "planning_failed"
    assert operation["next_actions"] == [{"id": "review_project_request"}]
    assert project["project"]["job_ids"] == []


def _planning_failed_project() -> dict:
    return {
        "project_id": "doc277-project",
        "title": "Planning failure",
        "user_goal": "Create one clean commercial portrait.",
        "short_summary": "Create one clean commercial portrait.",
        "primary_template_id": "general_template",
        "job_ids": [],
        "metadata": {
            "current_operation": {
                "operation_id": "doc277-operation",
                "state": "planning_failed",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_project_request"}],
            }
        },
    }


def test_doc277_desktop_terminal_planning_never_shows_preparing_or_retries() -> None:
    project = _planning_failed_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                (project) => {
                  v3State.currentProject = project;
                  v3State.currentJob = { job_id: "stale-job", status: "planned" };
                  v3State.selectedScenario = "general_creative";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "general_template", project_can_create_jobs: true }];
                  document.querySelector("#v3ProjectNextActions").addEventListener("click", handleV3ProjectActionClick);
                  renderV3ProjectNextActions();
                }
                """,
                project,
            )
            text = page.locator("#v3ProjectNextActions").inner_text()
            assert "本次规划未完成" in text
            assert "正在准备生成" not in page.locator("body").inner_text()
            assert page.locator("[data-v3-project-action='review_project_request']").count() == 1
            assert page.locator("[data-v3-project-action='start_first_generation']").count() == 0

            page.locator("[data-v3-project-action='review_project_request']").click()
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()


def test_doc277_mobile_terminal_planning_never_shows_preparing_or_retries() -> None:
    project = _planning_failed_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                (project) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  mobileV3State.currentProject = project;
                  mobileV3State.projects = [project];
                  mobileV3State.currentJob = { job_id: "stale-job", status: "planned" };
                  mobileV3State.selectedTemplate = "general_template";
                  renderMobileV3ProjectCurrentOperation(project);
                  openMobileSurface("v3-project-detail");
                }
                """,
                project,
            )
            text = page.locator("#mobileV3ProjectCurrentOperation").inner_text()
            assert "本次规划未完成" in text
            assert "正在准备生成" not in page.locator("body").inner_text()
            assert page.locator("[data-mobile-v3-project-action='review_project_request']").count() == 1

            page.locator("[data-mobile-v3-project-action='review_project_request']").click()
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()
