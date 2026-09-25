"""Authenticated binding routes and shared desktop/mobile reference panel."""
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import _general_project
from alchemy_creative_agent_3_0.tests.test_v3_doc322_project_workflow import create_source

ROOT=Path(__file__).resolve().parents[2]


def test_http_binding_compare_and_swap_and_foreign_project_rejection(tmp_path,monkeypatch):
    import app.main as main
    from app.config import settings
    handlers,project,_,_=_general_project(tmp_path)
    raw=handlers.project_service.project_store.get_project(project["project_id"])
    raw.metadata["veyra_user_id"]=101
    handlers.project_service.project_store.save_project(raw)
    source,output=create_source(handlers,project)
    monkeypatch.setattr(main,"v3_route_handlers",handlers)
    monkeypatch.setattr(settings,"veyra_auth_enabled",True)
    monkeypatch.setattr(main,"_veyra_user_id_from_request",lambda request,authorization:101)
    client=TestClient(main.app)
    url=f"/api/v3/creative-agent/projects/{project['project_id']}/continuity-anchor"
    state=client.get(url).json()
    payload={"output_id":output.output_id,"expected_job_id":source.job_id,"expected_version":state["version"],"confirm_binding":True}
    bound=client.post(url+"/bind",json=payload)
    assert bound.status_code==200,bound.text
    assert bound.json()["active_continuity_anchor"]["output_id"]==output.output_id
    stale=client.post(url+"/bind",json=payload)
    assert stale.status_code==409
    wrong=client.post(url+"/unbind",json={"expected_version":bound.json()["version"],"confirm_unbind":"true"})
    assert wrong.status_code==400
    unbound=client.post(url+"/unbind",json={"expected_version":bound.json()["version"],"confirm_unbind":True})
    assert unbound.status_code==200
    assert unbound.json()["state"]=="unbound"
    monkeypatch.setattr(main,"_veyra_user_id_from_request",lambda request,authorization:202)
    assert client.get(url).status_code==404
    assert client.post(url+"/bind",json=payload).status_code==404


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        chrome=Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        launched=pw.chromium.launch(executable_path=str(chrome),headless=True) if chrome.exists() else pw.chromium.launch(headless=True)
        yield launched
        launched.close()


@pytest.mark.parametrize("width",[390,1280])
def test_shared_panel_is_singleton_and_unbind_is_versioned(browser,width):
    page=browser.new_page(viewport={"width":width,"height":900})
    page.set_content('<main id="board" style="max-width:100%;overflow-wrap:anywhere"></main>')
    page.add_script_tag(path=str(ROOT/"src_skeleton/app/static/continuity-anchor.js"))
    project={"project_id":"project_test","metadata":{
        "current_job_reference_mode":"standard_direct_reference",
        "current_job_reference_inputs":[{"asset_id":"a","filename":"<img onerror=alert(1)>","preview_url":"javascript:alert(1)"}],
        "project_source_library":{"entries":[{"label":"MUST_NOT_APPEAR"}]},
        "continuity_anchor":{"version":3,"state":"active","auto_enabled":False,
            "active_continuity_anchor":{"output_id":"v3_output_one","source_job_id":"job_one","preview_url":"/api/v3/creative-agent/outputs/v3_output_one/preview"}}}}
    page.evaluate("""p => {
        window.writes=[];window.refreshCount=0;
        window.options={project:p,request:async(path,body)=>{window.writes.push({path,...body});return {};},
          refresh:async()=>{window.refreshCount++;},isCurrent:id=>id===p.project_id,notify:()=>{}};
        window.AlchemyContinuity.render(document.querySelector('#board'),window.options);
    }""",project)
    assert page.locator('[data-continuity-state="active"]').count()==1
    assert page.locator('[data-reference-mode="standard_direct_reference"]').count()==1
    assert page.locator('img').count()==1  # Malicious source URL is not rendered.
    assert "MUST_NOT_APPEAR" not in page.locator('#board').inner_text()
    page.on('dialog',lambda dialog:dialog.accept())
    page.get_by_role('button',name='解绑主图').click()
    page.wait_for_function('window.writes.length===1')
    call=page.evaluate('window.writes[0]')
    assert call['path'].endswith('/continuity-anchor/unbind')
    assert call['body']=={'expected_version':3,'confirm_unbind':True}
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.close()


