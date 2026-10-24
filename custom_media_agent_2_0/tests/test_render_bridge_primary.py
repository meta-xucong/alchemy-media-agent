"""Offline V2 entry/queue tests; no V1 or real renderer imports."""
import asyncio
import base64
import hashlib
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import settings
from app.repositories import repository
from app.schemas import CreateImageJobRequest, ImagePromptPlan, ProviderInputImage
from app.services import generation, render_bridge_primary as bridge, output_storage, task_queue
from app.providers.images.base import V2ImageProviderOutput, V2ImageProviderResult


def request(count=1):
    return CreateImageJobRequest(prompt_plan=ImagePromptPlan(plan_id="p", mode="smart_enhance",
        prompt="A blue vase", provider_parameters={"count": count, "quality": "auto"}))


def image_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (23, 19), "blue").save(stream, format="PNG")
    return stream.getvalue()


class Transport:
    settings = SimpleNamespace(enabled=True)
    def __init__(self):
        self.calls, self.acks, self.claims, self.cancelled = [], [], [], []
        self.pending = False
        self.api = False
        self.owned = set()
        self.before_resolve = None
    async def resolve(self, unit):
        self.calls.append(unit)
        if self.before_resolve:
            self.before_resolve(unit)
        content = image_bytes()
        return SimpleNamespace(route="api" if self.api else "bridge", state="queued" if self.pending else "receipt_ready",
            reason="queue_capacity" if self.api else "bridge_primary", origin_key=unit.key,
            execution_key=unit.key, task_id="task", receipt_id="receipt",
            image=None if self.pending or self.api else SimpleNamespace(content=content, mime_type="image/png",
                sha256=hashlib.sha256(content).hexdigest(), width=23, height=19))
    def claim_api(self, unit):
        self.claims.append(unit.key)
        if unit.key in self.owned: return False
        self.owned.add(unit.key)
        return True
    def complete_api(self, unit): pass
    async def acknowledge(self, unit, registration_ref):
        assert repository.get_image_job(unit.unit_id.rsplit(":", 1)[0]).status == "completed"
        self.acks.append(registration_ref)
    async def close(self): pass
    def has_binding(self, unit): return True
    async def cancel(self, unit): self.cancelled.append(unit.unit_id)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    original_storage = settings.storage_dir
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    fake = Transport()
    monkeypatch.setattr(bridge, "transport", lambda *args: fake)
    monkeypatch.setattr(bridge, "enabled", lambda: fake.settings.enabled)
    monkeypatch.setattr(generation, "_with_prompt_transform", lambda request: request)
    monkeypatch.setattr(generation, "_with_prompt_integrity_preflight", lambda request: (request, {"status": "passed"}))
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *a, **k: False)
    monkeypatch.setattr(generation, "review_image_job", lambda job: job)
    monkeypatch.setattr(generation, "persist_image_job_history", lambda job: None)
    try:
        yield fake
    finally:
        object.__setattr__(settings, "storage_dir", original_storage)


def test_bridge_entry_without_api_credentials_preserves_original_and_replay(isolated, monkeypatch):
    async def forbidden(*args): raise AssertionError("API selection must not run")
    monkeypatch.setattr(generation, "get_v2_image_provider", forbidden)
    running = asyncio.run(generation.create_running_image_job(request()))
    assert running.status == "running"
    result = asyncio.run(generation.create_image_job(request(), job_id=running.job_id))
    assert result.status == "completed" and result.provider_id == "render_bridge"
    output = result.outputs[0]
    assert output_storage.read_output_content(output.output_id)[0] == image_bytes()
    assert output.metadata["original_sha256"] == hashlib.sha256(image_bytes()).hexdigest()
    assert (output.metadata["width"], output.metadata["height"]) == (23, 19)
    again = asyncio.run(generation.create_image_job(request(), job_id=running.job_id))
    assert again.outputs[0].output_id == output.output_id
    assert len(isolated.calls) == 1


