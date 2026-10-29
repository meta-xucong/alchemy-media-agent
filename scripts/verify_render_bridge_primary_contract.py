"""Synthetic cross-repository contract check, not live Codex or paid acceptance.

Run in the companion Bridge's locked test environment. The only credential is a
local fixture token. HTTP handlers are exercised through ASGI, not the network.
"""
import argparse
import asyncio
import hashlib
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--bridge-checkout", type=Path, required=True)
parser.add_argument("--require-codex-adapter", action="store_true",
                    help="Also require native adapter negotiation against the pinned candidate; never invokes a CLI")
args = parser.parse_args()
bridge_source = args.bridge_checkout.resolve() / "src"
if not (bridge_source / "render_bridge" / "api.py").is_file():
    parser.error("Bridge checkout has no src/render_bridge/api.py")
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(bridge_source)]
import httpx
from render_bridge_primary import PrimarySettings, PrimaryTransport, PrimaryRequest
from render_bridge_primary.http import BridgeClient, BridgeError
from render_bridge.domain import BridgeStore,SourceScope
from render_bridge.api import create_app
from render_bridge.fake import run_fake_once, fixture_png

async def verify_codex_adapter():
    """Exercise the native wire contract with synthetic bytes, not a renderer."""
    with tempfile.TemporaryDirectory(prefix='primary-native-contract-') as directory:
        root = Path(directory)
        scope = SourceScope('fixture', 'workspace')
        store = BridgeStore(root/'bridge.sqlite3', root/'artifacts', enabled_profiles=('codex-image',))
        store.provision_node(scope, 'node', 'instance')
        store.report_heartbeat(scope, 'node', 'instance', 'available', ['codex-image'], [dict(
            profile_id='codex-image', profile_revision='1', report_revision=1,
            health='available', reason_code='ready', evidence_kind='local_probe', revalidation_generation=0)])
        app = create_app(store=store, source_tokens={'fixture-token': scope})
        client = BridgeClient('https://fixture.invalid', 'fixture-token', transport=httpx.ASGITransport(app=app))
        try:
            caps = await client.capabilities()
            profile = next(p for p in caps['profiles'] if p['execution_profile_id'] == 'codex-image')
            adapter = profile['parameter_contract'].get('codex_adapter')
            assert isinstance(adapter, dict), 'Pinned Bridge lacks the required native Codex adapter contract'
            assert adapter['values'] == ['codex_cli_imagegen_v1'], adapter
            assert adapter['image_options_contract']['references']['max_count'] == 5
            assert profile['image_options_contract']['references']['max_count'] == 8
            settings = PrimarySettings(enabled=True, base_url='https://fixture.invalid', token='fixture-token',
                profile='codex-image', workspace='workspace', state_dir=root/'ledger')
            transport = PrimaryTransport(settings, client=client)
            def request(key):
                return PrimaryRequest('v2', 'owner', key, 'Synthetic fixture', {
                    'codex_adapter': 'codex_cli_imagegen_v1',
                    'image_options': {'schema_version': '1', 'transparent_background': True}})
            # create_task passes through the real HTTP schema and admission handler.
            first = await transport.resolve(request('first'))
            assert (first.route, first.state) == ('bridge', 'queued'), first
            assert (await transport.resolve(request('first'))).task_id == first.task_id
            claim = store.claim_task(scope, first.task_id, node_id='node', executor_instance='instance')
            assert store.start_execution(scope, first.task_id, claim['claim_id'])['may_execute']
            assert not store.start_execution(scope, first.task_id, claim['claim_id'])['may_execute']
            content = fixture_png(32, 24)
            digest = hashlib.sha256(content).hexdigest()
            upload = store.create_upload(scope, first.task_id, claim['claim_id'], dict(
                attempt_id=claim['attempt_id'], slot_id='primary', original_sha256=digest,
                size=len(content), mime_type='image/png'))
            store.put_upload_content(scope, upload['upload_id'], claim['claim_id'], content)
            store.commit_upload(scope, upload['upload_id'], claim['claim_id'])
            result = await transport.resolve(request('first'))
            assert result.image.content == content and result.image.sha256 == digest
            await transport.acknowledge(request('first'), 'fixture-output')
            assert (await transport.resolve(request('first'))).image.content == content
            original_create = client.create_task
            admitted = {}
            async def lose_response(payload):
                admitted.update(await original_create(payload))
                raise BridgeError('bridge_unreachable')
            client.create_task = lose_response
            unknown = await transport.resolve(request('lost'))
            assert (unknown.route, unknown.state) == ('bridge', 'bridge_submission_unknown'), unknown
            client.create_task = original_create
            recovered = await PrimaryTransport(settings, client=client).resolve(request('lost'))
            assert (recovered.route, recovered.state) == ('bridge', 'queued'), recovered
            assert recovered.task_id == admitted['remote_task_id']
            print('PASS native Codex wire: explicit marker/nested capabilities, replay, once-start, original receipt/ACK, same-origin response-loss recovery; synthetic pixels only, no CLI acceptance')
        finally:
            await client.close()
            store.close()

