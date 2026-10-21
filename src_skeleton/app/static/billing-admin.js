const v2LocalApiBase = "http://127.0.0.1:8020/api/v2";
const localPortalHomeUrl = "http://127.0.0.1:18080/";
const productionPortalHomeUrl = "https://aiself.vip/";
const v2ApiBase =
  window.ALCHEMY_V2_API_BASE ||
  (isLocalAlchemyHost() ? v2LocalApiBase : `${window.location.origin}/api/v2`);
const veyraTokenStorageKey = "alchemy_veyra_access_token";

function isLocalAlchemyHost() {
  return ["127.0.0.1", "localhost", "::1", "[::1]"].includes(window.location.hostname);
}

const els = {
  brandHomeLink: document.querySelector("#brandHomeLink"),
  adminState: document.querySelector("#adminState"),
  billingConsoleState: document.querySelector("#billingConsoleState"),
  billingRefreshBtn: document.querySelector("#billingRefreshBtn"),
  billingSettingsForm: document.querySelector("#billingSettingsForm"),
  billingRulesGrid: document.querySelector("#billingRulesGrid"),
  billingSaveBtn: document.querySelector("#billingSaveBtn"),
  billingSettingsHint: document.querySelector("#billingSettingsHint"),
  retentionConsoleState: document.querySelector("#retentionConsoleState"),
  retentionSettingsForm: document.querySelector("#retentionSettingsForm"),
  retentionProtectedData: document.querySelector("#retentionProtectedData"),
  retentionDays: document.querySelector("#retentionDays"),
  retentionSaveBtn: document.querySelector("#retentionSaveBtn"),
  retentionSettingsHint: document.querySelector("#retentionSettingsHint"),
  globalToast: document.querySelector("#globalToast"),
};

const state = {
  rules: [],
  loading: false,
};

document.addEventListener("DOMContentLoaded", () => {
  hydratePortalHomeLink();
  els.billingRefreshBtn?.addEventListener("click", () => loadBillingSettings({ silent: false }));
  els.billingSettingsForm?.addEventListener("submit", saveBillingSettings);
  els.retentionSettingsForm?.addEventListener("submit", saveRetentionSettings);
  loadBillingSettings({ silent: true }).catch((error) => showGlobalToast(friendlyError(error), "error"));
  loadRetentionSettings().catch((error) => showGlobalToast(friendlyError(error), "error"));
  initializeBridgeAdmin();
});

function hydratePortalHomeLink() {
  if (!els.brandHomeLink) return;
  const configuredUrl =
    typeof window.VEYRA_PORTAL_URL === "string" && window.VEYRA_PORTAL_URL.trim()
      ? window.VEYRA_PORTAL_URL.trim()
      : "";
  const localHostnames = new Set(["127.0.0.1", "localhost", "::1"]);
  els.brandHomeLink.href = configuredUrl || (localHostnames.has(window.location.hostname) ? localPortalHomeUrl : productionPortalHomeUrl);
}

async function loadBillingSettings({ silent = true } = {}) {
  setLoading(true);
  try {
    const settings = await v2Request("/veyra/billing/settings");
    state.rules = Array.isArray(settings.rules) ? settings.rules : [];
    renderRules();
    if (els.adminState) els.adminState.textContent = "管理员已验证";
    if (els.billingConsoleState) els.billingConsoleState.textContent = settings.persisted ? "已持久化" : "启动配置";
    if (!silent) showGlobalToast("计费设置已刷新。");
  } catch (error) {
    if (error.status === 403) {
      renderForbidden();
    } else if (error.status === 401) {
      renderSignedOut();
    }
    throw error;
  } finally {
    setLoading(false);
  }
}

async function saveBillingSettings(event) {
  event.preventDefault();
  const rules = [...document.querySelectorAll("[data-billing-rule]")].map((row) => ({
    key: row.dataset.billingRule,
    enabled: Boolean(row.querySelector("[data-rule-enabled]")?.checked),
    charge_amount: Number(row.querySelector("[data-rule-amount]")?.value || 0),
  }));
  for (const rule of rules) {
    if (!Number.isFinite(rule.charge_amount) || rule.charge_amount < 0) {
      showGlobalToast("扣费金额必须是 0 或正数。", "error");
      return;
    }
  }
  setLoading(true);
  try {
    const settings = await v2Request("/veyra/billing/settings", {
      method: "POST",
      body: { rules },
    });
    state.rules = Array.isArray(settings.rules) ? settings.rules : [];
    renderRules();
    if (els.billingConsoleState) els.billingConsoleState.textContent = "已持久化";
    showGlobalToast("计费参数已保存。");
  } catch (error) {
    showGlobalToast(`保存失败：${friendlyError(error)}`, "error");
  } finally {
    setLoading(false);
  }
}

