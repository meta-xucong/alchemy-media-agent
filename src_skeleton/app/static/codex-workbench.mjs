import { caseThumbnail, createPayload, initialDraft, labPath, projectRun, ratios, runPath, updateDraft, v2CreatePath } from "./codex-workbench-state.mjs";

const el = (id) => document.getElementById(id);
const modeButtons = [...document.querySelectorAll("[data-product]")];
const labSamples = new Map([["M001", "chrome"], ["M002", "copper"], ["M003", "lacquer"]]);
const caseNames = new Map();
let styles = new Map();
let limits = { maxSelectedStyles: 8, maxImagesPerStyle: 4, maxTotalImages: 24 };
let draft = initialDraft();
let catalog = [];
let labCatalog = null;
let catalogSequence = 0;
let nextCursor = null;
let nextLocalPage = [];
let busy = false;
let run = null;
let uncertain = null;
let authEpoch = 0;
const resultCards = new Map();
const pageSize = 12;

function fromApiError(status) {
  const message = status === 401 ? "请登录 Alchemy。" : status === 403 ? "当前账号没有访问权限。"
    : status === 429 || status === 503 ? "服务繁忙，请稍后再试。" : "Alchemy 请求失败（" + status + "）。";
  return Object.assign(new Error(message), { status });
}

async function api(path, { body, headers = {} } = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json", ...headers } : headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(18000),
  });
  if (!response.ok) {
    if (response.status === 401) el("login").hidden = false;
    throw fromApiError(response.status);
  }
  return response.json();
}

function setDraft(patch) {
  const input = {};
  for (const key of Object.keys(initialDraft())) if (Object.hasOwn(patch, key)) input[key] = patch[key];
  const changedProduct = input.product && input.product !== draft.product;
  draft = updateDraft(draft, input, styles, limits);
  renderDraft();
  if (changedProduct) {
    el("query").value = "";
    reload();
  }
  return snapshot();
}

function snapshot() {
  return { ...draft, style_ids: [...draft.style_ids], case_title: caseNames.get(draft.case_id) || null,
    style_names: draft.style_ids.map((id) => styles.get(id)?.display_name),
    quantity: draft.product === "lab" ? draft.style_ids.length * draft.per_style : draft.count };
}

function renderDraft() {
  const lab = draft.product === "lab";
  for (const button of modeButtons) button.setAttribute("aria-pressed", String(button.dataset.product === draft.product));
  el("library-title").textContent = lab ? "风格目录" : "案例库";
  const selectedNames = lab ? snapshot().style_names : [caseNames.get(draft.case_id)].filter(Boolean);
  el("selected").textContent = selectedNames.length ? "已选 · " + selectedNames.join("、") : lab ? "请从风格目录点选。" : "自动选案例，或从左侧手动指定。";
  if (el("prompt").value !== draft.prompt) el("prompt").value = draft.prompt;
  el("ratio").value = draft.ratio;
  el("count").max = lab ? limits.maxImagesPerStyle : 8;
  el("count").value = lab ? draft.per_style : draft.count;
  el("count-label").textContent = lab ? "每种张数" : "张数";
  el("total").textContent = "共 " + snapshot().quantity + " 张";
  el("generate").disabled = busy || Boolean(uncertain);
  for (const button of el("catalog").querySelectorAll("[data-id]")) {
    button.setAttribute("aria-pressed", String(lab ? draft.style_ids.includes(button.dataset.id) : button.dataset.id === draft.case_id));
  }
}

async function loadLabCatalog() {
  if (!labCatalog) labCatalog = api(labPath + "/styles").then((payload) => {
    styles = new Map((payload.styles || []).map((style) => [style.id, style]));
    limits = { ...limits, ...payload.limits };
    return [...styles.values()];
  }).catch((error) => { labCatalog = null; throw error; });
  return labCatalog;
}

async function loadCatalog({ append = false } = {}) {
  const sequence = ++catalogSequence;
  const product = draft.product;
  const query = el("query").value.trim();
  if (!append) { catalog = []; nextCursor = null; nextLocalPage = []; renderCatalog(); }
  el("more").disabled = true;
  el("catalog-notice").textContent = "正在读取目录…";
  try {
    let items, cursor = null, remaining = [];
    if (product === "lab") {
      const all = await loadLabCatalog();
      const term = query.toLowerCase();
      const filtered = append ? nextLocalPage : all.filter((item) =>
        [item.id, item.display_name, item.short_description, item.family, ...(item.tags || [])].join(" ").toLowerCase().includes(term));
      items = filtered.slice(0, pageSize);
      remaining = filtered.slice(pageSize);
    } else if (query) {
      const result = await api("/api/v2/prompt-cases/search", { body: { query_text: query, limit: 24 } });
      items = result.cases || [];
    } else {
      const params = new URLSearchParams({ limit: String(pageSize) });
      if (append && nextCursor != null) params.set("cursor", nextCursor);
      const result = await api("/api/v2/templates/page?" + params);
      items = result.items || [];
      cursor = result.next_cursor ?? null;
    }
    if (sequence !== catalogSequence) return [];
    catalog = [...catalog, ...items.map((item) => {
      if (product === "lab") {
        const sample = labSamples.get(item.id);
        return { id: item.id, title: item.display_name, description: item.short_description || "", sample,
          image: sample ? "/static/codex-lab-" + sample + "-v1.jpg" : "" };
      }
      caseNames.set(item.case_id, item.title);
      return { id: item.case_id, title: item.title, description: item.category, image: caseThumbnail(item.preview_url) };
    })];
    nextCursor = cursor;
    nextLocalPage = remaining;
    el("login").hidden = true;
    el("catalog-notice").textContent = catalog.length ? "" : "未找到匹配结果。";
    renderCatalog();
    return catalog.slice(0, 24);
  } catch (error) {
    if (sequence !== catalogSequence) return [];
    el("catalog-notice").textContent = "目录读取失败。 " + error.message;
    throw error;
  } finally {
    if (sequence === catalogSequence) el("more").disabled = false;
  }
}

