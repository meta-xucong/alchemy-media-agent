from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any, Iterator
from datetime import datetime, timezone

from app.repositories.sqlite_json import SQLiteJsonMap, connect
from app.schemas import Asset, GenerationJob, GenerationOutput, JobStatus, ProviderError, Session


class MemoryRepository:
    """Compatibility-named V1 repository backed by SQLite, not process memory."""

    OUTPUT_DELETE_ATTEMPT_LEASE_SECONDS = 900

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path_override = Path(database_path) if database_path else None
        jobs = self._record_map("jobs", GenerationJob, self._job_index)
        self.sessions = self._record_map("sessions", Session)
        self.assets = self._record_map("assets", Asset)
        self.jobs = jobs
        self.outputs = self._record_map("outputs", GenerationOutput)
        self.idempotency_index = self._record_map("idempotency", str)
        self.output_delete_claims = SQLiteJsonMap(
            lambda: self.database_path,
            "output_delete_claims",
            validator=json.loads,
        )

    @property
    def database_path(self) -> Path:
        if self._database_path_override is not None:
            return self._database_path_override
        # Import lazily to avoid a repository -> storage -> application import cycle.
        from app.storage import media_store

        return Path(media_store.root) / "repository.sqlite3"

    def _record_map(self, namespace: str, model: Any, index_fields=None) -> SQLiteJsonMap:
        def validate(payload: str):
            if model is str:
                return json.loads(payload)
            return model.model_validate_json(payload)

        return SQLiteJsonMap(
            lambda: self.database_path,
            namespace,
            validator=validate,
            index_fields=index_fields,
        )

    @staticmethod
    def _job_index(job: GenerationJob) -> dict[str, str | None]:
        return {
            "session_id": job.session_id,
            "job_type": job.job_type,
            "sort_at": job.updated_at or job.created_at,
            "idempotency_key": job.idempotency_key,
        }

    def save_session(self, session: Session) -> Session:
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_json = self.sessions.get_record_json_on(connection, session.id)
            if existing_json is not None:
                existing = Session.model_validate_json(existing_json)
                old_owner_id = self._positive_owner_id(existing.veyra_user_id)
                new_owner_id = self._positive_owner_id(session.veyra_user_id)
                if old_owner_id is not None and new_owner_id is None:
                    session = session.model_copy(update={"veyra_user_id": old_owner_id})
                elif old_owner_id != new_owner_id:
                    raise ValueError("A session owner cannot be reassigned or inferred after creation.")
            self.sessions.put_on(connection, session.id, session)
            connection.commit()
            return session
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _positive_owner_id(value: Any) -> int | None:
        try:
            owner_id = int(value or 0)
        except (TypeError, ValueError):
            return None
        return owner_id if owner_id > 0 else None

    def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def save_asset(self, asset) -> Any:
        self.assets[asset.id] = asset
        return asset

    @staticmethod
    def _output_owner_id(output: GenerationOutput) -> int | None:
        try:
            owner_id = int((output.metadata or {}).get("veyra_user_id") or 0)
        except (TypeError, ValueError):
            return None
        return owner_id if owner_id > 0 else None

    def get_asset(self, asset_id: str) -> Any | None:
        return self.assets.get(asset_id)

    def save_job(self, job: GenerationJob) -> GenerationJob:
        connection = connect(self.database_path)
        try:
            with connection:
                # Serialize owner lookup and canonicalization with every writer.
                # A deferred transaction would allow a stale ownerless snapshot
                # to read first, then overwrite a private owner committed by a
                # concurrent save before this transaction's first write.
                connection.execute("BEGIN IMMEDIATE")
                canonical_outputs: list[GenerationOutput] = []
                for output in job.outputs:
                    if self.output_delete_claims.get_record_json_on(connection, output.id) is not None:
                        # Deletion owns this ID until all filesystem/history work
                        # finishes. Never let a stale provider snapshot rebind it.
                        continue
                    existing_json = self.outputs.get_record_json_on(connection, output.id)
                    if existing_json is not None:
                        existing = GenerationOutput.model_validate_json(existing_json)
                        existing_owner = self._output_owner_id(existing)
                        incoming_owner = self._output_owner_id(output)
                        if existing_owner is not None and incoming_owner is not None and existing_owner != incoming_owner:
                            raise ValueError("An output ID cannot be reassigned to a different account.")
                        if existing_owner is not None and incoming_owner is None:
                            metadata = dict(output.metadata or {})
                            metadata["veyra_user_id"] = existing_owner
                            output = output.model_copy(update={"metadata": metadata})
                    canonical_outputs.append(output)
                    self.outputs.put_on(connection, output.id, output)
                # Keep the Job projection consistent with the canonical output
                # records. History listing reads nested Job.outputs, so only
                # normalizing the outputs table would leave an ownerless copy
                # that could be projected as public after a same-Job update.
                canonical_job = job.model_copy(update={"outputs": canonical_outputs})
                self.jobs.put_on(connection, canonical_job.id, canonical_job)
                if job.idempotency_key:
                    self.idempotency_index.put_on(connection, job.idempotency_key, canonical_job.id)
        finally:
            connection.close()
        return canonical_job

    def begin_output_delete_claim(
        self,
        output_id: str,
        *,
        owner_id: int | None,
        canonical_job_id: str | None,
        event_job_id: str | None,
    ) -> dict[str, Any] | None:
        """Fence output identity/ownership across non-transactional cleanup steps."""
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            now = time.time()
            attempt_id = secrets.token_urlsafe(18)
            existing_json = self.output_delete_claims.get_record_json_on(connection, output_id)
            if existing_json is not None:
                claim = json.loads(existing_json)
                if self._positive_owner_id(claim.get("owner_id")) != self._positive_owner_id(owner_id):
                    connection.rollback()
                    return None
                try:
                    lease_expires_at = float(claim.get("lease_expires_at") or 0)
                except (TypeError, ValueError):
                    lease_expires_at = 0
                if claim.get("attempt_id") and lease_expires_at > now:
                    connection.rollback()
                    return None
                claim["attempt_id"] = attempt_id
                claim["lease_expires_at"] = now + self.OUTPUT_DELETE_ATTEMPT_LEASE_SECONDS
                self.output_delete_claims.put_on(connection, output_id, claim)
                connection.commit()
                return claim

            output = self.get_output_on(connection, output_id)
            current_job_id = output.job_id if output else None
            if current_job_id != canonical_job_id:
                connection.rollback()
                return None

            canonical_owner_id = self._output_owner_id(output) if output else None
            resolved_owner_id = canonical_owner_id
            owner_conflict = False
            if canonical_owner_id is None:
                table_exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='v1_history_owner_evidence'"
                ).fetchone()
                history_evidence = (
                    connection.execute(
                        "SELECT owner_id, owner_conflict FROM v1_history_owner_evidence WHERE output_id=?",
                        (output_id,),
                    ).fetchone()
                    if table_exists
                    else None
                )
                if history_evidence is not None:
                    owner_conflict = bool(history_evidence[1])
                    resolved_owner_id = self._positive_owner_id(history_evidence[0])
                if resolved_owner_id is None and not owner_conflict:
                    job_rows = connection.execute(
                        "SELECT payload FROM v1_records WHERE namespace='jobs'"
                    ).fetchall()
                    observed_owners: set[int] = set()
                    for row in job_rows:
                        job = GenerationJob.model_validate_json(row[0])
                        for nested in job.outputs:
                            if nested.id == output_id:
                                nested_owner_id = self._output_owner_id(nested)
                                if nested_owner_id is not None:
                                    observed_owners.add(nested_owner_id)
                    if len(observed_owners) > 1:
                        owner_conflict = True
                    elif observed_owners:
                        resolved_owner_id = next(iter(observed_owners))

            if owner_conflict or resolved_owner_id != self._positive_owner_id(owner_id):
                connection.rollback()
                return None
            if event_job_id and self._validated_output_event_session_on(
                connection,
                event_job_id,
                output_id,
                self._positive_owner_id(owner_id),
            ) is None:
                event_job_id = None

            claim = {
                "output_id": output_id,
                "owner_id": self._positive_owner_id(owner_id),
                "canonical_job_id": current_job_id,
                "event_job_id": event_job_id,
                "attempt_id": attempt_id,
                "lease_expires_at": now + self.OUTPUT_DELETE_ATTEMPT_LEASE_SECONDS,
            }
            self.output_delete_claims.put_on(connection, output_id, claim)
            connection.commit()
            return claim
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_output_delete_claim(self, output_id: str) -> dict[str, Any] | None:
        return self.output_delete_claims.get(output_id)

    def release_output_delete_claim_attempt(
        self,
        output_id: str,
        *,
        owner_id: int | None,
        attempt_id: str,
    ) -> bool:
        """Release an interrupted attempt while retaining its authorization anchor."""
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            claim_json = self.output_delete_claims.get_record_json_on(connection, output_id)
            if claim_json is None:
                connection.commit()
                return False
            claim = json.loads(claim_json)
            if (
                self._positive_owner_id(claim.get("owner_id")) != self._positive_owner_id(owner_id)
                or claim.get("attempt_id") != attempt_id
            ):
                connection.rollback()
                return False
            claim["attempt_id"] = None
            claim["lease_expires_at"] = 0
            self.output_delete_claims.put_on(connection, output_id, claim)
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finish_output_delete_claim(
        self,
        output_id: str,
        *,
        owner_id: int | None,
        attempt_id: str,
    ) -> bool:
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            claim_json = self.output_delete_claims.get_record_json_on(connection, output_id)
            if claim_json is None:
                connection.commit()
                return False
            claim = json.loads(claim_json)
            if (
                self._positive_owner_id(claim.get("owner_id")) != self._positive_owner_id(owner_id)
                or claim.get("attempt_id") != attempt_id
            ):
                connection.rollback()
                return False
            removed = self.output_delete_claims.delete_on(connection, output_id)
            connection.commit()
            return bool(removed)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_job(self, job_id: str) -> GenerationJob | None:
        return self.jobs.get(job_id)

    def list_jobs(self, *, job_type: str | None = None, session_id: str | None = None) -> list[GenerationJob]:
        return self.jobs.list_jobs(job_type=job_type, session_id=session_id)

    def iter_jobs(self, *, job_type: str | None = None, session_id: str | None = None) -> Iterator[GenerationJob]:
        yield from self.jobs.iter_jobs(job_type=job_type, session_id=session_id)

    def get_job_by_idempotency_key(self, idempotency_key: str | None) -> GenerationJob | None:
        if not idempotency_key:
            return None
        job_id = self.idempotency_index.get(idempotency_key)
        return self.jobs.get(job_id) if job_id else self.jobs.get_job_by_idempotency_key(idempotency_key)

    def get_output(self, output_id: str) -> GenerationOutput | None:
        return self.outputs.get(output_id)

    def get_output_on(self, connection, output_id: str) -> GenerationOutput | None:
        payload = self.outputs.get_record_json_on(connection, output_id)
        return GenerationOutput.model_validate_json(payload) if payload is not None else None

    def _rewrite_output_copies_on(
        self,
        connection,
        output_id: str,
        *,
        owner_id: int | None = None,
    ) -> GenerationOutput | None:
        """Update or remove every legacy Job projection for one output ID."""
        matching_output = None
        for job in self.jobs.iter_jobs():
            if not any(item.id == output_id for item in job.outputs):
                continue
            if matching_output is None:
                matching_output = next(item for item in job.outputs if item.id == output_id)
            if owner_id is None:
                outputs = [item for item in job.outputs if item.id != output_id]
            else:
                outputs = []
                for item in job.outputs:
                    if item.id != output_id or self._output_owner_id(item) is not None:
                        outputs.append(item)
                        continue
                    metadata = dict(item.metadata or {})
                    metadata["veyra_user_id"] = owner_id
                    outputs.append(item.model_copy(update={"metadata": metadata}))
            if outputs != job.outputs:
                self.jobs.put_on(connection, job.id, job.model_copy(update={"outputs": outputs}))
        return matching_output

    def delete_output(self, output_id: str) -> GenerationOutput | None:
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            output_json = self.outputs.get_record_json_on(connection, output_id)
            if output_json is None:
                self._rewrite_output_copies_on(connection, output_id)
                connection.commit()
                return None
            output = GenerationOutput.model_validate_json(output_json)
            self.outputs.delete_on(connection, output_id)
            self._rewrite_output_copies_on(connection, output_id)
            connection.commit()
            return output
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def delete_output_with_event(
        self,
        output_id: str,
        *,
        event_job_id: str | None = None,
        event_owner_id: int | None = None,
        attempt_id: str,
    ) -> GenerationOutput | None:
        """Remove a canonical or legacy Job output and append any event atomically."""
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            claim_json = self.output_delete_claims.get_record_json_on(connection, output_id)
            if claim_json is None:
                raise RuntimeError("Output deletion requires an active ownership claim.")
            claim = json.loads(claim_json)
            claimed_owner_id = self._positive_owner_id(claim.get("owner_id"))
            if self._positive_owner_id(event_owner_id) != claimed_owner_id:
                raise RuntimeError("Output deletion owner does not match its active claim.")
            if claim.get("attempt_id") != attempt_id or float(claim.get("lease_expires_at") or 0) <= time.time():
                raise RuntimeError("Output deletion attempt is no longer active.")
            event_job_id = str(claim.get("event_job_id") or "").strip() or None
            output_json = self.outputs.get_record_json_on(connection, output_id)
            if output_json is None:
                event_session_id = None
                if event_job_id:
                    event_session_id = self._validated_output_event_session_on(
                        connection,
                        event_job_id,
                        output_id,
                        event_owner_id,
                    )
                legacy_output = self._rewrite_output_copies_on(connection, output_id)
                if legacy_output is not None and event_job_id and event_session_id:
                    connection.execute(
                        "INSERT INTO v1_events(session_id, event_type, payload) VALUES(?, ?, ?)",
                        (
                            event_session_id,
                            "generation.output.deleted",
                            json.dumps(
                                {"output_id": legacy_output.id, "job_id": event_job_id},
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        ),
                    )
                connection.commit()
                return legacy_output
            output = GenerationOutput.model_validate_json(output_json)
            if output.job_id != claim.get("canonical_job_id"):
                raise RuntimeError("Canonical output association changed during deletion.")
            job_json = self.jobs.get_record_json_on(connection, output.job_id)
            self.outputs.delete_on(connection, output_id)
            session_id = None
            output_owner_id = self._output_owner_id(output)
            if output_owner_id is not None and event_job_id == output.job_id and job_json:
                job = GenerationJob.model_validate_json(job_json)
                matching_outputs = [item for item in job.outputs if item.id == output_id]
                if matching_outputs and all(
                    self._output_owner_id(item) == output_owner_id
                    for item in matching_outputs
                ):
                    session_id = job.session_id
            elif event_job_id:
                session_id = self._validated_output_event_session_on(
                    connection,
                    event_job_id,
                    output_id,
                    event_owner_id,
                )
            self._rewrite_output_copies_on(connection, output_id)
            if session_id:
                connection.execute(
                    "INSERT INTO v1_events(session_id, event_type, payload) VALUES(?, ?, ?)",
                    (
                        session_id,
                        "generation.output.deleted",
                        json.dumps(
                            {"output_id": output.id, "job_id": event_job_id or output.job_id},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    ),
                )
            connection.commit()
            return output
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _validated_output_event_session_on(
        self,
        connection,
        job_id: str,
        output_id: str,
        owner_id: int | None,
    ) -> str | None:
        """Return a session only when its Job copy matches the chosen owner evidence."""
        job_json = self.jobs.get_record_json_on(connection, job_id)
        if not job_json:
            return None
        job = GenerationJob.model_validate_json(job_json)
        matching_outputs = [item for item in job.outputs if item.id == output_id]
        if not matching_outputs or any(self._output_owner_id(item) != owner_id for item in matching_outputs):
            return None
        return job.session_id

    def preserve_output_owner(self, output_id: str, owner_id: int | None) -> GenerationOutput | None:
        """Persist a verified history owner on an output before its history anchor is removed."""
        try:
            verified_owner_id = int(owner_id or 0)
        except (TypeError, ValueError):
            return None
        if verified_owner_id <= 0:
            return None
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            output_json = self.outputs.get_record_json_on(connection, output_id)
            if output_json is None:
                self._rewrite_output_copies_on(connection, output_id, owner_id=verified_owner_id)
                connection.commit()
                return None
            output = GenerationOutput.model_validate_json(output_json)
            metadata = dict(output.metadata or {})
            try:
                current_owner_id = int(metadata.get("veyra_user_id") or 0)
            except (TypeError, ValueError):
                current_owner_id = 0
            if current_owner_id <= 0:
                metadata["veyra_user_id"] = verified_owner_id
                output = output.model_copy(update={"metadata": metadata})
                self.outputs.put_on(connection, output_id, output)
            canonical_owner_id = self._output_owner_id(output) or verified_owner_id
            self._rewrite_output_copies_on(connection, output_id, owner_id=canonical_owner_id)
            connection.commit()
            return output
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recover_interrupted_jobs(self, *, batch_size: int = 128) -> int:
        active_statuses = (
            JobStatus.created.value,
            JobStatus.queued.value,
            JobStatus.planning.value,
            JobStatus.safety_check.value,
            JobStatus.generating.value,
            JobStatus.postprocessing.value,
            JobStatus.evaluating.value,
            JobStatus.processing.value,
            JobStatus.submitted.value,
        )
        recovered = 0
        while True:
            connection = connect(self.database_path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                placeholders = ",".join("?" for _ in active_statuses)
                rows = connection.execute(
                    "SELECT record_key, payload FROM v1_records "
                    f"WHERE namespace='jobs' AND json_extract(payload, '$.status') IN ({placeholders}) "
                    "ORDER BY rowid LIMIT ?",
                    (*active_statuses, max(1, int(batch_size))),
                ).fetchall()
                if not rows:
                    connection.commit()
                    return recovered
                for row in rows:
                    job = GenerationJob.model_validate_json(row["payload"])
                    job.status = JobStatus.failed
                    job.error = ProviderError(
                        code="worker_interrupted",
                        message="The server restarted before this generation completed. It was not replayed automatically; submit a new request to retry.",
                        retryable=False,
                        detail={"recovery": "process_restart", "automatic_provider_replay": False},
                    )
                    job.updated_at = datetime.now(timezone.utc).isoformat()
                    self.jobs.put_on(connection, job.id, job)
                    recovered += 1
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def append_event(self, session_id: str | None, event_type: str, data: dict[str, Any]) -> None:
        if not session_id:
            return
        connection = connect(self.database_path)
        try:
            with connection:
                connection.execute(
                    "INSERT INTO v1_events(session_id, event_type, payload) VALUES(?, ?, ?)",
                    (session_id, event_type, json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
                )
        finally:
            connection.close()

    def iter_events(self, session_id: str):
        connection = connect(self.database_path)
        try:
            row = connection.execute(
                "SELECT COALESCE(MAX(event_id), 0) FROM v1_events WHERE session_id=?",
                (session_id,),
            ).fetchone()
            upper_event_id = int(row[0] or 0)
        finally:
            connection.close()

        last_event_id = 0
        batch_size = 128
        while last_event_id < upper_event_id:
            connection = connect(self.database_path)
            try:
                rows = connection.execute(
                    "SELECT event_id, event_type, payload FROM v1_events "
                    "WHERE session_id=? AND event_id>? AND event_id<=? "
                    "ORDER BY event_id LIMIT ?",
                    (session_id, last_event_id, upper_event_id, batch_size),
                ).fetchall()
            finally:
                connection.close()
            if not rows:
                return
            events = [
                (int(row["event_id"]), {"event": row["event_type"], "data": json.loads(row["payload"])})
                for row in rows
            ]
            for event_id, event in events:
                last_event_id = event_id
                yield event

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        return list(self.iter_events(session_id))

    def reset(self) -> None:
        connection = connect(self.database_path)
        try:
            with connection:
                connection.execute(
                    "DELETE FROM v1_records WHERE namespace IN (?, ?, ?, ?, ?, ?)",
                    ("sessions", "assets", "jobs", "outputs", "idempotency", "output_delete_claims"),
                )
                connection.execute("DELETE FROM v1_events")
        finally:
            connection.close()


repository = MemoryRepository()
