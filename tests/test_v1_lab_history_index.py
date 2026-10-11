from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path, PureWindowsPath

import pytest

from app.repositories import history_index as index
from app.repositories.memory import MemoryRepository
from app.repositories.sqlite_json import connect
from app.schemas import GenerationJob, GenerationOutput, Session
from app.storage.local import LocalMediaStore


def job(number=0, *, session="s", output_id=None, owner=None, outputs=None):
    job_id = f"job_{number:012d}"
    return GenerationJob(
        id=job_id, session_id=session, job_type="image", status="ready", trace_id="synthetic",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        outputs=outputs if outputs is not None else [GenerationOutput(
            id=output_id or f"out_{number:012d}", job_id=job_id, url="/synthetic",
            metadata={"veyra_user_id": owner} if owner else {},
        )],
    )


@pytest.fixture
def stores(tmp_path):
    store = LocalMediaStore(tmp_path)
    repo = MemoryRepository(database_path=tmp_path / "repository.sqlite3")
    return store, repo


def put_jobs(repo, jobs):
    connection = connect(repo.database_path)
    try:
        with connection:
            for value in jobs:
                repo.jobs.put_on(connection, value.id, value)
    finally:
        connection.close()


def page(store, **kwargs):
    return index.read_history_page(store, surface=kwargs.pop("surface", "v1"), **kwargs)


def manifest(store, *, output_id="out_manifest000001", owner=None, lab=False, mock=False, date="2026-01-01T00:00:00Z"):
    record = {"id": output_id, "job_id": "job_manifest000001", "format": "png",
              "created_at": date, "veyra_user_id": owner, "provider": "mock_image" if mock else "live",
              "model": "live", "prompt": "synthetic", "session_id": "manifest-session"}
    if lab:
        record.update(source_app=index.LAB_PROJECT, alchemy_lab={"veyra_user_id": owner, "idea": "synthetic"})
    path = store.output_path(job_id=record["job_id"], output_id=output_id, output_format="png")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic")
    store.save_history_record(record)
    return record, path


def assert_counts(store):
    connection = connect(store.root / "repository.sqlite3")
    try:
        expected = {}
        for row in connection.execute("SELECT * FROM v1_read_winners"):
            for key in index._bucket_keys(row):
                expected[key] = expected.get(key, 0) + 1
        actual = {tuple(row[:4]): row[4] for row in connection.execute("SELECT * FROM v1_read_counts WHERE total>0")}
        assert actual == expected
    finally:
        connection.close()


def test_warm_job_reads_decode_only_page_and_single_update_is_incremental(stores, monkeypatch):
    store, repo = stores
    put_jobs(repo, (job(i, owner=41) for i in range(1000)))
    index.prepare_history_index(store)
    def forbidden(*args, **kwargs):
        raise AssertionError("Warm reads must not enumerate files or Jobs")
    monkeypatch.setattr(Path, "glob", forbidden)
    metrics = index.HistoryReadMetrics()
    records, total = page(store, owner_id=41, limit=1, metrics=metrics)
    assert total == 1000 and len(records) == 1
    assert metrics.authority_decodes == metrics.job_projection_outputs == metrics.filesystem_entries == 0
    assert metrics.page_decodes == 1 and metrics.winner_rows <= 2
    repo.jobs[job(0).id] = job(0, owner=77)
    changed = index.HistoryReadMetrics()
    assert page(store, owner_id=41, limit=1, metrics=changed)[1] == 999
    assert changed.refreshed_outputs == 1 and changed.job_projection_outputs == 1
    assert changed.authority_decodes < 10
    assert_counts(store)


def test_large_single_job_does_not_decode_full_job_on_warm_page(stores):
    store, repo = stores
    outputs = [GenerationOutput(id=f"out_large_{i:06d}", job_id="job_000000000000", url="/x") for i in range(2000)]
    put_jobs(repo, [job(outputs=outputs)])
    index.prepare_history_index(store)
    metrics = index.HistoryReadMetrics()
    assert page(store, all_owners=True, limit=1, metrics=metrics)[1] == 2000
    assert metrics.page_decodes == 1 and metrics.authority_decodes == 0 and metrics.job_projection_outputs == 0