async def main():
 root=Path(tempfile.mkdtemp(prefix='primary-independent-')); scope=SourceScope('fixture','workspace')
 store=BridgeStore(root/'bridge.sqlite3',root/'artifacts',max_queued_tasks=10)
 store.provision_node(scope,'node','instance')
 store.report_heartbeat(scope,'node','instance','available',['fake-image'],[dict(profile_id='fake-image',profile_revision='1',report_revision=1,health='available',reason_code='ready',evidence_kind='local_probe',revalidation_generation=0)])
 app=create_app(store=store,source_tokens={'fixture-token':scope})
 client=BridgeClient('https://fixture.invalid','fixture-token',transport=httpx.ASGITransport(app=app))
 settings=PrimarySettings(enabled=True,base_url='https://fixture.invalid',token='fixture-token',profile='fake-image',state_dir=root/'ledger',workspace='workspace')
 t=PrimaryTransport(settings,client=client)
 req=lambda i: PrimaryRequest('v2','owner',str(i),'fixture',{'width':32,'height':32})
 first=await t.resolve(req(0)); assert first.route=='bridge' and first.state=='queued',first
 for i in range(1,9): assert (await t.resolve(req(i))).route=='bridge'
 raced=await asyncio.gather(t.resolve(req(9)),t.resolve(req(10)))
 assert sorted(x.route for x in raced)==['api','bridge'],raced
 assert (await t.resolve(req(0))).task_id==first.task_id
 rendered=run_fake_once(store,scope,first.task_id,node_id='node',executor_instance='instance',start_log=root/'starts')
 result=await t.resolve(req(0)); assert result.image and result.image.sha256==rendered['receipt']['original_sha256']
 await t.acknowledge(req(0),'product-output-fixture')
 assert (await t.resolve(req(0))).image.content==result.image.content
 # response loss after durable admission; no resubmit, recover via origin with new transport
 original=client.create_task
 async def lost(payload):
  await original(payload); raise BridgeError('bridge_unreachable')
 client.create_task=lost
 unknown=await t.resolve(req(11)); assert unknown.route=='bridge' and unknown.state=='bridge_submission_unknown',unknown
 client.create_task=original
 recovered=await PrimaryTransport(settings,client=client).resolve(req(11)); assert recovered.state=='queued',recovered
 assert (await t.resolve(req(11))).route=='bridge'
 await t.cancel(req(11))
 canceled=await t.resolve(req(11)); assert canceled.route=='bridge' and canceled.state=='canceled',canceled
 store.report_heartbeat(scope,'node','instance','available',['fake-image'],[dict(profile_id='fake-image',profile_revision='1',report_revision=2,health='unavailable',reason_code='tool_missing',evidence_kind='local_probe',revalidation_generation=0)])
 unavailable=await t.resolve(req(12))
 assert unavailable.route=='bridge' and unavailable.state=='queued',unavailable
 print('PASS profile health is diagnostic only after accepting admission; existing task remains owned; same-task cancellation never API')
 print('PASS actual companion ASGI: 9-to-10 competition, full queue replay, original receipt/hash/bytes/dimensions, ACK and post-admission response-loss restart recovery')
 print('evidence_root',root)
 await client.close(); store.close()
 if args.require_codex_adapter:
  await verify_codex_adapter()
asyncio.run(main())
