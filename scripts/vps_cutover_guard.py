#!/usr/bin/env python3
"""Read-only work fence inspection and bounded SQLite cutover snapshots.

This utility never starts services, imports the application, runs providers, or
prints database payloads. Restore is intended only before candidate writers are
allowed to run and while all production writers remain stopped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import sqlite3
import stat
import tempfile
import subprocess
import sys
import time
import uuid


V1_ACTIVE = {
    "created", "queued", "planning", "safety_check", "generating",
    "postprocessing", "evaluating", "processing", "submitted",
    "planned", "finalizing",
}
V1_KNOWN = V1_ACTIVE | {
    "provider_not_configured", "ready", "generated", "selected", "failed",
    "canceled", "cancelled", "rejected", "blocked", "not_found",
}
LAB_ACTIVE = {"queued", "running"}
LAB_KNOWN = LAB_ACTIVE | {"completed", "partial_success", "failed"}
V2_ACTIVE = {"queued", "running"}
V2_KNOWN = V2_ACTIVE | {"completed", "failed", "cancelled", "rejected"}
V3_ACTIVE = {
    "created", "queued", "planning", "safety_check", "generating",
    "postprocessing", "evaluating", "processing", "submitted", "planned",
    "finalizing",
}
V3_KNOWN = V3_ACTIVE | {
    "provider_not_configured", "ready", "generated", "selected", "not_found",
    "failed", "blocked", "canceled", "cancelled", "rejected",
}
V3_PLANNING_STATES = {"planning", "planning_failed"}


class CutoverBlocked(RuntimeError):
    pass


def _private_mode(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        if os.name != "nt":
            raise


def _readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise CutoverBlocked("required_database_missing")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1.0)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}


def _read_v3_bootstrap_environment(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise CutoverBlocked("v3_bootstrap_environment_unreadable") from None
    relevant = {
        "ALCHEMY_V3_PROJECT_DIR", "ALCHEMY_V3_JOB_DIR", "MEDIA_STORAGE_ROOT",
        "MEDIA_AGENT_RUNTIME_ENV_FILE", "ALCHEMY_MEDIA_AGENT_ENV_FILE",
        "ALCHEMY_MEDIA_RUNTIME_ENV_FILE",
    }
    values: dict[str, str] = {}
    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        key, separator, raw_value = entry.partition("=")
        key = key.strip()
        if key not in relevant:
            tokens = key.split(None, 1)
            if tokens and tokens[0] in relevant:
                raise CutoverBlocked("v3_storage_environment_ambiguous")
            continue
        if not separator or key in values:
            raise CutoverBlocked("v3_storage_environment_ambiguous")
        value = raw_value.strip()
        if value.startswith(("'", '"')):
            quote = value[0]
            closing = value.find(quote, 1)
            trailing = value[closing + 1:].strip() if closing >= 0 else "invalid"
            if closing < 0 or (trailing and not trailing.lstrip().startswith("#")):
                raise CutoverBlocked("v3_storage_environment_ambiguous")
            value = value[1:closing]
        else:
            value = value.split(" #", 1)[0].strip()
        values[key] = value
    return values


def verify_v3_storage_roots(
    container_inspect: object, v1_media_root: Path, bootstrap_env_file: Path | None = None,
) -> dict:
    """Verify V3's effective container roots map to the guarded host mount."""
    if not isinstance(container_inspect, list) or len(container_inspect) != 1:
        raise CutoverBlocked("v3_container_inspect_ambiguous")
    container = container_inspect[0]
    config = container.get("Config") if isinstance(container, dict) else None
    mounts = container.get("Mounts") if isinstance(container, dict) else None
    if not isinstance(config, dict) or not isinstance(mounts, list):
        raise CutoverBlocked("v3_container_inspect_invalid")

    workdir = config.get("WorkingDir") or "/"
    if not isinstance(workdir, str) or not workdir.startswith("/"):
        raise CutoverBlocked("v3_container_workdir_invalid")
    env_items = config.get("Env")
    if not isinstance(env_items, list):
        raise CutoverBlocked("v3_storage_environment_ambiguous")
    relevant = {
        "ALCHEMY_V3_PROJECT_DIR", "ALCHEMY_V3_JOB_DIR", "MEDIA_STORAGE_ROOT",
        "MEDIA_AGENT_RUNTIME_ENV_FILE", "ALCHEMY_MEDIA_AGENT_ENV_FILE",
        "ALCHEMY_MEDIA_RUNTIME_ENV_FILE",
    }
    env: dict[str, str] = {}
    for item in env_items:
        if not isinstance(item, str) or "=" not in item:
            raise CutoverBlocked("v3_storage_environment_ambiguous")
        key, value = item.split("=", 1)
        if key not in relevant:
            continue
        if key in env:
            raise CutoverBlocked("v3_storage_environment_ambiguous")
        env[key] = value
    bootstrap_env = _read_v3_bootstrap_environment(bootstrap_env_file)
    effective_env = {**bootstrap_env, **env}
    runtime_pointers = (
        "MEDIA_AGENT_RUNTIME_ENV_FILE", "ALCHEMY_MEDIA_AGENT_ENV_FILE",
        "ALCHEMY_MEDIA_RUNTIME_ENV_FILE",
    )
    if any(bootstrap_env.get(key) for key in runtime_pointers) or any(
        effective_env.get(key) for key in runtime_pointers
    ):
        raise CutoverBlocked("v3_runtime_env_file_unsupported")

    def resolved_container_path(value: str) -> str:
        if not value:
            raise CutoverBlocked("v3_storage_root_invalid")
        path = PurePosixPath(value)
        if not path.is_absolute():
            path = PurePosixPath(workdir) / path
        return posixpath.normpath(str(path))

    project_value = effective_env.get("ALCHEMY_V3_PROJECT_DIR") or "/app/.media_storage/v3_projects"
    job_base = effective_env.get("ALCHEMY_V3_JOB_DIR") or effective_env.get("MEDIA_STORAGE_ROOT") or "/app/.media_storage"
    project_root = resolved_container_path(project_value)
    jobs_root = resolved_container_path(str(PurePosixPath(job_base) / "v3_jobs"))
    expected_project = "/app/.media_storage/v3_projects"
    expected_jobs = "/app/.media_storage/v3_jobs"
    for key, value in bootstrap_env.items():
        if not value:
            continue
        if key == "ALCHEMY_V3_PROJECT_DIR" and resolved_container_path(value) != expected_project:
            raise CutoverBlocked("v3_storage_root_mismatch")
        if (
            key in {"ALCHEMY_V3_JOB_DIR", "MEDIA_STORAGE_ROOT"}
            and resolved_container_path(value) != "/app/.media_storage"
        ):
            raise CutoverBlocked("v3_storage_root_mismatch")
    if project_root != expected_project or jobs_root != expected_jobs:
        raise CutoverBlocked("v3_storage_root_mismatch")

    try:
        expected_host_root = v1_media_root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise CutoverBlocked("v3_storage_mount_mismatch") from None
    storage_mounts = [mount for mount in mounts if isinstance(mount, dict)
                      and mount.get("Destination") == "/app/.media_storage"]
    if len(storage_mounts) != 1:
        raise CutoverBlocked("v3_storage_mount_mismatch")
    storage_mount = storage_mounts[0]
    source = storage_mount.get("Source")
    if not isinstance(source, str) or not source:
        raise CutoverBlocked("v3_storage_mount_mismatch")
    try:
        actual_host_root = Path(source).resolve(strict=True)
    except (OSError, RuntimeError):
        raise CutoverBlocked("v3_storage_mount_mismatch") from None
    if actual_host_root != expected_host_root or storage_mount.get("RW") is not True:
        raise CutoverBlocked("v3_storage_mount_mismatch")
    for relative_root in ("v3_projects", "v3_jobs"):
        try:
            if not _within(expected_host_root / relative_root, [expected_host_root]):
                raise CutoverBlocked("v3_storage_root_mismatch")
        except (OSError, RuntimeError):
            raise CutoverBlocked("v3_storage_root_mismatch") from None

    for mount in mounts:
        if not isinstance(mount, dict):
            raise CutoverBlocked("v3_storage_mount_mismatch")
        destination = mount.get("Destination")
        if not isinstance(destination, str) or not destination.startswith("/"):
            raise CutoverBlocked("v3_storage_mount_mismatch")
        normalized = posixpath.normpath(destination)
        for record_root in (expected_project, expected_jobs):
            if normalized == record_root or normalized.startswith(record_root + "/"):
                raise CutoverBlocked("v3_storage_mount_shadowing")

    return {
        "status": "verified",
        "v3_projects_root": project_root,
        "v3_jobs_root": jobs_root,
        "v1_media_mount": str(actual_host_root),
    }


