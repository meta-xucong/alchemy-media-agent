import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest

from alchemy_creative_agent_3_0.app.product_api import CreateCreativeJobRequest, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.service import PersistentProductJobStore, ProductJobRecord
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectMemorySummary,
    ProjectRecord,
    ProjectTimelineItem,
    TimelineItemType,
)
from alchemy_creative_agent_3_0.app.project_mode.service import _PROJECT_OUTPUT_JOB_METADATA_KEYS
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.store import PersistentProjectStore


def _project(project_id: str, updated_at: str, *, owner_id: int = 7) -> ProjectRecord:
    return ProjectRecord(
        project_id=project_id,
        title=project_id,
        user_goal=f"goal {project_id}",
        short_summary=f"summary {project_id}",
        created_at=updated_at,
        updated_at=updated_at,
        metadata={"veyra_user_id": owner_id},
    )


def test_project_listing_reads_full_records_only_for_the_requested_page(tmp_path, monkeypatch) -> None:
    store = PersistentProjectStore(tmp_path / "projects")
    for index in range(8):
        store.save_project(
            _project(
                f"project_memory_{index}",
                f"2026-08-30T00:{index:02d}:00+00:00",
                owner_id=7 if index % 2 == 0 else 9,
            )
        )

    loaded: list[str] = []
    original_get = store.get_project

    def tracked_get(project_id: str):
        loaded.append(project_id)
        return original_get(project_id)

    monkeypatch.setattr(store, "get_project", tracked_get)
    service = object.__new__(V3ProjectModeService)
    service.project_store = store
    service._lightweight_memory_summary = lambda project, *, owner_user_id=None: ProjectMemorySummary(
        project_id=project.project_id,
        title=project.title,
        goal=project.short_summary,
        updated_at=project.updated_at,
    )
    service._memory_summary = service._lightweight_memory_summary
    service.template_cards = lambda: []
    service._metadata = lambda: {}

    first = service.list_projects(limit=2, owner_user_id=7, view="summary")

    assert [item.project_id for item in first.projects] == ["project_memory_6", "project_memory_4"]
    assert loaded == ["project_memory_6", "project_memory_4"]
    assert first.total == 4
    assert first.has_more is True


def test_persistent_project_listing_cursor_pages_preserve_owner_and_order(tmp_path) -> None:
    store = PersistentProjectStore(tmp_path / "projects")
    for index in range(9):
        store.save_project(
            _project(
                f"project_cursor_{index}",
                f"2026-08-30T00:{index:02d}:00+00:00",
                owner_id=7 if index % 2 == 0 else 9,
            )
        )
    archived = _project("project_cursor_archived", "2026-08-30T01:00:00+00:00", owner_id=7)
    archived.status = "archived"
    store.save_project(archived)
    service = object.__new__(V3ProjectModeService)
    service.project_store = store
    service._lightweight_memory_summary = lambda project, *, owner_user_id=None: ProjectMemorySummary(
        project_id=project.project_id,
        title=project.title,
        goal=project.short_summary,
        updated_at=project.updated_at,
    )
    service._memory_summary = service._lightweight_memory_summary
    service.template_cards = lambda: []
    service._metadata = lambda: {}

    first = service.list_projects(limit=2, owner_user_id=7, view="summary")
    second = service.list_projects(
        limit=2,
        owner_user_id=7,
        cursor=first.next_cursor,
        view="summary",
    )

    assert first.total == 5
    assert first.has_more is True
    assert second.has_more is True
    assert [item.project_id for item in first.projects] == ["project_cursor_8", "project_cursor_6"]
    assert [item.project_id for item in second.projects] == ["project_cursor_4", "project_cursor_2"]


def test_project_store_cache_does_not_retain_released_projects(tmp_path) -> None:
    store = PersistentProjectStore(tmp_path / "projects")
    project = _project("project_cache_large", "2026-09-01T00:00:00+00:00")
    project.metadata["append_only_history"] = "x" * 20_000
    store.save_project(project)

    assert store.get_project(project.project_id) is project
    reference = weakref.ref(project)
    del project
    gc.collect()

    assert reference() is None
    assert len(store._projects) == 0  # noqa: SLF001
    restored = store.get_project("project_cache_large")
    assert restored is not None
    assert restored.metadata["append_only_history"] == "x" * 20_000


