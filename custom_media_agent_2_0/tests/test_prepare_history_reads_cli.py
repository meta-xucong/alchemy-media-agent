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
