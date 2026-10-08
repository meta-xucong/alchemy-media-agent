"""Output snapshot freshness across real worker waits and registration gaps."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from scripts.benchmark_v3_browse_compute import make_fixture, safe_environment

safe_environment()
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore, V3ProjectModeService
from alchemy_creative_agent_3_0.app.product_api import V3GeneratedOutputStore, V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService, PersistentProductJobStore
from app import browse_compute as compute
from app.browse_reads import run_output_browse


def _service(root):
    product = V3ProductApiService(
        job_store=PersistentProductJobStore(root / 'jobs'),
        output_store=V3GeneratedOutputStore(root / 'outputs'),
        asset_store=V3UploadedAssetStore(root / 'uploads'),
    )
    return V3ProjectModeService(product_service=product, project_store=PersistentProjectStore(root / 'projects'))


@pytest.mark.parametrize('case', ['owner', 'delete'])
@pytest.mark.parametrize('surface', ['detail', 'global'])
@pytest.mark.parametrize('mode', ['all_large', 'second_small', 'second_orphan'])
def test_later_output(case, surface, mode, tmp_path, monkeypatch):
    make_fixture(tmp_path, projects=1, history_rows=4, job_history_rows=700)
    service = _service(tmp_path)
    if mode == 'second_small':
        path = tmp_path / 'jobs/job_benchmark_000_1.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['request']['metadata']['synthetic_review_history'] = []
        path.write_text(json.dumps(data), encoding='utf-8')
        assert path.stat().st_size < 1024 * 1024
    if mode == 'second_orphan':
        path = tmp_path / 'projects/project_benchmark_000/project.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['job_ids'].remove('job_benchmark_000_1')
        path.write_text(json.dumps(data), encoding='utf-8')
    kwargs = dict(owner_user_id=1, compact=True,
                  project_id='project_benchmark_000' if surface == 'detail' else None)
    before = service.list_project_outputs(**kwargs)
    assert len(before['items']) >= 5
    store = service.product_service.output_store
    target = store.list_by_job('job_benchmark_000_1')[0]
    root_revision = store._storage_revision()
    changed = False
    original = compute._BrowseLease.read_job

    async def intercepted(lease, path, job_id, revision):
        nonlocal changed
        value = await original(lease, path, job_id, revision)
        if not changed:
            assert job_id == 'job_benchmark_000_0'
            assert revision[2] >= 1024 * 1024
            changed = True
            metadata_path = store._record_path(target.output_id)
            if case == 'delete':
                metadata_path.unlink()
            else:
                data = json.loads(metadata_path.read_text(encoding='utf-8'))
                data['metadata']['veyra_user_id'] = 2
                metadata_path.write_text(json.dumps(data), encoding='utf-8')
            assert root_revision == store._storage_revision()
        return value

    monkeypatch.setattr(compute._BrowseLease, 'read_job', intercepted)
    pool = compute.BoundedBrowseCompute(1)
    try:
        actual = asyncio.run(run_output_browse(service, pool, **kwargs))
    finally:
        pool.shutdown()
    expected = service.list_project_outputs(**kwargs)
    assert changed
    assert actual == expected
    if mode != 'second_orphan':
        assert len(before['items']) == 6 and len(actual['items']) == 5
    elif surface == 'detail':
        assert len(before['history_items']) == 1 and not actual['history_items']
        assert len(before['items']) == len(actual['items']) == 5


@pytest.mark.parametrize('case', ['owner', 'delete', 'cache_replacement', 'live_owner'])
@pytest.mark.parametrize('fallback', [False, True])
def test_output_registration_binds_original_read(case, fallback, tmp_path, monkeypatch):
    """Mutations after batch return must not be relabeled by registration stat."""
    make_fixture(tmp_path, projects=1, history_rows=4, job_history_rows=4)
    service = _service(tmp_path)
    store = service.product_service.output_store
    kwargs = dict(owner_user_id=1, compact=True, project_id='project_benchmark_000')
    assert len(service.list_project_outputs(**kwargs)['items']) == 6
    target_id = store.list_by_job('job_benchmark_000_1')[0].output_id
    method = 'list_by_project' if fallback else 'list_by_project_and_jobs'
    original = getattr(store, method)
    changed = False

    def intercepted(*args, **kw):
        nonlocal changed
        records = original(*args, **kw)
        if not changed:
            changed = True
            target = next(r for r in records if r.output_id == target_id)
            path = store._record_path(target_id)
            if case == 'delete':
                path.unlink()
            elif case == 'live_owner':
                target.metadata['veyra_user_id'] = 2
            else:
                data = json.loads(path.read_text(encoding='utf-8'))
                data['metadata']['veyra_user_id'] = 2
                path.write_text(json.dumps(data), encoding='utf-8')
                if case == 'cache_replacement':
                    assert store.get_output(target_id) is not target
        return records

    if fallback:
        def broken_batch(*args, **kw):
            raise OSError('simulate unavailable combined index')
        monkeypatch.setattr(store, 'list_by_project_and_jobs', broken_batch)
    monkeypatch.setattr(store, method, intercepted)
    pool = compute.BoundedBrowseCompute(1)
    try:
        actual = asyncio.run(run_output_browse(service, pool, **kwargs))
    finally:
        pool.shutdown()
    assert changed
    assert actual == service.list_project_outputs(**kwargs)
    assert len(actual['items']) == 5


def test_output_evidence_survives_lru_eviction_without_sync_restart(tmp_path, monkeypatch):
    from alchemy_creative_agent_3_0.app.product_api import outputs
    monkeypatch.setattr(outputs, '_OUTPUT_RECORD_CACHE_MAX_ENTRIES', 2)
    make_fixture(tmp_path, projects=1, history_rows=4, job_history_rows=700)
    service = _service(tmp_path)
    kwargs = dict(owner_user_id=1, compact=True, project_id='project_benchmark_000')
    expected = service.list_project_outputs(**kwargs)
    assert len(expected['items']) == 6
    def forbidden_restart(**kw):
        pytest.fail('LRU eviction is not a stale read and must not force synchronous restart')
    monkeypatch.setattr(service, 'list_project_outputs', forbidden_restart)
    pool = compute.BoundedBrowseCompute(1)
    try:
        assert asyncio.run(run_output_browse(service, pool, **kwargs)) == expected
    finally:
        pool.shutdown()
    assert len(service.product_service.output_store._scoped_records_by_id_cache) <= 2


def test_output_read_evidence_is_private_and_detects_decode_race(tmp_path, monkeypatch):
    from dataclasses import asdict, fields
    from app.browse_reads import _ReadGuard, _ReadScopeChanged
    make_fixture(tmp_path, projects=1, history_rows=4, job_history_rows=4)
    service = _service(tmp_path)
    store = service.product_service.output_store
    record = store.list_by_job('job_benchmark_000_0')[0]
    expected_keys = {field.name for field in fields(record)}
    assert set(record.to_json_dict()) == set(asdict(record)) == expected_keys
    assert '_read_provenance' not in expected_keys
    assert store.get_output(record.output_id) is record
    assert record._read_provenance[1] is not None
    store._invalidate_cache()
    original = json.load
    changed = False
    def racing_load(handle, *args, **kwargs):
        nonlocal changed
        data = original(handle, *args, **kwargs)
        if not changed and str(handle.name) == str(store._record_path(record.output_id)):
            changed = True
            newer = dict(data)
            newer['metadata'] = {**data['metadata'], 'veyra_user_id': 2}
            Path(handle.name).write_text(json.dumps(newer), encoding='utf-8')
        return data
    monkeypatch.setattr(json, 'load', racing_load)
    stale = store.get_output(record.output_id)
    assert changed and stale.metadata['veyra_user_id'] == 1
    assert stale._read_provenance[1] is None
    with pytest.raises(_ReadScopeChanged):
        _ReadGuard(service, 1).add_output_records([stale])
    fresh = store.get_output(record.output_id)
    assert fresh.metadata['veyra_user_id'] == 2
    assert fresh._read_provenance[1] is not None
