from __future__ import annotations

import sqlite3
import threading
from dataclasses import replace
from datetime import timedelta, timezone, datetime
from pathlib import Path

import pytest

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CreativeRun
from app.services import task_queue


def _run(run_id: str) -> CreativeRun:
    now = utc_now()
    return CreativeRun(
        run_id=run_id,
        status="generating",
        mode="smart_enhance",
        intent_summary="offline queue claim test",
        trace_id=f"trace_{run_id}",
        created_at=now,
        updated_at=now,
    )


def _configure_queue(tmp_path: Path, monkeypatch, *, name: str = "queue.sqlite3", timeout: float = 5.0, slots: int = 1):
    database_path = tmp_path / name
    monkeypatch.setattr(
        task_queue,
        "settings",
        replace(
            settings,
            task_queue_db_path=database_path,
            task_queue_claim_timeout_seconds=timeout,
            task_queue_max_attempts=4,
            task_queue_max_pending=20,
            max_concurrent_image_generations=slots,
        ),
    )
    task_queue.initialize_task_queue()
    return database_path


def _enqueue(run_id: str) -> str:
    run = _run(run_id)
    return task_queue.enqueue_creative_task(
        kind="creative_run",
        request_payload={"user_prompt": "offline fake"},
        queued_run=run,
    )


def _make_stale(claim) -> None:
    stale_locked_at = (utc_now() - timedelta(days=1)).isoformat()
    with task_queue._connect() as connection:
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            (stale_locked_at, claim.task_id),
        )


@pytest.mark.parametrize("action", ["complete", "fail", "retry", "snapshot", "release"])
def test_superseded_claim_cannot_mutate_new_attempt(tmp_path: Path, monkeypatch, action: str) -> None:
    _configure_queue(tmp_path, monkeypatch, name=f"{action}.sqlite3")
    run_id = f"run_fenced_{action}"
    _enqueue(run_id)
    old_claim = task_queue.claim_next_task("worker-old")
    assert old_claim is not None
    _make_stale(old_claim)
    new_claim = task_queue.claim_next_task("worker-new")
    assert new_claim is not None
    assert new_claim.task_id == old_claim.task_id
    assert new_claim.claim_token != old_claim.claim_token

    run = _run(f"{run_id}_stale-write")
    if action == "complete":
        changed = task_queue.complete_task(old_claim, run)
    elif action == "fail":
        changed = task_queue.fail_task(old_claim, "stale error", run)
    elif action == "retry":
        changed = task_queue.retry_task(old_claim, "stale retry", run, retry_delay_seconds=60)
    elif action == "snapshot":
        changed = task_queue.update_task_snapshot(run, claim=old_claim)
    else:
        changed = task_queue.release_task(old_claim)

    assert changed is False
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT status, attempts, locked_by, claim_token, result_json, error_json FROM v2_tasks WHERE task_id = ?",
            (old_claim.task_id,),
        ).fetchone()
    assert row["status"] == "running"
    assert row["attempts"] == new_claim.attempts
    assert row["locked_by"] == "worker-new"
    assert row["claim_token"] == new_claim.claim_token
    assert row["result_json"] is None
    assert row["error_json"] is None
    snapshot = task_queue.get_run_snapshot(run_id)
    assert snapshot is not None and snapshot.run_id == run_id