def test_cross_session_global_owner_and_distinct_scope_winners(stores):
    store, repo = stores
    output_id = "out_cross_session"
    put_jobs(repo, [job(1, session="a", output_id=output_id), job(2, session="b", output_id=output_id, owner=41)])
    assert page(store, owner_id=77, session_id="a") == ([], 0)
    rows, total = page(store, owner_id=41, session_id="a")
    assert total == 1 and rows[0]["job_id"] == job(1).id and rows[0]["veyra_user_id"] == 41
    assert page(store, owner_id=41)[0][0]["job_id"] == job(2).id
    # Canonical output changes must refresh every scope, not only its Job.
    repo.outputs[output_id] = GenerationOutput(id=output_id, job_id=job(2).id, url="/x", metadata={"veyra_user_id": 77})
    assert page(store, owner_id=41, session_id="a") == ([], 0)
    assert page(store, owner_id=77, session_id="a")[1] == 1
    assert page(store, owner_id=77, session_id="b")[1] == 1
    assert_counts(store)


def test_job_replacement_refreshes_old_new_ids_and_session_deletion_classification(stores):
    store, repo = stores
    repo.save_session(Session(id="a", project_id="project", created_at="2026-01-01T00:00:00Z"))
    put_jobs(repo, [job(1, session="a", output_id="old")])
    assert page(store, all_owners=True, session_id="a")[1] == 1
    repo.jobs[job(1).id] = job(1, session="b", output_id="new")
    assert page(store, all_owners=True, session_id="a") == ([], 0)
    assert page(store, all_owners=True, session_id="b")[0][0]["id"] == "new"
    repo.save_session(Session(id="b", project_id=index.LAB_PROJECT, created_at="2026-01-01T00:00:00Z"))
    assert page(store, all_owners=True) == ([], 0)
    del repo.sessions["b"]
    assert page(store, all_owners=True)[1] == 1
    repo.jobs.clear()
    assert page(store, all_owners=True) == ([], 0)
    assert_counts(store)


def test_same_job_duplicate_conflict_and_canonical_precedence(stores):
    store, repo = stores
    outputs = [GenerationOutput(id="same", job_id=job(1).id, url=f"/{owner}", metadata={"veyra_user_id": owner}) for owner in (41, 77)]
    put_jobs(repo, [job(1, outputs=outputs)])
    assert page(store, all_owners=True) == ([], 0)
    repo.outputs["same"] = outputs[1]
    assert page(store, owner_id=77)[0][0]["url"] == "/77"
    assert page(store, owner_id=41) == ([], 0)
    del repo.outputs["same"]
    assert page(store, all_owners=True) == ([], 0)
    assert_counts(store)


def test_lab_conflict_fails_closed_and_mock_counts_follow_changes(stores):
    store, repo = stores
    record, _ = manifest(store, owner=41, lab=True)
    assert page(store, surface="lab", owner_id=41)[1] == 1
    assert page(store, all_owners=True) == ([], 0)
    store.save_history_record({**record, "provider": "mock_image"})
    assert page(store, surface="lab", owner_id=41) == ([], 0)
    assert page(store, surface="lab", owner_id=41, include_mock=True)[1] == 1
    store.save_history_record({**record, "veyra_user_id": 77})
    assert page(store, surface="lab", all_owners=True, include_mock=True) == ([], 0)
    repo.outputs[record["id"]] = GenerationOutput(id=record["id"], job_id=record["job_id"], url="/x", metadata={"veyra_user_id": 41})
    assert page(store, surface="lab", owner_id=41, include_mock=True)[1] == 1
    assert page(store, surface="lab", owner_id=77, include_mock=True) == ([], 0)
    assert_counts(store)