def test_persistent_timeline_and_private_history_are_not_retained_in_memory(tmp_path) -> None:
    store = PersistentProjectStore(tmp_path / "projects")
    project = _project("project_history_cache", "2026-09-01T00:00:00+00:00")
    store.save_project(project)
    timeline_item = ProjectTimelineItem(
        timeline_item_id="timeline_history_cache",
        project_id=project.project_id,
        item_type=TimelineItemType.JOB_CREATED,
        title="Created job",
        summary="Persistent history item.",
        created_at="2026-09-01T00:01:00+00:00",
    )

    store.append_timeline(timeline_item)
    assert store._timeline == {}  # noqa: SLF001
    assert store.list_timeline(project.project_id) == [timeline_item]
    assert store._timeline == {}  # noqa: SLF001
    assert (tmp_path / "projects" / project.project_id / "timeline.json").exists()

    namespace = "doc322_continuity_anchor_bindings_v1"
    store.compare_and_append_private_record(
        project.project_id,
        namespace,
        {"version": 1, "identity_digest": "anchor_v1"},
        expected_version=0,
    )
    assert store._private_records == {}  # noqa: SLF001
    assert store.list_private_records(project.project_id, namespace) == [
        {"version": 1, "identity_digest": "anchor_v1"}
    ]
    assert store._private_records == {}  # noqa: SLF001
    with pytest.raises(ValueError, match="continuity_anchor_conflict"):
        store.compare_and_append_private_record(
            project.project_id,
            namespace,
            {"version": 1, "identity_digest": "anchor_v2"},
            expected_version=0,
        )
    assert store._private_records == {}  # noqa: SLF001


def test_persistent_timeline_concurrent_appends_preserve_every_event(tmp_path) -> None:
    store = PersistentProjectStore(tmp_path / "projects")
    project = _project("project_timeline_concurrent", "2026-09-01T00:00:00+00:00")
    store.save_project(project)

    def append(index: int) -> None:
        store.append_timeline(
            ProjectTimelineItem(
                timeline_item_id=f"timeline_concurrent_{index}",
                project_id=project.project_id,
                item_type=TimelineItemType.JOB_CREATED,
                title=f"Created job {index}",
                summary="Concurrent append regression.",
                created_at=f"2026-09-01T00:{index:02d}:00+00:00",
            )
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, range(24)))

    items = store.list_timeline(project.project_id)
    assert len(items) == 24
    assert {item.timeline_item_id for item in items} == {
        f"timeline_concurrent_{index}" for index in range(24)
    }
    assert store._timeline == {}  # noqa: SLF001


def test_project_listing_reuses_small_header_cache_between_pages(tmp_path, monkeypatch) -> None:
    import alchemy_creative_agent_3_0.app.project_mode.store as project_store_module

    store = PersistentProjectStore(tmp_path / "projects")
    for index in range(4):
        store.save_project(_project(f"project_header_{index}", f"2026-08-{index + 1:02d}T00:00:00+00:00"))
    store = PersistentProjectStore(tmp_path / "projects")

    parse_count = 0
    original_parser = project_store_module._read_project_header_json

    def tracked_parser(*args, **kwargs):
        nonlocal parse_count
        parse_count += 1
        return original_parser(*args, **kwargs)

    monkeypatch.setattr(project_store_module, "_read_project_header_json", tracked_parser)
    first = store.list_project_headers()
    parsed_after_first = parse_count
    second = store.list_project_headers()

    assert parsed_after_first == 0
    assert parse_count == parsed_after_first
    assert first == second


def test_project_header_parser_skips_large_nested_evidence(tmp_path) -> None:
    from alchemy_creative_agent_3_0.app.project_mode.store import _read_project_header_json

    large_project = {
        "project_id": "project_header_large",
        "status": "active",
        "created_at": "2026-08-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
        "metadata": {
            "veyra_user_id": 7,
            "evidence": {"payload": ["x" * 10_000, {"text": "escaped } ] \\\" delimiter"}]},
        },
    }
    path = tmp_path / "project.json"
    path.write_text(json.dumps(large_project), encoding="utf-8")

    header = _read_project_header_json(path, "project_header_large")

    assert header == {
        "project_id": "project_header_large",
        "status": "active",
        "created_at": "2026-08-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
        "owner_user_id": 7,
    }


