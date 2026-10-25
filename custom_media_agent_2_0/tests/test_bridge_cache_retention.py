"""Synthetic published jobs only; no provider, billing, or external HTTP."""
import asyncio
import base64
import hashlib
import json
from datetime import datetime, timezone
from dataclasses import replace

import pytest

from app.repositories import repository
from app.schemas import CreateImageJobRequest, ImagePromptPlan, ImageJob, ImageOutput
from app.services import render_bridge_primary as bridge
from app.providers.images.base import V2ImageProviderResult, V2ImageProviderOutput
from render_bridge_primary import PrimarySettings, PrimaryTransport, PrimaryError
from render_bridge_primary.http import BridgeError


class Client:
    calls = 0
    fail = False
    async def close(self): pass
    async def accept_registered_receipt(self, *a, **kw):
        self.calls += 1
        if self.fail: raise BridgeError('bridge_unreachable')


@pytest.fixture
def published(tmp_path, monkeypatch):
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT', str(tmp_path / 'ledger'))
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG', str(tmp_path / 'no-config'))
    request = CreateImageJobRequest(veyra_user_id=17, prompt_plan=ImagePromptPlan(
        plan_id='plan', mode='smart_enhance', prompt='blue vase', provider_parameters={'count': 1}))
    now = datetime.now(timezone.utc)
    record = bridge.freeze(request, 'job', now, False)
    record['references'] = [{'content': base64.b64encode(b'private reference bytes').decode(), 'mime_type': 'image/png'}]
    record['queue_task_id'] = 'queue-task'
    for key in ['job:job', 'task:queue-task']:
        bridge._path(key).write_text(json.dumps(record), encoding='utf-8')
    output = ImageOutput(output_id='output', job_id='job', url='/native/output', created_at=now)
    job = ImageJob(job_id='job', run_id=None, status='completed', provider_id='render_bridge',
        model='native', prompt_plan=request.prompt_plan, outputs=[output], created_at=now, updated_at=now)
    repository.save_image_job(job)
    content = b'private result bytes'
    cached = V2ImageProviderResult(provider='render_bridge', model='native', outputs=[
        V2ImageProviderOutput(b64_json=base64.b64encode(content).decode(), mime_type='image/png', format='png')])
    bridge._cache_path(record, 0).write_text(cached.model_dump_json(), encoding='utf-8')
    client = Client()
    transport = PrimaryTransport(PrimarySettings(state_dir=tmp_path / 'ledger/v2'), client=client)
    unit = bridge._unit_request(record, 0, transport)
    row = transport._start(unit)
    data = json.loads(row['data'])
    data.update(state='artifacts_ready', receipt_id='receipt', task_id='task', attempt_id='attempt',
        image={'sha256': hashlib.sha256(content).hexdigest(), 'mime_type': 'image/png', 'width': 2, 'height': 3})
    transport._save(unit, data, image=content)
    monkeypatch.setattr(bridge, 'transport', lambda *a: transport)
    return record, unit, transport, client


def test_ack_releases_duplicates_preserves_native_output_and_tombstone(published):
    record, unit, transport, client = published
    assert asyncio.run(bridge.acknowledge(record))
    retired = bridge.load_frozen('job')
    assert retired['cache_retired'] and retired['references'] == []
    assert retired['request']['veyra_user_id'] == 17
    assert json.loads(bridge._path('task:queue-task').read_text())['references'] == []
    assert not bridge._cache_path(record, 0).exists()
    assert repository.get_output('output').url == '/native/output'
    row = transport._read(unit)
    assert row['image'] is None and row['digest'] == unit.digest
    assert json.loads(row['data'])['cache_retired']
    assert asyncio.run(bridge.acknowledge(retired))
    assert client.calls == 1
    with pytest.raises(bridge.BridgeWait, match='bridge_cache_retired'):
        asyncio.run(bridge._generate(retired, None, transport))
    # A stale result cannot repopulate bytes; changed semantics cannot reuse key.
    transport._save(unit, json.loads(row['data']), image=b'stale')
    assert transport._read(unit)['image'] is None
    with pytest.raises(PrimaryError, match='request_semantics_changed'):
        transport.retire_units([replace(unit, prompt='different')])


def test_lost_ack_keeps_recovery_bytes_then_bounded_maintenance_retires(published):
    record, unit, transport, client = published
    client.fail = True
    assert not asyncio.run(bridge.acknowledge(record))
    assert bridge._cache_path(record, 0).exists()
    assert transport._read(unit)['image'] is not None
    assert not bridge.load_frozen('job').get('cache_retired')
    client.fail = False
    assert asyncio.run(bridge.maintain_completed_caches(limit=1)) == 1
    assert bridge.load_frozen('job')['cache_retired']
    assert asyncio.run(bridge.maintain_completed_caches()) == 0


