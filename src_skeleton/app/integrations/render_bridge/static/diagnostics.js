'use strict';

const api = '/api/integrations/render-bridge/v1';
const $ = (id) => document.getElementById(id);
const maxReportBytes = 64 * 1024;
let checking = false;
let importing = false;

function sessionToken() {
  try { return localStorage.getItem('alchemy_veyra_access_token') || ''; }
  catch { return ''; }
}

async function fetchJSON(path, options = {}) {
  const token = sessionToken();
  const headers = {...options.headers};
  if (token) headers.Authorization = `Bearer ${token}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${api}${path}`, {
      credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      ...options, headers, signal: controller.signal,
    });
    if (token !== sessionToken()) throw new Error('session_changed');
    const value = await response.json();
    if (!response.ok) throw new Error(value.detail?.code || value.detail?.error_code || `http_${response.status}`);
    if (value.schema_version !== '1') throw new Error('unsupported_diagnostics_version');
    return value;
  } finally { clearTimeout(timeout); }
}

function paragraph(text, className = '') {
  const node = document.createElement('p');
  node.textContent = text;
  node.className = className;
  return node;
}

function readable(value) {
  if (value === undefined || value === null) return '未提供';
  if (Array.isArray(value)) return value.length ? value.map(readable).join('、') : '无';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function status(id, text, error = false) {
  $(id).textContent = text;
  $(id).className = error ? 'error' : '';
}

function errorText(error) {
  const messages = {
    report_too_large: '报告超过 64 KiB，未发送。',
    invalid_report_json: '报告不是有效 JSON，未发送。',
    invalid_report_format: '请选择 render_bridge_doctor JSON 报告，未发送。',
    unsupported_report_version: '不支持此报告版本，请使用 schema_version 为 1 的 doctor 报告，未发送。',
    unsupported_diagnostics_version: '服务端诊断格式版本不兼容，请更新匹配的组件。',
    session_changed: '登录会话已变化，请重新检查。',
  };
  return messages[error.message] || (error.name === 'AbortError'
    ? '请求超时，请检查服务后重试。'
    : `检查未完成（${error.message || 'request_failed'}）。请确认当前登录与服务配置后重试。`);
}

async function initialize() {
  try {
    const data = await fetchJSON('/diagnostics');
    if (data.source !== 'alchemy_server_configuration') throw new Error('unexpected_diagnostics_source');
    $('native-link').hidden = !data.native_enabled;
    $('configuration').replaceChildren(
      paragraph(`模式：${readable(data.mode)}`),
      paragraph(`已配置执行配置：${readable(data.configured_profiles)}`),
      paragraph(`原生开发入口：${data.native_enabled ? '已启用' : '未启用'}；支持：${readable(data.native_profiles)}`),
      paragraph('本地 CLI：未检查。浏览器无法探测另一台机器上的代理。', 'muted'),
      paragraph('真实原生配置：不支持。真实生成：未验证。正式交付：否。', 'muted'),
    );
    if (data.configuration_error) $('configuration').append(paragraph(`配置错误：${readable(data.configuration_error)}`, 'error'));
    status('notice', '已读取 Alchemy 配置。此次配置读取未连接 Bridge，也未运行本地 CLI。');
  } catch (error) { status('notice', errorText(error), true); }
}

function renderProfile(profile) {
  const article = document.createElement('article');
  article.className = 'task';
  article.append(
    paragraph(`${readable(profile.execution_profile_id)} · 修订 ${readable(profile.execution_profile_revision)}`, 'task-title'),
    paragraph(`执行模式：${readable(profile.execution_mode)}；验证声明：${readable(profile.validation)}`),
    paragraph('生产验证：未验证。此能力声明不代表已完成真实生成。', 'muted'),
  );
  const contract = profile.parameter_contract;
  if (!contract || contract.schema_version !== '1') {
    article.append(paragraph('参数合同不可用：服务端未提供兼容版本。这不代表没有能力；请更新匹配的 Bridge 后重查。', 'muted'));
  } else {
    for (const [label, key] of [
      ['接受参数', 'accepted_parameters'], ['必填参数', 'required_parameters'],
      ['尺寸语义', 'dimension_semantics'], ['种子语义', 'seed_semantics'], ['执行器控制', 'executor_control'],
      ['参考图语义', 'reference_semantics'], ['不支持参数', 'unsupported_parameters'],
    ]) article.append(paragraph(`${label}：${readable(contract[key])}`));
  }
  return article;
}

$('check-server').addEventListener('click', async () => {
  if (checking) return;
  checking = true;
  $('check-server').disabled = true;
  $('server-profiles').replaceChildren();
  status('server-status', '正在检查已配置 Bridge 的 HTTP 服务，不探测本地 CLI…');
  try {
    const data = await fetchJSON('/diagnostics/server');
    if (data.source !== 'configured_bridge_http') throw new Error('unexpected_diagnostics_source');
    const labels = {ok: 'HTTP 连接正常', unavailable: 'HTTP 服务不可达', incompatible: 'HTTP 合同不兼容'};
    const label = labels[data.connection];
    if (!label) throw new Error('invalid_diagnostics_connection');
    status('server-status', `${label}${data.code ? `（${readable(data.code)}）` : ''}。本地 CLI、登录与真实生成未验证。`, data.connection !== 'ok');
    const profiles = Array.isArray(data.profiles) ? data.profiles : [];
    $('server-profiles').replaceChildren(...profiles.map(renderProfile));
    if (!profiles.length) $('server-profiles').append(paragraph('本次未取得执行配置能力。请检查 Bridge 服务、配置或版本后重试。', 'muted'));
  } catch (error) { status('server-status', errorText(error), true); }
  finally { checking = false; $('check-server').disabled = false; }
});

$('import-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (importing) return;
  const file = $('report-file').files[0];
  if (!file) return;
  importing = true;
  $('import-report').disabled = true;
  $('report-file').disabled = true;
  $('report-result').replaceChildren();
  status('report-status', '正在校验报告格式，不运行 CLI，也不接受其中的授权声明…');
  try {
    if (file.size > maxReportBytes) throw new Error('report_too_large');
    const original = await file.text();
    let report;
    try { report = JSON.parse(original); }
    catch { throw new Error('invalid_report_json'); }
    if (!report || typeof report !== 'object' || Array.isArray(report)) throw new Error('invalid_report_format');
    if (report.schema_version !== '1') throw new Error('unsupported_report_version');
    if (report.kind !== 'render_bridge_doctor') throw new Error('invalid_report_format');
    const data = await fetchJSON('/diagnostics/report', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Alchemy-Bridge-Preview': '1'},
      body: original,
    });
    if (data.source !== 'user_imported_local_report' || data.verified_by_server !== false || data.authorization_effect !== 'none') {
      throw new Error('unexpected_report_authority');
    }
    report = data.report;
    if (!report || report.schema_version !== '1') throw new Error('unsupported_diagnostics_version');
    const outcomes = {ready: '检查项就绪（仅报告自述）', attention: '需要处理', invalid: '配置无效或无法读取（报告自述）'};
    status('report-status', `已导入自述证据：${outcomes[report.outcome] || '未知检查结果'}。未授权执行配置，登录与真实生成未验证。`);
    const result = $('report-result');
    result.append(
      paragraph(`报告生成器：${readable(report.producer?.name)} ${readable(report.producer?.version)}`, 'muted'),
      paragraph(`报告执行配置：${readable(report.profiles)}`, 'muted'),
      paragraph('服务端只校验格式，无法确认来源或新鲜度。本页面不保存报告。', 'muted'),
    );
    const evidence = {configuration: '配置记录', local_probe: '本地探测（报告自述）', operator_declaration: '操作者声明', not_checked: '未检查'};
    const states = {pass: '通过（报告自述）', attention: '需处理', fail: '失败', not_checked: '未检查'};
    for (const check of report.checks || []) {
      const article = document.createElement('article');
      article.className = 'task';
      article.append(
        paragraph(`${readable(check.id)}：${states[check.status] || readable(check.status)}`, 'task-title'),
        paragraph(`证据：${evidence[check.evidence] || readable(check.evidence)}；代码：${readable(check.code)}`, 'muted'),
        paragraph(`下一步：${readable(check.next_step)}`),
      );
      result.append(article);
    }
  } catch (error) { status('report-status', errorText(error), true); }
  finally {
    importing = false;
    $('import-report').disabled = false;
    $('report-file').disabled = false;
    $('report-file').value = '';
  }
});

window.addEventListener('storage', (event) => {
  if (event.key === 'alchemy_veyra_access_token' || event.key === null) {
    $('configuration').replaceChildren();
    $('server-profiles').replaceChildren();
    $('report-result').replaceChildren();
    $('report-file').value = '';
    status('server-status', '登录会话已变化，请重新检查。');
    status('report-status', '登录会话已变化，已清除导入报告。');
    initialize();
  }
});
window.addEventListener('pagehide', () => {
  $('report-file').value = '';
  $('report-result').replaceChildren();
  status('report-status', '尚未导入。本页面不保存报告。');
});
initialize();