function make(tag, text = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

function addImageOrPlaceholder(parent, item) {
  const placeholder = make("span", "暂无样张");
  placeholder.className = "placeholder";
  if (!item.image) { parent.append(placeholder); return; }
  const img = make("img");
  img.alt = item.title;
  img.loading = "lazy";
  if (item.sample) img.classList.add("lab-sample", item.sample);
  img.addEventListener("error", () => img.replaceWith(placeholder), { once: true });
  img.src = item.image;
  parent.append(img);
}

function renderCatalog() {
  el("catalog").replaceChildren(...catalog.map((item) => {
    const card = make("button");
    card.type = "button";
    card.className = "card";
    card.dataset.id = item.id;
    addImageOrPlaceholder(card, item);
    card.append(make("strong", item.title), make("small", [item.sample ? "固定风格示意" : "", item.description].filter(Boolean).join(" · ")));
    card.addEventListener("click", () => {
      try {
        if (draft.product === "v2") setDraft({ case_id: draft.case_id === item.id ? null : item.id });
        else setDraft({ style_ids: draft.style_ids.includes(item.id) ? draft.style_ids.filter((id) => id !== item.id) : [...draft.style_ids, item.id] });
      } catch (error) { el("run-notice").textContent = error.message; }
    });
    return card;
  }));
  el("more").hidden = nextCursor == null && !nextLocalPage.length;
  renderDraft();
}

function renderRun() {
  const resultStrings = { completed: "已完成", partial_success: "部分完成", failed: "任务失败", cancelled: "已取消", waiting_for_user: "需要处理", blocked_by_policy: "无法继续生成" };
  el("result-panel").hidden = !run;
  if (!run) return;
  el("result-state").textContent = (resultStrings[run.status] || "正在处理") + " · " + run.id + (run.selected.length ? " · " + run.selected.map((item) => item.title).join("、") : "");
  for (const output of run.outputs) {
    let card = resultCards.get(output.id);
    if (!card) {
      const box = make("article");
      box.className = "result";
      const preview = make("img");
      preview.alt = output.title || "生成结果";
      const retry = make("button", "重新加载预览");
      retry.type = "button";
      retry.hidden = true;
      preview.addEventListener("error", () => { preview.hidden = false; retry.hidden = false; });
      preview.addEventListener("load", () => { retry.hidden = true; });
      retry.addEventListener("click", () => { preview.src = output.preview + "?reload=" + Date.now(); });
      preview.src = output.preview;
      const original = make("a", "下载原图");
      original.href = output.original;
      original.download = output.id;
      const review = make("p");
      box.append(preview, retry, original, review);
      el("results").append(box);
      card = { review };
      resultCards.set(output.id, card);
    }
    const label = { pass: "审核通过", needs_review: "需人工复核", fail: "审核未通过" }[output.review] || output.review;
    card.review.textContent = label ? [label, ...output.reasons.filter(Boolean)].join(" · ") : "";
  }
}

async function trackOriginal(epoch) {
  while (epoch === authEpoch && run && !run.terminal) {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    if (epoch !== authEpoch || !run) return;
    try {
      const next = projectRun(run.product, await api(runPath(run)));
      if (epoch !== authEpoch) return;
      if (next.id !== run.id) throw new Error("返回了不同的任务 ID。");
      run = next;
      el("run-notice").textContent = "";
      renderRun();
    } catch (error) {
      if (epoch !== authEpoch) return;
      el("run-notice").textContent = "正在继续查询原任务。 " + error.message;
      if ([401, 403].includes(error.status)) await new Promise((resolve) => setTimeout(resolve, 7500));
    }
  }
}

async function submit(previous = null) {
  if (busy || (uncertain && previous !== uncertain)) return;
  const submission = previous || { product: draft.product, payload: createPayload(draft), key: crypto.randomUUID() };
  const v2 = submission.product === "v2";
  const epoch = authEpoch;
  busy = true;
  uncertain = null;
  run = null;
  resultCards.clear();
  el("results").replaceChildren();
  renderRun();
  renderDraft();
  el("recover").hidden = true;
  el("lab-history").hidden = true;
  el("run-notice").textContent = "正在提交…";
  try {
    const receipt = await api(v2 ? v2CreatePath : labPath + "/sessions", {
      body: submission.payload, headers: v2 ? { "Idempotency-Key": submission.key } : {},
    });
    if (epoch !== authEpoch) return;
    run = projectRun(submission.product, receipt);
    el("run-notice").textContent = "";
    renderRun();
    await trackOriginal(epoch);
  } catch (error) {
    if (epoch !== authEpoch) return;
    if (!run && (!error.status || error.status === 408 || error.status >= 500)) {
      uncertain = submission;
      el("recover").hidden = !v2;
      el("lab-history").hidden = v2;
      el("run-notice").textContent = v2 ? "提交回执未收到。可以用原请求找回任务。" : "提交回执未收到。请先在 LAB 历史核对原任务。";
    } else el("run-notice").textContent = error.message;
  } finally {
    if (epoch === authEpoch) {
      busy = false;
      renderDraft();
    }
  }
}

const textSchema = { type: "string" };
const idSchema = { type: "string", pattern: "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$" };
const schema = (properties = {}, required = []) => ({ type: "object", properties, required, additionalProperties: false });
const context = document.modelContext;
if (typeof context?.registerTool === "function") {
  const register = (name, description, inputSchema, execute, readOnlyHint) => {
    context.registerTool({ name, description, inputSchema, execute, annotations: { readOnlyHint } });
  };
  register("alchemy_read_draft", "Read current V2 or LAB draft, including user-selected cases, styles and parameters. Does not submit.", schema(), async () => snapshot(), true);
  register("alchemy_find_cards", "Search the visible V2 case or LAB style catalog. Returns IDs, names and thumbnails; updates the visible search.", schema({ query: textSchema }, ["query"]), async ({ query }) => {
    el("query").value = query;
    return { product: draft.product, cards: await loadCatalog() };
  }, false);
  register("alchemy_update_draft", "Set user-requested settings in this page only. Read the draft and find catalog IDs first. Never submits an image task.", schema({
    product: { type: "string", enum: ["v2", "lab"] }, prompt: textSchema, ratio: { type: "string", enum: ratios },
    count: { type: "integer", minimum: 1, maximum: 8 }, case_id: { anyOf: [idSchema, { type: "null" }] },
    style_ids: { type: "array", items: idSchema }, per_style: { type: "integer", minimum: 1, maximum: 4 },
  }), async (patch) => {
    if (patch.style_ids?.length) await loadLabCatalog();
    if (patch.case_id && !caseNames.has(patch.case_id)) {
      const item = await api("/api/v2/prompt-cases/" + encodeURIComponent(patch.case_id));
      if (!item.is_active || item.case_id !== patch.case_id) throw new Error("案例已下架。");
      caseNames.set(item.case_id, item.title);
    }
    return setDraft(patch);
  }, false);
  register("alchemy_read_result", "Read current run ID, actual choices, and output identities. For the original, use alchemy_read_workbench_image with this product and output ID.", schema(), async () => run, true);
}

function handleDraft(patch) {
  try { setDraft(patch); } catch (error) { el("run-notice").textContent = error.message; renderDraft(); }
}
const reload = (options) => { void loadCatalog(options).catch(() => {}); };
for (const button of modeButtons) button.addEventListener("click", () => handleDraft({ product: button.dataset.product }));
el("search").addEventListener("submit", (event) => { event.preventDefault(); reload(); });
el("more").addEventListener("click", () => reload({ append: true }));
el("reload").addEventListener("click", () => reload());
el("prompt").addEventListener("input", () => handleDraft({ prompt: el("prompt").value }));
el("ratio").addEventListener("change", () => handleDraft({ ratio: el("ratio").value }));
el("count").addEventListener("change", () => handleDraft({ [draft.product === "lab" ? "per_style" : "count"]: Number(el("count").value) }));
el("generation").addEventListener("submit", (event) => {
  event.preventDefault();
  void submit().catch((error) => { el("run-notice").textContent = error.message; });
});
el("recover").addEventListener("click", () => { if (uncertain?.product === "v2") void submit(uncertain); });
window.addEventListener("storage", (event) => {
  if (event.key !== null && event.key !== "alchemy_veyra_access_token") return;
  if (event.key && event.oldValue === event.newValue) return;
  authEpoch++;
  draft = initialDraft();
  caseNames.clear();
  labCatalog = null;
  styles = new Map();
  run = uncertain = null;
  busy = false;
  resultCards.clear();
  el("results").replaceChildren();
  el("recover").hidden = el("lab-history").hidden = true;
  el("query").value = el("run-notice").textContent = "";
  renderRun();
  reload();
});
renderDraft();
reload();