def test_missing_file_repairs_manifest_but_not_job_candidate(stores, monkeypatch):
    store, repo = stores
    record, path = manifest(store, owner=41)
    assert page(store, owner_id=41)[1] == 1
    path.unlink()
    monkeypatch.setattr(Path, "glob", lambda *a, **k: (_ for _ in ()).throw(AssertionError("No scan")))
    assert page(store, owner_id=41) == ([], 0)
    put_jobs(repo, [job(1, output_id=record["id"], owner=41)])
    assert page(store, owner_id=41)[1] == 1
    assert_counts(store)


def test_unmanaged_new_files_require_explicit_reconciliation_and_claim_blocks_recovery(stores):
    store, repo = stores
    assert page(store, all_owners=True) == ([], 0)
    path = store.output_path(job_id=job(1).id, output_id="out_000000000001", output_format="png")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic")
    assert page(store, all_owners=True) == ([], 0)
    index.reconcile_history_files(store)
    assert page(store, all_owners=True)[1] == 1
    repo.output_delete_claims[path.stem] = {"owner_id": 41}
    assert page(store, all_owners=True) == ([], 0)
    del repo.output_delete_claims[path.stem]
    assert page(store, all_owners=True)[1] == 1


def test_missing_directory_has_capped_repair_without_scan(stores, monkeypatch):
    store, _ = stores
    paths = [manifest(store, output_id=f"out_repair_{i:06d}", owner=41)[1] for i in range(10)]
    index.prepare_history_index(store)
    for path in paths:
        path.unlink()
    monkeypatch.setattr(Path, "glob", lambda *a, **k: (_ for _ in ()).throw(AssertionError("No scan")))
    metrics = index.HistoryReadMetrics()
    with pytest.raises(index.HistoryIndexUnavailable):
        page(store, owner_id=41, limit=1, metrics=metrics)
    assert metrics.file_stats <= 10


def test_empty_ready_index_does_not_suppress_later_legacy_import(stores):
    store, _ = stores
    assert page(store, all_owners=True) == ([], 0)
    record = {"id": "out_later000001", "job_id": "job_later000001", "format": "png"}
    path = store.output_path(job_id=record["job_id"], output_id=record["id"], output_format="png")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    store.history_file.parent.mkdir(parents=True)
    store.history_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
    assert page(store, all_owners=True)[1] == 1


def test_atomic_dirty_trigger_with_upserts_and_rollback(stores):
    store, repo = stores
    put_jobs(repo, [job(1)])
    assert page(store, all_owners=True)[1] == 1
    connection = connect(repo.database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for _ in range(3):
            repo.jobs.put_on(connection, job(1).id, job(1, outputs=[]))
        assert connection.execute("SELECT COUNT(*) FROM v1_read_dirty WHERE kind='jobs'").fetchone()[0] == 1
        connection.rollback()
        assert connection.execute("SELECT COUNT(*) FROM v1_read_dirty").fetchone()[0] == 0
    finally:
        connection.close()
    assert page(store, all_owners=True)[1] == 1


def test_interrupted_build_rolls_back_and_explicit_rebuild_does_not_replay_jsonl(stores, monkeypatch):
    store, repo = stores
    put_jobs(repo, [job(1)])
    original = index._resolve
    monkeypatch.setattr(index, "_resolve", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("interrupted")))
    with pytest.raises(RuntimeError):
        index.prepare_history_index(store)
    connection = connect(repo.database_path)
    assert connection.execute("SELECT COUNT(*) FROM v1_read_winners").fetchone()[0] == 0
    assert connection.execute("SELECT value FROM v1_read_state WHERE state_key='version'").fetchone() is None
    connection.close()
    monkeypatch.setattr(index, "_resolve", original)
    record, _ = manifest(store)
    index.prepare_history_index(store)
    # Keep stale source bytes but delete the current SQLite authority.
    connection = connect(repo.database_path)
    with connection:
        connection.execute("DELETE FROM v1_history_records WHERE output_id=?", (record["id"],))
    connection.close()
    index.prepare_history_index(store, rebuild=True)
    connection = connect(repo.database_path)
    assert connection.execute("SELECT 1 FROM v1_history_records WHERE output_id=?", (record["id"],)).fetchone() is None
    connection.close()
    assert_counts(store)