def test_v2_queued_billing_idempotency_is_stable_across_worker_job_ids(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from app.services import generation

    _configure_queue(tmp_path, monkeypatch)
    _enqueue("run_billing_idempotency")
    claim = task_queue.claim_next_task("worker-billing")
    assert claim is not None
    rule = SimpleNamespace(key="alchemy:v2")

    with task_queue.claimed_task(claim):
        first_attempt = generation._billing_idempotency_key(rule, "job_attempt_one")
        second_attempt = generation._billing_idempotency_key(rule, "job_attempt_two")
        first_reference = generation._billing_reference_id("job_attempt_one")
        second_reference = generation._billing_reference_id("job_attempt_two")

    assert first_attempt == second_attempt == f"alchemy:v2:task:{claim.task_id}"
    assert first_reference == second_reference == claim.task_id
    assert generation._billing_idempotency_key(rule, "job_direct") == "alchemy:v2:image:job_direct"
    assert generation._billing_reference_id("job_direct") == "job_direct"


def test_claim_write_fence_prevents_takeover_during_local_commit(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch)
    _enqueue("run_claim_commit_fence")
    claim = task_queue.claim_next_task("worker-commit")
    assert claim is not None

    commit_started = threading.Event()
    allow_commit = threading.Event()
    takeover_finished = threading.Event()
    committed: list[str] = []
    replacement_claims = []

    def local_commit() -> str:
        commit_started.set()
        assert allow_commit.wait(3)
        committed.append("saved")
        return "saved"

    def persist() -> None:
        with task_queue.claimed_task(claim):
            assert task_queue.persist_claimed_operation(local_commit) == "saved"

    def take_over() -> None:
        _make_stale(claim)
        replacement_claims.append(task_queue.claim_next_task("worker-replacement-commit"))
        takeover_finished.set()

    persister = threading.Thread(target=persist, daemon=True)
    persister.start()
    assert commit_started.wait(2)
    takeover = threading.Thread(target=take_over, daemon=True)
    takeover.start()
    try:
        assert not takeover_finished.wait(0.1)
    finally:
        allow_commit.set()
    persister.join(3)
    takeover.join(3)

    assert not persister.is_alive()
    assert not takeover.is_alive()
    assert committed == ["saved"]
    assert takeover_finished.is_set()
    assert replacement_claims[0] is not None
    assert replacement_claims[0].claim_token != claim.claim_token


def test_legacy_queue_schema_adds_claim_fencing_columns(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(
        task_queue,
        "settings",
        replace(settings, task_queue_db_path=database_path),
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE v2_tasks (
                task_id TEXT PRIMARY KEY, kind TEXT NOT NULL, run_id TEXT NOT NULL,
                status TEXT NOT NULL, payload_json TEXT NOT NULL, queued_run_json TEXT NOT NULL,
                result_json TEXT, error_json TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3, locked_by TEXT, locked_at TEXT,
                not_before TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )
    task_queue.initialize_task_queue()
    with task_queue._connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(v2_tasks)")}
    assert {"claim_token", "claim_generation", "success_checkpoint_json"} <= columns


def test_legacy_queue_schema_migration_is_serialized_across_initializers(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "legacy_concurrent.sqlite3"
    monkeypatch.setattr(
        task_queue,
        "settings",
        replace(settings, task_queue_db_path=database_path, task_queue_busy_timeout_seconds=5.0),
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE v2_tasks (
                task_id TEXT PRIMARY KEY, kind TEXT NOT NULL, run_id TEXT NOT NULL,
                status TEXT NOT NULL, payload_json TEXT NOT NULL, queued_run_json TEXT NOT NULL,
                result_json TEXT, error_json TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3, locked_by TEXT, locked_at TEXT,
                not_before TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )

    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def initialize() -> None:
        try:
            start.wait(timeout=3)
            task_queue.initialize_task_queue()
        except BaseException as exc:
            errors.append(exc)

    workers = [threading.Thread(target=initialize) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(8)
    assert all(not worker.is_alive() for worker in workers)
    assert errors == []
    with task_queue._connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(v2_tasks)")}
    assert {"claim_token", "claim_generation"} <= columns


def test_claim_heartbeat_refreshes_active_attempt_before_recovery(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch, timeout=3.0)
    _enqueue("run_heartbeat_fresh")
    claim = task_queue.claim_next_task("worker-heartbeat")
    assert claim is not None
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = [start]
    monkeypatch.setattr(task_queue, "utc_now", lambda: clock[0])
    clock[0] = start + timedelta(seconds=20)

    assert task_queue.refresh_task_claim(claim) is True
    clock[0] = start + timedelta(seconds=22)
    assert task_queue.claim_next_task("replacement") is None
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT locked_at, claim_generation FROM v2_tasks WHERE task_id = ?",
            (claim.task_id,),
        ).fetchone()
    assert row["locked_at"] == clock[0].replace(second=20).isoformat()
    assert row["claim_generation"] == 1


def test_claim_heartbeat_covers_preflight_provider_and_terminal_persistence(tmp_path: Path, monkeypatch) -> None:
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch, timeout=3.0)
    _enqueue("run_heartbeat_lifecycle")
    refresh_count = 0
    refresh_condition = threading.Condition()
    original_refresh = task_queue.refresh_task_claim

    def observed_refresh(claim):
        nonlocal refresh_count
        result = original_refresh(claim)
        with refresh_condition:
            refresh_count += 1
            refresh_condition.notify_all()
        return result

    monkeypatch.setattr(task_queue, "refresh_task_claim", observed_refresh)

    def wait_for_refresh(target: int) -> None:
        with refresh_condition:
            assert refresh_condition.wait_for(lambda: refresh_count >= target, timeout=3)

    preflight_started = threading.Event()
    continue_preflight = threading.Event()
    provider_started = threading.Event()
    continue_provider = threading.Event()
    finalize_started = threading.Event()

    async def fake_preflight(_request, _run_id):
        preflight_started.set()
        await asyncio.to_thread(continue_preflight.wait, 3)
        return None

    class Runtime:
        async def complete_queued_run(self, _request, run_id: str):
            provider_started.set()
            await asyncio.to_thread(continue_provider.wait, 3)
            return _run(run_id)

    import asyncio

    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", fake_preflight)
    original_complete = task_queue.complete_task

    def observed_complete(claim, run):
        finalize_started.set()
        wait_for_refresh(refresh_count + 1)
        return original_complete(claim, run)

    monkeypatch.setattr(task_queue, "complete_task", observed_complete)
    interval = 0.02
    result: list[bool] = []
    worker = threading.Thread(
        target=lambda: result.append(queue_worker.process_next_task_once(Runtime(), "worker-long")),
        daemon=True,
    )
    monkeypatch.setattr(task_queue, "claim_heartbeat_interval_seconds", lambda: interval)
    worker.start()
    assert preflight_started.wait(3)
    wait_for_refresh(1)
    continue_preflight.set()
    assert provider_started.wait(3)
    wait_for_refresh(2)
    continue_provider.set()
    assert finalize_started.wait(3)
    wait_for_refresh(3)
    worker.join(3)
    assert not worker.is_alive()
    assert result == [True]
    with task_queue._connect() as connection:
        terminal = connection.execute(
            "SELECT status, claim_token FROM v2_tasks WHERE run_id = ?",
            ("run_heartbeat_lifecycle",),
        ).fetchone()
    assert terminal["status"] == "completed"
    assert terminal["claim_token"] is None


def test_lost_claim_during_preflight_is_rechecked_before_provider(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch, timeout=1.0)
    _enqueue("run_claim_lost_preflight")
    preflight_started = threading.Event()
    continue_preflight = threading.Event()
    provider_calls = 0

    async def fake_preflight(_request, _run_id):
        preflight_started.set()
        await asyncio.to_thread(continue_preflight.wait, 3)
        return None

    class Runtime:
        async def complete_queued_run(self, _request, _run_id: str):
            nonlocal provider_calls
            provider_calls += 1
            return _run("run_claim_lost_preflight")

    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", fake_preflight)
    result: list[bool] = []
    worker = threading.Thread(
        target=lambda: result.append(queue_worker.process_next_task_once(Runtime(), "worker-old")),
        daemon=True,
    )
    worker.start()
    assert preflight_started.wait(3)
    with task_queue._connect() as connection:
        claim_row = connection.execute(
            "SELECT task_id FROM v2_tasks WHERE run_id = ?", ("run_claim_lost_preflight",)
        ).fetchone()
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            ((utc_now() - timedelta(days=1)).isoformat(), claim_row["task_id"]),
        )
    replacement = task_queue.claim_next_task("worker-replacement")
    assert replacement is not None
    continue_preflight.set()
    worker.join(3)
    assert not worker.is_alive()
    assert result == [True]
    assert provider_calls == 0
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT status, locked_by, claim_token FROM v2_tasks WHERE task_id = ?",
            (replacement.task_id,),
        ).fetchone()
    assert row["status"] == "running"
    assert row["locked_by"] == "worker-replacement"
    assert row["claim_token"] == replacement.claim_token


def test_lost_claim_during_insufficient_balance_preflight_writes_no_repository_records(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from app.repositories import repository
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch, timeout=1.0)
    repository.reset()
    _enqueue("run_claim_lost_insufficient_balance")
    preflight_started = threading.Event()
    continue_preflight = threading.Event()
    job_ids: list[str] = []

    async def insufficient_balance_preflight(request, run_id):
        preflight_started.set()
        await asyncio.to_thread(continue_preflight.wait, 3)
        run = queue_worker._veyra_balance_failed_run(request, run_id)
        job_ids.extend(job.job_id for job in run.generation_jobs)
        return run

    class Runtime:
        async def complete_queued_run(self, _request, _run_id: str):
            raise AssertionError("lost claim must stop before creative provider work")

    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", insufficient_balance_preflight)
    result: list[bool] = []
    worker = threading.Thread(
        target=lambda: result.append(queue_worker.process_next_task_once(Runtime(), "worker-old")),
        daemon=True,
    )
    worker.start()
    assert preflight_started.wait(3)
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT task_id FROM v2_tasks WHERE run_id = ?", ("run_claim_lost_insufficient_balance",)
        ).fetchone()
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            ((utc_now() - timedelta(days=1)).isoformat(), row["task_id"]),
        )
    replacement = task_queue.claim_next_task("worker-replacement")
    assert replacement is not None
    continue_preflight.set()
    worker.join(3)
    assert not worker.is_alive()
    assert result == [True]
    assert len(job_ids) == 1
    assert repository.get_image_job(job_ids[0]) is None
    assert repository.get_creative_run("run_claim_lost_insufficient_balance") is None
    repository.reset()


