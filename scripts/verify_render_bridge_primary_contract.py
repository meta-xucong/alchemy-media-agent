"""Synthetic cross-repository contract check, not live Codex or paid acceptance.

Run in the companion Bridge's locked test environment. The only credential is a
local fixture token. HTTP handlers are exercised through ASGI, not the network.
"""
import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--bridge-checkout", type=Path, required=True)
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
from render_bridge.fake import run_fake_once
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
 store.report_heartbeat(scope,'node','instance','available',['fake-image'],[dict(profile_id='fake-image',profile_revision='1',report_revision=2,health='unavailable',reason_code='tool_missing',evidence_kind='local_probe',revalidation_generation=0)])
 assert (await t.resolve(req(12))).route=='api'
 assert (await t.resolve(req(11))).route=='bridge'
 await t.cancel(req(11))
 canceled=await t.resolve(req(11)); assert canceled.route=='bridge' and canceled.state=='canceled',canceled
 print('PASS health fault affects only new requests; admitted task remains owned; same-task cancellation never API')
 print('PASS actual companion ASGI: 9-to-10 competition, full queue replay, original receipt/hash/bytes/dimensions, ACK and post-admission response-loss restart recovery')
 print('evidence_root',root)
 await client.close(); store.close()
asyncio.run(main())
