import asyncio
import hashlib
import io
import struct
from dataclasses import replace
import zlib

import pytest
from PIL import Image

from render_bridge_primary import PrimaryRequest, PrimarySettings, PrimaryTransport, PrimaryError, Reference
from render_bridge_primary.http import BridgeError


def request(**kw):
    return PrimaryRequest(product='v2', owner_id='u', unit_id='job:0', prompt='image', parameters={}, **kw)


class Client:
    calls = 0
    outcome = None
    async def capabilities(self):
        return {'admission': {'accepting_new_tasks': True},
            'limits': {'max_input_bytes':16*1024*1024,'max_input_image_pixels':16*1024*1024},
            'routing_availability_v1': {'profiles':[{'profile_id':'codex-image','health':'available','valid_until':'2099-01-01T00:00:00+00:00'}]}, 'profiles': [{
            'execution_profile_id': 'codex-image', 'execution_profile_revision': '1',
            'parameter_contract': {'accepted_parameters': ['width','height','seed','image_options'], 'dimension_semantics':'original_dimensions_recorded'},
            'image_options_contract': {'quality':{'values':['auto']}, 'output_format':{'values':['png','jpeg']}, 'references':{'max_count':8}},
            'limits': {'max_input_bytes':16*1024*1024,'max_input_image_pixels':16*1024*1024,
                       'max_output_bytes':16777216}}]}
    async def create_input(self, payload):
        return {'input_id':payload['input_key']}
    async def upload_input(self, input_id, content, mime_type):
        self.uploaded=(input_id,content,mime_type)
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


@pytest.mark.parametrize('code,status,route',[('queue_capacity',429,'api'),('bridge_draining',503,'api'),('node_unavailable',503,'api'),('bridge_request_failed',503,'bridge')])
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
    results={}
    for product in ('v2','v3'):
        req=PrimaryRequest(product=product, owner_id='u', unit_id='job:0', prompt='image',
                           parameters={}, hard_requirements={'mask':True})
        results[product]=asyncio.run(t.resolve(req))
    assert all(r.reason=='bridge_capability_unsupported' and r.route=='api' for r in results.values())
    assert c.calls==0
    assert results['v2'].provenance.get('capability_rejection') is None
    assert results['v3'].provenance['capability_rejection']=={
        'code':'hard_requirement_not_advertised','field':'mask'}


def test_v3_capability_rejection_records_safe_input_reason(tmp_path):
    c=Client(); t=PrimaryTransport(settings(tmp_path),client=c)
    oversized=Reference(b'x' * (16 * 1024 * 1024 + 1), 'image/png')
    r=asyncio.run(t.resolve(PrimaryRequest(
        product='v3', owner_id='u', unit_id='job:0', prompt='image', parameters={},
        references=(oversized,),
    )))
    assert r.route=='api' and r.reason=='bridge_capability_unsupported' and c.calls==0
    assert r.provenance['capability_rejection']=={'code':'reference_input_over_byte_limit'}
    assert str(len(oversized.content)) not in repr(r.provenance)


def _padded_png(size, target_bytes):
    stream=io.BytesIO()
    Image.new('RGB',size,'blue').save(stream,format='PNG')
    content=stream.getvalue()
    chunk_data=b'Comment\0'+b'x'*(target_bytes-len(content)-12)
    chunk=(struct.pack('>I',len(chunk_data))+b'tEXt'+chunk_data+
           struct.pack('>I',zlib.crc32(b'tEXt'+chunk_data)&0xffffffff))
    return content[:-12]+chunk+content[-12:]


def _png_header_with_dimensions(width, height):
    stream = io.BytesIO()
    Image.new('RGB', (1, 1), 'blue').save(stream, format='PNG')
    content = bytearray(stream.getvalue())
    content[16:20] = struct.pack('>I', width)
    content[20:24] = struct.pack('>I', height)
    content[29:33] = struct.pack('>I', zlib.crc32(b'IHDR' + content[16:29]) & 0xffffffff)
    return bytes(content)