def test_current_claim_persists_insufficient_balance_preflight_without_provider_work(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from app.repositories import repository
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch)
    repository.reset()
    _enqueue("run_current_insufficient_balance")

    async def insufficient_balance_preflight(request, run_id):
        return queue_worker._veyra_balance_failed_run(request, run_id)

    class Runtime:
        async def complete_queued_run(self, _request, _run_id: str):
            raise AssertionError("insufficient balance must stop before creative provider work")

    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", insufficient_balance_preflight)
    assert queue_worker.process_next_task_once(Runtime(), "worker-balance") is True
    saved_run = repository.get_creative_run("run_current_insufficient_balance")
    assert saved_run is not None and saved_run.status == "failed"
    assert len(saved_run.generation_jobs) == 1
    saved_job = repository.get_image_job(saved_run.generation_jobs[0].job_id)
    assert saved_job is not None and saved_job.status == "failed"
    assert task_queue.get_run_snapshot("run_current_insufficient_balance").status == "failed"
    repository.reset()


def test_lost_claim_during_provider_does_not_commit_job_output_history_or_charge(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import base64
    from io import BytesIO
    from types import SimpleNamespace

    from PIL import Image

    from app.providers.images.base import V2ImageProviderOutput, V2ImageProviderResult
    from app.repositories import repository
    from app.schemas import CreateImageJobRequest, ImagePromptPlan
    from app.services import generation, image_history, output_storage, queue_worker, veyra_usage

    database_path = tmp_path / "provider-fence.sqlite3"
    runtime_settings = replace(
        settings,
        task_queue_db_path=database_path,
        task_queue_claim_timeout_seconds=30.0,
        task_queue_max_attempts=4,
        task_queue_max_pending=20,
        max_concurrent_image_generations=1,
        storage_dir=tmp_path / "storage",
        image_history_path=tmp_path / "image_history.jsonl",
        veyra_usage_path=tmp_path / "veyra_usage.jsonl",
        persist_image_history=True,
        veyra_auth_enabled=True,
    )
    monkeypatch.setattr(task_queue, "settings", runtime_settings)
    monkeypatch.setattr(queue_worker, "settings", runtime_settings)
    monkeypatch.setattr(generation, "settings", runtime_settings)
    monkeypatch.setattr(output_storage, "settings", runtime_settings)
    monkeypatch.setattr(image_history, "settings", runtime_settings)
    monkeypatch.setattr(veyra_usage, "settings", runtime_settings)
    task_queue.initialize_task_queue()
    repository.reset()

    run_id = "run_claim_lost_during_provider"
    queued_run = _run(run_id)
    task_queue.enqueue_creative_task(
        kind="creative_run",
        request_payload={"user_prompt": "offline fake"},
        queued_run=queued_run,
    )

    provider_started = threading.Event()
    finish_provider = threading.Event()
    provider_image = BytesIO()
    Image.new("RGB", (16, 16), "white").save(provider_image, format="PNG")
    encoded_png = base64.b64encode(provider_image.getvalue()).decode("ascii")

    class FakeProvider:
        name = "fake_image"

        async def generate(self, _request):
            provider_started.set()
            await asyncio.to_thread(finish_provider.wait, 5)
            return V2ImageProviderResult(
                provider=self.name,
                model="fake-image-v1",
                outputs=[V2ImageProviderOutput(b64_json=encoded_png, mime_type="image/png", format="png")],
            )

    monkeypatch.setattr(generation, "get_v2_image_provider", lambda _hint: asyncio.sleep(0, result=FakeProvider()))
    monkeypatch.setattr(generation, "_ensure_veyra_balance", lambda **_kwargs: asyncio.sleep(0))
    monkeypatch.setattr(
        generation,
        "get_billing_rule",
        lambda _key: SimpleNamespace(key="alchemy:v2", enabled=True, charge_amount=1.0, source="alchemy"),
    )
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *_args, **_kwargs: True)
    debit_calls: list[dict] = []

    class FakeBillingClient:
        async def debit(self, **kwargs):
            debit_calls.append(kwargs)
            return SimpleNamespace(
                user_id=17,
                amount=1.0,
                balance_after=9.0,
                idempotency_key=kwargs["idempotency_key"],
                replayed=False,
            )

    monkeypatch.setattr(generation, "VeyraSub2APIClient", FakeBillingClient)

    claim_by_worker = {}
    original_claim = task_queue.claim_next_task

    def observe_claim(worker_id: str):
        claim = original_claim(worker_id)
        if claim is not None:
            claim_by_worker[worker_id] = claim
        return claim

    monkeypatch.setattr(task_queue, "claim_next_task", observe_claim)
    monkeypatch.setattr(task_queue, "claim_heartbeat_interval_seconds", lambda: 30.0)

    class Runtime:
        async def complete_queued_run(self, _request, active_run_id: str):
            image_request = CreateImageJobRequest(
                run_id=active_run_id,
                prompt_plan=ImagePromptPlan(
                    plan_id="plan_claim_loss_provider",
                    mode="smart_enhance",
                    prompt="Offline fake provider output.",
                ),
                provider_hint="fake_image",
                veyra_user_id=17,
            )
            running_job = await generation.create_running_image_job(image_request)
            job = await generation.create_image_job(
                image_request,
                job_id=running_job.job_id,
                created_at=running_job.created_at,
            )
            return _run(active_run_id).model_copy(update={"status": "completed", "generation_jobs": [job]})

    result: list[bool] = []
    worker = threading.Thread(
        target=lambda: result.append(queue_worker.process_next_task_once(Runtime(), "worker-old-provider")),
        daemon=True,
    )
    worker.start()
    try:
        assert provider_started.wait(3)
        old_claim = claim_by_worker["worker-old-provider"]
        _make_stale(old_claim)
        replacement = original_claim("worker-replacement-provider")
        assert replacement is not None
    finally:
        finish_provider.set()

    worker.join(5)
    assert not worker.is_alive()
    assert result == [True]
    assert debit_calls == []
    assert repository.image_jobs == {}
    assert repository.outputs == {}
    assert not runtime_settings.image_history_path.exists()
    output_root = runtime_settings.storage_dir / "outputs"
    assert not output_root.exists() or next(output_root.iterdir(), None) is None
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT status, locked_by, claim_token, result_json FROM v2_tasks WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert row["status"] == "running"
    assert row["locked_by"] == "worker-replacement-provider"
    assert row["claim_token"] == replacement.claim_token
    assert row["result_json"] is None


