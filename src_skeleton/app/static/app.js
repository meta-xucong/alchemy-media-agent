const intensityMap = {
  swift: { label: "快速" },
  balanced: { label: "均衡" },
  studio: { label: "精修" },
  atelier: { label: "臻选" },
};

const qualityMap = {
  auto: "自动",
  low: "低",
  medium: "中",
  high: "高",
};

const coffeeSamplePrompt = "生成 4 张日系清爽风格的咖啡产品海报，适配手机竖屏的";
const defaultImageCount = "1";
const coffeeSampleCount = "4";
const heroCarouselIntervalMs = 5000;

const state = {
  sessionId: null,
  assetIds: [],
  currentJob: null,
  selectedOutputId: null,
  selectedSize: "1024x1536",
  selectedFormat: "png",
  selectedQuality: "high",
  selectedIntensity: "balanced",
  selectedProvider: "openai_gpt_image",
  selectedLlmProvider: "openai",
  imageProviderReady: false,
  imageProviderCapabilities: {},
  providerSettings: null,
  heroHistoryItems: [],
};

let providerSaveTimer = null;
let providerChangeVersion = 0;
let heroCarouselTimer = null;
let heroCarouselIndex = 0;

const els = {
  sessionLabel: document.querySelector("#sessionLabel"),
  tabs: document.querySelectorAll("[data-tab]"),
  panels: document.querySelectorAll("[data-panel]"),
  providerList: document.querySelector("#providerList"),
  videoProviderList: document.querySelector("#videoProviderList"),
  providerState: document.querySelector("#providerState"),
  openaiApiKeyInput: document.querySelector("#openaiApiKeyInput"),
  openaiBaseUrlInput: document.querySelector("#openaiBaseUrlInput"),
  openaiImageModelInput: document.querySelector("#openaiImageModelInput"),
  geminiImageModelInput: document.querySelector("#geminiImageModelInput"),
  geminiImageBaseUrlInput: document.querySelector("#geminiImageBaseUrlInput"),
  geminiImageApiKeyInput: document.querySelector("#geminiImageApiKeyInput"),
  openaiLlmModelInput: document.querySelector("#openaiLlmModelInput"),
  kimiLlmModelInput: document.querySelector("#kimiLlmModelInput"),
  anthropicBaseUrlInput: document.querySelector("#anthropicBaseUrlInput"),
  anthropicApiKeyInput: document.querySelector("#anthropicApiKeyInput"),
  imageActiveLabel: document.querySelector("#imageActiveLabel"),
  thinkingActiveLabel: document.querySelector("#thinkingActiveLabel"),
  openaiImageState: document.querySelector("#openaiImageState"),
  geminiImageState: document.querySelector("#geminiImageState"),
  openaiThinkingState: document.querySelector("#openaiThinkingState"),
  kimiThinkingState: document.querySelector("#kimiThinkingState"),
  intensityValue: document.querySelector("#intensityValue"),
  assetInput: document.querySelector("#assetInput"),
  assetName: document.querySelector("#assetName"),
  assetPreview: document.querySelector("#assetPreview"),
  assetPreviewLabel: document.querySelector("#assetPreviewLabel"),
  assetState: document.querySelector("#assetState"),
  rightsCheck: document.querySelector("#rightsCheck"),
  promptInput: document.querySelector("#promptInput"),
  generateBtn: document.querySelector("#generateBtn"),
  smokeBtn: document.querySelector("#smokeBtn"),
  newSessionBtn: document.querySelector("#newSessionBtn"),
  countInput: document.querySelector("#countInput"),
  countValue: document.querySelector("#countValue"),
  qualityValue: document.querySelector("#qualityValue"),
  jobStatus: document.querySelector("#jobStatus"),
  outputCount: document.querySelector("#outputCount"),
  traceId: document.querySelector("#traceId"),
  gallery: document.querySelector("#gallery"),
  historyGallery: document.querySelector("#historyGallery"),
  historyCount: document.querySelector("#historyCount"),
  refreshHistoryBtn: document.querySelector("#refreshHistoryBtn"),
  heroHistoryCarousel: document.querySelector("#heroHistoryCarousel"),
  caseReferenceCarousel: document.querySelector(".case-showcase .case-carousel"),
  outputTemplate: document.querySelector("#outputTemplate"),
  revisionInput: document.querySelector("#revisionInput"),
  reviseBtn: document.querySelector("#reviseBtn"),
  selectedOutputLabel: document.querySelector("#selectedOutputLabel"),
  eventList: document.querySelector("#eventList"),
  eventCount: document.querySelector("#eventCount"),
  noticeBar: document.querySelector("#noticeBar"),
  globalToast: document.querySelector("#globalToast"),
  galleryWrap: document.querySelector(".gallery-wrap"),
  sampleGuideModal: document.querySelector("#sampleGuideModal"),
  closeSampleGuideBtn: document.querySelector("#closeSampleGuideBtn"),
  applySampleBtn: document.querySelector("#applySampleBtn"),
  applyAndGenerateSampleBtn: document.querySelector("#applyAndGenerateSampleBtn"),
  samplePromptPreview: document.querySelector("#samplePromptPreview"),
  imageLightbox: document.querySelector("#imageLightbox"),
  lightboxImage: document.querySelector("#lightboxImage"),
  lightboxTitle: document.querySelector("#lightboxTitle"),
  lightboxMeta: document.querySelector("#lightboxMeta"),
  lightboxPromptBtn: document.querySelector("#lightboxPromptBtn"),
  lightboxPromptPanel: document.querySelector("#lightboxPromptPanel"),
  lightboxPromptText: document.querySelector("#lightboxPromptText"),
  closePromptPanelBtn: document.querySelector("#closePromptPanelBtn"),
  lightboxDownload: document.querySelector("#lightboxDownload"),
  closeImageLightboxBtn: document.querySelector("#closeImageLightboxBtn"),
};

