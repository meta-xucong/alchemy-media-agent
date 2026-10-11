"""Rebuildable V1/Lab read projections; business truth stays in existing tables.

Tracking triggers are installed with the repository schema. They coalesce dirty
source keys in the same transaction as every authoritative write, including
dict-shaped compatibility writes. No providers or application startup are used.
"""
from __future__ import annotations

import heapq
import itertools
import json
import os
import sqlite3
import stat
import time
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.history_projection import job_history_item, positive_owner

VERSION = 1
BATCH = 128
REFRESH_SECONDS = 2.0
READ_ROUNDS = 3
GLOBAL_SCOPE = "global"
LAB_PROJECT = "alchemy_lab_rare_style_explorer"
V2_PROJECT = "alchemy_v2_bridge"


class HistoryIndexUnavailable(RuntimeError):
    """A sanitized, explicit index preparation/reconciliation failure."""


@dataclass
class HistoryReadMetrics:
    authority_decodes: int = 0
    job_projection_outputs: int = 0
    source_rows: int = 0
    winner_rows: int = 0
    page_decodes: int = 0
    filesystem_entries: int = 0
    file_stats: int = 0
    dirty_keys: int = 0
    refreshed_outputs: int = 0
    sqlite_vm_steps: int = 0


_METRICS: ContextVar[HistoryReadMetrics | None] = ContextVar("history_index_metrics", default=None)


def _metric(name: str, amount: int = 1) -> None:
    metrics = _METRICS.get()
    if metrics is not None:
        setattr(metrics, name, getattr(metrics, name) + amount)


def _decode(payload: str) -> dict:
    _metric("authority_decodes")
    return json.loads(payload)


def _epoch(value: Any) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        return 0.0


def _lab(record: dict) -> bool:
    source = str(record.get("source_app") or "")
    return (source == LAB_PROJECT or source.startswith("alchemy_lab_")
            or source.startswith("alchemy_lab:")
            or str(record.get("idempotency_key") or "").startswith("lab:")
            or bool(record.get("alchemy_lab")))


def _non_v1(record: dict) -> bool:
    return (_lab(record) or record.get("source_app") == V2_PROJECT
            or str(record.get("idempotency_key") or "").startswith("v2:"))