def test_pending_resumes_frozen_request_without_mock_or_api(isolated, monkeypatch):
    async def forbidden(*args): raise AssertionError("must not select API/mock")
    monkeypatch.setattr(generation, "get_v2_image_provider", forbidden)
    isolated.pending = True
    first = asyncio.run(generation.create_image_job(request(), job_id="frozen-job"))
    assert first.error["error_code"] == "bridge_wait"
    isolated.pending = False
    changed = request().model_copy(update={"prompt_plan": request().prompt_plan.model_copy(update={"prompt": "CHANGED"})})
    result = asyncio.run(generation.create_image_job(changed, job_id="frozen-job"))
    assert result.status == "completed"
    assert isolated.calls[0].digest == isolated.calls[1].digest
    assert isolated.calls[1].prompt == "A blue vase"


def test_batch_caches_first_unit_while_second_waits(isolated, monkeypatch):
    async def forbidden(*args): raise AssertionError("no API")
    monkeypatch.setattr(generation, "get_v2_image_provider", forbidden)
    isolated.before_resolve = lambda unit: setattr(isolated, "pending", unit.unit_id.endswith(":1"))
    first = asyncio.run(generation.create_image_job(request(2), job_id="batch"))
    assert first.status == "queued" and len(isolated.calls) == 2
    isolated.before_resolve = None
    isolated.pending = False
    result = asyncio.run(generation.create_image_job(request(2), job_id="batch"))
    assert result.status == "completed" and len(result.outputs) == 2
    assert [unit.unit_id for unit in isolated.calls] == ["batch:0", "batch:1", "batch:1"]


def test_explicit_nonadmission_api_runs_once(isolated, monkeypatch):
    isolated.api = True
    calls = []
    class Provider:
        async def generate(self, request):
            calls.append(request)
            return V2ImageProviderResult(provider="native_api", model="test", outputs=[V2ImageProviderOutput(
                b64_json=base64.b64encode(image_bytes()).decode())])
    async def select(hint): return Provider()
    monkeypatch.setattr(generation, "get_v2_image_provider", select)
    result = asyncio.run(generation.create_image_job(request(), job_id="api-job"))
    assert result.status == "completed" and len(calls) == 1
    result = asyncio.run(generation.create_image_job(request(), job_id="api-job"))
    assert result.status == "completed" and len(calls) == 1
    assert result.outputs[0].metadata["render_bridge_primary"]["reason"] == "queue_capacity"


def test_postprocessing_requirements_are_not_silently_dropped(isolated):
    req = request()
    req.prompt_plan.user_variables["reference_delivery"] = {"deterministic_text_overlay": {"items": [{"text": "hello"}]}}
    frozen = bridge.freeze(req, "overlay", generation.utc_now(), True)
    assert bridge._unit_request(frozen, 0).hard_requirements["deterministic_postprocess"] is True


def test_reference_bytes_are_frozen_and_strong_fusion_is_hard(isolated, tmp_path, monkeypatch):
    path = tmp_path / "reference.png"
    path.write_bytes(image_bytes())
    monkeypatch.setattr(bridge, "uploaded_asset_path", lambda asset: path)
    req = request()
    req.input_images = [ProviderInputImage(asset_id="asset", role="subject_reference", provider_input_required=True)]
    frozen = bridge.freeze(req, "reference", generation.utc_now(), False)
    path.write_bytes(b"changed")
    primary = bridge._unit_request(frozen, 0)
    assert primary.references[0].content == image_bytes()
    assert primary.hard_requirements["reference_fusion"] is True


def test_queue_wait_does_not_consume_attempts():
    from app.services.queue_worker import _job_retry_directive
    directive = _job_retry_directive({"provider": "render_bridge", "error_code": "bridge_wait"})
    assert directive.consume_attempt is False


