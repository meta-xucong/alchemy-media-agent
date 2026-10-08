#!/usr/bin/env python3
"""Offline bounded-browse acceptance benchmark (Linux /proc metrics).

Run from the repository with its Python dependencies installed:
  python scripts/benchmark_v3_browse_compute.py --cpus 0,1 --rounds 5

Creates only tempfile synthetic projects/jobs/16px PNGs, invokes the actual
project-outputs endpoint directly, and compares disabled/1/2-worker responses.
No server, account, provider call, or production storage is used. This is not a
2GB/VPS qualification: report host limits separately. Defaults test two users.
"""
from __future__ import annotations
import argparse,asyncio,base64,gc,hashlib,io,json,os,statistics,subprocess,sys,tempfile,threading,time
from pathlib import Path
from types import SimpleNamespace


def safe_environment():
    os.environ.update(V3_LLM_BRAIN_REMOTE_ENABLED='false',LLM_PROMPT_PLANNING_ENABLED='false',MEDIA_AGENT_MODE='mock',MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS='false',MOCK_IMAGE_PROVIDER_ENABLED='true',OPENAI_API_KEY='',ANTHROPIC_AUTH_TOKEN='',CODEX_AUTH_FILE=os.devnull,CLAUDE_SETTINGS_FILE=os.devnull)


def isolate_runtime(root):
    """Isolate all default storage before importing the real endpoint."""
    bootstrap = Path(root).resolve() / "isolated-app-startup"
    bootstrap.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "ALCHEMY_APP_ROOT": str(bootstrap),
        "MEDIA_STORAGE_ROOT": str(bootstrap / "v1"),
        "ALCHEMY_V3_JOB_DIR": str(bootstrap / "job-root"),
        "ALCHEMY_V3_PROJECT_DIR": str(bootstrap / "projects"),
        "ALCHEMY_V3_OUTPUT_DIR": str(bootstrap / "outputs"),
        "ALCHEMY_V3_UPLOAD_DIR": str(bootstrap / "uploads"),
        "ALCHEMY_V3_MCP_MATERIALIZATION_ROOT": str(bootstrap / "materialization"),
        "V3_VISUAL_ASSET_CATALOG_ROOT": str(bootstrap / "visual-assets"),
        "V3_VISUAL_ASSET_LIBRARY_ROOT": str(bootstrap / "visual-library"),
        "ALCHEMY_V3_RUNTIME_DESCRIPTOR": "",
        "ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED": "false",
        "PYTHON_DOTENV_DISABLED": "1",
        "MEDIA_AGENT_RUNTIME_ENV_FILE": os.devnull,
        "ALCHEMY_MEDIA_AGENT_ENV_FILE": os.devnull,
        "ALCHEMY_MEDIA_RUNTIME_ENV_FILE": os.devnull,
    })
    for name in (
        "V2_DATA_DIR", "V2_STORAGE_DIR", "V2_CASE_INDEX_PATH",
        "V2_IMAGE_HISTORY_PATH", "VEYRA_USAGE_PATH", "V2_REMOTE_SNAPSHOT_DIR",
        "V2_CASE_THUMBNAIL_DIR", "V2_HISTORY_THUMBNAIL_DIR", "V2_TASK_QUEUE_DB_PATH",
        "V2_CLAUDE_ORCHESTRATOR_WORKSPACE_DIR", "V2_CLAUDE_ORCHESTRATOR_CACHE_PATH",
    ):
        os.environ[name] = str(bootstrap / name.lower())