def test_lost_claim_during_balance_preflight_skips_provider_request(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from types import SimpleNamespace

    from app.providers.images.base import V2ImageProviderResult
    from app.repositories import repository
    from app.schemas import CreateImageJobRequest, ImagePromptPlan
    from app.services import generation

    runtime_settings = replace(
        settings,
        task_queue_db_path=tmp_path / "balance-preflight.sqlite3",
        task_queue_claim_timeout_seconds=30.0,
        task_queue_max_attempts=4,
        task_queue_max_pending=20,
        storage_dir=tmp_path / "storage",
        image_history_path=tmp_path / "image_history.jsonl",
        veyra_usage_path=tmp_path / "veyra_usage.jsonl",
        persist_image_history=True,
        veyra_auth_enabled=True,
    )
    monkeypatch.setattr(task_queue, "settings", runtime_settings)
    monkeypatch.setattr(generation, "settings", runtime_settings)
    task_queue.initialize_task_queue()
    repository.reset()

    run_id = "run_claim_lost_during_balance_preflight"
    _enqueue(run_id)
    old_claim = task_queue.claim_next_task("worker-old-balance")
    assert old_claim is not None
    replacement_claims = []
    provider_calls = 0

    class FakeProvider:
        name = "fake_image"

        async def generate(self, _request):
            nonlocal provider_calls
            provider_calls += 1
            return V2ImageProviderResult(provider=self.name, model="fake-v1", outputs=[])

    async def take_over_during_balance_check(**_kwargs):
        _make_stale(old_claim)
        replacement_claims.append(task_queue.claim_next_task("worker-new-balance"))

    monkeypatch.setattr(generation, "get_v2_image_provider", lambda _hint: asyncio.sleep(0, result=FakeProvider()))
    monkeypatch.setattr(generation, "_ensure_veyra_balance", take_over_during_balance_check)
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        generation,
        "get_billing_rule",
        lambda _key: SimpleNamespace(key="alchemy:v2", enabled=True, charge_amount=1.0, source="alchemy"),
    )

    request = CreateImageJobRequest(
        run_id=run_id,
        prompt_plan=ImagePromptPlan(plan_id="plan_preflight_fence", mode="smart_enhance", prompt="offline fake"),
        provider_hint="fake_image",
        veyra_user_id=17,
    )
    with task_queue.claimed_task(old_claim):
        with pytest.raises(task_queue.StaleTaskClaim):
            asyncio.run(generation.create_image_job(request, job_id="job_preflight_fence"))

    assert replacement_claims and replacement_claims[0] is not None
    assert provider_calls == 0
    assert repository.get_image_job("job_preflight_fence") is None
    assert repository.outputs == {}