def test_project_header_parser_streams_large_unneeded_string(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    import alchemy_creative_agent_3_0.app.project_mode.store as project_store_module

    path = tmp_path / "project.json"
    path.write_text(
        json.dumps(
            {
                "status": "active",
                "created_at": "2026-08-01T00:00:00+00:00",
                "updated_at": "2026-09-01T00:00:00+00:00",
                "metadata": {"veyra_user_id": 7, "large_evidence": "x" * 300_000},
            }
        ),
        encoding="utf-8",
    )
    read_sizes: list[int] = []
    original_open = Path.open

    class TrackedHandle:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def read(self, size=-1):
            read_sizes.append(size)
            return self.handle.read(size)

    def tracked_open(candidate, *args, **kwargs):
        return TrackedHandle(original_open(candidate, *args, **kwargs))

    monkeypatch.setattr(Path, "open", tracked_open)

    header = project_store_module._read_project_header_json(path, "project_streamed")

    assert header["owner_user_id"] == 7
    assert max(read_sizes) == project_store_module._JsonStreamReader._CHUNK_SIZE
    assert path.stat().st_size > max(read_sizes)


@pytest.mark.parametrize(
    "invalid_json",
    [
        '{"status":"active","metadata":{"veyra_user_id":7,"evidence":[1,]}}',
        '{"status":"active","metadata":{"veyra_user_id":7,"evidence":"bad\\qescape"}}',
        '{"status":"active","metadata":{"veyra_user_id":7,"evidence":NaN}}',
        '{"status":"active","metadata":{"veyra_user_id":7,}}',
        '{"status":"active","metadata":{"veyra_user_id":7},}',
    ],
)
def test_project_header_parser_rejects_invalid_skipped_json(tmp_path, invalid_json) -> None:
    from alchemy_creative_agent_3_0.app.project_mode.store import _read_project_header_json

    path = tmp_path / "project.json"
    path.write_text(invalid_json, encoding="utf-8")

    with pytest.raises((ValueError, json.JSONDecodeError)):
        _read_project_header_json(path, "project_invalid")


def test_project_header_cache_does_not_keep_a_stale_revision(tmp_path, monkeypatch) -> None:
    import alchemy_creative_agent_3_0.app.project_mode.store as project_store_module

    store = PersistentProjectStore(tmp_path / "projects")
    old = _project("project_header_race", "2026-09-01T00:00:00+00:00", owner_id=7)
    store.save_project(old)
    original_parser = project_store_module._read_project_header_json

    def change_owner_during_header_read(path, project_id):
        header = original_parser(path, project_id)
        current = _project(project_id, "2026-09-02T00:00:00+00:00", owner_id=9)
        store.save_project(current)
        return header

    monkeypatch.setattr(project_store_module, "_read_project_header_json", change_owner_during_header_read)

    store._project_header_cache.clear()  # noqa: SLF001
    store._project_header_path(old.project_id).unlink()  # noqa: SLF001

    assert store.list_project_headers() == []
    assert "project_header_race" not in store._project_header_cache  # noqa: SLF001


def test_project_header_sidecar_uses_small_schema_and_survives_store_reopen(tmp_path, monkeypatch) -> None:
    import alchemy_creative_agent_3_0.app.project_mode.store as project_store_module

    root = tmp_path / "projects"
    store = PersistentProjectStore(root)
    project = _project("project_header_sidecar", "2026-09-03T00:00:00+00:00", owner_id=17)
    project.metadata["append_only_history"] = "x" * 50_000
    store.save_project(project)
    sidecar_path = root / project.project_id / "project_header.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    assert set(sidecar) == {"schema_version", "source_revision", "header"}
    assert set(sidecar["header"]) == {
        "project_id", "status", "created_at", "updated_at", "owner_user_id",
    }
    assert "append_only_history" not in json.dumps(sidecar)

    reopened = PersistentProjectStore(root)
    monkeypatch.setattr(
        project_store_module,
        "_read_project_header_json",
        lambda *_args, **_kwargs: pytest.fail("valid sidecar should avoid the streaming parser"),
    )
    assert reopened.list_project_headers()[0]["owner_user_id"] == 17

    assert store.delete_project(project.project_id)
    assert not sidecar_path.exists()


def test_project_header_sidecar_skips_publication_after_external_replacement(tmp_path, monkeypatch) -> None:
    root = tmp_path / "projects"
    store = PersistentProjectStore(root)
    project = _project("project_header_external", "2026-09-03T00:00:00+00:00", owner_id=7)
    original_write = store._write_project_bytes  # noqa: SLF001

    def write_then_external_replace(project_id, serialized):
        original_write(project_id, serialized)
        project_path = store._project_path(project_id)  # noqa: SLF001
        external = json.loads(project_path.read_text(encoding="utf-8"))
        external["updated_at"] = "2026-09-04T00:00:00+00:00"
        external["metadata"]["veyra_user_id"] = 9
        replacement = project_path.with_suffix(".external.tmp")
        replacement.write_text(json.dumps(external), encoding="utf-8")
        replacement.replace(project_path)

    monkeypatch.setattr(store, "_write_project_bytes", write_then_external_replace)
    store.save_project(project)

    assert not store._project_header_path(project.project_id).exists()  # noqa: SLF001
    restored = store.get_project(project.project_id)
    assert restored is not None
    assert restored.metadata["veyra_user_id"] == 9
    assert store.list_project_headers()[0]["owner_user_id"] == 9


def test_project_header_pair_writes_are_serialized_across_stores(tmp_path, monkeypatch) -> None:
    from threading import Event

    root = tmp_path / "projects"
    first_store = PersistentProjectStore(root)
    second_store = PersistentProjectStore(root)
    first_project = _project("project_header_interleave", "2026-09-05T00:00:00+00:00", owner_id=7)
    second_project = _project("project_header_interleave", "2026-09-06T00:00:00+00:00", owner_id=9)
    second_project.status = "archived"
    first_write_entered = Event()
    allow_first_to_finish = Event()
    second_write_entered = Event()
    first_write = first_store._write_project_bytes  # noqa: SLF001
    second_write = second_store._write_project_bytes  # noqa: SLF001

    def pause_first(project_id, serialized):
        first_write(project_id, serialized)
        first_write_entered.set()
        assert allow_first_to_finish.wait(timeout=5)

    def observe_second(project_id, serialized):
        second_write_entered.set()
        second_write(project_id, serialized)

    monkeypatch.setattr(first_store, "_write_project_bytes", pause_first)
    monkeypatch.setattr(second_store, "_write_project_bytes", observe_second)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(first_store.save_project, first_project)
        assert first_write_entered.wait(timeout=5)
        second_future = executor.submit(second_store.save_project, second_project)
        assert not second_write_entered.wait(timeout=0.05)
        allow_first_to_finish.set()
        first_future.result(timeout=5)
        second_future.result(timeout=5)

    project_path = root / first_project.project_id / "project.json"
    sidecar_path = root / first_project.project_id / "project_header.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    disk_project = json.loads(project_path.read_text(encoding="utf-8"))
    revision = first_store._project_revision(project_path)  # noqa: SLF001
    assert sidecar["source_revision"] == list(revision)
    assert sidecar["header"]["owner_user_id"] == 9
    assert sidecar["header"]["status"] == "archived"
    assert disk_project["metadata"]["veyra_user_id"] == 9
    assert first_store.list_project_headers()[0]["owner_user_id"] == 9


def test_project_header_cache_is_also_bounded(tmp_path, monkeypatch) -> None:
    import alchemy_creative_agent_3_0.app.project_mode.store as project_store_module

    monkeypatch.setattr(project_store_module, "_PROJECT_HEADER_CACHE_MAX_ENTRIES", 3)
    store = PersistentProjectStore(tmp_path / "projects")
    for index in range(7):
        store.save_project(_project(f"project_header_bound_{index}", f"2026-08-{index + 1:02d}T00:00:00+00:00"))

    assert len(store.list_project_headers()) == 7
    assert len(store._project_header_cache) <= 3  # noqa: SLF001


def test_project_page_reads_are_bounded_and_full_catalog_remains_complete(tmp_path, monkeypatch) -> None:
    store = PersistentProjectStore(tmp_path / "projects")
    for index in range(40):
        store.save_project(
            _project(
                f"project_catalog_{index:02d}",
                f"2026-08-{(index // 24) + 1:02d}T{index % 24:02d}:00:00+00:00",
            )
        )

    loaded: list[str] = []
    original_read = store._read_project  # noqa: SLF001

    def tracked_read(project_id: str):
        loaded.append(project_id)
        return original_read(project_id)

    monkeypatch.setattr(store, "_read_project", tracked_read)
    recent = store.list_projects(limit=5)
    page_read_count = len(loaded)
    complete = store.list_all_projects()

    assert len(recent) == 5
    assert [project.project_id for project in recent] == [
        "project_catalog_39",
        "project_catalog_38",
        "project_catalog_37",
        "project_catalog_36",
        "project_catalog_35",
    ]
    assert len(complete) == 40
    assert {project.project_id for project in complete} == {
        f"project_catalog_{index:02d}" for index in range(40)
    }
    assert page_read_count <= 5
    assert len(loaded) > page_read_count
    del recent, complete
    gc.collect()
    assert len(store._projects) == 0  # noqa: SLF001


def test_job_store_cache_does_not_retain_released_history(tmp_path) -> None:
    store = PersistentProductJobStore(tmp_path / "jobs")
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(user_input="history" + ("x" * 20_000)),
        status=ProductJobStatusValue.GENERATING,
        job_id_value="job_memory_large",
    )
    store.save(record)

    assert store.get("job_memory_large") is record
    reference = weakref.ref(record)
    del record
    gc.collect()

    assert reference() is None
    assert len(store._records) == 0  # noqa: SLF001
    assert store.count() == 1
    restored = store.get("job_memory_large")
    assert restored is not None
    assert restored.request.user_input == "history" + ("x" * 20_000)
    assert (tmp_path / "jobs" / "job_memory_large.json").exists()


