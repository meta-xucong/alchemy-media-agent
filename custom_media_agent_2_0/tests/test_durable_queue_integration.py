from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.config import settings
from app.repositories import repository
from app.repositories.memory import InMemoryV2Repository, utc_now
from app.repositories.sqlite_calls import BoundedSQLiteCalls
from app.schemas import CreateCreativeRunRequest, CreativeRun, ImageJob, ImageOutput, ImagePromptPlan
from app.services import task_queue


def _run(run_id: str) -> CreativeRun:
    now = utc_now()
    return CreativeRun(
        run_id=run_id, status="generating", mode="smart_enhance",
        intent_summary="offline durable queue integration", trace_id=f"trace_{run_id}",
        created_at=now, updated_at=now,
    )


@pytest.mark.parametrize("owner", ["superseded", "completed"])
@pytest.mark.parametrize("action", ["complete", "retry", "fail", "release", "snapshot", "heartbeat", "persist"])
def test_terminal_task_and_durable_run_reject_late_mutations(tmp_path, monkeypatch, owner, action):
    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    run = _run("terminal-run")
    repository.save_creative_run(run)
    task_queue.enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline"}, queued_run=run)
    old_claim = task_queue.claim_next_task("old-worker")
    assert old_claim is not None
    with task_queue._connect() as connection:
        connection.execute(
            "UPDATE v2_tasks SET locked_at=? WHERE task_id=?",
            ((utc_now() - timedelta(days=1)).isoformat(), old_claim.task_id),
        )
    current = task_queue.claim_next_task("new-worker")
    assert current is not None and current.claim_token != old_claim.claim_token
    completed = run.model_copy(update={"status": "completed"})
    with task_queue.claimed_task(current):
        task_queue.persist_claimed_operation(lambda: repository.save_creative_run(completed))
    assert task_queue.complete_task(current, completed)
    with task_queue._connect() as connection:
        before = dict(connection.execute("SELECT * FROM v2_tasks WHERE task_id=?", (current.task_id,)).fetchone())
    claim = old_claim if owner == "superseded" else current
    if action == "complete":
        changed = task_queue.complete_task(claim, run)
    elif action == "retry":
        changed = task_queue.retry_task(claim, "late retry", run, retry_delay_seconds=0)
    elif action == "fail":
        changed = task_queue.fail_task(claim, "late failure", run)
    elif action == "release":
        changed = task_queue.release_task(claim)
    elif action == "snapshot":
        changed = task_queue.update_task_snapshot(run, claim=claim)
    elif action == "heartbeat":
        changed = task_queue.refresh_task_claim(claim)
    else:
        with task_queue.claimed_task(claim), pytest.raises(task_queue.StaleTaskClaim):
            task_queue.persist_claimed_operation(lambda: repository.save_creative_run(run))
        changed = False
    assert changed is False
    with task_queue._connect() as connection:
        after = dict(connection.execute("SELECT * FROM v2_tasks WHERE task_id=?", (current.task_id,)).fetchone())
    assert after == before
    assert task_queue.get_run_snapshot(run.run_id) == completed
    reopened = InMemoryV2Repository(database_path=repository.database_path)
    assert reopened.get_creative_run(run.run_id) == completed
    assert task_queue.claim_next_task("restart-worker") is None


def test_durable_running_job_cleanup_serializes_against_completed_replacement(tmp_path, monkeypatch):
    repo = InMemoryV2Repository(database_path=tmp_path / "repository.sqlite3")
    now = utc_now()
    job = ImageJob(
        job_id="job-race", run_id="run-race", status="running", provider_id="mock_image", model="mock",
        prompt_plan=ImagePromptPlan(plan_id="plan", mode="smart_enhance", prompt="offline"),
        outputs=[], created_at=now, updated_at=now,
    )
    output = ImageOutput(output_id="output-race", job_id=job.job_id, url="/offline.png", created_at=now)
    completed = job.model_copy(update={"status": "completed", "outputs": [output]})
    repo.save_image_job(job)
    read_started = threading.Event()
    allow_delete = threading.Event()
    writer_started = threading.Event()
    original_get = repo.image_jobs.get_json_on

    def pause_after_read(connection, key):
        value = original_get(connection, key)
        read_started.set()
        assert allow_delete.wait(3)
        return value

    monkeypatch.setattr(repo.image_jobs, "get_json_on", pause_after_read)

    def save_replacement():
        writer_started.set()
        return repo.save_image_job(completed)

    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(repo.delete_image_job, job.job_id)
        assert read_started.wait(2)
        probe = sqlite3.connect(repo.database_path, timeout=0)
        try:
            # No competing writer exists yet: the cleanup's read-condition must
            # itself own the write lock, not race a later DELETE against a save.
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                probe.execute("BEGIN IMMEDIATE")
        except BaseException:
            allow_delete.set()
            raise
        finally:
            probe.close()
        replacement = pool.submit(save_replacement)
        assert writer_started.wait(2)
        try:
            assert not replacement.done()
        finally:
            allow_delete.set()
        assert deletion.result(timeout=3) == job
        assert replacement.result(timeout=3) == completed
    monkeypatch.setattr(repo.image_jobs, "get_json_on", original_get)
    reopened = InMemoryV2Repository(database_path=repo.database_path)
    assert reopened.get_image_job(job.job_id) == completed
    assert reopened.get_output(output.output_id) == output
    assert reopened.delete_image_job(job.job_id) is None
    assert reopened.get_image_job(job.job_id) == completed