def test_success_checkpoint_restores_all_completed_jobs_without_generation_or_rebilling(tmp_path: Path, monkeypatch) -> None:
    from app.repositories import repository
    from app.schemas import CreativeRun, ImageJob, ImageOutput, ImagePromptPlan
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch)
    run_id = "run_checkpoint_multijob"
    _enqueue(run_id)
    claim = task_queue.claim_next_task("worker-checkpoint-source")
    assert claim is not None
    repository.reset()
    now = utc_now()
    plan = ImagePromptPlan(
        plan_id="plan_checkpoint",
        mode="smart_enhance",
        prompt="effective offline fake after prompt transforms",
    )
    source_plan = plan.model_copy(update={"prompt": "pre-transform offline fake"})
    usage_path = tmp_path / "veyra_usage.jsonl"
    usage_record = '{"idempotency_key":"alchemy:v2:task:' + claim.task_id + '","user_id":17}\n'
    usage_path.write_text(usage_record, encoding="utf-8")

    def completed_job(job_id: str, output_id: str) -> ImageJob:
        output = ImageOutput(
            output_id=output_id,
            job_id=job_id,
            url=f"/api/v2/outputs/{output_id}/download",
            metadata={
                "veyra_user_id": 17,
                "veyra_billing": {"idempotency_key": f"alchemy:v2:task:{claim.task_id}"},
            },
            created_at=now,
        )
        return ImageJob(
            job_id=job_id,
            run_id=run_id,
            status="completed",
            provider_id="fake_image",
            model="fake-v1",
            prompt_plan=plan,
            outputs=[output],
            created_at=now,
            updated_at=now,
        )

    first_job = completed_job("job_checkpoint_1", "out_checkpoint_1")
    second_running = ImageJob(
        job_id="job_checkpoint_2",
        run_id=run_id,
        status="running",
        provider_id="fake_image",
        model="fake-v1",
        prompt_plan=plan,
        created_at=now,
        updated_at=now,
    )
    second_job = completed_job("job_checkpoint_2", "out_checkpoint_2")
    generating_run = _run(run_id).model_copy(
        update={"prompt_plan": source_plan, "generation_jobs": [first_job, second_running]}
    )
    checkpoint_time = now + timedelta(seconds=1)

    with task_queue.claimed_task(claim):
        task_queue.persist_claimed_operation(lambda: repository.save_image_job(first_job))
        assert task_queue.update_task_snapshot(generating_run, claim=claim)
        monkeypatch.setattr(task_queue, "utc_now", lambda: checkpoint_time)
        task_queue.persist_claimed_operation(
            lambda: repository.save_image_job(second_job),
            on_persisted=task_queue.checkpoint_completed_generation,
        )
        checkpoint = task_queue.get_success_checkpoint(claim)
    assert checkpoint is not None
    assert [job.job_id for job in checkpoint.generation_jobs] == [first_job.job_id, second_job.job_id]
    assert checkpoint.prompt_plan == plan
    assert checkpoint.updated_at == checkpoint_time

    with task_queue._connect() as connection:
        checkpoint_json = connection.execute(
            "SELECT success_checkpoint_json FROM v2_tasks WHERE run_id = ?",
            (run_id,),
        ).fetchone()["success_checkpoint_json"]
        envelope = task_queue._json_loads(checkpoint_json)
        envelope["generation_job_ids"] = envelope["generation_job_ids"][:1]
        envelope["generation_output_ids"] = {
            first_job.job_id: envelope["generation_output_ids"][first_job.job_id]
        }
        envelope["run"]["generation_jobs"] = envelope["run"]["generation_jobs"][:1]
        connection.execute(
            "UPDATE v2_tasks SET success_checkpoint_json = ? WHERE run_id = ?",
            (task_queue._json_dumps(envelope), run_id),
        )
    with task_queue.claimed_task(claim):
        with pytest.raises(task_queue.InvalidSuccessCheckpoint) as corrupt_checkpoint:
            task_queue.get_success_checkpoint(claim)
    assert corrupt_checkpoint.value.cause_type == "ValueError"
    fallback_snapshot = task_queue.get_run_snapshot(run_id)
    assert fallback_snapshot is not None and fallback_snapshot.status == "generating"
    assert [job.job_id for job in fallback_snapshot.generation_jobs] == [first_job.job_id, second_running.job_id]
    with task_queue._connect() as connection:
        connection.execute(
            "UPDATE v2_tasks SET success_checkpoint_json = ? WHERE run_id = ?",
            (checkpoint_json, run_id),
        )

    finalize_calls = 0

    def finalization_stays_busy(_claim, _run):
        nonlocal finalize_calls
        finalize_calls += 1
        raise sqlite3.OperationalError("database is locked")

    original_complete = task_queue.complete_task
    monkeypatch.setattr(task_queue, "complete_task", finalization_stays_busy)
    monkeypatch.setattr(queue_worker.time, "sleep", lambda _delay: None)
    assert queue_worker._complete_task_with_bounded_retry(claim, checkpoint) is False
    assert finalize_calls == queue_worker._FINALIZATION_RETRIES == 3
    monkeypatch.setattr(task_queue, "complete_task", original_complete)
    with task_queue._connect() as connection:
        pending_recovery = connection.execute(
            "SELECT status, success_checkpoint_json, result_json FROM v2_tasks WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert pending_recovery["status"] == "running"
    assert pending_recovery["success_checkpoint_json"]
    assert pending_recovery["result_json"] is None
    assert task_queue.get_run_snapshot(run_id).status == "completed"

    with task_queue._connect() as connection:
        connection.execute(
            "UPDATE v2_tasks SET attempts = max_attempts WHERE task_id = ?",
            (claim.task_id,),
        )
    _make_stale(claim)
    repository.reset()  # Simulate process-local projection loss after a worker restart.

    async def should_not_preflight(*_args, **_kwargs):
        raise AssertionError("checkpoint recovery must not repeat billing preflight")

    class Runtime:
        async def complete_queued_run(self, *_args, **_kwargs):
            raise AssertionError("checkpoint recovery must not repeat orchestration or generation")

    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", should_not_preflight)
    assert queue_worker.process_next_task_once(Runtime(), "worker-checkpoint-recovery") is True

    recovered_run = repository.get_creative_run(run_id)
    assert recovered_run is not None and recovered_run.status == "completed"
    assert [job.job_id for job in recovered_run.generation_jobs] == [first_job.job_id, second_job.job_id]
    assert set(repository.image_jobs) == {first_job.job_id, second_job.job_id}
    assert set(repository.outputs) == {"out_checkpoint_1", "out_checkpoint_2"}
    assert repository.get_output("out_checkpoint_2").metadata["veyra_user_id"] == 17
    assert repository.get_output("out_checkpoint_2").metadata["veyra_billing"]["idempotency_key"] == (
        f"alchemy:v2:task:{claim.task_id}"
    )
    assert usage_path.read_text(encoding="utf-8") == usage_record
    assert task_queue.get_run_snapshot(run_id).status == "completed"
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT status, attempts, max_attempts, success_checkpoint_json, result_json "
            "FROM v2_tasks WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert row["status"] == "completed"
    assert row["attempts"] == row["max_attempts"]
    assert row["success_checkpoint_json"] is None
    assert row["result_json"]


def test_image_generation_persists_checkpoint_with_completed_job(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    from app.providers.images.base import V2ImageProviderResult
    from app.repositories import repository
    from app.schemas import CreateImageJobRequest, ImageJob, ImagePromptPlan
    from app.services import generation

    database_path = _configure_queue(tmp_path, monkeypatch)
    runtime_settings = replace(settings, task_queue_db_path=database_path)
    monkeypatch.setattr(generation, "settings", runtime_settings)
    repository.reset()
    run_id = "run_generation_checkpoint"
    _enqueue(run_id)
    claim = task_queue.claim_next_task("worker-generation-checkpoint")
    assert claim is not None
    now = utc_now()
    plan = ImagePromptPlan(plan_id="plan_generation_checkpoint", mode="smart_enhance", prompt="offline fake")
    running_job = ImageJob(
        job_id="job_generation_checkpoint",
        run_id=run_id,
        status="running",
        provider_id="fake_image",
        model="fake-v1",
        prompt_plan=plan,
        created_at=now,
        updated_at=now,
    )

    class FakeProvider:
        name = "fake_image"

        async def generate(self, _request):
            return V2ImageProviderResult(provider=self.name, model="fake-v1", outputs=[])

    monkeypatch.setattr(generation, "get_v2_image_provider", lambda _hint: asyncio.sleep(0, result=FakeProvider()))
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *_args, **_kwargs: False)
    request = CreateImageJobRequest(run_id=run_id, prompt_plan=plan, provider_hint="fake_image")
    generating_run = _run(run_id).model_copy(update={"generation_jobs": [running_job]})

    with task_queue.claimed_task(claim):
        assert task_queue.update_task_snapshot(generating_run, claim=claim)
        job = asyncio.run(generation.create_image_job(request, job_id=running_job.job_id, created_at=now))
        checkpoint = task_queue.get_success_checkpoint(claim)

    assert job.status == "completed"
    assert checkpoint is not None and checkpoint.status == "completed"
    assert len(checkpoint.generation_jobs) == 1
    assert checkpoint.generation_jobs[0].job_id == running_job.job_id


def test_multijob_checkpoint_waits_until_every_generation_job_is_complete(tmp_path: Path, monkeypatch) -> None:
    import json

    from app.repositories import repository
    from app.schemas import ImageJob, ImageOutput, ImagePromptPlan

    _configure_queue(tmp_path, monkeypatch)
    run_id = "run_checkpoint_partial_multijob"
    _enqueue(run_id)
    claim = task_queue.claim_next_task("worker-checkpoint-partial")
    assert claim is not None
    now = utc_now()
    plan = ImagePromptPlan(plan_id="plan_partial_checkpoint", mode="smart_enhance", prompt="offline fake")
    first = ImageJob(
        job_id="job_partial_1",
        run_id=run_id,
        status="completed",
        provider_id="fake_image",
        model="fake-v1",
        prompt_plan=plan,
        created_at=now,
        updated_at=now,
    )
    current_running = ImageJob(
        job_id="job_partial_2",
        run_id=run_id,
        status="running",
        provider_id="fake_image",
        model="fake-v1",
        prompt_plan=plan,
        created_at=now,
        updated_at=now,
    )
    still_queued = ImageJob(
        job_id="job_partial_3",
        run_id=run_id,
        status="queued",
        provider_id="fake_image",
        model="fake-v1",
        prompt_plan=plan,
        created_at=now,
        updated_at=now,
    )
    completed_current = current_running.model_copy(update={"status": "completed", "updated_at": now})
    generating_run = _run(run_id).model_copy(update={"generation_jobs": [first, current_running, still_queued]})
    repository.reset()

    with task_queue.claimed_task(claim):
        assert task_queue.update_task_snapshot(generating_run, claim=claim)
        task_queue.persist_claimed_operation(
            lambda: repository.save_image_job(completed_current),
            on_persisted=task_queue.checkpoint_completed_generation,
        )
        assert task_queue.get_success_checkpoint(claim) is None
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT success_checkpoint_json FROM v2_tasks WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert row["success_checkpoint_json"] is None
    truncated_run = _run(run_id).model_copy(
        update={"status": "completed", "generation_jobs": [first, completed_current]}
    )
    envelope = json.loads(task_queue._encode_success_checkpoint(truncated_run))
    envelope["run"]["generation_jobs"] = envelope["run"]["generation_jobs"][:1]
    with pytest.raises(ValueError, match="manifest does not match"):
        task_queue._decode_success_checkpoint(task_queue._json_dumps(envelope))
    valid_output = ImageOutput(
        output_id="out_partial_checkpoint",
        job_id=completed_current.job_id,
        url="/api/v2/outputs/out_partial_checkpoint/download",
        created_at=now,
    )
    valid_run = _run(run_id).model_copy(
        update={
            "status": "completed",
            "generation_jobs": [completed_current.model_copy(update={"outputs": [valid_output]})],
        }
    )
    truncated_outputs = json.loads(task_queue._encode_success_checkpoint(valid_run))
    truncated_outputs["run"]["generation_jobs"][0].pop("outputs")
    with pytest.raises(ValueError, match="output manifest does not match"):
        task_queue._decode_success_checkpoint(task_queue._json_dumps(truncated_outputs))

    invalid_output = valid_output.model_copy(update={"job_id": "different_job"})
    invalid_run = _run(run_id).model_copy(
        update={
            "status": "completed",
            "generation_jobs": [completed_current.model_copy(update={"outputs": [invalid_output]})],
        }
    )
    with pytest.raises(ValueError, match="output from another job"):
        task_queue._decode_success_checkpoint(task_queue._encode_success_checkpoint(invalid_run))


def test_worker_bounded_finalization_retries_sqlite_busy(tmp_path: Path, monkeypatch) -> None:
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch)
    calls = 0

    def complete_once_locked(claim, run):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise sqlite3.OperationalError("database is locked")
        return True

    monkeypatch.setattr(task_queue, "complete_task", complete_once_locked)
    monkeypatch.setattr(queue_worker.time, "sleep", lambda _delay: None)
    claim = task_queue.QueuedTask(
        task_id="task_finalize_retry",
        kind="creative_run",
        run_id="run_finalize_retry",
        payload={},
        attempts=1,
        max_attempts=3,
        worker_id="worker-finalize",
        claim_token="claim-finalize",
    )
    assert queue_worker._complete_task_with_bounded_retry(claim, _run(claim.run_id)) is True
    assert calls == 3


