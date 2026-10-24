import asyncio
import hashlib
import io
from dataclasses import replace

import pytest
from PIL import Image

from render_bridge_primary import PrimaryRequest, PrimarySettings, PrimaryTransport, PrimaryError
from render_bridge_primary.http import BridgeError


def request(**kw):
    return PrimaryRequest(product='v2', owner_id='u', unit_id='job:0', prompt='image', parameters={}, **kw)


class Client:
    calls = 0
    outcome = None
    async def capabilities(self):
        return {'admission': {'accepting_new_tasks': True}, 'routing_availability_v1': {'profiles':[{'profile_id':'codex-image','health':'available','valid_until':'2099-01-01T00:00:00+00:00'}]}, 'profiles': [{
            'execution_profile_id': 'codex-image', 'execution_profile_revision': '1',
            'parameter_contract': {'accepted_parameters': ['width','height','seed','image_options'], 'dimension_semantics':'original_dimensions_recorded'},
            'image_options_contract': {'quality':{'values':['auto']}, 'output_format':{'values':['png','jpeg']}, 'references':{'max_count':8}},
            'limits': {'max_output_bytes':16777216}}]}
    async def create_task(self, payload):
        self.calls += 1
        self.payload = payload
        if self.outcome: raise self.outcome
        return {'remote_task_id':'task_1','origin_key':payload['origin_key'],'request':payload,'state':'queued','receipt_id':None,'attempt_id':'attempt_1'}
    async def by_origin(self, origin):
        raise BridgeError('not_found', status=404)
    async def close(self): pass


def settings(tmp_path):
    return PrimarySettings(enabled=True,base_url='http://127.0.0.1:9999',token='fixture',state_dir=tmp_path)


def test_loss_restart_404_never_fallback(tmp_path):
    c=Client(); c.outcome=BridgeError('bridge_unreachable')
    first=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request()))
    second=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request()))
    assert first.route == second.route == 'bridge'
    assert second.state == 'bridge_submission_unknown'
    assert c.calls == 1


@pytest.mark.parametrize('code,status,route',[('queue_capacity',429,'api'),('bridge_draining',503,'api'),('bridge_request_failed',503,'bridge')])
def test_nonadmission(tmp_path,code,status,route):
    c=Client(); c.outcome=BridgeError(code,status=status)
    assert asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request())).route==route


def test_semantics_cannot_change_same_unit(tmp_path):
    t=PrimaryTransport(settings(tmp_path),client=Client())
    asyncio.run(t.resolve(request()))
    with pytest.raises(PrimaryError,match='request_semantics_changed'):
        asyncio.run(t.resolve(replace(request(),prompt='different')))


def test_api_claim_is_one_way(tmp_path):
    c=Client(); c.outcome=BridgeError('queue_capacity',status=429)
    t=PrimaryTransport(settings(tmp_path),client=c)
    asyncio.run(t.resolve(request()))
    assert t.claim_api(request()) is True
    assert t.claim_api(request()) is False
    assert asyncio.run(t.resolve(request())).state=='api_execution_unknown'


def test_hard_controls_reject_before_create(tmp_path):
    c=Client(); t=PrimaryTransport(settings(tmp_path),client=c)
    r=asyncio.run(t.resolve(request(hard_requirements={'mask':True})))
    assert r.reason=='bridge_capability_unsupported' and r.route=='api' and c.calls==0


def test_disabled_no_state_and_owned_work_sticky(tmp_path):
    disabled=replace(settings(tmp_path),enabled=False)
    t=PrimaryTransport(disabled,client=Client())
    assert asyncio.run(t.resolve(request())).reason=='bridge_disabled'
    assert not (tmp_path/'primary.sqlite3').exists()
    c=Client(); t=PrimaryTransport(settings(tmp_path),client=c)
    asyncio.run(t.resolve(request()))
    assert asyncio.run(PrimaryTransport(disabled,client=c).resolve(request())).route=='bridge'
    assert c.calls==1