def test_more_than_ten_thousand_job_rows_tail_page_and_counts(stores):
    store, repo = stores
    put_jobs(repo, (job(i) for i in range(10001)))
    index.prepare_history_index(store)
    metrics = index.HistoryReadMetrics()
    rows, total = page(store, all_owners=True, limit=1, offset=10000, metrics=metrics)
    assert total == 10001 and rows[0]["id"] == "out_000000000000"
    assert metrics.page_decodes == 1 and metrics.authority_decodes == 0
    assert metrics.winner_rows == 10001  # Explicit offset cost, not JSON work.


def test_index_plans_cover_output_refresh_and_global_order(stores):
    store, repo = stores
    index.prepare_history_index(store)
    connection = connect(repo.database_path)
    try:
        cases = [
            ("SELECT * FROM v1_read_winners WHERE output_id=?", ("x",), "v1_read_winners_output_idx"),
            ("SELECT MAX(sequence) FROM v1_read_sources WHERE kind='file'", (), "v1_read_sources_sequence_idx"),
            ("SELECT source_key FROM v1_read_sources WHERE kind='history' AND file_path=?", ("/synthetic/missing",), "v1_read_sources_kind_path_idx"),
            ("SELECT kind,source_key FROM v1_read_dirty WHERE kind!='resolve' ORDER BY kind,source_key LIMIT 128", (), "v1_read_dirty_sources_idx"),
            ("SELECT * FROM v1_read_winners WHERE surface='v1' AND scope='global' ORDER BY sort_epoch DESC,job_id DESC,output_id DESC LIMIT 1", (), "v1_read_v1_page_idx"),
        ]
        for sql, parameters, expected in cases:
            plan = " ".join(row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql, parameters))
            assert expected in plan and "TEMP B-TREE" not in plan
    finally:
        connection.close()


def test_cold_manifest_path_lookup_vm_work_is_population_independent(stores):
    store, repo = stores
    index.prepare_history_index(store)
    connection = connect(repo.database_path)
    sql = "SELECT source_key FROM v1_read_sources WHERE kind='history' AND file_path=?"
    costs = []
    try:
        # Do not ANALYZE: fresh cold builds must choose both equality keys.
        for size in (100, 1000):
            connection.execute("DELETE FROM v1_read_sources")
            connection.executemany(
                "INSERT INTO v1_read_sources(kind,source_key,output_id,file_path,sequence) "
                "VALUES('history',?,?,?,?)",
                ((str(i), str(i), f"/synthetic/{i}", i) for i in range(size)),
            )
            steps = [0]

            def count_step():
                steps[0] += 1
                return 0

            connection.set_progress_handler(count_step, 1)
            try:
                assert len(connection.execute(sql, ("/synthetic/0",)).fetchall()) == 1
                assert connection.execute(sql, ("/synthetic/missing",)).fetchall() == []
            finally:
                connection.set_progress_handler(None, 0)
            costs.append(steps[0])
        assert max(costs) < 100
        assert costs[1] <= costs[0] + 10
    finally:
        connection.close()


def test_file_only_public_becomes_private_atomically_after_job_publication(stores):
    store, repo = stores
    value = job(1, owner=41)
    path = store.output_path(job_id=value.id, output_id=value.outputs[0].id, output_format="png")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic")
    assert page(store, owner_id=77)[1] == 1
    repo.save_job(value)
    assert page(store, owner_id=77) == ([], 0)
    assert page(store, owner_id=41)[1] == 1
    assert page(store, owner_id=77, session_id=value.session_id) == ([], 0)
    assert page(store, owner_id=41, session_id=value.session_id)[1] == 1
    assert_counts(store)