document.addEventListener("DOMContentLoaded", async () => {
  bindControls();
  try {
    await createSession({ announce: false });
    await loadProviders();
    await refreshHistory({ silent: true });
  } catch (error) {
    showNotice(`初始化失败：${friendlyError(error)}`, "error");
  }
});

window.addEventListener("unhandledrejection", (event) => {
  showNotice(`请求异常：${friendlyError(event.reason)}`, "error");
});

window.addEventListener("error", (event) => {
  showNotice(`界面异常：${event.message}`, "error");
});

function bindControls() {
  els.tabs.forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });

  els.countInput.addEventListener("input", () => {
    els.countValue.textContent = els.countInput.value;
  });

  document.querySelectorAll("[data-size]").forEach((button) => {
    button.addEventListener("click", () => {
      setActive(button, "[data-size]");
      state.selectedSize = button.dataset.size;
    });
  });

  document.querySelectorAll("[data-format]").forEach((button) => {
    button.addEventListener("click", () => {
      setActive(button, "[data-format]");
      state.selectedFormat = button.dataset.format;
    });
  });

  document.querySelectorAll("[data-quality]").forEach((button) => {
    button.addEventListener("click", () => {
      setActive(button, "[data-quality]");
      state.selectedQuality = button.dataset.quality;
      els.qualityValue.textContent = qualityMap[state.selectedQuality];
    });
  });

  document.querySelectorAll("[data-intensity]").forEach((button) => {
    button.addEventListener("click", () => {
      setActive(button, "[data-intensity]");
      state.selectedIntensity = button.dataset.intensity;
      els.intensityValue.textContent = intensityMap[state.selectedIntensity].label;
      scheduleProviderSettingsSync({ immediate: true });
    });
  });

  document.querySelectorAll("[data-image-provider]").forEach((button) => {
    button.addEventListener("click", () => setImageProvider(button.dataset.imageProvider, { persist: true }));
  });

  document.querySelectorAll("[data-llm-provider]").forEach((button) => {
    button.addEventListener("click", () => setThinkingProvider(button.dataset.llmProvider, { persist: true }));
  });

  els.assetInput.addEventListener("change", handleAsset);
  els.generateBtn.addEventListener("click", generateImage);
  els.reviseBtn.addEventListener("click", reviseSelectedOutput);
  els.refreshHistoryBtn.addEventListener("click", () => refreshHistory({ silent: false }));
  els.heroHistoryCarousel.addEventListener("click", openActiveHeroHistorySlide);
  bindProviderAutosave();
  els.newSessionBtn.addEventListener("click", startNewSession);
  els.smokeBtn.addEventListener("click", openSampleGuide);
  els.closeSampleGuideBtn.addEventListener("click", closeSampleGuide);
  els.closeImageLightboxBtn.addEventListener("click", closeImageLightbox);
  els.lightboxPromptBtn.addEventListener("click", toggleLightboxPrompt);
  els.closePromptPanelBtn.addEventListener("click", closeLightboxPrompt);
  els.applySampleBtn.addEventListener("click", () => applyCoffeeSample({ generate: false }));
  els.applyAndGenerateSampleBtn.addEventListener("click", () => applyCoffeeSample({ generate: true }));
  els.sampleGuideModal.addEventListener("click", (event) => {
    if (event.target === els.sampleGuideModal) closeSampleGuide();
  });
  els.imageLightbox.addEventListener("click", (event) => {
    if (event.target.hasAttribute("data-close-lightbox")) closeImageLightbox();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !els.sampleGuideModal.hidden) closeSampleGuide();
    if (event.key === "Escape" && !els.imageLightbox.hidden) closeImageLightbox();
  });
}

