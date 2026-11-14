/* Account-bound RenderBridge node rewards. */
(() => {
  "use strict";

  const root = document.querySelector("[data-node-rewards]");
  if (!root) return;

  const sessionKey = "alchemy_veyra_access_token";
  const state = { loading: false, binding: false, epoch: 0, challenge: "",
                  claimEpoch: 0, pollTimer: null };
  const CLAIM_POLL_MS = 5000;
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
    node_reward_claim_unverified: "正在等待目标节点确认；确认后会自动绑定。",
    node_reward_claim_invalid: "绑定码无效或已使用，请重新创建。",
    node_reward_claim_expired: "绑定码已过期，请重新创建。",
    node_reward_claim_mismatch: "Bridge 返回的节点证明无效，请重新创建绑定码。",

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

  function setChallenge(value) {
    const next = value || "";
    if (state.challenge !== next) {
      state.challenge = next;
      state.claimEpoch += 1;
      if (state.pollTimer) window.clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
    const row = $("#nodeRewardsClaimRow");
    const code = $("#nodeRewardsClaimCode");
    const create = $("#nodeRewardsBindNodeBtn");
    if (row) row.hidden = !state.challenge;
    if (code) code.textContent = state.challenge;
    if (create) {
      create.disabled = state.binding || Boolean(state.challenge);
      create.textContent = state.challenge ? "等待节点确认…" : "创建绑定码";
    }
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
      list.append(text("p", "还没有绑定节点。先创建绑定码，在目标机器的本地状态页确认；每台机器分别创建一次。",
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

  async function createBindingClaim() {
    if (state.binding || state.challenge) return;
    state.binding = true;
    const button = $("#nodeRewardsBindNodeBtn");
    if (button) {
      button.disabled = true;
      button.textContent = "正在创建…";
    }
    setChallenge("");
    showNotice("");
    try {
      const result = await request("/api/account/node-rewards/claims", {
        method: "POST",
        body: {},
      });
      if (!result || result.status !== "challenge_created"
          || typeof result.challenge !== "string"
          || !/^[A-Za-z0-9_-]{43}$/.test(result.challenge)) {
        throw errorFor("node_reward_claim_verification_unavailable", 503);
      }
      setChallenge(result.challenge);
      showNotice("绑定码已创建。请在目标机器的 RenderBridge 本地状态页输入并确认；确认后本页会自动完成绑定。");
      scheduleBindingPoll(state.claimEpoch, 1200);
    } catch (error) {
      showNotice(friendly(error));
    } finally {
      state.binding = false;
      if (button) {
        button.disabled = Boolean(state.challenge);
        button.textContent = state.challenge ? "等待节点确认…" : "创建绑定码";
      }
    }
  }

  function scheduleBindingPoll(epoch, delay = CLAIM_POLL_MS) {
    if (!state.challenge || epoch !== state.claimEpoch || state.pollTimer) return;
    state.pollTimer = window.setTimeout(() => {
      state.pollTimer = null;
      pollBinding(epoch);
    }, delay);
  }

  async function pollBinding(epoch) {
    if (state.binding || !state.challenge || epoch !== state.claimEpoch) return;
    state.binding = true;
    try {
      const result = await request("/api/account/node-rewards/bindings", {
        method: "POST",
        body: { challenge: state.challenge },
      });
      if (epoch !== state.claimEpoch || !state.challenge) return;
      if (!result || !["bound", "already_bound"].includes(result.status)
          || typeof result.node_id !== "string") {
        throw errorFor("node_reward_claim_unverified", 503);
      }
      const message = result.status === "already_bound"
        ? "此节点已绑定到当前 Alchemy 账户。"
        : "节点 " + result.node_id + " 已绑定到当前 Alchemy 账户。";
      setChallenge("");
      await load();
      showNotice(message);
    } catch (error) {
      if (epoch !== state.claimEpoch || !state.challenge) return;
      const terminal = [
        "node_reward_claim_invalid", "node_reward_claim_expired",
        "node_reward_claim_mismatch", "node_already_bound",
        "node_revoked", "node_not_active",
      ];
      if (terminal.includes(error && error.message)) {
        setChallenge("");
        showNotice(friendly(error));
        return;
      }
      showNotice(error && error.message === "node_reward_claim_unverified"
        ? "等待目标节点在本地确认；确认后会自动完成绑定。"
        : friendly(error));
      scheduleBindingPoll(epoch, CLAIM_POLL_MS);
    } finally {
      state.binding = false;
      const create = $("#nodeRewardsBindNodeBtn");
      if (create) {
        create.disabled = Boolean(state.challenge);
        create.textContent = state.challenge ? "等待节点确认…" : "创建绑定码";
      }
    }
  }

  async function copyChallenge() {
    if (!state.challenge) return;
    try {
      await navigator.clipboard.writeText(state.challenge);
      showNotice("绑定码已复制。请只在目标节点本地状态页中确认。");
    } catch {
      showNotice("无法自动复制，请手动选中绑定码复制到目标节点本地状态页。");
    }
  }

  $("#nodeRewardsBindForm")?.addEventListener("submit", (event) => { event.preventDefault(); createBindingClaim(); });
  $("#nodeRewardsCopyClaimBtn")?.addEventListener("click", copyChallenge);
  $("#nodeRewardsRefreshBtn")?.addEventListener("click", load);
  document.addEventListener("alchemy:account-view", (event) => {
    if (event.detail && event.detail.view === "node-rewards") load();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === sessionKey || event.key === null) {
      state.epoch += 1;
      setChallenge("");
      unavailable("请先登录 Alchemy 账户。");
    }
  });
  window.addEventListener("pagehide", () => {
    state.epoch += 1;
    state.claimEpoch += 1;
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
  });
})();