def test_project_output_snapshot_keeps_only_authorization_and_review_metadata() -> None:
    service = object.__new__(V3ProjectModeService)
    large_retry_history = ["retry evidence"] * 100
    record = type(
        "Record",
        (),
        {
            "request": type(
                "Request",
                (),
                {
                    "metadata": {
                        "project_id": "project_memory_1",
                        "veyra_user_id": 7,
                        "post_generation_review_closure": {"state": "review_withheld_finalization_failed"},
                        "large_retry_history": large_retry_history,
                    }
                },
            )()
        },
    )()

    projection = service._project_output_job_record_projection(record)
    metadata = service._project_output_job_request_metadata(projection)

    assert set(metadata) == set(_PROJECT_OUTPUT_JOB_METADATA_KEYS)
    assert metadata["project_id"] == "project_memory_1"
    assert metadata["veyra_user_id"] == 7
    assert "large_retry_history" not in metadata


@pytest.mark.parametrize(
    ("owner_metadata", "expected_visible"),
    [
        ({}, True),
        ({"project_id": "project_owner_projection", "veyra_user_id": 7}, True),
        ({"project_id": "project_owner_projection", "veyra_user_id": 9}, False),
        ({"project_id": "project_owner_projection", "veyra_user_id": "invalid-owner"}, False),
    ],
    ids=("owner-missing", "owner-matches", "owner-mismatches", "owner-invalid"),
)
def test_project_job_owner_fallback_matches_full_record_and_lightweight_projection(
    owner_metadata: dict[str, object], expected_visible: bool
) -> None:
    service = object.__new__(V3ProjectModeService)
    project = _project("project_owner_projection", "2026-09-01T00:00:00+00:00", owner_id=7)
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(user_input="owner projection", metadata=owner_metadata),
        status=ProductJobStatusValue.GENERATED,
        job_id_value="job_owner_projection",
    )
    projected = service._project_output_job_record_projection(record)
    output_records = [
        SimpleNamespace(
            metadata={"project_id": project.project_id},
        )
    ]

    def visible(job_record: object) -> bool:
        return service._project_job_record_visible_to_owner(project, job_record, 7) or (
            service._project_job_owner_gap_can_use_project_output_scope(
                project, job_record, output_records, 7
            )
        )

    assert visible(record) is expected_visible
    assert visible(projected) is expected_visible


