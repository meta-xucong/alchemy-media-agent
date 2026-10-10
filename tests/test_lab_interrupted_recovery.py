import asyncio
import threading
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.services.alchemy_lab import (
    AlchemyLabStore,
    ExplorationError,
    ExplorationRequest,
    ExplorationSession,
    GenerationVariant,
)
from app.repositories.sqlite_calls import SQLiteStorageBusy
from app.services import alchemy_lab


def test_restart_recovery_closes_active_lab_session_once_and_preserves_favorites(tmp_path):
    store = AlchemyLabStore(database_path=tmp_path / "lab.sqlite3")
    active = ExplorationSession(
        id="lab-active",
        veyra_user_id=77,
        status="running",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:01:00Z",
        request=ExplorationRequest(idea="resume safely"),
        favorites=["variant-done"],
        variants=[
            GenerationVariant(
                id="variant-done",
                session_id="lab-active",
                prompt_id="prompt-1",
                style_preset_id="style-1",
                index_within_style=1,
                status="succeeded",
                created_at="2026-10-09T00:00:00Z",
            ),
            GenerationVariant(
                id="variant-running",
                session_id="lab-active",
                prompt_id="prompt-2",
                style_preset_id="style-1",
                index_within_style=2,
                status="running",
                created_at="2026-10-09T00:00:00Z",
            ),
        ],
    )
    completed = ExplorationSession(
        id="lab-complete",
        status="completed",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:01:00Z",
        request=ExplorationRequest(idea="already done"),
    )
    store.save(active)
    store.save(completed)

    assert store.recover_interrupted_sessions(batch_size=1) == 1
    assert store.recover_interrupted_sessions(batch_size=1) == 0
    restored = store.get(active.id)
    assert restored.status == "partial_success"
    assert restored.favorites == ["variant-done"]
    assert restored.errors[-1].code == "worker_interrupted"
    assert restored.errors[-1].retryable is False
    assert restored.variants[1].status == "failed"
    assert store.get(completed.id) == completed


def test_restart_recovery_completes_session_when_every_variant_already_succeeded(tmp_path):
    store = AlchemyLabStore(database_path=tmp_path / "lab.sqlite3")
    session = ExplorationSession(
        id="lab-aggregate-not-saved",
        veyra_user_id=77,
        status="running",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:01:00Z",
        request=ExplorationRequest(idea="all variants completed"),
        favorites=["variant-done"],
        variants=[
            GenerationVariant(
                id="variant-done",
                session_id="lab-aggregate-not-saved",
                prompt_id="prompt-1",
                style_preset_id="style-1",
                index_within_style=1,
                status="succeeded",
                created_at="2026-10-09T00:00:00Z",
            )
        ],
    )
    store.save(session)

    assert store.recover_interrupted_sessions() == 1
    recovered = store.get(session.id)
    assert recovered.status == "completed"
    assert recovered.favorites == ["variant-done"]
    assert not any(error.code == "worker_interrupted" for error in recovered.errors)
    assert recovered.progress["status"] == "completed"
    assert recovered.progress["completed"] == 1
    assert store.recover_interrupted_sessions() == 0


def test_restart_recovery_classifies_already_terminal_variants_without_false_interruption(tmp_path):
    store = AlchemyLabStore(database_path=tmp_path / "lab.sqlite3")
    failed_error = ExplorationError(
        code="provider_failed",
        message="The provider rejected this variant.",
        retryable=False,
    )
    cases = [
        (
            "mixed-terminal",
            ["succeeded", "failed"],
            "partial_success",
            1,
            1,
        ),
        (
            "all-failed-terminal",
            ["failed", "failed"],
            "failed",
            0,
            2,
        ),
    ]
    for session_id, statuses, expected_status, expected_completed, expected_failed in cases:
        variants = [
            GenerationVariant(
                id=f"{session_id}-{index}",
                session_id=session_id,
                prompt_id=f"prompt-{index}",
                style_preset_id="style-1",
                index_within_style=index + 1,
                status=status,
                error=failed_error if status == "failed" else None,
                created_at="2026-10-09T00:00:00Z",
            )
            for index, status in enumerate(statuses)
        ]
        session = ExplorationSession(
            id=session_id,
            status="running",
            created_at="2026-10-09T00:00:00Z",
            updated_at="2026-10-09T00:01:00Z",
            request=ExplorationRequest(idea=session_id),
            errors=[failed_error] if expected_failed else [],
            variants=variants,
        )
        store.save(session)

    assert store.recover_interrupted_sessions() == 2
    for session_id, _, expected_status, expected_completed, expected_failed in cases:
        recovered = store.get(session_id)
        assert recovered.status == expected_status
        assert not any(error.code == "worker_interrupted" for error in recovered.errors)
        assert recovered.progress["status"] == expected_status
        assert recovered.progress["completed"] == expected_completed
        assert recovered.progress["failed"] == expected_failed
    assert store.recover_interrupted_sessions() == 0


