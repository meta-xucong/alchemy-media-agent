"""Offline tests through product entrypoints and the real durable primary ledger."""
import asyncio
import base64
import hashlib
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from app.providers.mock_image import MockImageProvider
from app.repositories import repository
from app.schemas import ImageGenerationResult, JobStatus
from app.services import image_service as images, primary_image_transport as primary, alchemy_lab as lab
from app.storage import media_store
from render_bridge_primary import PrimarySettings, PrimaryTransport
from render_bridge_primary.http import BridgeError


class Bridge:
    def __init__(self):
        stream = io.BytesIO()
        Image.new('RGB', (7, 11), (20, 60, 80)).save(stream, format='PNG')
        self.content = stream.getvalue()
        self.tasks = {}; self.creates = 0; self.acks = []; self.cancels = []; self.inputs = []
        self.state = 'artifacts_ready'; self.error = None; self.healthy = True; self.native = True

    async def capabilities(self):
        return {'admission': {'accepting_new_tasks': True}, 'routing_availability_v1': {'profiles': [
            {'profile_id': 'codex-image', 'health': 'available' if self.healthy else 'unavailable', 'valid_until': '2099-01-01T00:00:00Z'}]},
            'profiles': [{'execution_profile_id': 'codex-image', 'execution_profile_revision': '1',
            'parameter_contract': {'accepted_parameters': ['width', 'height', 'seed', 'image_options'], 'dimension_semantics': 'original_dimensions_recorded',
                **({'codex_adapter': {'values': ['codex_cli_imagegen_v1'], 'image_options_contract': {
                    'transparent_background': {'values': [True, False]}, 'references': {'max_count': 5}}}} if self.native else {})},
            'image_options_contract': {'quality': {'values': ['auto']}, 'output_format': {'values': ['png', 'jpeg']}, 'references': {'max_count': 8}}}]}

    async def create_input(self, payload):
        return {"input_id": payload["input_key"]}

    async def upload_input(self, input_id, content, mime_type):
        self.inputs.append((input_id, content, mime_type))

    async def create_task(self, payload):
        self.creates += 1
        task = {'remote_task_id': 'task_'+str(self.creates), 'origin_key': payload['origin_key'], 'request': payload, 'state': self.state, 'attempt_id': 'attempt_'+str(self.creates)}
        task['receipt_id'] = 'receipt_'+str(self.creates) if self.state == 'artifacts_ready' else None
        self.tasks[payload['origin_key']] = task
        if self.error:
            raise self.error
        return task

    async def by_origin(self, origin):
        task = dict(self.tasks[origin], state=self.state)
        task['receipt_id'] = 'receipt_'+task['remote_task_id'].split('_')[-1] if self.state == 'artifacts_ready' else None
        self.tasks[origin] = task
        return task

    async def receipt(self, receipt_id):
        return {'receipt_id': receipt_id, 'task_id': 'task_'+receipt_id.split('_')[-1], 'artifact_id': 'artifact',
                'attempt_id': 'attempt_'+receipt_id.split('_')[-1], 'execution_profile_id': 'codex-image', 'execution_profile_revision': '1', 'slot_id': 'primary',
                'original_sha256': hashlib.sha256(self.content).hexdigest(), 'size': len(self.content), 'mime_type': 'image/png', 'dimensions': {'width': 7, 'height': 11}}

    async def artifact(self, artifact_id, limit):
        return self.content, {}

    async def accept_registered_receipt(self, receipt_id, **kw):
        # ACK must observe the committed host output, not merely downloaded pixels.
        assert any(j.status == JobStatus.ready and j.outputs for j in repository.list_jobs())
        self.acks.append(receipt_id)

    async def cancel(self, task_id):
        self.cancels.append(task_id)

    async def close(self):
        pass


class Api(MockImageProvider):
    name = 'fixture_api'
    def __init__(self): self.calls = 0; self.requests = []; self.fail = False
    async def generate(self, request):
        self.calls += 1; self.requests.append(request)
        if self.fail: raise TimeoutError('uncertain response')
        result = await super().generate(request)
        return result.model_copy(update={'provider': self.name})


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, 'root', tmp_path/'media')
    monkeypatch.setattr(images.settings, 'default_image_provider', 'fixture_api')
    monkeypatch.setattr(images.settings, 'llm_prompt_planning_enabled', False)
    monkeypatch.setattr(images, '_should_check_veyra_billing', lambda request: False)
    monkeypatch.setattr(images, 'review_image_output', lambda *args: None)
    bridge = Bridge(); api = Api()
    monkeypatch.setitem(images.registry.image_providers, 'fixture_api', api)
    monkeypatch.setattr(primary, 'primary_enabled', lambda product: True)
    monkeypatch.setattr(primary, 'transport_for', lambda product: PrimaryTransport(
        PrimarySettings(enabled=True, base_url='http://bridge.invalid', token='fixture-only', state_dir=tmp_path/product), client=bridge))
    monkeypatch.setattr(lab, 'lab_store', lab.AlchemyLabStore(database_path=tmp_path/'lab.sqlite3'))
    async def no_enhance(session): pass
    monkeypatch.setattr(lab, '_ensure_session_prompts_enhanced', no_enhance)
    return bridge, api