async function loadRetentionSettings() {
  try {
    const settings = await adminRequest("/v1/admin/retention/settings");
    if (els.retentionProtectedData) els.retentionProtectedData.checked = Boolean(settings.delete_protected_data);
    if (els.retentionDays) els.retentionDays.value = String(settings.retention_days ?? 30);
    if (els.retentionConsoleState) els.retentionConsoleState.textContent = settings.persisted ? "已持久化" : "默认配置";
    if (els.retentionSettingsHint) els.retentionSettingsHint.textContent = "只有管理员可以修改。";
  } catch (error) {
    if (error.status === 403) renderRetentionForbidden();
    else if (error.status === 401) renderRetentionSignedOut();
    throw error;
  }
}

async function saveRetentionSettings(event) {
  event.preventDefault();
  const retentionDays = Number(els.retentionDays?.value || 30);
  if (!Number.isInteger(retentionDays) || retentionDays < 1 || retentionDays > 3650) {
    showGlobalToast("保留天数必须是 1 到 3650 之间的整数。", "error");
    return;
  }
  if (els.retentionSaveBtn) els.retentionSaveBtn.disabled = true;
  try {
    const settings = await adminRequest("/v1/admin/retention/settings", {
      method: "POST",
      body: {
        delete_protected_data: Boolean(els.retentionProtectedData?.checked),
        retention_days: retentionDays,
      },
    });
    if (els.retentionProtectedData) els.retentionProtectedData.checked = Boolean(settings.delete_protected_data);
    if (els.retentionDays) els.retentionDays.value = String(settings.retention_days ?? retentionDays);
    if (els.retentionConsoleState) els.retentionConsoleState.textContent = "已持久化";
    showGlobalToast("清理设置已保存。");
  } catch (error) {
    showGlobalToast(`保存失败：${friendlyError(error)}`, "error");
  } finally {
    if (els.retentionSaveBtn) els.retentionSaveBtn.disabled = false;
  }
}

function renderRules() {
  if (!els.billingRulesGrid) return;
  els.billingRulesGrid.innerHTML = "";
  if (!state.rules.length) {
    els.billingRulesGrid.innerHTML = `<p class="empty-state">没有可配置的计费规则。</p>`;
    return;
  }
  state.rules.forEach((rule) => {
    const row = document.createElement("article");
    row.className = "billing-rule-card";
    row.dataset.billingRule = rule.key;
    row.innerHTML = `
      <div>
        <p class="eyebrow">${escapeHtml(rule.agent || "agent")} / ${escapeHtml(rule.version || "version")}</p>
        <h3>${escapeHtml(rule.label || rule.key)}</h3>
        <span class="micro-copy">${escapeHtml(rule.key)}</span>
      </div>
      <label class="billing-toggle-row">
        <input data-rule-enabled type="checkbox" ${rule.enabled ? "checked" : ""} />
        <span>启用扣费</span>
      </label>
      <label class="field">
        <span>单次生图扣费</span>
        <input data-rule-amount type="number" min="0" step="0.01" value="${Number(rule.charge_amount || 0)}" />
      </label>
    `;
    els.billingRulesGrid.appendChild(row);
  });
}

function renderSignedOut() {
  if (els.adminState) els.adminState.textContent = "未登录";
  if (els.billingConsoleState) els.billingConsoleState.textContent = "未接入";
  if (els.billingSettingsHint) els.billingSettingsHint.textContent = "请从 Veyra Agent 登录后再进入管理员页。";
  if (els.billingRulesGrid) els.billingRulesGrid.innerHTML = `<p class="empty-state">当前没有 Alchemy 管理员会话。</p>`;
}