def test_concurrent_first_create_single_permit(tmp_path):
    class Slow(Client):
        async def capabilities(self):
            await asyncio.sleep(.01)
            return await super().capabilities()
    async def run():
        c=Slow()
        a=PrimaryTransport(settings(tmp_path),client=c)
        b=PrimaryTransport(settings(tmp_path),client=c)
        results=await asyncio.gather(a.resolve(request()),b.resolve(request()))
        assert all(x.route=='bridge' for x in results)
        assert c.calls==1
    asyncio.run(run())


class ReceiptClient(Client):
    def __init__(self):
        stream=io.BytesIO(); Image.new('RGB',(7,11),(10,30,20)).save(stream,format='PNG')
        self.content=stream.getvalue(); self.acks=[]; self.cancels=[]
    async def create_task(self,payload):
        result=await super().create_task(payload)
        return {**result,'state':'artifacts_ready','receipt_id':'receipt_1','attempt_id':'attempt_1'}
    async def receipt(self,receipt_id):
        return {'receipt_id':receipt_id,'task_id':'task_1','artifact_id':'artifact_1','attempt_id':'attempt_1','execution_profile_id':'codex-image','execution_profile_revision':'1','slot_id':'primary',
                'original_sha256':hashlib.sha256(self.content).hexdigest(),'size':len(self.content),
                'mime_type':'image/png','dimensions':{'width':7,'height':11}}
    async def artifact(self,artifact_id,limit): return self.content,{}
    async def accept_registered_receipt(self,*args,**kwargs): self.acks.append((args,kwargs))
    async def cancel(self,task_id): self.cancels.append(task_id)


def test_original_bytes_durable_and_ack_deferred(tmp_path):
    c=ReceiptClient(); t=PrimaryTransport(settings(tmp_path),client=c)
    result=asyncio.run(t.resolve(request()))
    assert result.image.content==c.content
    assert (result.image.width,result.image.height)==(7,11)
    assert not c.acks
    restarted=PrimaryTransport(settings(tmp_path),client=c)
    assert asyncio.run(restarted.resolve(request())).image.content==c.content
    asyncio.run(restarted.acknowledge(request(),'product:job:output'))
    assert len(c.acks)==1 and c.calls==1
    asyncio.run(restarted.acknowledge(request(),'product:job:output'))
    assert len(c.acks)==1


def test_receipt_metadata_mismatch_fails_closed(tmp_path):
    class Bad(ReceiptClient):
        async def receipt(self,rid):
            return {**await super().receipt(rid),'dimensions':{'width':2,'height':2}}
    with pytest.raises(PrimaryError,match='bridge_artifact_metadata_mismatch'):
        asyncio.run(PrimaryTransport(settings(tmp_path),client=Bad()).resolve(request()))


def test_health_expired_no_create(tmp_path):
    class Stale(Client):
        async def capabilities(self):
            caps=await super().capabilities()
            caps['routing_availability_v1']['profiles'][0]['valid_until']='2000-01-01T00:00:00Z'
            return caps
    c=Stale()
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request()))
    assert result.reason=='bridge_unavailable' and c.calls==0


def test_cancel_unknown_does_not_create_again(tmp_path):
    c=Client(); c.outcome=BridgeError('bridge_unreachable')
    t=PrimaryTransport(settings(tmp_path),client=c)
    asyncio.run(t.resolve(request()))
    assert asyncio.run(t.cancel(request())).route=='bridge'
    assert c.calls==1


def test_scope_changes_fail_closed(tmp_path):
    c=Client(); t=PrimaryTransport(settings(tmp_path),client=c)
    asyncio.run(t.resolve(request()))
    with pytest.raises(PrimaryError,match='bridge_scope_changed'):
        asyncio.run(PrimaryTransport(replace(settings(tmp_path),base_url='http://localhost:111'),client=c).resolve(request()))


