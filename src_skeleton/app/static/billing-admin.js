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
  const get = (id) => document.querySelector(`#bridgeAdmin${id}`);
  const fields = get("Fields"), hint = get("Hint"), result = get("Result"), status = get("State");
  const rewardState = document.querySelector("#bridgeRewardState");
  const rewardSummary = document.querySelector("#bridgeRewardSummary");
  const rewardRows = document.querySelector("#bridgeRewardRows");
  const rewardRefresh = document.querySelector("#bridgeRewardRefresh");
  const url = get("Url"), workspace = get("Workspace"), nativeProfiles = get("NativeProfiles"), native = get("Native");
  const toolButtons = Array.from(get("Profiles").querySelectorAll("button[data-profile]"));
  const actions = { enabled: get("Enable"), draining: get("Pause"), disabled: get("Disable") };
  const toolNames = { "fake-image": "模拟测试（不生成真实图片）", "codex-image": "Codex 绘图", "midjourney-manual": "Midjourney 人工导入" };
  let saved = null, busy = false, authorized = false, correctingRewardBinding = false;
  const errors = {
    bridge_configuration_missing: "请找管理员完成首次连接，再点击开启。",
    credential_endpoint_mismatch: "连接地址还未准备好，请找管理员确认连接设置。",
    credential_workspace_mismatch: "工作区与服务器配置不一致，请找管理员确认。",
    bridge_pending_tasks_require_existing_configuration: "还有任务未完成。请先暂停，等已有任务完成后再修改工具或连接设置。",
    bridge_pending_state_unavailable: "暂时无法确认已有任务状态，请稍后重试。",
    invalid_bridge_url: "连接地址不正确，请找管理员检查。",
    invalid_profiles: "请至少选择一种绘图工具。",
    invalid_native_profiles: "开发入口的工具需要同时在允许使用的工具中选中。",
    bridge_settings_write_failed: "没有保存成功，请稍后重试。",
  };
  function controls() {
    fields.disabled = busy || !authorized;
    for (const [mode, button] of Object.entries(actions)) button.disabled = busy || !authorized || saved?.mode === mode;
    get("Probe").disabled = busy || !authorized;
    get("Fallback").disabled = busy || !authorized;
    if (rewardRefresh) rewardRefresh.disabled = busy || !authorized;
  }
  function rewardBindingCorrection(node) {
    if (node.reward_status !== "accruing"
        || !Number.isSafeInteger(node.metrics?.rewardable_images)
        || node.metrics.rewardable_images < 0
        || node.reward_account_bound !== true
        || !Number.isSafeInteger(node.reward_account_user_id)
        || !Number.isSafeInteger(node.binding_revision)
        || !node.pool_id || !node.node_id || !node.executor_instance) return null;
    const details = document.createElement("details");
    details.className = "bridge-admin-details";
    const summary = document.createElement("summary");
    summary.textContent = "修正账号归属";
    const note = document.createElement("p");
    note.className = "micro-copy";
    note.textContent = "仅用于管理员核实后的误绑纠正。转移前累计留在原账号，新账号从当前 Bridge 图片计数之后开始累计。";
    const form = document.createElement("form");
    form.dataset.rewardBindingCorrection = "true";
    form.dataset.poolId = String(node.pool_id);
    form.dataset.nodeId = String(node.node_id);
    form.dataset.executorInstance = String(node.executor_instance);
    form.dataset.expectedUserId = String(node.reward_account_user_id);
    form.dataset.expectedRevision = String(node.binding_revision);
    const label = document.createElement("label"); label.className = "field";
    const caption = document.createElement("span"); caption.textContent = "目标 Alchemy 账号 ID";
    const input = document.createElement("input"); input.type = "number"; input.min = "1";
    input.step = "1"; input.required = true; input.inputMode = "numeric";
    input.setAttribute("aria-label", "目标 Alchemy 账号 ID");
    label.append(caption, input);
    const button = document.createElement("button");
    button.className = "button secondary"; button.type = "submit";
    button.textContent = "核实后修正";
    const actions = document.createElement("div"); actions.className = "billing-actions";
    actions.append(button); form.append(label, actions);
    details.append(summary, note, form);
    return details;
  }
  async function submitRewardBindingCorrection(event) {
    const form = event.target.closest("form[data-reward-binding-correction]");
    if (!form) return;
    event.preventDefault();
    if (!authorized || correctingRewardBinding) return;
    const input = form.querySelector('input[type="number"]');
    const newUserId = Number(input?.value);
    if (!Number.isSafeInteger(newUserId) || newUserId <= 0) {
      showGlobalToast("请输入有效的目标 Alchemy 账号 ID。", "error"); return;
    }
    const oldUserId = Number(form.dataset.expectedUserId);
    if (newUserId === oldUserId) {
      showGlobalToast("目标账号与当前账号相同，无需修正。", "error"); return;
    }
    const count = Number(form.dataset.rewardableImages);
    const boundary = Number.isSafeInteger(count) && count >= 0 ? count.toLocaleString("zh-CN") : "当前可验证的";
    if (!window.confirm(`节点 ${form.dataset.nodeId} 将从账号 ${oldUserId} 转到账号 ${newUserId}。截至 Bridge 当前已确认 ${boundary} 张可计奖图片，历史累计保留给原账号，新账号从该计数之后开始。继续吗？`)) return;
    correctingRewardBinding = true;
    const button = form.querySelector('button[type="submit"]');
    if (button) { button.disabled = true; button.textContent = "正在修正…"; }
    try {
      await adminRequest("/v1/admin/render-bridge/rewards/bindings/correct", {
        method: "POST",
        headers: { "X-Alchemy-Bridge-Admin": "1" },
        body: {
          pool_id: form.dataset.poolId,
          node_id: form.dataset.nodeId,
          executor_instance: form.dataset.executorInstance,
          expected_user_id: oldUserId,
          expected_revision: Number(form.dataset.expectedRevision),
          new_user_id: newUserId,
        },
      });
      showGlobalToast("账号归属已修正，正在刷新奖励统计。");
      await refreshRewards();
    } catch (error) {
      let code;
      try { code = JSON.parse(error.message).detail?.code; } catch {}
      const messages = {
        node_reward_binding_stale: "绑定已被其他操作更新，请刷新后重新核实。",
        node_reward_baseline_unavailable: "奖励基线尚未确认，本次没有修改绑定；请先等待基线初始化。",
        reward_metrics_incomplete: "Bridge 计数暂不完整，本次没有修改绑定。",
        reward_image_count_unavailable: "Bridge 图片计数不可用，本次没有修改绑定。",
        reward_destination_account_unavailable: "目标账号不存在或未启用，本次没有修改绑定。",
        node_reward_metrics_regressed: "Bridge 计数低于原基线，本次没有修改绑定。",
      };
      showGlobalToast(messages[code] || "修正未完成，请刷新并确认管理员权限。", "error");
    } finally {
      correctingRewardBinding = false;
      if (button) { button.disabled = false; button.textContent = "核实后修正"; }
    }
  }
  function ready(value) { return Boolean(value.base_url && value.workspace && value.credential_configured); }
  function basicStatus(value) {
    if (!ready(value)) { status.textContent = "还没连接好"; hint.textContent = "请找管理员完成首次连接，再点击开启。"; }
    else if (value.configuration_error || value.native_runtime_error) { status.textContent = "暂时不可用"; hint.textContent = "请找管理员检查连接设置，再点击检查连接。"; }
    else if (value.mode === "disabled") { status.textContent = "已关闭"; hint.textContent = "需要使用时，点击开启。已有任务不会删除。"; }
    else if (value.mode === "draining") { status.textContent = "已暂停"; hint.textContent = "已有任务会继续完成。需要接收新任务时，点击开启。"; }
    else { status.textContent = "已开启，待检查"; hint.textContent = "点击检查连接，看看绘图工具是否在线。"; }
  }
  function render(value) {
    saved = value;
    url.value = value.base_url || "";
    workspace.value = value.workspace || "";
    native.checked = Boolean(value.native_enabled);
    get("Fallback").checked = value.auto_fallback_enabled === true;
    get("QueueWait").value = value.queue_wait_seconds ?? 30;
    for (const button of toolButtons) button.setAttribute("aria-pressed", String((value.profiles || []).includes(button.dataset.profile)));
    for (const option of nativeProfiles.options) option.selected = (value.native_profiles || []).includes(option.value);
    get("Credential").textContent = value.credential_configured ? "已配置 · 不显示密钥" : "尚未配置，请找管理员完成";
    get("ToolSummary").textContent = `当前工具：${(value.profiles || []).map((id) => toolNames[id] || "其他工具").join("、") || "尚未选择"}`;
    const entry = get("Open");
    entry.hidden = value.mode !== "enabled" || !value.runtime_active || Boolean(value.configuration_error) || (value.native_enabled && !value.native_runtime_active);
    entry.href = value.native_enabled ? "/render-bridge-native-test" : "/render-bridge-preview";
    entry.textContent = "打开桥接试用入口";
    basicStatus(value);
    controls();
  }
  function fail(error) {
    if (error.status === 401 || error.status === 403) {
      authorized = false;
      get("Open").hidden = true;
      status.textContent = error.status === 401 ? "请先登录" : "需要管理员权限";
      hint.textContent = error.status === 401 ? "请登录管理员账户后重新打开此页。" : "请让管理员帮你完成设置。";
      if (rewardState) rewardState.textContent = error.status === 401 ? "请先登录管理员账号" : "需要管理员权限";
      if (rewardRows) {
        const empty = document.createElement("div"); empty.className = "bridge-node-empty";
        empty.textContent = error.status === 401 ? "登录管理员账号后可查看节点状态和奖励统计。" : "当前账号没有查看节点统计的权限。";
        rewardRows.replaceChildren(empty);
      }
    } else {
      let code;
      try { code = JSON.parse(error.message).detail?.code; } catch {}
      status.textContent = "操作未完成";
      hint.textContent = errors[code] || "暂时没有完成，请稍后重试。仍不成功时，请找管理员帮忙。";
    }
    controls();
  }
  async function refreshRewards() {
    if (!authorized || !rewardState || !rewardSummary || !rewardRows) return;
    rewardState.textContent = "正在读取…";
    try {
      const value = await adminRequest("/v1/admin/render-bridge/rewards");
      if (!value.available) {
        rewardState.textContent = value.code === "reward_metrics_not_configured" ? "统计连接尚未配置" : "节点数据暂不可用";
        rewardSummary.replaceChildren();
        for (const [label, detail] of [["节点总数", "连接统计后显示"], ["忙碌节点", "当前正在处理任务"], ["成功图片", "节点账本累计"], ["累计奖励积分", "从账号绑定起按图片累计"]]) {
          const card = document.createElement("div"); card.className = "bridge-reward-stat";
          const name = document.createElement("span"); name.textContent = label;
          const count = document.createElement("strong"); count.textContent = "—";
          const note = document.createElement("small"); note.textContent = detail;
          card.append(name, count, note); rewardSummary.append(card);
        }
        const empty = document.createElement("div"); empty.className = "bridge-node-empty";
        empty.textContent = "暂时无法读取节点统计，请稍后刷新或检查连接设置。";
        rewardRows.replaceChildren(empty); return;
      }
      const labels = { online: "在线", busy: "忙碌", needs_attention: "需处理", offline: "离线",
        active: "正常", draining: "暂停接单", revoked: "已撤销",
        assigned: "已分配", claimed: "已领取", running: "执行中", uploading: "上传中",
        awaiting_user: "待人工", execution_unknown: "结果未知", succeeded: "成功", failed: "失败",
        cancelled: "已取消", artifacts_ready: "已提交" };
      const nodes = Array.isArray(value.nodes) ? value.nodes : [];
      const safeCount = (count) => Number.isSafeInteger(count) && count >= 0 ? count : null;
      const countText = (count) => count === null ? "—" : count.toLocaleString("zh-CN");
      const imageCounts = nodes.map((node) => safeCount(node.metrics?.rewardable_images));
      const allImageCountsAvailable = imageCounts.every((count) => count !== null);
      const imageTotal = allImageCountsAvailable
        ? imageCounts.reduce((sum, count) => sum + BigInt(count), 0n) : null;
      const totalNodes = nodes.length;
      const onlineNodes = nodes.filter((node) => ["online", "busy"].includes(node.liveness)).length;
      const busyNodes = nodes.filter((node) => node.liveness === "busy").length;
      const rewardTotals = value.reward_totals || {};
      const pointsTotal = value.reward_account_stats_available === true && rewardTotals.complete === true
        && typeof rewardTotals.reward_points === "string" && /^\d+\.\d{2}$/.test(rewardTotals.reward_points)
        ? rewardTotals.reward_points : "—";
      const pointsDetail = value.reward_account_stats_available !== true
        ? "账号奖励统计暂不可用"
        : rewardTotals.complete === true
          ? `${countText(safeCount(rewardTotals.bound_nodes))} 台已绑定账号`
          : `${countText(safeCount(rewardTotals.pending_nodes))} 台奖励数据待确认`;
      const summaryItems = [
        ["节点总数", countText(totalNodes), `${onlineNodes} 台在线`],
        ["忙碌节点", countText(busyNodes), "当前正在处理任务"],
        ["成功图片", countText(imageTotal), "已确认交付"],
        ["累计奖励积分", pointsTotal, pointsDetail],
      ];
      rewardSummary.replaceChildren();
      for (const [label, count, detail] of summaryItems) {
        const card = document.createElement("div"); card.className = "bridge-reward-stat";
        const name = document.createElement("span"); name.textContent = label;
        const number = document.createElement("strong"); number.textContent = count;
        const note = document.createElement("small"); note.textContent = detail;
        card.append(name, number, note); rewardSummary.append(card);
      }

      const ageText = (seconds) => {
        if (!Number.isSafeInteger(seconds) || seconds < 0) return "心跳时间未知";
        if (seconds < 60) return `最近心跳 ${seconds} 秒前`;
        if (seconds < 3600) return `最近心跳 ${Math.floor(seconds / 60)} 分钟前`;
        return `最近心跳 ${Math.floor(seconds / 3600)} 小时前`;
      };
      const statusText = { online: "在线", busy: "忙碌", needs_attention: "需关注", offline: "离线" };
      const statusClass = { online: "online", busy: "busy", needs_attention: "attention", offline: "offline" };
      const receiveText = { active: "接单正常", draining: "暂停接单", revoked: "已停用" };
      const createMetric = (label, value) => {
        const item = document.createElement("div"); item.className = "bridge-node-metric";
        const caption = document.createElement("span"); caption.textContent = label;
        const number = document.createElement("strong"); number.textContent = value;
        item.append(caption, number); return item;
      };
      rewardRows.replaceChildren();
      for (const node of nodes) {
        const metrics = node.metrics || {};
        const imageCount = safeCount(metrics.rewardable_images);
        const failedCount = safeCount(metrics.failed);
        const card = document.createElement("article"); card.className = "bridge-node-card"; card.setAttribute("role", "listitem");
        const heading = document.createElement("div"); heading.className = "bridge-node-heading";
        const identity = document.createElement("div"); identity.className = "bridge-node-identity";
        const name = document.createElement("strong"); name.textContent = node.pool_name || "RenderBridge 节点";
        const id = document.createElement("code"); id.textContent = node.node_id || "节点 ID 未知";
        identity.append(name, id);
        const state = document.createElement("span");
        state.className = `bridge-node-status is-${statusClass[node.liveness] || "unknown"}`;
        state.textContent = statusText[node.liveness] || "状态未知";
        heading.append(identity, state);

        const meta = document.createElement("p"); meta.className = "bridge-node-meta";
        meta.textContent = `${receiveText[node.node_state] || "接单状态未知"} · ${ageText(node.heartbeat_age_seconds)}`;
        const accountMeta = document.createElement("p"); accountMeta.className = "bridge-node-meta";
        if (node.reward_account_bound === false) accountMeta.textContent = "未绑定 Alchemy 账号";
        else if (node.reward_account_bound === true && Number.isSafeInteger(node.reward_account_user_id)) {
          const historicalImages = safeCount(node.historical_reward_images);
          const historicalPoints = typeof node.historical_reward_points === "string"
            && /^\d+\.\d{2}$/.test(node.historical_reward_points) ? node.historical_reward_points : "0.00";
          accountMeta.textContent = `当前账号 #${node.reward_account_user_id}`
            + (historicalImages > 0 ? ` · 历史归属 ${countText(historicalImages)} 张 / ${historicalPoints} 积分` : "")
            + (node.reward_status === "baseline_pending" ? " · 奖励基线待初始化，暂不能修正" : "");
        }
        else if (node.reward_status === "baseline_pending") accountMeta.textContent = "奖励基线待初始化";
        else accountMeta.textContent = "账号奖励状态暂不可用";
        const current = document.createElement("p"); current.className = "bridge-node-current";
        if (node.current_execution) {
          current.textContent = `当前任务：${labels[node.current_execution.state] || "处理中"}`;
        } else {
          current.textContent = "当前没有执行中的任务";
          current.classList.add("is-idle");
        }

        const stats = document.createElement("div"); stats.className = "bridge-node-stats";
        const nodePoints = node.reward_status === "unbound" && node.reward_account_bound === false
          ? "0.00"
          : node.reward_status === "accruing" && typeof node.reward_points === "string" && /^\d+\.\d{2}$/.test(node.reward_points)
            ? node.reward_points : "—";
        stats.append(createMetric("成功图片", countText(imageCount)));
        stats.append(createMetric("计奖图片", countText(safeCount(node.reward_images))));
        stats.append(createMetric("当前账号积分", nodePoints));
        stats.append(createMetric("失败任务", countText(failedCount)));
        const correction = value.truncated === true ? null : rewardBindingCorrection(node);
        if (correction) correction.querySelector("form").dataset.rewardableImages = String(metrics.rewardable_images ?? "");
        card.append(heading, meta, accountMeta, current, stats);
        if (correction) card.append(correction);
        rewardRows.append(card);
      }
      if (!nodes.length) {
        const empty = document.createElement("div"); empty.className = "bridge-node-empty";
        empty.textContent = "还没有接入的节点。启动节点程序后，状态会显示在这里。";
        rewardRows.append(empty);
      }
      const trackingDate = value.tracking_since ? new Date(value.tracking_since).toLocaleDateString() : "未知日期";
      rewardState.textContent = `统计自 ${trackingDate} · 每 15 秒更新 · 当前 ${new Date().toLocaleTimeString()}${value.truncated ? " · 仅显示部分节点" : ""}`;
    } catch {
      rewardState.textContent = "统计暂不可用";
      const empty = document.createElement("div"); empty.className = "bridge-node-empty";
      empty.textContent = "读取失败，请稍后刷新。"; rewardRows.replaceChildren(empty);
      rewardSummary.querySelectorAll(".bridge-reward-stat strong").forEach((item) => { item.textContent = "—"; });
    }
  }
  function payload(value) {
    return { mode: value.mode, base_url: value.base_url, workspace: value.workspace,
      profiles: value.profiles, native_enabled: value.native_enabled, native_profiles: value.native_profiles,
      auto_fallback_enabled: value.auto_fallback_enabled === true, queue_wait_seconds: value.queue_wait_seconds ?? 30 };
  }
  async function save(body, message) {
    if (busy || !authorized) return;
    busy = true; controls(); status.textContent = "正在保存…";
    try {
      const value = await adminRequest("/v1/admin/render-bridge/settings", { method: "POST", headers: { "X-Alchemy-Bridge-Admin": "1" }, body });
      render(value);
      result.textContent = "设置已改变，请重新检查连接。";
      if (message && !value.configuration_error && !value.native_runtime_error) hint.textContent = message;
    } catch (error) { get("Fallback").checked = saved?.auto_fallback_enabled === true; fail(error); }
    finally { busy = false; controls(); }
  }
  get("Fallback").addEventListener("change", () => {
    if (!saved || busy || !authorized) return;
    save({ ...payload(saved), auto_fallback_enabled: get("Fallback").checked }, "自动云端选项已保存。只影响明确选择此方式的新任务，不会更改已有任务。");
  });
  for (const [mode, button] of Object.entries(actions)) button.addEventListener("click", () => {
    if (!saved || busy) return;
    if (mode !== "disabled" && !ready(saved)) { basicStatus(saved); return; }
    // One click changes only the saved mode, never unsaved advanced tool choices.
    save({ ...payload(saved), mode });
  });
  for (const button of toolButtons) button.addEventListener("click", () => {
    button.setAttribute("aria-pressed", String(button.getAttribute("aria-pressed") !== "true"));
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!saved) return;
    save({ mode: saved.mode, base_url: url.value, workspace: workspace.value,
      profiles: toolButtons.filter((button) => button.getAttribute("aria-pressed") === "true").map((button) => button.dataset.profile),
      auto_fallback_enabled: saved.auto_fallback_enabled === true, queue_wait_seconds: Number(get("QueueWait").value),
      native_enabled: native.checked, native_profiles: Array.from(nativeProfiles.selectedOptions, (option) => option.value) }, "连接设置已保存。需要确认连接时，点击检查连接。");
  });
  get("Probe").addEventListener("click", async () => {
    if (busy || !saved || !authorized) return;
    if (!ready(saved)) { basicStatus(saved); return; }
    if (saved.mode === "disabled") { status.textContent = "已关闭"; hint.textContent = "先点击开启，再检查连接。关闭时不会连接绘图工具。"; return; }
    busy = true; controls(); status.textContent = "正在检查连接…";
    try {
      const value = await adminRequest("/v1/admin/render-bridge/probe", { method: "POST", headers: { "X-Alchemy-Bridge-Admin": "1" } });
      const labels = { not_checked: "未检查", reachable: "可连接", unavailable: "不可连接", accepted: "通过", rejected: "未通过", compatible: "兼容", incompatible: "不兼容", unknown: "未知", offline: "离线", available: "已报告可用", busy: "忙碌", attention: "需要处理" };
      const label = (value) => labels[value] || "未知";
      const lines = [`HTTP 连接：${label(value.connection)}`, `身份验证：${label(value.authentication)}`, `能力协议：${label(value.capabilities)}`, `执行节点：${label(value.node_readiness)}`];
      if (value.admission) lines.push(`Bridge 新任务接收：${value.admission.accepting_new_tasks ? "允许" : "暂停"}`);
      for (const profile of value.profiles || []) lines.push(`${profile.execution_profile_id}：${label(profile.availability)}`);
      lines.push("真实生图尚未验证；检查不会生成图片、配置凭据或授权正式交付。");
      result.textContent = lines.join("\n");
      const selectedEvidence = (saved.profiles || []).map((id) => (value.profiles || []).find((profile) => profile.execution_profile_id === id));
      const toolNeedsAttention = selectedEvidence.some((profile) => profile && ["offline", "attention"].includes(profile.availability));
      const toolEvidenceKnown = selectedEvidence.length > 0 && selectedEvidence.every((profile) => profile && ["available", "busy"].includes(profile.availability));
      if (value.connection !== "reachable" || value.authentication !== "accepted" || value.capabilities !== "compatible") {
        status.textContent = "暂时连接不上"; hint.textContent = "请确认绘图电脑和桥接程序已打开，再试一次。仍不成功时，请找管理员帮忙。";
      } else if (value.node_readiness === "offline") {
        status.textContent = "绘图电脑不在线"; hint.textContent = "请打开绘图电脑上的桥接程序，再点击检查连接。";
      } else if (value.node_readiness === "attention" || toolNeedsAttention) {
        status.textContent = "工具需要处理"; hint.textContent = "请到绘图电脑上查看提示，处理后再检查连接。";
      } else if (!["available", "busy"].includes(value.node_readiness) || !toolEvidenceKnown) {
        status.textContent = "已连接，工具状态待确认"; hint.textContent = "请让管理员确认绘图电脑上的工具已准备好。";
      } else if (saved.mode === "draining" || value.admission?.accepting_new_tasks === false) {
        status.textContent = "已连接，暂停接收新任务"; hint.textContent = saved.mode === "draining" ? "需要接收新任务时，点击开启。" : "请让管理员恢复接收新任务。";
      } else if (value.node_readiness === "busy") {
        status.textContent = "绘图工具正在忙"; hint.textContent = "请稍后再检查。不要为同一任务重复点击生成。";
      } else {
        status.textContent = "已连接，工具在线"; hint.textContent = "连接检查通过，但还没有验证真实图片生成效果。";
      }
    } catch (error) { fail(error); }
    finally { busy = false; controls(); }
  });
  if (rewardRefresh) rewardRefresh.addEventListener("click", refreshRewards);
  rewardRows?.addEventListener("submit", submitRewardBindingCorrection);
  setInterval(() => { if (!document.hidden) refreshRewards(); }, 15000);
  adminRequest("/v1/admin/render-bridge/settings").then((value) => { authorized = true; render(value); controls(); refreshRewards(); }).catch(fail);
}