def inspect_active_work(v1_database: Path, v2_queue_database: Path, v3_projects: Path) -> dict:
    counts = {"v1_active_jobs": 0, "v3_active_jobs": 0, "v3_planning_operations": 0,
              "v2_queued_or_running_tasks": 0, "v2_unexpired_generation_leases": 0,
              "lab_active_sessions": 0}
    v1 = _readonly(v1_database)
    try:
        if "v1_records" not in _tables(v1):
            raise CutoverBlocked("v1_repository_schema_missing")
        for (payload_text,) in v1.execute("SELECT payload FROM v1_records WHERE namespace='jobs'"):
            try:
                payload = json.loads(payload_text)
            except (TypeError, json.JSONDecodeError):
                raise CutoverBlocked("v1_job_state_unreadable") from None
            if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
                raise CutoverBlocked("v1_job_state_unreadable")
            status = payload["status"].lower()
            if status not in V1_KNOWN:
                raise CutoverBlocked("v1_job_state_unknown")
            counts["v1_active_jobs"] += status in V1_ACTIVE
        for (payload_text,) in v1.execute("SELECT payload FROM v1_records WHERE namespace='lab_sessions'"):
            try:
                payload = json.loads(payload_text)
            except (TypeError, json.JSONDecodeError):
                raise CutoverBlocked("lab_session_state_unreadable") from None
            if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
                raise CutoverBlocked("lab_session_state_unreadable")
            status = payload["status"].lower()
            if status not in LAB_KNOWN:
                raise CutoverBlocked("lab_session_state_unknown")
            counts["lab_active_sessions"] += status in LAB_ACTIVE
    finally:
        v1.close()

    v2 = _readonly(v2_queue_database)
    try:
        if "v2_tasks" not in _tables(v2):
            raise CutoverBlocked("v2_task_queue_schema_missing")
        for (raw_status,) in v2.execute("SELECT status FROM v2_tasks"):
            status = str(raw_status).lower()
            if status not in V2_KNOWN:
                raise CutoverBlocked("v2_task_state_unknown")
            counts["v2_queued_or_running_tasks"] += status in V2_ACTIVE
        if "resource_leases" in _tables(v2):
            columns = {str(row[1]) for row in v2.execute("PRAGMA table_info(resource_leases)")}
            if not {"namespace", "lease_until"}.issubset(columns):
                raise CutoverBlocked("v2_generation_lease_schema_unknown")
            counts["v2_unexpired_generation_leases"] = int(v2.execute(
                "SELECT COUNT(*) FROM resource_leases WHERE namespace='generation' AND lease_until>?",
                (time.time(),),
            ).fetchone()[0])
    finally:
        v2.close()

    if not v3_projects.is_dir():
        raise CutoverBlocked("v3_projects_root_missing")
    for directory_name, kind in (("v3_projects", "project"), ("v3_jobs", "job")):
        root = v3_projects.parent / directory_name
        if not root.exists():
            continue
        # These are the V3 stores' authoritative record paths. Project
        # directories also contain timeline.json and timeline backup arrays;
        # interpreting every JSON below v3_projects as a ProjectRecord makes
        # valid auxiliary history block a cutover. Keep malformed canonical
        # project/job records fail-closed while ignoring non-record sidecars.
        record_paths = (
            root.glob("project_*/project.json") if kind == "project"
            else root.glob("job_*.json")
        )
        for path in record_paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise CutoverBlocked("v3_state_unreadable") from None
            if not isinstance(payload, dict):
                raise CutoverBlocked("v3_state_unreadable")
            metadata_value = payload.get("metadata")
            if metadata_value is not None and not isinstance(metadata_value, dict):
                raise CutoverBlocked("v3_project_metadata_unreadable")
            metadata = metadata_value if isinstance(metadata_value, dict) else {}
            operation = metadata.get("doc277_planning_current_operation")
            if operation is not None:
                if not isinstance(operation, dict) or not isinstance(operation.get("state"), str):
                    raise CutoverBlocked("v3_planning_state_unreadable")
                operation_state = operation["state"].lower()
                if operation_state not in V3_PLANNING_STATES:
                    raise CutoverBlocked("v3_planning_state_unknown")
                counts["v3_planning_operations"] += operation_state == "planning"
            if kind == "job":
                status = payload.get("status")
                if not isinstance(status, str):
                    raise CutoverBlocked("v3_job_state_unreadable")
                normalized_status = status.lower()
                if normalized_status not in V3_KNOWN:
                    raise CutoverBlocked("v3_job_state_unknown")
                counts["v3_active_jobs"] += normalized_status in V3_ACTIVE

    active = sum(counts.values())
    return {"status": "idle" if active == 0 else "blocked", "scope": "durable_active_work_inventory",
            "counts": counts, "active_work_items": active}


