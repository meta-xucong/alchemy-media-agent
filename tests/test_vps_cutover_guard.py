from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys

import pytest


_PATH = Path(__file__).parents[1] / "scripts" / "vps_cutover_guard.py"
_SPEC = importlib.util.spec_from_file_location("vps_cutover_guard", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)


def _databases(tmp_path: Path, *, v1_status: str = "ready", v2_status: str = "completed"):
    v1 = tmp_path / "v1" / "repository.sqlite3"
    v1.parent.mkdir()
    connection = sqlite3.connect(v1)
    try:
        connection.execute("CREATE TABLE v1_records(namespace TEXT, record_key TEXT, payload TEXT)")
        connection.execute("INSERT INTO v1_records VALUES('jobs','j1',?)", (json.dumps({"status": v1_status}),))
        connection.execute("INSERT INTO v1_records VALUES('lab_sessions','s-terminal',?)", (json.dumps({"status": "completed"}),))
        connection.commit()
    finally:
        connection.close()
    v2 = tmp_path / "v2" / "task_queue.sqlite3"
    v2.parent.mkdir()
    connection = sqlite3.connect(v2)
    try:
        connection.execute("CREATE TABLE v2_tasks(status TEXT)")
        connection.execute("CREATE TABLE resource_leases(namespace TEXT, lease_until REAL)")
        connection.execute("INSERT INTO v2_tasks VALUES(?)", (v2_status,))
        connection.commit()
    finally:
        connection.close()
    projects = tmp_path / "v1" / "v3_projects"
    projects.mkdir()
    (tmp_path / "v1" / "v3_jobs").mkdir()
    return v1, v2, projects


def test_inspect_active_work_reports_idle_without_mutating(tmp_path):
    v1, v2, projects = _databases(tmp_path)
    before = {path: path.read_bytes() for path in (v1, v2)}

    result = _MODULE.inspect_active_work(v1, v2, projects)

    assert result["status"] == "idle"
    assert result["active_work_items"] == 0
    assert {path: path.read_bytes() for path in (v1, v2)} == before


@pytest.mark.parametrize("v1_status,v2_status", [("generating", "completed"), ("ready", "queued"), ("ready", "running")])
def test_inspect_active_work_blocks_durable_work(tmp_path, v1_status, v2_status):
    v1, v2, projects = _databases(tmp_path, v1_status=v1_status, v2_status=v2_status)
    assert _MODULE.inspect_active_work(v1, v2, projects)["status"] == "blocked"


def test_inspect_active_work_fails_closed_on_unknown_job_status(tmp_path):
    v1, v2, projects = _databases(tmp_path, v1_status="mystery")
    with pytest.raises(_MODULE.CutoverBlocked, match="unknown"):
        _MODULE.inspect_active_work(v1, v2, projects)


@pytest.mark.parametrize("status", ["queued", "running"])
def test_inspect_active_work_blocks_queued_or_running_lab_sessions(tmp_path, status):
    v1, v2, projects = _databases(tmp_path)
    with sqlite3.connect(v1) as connection:
        connection.execute(
            "INSERT INTO v1_records VALUES('lab_sessions','s-active',?)",
            (json.dumps({"status": status}),),
        )

    result = _MODULE.inspect_active_work(v1, v2, projects)

    assert result["status"] == "blocked"
    assert result["counts"]["lab_active_sessions"] == 1


@pytest.mark.parametrize("payload", ["{", json.dumps({"status": "unknown"}), json.dumps({})])
def test_inspect_active_work_fails_closed_on_malformed_or_unknown_lab_state(tmp_path, payload):
    v1, v2, projects = _databases(tmp_path)
    with sqlite3.connect(v1) as connection:
        connection.execute("INSERT INTO v1_records VALUES('lab_sessions','s-bad',?)", (payload,))

    with pytest.raises(_MODULE.CutoverBlocked, match="lab_session"):
        _MODULE.inspect_active_work(v1, v2, projects)


