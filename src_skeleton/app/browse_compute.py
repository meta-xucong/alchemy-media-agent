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
from pathlib import PurePosixPath
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


def _decode_mountinfo_path(value: str) -> str:
    return value.replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")


def _cgroup_relative_path(process_path: str, mount_root: str) -> PurePosixPath | None:
    process = PurePosixPath(process_path)
    root = PurePosixPath(mount_root)
    if process == PurePosixPath("/"):
        return PurePosixPath(".")
    if ".." in process.parts or ".." in root.parts:
        return None
    try:
        relative = process.relative_to(root)
    except ValueError:
        return None
    return relative


def _parse_cpu_cgroup_locations(cgroup_text: str, mountinfo_text: str):
    v2_path = None
    v1_cpu_path = None
    for line in cgroup_text.splitlines():
        try:
            hierarchy, controllers, path = line.split(":", 2)
        except ValueError:
            continue
        if hierarchy == "0" and not controllers:
            v2_path = path
        elif "cpu" in controllers.split(","):
            v1_cpu_path = path

    mounts = []
    for line in mountinfo_text.splitlines():
        try:
            left, right = line.split(" - ", 1)
            before = left.split()
            after = right.split()
            mount_root = _decode_mountinfo_path(before[3])
            mount_point = _decode_mountinfo_path(before[4])
            filesystem = after[0]
            super_options = set(after[2].split(",")) if len(after) > 2 else set()
        except (IndexError, ValueError):
            continue
        if filesystem == "cgroup2" and v2_path:
            relative = _cgroup_relative_path(v2_path, mount_root)
            if relative is not None:
                mounts.append((mount_point, relative, True))
        elif filesystem == "cgroup" and "cpu" in super_options and v1_cpu_path:
            relative = _cgroup_relative_path(v1_cpu_path, mount_root)
            if relative is not None:
                mounts.append((mount_point, relative, False))
    return mounts


def _mountpoint_directory(mount_point: str, cgroup_root: Path) -> Path:
    root = Path(cgroup_root)
    if root == Path("/sys/fs/cgroup"):
        return Path(mount_point)
    mount = PurePosixPath(mount_point)
    standard_root = PurePosixPath("/sys/fs/cgroup")
    try:
        relative = mount.relative_to(standard_root)
    except ValueError:
        relative = PurePosixPath(mount.name)
    return root.joinpath(*relative.parts)


def _quota_at(directory: Path, *, cgroup_v2: bool) -> int | None:
    try:
        if cgroup_v2:
            quota_text, period_text = (directory / "cpu.max").read_text(encoding="ascii").split()[:2]
            if quota_text == "max":
                return None
            quota, period = int(quota_text), int(period_text)
        else:
            quota = int((directory / "cpu.cfs_quota_us").read_text(encoding="ascii").strip())
            period = int((directory / "cpu.cfs_period_us").read_text(encoding="ascii").strip())
        if quota > 0 and period > 0:
            return max(1, quota // period)
    except (OSError, UnicodeError, ValueError):
        pass
    return None


def _read_cpu_quota(
    cgroup_root: Path,
    *,
    proc_cgroup_path: Path = Path("/proc/self/cgroup"),
    mountinfo_path: Path = Path("/proc/self/mountinfo"),
) -> int | None:
    """Read the tightest quota from the current cgroup and each ancestor."""
    limits = []
    try:
        locations = _parse_cpu_cgroup_locations(
            proc_cgroup_path.read_text(encoding="utf-8"),
            mountinfo_path.read_text(encoding="utf-8"),
        )
    except (OSError, UnicodeError):
        locations = []
    for mount_point, relative, cgroup_v2 in locations:
        mount_dir = _mountpoint_directory(mount_point, cgroup_root)
        for length in range(len(relative.parts), -1, -1):
            directory = mount_dir.joinpath(*relative.parts[:length])
            quota = _quota_at(directory, cgroup_v2=cgroup_v2)
            if quota is not None:
                limits.append(quota)

    if locations:
        return min(limits) if limits else None

    # Retain a fallback only when proc/mount data cannot identify this process's cgroup.
    for directory in (Path(cgroup_root), Path(cgroup_root) / "cpu", Path(cgroup_root) / "cpu,cpuacct"):
        for cgroup_v2 in (True, False):
            quota = _quota_at(directory, cgroup_v2=cgroup_v2)
            if quota is not None:
                limits.append(quota)
    return min(limits) if limits else None


def effective_cpu_count(
    *,
    affinity_count: int | None = None,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    proc_cgroup_path: Path = Path("/proc/self/cgroup"),
    mountinfo_path: Path = Path("/proc/self/mountinfo"),
) -> int:
    """Resolve CPU affinity and the tightest applicable Linux cgroup quota."""
    if affinity_count is None:
        get_affinity = getattr(os, "sched_getaffinity", None)
        try:
            affinity_count = len(get_affinity(0)) if get_affinity else (os.cpu_count() or 1)
        except OSError:
            affinity_count = os.cpu_count() or 1
    available = max(1, int(affinity_count))
    quota_count = _read_cpu_quota(
        Path(cgroup_root),
        proc_cgroup_path=Path(proc_cgroup_path),
        mountinfo_path=Path(mountinfo_path),
    )
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
        # Keep six bounded request slots beyond active workers. On a two-core
        # host this admits up to eight heavy browse requests without allowing
        # an unbounded executor backlog.
        self.max_pending = max_pending if max_pending is not None else workers + 6
        if not 1 <= self.max_pending <= workers + 6:
            raise ValueError("browse admission must be between 1 and workers + 6")
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
