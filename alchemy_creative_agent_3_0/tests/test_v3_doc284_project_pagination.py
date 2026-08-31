from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectMemorySummary, ProjectRecord
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService


def _project(project_id: str, updated_at: str, owner_id: int) -> ProjectRecord:
    return ProjectRecord(
        project_id=project_id,
        title=project_id,
        user_goal=f"goal {project_id}",
        short_summary=f"summary {project_id}",
        created_at=updated_at,
        updated_at=updated_at,
        metadata={"veyra_user_id": owner_id},
    )


class _ProjectStore:
    def __init__(self, projects: list[ProjectRecord]) -> None:
        self.projects = projects

    def list_all_projects(self) -> list[ProjectRecord]:
        return list(self.projects)


def _service(projects: list[ProjectRecord]) -> V3ProjectModeService:
    service = object.__new__(V3ProjectModeService)
    service.project_store = _ProjectStore(projects)
    service._memory_summary = lambda project, *, owner_user_id=None: ProjectMemorySummary(
        project_id=project.project_id,
        title=project.title,
        goal=project.short_summary,
        updated_at=project.updated_at,
    )
    service.template_cards = lambda: []
    service._metadata = lambda: {}
    return service


def test_project_pagination_returns_each_owned_project_once() -> None:
    projects = [
        _project("project_5", "2026-08-30T00:05:00+00:00", 7),
        _project("project_4", "2026-08-30T00:04:00+00:00", 7),
        _project("project_3", "2026-08-30T00:03:00+00:00", 9),
        _project("project_2", "2026-08-30T00:02:00+00:00", 7),
        _project("project_1", "2026-08-30T00:01:00+00:00", 7),
        _project("project_0", "2026-08-30T00:00:00+00:00", 7),
    ]
    service = _service(projects)
    service._reconcile_project_outputs = lambda project: pytest.fail(
        "project listing must remain a read-only summary projection"
    )

    first = service.list_projects(limit=2, owner_user_id=7)
    second = service.list_projects(limit=2, owner_user_id=7, cursor=first.next_cursor)
    third = service.list_projects(limit=2, owner_user_id=7, cursor=second.next_cursor)

    ids = [item.project_id for item in [*first.projects, *second.projects, *third.projects]]
    assert ids == ["project_5", "project_4", "project_2", "project_1", "project_0"]
    assert first.total == 5
    assert first.has_more is True
    assert second.has_more is True
    assert third.has_more is False
    assert third.next_cursor is None


def test_project_pagination_rejects_malformed_cursor() -> None:
    service = _service([_project("project_1", "2026-08-30T00:01:00+00:00", 7)])

    with pytest.raises(ValueError) as error:
        service.list_projects(limit=1, owner_user_id=7, cursor="not-a-v3-cursor")

    assert str(error.value) == "v3_project_cursor_invalid"


def test_project_list_builds_summaries_only_for_the_requested_page() -> None:
    projects = [
        _project(f"project_{index}", f"2026-08-30T00:{index:02d}:00+00:00", 7)
        for index in range(20)
    ]
    service = _service(projects)
    summarized: list[str] = []
    owners: list[int | None] = []
    service._memory_summary = lambda project, *, owner_user_id=None: (
        owners.append(owner_user_id)
        or
        summarized.append(project.project_id)
        or ProjectMemorySummary(
            project_id=project.project_id,
            title=project.title,
            goal=project.short_summary,
            updated_at=project.updated_at,
        )
    )

    response = service.list_projects(limit=3, owner_user_id=7)

    assert len(response.projects) == 3
    assert summarized == [item.project_id for item in response.projects]
    assert owners == [7, 7, 7]


def test_global_project_output_listing_does_not_reconcile_each_project() -> None:
    project = _project("project_1", "2026-08-30T00:01:00+00:00", 7)
    service = object.__new__(V3ProjectModeService)
    service.project_store = SimpleNamespace(list_projects=lambda limit: [project])
    service._metadata = lambda: {}
    service._project_output_items = lambda *args, **kwargs: []
    service._project_review_output_items = lambda *args, **kwargs: []
    service._reconcile_project_outputs = lambda value: pytest.fail(
        "global output listing must not mutate or reconcile project history"
    )

    response = service.list_project_outputs(limit=10, owner_user_id=7, compact=True)

    assert response["items"] == []
    assert response["review_items"] == []
