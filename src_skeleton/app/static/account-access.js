/* Shared account-center API/MCP access panel. API secrets never enter storage or the DOM after the dialog closes. */
(() => {
  "use strict";

  const root = document.querySelector("[data-account-access]");
  if (!root) return;

  const sessionKey = "alchemy_veyra_access_token";
  const secretPattern = /^alk_(?:v3|live)_[A-Za-z0-9_-]{43}$/;
  const state = {
    ready: false,
    creating: false,
    loading: false,
    activeCount: 0,
    secret: "",
    revokeTarget: null,
    epoch: 0,
  };
  const messages = {
    api_key_invalid: "密钥已过期、停用或不正确，请创建新密钥。",
    account_login_not_configured: "当前服务尚未启用原账户登录，请联系管理员。",
    account_inactive: "当前账户已停用，请联系管理员。",
    active_key_limit: "最多同时保留 5 把有效密钥，请先停用不再使用的密钥。",
    invalid_key_name: "名称请保持在 50 个字符以内，不要输入控制字符。",
    same_origin_required: "当前页面来源无法验证，请从 Alchemy 内重新打开。",
    key_service_unavailable: "密钥服务暂不可用，请稍后刷新。",
    session_login_required: "请先登录 Alchemy 账户。",
    key_not_found: "密钥已不存在或不属于当前账户，请刷新。",
  };

  const $ = (selector) => root.querySelector(selector) || document.querySelector(selector);
  const accountShell = () => root.closest(".account-center-dialog, .mobile-view") || document;

  function readToken() {
    try {
      return localStorage.getItem(sessionKey) || "";
    } catch {
      return "";
    }
  }

  function errorWithCode(code, status = 0) {
    const error = new Error(code);
    error.status = status;
    return error;
  }

  async function request(path, options = {}) {
    const token = readToken();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    headers.Authorization = `Bearer ${token}`;
    if (options.method && options.method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-Alchemy-UI"] = "api-access";
    }
    try {
      const response = await fetch(path, {
        method: options.method || "GET",
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const code = payload.detail?.code || payload.detail?.error_code || "request_failed";
        throw errorWithCode(code, response.status);
      }
      return payload;
    } catch (error) {
      if (!error.status) error.unknown = true;
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function friendly(error) {
    return messages[error?.message] || (error?.status === 401 ? "登录已失效，请重新登录。" : error?.status === 403 ? "当前账户无权执行此操作。" : "暂时无法连接，请刷新后重试。");
  }

  function text(tag, value, className = "") {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  }

  function date(value) {
    if (!value) return "尚未使用";
    return new Date(value).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  function showNotice(message = "") {
    const notice = $("#accountAccessNotice");
    if (!notice) return;
    notice.textContent = message;
    notice.hidden = !message;
  }

  function setStateLabel(value) {
    const node = $("#accountAccessState");
    if (node) node.textContent = value;
  }

  function clearSecret() {
    state.secret = "";
    const input = $("#accountAccessSecretInput");
    const manual = $("#accountAccessManualCopy");
    if (input) input.value = "";
    if (manual) {
      manual.value = "";
      manual.hidden = true;
    }
    const feedback = $("#accountAccessSecretFeedback");
    if (feedback) feedback.textContent = "";
  }

  function setControls() {
    const create = $("#accountAccessCreateBtn");
    const refresh = $("#accountAccessRefreshBtn");
    if (create) {
      create.disabled = !state.ready || state.creating || state.activeCount >= 5;
      create.textContent = state.creating ? "创建中…" : state.activeCount >= 5 ? "已达上限，请先停用" : "创建密钥";
    }
    if (refresh) refresh.disabled = !state.ready || state.loading;
  }

  function renderSignedOut(error = null) {
    state.ready = false;
    state.activeCount = 0;
    const connectionFailed = Boolean(error?.unknown && !error?.status);
    setStateLabel(connectionFailed ? "连接失败" : error?.status === 403 ? "访问受限" : "未登录");
    const list = $("#accountAccessKeyList");
    if (list) list.replaceChildren(text("p", connectionFailed ? "账户信息暂时无法读取，请刷新后重试。" : "登录后才能查看和创建 API 密钥。", "account-access-empty"));
    showNotice(error ? friendly(error) : "请先登录 Alchemy 账户，再管理 API 和 MCP。");
    setControls();
  }

  function renderKeys(payload) {
    state.activeCount = Number(payload?.summary?.active || 0);
    const list = $("#accountAccessKeyList");
    if (!list) return;
    list.replaceChildren();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    if (!items.length) {
      list.append(text("p", "还没有 API 密钥。创建一把，就能连接脚本或 Codex。", "account-access-empty"));
    }
    const statusLabels = { active: "使用中", revoked: "已停用", expired: "已过期" };
    for (const item of items) {
      const row = text("article", "", "account-access-key-row");
      const info = text("div", "", "account-access-key-info");
      const title = text("div", "", "account-access-key-title");
      title.append(text("strong", item.name || "我的 API"), text("span", statusLabels[item.status] || "未知", `access-status ${item.status || ""}`));
      info.append(title, text("code", item.masked || "alk_…"));
      info.append(text("p", `创建 ${date(item.created_at)} · 到期 ${date(item.expires_at)}`));
      info.append(text("p", `最近使用：${date(item.last_used_at)} · 已认证请求 ${Number(item.request_count || 0).toLocaleString()}`));
      const revoke = text("button", "停用", "button compact secondary");
      revoke.type = "button";
      revoke.disabled = item.status !== "active";
      revoke.setAttribute("aria-label", `停用 ${item.name || "API 密钥"}`);
      revoke.addEventListener("click", () => openRevoke(item));
      row.append(info, revoke);
      list.append(row);
    }
    setControls();
  }

  async function loadKeys({ showErrors = true } = {}) {
    if (state.loading || !state.ready) return;
    state.loading = true;
    setControls();
    const epoch = state.epoch;
    try {
      const payload = await request("/api/access/keys?offset=0&q=");
      if (state.ready && epoch === state.epoch) {
        renderKeys(payload);
        if (showErrors) showNotice("");
      }
    } catch (error) {
      if (error.status === 401 || error.status === 403) renderSignedOut(error);
      else if (showErrors) showNotice(`${friendly(error)} 未清空已有密钥，请刷新重试。`);
    } finally {
      state.loading = false;
      setControls();
    }
  }

  async function refresh() {
    state.epoch += 1;
    clearSecret();
    if ($("#accountAccessSecretDialog")?.open) $("#accountAccessSecretDialog").close();
    try {
      await request("/api/access/me");
      state.ready = true;
      setStateLabel("已接入");
      showNotice("");
      setControls();
      await loadKeys({ showErrors: true });
    } catch (error) {
      renderSignedOut(error);
    }
  }

  function selectForCopy(value, message = "已选中内容。电脑按 Ctrl+C（Mac 按 ⌘C）；手机长按后选择复制。") {
    if (!value) return;
    const manual = $("#accountAccessManualCopy");
    const feedback = $("#accountAccessSecretFeedback");
    if (!manual) return;
    manual.value = value;
    manual.hidden = false;
    manual.focus();
    manual.select();
    if (feedback) feedback.textContent = message;
  }

  function apiGenerationExample(origin, apiKey) {
    return `// Node.js 18+。本示例会创建项目、提交一次真实生图并轮询结果。
const BASE_URL = ${JSON.stringify(origin)};
const API_KEY = ${JSON.stringify(apiKey)};
const PROMPT = "A clean studio product image of a red apple on a white ceramic plate";
const headers = { Authorization: \`Bearer \${API_KEY}\`, "Content-Type": "application/json" };
async function call(path, options = {}) {
  const response = await fetch(BASE_URL + path, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  return data;
}
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const projectResponse = await call("/api/v3/creative-agent/projects", { method: "POST", body: JSON.stringify({ user_goal: PROMPT, title: "API 生图示例", primary_template_id: "general_template" }) });
const projectId = projectResponse.project.project_id;
await call(\`/api/v3/creative-agent/projects/\${projectId}/jobs\`, { method: "POST", body: JSON.stringify({ user_input: PROMPT, template_id: "general_template", metadata: { require_real_images: true, requested_image_count: 1, requested_image_size: "1024x1024" }, auto_generate: { quality_mode: "standard", metadata: { require_real_images: true, requested_image_count: 1, requested_image_size: "1024x1024" } } }) });
for (;;) { const project = await call(\`/api/v3/creative-agent/projects/\${projectId}\`); const jobId = project.project?.job_ids?.at(-1); if (!jobId) { await wait(5000); continue; } for (;;) { const job = await call(\`/api/v3/creative-agent/jobs/\${jobId}\`); if (["generated", "failed", "blocked", "cancelled"].includes(job.status)) { if (job.status !== "generated") throw new Error(JSON.stringify(job)); const exported = await call(\`/api/v3/creative-agent/jobs/\${jobId}/export\`); console.log(new URL(exported.manifest.generated_assets?.[0]?.download_url, BASE_URL).href); break; } await wait(5000); } break; }`;
  }

  function mcpConfig(origin, apiKey) {
    return JSON.stringify({ env: { ALCHEMY_PRODUCT_API_BASE_URL: origin, ALCHEMY_PRODUCT_SESSION_TOKEN: apiKey } }, null, 2);
  }

  async function createKey(event) {
    event.preventDefault();
    if (state.creating || !state.ready || state.activeCount >= 5) return;
    state.creating = true;
    setControls();
    showNotice("");
    const epoch = state.epoch;
    try {
      const name = $("#accountAccessKeyName")?.value.trim() || "我的 API";
      const payload = await request("/api/access/keys", { method: "POST", body: { name } });
      if (epoch !== state.epoch || !secretPattern.test(payload?.secret || "")) throw new Error("invalid_response");
      state.secret = payload.secret;
      $("#accountAccessSecretInput").value = state.secret;
      $("#accountAccessKeyName").value = "";
      $("#accountAccessSecretDialog").showModal();
      await loadKeys({ showErrors: false });
    } catch (error) {
      if (error.status === 401 || error.status === 403) renderSignedOut(error);
      else showNotice(error.unknown || error.message === "invalid_response" ? "没有收到完整密钥，创建可能已成功。请先刷新列表确认，不要连续重复点击。" : friendly(error));
    } finally {
      state.creating = false;
      setControls();
    }
  }

  function openRevoke(item) {
    state.revokeTarget = item;
    $("#accountAccessRevokeDescription").textContent = `${item.name || "我的 API"} · ${item.masked || "alk_…"}`;
    $("#accountAccessRevokeFeedback").textContent = "";
    $("#accountAccessConfirmRevoke").disabled = false;
    $("#accountAccessRevokeDialog").showModal();
  }

  async function revoke() {
    if (!state.revokeTarget) return;
    const button = $("#accountAccessConfirmRevoke");
    if (button.disabled) return;
    button.disabled = true;
    try {
      await request(`/api/access/keys/${encodeURIComponent(state.revokeTarget.id)}/revoke`, { method: "POST", body: {} });
      $("#accountAccessRevokeDialog").close();
      showNotice("密钥已停用，新的 API/MCP 请求将被拒绝。");
      await loadKeys({ showErrors: true });
    } catch (error) {
      $("#accountAccessRevokeFeedback").textContent = friendly(error) + (error.unknown ? " 请刷新确认状态。" : "");
    } finally {
      button.disabled = false;
    }
  }

  function setView(view = "overview") {
    const shell = accountShell();
    shell.querySelectorAll("[data-account-view]").forEach((panel) => {
      panel.hidden = panel.dataset.accountView !== view;
    });
    shell.querySelectorAll("[data-account-view-target]").forEach((button) => {
      const active = button.dataset.accountViewTarget === view;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    if (view === "access") refresh();
  }

  function bind() {
    const serviceAddress = $("#accountAccessServiceAddress");
    if (serviceAddress) serviceAddress.value = location.origin;
    $("#accountAccessKeyForm")?.addEventListener("submit", createKey);
    $("#accountAccessRefreshBtn")?.addEventListener("click", () => refresh());
    $("#accountAccessConfirmRevoke")?.addEventListener("click", revoke);
    document.querySelectorAll("[data-account-access-close-secret]").forEach((button) => button.addEventListener("click", () => { clearSecret(); $("#accountAccessSecretDialog")?.close(); }));
    document.querySelectorAll("[data-account-access-cancel-revoke]").forEach((button) => button.addEventListener("click", () => $("#accountAccessRevokeDialog")?.close()));
    $("#accountAccessSecretDialog")?.addEventListener("cancel", clearSecret);
    $("#accountAccessSecretDialog")?.addEventListener("close", clearSecret);
    $("#accountAccessRevokeDialog")?.addEventListener("close", () => { state.revokeTarget = null; });
    $("[data-account-access-copy-secret]")?.addEventListener("click", () => selectForCopy(state.secret));
    $("[data-account-access-copy-api]")?.addEventListener("click", () => selectForCopy(apiGenerationExample(location.origin, state.secret)));
    $("[data-account-access-copy-mcp]")?.addEventListener("click", () => selectForCopy(mcpConfig(location.origin, state.secret)));
    $("[data-account-access-copy-address]")?.addEventListener("click", () => selectForCopy(location.origin, "已选中服务地址。电脑按 Ctrl+C（Mac 按 ⌘C）；手机长按后选择复制。"));
    document.addEventListener("click", (event) => {
      const viewButton = event.target.closest("[data-account-view-target]");
      if (viewButton && accountShell().contains(viewButton)) {
        event.preventDefault();
        setView(viewButton.dataset.accountViewTarget || "overview");
      }
      const opener = event.target.closest("[data-account-open]");
      if (opener) {
        event.preventDefault();
        if (typeof window.openAccountCenter === "function") window.openAccountCenter(opener.dataset.accountOpen || "overview");
        else if (opener.dataset.mobileOpen === "account") window.setTimeout(() => setView(opener.dataset.accountOpen || "overview"), 0);
      }
    });
    window.addEventListener("pagehide", () => { state.epoch += 1; clearSecret(); if ($("#accountAccessSecretDialog")?.open) $("#accountAccessSecretDialog").close(); });
    window.addEventListener("storage", (event) => { if (event.key === sessionKey || event.key === null) renderSignedOut(errorWithCode("session_login_required", 401)); });
  }

  bind();
  window.AlchemyAccountAccess = { refresh, setView };
})();