_V2_STORAGE_KEYS = (
    "V2_DATA_DIR", "V2_STORAGE_DIR", "V2_IMAGE_HISTORY_PATH", "V2_TASK_QUEUE_DB_PATH",
)
_V2_UNITS = ("alchemy-v2-api.service", "alchemy-v2-worker.service", "alchemy-v2-sync-worker.service")


def _canonical_absolute(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        raise CutoverBlocked("v2_storage_root_not_absolute")
    return str(path.resolve(strict=False))


def verify_v2_storage_roots(
    expected_environment: dict[str, str],
    unit_configuration: dict[str, dict[str, list[str]]],
    process_environments: dict[str, dict[str, str]],
    allowed_drop_ins: dict[str, list[str]] | None = None,
    allowed_environment_files: dict[str, list[str]] | None = None,
) -> dict:
    """Require identical absolute roots in all running V2 services and known unit config."""
    result = verify_v2_storage_unit_roots(
        expected_environment, unit_configuration, allowed_drop_ins, allowed_environment_files,
    )
    expected = {key: _canonical_absolute(expected_environment[key]) for key in _V2_STORAGE_KEYS}
    for unit in _V2_UNITS:
        process_environment = process_environments[unit]
        if not all(key in process_environment for key in _V2_STORAGE_KEYS):
            raise CutoverBlocked("v2_process_storage_root_missing")
        actual = {key: _canonical_absolute(process_environment[key]) for key in _V2_STORAGE_KEYS}
        if actual != expected:
            raise CutoverBlocked("v2_process_storage_root_mismatch")
    return {**result, "processes_checked": len(_V2_UNITS)}


def verify_v2_storage_unit_roots(
    expected_environment: dict[str, str],
    unit_configuration: dict[str, dict[str, list[str]]],
    allowed_drop_ins: dict[str, list[str]] | None = None,
    allowed_environment_files: dict[str, list[str]] | None = None,
) -> dict:
    """Verify configured roots and file precedence before any service starts."""
    if set(expected_environment) != set(_V2_STORAGE_KEYS):
        raise CutoverBlocked("v2_storage_root_inventory_incomplete")
    for value in expected_environment.values():
        _canonical_absolute(value)
    if set(unit_configuration) != set(_V2_UNITS):
        raise CutoverBlocked("v2_storage_unit_inventory_incomplete")
    for unit in _V2_UNITS:
        config = unit_configuration[unit]
        env_files = [str(Path(item).resolve(strict=False)) for item in config.get("environment_files", [])]
        drop_ins = config.get("drop_in_paths", [])
        permitted_drop_ins = (allowed_drop_ins or {}).get(unit, [])
        permitted_env_files = (allowed_environment_files or {}).get(unit, ["/etc/alchemy/alchemy-v2.env"])
        permitted_env_files = [str(Path(item).resolve(strict=False)) for item in permitted_env_files]
        permitted_drop_ins = [str(Path(item).resolve(strict=False)) for item in permitted_drop_ins]
        if env_files != permitted_env_files or drop_ins != permitted_drop_ins:
            raise CutoverBlocked("v2_unit_environment_override_unknown")
    return {"status": "verified", "units_checked": len(_V2_UNITS), "root_keys_checked": len(_V2_STORAGE_KEYS)}


def read_v2_unit_configuration(unit_names: tuple[str, ...] = _V2_UNITS) -> dict[str, dict[str, list[str]]]:
    """Read systemd file precedence without requiring the unit to be running."""
    units: dict[str, dict[str, list[str]]] = {}
    for unit in unit_names:
        result = subprocess.run(
            ["systemctl", "show", unit, "--property=EnvironmentFiles", "--property=DropInPaths"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise CutoverBlocked("v2_systemd_inspection_failed")
        values = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value.strip()
        raw_env_files = values.get("EnvironmentFiles", "")
        env_files = [part.split(" ", 1)[0] for part in raw_env_files.split() if part.startswith("/")]
        drop_ins = [part for part in values.get("DropInPaths", "").split() if part.startswith("/")]
        units[unit] = {"environment_files": env_files, "drop_in_paths": drop_ins}
    return units


def estimate_cutover_space(
    *, databases: list[Path], sources: list[Path], index_growth_bytes: int,
    restore_temporary_bytes: int, reserve_bytes: int, verification_scratch_bytes: int = 0,
) -> dict[str, int]:
    """Compute required peak bytes; missing/unreadable inputs are not guessed."""
    if min(index_growth_bytes, restore_temporary_bytes, reserve_bytes, verification_scratch_bytes) < 0:
        raise CutoverBlocked("cutover_space_estimate_invalid")
    backup_bytes = 0
    for path in [*databases, *sources]:
        try:
            backup_bytes += path.stat().st_size
        except FileNotFoundError:
            continue
        except OSError:
            raise CutoverBlocked("cutover_space_input_unreadable") from None
    for database in databases:
        try:
            backup_bytes += Path(str(database) + "-wal").stat().st_size
        except FileNotFoundError:
            pass
        except OSError:
            raise CutoverBlocked("cutover_space_input_unreadable") from None
    backup_bytes = max(16 * 1024 * 1024, backup_bytes + backup_bytes // 4 + 16 * 1024 * 1024)
    required = backup_bytes + index_growth_bytes + restore_temporary_bytes + verification_scratch_bytes + reserve_bytes
    return {
        "backup_bytes": backup_bytes,
        "index_growth_bytes": index_growth_bytes,
        "restore_temporary_bytes": restore_temporary_bytes,
        "verification_scratch_bytes": verification_scratch_bytes,
        "reserve_bytes": reserve_bytes,
        "required_backup_bytes": backup_bytes + reserve_bytes,
        "required_data_bytes": index_growth_bytes + restore_temporary_bytes + verification_scratch_bytes + reserve_bytes,
        "required_bytes": required,
    }


def estimate_cutover_space_from_files(databases: list[Path], sources: list[Path], reserve_bytes: int) -> dict:
    database_footprint = 0
    largest_database = 0
    source_footprint = 0
    for database in databases:
        size = 0
        for path in (database, Path(str(database) + "-wal")):
            try:
                size += path.stat().st_size
            except FileNotFoundError:
                continue
            except OSError:
                raise CutoverBlocked("cutover_space_input_unreadable") from None
        database_footprint += size
        largest_database = max(largest_database, size)
    for source in sources:
        try:
            source_footprint += source.stat().st_size
        except FileNotFoundError:
            continue
        except OSError:
            raise CutoverBlocked("cutover_space_input_unreadable") from None
    # The read projections duplicate row-level metadata/payloads. Use a
    # deliberately high multiplier; this is a conservative planning estimate,
    # not a mathematical upper bound. Unreadable inputs fail closed.
    index_growth = max(16 * 1024 * 1024, database_footprint * 2 + source_footprint * 4)
    verification_scratch = max(16 * 1024 * 1024, source_footprint * 2)
    return estimate_cutover_space(
        databases=databases, sources=sources, index_growth_bytes=index_growth,
        restore_temporary_bytes=largest_database, reserve_bytes=reserve_bytes,
        verification_scratch_bytes=verification_scratch,
    )


def read_v2_process_configuration(unit_names: tuple[str, ...] = _V2_UNITS) -> tuple[dict, dict]:
    """Read non-secret systemd properties and only V2 storage keys from /proc."""
    units = read_v2_unit_configuration(unit_names)
    processes: dict[str, dict[str, str]] = {}
    for unit in unit_names:
        result = subprocess.run(
            ["systemctl", "show", unit, "--property=MainPID"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise CutoverBlocked("v2_systemd_inspection_failed")
        values = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value.strip()
        pid = values.get("MainPID", "")
        if not pid.isdecimal() or pid == "0":
            raise CutoverBlocked("v2_process_not_running")
        try:
            raw = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        except OSError:
            raise CutoverBlocked("v2_process_environment_unavailable") from None
        environment = {}
        for entry in raw:
            key, separator, value = entry.partition(b"=")
            if separator and key.decode(errors="ignore") in _V2_STORAGE_KEYS:
                environment[key.decode()] = value.decode(errors="strict")
        processes[unit] = environment
    return units, processes


def _read_simple_environment_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        raise CutoverBlocked("v2_environment_file_unreadable") from None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        if not separator:
            raise CutoverBlocked("v2_environment_file_invalid")
        key = key.strip()
        if key in _V2_STORAGE_KEYS:
            if key in values:
                raise CutoverBlocked("v2_environment_file_duplicate_root")
            values[key] = value.strip().strip('"').strip("'")
    return values


def verify_live_v2_storage_roots(environment_file: Path, expected_environment: dict[str, str]) -> dict:
    file_values = _read_simple_environment_file(environment_file)
    if set(file_values) != set(_V2_STORAGE_KEYS):
        raise CutoverBlocked("v2_environment_file_root_inventory_incomplete")
    expected = {key: _canonical_absolute(expected_environment[key]) for key in _V2_STORAGE_KEYS}
    configured = {key: _canonical_absolute(file_values[key]) for key in _V2_STORAGE_KEYS}
    if configured != expected:
        raise CutoverBlocked("v2_environment_file_root_mismatch")
    units, processes = read_v2_process_configuration()
    return verify_v2_storage_roots(expected, units, processes)


def verify_live_v2_storage_unit_roots(
    environment_file: Path, expected_environment: dict[str, str],
    runtime_drop_in: str | None = None, runtime_env_path: str | None = None,
) -> dict:
    file_values = _read_simple_environment_file(environment_file)
    if set(file_values) != set(_V2_STORAGE_KEYS):
        raise CutoverBlocked("v2_environment_file_root_inventory_incomplete")
    expected = {key: _canonical_absolute(expected_environment[key]) for key in _V2_STORAGE_KEYS}
    configured = {key: _canonical_absolute(file_values[key]) for key in _V2_STORAGE_KEYS}
    if configured != expected:
        raise CutoverBlocked("v2_environment_file_root_mismatch")
    if bool(runtime_drop_in) != bool(runtime_env_path):
        raise CutoverBlocked("v2_cutover_environment_file_missing")
    allowed_drop_ins = None
    allowed_environment_files = None
    if runtime_drop_in and runtime_env_path:
        verify_v2_api_runtime_contract(Path(runtime_env_path), Path(runtime_drop_in))
        allowed_drop_ins = {"alchemy-v2-api.service": [runtime_drop_in]}
        allowed_environment_files = {
            "alchemy-v2-api.service": [str(environment_file), runtime_env_path],
        }
    units = read_v2_unit_configuration()
    return verify_v2_storage_unit_roots(
        expected, units, allowed_drop_ins=allowed_drop_ins,
        allowed_environment_files=allowed_environment_files,
    )


def verify_live_v2_storage_roots_with_api_runtime_contract(
    environment_file: Path, expected_environment: dict[str, str], runtime_drop_in: str, runtime_env_path: str,
) -> dict:
    file_values = _read_simple_environment_file(environment_file)
    if set(file_values) != set(_V2_STORAGE_KEYS):
        raise CutoverBlocked("v2_environment_file_root_inventory_incomplete")
    expected = {key: _canonical_absolute(expected_environment[key]) for key in _V2_STORAGE_KEYS}
    configured = {key: _canonical_absolute(file_values[key]) for key in _V2_STORAGE_KEYS}
    if configured != expected:
        raise CutoverBlocked("v2_environment_file_root_mismatch")
    units, processes = read_v2_process_configuration()
    allowed = {"alchemy-v2-api.service": [runtime_drop_in]}
    env_files = {"alchemy-v2-api.service": ["/etc/alchemy/alchemy-v2.env", runtime_env_path]}
    return verify_v2_storage_roots(
        expected, units, processes, allowed_drop_ins=allowed, allowed_environment_files=env_files,
    )


def verify_v2_api_side_effects_disabled(environment: dict[str, str]) -> dict:
    keys = (
        "V2_TASK_QUEUE_INLINE_WORKER_ENABLED", "V2_SYNC_GITHUB_ON_STARTUP",
        "V2_ENABLE_REMOTE_GITHUB_SYNC",
    )
    if any(key not in environment for key in keys):
        raise CutoverBlocked("v2_api_side_effect_setting_missing")
    if any(environment[key].strip().lower() not in {"0", "false", "no", "off"} for key in keys):
        raise CutoverBlocked("v2_api_background_writer_enabled")
    return {"status": "verified", "settings_checked": len(keys)}


def verify_v2_api_runtime_contract(environment_file: Path, drop_in: Path) -> dict:
    expected_flags = {
        "V2_TASK_QUEUE_INLINE_WORKER_ENABLED": "false",
        "V2_SYNC_GITHUB_ON_STARTUP": "false",
        "V2_ENABLE_REMOTE_GITHUB_SYNC": "false",
    }
    try:
        lines = [line.strip() for line in environment_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        drop_lines = [line.strip() for line in drop_in.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        raise CutoverBlocked("v2_api_runtime_contract_unreadable") from None
    parsed: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if not separator or key in parsed:
            raise CutoverBlocked("v2_api_runtime_contract_invalid")
        parsed[key] = value
    if parsed != expected_flags:
        raise CutoverBlocked("v2_api_runtime_contract_invalid")
    expected_drop_lines = ["[Service]", f"EnvironmentFile={environment_file}"]
    if drop_lines != expected_drop_lines:
        raise CutoverBlocked("v2_api_runtime_contract_invalid")
    return {"status": "verified", "settings_checked": len(expected_flags)}


def read_process_environment(pid: int) -> dict[str, str]:
    try:
        entries = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    except OSError:
        raise CutoverBlocked("v2_process_environment_unavailable") from None
    values = {}
    for entry in entries:
        key, separator, value = entry.partition(b"=")
        if separator:
            values[key.decode(errors="ignore")] = value.decode(errors="strict")
    return values


def _within(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved == root.resolve() or root.resolve() in resolved.parents for root in roots)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _original_file_metadata(path: Path) -> dict:
    try:
        details = path.stat(follow_symlinks=False)
    except OSError:
        raise CutoverBlocked("backup_source_metadata_unavailable") from None
    if not stat.S_ISREG(details.st_mode):
        raise CutoverBlocked("backup_source_not_regular_file")
    return {"uid": int(details.st_uid), "gid": int(details.st_gid), "mode": stat.S_IMODE(details.st_mode)}


def _apply_file_metadata(path: Path, metadata: dict) -> None:
    uid, gid, mode = metadata.get("uid"), metadata.get("gid"), metadata.get("mode")
    if (not isinstance(uid, int) or isinstance(uid, bool) or uid < 0 or
            not isinstance(gid, int) or isinstance(gid, bool) or gid < 0 or
            not isinstance(mode, int) or isinstance(mode, bool) or mode < 0 or mode > 0o7777):
        raise CutoverBlocked("backup_manifest_metadata_invalid")
    try:
        if hasattr(os, "chown"):
            os.chown(path, uid, gid, follow_symlinks=False)
        elif os.name != "nt":
            raise CutoverBlocked("restore_owner_metadata_unsupported")
        if os.name == "nt":
            os.chmod(path, mode)
        else:
            os.chmod(path, mode, follow_symlinks=False)
        observed = path.stat(follow_symlinks=False)
    except (OSError, NotImplementedError):
        raise CutoverBlocked("restore_file_metadata_failed") from None
    if stat.S_IMODE(observed.st_mode) != mode:
        raise CutoverBlocked("restore_file_mode_mismatch")
    if os.name != "nt" and (int(observed.st_uid) != uid or int(observed.st_gid) != gid):
        raise CutoverBlocked("restore_file_owner_mismatch")


def verify_v2_write_access(directories: list[Path], databases: list[Path], append_files: list[Path]) -> dict:
    checked_directories = 0
    checked_databases = 0
    checked_append_files = 0
    for directory in directories:
        if not directory.is_dir():
            raise CutoverBlocked("write_probe_directory_missing")
        descriptor, probe_name = tempfile.mkstemp(prefix=".alchemy-write-check-", dir=directory)
        os.close(descriptor)
        Path(probe_name).unlink()
        checked_directories += 1
    for database in databases:
        if not database.is_file():
            raise CutoverBlocked("write_probe_database_missing")
        connection = None
        try:
            uri = database.resolve().as_uri() + "?mode=rw"
            connection = sqlite3.connect(uri, uri=True, timeout=1.0, isolation_level=None)
            connection.execute("BEGIN IMMEDIATE")
            probe_table = f"__alchemy_cutover_probe_{uuid.uuid4().hex}"
            connection.execute(f'CREATE TABLE "{probe_table}" (value INTEGER NOT NULL)')
            connection.execute(f'INSERT INTO "{probe_table}" (value) VALUES (1)')
            connection.execute("ROLLBACK")
            residue = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (probe_table,),
            ).fetchone()
            if residue is not None:
                raise CutoverBlocked("write_probe_database_rollback_failed")
        except (sqlite3.Error, OSError):
            if connection is not None and connection.in_transaction:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise CutoverBlocked("write_probe_database_unwritable") from None
        finally:
            if connection is not None:
                connection.close()
        checked_databases += 1
    for source in append_files:
        if not source.exists():
            continue
        try:
            details = source.stat(follow_symlinks=False)
            if not stat.S_ISREG(details.st_mode):
                raise CutoverBlocked("write_probe_append_file_not_regular")
            descriptor = os.open(source, os.O_WRONLY | os.O_APPEND)
            os.close(descriptor)
        except OSError:
            raise CutoverBlocked("write_probe_append_file_unwritable") from None
        checked_append_files += 1
    return {"status": "verified", "directories": checked_directories,
            "databases": checked_databases, "append_files": checked_append_files}


def create_backup(backup_dir: Path, roots: list[Path], databases: list[Path], sources: list[Path]) -> dict:
    backup_dir = backup_dir.resolve()
    if backup_dir.exists():
        raise CutoverBlocked("backup_destination_already_exists")
    if not roots or any(not root.is_dir() for root in roots):
        raise CutoverBlocked("backup_root_missing")
    backup_dir.mkdir(mode=0o700, parents=True)
    _private_mode(backup_dir, 0o700)
    records = []
    try:
        seen: set[Path] = set()
        for index, database in enumerate(databases):
            path = database.resolve()
            if path in seen:
                continue
            seen.add(path)
            if not _within(path, roots):
                raise CutoverBlocked("database_outside_allowed_roots")
            existed = path.is_file()
            item = {"kind": "sqlite", "path": str(path), "existed": existed}
            if existed:
                item["metadata"] = _original_file_metadata(path)
                target = backup_dir / f"sqlite-{index:04d}.db"
                source = _readonly(path)
                try:
                    destination = sqlite3.connect(target)
                    try:
                        source.backup(destination)
                        check = destination.execute("PRAGMA quick_check").fetchone()
                        if not check or check[0] != "ok":
                            raise CutoverBlocked("sqlite_backup_quick_check_failed")
                    finally:
                        destination.close()
                finally:
                    source.close()
                _private_mode(target, 0o600)
                item.update({"backup": target.name, "sha256": _sha256(target)})
            records.append(item)

        for index, source_path in enumerate(sources):
            path = source_path.resolve()
            if not _within(path, roots):
                raise CutoverBlocked("source_outside_allowed_roots")
            existed = path.is_file()
            item = {"kind": "source", "path": str(path), "existed": existed}
            if existed:
                item["metadata"] = _original_file_metadata(path)
                target = backup_dir / f"source-{index:04d}-{path.name}"
                shutil.copy2(path, target)
                _private_mode(target, 0o600)
                item.update({"backup": target.name, "sha256": _sha256(target)})
            records.append(item)

        manifest = {"schema_version": 2, "restore_scope": "pre_candidate_writer_start_only",
                    "allowed_roots": [str(root.resolve()) for root in roots], "records": records}
        manifest_path = backup_dir / "manifest.json"
        temporary = backup_dir / "manifest.json.tmp"
        temporary.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
        _private_mode(temporary, 0o600)
        os.replace(temporary, manifest_path)
        return {"status": "backed_up", "database_count": sum(item["kind"] == "sqlite" for item in records),
                "source_count": sum(item["kind"] == "source" for item in records),
                "manifest_sha256": _sha256(manifest_path)}
    except Exception:
        # Keep partial evidence for operator inspection; do not silently remove it.
        raise


def restore_backup(manifest_path: Path, roots: list[Path]) -> dict:
    manifest_path = manifest_path.resolve()
    backup_dir = manifest_path.parent
    if not _within(manifest_path, [backup_dir]) or not manifest_path.is_file():
        raise CutoverBlocked("backup_manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2 or manifest.get("restore_scope") != "pre_candidate_writer_start_only":
        raise CutoverBlocked("backup_manifest_invalid")
    declared_roots = [Path(value).resolve() for value in manifest.get("allowed_roots", [])]
    if {str(root) for root in declared_roots} != {str(root.resolve()) for root in roots}:
        raise CutoverBlocked("backup_roots_mismatch")
    restored = 0
    for item in manifest.get("records", []):
        target = Path(item["path"]).resolve()
        if not _within(target, roots):
            raise CutoverBlocked("restore_path_outside_allowed_roots")
        if not item.get("existed"):
            if target.exists():
                target.unlink()
            if item.get("kind") == "sqlite":
                for suffix in ("-wal", "-shm", "-journal"):
                    sidecar = Path(str(target) + suffix)
                    if not _within(sidecar, roots):
                        raise CutoverBlocked("restore_path_outside_allowed_roots")
                    sidecar.unlink(missing_ok=True)
        else:
            backup = (backup_dir / item["backup"]).resolve()
            if backup.parent != backup_dir or _sha256(backup) != item.get("sha256"):
                raise CutoverBlocked("backup_checksum_mismatch")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".cutover-restore-tmp")
            shutil.copy2(backup, temporary)
            _apply_file_metadata(temporary, item.get("metadata", {}))
            os.replace(temporary, target)
            if item["kind"] == "sqlite":
                for suffix in ("-wal", "-shm", "-journal"):
                    Path(str(target) + suffix).unlink(missing_ok=True)
                connection = _readonly(target)
                try:
                    check = connection.execute("PRAGMA quick_check").fetchone()
                    if not check or check[0] != "ok":
                        raise CutoverBlocked("restored_sqlite_quick_check_failed")
                finally:
                    connection.close()
            if _sha256(target) != item.get("sha256"):
                raise CutoverBlocked("restored_file_checksum_mismatch")
        restored += 1
    return {"status": "restored", "record_count": restored}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect-active-work")
    inspect.add_argument("--v1-database", required=True, type=Path)
    inspect.add_argument("--v2-queue-database", required=True, type=Path)
    inspect.add_argument("--v3-projects-root", required=True, type=Path)
    verify_v3_roots = subparsers.add_parser("verify-v3-storage-roots")
    verify_v3_roots.add_argument("--v1-media-root", required=True, type=Path)
    verify_v3_roots.add_argument("--bootstrap-env-file", required=True, type=Path)
    roots = subparsers.add_parser("verify-v2-storage-roots")
    roots.add_argument("--environment-file", required=True, type=Path)
    roots.add_argument("--data-dir", required=True)
    roots.add_argument("--storage-dir", required=True)
    roots.add_argument("--history-path", required=True)
    roots.add_argument("--queue-db", required=True)
    roots.add_argument("--allow-api-drop-in", type=str)
    roots.add_argument("--allow-api-environment-file", type=str)
    api_flags = subparsers.add_parser("verify-v2-api-no-background-writers")
    api_flags.add_argument("--pid", required=True, type=int)
    unit_roots = subparsers.add_parser("verify-v2-storage-unit-roots")
    unit_roots.add_argument("--environment-file", required=True, type=Path)
    unit_roots.add_argument("--data-dir", required=True)
    unit_roots.add_argument("--storage-dir", required=True)
    unit_roots.add_argument("--history-path", required=True)
    unit_roots.add_argument("--queue-db", required=True)
    unit_roots.add_argument("--allow-api-drop-in", type=str)
    unit_roots.add_argument("--allow-api-environment-file", type=str)
    api_override = subparsers.add_parser("verify-v2-api-runtime-contract")
    api_override.add_argument("--environment-file", required=True, type=Path)
    api_override.add_argument("--drop-in", required=True, type=Path)
    backup = subparsers.add_parser("backup")
    backup.add_argument("--backup-dir", required=True, type=Path)
    backup.add_argument("--allowed-root", action="append", required=True, type=Path)
    backup.add_argument("--database", action="append", default=[], type=Path)
    backup.add_argument("--source", action="append", default=[], type=Path)
    estimate = subparsers.add_parser("estimate-space")
    estimate.add_argument("--inventory-file", required=True, type=Path)
    estimate.add_argument("--source", action="append", default=[], type=Path)
    estimate.add_argument("--reserve-bytes", required=True, type=int)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--manifest", required=True, type=Path)
    restore.add_argument("--allowed-root", action="append", required=True, type=Path)
    write_probe = subparsers.add_parser("verify-v2-write-access")
    write_probe.add_argument("--directory", action="append", default=[], type=Path)
    write_probe.add_argument("--sqlite-db", action="append", default=[], type=Path)
    write_probe.add_argument("--append-file", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect-active-work":
            result = inspect_active_work(args.v1_database, args.v2_queue_database, args.v3_projects_root)
        elif args.command == "verify-v3-storage-roots":
            try:
                container_inspect = json.load(sys.stdin)
            except (OSError, json.JSONDecodeError):
                raise CutoverBlocked("v3_container_inspect_invalid") from None
            result = verify_v3_storage_roots(
                container_inspect, args.v1_media_root, args.bootstrap_env_file
            )
        elif args.command == "verify-v2-storage-roots":
            expected_roots = {
                "V2_DATA_DIR": args.data_dir,
                "V2_STORAGE_DIR": args.storage_dir,
                "V2_IMAGE_HISTORY_PATH": args.history_path,
                "V2_TASK_QUEUE_DB_PATH": args.queue_db,
            }
            if args.allow_api_drop_in:
                if not args.allow_api_environment_file:
                    raise CutoverBlocked("v2_cutover_environment_file_missing")
                result = verify_live_v2_storage_roots_with_api_runtime_contract(
                    args.environment_file, expected_roots, args.allow_api_drop_in,
                    args.allow_api_environment_file,
                )
            else:
                result = verify_live_v2_storage_roots(args.environment_file, expected_roots)
        elif args.command == "verify-v2-api-no-background-writers":
            result = verify_v2_api_side_effects_disabled(read_process_environment(args.pid))
        elif args.command == "verify-v2-storage-unit-roots":
            expected_roots = {
                "V2_DATA_DIR": args.data_dir,
                "V2_STORAGE_DIR": args.storage_dir,
                "V2_IMAGE_HISTORY_PATH": args.history_path,
                "V2_TASK_QUEUE_DB_PATH": args.queue_db,
            }
            result = verify_live_v2_storage_unit_roots(
                args.environment_file, expected_roots, args.allow_api_drop_in,
                args.allow_api_environment_file,
            )
        elif args.command == "verify-v2-api-runtime-contract":
            result = verify_v2_api_runtime_contract(args.environment_file, args.drop_in)
        elif args.command == "estimate-space":
            if args.reserve_bytes <= 0:
                raise CutoverBlocked("cutover_space_reserve_invalid")
            try:
                databases = [Path(value.decode()) for value in args.inventory_file.read_bytes().split(b"\0") if value]
            except OSError:
                raise CutoverBlocked("cutover_space_inventory_unreadable") from None
            result = {"status": "estimated", **estimate_cutover_space_from_files(databases, args.source, args.reserve_bytes)}
        elif args.command == "backup":
            result = create_backup(args.backup_dir, args.allowed_root, args.database, args.source)
        elif args.command == "verify-v2-write-access":
            result = verify_v2_write_access(args.directory, args.sqlite_db, args.append_file)
        else:
            result = restore_backup(args.manifest, args.allowed_root)
        print(json.dumps(result, separators=(",", ":")))
        return 0 if result.get("status") in {"idle", "backed_up", "restored", "estimated", "verified"} else 2
    except (CutoverBlocked, OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        # Keep output suitable for deployment logs and omit paths/payloads.
        reason = str(exc) if isinstance(exc, CutoverBlocked) else type(exc).__name__
        print(json.dumps({"status": "blocked", "reason": reason}, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
