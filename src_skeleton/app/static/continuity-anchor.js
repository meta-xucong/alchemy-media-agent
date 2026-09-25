/* Doc322: one server-owned binding; never reconstruct sources from history. */
(() => {
  "use strict";
  const el = (tag, text, className = "") => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    node.className = className;
    return node;
  };
  const image = (url, label) => {
    if (!/^\/api\/v3\/creative-agent\/(outputs|uploads)\/[A-Za-z0-9_-]+\/(preview|thumbnail|content)$/.test(String(url))) return null;
    const node = el("img"); node.src = url; node.alt = label;
    node.loading = "lazy"; node.style.cssText = "width:96px;height:96px;object-fit:contain;border-radius:10px";
    return node;
  };
  const group = (board, title, description) => {
    const section = el("section", undefined, "v3-project-reference-group v3-mobile-reference-group");
    section.style.cssText = "min-width:0;overflow-wrap:anywhere";
    section.append(el("strong", title), el("p", description));
    board.append(section); return section;
  };
  const pending = new Set();
  async function change(options, output = null) {
    const {project, request, refresh, isCurrent, notify} = options;
    const state = project?.metadata?.continuity_anchor;
    if (!project?.project_id || !Number.isInteger(state?.version)) {
      notify("主图状态尚未确认，请刷新项目。", "warning"); return;
    }
    const message = output ? "将这张已通过图片设为唯一连续性主图？原主图会被替换，历史记录保留。" : "解除当前主图？解绑后不会自动从历史补回。";
    if (!window.confirm(message)) return;
    if (pending.has(project.project_id)) return;
    pending.add(project.project_id);
    try {
      await request(`/projects/${encodeURIComponent(project.project_id)}/continuity-anchor/${output ? "bind" : "unbind"}`, {
        method: "POST", body: output ? {output_id: output.output_id, expected_job_id: output.job_id,
          expected_version: state.version, confirm_binding: true} : {expected_version: state.version, confirm_unbind: true},
      });
      if (!isCurrent(project.project_id)) return;
      await refresh();
      if (!isCurrent(project.project_id)) return;
      notify(output ? "已设为唯一连续性主图。" : "已解绑；后续任务不会自动补回历史图片。", "success");
    } catch (error) {
      if (!isCurrent(project.project_id)) return;
      notify("主图状态暂未确认，请刷新项目核对；未自动重试。", "warning");
      try { await refresh(); } catch (_) { /* Preserve the last known view when offline. */ }
    } finally {
      pending.delete(project.project_id);
    }
  }
  function render(board, options) {
    const {project} = options;
    const state = project?.metadata?.continuity_anchor;
    if (!board || !state) return false;
    board.replaceChildren(); board.classList.remove("empty-v3-list", "empty-v2-list");
    const active = state.state === "active" ? state.active_continuity_anchor : null;
    const anchor = group(board, "当前连续性主图 · 最多一张", active
      ? "仅这张已绑定成片参与后续连续性；不会替代本次明确的参考要求。"
      : state.state === "unbound" ? "已解绑，不自动从历史补回。可在正式交付图片上选择“设为主图”。"
      : state.state === "invalid" ? "原主图证据已失效；不会换用别的历史图片。请解绑或重新选择。"
      : "尚无主图。符合条件的首张正式通过图片可自动绑定，也可手动选择。" );
    anchor.dataset.continuityState = state.state;
    if (active) { const img = image(active.preview_url, "当前连续性主图"); if (img) anchor.append(img); }
    if (active || state.state === "invalid") {
      const button = el("button", "解绑主图", "button secondary"); button.type = "button";
      button.addEventListener("click", async () => {
        if (button.disabled) return;
        button.disabled = true;
        try { await change(options); } finally { if (button.isConnected) button.disabled = false; }
      }); anchor.append(button);
    }
    const mode = project.metadata.current_job_reference_mode;
    if (mode === "standard_direct_reference") {
      const inputs = Array.isArray(project.metadata.current_job_reference_inputs) ? project.metadata.current_job_reference_inputs : [];
      const direct = group(board, `本次参考图 · ${inputs.length} 张`, "仅显示当前已提交任务明确上传的原图；下一次任务不自动继承。");
      direct.dataset.referenceMode = mode;
      for (const item of inputs) {
        const card = el("article"); const img = image(item.preview_url, item.filename || "本次参考图");
        if (img) card.append(img); card.append(el("span", item.filename || "本次参考图")); direct.append(card);
      }
    } else if (mode === "professional_asset_binding") {
      group(board, "Professional 资产绑定", "仅使用你已明确绑定并冻结的资产版本。原有资产面板负责变更绑定。").dataset.referenceMode = mode;
    } else if (mode === "ecommerce_product_truth") {
      const inputs = group(board, "商品事实输入", "仅使用通过商品事实契约的参考。裁剪和特征证据不作为用户原图展示。");
      inputs.dataset.referenceMode = mode;
      const facts = project.metadata.ecommerce_project_view?.groups?.original_product_inputs?.items || [];
      for (const item of facts) {
        const img = image(item.preview_url || item.content_url, "商品事实输入"); if (img) inputs.append(img);
      }
    }
    return true;
  }
  window.AlchemyContinuity = Object.freeze({render, bind: change});
})();