def test_pending_count_api_unknown(tmp_path):
    from render_bridge_primary import pending_count
    c=Client(); c.outcome=BridgeError('queue_capacity',status=429)
    t=PrimaryTransport(settings(tmp_path),client=c)
    asyncio.run(t.resolve(request()))
    assert pending_count(tmp_path)==0
    t.claim_api(request()); assert pending_count(tmp_path)==1
    t.complete_api(request()); assert pending_count(tmp_path)==0


@pytest.mark.parametrize('patch',[{'schema_version':'2'},{'profiles':'codex-image'},{'profiles':['unknown']},{'mode':'yes'},{'base_url':'http://example.com'},{'base_url':'https://user:pass@example.com'},{'base_url':'https://example.com/path'}])
def test_invalid_control_fails_closed(tmp_path,monkeypatch,patch):
    import json
    path=tmp_path/'control.json'
    path.write_text(json.dumps({'schema_version':'1','mode':'enabled','profiles':['codex-image'],'base_url':'https://bridge.example','workspace':'test',**patch}))
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG',str(path))
    with pytest.raises(PrimaryError): PrimarySettings.from_env('v2')


def test_loopback_requires_explicit_environment_opt_in(tmp_path,monkeypatch):
    import json
    path=tmp_path/'control.json'
    path.write_text(json.dumps({'schema_version':'1','mode':'enabled','profiles':['codex-image'],'base_url':'http://127.0.0.1:9999','workspace':'test'}))
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG',str(path))
    monkeypatch.delenv('ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK',raising=False)
    with pytest.raises(PrimaryError): PrimarySettings.from_env('v2')
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK','true')
    assert PrimarySettings.from_env('v2').enabled


def test_cancel_binding_latches_and_suppresses_late_pixels(tmp_path):
    class Late(ReceiptClient):
        async def by_origin(self,origin):
            return {'remote_task_id':'task_1','origin_key':origin,'request':self.payload,'state':'artifacts_ready','receipt_id':'receipt_1','attempt_id':'attempt_1'}
    c=Late(); t=PrimaryTransport(settings(tmp_path),client=c)
    asyncio.run(t.resolve(request()))
    result=asyncio.run(t.cancel_binding('v2','u','job:0'))
    assert result.state=='cancel_requested' and result.image is None and c.calls==1
    assert asyncio.run(t.resolve(request())).image is None
    with pytest.raises(PrimaryError,match='bridge_cancel_requested'):
        asyncio.run(t.acknowledge(request(),'product:late'))


def test_cancel_binding_unknown_unit_never_creates(tmp_path):
    c=Client(); t=PrimaryTransport(settings(tmp_path),client=c)
    with pytest.raises(PrimaryError,match='route_not_resolved'):
        asyncio.run(t.cancel_binding('v2','u','missing'))
    assert c.calls==0


def test_cancel_listing_scopes_product_owner_and_prefix(tmp_path):
    t=PrimaryTransport(settings(tmp_path),client=Client())
    asyncio.run(t.resolve(request()))
    assert t.bindings_for('v2','u','job:')==['job:0']
    assert t.bindings_for('v2','other','job:')==[]
    assert t.bindings_for('v3','u','job:')==[]
    assert t.bindings_for('v2','u','else:')==[]


def test_stale_queued_observation_cannot_erase_artifact_or_ack(tmp_path):
    import json
    c=ReceiptClient(); t=PrimaryTransport(settings(tmp_path),client=c)
    result=asyncio.run(t.resolve(request()))
    data=json.loads(t._read(request())['data'])
    stale={k:v for k,v in data.items() if k not in {'image','receipt_id'}}
    stale['state']='queued'
    t._save(request(),stale)
    replay=asyncio.run(t.resolve(request()))
    assert replay.image.content==c.content and replay.state=='artifacts_ready'
    asyncio.run(t.acknowledge(request(),'product:registered'))
    t._save(request(),stale)
    assert asyncio.run(t.resolve(request())).state=='acked'


