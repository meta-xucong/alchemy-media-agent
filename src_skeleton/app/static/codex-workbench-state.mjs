export const labPath = "/api/lab/rare-style-explorer";
export const v2CreatePath = "/api/v2/creative/runs/async";
export const ratios = ["", "1:1", "4:5", "3:2", "9:16", "16:9"];
const idPattern = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const v2Terminal = ["completed", "failed", "cancelled", "blocked_by_policy", "waiting_for_user"];
const labTerminal = ["completed", "partial_success", "failed", "cancelled"];

export function initialDraft() {
  return { product: "v2", prompt: "", ratio: "", count: 1, case_id: null, style_ids: [], per_style: 1 };
}

export function updateDraft(previous, patch, styles, limits) {
  const next = { ...previous, ...patch };
  if (!["v2", "lab"].includes(next.product)) throw new Error("请选择 V2 或 LAB。");
  if (typeof next.prompt !== "string" || next.prompt.length > 6000) throw new Error("需求过长。");
  if (!ratios.includes(next.ratio)) throw new Error("画幅不可用。");
  if (!Number.isInteger(next.count) || next.count < 1 || next.count > 8) throw new Error("V2 张数为 1–8。");
  if (next.case_id !== null && !idPattern.test(next.case_id)) throw new Error("案例 ID 无效。");
  if (!Array.isArray(next.style_ids) || next.style_ids.length > limits.maxSelectedStyles
    || new Set(next.style_ids).size !== next.style_ids.length
    || next.style_ids.some((id) => !styles.has(id))) throw new Error("请从有效的 LAB 风格中选择。");
  if (!Number.isInteger(next.per_style) || next.per_style < 1 || next.per_style > limits.maxImagesPerStyle
    || next.style_ids.length * next.per_style > limits.maxTotalImages) throw new Error("LAB 总张数或每风格张数超过上限。");
  return next;
}

export function createPayload(draft) {
  const prompt = draft.prompt.trim();
  if (!prompt) throw new Error("请填写生图需求。");
  const aspect = draft.ratio ? { aspect_ratio: draft.ratio } : {};
  if (draft.product === "v2") {
    return { user_prompt: prompt, template_case_id: draft.case_id,
      mode_hint: draft.case_id ? "template_customize" : "smart_enhance",
      output: { count: draft.count, ...aspect } };
  }
  if (!draft.style_ids.length) throw new Error("请先选至少一种 LAB 风格。");
  return { idea: prompt, selected_style_ids: draft.style_ids, images_per_style: draft.per_style,
    target_count: draft.style_ids.length * draft.per_style, ...aspect };
}

export function caseThumbnail(raw) {
  const value = String(raw || "");
  const local = "/api/v2/case-thumbnails/";
  const github = "https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts/";
  const path = value.startsWith(local) ? value.slice(local.length).replace(/^(grid|preview)\//, "")
    : value.startsWith(github) ? value.slice(github.length).replace(/^[^/]+\//, "") : "";
  return /^images\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+$/.test(path) ? local + "grid/" + path : "";
}

function labOutputId(url) {
  return /^\/v1\/outputs\/([A-Za-z0-9][A-Za-z0-9_-]{0,127})\/(?:download|preview|thumbnail)$/.exec(url || "")?.[1] || null;
}

export function projectRun(product, payload) {
  if (product === "v2") {
    const id = payload.run_id;
    if (!idPattern.test(id || "")) throw new Error("V2 回执缺少任务 ID。");
    const outputs = (payload.generation_jobs || []).flatMap((job) => job.outputs || [])
      .filter((item) => idPattern.test(item.output_id || "")).map((item) => ({
        id: item.output_id,
        preview: "/api/v2/image/history/" + item.output_id + "/preview",
        original: "/api/v2/outputs/" + item.output_id + "/download",
        review: item.review?.decision || null,
        reasons: Array.isArray(item.review?.reasons) ? item.review.reasons : [],
      }));
    return { product, id, status: payload.status, terminal: v2Terminal.includes(payload.status), outputs,
      selected: (payload.selected_cases || []).map((item) => ({ id: item.case_id, title: item.title })) };
  }
  const { session, board } = payload;
  if (!idPattern.test(session?.id || "")) throw new Error("LAB 回执缺少任务 ID。");
  const variants = new Map((session.variants || []).map((item) => [item.id, item]));
  const outputs = (board?.groups || []).flatMap((group) => group.cards || []).flatMap((item) => {
    const asset = variants.get(item.variant_id)?.asset;
    const id = idPattern.test(asset?.output_id || "") ? asset.output_id :
      labOutputId(item.image_url) || labOutputId(item.preview_url) || labOutputId(item.thumbnail_url);
    if (!id || !item.image_url) return [];
    return [{ id, title: item.style_name, style_id: item.style_preset_id,
      preview: "/api/lab/outputs/" + id + "/preview", original: "/api/lab/outputs/" + id + "/download",
      review: asset?.review?.decision || null, reasons: asset?.review?.reasons || [] }];
  });
  const status = board?.status || session.status;
  return { product, id: session.id, status, terminal: labTerminal.includes(status), outputs,
    selected: (session.style_presets || []).map((item) => ({ id: item.id, title: item.display_name })) };
}

export function runPath(run) {
  return (run.product === "v2" ? "/api/v2/creative/runs/" : labPath + "/sessions/") + run.id;
}