def test_cancel_addresses_same_unit_only(isolated):
    frozen = bridge.freeze(request(2), "cancel-job", generation.utc_now(), False)
    asyncio.run(bridge.cancel(frozen))
    assert isolated.cancelled == ["cancel-job:0", "cancel-job:1"]


def test_v2_adapter_has_no_cross_product_imports():
    import ast
    from pathlib import Path
    path = Path(bridge.__file__)
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            assert not any(term in (node.module or "") for term in ("src_skeleton", "alchemy_creative_agent_3_0", "integrations.render_bridge"))


def test_queue_recovery_bypasses_planning_and_preserves_job(isolated, monkeypatch, tmp_path):
    from dataclasses import replace
    from app.agents.runtime import CreativeManagerRuntime
    from app.schemas import CreateCreativeRunRequest, CreativeRun
    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    now = generation.utc_now()
    req = request().model_copy(update={"run_id": "run"})
    job = asyncio.run(generation.create_running_image_job(req))
    run = CreativeRun(run_id="run", status="generating", mode="smart_enhance", intent_summary="offline",
                      trace_id="trace", created_at=now, updated_at=now, generation_jobs=[job])
    repository.save_creative_run(run)
    task_queue.enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline"}, queued_run=run)
    claim = task_queue.claim_next_task("worker")
    with task_queue.claimed_task(claim):
        isolated.pending = True
        first = asyncio.run(generation.create_image_job(req, job_id=job.job_id))
        assert first.error["error_code"] == "bridge_wait"
        isolated.pending = False
        runtime = CreativeManagerRuntime()
        async def forbidden(*a, **k): raise AssertionError("must not replan")
        monkeypatch.setattr(runtime, "_run_deterministic_manager", forbidden)
        resumed = asyncio.run(runtime.complete_queued_run(CreateCreativeRunRequest(user_prompt="different"), "run"))
        assert resumed.status == "completed"
        assert resumed.generation_jobs[0].job_id == job.job_id
        assert task_queue.get_success_checkpoint().status == "completed"


def test_stale_claim_after_bridge_response_cannot_debit_or_store(isolated, monkeypatch, tmp_path):
    from dataclasses import replace
    from app.schemas import CreativeRun
    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    now = generation.utc_now()
    run = CreativeRun(run_id="stale", status="generating", mode="smart_enhance", intent_summary="offline",
                      trace_id="trace", created_at=now, updated_at=now)
    repository.save_creative_run(run)
    task_queue.enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline"}, queued_run=run)
    claim = task_queue.claim_next_task("old")
    def supersede(_):
        with task_queue._connect() as db:
            db.execute("UPDATE v2_tasks SET claim_token='superseded' WHERE task_id=?", (claim.task_id,))
    isolated.before_resolve = supersede
    with task_queue.claimed_task(claim), pytest.raises(task_queue.StaleTaskClaim):
        asyncio.run(generation.create_image_job(request(), job_id="stale-job"))
    assert not list((settings.storage_dir / "outputs").glob("**/*"))
    assert isolated.acks == []


