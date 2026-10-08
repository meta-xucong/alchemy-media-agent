"""Pure decode, bounded admission and owner interleaving regression contracts."""
from __future__ import annotations

import asyncio
from concurrent.futures import Future
from contextlib import contextmanager
import gc
import json
from pathlib import Path
import pickle

import pytest

from app.browse_compute import (
    BoundedBrowseCompute, BrowseCapacityExceeded, BrowseComputeUnavailable,
    decode_job_file, file_revision,
)
from app.browse_reads import run_output_browse
from alchemy_creative_agent_3_0.app.browse_protocol import BrowseJobRead, drive_browse_reads
from alchemy_creative_agent_3_0.app.product_api.service import (
    PersistentProductJobStore, ProductJobRecord, V3ProductApiService,
    deserialize_product_job_record,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore, V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord, ProjectStatus


@pytest.fixture(autouse=True)
def _exercise_worker_seam_with_small_fixtures(monkeypatch):
    from app import browse_reads
    monkeypatch.setattr(browse_reads, "MIN_SOURCE_BYTES", 0)


def _fixture(tmp_path):
    jobs = PersistentProductJobStore(tmp_path / "jobs")
    projects = PersistentProjectStore(tmp_path / "projects")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(user_input="A studio image", metadata={"veyra_user_id": 1}),
        status=ProductJobStatusValue.GENERATED, job_id_value="job_browse_fixture",
    )
    jobs.save(record)
    project = ProjectRecord(
        project_id="project_browse_fixture", title="Fixture", user_goal="Studio", short_summary="Studio",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        job_ids=[record.job_id], metadata={"veyra_user_id": 1},
    )
    projects.save_project(project)
    # Global output browsing reads declared Jobs even without materialized outputs.
    service = V3ProjectModeService(
        product_service=V3ProductApiService(job_store=jobs, output_store=outputs),
        project_store=projects,
    )
    del record, project
    gc.collect()
    return service


class _ImmediatePool:
    def __init__(self, mutate=None):
        self.mutate = mutate
        self.reads = 0

    @contextmanager
    def admit(self):
        yield self

    async def read_job(self, path, job_id, revision):
        self.reads += 1
        data = decode_job_file(str(path), job_id, revision)
        await asyncio.sleep(0)
        if self.mutate:
            self.mutate()
            self.mutate = None
        return data


def test_pure_decode_matches_store_and_rejects_stale_or_wrong_identity(tmp_path):
    service = _fixture(tmp_path)
    store = service.product_service.job_store
    path = store._record_path("job_browse_fixture")
    revision = file_revision(path)
    result = decode_job_file(str(path), "job_browse_fixture", revision)
    assert pickle.loads(result) == store._read_record("job_browse_fixture")
    assert decode_job_file(str(path), "job_other", revision) is None
    assert decode_job_file(str(path), "job_browse_fixture", (0, 0, 0)) is None


def test_parser_preserves_schema_override_and_malformed_behavior(tmp_path):
    service = _fixture(tmp_path)
    store = service.product_service.job_store
    payload = json.loads(store._record_path("job_browse_fixture").read_text())
    payload["schema_version"] = "adapter_version"
    assert deserialize_product_job_record(payload) is None
    assert deserialize_product_job_record(payload, schema_version="adapter_version") is not None
    payload["request"]["user_input"] = {"invalid": "type"}
    assert deserialize_product_job_record(payload, schema_version="adapter_version") is None


def test_source_and_result_bounds_preserve_owner_fallback(tmp_path, monkeypatch):
    service = _fixture(tmp_path)
    path = service.product_service.job_store._record_path("job_browse_fixture")
    import app.browse_compute as module
    monkeypatch.setattr(module, "MAX_SOURCE_BYTES", 10)
    assert decode_job_file(str(path), "job_browse_fixture", file_revision(path)) is None
    monkeypatch.setattr(module, "MAX_SOURCE_BYTES", 4 * 1024 * 1024)
    monkeypatch.setattr(module, "MAX_RESULT_BYTES", 10)
    assert decode_job_file(str(path), "job_browse_fixture", file_revision(path)) is None


def test_sync_driver_preserves_lookup_exception_policy():
    class Product:
        def get_job_read_snapshot(self, *args, **kwargs):
            raise ValueError("fixture read error")
    def steps():
        try:
            yield BrowseJobRead("job_fixture", [])
        except ValueError:
            return "original policy"
    assert drive_browse_reads(steps(), Product()) == "original policy"


def test_async_response_parity_and_no_retained_full_job(tmp_path):
    service = _fixture(tmp_path)
    expected = service.list_project_outputs(owner_user_id=1, compact=True)
    pool = _ImmediatePool()
    actual = asyncio.run(run_output_browse(service, pool, owner_user_id=1, compact=True))
    assert actual == expected
    assert pool.reads == 1
    gc.collect()
    assert not service.product_service.job_store._records