function renderForbidden() {
  if (els.adminState) els.adminState.textContent = "非管理员";
  if (els.billingConsoleState) els.billingConsoleState.textContent = "无权限";
  if (els.billingSettingsHint) els.billingSettingsHint.textContent = "只有 sub2api 管理员账户可以修改计费参数。";
  if (els.billingRulesGrid) els.billingRulesGrid.innerHTML = `<p class="empty-state">当前账户不是 sub2api 管理员。</p>`;
}

function renderRetentionSignedOut() {
  if (els.retentionConsoleState) els.retentionConsoleState.textContent = "未登录";
  if (els.retentionSettingsHint) els.retentionSettingsHint.textContent = "请从 Veyra Agent 登录后再进入管理员页。";
  if (els.retentionSettingsForm) els.retentionSettingsForm.innerHTML = `<p class="empty-state">当前没有 Alchemy 管理员会话。</p>`;
}

function renderRetentionForbidden() {
  if (els.retentionConsoleState) els.retentionConsoleState.textContent = "非管理员";
  if (els.retentionSettingsHint) els.retentionSettingsHint.textContent = "只有管理员可以修改清理设置。";
  if (els.retentionSettingsForm) els.retentionSettingsForm.innerHTML = `<p class="empty-state">当前账户不是管理员。</p>`;
}

function setLoading(isLoading) {
  state.loading = isLoading;
  if (els.billingRefreshBtn) {
    els.billingRefreshBtn.disabled = isLoading;
    els.billingRefreshBtn.textContent = isLoading ? "刷新中..." : "刷新设置";
  }
  if (els.billingSaveBtn) {
    els.billingSaveBtn.disabled = isLoading;
    els.billingSaveBtn.textContent = isLoading ? "保存中..." : "保存全部设置";
  }
}

