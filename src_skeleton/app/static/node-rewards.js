/* Account-bound RenderBridge node rewards. */
(() => {
  "use strict";

  const root = document.querySelector("[data-node-rewards]");
  if (!root) return;

  const sessionKey = "alchemy_veyra_access_token";
  const state = { loading: false, binding: false, epoch: 0 };
  const $ = (selector) => root.querySelector(selector);
  const labels = {
    session_login_required: "请先登录 Alchemy 账户。",
    veyra_session_required: "请先登录 Alchemy 账户。",
    account_login_not_configured: "当前服务暂未启用 Alchemy 账户登录。",
    account_inactive: "当前 Alchemy 账户不可用。",
    node_reward_metrics_unavailable: "节点奖励统计服务暂不可用，请稍后刷新。",
    node_reward_image_count_unavailable: "Bridge 暂未提供真实图片计数，当前不会计算奖励。",
    node_reward_history_unavailable: "暂时无法读取已绑定节点的记录，请稍后刷新。",
    node_reward_storage_unavailable: "节点绑定信息暂时无法读取，请稍后重试。",
    node_reward_metrics_incomplete: "Bridge 节点列表未完整返回，暂时无法验证该节点。",
    node_not_registered: "Bridge 中没有找到此节点，请确认节点已完成注册并联网。",
    node_identity_ambiguous: "节点 ID 重复，暂时无法唯一确认。请联系管理员。",
    node_revoked: "这台节点已停用，无法绑定奖励。",
    node_not_active: "这台节点当前不可用，暂时无法绑定奖励。",
    node_already_bound: "这台节点已绑定到其他 Alchemy 账户。",
    same_origin_required: "页面来源校验失败，请从 Alchemy 账户中心重新操作。",
  };

  function readToken() {
    try {
      return localStorage.getItem(sessionKey) || "";
    } catch {
      return "";
    }
  }

  function errorFor(code, status = 0) {
    const error = new Error(code || "request_failed");
    error.status = status;
    return error;
  }

  async function request(path, options = {}) {
    const method = options.method || "GET";
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    const headers = { Accept: "application/json" };
    const token = readToken();
    if (token) headers.Authorization = "Bearer " + token;
    if (method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-Alchemy-UI"] = "node-rewards";
    }
    try {
      const response = await fetch(path, {
        method,
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail || {};
        throw errorFor(detail.code || detail.error_code || "request_failed", response.status);
      }
      return payload;
    } catch (error) {
      if (!error.status && error.name !== "AbortError") error.unknown = true;
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function friendly(error) {
    if (labels[error && error.message]) return labels[error.message];
    if (error && error.status === 401) return "登录已失效，请重新登录后查看节点奖励。";
    if (error && error.status === 403) return "当前账户无权执行此操作。";
    if (error && error.name === "AbortError") return "节点奖励服务响应超时，请稍后刷新。";
    if (error && error.unknown) return "无法连接节点奖励服务，请检查网络后重试。";
    return "节点奖励暂时无法读取，请稍后刷新。";
  }

  function showNotice(message) {
    const notice = $("#nodeRewardsNotice");
    if (!notice) return;
    notice.textContent = message || "";
    notice.hidden = !message;
  }

  function setState(value) {
    const node = $("#nodeRewardsState");
    if (node) node.textContent = value;
  }

  function text(tag, value, className = "") {
    const node = document.createElement(tag);
    node.textContent = value == null ? "" : String(value);
    if (className) node.className = className;
    return node;
  }

  function date(value) {
    if (!value) return "暂无";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? "暂无"
      : parsed.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  function unavailable(message) {
    setState(message && message.includes("登录") ? "未登录" : "暂不可用");
    $("#nodeRewardsNodeCount").textContent = "-";
    $("#nodeRewardsImageCount").textContent = "-";
    $("#nodeRewardsPoints").textContent = "-";
    $("#nodeRewardsTrackingSince").textContent = "奖励统计暂不可用";
    const list = $("#nodeRewardsNodeList");
    if (list) list.replaceChildren(text("p", message || "节点奖励暂不可用。", "account-access-empty"));
    showNotice(message || "");
  }

  function renderNode(item) {
    const row = text("article", "", "node-rewards-node");
    const heading = text("div", "", "node-rewards-node-heading");
    const title = text("strong", item.pool_name || item.node_id || "共享节点");
    const livenessLabels = { online: "在线", busy: "运行中", needs_attention: "需要检查", offline: "离线" };
    const stateLabels = { active: "已启用", draining: "暂停接单", revoked: "已停用" };
    const stateLabel = item.binding_status === "corrected"
      ? "归属已修正"
      : livenessLabels[item.liveness] || stateLabels[item.node_state] || "状态未知";
    heading.append(title, text("span", stateLabel, "node-rewards-status"));
    row.append(heading);
    row.append(text("p", "节点 ID：" + (item.node_id || "-"), "node-rewards-identity"));

    const stats = text("div", "", "node-rewards-node-stats");
    stats.append(
      text("span", "成功图片 " + Number(item.successful_images || 0).toLocaleString("zh-CN")),
      text("strong", item.reward_points + " 积分"),
      text("small", item.binding_status === "corrected"
        ? "归属修正于：" + date(item.corrected_at)
        : "最近在线：" + date(item.last_seen_at)),
      text("small", "绑定于：" + date(item.bound_at)),
    );
    row.append(stats);

    if (item.current_execution && item.current_execution.state) {
      const executionLabels = {
        running: "正在生成",
        uploading: "正在回传图片",
        awaiting_user: "等待人工操作",
        execution_unknown: "执行状态待确认",
      };
      row.append(text("p", "当前任务：" + (executionLabels[item.current_execution.state] || "处理中"),
                      "node-rewards-execution"));
    }
    return row;
  }

  function render(payload) {
    if (!payload || payload.available !== true) {
      unavailable(labels[payload && payload.code] || "节点奖励数据暂不可用，请稍后刷新。");
      return;
    }

    const totals = payload.totals || {};
    setState("已接入");
    $("#nodeRewardsNodeCount").textContent = Number(totals.bound_nodes || 0).toLocaleString("zh-CN");
    $("#nodeRewardsImageCount").textContent = Number(totals.successful_images || 0).toLocaleString("zh-CN");
    $("#nodeRewardsPoints").textContent = String(totals.reward_points || "0.00");
    $("#nodeRewardsTrackingSince").textContent = payload.tracking_since
      ? "统计开始于 " + date(payload.tracking_since)
      : "尚无奖励记录";
    showNotice("");

    const list = $("#nodeRewardsNodeList");
    if (!list) return;
    list.replaceChildren();
    const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
    if (!nodes.length) {
      list.append(text("p", "还没有绑定节点。登录 Alchemy 后，输入本机状态页显示的节点 ID 即可绑定。",
                      "account-access-empty"));
      return;
    }
    nodes.forEach((item) => list.append(renderNode(item)));
  }

  async function load() {
    if (state.loading) return;
    state.loading = true;
    const epoch = ++state.epoch;
    setState("读取中");
    const refresh = $("#nodeRewardsRefreshBtn");
    if (refresh) refresh.disabled = true;
    try {
      const payload = await request("/api/account/node-rewards");
      if (epoch === state.epoch) render(payload);
    } catch (error) {
      if (epoch === state.epoch) unavailable(friendly(error));
    } finally {
      state.loading = false;
      if (refresh) refresh.disabled = false;
    }
  }

  async function bindNode() {
    if (state.binding) return;
    const input = $("#nodeRewardsNodeIdInput");
    const nodeId = input ? input.value.trim() : "";
    if (!nodeId) {
      showNotice("请输入节点状态页显示的节点 ID。");
      input?.focus();
      return;
    }
    state.binding = true;
    const button = $("#nodeRewardsBindNodeBtn");
    if (button) {
      button.disabled = true;
      button.textContent = "正在绑定…";
    }
    showNotice("");
    try {
      await request("/api/account/node-rewards/bindings", {
        method: "POST",
        body: { node_id: nodeId },
      });
      if (input) input.value = "";
      showNotice("节点已绑定到当前 Alchemy 账户。");
      await load();
    } catch (error) {
      showNotice(friendly(error));
    } finally {
      state.binding = false;
      if (button) {
        button.disabled = false;
        button.textContent = "绑定此节点";
      }
    }
  }

  $("#nodeRewardsBindForm")?.addEventListener("submit", (event) => { event.preventDefault(); bindNode(); });
  $("#nodeRewardsNodeIdInput")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      bindNode();
    }
  });
  $("#nodeRewardsRefreshBtn")?.addEventListener("click", load);
  document.addEventListener("alchemy:account-view", (event) => {
    if (event.detail && event.detail.view === "node-rewards") load();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === sessionKey || event.key === null) {
      state.epoch += 1;
      unavailable("请先登录 Alchemy 账户。");
    }
  });
  window.addEventListener("pagehide", () => {
    state.epoch += 1;
  });
})();