@pytest.mark.parametrize('field,value',[('attempt_id','wrong'),('execution_profile_id','fake-image'),('execution_profile_revision','2'),('slot_id','other')])
def test_receipt_execution_identity_bound(tmp_path,field,value):
    class Wrong(ReceiptClient):
        async def receipt(self,rid): return {**await super().receipt(rid),field:value}
    with pytest.raises(PrimaryError,match='bridge_receipt_identity_mismatch'):
        asyncio.run(PrimaryTransport(settings(tmp_path),client=Wrong()).resolve(request()))


def test_cancel_racing_first_nonadmission_does_not_select_api(tmp_path):
    class CancelFirst(Client):
        async def create_task(self,payload):
            self.payload=payload; self.calls+=1
            await t.cancel_binding('v2','u','job:0')
            raise BridgeError('queue_capacity',status=429)
    c=CancelFirst(); t=PrimaryTransport(settings(tmp_path),client=c)
    result=asyncio.run(t.resolve(request()))
    assert result.route=='bridge' and result.state=='cancel_requested'


@pytest.mark.parametrize('parameters',[{'width':50000},{'width':10000,'height':10000},{'seed':2**32},{'width':True}])
def test_known_parameter_limits_fallback_before_post(tmp_path,parameters):
    c=Client(); t=PrimaryTransport(settings(tmp_path),client=c)
    result=asyncio.run(t.resolve(replace(request(),parameters=parameters)))
    assert result.reason=='bridge_capability_unsupported' and c.calls==0


def test_explicit_disabled_api_claim_for_owned_batch_is_durable(tmp_path):
    t=PrimaryTransport(replace(settings(tmp_path),enabled=False),client=Client())
    assert asyncio.run(t.resolve(request())).reason=='bridge_disabled'
    assert t.claim_api(request()) is True
    assert t.claim_api(request()) is False
    assert asyncio.run(t.resolve(request())).state=='api_execution_unknown'


def test_safe_provenance_captures_diagnostic_queue_without_claiming_model(tmp_path):
    class Snapshot(Client):
        async def capabilities(self):
            return {**await super().capabilities(),'queue':{'active_tasks':9,'max_queued_tasks':10}}
    c=Snapshot(); t=PrimaryTransport(settings(tmp_path),client=c)
    result=asyncio.run(t.resolve(request()))
    p=result.provenance
    assert p['product']=='v2' and p['execution_profile_id']=='codex-image'
    assert p['queue_active_count']==9 and p['queue_limit']==10
    assert p['queue_snapshot_diagnostic'] is True
    assert p['actual_provider']=='render_bridge' and p['provider_evidence']=='transport_only'
    assert p['actual_model'] is None and p['model_evidence']=='not_reported'
    replay=asyncio.run(t.resolve(request()))
    assert replay.provenance['queue_observed_at']==p['queue_observed_at']
    assert c.calls==1


def test_queue_snapshot_is_not_admission_authority(tmp_path):
    class FullSnapshot(Client):
        async def capabilities(self):
            return {**await super().capabilities(),'queue':{'active_tasks':10,'max_queued_tasks':10}}
    c=FullSnapshot()
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request()))
    assert result.route=='bridge' and c.calls==1