def install_tracking(connection: sqlite3.Connection) -> None:
    """Only additive derived schema; never executescript/commit caller's work."""
    existing = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_read_%'"
    )}
    required = {"v1_read_sources", "v1_read_winners", "v1_read_counts", "v1_read_dirty", "v1_read_state"}
    incomplete = bool("v1_read_state" in existing and not required.issubset(existing))
    statements = [
        """CREATE TABLE IF NOT EXISTS v1_read_state(
            state_key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS v1_read_dirty(
            kind TEXT NOT NULL, source_key TEXT NOT NULL, PRIMARY KEY(kind,source_key))""",
        "CREATE INDEX IF NOT EXISTS v1_read_dirty_sources_idx ON v1_read_dirty(kind,source_key) WHERE kind!='resolve'",
        """CREATE TABLE IF NOT EXISTS v1_read_sources(
            kind TEXT NOT NULL, source_key TEXT NOT NULL, output_id TEXT NOT NULL,
            job_id TEXT NOT NULL DEFAULT '', session_id TEXT NOT NULL DEFAULT '',
            owner_id INTEGER, non_v1 INTEGER NOT NULL DEFAULT 0,
            is_lab INTEGER NOT NULL DEFAULT 0, lab_owner INTEGER,
            owner_conflict INTEGER NOT NULL DEFAULT 0,
            eligible INTEGER NOT NULL DEFAULT 0, is_mock INTEGER NOT NULL DEFAULT 0,
            sort_epoch REAL NOT NULL DEFAULT 0, sort_text TEXT NOT NULL DEFAULT '',
            job_sort TEXT NOT NULL DEFAULT '', sequence INTEGER NOT NULL DEFAULT 0,
            position INTEGER NOT NULL DEFAULT 0, file_path TEXT NOT NULL DEFAULT '',
            file_exists INTEGER NOT NULL DEFAULT 0, file_regular INTEGER NOT NULL DEFAULT 0,
            payload TEXT, PRIMARY KEY(kind,source_key))""",
        "CREATE INDEX IF NOT EXISTS v1_read_sources_output_idx ON v1_read_sources(output_id)",
        "CREATE INDEX IF NOT EXISTS v1_read_sources_job_idx ON v1_read_sources(kind,job_id)",
        "CREATE INDEX IF NOT EXISTS v1_read_sources_session_idx ON v1_read_sources(kind,session_id)",
        "CREATE INDEX IF NOT EXISTS v1_read_sources_path_idx ON v1_read_sources(file_path)",
        "CREATE INDEX IF NOT EXISTS v1_read_sources_kind_path_idx ON v1_read_sources(kind,file_path)",
        "CREATE INDEX IF NOT EXISTS v1_read_sources_sequence_idx ON v1_read_sources(kind,sequence)",
        """CREATE TABLE IF NOT EXISTS v1_read_winners(
            surface TEXT NOT NULL, scope TEXT NOT NULL, output_id TEXT NOT NULL,
            kind TEXT NOT NULL, source_key TEXT NOT NULL, owner_id INTEGER NOT NULL,
            sort_epoch REAL NOT NULL, sort_text TEXT NOT NULL, job_id TEXT NOT NULL,
            sequence INTEGER NOT NULL, is_mock INTEGER NOT NULL,
            PRIMARY KEY(surface,scope,output_id))""",
        "CREATE INDEX IF NOT EXISTS v1_read_v1_page_idx ON v1_read_winners(surface,scope,sort_epoch DESC,job_id DESC,output_id DESC)",
        "CREATE INDEX IF NOT EXISTS v1_read_winners_output_idx ON v1_read_winners(output_id)",
        "CREATE INDEX IF NOT EXISTS v1_read_v1_owner_idx ON v1_read_winners(surface,scope,owner_id,sort_epoch DESC,job_id DESC,output_id DESC)",
        "CREATE INDEX IF NOT EXISTS v1_read_lab_page_idx ON v1_read_winners(surface,scope,sort_text DESC,sort_epoch DESC,sequence ASC)",
        "CREATE INDEX IF NOT EXISTS v1_read_lab_owner_idx ON v1_read_winners(surface,scope,owner_id,sort_text DESC,sort_epoch DESC,sequence ASC)",
        "CREATE INDEX IF NOT EXISTS v1_read_lab_real_page_idx ON v1_read_winners(surface,scope,is_mock,sort_text DESC,sort_epoch DESC,sequence ASC)",
        "CREATE INDEX IF NOT EXISTS v1_read_lab_real_owner_idx ON v1_read_winners(surface,scope,is_mock,owner_id,sort_text DESC,sort_epoch DESC,sequence ASC)",
        """CREATE TABLE IF NOT EXISTS v1_read_counts(
            surface TEXT NOT NULL, scope TEXT NOT NULL, owner_id INTEGER NOT NULL,
            non_mock INTEGER NOT NULL, total INTEGER NOT NULL CHECK(total>=0),
            PRIMARY KEY(surface,scope,owner_id,non_mock))""",
    ]
    for statement in statements:
        connection.execute(statement)
    if incomplete:
        connection.execute("INSERT OR REPLACE INTO v1_read_state VALUES('blocked','schema_incomplete')")
    tracked = "('jobs','outputs','sessions','output_delete_claims')"
    for event, reference in (("INSERT", "NEW"), ("DELETE", "OLD")):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS v1_read_records_{event.lower()}
            AFTER {event} ON v1_records WHEN {reference}.namespace IN {tracked}
            BEGIN INSERT INTO v1_read_dirty(kind,source_key)
              SELECT {reference}.namespace,{reference}.record_key WHERE NOT EXISTS(
                SELECT 1 FROM v1_read_dirty WHERE kind={reference}.namespace AND source_key={reference}.record_key
              ); END""")
    connection.execute(f"""CREATE TRIGGER IF NOT EXISTS v1_read_records_update
        AFTER UPDATE ON v1_records
        BEGIN
          INSERT INTO v1_read_dirty SELECT OLD.namespace,OLD.record_key WHERE OLD.namespace IN {tracked}
            AND NOT EXISTS(SELECT 1 FROM v1_read_dirty WHERE kind=OLD.namespace AND source_key=OLD.record_key);
          INSERT INTO v1_read_dirty SELECT NEW.namespace,NEW.record_key WHERE NEW.namespace IN {tracked}
            AND NOT EXISTS(SELECT 1 FROM v1_read_dirty WHERE kind=NEW.namespace AND source_key=NEW.record_key);
        END""")
    install_manifest_tracking(connection)


def install_manifest_tracking(connection: sqlite3.Connection) -> None:
    for table in ("v1_history_records", "v1_history_owner_evidence"):
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            continue
        for event, reference in (("INSERT", "NEW"), ("UPDATE", "NEW"), ("DELETE", "OLD")):
            connection.execute(f"""CREATE TRIGGER IF NOT EXISTS v1_read_{table}_{event.lower()}
                AFTER {event} ON {table} BEGIN
                INSERT INTO v1_read_dirty SELECT 'history',{reference}.output_id
                  WHERE NOT EXISTS(SELECT 1 FROM v1_read_dirty WHERE kind='history' AND source_key={reference}.output_id); END""")


def mark_file_changed(store, path: Path) -> None:
    from app.repositories.sqlite_json import connect
    connection = connect(store.root / "repository.sqlite3")
    try:
        with connection:
            connection.execute("INSERT OR IGNORE INTO v1_read_dirty VALUES('file',?)", (str(path.resolve()),))
    finally:
        connection.close()


def _queue_output(connection, output_id: str) -> None:
    connection.execute("INSERT OR IGNORE INTO v1_read_dirty VALUES('resolve',?)", (output_id,))


def _put_source(connection, **values) -> None:
    _metric("source_rows")
    names = list(values)
    connection.execute(
        "INSERT OR REPLACE INTO v1_read_sources(" + ",".join(names) + ") VALUES("
        + ",".join("?" for _ in names) + ")", tuple(values.values()),
    )
    _queue_output(connection, values["output_id"])


def _refresh_job(connection, store, job_id: str, row=None) -> None:
    from app.schemas import GenerationJob, Session
    connection.execute("INSERT OR IGNORE INTO v1_read_dirty SELECT 'resolve',output_id FROM v1_read_sources WHERE kind='job' AND job_id=?", (job_id,))
    connection.execute("DELETE FROM v1_read_sources WHERE kind='job' AND job_id=?", (job_id,))
    row = row or connection.execute("SELECT rowid,payload FROM v1_records WHERE namespace='jobs' AND record_key=?", (job_id,)).fetchone()
    if row is None:
        return
    _metric("authority_decodes")
    job = GenerationJob.model_validate_json(row[1])
    if job.job_type != "image":
        return
    session_row = connection.execute("SELECT payload FROM v1_records WHERE namespace='sessions' AND record_key=?", (job.session_id,)).fetchone()
    if session_row:
        _metric("authority_decodes")
        project = Session.model_validate_json(session_row[0]).project_id
    else:
        project = None
    non_v1 = str(job.idempotency_key or "").startswith(("v2:", "lab:")) or project in {V2_PROJECT, LAB_PROJECT}
    for position, output in enumerate(job.outputs):
        eligible = output.format in {"png", "jpeg", "webp"}
        payload = None
        if eligible and not non_v1:
            payload = job_history_item(job, output, store).model_dump_json()
            _metric("job_projection_outputs")
        _put_source(connection, kind="job", source_key=json.dumps([job.id, position]),
                    output_id=output.id, job_id=job.id, session_id=job.session_id or "",
                    owner_id=positive_owner((output.metadata or {}).get("veyra_user_id")),
                    non_v1=int(non_v1), eligible=int(eligible),
                    sort_epoch=_epoch(job.created_at or job.updated_at),
                    sort_text=job.created_at or job.updated_at or "",
                    job_sort=job.updated_at or job.created_at or "", sequence=int(row[0]),
                    position=position, payload=payload,
                    file_path=str(store.output_path(job_id=job.id, output_id=output.id, output_format=output.format).resolve()))


def _checked_path(store, path: Path) -> Path:
    root = store.generated_root.resolve()
    lexical = Path(os.path.abspath(path))
    configured_root = Path(os.path.abspath(store.generated_root))
    # Reject obvious foreign paths before resolving/statting their components.
    if root not in lexical.parents and configured_root not in lexical.parents:
        raise HistoryIndexUnavailable("History file inventory requires an explicit rebuild.")
    resolved = lexical.resolve()
    if root not in resolved.parents:
        raise HistoryIndexUnavailable("History file inventory contains an unsafe path.")
    return resolved


def _presence(path: Path, *, store=None) -> tuple[bool, bool]:
    if store is not None:
        path = _checked_path(store, path)
    _metric("file_stats")
    try:
        mode = path.stat().st_mode
        return True, stat.S_ISREG(mode)
    except FileNotFoundError:
        return False, False


def _refresh_manifest(connection, store, output_id: str, row=None) -> None:
    _queue_output(connection, output_id)
    connection.execute("DELETE FROM v1_read_sources WHERE kind='history' AND source_key=?", (output_id,))
    row = row or connection.execute("SELECT sequence,payload FROM v1_history_records WHERE output_id=?", (output_id,)).fetchone()
    if row is None:
        return
    record = _decode(row[1])
    path = store.output_path(job_id=record.get("job_id", ""), output_id=output_id,
                             output_format=record.get("format") or "png")
    exists, regular = _presence(path, store=store)
    metadata = record.get("alchemy_lab") if isinstance(record.get("alchemy_lab"), dict) else {}
    _put_source(connection, kind="history", source_key=output_id, output_id=output_id,
                job_id=record.get("job_id") or "", session_id=record.get("session_id") or "",
                owner_id=positive_owner(record.get("veyra_user_id")),
                owner_conflict=int(bool(record.get("_veyra_owner_conflict"))),
                non_v1=int(_non_v1(record)), is_lab=int(_lab(record)),
                lab_owner=positive_owner(record.get("veyra_user_id") or metadata.get("veyra_user_id")),
                eligible=int(record.get("format") in {"png", "jpeg", "webp"} and regular),
                is_mock=int(str(record.get("provider") or "").strip().lower() in {"mock", "mock_image"}
                            or str(record.get("model") or "").strip().lower().startswith("mock-")),
                sort_epoch=_epoch(record.get("created_at") or record.get("updated_at")),
                sort_text=record.get("created_at") or record.get("updated_at") or "",
                sequence=int(row[0]), file_path=str(path.resolve()),
                file_exists=int(exists), file_regular=int(regular))


def _refresh_file(connection, store, path: Path) -> None:
    from app.storage.local import _format_from_suffix, _looks_like_generated_job_id, _looks_like_generated_output_id
    path = _checked_path(store, path)
    key = str(path)
    old = connection.execute("SELECT output_id,sequence FROM v1_read_sources WHERE kind='file' AND source_key=?", (key,)).fetchone()
    if old:
        _queue_output(connection, old[0])
    connection.execute("DELETE FROM v1_read_sources WHERE kind='file' AND source_key=?", (key,))
    # Known manifest paths can have legacy names excluded from file recovery.
    for row in connection.execute("SELECT source_key FROM v1_read_sources WHERE kind='history' AND file_path=?", (key,)):
        connection.execute("INSERT OR IGNORE INTO v1_read_dirty VALUES('history',?)", (row[0],))
    root = store.generated_root.resolve()
    if path.parent.parent != root or path.name.startswith("."):
        return
    output_format = _format_from_suffix(path.suffix)
    if output_format not in {"png", "jpeg", "webp", "mp4"}:
        return
    recovery_eligible = (output_format in {"png", "jpeg", "webp"}
                         and _looks_like_generated_job_id(path.parent.name)
                         and _looks_like_generated_output_id(path.stem))
    _metric("file_stats")
    try:
        info = path.stat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode):
        return
    sequence = int(old[1]) if old else int(connection.execute(
        "SELECT COALESCE(MAX(sequence),0)+1 FROM v1_read_sources WHERE kind='file'"
    ).fetchone()[0])
    timestamp = datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()
    payload = {"id": path.stem, "job_id": path.parent.name,
               "url": f"/v1/outputs/{path.stem}/download", "thumbnail_url": store.thumbnail_url(path.stem),
               "preview_url": store.preview_url(path.stem), "format": output_format,
               "provider": "local_filesystem", "model": "recovered-output",
               "prompt": "历史图片（从本地输出目录恢复，原始提示词不可用）",
               "final_prompt": "历史图片（从本地输出目录恢复，原始提示词不可用）",
               "created_at": timestamp, "updated_at": timestamp, "source": "filesystem"}
    _put_source(connection, kind="file", source_key=key, output_id=path.stem, job_id=path.parent.name,
                eligible=int(recovery_eligible), sort_epoch=_epoch(timestamp), sort_text=timestamp, sequence=sequence,
                file_path=key, file_exists=1, file_regular=1,
                payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _owner(connection, output_id: str, sources) -> tuple[int | None, bool]:
    from app.schemas import GenerationOutput

    canonical = connection.execute("SELECT payload FROM v1_records WHERE namespace='outputs' AND record_key=?", (output_id,)).fetchone()
    if canonical:
        _metric("authority_decodes")
        output = GenerationOutput.model_validate_json(canonical[0])
        owner = positive_owner((output.metadata or {}).get("veyra_user_id"))
        if owner is not None:
            return owner, False
    history = next((row for row in sources if row["kind"] == "history"), None)
    if history is not None:
        evidence = connection.execute("SELECT owner_id,owner_conflict FROM v1_history_owner_evidence WHERE output_id=?", (output_id,)).fetchone()
        if history["owner_conflict"] or (evidence is not None and evidence[1]):
            return None, True
        owner = positive_owner(evidence[0]) if evidence is not None else positive_owner(history["owner_id"])
        if owner is not None:
            return owner, False
    owners = {row["owner_id"] for row in sources if row["kind"] == "job" and row["owner_id"] is not None}
    if len(owners) > 1:
        return None, True
    if owners:
        return next(iter(owners)), False
    claim = connection.execute("SELECT payload FROM v1_records WHERE namespace='output_delete_claims' AND record_key=?", (output_id,)).fetchone()
    return (positive_owner(_decode(claim[0]).get("owner_id")) if claim else None), False


def _bucket_keys(row):
    for owner in (-1, int(row["owner_id"])):
        yield row["surface"], row["scope"], owner, 0
        if row["surface"] == "lab" and not row["is_mock"]:
            yield row["surface"], row["scope"], owner, 1


def _remove_winners(connection, output_id: str) -> None:
    for row in connection.execute("SELECT * FROM v1_read_winners WHERE output_id=?", (output_id,)):
        for key in _bucket_keys(row):
            changed = connection.execute("UPDATE v1_read_counts SET total=total-1 WHERE surface=? AND scope=? AND owner_id=? AND non_mock=? AND total>0", key).rowcount
            if changed != 1:
                raise HistoryIndexUnavailable("History count state requires an explicit rebuild.")
            connection.execute("DELETE FROM v1_read_counts WHERE surface=? AND scope=? AND owner_id=? AND non_mock=? AND total=0", key)
    connection.execute("DELETE FROM v1_read_winners WHERE output_id=?", (output_id,))


def _winner(connection, row, *, surface, scope, owner_id) -> None:
    data = dict(surface=surface, scope=scope, output_id=row["output_id"], kind=row["kind"],
                source_key=row["source_key"], owner_id=owner_id or 0, sort_epoch=row["sort_epoch"],
                sort_text=row["sort_text"], job_id=row["job_id"], sequence=row["sequence"], is_mock=row["is_mock"])
    connection.execute("INSERT INTO v1_read_winners(" + ",".join(data) + ") VALUES(" + ",".join("?" for _ in data) + ")", tuple(data.values()))
    for key in _bucket_keys(data):
        connection.execute("INSERT INTO v1_read_counts VALUES(?,?,?,?,1) ON CONFLICT(surface,scope,owner_id,non_mock) DO UPDATE SET total=total+1", key)


def _resolve(connection, output_id: str) -> None:
    _metric("refreshed_outputs")
    _remove_winners(connection, output_id)
    sources = connection.execute("SELECT * FROM v1_read_sources WHERE output_id=?", (output_id,)).fetchall()
    _metric("source_rows", len(sources))
    owner, conflict = _owner(connection, output_id, sources)
    if conflict:
        return
    for row in sources:
        if row["kind"] == "history" and row["is_lab"] and row["file_exists"]:
            _winner(connection, row, surface="lab", scope=GLOBAL_SCOPE,
                    owner_id=owner if owner is not None else row["lab_owner"])
    if any(row["non_v1"] for row in sources):
        return
    has_claim = connection.execute("SELECT 1 FROM v1_records WHERE namespace='output_delete_claims' AND record_key=?", (output_id,)).fetchone() is not None
    candidates = [row for row in sources if row["eligible"] and not (has_claim and row["kind"] == "file")]
    # Stable traversal tie order, then source priority/owner-match precedence.
    jobs = sorted((row for row in candidates if row["kind"] == "job"), key=lambda row: (row["sequence"], row["position"]))
    jobs.sort(key=lambda row: row["job_sort"], reverse=True)
    history = [row for row in candidates if row["kind"] == "history"]
    files = sorted((row for row in candidates if row["kind"] == "file"), key=lambda row: (-row["sort_epoch"], row["sequence"]))
    ordered = jobs + history + files
    scopes = [GLOBAL_SCOPE] + ["session:" + session for session in sorted({row["session_id"] for row in ordered if row["kind"] != "file" and row["session_id"]})]
    for scope in scopes:
        available = [row for row in ordered if scope == GLOBAL_SCOPE or (row["kind"] != "file" and "session:" + row["session_id"] == scope)]
        if not available:
            continue
        best = min(available, key=lambda row: ({"job": 0, "history": 1, "file": 2}[row["kind"]], -int(owner is not None and row["owner_id"] == owner)))
        _winner(connection, best, surface="v1", scope=scope, owner_id=owner)


def _drain(connection, store, *, deadline: float | None) -> bool:
    while True:
        rows = connection.execute("SELECT kind,source_key FROM v1_read_dirty WHERE kind!='resolve' ORDER BY kind,source_key LIMIT ?", (BATCH,)).fetchall()
        if not rows:
            rows = connection.execute("SELECT kind,source_key FROM v1_read_dirty ORDER BY kind,source_key LIMIT ?", (BATCH,)).fetchall()
        if not rows:
            return True
        for kind, key in rows:
            connection.execute("DELETE FROM v1_read_dirty WHERE kind=? AND source_key=?", (kind, key))
            _metric("dirty_keys")
            if kind == "jobs":
                _refresh_job(connection, store, key)
            elif kind == "sessions":
                connection.execute("INSERT OR IGNORE INTO v1_read_dirty SELECT 'jobs',record_key FROM v1_records WHERE namespace='jobs' AND session_id=?", (key,))
                connection.execute("INSERT OR IGNORE INTO v1_read_dirty SELECT 'jobs',job_id FROM v1_read_sources WHERE kind='job' AND session_id=?", (key,))
            elif kind == "history":
                _refresh_manifest(connection, store, key)
            elif kind == "file":
                _refresh_file(connection, store, Path(key))
            elif kind in {"outputs", "output_delete_claims"}:
                _queue_output(connection, key)
            elif kind == "resolve":
                _resolve(connection, key)
            else:
                raise HistoryIndexUnavailable("Unknown history change requires an explicit rebuild.")
        if deadline is not None and time.monotonic() >= deadline:
            return False


def _build(connection, store) -> None:
    for table in ("v1_read_winners", "v1_read_counts", "v1_read_sources", "v1_read_dirty"):
        connection.execute(f"DELETE FROM {table}")
    for row in connection.execute("SELECT rowid,payload,record_key FROM v1_records WHERE namespace='jobs' ORDER BY rowid"):
        _refresh_job(connection, store, row[2], row)
    for row in connection.execute("SELECT sequence,payload,output_id FROM v1_history_records ORDER BY sequence"):
        _refresh_manifest(connection, store, row[2], row)
    for path in store.generated_root.glob("*/*"):
        _metric("filesystem_entries")
        _refresh_file(connection, store, path)
    _drain(connection, store, deadline=None)
    connection.execute("INSERT OR REPLACE INTO v1_read_state VALUES('storage_root',?)", (str(store.root.resolve()),))
    connection.execute("INSERT OR REPLACE INTO v1_read_state VALUES('version',?)", (str(VERSION),))
    connection.execute("DELETE FROM v1_read_state WHERE state_key='blocked'")


def prepare_history_index(store, *, rebuild: bool = False) -> None:
    """Explicit maintenance preparation; first-use invokes the same atomic build."""
    from app.repositories.sqlite_json import connect
    store._ensure_history_index()
    connection = connect(store.root / "repository.sqlite3")
    try:
        connection.execute("BEGIN IMMEDIATE")
        if rebuild:
            install_tracking(connection)
        _check_schema(connection, store=store, check_marker=not rebuild)
        version = connection.execute("SELECT value FROM v1_read_state WHERE state_key='version'").fetchone()
        blocked = connection.execute("SELECT 1 FROM v1_read_state WHERE state_key='blocked'").fetchone()
        if blocked and not rebuild:
            raise HistoryIndexUnavailable("History index requires an explicit rebuild.")
        if version is not None and version[0] != str(VERSION) and not rebuild:
            raise HistoryIndexUnavailable("History index version requires an explicit rebuild.")
        if rebuild or version is None:
            _build(connection, store)
        else:
            _drain(connection, store, deadline=time.monotonic() + REFRESH_SECONDS)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def reconcile_history_files(store) -> None:
    """Explicit, full inventory observation; never called by an unchanged read."""
    from app.repositories.sqlite_json import connect
    prepare_history_index(store)
    connection = connect(store.root / "repository.sqlite3")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TEMP TABLE observed_files(path TEXT PRIMARY KEY)")
        for path in store.generated_root.glob("*/*"):
            _metric("filesystem_entries")
            key = str(path.resolve())
            connection.execute("INSERT OR IGNORE INTO observed_files VALUES(?)", (key,))
            _refresh_file(connection, store, path)
        # Stream persistent keys; the coalesced queue owns pending work.
        connection.execute("INSERT OR IGNORE INTO v1_read_dirty SELECT 'file',source_key FROM v1_read_sources WHERE kind='file' AND source_key NOT IN (SELECT path FROM observed_files)")
        connection.execute("INSERT OR IGNORE INTO v1_read_dirty SELECT 'history',output_id FROM v1_history_records")
        _drain(connection, store, deadline=None)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _page_rows(connection, *, surface, scope, owner_id, all_owners, include_mock, limit, offset, output_id=None):
    clauses = "surface=? AND scope=?"
    args: list[Any] = [surface, scope]
    if output_id is not None:
        clauses += " AND output_id=?"
        args.append(output_id)
    if surface == "lab" and not include_mock:
        clauses += " AND is_mock=0"
    order = "sort_epoch DESC,job_id DESC,output_id DESC" if surface == "v1" else "sort_text DESC,sort_epoch DESC,sequence ASC"
    owners = [-1] if all_owners else ([owner_id or 0, 0] if surface == "v1" and owner_id else [owner_id or 0])
    owners = list(dict.fromkeys(owners))
    total = 0
    non_mock = int(surface == "lab" and not include_mock)
    for owner in owners:
        if output_id is not None:
            owner_clause = "" if owner == -1 else " AND owner_id=?"
            total += int(connection.execute("SELECT COUNT(*) FROM v1_read_winners WHERE " + clauses + owner_clause,
                                            args if owner == -1 else [*args, owner]).fetchone()[0])
            continue
        count = connection.execute("SELECT total FROM v1_read_counts WHERE surface=? AND scope=? AND owner_id=? AND non_mock=?", (surface, scope, owner, non_mock)).fetchone()
        if count is None:
            owner_clause = "" if owner == -1 else " AND owner_id=?"
            if connection.execute("SELECT 1 FROM v1_read_winners WHERE " + clauses + owner_clause + " LIMIT 1",
                                  args if owner == -1 else [*args, owner]).fetchone():
                raise HistoryIndexUnavailable("History count state requires an explicit rebuild.")
        total += int(count[0]) if count else 0
    def stream(owner):
        sql = "SELECT * FROM v1_read_winners WHERE " + clauses
        params = list(args)
        if owner != -1:
            sql += " AND owner_id=?"
            params.append(owner)
        cursor = connection.execute(sql + " ORDER BY " + order + " LIMIT ?", (*params, offset + limit))
        try:
            for row in cursor:
                _metric("winner_rows")
                yield row
        finally:
            cursor.close()
    streams = [stream(owner) for owner in owners]
    if len(streams) == 1:
        merged = streams[0]
    else:
        merged = heapq.merge(*streams, key=lambda row: (row["sort_epoch"], row["job_id"], row["output_id"]), reverse=True)
    try:
        rows = list(itertools.islice(merged, offset, offset + limit))
    finally:
        for iterator in streams:
            iterator.close()
    if len(rows) != min(limit, max(0, total - offset)):
        raise HistoryIndexUnavailable("History count state requires an explicit rebuild.")
    return rows, total


def _check_schema(connection, *, store=None, check_marker=True) -> None:
    names = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('v1_read_sources','v1_read_winners','v1_read_counts','v1_read_dirty','v1_read_state')"
    )}
    if len(names) != 5:
        raise HistoryIndexUnavailable("History index schema requires an explicit rebuild.")
    version = connection.execute("SELECT 1 FROM v1_read_state WHERE state_key='version'").fetchone()
    if check_marker and version is not None and store is not None:
        binding = connection.execute("SELECT value FROM v1_read_state WHERE state_key='storage_root'").fetchone()
        if binding is None or Path(binding[0]) != store.root.resolve():
            raise HistoryIndexUnavailable("History index storage root changed; explicitly rebuild the index.")
    if check_marker and version is None:
        if (connection.execute("SELECT 1 FROM v1_read_sources LIMIT 1").fetchone()
                or connection.execute("SELECT 1 FROM v1_read_winners LIMIT 1").fetchone()
                or connection.execute("SELECT 1 FROM v1_read_counts LIMIT 1").fetchone()):
            raise HistoryIndexUnavailable("History index marker requires an explicit rebuild.")


@contextmanager
def _clean_snapshot(store):
    """A bounded keyed-reader entry point sharing the history readiness rules."""
    from app.repositories.sqlite_json import connect

    store._ensure_history_index()
    for _round in range(READ_ROUNDS):
        connection = connect(store.root / "repository.sqlite3")
        try:
            connection.execute("BEGIN")
            _check_schema(connection, store=store)
            version = connection.execute("SELECT value FROM v1_read_state WHERE state_key='version'").fetchone()
            if connection.execute("SELECT 1 FROM v1_read_state WHERE state_key='blocked'").fetchone():
                raise HistoryIndexUnavailable("History index requires an explicit rebuild.")
            if version is not None and version[0] != str(VERSION):
                raise HistoryIndexUnavailable("History index version requires an explicit rebuild.")
            if version is not None and not connection.execute("SELECT 1 FROM v1_read_dirty LIMIT 1").fetchone():
                yield connection
                return
        finally:
            connection.close()
        prepare_history_index(store)
    raise HistoryIndexUnavailable("History is changing; retry or prepare the index.")


def lookup_output_owner(store, output_id: str) -> tuple[int | None, bool]:
    """Global owner evidence for legacy thumbnails, without an all-Job scan."""
    with _clean_snapshot(store) as connection:
        sources = connection.execute(
            "SELECT kind,owner_id,owner_conflict FROM v1_read_sources WHERE output_id=?", (output_id,),
        ).fetchall()
        return _owner(connection, output_id, sources)


def lookup_output_file(store, output_id: str) -> tuple[tuple[Path, str, str] | None, bool]:
    """Indexed image path candidates; known missing media never scans the tree.

    Unknown direct-ID/video requests can retain their separate legacy fallback.
    Presence repair is coalesced, and per-ID duplicate fanout is capped here.
    """
    from app.storage.local import _format_from_suffix

    missing = []
    checked: set[Path] = set()
    result = None
    with _clean_snapshot(store) as connection:
        rows = connection.execute(
            "SELECT kind,file_path,sequence FROM v1_read_sources WHERE output_id=? AND file_path!='' "
            "ORDER BY CASE WHEN kind='file' THEN 0 ELSE 1 END,sequence LIMIT ?", (output_id, BATCH + 1),
        ).fetchall()
        known = bool(rows)
        for row in rows[:BATCH]:
            path = Path(row["file_path"])
            # Legacy metadata can declare .png while the extant file is .jpg.
            # Probe only known directories and a fixed recognized suffix set.
            for candidate in [path, *(path.with_suffix("." + suffix) for suffix in ("png", "jpg", "jpeg", "webp", "mp4"))]:
                if candidate in checked:
                    continue
                checked.add(candidate)
                _exists, regular = _presence(candidate, store=store)
                output_format = _format_from_suffix(candidate.suffix)
                if regular and output_format:
                    result = candidate, output_format, candidate.parent.name
                    break
            if result:
                break
            missing.append(path)
    for path in dict.fromkeys(missing):
        mark_file_changed(store, path)
    if result is None and len(rows) > BATCH:
        raise HistoryIndexUnavailable("Output file inventory needs reconciliation.")
    return result, known


def read_history_page(store, *, surface: str, session_id: str | None = None,
                      owner_id: int | None = None, all_owners: bool = False,
                      include_mock: bool = False, limit: int = 50, offset: int = 0,
                      metrics: HistoryReadMetrics | None = None,
                      output_id: str | None = None) -> tuple[list[dict], int]:
    """Read a complete inventory snapshot, with bounded catch-up/page repair."""
    from app.repositories.sqlite_json import connect
    token = _METRICS.set(metrics)
    try:
        # Import state is independent of derived-ready: a formerly missing
        # legacy source must still be validated if it later appears.
        store._ensure_history_index()
        for _round in range(READ_ROUNDS):
            connection = connect(store.root / "repository.sqlite3")
            repair_paths: list[str] = []
            try:
                if metrics is not None:
                    connection.set_progress_handler(lambda: (_metric("sqlite_vm_steps", 100), 0)[1], 100)
                connection.execute("BEGIN")
                _check_schema(connection, store=store)
                version = connection.execute("SELECT value FROM v1_read_state WHERE state_key='version'").fetchone()
                if connection.execute("SELECT 1 FROM v1_read_state WHERE state_key='blocked'").fetchone():
                    raise HistoryIndexUnavailable("History index requires an explicit rebuild.")
                if version is not None and version[0] != str(VERSION):
                    raise HistoryIndexUnavailable("History index version requires an explicit rebuild.")
                if version is None or connection.execute("SELECT 1 FROM v1_read_dirty LIMIT 1").fetchone():
                    connection.rollback()
                    connection.close()
                    connection = None
                    prepare_history_index(store)
                    continue
                scope = "session:" + session_id if surface == "v1" and session_id else GLOBAL_SCOPE
                rows, total = _page_rows(connection, surface=surface, scope=scope,
                                         owner_id=owner_id, all_owners=all_owners,
                                         include_mock=include_mock, limit=min(200, max(0, limit)), offset=max(0, offset), output_id=output_id)
                records = []
                for row in rows:
                    source = connection.execute("SELECT * FROM v1_read_sources WHERE kind=? AND source_key=?", (row["kind"], row["source_key"])).fetchone()
                    if source is None:
                        raise HistoryIndexUnavailable("History source index requires an explicit rebuild.")
                    if source["kind"] != "job":
                        exists, regular = _presence(Path(source["file_path"]), store=store)
                        if not (exists if surface == "lab" else regular):
                            repair_paths.append(source["file_path"])
                            continue
                    if source["kind"] == "history":
                        raw = connection.execute("SELECT payload FROM v1_history_records WHERE output_id=?", (row["output_id"],)).fetchone()
                        if raw is None:
                            raise HistoryIndexUnavailable("History manifest index requires an explicit rebuild.")
                        record = json.loads(raw[0])
                        record.update(source="manifest", thumbnail_url=store.thumbnail_url(row["output_id"]),
                                      preview_url=store.preview_url(row["output_id"]), url=f"/v1/outputs/{row['output_id']}/download")
                    else:
                        if source["payload"] is None:
                            raise HistoryIndexUnavailable("History projection requires an explicit rebuild.")
                        record = json.loads(source["payload"])
                    _metric("page_decodes")
                    record["veyra_user_id"] = positive_owner(row["owner_id"])
                    records.append(record)
                connection.commit()
                if not repair_paths:
                    return records, total
            finally:
                if connection is not None:
                    connection.close()
            for path in repair_paths:
                mark_file_changed(store, Path(path))
        raise HistoryIndexUnavailable("History is changing or file inventory needs reconciliation; retry or prepare the index.")
    finally:
        _METRICS.reset(token)
