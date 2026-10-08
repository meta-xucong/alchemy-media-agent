"""Bounded, lazily-started Job deserialization processes. No API/store authority here.

Workers receive one trusted, revision-tagged local file at a time. They never
construct a service/store, write records, recover jobs, or import app.main.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from contextlib import contextmanager
import logging
import multiprocessing
import os
from pathlib import Path
import pickle
import re
import threading

MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_RESULT_BYTES = 4 * 1024 * 1024
logger = logging.getLogger(__name__)


class BrowseCapacityExceeded(RuntimeError):
    pass


class BrowseComputeUnavailable(RuntimeError):
    pass


def _read_cpu_quota(cgroup_root: Path) -> int | None:
    """Return whole CPUs available from a finite cgroup quota, when present."""
    try:
        quota_text, period_text = (cgroup_root / "cpu.max").read_text(encoding="ascii").split()[:2]
        if quota_text != "max":
            quota, period = int(quota_text), int(period_text)
            if quota > 0 and period > 0:
                return max(1, quota // period)
    except (OSError, UnicodeError, ValueError):
        pass

    for cpu_dir in (cgroup_root / "cpu", cgroup_root / "cpu,cpuacct", cgroup_root):
        try:
            quota = int((cpu_dir / "cpu.cfs_quota_us").read_text(encoding="ascii").strip())
            period = int((cpu_dir / "cpu.cfs_period_us").read_text(encoding="ascii").strip())
            if quota > 0 and period > 0:
                return max(1, quota // period)
        except (OSError, UnicodeError, ValueError):
            continue
    return None


def effective_cpu_count(*, affinity_count: int | None = None, cgroup_root: Path = Path("/sys/fs/cgroup")) -> int:
    """Resolve CPU affinity and Linux cgroup quota conservatively."""
    if affinity_count is None:
        get_affinity = getattr(os, "sched_getaffinity", None)
        try:
            affinity_count = len(get_affinity(0)) if get_affinity else (os.cpu_count() or 1)
        except OSError:
            affinity_count = os.cpu_count() or 1
    available = max(1, int(affinity_count))
    quota_count = _read_cpu_quota(Path(cgroup_root))
    return min(available, quota_count) if quota_count is not None else available


def resolve_browse_compute_workers(
    raw_value: str | None,
    *,
    available_cpus: int,
    default: int = 2,
) -> int:
    """Parse operator configuration and cap it to CPUs visible to the app."""
    try:
        requested = int(raw_value) if raw_value and raw_value.strip() else default
    except (TypeError, ValueError):
        logger.warning("Invalid V3_BROWSE_COMPUTE_WORKERS=%r; using default=%s", raw_value, default)
        requested = default
    if requested < 0:
        logger.warning("Negative V3_BROWSE_COMPUTE_WORKERS=%r; using default=%s", raw_value, default)
        requested = default
    if requested == 0:
        return 0
    cpu_limit = max(1, int(available_cpus))
    if requested > cpu_limit:
        logger.info(
            "Clamping V3_BROWSE_COMPUTE_WORKERS from %s to effective CPU count %s",
            requested,
            cpu_limit,
        )
    return min(requested, cpu_limit)


def file_revision(path):
    try:
        stat = Path(path).stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size


def _initialize_reader():
    # Scrub inherited provider credentials before loading application contracts.
    # This is defense in depth for trusted local code, not a process sandbox.
    keep = {key: value for key, value in os.environ.items() if key in {
        "PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL", "TZ",
        "TMPDIR", "TEMP", "TMP",
    }}
    os.environ.clear()
    os.environ.update(keep)
    os.environ.update({
        "V3_LLM_BRAIN_REMOTE_ENABLED": "false", "LLM_PROMPT_PLANNING_ENABLED": "false",
        "MEDIA_AGENT_MODE": "mock", "MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS": "false",
        "CODEX_AUTH_FILE": os.devnull, "CLAUDE_SETTINGS_FILE": os.devnull,
    })


def decode_job_file(path: str, job_id: str, revision: tuple[int, int, int]):
    """Read/validate one exact file revision; None means use the owner fallback."""
    import json
    from alchemy_creative_agent_3_0.app.product_api.service import deserialize_product_job_record

    if not re.fullmatch(r"job_[A-Za-z0-9_-]{1,128}", job_id) or Path(path).name != f"{job_id}.json":
        return None
    if revision[2] > MAX_SOURCE_BYTES or file_revision(path) != revision:
        return None
    try:
        with open(path, "rb") as handle:
            source = handle.read(MAX_SOURCE_BYTES + 1)
        if len(source) > MAX_SOURCE_BYTES:
            return None
        payload = json.loads(source.decode("utf-8"))
        # Legacy absent timestamps are defaulted from the owner clock. Do not
        # materialize those defaults earlier in a queued worker.
        if not isinstance(payload, dict) or not payload.get("created_at") or not payload.get("updated_at"):
            return None
        record = deserialize_product_job_record(payload)
        del payload, source
        if record is None or record.job_id != job_id or file_revision(path) != revision:
            return None
        serialized = pickle.dumps(record, protocol=pickle.HIGHEST_PROTOCOL)
        if len(serialized) > MAX_RESULT_BYTES:
            return None
        return serialized
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        return None


class BoundedBrowseCompute:
    """Admission covers the whole request, including a cancelled physical task.

    Every lease has at most one submitted task. Completed records must be
    consumed and released by the owner before the lease submits another read.
    """
    def __init__(self, workers: int = 1, *, max_pending: int | None = None, timeout: float = 30.0):
        if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
            raise ValueError("browse workers must be a positive integer")
        self.workers = workers
        self.max_pending = max_pending if max_pending is not None else workers + 1
        if not 1 <= self.max_pending <= workers + 1:
            raise ValueError("browse admission must be between 1 and workers + 1")
        self.timeout = timeout
        self._lock = threading.Lock()
        self._executor = None
        self._admitted = 0
        self._closed = False

    @property
    def admitted(self):
        with self._lock:
            return self._admitted

    @contextmanager
    def admit(self):
        with self._lock:
            if self._closed:
                raise BrowseComputeUnavailable("browse compute is closed")
            if self._admitted >= self.max_pending:
                raise BrowseCapacityExceeded("browse read capacity exceeded")
            self._admitted += 1
        lease = _BrowseLease(self)
        try:
            yield lease
        finally:
            lease.close()

    def _submit(self, path, job_id, revision):
        with self._lock:
            if self._closed:
                raise BrowseComputeUnavailable("browse compute is closed")
            if self._executor is None:
                self._executor = ProcessPoolExecutor(
                    max_workers=self.workers,
                    mp_context=multiprocessing.get_context("spawn"),
                    initializer=_initialize_reader,
                )
            executor = self._executor
            try:
                return executor, executor.submit(decode_job_file, path, job_id, revision)
            except BrokenProcessPool as exc:
                self._executor = None
                executor.shutdown(wait=False)
                raise BrowseComputeUnavailable("browse compute worker stopped") from exc

    def _broken(self, executor):
        with self._lock:
            if self._executor is executor:
                self._executor = None
        executor.shutdown(wait=False)

    def shutdown(self):
        """Stop admission and drain only the finite admitted work; no new reads."""
        with self._lock:
            self._closed = True
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=False)


class _BrowseLease:
    def __init__(self, pool):
        self.pool = pool
        self.future = None
        self.closed = False
        self.released = False

    async def read_job(self, path, job_id, revision):
        if self.closed or (self.future is not None and not self.future.done()):
            raise BrowseComputeUnavailable("browse lease is not available")
        try:
            executor, future = self.pool._submit(str(path), job_id, revision)
        except BrowseComputeUnavailable:
            raise
        except Exception as exc:
            raise BrowseComputeUnavailable("browse compute submission failed") from exc
        self.future = future
        future.add_done_callback(lambda _: self._release_if_finished())
        try:
            # Neither timeout nor caller cancellation cancels the physical work.
            wrapped = asyncio.wrap_future(future)
            # Consume late failures even when the HTTP request has gone away.
            wrapped.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
            return await asyncio.wait_for(asyncio.shield(wrapped), self.pool.timeout)
        except BrokenProcessPool as exc:
            self.pool._broken(executor)
            raise BrowseComputeUnavailable("browse compute worker stopped") from exc
        except TimeoutError as exc:
            raise BrowseComputeUnavailable("browse compute read timed out") from exc
        except Exception as exc:
            raise BrowseComputeUnavailable("browse compute read failed") from exc

    def close(self):
        with self.pool._lock:
            self.closed = True
        self._release_if_finished()

    def _release_if_finished(self):
        with self.pool._lock:
            if self.closed and not self.released and (self.future is None or self.future.done()):
                self.released = True
                self.pool._admitted -= 1
