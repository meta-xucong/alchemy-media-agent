'use strict';
const api = '/api/integrations/render-bridge/v1';
const $ = (id) => document.getElementById(id);
let mode = 'disabled';
let sending = false;
let requestKey = null;
let requestFingerprint = null;
let generation = 0;
const imageURLs = new Set();
const states = {queued:'等待提交', submitting:'正在提交', claimed:'已领取', running:'执行中', awaiting_user:'等待人工操作', execution_unknown:'执行状态待确认', artifacts_ready:'正在校验产物', preview_ready:'测试预览就绪 · 未原生登记', remote_unavailable:'Bridge 暂不可达，按原任务继续查询', cancel_requested:'已隐藏，正在取消远端任务', canceled:'已取消', expired:'已过期', failed:'远端任务失败', blocked_scope:'项目权限已变化', blocked_revision:'项目版本已变化，预览已隐藏', protocol_error:'合同校验失败'};
function sessionToken(){try{return localStorage.getItem('alchemy_veyra_access_token')||'';}catch{return '';}}
function clearImages(){for(const url of imageURLs)URL.revokeObjectURL(url);imageURLs.clear();}
async function authorizedFetch(path,options={}){
  const url=new URL(path,location.href);if(url.origin!==location.origin)throw new Error('cross_origin_not_allowed');
  const headers={...options.headers};const token=sessionToken();if(token)headers.Authorization=`Bearer ${token}`;
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),15000);
  try{return await fetch(url,{credentials:'same-origin',cache:'no-store',redirect:'error',...options,headers,signal:controller.signal});}
  finally{clearTimeout(timeout);}
}
async function fetchJSON(path, options={}) {
  const response = await authorizedFetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.detail?.code || value.detail?.error_code || `HTTP ${response.status}`);
  return value;
}
function notice(text, error=false) { $('notice').textContent=text; $('notice').className=error?'error':''; }
function paragraph(text, className='') { const p=document.createElement('p'); p.textContent=text; p.className=className; return p; }
async function refresh() {
  const project=$('project').value;
  const token=sessionToken();
  const current=++generation;
  if (!project) { clearImages();$('tasks').replaceChildren(paragraph('选择项目后查看任务。','muted')); return; }
  try {
    const result=await fetchJSON(`${api}/tasks?project_id=${encodeURIComponent(project)}`);
    if (current!==generation || project!==$('project').value || token!==sessionToken()) return;
    clearImages();
    const items=result.tasks.map(task=>{
      const article=document.createElement('article'); article.className='task';
      article.append(paragraph(states[task.state] || task.state,'task-title'));
      article.append(paragraph(`${task.profile_id} · ${new Date(task.created_at).toLocaleString()}`,'muted'));
      if(task.last_error) article.append(paragraph(task.last_error,'error'));
      if(task.action_required_detail?.message) article.append(paragraph(task.action_required_detail.message,'error'));
      if(task.preview_url){
        const img=document.createElement('img');img.alt='Bridge 测试图，原生登记未接通';article.append(img);
        authorizedFetch(task.preview_url).then(async response=>{
          if(!response.ok)throw new Error('preview_not_available');
          const blob=await response.blob();
          if(current!==generation||token!==sessionToken()||!img.isConnected)return;
          const url=URL.createObjectURL(blob);imageURLs.add(url);img.src=url;
        }).catch(()=>{img.remove();});
      }
      article.append(paragraph(`原生登记未接通 · Bridge 确认：${task.delivery_ack}`,'muted'));
      if(!['canceled','failed','expired'].includes(task.state)){
        const cancel=document.createElement('button');cancel.textContent='取消 / 隐藏';cancel.className='secondary';
        cancel.onclick=async()=>{cancel.disabled=true;try{await fetchJSON(`${api}/tasks/${encodeURIComponent(task.integration_job_id)}/cancel`,{method:'POST',headers:{'X-Alchemy-Bridge-Preview':'1'}});await refresh();}catch(error){notice(error.message,true);cancel.disabled=false;}};
        article.append(cancel);
      }
      return article;
    });
    $('tasks').replaceChildren(...(items.length?items:[paragraph('这个项目还没有 Bridge 测试任务。','muted')]));
  }catch(error){if(current===generation){clearImages();$('tasks').replaceChildren();notice(`读取失败：${error.message}`,true);}}
}
async function fileInput(file){
  if(!['image/png','image/jpeg'].includes(file.type)||file.size>1048576)throw new Error('参考图必须为 PNG/JPEG，且每张不超过 1 MiB');
  return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({mime_type:file.type,content_base64:String(reader.result).split(',')[1]});reader.onerror=reject;reader.readAsDataURL(file);});
}
$('create-form').addEventListener('submit',async event=>{
  event.preventDefault();if(sending||mode!=='enabled')return;sending=true;$('submit').disabled=true;
  try{
    const files=[...$('references').files];if(files.length>8)throw new Error('最多选择 8 张参考图');
    const payload={project_id:$('project').value,profile_id:$('profile').value,prompt:$('prompt').value,width:Number($('width').value),height:Number($('height').value),seed:0,references:await Promise.all(files.map(fileInput)),acknowledge_test_only:$('acknowledge').checked};
    const fingerprint=JSON.stringify(payload);if(fingerprint!==requestFingerprint){requestFingerprint=fingerprint;requestKey=crypto.randomUUID();}
    payload.client_request_id=requestKey;
    await fetchJSON(`${api}/tasks`,{method:'POST',headers:{'Content-Type':'application/json','X-Alchemy-Bridge-Preview':'1'},body:JSON.stringify(payload)});
    notice('测试任务已保存。可安全离开页面，模块只会恢复自己的任务。');await refresh();
  }catch(error){notice(`提交未确认：${error.message}。相同输入重试会沿用同一请求编号。`,true);}
  finally{sending=false;$('submit').disabled=mode!=='enabled';}
});
$('project').addEventListener('change',refresh);$('refresh').addEventListener('click',refresh);
$('profile').addEventListener('change',()=>{const size=$('profile').value==='fake-image'?32:1024;$('width').value=size;$('height').value=size;});
async function initialize(){
  try{
    const status=await fetchJSON(`${api}/status`);mode=status.mode;
    for(const profile of status.profiles){const option=document.createElement('option');option.value=profile;option.textContent=profile==='fake-image'?'fake-image · 合成测试，不调用模型':`${profile} · 真实工具仍需本地能力验收`;$('profile').append(option);}
    $('submit').disabled=mode!=='enabled'||!status.available;
    notice(status.error?`模块不可用：${status.error}`:mode==='draining'?'仅恢复现有任务，已停止接受新测试。':'独立测试已启用。原生登记未接通。',!!status.error);
    const projects=await fetchJSON('/api/v3/creative-agent/projects?limit=100&view=summary');
    for(const project of projects.projects||[]){const option=document.createElement('option');option.value=project.project_id;option.textContent=project.title||project.project_id;$('project').append(option);}
  }catch(error){notice(`需要有效登录或显式本机测试配置：${error.message}`,true);}
}
initialize();
const timer=setInterval(()=>{if(!document.hidden&&$('project').value)refresh();},5000);
window.addEventListener('pagehide',()=>{clearInterval(timer);generation++;clearImages();});
window.addEventListener('storage',event=>{if(event.key==='alchemy_veyra_access_token'){generation++;clearImages();$('tasks').replaceChildren();refresh();}});