async function v2Request(path, options = {}) {
  const headers = {};
  if (options.body) headers["Content-Type"] = "application/json";
  const token = getVeyraToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${v2ApiBase}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
    credentials: "include",
  });
  if (!response.ok) {
    const detail = await response.text();
    const error = new Error(detail || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function adminRequest(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  const token = getVeyraToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
    credentials: "include",
  });
  if (!response.ok) {
    const detail = await response.text();
    const error = new Error(detail || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function getVeyraToken() {
  try {
    return localStorage.getItem(veyraTokenStorageKey) || "";
  } catch {
    return "";
  }
}

function showGlobalToast(message, type = "success") {
  if (!els.globalToast) return;
  els.globalToast.textContent = message;
  els.globalToast.className = `global-toast ${type === "error" ? "error" : ""}`.trim();
  els.globalToast.hidden = false;
  window.clearTimeout(showGlobalToast.timer);
  showGlobalToast.timer = window.setTimeout(() => {
    els.globalToast.hidden = true;
  }, 2600);
}

function friendlyError(error) {
  if (!error) return "未知错误";
  try {
    const parsed = JSON.parse(error.message);
    return parsed.detail?.message || parsed.detail?.error_code || parsed.message || error.message;
  } catch {
    return error.message || String(error);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function initializeBridgeAdmin() {
  const form = document.querySelector("#bridgeAdminForm");
  if (!form) return;
  const fields = document.querySelector("#bridgeAdminFields");
  const hint = document.querySelector("#bridgeAdminHint");
  const result = document.querySelector("#bridgeAdminResult");
  const mode = document.querySelector("#bridgeAdminMode");
  const url = document.querySelector("#bridgeAdminUrl");
  const workspace = document.querySelector("#bridgeAdminWorkspace");
  const profiles = document.querySelector("#bridgeAdminProfiles");
  const nativeProfiles = document.querySelector("#bridgeAdminNativeProfiles");
  const native = document.querySelector("#bridgeAdminNative");
  const status = document.querySelector("#bridgeAdminState");
  const probe = document.querySelector("#bridgeAdminProbe");
  const errors = {
    bridge_configuration_missing: "配置不完整：请填写地址和工作区，并由部署管理员在服务器环境中配置凭据。",
    credential_endpoint_mismatch: "地址与服务器凭据绑定的目标不一致。请先由部署管理员更新对应的服务器配置。",
    bridge_pending_tasks_require_existing_configuration: "仍有未完成任务，暂不能修改目标或执行配置。可先排空，或停用并保留原配置。",
    bridge_pending_state_unavailable: "无法确认已有任务状态，暂不允许修改目标配置。",
    invalid_bridge_url: "请使用不含账号、密码、路径或查询参数的 HTTPS 服务地址。",
    invalid_profiles: "请选择有效且不重复的执行配置。",
    invalid_native_profiles: "原生开发入口配置必须包含在允许的执行配置中。",
    bridge_settings_write_failed: "设置保存失败，原配置未更改。",
  };
  const selected = (select) => Array.from(select.selectedOptions, (option) => option.value);
  function render(value) {
    mode.value = value.mode;
    url.value = value.base_url || "";
    workspace.value = value.workspace || "";
    native.checked = value.native_enabled;
    for (const option of profiles.options) option.selected = (value.profiles || []).includes(option.value);
    for (const option of nativeProfiles.options) option.selected = (value.native_profiles || []).includes(option.value);
    document.querySelector("#bridgeAdminCredential").textContent = value.credential_configured ? "已配置 · 不显示密钥" : "未配置 · 请由部署管理员在服务器设置";
    const modes = { disabled: "已停用", enabled: "已启用", draining: "排空中" };
    status.textContent = (modes[value.mode] || "状态未知") + (value.mode !== "disabled" && value.configuration_error ? " · 不可用" : "");
    probe.disabled = value.mode === "disabled" || Boolean(value.configuration_error);
    hint.textContent = value.configuration_error && value.mode !== "disabled"
      ? (errors[value.configuration_error] || "运行配置异常，请检查服务器配置。")
      : "页面加载不探测远程服务。探测仅检查已保存配置；HTTP 连通不等于节点或真实工具可用。";
    if (value.native_enabled && value.native_runtime_error) hint.textContent += " 原生开发入口初始化失败，尚不可用。";
  }
  function fail(error) {
    if (error.status === 401 || error.status === 403) {
      fields.disabled = true;
      status.textContent = error.status === 401 ? "未登录" : "非管理员";
      hint.textContent = error.status === 401 ? "请登录 Alchemy 管理员账户后重试。" : "只有管理员可以读取或修改桥接设置。";
      return;
    }
    let code;
    try { code = JSON.parse(error.message).detail?.code; } catch {}
    hint.textContent = errors[code] || "桥接操作失败，请稍后重试。";
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    fields.disabled = true;
    result.hidden = true;
    try {
      const value = await adminRequest("/v1/admin/render-bridge/settings", {
        method: "POST", headers: { "X-Alchemy-Bridge-Admin": "1" },
        body: { mode: mode.value, base_url: url.value, workspace: workspace.value,
          profiles: selected(profiles), native_enabled: native.checked, native_profiles: selected(nativeProfiles) },
      });
      fields.disabled = false;
      render(value);
      hint.textContent = (value.configuration_error && value.mode !== "disabled") || value.native_runtime_error ? hint.textContent : "桥接设置已保存并生效。已有任务数据保留。";
    } catch (error) { fields.disabled = false; fail(error); }
  });
  probe.addEventListener("click", async () => {
    fields.disabled = true;
    result.hidden = false;
    result.textContent = "正在探测已保存配置…";
    try {
      const value = await adminRequest("/v1/admin/render-bridge/probe", { method: "POST", headers: { "X-Alchemy-Bridge-Admin": "1" } });
      const labels = { not_checked: "未检查", reachable: "可连接", unavailable: "不可连接", accepted: "通过", rejected: "未通过", compatible: "兼容", incompatible: "不兼容", unknown: "未知", offline: "离线", available: "已报告可用", busy: "忙碌", attention: "需要处理" };
      const label = (value) => labels[value] || "未知";
      const lines = [`HTTP 连接：${label(value.connection)}`, `身份验证：${label(value.authentication)}`, `能力协议：${label(value.capabilities)}`, `执行节点：${label(value.node_readiness)}`];
      if (value.admission) lines.push(`Bridge 新任务接收：${value.admission.accepting_new_tasks ? "允许" : "暂停"}`);
      for (const profile of value.profiles || []) lines.push(`${profile.execution_profile_id}：${label(profile.availability)}`);
      lines.push("真实生图尚未验证；探测不会生成图片、配置凭据或授权正式交付。");
      result.textContent = lines.join("\n");
      fields.disabled = false;
    } catch (error) { fields.disabled = false; result.textContent = "探测未完成。"; fail(error); }
  });
  adminRequest("/v1/admin/render-bridge/settings").then((value) => { fields.disabled = false; render(value); }).catch(fail);
}