@pytest.mark.parametrize("mode,expected,forbidden",[("professional_asset_binding","Professional 资产绑定","本次参考图"),("ecommerce_product_truth","商品事实输入","Professional 资产绑定")])
def test_mode_panel_does_not_display_other_source_channels(browser,mode,expected,forbidden):
    page=browser.new_page()
    page.set_content('<main id="board"></main>')
    page.add_script_tag(path=str(ROOT/"src_skeleton/app/static/continuity-anchor.js"))
    page.evaluate("""mode => window.AlchemyContinuity.render(document.querySelector('#board'),{
        project:{project_id:'p',metadata:{current_job_reference_mode:mode,
          current_job_reference_inputs:[{filename:'FORBIDDEN_DIRECT'}],continuity_anchor:{state:'unbound',version:1}}},
        request:()=>{},refresh:()=>{},isCurrent:()=>true,notify:()=>{}})""",mode)
    text=page.locator('#board').inner_text()
    assert expected in text
    assert forbidden not in text
    assert 'FORBIDDEN_DIRECT' not in text
    assert page.locator('button').count()==0
    page.close()


def test_both_shells_load_same_versioned_component_without_global_source_persist():
    for rel in ['src_skeleton/app/static/index.html','src_skeleton/app/mobile_static/index.html']:
        assert 'continuity-anchor.js?v=__CONTINUITY_ANCHOR_VERSION__' in (ROOT/rel).read_text(encoding='utf-8')
    for rel in ['src_skeleton/app/static/app.js','src_skeleton/app/mobile_static/mobile.js']:
        source=(ROOT/rel).read_text(encoding='utf-8')
        assert 'window.AlchemyContinuity?.render' in source
        assert 'window.AlchemyContinuity.bind' in source


def test_failed_write_and_refresh_do_not_retry_or_reject_the_ui_promise(browser):
    page=browser.new_page()
    page.set_content('<main id="board"></main>')
    page.add_script_tag(path=str(ROOT/"src_skeleton/app/static/continuity-anchor.js"))
    result=page.evaluate("""async () => {
        window.confirm=()=>true;
        let writes=0, notices=[];
        const options={project:{project_id:'p',metadata:{continuity_anchor:{state:'none',version:1}}},
          request:async()=>{writes++;throw new Error('connection_lost');},
          refresh:async()=>{throw new Error('offline');},isCurrent:()=>true,
          notify:(text,tone)=>notices.push({text,tone})};
        await window.AlchemyContinuity.bind(options,{output_id:'out',job_id:'job'});
        return {writes,notices};
    }""")
    assert result["writes"]==1
    assert result["notices"] and all(item["tone"]=="warning" for item in result["notices"])
    page.close()


def test_project_switch_during_refresh_does_not_publish_a_stale_success(browser):
    page=browser.new_page()
    page.set_content('<main id="board"></main>')
    page.add_script_tag(path=str(ROOT/"src_skeleton/app/static/continuity-anchor.js"))
    result=page.evaluate("""async () => {
        window.confirm=()=>true;
        let current=true,notices=[];
        await window.AlchemyContinuity.bind({project:{project_id:'p',metadata:{continuity_anchor:{state:'none',version:1}}},
          request:async()=>({}),refresh:async()=>{current=false;},isCurrent:()=>current,
          notify:(text,tone)=>notices.push({text,tone})},{output_id:'out',job_id:'job'});
        return notices;
    }""")
    assert result==[]
    page.close()