def make_fixture(root,projects=24,history_rows=600,job_history_rows=100):
    from PIL import Image
    from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
    from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord
    from alchemy_creative_agent_3_0.app.product_api import V3GeneratedOutputStore
    from alchemy_creative_agent_3_0.app.product_api.service import ProductJobRecord,PersistentProductJobStore
    from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest,ProductJobStatusValue
    ps=PersistentProjectStore(root/'projects');js=PersistentProductJobStore(root/'jobs');outputs=V3GeneratedOutputStore(root/'outputs')
    rows=[{'event_id':f'event_{i}','reason':'Historical review and continuation evidence. '*12,'scores':{'quality':.93,'identity':.91},'attempts':[{'candidate':str(j),'prompt':'Commercial creative direction. '*8,'accepted':j==2} for j in range(4)]} for i in range(max(history_rows,job_history_rows))]
    image=io.BytesIO();Image.new('RGB',(16,16),(180,190,200)).save(image,format='PNG');png=base64.b64encode(image.getvalue()).decode()
    for i in range(projects):
        owner=1+i%2;pid=f'project_benchmark_{i:03d}';ids=[]
        for j in range(6):
            jid=f'job_benchmark_{i:03d}_{j}';ids.append(jid)
            js.save(ProductJobRecord(request=CreateCreativeJobRequest(user_input='Studio image',metadata={'veyra_user_id':owner,'project_id':pid,'synthetic_review_history':rows[:job_history_rows]}),status=ProductJobStatusValue.GENERATED,job_id_value=jid))
            outputs.save_base64_output(job_id=jid,candidate_id=f'candidate_{i}_{j}',asset_id=f'asset_{i}_{j}',provider='offline_fixture',model='fixture',encoded_image=png,mime_type='image/png',output_format='png',metadata={'veyra_user_id':owner,'project_id':pid,'final_provider_prompt':'Studio image','requested_image_count':1})
        stamp=f'2026-09-01T{i//60:02d}:{i%60:02d}:00+00:00'
        ps.save_project(ProjectRecord(project_id=pid,title=f'History project {i}',user_goal='Studio image',short_summary='Studio image',created_at=stamp,updated_at=stamp,job_ids=ids,timeline_refs=[f'timeline_{k}' for k in range(history_rows)],metadata={'veyra_user_id':owner,'synthetic_append_only_history':rows[:history_rows]}))
    return {'projects':projects,'jobs':projects*6,'project_bytes':sum(p.stat().st_size for p in (root/'projects').rglob('*.json')),'job_history_rows':job_history_rows,'job_bytes':sum(p.stat().st_size for p in (root/'jobs').glob('job_*.json'))}



class TimedBytes(bytes):
    def __new__(cls,payload,metrics=None):
        obj=super().__new__(cls,payload);obj.metrics=metrics or {};return obj
    def __reduce__(self):return TimedBytes,(bytes(self),self.metrics)

def diagnostic_decode(path,job_id,revision):
    from app.browse_compute import decode_job_file
    start=time.perf_counter();cpu=time.process_time();payload=decode_job_file(path,job_id,revision)
    return TimedBytes(payload,{'wall':time.perf_counter()-start,'cpu':time.process_time()-cpu,'pid':os.getpid()}) if payload is not None else None

class ProcessMonitor:
    """Sample this endpoint owner and descendants; excludes benchmark controller."""
    def __init__(self):
        self.parent=os.getpid();self.stop=threading.Event();self.samples=[]
        self.thread=threading.Thread(target=self._run,daemon=True)
    def _run(self):
        ticks=os.sysconf('SC_CLK_TCK');pages=os.sysconf('SC_PAGE_SIZE')
        while not self.stop.is_set():
            rows={}
            for path in Path('/proc').iterdir():
                if not path.name.isdigit():continue
                try:
                    v=(path/'stat').read_text().rsplit(')',1)[1].split()
                    rows[int(path.name)]={'ppid':int(v[1]),'cpu':(int(v[11])+int(v[12]))/ticks,'rss':int(v[21])*pages}
                except (OSError,ValueError,IndexError):continue
            descendants={self.parent}
            while True:
                new={pid for pid,row in rows.items() if row['ppid'] in descendants}
                if new<=descendants:break
                descendants|=new
            self.samples.append((time.perf_counter(),{pid:rows[pid] for pid in descendants if pid in rows}))
            self.stop.wait(.01)
    def start(self):self.thread.start()
    def finish(self):
        self.stop.set();self.thread.join();children={};overlap=0
        for when,rows in self.samples:
            for pid,row in rows.items():
                if pid==self.parent:continue
                entry=children.setdefault(pid,{'first_cpu':row['cpu'],'last_cpu':row['cpu'],'peak_rss_bytes':0})
                entry['last_cpu']=max(entry['last_cpu'],row['cpu']);entry['peak_rss_bytes']=max(entry['peak_rss_bytes'],row['rss'])
        for (_,old),(_,new) in zip(self.samples,self.samples[1:]):
            overlap+=sum(pid!=self.parent and pid in old and new[pid]['cpu']>old[pid]['cpu'] for pid in new)>=2
        return {'tree_peak_rss_bytes':max((sum(r['rss'] for r in rows.values()) for _,rows in self.samples),default=0),'children':children,'concurrent_child_cpu_samples':overlap}