function switchTab(tabName) {
  els.tabs.forEach((button) => {
    const active = button.dataset.tab === tabName;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  els.panels.forEach((panel) => {
    const active = panel.dataset.panel === tabName;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
}

function setActive(activeButton, selector) {
  document.querySelectorAll(selector).forEach((button) => button.classList.remove("active"));
  activeButton.classList.add("active");
}

function setSize(size) {
  const button = document.querySelector(`[data-size="${size}"]`);
  if (!button) return;
  setActive(button, "[data-size]");
  state.selectedSize = size;
}

function setFormat(format) {
  const button = document.querySelector(`[data-format="${format}"]`);
  if (!button) return;
  setActive(button, "[data-format]");
  state.selectedFormat = format;
}

function setQuality(quality) {
  const button = document.querySelector(`[data-quality="${quality}"]`);
  if (!button) return;
  setActive(button, "[data-quality]");
  state.selectedQuality = quality;
  els.qualityValue.textContent = qualityMap[quality] || quality;
}

function setIntensity(value) {
  const button = document.querySelector(`[data-intensity="${value}"]`);
  if (!button) return;
  setActive(button, "[data-intensity]");
  state.selectedIntensity = value;
  els.intensityValue.textContent = intensityMap[value].label;
}

function setImageProvider(provider, { persist = false } = {}) {
  const requested = provider === "gemini_image" ? "gemini_image" : "openai_gpt_image";
  if (requested === "gemini_image" && !isImageProviderUsable("gemini_image")) {
    state.selectedProvider = "openai_gpt_image";
    showNotice("Gemini 生图当前还是占位入口，已自动切回 GPT 生图。", "warning");
  } else {
    state.selectedProvider = requested;
  }
  document.querySelectorAll("[data-image-provider]").forEach((button) => {
    button.classList.toggle("active", button.dataset.imageProvider === state.selectedProvider);
  });
  els.imageActiveLabel.textContent = state.selectedProvider === "gemini_image" ? "Gemini 优先" : "GPT 优先";
  if (persist) scheduleProviderSettingsSync({ immediate: true });
}

function setThinkingProvider(provider, { persist = false } = {}) {
  state.selectedLlmProvider = provider === "anthropic" ? "anthropic" : "openai";
  document.querySelectorAll("[data-llm-provider]").forEach((button) => {
    button.classList.toggle("active", button.dataset.llmProvider === state.selectedLlmProvider);
  });
  els.thinkingActiveLabel.textContent = state.selectedLlmProvider === "anthropic" ? "Kimi 优先" : "GPT 优先";
  if (persist) scheduleProviderSettingsSync({ immediate: true });
}

function bindProviderAutosave() {
  [
    els.openaiBaseUrlInput,
    els.anthropicBaseUrlInput,
    els.geminiImageBaseUrlInput,
    els.openaiImageModelInput,
    els.geminiImageModelInput,
    els.openaiLlmModelInput,
    els.kimiLlmModelInput,
  ].forEach((input) => {
    input.addEventListener("input", () => scheduleProviderSettingsSync());
    input.addEventListener("change", () => scheduleProviderSettingsSync({ immediate: true }));
  });

  [els.openaiApiKeyInput, els.geminiImageApiKeyInput, els.anthropicApiKeyInput].forEach((input) => {
    input.addEventListener("input", () => scheduleProviderSettingsSync({ delay: 900 }));
    input.addEventListener("change", () => scheduleProviderSettingsSync({ immediate: true }));
  });
}

function scheduleProviderSettingsSync({ immediate = false, delay = 650 } = {}) {
  providerChangeVersion += 1;
  const version = providerChangeVersion;
  window.clearTimeout(providerSaveTimer);
  els.providerState.textContent = "应用中";
  providerSaveTimer = window.setTimeout(() => {
    providerSaveTimer = null;
    syncProviderSettings({ silent: false, version }).catch(() => null);
  }, immediate ? 0 : delay);
}

function openSampleGuide() {
  els.samplePromptPreview.textContent = coffeeSamplePrompt;
  els.sampleGuideModal.hidden = false;
  document.body.classList.add("modal-open");
  els.closeSampleGuideBtn.focus();
}

function closeSampleGuide() {
  els.sampleGuideModal.hidden = true;
  document.body.classList.remove("modal-open");
  els.smokeBtn.focus();
}

async function applyCoffeeSample({ generate }) {
  closeSampleGuide();
  switchTab("image");
  els.promptInput.value = coffeeSamplePrompt;
  els.countInput.value = coffeeSampleCount;
  els.countValue.textContent = coffeeSampleCount;
  setSize("1024x1536");
  setFormat("png");
  setQuality("high");
  setIntensity("balanced");
  showNotice("咖啡海报示例已载入工作台。", "success");
  showGlobalToast(generate ? "示例已载入，开始生成。" : "示例已载入。");
  els.promptInput.scrollIntoView({ behavior: "smooth", block: "center" });
  if (generate) {
    await generateImage();
  }
}

async function createSession({ announce = true } = {}) {
  const session = await request("/v1/sessions", {
    method: "POST",
    body: {
      project_id: "frontend_project",
      title: "Alchemy Image Atelier",
      orchestration_mode: "runtime_first",
    },
  });
  state.sessionId = session.id;
  state.assetIds = [];
  state.currentJob = null;
  state.selectedOutputId = null;
  els.sessionLabel.textContent = session.id;
  els.gallery.innerHTML = "";
  els.gallery.classList.remove("loading");
  els.gallery.classList.add("empty-gallery");
  els.assetName.textContent = "图片、PDF、文档或表格";
  els.assetState.textContent = "空";
  els.assetInput.value = "";
  resetAssetPreview();
  els.revisionInput.value = "";
  els.selectedOutputLabel.textContent = "未选";
  setStatus("待命", 0, "-");
  showNotice("会话已准备好。", "success");
  if (announce) {
    showGlobalToast(`新会话已创建：${session.id}`);
  }
  toggleBusy(false);
  renderEvents([]);
  return session;
}

async function startNewSession() {
  const originalText = els.newSessionBtn.textContent;
  els.newSessionBtn.disabled = true;
  els.newSessionBtn.textContent = "创建中";
  showGlobalToast("正在创建新会话。");
  try {
    await createSession();
    switchTab("image");
    els.promptInput.value = "";
    els.countInput.value = defaultImageCount;
    els.countValue.textContent = defaultImageCount;
    setSize("1024x1536");
    setFormat("png");
    setQuality("high");
    els.promptInput.focus();
  } catch (error) {
    showNotice(`新会话创建失败：${friendlyError(error)}`, "error");
    showGlobalToast("新会话创建失败。", "error");
  } finally {
    els.newSessionBtn.disabled = false;
    els.newSessionBtn.textContent = originalText;
  }
}

async function loadProviders() {
  const [providers, runtime] = await Promise.all([
    request("/v1/providers"),
    request("/v1/runtime/provider-settings"),
  ]);
  state.providerSettings = runtime;
  state.imageProviderCapabilities = Object.fromEntries((providers.image || []).map((provider) => [provider.provider, provider]));
  state.selectedProvider = runtime.default_image_provider || "openai_gpt_image";
  state.selectedLlmProvider = runtime.default_llm_provider || "openai";
  state.selectedIntensity = runtime.image_work_intensity || "balanced";
  els.openaiImageModelInput.value = runtime.openai_image_model || "gpt-image-2";
  els.geminiImageModelInput.value = runtime.gemini_image_model || "gemini-3.1-flash-image";
  els.openaiLlmModelInput.value = runtime.openai_llm_model || "gpt-5.5";
  els.kimiLlmModelInput.value = runtime.kimi_llm_model || "kimi-for-coding";
  els.geminiImageBaseUrlInput.value = runtime.gemini_image_base_url || "";
  els.openaiBaseUrlInput.value = runtime.openai_base_url || "";
  els.anthropicBaseUrlInput.value = runtime.anthropic_base_url || "https://aiself.vip";
  els.intensityValue.textContent = intensityMap[state.selectedIntensity]?.label || "均衡";
  setActiveIntensity(state.selectedIntensity);
  setImageProvider(state.selectedProvider);
  setThinkingProvider(state.selectedLlmProvider);

  renderProviderLists(providers, runtime);
  const openai = providers.image.find((provider) => provider.provider === "openai_gpt_image");
  const gemini = providers.image.find((provider) => provider.provider === "gemini_image");
  if (!isImageProviderUsable(state.selectedProvider) && isImageProviderUsable("openai_gpt_image")) {
    state.selectedProvider = "openai_gpt_image";
  }
  const selectedImage = providers.image.find((provider) => provider.provider === state.selectedProvider);
  const fallbackImage = providers.image.find((provider) => provider.provider !== state.selectedProvider && ["openai_gpt_image", "gemini_image"].includes(provider.provider));
  state.imageProviderReady = Boolean(selectedImage?.configured || fallbackImage?.configured);
  els.openaiImageState.textContent = openai?.configured ? runtime.openai_image_model : "需 API";
  els.geminiImageState.textContent = gemini?.configured ? runtime.gemini_image_model : "待接入";
  els.openaiThinkingState.textContent = runtime.openai_api_key_configured ? runtime.openai_llm_model : "需 API";
  els.kimiThinkingState.textContent = runtime.anthropic_api_key_configured ? runtime.kimi_llm_model : "需 API";
  els.providerState.textContent = state.imageProviderReady ? `${providerLabel(state.selectedProvider)} ready` : "需要 API";
  setImageProviderAvailability("openai_gpt_image", Boolean(openai?.configured), "");
  setImageProviderAvailability(
    "gemini_image",
    Boolean(gemini?.configured),
    gemini?.configured ? "" : "Gemini 生图尚未接入 live provider，当前不可选。"
  );

  if (state.imageProviderReady) {
    showNotice(`模型已就绪：生图 ${providerLabel(state.selectedProvider)}；思考 ${thinkingProviderLabel(state.selectedLlmProvider)}。`, "success");
  } else {
    showNotice("请在高级 API 配置里保存 GPT API Key 后生成图片；Gemini 生图为预留入口。", "warning");
  }
}

function setActiveIntensity(value) {
  const button = document.querySelector(`[data-intensity="${value}"]`) || document.querySelector("[data-intensity='balanced']");
  if (button) setActive(button, "[data-intensity]");
}

function renderProviderLists(providers, runtime) {
  els.providerList.innerHTML = "";
  providers.image
    .filter((provider) => ["openai_gpt_image", "gemini_image", "mock_image"].includes(provider.provider))
    .forEach((provider) => {
    els.providerList.appendChild(providerRow(provider, runtime.provider_notes?.[provider.provider]));
  });

  els.videoProviderList.innerHTML = "";
  providers.video.forEach((provider) => {
    els.videoProviderList.appendChild(providerRow(provider, runtime.provider_notes?.[provider.provider]));
  });
}

function providerRow(provider, note) {
  const row = document.createElement("div");
  row.className = `provider-row ${provider.configured ? "ready" : "muted-row"}`;

  const title = document.createElement("div");
  title.className = "provider-title";
  const name = document.createElement("strong");
  name.textContent = providerLabel(provider.provider);
  const badge = document.createElement("span");
  badge.className = "mini-pill";
  badge.textContent = provider.configured ? "已接入" : provider.provider === "gemini_image" ? "待接入" : ["openai_gpt_image"].includes(provider.provider) ? "需 API" : "未接入";
  title.append(name, badge);

  const models = document.createElement("span");
  models.className = "provider-models";
  models.textContent = provider.models.join(", ") || "-";

  const reason = document.createElement("p");
  reason.textContent = provider.reason || note || "";

  row.append(title, models, reason);
  return row;
}

function providerLabel(provider) {
  const labels = {
    openai_gpt_image: "OpenAI GPT Image",
    gemini_image: "Gemini Image",
    mock_image: "Mock Image",
    seedance: "Seedance Video",
  };
  return labels[provider] || provider;
}

function isImageProviderUsable(provider) {
  return Boolean(state.imageProviderCapabilities?.[provider]?.configured);
}

function setImageProviderAvailability(provider, enabled, title) {
  const button = document.querySelector(`[data-image-provider="${provider}"]`);
  if (!button) return;
  button.disabled = !enabled;
  button.title = title || "";
  button.classList.toggle("disabled", !enabled);
}

function thinkingProviderLabel(provider) {
  return provider === "anthropic" ? "Kimi" : "GPT";
}

async function flushProviderSettingsSync({ silent = true } = {}) {
  if (!providerSaveTimer) return null;
  const version = providerChangeVersion;
  window.clearTimeout(providerSaveTimer);
  providerSaveTimer = null;
  return syncProviderSettings({ silent, version });
}

async function syncProviderSettings({ silent, version = providerChangeVersion }) {
  toggleProviderSaving(true);
  try {
    const payload = {
      default_image_provider: state.selectedProvider,
      default_image_model: selectedImageModel(),
      openai_image_model: els.openaiImageModelInput.value.trim() || "gpt-image-2",
      gemini_image_model: els.geminiImageModelInput.value.trim() || "gemini-3.1-flash-image",
      gemini_image_base_url: els.geminiImageBaseUrlInput.value.trim(),
      default_llm_provider: state.selectedLlmProvider,
      default_llm_model: selectedThinkingModel(),
      openai_llm_model: els.openaiLlmModelInput.value.trim() || "gpt-5.5",
      kimi_llm_model: els.kimiLlmModelInput.value.trim() || "kimi-for-coding",
      image_work_intensity: state.selectedIntensity,
      openai_base_url: els.openaiBaseUrlInput.value.trim(),
      anthropic_base_url: els.anthropicBaseUrlInput.value.trim(),
    };
    const apiKey = els.openaiApiKeyInput.value.trim();
    if (apiKey) payload.openai_api_key = apiKey;
    const geminiImageApiKey = els.geminiImageApiKeyInput.value.trim();
    if (geminiImageApiKey) payload.gemini_image_api_key = geminiImageApiKey;
    const backupApiKey = els.anthropicApiKeyInput.value.trim();
    if (backupApiKey) payload.anthropic_api_key = backupApiKey;

    const runtime = await request("/v1/runtime/provider-settings", {
      method: "POST",
      body: payload,
    });
    state.providerSettings = runtime;
    const isCurrentSave = version === providerChangeVersion;
    if (!isCurrentSave) return runtime;
    els.openaiApiKeyInput.value = "";
    els.geminiImageApiKeyInput.value = "";
    els.anthropicApiKeyInput.value = "";
    await loadProviders();
    if (!silent) {
      const message = modelEffectMessage(runtime);
      showNotice(message, "success");
      showGlobalToast(message);
    }
    return runtime;
  } catch (error) {
    showNotice(`Provider 配置失败：${friendlyError(error)}`, "error");
    throw error;
  } finally {
    if (version === providerChangeVersion) toggleProviderSaving(false);
  }
}

function selectedImageModel() {
  if (state.selectedProvider === "gemini_image") {
    return els.geminiImageModelInput.value.trim() || "gemini-3.1-flash-image";
  }
  return els.openaiImageModelInput.value.trim() || "gpt-image-2";
}

function selectedThinkingModel() {
  if (state.selectedLlmProvider === "anthropic") {
    return els.kimiLlmModelInput.value.trim() || "kimi-for-coding";
  }
  return els.openaiLlmModelInput.value.trim() || "gpt-5.5";
}

function toggleProviderSaving(isSaving) {
  if (isSaving) {
    els.providerState.textContent = "应用中";
    return;
  }
  els.providerState.textContent = state.imageProviderReady ? "配置已生效" : "需要 API";
}

function otherImageProvider(provider) {
  return provider === "gemini_image" ? "openai_gpt_image" : "gemini_image";
}

function otherThinkingProvider(provider) {
  return provider === "anthropic" ? "openai" : "anthropic";
}

function modelEffectMessage(runtime) {
  const imageProvider = runtime.default_image_provider || state.selectedProvider;
  const thinkingProvider = runtime.default_llm_provider || state.selectedLlmProvider;
  return `配置已生效：生图 ${providerLabel(imageProvider)} 优先，${providerLabel(otherImageProvider(imageProvider))} 兜底；思考 ${thinkingProviderLabel(thinkingProvider)} 优先，${thinkingProviderLabel(otherThinkingProvider(thinkingProvider))} 兜底。`;
}

async function handleAsset() {
  const file = els.assetInput.files[0];
  if (!file) return;
  els.assetName.textContent = file.name;
  els.assetState.textContent = "上传";
  renderAssetPreview(file);
  const upload = await request("/v1/assets/upload-url", {
    method: "POST",
    body: {
      filename: file.name,
      mime_type: file.type || "application/octet-stream",
      size_bytes: file.size,
      consent: { rights_confirmed: els.rightsCheck.checked },
    },
  });
  const asset = await request(`/v1/assets/${upload.asset_id}/complete`, { method: "POST" });
  if (asset.status === "ready") {
    state.assetIds = [asset.id];
    els.assetState.textContent = "ready";
    addEvent("asset.status", `${asset.id} · ${asset.material_brief.asset_type}`);
  } else {
    els.assetState.textContent = asset.status;
  }
}

function renderAssetPreview(file) {
  els.assetPreview.classList.remove("empty-asset-preview");
  els.assetPreview.style.backgroundImage = "";
  els.assetPreviewLabel.textContent = file.name;
  if (!file.type.startsWith("image/")) {
    els.assetPreview.classList.add("document-preview");
    return;
  }
  els.assetPreview.classList.remove("document-preview");
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    els.assetPreview.style.backgroundImage = `url("${reader.result}")`;
    els.assetPreviewLabel.textContent = "";
  });
  reader.readAsDataURL(file);
}

function resetAssetPreview() {
  els.assetPreview.classList.add("empty-asset-preview");
  els.assetPreview.classList.remove("document-preview");
  els.assetPreview.style.backgroundImage = "";
  els.assetPreviewLabel.textContent = "未选择素材";
}

async function generateImage() {
  const prompt = els.promptInput.value.trim() || els.promptInput.placeholder;
  await ensureSession();
  await flushProviderSettingsSync({ silent: true });
  if (!state.imageProviderReady || els.openaiApiKeyInput.value.trim() || els.geminiImageApiKeyInput.value.trim() || els.anthropicApiKeyInput.value.trim()) {
    await syncProviderSettings({ silent: true });
  }
  if (state.selectedProvider === "gemini_image" && isImageProviderUsable("openai_gpt_image")) {
    setImageProvider("openai_gpt_image");
    await syncProviderSettings({ silent: true });
  }
  if (!state.imageProviderReady) {
    showNotice("生图模型未就绪。请先配置 GPT API；Gemini 生图当前仅保留接入框架。", "warning");
    (state.selectedProvider === "gemini_image" ? els.geminiImageApiKeyInput : els.openaiApiKeyInput).focus();
    return;
  }

  toggleBusy(true);
  const count = Number(els.countInput.value);
  showNotice(`正在生成 ${count} 张图片；优先使用 ${providerLabel(state.selectedProvider)}，质量：${qualityMap[state.selectedQuality]}。`, "info");
  setStatus("生成中", 0, "pending");
  renderSkeleton(count);
  try {
    const job = await request("/v1/image/jobs", {
      method: "POST",
      body: {
        session_id: state.sessionId,
        prompt,
        asset_ids: state.assetIds,
        count,
        size: state.selectedSize,
        quality: state.selectedQuality,
        work_intensity: state.selectedIntensity,
        output_format: state.selectedFormat,
        provider_preference: state.selectedProvider,
      },
    });
    state.currentJob = job;
    setStatus(job.status, job.outputs.length, job.trace_id);
    if (job.status !== "ready" || job.outputs.length === 0) {
      renderGallery([]);
      showNotice(`生成失败：${jobErrorMessage(job)}`, "error");
      await refreshEvents();
      return;
    }
    renderGallery(job.outputs);
    showNotice(`已生成 ${job.outputs.length} 张图片。`, "success");
    els.galleryWrap.scrollIntoView({ behavior: "smooth", block: "start" });
    await refreshHistory({ silent: true });
    await refreshEvents();
  } catch (error) {
    showNotice(`生成失败：${friendlyError(error)}`, "error");
    setStatus("失败", 0, "-");
    renderGallery([]);
  } finally {
    toggleBusy(false);
  }
}

async function reviseSelectedOutput() {
  if (!state.currentJob || !state.selectedOutputId) {
    showNotice("请先在结果区选择一张图片。", "warning");
    return;
  }
  const feedback = els.revisionInput.value.trim() || els.revisionInput.placeholder;
  await ensureSession();
  toggleBusy(true);
  showNotice("正在生成修改版本。", "info");
  setStatus("修改中", 0, state.currentJob.trace_id);
  try {
    const job = await request(`/v1/image/jobs/${state.currentJob.id}/revise`, {
      method: "POST",
      body: {
        output_id: state.selectedOutputId,
        feedback,
        preserve: ["composition", "main_subject"],
        provider_preference: state.selectedProvider,
      },
    });
    state.currentJob = job;
    setStatus(job.status, job.outputs.length, job.trace_id);
    if (job.status !== "ready" || job.outputs.length === 0) {
      showNotice(`修改失败：${jobErrorMessage(job)}`, "error");
      await refreshEvents();
      return;
    }
    renderGallery(job.outputs);
    showNotice("修改版本已生成。", "success");
    els.galleryWrap.scrollIntoView({ behavior: "smooth", block: "start" });
    await refreshHistory({ silent: true });
    await refreshEvents();
  } catch (error) {
    showNotice(`修改失败：${friendlyError(error)}`, "error");
  } finally {
    toggleBusy(false);
  }
}

async function ensureSession() {
  if (!state.sessionId) {
    showNotice("正在准备会话，请稍候。", "info");
    await createSession();
  }
}

function renderGallery(outputs) {
  els.gallery.innerHTML = "";
  els.gallery.classList.remove("loading");
  els.gallery.classList.toggle("empty-gallery", outputs.length === 0);
  state.selectedOutputId = null;
  els.selectedOutputLabel.textContent = "未选";
  updateRevisionState();

  outputs.forEach((output, index) => {
    const node = els.outputTemplate.content.cloneNode(true);
    const card = node.querySelector(".output-card");
    const preview = node.querySelector(".output-preview");
    const id = node.querySelector(".output-id");
    const link = node.querySelector(".download-link");
    preview.dataset.label = `${output.format.toUpperCase()} · ${index + 1}`;
    preview.innerHTML = `<img class="output-image" alt="生成结果 ${index + 1}" src="${output.thumbnail_url || output.url}" loading="lazy" decoding="async" />`;
    id.textContent = output.id;
    link.href = output.url;
    link.download = `${output.id}.${output.format === "jpeg" ? "jpg" : output.format}`;
    preview.addEventListener("click", () => {
      document.querySelectorAll(".output-card").forEach((item) => item.classList.remove("selected"));
      card.classList.add("selected");
      state.selectedOutputId = output.id;
      els.selectedOutputLabel.textContent = output.id.slice(0, 10);
      updateRevisionState();
      openImageLightbox({
        id: output.id,
        title: `生成结果 ${index + 1}`,
        url: output.url,
        format: output.format,
        meta: `${output.format.toUpperCase()} · ${output.width || "-"}x${output.height || "-"}`,
        promptText: promptTextFromJob(state.currentJob),
      });
    });
    els.gallery.appendChild(node);
  });
}

function renderSkeleton(count) {
  els.gallery.innerHTML = "";
  els.gallery.classList.add("loading");
  els.gallery.classList.remove("empty-gallery");
  const total = Math.max(1, Math.min(10, count || 1));
  for (let index = 0; index < total; index += 1) {
    const card = document.createElement("div");
    card.className = "skeleton-card";
    els.gallery.appendChild(card);
  }
}

async function refreshHistory({ silent = false } = {}) {
  if (!els.historyGallery) return;
  els.refreshHistoryBtn.disabled = true;
  try {
    const history = await request("/v1/image/history?limit=1000");
    renderHistory(history.items || []);
    renderHeroHistory(history.items || []);
    if (!silent) {
      showNotice(`已加载 ${history.items?.length || 0} 张历史图片。`, "success");
      showGlobalToast("历史图片已刷新。");
    }
  } catch (error) {
    restartHeroCarousels();
    if (!silent) showNotice(`历史图片加载失败：${friendlyError(error)}`, "error");
  } finally {
    els.refreshHistoryBtn.disabled = false;
  }
}

function renderHistory(items) {
  els.historyGallery.innerHTML = "";
  const sortedItems = [...items].sort(compareHistoryItems);
  els.historyCount.textContent = String(sortedItems.length);
  els.historyGallery.classList.toggle("empty-history", sortedItems.length === 0);
  sortedItems.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = `output-card history-card ${item.source === "repository" ? "" : "readonly"}`;

    const preview = document.createElement("button");
    preview.className = "output-preview";
    preview.type = "button";
    preview.dataset.label = `${item.format.toUpperCase()} · ${item.source === "repository" ? "可编辑" : "历史"}`;

    const image = document.createElement("img");
    image.className = "output-image";
    image.alt = `历史图片 ${index + 1}`;
    image.loading = "lazy";
    image.decoding = "async";
    image.src = item.thumbnail_url || item.url;
    preview.appendChild(image);

    const meta = document.createElement("div");
    meta.className = "history-meta";

    const prompt = document.createElement("p");
    prompt.className = "history-prompt";
    prompt.textContent = item.prompt || "本地历史图片";

    const details = document.createElement("div");
    details.className = "history-detail";
    const model = item.model || item.source;
    details.textContent = historyMetaText(item, model);

    const footer = document.createElement("div");
    footer.className = "output-meta";
    const id = document.createElement("span");
    id.className = "output-id";
    id.textContent = item.id;
    const link = document.createElement("a");
    link.className = "download-link";
    link.href = item.url;
    link.download = `${item.id}.${item.format === "jpeg" ? "jpg" : item.format}`;
    link.textContent = "下载";
    const deleteButton = document.createElement("button");
    deleteButton.className = "delete-link";
    deleteButton.type = "button";
    deleteButton.textContent = "删除";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteHistoryItem(item, card);
    });

    preview.addEventListener("click", () => selectHistoryItem(item, card));
    const actions = document.createElement("div");
    actions.className = "history-card-actions";
    actions.append(link, deleteButton);
    footer.append(id, actions);
    meta.append(prompt, details);
    card.append(preview, meta, footer);
    els.historyGallery.appendChild(card);
  });
}

