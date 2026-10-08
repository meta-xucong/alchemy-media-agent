"""Non-vacuous independent async browse acceptance with real offline outputs."""
from __future__ import annotations
import asyncio,json,os
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def _force_worker_eligibility(monkeypatch):
    from app import browse_reads
    monkeypatch.setattr(browse_reads,'MIN_SOURCE_BYTES',0,raising=False)


def _service(root):
    from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore,V3ProjectModeService
    from alchemy_creative_agent_3_0.app.product_api import V3GeneratedOutputStore,V3UploadedAssetStore
    from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService,PersistentProductJobStore
    product=V3ProductApiService(job_store=PersistentProductJobStore(root/'jobs'),output_store=V3GeneratedOutputStore(root/'outputs'),asset_store=V3UploadedAssetStore(root/'uploads'))
    return V3ProjectModeService(product_service=product,project_store=PersistentProjectStore(root/'projects'))


def _fixture(tmp_path):
    from scripts.benchmark_v3_browse_compute import make_fixture
    make_fixture(tmp_path,projects=2,history_rows=4,job_history_rows=4)
    return _service(tmp_path)


def _replace(path,mutate):
    payload=json.loads(path.read_text(encoding='utf-8'));mutate(payload)
    temp=path.with_suffix('.acceptance.tmp');temp.write_text(json.dumps(payload),encoding='utf-8');temp.replace(path)


@pytest.mark.parametrize('case',[
    'project_owner','project_archive','project_delete','earlier_job_owner',
    'earlier_job_delete','output_delete','live_project_owner','live_earlier_job_owner',
])
def test_real_outputs_never_leak_across_worker_await(case,tmp_path,monkeypatch):
    from app import browse_compute as compute
    from app.browse_reads import run_output_browse
    service=_fixture(tmp_path);pool=compute.BoundedBrowseCompute(1)
    kwargs=dict(limit=60,owner_user_id=1,compact=True,project_id='project_benchmark_000',surface=None,project_ids=None)
    before=service.list_project_outputs(**kwargs)
    assert len(before['items'])==6, 'The race must start with six genuinely visible materialized outputs.'
    count=0;firstpath=firstid=None;changed=False;held=[]
    live=service.project_store.get_project('project_benchmark_000') if case=='live_project_owner' else None
    original=compute._BrowseLease.read_job
    async def intercepted(lease,path,job_id,revision):
        nonlocal count,firstpath,firstid,changed
        value=await original(lease,path,job_id,revision);count+=1
        if firstpath is None:firstpath=Path(path);firstid=job_id
        threshold=2 if case.startswith('earlier_') or case=='live_earlier_job_owner' else 1
        if not changed and count==threshold:
            changed=True;projectpath=tmp_path/'projects/project_benchmark_000/project.json'
            if case=='project_owner':_replace(projectpath,lambda p:p['metadata'].__setitem__('veyra_user_id',2))
            elif case=='project_archive':_replace(projectpath,lambda p:p.__setitem__('status','archived'))
            elif case=='project_delete':projectpath.unlink()
            elif case=='earlier_job_owner':_replace(firstpath,lambda p:p['request']['metadata'].__setitem__('veyra_user_id',2))
            elif case=='earlier_job_delete':firstpath.unlink()
            elif case=='output_delete':
                rows=service.product_service.output_store.list_by_job(job_id);assert rows
                service.product_service.output_store._record_path(rows[0].output_id).unlink()
            elif case=='live_project_owner':live.metadata['veyra_user_id']=2
            elif case=='live_earlier_job_owner':
                record=service.product_service.job_store.get(firstid);assert record is not None
                held.append(record);record.request.metadata['veyra_user_id']=2
        return value
    monkeypatch.setattr(compute._BrowseLease,'read_job',intercepted)
    try:
        if case=='project_delete':
            with pytest.raises(KeyError):asyncio.run(run_output_browse(service,pool,**kwargs))
            with pytest.raises(KeyError):service.list_project_outputs(**kwargs)
        else:
            actual=asyncio.run(run_output_browse(service,pool,**kwargs));expected=service.list_project_outputs(**kwargs)
            assert actual==expected
            assert len(actual['items'])==(0 if case in {'project_owner','project_archive','live_project_owner'} else 5)
            assert actual['items']!=before['items']
        assert changed
    finally:pool.shutdown()


@pytest.mark.parametrize('workers',[1,2])
@pytest.mark.parametrize('surface',['global','detail','home_preview','delivery_preview'])
def test_actual_output_surface_exact_response_parity(workers,surface,tmp_path):
    from app.browse_compute import BoundedBrowseCompute
    from app.browse_reads import run_output_browse
    service=_fixture(tmp_path);pool=BoundedBrowseCompute(workers)
    kwargs=dict(limit=60,owner_user_id=1,compact=True,project_id='project_benchmark_000' if surface in {'detail','delivery_preview'} else None,surface=surface if surface in {'home_preview','delivery_preview'} else None,project_ids=['project_benchmark_000'] if surface=='home_preview' else None)
    expected=service.list_project_outputs(**kwargs)
    assert expected['items'], 'Parity with an empty fixture would not test delivery behavior.'
    try:actual=asyncio.run(run_output_browse(service,pool,**kwargs))
    finally:pool.shutdown()
    assert actual==expected