@pytest.mark.parametrize("checkpoint_kind", ["malformed_json", "invalid_manifest"])
def test_corrupt_success_checkpoint_is_quarantined_without_blocking_following_work(
    tmp_path: Path,
    monkeypatch,
    checkpoint_kind: str,
) -> None:
    from app.repositories import repository
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch)
    run_id = f"run_checkpoint_corrupt_{checkpoint_kind}"
    _enqueue(run_id)
    claim = task_queue.claim_next_task("worker-checkpoint-corrupt-source")
    assert claim is not None
    with task_queue.claimed_task(claim):
        assert task_queue.get_success_checkpoint(claim) is None
    _make_stale(claim)
    checkpoint_raw = (
        "{corrupt-json"
        if checkpoint_kind == "malformed_json"
        else task_queue._json_dumps({"version": 2, "run": {}})
    )
    with task_queue._connect() as connection:
        connection.execute(
            "UPDATE v2_tasks SET success_checkpoint_json = ? WHERE task_id = ?",
            (checkpoint_raw, claim.task_id),
        )

    class Runtime:
        async def complete_queued_run(self, *_args, **_kwargs):
            raise AssertionError("corrupt checkpoint must stop before orchestration or generation")

    assert queue_worker.process_next_task_once(Runtime(), "worker-checkpoint-corrupt-recovery") is True
    assert repository.get_creative_run(run_id) is None
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT status, attempts, success_checkpoint_json, result_json, error_json, locked_by, claim_token "
            "FROM v2_tasks WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert row["status"] == "failed"
    assert row["attempts"] == 1
    assert row["success_checkpoint_json"] == checkpoint_raw
    assert row["result_json"] is None
    assert row["locked_by"] is None
    assert row["claim_token"] is None
    error = task_queue._json_loads(row["error_json"])
    assert error["code"] == "success_checkpoint_recovery_failed"
    assert error["retryable"] is False

    # A corrupt checkpoint is terminal evidence, so it cannot occupy direct
    # generation admission or keep an older queue row ahead of later work.
    with task_queue.generation_capacity(request_kind="direct"):
        pass
    following_run_id = f"{run_id}_following"
    _enqueue(following_run_id)

    async def no_preflight(*_args, **_kwargs):
        return None

    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", no_preflight)

    class FollowingRuntime:
        async def complete_queued_run(self, _request, next_run_id):
            return _run(next_run_id)

    assert queue_worker.process_next_task_once(FollowingRuntime(), "worker-following-task") is True
    with task_queue._connect() as connection:
        following = connection.execute(
            "SELECT status FROM v2_tasks WHERE run_id = ?",
            (following_run_id,),
        ).fetchone()
    assert following["status"] == "completed"