async def submit(count=1, **kwargs):
    prepared = await images.submit_image_job(session_id='session', prompt='A quiet landscape', count=count,
        work_intensity='passthrough', provider_preference='fixture_api', **kwargs)
    return await images.run_submitted_image_job(prepared.job.id, prepared.request)


def test_v1_real_entry_original_bytes_and_concurrent_resume(runtime, monkeypatch):
    bridge, api = runtime
    def forbidden(*args): raise AssertionError('Original Bridge bytes must not be postprocessed')
    monkeypatch.setattr(images, '_apply_advanced_postprocess', forbidden)
    job = asyncio.run(submit(count=2))
    assert job.status == JobStatus.ready
    assert len(job.outputs) == bridge.creates == len(bridge.acks) == 2
    assert api.calls == 0
    for output in job.outputs:
        assert (output.width, output.height) == (7, 11)
        assert output.metadata['sha256'] == hashlib.sha256(bridge.content).hexdigest()
        assert media_store.find_output_file(output.id)[0].read_bytes() == bridge.content
    async def polls(): return await asyncio.gather(primary.resume_primary_job(job.id), primary.resume_primary_job(job.id))
    assert all(len(j.outputs) == 2 for j in asyncio.run(polls()))
    assert bridge.creates == 2 and len(bridge.acks) == 2


@pytest.mark.parametrize('state', ['queued', 'running', 'execution_unknown', 'bridge_submission_unknown'])
def test_v1_pending_restart_same_origin_no_api(runtime, state):
    bridge, api = runtime
    bridge.state = state
    if state == 'bridge_submission_unknown': bridge.error = BridgeError('bridge_unreachable')
    job = asyncio.run(submit())
    assert job.status == JobStatus.generating and api.calls == 0
    assert repository.recover_interrupted_jobs(batch_size=1) == 0
    resumed = asyncio.run(primary.resume_primary_job(job.id))
    assert resumed.status == JobStatus.generating and bridge.creates == 1 and api.calls == 0
    bridge.state = 'artifacts_ready'
    resumed = asyncio.run(primary.resume_primary_job(job.id))
    assert resumed.status == JobStatus.ready and len(resumed.outputs) == 1
    assert bridge.creates == 1 and api.calls == 0


@pytest.mark.parametrize('reason', ['queue', 'health', 'capability'])
def test_v1_proven_nonadmission_uses_exact_api_request_once(runtime, reason):
    bridge, api = runtime
    kwargs = {}
    if reason == 'queue': bridge.error = BridgeError('queue_capacity', status=429)
    if reason == 'health': bridge.healthy = False
    if reason == 'capability': bridge.native = False; kwargs = {'background': 'transparent', 'output_compression': 0, 'quality': 'high'}
    job = asyncio.run(submit(**kwargs))
    assert job.status == JobStatus.ready and api.calls == 1
    if reason == 'capability':
        assert api.requests[0].prompt_plan.background == 'transparent'
        assert api.requests[0].prompt_plan.output_compression == 0
        assert api.requests[0].prompt_plan.quality == 'high'
        assert bridge.creates == 0
    asyncio.run(primary.resume_primary_job(job.id))
    assert api.calls == 1


def test_api_response_loss_never_reinvokes_provider(runtime):
    bridge, api = runtime
    bridge.healthy = False; api.fail = True
    job = asyncio.run(submit())
    assert job.error.code == 'api_execution_unknown'
    api.fail = False
    job = asyncio.run(primary.resume_primary_job(job.id))
    assert job.status == JobStatus.generating and api.calls == 1 and not job.outputs


def test_cancellation_never_falls_back_or_publishes_late_receipt(runtime):
    bridge, api = runtime
    bridge.state = 'queued'
    job = asyncio.run(submit())
    canceled = asyncio.run(primary.cancel_primary_job(job.id))
    assert canceled.status == JobStatus.canceled and bridge.cancels
    bridge.state = 'artifacts_ready'
    resumed = asyncio.run(primary.resume_primary_job(job.id))
    assert resumed.status == JobStatus.canceled and not resumed.outputs
    assert bridge.creates == 1 and not api.calls and not bridge.acks


def make_lab_session():
    sid = 'lab_test'
    style = lab.FALLBACK_STYLE_PRESETS[0]
    session = lab.ExplorationSession(id=sid, status='queued', created_at='2026-10-24T00:00:00Z', updated_at='2026-10-24T00:00:00Z',
        request=lab.ExplorationRequest(idea='A quiet landscape', provider_preference='fixture_api', generation_interval_seconds=0), style_presets=[style],
        prompts=[lab.ComposedPrompt(id='prompt', session_id=sid, style_preset_id=style.id, style_preset_version='1', idea='A quiet landscape', final_prompt='A quiet landscape')],
        variants=[lab.GenerationVariant(id='variant', session_id=sid, prompt_id='prompt', style_preset_id=style.id, index_within_style=1, status='queued', created_at='2026-10-24T00:00:00Z')])
    lab.lab_store.save(session)
    return session


