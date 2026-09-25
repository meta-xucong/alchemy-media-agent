"""Single authoritative binding, CAS, stale cache, tombstones and replay."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import pytest
from alchemy_creative_agent_3_0.app.project_mode.continuity_anchor import ContinuityAnchorBindingService, NAMESPACE
from alchemy_creative_agent_3_0.app.project_mode.store import InMemoryProjectStore, PersistentProjectStore


def resolve(project, output, job):
    if output=="held":raise ValueError("continuity_anchor_not_formally_accepted")
    if job and job!="job_source":raise ValueError("continuity_anchor_project_mismatch")
    return {"output_id":output,"asset_id":output,"job_id":"job_source","candidate_id":"candidate",
        "source_asset_id":"asset","content_sha256":"a"*64,"file_path":"not_consumed_by_binding_store"}


@pytest.mark.parametrize("persistent",[False,True])
def test_replace_unbind_and_restart_do_not_resurrect_history(tmp_path,persistent):
    store=PersistentProjectStore(tmp_path) if persistent else InMemoryProjectStore()
    service=ContinuityAnchorBindingService(store,resolve)
    first=service.change("project_test",output_id="first",expected_version=0)
    second=service.change("project_test",output_id="second",expected_version=1)
    assert second["supersedes_binding_id"]==first["active_continuity_anchor"]["binding_id"]
    unbound=service.change("project_test",output_id=None,expected_version=2)
    assert unbound["active_continuity_anchor"] is None
    assert unbound["auto_enabled"] is False
    if persistent:service=ContinuityAnchorBindingService(PersistentProjectStore(tmp_path),resolve)
    with pytest.raises(ValueError,match="conflict"):
        service.change("project_test",output_id="old",expected_version=3,mode="auto_first_formal")
    assert service.state("project_test")["state"]=="unbound"
    assert service.change("project_test",output_id="manual",expected_version=3)["state"]=="active"


def test_two_store_instances_and_threads_cannot_overwrite_newer_binding(tmp_path):
    services=[ContinuityAnchorBindingService(PersistentProjectStore(tmp_path),resolve) for _ in range(8)]
    def bind(pair):
        index,service=pair
        try:return service.change("project_test",output_id=f"out_{index}",expected_version=0)["state"]
        except ValueError as exc:return str(exc)
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(bind,enumerate(services)))
    assert results.count("active")==1
    assert results.count("continuity_anchor_conflict")==7
    assert len(services[0].store.list_private_records("project_test",NAMESPACE))==1


def test_rejected_source_leaves_prior_active_binding_unchanged(tmp_path):
    service=ContinuityAnchorBindingService(PersistentProjectStore(tmp_path),resolve)
    before=service.change("project_test",output_id="good",expected_version=0)
    with pytest.raises(ValueError,match="not_formally_accepted"):
        service.change("project_test",output_id="held",expected_version=1)
    assert service.state("project_test")==before


def test_corrupt_history_never_becomes_empty_auto_eligible_project(tmp_path):
    service=ContinuityAnchorBindingService(PersistentProjectStore(tmp_path),resolve)
    service.change("project_test",output_id=None,expected_version=0)
    file=tmp_path/"project_test/private_records.json"
    file.write_text("not-json",encoding="utf-8")
    with pytest.raises(ValueError,match="store_invalid"):
        service.state("project_test")


def test_deleted_or_invalid_formal_output_is_not_replaced(tmp_path):
    service=ContinuityAnchorBindingService(PersistentProjectStore(tmp_path),resolve)
    service.change("project_test",output_id="good",expected_version=0)
    service.resolve_output=lambda *args:(_ for _ in ()).throw(ValueError("gone"))
    state=service.state("project_test")
    assert state["state"]=="invalid"
    assert state["active_continuity_anchor"] is None
    assert state["auto_enabled"] is False


def test_private_other_namespace_append_cannot_erase_anchor_from_stale_cache(tmp_path):
    a,b=PersistentProjectStore(tmp_path),PersistentProjectStore(tmp_path)
    b.list_private_records("project_test",NAMESPACE)
    service=ContinuityAnchorBindingService(a,resolve)
    service.change("project_test",output_id=None,expected_version=0)
    b.append_private_record("project_test","doc73_auto_identity_anchor_controls_v1",{"state":"bound","record":"legacy"})
    assert ContinuityAnchorBindingService(PersistentProjectStore(tmp_path),resolve).state("project_test")["state"]=="unbound"


@pytest.mark.parametrize("invalid",[{},None,False,"old"])
def test_malformed_namespace_cannot_reset_an_unbind_tombstone(tmp_path,invalid):
    directory=tmp_path/"project_test";directory.mkdir()
    (directory/"private_records.json").write_text(json.dumps({NAMESPACE:invalid}),encoding="utf-8")
    with pytest.raises(ValueError,match="history_invalid"):
        ContinuityAnchorBindingService(PersistentProjectStore(tmp_path),resolve).state("project_test")


def _cross_process_bind(root,output,ready,start,queue):
    service=ContinuityAnchorBindingService(PersistentProjectStore(root),resolve)
    ready.put(True);start.wait(10)
    try:
        service.change("project_test",output_id=output,expected_version=0)
        queue.put("active")
    except ValueError as exc:
        queue.put(str(exc))


def test_separate_processes_have_exactly_one_anchor_writer(tmp_path):
    import multiprocessing
    ctx=multiprocessing.get_context("spawn");ready=ctx.Queue();start=ctx.Event();queue=ctx.Queue()
    processes=[ctx.Process(target=_cross_process_bind,args=(str(tmp_path),f"out_{i}",ready,start,queue)) for i in range(2)]
    for process in processes:process.start()
    try:
        for _ in processes:assert ready.get(timeout=20) is True
        start.set()
        results=[queue.get(timeout=20) for _ in processes]
        assert sorted(results)==["active","continuity_anchor_conflict"]
        for process in processes:
            process.join(10)
            assert process.exitcode==0
    finally:
        for process in processes:
            if process.is_alive():process.terminate();process.join(5)