def test_project_output_snapshot_compacts_job_status_and_record() -> None:
    service = object.__new__(V3ProjectModeService)
    project = _project("project_snapshot", "2026-09-01T00:00:00+00:00")
    project.job_ids = ["job_snapshot"]
    output_record = SimpleNamespace(job_id="job_snapshot", output_id="output_1")
    source_status = SimpleNamespace(
        job_id="job_snapshot",
        status=ProductJobStatusValue.GENERATED,
        metadata={
            "final_delivery": {"delivery_gate_applies": True},
            "post_generation_review": {
                "recommended_output_ids": ["output_1"],
                "review_items": [{"output_id": "output_1", "status": "pass", "raw_evidence": "x" * 10_000}],
            },
            "specialized_execution_summary": {"status": "completed", "role_keys": ["hero"], "large_role_recipe": "x" * 10_000},
            "large_history": ["x" * 10_000],
        },
        candidates=["large candidate history"],
    )
    source_job_record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="snapshot",
            metadata={
                "project_id": project.project_id,
                "veyra_user_id": 7,
                "post_generation_review_closure": {"state": "closed"},
                "large_history": ["x" * 10_000],
            },
        ),
        status=ProductJobStatusValue.GENERATED,
        job_id_value="job_snapshot",
    )

    class OutputStore:
        def list_by_job(self, job_id):
            return [output_record]

    service.product_service = SimpleNamespace(
        output_store=OutputStore(),
        get_job=lambda job_id: source_status,
        get_job_record=lambda job_id: source_job_record,
    )

    snapshot = service._project_output_read_snapshot([project])

    compact_status = snapshot["job_status_by_id"]["job_snapshot"]
    assert compact_status is not source_status
    assert compact_status.job_id == "job_snapshot"
    assert compact_status.status == ProductJobStatusValue.GENERATED
    assert compact_status.metadata["final_delivery"] == {"delivery_gate_applies": True}
    assert "large_history" not in compact_status.metadata
    assert compact_status.metadata["post_generation_review"]["review_items"] == [
        {"output_id": "output_1", "status": "pass"}
    ]
    assert "large_role_recipe" not in compact_status.metadata["specialized_execution_summary"]
    compact_record = snapshot["job_record_by_id"]["job_snapshot"]
    assert set(compact_record["_v3_project_output_request_metadata"]) == set(_PROJECT_OUTPUT_JOB_METADATA_KEYS)