def test_lab_real_entry_high_quality_uses_versioned_native_defaults(runtime):
    bridge, api = runtime
    session = make_lab_session()
    result = asyncio.run(lab.run_exploration_session(session.id))
    assert result.status == 'completed' and result.variants[0].status == 'succeeded'
    assert api.calls == 0 and bridge.creates == 1
    job = repository.list_jobs()[0]
    assert job.raw_response_summary[primary.KEY]['request']['prompt_plan']['quality'] == 'high'
    assert next(iter(bridge.tasks.values()))['request']['parameters'] == {'codex_adapter': 'codex_cli_imagegen_v1'}
    asyncio.run(lab.run_exploration_session(session.id))
    assert api.calls == 0 and bridge.creates == 1


def test_lab_real_entry_pending_restart_keeps_variant_job(runtime, monkeypatch):
    bridge, api = runtime
    bridge.state = 'execution_unknown'
    session = make_lab_session()
    first = asyncio.run(lab.run_exploration_session(session.id))
    assert first.status == 'running' and first.variants[0].status == 'running'
    job_id = first.variants[0].provider_metadata['job_id']
    assert lab.lab_store.recover_interrupted_sessions(batch_size=1) == 0
    assert repository.recover_interrupted_jobs(batch_size=1) == 0
    second = asyncio.run(lab.run_exploration_session(session.id))
    assert second.variants[0].provider_metadata['job_id'] == job_id
    assert bridge.creates == 1 and api.calls == 0
    bridge.state = 'artifacts_ready'
    final = asyncio.run(lab.run_exploration_session(session.id))
    assert final.status == 'completed' and final.variants[0].asset['job_id'] == job_id
    assert len(repository.list_jobs()) == 1 and bridge.creates == 1 and not api.calls


def test_billing_response_loss_reuses_outputs_and_debit_key_before_ack(runtime, monkeypatch):
    bridge, api = runtime
    debit_keys = []; charged = set(); preflights = []; account = {"balance": 2}
    rule = SimpleNamespace(enabled=True, charge_amount=2, key='fixture_rule', source='fixture')
    async def load_rule(key): return rule
    async def balance(**kwargs):
        preflights.append(kwargs)
        if account["balance"] < kwargs["amount"]:
            raise images.VeyraInsufficientBalance("No balance remains after the first debit")
    async def debit(**kwargs):
        key = kwargs['idempotency_key']; replayed = key in charged
        if not replayed:
            account["balance"] -= kwargs["amount"]
        debit_keys.append(key); charged.add(key)
        if len(debit_keys) == 1:
            raise RuntimeError('simulated loss after idempotent debit')
        return SimpleNamespace(user_id=41, amount=2, balance_after=account['balance'], idempotency_key=key, source='fixture', replayed=replayed)
    monkeypatch.setattr(images, '_should_check_veyra_billing', lambda request: True)
    monkeypatch.setattr(images, '_should_bill_veyra', lambda *args: True)
    monkeypatch.setattr(images, 'load_billing_rule', load_rule)
    monkeypatch.setattr(images, 'ensure_sufficient_balance', balance)
    monkeypatch.setattr(images, 'debit_balance', debit)
    monkeypatch.setattr(images, 'record_veyra_usage', lambda record: None)
    first = asyncio.run(submit(veyra_user_id=41))
    assert first.status == JobStatus.generating and not first.outputs and not bridge.acks
    output_id = first.raw_response_summary[primary.KEY]['outputs'][0]['id']
    assert media_store.output_publication_blocked(output_id)
    with pytest.raises(primary.PrimaryFinalizationInProgress):
        asyncio.run(primary.cancel_primary_job(first.id))
    async def unavailable_rule(key): raise images.VeyraAuthError("temporary billing metadata outage")
    monkeypatch.setattr(images, "load_billing_rule", unavailable_rule)
    resumed = asyncio.run(primary.resume_primary_job(first.id))
    assert resumed.status == JobStatus.ready and resumed.outputs[0].id == output_id
    assert account["balance"] == 0
    assert len(charged) == 1 and len(set(debit_keys)) == 1 and len(debit_keys) == 2
    assert len(preflights) == 1 and bridge.creates == 1 and api.calls == 0 and len(bridge.acks) == 1
    assert not media_store.output_publication_blocked(output_id)


def test_batch_keeps_first_completed_unit_while_second_is_pending(runtime):
    bridge, api = runtime
    original = bridge.create_task
    async def create(payload):
        if bridge.creates == 1: bridge.state = 'queued'
        return await original(payload)
    bridge.create_task = create
    first = asyncio.run(submit(count=2))
    assert first.status == JobStatus.generating and not first.outputs
    first_id = first.raw_response_summary[primary.KEY]['outputs'][0]['id']
    assert media_store.output_publication_blocked(first_id) and not bridge.acks
    bridge.state = 'artifacts_ready'
    done = asyncio.run(primary.resume_primary_job(first.id))
    assert done.status == JobStatus.ready and len(done.outputs) == 2
    assert done.outputs[0].id == first_id and bridge.creates == 2 and not api.calls


def test_authenticated_job_poll_resumes_only_after_access_check(runtime, monkeypatch):
    from app import main
    from fastapi import HTTPException
    from starlette.requests import Request
    bridge, api = runtime
    bridge.state = 'queued'
    first = asyncio.run(submit())
    bridge.state = 'artifacts_ready'
    req = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [], 'query_string': b''})
    async def deny(*args, **kwargs): raise HTTPException(404)
    monkeypatch.setattr(main, '_require_v1_session_access', deny)
    with pytest.raises(HTTPException): asyncio.run(main.get_image_job(first.id, req, 'fixture'))
    assert repository.get_job(first.id).status == JobStatus.generating and not bridge.acks
    async def allow(*args, **kwargs): return 41
    monkeypatch.setattr(main, '_require_v1_session_access', allow)
    result = asyncio.run(main.get_image_job(first.id, req, 'fixture'))
    assert result.status == JobStatus.ready and bridge.creates == 1 and not api.calls