def test_actual_core_negotiates_auto_and_rejects_high(isolated, tmp_path, monkeypatch):
    from render_bridge_primary import PrimarySettings, PrimaryTransport
    class Client:
        calls = 0
        async def capabilities(self):
            return {"admission": {"accepting_new_tasks": True}, "routing_availability_v1": {"profiles": [
                {"profile_id": "codex-image", "health": "available", "valid_until": "2099-01-01T00:00:00+00:00"}]},
                "profiles": [{"execution_profile_id": "codex-image", "execution_profile_revision": "1",
                    "parameter_contract": {"dimension_semantics": "original_dimensions_recorded"},
                    "image_options_contract": {"quality": {"values": ["auto"]}, "output_format": {"values": ["png", "jpeg"]},
                        "references": {"max_count": 8}}}]}
        async def create_task(self, payload):
            self.calls += 1
            return {"remote_task_id": "task", "origin_key": payload["origin_key"], "request": payload, "state": "queued"}
        async def close(self): pass
    client = Client()
    core = PrimaryTransport(PrimarySettings(enabled=True, base_url="http://localhost:9999", token="fixture", state_dir=tmp_path / "core"), client=client)
    monkeypatch.setattr(bridge, "transport", lambda *args: core)
    auto = asyncio.run(generation.create_image_job(request(), job_id="auto"))
    assert auto.error["error_code"] == "bridge_wait" and client.calls == 1
    req = request()
    req.prompt_plan.provider_parameters["quality"] = "high"
    seen = []
    class Provider:
        async def generate(self, req):
            seen.append(req.prompt_plan.provider_parameters)
            return V2ImageProviderResult(provider="native_api", model="test", outputs=[V2ImageProviderOutput(b64_json=base64.b64encode(image_bytes()).decode())])
    async def select(_): return Provider()
    monkeypatch.setattr(generation, "get_v2_image_provider", select)
    high = asyncio.run(generation.create_image_job(req, job_id="high"))
    assert high.status == "completed" and client.calls == 1
    assert seen[0]["quality"] == "high"
    assert high.outputs[0].metadata["render_bridge_primary"]["reason"] == "bridge_capability_unsupported"


def test_direct_controls_require_matching_owner_and_reject_queue_owned(isolated, monkeypatch):
    from dataclasses import replace
    from fastapi import HTTPException
    from app import main
    req = request().model_copy(update={"veyra_user_id": 17})
    bridge.freeze(req, "private", generation.utc_now(), False)
    monkeypatch.setattr(main, "settings", replace(settings, veyra_auth_enabled=True))
    monkeypatch.setattr(main, "_require_veyra_user_if_enabled", lambda *a: 22)
    with pytest.raises(HTTPException) as wrong:
        main._bridge_job_request("private", object(), "")
    assert wrong.value.status_code == 404
    monkeypatch.setattr(main, "_require_veyra_user_if_enabled", lambda *a: 17)
    assert main._bridge_job_request("private", object(), "")["job_id"] == "private"
    frozen = bridge.load_frozen("private")
    frozen["queue_task_id"] = "queue-task"
    monkeypatch.setattr(bridge, "load_frozen", lambda job_id=None: frozen)
    with pytest.raises(HTTPException) as owned:
        main._bridge_job_request("private", object(), "")
    assert owned.value.status_code == 409


def test_cancelled_direct_job_cannot_resume_generation(isolated, monkeypatch):
    from app import main
    isolated.pending = True
    pending = asyncio.run(generation.create_image_job(request(), job_id="cancelled"))
    assert pending.error["error_code"] == "bridge_wait"
    cancelled = asyncio.run(main.cancel_bridge_image_job("cancelled", object(), ""))
    assert cancelled.status == "cancelled"
    count = len(isolated.calls)
    isolated.pending = False
    resumed = asyncio.run(generation.create_image_job(request(), job_id="cancelled"))
    assert resumed.status == "cancelled" and len(isolated.calls) == count


def test_receipt_ack_failure_does_not_undo_committed_output(isolated, monkeypatch):
    from render_bridge_primary.http import BridgeError
    async def unavailable(*args, **kwargs): raise BridgeError("bridge_unreachable")
    monkeypatch.setattr(isolated, "acknowledge", unavailable)
    result = asyncio.run(generation.create_image_job(request(), job_id="ack-outage"))
    assert result.status == "completed"
    again = asyncio.run(generation.create_image_job(request(), job_id="ack-outage"))
    assert again.outputs[0].output_id == result.outputs[0].output_id
    assert len(isolated.calls) == 1