function renderHeroHistory(items) {
  if (!els.heroHistoryCarousel) return;
  clearHeroCarouselTimer();
  const heroItems = [...items].filter((item) => item.url || item.thumbnail_url).sort(compareHistoryItems);
  state.heroHistoryItems = heroItems;
  els.heroHistoryCarousel.innerHTML = "";
  els.heroHistoryCarousel.classList.toggle("empty-hero-history", heroItems.length === 0);
  if (heroItems.length === 0) {
    const emptySlide = document.createElement("article");
    emptySlide.className = "case-slide active";
    els.heroHistoryCarousel.appendChild(emptySlide);
    restartHeroCarousels();
    return;
  }
  heroItems.forEach((item, index) => {
    const slide = document.createElement("article");
    slide.className = `case-slide ${index === 0 ? "active" : ""}`;

    const image = document.createElement("img");
    image.src = item.thumbnail_url || item.url;
    image.alt = item.prompt || `历史生成作品 ${index + 1}`;
    image.loading = index === 0 ? "eager" : "lazy";
    image.decoding = "async";

    slide.append(image);
    els.heroHistoryCarousel.appendChild(slide);
  });
  restartHeroCarousels();
}

function openActiveHeroHistorySlide() {
  if (!state.heroHistoryItems.length || !els.heroHistoryCarousel) return;
  const slides = Array.from(els.heroHistoryCarousel.querySelectorAll(".case-slide"));
  const activeIndex = Math.max(0, slides.findIndex((slide) => slide.classList.contains("active")));
  const item = state.heroHistoryItems[activeIndex];
  if (!item) return;
  openImageLightbox({
    id: item.id,
    title: item.prompt ? item.prompt.slice(0, 34) : "历史图片",
    url: item.url,
    format: item.format,
    meta: historyMetaText(item),
    promptText: item.prompt || "",
  });
}

