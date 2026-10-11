"""Synthetic capacity/preparation boundaries; never uses default data paths."""
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest

from app.services import favorites, image_history as history


@pytest.fixture
def cli(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts" / "prepare_v2_history_reads.py"))
    settings = SimpleNamespace(
        data_dir=tmp_path, image_history_path=tmp_path / "history.jsonl", veyra_auth_enabled=False,
    )
    monkeypatch.setattr(history, "settings", settings)
    monkeypatch.setattr(favorites, "settings", settings)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setenv("V2_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("V2_IMAGE_HISTORY_PATH", str(settings.image_history_path))
    monkeypatch.setattr(namespace["shutil"], "disk_usage", lambda _: SimpleNamespace(free=1024))
    return namespace, ["--data-root", str(tmp_path), "--history-path", str(settings.image_history_path)]


def test_preflight_is_read_only_and_reports_footprint(cli, tmp_path, capsys):
    namespace, args = cli
    (tmp_path / "image_history_index.sqlite3").write_bytes(b"123")
    (tmp_path / "image_history_index.sqlite3-wal").write_bytes(b"4567")
    assert namespace["main"]([*args, "--preflight"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "preflight"
    assert result["disk"]["within_budget"] is None
    assert result["disk"]["locations"][0] == {
        "scope": "history", "free_bytes": 1024, "database_bytes": 3, "wal_bytes": 4, "shm_bytes": 0,
    }
    assert not (tmp_path / "image_favorites.sqlite3").exists()


@pytest.mark.parametrize("budget", [[], ["--minimum-free-bytes", "0"], ["--minimum-free-bytes", "-1"]])
def test_mutating_preparation_requires_positive_explicit_budget(cli, tmp_path, budget):
    namespace, args = cli
    with pytest.raises(SystemExit) as captured:
        namespace["main"]([*args, *budget])
    assert captured.value.code == 2
    assert not (tmp_path / "image_history_index.sqlite3").exists()
    assert not (tmp_path / "image_favorites.sqlite3").exists()


def test_underbudget_fails_before_preparation_or_writes(cli, tmp_path, monkeypatch, capsys):
    namespace, args = cli

    def forbidden_prepare():
        raise AssertionError("insufficient capacity must stop before preparation")

    monkeypatch.setattr(history, "prepare_history_reads", forbidden_prepare)
    assert namespace["main"]([*args, "--minimum-free-bytes", "1025"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error_type"] == "insufficient_free_space"
    assert result["disk"]["within_budget"] is False
    assert not (tmp_path / "image_history_index.sqlite3").exists()
    assert not (tmp_path / "image_favorites.sqlite3").exists()


def test_explicit_preparation_enables_reads(cli, capsys):
    namespace, args = cli
    assert namespace["main"]([*args, "--minimum-free-bytes", "1024"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready"
    assert history.list_image_history(favorite=True).total == 0


def test_failed_preparation_does_not_expose_source_or_path(cli, tmp_path, capsys):
    namespace, args = cli
    (tmp_path / "history.jsonl").write_text('{"private-source":', encoding="utf-8")
    assert namespace["main"]([*args, "--minimum-free-bytes", "1024"]) == 2
    output = capsys.readouterr().out
    assert json.loads(output)["error_type"] == "LegacyHistoryImportError"
    assert "private-source" not in output and str(tmp_path) not in output


def _verifier_namespace():
    path = Path(__file__).resolve().parents[2] / "scripts" / "verify_v2_history_reads.py"
    return runpy.run_path(str(path))


def test_read_only_verifier_refuses_missing_indexes_without_creating_files(cli, tmp_path, capsys):
    _prepare, args = cli
    before = {path.name for path in tmp_path.iterdir()}

    assert _verifier_namespace()["main"](args) == 2

    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "blocked", "error_type": "HistoryReadVerificationError"}
    assert {path.name for path in tmp_path.iterdir()} == before


def test_read_only_verifier_accepts_prepared_indexes_without_modifying_them(cli, tmp_path, capsys, monkeypatch):
    prepare, args = cli
    assert prepare["main"]([*args, "--minimum-free-bytes", "1024"]) == 0
    capsys.readouterr()
    databases = [tmp_path / "image_history_index.sqlite3", tmp_path / "image_favorites.sqlite3"]
    before = {path.name: path.read_bytes() for path in databases}
    monkeypatch.setattr(prepare["shutil"], "disk_usage", lambda _: SimpleNamespace(free=1024 * 1024 * 1024))

    assert _verifier_namespace()["main"](args) == 0

    assert json.loads(capsys.readouterr().out) == {
        "status": "verified", "scope": "v2_history_favorites_readiness",
        "history_source_parity": "verified", "history_records_reconciled": 0,
        "favorites_authority": "sqlite_after_migration",
    }
    assert {path.name: path.read_bytes() for path in databases} == before


def test_read_only_verifier_detects_corrupt_counts_without_repair(cli, tmp_path, capsys):
    import sqlite3

    prepare, args = cli
    assert prepare["main"]([*args, "--minimum-free-bytes", "1024"]) == 0
    capsys.readouterr()
    database = tmp_path / "image_history_index.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE v2_history_counts SET row_count=99 WHERE bucket='all'")
    with sqlite3.connect(database) as connection:
        before = list(connection.execute("SELECT bucket,row_count FROM v2_history_counts ORDER BY bucket"))

    assert _verifier_namespace()["main"](args) == 2

    assert json.loads(capsys.readouterr().out) == {
        "status": "blocked", "error_type": "HistoryCountIndexError",
    }
    with sqlite3.connect(database) as connection:
        after = list(connection.execute("SELECT bucket,row_count FROM v2_history_counts ORDER BY bucket"))
    assert after == before


def test_read_only_verifier_blocks_missing_source_row_even_when_counts_match(cli, tmp_path, capsys, monkeypatch):
    import sqlite3
    from datetime import datetime, timezone
    from app.schemas import ImageHistoryItem
    from app.services.history_counts import rebuild_history_counts

    prepare, args = cli
    item = ImageHistoryItem(
        output_id="out-a", job_id="job-a", provider_id="provider", model="model",
        prompt="fixture", url="/outputs/out-a", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    (tmp_path / "history.jsonl").write_text(item.model_dump_json() + "\n", encoding="utf-8")
    assert prepare["main"]([*args, "--minimum-free-bytes", "1024"]) == 0
    capsys.readouterr()
    database = tmp_path / "image_history_index.sqlite3"
    monkeypatch.setattr(prepare["shutil"], "disk_usage", lambda _: SimpleNamespace(free=1024 * 1024 * 1024))
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM v2_image_history WHERE output_id='out-a'")
        connection.commit()
        connection.execute("PRAGMA recursive_triggers=ON")
        rebuild_history_counts(connection)
    before = database.read_bytes()

    assert _verifier_namespace()["main"](args) == 2

    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "blocked", "error_type": "HistoryReadVerificationError"}
    assert database.read_bytes() == before


def test_read_only_verifier_blocks_index_row_missing_from_source(cli, tmp_path, capsys, monkeypatch):
    import sqlite3
    from datetime import datetime, timezone
    from app.schemas import ImageHistoryItem
    from app.services.image_history import _history_connect, _upsert_history_item

    prepare, args = cli
    assert prepare["main"]([*args, "--minimum-free-bytes", "1024"]) == 0
    capsys.readouterr()
    item = ImageHistoryItem(
        output_id="out-extra", job_id="job-extra", provider_id="provider", model="model",
        prompt="fixture", url="/outputs/out-extra", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    connection = _history_connect()
    try:
        with connection:
            _upsert_history_item(connection, item)
    finally:
        connection.close()
    database = tmp_path / "image_history_index.sqlite3"
    monkeypatch.setattr(prepare["shutil"], "disk_usage", lambda _: SimpleNamespace(free=1024 * 1024 * 1024))
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA recursive_triggers=ON")
        from app.services.history_counts import verify_history_counts
        verify_history_counts(connection)
    before = database.read_bytes()

    assert _verifier_namespace()["main"](args) == 2
    assert json.loads(capsys.readouterr().out) == {
        "status": "blocked", "error_type": "HistoryReadVerificationError",
    }
    assert database.read_bytes() == before


def test_read_only_verifier_reconciles_duplicate_ids_using_latest_source_record(cli, tmp_path, capsys, monkeypatch):
    from datetime import datetime, timezone, timedelta
    from app.schemas import ImageHistoryItem

    prepare, args = cli
    first = ImageHistoryItem(
        output_id="out-duplicate", job_id="job-a", provider_id="provider", model="model",
        prompt="older", url="/outputs/out-duplicate", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    latest = first.model_copy(update={
        "job_id": "job-b", "prompt": "newer", "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=1),
    })
    (tmp_path / "history.jsonl").write_text(
        first.model_dump_json() + "\n" + latest.model_dump_json() + "\n", encoding="utf-8",
    )
    assert prepare["main"]([*args, "--minimum-free-bytes", "1024"]) == 0
    capsys.readouterr()
    monkeypatch.setattr(prepare["shutil"], "disk_usage", lambda _: SimpleNamespace(free=1024 * 1024 * 1024))

    assert _verifier_namespace()["main"](args) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "verified"
    assert result["history_records_reconciled"] == 1


def test_read_only_verifier_rejects_one_oversized_jsonl_record_with_bounded_read(cli, tmp_path, capsys, monkeypatch):
    from datetime import datetime, timezone
    from app.schemas import ImageHistoryItem
    from app.services.history_read_maintenance import MAX_HISTORY_SOURCE_LINE_BYTES

    prepare, args = cli
    source_path = tmp_path / "history.jsonl"
    assert prepare["main"]([*args, "--minimum-free-bytes", "1024"]) == 0
    capsys.readouterr()
    item = ImageHistoryItem(
        output_id="out-large", job_id="job-large", provider_id="provider", model="model",
        prompt="fixture", url="/outputs/out-large", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata={"oversized": "x" * MAX_HISTORY_SOURCE_LINE_BYTES},
    )
    source_path.write_text(item.model_dump_json() + "\n", encoding="utf-8")
    databases = [tmp_path / "image_history_index.sqlite3", tmp_path / "image_favorites.sqlite3"]
    before = {path.name: path.read_bytes() for path in databases}
    source_before = source_path.read_bytes()
    monkeypatch.setattr(prepare["shutil"], "disk_usage", lambda _: SimpleNamespace(free=1024 * 1024 * 1024))

    assert _verifier_namespace()["main"](args) == 2

    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "blocked", "error_type": "HistoryReadVerificationError"}
    assert source_path.read_bytes() == source_before
    assert {path.name: path.read_bytes() for path in databases} == before