def test_disabled_mode_recovers_owned_task_but_new_mock_stays_legacy(runtime, monkeypatch):
    bridge, api = runtime
    bridge.state = 'queued'
    first = asyncio.run(submit())
    monkeypatch.setattr(primary, 'primary_enabled', lambda product: False)
    bridge.state = 'artifacts_ready'
    assert asyncio.run(primary.resume_primary_job(first.id)).status == JobStatus.ready
    monkeypatch.setitem(images.registry.image_providers, 'mock_image', MockImageProvider())
    mock = asyncio.run(images.create_image_job(session_id='mock', prompt='offline fixture', provider_preference='mock_image', work_intensity='passthrough'))
    assert mock.provider == 'mock_image' and primary.KEY not in mock.raw_response_summary
    assert bridge.creates == 1


def test_bridge_original_write_crash_reuses_reserved_id_and_cached_pixels(runtime, monkeypatch):
    bridge, api = runtime
    original = media_store.ensure_thumbnail
    calls = 0
    def crash_after_original(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1: raise RuntimeError('simulated interruption after original write')
        return original(**kwargs)
    monkeypatch.setattr(media_store, 'ensure_thumbnail', crash_after_original)
    pending = asyncio.run(submit())
    assert pending.status == JobStatus.generating and not pending.outputs
    files = list((media_store.generated_root/pending.id).glob('*.png'))
    assert len(files) == 1 and files[0].read_bytes() == bridge.content
    assert media_store.output_publication_blocked(files[0].stem)
    done = asyncio.run(primary.resume_primary_job(pending.id))
    assert done.status == JobStatus.ready and done.outputs[0].id == files[0].stem
    assert bridge.creates == 1 and not api.calls and len(bridge.acks) == 1


def test_reservation_replay_requires_exact_owner_job_and_hash(runtime):
    bridge, _ = runtime
    from app.repositories.output_publication import reserve_output
    digest = hashlib.sha256(bridge.content).hexdigest()
    args = dict(output_id='out_unpublished_primary', job_id='job_primary', owner_id=41, replay_sha256=digest)
    reserve_output(repository.database_path, **args)
    reserve_output(repository.database_path, **args)
    for change in ({'owner_id': 42}, {'job_id': 'other'}, {'replay_sha256': '0'*64}, {'replay_sha256': None}):
        with pytest.raises(ValueError): reserve_output(repository.database_path, **{**args, **change})


def test_lab_authenticated_poll_restores_pending_session(runtime, monkeypatch):
    from app import main
    from starlette.requests import Request
    bridge, api = runtime
    monkeypatch.setattr(PrimaryTransport, '_supported', staticmethod(lambda *args: True))
    bridge.state = 'queued'
    session = make_lab_session()
    first = asyncio.run(lab.run_exploration_session(session.id))
    assert first.status == 'running'
    bridge.state = 'artifacts_ready'
    async def context(*args, **kwargs): return {'user_id': None, 'is_admin': False}
    monkeypatch.setattr(main, '_veyra_history_context', context)
    req = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [], 'query_string': b''})
    bridge.state = 'queued'
    pending = asyncio.run(main.get_rare_style_explorer_session(session.id, req, 'fixture'))
    _assert_lab_response_schema(pending)
    assert pending['session']['status'] == 'running'
    assert 'primary_transport' not in pending['session']['variants'][0]['provider_metadata']
    assert lab.lab_store.get(session.id).variants[0].provider_metadata['primary_transport'] is True
    bridge.state = 'artifacts_ready'
    result = asyncio.run(main.get_rare_style_explorer_session(session.id, req, 'fixture'))
    _assert_lab_response_schema(result)
    assert result['session']['status'] == 'completed'
    assert bridge.creates == 1 and api.calls == 0


def test_primary_checkpoints_merge_and_terminal_state_cannot_regress(runtime):
    bridge, _ = runtime
    bridge.state = 'queued'
    job = asyncio.run(submit())
    stale = job.model_copy(deep=True)
    current = job.model_copy(deep=True)
    current.raw_response_summary[primary.KEY]['outputs'] = [{'id': 'private_a', 'job_id': job.id, 'url': '/private'}]
    repository.save_job(current)
    repository.save_job(stale)
    assert repository.get_job(job.id).raw_response_summary[primary.KEY]['outputs'][0]['id'] == 'private_a'
    current.status = JobStatus.canceled
    repository.save_job(current)
    assert repository.save_job(stale).status == JobStatus.canceled
    assert repository.get_job(job.id).status == JobStatus.canceled