def test_ack_intent_survives_lost_response_and_terminal_product_restart(tmp_path):
    class LostAck(ReceiptClient):
        async def accept_registered_receipt(self,*args,**kwargs):
            await super().accept_registered_receipt(*args,**kwargs)
            if len(self.acks)==1: raise BridgeError('bridge_unreachable')
    c=LostAck(); t=PrimaryTransport(settings(tmp_path),client=c)
    asyncio.run(t.resolve(request()))
    with pytest.raises(BridgeError): asyncio.run(t.acknowledge(request(),'product:verified-output'))
    with pytest.raises(PrimaryError,match='native_registration_mismatch'):
        asyncio.run(t.acknowledge(request(),'different-output'))
    # Native registration/ACK intent precedes and therefore wins over a later cancel.
    asyncio.run(t.cancel(request()))
    restarted=PrimaryTransport(replace(settings(tmp_path),enabled=False),client=c)
    result=asyncio.run(restarted.reconcile_pending())
    assert result['acked']==1 and c.acks[0]==c.acks[1]
    assert asyncio.run(restarted.resolve(request())).state=='acked'
    assert asyncio.run(restarted.reconcile_pending())['checked']==0
    assert c.calls==1 and not c.cancels


def test_cancel_inflight_origin_absent_then_maintenance_recovers_same_task(tmp_path):
    class Delayed(Client):
        def __init__(self):
            self.entered=asyncio.Event(); self.release=asyncio.Event(); self.remote=None; self.cancels=[]
        async def create_task(self,payload):
            self.calls+=1; self.payload=payload; self.entered.set(); await self.release.wait()
            self.remote={'remote_task_id':'task_1','origin_key':payload['origin_key'],'request':payload,'state':'queued','receipt_id':None,'attempt_id':'attempt_1'}
            raise BridgeError('bridge_unreachable')
        async def by_origin(self,origin):
            if self.remote is None: raise BridgeError('not_found',status=404)
            return dict(self.remote)
        async def cancel(self,task_id):
            self.cancels.append(task_id); self.remote['state']='canceled'
    async def run():
        c=Delayed(); t=PrimaryTransport(settings(tmp_path),client=c)
        creating=asyncio.create_task(t.resolve(request())); await c.entered.wait()
        assert (await t.cancel(request())).state=='cancel_requested'
        c.release.set(); assert (await creating).state=='cancel_requested'
        restarted=PrimaryTransport(settings(tmp_path),client=c)
        assert (await restarted.reconcile_pending())['pending']==1
        assert (await restarted.reconcile_pending())['canceled']==1
        assert (await restarted.reconcile_pending())['checked']==0
        assert c.calls==1 and c.cancels==['task_1']
        assert (await restarted.resolve(request())).state=='canceled'
    asyncio.run(run())


def test_maintenance_scope_guard_and_no_intent_no_http(tmp_path):
    c=ReceiptClient(); t=PrimaryTransport(settings(tmp_path),client=c)
    assert asyncio.run(t.reconcile_pending())['checked']==0
    asyncio.run(t.resolve(request()))
    assert asyncio.run(t.reconcile_pending())['checked']==0
    async def fail(*args,**kwargs): raise BridgeError('bridge_unreachable')
    c.accept_registered_receipt=fail
    with pytest.raises(BridgeError): asyncio.run(t.acknowledge(request(),'native-output'))
    wrong=PrimaryTransport(replace(settings(tmp_path),workspace='changed'),client=c)
    assert asyncio.run(wrong.reconcile_pending())['errors']==1
    assert asyncio.run(t.resolve(request())).state=='artifacts_ready'


def test_bindings_active_only_omits_registered_output_and_terminal_units(tmp_path):
    c=ReceiptClient(); t=PrimaryTransport(settings(tmp_path),client=c)
    asyncio.run(t.resolve(request()))
    assert t.bindings_for('v2','u','job:',route='bridge')==['job:0']
    assert t.bindings_for('v2','u','job:',route='bridge',active_only=True)==['job:0']
    asyncio.run(t.acknowledge(request(),'native-output'))
    assert t.bindings_for('v2','u','job:',route='bridge',active_only=True)==[]
    pending=replace(request(),unit_id='job:1'); c.state='queued'
    c.create_task=Client.create_task.__get__(c,ReceiptClient)
    asyncio.run(t.resolve(pending))
    assert t.bindings_for('v2','u','job:',route='bridge',active_only=True)==['job:1']