@pytest.mark.parametrize("status", ["queued", "generating", "finalizing"])
def test_inspect_active_work_blocks_v3_jobs_in_nonterminal_states(tmp_path, status):
    v1, v2, projects = _databases(tmp_path)
    jobs = tmp_path / "v1" / "v3_jobs"
    (jobs / "job.json").write_text(json.dumps({"status": status}), encoding="utf-8")

    result = _MODULE.inspect_active_work(v1, v2, projects)

    assert result["status"] == "blocked"
    assert result["counts"]["v3_active_jobs"] == 1


def test_inspect_active_work_fails_closed_on_unknown_v3_job_and_planning_states(tmp_path):
    v1, v2, projects = _databases(tmp_path)
    jobs = tmp_path / "v1" / "v3_jobs"
    job = jobs / "job.json"
    job.write_text(json.dumps({"status": "unrecognized"}), encoding="utf-8")
    with pytest.raises(_MODULE.CutoverBlocked, match="unknown"):
        _MODULE.inspect_active_work(v1, v2, projects)

    job.unlink()
    project = projects / "project.json"
    project.write_text(json.dumps({"metadata": {"doc277_planning_current_operation": {"state": "mystery"}}}), encoding="utf-8")
    with pytest.raises(_MODULE.CutoverBlocked, match="planning_state_unknown"):
        _MODULE.inspect_active_work(v1, v2, projects)


def test_inspect_active_work_blocks_pending_v3_planning_operation(tmp_path):
    v1, v2, projects = _databases(tmp_path)
    project = projects / "project.json"
    project.write_text(json.dumps({"metadata": {"doc277_planning_current_operation": {"state": "planning"}}}), encoding="utf-8")

    result = _MODULE.inspect_active_work(v1, v2, projects)

    assert result["status"] == "blocked"
    assert result["counts"]["v3_planning_operations"] == 1


def test_backup_and_restore_preserve_database_and_source_epoch(tmp_path):
    v1, v2, _projects = _databases(tmp_path)
    source = tmp_path / "v1" / "history.jsonl"
    source.write_text('{"id":"before"}\n', encoding="utf-8")
    roots = [tmp_path / "v1", tmp_path / "v2"]
    backup_dir = tmp_path / "backup"

    result = _MODULE.create_backup(backup_dir, roots, [v1, v2], [source])
    assert result["status"] == "backed_up"
    if os.name != "nt":
        assert (backup_dir.stat().st_mode & 0o777) == 0o700

    connection = sqlite3.connect(v1)
    try:
        connection.execute("UPDATE v1_records SET payload='{}'")
        connection.commit()
    finally:
        connection.close()
    v2.unlink()
    source.write_text('{"id":"after"}\n', encoding="utf-8")

    restored = _MODULE.restore_backup(backup_dir / "manifest.json", roots)
    assert restored["status"] == "restored"
    with sqlite3.connect(v1) as connection:
        assert json.loads(connection.execute("SELECT payload FROM v1_records").fetchone()[0]) == {"status": "ready"}
    with sqlite3.connect(v2) as connection:
        assert connection.execute("SELECT status FROM v2_tasks").fetchone()[0] == "completed"
    assert source.read_text(encoding="utf-8") == '{"id":"before"}\n'