def test_cancelled_queue_admission_finishes_without_orphan_or_early_capacity_release(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    calls = BoundedSQLiteCalls(capacity=1, thread_name_prefix="admission-test")
    monkeypatch.setattr(main, "sqlite_calls", calls)
    created = threading.Event()
    continue_enqueue = threading.Event()
    enqueued = threading.Event()
    original_queue = main.creative_manager.build_queued_run
    original_enqueue = main.enqueue_creative_task
    runs = []

    def pause_after_creation(request):
        run = original_queue(request)
        runs.append(run)
        created.set()
        assert continue_enqueue.wait(3)
        return run

    def finish_enqueue(**kwargs):
        result = original_enqueue(**kwargs)
        enqueued.set()
        return result

    monkeypatch.setattr(main.creative_manager, "build_queued_run", pause_after_creation)
    monkeypatch.setattr(main, "enqueue_creative_task", finish_enqueue)

    async def exercise():
        admission = asyncio.create_task(main._enqueue_creative_run(
            CreateCreativeRunRequest(user_prompt="offline"), kind="creative_run"
        ))
        assert await asyncio.to_thread(created.wait, 2)
        admission.cancel()
        with pytest.raises(asyncio.CancelledError):
            await admission
        with pytest.raises(HTTPException) as full:
            await main._run_sqlite_api_call(lambda: "unexpected")
        assert full.value.status_code == 503
        continue_enqueue.set()
        assert await asyncio.to_thread(enqueued.wait, 2)

    try:
        asyncio.run(exercise())
    finally:
        continue_enqueue.set()
        calls._executor.shutdown(wait=True)
    reopened = InMemoryV2Repository(database_path=repository.database_path)
    assert len(runs) == 1
    assert reopened.get_creative_run(runs[0].run_id) is None
    assert task_queue.get_run_snapshot(runs[0].run_id) == runs[0]
    assert task_queue.task_queue_stats()["counts"] == {"queued": 1}


@pytest.mark.parametrize("kind", ["creative_run", "revision_run"])
def test_rejected_admission_needs_no_repository_write_or_cleanup(tmp_path, monkeypatch, kind):
    import app.main as main

    monkeypatch.setattr(task_queue, "settings", replace(
        settings, task_queue_db_path=tmp_path / "queue.sqlite3", task_queue_max_pending=1,
    ))
    request = CreateCreativeRunRequest(user_prompt="offline")
    event_loop_thread = threading.get_ident()
    admission_threads = []
    original_enqueue = main.enqueue_creative_task

    def checked_enqueue(**kwargs):
        admission_threads.append(threading.get_ident())
        return original_enqueue(**kwargs)

    def unavailable_repository(_run):
        raise sqlite3.OperationalError("repository database is locked")

    monkeypatch.setattr(main, "enqueue_creative_task", checked_enqueue)
    monkeypatch.setattr(repository, "save_creative_run", unavailable_repository)

    async def exercise():
        first = await main._enqueue_creative_run(request, kind=kind)
        with pytest.raises(HTTPException) as full:
            await main._enqueue_creative_run(request, kind=kind)
        assert full.value.status_code == 429
        assert full.value.detail["error_code"] == "task_queue_full"
        return first

    first = asyncio.run(exercise())
    reopened = InMemoryV2Repository(database_path=repository.database_path)
    assert list(reopened.creative_runs) == []
    assert len(admission_threads) == 2 and event_loop_thread not in admission_threads
    assert task_queue.get_run_snapshot(first.run_id) == first
    assert task_queue.task_queue_stats()["counts"] == {"queued": 1}


def test_queue_storage_lock_creates_no_durable_repository_orphan(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    attempted = []

    def reject_enqueue(**kwargs):
        attempted.append(kwargs["queued_run"].run_id)
        raise sqlite3.OperationalError("queue database is locked")

    monkeypatch.setattr(main, "enqueue_creative_task", reject_enqueue)

    async def exercise():
        with pytest.raises(HTTPException) as error:
            await main._enqueue_creative_run(CreateCreativeRunRequest(user_prompt="offline"), kind="creative_run")
        assert error.value.status_code == 503
        assert error.value.headers["Retry-After"] == "1"
        assert error.value.detail["error_code"] == "storage_busy"

    asyncio.run(exercise())
    assert len(attempted) == 1
    assert list(repository.creative_runs) == []
    assert task_queue.task_queue_stats()["counts"] == {}


def test_pure_queue_builder_preserves_legacy_queue_run_persistence():
    from app.agents.runtime import CreativeManagerRuntime

    runtime = CreativeManagerRuntime()
    request = CreateCreativeRunRequest(user_prompt="offline")
    snapshot = runtime.build_queued_run(request)
    assert snapshot.status == "planning"
    assert repository.get_creative_run(snapshot.run_id) is None
    legacy = runtime.queue_run(request)
    reopened = InMemoryV2Repository(database_path=repository.database_path)
    assert reopened.get_creative_run(legacy.run_id) == legacy


def test_worker_restores_admission_identity_from_queue_before_stale_repository(tmp_path, monkeypatch):
    from app.agents.runtime import CreativeManagerRuntime

    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    runtime = CreativeManagerRuntime()
    request = CreateCreativeRunRequest(user_prompt="offline")
    queued = runtime.build_queued_run(request)
    task_queue.enqueue_creative_task(kind="creative_run", request_payload=request.model_dump(mode="json"), queued_run=queued)
    repository.save_creative_run(queued.model_copy(update={"trace_id": "obsolete-repository-trace"}))
    claim = task_queue.claim_next_task("restarted-worker")
    assert claim is not None
    observed = {}

    async def complete(_request, **kwargs):
        observed.update(kwargs)
        return queued.model_copy(update={"status": "completed"})

    monkeypatch.setattr(runtime, "_run_deterministic_manager", complete)
    with task_queue.claimed_task(claim):
        completed = asyncio.run(runtime.complete_queued_run(request, queued.run_id))
    assert completed.status == "completed"
    assert observed == {"run_id": queued.run_id, "trace_id": queued.trace_id, "created_at": queued.created_at}


def test_queue_wal_setup_busy_maps_to_retryable_503_without_admission(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))

    def busy_wal_setup(_connection):
        raise task_queue.QueueStorageBusy("WAL setup timed out")

    monkeypatch.setattr(task_queue, "_ensure_wal_mode", busy_wal_setup)

    async def exercise():
        with pytest.raises(HTTPException) as error:
            await main._enqueue_creative_run(CreateCreativeRunRequest(user_prompt="offline"), kind="creative_run")
        assert error.value.status_code == 503
        assert error.value.headers["Retry-After"] == "5"
        assert error.value.detail["error_code"] == "local_database_busy"
        assert error.value.detail["retryable"] is True

    asyncio.run(exercise())
    assert list(repository.creative_runs) == []
    with sqlite3.connect(task_queue.settings.task_queue_db_path) as connection:
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='v2_tasks'").fetchone() is None


def test_legacy_queue_wal_reader_lock_returns_503_without_publishing_run(tmp_path, monkeypatch):
    import app.main as main

    path = tmp_path / "legacy-queue.sqlite3"
    monkeypatch.setattr(task_queue, "settings", replace(
        settings, task_queue_db_path=path, task_queue_busy_timeout_seconds=0.1,
    ))
    reader = sqlite3.connect(path)
    reader.execute("PRAGMA journal_mode=DELETE")
    reader.execute("CREATE TABLE legacy_marker(value TEXT)")
    reader.execute("INSERT INTO legacy_marker VALUES ('keep')")
    reader.commit()
    reader.execute("BEGIN")
    assert reader.execute("SELECT * FROM legacy_marker").fetchone()[0] == "keep"

    async def exercise():
        with pytest.raises(HTTPException) as error:
            await main._enqueue_creative_run(CreateCreativeRunRequest(user_prompt="offline"), kind="creative_run")
        assert error.value.status_code == 503
        assert error.value.detail["error_code"] == "local_database_busy"
        assert error.value.detail["retryable"] is True
        assert isinstance(error.value.__cause__, task_queue.QueueStorageBusy)

    try:
        asyncio.run(exercise())
    finally:
        reader.close()
    assert list(repository.creative_runs) == []
    assert task_queue.task_queue_stats()["counts"] == {}
    with task_queue._connect() as connection:
        assert connection.execute("SELECT value FROM legacy_marker").fetchone()[0] == "keep"