def test_2986403_byte_reference_is_sent_to_bridge_unchanged(tmp_path):
    original=_padded_png((1024,1536),2_976_403)
    client=Client()
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=client).resolve(
        PrimaryRequest(product='v3',owner_id='u',unit_id='job:0',prompt='image',parameters={},
                       references=(Reference(original,'image/png'),))))
    assert result.route=='bridge'
    input_id='rb_'+PrimaryRequest(product='v3',owner_id='u',unit_id='job:0',prompt='image',parameters={}).key+'_0'
    assert client.uploaded==(input_id,original,'image/png')
    assert client.payload['references']==[{'input_ref':input_id,'role':'reference',
                                           'hash':hashlib.sha256(original).hexdigest()}]


def test_legacy_bridge_missing_input_pixel_limit_uses_current_bound(tmp_path):
    class Legacy(Client):
        async def capabilities(self):
            caps=await super().capabilities()
            caps['limits'].pop('max_input_image_pixels')
            return caps
    c=Legacy(); t=PrimaryTransport(settings(tmp_path),client=c)
    too_many_pixels=Reference(_png_header_with_dimensions(4097,4097),'image/png')
    result=asyncio.run(t.resolve(PrimaryRequest(product='v3',owner_id='u',unit_id='job:0',
        prompt='image',parameters={},references=(too_many_pixels,))))
    assert result.route=='api' and result.reason=='bridge_capability_unsupported'
    assert result.provenance['capability_rejection']=={'code':'reference_input_over_pixel_limit'}
    assert c.calls==0


def test_legacy_bridge_missing_input_byte_limit_uses_current_bound(tmp_path):
    class Legacy(Client):
        async def capabilities(self):
            caps=await super().capabilities()
            caps['limits'].pop('max_input_bytes')
            return caps
    c=Legacy(); t=PrimaryTransport(settings(tmp_path),client=c)
    oversized=Reference(b'x' * (16 * 1024 * 1024 + 1), 'image/png')
    result=asyncio.run(t.resolve(PrimaryRequest(product='v3',owner_id='u',unit_id='job:0',
        prompt='image',parameters={},references=(oversized,))))
    assert result.route=='api' and result.reason=='bridge_capability_unsupported'
    assert result.provenance['capability_rejection']=={'code':'reference_input_over_byte_limit'}
    assert c.calls==0


def test_new_bridge_rejects_input_pixels_above_advertised_bound_before_upload(tmp_path):
    c=Client(); t=PrimaryTransport(settings(tmp_path),client=c)
    too_many_pixels=Reference(_png_header_with_dimensions(4097,4097),'image/png')
    result=asyncio.run(t.resolve(PrimaryRequest(product='v3',owner_id='u',unit_id='job:0',
        prompt='image',parameters={},references=(too_many_pixels,))))
    assert result.route=='api' and result.reason=='bridge_capability_unsupported'
    assert result.provenance['capability_rejection']=={'code':'reference_input_over_pixel_limit'}
    assert not hasattr(c,'uploaded') and c.calls==0


@pytest.mark.parametrize('content,mime', [
    pytest.param(b'not an image', 'image/png', id='invalid-image'),
    pytest.param(_png_header_with_dimensions(9500, 9500), 'image/png', id='decompression-bomb'),
    pytest.param(_png_header_with_dimensions(1, 1), 'image/jpeg', id='mime-mismatch'),
])
def test_invalid_or_decompression_bomb_reference_never_uploads(tmp_path, content, mime):
    client = Client()
    result = asyncio.run(PrimaryTransport(settings(tmp_path), client=client).resolve(
        PrimaryRequest(product='v3', owner_id='u', unit_id='job:0', prompt='image',
                       parameters={}, references=(Reference(content, mime),))))
    assert result.route == 'api' and result.reason == 'bridge_capability_unsupported'
    assert result.provenance['capability_rejection']['code'] in {
        'reference_input_format', 'reference_input_invalid', 'reference_input_over_pixel_limit',
    }
    assert not hasattr(client, 'uploaded') and client.calls == 0


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


def test_expired_profile_health_does_not_silently_select_api(tmp_path):
    class Stale(Client):
        async def capabilities(self):
            caps=await super().capabilities()
            caps['routing_availability_v1']['profiles'][0]['valid_until']='2000-01-01T00:00:00Z'
            return caps
    c=Stale()
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request()))
    assert result.route=='bridge' and result.state=='queued' and c.calls==1