def test_missing_derived_table_blocks_cached_and_reopened_connections_until_rebuild(stores):
    from app.repositories import sqlite_json
    store, repo = stores
    put_jobs(repo, [job(1)])
    assert page(store, all_owners=True)[1] == 1
    connection = connect(repo.database_path)
    connection.execute("DROP TABLE v1_read_counts")
    connection.close()
    with pytest.raises(index.HistoryIndexUnavailable):
        page(store, all_owners=True)
    # Simulate process reopen: schema bootstrap's blocked marker must persist,
    # and connect must not hand back an implicit DML transaction.
    sqlite_json._INITIALIZED_DATABASES.pop(str(repo.database_path.resolve()), None)
    connection = connect(repo.database_path)
    assert not connection.in_transaction
    assert connection.execute("SELECT value FROM v1_read_state WHERE state_key='blocked'").fetchone()
    connection.close()
    with pytest.raises(index.HistoryIndexUnavailable):
        page(store, all_owners=True)
    index.prepare_history_index(store, rebuild=True)
    assert page(store, all_owners=True)[1] == 1
    assert_counts(store)


def test_missing_marker_or_observed_corrupt_count_requires_explicit_rebuild(stores):
    store, repo = stores
    put_jobs(repo, [job(1)])
    assert page(store, all_owners=True)[1] == 1
    connection = connect(repo.database_path)
    with connection:
        connection.execute("UPDATE v1_read_counts SET total=0")
    connection.close()
    with pytest.raises(index.HistoryIndexUnavailable):
        page(store, all_owners=True)
    index.prepare_history_index(store, rebuild=True)
    connection = connect(repo.database_path)
    with connection:
        connection.execute("DELETE FROM v1_read_state WHERE state_key='version'")
    connection.close()
    with pytest.raises(index.HistoryIndexUnavailable):
        page(store, all_owners=True)
    index.prepare_history_index(store, rebuild=True)
    assert page(store, all_owners=True)[1] == 1


def test_lab_manifest_history_is_complete_beyond_old_ten_thousand_window(stores):
    store, repo = stores
    store._ensure_history_index()
    directory = store.generated_root / "job_000000000001"
    directory.mkdir(parents=True)
    connection = connect(repo.database_path)
    try:
        with connection:
            for number in range(10001):
                output_id = f"out_{number:012d}"
                (directory / f"{output_id}.png").write_bytes(b"x")
                store._upsert_history_index(connection, {
                    "id": output_id, "job_id": directory.name, "format": "png",
                    "created_at": "2026-01-01T00:00:00Z", "veyra_user_id": 41,
                    "source_app": index.LAB_PROJECT, "provider": "live",
                })
    finally:
        connection.close()
    index.prepare_history_index(store)
    metrics = index.HistoryReadMetrics()
    rows, total = page(store, surface="lab", owner_id=41, limit=1, offset=10000, metrics=metrics)
    assert total == 10001 and rows[0]["id"] == "out_000000010000"
    assert metrics.page_decodes == 1 and metrics.authority_decodes == 0
    rows, count = page(store, surface="lab", owner_id=41, output_id="out_000000010000", limit=1)
    assert count == 1 and len(rows) == 1
    assert page(store, all_owners=True) == ([], 0)


