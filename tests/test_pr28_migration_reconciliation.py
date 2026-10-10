"""Bounded migration-contract counterexamples, not a production importer.

All records are synthetic and all databases use pytest temporary paths. Neither
API startup hooks nor workers are started. These checks explain why migration
acceptance needs full payloads, derived indexes, and a WAL-consistent backup.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3

import pytest

from app.repositories.memory import MemoryRepository
from app.repositories.sqlite_json import connect
from app.schemas import GenerationJob, Session
from app.services.retention_settings import get_retention_settings, save_retention_settings


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/migrations/PR28-legacy-ram-state-cutover-plan.md"
AUDITED_TEXT_SUFFIXES = (".py", ".service", ".env.example")


def _candidate_source_blob(path: Path) -> str:
    """Hash declared text sources as LF Git blobs using current working-tree bytes.

    Only checkout CRLF is normalized; bare CR, BOM, whitespace, and all other
    bytes remain significant. Do not read a potentially stale Git index or
    require historical objects to be available in shallow/source-only checkouts.
    """
    assert path.name.endswith(AUDITED_TEXT_SUFFIXES), f"Undeclared text source: {path}"
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(f"blob {len(content)}\0".encode("ascii") + content).hexdigest()


def _canonical_digest(payload: object) -> str:
    """Test-only canonical encoding of an already approved JSON payload."""
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_v2_sqlite_map_module():
    # This helper is self-contained. Loading its file avoids mixing the two
    # products' identically named `app` packages or importing either API.
    path = ROOT / "custom_media_agent_2_0/app/repositories/sqlite_json.py"
    spec = importlib.util.spec_from_file_location("pr28_test_v2_sqlite_json", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_original_source_manifest_remains_the_frozen_38_file_history():
    original = PLAN.read_text(encoding="utf-8").split("## 2.1", 1)[0]
    rows = re.findall(r"^\| `([^`]+)` \| `([0-9a-f]{40})` \| `([0-9a-f]{40})` \|", original, re.M)
    assert len(rows) == 38
    assert len({path for path, _, _ in rows}) == 38
    digest = hashlib.sha256()
    for path, source, target in sorted(rows, key=lambda row: row[0].encode("utf-8")):
        digest.update(f"{path}\0{source}\0{target}\n".encode("utf-8"))
    assert digest.hexdigest() == "75dc6244e548a0b7e60ad4342eac9d61bcd2135563e0f89cf9e93946998542b8"


@pytest.mark.parametrize("suffix", AUDITED_TEXT_SUFFIXES)
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_candidate_text_source_blob_has_lf_crlf_parity(tmp_path, suffix, newline):
    path = tmp_path / f"source{suffix}"
    canonical = "# UTF-8 source: caf\u00e9\nvalue = 1\n".encode("utf-8")
    expected = hashlib.sha1(f"blob {len(canonical)}\0".encode("ascii") + canonical).hexdigest()
    path.write_bytes(canonical.replace(b"\n", newline))
    assert _candidate_source_blob(path) == expected


@pytest.mark.parametrize("changed", [
    b"value = 2\r\n",  # Real content change, even in a CRLF checkout.
    b"value = 1 \n",  # Trailing whitespace is significant.
    b"value = 1",  # A missing final newline is significant.
    b"value = 1\r",  # A bare CR is not a checkout CRLF line ending.
    b"\xef\xbb\xbfvalue = 1\n",  # A BOM is not removed.
])
def test_candidate_text_source_blob_detects_working_tree_mutations(tmp_path, changed):
    path = tmp_path / "source.py"
    path.write_bytes(b"value = 1\n")
    audited_blob = _candidate_source_blob(path)
    path.write_bytes(changed)
    assert _candidate_source_blob(path) != audited_blob


def test_candidate_source_blob_rejects_undeclared_file_types(tmp_path):
    path = tmp_path / "source.bin"
    path.write_bytes(b"binary\r\ncontent")
    with pytest.raises(AssertionError, match="Undeclared text source"):
        _candidate_source_blob(path)


def test_candidate_source_overlay_and_expanded_manifest_are_internally_consistent():
    document = PLAN.read_text(encoding="utf-8")
    original = re.findall(
        r"^\| `([^`]+)` \| `([0-9a-f]{40})` \| `([0-9a-f]{40})` \|",
        document.split("## 2.1", 1)[0], re.M,
    )
    overlay = re.findall(
        r"^\| `([^`]+)` \| `([0-9a-f]{40}|ABSENT)` \| `([0-9a-f]{40}|ABSENT)` \| `([0-9a-f]{40})` \|",
        document, re.M,
    )
    assert overlay
    assert len({row[0] for row in overlay}) == len(overlay)
    overlay_digest = hashlib.sha256()
    for row in sorted(overlay, key=lambda row: row[0].encode("utf-8")):
        overlay_digest.update(("\0".join(row) + "\n").encode("utf-8"))
    assert f"Candidate overlay: {len(overlay)} files; SHA-256 `{overlay_digest.hexdigest()}`" in document
    full = {path: (old, target) for path, old, target in original}
    for path, old, original_target, candidate in overlay:
        if path in full:
            assert full[path] == (old, original_target)
        full[path] = (old, candidate)
    expanded_digest = hashlib.sha256()
    for path in sorted(full, key=lambda path: path.encode("utf-8")):
        expanded_digest.update(f"{path}\0{full[path][0]}\0{full[path][1]}\n".encode("utf-8"))
        # No Git executable, index contents, or old objects in shallow CI.
        actual_blob = _candidate_source_blob(ROOT / path)
        assert actual_blob == full[path][1], f"Candidate source drifted after audit: {path}"
    assert f"Expanded old-to-candidate manifest: {len(full)} files; SHA-256 `{expanded_digest.hexdigest()}`" in document


@pytest.mark.parametrize("changed_field", ["prompt", "metadata", "ordered_references", "missing_field"])
def test_full_payload_digest_detects_changes_that_summary_reconciliation_misses(changed_field):
    source = {
        "id": "synthetic_job", "status": "ready", "owner_id": 41,
        "session_id": "synthetic_session", "output_ids": ["synthetic_output"],
        "prompt": "synthetic original prompt", "metadata": {"seed": 7},
        "ordered_references": ["reference_a", "reference_b"], "error": None,
    }
    target = copy.deepcopy(source)
    if changed_field == "prompt":
        target["prompt"] = "synthetic altered prompt"
    elif changed_field == "metadata":
        target["metadata"]["seed"] = 9
    elif changed_field == "ordered_references":
        target["ordered_references"].reverse()
    else:
        del target["error"]

    summary_fields = ("id", "status", "owner_id", "session_id", "output_ids")
    assert {key: source[key] for key in summary_fields} == {key: target[key] for key in summary_fields}
    assert _canonical_digest(source) != _canonical_digest(target)
    assert _canonical_digest(source) == _canonical_digest(dict(reversed(list(source.items()))))
    with pytest.raises(ValueError):
        _canonical_digest({"invalid": float("nan")})


@pytest.mark.parametrize("updated_at", ["2026-10-10T00:01:00Z", ""])
def test_v1_exact_payload_is_insufficient_without_derived_job_columns(tmp_path, updated_at):
    repo = MemoryRepository(database_path=tmp_path / "repository.sqlite3")
    session = Session(id="session_a", project_id="synthetic", created_at="2026-10-10T00:00:00Z", veyra_user_id=41)
    repo.save_session(session)
    job = GenerationJob(
        id="job_a", session_id=session.id, job_type="image", status="ready",
        trace_id="synthetic_trace", idempotency_key="synthetic_key",
        created_at=session.created_at, updated_at=updated_at,
    )
    connection = connect(repo.database_path)
    try:
        with connection:
            connection.execute(
                "INSERT INTO v1_records(namespace, record_key, payload) VALUES('jobs', ?, ?)",
                (job.id, job.model_dump_json()),
            )
        assert repo.get_job(job.id) == job
        assert _canonical_digest(repo.get_job(job.id).model_dump(mode="json")) == _canonical_digest(job.model_dump(mode="json"))
        assert repo.list_jobs(session_id=session.id) == []
        assert repo.get_job_by_idempotency_key(job.idempotency_key, session_id=session.id, owner_id=41) is None

        repo.save_job(job)
        assert repo.get_job(job.id) == job
        assert repo.list_jobs(job_type="image", session_id=session.id) == [job]
        assert repo.get_job_by_idempotency_key(job.idempotency_key, session_id=session.id, owner_id=41) == job
        assert repo.get_job_by_idempotency_key(job.idempotency_key, session_id="other_session", owner_id=41) is None
        assert repo.get_job_by_idempotency_key(job.idempotency_key, session_id=session.id, owner_id=99) is None
        assert repo.idempotency_index[job.idempotency_key] == job.id
        row = connection.execute(
            "SELECT session_id, job_type, sort_at, idempotency_key FROM v1_records WHERE namespace='jobs' AND record_key=?",
            (job.id,),
        ).fetchone()
        assert tuple(row) == (session.id, "image", updated_at or job.created_at, job.idempotency_key)
        assert [row[2] for row in connection.execute("PRAGMA index_info(v1_records_scoped_idem_idx)")] == [
            "namespace", "idempotency_key", "session_id",
        ]
    finally:
        connection.close()


def test_v2_exact_payload_is_insufficient_without_case_filter_columns(tmp_path):
    module = _load_v2_sqlite_map_module()
    db = tmp_path / "repository.sqlite3"
    cases = module.SQLiteJsonMap(
        db, "prompt_cases", validator=json.loads,
        index_fields=lambda value: {
            "provider_id": value["provider_id"], "active": int(value["is_active"]),
            "quality": value["quality_score"], "index_version": value["index_version"],
        },
    )
    source = [
        {"case_id": "case_low", "provider_id": "provider_a", "is_active": True, "quality_score": 0.2, "index_version": "v1"},
        {"case_id": "case_high", "provider_id": "provider_b", "is_active": True, "quality_score": 0.9, "index_version": "v2"},
        {"case_id": "case_hidden", "provider_id": "provider_a", "is_active": False, "quality_score": 1.0, "index_version": "v3"},
    ]
    connection = module.connect(db)
    try:
        with connection:
            connection.executemany(
                "INSERT INTO v2_records(namespace, record_key, payload) VALUES('prompt_cases', ?, ?)",
                [(case["case_id"], json.dumps(case)) for case in source],
            )
        assert [cases[case["case_id"]] for case in source] == source
        assert cases.list_values(active_only=True) == []
        assert cases.active_index_versions() == []
        for case in source:
            cases[case["case_id"]] = case
        assert [case["case_id"] for case in cases.list_values(active_only=True)] == ["case_high", "case_low"]
        assert [case["case_id"] for case in cases.list_values(active_only=False)] == ["case_hidden", "case_high", "case_low"]
        assert cases.active_index_versions() == ["v1", "v2"]
        selected = connection.execute(
            "SELECT record_key, provider_id, active, quality, index_version FROM v2_records "
            "WHERE namespace='prompt_cases' AND provider_id=? AND active=? AND index_version=?",
            ("provider_a", 1, "v1"),
        ).fetchall()
        assert [tuple(row) for row in selected] == [("case_low", "provider_a", 1, 0.2, "v1")]
        assert [row[2] for row in connection.execute("PRAGMA index_info(v2_records_case_sort_idx)")] == [
            "namespace", "active", "quality", "record_key",
        ]
    finally:
        connection.close()


def test_retention_policy_is_independent_data_with_silent_missing_or_invalid_defaults(tmp_path):
    missing = get_retention_settings(tmp_path)
    assert (missing["retention_days"], missing["delete_protected_data"], missing["persisted"]) == (30, False, False)
    saved = save_retention_settings(root=tmp_path, delete_protected_data=True, retention_days=91)
    assert get_retention_settings(tmp_path) == saved
    assert (saved["retention_days"], saved["delete_protected_data"], saved["persisted"]) == (91, True, True)
    (tmp_path / "retention_settings.json").write_text("invalid synthetic JSON", encoding="utf-8")
    invalid = get_retention_settings(tmp_path)
    assert (invalid["retention_days"], invalid["delete_protected_data"], invalid["persisted"]) == (30, False, True)


def test_sqlite_backup_includes_committed_wal_payload_and_restores_cleanly(tmp_path):
    source_path, backup_path = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    source = sqlite3.connect(source_path)
    backup = sqlite3.connect(backup_path)
    payload = {"id": "synthetic_record", "metadata": {"marker": "committed_in_wal"}}
    try:
        assert source.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        source.execute("PRAGMA wal_autocheckpoint=0")
        source.execute("CREATE TABLE records (record_key TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        source.commit()
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        source.execute("INSERT INTO records VALUES (?, ?)", (payload["id"], json.dumps(payload)))
        source.commit()
        assert source_path.with_name(source_path.name + "-wal").stat().st_size > 0
        source.backup(backup)
    finally:
        backup.close()
        source.close()
    with sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        result = json.loads(restored.execute("SELECT payload FROM records WHERE record_key=?", (payload["id"],)).fetchone()[0])
        assert _canonical_digest(result) == _canonical_digest(payload)