def test_unknown_profile_health_does_not_silently_select_api(tmp_path):
    class Unverified(Client):
        async def capabilities(self):
            caps=await super().capabilities()
            caps['routing_availability_v1']['profiles'][0].update(
                health='unknown', reason_code='unverified', valid_until=None)
            return caps
    c=Unverified()
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request()))
    assert result.route=='bridge' and result.state=='queued' and c.calls==1


def test_explicitly_unavailable_profile_health_keeps_bridge_primary(tmp_path):
    class Unavailable(Client):
        async def capabilities(self):
            caps=await super().capabilities()
            caps['routing_availability_v1']['profiles'][0].update(
                health='unavailable', reason_code='auth_unavailable')
            return caps
    c=Unavailable()
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request()))
    assert result.route=='bridge' and result.state=='queued' and c.calls==1


def _small_png():
    stream=io.BytesIO()
    Image.new('RGB',(7,11),'blue').save(stream,format='PNG')
    return stream.getvalue()


def test_store_busy_input_upload_retries_once_after_retry_after(tmp_path, monkeypatch):
    import time

    class BusyOnce(Client):
        def __init__(self):
            self.input_keys=[]
            self.uploads=[]
        async def create_input(self, payload):
            self.input_keys.append(dict(payload))
            return {'input_id':payload['input_key']}
        async def upload_input(self, input_id, content, mime_type):
            self.uploads.append((input_id,content,mime_type))
            if len(self.uploads)==1:
                raise BridgeError('store_busy',status=503,retry_not_before=time.time()+60)

    delays=[]
    async def no_wait(delay): delays.append(delay)
    monkeypatch.setattr(asyncio,'sleep',no_wait)
    content=_small_png(); c=BusyOnce(); req=replace(request(),references=(Reference(content,'image/png'),))
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(req))
    assert result.route=='bridge' and result.state=='queued' and c.calls==1
    assert delays and delays[0]>=59
    assert len(c.input_keys)==1 and c.input_keys[0]['input_key']==f'{result.origin_key}_0'
    assert c.uploads==[(c.input_keys[0]['input_key'],content,'image/png')]*2


def test_store_busy_input_upload_stays_preflight_and_recovers_same_origin(tmp_path, monkeypatch):
    import time

    class BusyThenReady(Client):
        def __init__(self):
            self.input_keys=[]
            self.uploads=[]
            self.busy=True
        async def create_input(self, payload):
            self.input_keys.append(dict(payload))
            return {'input_id':payload['input_key']}
        async def upload_input(self, input_id, content, mime_type):
            self.uploads.append((input_id,content,mime_type))
            if self.busy:
                raise BridgeError('store_busy',status=503,retry_not_before=time.time()+60)

    async def no_wait(_delay): pass
    monkeypatch.setattr(asyncio,'sleep',no_wait)
    content=_small_png(); c=BusyThenReady(); req=replace(request(),references=(Reference(content,'image/png'),))
    transport=PrimaryTransport(settings(tmp_path),client=c)
    first=asyncio.run(transport.resolve(req))
    stored=transport._read(req)
    import json
    assert first.route=='bridge' and first.state=='failed' and first.reason=='bridge_store_busy'
    assert first.provenance['state']=='failed' and first.provenance['reason']=='bridge_store_busy'
    assert json.loads(stored['data'])['state']=='preflight'
    assert len(c.uploads)==2 and c.calls==0

    c.busy=False
    recovered=asyncio.run(transport.resolve(req))
    assert recovered.route=='bridge' and recovered.state=='queued'
    assert recovered.origin_key==first.origin_key
    assert [item['input_key'] for item in c.input_keys]==[f'{first.origin_key}_0']*2
    assert c.uploads[-1]==(f'{first.origin_key}_0',content,'image/png')
    assert c.calls==1


def test_store_busy_input_creation_retries_same_input_key_once(tmp_path, monkeypatch):
    import time

    class BusyCreateOnce(Client):
        def __init__(self): self.input_payloads=[]
        async def create_input(self, payload):
            self.input_payloads.append(dict(payload))
            if len(self.input_payloads)==1:
                raise BridgeError('store_busy',status=503,retry_not_before=time.time()+60)
            return {'input_id':payload['input_key']}
        async def upload_input(self, input_id, content, mime_type):
            self.uploaded=(input_id,content,mime_type)

    async def no_wait(_delay): pass
    monkeypatch.setattr(asyncio,'sleep',no_wait)
    content=_small_png(); c=BusyCreateOnce(); req=replace(request(),references=(Reference(content,'image/png'),))
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(req))
    assert result.route=='bridge' and result.state=='queued' and c.calls==1
    assert len(c.input_payloads)==2 and c.input_payloads[0]==c.input_payloads[1]
    assert c.uploaded==(c.input_payloads[0]['input_key'],content,'image/png')