def test_project_output_snapshot_uses_batched_outputs_and_one_job_snapshot_read() -> None:
    service = object.__new__(V3ProjectModeService)
    project = _project("project_snapshot_batch", "2026-09-01T00:00:00+00:00")
    project.job_ids = ["job_snapshot_batch"]
    record = SimpleNamespace(job_id="job_snapshot_batch", output_id="output_batch")
    status = SimpleNamespace(
        job_id="job_snapshot_batch",
        status=ProductJobStatusValue.GENERATED,
        metadata={},
        asset_series=[],
        candidates=[],
    )

    class OutputStore:
        def __init__(self):
            self.calls = 0

        def list_by_project_and_jobs(self, project_id, job_ids, *, limit=None):
            self.calls += 1
            assert project_id == project.project_id
            assert job_ids == ["job_snapshot_batch"]
            return [record]

        def list_by_job(self, _job_id, **_kwargs):
            raise AssertionError("batched output snapshot must not reread a Job catalog")

        def list_by_project(self, _project_id, **_kwargs):
            raise AssertionError("batched output snapshot must not rescan the project catalog")

    class ProductService:
        def __init__(self):
            self.output_store = OutputStore()
            self.job_reads = 0

        def get_job_read_snapshot(self, job_id, *, output_records=None):
            self.job_reads += 1
            assert job_id == "job_snapshot_batch"
            assert output_records == [record]
            return status, SimpleNamespace(request=SimpleNamespace(metadata={}))

        def get_job(self, _job_id):
            raise AssertionError("status should come from the same durable Job read")

        def get_job_record(self, _job_id):
            raise AssertionError("record should come from the same durable Job read")

    service.product_service = ProductService()
    snapshot = service._project_output_read_snapshot([project])

    assert service.product_service.output_store.calls == 1
    assert service.product_service.job_reads == 1
    assert snapshot["records_by_job"]["job_snapshot_batch"] == [record]
    assert snapshot["job_status_by_id"]["job_snapshot_batch"].status == ProductJobStatusValue.GENERATED


def test_project_output_status_projection_preserves_missing_role_diagnostics() -> None:
    status = SimpleNamespace(
        job_id="job_missing_role_projection",
        status=ProductJobStatusValue.GENERATED,
        metadata={
            "specialized_execution_summary": {
                "status": "incomplete",
                "final_delivery_withheld": True,
                "role_keys": ["hero", "environmental_context"],
                "missing_role_keys": ["environmental_context"],
                "large_debug_payload": "x" * 10000,
            }
        },
        asset_series=[],
        candidates=[],
    )

    projection = V3ProjectModeService._project_output_job_status_projection(status)

    execution = projection.metadata["specialized_execution_summary"]
    assert execution["missing_role_keys"] == ["environmental_context"]
    assert "large_debug_payload" not in execution
import gc
import weakref
