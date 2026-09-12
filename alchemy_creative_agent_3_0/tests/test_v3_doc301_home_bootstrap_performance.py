"""Regression contracts for the V3 home bootstrap performance repair."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore, V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.contracts import OutputRef


ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "301_V3_HOME_BOOTSTRAP_PERFORMANCE_AND_V2_PARITY_SPEC.md"
ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def _service() -> tuple[V3ProjectModeService, str]:
    service = V3ProjectModeService(
        product_service=V3ProductApiService(),
        project_store=InMemoryProjectStore(),
    )
    response = service.create_project({"user_goal": "Create a useful project preview."})
    assert response.project is not None
    return service, response.project.project_id


def test_summary_project_list_does_not_reconcile_jobs_outputs_or_timeline() -> None:
    service, project_id = _service()

    def unexpected(*_args, **_kwargs):
        raise AssertionError("summary catalog must not read the full project history")

    service._memory_summary = unexpected
    service._project_output_items = unexpected
    service._latest_project_job_status = unexpected
    service.project_store.list_timeline = unexpected

    response = service.list_projects(limit=1, view="summary")

    assert [item.project_id for item in response.projects] == [project_id]
    assert response.metadata["view"] == "summary"
    assert response.projects[0].latest_thumbnail_urls == []
    assert response.projects[0].latest_job_status is None


def test_summary_project_list_does_not_dereference_selected_output_records() -> None:
    service, project_id = _service()
    project = service.project_store.get_project(project_id)
    assert project is not None
    project.selected_output_refs = [
        OutputRef(
            output_ref_id="output-ref-summary",
            source_type="generated_output",
            project_id=project_id,
            output_id="v3_output_summary_selected",
            selected_at=project.updated_at,
        )
    ]
    service.project_store.save_project(project)

    def unexpected(*_args, **_kwargs):
        raise AssertionError("summary catalog must not dereference output records")

    service.product_service.output_store.get_output = unexpected

    response = service.list_projects(limit=1, owner_user_id=None, view="summary")

    assert response.projects[0].selected_asset_count == 1


def test_global_output_delivery_and_review_share_one_request_snapshot() -> None:
    project = SimpleNamespace(
        project_id="project_snapshot",
        status="active",
        job_ids=["job_snapshot"],
    )
    calls = {"job": 0, "job_record": 0, "output": 0}
    output_record = SimpleNamespace(output_id="v3_output_snapshot", job_id="job_snapshot")

    class _Product:
        output_store = SimpleNamespace(
            list_by_job=lambda _job_id: calls.__setitem__("output", calls["output"] + 1) or [output_record],
        )

        @staticmethod
        def get_job(_job_id):
            calls["job"] += 1
            return SimpleNamespace(metadata={})

        @staticmethod
        def get_job_record(_job_id):
            calls["job_record"] += 1
            return SimpleNamespace(request=SimpleNamespace(metadata={}))

    service = object.__new__(V3ProjectModeService)
    service.product_service = _Product()
    service.project_store = SimpleNamespace(list_projects=lambda limit: [project])
    service._metadata = lambda: {}
    service._project_visible_to_owner = lambda *_args: True
    delivery_kwargs = []
    review_kwargs = []
    service._project_output_items = lambda *_args, **kwargs: delivery_kwargs.append(kwargs) or []
    service._project_review_output_items = lambda *_args, **kwargs: review_kwargs.append(kwargs) or []

    response = service.list_project_outputs(limit=1, compact=True)

    assert response["items"] == []
    assert response["review_items"] == []
    assert calls == {"job": 1, "job_record": 1, "output": 1}
    assert delivery_kwargs[0]["job_status_by_id"] is review_kwargs[0]["job_status_by_id"]
    assert delivery_kwargs[0]["job_record_by_id"] is review_kwargs[0]["job_record_by_id"]
    assert delivery_kwargs[0]["output_records_by_job"] is review_kwargs[0]["output_records_by_job"]


def test_default_project_list_keeps_full_view_compatibility_metadata() -> None:
    service, _project_id = _service()

    response = service.list_projects(limit=1)

    assert response.metadata["view"] == "full"
    assert response.projects[0].latest_job_status is None


def test_home_preview_is_bounded_delivery_only_and_skips_full_history_paths() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(
        project_id="project_home_preview",
        status="active",
    )
    service.project_store = SimpleNamespace(list_projects=lambda limit: [project])
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_delivery_preview_items = lambda *_args, **_kwargs: [
        {
            "project_id": project.project_id,
            "output_id": "v3_output_preview",
            "created_at": "2026-09-13T00:00:00Z",
        }
    ]
    service._project_output_items = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("home preview must not use the full delivery/history projection")
    )
    service._project_review_output_items = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("home preview must not read review history")
    )
    service._reconcile_project_outputs = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("home preview must not reconcile project history")
    )
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
    )

    assert response["items"][0]["output_id"] == "v3_output_preview"
    assert response["review_items"] == []
    assert response["metadata"]["surface"] == "home_preview"
    assert response["metadata"]["complete"] is False


def test_desktop_home_bootstrap_releases_before_output_and_image_work() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    shell = source.split("async function initV3Shell", 1)[1].split(
        "function clearV3PendingUploads", 1
    )[0]
    projects = source.split("async function loadV3Projects", 1)[1].split(
        "async function loadV3History", 1
    )[0]

    assert "&view=summary" in shell
    assert "surface: \"home_preview\"" in shell
    assert "await loadV3ProjectOutputs" not in shell
    assert "await waitForV3FirstHomePreviewImage" not in shell
    assert "return waitForV3HomePreviewImages({ blockPage: false });" in shell
    assert 'v3State.imageHistoryLoaded = normalizedSurface !== "home_preview"' in source
    assert 'const previewOnly = v3State.imageHistorySurface === "home_preview"' in source
    assert "if ((!group.items.length || previewOnly) && group.projectId)" in source
    assert "&view=summary${cursor}" in projects
    assert "!v3State.loading" in source.split("function openV3Home", 1)[1].split(
        "function openV3ProfessionalWorkspace", 1
    )[0]


def test_mobile_home_bootstrap_releases_before_output_and_image_work() -> None:
    source = MOBILE.read_text(encoding="utf-8")
    loader = source.split("async function loadMobileV3Projects", 1)[1].split(
        "function setMobileV3LoadingLayer", 1
    )[0]

    assert "&view=summary${cursor}" in loader
    assert "surface=home_preview" in loader
    assert "await mobileV3Request(`/project-outputs?limit=${mobileV3ProjectPageSize}&compact=true`)" not in loader
    assert "await waitForMobileV3FirstHomePreviewImage()" not in loader
    assert "return waitForMobileV3HomePreviewImages({ blockPage: false });" in loader
    assert "previewProjectIds" in source
    assert "已有封面 · 点击查看全部" in source


def test_home_output_loader_allows_small_preview_limit_without_global_minimum() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    loader = source.split("async function loadV3ProjectOutputs", 1)[1].split(
        "function clearV3PendingUploads", 1
    )[0]

    assert "surface = \"\"" in loader
    assert 'normalizedSurface === "home_preview" ? 1 : 12' in loader
    assert "surfaceQuery" in loader


def test_output_store_reuses_warm_record_index_and_rechecks_changed_media(tmp_path: Path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id="job_home_cache",
        candidate_id="candidate_home_cache",
        asset_id="asset_home_cache",
        provider="test",
        model="test-model",
        encoded_image=ONE_PIXEL_PNG,
    )
    assert store.list_by_job(record.job_id)

    with patch.object(Path, "read_text", side_effect=AssertionError("warm get_output must use the parsed index")):
        assert store.get_output(record.output_id) is not None

    assert store.file_for_variant(record.output_id, "thumbnail") is not None
    original = Path(record.file_path)
    original.write_bytes(original.read_bytes() + b"changed")
    assert store.file_for_variant(record.output_id, "thumbnail") is None


def test_doc301_freezes_compatibility_and_acceptance_boundaries() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "GET /api/v3/creative-agent/projects?view=summary" in doc
    assert "surface=home_preview" in doc
    assert "Existing callers" in doc
    assert "No Brain, Provider, Review, Retry" in doc
    assert "independently audited" in doc