def test_default_worker_instances_have_distinct_ids_and_claim_lock_errors_recover(tmp_path: Path, monkeypatch) -> None:
    import sys
    from app.workers import task_queue_worker
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch)
    runtime = object()
    first = queue_worker.QueueWorker(runtime)
    second = queue_worker.QueueWorker(runtime)
    assert first.worker_id != second.worker_id

    calls = 0
    original_claim = task_queue.claim_next_task

    def busy_once(worker_id: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.OperationalError("database is locked")
        return original_claim(worker_id)

    monkeypatch.setattr(task_queue, "claim_next_task", busy_once)
    assert queue_worker.process_next_task_once(runtime, "worker-lock-retry") is False
    assert queue_worker.process_next_task_once(runtime, "worker-lock-retry") is False
    assert calls == 2

    worker_ids: list[str] = []
    monkeypatch.setattr(task_queue_worker, "ensure_runtime_dirs", lambda: None)
    monkeypatch.setattr(task_queue_worker, "bootstrap_v2_repository", lambda **_kwargs: None)
    monkeypatch.setattr(task_queue_worker, "initialize_task_queue", lambda: None)
    monkeypatch.setattr(task_queue_worker, "CreativeManagerRuntime", lambda: runtime)
    monkeypatch.setattr(
        task_queue_worker,
        "process_next_task_once",
        lambda _runtime, worker_id: worker_ids.append(worker_id) or False,
    )
    monkeypatch.setattr(sys, "argv", ["task_queue_worker", "--once"])
    task_queue_worker.main()
    task_queue_worker.main()
    assert len(worker_ids) == 2 and worker_ids[0] != worker_ids[1]
    assert all(worker_id.startswith("v2-standalone-") for worker_id in worker_ids)


def test_worker_slot_ownership_allows_spare_direct_slot_but_waits_for_unleased_claim(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch, slots=2)
    _enqueue("run_spare_slot")
    claim = task_queue.claim_next_task("worker-active")
    assert claim is not None

    with pytest.raises(task_queue.GenerationCapacityExceeded):
        with task_queue.generation_capacity(request_kind="direct"):
            pass

    with task_queue.generation_capacity(request_kind="worker", claim=claim):
        with task_queue.generation_capacity(request_kind="direct"):
            pass


def test_fresh_final_attempt_claim_blocks_direct_until_worker_acquires_lease(tmp_path: Path, monkeypatch) -> None:
    from app.services import generation_capacity as capacity_module

    _configure_queue(tmp_path, monkeypatch, timeout=5.0, slots=1)
    monkeypatch.setattr(task_queue, "settings", replace(task_queue.settings, task_queue_max_attempts=1))
    task_id = _enqueue("run_final_attempt_priority")
    claim = task_queue.claim_next_task("worker-final-attempt")
    assert claim is not None
    assert claim.task_id == task_id
    assert claim.attempts == claim.max_attempts == 1

    worker_at_reservation = threading.Event()
    allow_worker_reservation = threading.Event()
    worker_acquired = threading.Event()
    worker_errors: list[BaseException] = []
    original_reserve = capacity_module._reserve

    def held_worker_reserve(*args, **kwargs):
        request_kind = args[4] if len(args) > 4 else kwargs.get("request_kind")
        if request_kind == "worker" and kwargs.get("task_id") == claim.task_id:
            worker_at_reservation.set()
            if not allow_worker_reservation.wait(3):
                raise TimeoutError("worker reservation barrier was not released")
        return original_reserve(*args, **kwargs)

    monkeypatch.setattr(capacity_module, "_reserve", held_worker_reserve)

    def run_worker() -> None:
        try:
            with task_queue.generation_capacity(request_kind="worker", claim=claim):
                worker_acquired.set()
        except BaseException as exc:
            worker_errors.append(exc)

    worker = threading.Thread(target=run_worker)
    worker.start()
    try:
        assert worker_at_reservation.wait(2)
        with pytest.raises(task_queue.GenerationCapacityExceeded):
            with task_queue.generation_capacity(request_kind="direct"):
                pass
    finally:
        allow_worker_reservation.set()
        worker.join(5)

    assert not worker.is_alive()
    assert worker_errors == []
    assert worker_acquired.is_set()


def test_exhausted_stale_claim_terminalization_preserves_existing_lease_spare_slot(tmp_path: Path, monkeypatch) -> None:
    database_path = _configure_queue(tmp_path, monkeypatch, timeout=3600.0, slots=2)
    monkeypatch.setattr(task_queue, "settings", replace(task_queue.settings, task_queue_max_attempts=1))
    _enqueue("run_active_lease_spare_slot")
    active_claim = task_queue.claim_next_task("worker-holding-lease")
    assert active_claim is not None

    with task_queue.generation_capacity(request_kind="worker", claim=active_claim):
        _enqueue("run_exhausted_stale_spare_slot")
        stale_exhausted_claim = task_queue.claim_next_task("worker-exhausted-stale")
        assert stale_exhausted_claim is not None
        assert stale_exhausted_claim.attempts == stale_exhausted_claim.max_attempts == 1
        _make_stale(stale_exhausted_claim)

        with task_queue.generation_capacity(request_kind="direct"):
            with task_queue._connect() as connection:
                terminal = connection.execute(
                    "SELECT status, locked_by, locked_at FROM v2_tasks WHERE task_id = ?",
                    (stale_exhausted_claim.task_id,),
                ).fetchone()
                leases = connection.execute(
                    "SELECT slot, owner_task_id, owner_claim_token FROM resource_leases WHERE namespace = 'generation'"
                ).fetchall()
            assert terminal is not None
            assert terminal["status"] == "failed"
            assert terminal["locked_by"] is None and terminal["locked_at"] is None
            assert len(leases) == 2
            assert any(
                row["owner_task_id"] == active_claim.task_id
                and row["owner_claim_token"] == active_claim.claim_token
                for row in leases
            )

        with task_queue._connect() as connection:
            remaining = connection.execute(
                "SELECT owner_task_id, owner_claim_token FROM resource_leases WHERE namespace = 'generation'"
            ).fetchall()
        assert len(remaining) == 1
        assert remaining[0]["owner_task_id"] == active_claim.task_id
        assert remaining[0]["owner_claim_token"] == active_claim.claim_token


def test_stale_recoverable_running_task_does_not_block_direct_admission_forever(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch, timeout=2.0)
    _enqueue("run_stale_recoverable")
    claim = task_queue.claim_next_task("worker-stopped")
    assert claim is not None
    _make_stale(claim)
    with task_queue.generation_capacity(request_kind="direct"):
        pass


def test_future_retry_and_terminal_rows_do_not_block_direct_but_due_queue_does(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch)
    _enqueue("run_future_retry")
    future_claim = task_queue.claim_next_task("worker-future")
    assert future_claim is not None
    assert task_queue.retry_task(
        future_claim,
        "wait before retry",
        _run(future_claim.run_id),
        retry_delay_seconds=3600,
        consume_attempt=False,
    ) is True
    with task_queue.generation_capacity(request_kind="direct"):
        pass

    _enqueue("run_due_queue")
    with pytest.raises(task_queue.GenerationCapacityExceeded):
        with task_queue.generation_capacity(request_kind="direct"):
            pass

    due_claim = task_queue.claim_next_task("worker-due")
    assert due_claim is not None
    assert task_queue.complete_task(due_claim, _run(due_claim.run_id)) is True
    with task_queue.generation_capacity(request_kind="direct"):
        pass