@pytest.mark.parametrize("change", ["owner", "archive", "delete", "job", "output"])
def test_changed_scope_restarts_before_projection(tmp_path, change):
    service = _fixture(tmp_path)
    calls = []
    original = service.list_project_outputs
    def fallback(**kwargs):
        calls.append("fresh")
        return original(**kwargs)
    service.list_project_outputs = fallback
    def mutate():
        if change in {"owner", "archive", "delete"}:
            project = service.project_store.get_project("project_browse_fixture")
            if change == "delete":
                service.project_store.delete_project(project.project_id)
            else:
                if change == "owner":
                    project.metadata["veyra_user_id"] = 2
                else:
                    project.status = ProjectStatus.ARCHIVED
                service.project_store.save_project(project)
        elif change == "job":
            job = service.product_service.job_store.get("job_browse_fixture")
            job.request.metadata["veyra_user_id"] = 2
            service.product_service.job_store.save(job)
        else:
            output_store = service.product_service.output_store
            output_store.storage_root.mkdir(parents=True, exist_ok=True)
            output_store._mark_storage_mutation()
    actual = asyncio.run(run_output_browse(service, _ImmediatePool(mutate), owner_user_id=1, compact=True))
    assert calls == ["fresh"]
    assert actual == original(owner_user_id=1, compact=True)


def test_live_identity_appearing_during_await_is_not_replaced(tmp_path):
    service = _fixture(tmp_path)
    retained = []
    def mutate():
        record = service.product_service.job_store.get("job_browse_fixture")
        record.request.metadata["unsaved_marker"] = "must survive"
        retained.append(record)
    asyncio.run(run_output_browse(service, _ImmediatePool(mutate), owner_user_id=1, compact=True))
    assert service.product_service.job_store.get("job_browse_fixture") is retained[0]
    assert retained[0].request.metadata["unsaved_marker"] == "must survive"


def test_cancellation_keeps_physical_capacity_until_future_done(monkeypatch):
    pool = BoundedBrowseCompute(1, max_pending=1)
    future = Future()
    monkeypatch.setattr(pool, "_submit", lambda *args: (object(), future))
    async def request():
        with pool.admit() as lease:
            await lease.read_job("unused", "job_fixture", (0, 0, 1))
    async def scenario():
        task = asyncio.create_task(request())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert pool.admitted == 1
        for _ in range(100):
            with pytest.raises(BrowseCapacityExceeded):
                with pool.admit():
                    pass
        future.set_result(None)
        await asyncio.sleep(0)
        assert pool.admitted == 0
    asyncio.run(scenario())


def test_timeout_keeps_physical_capacity_and_shutdown_stops_admission(monkeypatch):
    pool = BoundedBrowseCompute(1, max_pending=1, timeout=0.001)
    future = Future()
    monkeypatch.setattr(pool, "_submit", lambda *args: (object(), future))
    async def scenario():
        with pytest.raises(BrowseComputeUnavailable):
            with pool.admit() as lease:
                await lease.read_job("unused", "job_fixture", (0, 0, 1))
        assert pool.admitted == 1
        future.set_result(None)
        await asyncio.sleep(0)
        assert pool.admitted == 0
    asyncio.run(scenario())
    pool.shutdown()
    with pytest.raises(BrowseComputeUnavailable):
        with pool.admit():
            pass


def test_infrastructure_failure_does_not_become_empty_success(tmp_path):
    service = _fixture(tmp_path)
    class FailedPool(_ImmediatePool):
        async def read_job(self, *args):
            raise BrowseComputeUnavailable("worker failed")
    with pytest.raises(BrowseComputeUnavailable):
        asyncio.run(run_output_browse(service, FailedPool(), owner_user_id=1))