function restartHeroCarousels() {
  clearHeroCarouselTimer();
  heroCarouselIndex = 0;
  const carousels = [els.heroHistoryCarousel, els.caseReferenceCarousel].filter(Boolean);
  carousels.forEach((carousel) => {
    carousel.classList.add("synced-carousel");
    activateCarouselSlide(carousel, 0);
  });
  const maxSlideCount = Math.max(0, ...carousels.map((carousel) => carousel.querySelectorAll(".case-slide").length));
  if (maxSlideCount <= 1) return;
  heroCarouselTimer = window.setInterval(() => {
    heroCarouselIndex += 1;
    carousels.forEach((carousel) => {
      const slideCount = carousel.querySelectorAll(".case-slide").length;
      if (slideCount > 1) {
        activateCarouselSlide(carousel, heroCarouselIndex % slideCount);
      }
    });
  }, heroCarouselIntervalMs);
}

function activateCarouselSlide(carousel, activeIndex) {
  const slides = Array.from(carousel.querySelectorAll(".case-slide"));
  slides.forEach((slide, index) => {
    slide.classList.toggle("active", index === activeIndex);
  });
}

function clearHeroCarouselTimer() {
  if (!heroCarouselTimer) return;
  window.clearInterval(heroCarouselTimer);
  heroCarouselTimer = null;
}