def test_restart_recovery_marks_empty_session_interrupted_without_provider_replay(tmp_path):
    store = AlchemyLabStore(database_path=tmp_path / "lab.sqlite3")
    session = ExplorationSession(
        id="lab-empty-active",
        status="running",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:01:00Z",
        request=ExplorationRequest(idea="no persisted variants"),
    )
    store.save(session)

    assert store.recover_interrupted_sessions() == 1
    recovered = store.get(session.id)
    assert recovered.status == "failed"
    assert recovered.errors[-1].code == "worker_interrupted"
    assert recovered.progress["failed"] == 0
    assert store.recover_interrupted_sessions() == 0


def test_startup_registers_v1_and_lab_interrupted_work_recovery(monkeypatch):
    from app import main as v1_main

    recovered = []
    monkeypatch.setattr(v1_main.repository, "recover_interrupted_jobs", lambda: recovered.append("v1") or 0)
    monkeypatch.setattr(v1_main.lab_store, "recover_interrupted_sessions", lambda: recovered.append("lab") or 0)

    startup_callbacks = v1_main.app.router.on_startup
    original_callbacks = list(startup_callbacks)
    try:
        startup_callbacks[:] = [v1_main._recover_interrupted_v1_and_lab_work_on_startup]
        with TestClient(v1_main.app):
            pass
    finally:
        startup_callbacks[:] = original_callbacks

    assert recovered == ["v1", "lab"]


def test_lab_session_admission_is_bounded_and_releases_after_runner_finishes(monkeypatch):
    prepare_gate = asyncio.Event()
    runner_gate = asyncio.Event()
    prepare_started = threading.Event()
    runner_started = threading.Event()
    prepare_calls = 0
    runner_calls = 0

    async def fake_prepare(_request, *, veyra_user_id=None):
        nonlocal prepare_calls
        prepare_calls += 1
        if prepare_calls == 2:
            prepare_started.set()
        await prepare_gate.wait()
        return ExplorationSession(
            id=f"admitted-{prepare_calls}",
            veyra_user_id=veyra_user_id,
            status="queued",
            created_at="2026-10-09T00:00:00Z",
            updated_at="2026-10-09T00:00:00Z",
            request=ExplorationRequest(idea="bounded session"),
        )

    async def fake_runner(_session_id, *, veyra_user_id=None):
        nonlocal runner_calls
        runner_calls += 1
        if runner_calls == 2:
            runner_started.set()
        await runner_gate.wait()

    monkeypatch.setattr(alchemy_lab, "prepare_exploration_session", fake_prepare)
    monkeypatch.setattr(alchemy_lab, "_run_exploration_session_guarded", fake_runner)

    async def exercise():
        first_two = [
            asyncio.create_task(
                alchemy_lab.create_exploration_session(ExplorationRequest(idea=f"session-{index}"))
            )
            for index in range(2)
        ]
        assert await asyncio.to_thread(prepare_started.wait, 2)
        try:
            await alchemy_lab.create_exploration_session(ExplorationRequest(idea="over limit"))
        except SQLiteStorageBusy:
            rejected = True
        else:
            rejected = False
        assert prepare_calls == 2

        prepare_gate.set()
        sessions = await asyncio.gather(*first_two)
        assert len(sessions) == 2
        assert await asyncio.to_thread(runner_started.wait, 2)
        runner_gate.set()
        for _ in range(100):
            await asyncio.sleep(0.01)
            if not alchemy_lab._background_tasks:
                break
        else:
            raise AssertionError("Lab runner tasks did not finish and release admission")

        next_session = await alchemy_lab.create_exploration_session(ExplorationRequest(idea="capacity returned"))
        for _ in range(100):
            await asyncio.sleep(0.01)
            if not alchemy_lab._background_tasks:
                break
        else:
            raise AssertionError("released Lab runner task did not finish")
        return rejected, next_session

    rejected, next_session = asyncio.run(exercise())
    assert rejected is True
    assert next_session.status == "queued"