def test_malformed_available_health_does_not_silently_select_api(tmp_path):
    class Malformed(Client):
        async def capabilities(self):
            caps=await super().capabilities()
            caps['routing_availability_v1']['profiles'][0]['valid_until']=123
            return caps
    c=Malformed()
    result=asyncio.run(PrimaryTransport(settings(tmp_path),client=c).resolve(request()))
    assert result.route=='bridge' and result.state=='queued' and c.calls==1


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

@pytest.mark.parametrize('advertised', [False, True])
def test_codex_adapter_requires_explicit_capability_before_submission(tmp_path, advertised):
    class VersionedClient(Client):
        async def capabilities(self):
            caps = await super().capabilities()
            if advertised:
                caps['profiles'][0]['parameter_contract']['codex_adapter'] = {'values': ['codex_cli_imagegen_v1'],
                    'image_options_contract': caps['profiles'][0]['image_options_contract']}
            return caps
    client = VersionedClient()
    transport = PrimaryTransport(settings(tmp_path), client=client)
    unit = replace(request(), parameters={'codex_adapter': 'codex_cli_imagegen_v1'})
    result = asyncio.run(transport.resolve(unit))
    assert result.route == ('bridge' if advertised else 'api')
    assert client.calls == (1 if advertised else 0)
    if advertised:
        assert client.payload['parameters'] == unit.parameters
    else:
        assert result.reason == 'bridge_capability_unsupported'


def test_codex_unsupported_optional_image_options_use_native_defaults(tmp_path):
    class DefaultsClient(Client):
        async def capabilities(self):
            caps = await super().capabilities()
            caps['profiles'][0]['parameter_contract']['codex_adapter'] = {
                'values': ['codex_cli_imagegen_v1'],
                'image_options_contract': {'references': {'max_count': 5}},
            }
            return caps

    client = DefaultsClient()
    transport = PrimaryTransport(settings(tmp_path), client=client)
    unit = replace(request(), parameters={
        'codex_adapter': 'codex_cli_imagegen_v1',
        'image_options': {'schema_version': '1', 'quality': 'high',
                          'output_format': 'webp', 'transparent_background': True},
    })
    result = asyncio.run(transport.resolve(unit))
    assert result.route == 'bridge'
    assert client.calls == 1
    assert client.payload['parameters'] == {'codex_adapter': 'codex_cli_imagegen_v1'}
    assert unit.parameters['image_options']['transparent_background'] is True
    assert transport._read(unit)['key'] == unit.key


def test_candidate_match_is_exact_read_only_and_preserves_semantic_guard(tmp_path):
    transport = PrimaryTransport(settings(tmp_path), client=Client())
    old = replace(request(), parameters={'width': 1024, 'height': 1024})
    assert transport.match_existing_request((old, request())) is None
    assert not transport.path.exists()
    transport._start(old)
    before = transport._read(old)
    assert transport.match_existing_request((request(), old)) == old
    after = transport._read(old)
    assert dict(before) == dict(after)
    with pytest.raises(PrimaryError, match='request_semantics_changed'):
        transport.match_existing_request((request(),))
    with pytest.raises(PrimaryError, match='request_semantics_changed'):
        asyncio.run(transport.resolve(request()))


def test_native_and_legacy_options_use_distinct_advertised_contracts(tmp_path):
    caps = asyncio.run(Client().capabilities())
    profile = caps['profiles'][0]
    profile['parameter_contract']['codex_adapter'] = {'values': ['codex_cli_imagegen_v1'],
        'image_options_contract': {'references': {'max_count': 5},
                                   'transparent_background': {'values': [True]}}}
    legacy = replace(request(), parameters={'image_options': {
        'schema_version': '1', 'quality': 'auto', 'output_format': 'jpeg'}})
    native = replace(request(), parameters={'codex_adapter': 'codex_cli_imagegen_v1'})
    assert PrimaryTransport._supported(legacy, caps, 'codex-image')
    assert PrimaryTransport._supported(native, caps, 'codex-image')
    assert not PrimaryTransport._supported(replace(legacy, parameters={**legacy.parameters,
        'codex_adapter': 'codex_cli_imagegen_v1'}), caps, 'codex-image')
    profile['parameter_contract']['codex_adapter'].pop('image_options_contract')
    assert not PrimaryTransport._supported(native, caps, 'codex-image')