@pytest.mark.parametrize('state', ['queued', 'execution_unknown', 'api_execution_unknown', 'artifacts_ready'])
def test_unresolved_or_unacked_unit_never_retired(published, state):
    record, unit, transport, client = published
    with transport._db() as db:
        row = transport._read(unit); data = json.loads(row['data']); data['state'] = state
        db.execute('UPDATE units SET state=?, data=? WHERE key=?', (state, json.dumps(data), unit.key))
    assert not bridge._retire_completed_cache(record, transport)
    assert bridge._cache_path(record, 0).exists()
    assert transport._read(unit)['image'] is not None


def test_api_completed_unit_cache_can_retire_without_remote_ack(published):
    record, unit, transport, client = published
    row = transport._read(unit); data = json.loads(row['data'])
    data.update(route='api', state='api_completed')
    with transport._db() as db:
        db.execute('UPDATE units SET state=?,data=? WHERE key=?', ('api_completed', json.dumps(data), unit.key))
    assert bridge._retire_completed_cache(record, transport)
    assert not bridge._cache_path(record, 0).exists() and client.calls == 0
    assert not transport.claim_api(unit)


def test_native_unsettled_job_not_retired_even_with_ack(published):
    record, unit, transport, client = published
    asyncio.run(transport.acknowledge(unit, 'v2:job:0'))
    job = repository.get_image_job('job')
    repository.save_image_job(job.model_copy(update={'status': 'queued'}))
    assert not bridge._retire_completed_cache(record, transport)
    assert bridge._cache_path(record, 0).exists()


def test_delete_native_output_does_not_resurrect_on_completed_replay(published):
    record, unit, transport, client = published
    assert asyncio.run(bridge.acknowledge(record))
    repository.delete_output('output')
    assert bridge.cleanup_published_job_cache('job')
    assert repository.get_image_job('job').outputs == []
    assert asyncio.run(bridge.acknowledge(bridge.load_frozen('job')))
    assert repository.get_output('output') is None


def test_restart_after_ledger_retirement_before_frozen_files(published):
    record, unit, transport, client = published
    asyncio.run(transport.acknowledge(unit, 'v2:job:0'))
    assert transport.retire_units([unit])
    assert not bridge.load_frozen('job').get('cache_retired')
    bridge.request_cache_cleanup('job')
    assert asyncio.run(bridge.maintain_completed_caches()) == 1
    assert bridge.load_frozen('job')['cache_retired']
    assert not bridge._cache_path(record, 0).exists()


def test_restart_after_only_job_tombstone_written(published, monkeypatch):
    record, unit, transport, client = published
    original = bridge.os.replace
    task_path = bridge._path('task:queue-task')
    def crash(source, target):
        if target == task_path: raise OSError('synthetic crash')
        return original(source, target)
    monkeypatch.setattr(bridge.os, 'replace', crash)
    assert not asyncio.run(bridge.acknowledge(record))
    assert bridge.load_frozen('job')['cache_retired']
    assert json.loads(task_path.read_text())['references']
    monkeypatch.setattr(bridge.os, 'replace', original)
    assert asyncio.run(bridge.maintain_completed_caches()) == 1
    assert json.loads(task_path.read_text())['references'] == []
    assert not bridge._cache_path(record, 0).exists()


def test_completed_generation_entry_after_delete_keeps_empty_native_job(published, monkeypatch):
    from app.services import generation
    record, unit, transport, client = published
    assert asyncio.run(bridge.acknowledge(record))
    repository.delete_output('output')
    async def forbidden(*a, **kw): raise AssertionError('deleted image must not be regenerated')
    monkeypatch.setattr(generation, 'get_v2_image_provider', forbidden)
    result = asyncio.run(generation.create_image_job(bridge.frozen_request(record), job_id='job'))
    assert result.status == 'completed' and result.outputs == []
    assert repository.get_output('output') is None


def test_multi_unit_retirement_is_all_or_nothing(published):
    record, unit, transport, client = published
    asyncio.run(transport.acknowledge(unit, 'v2:job:0'))
    other = replace(unit, unit_id='job:1')
    transport._start(other)
    assert not transport.retire_units([unit, other])
    assert transport._read(unit)['image'] is not None


def test_malformed_cleanup_record_is_retained_without_worker_failure(published):
    record, unit, transport, client = published
    bridge.request_cache_cleanup('job')
    path = bridge._path('job:job')
    path.write_text('{"malformed": true}', encoding='utf-8')
    assert asyncio.run(bridge.maintain_completed_caches()) == 0
    assert path.exists() and bridge._cache_path(record, 0).exists()
    assert transport._read(unit)['image'] is not None and client.calls == 0
