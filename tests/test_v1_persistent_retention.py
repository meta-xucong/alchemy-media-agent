from app.repositories.memory import MemoryRepository
from app.services.alchemy_lab import AlchemyLabStore, ExplorationRequest, ExplorationSession
from app.schemas import GenerationJob, GenerationOutput, Session
import gc
import threading
import weakref


def test_v1_records_survive_repository_reopen_and_preserve_job_indexes(tmp_path):
    db_path = tmp_path / "v1.sqlite3"
    first = MemoryRepository(database_path=db_path)
    session = Session(id="ses_durable", project_id="project", created_at="2026-10-09T00:00:00Z")
    output = GenerationOutput(id="out_durable", job_id="job_durable", url="/v1/outputs/out_durable")
    job = GenerationJob(
        id="job_durable",
        session_id=session.id,
        job_type="image",
        status="ready",
        trace_id="trace",
        idempotency_key="idem_durable",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:01:00Z",
        outputs=[output],
    )
    first.save_session(session)
    first.save_job(job)
    first.append_event(session.id, "job.ready", {"job_id": job.id})

    reopened = MemoryRepository(database_path=db_path)
    assert reopened.get_session(session.id) == session
    assert reopened.get_job(job.id) == job
    assert reopened.get_output(output.id) == output
    assert reopened.get_job_by_idempotency_key("idem_durable") == job
    assert reopened.list_jobs(session_id=session.id) == [job]
    assert reopened.list_events(session.id) == [{"event": "job.ready", "data": {"job_id": job.id}}]


def test_v1_equal_timestamp_jobs_keep_original_insertion_order(tmp_path):
    repo = MemoryRepository(database_path=tmp_path / "v1.sqlite3")
    created_at = "2026-10-09T00:00:00Z"
    for job_id in ("job_z", "job_a", "job_m"):
        repo.save_job(
            GenerationJob(
                id=job_id,
                job_type="image",
                status="ready",
                trace_id="trace",
                created_at=created_at,
                updated_at=created_at,
            )
        )

    assert [job.id for job in repo.list_jobs()] == ["job_z", "job_a", "job_m"]


def test_v1_output_delete_updates_durable_job_projection(tmp_path):
    repo = MemoryRepository(database_path=tmp_path / "v1.sqlite3")
    output = GenerationOutput(id="out_delete", job_id="job_delete", url="/out")
    job = GenerationJob(
        id="job_delete",
        job_type="image",
        status="ready",
        trace_id="trace",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:00:00Z",
        outputs=[output],
    )
    repo.save_job(job)

    assert repo.delete_output(output.id) == output
    assert repo.get_output(output.id) is None
    assert repo.get_job(job.id).outputs == []
    assert MemoryRepository(database_path=repo.database_path).get_job(job.id).outputs == []


def test_concurrent_v1_output_deletes_do_not_restore_each_others_reference(tmp_path):
    db_path = tmp_path / "v1.sqlite3"
    first = MemoryRepository(database_path=db_path)
    outputs = [
        GenerationOutput(id="out_delete_a", job_id="job_delete_race", url="/a"),
        GenerationOutput(id="out_delete_b", job_id="job_delete_race", url="/b"),
    ]
    first.save_job(GenerationJob(
        id="job_delete_race",
        job_type="image",
        status="ready",
        trace_id="trace",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:00:00Z",
        outputs=outputs,
    ))
    repositories = [MemoryRepository(database_path=db_path) for _ in outputs]
    barrier = threading.Barrier(2)
    errors = []

    def delete(repo, output_id):
        try:
            barrier.wait(timeout=2)
            repo.delete_output(output_id)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=delete, args=(repo, output.id)) for repo, output in zip(repositories, outputs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
        assert not thread.is_alive()

    assert errors == []
    restored = MemoryRepository(database_path=db_path).get_job("job_delete_race")
    assert restored.outputs == []


def test_restart_recovery_marks_active_v1_jobs_failed_once_without_touching_terminal_jobs(tmp_path):
    repo = MemoryRepository(database_path=tmp_path / "v1.sqlite3")
    def job(job_id, status):
        return GenerationJob(
            id=job_id,
            job_type="image",
            status=status,
            trace_id="trace",
            created_at="2026-10-09T00:00:00Z",
            updated_at="2026-10-09T00:00:00Z",
        )

    repo.save_job(job("job_active_a", "generating"))
    repo.save_job(job("job_active_b", "queued"))
    repo.save_job(job("job_complete", "ready"))

    assert repo.recover_interrupted_jobs(batch_size=1) == 2
    assert repo.recover_interrupted_jobs(batch_size=1) == 0
    for job_id in ("job_active_a", "job_active_b"):
        restored = repo.get_job(job_id)
        assert restored.status == "failed"
        assert restored.error.code == "worker_interrupted"
        assert restored.error.retryable is False
        assert restored.error.detail["automatic_provider_replay"] is False
    assert repo.get_job("job_complete").status == "ready"


def test_v1_reset_clears_repository_rows_without_removing_media_files(tmp_path):
    repo = MemoryRepository(database_path=tmp_path / "v1.sqlite3")
    lab = AlchemyLabStore(database_path=repo.database_path)
    repo.save_session(Session(id="ses_reset", project_id="project", created_at="2026-10-09T00:00:00Z"))
    repo.append_event("ses_reset", "test", {})
    lab_session = ExplorationSession(
        id="lab_survives_v1_reset",
        veyra_user_id=77,
        status="completed",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:00:00Z",
        request=ExplorationRequest(idea="keep across V1 reset"),
    )
    lab.save(lab_session)

    repo.reset()

    assert len(repo.sessions) == 0
    assert list(repo.sessions) == []
    assert repo.list_events("ses_reset") == []
    assert lab.get(lab_session.id) == lab_session

    lab.reset()
    assert lab.get(lab_session.id) is None


def test_lab_session_and_favorites_survive_store_reopen(tmp_path):
    db_path = tmp_path / "v1.sqlite3"
    session = ExplorationSession(
        id="lab_durable",
        veyra_user_id=77,
        status="completed",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:01:00Z",
        request=ExplorationRequest(idea="test"),
        favorites=["variant-1"],
        progress={"completed": 1},
    )
    first = AlchemyLabStore(database_path=db_path)
    first.save(session)

    reopened = AlchemyLabStore(database_path=db_path)

    assert reopened.get(session.id) == session
    reopened.reset()
    assert AlchemyLabStore(database_path=db_path).get(session.id) is None


def test_repository_does_not_keep_decoded_history_objects_alive(tmp_path):
    repo = MemoryRepository(database_path=tmp_path / "v1.sqlite3")
    session = Session(id="ses_ephemeral", project_id="project", created_at="2026-10-09T00:00:00Z")
    repo.save_session(session)
    restored = repo.get_session(session.id)
    reference = weakref.ref(restored)

    del restored
    gc.collect()

    assert reference() is None
