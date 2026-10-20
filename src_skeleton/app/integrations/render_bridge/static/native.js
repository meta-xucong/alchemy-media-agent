'use strict';
const api = '/api/integrations/render-bridge/v1/native';
const $ = id => document.getElementById(id);
let enabled = false, sending = false, referencesReady = false;
let generation = 0, referenceGeneration = 0, lastPayload = '', requestKey = '';
function token() { try { return localStorage.getItem('alchemy_veyra_access_token') || ''; } catch { return ''; } }
function notice(text, error = false) { $('notice').textContent = text; $('notice').className = error ? 'error' : ''; }
function updateSubmit() { $('submit').disabled = !enabled || sending || !referencesReady; }
async function request(path, options = {}) {
  const headers = { ...options.headers }; const session = token();
  if (session) headers.Authorization = `Bearer ${session}`;
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', redirect: 'error', ...options, headers });
  const value = await response.json();
  if (!response.ok) throw new Error(value.detail?.code || value.detail?.error_code || `HTTP ${response.status}`);
  return value;
}
function line(text, kind = '') { const node = document.createElement('p'); node.textContent = text; node.className = kind; return node; }
function clearReferences() {
  referencesReady = false;
  for (const id of ['reference-1', 'reference-2']) {
    const option = document.createElement('option'); option.value = ''; option.textContent = '不使用';
    $(id).replaceChildren(option); $(id).disabled = true;
  }
  updateSubmit();
}
async function loadReferences() {
  const project = $('project').value, current = ++referenceGeneration, session = token();
  clearReferences();
  if (!project) { $('reference-status').textContent = '请先选择项目。'; return; }
  $('reference-status').textContent = '正在读取本项目已授权原图…';
  try {
    const result = await request(`${api}/references?project_id=${encodeURIComponent(project)}`);
    if (current !== referenceGeneration || project !== $('project').value || session !== token()) return;
    for (const id of ['reference-1', 'reference-2']) {
      for (const item of result.references || []) {
        const option = document.createElement('option'); option.value = item.asset_id;
        option.textContent = `${item.label || item.asset_id} · ${Math.ceil(item.size_bytes / 1024)} KiB`;
        $(id).append(option);
      }
      $(id).disabled = false;
    }
    referencesReady = true;
    $('reference-status').textContent = '按 1、2 顺序传输原图，不裁剪、不压缩。每张限 PNG/JPEG、1 MiB 和 1,048,576 像素。若原生计划要求未支持的保真参数，将明确拒绝，不降低要求。合成图不会按参考内容生成。';
    updateSubmit();
  } catch (error) {
    if (current === referenceGeneration) {
      $('reference-status').textContent = `无法读取参考原图：${error.message}`;
      notice(error.message, true);
    }
  }
}
const labels = { plan_pending: '等待创建原生计划', plan_unknown: '计划结果待确认，不会重复调用 Brain', plan_blocked: '计划不满足受限合同', queued: 'Bridge 排队中', running: '合成渲染中', uploading: '传输结果中', import_unknown: '原生登记结果待确认，尚未 accepted', registered: '原生登记已确认 · 非正式交付', cancel_requested: '正在取消', canceled: '已取消', rejected: '原生登记拒绝', blocked_scope: '项目权限或连接配置已变化', blocked_revision: '冻结目标已变化', protocol_error: '合同校验失败', remote_unavailable: '远端暂不可达，等待同任务恢复' };
async function refresh() {
  const project = $('project').value, current = ++generation, session = token();
  if (!project) { $('tasks').replaceChildren(); return; }
  try {
    const result = await request(`${api}/tasks?project_id=${encodeURIComponent(project)}`);
    if (current !== generation || project !== $('project').value || session !== token()) return;
    const rows = result.tasks.map(task => {
      const box = document.createElement('article'); box.className = 'task';
      box.append(line(labels[task.state] || task.state, 'task-title'), line(new Date(task.created_at).toLocaleString(), 'muted'));
      box.append(line(`${task.size || '1024x1024'} · ${task.reference_count || 0} 张参考原图 · 仅传输验证`, 'muted'));
      if (task.last_error) box.append(line(task.last_error, 'error'));
      box.append(line(`登记：${task.native_registration} · 确认：${task.delivery_ack}`));
      if (task.native_registration_ref) box.append(line(task.native_registration_ref, 'muted'));
      if (task.review_status) box.append(line(`审核状态：${task.review_status}。不会自动选中或正式交付。`));
      if (!['registered', 'canceled', 'failed', 'expired', 'rejected', 'plan_blocked'].includes(task.state)) {
        const button = document.createElement('button'); button.className = 'secondary'; button.textContent = '取消';
        button.onclick = async () => {
          button.disabled = true;
          try { await request(`${api}/tasks/${encodeURIComponent(task.integration_job_id)}/cancel`, { method: 'POST', headers: { 'X-Alchemy-Bridge-Preview': '1' } }); await refresh(); }
          catch (error) { notice(error.message, true); button.disabled = false; }
        };
        box.append(button);
      }
      return box;
    });
    $('tasks').replaceChildren(...(rows.length ? rows : [line('暂无原生开发测试任务。', 'muted')]));
  } catch (error) { if (current === generation) { $('tasks').replaceChildren(); notice(error.message, true); } }
}
$('create-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!enabled || sending || !referencesReady) return;
  const uploaded = [$('reference-1').value, $('reference-2').value].filter(Boolean);
  if (new Set(uploaded).size !== uploaded.length) { notice('请勿重复选择同一张参考原图。', true); return; }
  sending = true; updateSubmit();
  try {
    const body = { project_id: $('project').value, user_input: $('user-input').value, uploaded_asset_ids: uploaded,
      size: $('size').value, acknowledge_synthetic_native_test: $('acknowledge').checked };
    const value = JSON.stringify(body);
    if (value !== lastPayload) { lastPayload = value; requestKey = crypto.randomUUID(); }
    body.client_request_id = requestKey;
    await request(`${api}/tasks`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Alchemy-Bridge-Preview': '1' }, body: JSON.stringify(body) });
    notice('显式测试请求已保存。原图按冻结顺序传输，合成输出不表示参考保真效果。'); await refresh();
  } catch (error) { notice(`提交未确认：${error.message}。相同输入可沿用原请求重试。`, true); }
  finally { sending = false; updateSubmit(); }
});
$('project').addEventListener('change', () => { generation++; $('tasks').replaceChildren(); loadReferences(); refresh(); });
$('refresh').addEventListener('click', refresh);
async function initialize() {
  try {
    const status = await request(`${api}/status`); enabled = status.available && status.mode === 'enabled'; updateSubmit();
    notice(status.error || '仅合成图开发测试，真实渲染工具、参考保真与真实计费未验收。', !!status.error);
    const projects = await request('/api/v3/creative-agent/projects?limit=100&view=summary');
    for (const project of projects.projects || []) { const option = document.createElement('option'); option.value = project.project_id; option.textContent = project.title || project.project_id; $('project').append(option); }
  } catch (error) { notice(`请使用已认证的项目所有者账号：${error.message}`, true); }
}
initialize();
const timer = setInterval(() => { if (!document.hidden && $('project').value) refresh(); }, 5000);
window.addEventListener('pagehide', () => { clearInterval(timer); generation++; referenceGeneration++; });
window.addEventListener('storage', event => {
  if (event.key === 'alchemy_veyra_access_token') { generation++; $('tasks').replaceChildren(); loadReferences(); refresh(); }
});
