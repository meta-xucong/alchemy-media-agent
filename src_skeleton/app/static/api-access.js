/* Access UI only. Existing session storage is read; API secrets are never persisted. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const sessionKey = "alchemy_veyra_access_token";
  const app = $("apiAccessApp"), overview = $("apiAdminOverview");
  if (!app && !overview) return;
  const admin = location.pathname === "/admin/api-access";
  let sessionEpoch = 0;
  let secret = "", offset = 0, query = "", ready = false, creating = false, loading = false, activeCount = 0, revokeTarget = null;
  const messages = {
    api_key_invalid: "密钥已过期、停用或不正确，请创建新密钥。",
    account_login_not_configured: "当前服务尚未启用原账户登录。请联系管理员，不要填写模型供应商密钥。",
    account_inactive: "当前账户已停用，请联系管理员。",
    active_key_limit: "最多同时保留 5 把有效密钥，请先停用不再使用的密钥。",
    invalid_key_name: "名称请保持在 50 个字符以内，不要输入控制字符。",
    same_origin_required: "当前页面来源无法验证，请从 Alchemy 内重新打开。",
    key_service_unavailable: "密钥服务暂不可用，请稍后刷新。",
    session_login_required: "请使用原账户登录后管理密钥。",
    key_not_found: "密钥已不存在或不属于当前账户，请刷新。"
  };
  function session() { try { return localStorage.getItem(sessionKey) || ""; } catch { return ""; } }
  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    const headers = { Accept: "application/json", ...options.headers };
    const token = session();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (options.method && options.method !== "GET") { headers["Content-Type"] = "application/json"; headers["X-Alchemy-UI"] = "api-access"; }
    try {
      const response = await fetch(path, { ...options, headers, signal: controller.signal, credentials: "same-origin", cache: "no-store", redirect: "error" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(payload.detail?.code || payload.detail?.error_code || "request_failed");
        error.status = response.status; error.unknown = response.status >= 500; throw error;
      }
      return payload;
    } catch (error) { if (!error.status) error.unknown = true; throw error; }
    finally { clearTimeout(timeout); }
  }
  function friendly(error) {
    return messages[error.message] || (error.status === 401 ? "登录已失效，请重新登录。" : error.status === 403 ? "当前账户没有管理员权限。" : "暂时无法连接，请检查网络后刷新。");
  }
  function text(tag, value, className) { const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; return node; }
  function date(value) { return value ? new Date(value).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "尚未使用"; }
  function notice(message) { $("accessAlert").textContent = message; $("accessAlert").hidden = !message; }
  function clearSecret() { secret = ""; if ($("newSecret")) $("newSecret").value = ""; if ($("manualCopy")) { $("manualCopy").value = ""; $("manualCopy").hidden = true; } }
  function signedOut(error) {
    sessionEpoch += 1; ready = false; clearSecret(); if ($("secretDialog")?.open) $("secretDialog").close();
    if ($("revokeDialog")?.open) $("revokeDialog").close();
    $("keyList").replaceChildren(text("p", "登录后才能查看密钥。", "access-empty"));
    $("adminSummary").replaceChildren(); $("adminLink").hidden = true;
    $("accountLabel").textContent = error.status === 403 ? "访问受限" : "未登录"; $("loginLink").hidden = error.status !== 401;
    notice(friendly(error)); controls();
  }
  function controls() {
    $("createKeyButton").disabled = !ready || creating || activeCount >= 5;
    $("createKeyButton").textContent = creating ? "创建中…" : activeCount >= 5 ? "已达上限，请先停用" : "创建密钥";
    $("refreshKeys").disabled = !ready || loading;
  }
  function stats(target, summary) {
    target.replaceChildren();
    for (const [key, label] of [["active", "有效密钥"], ["total", "全部密钥"], ["requests", "已认证请求（非生图次数）"]]) {
      const cell = text("div", "", "access-stat"); cell.append(text("strong", Number(summary[key] || 0).toLocaleString()), text("span", label)); target.append(cell);
    }
  }
  function render(payload) {
    activeCount = payload.summary.active;
    const list = $("keyList"); list.replaceChildren();
    if (!payload.items.length) list.append(text("p", query ? "没有找到对应密钥，试试其他名称或账户 ID。" : "还没有密钥。创建一把，就能连接其他工具。", "access-empty"));
    for (const item of payload.items) {
      const row = text("article", "", "access-key"), info = text("div", "", "access-key-info"), title = text("div", "", "access-key-title");
      title.append(text("strong", item.name), text("span", { active: "使用中", revoked: "已停用", expired: "已过期" }[item.status] || "未知", `access-status ${item.status}`));
      info.append(title, text("code", item.masked));
      info.append(text("p", `${admin ? `账户 #${item.owner_id} · ` : ""}创建 ${date(item.created_at)} · 到期 ${date(item.expires_at)}`));
      info.append(text("p", `最近使用：${date(item.last_used_at)} · 已认证请求 ${item.request_count}`));
      const button = text("button", "停用", "access-button secondary"); button.type = "button"; button.disabled = item.status !== "active";
      button.setAttribute("aria-label", `停用 ${item.name}`); button.addEventListener("click", () => openRevoke(item)); row.append(info, button); list.append(row);
    }
    $("keyPagination").hidden = !offset && !payload.has_more;
    $("prevKeys").disabled = offset === 0; $("nextKeys").disabled = !payload.has_more;
    $("pageCount").textContent = `第 ${Math.floor(offset / 20) + 1} 页 · 共 ${payload.total} 把`;
    if (admin) { $("adminSummary").hidden = false; stats($("adminSummary"), payload.summary); }
    controls();
  }
  async function loadKeys() {
    if (loading || !ready) return;
    loading = true; controls();
    const epoch = sessionEpoch;
    try { const result = await request(`/api/access/${admin ? "admin/" : ""}keys?offset=${offset}&q=${encodeURIComponent(query)}`); if (ready && epoch === sessionEpoch) render(result); }
    catch (error) { if (error.status === 401 || error.status === 403) signedOut(error); else { $("keyList").replaceChildren(text("p", "读取失败，未清空您的密钥。请点击刷新重试。", "access-empty")); notice(friendly(error)); } }
    finally { loading = false; controls(); }
  }
  async function createKey(event) {
    event.preventDefault(); if (creating || !ready || activeCount >= 5) return;
    creating = true; controls(); notice("");
    const epoch = sessionEpoch;
    try {
      const payload = await request("/api/access/keys", { method: "POST", body: JSON.stringify({ name: $("keyName").value.trim() || "我的 API" }) });
      if (!ready || epoch !== sessionEpoch) return;
      if (!/^alk_(?:v3|live)_[A-Za-z0-9_-]{43}$/.test(payload.secret || "")) throw new Error("invalid_response");
      secret = payload.secret; $("newSecret").value = secret; $("secretFeedback").textContent = "";
      $("manualCopy").hidden = true; $("secretDialog").showModal(); $("copySecret").focus();
      $("keyName").value = ""; offset = 0; await loadKeys();
    } catch (error) {
      if (error.status === 401) signedOut(error);
      else notice(error.unknown || error.message === "invalid_response" ? "没有收到完整密钥，创建可能已成功。请先刷新列表；如出现新记录，停用它后再新建，不要连续重复点击。" : friendly(error));
    } finally { creating = false; controls(); }
  }
  function openRevoke(item) {
    revokeTarget = item; $("revokeDescription").textContent = `${item.name} · ${item.masked}${admin ? ` · 账户 #${item.owner_id}` : ""}`;
    $("revokeFeedback").textContent = ""; $("confirmRevoke").disabled = false; $("revokeDialog").showModal(); $("cancelRevoke").focus();
  }
  async function revoke() {
    if (!revokeTarget || $("confirmRevoke").disabled) return;
    $("confirmRevoke").disabled = true;
    try {
      await request(`/api/access/${admin ? "admin/" : ""}keys/${encodeURIComponent(revokeTarget.id)}/revoke`, { method: "POST", body: "{}" });
      $("revokeDialog").close(); notice("密钥已停用，新的调用将被拒绝。"); await loadKeys();
    } catch (error) { $("revokeFeedback").textContent = friendly(error) + (error.unknown ? " 请刷新确认是否已停用。" : ""); }
    finally { $("confirmRevoke").disabled = false; }
  }
  function selectForCopy(value) {
    if (!value) return;
    const field = $("manualCopy"); field.value = value; field.hidden = false;
    field.focus(); field.select();
    $("secretFeedback").textContent = "已选中内容。电脑按 Ctrl+C（Mac 按 ⌘C）；手机长按后选择复制。";
  }
  function apiGenerationExample(origin, apiKey) {
    return `// Node.js 18+。运行前请确认这次调用需要真实生图（会按账户规则计费）。
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

// 1. 创建项目
const projectResponse = await call("/api/v3/creative-agent/projects", {
  method: "POST",
  body: JSON.stringify({ user_goal: PROMPT, title: "API 生图示例", primary_template_id: "general_template" })
});
const projectId = projectResponse.project.project_id;
// 2. 提交生图任务
const accepted = await call(
  \`/api/v3/creative-agent/projects/\${projectId}/jobs\`,
  { method: "POST", body: JSON.stringify({
      user_input: PROMPT,
      template_id: "general_template",
      metadata: { require_real_images: true, requested_image_count: 1, requested_image_size: "1024x1024" },
      auto_generate: { quality_mode: "standard", metadata: { require_real_images: true, requested_image_count: 1, requested_image_size: "1024x1024" } }
  }) }
);
console.log("已提交，项目 ID：", projectId, "操作 ID：", accepted.metadata?.current_operation?.operation_id || accepted.job_id);

// 3. 查询任务并拿到导出地址
let jobId = "";
for (;;) {
  const project = await call(
    \`/api/v3/creative-agent/projects/\${projectId}\`,
    { headers: { Authorization: \`Bearer \${API_KEY}\` } }
  );
  jobId = project.project?.job_ids?.at(-1) || "";
  if (jobId) break;
  await wait(5000);
}
for (;;) {
  const job = await call(\`/api/v3/creative-agent/jobs/\${jobId}\`);
  console.log("任务状态：", job.status);
  if (["generated", "failed", "blocked", "cancelled"].includes(job.status)) {
    if (job.status !== "generated") throw new Error(JSON.stringify(job));
    const exported = await call(\`/api/v3/creative-agent/jobs/\${jobId}/export\`);
    const downloadUrl = exported.manifest.generated_assets?.[0]?.download_url;
    console.log("图片下载地址：", new URL(downloadUrl, BASE_URL).href);
    break;
  }
  await wait(5000);
}`;
  }
  async function start() {
    const epoch = sessionEpoch;
    if (overview) {
      try {
        const payload = await request("/api/access/admin/keys");
        const grid = text("div", "", "access-stats"); stats(grid, payload.summary);
        overview.replaceChildren(grid, text("p", "这里只统计已认证的请求，不代表生图数量或费用。"));
      } catch (error) { overview.replaceChildren(text("p", friendly(error))); }
      return;
    }
    if (admin) {
      $("pageTitle").textContent = "API 管理";
      $("pageDescription").textContent = "查看密钥使用情况，停用不再需要的访问。账户和费用仍由原系统管理。";
      $("createPanel").hidden = true; $("usageHelp").hidden = true; $("adminSearch").hidden = false;
      $("listTitle").textContent = "全部账户的密钥";
      $("listHelp").textContent = "仅展示脱敏信息。管理员不能查看完整密钥，也不能代替用户创建密钥。";
      $("adminLink").href = "/admin/billing"; $("adminLink").textContent = "计费与设置";
    }
    $("serviceAddress").value = location.origin;
    try {
      const me = await request("/api/access/me");
      if (epoch !== sessionEpoch) return;
      $("accountLabel").textContent = me.email || `账户 #${me.user_id}`; $("adminLink").hidden = !me.is_admin;
      if (admin && !me.is_admin) { const error = new Error("forbidden"); error.status = 403; throw error; }
      ready = true; controls(); await loadKeys();
    } catch (error) { signedOut(error); }
  }
  if (app) {
    $("createKeyForm").addEventListener("submit", createKey);
    $("refreshKeys").addEventListener("click", () => { notice(""); loadKeys(); });
    $("adminSearch").addEventListener("submit", (event) => { event.preventDefault(); if (loading) return; query = $("keySearch").value.trim(); offset = 0; loadKeys(); });
    $("prevKeys").addEventListener("click", () => { if (loading) return; offset = Math.max(0, offset - 20); loadKeys(); });
    $("nextKeys").addEventListener("click", () => { if (loading) return; offset += 20; loadKeys(); });
    $("closeSecret").addEventListener("click", () => { clearSecret(); $("secretDialog").close(); });
    $("secretDialog").addEventListener("cancel", clearSecret);
    $("secretDialog").addEventListener("close", clearSecret);
    $("cancelRevoke").addEventListener("click", () => $("revokeDialog").close());
    $("revokeDialog").addEventListener("close", () => { revokeTarget = null; });
    $("confirmRevoke").addEventListener("click", revoke);
    $("copySecret").addEventListener("click", () => selectForCopy(secret));
    $("copyApi").addEventListener("click", () => { if (secret) selectForCopy(apiGenerationExample(location.origin, secret)); });
    $("copyMcp").addEventListener("click", () => { if (secret) selectForCopy(JSON.stringify({ env: { ALCHEMY_PRODUCT_API_BASE_URL: location.origin, ALCHEMY_PRODUCT_SESSION_TOKEN: secret } }, null, 2)); });
    $("copyAddress").addEventListener("click", () => { $("serviceAddress").focus(); $("serviceAddress").select(); notice("地址已选中，请使用系统复制操作。"); });
    window.addEventListener("pagehide", () => { sessionEpoch += 1; ready = false; clearSecret(); if ($("secretDialog").open) $("secretDialog").close(); });
    window.addEventListener("pageshow", (event) => { if (event.persisted) start(); });
    window.addEventListener("storage", (event) => { if (event.key === sessionKey || event.key === null) { const error = new Error("session_login_required"); error.status = 401; signedOut(error); } });
  }
  start();
})();