def test_restart_after_debit_reuses_pixels_and_billing_idempotency(isolated, monkeypatch):
    charged = set()
    debit_calls = []
    balance_calls = []
    rule = SimpleNamespace(key="alchemy:v2", source="v2", charge_amount=1)
    monkeypatch.setattr(generation, "get_billing_rule", lambda _: rule)
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *a, **k: True)
    async def balance(**kwargs): balance_calls.append(kwargs)
    monkeypatch.setattr(generation, "_ensure_veyra_balance", balance)
    class Billing:
        async def debit(self, **kwargs):
            key = kwargs["idempotency_key"]
            replayed = key in charged
            charged.add(key)
            debit_calls.append(key)
            return SimpleNamespace(user_id=17, amount=1, balance_after=0, idempotency_key=key,
                                   replayed=replayed, source="v2")
    monkeypatch.setattr(generation, "VeyraSub2APIClient", Billing)
    monkeypatch.setattr(generation, "record_veyra_usage", lambda *_: None)
    save = generation._job_from_result
    def crash(*args, **kwargs): raise OSError("simulated crash after debit")
    monkeypatch.setattr(generation, "_job_from_result", crash)
    req = request().model_copy(update={"veyra_user_id": 17})
    with pytest.raises(OSError):
        asyncio.run(generation.create_image_job(req, job_id="billing-recovery"))
    monkeypatch.setattr(generation, "_job_from_result", save)
    result = asyncio.run(generation.create_image_job(req, job_id="billing-recovery"))
    assert result.status == "completed"
    assert len(charged) == 1 and len(debit_calls) == 2
    assert len(isolated.calls) == 1 and len(balance_calls) == 1


def test_api_response_loss_is_not_another_provider_attempt(isolated, monkeypatch):
    from app.providers.images.base import V2ImageProviderError
    isolated.api = True
    calls = []
    class Provider:
        async def generate(self, request):
            calls.append(request)
            raise V2ImageProviderError("response lost", provider="native_api")
    async def select(hint): return Provider()
    monkeypatch.setattr(generation, "get_v2_image_provider", select)
    first = asyncio.run(generation.create_image_job(request(), job_id="api-loss"))
    assert first.status == "failed"
    again = asyncio.run(generation.create_image_job(request(), job_id="api-loss"))
    assert again.error["detail"]["state"] == "api_execution_unknown"
    assert len(calls) == 1


def test_worker_recovery_does_not_repeat_balance_preflight(isolated, monkeypatch, tmp_path):
    from dataclasses import replace
    from app.agents.runtime import CreativeManagerRuntime
    from app.schemas import CreativeRun
    from app.services import queue_worker
    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    now = generation.utc_now()
    req = request().model_copy(update={"run_id": "worker-recovery", "veyra_user_id": 17})
    job = asyncio.run(generation.create_running_image_job(req))
    run = CreativeRun(run_id=req.run_id, status="generating", mode="smart_enhance", intent_summary="offline",
                      trace_id="trace", created_at=now, updated_at=now, generation_jobs=[job])
    repository.save_creative_run(run)
    task_queue.enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline", "veyra_user_id": 17}, queued_run=run)
    claim = task_queue.claim_next_task("before-restart")
    with task_queue.claimed_task(claim):
        isolated.pending = True
        pending = asyncio.run(generation.create_image_job(req, job_id=job.job_id))
        assert pending.error["error_code"] == "bridge_wait"
        assert task_queue.retry_task(claim, "recover", run, retry_delay_seconds=0, consume_attempt=False)
    isolated.pending = False
    async def forbidden(*args): raise AssertionError("no fresh balance preflight after admitted task")
    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", forbidden)
    assert queue_worker.process_next_task_once(CreativeManagerRuntime(), "after-restart")
    assert task_queue.get_run_snapshot(req.run_id).status == "completed"
    assert len(isolated.calls) == 2


@pytest.mark.parametrize("pending", [False, True])
def test_cancel_during_first_unit_prevents_next_unit_and_failed_overwrite(isolated, pending):
    isolated.pending = pending
    def cancel_local(unit):
        job = repository.get_image_job("cancel-race")
        repository.save_image_job(job.model_copy(update={"status": "cancelled"}))
    isolated.before_resolve = cancel_local
    result = asyncio.run(generation.create_image_job(request(2), job_id="cancel-race"))
    assert result.status == "cancelled"
    assert repository.get_image_job("cancel-race").status == "cancelled"
    assert [unit.unit_id for unit in isolated.calls] == ["cancel-race:0"]
    assert not list((settings.storage_dir / "outputs").glob("**/*"))