def test_cli_pins_explicit_root_and_refuses_implicit_legacy_import(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "prepare_v1_history_index.py"
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    other = tmp_path / "poison-default"
    env = {**os.environ, "MEDIA_STORAGE_ROOT": str(other)}
    result = subprocess.run([sys.executable, str(script), "--storage-root", str(explicit), "--prepare"],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "ready"
    assert not other.exists()

    legacy = tmp_path / "pending"
    (legacy / "history").mkdir(parents=True)
    source = legacy / "history" / "outputs.jsonl"
    source.write_text(json.dumps({"id": "private-do-not-print"}) + "\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), "--storage-root", str(legacy), "--prepare"],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 2 and "legacy_import_pending" in result.stdout
    assert "private-do-not-print" not in result.stdout + result.stderr
    assert not (legacy / "repository.sqlite3").exists()
    assert not other.exists()


def test_keyed_legacy_owner_and_irregular_file_locator_do_not_scan(stores, monkeypatch):
    store, repo = stores
    value = job(1, owner=41, output_id="legacy-output", session="private-session")
    value = value.model_copy(update={"id": "legacy-directory"})
    put_jobs(repo, [value])
    directory = store.generated_root / value.id
    directory.mkdir(parents=True)
    alternative = directory / "legacy-output.jpg"
    alternative.write_bytes(b"synthetic")
    index.prepare_history_index(store)
    monkeypatch.setattr(Path, "glob", lambda *a, **k: (_ for _ in ()).throw(AssertionError("No tree scan")))
    monkeypatch.setattr(repo, "iter_jobs", lambda **k: (_ for _ in ()).throw(AssertionError("No Job scan")))
    assert index.lookup_output_owner(store, "legacy-output") == (41, False)
    found, known = index.lookup_output_file(store, "legacy-output")
    assert known and found == (alternative, "jpeg", value.id)
    assert page(store, owner_id=77) == ([], 0)
    alternative.unlink()
    # Bounded extension fallback also works for files changed after inventory.
    replacement = directory / "legacy-output.webp"
    replacement.write_bytes(b"synthetic")
    assert index.lookup_output_file(store, "legacy-output")[0] == (replacement, "webp", value.id)
    second = job(2, owner=77, output_id="legacy-output", session="other-session")
    repo.jobs[second.id] = second
    assert index.lookup_output_owner(store, "legacy-output") == (None, True)
    assert page(store, all_owners=True) == ([], 0)
    repo.outputs["legacy-output"] = GenerationOutput(id="legacy-output", job_id=value.id, url="/x", metadata={"veyra_user_id": 41})
    assert index.lookup_output_owner(store, "legacy-output") == (41, False)


def test_incremental_refresh_failure_rolls_back_counts_and_keeps_dirty_key(stores, monkeypatch):
    store, repo = stores
    put_jobs(repo, [job(1, owner=41)])
    assert page(store, owner_id=41)[1] == 1
    repo.jobs[job(1).id] = job(1, owner=77)
    original = index._winner
    monkeypatch.setattr(index, "_winner", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("interrupt refresh")))
    with pytest.raises(RuntimeError):
        index.prepare_history_index(store)
    connection = connect(repo.database_path)
    assert connection.execute("SELECT 1 FROM v1_read_dirty WHERE kind='jobs'").fetchone()
    assert {row[0] for row in connection.execute("SELECT owner_id FROM v1_read_winners")} == {41}
    connection.close()
    assert_counts(store)
    monkeypatch.setattr(index, "_winner", original)
    assert page(store, owner_id=41) == ([], 0)
    assert page(store, owner_id=77)[1] == 1
    assert_counts(store)


def test_history_index_errors_are_sanitized_on_both_api_lanes(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from app import main

    async def blocked(*args, **kwargs):
        raise index.HistoryIndexUnavailable("History index requires an explicit rebuild.")
    monkeypatch.setattr(main.sqlite_calls, "run", blocked)
    monkeypatch.setattr(main.sqlite_calls, "run_read", blocked)
    for function in (main._run_sqlite_api_call, main._run_sqlite_read_api_call):
        with pytest.raises(HTTPException) as error:
            asyncio.run(function(lambda: None))
        assert error.value.status_code == 503
        assert error.value.detail["code"] == "history_index_unavailable"


def test_cli_verify_detects_excess_counts_without_writing_or_importing(stores, tmp_path):
    store, repo = stores
    put_jobs(repo, [job(1)])
    index.prepare_history_index(store)
    script = Path(__file__).resolve().parents[1] / "scripts" / "prepare_v1_history_index.py"
    command = [sys.executable, str(script), "--storage-root", str(store.root), "--verify"]
    good = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert good.returncode == 0 and json.loads(good.stdout)["status"] == "verified"
    connection = connect(repo.database_path)
    with connection:
        connection.execute("UPDATE v1_read_counts SET total=total+10")
    connection.close()
    before = repo.database_path.read_bytes()
    bad = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert bad.returncode == 2 and not json.loads(bad.stdout)["count_buckets_match"]
    assert repo.database_path.read_bytes() == before
    missing = tmp_path / "missing-database"
    missing.mkdir()
    result = subprocess.run([sys.executable, str(script), "--storage-root", str(missing), "--verify"],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 2 and not (missing / "repository.sqlite3").exists()


def test_count_bucket_churn_does_not_retain_inactive_owner_session_keys(stores):
    store, repo = stores
    put_jobs(repo, [job(1, owner=1, session="first")])
    assert page(store, all_owners=True)[1] == 1
    for owner in range(2, 30):
        repo.jobs[job(1).id] = job(1, owner=owner, session=f"session-{owner}")
        assert page(store, owner_id=owner)[1] == 1
        connection = connect(repo.database_path)
        assert connection.execute("SELECT COUNT(*) FROM v1_read_counts").fetchone()[0] == 4
        assert connection.execute("SELECT COUNT(*) FROM v1_read_counts WHERE total=0").fetchone()[0] == 0
        connection.close()
    repo.jobs.clear()
    assert page(store, all_owners=True) == ([], 0)
    connection = connect(repo.database_path)
    assert connection.execute("SELECT COUNT(*) FROM v1_read_counts").fetchone()[0] == 0
    connection.close()


def test_copied_index_cannot_read_old_root_until_explicit_rebuild(stores, monkeypatch):
    store, repo = stores
    record, old_path = manifest(store, owner=41)
    index.prepare_history_index(store)
    moved_root = store.root.parent / (store.root.name + "-copy")
    shutil.copytree(store.root, moved_root)
    moved = LocalMediaStore(moved_root)
    original_stat = Path.stat

    def forbid_old_root(path, *args, **kwargs):
        if store.generated_root in path.parents:
            raise AssertionError("Copied index must never inspect old-root files")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", forbid_old_root)
    for call in (lambda: page(moved, owner_id=41),
                 lambda: index.lookup_output_owner(moved, record["id"]),
                 lambda: index.lookup_output_file(moved, record["id"]),
                 lambda: index.prepare_history_index(moved)):
        with pytest.raises(index.HistoryIndexUnavailable, match="storage root"):
            call()
    index.prepare_history_index(moved, rebuild=True)
    assert page(moved, owner_id=41)[1] == 1
    found, known = index.lookup_output_file(moved, record["id"])
    assert known and found[0] == moved_root / old_path.relative_to(store.root)
    assert_counts(moved)


def test_corrupt_foreign_index_path_is_rejected_before_stat(stores, tmp_path, monkeypatch):
    store, repo = stores
    record, _ = manifest(store)
    index.prepare_history_index(store)
    foreign = tmp_path.parent / "must-not-read-private-file.png"
    connection = connect(repo.database_path)
    with connection:
        connection.execute("UPDATE v1_read_sources SET file_path=? WHERE output_id=?", (str(foreign), record["id"]))
    connection.close()
    original_stat = Path.stat

    def forbidden(path, *args, **kwargs):
        if path == foreign:
            raise AssertionError("Foreign indexed path must not be statted")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", forbidden)
    with pytest.raises(index.HistoryIndexUnavailable):
        page(store, all_owners=True)
    with pytest.raises(index.HistoryIndexUnavailable):
        index.lookup_output_file(store, record["id"])


def test_storage_binding_path_comparison_is_case_aware_on_windows():
    # Path uses these Windows equality semantics on that platform; do not
    # compare the persisted/current root using case-sensitive raw strings.
    stored = PureWindowsPath(r"D:\AI\Media Store")
    assert stored == PureWindowsPath(r"d:\ai\media store")
    assert stored != PureWindowsPath(r"D:\AI\Different Store")