def test_lab_session_capacity_failure_uses_retryable_api_response(monkeypatch):
    from app import main as v1_main

    async def fail_busy(*_args, **_kwargs):
        raise SQLiteStorageBusy("Lab session capacity is busy; retry shortly.")

    monkeypatch.setattr(v1_main, "_veyra_user_id_from_request", lambda *_args, **_kwargs: 77)
    monkeypatch.setattr(v1_main, "create_exploration_session", fail_busy)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            v1_main.create_rare_style_explorer_session(
                ExplorationRequest(idea="busy"),
                SimpleNamespace(),
                authorization="",
            )
        )
    assert raised.value.status_code == 503
    assert raised.value.headers["Retry-After"] == "1"
    assert raised.value.detail["code"] == "storage_busy"


def test_canceled_lab_create_keeps_admission_until_saved_session_has_runner(tmp_path, monkeypatch):
    save_started = threading.Event()
    release_save = threading.Event()
    runner_started = threading.Event()
    release_runner = asyncio.Event()
    runner_calls = 0
    store = AlchemyLabStore(database_path=tmp_path / "lab.sqlite3")
    admission = threading.BoundedSemaphore(1)
    monkeypatch.setattr(alchemy_lab, "lab_store", store)
    monkeypatch.setattr(alchemy_lab, "_LAB_SESSION_CAPACITY", admission)
    monkeypatch.setattr(alchemy_lab, "_should_run_inline", lambda _request: False)
    original_save = store.save

    session = ExplorationSession(
        id="lab-cancel-during-save",
        status="queued",
        created_at="2026-10-09T00:00:00Z",
        updated_at="2026-10-09T00:00:00Z",
        request=ExplorationRequest(idea="cancel during durable handoff"),
    )

    def blocked_save(value):
        save_started.set()
        if not release_save.wait(timeout=3):
            raise TimeoutError("test did not release Lab save")
        return original_save(value)

    async def fake_prepare(_request, *, veyra_user_id=None):
        session.veyra_user_id = veyra_user_id
        return await alchemy_lab._run_lab_sqlite_call(blocked_save, session)

    async def fake_runner(session_id, *, veyra_user_id=None):
        nonlocal runner_calls
        runner_calls += 1
        runner_started.set()
        await asyncio.wait_for(release_runner.wait(), timeout=3)
        current = store.get(session_id)
        current.status = "failed"
        current.progress = {"status": "failed", "completed": 0, "failed": 0}
        store.save_runner_state(current)

    monkeypatch.setattr(alchemy_lab, "prepare_exploration_session", fake_prepare)
    monkeypatch.setattr(alchemy_lab, "_run_exploration_session_guarded", fake_runner)

    async def exercise():
        create_task = asyncio.create_task(
            alchemy_lab.create_exploration_session(ExplorationRequest(idea="cancel during durable handoff"))
        )
        assert await asyncio.to_thread(save_started.wait, 2)
        create_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await create_task
        acquired_after_cancel = admission.acquire(blocking=False)
        if acquired_after_cancel:
            admission.release()

        release_save.set()
        assert await asyncio.to_thread(runner_started.wait, 2)
        persisted = store.get(session.id)
        assert persisted is not None and persisted.status == "queued"
        acquired_while_runner_active = admission.acquire(blocking=False)
        if acquired_while_runner_active:
            admission.release()

        release_runner.set()
        for _ in range(100):
            await asyncio.sleep(0.01)
            if not alchemy_lab._background_tasks:
                break
        else:
            raise AssertionError("canceled create/runner ownership did not finish")

        acquired_after_runner = admission.acquire(blocking=False)
        if acquired_after_runner:
            admission.release()
        return acquired_after_cancel, acquired_while_runner_active, acquired_after_runner

    after_cancel, while_runner_active, after_runner = asyncio.run(exercise())
    assert after_cancel is False
    assert while_runner_active is False
    assert after_runner is True
    assert runner_calls == 1
