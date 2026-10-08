"""Owner-only async driver for the existing output-browse state machine."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import pickle

from alchemy_creative_agent_3_0.app.browse_protocol import BrowseScope, BrowseJobRead, BrowseCheckpoint
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectStatus
from .browse_compute import MAX_SOURCE_BYTES, BrowseComputeUnavailable, file_revision


# Conservative IPC eligibility: small reads keep their existing owner path.
# File size is only a cost proxy; enable after workload-specific measurement.
MIN_SOURCE_BYTES = 1024 * 1024


class _ReadScopeChanged(Exception):
    pass


class _ReadGuard:
    def __init__(self, service, owner_user_id):
        self.service = service
        self.owner_user_id = owner_user_id
        self.paths = {}
        self.projects = []
        self.expiries = []
        self.job_ids = set()
        self.output_revision = service.product_service.output_store._storage_revision()

    def watch(self, path):
        path = str(path)
        revision = file_revision(path)
        if path in self.paths and self.paths[path] != revision:
            raise _ReadScopeChanged()
        self.paths[path] = revision
        return revision

    def add_scope(self, projects):
        store = self.service.project_store
        for project in projects:
            # Bind the already-authorized object to its original cached file
            # version, not a newer revision first observed after authorization.
            revision = store._project_revisions.get(project.project_id)
            if store._projects.get(project.project_id) is not project or revision is None:
                raise _ReadScopeChanged()
            if self.watch(store._project_path(project.project_id)) != revision:
                raise _ReadScopeChanged()
            if (store._projects.get(project.project_id) is not project
                or store._project_revisions.get(project.project_id) != revision
                or project.status == ProjectStatus.ARCHIVED
                or not self.service._project_visible_to_owner(project, self.owner_user_id)):
                # A same-identity mutation/save may preserve cache freshness
                # while invalidating the service's earlier eligibility check.
                raise _ReadScopeChanged()
            self.projects.append((project, project.status, self.service._positive_owner_id(
                dict(project.metadata or {}).get("veyra_user_id")), tuple(project.job_ids)))

    def add_outputs(self, job_id, records):
        output_store = self.service.product_service.output_store
        self.job_ids.add(job_id)
        self.watch(output_store._job_closure_path(job_id))
        from alchemy_creative_agent_3_0.app.product_api.outputs import _valid_output_id, _FORMAT_SUFFIXES
        for record in records or ():
            if not _valid_output_id(record.output_id):
                raise _ReadScopeChanged()
            self.watch(output_store._record_path(record.output_id))
            # Match the output store's canonical original, not a historical
            # metadata path that could point outside the output directory.
            self.watch(output_store.storage_root / record.output_id /
                       f"original{_FORMAT_SUFFIXES.get(record.output_format, '.png')}")

    def check(self):
        if self.output_revision != self.service.product_service.output_store._storage_revision():
            raise _ReadScopeChanged()
        if any(file_revision(path) != revision for path, revision in self.paths.items()):
            raise _ReadScopeChanged()
        # A new mutable owner identity may have appeared after an earlier
        # compact snapshot, without having reached its durable save yet.
        job_store = self.service.product_service.job_store
        if any(job_store._records.get(job_id) is not None for job_id in self.job_ids):
            raise _ReadScopeChanged()
        for project, status, owner, job_ids in self.projects:
            cached = self.service.project_store._projects.get(project.project_id)
            if cached is not None and cached is not project:
                raise _ReadScopeChanged()
            if (project.status != status or tuple(project.job_ids) != job_ids
                or self.service._positive_owner_id(dict(project.metadata or {}).get("veyra_user_id")) != owner):
                raise _ReadScopeChanged()
        now = datetime.now(timezone.utc)
        if any(now >= expiry for expiry in self.expiries):
            raise _ReadScopeChanged()


async def run_output_browse(service, pool, **kwargs):
    """Await only cold Job decoding; all policy and writes run on the owner.

    A live mutable cache identity or changed read scope restarts once through
    the unmodified synchronous path. Overload/cancellation/worker errors do
    NOT fall back into unbounded work on the API process.
    """
    from alchemy_creative_agent_3_0.app.product_api.service import (
        PersistentProductJobStore, _failure_artifact_expiry, _valid_product_job_id,
    )
    from alchemy_creative_agent_3_0.app.project_mode.store import PersistentProjectStore
    from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore

    product = service.product_service
    store = product.job_store
    if (not isinstance(store, PersistentProductJobStore)
        or not isinstance(service.project_store, PersistentProjectStore)
        or not isinstance(product.output_store, V3GeneratedOutputStore)):
        return service.list_project_outputs(**kwargs)

    with ExitStack() as admission:
        lease = None
        steps = service.iter_project_output_reads(**kwargs)
        guard = _ReadGuard(service, kwargs.get("owner_user_id"))
        value = error = None
        try:
            while True:
                try:
                    step = steps.throw(error) if error is not None else steps.send(value)
                except StopIteration as done:
                    return done.value
                # Do not retain the full record/status tuple across a new await.
                value = error = None
                if isinstance(step, BrowseScope):
                    guard.add_scope(step.projects)
                    continue
                if isinstance(step, BrowseCheckpoint):
                    if lease is not None:
                        guard.check()
                    continue
                if not isinstance(step, BrowseJobRead):
                    raise RuntimeError("unknown output read suspension")

                if not _valid_product_job_id(step.job_id):
                    # Keep unusual legacy identities wholly synchronous; do
                    # not create an unguarded restored-output read before a
                    # later valid Job suspends this request.
                    raise _ReadScopeChanged()
                guard.add_outputs(step.job_id, step.output_records)
                path = store._record_path(step.job_id)
                revision = guard.watch(path)
                # Never replace or snapshot an active mutable identity across
                # an await. Keep all reads of such a scope on its current owner.
                if store._records.get(step.job_id) is not None:
                    raise _ReadScopeChanged()
                record = None
                if revision is not None and MIN_SOURCE_BYTES <= revision[2] <= MAX_SOURCE_BYTES:
                    if lease is None:
                        lease = admission.enter_context(pool.admit())
                    serialized = await lease.read_job(path, step.job_id, revision)
                    # Full-scope validation happens once at the mandatory
                    # checkpoint, before reconcile/projection. Rechecking the
                    # accumulated paths after every Job would be quadratic.
                    if store._record_revision(step.job_id) != revision:
                        raise _ReadScopeChanged()
                    if store._records.get(step.job_id) is not None:
                        raise _ReadScopeChanged()
                    if serialized is not None:
                        try:
                            record = pickle.loads(serialized)
                        except Exception as exc:
                            raise BrowseComputeUnavailable("browse compute result invalid") from exc
                    del serialized
                    if record is not None:
                        if record.job_id != step.job_id or store._record_revision(step.job_id) != revision:
                            raise _ReadScopeChanged()
                        if str(record.status) in {"generating", "finalizing"}:
                            raise _ReadScopeChanged()
                        # Exact decoded revision, never a newly refreshed one.
                        store._cache_record(record, revision)
                if record is None:
                    try:
                        record = store.get(step.job_id)
                    except Exception as exc:
                        # Keep the original snapshot's domain-read error path.
                        error = exc
                        continue
                if record is not None and str(record.status) in {"generating", "finalizing"}:
                    raise _ReadScopeChanged()
                try:
                    # Unchanged authoritative expiry, recovery, closure, review
                    # and ownership policies. The weak cache only avoids decode.
                    value = product.get_job_read_snapshot(step.job_id, output_records=step.output_records)
                    expiry = _failure_artifact_expiry(value[1]) if value[1] is not None else None
                    if expiry:
                        guard.expiries.append(datetime.fromisoformat(expiry))
                    if record is None and value[1] is not None and str(value[1].status) in {"generating", "finalizing"}:
                        raise _ReadScopeChanged()
                except _ReadScopeChanged:
                    raise
                except Exception as exc:
                    error = exc
                finally:
                    record = None
        except _ReadScopeChanged:
            # Close suspended stale locals before fresh authorization or writes.
            steps.close()
            value = error = record = None
            guard = None
            return service.list_project_outputs(**kwargs)
        finally:
            steps.close()
