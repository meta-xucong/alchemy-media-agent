"""Existing source failed-state contract: no retry/fallback after proven failure.

The Bridge owns terminal execution proof and slot release. This synthetic HTTP
boundary verifies only Alchemy convergence; it does not attest a real Codex turn.
"""
import asyncio
import pytest
from test_render_bridge_auto_fallback import create_service, preferred
from test_render_bridge_native_coordinator import request
from test_render_bridge_preview import due

@pytest.mark.parametrize('strategy', ['bridge_only','prefer_bridge'])
@pytest.mark.parametrize('before', ['running', 'execution_unknown'])
def test_proven_remote_failure_is_terminal_without_fallback(tmp_path, strategy, before):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.ready = False
        req = preferred() if strategy == 'prefer_bridge' else request()
        try:
            job = await svc.create('101', req)
            queued = await due(svc, job)
            remote = bridge.tasks[queued['origin_key']]
            remote['state'] = before
            assert (await due(svc, job))['state'] == before
            bridge.health = 'unavailable'
            bridge.revision += 1
            remote['state'] = 'failed'
            terminal = await due(svc, job)
            assert terminal['state'] == terminal['remote_state'] == 'failed'
            assert not terminal.get('withdrawal_request')
            assert terminal['cloud_execution_attempted'] is False
            assert gateway.cloud_calls == gateway.register_calls == 0
            assert not bridge.acks
            assert not [c for c in bridge.calls if 'withdraw-before-start' in c[1]]
            assert await svc.local(svc.store.claim_due, 10, 10**15) == []
            with svc.store.connection() as db:
                assert db.execute('SELECT lease_until FROM integration_jobs WHERE id=?',(job['id'],)).fetchone()[0] == 0
            bridge.health = 'available'
            bridge.revision += 1
            assert (await due(svc, job))['state'] == 'failed'
            assert await svc.create('101', req) == await svc.local(svc.store.get, job['id'])
            assert gateway.create_calls == 1 and gateway.cloud_calls == 0
            await svc.close()
            svc, _, _ = create_service(tmp_path, bridge=bridge, gateway=gateway)
            assert (await due(svc, job))['state'] == 'failed'
            assert len(bridge.tasks) == 1 and gateway.create_calls == 1
        finally:
            await svc.close()
    asyncio.run(case())