def percentile(values,p):
    return sorted(values)[min(len(values)-1,int(len(values)*p))] if values else None


async def endpoint_worker(args):
    isolate_runtime(args.fixture)
    import src_skeleton.app.main as main
    from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore,V3ProjectModeService
    from alchemy_creative_agent_3_0.app.product_api import V3GeneratedOutputStore,V3UploadedAssetStore
    from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService,PersistentProductJobStore
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from app import browse_reads,browse_compute
    root=Path(args.fixture)
    bootstrap=(root/'isolated-app-startup').resolve()
    bootstrap_roots={
        'jobs':main._v3_product_service.job_store.storage_root,
        'projects':main.v3_route_handlers.project_service.project_store.storage_root,
        'outputs':main._v3_product_service.output_store.storage_root,
        'standalone_outputs':main.v3_output_store.storage_root,
        'uploads':main._v3_product_service.asset_store.storage_root,
        'visual_assets':main._v3_product_service.visual_asset_catalog.storage_root,
        'visual_library':main._v3_visual_asset_library_catalog.storage_root,
        'v1_media':main.settings.media_storage_root,
    }
    assert all(Path(value).resolve().is_relative_to(bootstrap) for value in bootstrap_roots.values()),bootstrap_roots
    product=V3ProductApiService(job_store=PersistentProductJobStore(root/'jobs'),output_store=V3GeneratedOutputStore(root/'outputs'),asset_store=V3UploadedAssetStore(root/'uploads'))
    service=V3ProjectModeService(product_service=product,project_store=PersistentProjectStore(root/'projects'))
    counters={'synchronous_calls':0,'child_reads':0,'child_read_none':0,'scope_changes':{}}
    original_sync=service.list_project_outputs
    def sync(*a,**kw):
        counters['synchronous_calls']+=1;return original_sync(*a,**kw)
    service.list_project_outputs=sync
    previous_exception=browse_reads._ReadScopeChanged
    class ScopeChange(previous_exception):
        def __init__(self,*a):
            f=sys._getframe(1);key=f'{f.f_code.co_name}:{f.f_lineno}'
            counters['scope_changes'][key]=counters['scope_changes'].get(key,0)+1
            super().__init__(*a)
    browse_reads._ReadScopeChanged=ScopeChange
    if args.diagnostic:browse_compute.decode_job_file=diagnostic_decode
    original_loads=browse_reads.pickle.loads
    def measured_loads(payload):
        start=time.perf_counter();value=original_loads(payload)
        counters['parent_unpickle_seconds']=counters.get('parent_unpickle_seconds',0)+time.perf_counter()-start
        return value
    if args.diagnostic:browse_reads.pickle=SimpleNamespace(loads=measured_loads)
    original_read=browse_compute._BrowseLease.read_job
    async def read(*a,**kw):
        counters['child_reads']+=1;start=time.perf_counter();value=await original_read(*a,**kw)
        if args.diagnostic:
            counters['await_seconds']=counters.get('await_seconds',0)+time.perf_counter()-start
            counters['source_bytes']=counters.get('source_bytes',0)+a[3][2]
            counters['ipc_payload_bytes']=counters.get('ipc_payload_bytes',0)+(len(value) if value else 0)
            for key,number in getattr(value,'metrics',{}).items():
                if key!='pid':counters['child_'+key+'_seconds']=counters.get('child_'+key+'_seconds',0)+number
        if value is None:counters['child_read_none']+=1
        return value
    browse_compute._BrowseLease.read_job=read
    handlers=object.__new__(V3ProductRouteHandlers);handlers.project_service=service
    main.v3_route_handlers=handlers
    main._require_veyra_user_if_enabled=lambda request,*a:request.owner
    main._v3_is_admin_request=lambda *a:asyncio.sleep(0,result=False)
    samples=[];errors=[];gaps=[];done=False
    async def heartbeat():
        previous=time.perf_counter()
        while not done:
            await asyncio.sleep(.002);now=time.perf_counter();gaps.append(now-previous);previous=now
    async def request(owner):
        start=time.perf_counter()
        try:
            result=await main.v3_project_outputs_endpoint(request=SimpleNamespace(owner=owner),limit=60,compact=True,project_id=(f'project_benchmark_{owner-1:03d}' if args.surface in {'detail','delivery_preview'} else None),surface=(args.surface if args.surface in {'home_preview','delivery_preview'} else None),project_ids=(','.join(f'project_benchmark_{i:03d}' for i in range(args.projects) if 1+i%2==owner) if args.surface=='home_preview' else None),authorization='')
        except Exception as exc:
            errors.append({'type':type(exc).__name__,'status':getattr(exc,'status_code',None),'detail':str(exc)});return None
        samples.append(time.perf_counter()-start);return result
    beat=asyncio.create_task(heartbeat());cold=ProcessMonitor();cold.start();start=time.perf_counter()
    await asyncio.gather(request(1),request(2));warmup=time.perf_counter()-start
    cold_metrics=cold.finish();warmup_counters=json.loads(json.dumps(counters));warmup_errors=list(errors)
    beat.cancel();await asyncio.gather(beat,return_exceptions=True)
    beat=asyncio.create_task(heartbeat());await asyncio.sleep(0)
    counters.clear();counters.update(synchronous_calls=0,child_reads=0,child_read_none=0,scope_changes={});samples.clear();errors.clear();gaps.clear()
    monitor=ProcessMonitor();monitor.start();start=time.perf_counter();cpu=time.process_time();responses=[]
    if args.profile:
        import cProfile
        profiler=cProfile.Profile();profiler.enable()
    for _ in range(args.rounds):responses=await asyncio.gather(request(1),request(2))
    if args.profile:profiler.disable()
    wall=time.perf_counter()-start;cpu=time.process_time()-cpu;done=True;await beat
    result={'workers':args.worker,'surface':args.surface,'successful_requests':len(samples),'error_count':len(errors),'errors':errors,'wall_seconds':wall,'successful_requests_per_second':len(samples)/wall,'parent_cpu_seconds':cpu,'p50_seconds':statistics.median(samples) if samples else None,'p95_seconds':percentile(samples,.95),'max_seconds':max(samples,default=None),'heartbeat_max_seconds':max(gaps,default=None),'heartbeat_p95_seconds':percentile(gaps,.95),'warmup_seconds':warmup,'warmup_errors':warmup_errors,'warmup_metrics':cold_metrics,'diagnostics':counters,'warmup_diagnostics':warmup_counters,'affinity':sorted(os.sched_getaffinity(0)),'bootstrap_roots_isolated':True}
    result.update(monitor.finish())
    if args.profile:
        import pstats
        output=io.StringIO();pstats.Stats(profiler,stream=output).sort_stats('cumulative').print_stats(35)
        result['profile_top_cumulative']=output.getvalue()
        output=io.StringIO();pstats.Stats(profiler,stream=output).sort_stats('tottime').print_stats(35)
        result['profile_top_self']=output.getvalue()
    canonical=json.dumps(responses,ensure_ascii=False,sort_keys=True).encode()
    result['response_sha256']=hashlib.sha256(canonical).hexdigest();result['response_bytes']=len(canonical)
    Path(args.result).write_text(json.dumps(result,indent=2),encoding='utf-8')
    if main._v3_browse_compute is not None:await asyncio.to_thread(main._v3_browse_compute.shutdown)