def test_lab_owner_cancel_endpoint_latches_session_and_job(runtime, monkeypatch):
    from app import main
    from fastapi import HTTPException
    from starlette.requests import Request
    bridge, api = runtime
    monkeypatch.setattr(PrimaryTransport, '_supported', staticmethod(lambda *args: True))
    monkeypatch.setattr(main.settings, 'veyra_auth_enabled', True)
    bridge.state = 'queued'
    session = make_lab_session(); session.veyra_user_id = 41
    lab.lab_store.save(session)
    running = asyncio.run(lab.run_exploration_session(session.id))
    req = Request({'type': 'http', 'method': 'POST', 'path': '/', 'headers': [], 'query_string': b''})
    async def context(_request, authorization=''): return {'user_id': int(authorization), 'is_admin': False}
    monkeypatch.setattr(main, '_veyra_history_context', context)
    with pytest.raises(HTTPException): asyncio.run(main.cancel_primary_lab_session(session.id, req, '77'))
    assert not bridge.cancels
    response = asyncio.run(main.cancel_primary_lab_session(session.id, req, '41'))
    assert response['session']['status'] == 'failed'
    assert 'primary_transport' not in response['session']
    assert 'board' in response
    _assert_lab_response_schema(response)
    assert bridge.cancels and bridge.creates == 1 and not api.calls
    job = repository.list_jobs()[0]
    assert job.status == JobStatus.canceled
    # Even a stale runner finishing later cannot overwrite owner cancellation.
    running.status = 'completed'
    assert lab.lab_store.save_runner_state(running).status == 'failed'
    bridge.state = 'artifacts_ready'
    assert asyncio.run(lab.run_exploration_session(session.id)).status == 'failed'
    assert not bridge.acks


def test_disabled_mid_batch_resumes_owned_bridge_then_claims_new_api_unit(runtime, monkeypatch, tmp_path):
    bridge, api = runtime
    bridge.state = 'queued'
    pending = asyncio.run(submit(count=2))
    assert bridge.creates == 1 and not api.calls
    bridge.state = 'artifacts_ready'
    monkeypatch.setattr(primary, 'primary_enabled', lambda product: False)
    monkeypatch.setattr(primary, 'transport_for', lambda product: PrimaryTransport(
        PrimarySettings(enabled=False, base_url='http://bridge.invalid', token='fixture-only', state_dir=tmp_path/product), client=bridge))
    done = asyncio.run(primary.resume_primary_job(pending.id))
    assert done.status == JobStatus.ready and len(done.outputs) == 2
    assert bridge.creates == 1 and api.calls == 1 and len(bridge.acks) == 1
    asyncio.run(primary.resume_primary_job(pending.id))
    assert api.calls == 1


def test_lab_cancel_during_cooldown_never_submits_second_variant(runtime, monkeypatch):
    bridge, api = runtime
    monkeypatch.setattr(PrimaryTransport, '_supported', staticmethod(lambda *args: True))
    session = make_lab_session()
    second = session.variants[0].model_copy(update={'id': 'variant_second', 'index_within_style': 2})
    session.variants.append(second)
    session.request.generation_interval_seconds = 1
    lab.lab_store.save(session)
    monkeypatch.setattr(lab, '_cooldown_after_variant', lambda *args, **kwargs: 1)
    original_sleep = asyncio.sleep
    async def cancel_at_cooldown(seconds):
        if seconds == 1:
            saved = lab.lab_store.get(session.id)
            assert saved.variants[0].status == 'succeeded'
            await lab.cancel_primary_exploration_session(session.id)
        else:
            await original_sleep(seconds)
    monkeypatch.setattr(lab.asyncio, 'sleep', cancel_at_cooldown)
    result = asyncio.run(lab.run_exploration_session(session.id))
    assert result.status == 'partial_success'
    assert result.variants[0].status == 'succeeded'
    assert result.variants[1].error.code == 'user_canceled'
    assert len(repository.list_jobs()) == 1 and bridge.creates == 1 and not api.calls


def test_lab_cancel_during_billing_preflight_prevents_first_transport(runtime, monkeypatch):
    bridge, api = runtime
    session = make_lab_session(); session.veyra_user_id = 41
    lab.lab_store.save(session)
    async def load_rule(key): return SimpleNamespace(enabled=True, charge_amount=2, key='fixture', source='fixture')
    async def cancel_before_admission(**kwargs): await lab.cancel_primary_exploration_session(session.id)
    monkeypatch.setattr(images, '_should_check_veyra_billing', lambda request: True)
    monkeypatch.setattr(images, '_should_bill_veyra', lambda *args: True)
    monkeypatch.setattr(images, 'load_billing_rule', load_rule)
    monkeypatch.setattr(images, 'ensure_sufficient_balance', cancel_before_admission)
    result = asyncio.run(lab.run_exploration_session(session.id))
    assert result.status == 'failed' and result.errors[-1].code == 'user_canceled'
    assert bridge.creates == 0 and api.calls == 0
    assert repository.list_jobs()[0].status == JobStatus.canceled