function compareHistoryItems(a, b) {
  const timeA = historyTime(a);
  const timeB = historyTime(b);
  if (timeA !== timeB) return timeB - timeA;
  return String(b.id || "").localeCompare(String(a.id || ""));
}

function historyTime(item) {
  const value = item.created_at || item.updated_at;
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

async function deleteHistoryItem(item, card) {
  const confirmed = window.confirm("删除后这张图片将从历史记录中移除，并删除本地文件。确认删除？");
  if (!confirmed) return;
  const deleteButton = card.querySelector(".delete-link");
  if (deleteButton) {
    deleteButton.disabled = true;
    deleteButton.textContent = "删除中";
  }
  try {
    await request(`/v1/image/history/${encodeURIComponent(item.id)}`, { method: "DELETE" });
    card.remove();
    const remaining = els.historyGallery.querySelectorAll(".history-card").length;
    els.historyCount.textContent = String(remaining);
    els.historyGallery.classList.toggle("empty-history", remaining === 0);
    if (state.selectedOutputId === item.id) {
      state.currentJob = null;
      state.selectedOutputId = null;
      els.selectedOutputLabel.textContent = "未选";
      updateRevisionState();
    }
    if (!els.imageLightbox.hidden && els.lightboxDownload.href.includes(encodeURIComponent(item.id))) {
      closeImageLightbox();
    }
    await refreshHistory({ silent: true });
    showNotice("历史图片已删除。", "success");
    showGlobalToast("历史图片已删除。");
  } catch (error) {
    if (deleteButton) {
      deleteButton.disabled = false;
      deleteButton.textContent = "删除";
    }
    showNotice(`删除失败：${friendlyError(error)}`, "error");
  }
}

function selectHistoryItem(item, card) {
  document.querySelectorAll(".output-card, .history-card").forEach((node) => node.classList.remove("selected"));
  card.classList.add("selected");
  openImageLightbox({
    id: item.id,
    title: item.prompt ? item.prompt.slice(0, 34) : "历史图片",
    url: item.url,
    format: item.format,
    meta: historyMetaText(item),
    promptText: item.prompt || "",
  });
  if (item.source !== "repository") {
    state.currentJob = null;
    state.selectedOutputId = null;
    els.selectedOutputLabel.textContent = "只读";
    updateRevisionState();
    showNotice("这张历史图来自本地历史清单，可查看和下载；当前会话缺少任务上下文，不能直接继续修改。", "warning");
    return;
  }
  state.currentJob = { id: item.job_id };
  state.selectedOutputId = item.id;
  els.selectedOutputLabel.textContent = item.id.slice(0, 10);
  updateRevisionState();
  showNotice("历史图片已选中，可以在“继续修改”里生成新版本。", "success");
}

function openImageLightbox({ id, title, url, format, meta, promptText }) {
  els.lightboxTitle.textContent = title || "图片预览";
  els.lightboxImage.src = url;
  els.lightboxImage.alt = title || "放大预览图";
  els.lightboxMeta.textContent = meta || id || "-";
  const fullPrompt = promptText || "";
  els.lightboxPromptText.textContent = fullPrompt || "这张图片没有记录到提示词。";
  els.lightboxPromptBtn.disabled = !fullPrompt;
  els.lightboxPromptBtn.classList.toggle("available", Boolean(fullPrompt));
  closeLightboxPrompt();
  els.lightboxDownload.href = url;
  els.lightboxDownload.download = `${id || "image"}.${format === "jpeg" ? "jpg" : format || "png"}`;
  els.imageLightbox.hidden = false;
  document.body.classList.add("modal-open");
  els.closeImageLightboxBtn.focus();
}

function closeImageLightbox() {
  els.imageLightbox.hidden = true;
  els.lightboxImage.removeAttribute("src");
  closeLightboxPrompt();
  document.body.classList.remove("modal-open");
}

function toggleLightboxPrompt() {
  if (els.lightboxPromptBtn.disabled) return;
  els.lightboxPromptPanel.hidden = !els.lightboxPromptPanel.hidden;
}

function closeLightboxPrompt() {
  els.lightboxPromptPanel.hidden = true;
}

function promptTextFromJob(job) {
  const plan = job?.prompt_plan;
  if (!plan) return "";
  const generationPrompt = plan.variables?.generation_prompt;
  if (generationPrompt) return generationPrompt;
  return [plan.main_subject, plan.scene, plan.style, plan.composition]
    .filter(Boolean)
    .join("\n");
}

async function refreshEvents() {
  const response = await fetch(`/v1/sessions/${state.sessionId}/events`);
  const text = await response.text();
  const rows = text
    .trim()
    .split("\n\n")
    .filter(Boolean)
    .map((block) => {
      const event = block.match(/^event: (.*)$/m)?.[1] || "event";
      const data = block.match(/^data: (.*)$/m)?.[1] || "{}";
      return { event, data };
    });
  renderEvents(rows);
}

function addEvent(event, data) {
  renderEvents([{ event, data }]);
}

function renderEvents(events) {
  els.eventList.innerHTML = "";
  els.eventCount.textContent = String(events.length);
  events.slice(-8).forEach((event) => {
    const row = document.createElement("div");
    row.className = "event-row";
    row.innerHTML = `<strong>${event.event}</strong><span>${escapeHtml(String(event.data))}</span>`;
    els.eventList.appendChild(row);
  });
}

function setStatus(status, outputs, traceId) {
  els.jobStatus.textContent = status;
  els.outputCount.textContent = String(outputs);
  els.traceId.textContent = traceId || "-";
}

function toggleBusy(isBusy) {
  els.generateBtn.disabled = isBusy;
  els.reviseBtn.disabled = isBusy || !state.currentJob || !state.selectedOutputId;
  els.generateBtn.textContent = isBusy ? "生成中..." : "生成图片";
  els.reviseBtn.textContent = isBusy ? "处理中..." : "生成修改版本";
}

function updateRevisionState() {
  els.reviseBtn.disabled = !state.currentJob || !state.selectedOutputId;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail);
  }
  return response.json();
}

function showNotice(message, type = "info") {
  els.noticeBar.textContent = message;
  els.noticeBar.className = `notice-bar ${type === "info" ? "" : type}`.trim();
}

function showGlobalToast(message, type = "success") {
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
    return parsed.detail?.message || parsed.detail?.code || error.message;
  } catch {
    return error.message || String(error);
  }
}

function jobErrorMessage(job) {
  if (!job || !job.error) return job ? job.status : "未知错误";
  if (job.error.code === "rate_limit_error") {
    return "上游并发额度已满，系统已重试但仍未拿到槽位。请稍后再点生成，或继续降低单次生成数量。";
  }
  return job.error.detail?.message || job.error.message || job.error.code || job.status;
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return map[char];
  });
}

function formatDate(value) {
  if (!value) return "未知时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未知时间";
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function historyMetaText(item, model = item.model || item.source) {
  const parts = [model];
  const intensity = item.work_intensity_label || intensityMap[item.work_intensity]?.label;
  if (intensity) parts.push(`强度：${intensity}`);
  parts.push(formatDate(item.created_at || item.updated_at));
  return parts.filter(Boolean).join(" · ");
}