def test_dense_source_is_bounded_and_oversize_preserves_owner_fallback(tmp_path):
    from app.browse_compute import BoundedBrowseCompute,MAX_SOURCE_BYTES,file_revision
    service=_fixture(tmp_path);store=service.product_service.job_store
    path=store._record_path('job_benchmark_000_0')
    _replace(path,lambda p:p['request']['metadata'].__setitem__('dense_evidence',[{} for _ in range(20000)]))
    assert path.stat().st_size<MAX_SOURCE_BYTES
    pool=BoundedBrowseCompute(1)
    async def read():
        with pool.admit() as lease:return await lease.read_job(path,'job_benchmark_000_0',file_revision(path))
    try:
        serialized=asyncio.run(read());assert serialized
        _replace(path,lambda p:p['request']['metadata'].__setitem__('large_evidence','x'*(MAX_SOURCE_BYTES+1)))
        assert asyncio.run(read()) is None
        assert store.get('job_benchmark_000_0') is not None
    finally:pool.shutdown()


def _sleep_worker(path,job_id,revision):
    import time
    time.sleep(float(path));return os.getpid()


def _inspect_worker(path,job_id,revision):
    import sys,threading
    from app.browse_compute import decode_job_file
    value=decode_job_file(path,job_id,revision)
    return {'pid':os.getpid(),'valid':bool(value),'main_loaded':any(name in sys.modules for name in ('app.main','src_skeleton.app.main')),'threads':[t.name for t in threading.enumerate()],'secret_present':'ACCEPTANCE_FAKE_PROVIDER_SECRET' in os.environ}


def test_real_spawn_import_isolation(tmp_path,monkeypatch):
    from app import browse_compute as compute
    service=_fixture(tmp_path);path=service.product_service.job_store._record_path('job_benchmark_000_0')
    monkeypatch.setenv('ACCEPTANCE_FAKE_PROVIDER_SECRET','synthetic-value')
    monkeypatch.setattr(compute,'decode_job_file',_inspect_worker)
    pool=compute.BoundedBrowseCompute(1)
    async def read():
        with pool.admit() as lease:return await lease.read_job(path,'job_benchmark_000_0',compute.file_revision(path))
    try:result=asyncio.run(read())
    finally:pool.shutdown()
    assert result['pid']!=os.getpid() and result['valid']
    assert not result['main_loaded'] and not result['secret_present']
    assert result['threads']==['MainThread']


def test_real_process_cancellation_preserves_physical_queue_bound(monkeypatch):
    import time
    from app import browse_compute as compute
    monkeypatch.setattr(compute,'decode_job_file',_sleep_worker)
    pool=compute.BoundedBrowseCompute(1,timeout=10)
    async def one():
        with pool.admit() as lease:return await lease.read_job('.5','unused',(0,0,0))
    async def exercise():
        tasks=[asyncio.create_task(one()) for _ in range(2)]
        await asyncio.sleep(.03);assert pool.admitted==2
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        assert pool.admitted==2
        for _ in range(1000):
            with pytest.raises(compute.BrowseCapacityExceeded):
                with pool.admit():pass
        assert len(pool._executor._pending_work_items)<=2
        deadline=time.monotonic()+10
        while pool.admitted and time.monotonic()<deadline:await asyncio.sleep(.02)
        assert pool.admitted==0
    try:asyncio.run(exercise())
    finally:pool.shutdown()


def test_real_worker_crash_recovers_and_timeout_drains(monkeypatch):
    from app import browse_compute as compute
    monkeypatch.setattr(compute,'decode_job_file',_sleep_worker)
    pool=compute.BoundedBrowseCompute(1,timeout=5)
    async def one(seconds):
        with pool.admit() as lease:return await lease.read_job(str(seconds),'unused',(0,0,0))
    async def crash():
        task=asyncio.create_task(one(2));await asyncio.sleep(.05)
        process=next(iter(pool._executor._processes.values()));old=process.pid;process.kill()
        with pytest.raises(compute.BrowseComputeUnavailable):await task
        assert pool.admitted==0
        assert await one(0)!=old
    try:asyncio.run(crash())
    finally:pool.shutdown()
    pool=compute.BoundedBrowseCompute(1,timeout=.001)
    try:
        with pytest.raises(compute.BrowseComputeUnavailable):asyncio.run(one(.05))
        assert pool.admitted==1
    finally:pool.shutdown()
    assert pool.admitted==0
    with pytest.raises(compute.BrowseComputeUnavailable):
        with pool.admit():pass