@pytest.mark.parametrize('product', ['v1', 'lab', 'lab_shared_db'])
def test_owner_cancel_cannot_hide_pixels_after_debit_commit_boundary(runtime, monkeypatch, product):
    from app import main
    from fastapi import HTTPException
    from starlette.requests import Request
    bridge, api = runtime
    monkeypatch.setattr(PrimaryTransport, '_supported', staticmethod(lambda *args: True))
    charged = []; entered = asyncio.Event(); release = asyncio.Event()
    async def rule(key): return SimpleNamespace(enabled=True, charge_amount=2, key='fixture', source='fixture')
    async def balance(**kwargs): pass
    async def debit(**kwargs):
        charged.append(kwargs['idempotency_key'])
        entered.set()
        await release.wait()
        return SimpleNamespace(user_id=41, amount=2, balance_after=0, idempotency_key=charged[0], source='fixture', replayed=False)
    async def access(*args, **kwargs): return 41
    async def context(*args, **kwargs): return {'user_id': 41, 'is_admin': False}
    monkeypatch.setattr(images, '_should_check_veyra_billing', lambda request: True)
    monkeypatch.setattr(images, '_should_bill_veyra', lambda *args: True)
    monkeypatch.setattr(images, 'load_billing_rule', rule)
    monkeypatch.setattr(images, 'ensure_sufficient_balance', balance)
    monkeypatch.setattr(images, 'debit_balance', debit)
    monkeypatch.setattr(images, 'record_veyra_usage', lambda record: None)
    monkeypatch.setattr(main, '_require_v1_session_access', access)
    monkeypatch.setattr(main, '_veyra_history_context', context)
    req = Request({'type': 'http', 'method': 'POST', 'path': '/', 'headers': [], 'query_string': b''})
    async def run():
        if product == 'lab_shared_db':
            monkeypatch.setattr(lab, 'lab_store', lab.AlchemyLabStore(database_path=repository.database_path))
        if product.startswith('lab'):
            session = make_lab_session(); session.veyra_user_id = 41; lab.lab_store.save(session)
            task = asyncio.create_task(lab.run_exploration_session(session.id))
        else:
            task = asyncio.create_task(submit(veyra_user_id=41))
        await asyncio.wait_for(entered.wait(), 5)
        job = repository.list_jobs()[0]
        try:
            with pytest.raises(HTTPException) as conflict:
                if product.startswith('lab'): await main.cancel_primary_lab_session(session.id, req, 'fixture')
                else: await main.cancel_primary_image_job(job.id, req, 'fixture')
            assert conflict.value.status_code == 409
        finally:
            release.set()
            await task
        published = repository.get_job(job.id)
        assert published.status == JobStatus.ready and len(published.outputs) == 1
        assert not media_store.output_publication_blocked(published.outputs[0].id)
        if product.startswith('lab'): assert lab.lab_store.get(session.id).status == 'completed'
        assert len(charged) == 1 and bridge.creates == 1 and len(bridge.acks) == 1 and not api.calls
    asyncio.run(run())


def test_public_job_poll_hides_frozen_request_and_private_checkpoints(runtime, monkeypatch):
    from app import main
    from starlette.requests import Request
    job = asyncio.run(submit())
    stored = repository.get_job(job.id)
    state = stored.raw_response_summary[primary.KEY]
    state['request']['prompt_plan']['variables']['internal_local_path'] = '/synthetic/private/source.png'
    state['outputs'][0]['metadata']['private_checkpoint_path'] = '/synthetic/private/checkpoint'
    state['units']['0']['unexpected_private_path'] = '/synthetic/private/route'
    repository.save_job(stored)
    async def allow(*args, **kwargs): return 41
    monkeypatch.setattr(main, '_require_v1_session_access', allow)
    req = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [], 'query_string': b''})
    public = asyncio.run(main.get_image_job(job.id, req, 'fixture'))
    projection = public.raw_response_summary[primary.KEY]
    assert 'request' not in projection and 'outputs' not in projection
    assert 'unexpected_private_path' not in projection['units']['0']
    assert projection['units']['0']['route'] == 'bridge'
    assert '/synthetic/private/' not in public.model_dump_json()
    durable = repository.get_job(job.id).raw_response_summary[primary.KEY]
    assert durable['request']['prompt_plan']['variables']['internal_local_path'] == '/synthetic/private/source.png'
    assert durable['outputs'][0]['metadata']['private_checkpoint_path'] == '/synthetic/private/checkpoint'


def test_lost_debit_response_freezes_all_arguments_across_billing_rule_change(runtime, monkeypatch):
    bridge, api = runtime
    rule = SimpleNamespace(enabled=True, charge_amount=2, key='original_rule', source='original_source')
    calls = []; charged = set(); lookups = []
    async def load(key): lookups.append(key); return rule
    async def balance(**kwargs): pass
    async def debit(**kwargs):
        calls.append(dict(kwargs)); charged.add(kwargs['idempotency_key'])
        if len(calls) == 1: raise RuntimeError('response lost after original charge')
        return SimpleNamespace(user_id=kwargs['user_id'], amount=kwargs['amount'], balance_after=0,
                               idempotency_key=kwargs['idempotency_key'], source=kwargs['source'], replayed=True)
    monkeypatch.setattr(images, '_should_check_veyra_billing', lambda request: True)
    monkeypatch.setattr(images, '_should_bill_veyra', lambda *args: True)
    monkeypatch.setattr(images, 'load_billing_rule', load)
    monkeypatch.setattr(images, 'ensure_sufficient_balance', balance)
    monkeypatch.setattr(images, 'debit_balance', debit)
    monkeypatch.setattr(images, 'record_veyra_usage', lambda record: None)
    pending = asyncio.run(submit(veyra_user_id=41))
    assert pending.status == JobStatus.generating
    frozen = pending.raw_response_summary[primary.KEY]['debit']
    assert frozen == calls[0]
    rule = SimpleNamespace(enabled=False, charge_amount=999, key='new_rule', source='new_source')
    monkeypatch.setattr(images, '_should_check_veyra_billing', lambda request: False)
    done = asyncio.run(primary.resume_primary_job(pending.id))
    assert done.status == JobStatus.ready
    assert calls == [frozen, frozen] and len(charged) == 1 and len(lookups) == 1
    assert frozen == {'user_id': 41, 'amount': 2, 'idempotency_key': f'original_rule:image:{pending.id}',
                      'source': 'original_source', 'reference_id': pending.id}
    assert bridge.creates == 1 and not api.calls and len(bridge.acks) == 1
    assert 'debit' not in primary.public_image_job(done).raw_response_summary[primary.KEY]