def test_backup_refuses_database_outside_allowed_roots(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.sqlite3"
    sqlite3.connect(outside).close()
    with pytest.raises(_MODULE.CutoverBlocked, match="outside"):
        _MODULE.create_backup(tmp_path / "backup", [allowed], [outside], [])


def test_restore_refuses_changed_allowed_roots(tmp_path):
    v1, v2, _projects = _databases(tmp_path)
    roots = [tmp_path / "v1", tmp_path / "v2"]
    backup_dir = tmp_path / "backup"
    _MODULE.create_backup(backup_dir, roots, [v1, v2], [])
    with pytest.raises(_MODULE.CutoverBlocked, match="roots_mismatch"):
        _MODULE.restore_backup(backup_dir / "manifest.json", [tmp_path / "v1"])


def test_restore_removes_new_database_and_sqlite_sidecars_created_after_backup(tmp_path):
    root = tmp_path / "v2"
    root.mkdir()
    future_database = root / "image_history_index.sqlite3"
    backup_dir = tmp_path / "backup"

    _MODULE.create_backup(backup_dir, [root], [future_database], [])
    connection = sqlite3.connect(future_database)
    try:
        connection.execute("CREATE TABLE created_after_backup(value TEXT)")
    finally:
        connection.close()
    for suffix in ("-wal", "-shm", "-journal"):
        Path(str(future_database) + suffix).write_bytes(b"stale sidecar")

    _MODULE.restore_backup(backup_dir / "manifest.json", [root])

    assert not future_database.exists()
    assert all(not Path(str(future_database) + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))


def test_v2_storage_root_verification_requires_all_live_processes_to_match(tmp_path):
    expected = {
        "V2_DATA_DIR": str(tmp_path / "data"),
        "V2_STORAGE_DIR": str(tmp_path / "storage"),
        "V2_IMAGE_HISTORY_PATH": str(tmp_path / "data" / "image_history.jsonl"),
        "V2_TASK_QUEUE_DB_PATH": str(tmp_path / "data" / "task_queue.sqlite3"),
    }
    units = {name: {"environment_files": ["/etc/alchemy/alchemy-v2.env"], "drop_in_paths": []}
             for name in _MODULE._V2_UNITS}
    processes = {name: dict(expected) for name in units}

    assert _MODULE.verify_v2_storage_roots(expected, units, processes)["status"] == "verified"

    processes["alchemy-v2-worker.service"]["V2_DATA_DIR"] = str(tmp_path / "other")
    with pytest.raises(_MODULE.CutoverBlocked, match="storage_root"):
        _MODULE.verify_v2_storage_roots(expected, units, processes)


def test_v2_storage_root_verification_rejects_relative_or_unverified_unit_config(tmp_path):
    expected = {
        "V2_DATA_DIR": "relative/data",
        "V2_STORAGE_DIR": str(tmp_path / "storage"),
        "V2_IMAGE_HISTORY_PATH": str(tmp_path / "history.jsonl"),
        "V2_TASK_QUEUE_DB_PATH": str(tmp_path / "queue.sqlite3"),
    }
    units = {name: {"environment_files": ["/etc/alchemy/alchemy-v2.env"], "drop_in_paths": []}
             for name in _MODULE._V2_UNITS}
    processes = {name: dict(expected) for name in units}
    with pytest.raises(_MODULE.CutoverBlocked, match="absolute"):
        _MODULE.verify_v2_storage_roots(expected, units, processes)

    expected = {
        "V2_DATA_DIR": str(tmp_path / "data"),
        "V2_STORAGE_DIR": str(tmp_path / "storage"),
        "V2_IMAGE_HISTORY_PATH": str(tmp_path / "history.jsonl"),
        "V2_TASK_QUEUE_DB_PATH": str(tmp_path / "queue.sqlite3"),
    }
    units["alchemy-v2-api.service"]["drop_in_paths"] = ["/etc/systemd/system/alchemy-v2-api.service.d/99-override.conf"]
    processes = {name: dict(expected) for name in units}
    with pytest.raises(_MODULE.CutoverBlocked, match="unit_environment"):
        _MODULE.verify_v2_storage_roots(expected, units, processes)


def test_cutover_space_estimate_includes_indexes_restore_temporary_and_reserve(tmp_path):
    database = tmp_path / "source.sqlite3"
    database.write_bytes(b"x" * 1000)
    source = tmp_path / "history.jsonl"
    source.write_bytes(b"y" * 2000)

    estimate = _MODULE.estimate_cutover_space(
        databases=[database], sources=[source], index_growth_bytes=3000,
        restore_temporary_bytes=1000, reserve_bytes=4000,
    )

    assert estimate["backup_bytes"] >= 3000
    assert estimate["index_growth_bytes"] == 3000
    assert estimate["restore_temporary_bytes"] == 1000
    assert estimate["reserve_bytes"] == 4000
    assert estimate["required_bytes"] >= 11000


def test_file_space_estimate_accounts_for_index_growth_and_verifier_scratch(tmp_path):
    database = tmp_path / "repository.sqlite3"
    database.write_bytes(b"d" * 2048)
    Path(str(database) + "-wal").write_bytes(b"w" * 1024)
    source = tmp_path / "history.jsonl"
    source.write_bytes(b"s" * 4096)

    estimate = _MODULE.estimate_cutover_space_from_files([database], [source], 4096)

    assert estimate["index_growth_bytes"] >= 2 * 2048 + 4 * 4096
    assert estimate["verification_scratch_bytes"] >= 2 * 4096
    assert estimate["restore_temporary_bytes"] >= 2048 + 1024
    assert estimate["required_data_bytes"] >= (
        estimate["index_growth_bytes"] + estimate["verification_scratch_bytes"]
        + estimate["restore_temporary_bytes"] + 4096
    )


def test_v2_api_side_effect_guard_requires_all_background_writer_flags_false():
    flags = {
        "V2_TASK_QUEUE_INLINE_WORKER_ENABLED": "false",
        "V2_SYNC_GITHUB_ON_STARTUP": "0",
        "V2_ENABLE_REMOTE_GITHUB_SYNC": "off",
    }
    assert _MODULE.verify_v2_api_side_effects_disabled(flags)["status"] == "verified"
    flags["V2_ENABLE_REMOTE_GITHUB_SYNC"] = "true"
    with pytest.raises(_MODULE.CutoverBlocked, match="background_writer_enabled"):
        _MODULE.verify_v2_api_side_effects_disabled(flags)


def test_v2_api_runtime_contract_is_exact_and_fail_closed(tmp_path):
    environment = tmp_path / "api.env"
    drop_in = tmp_path / "api.conf"
    environment.write_text(
        "V2_TASK_QUEUE_INLINE_WORKER_ENABLED=false\n"
        "V2_SYNC_GITHUB_ON_STARTUP=false\n"
        "V2_ENABLE_REMOTE_GITHUB_SYNC=false\n",
        encoding="utf-8",
    )
    drop_in.write_text(f"[Service]\nEnvironmentFile={environment}\n", encoding="utf-8")
    assert _MODULE.verify_v2_api_runtime_contract(environment, drop_in)["status"] == "verified"
    environment.write_text(environment.read_text(encoding="utf-8").replace("REMOTE_GITHUB_SYNC=false", "REMOTE_GITHUB_SYNC=true"), encoding="utf-8")
    with pytest.raises(_MODULE.CutoverBlocked, match="runtime_contract_invalid"):
        _MODULE.verify_v2_api_runtime_contract(environment, drop_in)


def test_v2_storage_roots_accept_only_the_api_specific_worker_ownership_overlay(tmp_path):
    expected = {
        "V2_DATA_DIR": str(tmp_path / "data"),
        "V2_STORAGE_DIR": str(tmp_path / "storage"),
        "V2_IMAGE_HISTORY_PATH": str(tmp_path / "history.jsonl"),
        "V2_TASK_QUEUE_DB_PATH": str(tmp_path / "queue.sqlite3"),
    }
    overlay = str(tmp_path / "alchemy-v2-api-runtime.env")
    drop_in = str(tmp_path / "90-alchemy-worker-ownership.conf")
    base_environment = str(tmp_path / "alchemy-v2.env")
    units = {
        "alchemy-v2-api.service": {
                "environment_files": [base_environment, overlay],
            "drop_in_paths": [drop_in],
        },
        "alchemy-v2-worker.service": {
            "environment_files": [base_environment], "drop_in_paths": [],
        },
        "alchemy-v2-sync-worker.service": {
            "environment_files": [base_environment], "drop_in_paths": [],
        },
    }
    processes = {name: dict(expected) for name in units}
    permitted_drop_ins = {"alchemy-v2-api.service": [drop_in]}
    permitted_env_files = {
        "alchemy-v2-api.service": [base_environment, overlay],
        "alchemy-v2-worker.service": [base_environment],
        "alchemy-v2-sync-worker.service": [base_environment],
    }

    assert _MODULE.verify_v2_storage_roots(
        expected, units, processes, permitted_drop_ins, permitted_env_files,
    )["status"] == "verified"
    units["alchemy-v2-api.service"]["environment_files"] = [overlay, "/etc/alchemy/alchemy-v2.env"]
    with pytest.raises(_MODULE.CutoverBlocked, match="unit_environment_override_unknown"):
        _MODULE.verify_v2_storage_roots(
            expected, units, processes, permitted_drop_ins, permitted_env_files,
        )


def test_prestart_storage_unit_verification_needs_no_running_processes(tmp_path, monkeypatch):
    roots = {
        "V2_DATA_DIR": str(tmp_path / "data"),
        "V2_STORAGE_DIR": str(tmp_path / "storage"),
        "V2_IMAGE_HISTORY_PATH": str(tmp_path / "history.jsonl"),
        "V2_TASK_QUEUE_DB_PATH": str(tmp_path / "queue.sqlite3"),
    }
    environment_file = tmp_path / "alchemy-v2.env"
    environment_file.write_text("".join(f"{key}={value}\n" for key, value in roots.items()), encoding="utf-8")
    units = {
        unit: {"environment_files": ["/etc/alchemy/alchemy-v2.env"], "drop_in_paths": []}
        for unit in _MODULE._V2_UNITS
    }
    monkeypatch.setattr(_MODULE, "read_v2_unit_configuration", lambda: units)
    monkeypatch.setattr(
        _MODULE, "read_v2_process_configuration",
        lambda: pytest.fail("pre-start root verification must not require process PIDs"),
    )

    assert _MODULE.verify_live_v2_storage_unit_roots(environment_file, roots)["status"] == "verified"


def test_backup_restore_preserves_original_file_metadata_and_keeps_backup_private(tmp_path):
    v1, _v2, _projects = _databases(tmp_path)
    source = tmp_path / "v1" / "history.jsonl"
    source.write_text('{"id":"before"}\n', encoding="utf-8")
    if os.name != "nt":
        os.chmod(v1, 0o660)
        os.chmod(source, 0o640)
    roots = [tmp_path / "v1"]
    backup_dir = tmp_path / "backup"
    _MODULE.create_backup(backup_dir, roots, [v1], [source])
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert all({"uid", "gid", "mode"} <= set(item["metadata"]) for item in manifest["records"] if item["existed"])
    if os.name != "nt":
        assert all((backup_dir / item["backup"]).stat().st_mode & 0o777 == 0o600 for item in manifest["records"] if item["existed"])
        os.chmod(v1, 0o600)
        os.chmod(source, 0o600)
    _MODULE.restore_backup(backup_dir / "manifest.json", roots)
    if os.name != "nt":
        assert v1.stat().st_mode & 0o777 == 0o660
        assert source.stat().st_mode & 0o777 == 0o640
        assert v1.stat().st_uid == manifest["records"][0]["metadata"]["uid"]
        assert source.stat().st_gid == manifest["records"][1]["metadata"]["gid"]


def test_restore_rejects_legacy_manifest_without_original_metadata(tmp_path):
    v1, _v2, _projects = _databases(tmp_path)
    roots = [tmp_path / "v1"]
    backup_dir = tmp_path / "backup"
    _MODULE.create_backup(backup_dir, roots, [v1], [])
    manifest_path = backup_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest["records"][0].pop("metadata", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(_MODULE.CutoverBlocked, match="manifest_invalid"):
        _MODULE.restore_backup(manifest_path, roots)


def test_v2_write_access_probe_checks_directory_sqlite_and_append_paths(tmp_path):
    root = tmp_path / "v2"
    root.mkdir()
    database = root / "queue.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE tasks(value TEXT)")
    append_file = root / "history.jsonl"
    append_file.write_text("{}\n", encoding="utf-8")

    result = _MODULE.verify_v2_write_access([root], [database], [append_file])

    assert result["status"] == "verified"
    assert database.exists() and append_file.read_text(encoding="utf-8") == "{}\n"


def test_v2_write_access_probe_rejects_missing_sqlite_file(tmp_path):
    with pytest.raises(_MODULE.CutoverBlocked, match="write_probe_database_missing"):
        _MODULE.verify_v2_write_access([tmp_path], [tmp_path / "missing.sqlite3"], [])


def test_v2_write_access_probe_cli_returns_verified_json(tmp_path, capsys):
    root = tmp_path / "v2"
    root.mkdir()
    database = root / "queue.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE tasks(value TEXT)")

    exit_code = _MODULE.main(["verify-v2-write-access", "--directory", str(root), "--sqlite-db", str(database)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"