def test_legacy_timestamp_defaults_remain_on_owner(tmp_path):
    service = _fixture(tmp_path)
    store = service.product_service.job_store
    path = store._record_path("job_browse_fixture")
    payload = json.loads(path.read_text())
    del payload["updated_at"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert decode_job_file(str(path), "job_browse_fixture", file_revision(path)) is None
    assert store._read_record("job_browse_fixture") is not None


def test_worker_submission_errors_map_to_retryable_error(monkeypatch):
    pool = BoundedBrowseCompute(1)
    def fail(*args):
        raise RuntimeError("executor unavailable")
    monkeypatch.setattr(pool, "_submit", fail)
    async def scenario():
        with pytest.raises(BrowseComputeUnavailable):
            with pool.admit() as lease:
                await lease.read_job("unused", "job_fixture", (0, 0, 1))
        assert pool.admitted == 0
    asyncio.run(scenario())


def test_decode_small_record_in_real_spawned_process(tmp_path):
    service = _fixture(tmp_path)
    store = service.product_service.job_store
    path = store._record_path("job_browse_fixture")
    expected = store._read_record("job_browse_fixture")
    pool = BoundedBrowseCompute(1)
    async def scenario():
        with pool.admit() as lease:
            data = await lease.read_job(path, "job_browse_fixture", file_revision(path))
            assert pickle.loads(data) == expected
    try:
        asyncio.run(scenario())
    finally:
        pool.shutdown()


def test_active_record_keeps_watchdog_on_synchronous_owner(tmp_path):
    service = _fixture(tmp_path)
    store = service.product_service.job_store
    record = store.get("job_browse_fixture")
    record.status = ProductJobStatusValue.GENERATING
    store.save(record)
    del record
    gc.collect()
    events = []
    original = service.list_project_outputs
    def fallback(**kwargs):
        events.append("fallback")
        return original(**kwargs)
    service.list_project_outputs = fallback
    original_read = service.product_service.get_job_read_snapshot
    def read(*args, **kwargs):
        assert events == ["fallback"]
        return original_read(*args, **kwargs)
    service.product_service.get_job_read_snapshot = read
    asyncio.run(run_output_browse(service, _ImmediatePool(), owner_user_id=1))
    assert events == ["fallback"]


def test_corrupt_and_oversized_record_do_not_truncate_output_response(tmp_path, monkeypatch):
    service = _fixture(tmp_path)
    import app.browse_reads as reads
    monkeypatch.setattr(reads, "MAX_SOURCE_BYTES", 10)
    expected = service.list_project_outputs(owner_user_id=1)
    pool = _ImmediatePool()
    assert asyncio.run(run_output_browse(service, pool, owner_user_id=1)) == expected
    assert pool.reads == 0
    path = service.product_service.job_store._record_path("job_browse_fixture")
    path.write_text("{ invalid json", encoding="utf-8")
    assert asyncio.run(run_output_browse(service, pool, owner_user_id=1)) == service.list_project_outputs(owner_user_id=1)


def test_preview_routes_do_not_consume_compute_admission(monkeypatch):
    from app import main
    from starlette.requests import Request
    monkeypatch.setattr(main, "_require_veyra_user_if_enabled", lambda *args: 1)
    async def not_admin(*args):
        return False
    monkeypatch.setattr(main, "_v3_is_admin_request", not_admin)
    monkeypatch.setattr(main, "_v3_browse_compute", object())
    async def unexpected(*args, **kwargs):
        raise AssertionError("preview must not use compute admission")
    monkeypatch.setattr(main, "run_output_browse", unexpected)
    monkeypatch.setattr(main.v3_route_handlers, "get_project_outputs", lambda *args: {"preview": True})
    for surface in ("home_preview", "delivery_preview"):
        result = asyncio.run(main.v3_project_outputs_endpoint(
            Request({"type": "http"}), surface=surface, authorization="",
        ))
        assert result == {"preview": True}


def test_capacity_maps_to_retryable_503(monkeypatch):
    from app import main
    from fastapi import HTTPException
    from starlette.requests import Request
    monkeypatch.setattr(main, "_require_veyra_user_if_enabled", lambda *args: 1)
    async def not_admin(*args):
        return False
    monkeypatch.setattr(main, "_v3_is_admin_request", not_admin)
    monkeypatch.setattr(main, "_v3_browse_compute", object())
    async def busy(*args, **kwargs):
        raise BrowseCapacityExceeded("busy")
    monkeypatch.setattr(main, "run_output_browse", busy)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(main.v3_project_outputs_endpoint(Request({"type": "http"}), authorization=""))
    assert caught.value.status_code == 503
    assert caught.value.headers == {"Retry-After": "1"}


def test_invalid_utf8_keeps_original_domain_lookup_policy(tmp_path):
    service = _fixture(tmp_path)
    path = service.product_service.job_store._record_path("job_browse_fixture")
    path.write_bytes(bytes([255]))
    expected = service.list_project_outputs(owner_user_id=1)
    actual = asyncio.run(run_output_browse(service, _ImmediatePool(), owner_user_id=1))
    assert actual == expected


def test_invalid_job_id_never_stats_outside_job_store(tmp_path, monkeypatch):
    service = _fixture(tmp_path)
    project = service.project_store.get_project("project_browse_fixture")
    project.job_ids = ["../../outside"]
    service.project_store.save_project(project)
    del project
    import app.browse_reads as reads
    original_revision = reads.file_revision
    def guarded_revision(path):
        assert ".." not in Path(path).parts
        return original_revision(path)
    monkeypatch.setattr(reads, "file_revision", guarded_revision)
    pool = _ImmediatePool()
    expected = service.list_project_outputs(owner_user_id=1)
    assert asyncio.run(run_output_browse(service, pool, owner_user_id=1)) == expected
    assert pool.reads == 0


def test_small_jobs_use_owner_without_compute_admission(tmp_path, monkeypatch):
    service = _fixture(tmp_path)
    import app.browse_reads as reads
    monkeypatch.setattr(reads, "MIN_SOURCE_BYTES", 1024 * 1024)
    class FullPool:
        def admit(self):
            raise BrowseCapacityExceeded("must not be called for small reads")
    expected = service.list_project_outputs(owner_user_id=1)
    assert asyncio.run(run_output_browse(service, FullPool(), owner_user_id=1)) == expected