def _assert_lab_response_schema(response):
    import json
    from pathlib import Path
    from fastapi.encoders import jsonable_encoder
    jsonschema = pytest.importorskip('jsonschema')
    schema = json.loads(Path('specs/alchemy_lab/rare_style_explorer.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(schema).validate(jsonable_encoder(response))


@pytest.mark.parametrize('state', ['queued', 'running', 'completed', 'failed', 'partial_success'])
def test_lab_public_projection_preserves_strict_schema_and_private_recovery_flag(runtime, state):
    import json
    from pathlib import Path
    jsonschema = pytest.importorskip('jsonschema')
    session = make_lab_session()
    session.primary_transport = True
    session.status = state
    if state in {'failed', 'partial_success'}:
        session.errors = [lab.ExplorationError(code='user_canceled', message='Canceled by owner', retryable=False)]
        session.variants[0].status = 'failed'
        session.variants[0].error = session.errors[0]
    lab.lab_store.save(session)
    public = lab.public_exploration_session(session)
    assert 'primary_transport' not in public and 'veyra_user_id' not in public
    schema = json.loads(Path('specs/alchemy_lab/rare_style_explorer.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(schema).validate({'session': public, 'board': lab.comparison_board(session).model_dump(mode='json')})
    assert lab.lab_store.get(session.id).primary_transport is True


def test_v1_native_defaults_preserve_prompt_and_original_request(runtime):
    from app.providers.openai_image import OpenAIGPTImageProvider
    bridge, api = runtime
    job = asyncio.run(submit(quality='high', size='1536x1024', output_format='webp',
                             output_compression=17, background='transparent'))
    assert job.status == JobStatus.ready and not api.calls and bridge.creates == 1
    frozen = primary.frozen_request(job)
    payload = next(iter(bridge.tasks.values()))['request']
    assert payload['prompt'] == OpenAIGPTImageProvider()._render_prompt(frozen.prompt_plan)
    assert payload['parameters'] == {'codex_adapter': 'codex_cli_imagegen_v1',
        'image_options': {'schema_version': '1', 'transparent_background': True}}
    assert frozen.prompt_plan.quality == 'high' and frozen.prompt_plan.output_format == 'webp'
    assert frozen.prompt_plan.output_compression == 17 and frozen.prompt_plan.size == '1536x1024'


def test_unmarked_legacy_ledger_recovers_without_digest_change(runtime):
    bridge, api = runtime
    async def run():
        prepared = await images.submit_image_job(session_id='session', prompt='Legacy landscape',
            work_intensity='passthrough', provider_preference='fixture_api')
        job, request = prepared.job, prepared.request
        job.raw_response_summary[primary.KEY] = {'request': request.model_dump(mode='json'), 'edit': False, 'units': {}}
        repository.save_job(job)
        unit = primary.primary_request(job, request, 0)
        bridge.state = 'queued'
        async with primary.transport_for('v1') as transport:
            await transport.resolve(unit)
        original_payload = next(iter(bridge.tasks.values()))['request']
        assert 'codex_adapter' not in original_payload['parameters']
        bridge.state = 'artifacts_ready'
        done = await primary.resume_primary_job(job.id)
        assert done.status == JobStatus.ready and bridge.creates == 1 and not api.calls
        assert primary.primary_request(done, primary.frozen_request(done), 0).digest == unit.digest
        assert 'adapter_version' not in done.raw_response_summary[primary.KEY]
    asyncio.run(run())


def test_v1_revision_entry_bridges_exact_source_bytes(runtime):
    from app.schemas import ReviseImageRequest
    bridge, api = runtime
    source = asyncio.run(submit())
    source_bytes = media_store.find_output_file(source.outputs[0].id)[0].read_bytes()
    prepared = asyncio.run(images.submit_revise_image_job(source.id, ReviseImageRequest(
        output_id=source.outputs[0].id, feedback='Make the sky blue', provider_preference='fixture_api')))
    done = asyncio.run(images.run_submitted_image_job(prepared.job.id, prepared.request, edit=True))
    assert done.status == JobStatus.ready and bridge.creates == 2 and not api.calls
    assert len(bridge.inputs) == 1 and bridge.inputs[0][1] == source_bytes
    assert bridge.inputs[0][2] == 'image/png'


@pytest.mark.parametrize('count', [5, 6])
def test_v1_references_preserve_order_and_never_truncate(runtime, tmp_path, monkeypatch, count):
    bridge, api = runtime
    paths = []
    for index in range(count):
        path = tmp_path / f'reference_{index}.png'
        path.write_bytes(bridge.content + bytes([index]))
        paths.append(path)
    async def run():
        prepared = await images.submit_image_job(session_id='session', prompt='Use all references',
            work_intensity='passthrough', provider_preference='fixture_api')
        request = prepared.request.model_copy(update={'asset_ids': [str(i) for i in range(count)]})
        monkeypatch.setattr(media_store, 'find_asset_file', lambda asset_id: paths[int(asset_id)])
        done = await images.run_submitted_image_job(prepared.job.id, request)
        assert done.status == JobStatus.ready
        if count == 5:
            assert bridge.creates == 1 and not api.calls
            assert [item[1] for item in bridge.inputs] == [path.read_bytes() for path in paths]
        else:
            assert bridge.creates == 0 and api.calls == 1 and not bridge.inputs
            assert api.requests[0].asset_ids == request.asset_ids
        unit = primary.primary_request(done, primary.frozen_request(done), 0)
        assert len(unit.references) == count
    asyncio.run(run())


@pytest.mark.parametrize('variable', ['mask', 'input_fidelity_required'])
def test_required_operations_are_not_optional_native_controls(runtime, variable):
    bridge, api = runtime
    async def run():
        prepared = await images.submit_image_job(session_id='session', prompt='Required operation',
            work_intensity='passthrough', provider_preference='fixture_api')
        request = prepared.request.model_copy(deep=True)
        request.prompt_plan.variables[variable] = True
        done = await images.run_submitted_image_job(prepared.job.id, request)
        assert done.status == JobStatus.ready and not bridge.creates and api.calls == 1
        assert api.requests[0].prompt_plan.variables[variable] is True
    asyncio.run(run())


@pytest.mark.parametrize("problem", ["foreign", "missing"])
def test_revision_missing_or_foreign_source_never_admits(runtime, problem):
    from app.schemas import ReviseImageRequest
    bridge, api = runtime
    source = asyncio.run(submit())
    prepared = asyncio.run(images.submit_revise_image_job(source.id, ReviseImageRequest(
        output_id=source.outputs[0].id, feedback='Blue sky', provider_preference='fixture_api')))
    if problem == "foreign":
        prepared.request.veyra_user_id = 99
    else:
        media_store.find_output_file(source.outputs[0].id)[0].unlink()
    done = asyncio.run(images.run_submitted_image_job(prepared.job.id, prepared.request, edit=True))
    assert done.status == JobStatus.generating and done.error.code == 'primary_reconciliation_required'
    assert bridge.creates == 1 and not api.calls and not bridge.inputs


def test_optional_variable_controls_use_defaults_but_frozen_request_is_untouched(runtime):
    bridge, api = runtime
    async def run():
        prepared = await images.submit_image_job(session_id='session', prompt='Native controls',
            work_intensity='passthrough', provider_preference='fixture_api')
        request = prepared.request.model_copy(deep=True)
        controls = {'seed': 123, 'input_fidelity': 'high', 'exact_dimensions': True, 'aspect_ratio': '16:9'}
        request.prompt_plan.variables.update(controls)
        done = await images.run_submitted_image_job(prepared.job.id, request)
        assert done.status == JobStatus.ready and bridge.creates == 1 and not api.calls
        assert next(iter(bridge.tasks.values()))['request']['parameters'] == {'codex_adapter': 'codex_cli_imagegen_v1'}
        assert all(primary.frozen_request(done).prompt_plan.variables[key] == value for key, value in controls.items())
    asyncio.run(run())


def test_unknown_checkpoint_version_never_resubmits_or_falls_back(runtime):
    bridge, api = runtime
    bridge.state = 'queued'
    job = asyncio.run(submit())
    job.raw_response_summary[primary.KEY]['adapter_version'] = 'future_adapter'
    repository.save_job(job)
    done = asyncio.run(primary.resume_primary_job(job.id))
    assert done.status == JobStatus.generating and done.error.code == 'primary_reconciliation_required'
    assert bridge.creates == 1 and not api.calls and not bridge.acks


def test_lab_old_bridge_capabilities_keep_original_high_quality_api(runtime):
    bridge, api = runtime
    bridge.native = False
    session = make_lab_session()
    done = asyncio.run(lab.run_exploration_session(session.id))
    assert done.status == 'completed' and bridge.creates == 0 and api.calls == 1
    assert api.requests[0].prompt_plan.quality == 'high'


def test_revision_does_not_duplicate_source_already_in_references(runtime, monkeypatch):
    from app.schemas import ReviseImageRequest
    bridge, api = runtime
    source = asyncio.run(submit())
    path = media_store.find_output_file(source.outputs[0].id)[0]
    prepared = asyncio.run(images.submit_revise_image_job(source.id, ReviseImageRequest(
        output_id=source.outputs[0].id, feedback='Blue sky', provider_preference='fixture_api')))
    prepared.request.asset_ids = ['existing_source']
    monkeypatch.setattr(media_store, 'find_asset_file', lambda asset_id: path)
    done = asyncio.run(images.run_submitted_image_job(prepared.job.id, prepared.request, edit=True))
    assert done.status == JobStatus.ready and len(bridge.inputs) == 1 and bridge.creates == 2 and not api.calls
