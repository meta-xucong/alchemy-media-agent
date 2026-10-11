#!/usr/bin/env python3
"""Offline V1/Lab/V2 history read scaling; every data path is a temporary fixture.

Example (use separately resolved V1/V2 dependency environments):
  python scripts/benchmark_history_reads.py --v1-python /venv-v1/bin/python \
    --v2-python /venv-v2/bin/python --sizes 100,1000,10000,50000 \
    --concurrency 2,4,8 --rounds 50 --diagnostic --output /tmp/history-read.json

Run this script against an immutable baseline using --repo /path/to/baseline.
This measures direct async GET handlers, not HTTP/browser/auth-network latency.
No application lifespan, Provider, generation, or production data is involved.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import asdict
from collections import Counter
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import resource
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

# Fixed PNG-shaped bytes, intentionally never decoded by this metadata-only benchmark.
# The IDAT checksum is invalid; keep bytes identical in baseline/optimized fixtures.
PNG_SHAPED_STUB = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def isolate(root: Path) -> None:
    os.environ.update({
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1",
        "ORT_DISABLE_TELEMETRY": "1", "OPENAI_AGENTS_DISABLE_TRACING": "1",
        "MEDIA_AGENT_MODE": "mock", "MOCK_IMAGE_PROVIDER_ENABLED": "true",
        "V3_LLM_BRAIN_REMOTE_ENABLED": "false", "LLM_PROMPT_PLANNING_ENABLED": "false",
        "MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS": "false", "OPENAI_API_KEY": "",
        "ANTHROPIC_AUTH_TOKEN": "", "CODEX_AUTH_FILE": os.devnull,
        "CLAUDE_SETTINGS_FILE": os.devnull, "V2_ENV_FILE": os.devnull,
        "MEDIA_AGENT_RUNTIME_ENV_FILE": os.devnull, "ALCHEMY_MEDIA_AGENT_ENV_FILE": os.devnull,
        "ALCHEMY_MEDIA_RUNTIME_ENV_FILE": os.devnull,
        "ALCHEMY_APP_ROOT": str(root / "app"), "MEDIA_STORAGE_ROOT": str(root / "v1"),
        "ALCHEMY_V3_RUNTIME_DESCRIPTOR": "", "ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED": "false",
        "V2_TASK_QUEUE_INLINE_WORKER_ENABLED": "false", "V2_ENABLE_REMOTE_GITHUB_SYNC": "false",
        "V2_SYNC_GITHUB_ON_STARTUP": "false", "V2_CASE_THUMBNAIL_PREWARM_ENABLED": "false",
        "VEYRA_AUTH_ENABLED": "true", "VEYRA_INTERNAL_TOKEN": "offline-synthetic",
        "VEYRA_SESSION_SECRET": "offline-synthetic", "MEDIA_ACCELERATION_ENABLED": "false",
    })
    paths = {
        "V2_DATA_DIR": "v2/data", "V2_STORAGE_DIR": "v2/storage",
        "V2_CASE_INDEX_PATH": "v2/case_index.json", "V2_IMAGE_HISTORY_PATH": "v2/image_history.jsonl",
        "VEYRA_USAGE_PATH": "v2/usage.jsonl", "V2_REMOTE_SNAPSHOT_DIR": "v2/snapshots",
        "V2_CASE_THUMBNAIL_DIR": "v2/case_thumbnails", "V2_HISTORY_THUMBNAIL_DIR": "v2/thumbnails",
        "V2_TASK_QUEUE_DB_PATH": "v2/task_queue.sqlite3",
        "V2_CLAUDE_ORCHESTRATOR_WORKSPACE_DIR": "v2/claude",
        "V2_CLAUDE_ORCHESTRATOR_CACHE_PATH": "v2/claude_cache.json",
        "ALCHEMY_V3_JOB_DIR": "v3/jobs", "ALCHEMY_V3_PROJECT_DIR": "v3/projects",
        "ALCHEMY_V3_OUTPUT_DIR": "v3/outputs", "ALCHEMY_V3_UPLOAD_DIR": "v3/uploads",
        "ALCHEMY_V3_MCP_MATERIALIZATION_ROOT": "v3/materialization",
        "V3_VISUAL_ASSET_CATALOG_ROOT": "v3/assets", "V3_VISUAL_ASSET_LIBRARY_ROOT": "v3/library",
    }
    os.environ.update({name: str(root / value) for name, value in paths.items()})


def forbid_network_and_dotenv() -> None:
    def denied(*_args, **_kwargs):
        raise AssertionError("Offline history benchmark attempted network access")
    socket.create_connection = denied
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            return denied(address)
        return original_connect(self, address)
    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            return denied(address)
        return original_connect_ex(self, address)
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    original_read_text = Path.read_text
    def read_text(path, *args, **kwargs):
        # V2's existing config always checks its project .env; never read it here.
        if path.name == ".env":
            return ""
        return original_read_text(path, *args, **kwargs)
    Path.read_text = read_text


def owner_for(index: int, mode: str) -> int | None:
    if mode == "old-owner":
        return 42 if index == 0 else 77
    return None if index % 10 == 0 else 42 if index % 2 == 0 else 77


def is_mock(index: int, owner_mode: str) -> bool:
    return index % 11 == 0 and not (owner_mode == "old-owner" and index == 0)


def output_id(index: int) -> str:
    return f"out_benchmark{index:012d}"


def seed(args) -> dict:
    root = Path(args.fixture)
    if args.surface == "v2":
        from app.config import settings
        from app.schemas import ImageHistoryItem
        path = settings.image_history_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as target:
            for index in range(args.rows):
                stamp = BASE_TIME + timedelta(seconds=index)
                owner = owner_for(index, args.owner_mode)
                item = ImageHistoryItem(
                    output_id=output_id(index), job_id=f"job_benchmark{index:012d}",
                    provider_id="offline_fixture", model="fixture", prompt="Synthetic read fixture. " * 8,
                    url=f"/api/v2/outputs/{output_id(index)}", created_at=stamp, updated_at=stamp,
                    metadata={"veyra_user_id": owner} if owner else {},
                )
                target.write(item.model_dump_json() + "\n")
    else:
        from app.storage import media_store
        from app.repositories import repository
        from app.repositories.sqlite_json import connect
        from app.schemas import GenerationJob, GenerationOutput, JobStatus
        path = media_store.history_file
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = connect(repository.database_path)
        try:
            with path.open("w", encoding="utf-8") as target, connection:
                for index in range(args.rows):
                    stamp = (BASE_TIME + timedelta(seconds=index)).isoformat()
                    owner = owner_for(index, args.owner_mode)
                    oid = output_id(index)
                    jid = f"job_benchmark{index:012d}"
                    image_path = media_store.output_path(job_id=jid, output_id=oid, output_format="png")
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    image_path.write_bytes(PNG_SHAPED_STUB)
                    epoch = (BASE_TIME + timedelta(seconds=index)).timestamp()
                    os.utime(image_path, (epoch, epoch))
                    mock = args.surface == "lab" and is_mock(index, args.owner_mode)
                    record = dict(id=oid, job_id=jid, session_id=f"ses_benchmark_{index % 10}",
                        format="png", provider="mock_image" if mock else "offline_fixture",
                        model="mock-fixture" if mock else "fixture", prompt="Synthetic read fixture. " * 8,
                        created_at=stamp, updated_at=stamp, url=f"/v1/outputs/{oid}/download")
                    if owner:
                        record["veyra_user_id"] = owner
                    if args.surface == "lab":
                        record.update(source_app="alchemy_lab_rare_style_explorer",
                            alchemy_lab={"idea": "Synthetic fixture", "style_name": "Fixture", "mode": "poster"})
                    target.write(json.dumps(record, ensure_ascii=False) + "\n")
                    if args.surface == "v1":
                        output = GenerationOutput(id=oid, job_id=jid, url=record["url"],
                            metadata={"veyra_user_id": owner} if owner else {})
                        job = GenerationJob(id=jid, session_id=record["session_id"], job_type="image",
                            status=JobStatus.ready, provider="offline_fixture", model="fixture", outputs=[output],
                            trace_id=f"trace_{index}", created_at=stamp, updated_at=stamp)
                        # Bulk insertion only constructs synthetic source records. No API mutation,
                        # generation, events, or writes to existing storage occur.
                        repository.jobs.put_on(connection, jid, job)
                        repository.outputs.put_on(connection, oid, output)
        finally:
            connection.close()
    with path.open("rb") as source:
        source_hash = hashlib.file_digest(source, "sha256").hexdigest()
    return {"rows": args.rows, "surface": args.surface, "owner_mode": args.owner_mode,
        "source_jsonl_sha256": source_hash, "source_jsonl_bytes": path.stat().st_size, "seed": "deterministic-sequential-v1",
        "image_bytes_each": len(PNG_SHAPED_STUB) if args.surface != "v2" else 0,
        "image_stub_sha256": hashlib.sha256(PNG_SHAPED_STUB).hexdigest() if args.surface != "v2" else None,
        "image_stub_note": "PNG-shaped fixed bytes with invalid IDAT checksum; image contents/codecs are excluded",
        "v1_repository_jobs": args.rows if args.surface == "v1" else 0}


def expected(args, owner: int) -> dict:
    indices = []
    for index in range(args.rows - 1, -1, -1):
        record_owner = owner_for(index, args.owner_mode)
        if args.surface == "lab":
            visible = record_owner == owner and (args.include_mock or not is_mock(index, args.owner_mode))
        else:
            visible = record_owner in (None, owner)
        if args.session_id and f"ses_benchmark_{index % 10}" != args.session_id:
            visible = False
        if visible:
            indices.append(index)
    offset = 0 if args.surface == "lab" else args.offset
    return {"total": len(indices), "ids": [output_id(i) for i in indices[offset:offset + args.limit]]}


def proc_io() -> dict:
    try:
        return {k: int(v) for k, v in (line.split(":", 1) for line in Path("/proc/self/io").read_text().splitlines())}
    except OSError:
        return {}


def rss() -> int:
    try:
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError):
        # ru_maxrss is peak rather than current; non-Linux runs are marked unsupported.
        return 0


class Monitor:
    def __init__(self):
        self.stop = threading.Event()
        self.peak = rss()
        self.thread = threading.Thread(target=self._sample, daemon=True)
    def _sample(self):
        while not self.stop.wait(.01):
            self.peak = max(self.peak, rss())
    def start(self):
        self.thread.start()
    def finish(self):
        self.stop.set()
        self.thread.join()
        self.peak = max(self.peak, rss())
        return self.peak


class Diagnostic(AbstractContextManager):
    """Intrusive logical-work instrumentation; use separately from timing runs."""
    def __init__(self, root, *, vm_step_interval=1000):
        self.root = str(Path(root).resolve())
        self.vm_step_interval = vm_step_interval
        self.counts = Counter()
        self.lock = threading.Lock()
        self.restores = []
    def add(self, name, value=1):
        with self.lock:
            self.counts[name] += value
    def inside(self, path):
        try:
            return os.path.abspath(os.fspath(path)).startswith(self.root + os.sep)
        except TypeError:
            return False
    def patch(self, owner, name, value):
        self.restores.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)
    def __enter__(self):
        diagnostic = self
        class Cursor(sqlite3.Cursor):
            def __iter__(self): return self
            def __next__(self):
                row = super().__next__(); diagnostic.add("sql_rows_fetched"); return row
            def fetchone(self):
                row = super().fetchone(); diagnostic.add("sql_rows_fetched", row is not None); return row
            def fetchall(self):
                rows = super().fetchall(); diagnostic.add("sql_rows_fetched", len(rows)); return rows
            def fetchmany(self, *args):
                rows = super().fetchmany(*args); diagnostic.add("sql_rows_fetched", len(rows)); return rows
        class Connection(sqlite3.Connection):
            def cursor(self, factory=Cursor): return super().cursor(factory)
            def execute(self, *args, **kwargs): return self.cursor().execute(*args, **kwargs)
            def executemany(self, *args, **kwargs): return self.cursor().executemany(*args, **kwargs)
            def executescript(self, *args, **kwargs): return self.cursor().executescript(*args, **kwargs)
        original_connect = sqlite3.connect
        def connect(*args, **kwargs):
            kwargs.setdefault("factory", Connection)
            value = original_connect(*args, **kwargs)
            self.add("sql_connections")
            value.set_trace_callback(lambda _statement: self.add("sql_statements"))
            value.set_progress_handler(
                lambda: (self.add("sql_vm_steps_lower_bound", self.vm_step_interval), 0)[1],
                self.vm_step_interval)
            return value
        self.patch(sqlite3, "connect", connect)
        original_loads = json.loads
        def loads(value, *args, **kwargs):
            self.add("json_deserializations")
            self.add("json_input_bytes", len(value.encode("utf-8")) if isinstance(value, str) else len(value))
            return original_loads(value, *args, **kwargs)
        self.patch(json, "loads", loads)
        from pydantic import BaseModel
        for name in ("model_validate_json", "model_validate"):
            original = getattr(BaseModel, name).__func__
            descriptor = BaseModel.__dict__[name]
            self.restores.append((BaseModel, name, descriptor))
            def validate(cls, value, *args, _original=original, _name=name, **kwargs):
                self.add(_name + "_calls")
                return _original(cls, value, *args, **kwargs)
            setattr(BaseModel, name, classmethod(validate))
        original_stat = Path.stat
        def stat(path, *args, **kwargs):
            if self.inside(path): self.add("filesystem_stat_calls")
            return original_stat(path, *args, **kwargs)
        self.patch(Path, "stat", stat)
        original_scandir = os.scandir
        class Scan:
            def __init__(self, inner): self.inner = inner
            def __iter__(self): return self
            def __next__(self):
                value = next(self.inner); diagnostic.add("directory_entries"); return value
            def __enter__(self): return self
            def __exit__(self, *args): self.inner.close()
            def close(self): self.inner.close()
        def scandir(path):
            result = original_scandir(path)
            if self.inside(path):
                self.add("filesystem_scandir_calls")
                return Scan(result)
            return result
        self.patch(os, "scandir", scandir)
        original_open = Path.open
        class File:
            def __init__(self, inner): self.inner = inner
            def __getattr__(self, name): return getattr(self.inner, name)
            def __enter__(self): self.inner.__enter__(); return self
            def __exit__(self, *args): return self.inner.__exit__(*args)
            def record(self, value):
                diagnostic.add("logical_file_bytes_read", len(value.encode("utf-8")) if isinstance(value, str) else len(value))
                return value
            def read(self, *args): return self.record(self.inner.read(*args))
            def readline(self, *args): return self.record(self.inner.readline(*args))
            def readlines(self, *args): return [self.record(line) for line in self.inner.readlines(*args)]
            def __iter__(self): return self
            def __next__(self): return self.record(next(self.inner))
        def open_file(path, *args, **kwargs):
            result = original_open(path, *args, **kwargs)
            if self.inside(path):
                self.add("filesystem_open_calls")
                return File(result)
            return result
        self.patch(Path, "open", open_file)
        return self
    def __exit__(self, *args):
        for owner, name, original in reversed(self.restores): setattr(owner, name, original)


def percentile(values, quantile):
    if not values: return None
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)]


def packages():
    result = {}
    for name in ("fastapi", "pydantic", "openai-agents", "mcp"):
        try: result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: result[name] = None
    return result


def reject_generated_content_reads(root):
    """Assert list handlers stay on metadata/SQL, never image bytes or codecs."""
    generated = str((Path(root) / "v1/generated_images").resolve()) + os.sep
    attempts = {"generated_file_content_opens": 0, "image_codec_calls": 0}
    def audit(event, arguments):
        if event != "open" or not arguments:
            return
        try:
            path = os.path.abspath(os.fsdecode(arguments[0]))
        except TypeError:
            return  # A numeric descriptor does not identify a generated path.
        if path.startswith(generated):
            attempts["generated_file_content_opens"] += 1
            raise AssertionError("History listing attempted to open generated image contents")
    sys.addaudithook(audit)
    def no_codec(*_args, **_kwargs):
        attempts["image_codec_calls"] += 1
        raise AssertionError("History listing attempted image decoding")
    from PIL import Image
    Image.open = no_codec
    if "cv2" in sys.modules:
        sys.modules["cv2"].imread = no_codec
        sys.modules["cv2"].imdecode = no_codec
    return attempts


async def endpoint_worker(args) -> dict:
    import_started = time.perf_counter()
    import app.main as main
    from app.repositories.sqlite_calls import sqlite_calls
    import_seconds = time.perf_counter() - import_started
    content_read_attempts = reject_generated_content_reads(args.fixture)
    # Calls are actual async GET handlers. Only external auth lookup is replaced
    # with an explicit synthetic owner, as in existing API tests; no lifespan.
    async def context(request, *_args, **_kwargs):
        return {"authenticated": True, "user_id": request.owner, "is_admin": False}
    if args.surface == "v2":
        main._veyra_request_context = context
        from app.config import settings
        assert Path(settings.image_history_path).is_relative_to(args.fixture)
        endpoint = main.image_history
    else:
        main._veyra_history_context = context
        assert Path(main.media_store.root).is_relative_to(args.fixture)
        endpoint = main.list_alchemy_lab_history if args.surface == "lab" else main.list_image_history
    if args.admission == "immediate" and hasattr(sqlite_calls, "run_read"):
        sqlite_calls.run_read = sqlite_calls.run
    application_counts = Counter()
    application_lock = threading.Lock()
    if args.diagnostic and args.surface in {"v1", "lab"}:
        try:
            from app.repositories.history_index import HistoryReadMetrics
        except ImportError:
            pass  # Immutable baseline has no native projection counters.
        else:
            name = "_list_image_history_sync" if args.surface == "v1" else "list_lab_history"
            original = getattr(main, name)
            def observed(*a, **kw):
                metrics = HistoryReadMetrics()
                try:
                    return original(*a, **kw, metrics=metrics)
                finally:
                    with application_lock:
                        application_counts.update(asdict(metrics))
            setattr(main, name, observed)
    expectations = {owner: expected(args, owner) for owner in (42, 77)}
    async def request(owner):
        kwargs = dict(request=SimpleNamespace(owner=owner), limit=args.limit, authorization="")
        if args.surface == "lab": kwargs["include_mock"] = args.include_mock
        else: kwargs["offset"] = args.offset
        if args.surface == "v1": kwargs["session_id"] = args.session_id
        value = await endpoint(**kwargs)
        return value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    def check(payload, owner):
        identifiers = [item.get("id", item.get("output_id")) for item in payload["items"]]
        observed = {"total": payload["total"], "ids": identifiers}
        return observed == expectations[owner], observed
    process_cold = None
    if args.worker != "cold":
        started = time.perf_counter()
        value = await request(42)
        valid, actual = check(value, 42)
        process_cold = {"seconds": time.perf_counter() - started, "correct": valid, "observed": actual}
        del value
        # Both owners warm before measuring hot batches; retain no responses.
        value = await request(77)
        del value
    application_counts.clear()
    gc.collect()
    io_before = proc_io(); rss_before = rss(); usage_before = resource.getrusage(resource.RUSAGE_SELF)
    monitor = Monitor(); monitor.start()
    gate_before = sqlite_calls.snapshot() if hasattr(sqlite_calls, "snapshot") else {}
    samples = []; failures = []; mismatches = []; hashes = set(); heartbeat = []
    stop = asyncio.Event(); batch_rss = []
    async def beat():
        last = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(.01)
            current = time.perf_counter(); heartbeat.append(current - last); last = current
    async def measured(owner):
        started = time.perf_counter()
        try:
            payload = await request(owner)
        except Exception as exc:
            failures.append({"seconds": time.perf_counter() - started,
                "type": type(exc).__name__, "status": getattr(exc, "status_code", None),
                "detail": str(getattr(exc, "detail", exc))})
            return
        samples.append(time.perf_counter() - started)
        valid, actual = check(payload, owner)
        if not valid and len(mismatches) < 5:
            mismatches.append({"owner": owner, "observed": actual, "expected": expectations[owner]})
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
        hashes.add((owner, hashlib.sha256(canonical).hexdigest()))
    ticker = asyncio.create_task(beat())
    diagnostics = Diagnostic(args.fixture, vm_step_interval=args.vm_step_interval) if args.diagnostic else None
    if diagnostics: diagnostics.__enter__()
    started = time.perf_counter(); cpu_started = time.process_time()
    rounds = 1 if args.worker == "cold" else args.rounds
    concurrency = 1 if args.worker == "cold" else args.parallel
    try:
        for _ in range(rounds):
            await asyncio.gather(*(measured(42 if i % 2 == 0 else 77) for i in range(concurrency)))
            batch_rss.append(rss())
    finally:
        wall = time.perf_counter() - started; cpu = time.process_time() - cpu_started
        if diagnostics: diagnostics.__exit__()
        stop.set(); await ticker
    peak = monitor.finish(); rss_after = rss(); usage_after = resource.getrusage(resource.RUSAGE_SELF)
    gate_after = sqlite_calls.snapshot() if hasattr(sqlite_calls, "snapshot") else {}
    io_after = proc_io(); gc.collect(); await asyncio.sleep(.05); rss_gc = rss()
    result = dict(surface=args.surface, rows=args.rows, concurrency=concurrency, rounds=rounds,
        phase="logical_cold_index_first_read" if args.worker == "cold" else "hot_pages",
        admission=args.admission, diagnostic=bool(diagnostics), page_size=args.limit, offset=args.offset,
        diagnostic_vm_step_interval=args.vm_step_interval if diagnostics else None,
        owner_mode=args.owner_mode, offered=rounds * concurrency, succeeded=len(samples), failed=len(failures),
        status_503=sum(f["status"] == 503 for f in failures), failures=failures[:20],
        correctness=not mismatches and bool(samples) and (process_cold is None or process_cold["correct"]), mismatches=mismatches,
        response_hashes=[{"owner": owner, "sha256": value} for owner, value in sorted(hashes)],
        wall_seconds=wall, cpu_seconds=cpu,
        user_cpu_seconds=usage_after.ru_utime-usage_before.ru_utime,
        system_cpu_seconds=usage_after.ru_stime-usage_before.ru_stime,
        successful_requests_per_second=len(samples)/wall,
        cpu_seconds_per_success=cpu/len(samples) if samples else None,
        p50_seconds=statistics.median(samples) if samples else None,
        p95_seconds=percentile(samples, .95) if len(samples) >= 100 else None, max_seconds=max(samples, default=None),
        error_p95_seconds=percentile([f["seconds"] for f in failures], .95),
        heartbeat_p95_seconds=percentile(heartbeat, .95), heartbeat_max_seconds=max(heartbeat, default=None),
        rss_before_bytes=rss_before, rss_peak_bytes=peak, rss_after_bytes=rss_after, rss_post_gc_bytes=rss_gc,
        rss_batch_end_bytes=batch_rss, process_cold_built_index=process_cold,
        io_delta={key: io_after[key]-io_before.get(key, 0) for key in io_after},
        gate_before=gate_before, gate_after=gate_after,
        gate_counter_delta={key: gate_after[key]-gate_before.get(key, 0) for key in gate_after
            if key not in {"pending", "running", "inflight"} and not key.startswith(("peak_", "max_"))},
        work_counts=dict(diagnostics.counts) if diagnostics else {},
        application_work_counts=dict(application_counts), content_read_attempts=content_read_attempts,
        startup_import_seconds=import_seconds,
        packages=packages(), python=sys.version, sqlite=sqlite3.sqlite_version,
        affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        fewer_than_100_success_samples=len(samples) < 100,
        storage_bytes=sum(p.stat().st_size for p in Path(args.fixture).rglob("*") if p.is_file()),
    )
    # Do not retain a sampled peak as evidence of post-quiescence allocation leaks.
    if hasattr(sqlite_calls, "shutdown"):
        await asyncio.to_thread(sqlite_calls.shutdown)
    else:
        await asyncio.to_thread(sqlite_calls._executor.shutdown, True)
    return result


def storage_inventory(repo):
    result = {}
    for relative in (".media_storage", "src_skeleton/.media_storage", "custom_media_agent_2_0/.v2_data",
                     "custom_media_agent_2_0/.v2_storage", ".env", "src_skeleton/.env", "custom_media_agent_2_0/.env"):
        root = repo / relative
        if root.exists():
            for path in (root, *root.rglob("*")) if root.is_dir() else (root,):
                info = path.stat()
                result[str(path.relative_to(repo))] = (path.is_dir(), info.st_size, info.st_mtime_ns)
    return result


def source_fingerprint(repo):
    digest = hashlib.sha256()
    for base in ("src_skeleton/app", "custom_media_agent_2_0/app"):
        for path in sorted((repo/base).rglob("*.py")):
            digest.update(str(path.relative_to(repo)).encode()); digest.update(b"\0"); digest.update(path.read_bytes())
    return digest.hexdigest()


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--v1-python", default=sys.executable); parser.add_argument("--v2-python", default=sys.executable)
    parser.add_argument("--sizes", default="100,1000,10000,50000")
    parser.add_argument("--concurrency", default="2,4,8"); parser.add_argument("--surfaces", default="v1,lab,v2")
    parser.add_argument("--rounds", type=int, default=10); parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0); parser.add_argument("--session-id")
    parser.add_argument("--include-mock", action="store_true")
    parser.add_argument("--owner-mode", choices=["balanced", "old-owner"], default="balanced")
    parser.add_argument("--admission", choices=["read", "immediate"], default="read")
    parser.add_argument("--diagnostic", action="store_true",
        help="Add separate instrumented hot passes; keep cold-build timing uninstrumented")
    parser.add_argument("--diagnostic-cold", action="store_true",
        help="Instrument the cold build instead of measuring comparable cold-build latency")
    parser.add_argument("--vm-step-interval", type=int, default=1000,
        help="Diagnostic SQLite progress-callback interval; smaller values increase measurement overhead")
    parser.add_argument("--cpus")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", choices=["seed", "cold", "hot"])
    parser.add_argument("--fixture", type=Path); parser.add_argument("--result", type=Path)
    parser.add_argument("--surface", choices=["v1", "lab", "v2"]); parser.add_argument("--rows", type=int)
    parser.add_argument("--parallel", type=int, default=2)
    args = parser.parse_args(); args.repo = args.repo.resolve()
    if args.rounds < 1 or not 1 <= args.limit <= 200 or args.offset < 0 or not 1 <= args.vm_step_interval <= 10000:
        parser.error("rounds >= 1, 1 <= limit <= 200, offset >= 0 and 1 <= vm-step-interval <= 10000 are required")
    if args.cpus: os.sched_setaffinity(0, {int(value) for value in args.cpus.split(",")})
    if args.worker:
        if args.fixture is None or args.result is None or args.surface is None or args.rows is None or not 1 <= args.rows <= 50000:
            parser.error("Workers require fixture, result, surface and rows between 1 and 50000")
        args.fixture = args.fixture.resolve()
        if not args.fixture.is_relative_to(Path(tempfile.gettempdir()).resolve()) or args.fixture.is_relative_to(args.repo):
            parser.error("Fixture workers require a new directory under the system temporary directory, outside the checkout")
        marker = args.fixture / ".history-read-fixture.json"
        identity = {"schema": 1, "surface": args.surface, "rows": args.rows, "owner_mode": args.owner_mode}
        if args.worker == "seed":
            # Never truncate an existing history file, even for a manually invoked
            # private worker. The controller always allocates a fresh child path.
            args.fixture.mkdir(parents=True, exist_ok=False)
            marker.write_text(json.dumps(identity), encoding="utf-8")
        elif not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")) != identity:
            parser.error("Read workers require the matching synthetic-fixture marker from a seed worker")
        isolate(args.fixture); forbid_network_and_dotenv(); os.chdir(args.fixture)
        sys.dont_write_bytecode = True
        source = "custom_media_agent_2_0" if args.surface == "v2" else "src_skeleton"
        sys.path[:0] = [str(args.repo/source), str(args.repo)]
        result = seed(args) if args.worker == "seed" else asyncio.run(endpoint_worker(args))
        args.result.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return
    sizes = [int(value) for value in args.sizes.split(",")]
    concurrent = [int(value) for value in args.concurrency.split(",")]
    surfaces = args.surfaces.split(",")
    if any(n < 1 or n > 50000 for n in sizes) or any(c < 1 or c > 8 for c in concurrent):
        parser.error("rows must be 1..50000 and concurrency 1..8")
    if any(s not in {"v1", "lab", "v2"} for s in surfaces): parser.error("Unknown surface")
    if args.session_id and surfaces != ["v1"]: parser.error("session-id applies only to the V1-only matrix")
    before = storage_inventory(args.repo); fingerprint = source_fingerprint(args.repo)
    started_at = datetime.now(timezone.utc).isoformat()
    runs = []; fixtures = []
    with tempfile.TemporaryDirectory(prefix="history-read-benchmark-") as temporary:
        root = Path(temporary)
        for surface in surfaces:
            executable = args.v2_python if surface == "v2" else args.v1_python
            for size in sizes:
                fixture = root/f"{surface}-{size}"
                common = [executable, str(Path(__file__).resolve()), "--repo", str(args.repo), "--surface", surface,
                    "--rows", str(size), "--fixture", str(fixture), "--rounds", str(args.rounds),
                    "--limit", str(args.limit), "--offset", str(args.offset), "--owner-mode", args.owner_mode,
                    "--admission", args.admission, "--vm-step-interval", str(args.vm_step_interval)]
                if args.include_mock: common.append("--include-mock")
                if args.session_id: common += ["--session-id", args.session_id]
                cases = [("seed", 1, False), ("cold", 1, args.diagnostic_cold)]
                cases += [("hot", c, False) for c in concurrent]
                if args.diagnostic: cases += [("hot", c, True) for c in concurrent]
                for index, (mode, parallel, diagnostic) in enumerate(cases):
                    destination = root/f"result-{surface}-{size}-{index}.json"
                    command = common + ["--worker", mode, "--parallel", str(parallel), "--result", str(destination)]
                    if diagnostic: command.append("--diagnostic")
                    subprocess.run(command, check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
                    value = json.loads(destination.read_text(encoding="utf-8"))
                    (fixtures if mode == "seed" else runs).append(value)
                    print(f"{surface} rows={size} phase={mode} concurrency={parallel} diagnostic={diagnostic}", file=sys.stderr)
        unchanged = before == storage_inventory(args.repo)
        if not unchanged: raise AssertionError("Benchmark changed checkout default storage")
    report = {"fixture_id_contract": "out_/job_ followed by alphanumeric characters only; accepted by real filesystem recovery", "scope": "Temporary synthetic data; direct async GET handlers; no HTTP transport, real auth, lifespan, Provider or production operations.",
        "image_scope": "Identical 68-byte PNG-shaped stubs, invalid IDAT checksum; lists assert no image-content opens or decoding. Thumbnail/preview codecs and browser rendering are excluded.",
        "cache_note": "Fixture creation warms OS cache. Logical cold is index/import absence, not disk-cold. Hot phases use fresh subprocesses and explicit owner warmup.",
        "measurement_note": "Diagnostic counts are separate from uninstrumented timing. SQL rows fetched and VM-step lower bounds are not exact engine rows scanned; native SQLite I/O uses process counters.",
        "rss_note": "RSS plateau after GC may be allocator reuse. This benchmark alone cannot prove a leak or VPS suitability.",
        "platform": platform.platform(), "source_fingerprint": fingerprint,
        "started_at_utc": started_at, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "configuration": {"sizes": sizes, "concurrency": concurrent, "surfaces": surfaces,
            "rounds": args.rounds, "page_size": args.limit, "offset": args.offset,
            "session_id": args.session_id, "include_mock": args.include_mock,
            "owner_mode": args.owner_mode, "admission": args.admission,
            "diagnostic_hot": args.diagnostic, "diagnostic_cold": args.diagnostic_cold,
            "vm_step_interval": args.vm_step_interval},
        "source_unchanged_during_run": fingerprint == source_fingerprint(args.repo),
        "checkout_default_storage_unchanged": unchanged, "fixtures": fixtures, "runs": runs}
    encoded = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output: args.output.resolve().write_text(encoded + "\n", encoding="utf-8")
    else: print(encoded)


if __name__ == "__main__":
    cli()
