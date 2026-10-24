"""Durable publication fence for newly materialized V1/Lab images.

Reservations are business security evidence, not rebuildable history state.
They precede image bytes and survive failed generation and output deletion.
Neither this module nor its legacy fallback infers ownership from a Session.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.repositories.sqlite_json import connect
from app.services.history_projection import positive_owner


PUBLICATION_NAMESPACE = "output_publications"


def reserve_output(database_path: Path, *, output_id: str, job_id: str, owner_id: int | None, replay_sha256: str | None = None) -> None:
    """Commit immutable identity/owner intent before any output bytes exist.

    Output IDs are single-use, including after interrupted writes or cleanup.
    Legacy generation retries mint fresh IDs and cannot reuse reservations.
    The primary transport may replay only an unpublished reservation with the
    identical immutable job, owner, and original image hash.
    """
    reservation = {"job_id": str(job_id), "owner_id": positive_owner(owner_id)}
    if replay_sha256 is not None:
        import re
        if not re.fullmatch(r"[0-9a-f]{64}", replay_sha256):
            raise ValueError("Invalid original image hash.")
        reservation["original_sha256"] = replay_sha256
    connection = connect(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM v1_records WHERE namespace='outputs' AND record_key=?", (output_id,),
        ).fetchone():
            raise ValueError("A published output ID cannot be materialized again.")
        existing = connection.execute(
            "SELECT payload FROM v1_records WHERE namespace=? AND record_key=?",
            (PUBLICATION_NAMESPACE, output_id),
        ).fetchone()
        if existing:
            # Only an unpublished original with identical immutable owner/job/hash
            # may recover an interrupted Bridge materialization.
            if replay_sha256 is None or json.loads(existing[0]) != reservation:
                raise ValueError("An output publication reservation cannot be reused or reassigned.")
        else:
            connection.execute(
                "INSERT INTO v1_records(namespace,record_key,payload) VALUES(?,?,?)",
                (PUBLICATION_NAMESPACE, output_id, json.dumps(reservation, separators=(",", ":"))),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def publication_blocked_on(
    connection: sqlite3.Connection, output_id: str, *, candidate_job_id: str | None = None,
) -> bool:
    """One predicate for history winners and media reads, using keyed lookups.

    Unmarked records keep their legacy authority. An unmarked bare file under
    a known Job has unknown publication state; a genuinely orphan legacy file
    remains recoverable/public. The index supplies file/Job associations, never
    a Session owner. Managed IDs require their exact canonical publication.
    """
    reservation = connection.execute(
        "SELECT payload FROM v1_records WHERE namespace=? AND record_key=?",
        (PUBLICATION_NAMESPACE, output_id),
    ).fetchone()
    canonical = connection.execute(
        "SELECT payload FROM v1_records WHERE namespace='outputs' AND record_key=?", (output_id,),
    ).fetchone()
    if reservation:
        if canonical is None:
            return True
        try:
            intent = json.loads(reservation[0])
            output = json.loads(canonical[0])
            metadata = output.get("metadata") or {}
            return not (
                output.get("id") == output_id
                and output.get("job_id") == intent["job_id"]
                and positive_owner(metadata.get("veyra_user_id")) == intent["owner_id"]
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            return True
    if canonical is not None:
        return False
    # The old storage recovery iterator can supply its observed path before
    # derived state is prepared. A keyed manifest lookup preserves legacy rows.
    has_manifest = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='v1_history_records'",
    ).fetchone()
    if has_manifest and connection.execute(
        "SELECT 1 FROM v1_history_records WHERE output_id=?", (output_id,),
    ).fetchone():
        return False
    if connection.execute(
        "SELECT 1 FROM v1_read_sources WHERE output_id=? AND kind IN ('history','job') LIMIT 1",
        (output_id,),
    ).fetchone():
        return False
    if candidate_job_id:
        # Only the old explicit filesystem recovery iterator uses this path.
        # Warm API/index reads instead use the projected per-output sources.
        job = connection.execute(
            "SELECT payload FROM v1_records WHERE namespace='jobs' AND record_key=?", (candidate_job_id,),
        ).fetchone()
        if job:
            try:
                return not any(item.get("id") == output_id for item in json.loads(job[0]).get("outputs", []))
            except (TypeError, ValueError, AttributeError):
                return True
    return connection.execute(
        "SELECT 1 FROM v1_read_sources AS files JOIN v1_records AS jobs "
        "ON jobs.namespace='jobs' AND jobs.record_key=files.job_id "
        "WHERE files.output_id=? AND files.kind='file' "
        "AND json_extract(files.payload,'$.format') IN ('png','jpeg','webp') LIMIT 1", (output_id,),
    ).fetchone() is not None