@pytest.mark.parametrize('directory', ['state#1', 'state?1'])
def test_candidate_match_uri_escapes_state_directory_without_writes(tmp_path, directory):
    import os
    if '?' in directory and os.name == 'nt':
        pytest.skip('Windows filenames cannot contain question marks')
    transport = PrimaryTransport(settings(tmp_path / directory), client=Client())
    unit = request()
    transport._start(unit)
    before_files = {path.relative_to(tmp_path): path.read_bytes()
                    for path in tmp_path.rglob('*') if path.is_file()}
    before_stat = transport.path.stat()
    assert transport.match_existing_request((unit,)) == unit
    after_files = {path.relative_to(tmp_path): path.read_bytes()
                   for path in tmp_path.rglob('*') if path.is_file()}
    assert after_files == before_files
    assert transport.path.stat().st_mtime_ns == before_stat.st_mtime_ns


def test_retirement_intent_preserved_until_confirmed_ack_then_reconciled(tmp_path):
    import json
    c = ReceiptClient(); t = PrimaryTransport(settings(tmp_path), client=c)
    result = asyncio.run(t.resolve(request()))
    stale = json.loads(t._read(request())['data'])
    assert t.request_retirement([request()])
    assert t.cached_result(request()).image.content == c.content
    # An older poll cannot overwrite the product's durable retirement intent.
    t._save(request(), stale)
    assert json.loads(t._read(request())['data'])['cache_retirement_requested']
    original_ack = c.accept_registered_receipt
    async def lose(*args, **kwargs): raise BridgeError('bridge_unreachable')
    c.accept_registered_receipt = lose
    with pytest.raises(BridgeError):
        asyncio.run(t.acknowledge(request(), 'native:verified'))
    assert t._read(request())['image'] == c.content
    assert 'payload' in json.loads(t._read(request())['data'])
    c.accept_registered_receipt = original_ack
    restarted = PrimaryTransport(settings(tmp_path), client=c)
    assert asyncio.run(restarted.reconcile_pending())['acked'] == 1
    row = restarted._read(request()); data = json.loads(row['data'])
    assert row['image'] is None and data['cache_retired']
    assert 'payload' not in data and data['image']['sha256'] == hashlib.sha256(c.content).hexdigest()
    assert restarted.cached_result(request()).state == 'acked'
    t._save(request(), stale, image=c.content)
    assert t._read(request())['image'] is None
    assert c.calls == 1


def test_retirement_intent_batch_rejects_pending_and_wrong_digest_atomically(tmp_path):
    import json
    c = ReceiptClient(); t = PrimaryTransport(settings(tmp_path), client=c)
    asyncio.run(t.resolve(request()))
    pending = replace(request(), unit_id='job:second')
    t._start(pending)
    assert not t.request_retirement([request(), pending])
    assert not json.loads(t._read(request())['data']).get('cache_retirement_requested')
    with pytest.raises(PrimaryError, match='request_semantics_changed'):
        t.request_retirement([replace(request(), prompt='other')])
    assert t._read(request())['image'] == c.content


def test_retirement_intent_after_ack_retires_immediately(tmp_path):
    c = ReceiptClient(); t = PrimaryTransport(settings(tmp_path), client=c)
    asyncio.run(t.resolve(request()))
    asyncio.run(t.acknowledge(request(), 'native:verified'))
    assert t.request_retirement([request()])
    assert t._read(request())['image'] is None
    asyncio.run(t.acknowledge(request(), 'native:verified'))
    assert len(c.acks) == 1


def test_cached_result_absent_does_not_create_ledger(tmp_path):
    t = PrimaryTransport(settings(tmp_path), client=Client())
    assert t.cached_result(request()) is None
    assert not t.path.exists()
