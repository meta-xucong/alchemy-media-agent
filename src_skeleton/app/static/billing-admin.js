const v2LocalApiBase = "http://127.0.0.1:8020/api/v2";
const localPortalHomeUrl = "http://127.0.0.1:18080/";
const productionPortalHomeUrl = "https://aiself.vip/";
const v2ApiBase =
  window.ALCHEMY_V2_API_BASE ||
  (window.location.port === "8017" ? v2LocalApiBase : `${window.location.origin}/api/v2`);
const veyraTokenStorageKey = "alchemy_veyra_access_token";

const els = {
  brandHomeLink: document.querySelector("#brandHomeLink"),
  adminState: document.querySelector("#adminState"),
  billingConsoleState: document.querySelector("#billingConsoleState"),
  billingRefreshBtn: document.querySelector("#billingRefreshBtn"),
  billingSettingsForm: document.querySelector("#billingSettingsForm"),
  billingRulesGrid: document.querySelector("#billingRulesGrid"),
  billingSaveBtn: document.querySelector("#billingSaveBtn"),
  billingSettingsHint: document.querySelector("#billingSettingsHint"),
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
  loadBillingSettings({ silent: true }).catch((error) => showGlobalToast(friendlyError(error), "error"));
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
  if (!getVeyraToken()) {
    renderSignedOut();
    throw new Error("请先从 Veyra Agent 登录管理员账户。");
  }
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