def checkout_storage_inventory(repo):
    snapshot={}
    for relative in ('.media_storage','src_skeleton/.media_storage','custom_media_agent_2_0/.media_storage','custom_media_agent_2_0/.data','.env','src_skeleton/.env'):
        root=repo/relative
        if not root.exists():continue
        for path in (root,*root.rglob('*')) if root.is_dir() else (root,):
            stat=path.stat();snapshot[str(path.relative_to(repo))]=(path.is_dir(),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
    return snapshot

def cli():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--cpus',help='Comma-separated allowed CPU IDs; no memory limit is imposed')
    parser.add_argument('--rounds',type=int,default=5);parser.add_argument('--projects',type=int,default=24);parser.add_argument('--history-rows',type=int,default=600)
    parser.add_argument('--job-history-rows',type=int,default=100);parser.add_argument('--order',default='0,1,2',help='Worker order; repeat IDs to test noise, e.g. 0,1,2,2,1,0')
    parser.add_argument('--diagnostic',action='store_true');parser.add_argument('--profile',action='store_true')
    parser.add_argument('--surface',choices=['global','detail','home_preview','delivery_preview'],default='global');parser.add_argument('--json-output',type=Path)
    parser.add_argument('--worker',type=int,choices=[0,1,2]);parser.add_argument('--fixture');parser.add_argument('--result')
    args=parser.parse_args();safe_environment()
    if args.json_output:args.json_output=args.json_output.resolve()
    if args.projects<2 or args.projects>100 or args.rounds<1:parser.error('Use 2–100 projects and at least one round')
    if args.cpus:os.sched_setaffinity(0,{int(cpu) for cpu in args.cpus.split(',')})
    repo=args.repo.resolve();sys.path[:0]=[str(repo),str(repo/'src_skeleton')]
    os.environ['PYTHONPATH']=os.pathsep.join([str(repo),str(repo/'src_skeleton'),os.environ.get('PYTHONPATH','')])
    if args.worker is not None:
        os.environ['V3_BROWSE_COMPUTE_WORKERS']=str(args.worker);os.chdir(args.fixture);asyncio.run(endpoint_worker(args));return
    storage_before=checkout_storage_inventory(repo)
    with tempfile.TemporaryDirectory(prefix='v3-browse-benchmark-') as directory:
        root=Path(directory);os.chdir(root);isolate_runtime(root);fixture=make_fixture(root,args.projects,args.history_rows,args.job_history_rows);gc.collect();reports=[]
        for run_index,workers in enumerate(int(x) for x in args.order.split(',')):
            destination=root/f'result_{run_index}_{workers}.json'
            command=[sys.executable,str(Path(__file__).resolve()),'--repo',str(repo),'--worker',str(workers),'--fixture',str(root),'--result',str(destination),'--rounds',str(args.rounds),'--projects',str(args.projects),'--surface',args.surface]
            if args.diagnostic:command.append('--diagnostic')
            if args.profile:command.append('--profile')
            subprocess.run(command,check=True,env=os.environ)
            reports.append(json.loads(destination.read_text()))
        storage_after=checkout_storage_inventory(repo)
        assert storage_before==storage_after,'Benchmark modified checkout default storage.'
        parity=all(report['response_sha256']==reports[0]['response_sha256'] for report in reports)
        report={'fixture':fixture,'exact_response_parity':parity,'memory_limit_enforced':False,'checkout_default_storage_unchanged':True,'scope':'Actual direct async endpoint; two synthetic owners; no HTTP transport or provider calls. Warm page cache; process startup separately reported. Linux RSS sampling excludes this fixture controller.','runs':reports,'diagnostic_instrumentation':args.diagnostic,'cprofile_enabled':args.profile}
        encoded=json.dumps(report,indent=2);print(encoded)
        if args.json_output:args.json_output.resolve().write_text(encoded,encoding='utf-8')
        if not parity or any(r['error_count'] or r['warmup_errors'] for r in reports):raise SystemExit(1)

if __name__=='__main__':cli()