def test_actual_cancel_handler_revokes_queued_claim_and_never_requeues(isolated, monkeypatch, tmp_path):
    from dataclasses import replace
    from app import main
    from app.schemas import CreativeRun
    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3"))
    now = generation.utc_now()
    req = request(2).model_copy(update={"run_id": "cancel-queue"})
    job = asyncio.run(generation.create_running_image_job(req))
    run = CreativeRun(run_id=req.run_id, status="generating", mode="smart_enhance", intent_summary="offline",
                      trace_id="trace", created_at=now, updated_at=now, generation_jobs=[job])
    repository.save_creative_run(run)
    task_queue.enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline"}, queued_run=run)
    claim = task_queue.claim_next_task("old-worker")
    with task_queue.claimed_task(claim):
        isolated.pending = True
        pending = asyncio.run(generation.create_image_job(req, job_id=job.job_id))
        assert pending.error["error_code"] == "bridge_wait"
    cancelled = asyncio.run(main.cancel_bridge_image_job(job.job_id, object(), ""))
    assert cancelled.status == "cancelled"
    assert task_queue.get_run_snapshot(req.run_id).status == "cancelled"
    assert not task_queue.task_claim_is_current(claim)
    assert not task_queue.retry_task(claim, "late", run, retry_delay_seconds=0)
    assert task_queue.claim_next_task("new-worker") is None
    with task_queue.claimed_task(claim), pytest.raises(task_queue.StaleTaskClaim):
        asyncio.run(generation.create_image_job(req, job_id=job.job_id))
    assert len(isolated.calls) == 1


@pytest.mark.parametrize("error_name", ["GenerationCapacityExceeded", "GenerationCapacityStorageBusy"])
def test_resume_maps_local_busy_without_dispatch(isolated, monkeypatch, error_name):
    from app import main
    from fastapi import HTTPException
    bridge.freeze(request(), "resume-busy", generation.utc_now(), False)
    async def busy(*args, **kwargs): raise getattr(main, error_name)("busy")
    monkeypatch.setattr(main, "run_with_generation_capacity", busy)
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.resume_bridge_image_job("resume-busy", object(), ""))
    assert error.value.status_code in {429, 503}
    assert isolated.calls == []


@pytest.mark.parametrize("queued", [False, True])
def test_cancel_after_applied_debit_defers_and_publishes_same_pixels(isolated, monkeypatch, queued):
    from app import main
    from app.schemas import CreativeRun
    from fastapi import HTTPException
    rule = SimpleNamespace(key="alchemy:v2", source="v2", charge_amount=1)
    monkeypatch.setattr(generation, "get_billing_rule", lambda _: rule)
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *a, **k: True)
    async def balance(**kwargs): pass
    monkeypatch.setattr(generation, "_ensure_veyra_balance", balance)
    monkeypatch.setattr(generation, "record_veyra_usage", lambda *_: None)
    req = request().model_copy(update={"veyra_user_id": 17, "run_id": "paid-run" if queued else None})
    job = asyncio.run(generation.create_running_image_job(req))
    claim = None
    if queued:
        now = generation.utc_now()
        run = CreativeRun(run_id="paid-run", status="generating", mode="smart_enhance", intent_summary="offline",
            trace_id="trace", created_at=now, updated_at=now, generation_jobs=[job])
        repository.save_creative_run(run)
        task_queue.enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline"}, queued_run=run)
        claim = task_queue.claim_next_task("billing-worker")
    charged = []
    async def scenario():
        applied, release = asyncio.Event(), asyncio.Event()
        class Billing:
            async def debit(self, **kwargs):
                charged.append(kwargs["idempotency_key"])
                applied.set()
                await release.wait()
                return SimpleNamespace(user_id=17, amount=1, balance_after=0, idempotency_key=kwargs["idempotency_key"], replayed=False)
        monkeypatch.setattr(generation, "VeyraSub2APIClient", Billing)
        if claim is not None:
            with task_queue.claimed_task(claim):
                pending = asyncio.create_task(generation.create_image_job(req, job_id=job.job_id))
        else:
            pending = asyncio.create_task(generation.create_image_job(req, job_id=job.job_id))
        await asyncio.wait_for(applied.wait(), 3)
        try:
            with pytest.raises(HTTPException) as rejected:
                await main.cancel_bridge_image_job(job.job_id, object(), "")
            assert rejected.value.status_code == 409
            assert rejected.value.detail["error_code"] == "bridge_finalization_in_progress"
            if claim is not None:
                assert task_queue.task_claim_is_current(claim)
        finally:
            release.set()
        return await pending
    result = asyncio.run(scenario())
    assert result.status == "completed" and len(result.outputs) == 1
    assert isolated.cancelled == [] and len(charged) == 1 and len(isolated.calls) == 1
    assert output_storage.read_output_content(result.outputs[0].output_id)[0] == image_bytes()


def test_finalization_restart_replays_frozen_debit_even_if_runtime_policy_changes(isolated, monkeypatch):
    from app import main
    from fastapi import HTTPException
    rule = SimpleNamespace(key="alchemy:v2", source="original-source", charge_amount=1)
    monkeypatch.setattr(generation, "get_billing_rule", lambda _: rule)
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *a, **k: True)
    async def balance(**kwargs): pass
    monkeypatch.setattr(generation, "_ensure_veyra_balance", balance)
    monkeypatch.setattr(generation, "record_veyra_usage", lambda *_: None)
    debits = []
    class Billing:
        async def debit(self, **kwargs):
            debits.append(kwargs)
            if len(debits) == 1:
                raise OSError("debit applied; response lost during process crash")
            return SimpleNamespace(user_id=17, amount=1, balance_after=0,
                idempotency_key=kwargs["idempotency_key"], replayed=True)
    monkeypatch.setattr(generation, "VeyraSub2APIClient", Billing)
    req = request().model_copy(update={"veyra_user_id": 17})
    with pytest.raises(OSError):
        asyncio.run(generation.create_image_job(req, job_id="finalization-restart"))
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(main.cancel_bridge_image_job("finalization-restart", object(), ""))
    assert rejected.value.status_code == 409
    rule.charge_amount = 9
    rule.source = "changed-source"
    rule.key = "changed-key"
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *a, **k: False)
    result = asyncio.run(generation.create_image_job(req, job_id="finalization-restart"))
    assert result.status == "completed"
    assert debits[0] == debits[1]
    assert len(isolated.calls) == 1


def test_uncertain_billing_retains_nonconsuming_finalization_wait(isolated, monkeypatch):
    from app.services.queue_worker import _job_retry_directive
    from app.services.veyra_auth import VeyraAuthError
    rule = SimpleNamespace(key="alchemy:v2", source="v2", charge_amount=1)
    monkeypatch.setattr(generation, "get_billing_rule", lambda _: rule)
    monkeypatch.setattr(generation, "_should_bill_veyra", lambda *a, **k: True)
    async def balance(**kwargs): pass
    monkeypatch.setattr(generation, "_ensure_veyra_balance", balance)
    class Billing:
        async def debit(self, **kwargs): raise VeyraAuthError("billing transport unavailable")
    monkeypatch.setattr(generation, "VeyraSub2APIClient", Billing)
    waiting = asyncio.run(generation.create_image_job(request(), job_id="debit-wait"))
    assert waiting.status == "queued"
    assert waiting.error["error_code"] == "bridge_finalization_wait"
    assert _job_retry_directive(waiting.error).consume_attempt is False
    assert len(isolated.calls) == 1
