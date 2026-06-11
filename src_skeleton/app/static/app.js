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
const historyPageSize = 24;
const heroHistoryPageSize = 8;
const v2TemplatePageSize = 48;
const v2HistoryPageSize = 24;
const v2RunLongWaitAttempt = 120;
const v2LocalApiBase = "http://127.0.0.1:8020/api/v2";
const localPortalHomeUrl = "http://127.0.0.1:18080/";
const productionPortalHomeUrl = "https://aiself.vip/";
const v2ApiBase =
  window.ALCHEMY_V2_API_BASE ||
  (window.location.port === "8017" ? v2LocalApiBase : `${window.location.origin}/api/v2`);
const veyraTokenStorageKey = "alchemy_veyra_access_token";
const veyraAccountStorageKey = "alchemy_veyra_account";
const v2ProgressStages = [
  { key: "queued", label: "任务排队", short: "排队中", percent: 8 },
  { key: "planning", label: "中枢规划", short: "规划中", percent: 22 },
  { key: "retrieving_cases", label: "案例匹配", short: "匹配中", percent: 38 },
  { key: "composing_prompt", label: "提示词组合", short: "组词中", percent: 54 },
  { key: "safety_checking", label: "安全检查", short: "检查中", percent: 64 },
  { key: "generating", label: "图像生成", short: "出图中", percent: 76 },
  { key: "reviewing", label: "质量复检", short: "复检中", percent: 90 },
  { key: "completed", label: "完成", short: "已完成", percent: 100 },
  { key: "failed", label: "已停止", short: "已停止", percent: 100 },
];
const v2ProgressByKey = Object.fromEntries(v2ProgressStages.map((stage) => [stage.key, stage]));
const v2StatusStageMap = {
  queued: "queued",
  planning: "planning",
  retrieving_cases: "retrieving_cases",
  composing_prompt: "composing_prompt",
  safety_checking: "safety_checking",
  generating: "generating",
  reviewing: "reviewing",
  completed: "completed",
  failed: "failed",
  cancelled: "failed",
  blocked_by_policy: "failed",
  waiting_for_user: "reviewing",
};
const v2CategoryLabels = {
  "ad-creative": "广告创意",
  ecommerce: "电商主图",
  ui: "界面设计",
  poster: "海报",
  portrait: "人像",
  "brand-visual": "品牌视觉",
  "social-media": "社媒",
};
const v2TagLabels = {
  premium: "高级质感",
  luxury: "奢华",
  cinematic: "电影感",
  "studio-lighting": "棚拍布光",
  minimal: "极简",
  clean: "干净",
  commercial: "商业",
  product: "产品",
  typography: "文字版式",
  photorealistic: "写实",
  editorial: "杂志感",
  ecommerce: "电商",
  poster: "海报",
  portrait: "人像",
  ui: "UI",
  "brand-visual": "品牌视觉",
  "social-media": "社媒",
  "brand-safe": "品牌安全",
  "raw_image_not_final_asset": "参考图不可直用",
  "avoid_real_brand_copying": "避免真实品牌",
  "requires_portrait_authorization": "需肖像授权",
};

const state = {
  sessionId: null,
  assetIds: [],
  assetMode: "basic",
  selectedAssetRoles: ["style_reference"],
  currentJob: null,
  selectedOutputId: null,
  selectedSize: "",
  selectedFormat: "png",
  selectedQuality: "high",
  selectedIntensity: "balanced",
  selectedProvider: "openai_gpt_image",
  selectedLlmProvider: "openai",
  imageProviderReady: false,
  imageProviderCapabilities: {},
  providerSettings: null,
  heroHistoryItems: [],
  heroHistorySource: "v1",
  historyItems: [],
  historyRenderLimit: historyPageSize,
  imageProgressStartedAt: null,
  imageProgressTimer: null,
  imageProgressLabel: "生成中",
};

const v2State = {
  loaded: false,
  loading: false,
  health: null,
  providers: [],
  imageProviderCapabilities: [],
  orchestratorStatus: null,
  modelSettings: null,
  templates: [],
  visibleTemplates: [],
  history: [],
  selectedTemplateId: null,
  selectedTemplateDetail: null,
  templateAutoFields: { subject: "", style: "", useCase: "" },
  activeCaseFacet: "all",
  caseSearchQuery: "",
  templateRenderLimit: v2TemplatePageSize,
  historyRenderLimit: v2HistoryPageSize,
  selectedRatio: "",
  uploadedAssets: [],
  currentRun: null,
  progressStartedAt: null,
  progressStageKey: "queued",
  progressDetail: "",
  progressType: "info",
  progressNoticeKey: "",
  progressTimer: null,
};

const veyraState = {
  account: null,
  history: [],
  usage: [],
  loading: false,
};

let providerSaveTimer = null;
let providerChangeVersion = 0;
let heroCarouselTimer = null;
let heroCarouselIndex = 0;
let activeTabName = "image";
let activeLightboxActions = [];

const els = {
  brandHomeLink: document.querySelector("#brandHomeLink"),
  headerAdminSettingsLink: document.querySelector("#headerAdminSettingsLink"),
  sessionLabel: document.querySelector("#sessionLabel"),
  tabs: document.querySelectorAll("[data-tab]"),
  panels: document.querySelectorAll("[data-panel]"),
  providerList: document.querySelector("#providerList"),
  videoProviderList: document.querySelector("#videoProviderList"),
  v2HealthState: document.querySelector("#v2HealthState"),
  v2ProviderState: document.querySelector("#v2ProviderState"),
  v2ProviderMeta: document.querySelector("#v2ProviderMeta"),
  v2IndexState: document.querySelector("#v2IndexState"),
  v2SyncMeta: document.querySelector("#v2SyncMeta"),
  v2InheritedProviderState: document.querySelector("#v2InheritedProviderState"),
  v2InheritedModelMeta: document.querySelector("#v2InheritedModelMeta"),
  v2ProviderModelState: document.querySelector("#v2ProviderModelState"),
  v2ModelSummary: document.querySelector("#v2ModelSummary"),
  v2ImageActiveLabel: document.querySelector("#v2ImageActiveLabel"),
  v2OpenaiImageState: document.querySelector("#v2OpenaiImageState"),
  v2GeminiImageState: document.querySelector("#v2GeminiImageState"),
  v2BrainActiveLabel: document.querySelector("#v2BrainActiveLabel"),
  v2BrainModelState: document.querySelector("#v2BrainModelState"),
  v2ImageProviderInput: document.querySelector("#v2ImageProviderInput"),
  v2AgentModelInput: document.querySelector("#v2AgentModelInput"),
  v2ClaudeModelInput: document.querySelector("#v2ClaudeModelInput"),
  v2ClaudeFallbackModelInput: document.querySelector("#v2ClaudeFallbackModelInput"),
  v2CaseIntelligenceProviderInput: document.querySelector("#v2CaseIntelligenceProviderInput"),
  v2CaseIntelligenceModelInput: document.querySelector("#v2CaseIntelligenceModelInput"),
  v2ReviewModelInput: document.querySelector("#v2ReviewModelInput"),
  v2ModelApplyBtn: document.querySelector("#v2ModelApplyBtn"),
  v2RefreshBtn: document.querySelector("#v2RefreshBtn"),
  v2SeedSyncBtn: document.querySelector("#v2SeedSyncBtn"),
  v2RemoteSyncBtn: document.querySelector("#v2RemoteSyncBtn"),
  v2TemplateCount: document.querySelector("#v2TemplateCount"),
  v2TemplateSearch: document.querySelector("#v2TemplateSearch"),
  v2TemplateSearchBtn: document.querySelector("#v2TemplateSearchBtn"),
  v2SearchThinking: document.querySelector("#v2SearchThinking"),
  v2CaseFacetBar: document.querySelector("#v2CaseFacetBar"),
  v2TemplateGrid: document.querySelector("#v2TemplateGrid"),
  v2ModeState: document.querySelector("#v2ModeState"),
  v2PromptInput: document.querySelector("#v2PromptInput"),
  v2NoticeBar: document.querySelector("#v2NoticeBar"),
  v2ProgressPanel: document.querySelector("#v2ProgressPanel"),
  v2ProgressTitle: document.querySelector("#v2ProgressTitle"),
  v2ProgressElapsed: document.querySelector("#v2ProgressElapsed"),
  v2ProgressFill: document.querySelector("#v2ProgressFill"),
  v2ProgressSteps: document.querySelector("#v2ProgressSteps"),
  v2ProgressDetail: document.querySelector("#v2ProgressDetail"),
  v2RunBtn: document.querySelector("#v2RunBtn"),
  v2SelectedTemplateLabel: document.querySelector("#v2SelectedTemplateLabel"),
  v2CountInput: document.querySelector("#v2CountInput"),
  v2CountValue: document.querySelector("#v2CountValue"),
  v2AssetInput: document.querySelector("#v2AssetInput"),
  v2AssetName: document.querySelector("#v2AssetName"),
  v2AssetPreview: document.querySelector("#v2AssetPreview"),
  v2AssetPreviewLabel: document.querySelector("#v2AssetPreviewLabel"),
  v2AssetState: document.querySelector("#v2AssetState"),
  v2AssetStrengthInput: document.querySelector("#v2AssetStrengthInput"),
  v2AssetNotesInput: document.querySelector("#v2AssetNotesInput"),
  v2AssetList: document.querySelector("#v2AssetList"),
  v2ClearAssetBtn: document.querySelector("#v2ClearAssetBtn"),
  v2AssetLockHint: document.querySelector("#v2AssetLockHint"),
  v2ClearTemplateBtn: document.querySelector("#v2ClearTemplateBtn"),
  v2SubjectInput: document.querySelector("#v2SubjectInput"),
  v2StyleInput: document.querySelector("#v2StyleInput"),
  v2UseCaseInput: document.querySelector("#v2UseCaseInput"),
  v2SelectedCases: document.querySelector("#v2SelectedCases"),
  v2BrainPanel: document.querySelector("#v2BrainPanel"),
  v2PromptPlan: document.querySelector("#v2PromptPlan"),
  v2Outputs: document.querySelector("#v2Outputs"),
  v2TraceId: document.querySelector("#v2TraceId"),
  v2HistoryCount: document.querySelector("#v2HistoryCount"),
  v2RefreshHistoryBtn: document.querySelector("#v2RefreshHistoryBtn"),
  v2HistoryGrid: document.querySelector("#v2HistoryGrid"),
  veyraAccountState: document.querySelector("#veyraAccountState"),
  veyraAccountEmail: document.querySelector("#veyraAccountEmail"),
  veyraAccountBalance: document.querySelector("#veyraAccountBalance"),
  veyraAccountStatus: document.querySelector("#veyraAccountStatus"),
  veyraAccountUserId: document.querySelector("#veyraAccountUserId"),
  veyraAccountHistoryCount: document.querySelector("#veyraAccountHistoryCount"),
  veyraAccountHistoryScope: document.querySelector("#veyraAccountHistoryScope"),
  veyraAccountHistoryTitle: document.querySelector("#veyraAccountHistoryTitle"),
  veyraAccountUsageTotal: document.querySelector("#veyraAccountUsageTotal"),
  veyraRefreshAccountBtn: document.querySelector("#veyraRefreshAccountBtn"),
  veyraAccountHistoryGrid: document.querySelector("#veyraAccountHistoryGrid"),
  veyraUsageList: document.querySelector("#veyraUsageList"),
  providerState: document.querySelector("#providerState"),
  openaiApiKeyInput: document.querySelector("#openaiApiKeyInput"),
  openaiBaseUrlInput: document.querySelector("#openaiBaseUrlInput"),
  openaiImageModelInput: document.querySelector("#openaiImageModelInput"),
  geminiImageModelInput: document.querySelector("#geminiImageModelInput"),
  geminiImageBaseUrlInput: document.querySelector("#geminiImageBaseUrlInput"),
  geminiImageApiKeyInput: document.querySelector("#geminiImageApiKeyInput"),
  openaiLlmModelInput: document.querySelector("#openaiLlmModelInput"),
  agentLlmModelInput: document.querySelector("#agentLlmModelInput"),
  anthropicBaseUrlInput: document.querySelector("#anthropicBaseUrlInput"),
  anthropicApiKeyInput: document.querySelector("#anthropicApiKeyInput"),
  imageActiveLabel: document.querySelector("#imageActiveLabel"),
  thinkingActiveLabel: document.querySelector("#thinkingActiveLabel"),
  openaiImageState: document.querySelector("#openaiImageState"),
  geminiImageState: document.querySelector("#geminiImageState"),
  openaiThinkingState: document.querySelector("#openaiThinkingState"),
  agentThinkingState: document.querySelector("#agentThinkingState"),
  intensityValue: document.querySelector("#intensityValue"),
  assetInput: document.querySelector("#assetInput"),
  assetName: document.querySelector("#assetName"),
  assetPreview: document.querySelector("#assetPreview"),
  assetPreviewLabel: document.querySelector("#assetPreviewLabel"),
  assetState: document.querySelector("#assetState"),
  advancedAssetPanel: document.querySelector("#advancedAssetPanel"),
  assetStrengthInput: document.querySelector("#assetStrengthInput"),
  assetStrengthValue: document.querySelector("#assetStrengthValue"),
  assetPreservationInput: document.querySelector("#assetPreservationInput"),
  assetPlacementField: document.querySelector("#assetPlacementField"),
  assetPlacementInput: document.querySelector("#assetPlacementInput"),
  assetIntentNotesInput: document.querySelector("#assetIntentNotesInput"),
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
  lightboxStage: document.querySelector(".lightbox-stage"),
  lightboxImage: document.querySelector("#lightboxImage"),
  lightboxTitle: document.querySelector("#lightboxTitle"),
  lightboxMeta: document.querySelector("#lightboxMeta"),
  lightboxPromptBtn: document.querySelector("#lightboxPromptBtn"),
  lightboxPromptPanel: document.querySelector("#lightboxPromptPanel"),
  lightboxPromptText: document.querySelector("#lightboxPromptText"),
  copyPromptBtn: document.querySelector("#copyPromptBtn"),
  closePromptPanelBtn: document.querySelector("#closePromptPanelBtn"),
  lightboxDownload: document.querySelector("#lightboxDownload"),
  lightboxActionBar: document.querySelector("#lightboxActionBar"),
  closeImageLightboxBtn: document.querySelector("#closeImageLightboxBtn"),
};

document.addEventListener("DOMContentLoaded", async () => {
  hydratePortalHomeLink();
  hydrateCachedVeyraAccount();
  bindControls();
  const hadVeyraTicket = new URLSearchParams(window.location.search).has("ticket");
  try {
    await handleVeyraTicketFromUrl();
    if (getVeyraToken() && !hadVeyraTicket) {
      loadVeyraAccountPanel({ silent: true, force: true }).catch(() => {
        veyraState.account = null;
        updateAdminSettingsEntry();
      });
    } else {
      updateAdminSettingsEntry();
    }
    await createSession({ announce: false });
    await loadProviders();
    await refreshHistory({ silent: true });
    initV2({ silent: true }).catch((error) => {
      updateV2Notice(`2.0 API 未连接：${friendlyError(error)}`, "warning");
      if (els.v2HealthState) els.v2HealthState.textContent = "离线";
    });
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
      state.selectedSize = button.dataset.size || "";
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

  document.querySelectorAll("[data-asset-role]").forEach((button) => {
    button.addEventListener("change", syncAdvancedAssetRoles);
  });

  if (els.assetStrengthInput) {
    els.assetStrengthInput.addEventListener("input", () => {
      els.assetStrengthValue.textContent = `${els.assetStrengthInput.value}%`;
    });
  }

  document.querySelectorAll("[data-llm-provider]").forEach((button) => {
    button.addEventListener("click", () => setThinkingProvider(button.dataset.llmProvider, { persist: true }));
  });

  document.querySelectorAll("[data-v2-image-provider]").forEach((button) => {
    button.addEventListener("click", () => setV2ImageProvider(button.dataset.v2ImageProvider, { persist: true }));
  });

  els.assetInput.addEventListener("change", handleAsset);
  els.generateBtn.addEventListener("click", generateImage);
  els.reviseBtn.addEventListener("click", reviseSelectedOutput);
  els.refreshHistoryBtn.addEventListener("click", () => refreshHistory({ silent: false }));
  els.heroHistoryCarousel.addEventListener("click", openActiveHeroHistorySlide);
  if (els.v2RefreshBtn) els.v2RefreshBtn.addEventListener("click", () => initV2({ silent: false, force: true }));
  if (els.v2ModelApplyBtn) els.v2ModelApplyBtn.addEventListener("click", applyV2ModelSettings);
  if (els.v2CaseIntelligenceProviderInput) {
    els.v2CaseIntelligenceProviderInput.addEventListener("change", hydrateV2CaseIntelligenceModelHint);
  }
  if (els.v2SeedSyncBtn) els.v2SeedSyncBtn.addEventListener("click", () => syncV2Provider("seed"));
  if (els.v2RemoteSyncBtn) els.v2RemoteSyncBtn.addEventListener("click", () => syncV2Provider("remote"));
  if (els.v2TemplateSearchBtn) els.v2TemplateSearchBtn.addEventListener("click", searchV2Templates);
  if (els.v2TemplateSearch) {
    els.v2TemplateSearch.addEventListener("keydown", (event) => {
      if (event.key === "Enter") searchV2Templates();
    });
  }
  if (els.v2CountInput) {
    els.v2CountInput.addEventListener("input", () => {
      els.v2CountValue.textContent = els.v2CountInput.value;
    });
  }
  if (els.v2AssetInput) els.v2AssetInput.addEventListener("change", handleV2Asset);
  document.querySelectorAll("[data-v2-asset-role]").forEach((input) => {
    input.addEventListener("change", renderV2AssetPanel);
  });
  if (els.v2AssetStrengthInput) els.v2AssetStrengthInput.addEventListener("change", renderV2AssetPanel);
  if (els.v2AssetNotesInput) els.v2AssetNotesInput.addEventListener("input", renderV2AssetPanel);
  if (els.v2ClearAssetBtn) els.v2ClearAssetBtn.addEventListener("click", clearV2Asset);
  document.querySelectorAll("[data-v2-ratio]").forEach((button) => {
    button.addEventListener("click", () => {
      setActive(button, "[data-v2-ratio]");
      v2State.selectedRatio = button.dataset.v2Ratio || "";
    });
  });
  if (els.v2ClearTemplateBtn) els.v2ClearTemplateBtn.addEventListener("click", clearV2Template);
  if (els.v2RefreshHistoryBtn) els.v2RefreshHistoryBtn.addEventListener("click", () => loadV2History({ silent: false }));
  if (els.veyraRefreshAccountBtn) els.veyraRefreshAccountBtn.addEventListener("click", () => loadVeyraAccountPanel({ silent: false, force: true }));
  if (els.v2RunBtn) els.v2RunBtn.addEventListener("click", runV2Creative);
  bindProviderAutosave();
  els.newSessionBtn.addEventListener("click", startNewSession);
  els.smokeBtn.addEventListener("click", openSampleGuide);
  els.closeSampleGuideBtn.addEventListener("click", closeSampleGuide);
  els.closeImageLightboxBtn.addEventListener("click", closeImageLightbox);
  els.lightboxImage.addEventListener("click", toggleLightboxZoom);
  els.lightboxPromptBtn.addEventListener("click", toggleLightboxPrompt);
  els.copyPromptBtn.addEventListener("click", copyLightboxPrompt);
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
  activeTabName = tabName || "image";
  els.tabs.forEach((button) => {
    const active = button.dataset.tab === tabName;
    button.classList.toggle("active", active);
    if (button.getAttribute("role") === "tab") {
      button.setAttribute("aria-selected", String(active));
    } else {
      button.setAttribute("aria-pressed", String(active));
    }
  });
  els.panels.forEach((panel) => {
    const active = panel.dataset.panel === tabName;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
  if (tabName === "v2" && !v2State.loaded && !v2State.loading) {
    initV2({ silent: false }).catch((error) => {
      updateV2Notice(`2.0 API 未连接：${friendlyError(error)}`, "warning");
    });
  } else if (tabName === "v2") {
    renderHeroHistory(v2State.history, { source: "v2" });
  } else if (tabName === "account") {
    renderHeroHistory(v2State.history, { source: "v2" });
    loadVeyraAccountPanel({ silent: true }).catch((error) => {
      showGlobalToast(`账户加载失败：${friendlyError(error)}`, "error");
    });
  } else {
    renderHeroHistory(state.historyItems, { source: "v1" });
  }
}

function hydratePortalHomeLink() {
  if (!els.brandHomeLink) return;
  const configuredUrl =
    typeof window.VEYRA_PORTAL_URL === "string" && window.VEYRA_PORTAL_URL.trim()
      ? window.VEYRA_PORTAL_URL.trim()
      : "";
  const localHostnames = new Set(["127.0.0.1", "localhost", "::1"]);
  const portalUrl = configuredUrl || (localHostnames.has(window.location.hostname) ? localPortalHomeUrl : productionPortalHomeUrl);
  els.brandHomeLink.href = portalUrl;
}

function setActive(activeButton, selector) {
  document.querySelectorAll(selector).forEach((button) => button.classList.remove("active"));
  activeButton.classList.add("active");
}

function setAssetMode(mode) {
  state.assetMode = mode === "advanced" ? "advanced" : "basic";
  if (els.advancedAssetPanel) {
    els.advancedAssetPanel.hidden = false;
  }
  if (els.assetState) {
    els.assetState.textContent = state.assetIds.length ? "高级" : "空";
  }
}

function selectedAssetRolesFromDom() {
  return Array.from(document.querySelectorAll("[data-asset-role]:checked"))
    .map((input) => input.dataset.assetRole)
    .filter(Boolean);
}

function setAdvancedAssetRoles(roles = ["style_reference"]) {
  const selectedRoles = roles.length ? roles : ["style_reference"];
  state.selectedAssetRoles = selectedRoles;
  document.querySelectorAll("[data-asset-role]").forEach((input) => {
    input.checked = selectedRoles.includes(input.dataset.assetRole);
  });
  renderAdvancedAssetRoles();
}

function syncAdvancedAssetRoles() {
  state.selectedAssetRoles = selectedAssetRolesFromDom();
  renderAdvancedAssetRoles();
}

function renderAdvancedAssetRoles() {
  const roles = state.selectedAssetRoles.length ? state.selectedAssetRoles : [];
  if (els.assetPlacementField) {
    els.assetPlacementField.hidden = !roles.includes("logo_overlay");
  }
  if (els.assetPreservationInput) {
    if (roles.includes("logo_overlay")) els.assetPreservationInput.value = "exact";
    else if (roles.some((role) => ["subject_reference", "portrait_identity"].includes(role))) els.assetPreservationInput.value = "strict";
    else if (roles.length === 1 && roles.includes("style_reference")) els.assetPreservationInput.value = "loose";
    else els.assetPreservationInput.value = "medium";
  }
}

function primaryAssetRole() {
  const priority = ["logo_overlay", "portrait_identity", "subject_reference", "style_reference", "background_reference", "composition_reference"];
  return priority.find((role) => state.selectedAssetRoles.includes(role)) || state.selectedAssetRoles[0] || "style_reference";
}

function assetRolePriority(role) {
  if (role === "logo_overlay") return 100;
  if (role === "portrait_identity" || role === "subject_reference") return 90;
  if (role === "style_reference") return 80;
  return 70;
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
    state.selectedProvider = isImageProviderUsable("openai_gpt_image") ? "openai_gpt_image" : requested;
    showNotice("Gemini 生图 API 尚未配置；保存 Gemini API Key 后即可切换。", "warning");
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
    els.agentLlmModelInput,
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
  els.assetName.textContent = "仅支持图片素材";
  els.assetState.textContent = "空";
  els.assetInput.value = "";
  setAssetMode("basic");
  setAdvancedAssetRoles(["style_reference"]);
  if (els.assetIntentNotesInput) els.assetIntentNotesInput.value = "";
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
    if (activeTabName === "v2") {
      resetV2Session();
      switchTab("v2");
      els.v2PromptInput?.focus();
    } else {
      await createSession();
      switchTab("image");
      els.promptInput.value = "";
      els.countInput.value = defaultImageCount;
      els.countValue.textContent = defaultImageCount;
      setSize("");
      setFormat("png");
      setQuality("high");
      els.promptInput.focus();
    }
  } catch (error) {
    showNotice(`新会话创建失败：${friendlyError(error)}`, "error");
    showGlobalToast("新会话创建失败。", "error");
  } finally {
    els.newSessionBtn.disabled = false;
    els.newSessionBtn.textContent = originalText;
  }
}

function resetV2Session() {
  v2State.selectedTemplateId = null;
  v2State.selectedTemplateDetail = null;
  v2State.templateAutoFields = { subject: "", style: "", useCase: "" };
  v2State.selectedRatio = "";
  v2State.uploadedAssets = [];
  v2State.currentRun = null;
  resetV2Progress();
  if (els.v2PromptInput) els.v2PromptInput.value = "";
  if (els.v2SubjectInput) els.v2SubjectInput.value = "";
  if (els.v2StyleInput) els.v2StyleInput.value = "";
  if (els.v2UseCaseInput) els.v2UseCaseInput.value = "";
  if (els.v2CountInput) els.v2CountInput.value = defaultImageCount;
  if (els.v2CountValue) els.v2CountValue.textContent = defaultImageCount;
  const defaultRatioButton = document.querySelector('[data-v2-ratio=""]');
  if (defaultRatioButton) setActive(defaultRatioButton, "[data-v2-ratio]");
  if (els.v2SelectedTemplateLabel) els.v2SelectedTemplateLabel.textContent = "未选择模板";
  if (els.v2ModeState) els.v2ModeState.textContent = "智能增强";
  clearV2Asset({ keepNotice: true });
  clearV2RunResult();
  renderV2Templates(v2State.visibleTemplates);
  renderV2AssetPanel();
  renderHeroHistory(v2State.history, { source: "v2" });
  updateV2Notice("V2.0 新会话已准备好。", "success");
  showGlobalToast("V2.0 新会话已创建。");
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
  els.geminiImageModelInput.value = runtime.gemini_image_model || "gemini-3-pro-image-preview";
  els.openaiLlmModelInput.value = runtime.openai_llm_model || "gpt-5.5";
  els.agentLlmModelInput.value = runtime.kimi_llm_model || "kimi-for-coding";
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
  els.geminiImageState.textContent = gemini?.configured ? runtime.gemini_image_model : "需 API";
  els.openaiThinkingState.textContent = runtime.openai_api_key_configured ? runtime.openai_llm_model : "需 API";
  els.agentThinkingState.textContent = runtime.anthropic_api_key_configured ? runtime.kimi_llm_model || "已配置" : "需 Kimi API";
  els.providerState.textContent = state.imageProviderReady ? `${providerLabel(state.selectedProvider)} ready` : "需要 API";
  renderV2ModelSettings();
  renderV2ProviderInheritance();
  setImageProviderAvailability("openai_gpt_image", Boolean(openai?.configured), "");
  setImageProviderAvailability(
    "gemini_image",
    Boolean(gemini?.configured),
    gemini?.configured ? "" : "填写 Gemini API Key 后即可选择。"
  );

  if (state.imageProviderReady) {
    showNotice(`模型已就绪：生图 ${providerLabel(state.selectedProvider)}；思考 ${thinkingProviderLabel(state.selectedLlmProvider)}。`, "success");
  } else {
    showNotice("请在高级 API 配置里保存 OpenAI 或 Gemini API Key 后生成图片。", "warning");
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
  badge.textContent = provider.configured ? "已接入" : ["openai_gpt_image", "gemini_image"].includes(provider.provider) ? "需 API" : "未接入";
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
    openai_gpt_image: "GPT Image 2",
    gemini_image: "Gemini Image",
    mock_image: "Mock Image",
    seedance: "Seedance Video",
  };
  return labels[provider] || provider;
}

function providerResultText({ requestedProvider, actualProvider, actualModel, fallback }) {
  const from = fallback?.from || requestedProvider;
  const to = fallback?.to || actualProvider;
  const actual = providerLabel(to || actualProvider || "image");
  const model = actualModel ? ` · ${actualModel}` : "";
  if (from && to && from !== to) {
    return `${providerLabel(from)} → ${actual} 兜底${model}`;
  }
  return `${actual}${model}`;
}

function providerInputSummaryFromJob(job) {
  const plan = job?.asset_plan?.provider_input_plan || job?.prompt_plan?.variables?.provider_input_plan;
  const outputMeta = job?.outputs?.[0]?.metadata || {};
  const referenceCount = plan?.reference_image_count ?? outputMeta.reference_image_count;
  const operation = plan?.operation || outputMeta.api_operation;
  if (!referenceCount && !operation) return "";
  const chunks = [];
  if (referenceCount) chunks.push(`参考图 ${referenceCount} 张`);
  if (operation) chunks.push(providerInputOperationLabel(operation));
  return chunks.join(" · ");
}

function imageProviderResultText(job) {
  if (!job) return "生图模型";
  const providerText = providerResultText({
    requestedProvider: job.raw_response_summary?.requested_image_provider,
    actualProvider: job.provider,
    actualModel: job.model,
    fallback: job.raw_response_summary?.image_provider_fallback,
  });
  const inputSummary = providerInputSummaryFromJob(job);
  return inputSummary ? `${providerText} · ${inputSummary}` : providerText;
}

function outputProviderResultText(output, job) {
  const metadata = output?.metadata || {};
  return providerResultText({
    requestedProvider: metadata.requested_provider || job?.raw_response_summary?.requested_image_provider,
    actualProvider: metadata.actual_provider || job?.provider,
    actualModel: metadata.actual_model || job?.model,
    fallback: metadata.provider_fallback || job?.raw_response_summary?.image_provider_fallback,
  });
}

function historyProviderResultText(item) {
  return providerResultText({
    requestedProvider: item?.requested_provider,
    actualProvider: item?.provider,
    actualModel: item?.model,
    fallback: item?.provider_fallback,
  });
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
      gemini_image_model: els.geminiImageModelInput.value.trim() || "gemini-3-pro-image-preview",
      gemini_image_base_url: els.geminiImageBaseUrlInput.value.trim(),
      default_llm_provider: state.selectedLlmProvider,
      default_llm_model: selectedThinkingModel(),
      openai_llm_model: els.openaiLlmModelInput.value.trim() || "gpt-5.5",
      kimi_llm_model: els.agentLlmModelInput.value.trim() || "kimi-for-coding",
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
    return els.geminiImageModelInput.value.trim() || "gemini-3-pro-image-preview";
  }
  return els.openaiImageModelInput.value.trim() || "gpt-image-2";
}

function selectedThinkingModel() {
  if (state.selectedLlmProvider === "anthropic") {
    return els.agentLlmModelInput.value.trim() || "kimi-for-coding";
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

async function initV2({ silent = true, force = false } = {}) {
  if (!force && v2State.loaded) {
    renderV2ProviderInheritance();
    renderV2AssetPanel();
    return;
  }
  v2State.loading = true;
  toggleV2Loading(true);
  updateV2Notice("正在检查 V2.0 Agent 中枢。", "info");
  try {
    const [health, providersResponse, imageProviderCapabilities, templatesResponse, historyResponse, orchestratorStatus, modelSettings] = await Promise.all([
      v2Request("/health"),
      v2Request("/resource-providers"),
      v2Request("/provider-capabilities"),
      v2Request("/templates?limit=1000"),
      loadV2HistoryResponse(),
      v2Request("/orchestrator/status"),
      v2Request("/runtime/model-settings"),
    ]);
    v2State.health = health;
    v2State.providers = providersResponse.providers || [];
    v2State.imageProviderCapabilities = imageProviderCapabilities.providers || [];
    v2State.orchestratorStatus = orchestratorStatus;
    v2State.modelSettings = modelSettings;
    v2State.templates = templatesResponse.templates || [];
    v2State.templateRenderLimit = v2TemplatePageSize;
    v2State.historyRenderLimit = v2HistoryPageSize;
    v2State.visibleTemplates = v2State.templates;
    v2State.history = historyResponse.items || [];
    v2State.loaded = true;
    renderV2Health(health);
    renderV2Providers(v2State.providers);
    renderV2CaseFacets(v2State.templates);
    renderV2Templates(v2State.visibleTemplates);
    renderV2History(v2State.history);
    if (activePanelName() === "v2") renderHeroHistory(v2State.history, { source: "v2" });
    renderV2ModelSettings();
    renderV2ProviderInheritance();
    renderV2Brain(null, orchestratorStatus);
    renderV2AssetPanel();
    updateV2Notice(silent ? "V2.0 Agent 中枢待命。" : "V2.0 Agent 中枢已就绪。", "success");
  } catch (error) {
    v2State.loaded = false;
    if (els.v2HealthState) els.v2HealthState.textContent = "离线";
    updateV2Notice(`2.0 初始化失败：${friendlyError(error)}`, "error");
    throw error;
  } finally {
    v2State.loading = false;
    toggleV2Loading(false);
  }
}

function renderV2ModelSettings() {
  const settings = v2State.modelSettings;
  if (!settings) {
    if (els.v2ModelSummary) els.v2ModelSummary.textContent = "等待 V2 后端";
    renderV2ModelCards({});
    return;
  }
  const selectedImageProvider = v2EffectiveImageProvider(settings);
  setInputValue(els.v2ImageProviderInput, selectedImageProvider || "auto");
  setInputValue(els.v2AgentModelInput, settings.default_agent_model || "gpt-4.1-mini");
  setInputValue(els.v2ClaudeModelInput, settings.claude_orchestrator_model || "");
  setInputValue(els.v2ClaudeFallbackModelInput, settings.claude_orchestrator_fallback_model || "");
  setInputValue(els.v2CaseIntelligenceProviderInput, settings.case_intelligence_provider || "rules");
  setInputValue(els.v2CaseIntelligenceModelInput, settings.case_intelligence_model || "");
  setInputValue(els.v2ReviewModelInput, settings.output_review_agent_model || "");

  const imageModel = v2ImageModelName(selectedImageProvider, settings);
  const claudeModel = settings.claude_orchestrator_model || "Claude Code 默认模型";
  const caseSource = v2CaseIntelligenceSourceLabel(settings.case_intelligence_provider);
  if (els.v2ModelSummary) {
    els.v2ModelSummary.textContent = `生图 ${imageModel} · 中枢 ${claudeModel} · 案例理解 ${caseSource}`;
  }
  renderV2ModelCards(settings);
  hydrateV2CaseIntelligenceModelHint();
}

function renderV2ModelCards(settings = v2State.modelSettings || {}) {
  const provider = v2EffectiveImageProvider(settings);
  document.querySelectorAll("[data-v2-image-provider]").forEach((button) => {
    const isActive = button.dataset.v2ImageProvider === provider;
    const capability = v2ProviderCapability(button.dataset.v2ImageProvider);
    const isConfigured = v2ImageProviderConfigured(button.dataset.v2ImageProvider);
    button.classList.toggle("active", isActive);
    button.disabled = !isConfigured;
    button.title = isConfigured ? "" : capability?.reason || "请先配置 V2 生图通道的 API Key。";
  });
  if (els.v2ImageActiveLabel) {
    els.v2ImageActiveLabel.textContent = v2ImageChannelLabel(provider);
  }
  if (els.v2OpenaiImageState) {
    const capability = v2ProviderCapability("openai_gpt_image");
    els.v2OpenaiImageState.textContent = settings.openai_api_key_configured
      ? capability?.configured === false
        ? "不可用"
        : settings.openai_image_model || "gpt-image-2"
      : "需 V2 API";
  }
  if (els.v2GeminiImageState) {
    const capability = v2ProviderCapability("gemini_image");
    els.v2GeminiImageState.textContent = settings.gemini_api_key_configured
      ? capability?.configured === false
        ? "模型不可生图"
        : settings.gemini_image_model || "gemini-2.5-flash-image"
      : "需 V2 API";
  }
  if (els.v2BrainActiveLabel) els.v2BrainActiveLabel.textContent = "Claude Code";
  if (els.v2BrainModelState) {
    els.v2BrainModelState.textContent = settings.claude_orchestrator_model || v2State.orchestratorStatus?.model || "默认模型";
  }
}

function v2EffectiveImageProvider(settings = v2State.modelSettings || {}) {
  const configured = settings.image_generation_provider;
  if (["openai_gpt_image", "gemini_image"].includes(configured) && v2ImageProviderConfigured(configured, settings)) {
    return configured;
  }
  if (configured === "mock_image" && settings.persisted) return "mock_image";
  const liveProvider = v2PreferredLiveImageProvider(settings);
  if (liveProvider) return liveProvider;
  return "mock_image";
}

function v2RequestedImageProvider(settings = v2State.modelSettings || {}) {
  const selected = els.v2ImageProviderInput?.value || "";
  if (["openai_gpt_image", "gemini_image", "mock_image"].includes(selected) && v2ImageProviderConfigured(selected, settings)) {
    return selected;
  }
  return v2EffectiveImageProvider(settings);
}

function v2PreferredLiveImageProvider(settings = v2State.modelSettings || {}) {
  if (v2ImageProviderConfigured("openai_gpt_image", settings)) return "openai_gpt_image";
  if (v2ImageProviderConfigured("gemini_image", settings)) return "gemini_image";
  return "";
}

function v2ImageProviderConfigured(provider, settings = v2State.modelSettings || {}) {
  if (provider === "mock_image") return true;
  const capability = v2ProviderCapability(provider);
  if (capability && capability.configured === false) return false;
  if (provider === "gemini_image") return Boolean(settings.gemini_api_key_configured);
  if (provider === "openai_gpt_image") return Boolean(settings.openai_api_key_configured);
  return false;
}

function v2ProviderCapability(provider) {
  return (v2State.imageProviderCapabilities || []).find((item) => item.provider === provider) || null;
}

function v2ImageModelName(provider, settings = v2State.modelSettings || {}) {
  if (provider === "gemini_image") return settings.gemini_image_model || "gemini-2.5-flash-image";
  if (provider === "mock_image") return "mock-image-v2-native";
  return settings.openai_image_model || "gpt-image-2";
}

async function setV2ImageProvider(provider, { persist = false } = {}) {
  const requested = ["openai_gpt_image", "gemini_image", "mock_image"].includes(provider) ? provider : "openai_gpt_image";
  if (!v2ImageProviderConfigured(requested)) {
    updateV2Notice("请先配置 V2 生图通道的 API Key。", "warning");
    renderV2ModelCards();
    return;
  }
  if (els.v2ImageProviderInput) els.v2ImageProviderInput.value = requested;
  v2State.modelSettings = {
    ...(v2State.modelSettings || {}),
    image_generation_provider: requested,
  };
  renderV2ModelCards(v2State.modelSettings);
  renderV2ProviderInheritance();
  if (persist) await applyV2ModelSettings();
}

function setInputValue(input, value) {
  if (!input || document.activeElement === input) return;
  input.value = value;
}

function v2CaseIntelligenceSourceLabel(value) {
  const labels = {
    rules: "本地案例画像",
    "claude-code": "Claude Code",
  };
  return labels[value] || value || "本地案例画像";
}

function hydrateV2CaseIntelligenceModelHint() {
  if (!els.v2CaseIntelligenceProviderInput || !els.v2CaseIntelligenceModelInput) return;
  const source = els.v2CaseIntelligenceProviderInput.value;
  if (source === "claude-code") {
    els.v2CaseIntelligenceModelInput.placeholder = els.v2ClaudeModelInput?.value || "Claude Code 默认模型";
  } else {
    els.v2CaseIntelligenceModelInput.placeholder = "本地案例画像不调用 LLM";
  }
}

async function applyV2ModelSettings() {
  if (!els.v2ModelApplyBtn) return;
  const originalText = els.v2ModelApplyBtn.textContent;
  els.v2ModelApplyBtn.disabled = true;
  els.v2ModelApplyBtn.textContent = "应用中";
  updateV2Notice("正在应用 V2 模型配置。", "info");
  try {
    const caseSource = els.v2CaseIntelligenceProviderInput?.value || "rules";
    const caseModel =
      els.v2CaseIntelligenceModelInput?.value.trim()
      || (caseSource === "claude-code" ? els.v2ClaudeModelInput?.value.trim() : "");
    const response = await v2Request("/runtime/model-settings", {
      method: "POST",
      body: {
        image_generation_provider: els.v2ImageProviderInput?.value || "auto",
        default_agent_model: els.v2AgentModelInput?.value.trim() || "gpt-4.1-mini",
        output_review_agent_enabled: true,
        output_review_agent_model: els.v2ReviewModelInput?.value.trim(),
        claude_orchestrator_enabled: true,
        claude_orchestrator_model: els.v2ClaudeModelInput?.value.trim(),
        claude_orchestrator_fallback_model: els.v2ClaudeFallbackModelInput?.value.trim(),
        case_intelligence_provider: caseSource,
        case_intelligence_model: caseModel,
      },
    });
    v2State.modelSettings = response;
    v2State.orchestratorStatus = await v2Request("/orchestrator/status");
    renderV2ModelSettings();
    renderV2ProviderInheritance();
    renderV2Brain(v2State.currentRun?.orchestrator_decision || null, v2State.orchestratorStatus);
    updateV2Notice("V2 模型配置已生效。", "success");
    showGlobalToast("V2 模型配置已应用。");
  } catch (error) {
    updateV2Notice(`V2 模型配置失败：${friendlyError(error)}`, "error");
  } finally {
    els.v2ModelApplyBtn.disabled = false;
    els.v2ModelApplyBtn.textContent = originalText;
  }
}

function renderV2Health(health) {
  if (!els.v2HealthState) return;
  els.v2HealthState.textContent = health?.agents_sdk_available ? "Agents SDK" : "Fallback";
}

function renderV2Providers(providers) {
  const provider = providers[0];
  if (!provider) {
    els.v2ProviderState.textContent = "未接入";
    els.v2ProviderMeta.textContent = "等待 provider";
    els.v2IndexState.textContent = "-";
    els.v2SyncMeta.textContent = "暂无索引";
    return;
  }
  els.v2ProviderState.textContent = provider.enabled ? provider.display_name : "已停用";
  els.v2ProviderMeta.textContent = provider.provider_id;
  els.v2IndexState.textContent = provider.active_index_version || "种子索引";
  els.v2SyncMeta.textContent = provider.last_sync_at ? formatDate(provider.last_sync_at) : "等待同步";
}

function renderV2ProviderInheritance() {
  if (!els.v2InheritedProviderState) return;
  const modelSettings = v2State.modelSettings || {};
  const imageProvider = v2EffectiveImageProvider(modelSettings);
  const imageReady = v2ImageProviderConfigured(imageProvider, modelSettings);
  const agentReady = Boolean(v2State.orchestratorStatus?.enabled || v2State.health?.agents_sdk_available);
  const thinkerReady = modelSettings.case_intelligence_provider === "claude-code" ? agentReady : true;
  els.v2InheritedProviderState.textContent = imageReady && thinkerReady ? "可用" : imageReady ? "缺中枢" : "待配置";
  const imageModel = v2ImageModelName(imageProvider, modelSettings);
  const claudeModel = modelSettings.claude_orchestrator_model || v2State.orchestratorStatus?.model || "Claude Code 默认模型";
  const imageChannel = v2ImageChannelLabel(imageProvider);
  const caseSource = v2CaseIntelligenceSourceLabel(modelSettings.case_intelligence_provider || "rules");
  if (els.v2ProviderModelState) els.v2ProviderModelState.textContent = `${imageChannel} ${imageModel}`;
  els.v2InheritedModelMeta.textContent = `${imageChannel} ${imageModel} · 中枢 ${claudeModel} · ${caseSource}`;
}

function v2ImageChannelLabel(value) {
  const labels = {
    auto: "自动",
    openai_gpt_image: "OpenAI",
    gemini_image: "Gemini",
    mock_image: "Mock",
  };
  return labels[value] || value || "自动";
}

async function syncV2Provider(mode) {
  const providerId = v2State.providers[0]?.provider_id || "github_evolinkai_gpt_image_cases";
  toggleV2Loading(true);
  updateV2Notice(mode === "remote" ? "正在检查 GitHub 是否有新案例。" : "正在恢复内置种子案例。", "info");
  try {
    const syncRun = await v2Request(`/resource-providers/${providerId}/sync?mode=${mode}`, { method: "POST" });
    const skipped = syncRun.stats?.skipped;
    els.v2SyncMeta.textContent = `${skipped ? "latest" : syncRun.status} · ${syncRun.stats?.cases_published || 0} cases`;
    await initV2({ silent: true, force: true });
    updateV2Notice(
      skipped ? `本地案例库已是最新：${syncRun.stats?.cases_published || 0} 个案例。` : `同步完成：${syncRun.stats?.cases_published || 0} 个案例。`,
      "success"
    );
    showGlobalToast("2.0 案例库已同步。");
  } catch (error) {
    updateV2Notice(`同步失败：${friendlyError(error)}`, "error");
  } finally {
    toggleV2Loading(false);
  }
}

async function loadV2History({ silent = true } = {}) {
  if (!els.v2HistoryGrid) return;
  if (!silent) updateV2Notice("正在刷新 2.0 历史。", "info");
  if (els.v2RefreshHistoryBtn) els.v2RefreshHistoryBtn.disabled = true;
  try {
    const response = await loadV2HistoryResponse();
    v2State.history = response.items || [];
    v2State.historyRenderLimit = v2HistoryPageSize;
    renderV2History(v2State.history);
    if (activePanelName() === "v2") renderHeroHistory(v2State.history, { source: "v2" });
    if (!silent) updateV2Notice(`已加载 ${v2State.history.length} 条 2.0 历史。`, "success");
  } catch (error) {
    if (!silent) updateV2Notice(`2.0 历史加载失败：${friendlyError(error)}`, "error");
  } finally {
    if (els.v2RefreshHistoryBtn) els.v2RefreshHistoryBtn.disabled = false;
  }
}

async function searchV2Templates() {
  const query = els.v2TemplateSearch.value.trim();
  toggleV2Loading(true);
  setV2CaseSearchThinking(true, query);
  try {
    v2State.caseSearchQuery = query;
    if (!query) {
      const response = await v2Request("/templates?limit=1000");
      v2State.templates = response.templates || [];
    } else {
      const response = await v2Request("/prompt-cases/search", {
        method: "POST",
        body: {
          query_text: query,
          risk_filters: ["exclude_protected_ip", "exclude_unlicensed_logo"],
          limit: 1000,
          diversity_level: "medium",
        },
      });
      v2State.templates = response.cases || [];
    }
    v2State.activeCaseFacet = "all";
    v2State.templateRenderLimit = v2TemplatePageSize;
    v2State.visibleTemplates = v2State.templates;
    renderV2CaseFacets(v2State.templates);
    renderV2Templates(v2State.visibleTemplates);
    if (query && v2State.visibleTemplates.length === 0) {
      updateV2Notice("没有匹配到相关案例。可以换一个更宽泛的描述，比如用途、主体、风格或关键材质。", "warning");
    } else {
      updateV2Notice(query ? `已按相关度找到 ${v2State.visibleTemplates.length} 个案例。` : `已展示 ${v2State.visibleTemplates.length} 个案例。`, "success");
    }
  } catch (error) {
    updateV2Notice(`案例匹配失败：${friendlyError(error)}`, "error");
  } finally {
    setV2CaseSearchThinking(false);
    toggleV2Loading(false);
  }
}

function setV2CaseSearchThinking(isLoading, query = "") {
  if (!els.v2SearchThinking) return;
  els.v2SearchThinking.hidden = !isLoading;
  if (els.v2TemplateSearchBtn) {
    els.v2TemplateSearchBtn.classList.toggle("is-thinking", isLoading);
    els.v2TemplateSearchBtn.textContent = isLoading ? "匹配中..." : "匹配案例";
  }
  if (isLoading) {
    const label = els.v2SearchThinking.querySelector("small");
    if (label) {
      label.textContent = query
        ? `正在理解“${query}”的主体、风格、用途和关键元素。`
        : "正在读取本地案例画像并准备展示。";
    }
  }
}

function renderV2CaseFacets(templates) {
  if (!els.v2CaseFacetBar) return;
  const counts = new Map();
  templates.forEach((template) => {
    const templateTags = new Set([template.category, ...(template.style_tags || []), ...(template.use_case_tags || [])].filter(Boolean));
    templateTags.forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  const facets = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 28);
  els.v2CaseFacetBar.innerHTML = "";
  const allButton = v2FacetButton("全部", "all", templates.length);
  els.v2CaseFacetBar.appendChild(allButton);
  facets.forEach(([tag, count]) => {
    els.v2CaseFacetBar.appendChild(v2FacetButton(v2DisplayLabel(tag), tag, count));
  });
}

function v2FacetButton(label, value, count) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `v2-facet ${v2State.activeCaseFacet === value ? "active" : ""}`;
  button.textContent = `${label} ${count}`;
  button.addEventListener("click", () => {
    v2State.activeCaseFacet = value;
    applyV2CaseFacet();
  });
  return button;
}

function applyV2CaseFacet() {
  const facet = v2State.activeCaseFacet;
  v2State.visibleTemplates =
    facet === "all"
      ? v2State.templates
      : v2State.templates.filter((template) =>
          [template.category, ...(template.style_tags || []), ...(template.use_case_tags || [])].includes(facet)
        );
  v2State.templateRenderLimit = v2TemplatePageSize;
  renderV2CaseFacets(v2State.templates);
  renderV2Templates(v2State.visibleTemplates);
  updateV2Notice(v2State.visibleTemplates.length ? `当前显示 ${v2State.visibleTemplates.length} 个案例。` : "这个分类下没有匹配案例。", v2State.visibleTemplates.length ? "success" : "warning");
}

function renderV2Templates(templates) {
  if (!els.v2TemplateGrid) return;
  els.v2TemplateGrid.innerHTML = "";
  const renderLimit = Math.min(v2State.templateRenderLimit, templates.length);
  const renderedTemplates = templates.slice(0, renderLimit);
  els.v2TemplateCount.textContent = templates.length ? `${renderLimit}/${templates.length}` : "0";
  els.v2TemplateGrid.classList.toggle("empty-v2-list", templates.length === 0);
  els.v2TemplateGrid.classList.toggle("has-empty-message", templates.length === 0);
  if (templates.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-v2-message";
    empty.textContent = v2State.caseSearchQuery
      ? `没有匹配“${v2State.caseSearchQuery}”的案例。`
      : "暂无案例数据。";
    els.v2TemplateGrid.appendChild(empty);
    return;
  }
  renderedTemplates.forEach((template) => {
    const card = document.createElement("article");
    card.className = `v2-template-card ${template.case_id === v2State.selectedTemplateId ? "selected" : ""}`;

    const preview = document.createElement(template.preview_url ? "button" : "div");
    preview.className = "v2-template-preview";
    if (template.preview_url) {
      preview.type = "button";
      const fullImageUrl = v2CasePreviewUrl(template.preview_url);
      const image = document.createElement("img");
      image.src = v2CaseThumbnailUrl(template.preview_url);
      image.alt = template.title || "案例预览";
      image.loading = "lazy";
      image.decoding = "async";
      preview.appendChild(image);
      preview.addEventListener("click", () => openV2CasePreview(template, fullImageUrl));
    } else {
      preview.textContent = "Case";
    }

    const body = document.createElement("div");
    body.className = "v2-template-body";

    const header = document.createElement("div");
    header.className = "v2-template-head";
    const title = document.createElement("strong");
    title.textContent = template.title || template.case_id;
    const category = document.createElement("span");
    category.className = "mini-pill";
    category.textContent = v2DisplayLabel(template.category || "case");
    header.append(title, category);
    if (v2State.caseSearchQuery && typeof template.score === "number") {
      const score = document.createElement("span");
      score.className = "mini-pill";
      score.textContent = `相关度 ${Math.round(template.score * 100)}%`;
      header.appendChild(score);
    }

    const summary = document.createElement("p");
    summary.textContent = template.summary || v2ReasonLabel(template.why_selected) || "可作为 V2.0 模板使用。";

    const tags = document.createElement("div");
    tags.className = "v2-tag-row";
    const displayTags = [
      ...(template.profile_tags || []),
      ...(template.style_tags || []),
      ...(template.use_case_tags || []),
    ];
    [...new Set(displayTags)].slice(0, 5).forEach((tag) => {
      const pill = document.createElement("span");
      pill.textContent = v2DisplayLabel(tag);
      tags.appendChild(pill);
    });

    const button = document.createElement("button");
    button.className = "button compact secondary";
    button.type = "button";
    const isSelected = template.case_id === v2State.selectedTemplateId;
    button.textContent = isSelected ? "已选择" : "选择";
    button.disabled = isSelected;
    button.addEventListener("click", () => {
      if (isSelected) return;
      selectV2Template(template.case_id);
    });

    body.append(header, summary, tags, button);
    card.append(preview, body);
    els.v2TemplateGrid.appendChild(card);
  });
  if (renderLimit < templates.length) {
    const loadMore = document.createElement("article");
    loadMore.className = "v2-template-load-more";
    const text = document.createElement("span");
    text.textContent = `已加载 ${renderLimit} / ${templates.length}`;
    const button = document.createElement("button");
    button.className = "button secondary";
    button.type = "button";
    button.textContent = "加载更多案例";
    button.addEventListener("click", () => {
      v2State.templateRenderLimit = Math.min(v2State.templateRenderLimit + v2TemplatePageSize, templates.length);
      renderV2Templates(templates);
    });
    loadMore.append(text, button);
    els.v2TemplateGrid.appendChild(loadMore);
  }
}

function openV2CasePreview(template, previewUrl = null) {
  if (!template?.preview_url) return;
  openImageLightbox({
    id: template.case_id,
    title: template.title || "案例预览",
    url: previewUrl || v2CasePreviewUrl(template.preview_url),
    format: "jpg",
    meta: [...(template.style_tags || []), ...(template.use_case_tags || [])].slice(0, 8).map(v2DisplayLabel).join(" · ") || v2DisplayLabel(template.category),
    promptText: template.summary || template.why_selected || "",
  });
}

function v2DisplayLabel(value) {
  if (!value) return "";
  return v2TagLabels[value] || v2CategoryLabels[value] || value;
}

function v2ReasonLabel(value) {
  if (!value) return "";
  return value
    .replaceAll("case profile match", "案例画像匹配")
    .replaceAll("feature tag match", "特征匹配")
    .replaceAll("semantic prompt overlap", "语义重合")
    .replaceAll("fuzzy text match", "模糊匹配")
    .replaceAll("style filter match", "风格匹配")
    .replaceAll("use-case match", "用途匹配")
    .replaceAll("category match", "分类匹配")
    .replaceAll("quality", "质量分");
}

function v2CasePreviewUrl(url) {
  if (!url) return "";
  const assetPath = v2CaseAssetPath(url);
  if (assetPath) return `${v2ApiBase}/case-assets/${assetPath}`;
  return url;
}

function v2CaseThumbnailUrl(url) {
  const assetPath = v2CaseAssetPath(url);
  if (assetPath) return `${v2ApiBase}/case-thumbnails/${assetPath}`;
  return url;
}

function v2CaseAssetPath(url) {
  if (!url) return "";
  if (url.startsWith("../images/")) {
    return url.replace(/^(\.\.\/)+/, "");
  }
  const marker = "/awesome-gpt-image-2-API-and-Prompts/main/";
  if (url.includes("raw.githubusercontent.com") && url.includes(marker)) {
    return url.split(marker)[1];
  }
  return "";
}

async function selectV2Template(caseId) {
  v2State.selectedTemplateId = caseId;
  const template = v2State.templates.find((item) => item.case_id === caseId);
  els.v2SelectedTemplateLabel.textContent = template ? `模板：${template.title}` : `模板：${caseId}`;
  els.v2ModeState.textContent = "模板定制";
  renderV2Templates(v2State.visibleTemplates);
  renderV2AssetPanel();
  try {
    const detail = await v2Request(`/prompt-cases/${encodeURIComponent(caseId)}`);
    v2State.selectedTemplateDetail = detail;
    hydrateV2TemplateVariables(detail);
    updateV2Notice(`已选择模板：${detail.title || caseId}，可以继续修改定制项。`, "success");
  } catch (error) {
    updateV2Notice(`模板详情加载失败：${friendlyError(error)}`, "warning");
  }
}

function clearV2Template() {
  v2State.selectedTemplateId = null;
  v2State.selectedTemplateDetail = null;
  v2State.templateAutoFields = { subject: "", style: "", useCase: "" };
  els.v2SelectedTemplateLabel.textContent = "未选择模板";
  els.v2ModeState.textContent = "智能增强";
  renderV2Templates(v2State.visibleTemplates);
  renderV2AssetPanel();
}

function hydrateV2TemplateVariables(detail) {
  if (!detail) return;
  const previousAuto = v2State.templateAutoFields || { subject: "", style: "", useCase: "" };
  const atoms = detail.prompt_atoms || {};
  const subject = v2FriendlyTemplateSubject(atoms.subject);
  if (els.v2SubjectInput && v2ShouldReplaceTemplateField(els.v2SubjectInput.value)) {
    els.v2SubjectInput.value = subject;
  }
  if (els.v2StyleInput && (!els.v2StyleInput.value.trim() || els.v2StyleInput.value.trim() === previousAuto.style)) {
    els.v2StyleInput.value = "";
  }
  if (els.v2UseCaseInput && (!els.v2UseCaseInput.value.trim() || els.v2UseCaseInput.value.trim() === previousAuto.useCase)) {
    els.v2UseCaseInput.value = "";
  }
  v2State.templateAutoFields = { subject, style: "", useCase: "" };
}

function v2FriendlyTemplateSubject(subject) {
  const normalized = String(subject || "").trim().toLowerCase();
  const generic = new Set(["product", "subject", "object", "item", "person", "model"]);
  if (!normalized || generic.has(normalized)) return "";
  return subject;
}

function v2ShouldReplaceTemplateField(value) {
  const clean = String(value || "").trim();
  if (!clean) return true;
  return clean
    .split(/[、,\s]+/)
    .filter(Boolean)
    .every((item) => /^[a-z0-9-]+$/i.test(item));
}

function startV2Progress(stageKey = "queued", detail = "正在提交任务到 V2.0 Agent。") {
  clearV2ProgressTimer();
  v2State.progressStartedAt = Date.now();
  v2State.progressNoticeKey = "";
  setV2Progress(stageKey, detail, "info", { forceNotice: true });
  v2State.progressTimer = window.setInterval(renderV2Progress, 1000);
}

function clearV2ProgressTimer() {
  if (!v2State.progressTimer) return;
  window.clearInterval(v2State.progressTimer);
  v2State.progressTimer = null;
}

function resetV2Progress() {
  clearV2ProgressTimer();
  v2State.progressStartedAt = null;
  v2State.progressStageKey = "queued";
  v2State.progressDetail = "";
  v2State.progressType = "info";
  v2State.progressNoticeKey = "";
  if (els.v2ProgressPanel) els.v2ProgressPanel.hidden = true;
}

function finishV2Progress(stageKey, detail, type = "success") {
  setV2Progress(stageKey, detail, type, { forceNotice: true });
  clearV2ProgressTimer();
}

function setV2Progress(stageKey = "planning", detail = "", type = "info", { forceNotice = false } = {}) {
  const normalizedStage = v2ProgressByKey[stageKey] ? stageKey : "planning";
  const stage = v2ProgressByKey[normalizedStage];
  v2State.progressStageKey = normalizedStage;
  v2State.progressDetail = detail || stage.label;
  v2State.progressType = type;
  renderV2Progress();
  if (els.v2RunBtn?.disabled) {
    els.v2RunBtn.textContent = `${stage.short}...`;
  }
  const noticeKey = `${normalizedStage}:${v2State.progressDetail}:${type}`;
  if (forceNotice || noticeKey !== v2State.progressNoticeKey) {
    v2State.progressNoticeKey = noticeKey;
    updateV2Notice(`${stage.label} · ${v2State.progressDetail}`, type);
  }
}

function renderV2Progress() {
  if (!els.v2ProgressPanel) return;
  const stage = v2ProgressByKey[v2State.progressStageKey] || v2ProgressByKey.planning;
  const elapsed = v2ProgressElapsedLabel();
  els.v2ProgressPanel.hidden = false;
  els.v2ProgressTitle.textContent = stage.label;
  els.v2ProgressElapsed.textContent = elapsed ? `已用 ${elapsed}` : "刚开始";
  els.v2ProgressFill.style.width = `${stage.percent}%`;
  els.v2ProgressDetail.textContent = v2State.progressDetail || "V2.0 Agent 正在处理。";
  renderV2ProgressSteps(stage.key);
}

function renderV2ProgressSteps(activeKey) {
  if (!els.v2ProgressSteps) return;
  const activeIndex = v2ProgressStages.findIndex((stage) => stage.key === activeKey);
  els.v2ProgressSteps.innerHTML = "";
  v2ProgressStages.forEach((stage, index) => {
    const step = document.createElement("span");
    step.className = "v2-progress-step";
    if (index < activeIndex) step.classList.add("done");
    if (index === activeIndex) step.classList.add("active");
    step.textContent = stage.label;
    els.v2ProgressSteps.appendChild(step);
  });
}

function v2ProgressElapsedLabel() {
  if (!v2State.progressStartedAt) return "";
  const seconds = Math.max(0, Math.round((Date.now() - v2State.progressStartedAt) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

function v2ClaudeProgressSummary(run = v2State.currentRun) {
  const summary = run?.progress_summary;
  return summary && typeof summary === "object" ? summary : null;
}

function v2ClaudeProgressEvents(run = v2State.currentRun) {
  return Array.isArray(run?.progress_events) ? run.progress_events : [];
}

function v2DurationFromMs(ms) {
  const value = Number(ms);
  if (!Number.isFinite(value) || value <= 0) return "";
  const seconds = Math.round(value / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function updateV2ProgressFromRun(run) {
  const statusStage = v2StatusStageMap[run?.status] || "planning";
  const stageKey = refineV2ProgressStage(statusStage, run);
  setV2Progress(stageKey, v2ProgressDetailForRun(stageKey, run), v2ProgressTypeForRun(run));
}

function refineV2ProgressStage(stageKey, run) {
  if (run?.status === "planning") {
    if (run.prompt_plan || run.orchestrator_decision?.final_prompt) return "composing_prompt";
    if ((run.selected_cases || []).length) return "retrieving_cases";
  }
  if (run?.status === "completed") return "completed";
  if (run?.status === "failed" || run?.status === "cancelled" || run?.status === "blocked_by_policy") return "failed";
  return stageKey;
}

function v2ProgressDetailForRun(stageKey, run) {
  const decision = run?.orchestrator_decision;
  const claudeProgress = v2ClaudeProgressSummary(run);
  const jobs = run?.generation_jobs || [];
  const outputs = jobs.flatMap((job) => job.outputs || []);
  if (run?.status === "failed") return run.next_actions?.[0] || "任务失败，已停止生成。";
  if (run?.status === "blocked_by_policy") return "安全策略要求停止本次生成。";
  if (run?.status === "waiting_for_user") return "需要用户确认后继续。";
  if (run?.status === "completed") return outputs.length ? `流程完成，共得到 ${outputs.length} 张输出。` : "流程结束。";
  if (stageKey === "composing_prompt" && claudeProgress?.message) {
    const elapsed = v2DurationFromMs(claudeProgress.elapsed_ms);
    return elapsed ? `${claudeProgress.message} · Claude累计 ${elapsed}` : claudeProgress.message;
  }
  if (decision?.fallback_reason) return v2FallbackReasonLabel(decision.fallback_reason);
  if (decision?.semantic_cache_hit || decision?.cache_hit) return "命中中枢缓存，正在快速复用高质量提示词。";
  if (stageKey === "queued") return "任务已提交，正在进入 Agent 流程。";
  if (stageKey === "planning") return "Claude Code 中枢正在理解需求并制定策略。";
  if (stageKey === "retrieving_cases") return `已匹配 ${(run?.selected_cases || []).length} 个案例，正在提炼可复用特征。`;
  if (stageKey === "composing_prompt") return "正在生成精简、可直接交给 Image 引擎的最终提示词。";
  if (stageKey === "safety_checking") return "正在检查提示词、素材绑定和生图通道是否可以安全执行。";
  if (stageKey === "generating") return `正在调用生图引擎，已返回 ${outputs.length} 张。`;
  if (stageKey === "reviewing") return outputs.length ? `已生成 ${outputs.length} 张，正在做质量复检。` : "正在等待出图结果并准备复检。";
  return "V2.0 Agent 正在处理。";
}

function v2ProgressTypeForRun(run) {
  if (run?.status === "failed" || run?.status === "cancelled") return "error";
  if (run?.status === "blocked_by_policy" || run?.status === "waiting_for_user") return "warning";
  if (run?.status === "completed") return "success";
  if (run?.orchestrator_decision?.fallback_reason) return "warning";
  return "info";
}

function v2FallbackReasonLabel(reason) {
  const text = String(reason || "");
  if (/claude_timeout|TimeoutExpired/i.test(text)) {
    return "Claude 中枢触达时间边界，系统应压缩续跑；若仍无可恢复结果则停止出图。";
  }
  if (/claude_output_token_limit|output token maximum|MAX_OUTPUT_TOKENS/i.test(text)) {
    return "Claude 中枢输出触达上限，系统应压缩续跑；若仍无可恢复结果则停止出图。";
  }
  if (/kimi_context_canceled|context canceled|kimi/i.test(text)) {
    return "Kimi 主源连接波动，系统会尝试压缩续跑或备用源接力。";
  }
  if (/claude_api_error|api error/i.test(text)) {
    return "Claude 中枢暂时不可用，系统会尝试备用源接力；无可恢复结果则停止出图。";
  }
  return "Claude 中枢未产出可恢复结果，流程已按中枢原则处理。";
}

async function runV2Creative() {
  const prompt = buildV2UserPrompt();
  if (!v2HasGenerationInput(prompt)) {
    updateV2Notice("信息不全：请先填写提示词，或选择案例模板/上传素材后再生成。", "warning");
    showGlobalToast("请先补全生图信息。", "error");
    els.v2PromptInput?.focus();
    return;
  }
  const imageProvider = v2RequestedImageProvider(v2State.modelSettings || {});
  if (imageProvider === "mock_image") {
    updateV2Notice("当前选择的是 Mock 测试通道，会快速生成占位图；需要真实生图请切换到 OpenAI 或 Gemini。", "warning");
  }
  toggleV2Loading(true);
  startV2Progress("queued", "正在提交任务到 V2.0 Agent。");
  renderV2RunPlaceholder();
  try {
    const output = {
      count: Number(els.v2CountInput.value),
      quality: "high",
      output_format: "png",
      provider_hint: imageProvider || "auto",
    };
    if (v2State.selectedRatio) {
      output.aspect_ratio = v2State.selectedRatio;
    }
    const queuedRun = await v2Request("/creative/runs/async", {
      method: "POST",
      body: {
        user_prompt: prompt,
        mode_hint: v2State.selectedTemplateId ? "template_customize" : "smart_enhance",
        template_case_id: v2State.selectedTemplateId,
        assets: v2AssetPayload(),
        output,
      },
    });
    v2State.currentRun = queuedRun;
    els.v2TraceId.textContent = queuedRun.trace_id || queuedRun.run_id || "planning";
    setV2Progress("planning", "任务已创建，Claude Code 中枢开始规划。", "info", { forceNotice: true });
    const run = v2IsTerminalRun(queuedRun) ? queuedRun : await pollV2Run(queuedRun.run_id);
    v2State.currentRun = run;
    renderV2Run(run);
    const notice = v2RunNotice(run);
    updateV2Notice(notice.message, notice.type);
    finishV2Progress(v2StatusStageMap[run.status] || "completed", notice.message, notice.type);
    showGlobalToast("V2.0 Agent 已完成出图流程。");
    await loadV2History({ silent: true });
  } catch (error) {
    const message = `V2.0 Agent 失败：${friendlyError(error)}`;
    finishV2Progress("failed", message, "error");
    updateV2Notice(message, "error");
    clearV2RunResult();
  } finally {
    clearV2ProgressTimer();
    toggleV2Loading(false);
  }
}

async function pollV2Run(runId) {
  let attempt = 0;
  let consecutiveReadErrors = 0;
  while (true) {
    await v2Delay(attempt === 0 ? 800 : 2000);
    attempt += 1;
    let run = null;
    try {
      run = await v2Request(`/creative/runs/${encodeURIComponent(runId)}`);
      consecutiveReadErrors = 0;
    } catch (error) {
      consecutiveReadErrors += 1;
      setV2Progress(
        v2State.progressStageKey || "planning",
        `暂时读不到后台状态，正在继续刷新；已重试 ${consecutiveReadErrors} 次。`,
        "warning",
        { forceNotice: consecutiveReadErrors === 1 || consecutiveReadErrors % 5 === 0 }
      );
      continue;
    }

    v2State.currentRun = run;
    els.v2TraceId.textContent = run.trace_id || run.run_id || "planning";
    updateV2ProgressFromRun(run);
    if (attempt === v2RunLongWaitAttempt || (attempt > v2RunLongWaitAttempt && attempt % 30 === 0)) {
      const stage = refineV2ProgressStage(v2StatusStageMap[run.status] || "planning", run);
      setV2Progress(stage, "后台仍在运行，页面会持续刷新直到任务明确完成或失败；真实出图可能需要数分钟。", "info", { forceNotice: true });
    }
    if (run.prompt_plan || run.orchestrator_decision || run.generation_jobs?.length || run.progress_summary?.message || run.progress_events?.length) {
      renderV2Run(run);
    }
    if (v2IsTerminalRun(run)) {
      return run;
    }
  }
}

function v2Delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function v2IsTerminalRun(run) {
  return ["completed", "failed", "cancelled", "blocked_by_policy", "waiting_for_user"].includes(run?.status);
}

function buildV2UserPrompt() {
  const base = els.v2PromptInput.value.trim();
  const variables = [
    els.v2SubjectInput?.value.trim() ? `替换主体：${els.v2SubjectInput.value.trim()}` : "",
    els.v2StyleInput?.value.trim() ? `想要的感觉：${els.v2StyleInput.value.trim()}` : "",
    els.v2UseCaseInput?.value.trim() ? `使用场景：${els.v2UseCaseInput.value.trim()}` : "",
  ].filter(Boolean);
  return variables.length ? `${base}\n${variables.join("\n")}` : base;
}

function v2HasGenerationInput(prompt = "") {
  return Boolean(String(prompt || "").trim() || v2State.selectedTemplateId || v2State.uploadedAssets.length);
}

function v2RunNotice(run) {
  const decision = run?.orchestrator_decision;
  if (run?.status === "failed") {
    return { message: `V2.0 Agent 失败：${run.next_actions?.[0] || "任务未完成"}。`, type: "error" };
  }
  if (run?.status === "blocked_by_policy") {
    return { message: "V2.0 已根据安全策略阻断本次请求。", type: "warning" };
  }
  if (run?.status === "waiting_for_user") {
    return { message: "V2.0 需要用户确认后才能继续生成。", type: "warning" };
  }
  const job = run?.generation_jobs?.[0];
  if (job?.status === "failed") {
    return { message: `V2.0 Agent 失败：${job.error?.message || "真实出图未完成"}。`, type: "error" };
  }
  if (job?.error && job.outputs?.length) {
    return { message: "真实出图失败，已使用 V2.0 mock 兜底。", type: "warning" };
  }
  const liveCount = (job?.outputs || []).filter((output) => output.metadata?.live).length;
  if (liveCount) {
    const brain = decision?.cache_hit ? "命中中枢缓存" : decision?.provider === "claude-code" ? "Claude 中枢已参与" : "中枢已完成";
    return { message: `V2.0 Agent 已完成 live 出图：${liveCount} 张，${v2ProviderResultText(job, job.outputs?.[0])}，${brain}。`, type: "success" };
  }
  if (decision?.fallback_reason) {
    return { message: `V2.0 ${v2FallbackReasonLabel(decision.fallback_reason)}`, type: "warning" };
  }
  return { message: `V2.0 Agent 已完成：${run.mode}。`, type: "success" };
}

function renderV2RunPlaceholder() {
  els.v2TraceId.textContent = "planning";
  els.v2SelectedCases.classList.add("empty-v2-list");
  els.v2SelectedCases.innerHTML = "";
  renderV2Brain({ invocation_status: "planning", provider: "claude-code" });
  els.v2PromptPlan.textContent = "正在组合提示词。";
  els.v2Outputs.classList.add("empty-v2-list");
  els.v2Outputs.innerHTML = "";
}

function renderV2Run(run) {
  els.v2TraceId.textContent = run.trace_id || run.run_id || "-";
  renderV2SelectedCases(run.selected_cases || []);
  renderV2Brain(run.orchestrator_decision, v2State.orchestratorStatus);
  renderV2PromptPlan(run.prompt_plan, run);
  const jobs = run.generation_jobs || [];
  const outputs = jobs.flatMap((job) => job.outputs || []);
  renderV2Outputs(outputs, jobs[0]);
}

function renderV2SelectedCases(cases) {
  els.v2SelectedCases.innerHTML = "";
  els.v2SelectedCases.classList.toggle("empty-v2-list", cases.length === 0);
  cases.forEach((item) => {
    const row = document.createElement("div");
    row.className = "v2-case-row";
    const title = document.createElement("strong");
    title.textContent = item.title || item.case_id;
    const reason = document.createElement("span");
    reason.textContent = v2ReasonLabel(item.why_selected) || item.category || item.case_id;
    row.append(title, reason);
    const profileTags = document.createElement("div");
    profileTags.className = "v2-tag-row";
    (item.profile_tags || []).slice(0, 5).forEach((tag) => {
      const pill = document.createElement("span");
      pill.textContent = v2DisplayLabel(tag);
      profileTags.appendChild(pill);
    });
    if (profileTags.childElementCount) row.appendChild(profileTags);
    els.v2SelectedCases.appendChild(row);
  });
}

function renderV2Brain(decision, status = null) {
  if (!els.v2BrainPanel) return;
  els.v2BrainPanel.innerHTML = "";
  const rows = [];
  const claudeProgress = v2ClaudeProgressSummary();
  const claudeEvents = v2ClaudeProgressEvents();
  if (decision) {
    const directives = decision.prompt_directives || {};
    const variables = v2State.currentRun?.prompt_plan?.user_variables || {};
    const uploadedAssets = Array.isArray(variables.uploaded_assets) ? variables.uploaded_assets : [];
    const providerPlan = variables.provider_input_plan || variables.asset_binding_plan?.provider_input_plan || {};
    const provider =
      decision.provider === "claude-code"
        ? decision.cache_hit
          ? "Claude Code（复用缓存）"
          : "Claude Code"
        : "安全回退";
    const selectedCaseCount = Array.isArray(decision.selected_case_ids) ? decision.selected_case_ids.length : 0;
    const caseSource = v2CaseIntelligenceSourceLabel(v2State.modelSettings?.case_intelligence_provider || "rules");
    rows.push(["中枢", provider, decision.fallback_reason ? "warn" : "ok"]);
    rows.push(["状态", v2BrainStatusLabel(decision), decision.fallback_reason ? "warn" : "ok"]);
    rows.push(["案例", selectedCaseCount ? `参考 ${selectedCaseCount} 个案例` : caseSource, ""]);
    if (uploadedAssets.length) rows.push(["素材", `已绑定 ${uploadedAssets.length} 张上传图片`, "ok"]);
    if (providerPlan.reference_image_count) {
      rows.push(["图像输入", `参考图 ${providerPlan.reference_image_count} 张 · ${providerInputOperationLabel(providerPlan.operation)}`, "ok"]);
    }
    if (directives.visual_strategy) rows.push(["策略", directives.visual_strategy, ""]);
    else if (directives.case_selection_rationale) rows.push(["策略", directives.case_selection_rationale, ""]);
    if (decision.fallback_reason) rows.push(["提示", v2FallbackReasonLabel(decision.fallback_reason), "warn"]);
  } else if (status) {
    const caseSource = v2CaseIntelligenceSourceLabel(v2State.modelSettings?.case_intelligence_provider || "rules");
    const caseCount = Array.isArray(v2State.templates) ? v2State.templates.length : 0;
    rows.push(["中枢", status.enabled ? "Claude Code 已开启" : "安全回退模式", status.enabled ? "ok" : "warn"]);
    rows.push(["状态", status.enabled ? "待命" : "备用流程待命", status.enabled ? "ok" : "warn"]);
    rows.push(["案例", caseCount ? `${caseSource} · ${caseCount} 个案例` : caseSource, ""]);
  }
  if (claudeProgress?.message) {
    const isWarn = ["error", "failed", "missing_decision"].includes(claudeProgress.status);
    rows.push(["Claude阶段", claudeProgress.message, isWarn ? "warn" : "ok"]);
    const elapsed = v2DurationFromMs(claudeProgress.elapsed_ms);
    const meta = [
      elapsed ? `累计 ${elapsed}` : "",
      claudeProgress.finished_stage_count ? `完成 ${claudeProgress.finished_stage_count} 段` : "",
      claudeProgress.retry_count ? `压缩续跑 ${claudeProgress.retry_count} 次` : "",
      claudeProgress.fallback_count ? `备用接力 ${claudeProgress.fallback_count} 次` : "",
    ].filter(Boolean);
    if (meta.length) rows.push(["Claude耗时", meta.join(" · "), isWarn ? "warn" : ""]);
    claudeEvents.slice(-3).forEach((event) => {
      const duration = v2DurationFromMs(event.duration_ms);
      const value = `${event.stage_label || event.stage || "Claude"} · ${event.status || ""}${duration ? ` · ${duration}` : ""}`;
      const tone = ["error", "failed", "missing_decision"].includes(event.status) ? "warn" : "";
      rows.push(["最近", value, tone]);
    });
  }
  els.v2BrainPanel.classList.toggle("empty-v2-list", rows.length === 0);
  if (rows.length === 0) {
    els.v2BrainPanel.textContent = "等待 Agent 判断。";
    return;
  }
  rows.forEach(([label, value, tone]) => {
    const row = document.createElement("div");
    row.className = `v2-brain-row ${tone ? `status-${tone}` : ""}`.trim();
    const strong = document.createElement("strong");
    strong.textContent = label;
    const span = document.createElement("span");
    span.textContent = value || "-";
    row.append(strong, span);
    els.v2BrainPanel.appendChild(row);
  });
}

function v2BrainStatusLabel(decision) {
  const status = decision?.invocation_status || "unknown";
  if (status === "success") return "规划完成";
  if (status === "cache_hit") return "命中缓存";
  if (status === "fallback") return "已回退";
  if (status === "disabled") return "未启用";
  if (status === "planning") return "中枢规划中";
  return status;
}

function renderV2PromptPlan(plan, run = v2State.currentRun) {
  if (!plan) {
    const claudeProgress = v2ClaudeProgressSummary(run);
    if (claudeProgress?.message) {
      const events = v2ClaudeProgressEvents(run).slice(-5);
      const elapsed = v2DurationFromMs(claudeProgress.elapsed_ms);
      const lines = [
        "Claude 调度进度",
        claudeProgress.message,
        elapsed ? `累计耗时: ${elapsed}` : "",
        claudeProgress.retry_count ? `压缩续跑: ${claudeProgress.retry_count} 次` : "",
        claudeProgress.fallback_count ? `备用接力: ${claudeProgress.fallback_count} 次` : "",
        "",
        ...events.map((event) => {
          const duration = v2DurationFromMs(event.duration_ms);
          return `- ${event.stage_label || event.stage || "Claude"} · ${event.status || "-"}${duration ? ` · ${duration}` : ""}`;
        }),
      ].filter((line, index, list) => line || list[index - 1]);
      els.v2PromptPlan.textContent = lines.join("\n");
      return;
    }
    els.v2PromptPlan.textContent = "正在等待提示词计划。";
    return;
  }
  const variables = plan.user_variables || plan.variables || {};
  const providerPlan = variables.provider_input_plan || variables.asset_binding_plan?.provider_input_plan || null;
  const uploadedAssets = Array.isArray(variables.uploaded_assets) ? variables.uploaded_assets : [];
  const bindingPlan = variables.asset_binding_plan || null;
  const assetLines = [];
  if (variables.template_lock_enabled) {
    assetLines.push("Template Lock: 已启用，手选案例优先锁定画面框架。");
  }
  if (uploadedAssets.length) {
    assetLines.push(`Uploaded Assets: ${uploadedAssets.length} 张`);
    uploadedAssets.slice(0, 4).forEach((asset) => {
      assetLines.push(`- ${assetRoleLabel(asset.role)} · ${asset.filename || asset.asset_id}`);
    });
  }
  if (providerPlan?.reference_image_count) {
    assetLines.push(`Provider Input: ${providerInputOperationLabel(providerPlan.operation)} · 参考图 ${providerPlan.reference_image_count} 张`);
  }
  if (Array.isArray(providerPlan?.placement_targets) && providerPlan.placement_targets.length) {
    assetLines.push("融合意图:");
    providerPlan.placement_targets.slice(0, 4).forEach((target) => {
      const mode = assetFusionModeLabel(target.fusion_mode);
      const label = target.target_label || target.target_surface || "-";
      assetLines.push(`- ${assetRoleLabel(target.role)} · ${mode} · ${label}`);
    });
  } else if (Array.isArray(bindingPlan?.bindings) && bindingPlan.bindings.length) {
    assetLines.push("融合意图:");
    bindingPlan.bindings.slice(0, 4).forEach((binding) => {
      const mode = assetFusionModeLabel(binding.fusion_mode);
      const placement = binding.placement_intent || {};
      const label = placement.target_label || binding.target_surface || "-";
      assetLines.push(`- ${assetRoleLabel(binding.role)} · ${mode} · ${label}`);
    });
  }
  if (Array.isArray(bindingPlan?.conflicts) && bindingPlan.conflicts.length) {
    assetLines.push(`Conflict Policy: ${bindingPlan.conflicts[0].resolution || "保持模板优先，素材填槽"}`);
  }
  const lines = [
    plan.prompt,
    "",
    `Negative: ${plan.negative_prompt || "-"}`,
    "",
    `Mode: ${plan.mode}`,
    `Aspect: ${plan.provider_parameters?.aspect_ratio || "-"}`,
    `Count: ${plan.provider_parameters?.count || "-"}`,
    ...(assetLines.length ? ["", assetLines.join("\n")] : []),
    "",
    plan.explanation || "",
  ].filter((line, index, list) => line || list[index - 1]);
  els.v2PromptPlan.textContent = lines.join("\n");
}

function renderV2Outputs(outputs, job) {
  els.v2Outputs.innerHTML = "";
  els.v2Outputs.classList.toggle("empty-v2-list", outputs.length === 0 && !job?.error);
  outputs.forEach((output, index) => {
    const card = document.createElement("article");
    card.className = "v2-output-card";
    const preview = document.createElement("button");
    preview.className = output.metadata?.mock ? "v2-live-preview v2-mock-preview" : "v2-live-preview";
    preview.type = "button";
    const image = document.createElement("img");
    image.src = v2OutputImageUrl(output);
    image.alt = `2.0 生成结果 ${index + 1}`;
    image.loading = "lazy";
    image.decoding = "async";
    preview.appendChild(image);
    preview.addEventListener("click", () => {
      openImageLightbox({
        id: output.output_id,
        title: `2.0 生成结果 ${index + 1}`,
        url: v2OutputImageUrl(output, { thumbnail: false }),
        thumbnailUrl: v2OutputImageUrl(output),
        format: v2OutputFormat(output),
        meta: v2ProviderResultText(job, output),
        promptText: v2PromptTextFromJob(job),
      });
    });
    const meta = document.createElement("div");
    meta.className = "v2-output-meta";
    const id = document.createElement("strong");
    id.textContent = output.output_id || `output-${index + 1}`;
    const detail = document.createElement("span");
    const review = output.review;
    const reviewText = review ? `${v2ReviewLabel(review.decision)} ${Math.round((review.score || 0) * 100)}%` : `${Math.round(v2OutputScore(output.score) * 100)}%`;
    detail.textContent = `${v2ProviderResultText(job, output)} · ${reviewText}`;
    const badge = document.createElement("span");
    badge.className = `v2-output-badge ${output.metadata?.live ? "live" : output.metadata?.mock ? "mock" : "unknown"}`;
    badge.textContent = output.metadata?.live ? "Live" : output.metadata?.mock ? "Mock" : "Output";
    meta.append(id, detail, badge);
    card.append(preview, meta);
    els.v2Outputs.appendChild(card);
  });
  if (job?.error) {
    const error = document.createElement("p");
    error.className = "v2-output-error";
    error.textContent = job.error.message || "真实出图失败，已使用兜底输出。";
    els.v2Outputs.appendChild(error);
  }
}

function renderV2History(items) {
  if (!els.v2HistoryGrid) return;
  els.v2HistoryGrid.innerHTML = "";
  const visibleItems = items.filter(isRenderableV2HistoryImage);
  const hiddenMockCount = items.length - visibleItems.length;
  const renderLimit = Math.min(v2State.historyRenderLimit, visibleItems.length);
  const renderedItems = visibleItems.slice(0, renderLimit);
  els.v2HistoryCount.textContent = renderLimit < visibleItems.length ? `${renderLimit}/${visibleItems.length}` : String(visibleItems.length);
  els.v2HistoryGrid.classList.toggle("empty-v2-list", visibleItems.length === 0);
  renderedItems.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "v2-history-card";
    const cardPrompt = v2HistoryCardPrompt(item);

    const preview = document.createElement(item.metadata?.mock ? "div" : "button");
    preview.className = item.metadata?.mock ? "v2-mock-preview" : "v2-live-preview";
    if (item.metadata?.mock) {
      preview.textContent = `H${index + 1}`;
    } else {
      preview.type = "button";
      const image = document.createElement("img");
      image.src = v2HistoryImageUrl(item);
      image.alt = cardPrompt || `2.0 历史 ${index + 1}`;
      image.loading = "lazy";
      image.decoding = "async";
      preview.appendChild(image);
      preview.addEventListener("click", () => openV2HistoryLightbox(item, index));
    }

    const meta = document.createElement("div");
    meta.className = "v2-history-meta";
    const prompt = document.createElement("strong");
    prompt.textContent = cardPrompt || item.output_id;
    const details = document.createElement("span");
    details.textContent = `${v2HistoryProviderResultText(item)} · ${formatDate(item.created_at)}`;
    meta.append(prompt, details);

    const footer = document.createElement("div");
    footer.className = "output-meta v2-history-footer";
    const id = document.createElement("span");
    id.className = "output-id";
    id.textContent = item.output_id || item.job_id || "-";
    const actions = document.createElement("div");
    actions.className = "history-card-actions";
    const link = document.createElement("a");
    link.className = "download-link";
    bindDownloadLink(
      link,
      v2HistoryImageUrl(item, { thumbnail: false }),
      `${item.output_id || "v2-image"}.${v2HistoryFormat(item) === "jpeg" ? "jpg" : v2HistoryFormat(item)}`,
    );
    link.textContent = "下载";
    const deleteButton = document.createElement("button");
    deleteButton.className = "delete-link";
    deleteButton.type = "button";
    deleteButton.textContent = "删除";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteV2HistoryItem(item, card);
    });
    actions.append(link, deleteButton);
    footer.append(id, actions);

    card.append(preview, meta, footer);
    els.v2HistoryGrid.appendChild(card);
  });
  if (hiddenMockCount > 0) {
    const note = document.createElement("article");
    note.className = "v2-history-note";
    note.textContent = `已隐藏 ${hiddenMockCount} 条测试占位记录，只显示真实图片。`;
    els.v2HistoryGrid.appendChild(note);
  }
  if (renderLimit < visibleItems.length) {
    const loadMore = document.createElement("article");
    loadMore.className = "v2-template-load-more v2-history-load-more";
    const text = document.createElement("span");
    text.textContent = `已加载 ${renderLimit} / ${visibleItems.length}`;
    const button = document.createElement("button");
    button.className = "button secondary";
    button.type = "button";
    button.textContent = "加载更多历史";
    button.addEventListener("click", () => {
      v2State.historyRenderLimit = Math.min(v2State.historyRenderLimit + v2HistoryPageSize, visibleItems.length);
      renderV2History(items);
    });
    loadMore.append(text, button);
    els.v2HistoryGrid.appendChild(loadMore);
  }
}

function isRenderableV2HistoryImage(item) {
  if (!item) return false;
  if (item.metadata?.mock || item.provider_id === "mock_image") return false;
  if (String(item.url || item.metadata?.url || "").includes("/mock-outputs/")) return false;
  return Boolean(v2HistoryImageUrl(item, { thumbnail: false }) || v2HistoryImageUrl(item));
}

function openV2HistoryLightbox(item, index = 0) {
  const cardPrompt = v2HistoryCardPrompt(item);
  openImageLightbox({
    id: item.output_id,
    title: cardPrompt ? cardPrompt.slice(0, 34) : `2.0 历史图片 ${index + 1}`,
    url: v2HistoryImageUrl(item, { thumbnail: false }),
    thumbnailUrl: v2HistoryImageUrl(item),
    format: v2HistoryFormat(item),
    meta: `${v2HistoryProviderResultText(item)} · ${formatDate(item.created_at || item.updated_at)}`,
    promptText: v2PromptTextFromHistory(item),
  });
}

async function deleteV2HistoryItem(item, card) {
  const confirmed = window.confirm("删除后这张图片将从 2.0 历史记录中移除。确认删除？");
  if (!confirmed) return;
  const deleteButton = card?.querySelector(".delete-link");
  if (deleteButton) {
    deleteButton.disabled = true;
    deleteButton.textContent = "删除中";
  }
  try {
    await v2Request(`/image/history/${encodeURIComponent(item.output_id)}`, { method: "DELETE" });
    v2State.history = v2State.history.filter((entry) => entry.output_id !== item.output_id);
    if (!els.imageLightbox.hidden && els.lightboxDownload.href.includes(encodeURIComponent(item.output_id))) {
      closeImageLightbox();
    }
    renderV2History(v2State.history);
    if (activePanelName() === "v2") renderHeroHistory(v2State.history, { source: "v2" });
    updateV2Notice("2.0 历史图片已删除。", "success");
    showGlobalToast("2.0 历史图片已删除。");
  } catch (error) {
    if (deleteButton) {
      deleteButton.disabled = false;
      deleteButton.textContent = "删除";
    }
    updateV2Notice(`删除失败：${friendlyError(error)}`, "error");
  }
}

function v2PromptTextFromJob(job) {
  const plan = job?.prompt_plan;
  if (!plan) return "";
  const original = v2CleanPromptText(plan.user_variables?.user_prompt || plan.user_variables?.original_prompt);
  const finalPrompt = v2CleanPromptText(plan.prompt);
  const finalLabel = plan.user_variables?.claude_final_prompt_used ? "Claude 思考后的最终提示词" : "Agent 最终提示词";
  const blocks = [`原始提示词\n${original || "未记录原始提示词。"}`];
  if (finalPrompt) blocks.push(`${finalLabel}\n${finalPrompt}`);
  if (plan.negative_prompt) blocks.push(`Negative\n${plan.negative_prompt}`);
  if (plan.explanation) blocks.push(`说明\n${plan.explanation}`);
  return blocks.join("\n\n");
}

function v2PromptTextFromHistory(item) {
  const metadata = item?.metadata || {};
  const original = v2CleanPromptText(metadata.original_prompt || metadata.user_prompt || metadata.original_user_prompt);
  const finalPrompt = v2CleanPromptText(metadata.final_prompt || item?.prompt);
  const finalLabel = metadata.claude_final_prompt_used ? "Claude 思考后的最终提示词" : "Agent 最终提示词";
  const blocks = [`原始提示词\n${original || "这条旧历史记录未保存原始提示词。"}`];
  if (finalPrompt) blocks.push(`${finalLabel}\n${finalPrompt}`);
  if (metadata.negative_prompt) blocks.push(`Negative\n${metadata.negative_prompt}`);
  if (metadata.prompt_explanation || metadata.explanation) blocks.push(`说明\n${metadata.prompt_explanation || metadata.explanation}`);
  return blocks.join("\n\n");
}

function v2HistoryCardPrompt(item) {
  return (
    v2CleanPromptText(item?.metadata?.original_prompt || item?.metadata?.user_prompt || item?.metadata?.original_user_prompt) ||
    v2CleanPromptText(item?.prompt)
  );
}

function v2CleanPromptText(value) {
  return String(value || "").trim();
}

function v2ProviderResultText(job, output) {
  const metadata = output?.metadata || {};
  return providerResultText({
    requestedProvider: metadata.requested_provider || job?.prompt_plan?.provider_parameters?.provider_hint,
    actualProvider: metadata.actual_provider || job?.provider_id,
    actualModel: metadata.actual_model || job?.model,
    fallback: metadata.provider_fallback,
  });
}

function v2HistoryProviderResultText(item) {
  const metadata = item?.metadata || {};
  return providerResultText({
    requestedProvider: metadata.requested_provider,
    actualProvider: metadata.actual_provider || item?.provider_id,
    actualModel: metadata.actual_model || item?.model,
    fallback: metadata.provider_fallback,
  });
}

function v2OutputFormat(output) {
  return output?.metadata?.format || "png";
}

function v2HistoryFormat(item) {
  return item?.metadata?.format || "png";
}

function v2MediaUrl(url) {
  if (!url) return "";
  if (url.startsWith("/api/v2/")) {
    return `${v2ApiBase}${url.slice("/api/v2".length)}`;
  }
  return url;
}

function v2OutputImageUrl(output, { thumbnail = true } = {}) {
  const metadata = output?.metadata || {};
  const url =
    (thumbnail && (output?.thumbnail_url || metadata.thumbnail_url)) ||
    output?.url ||
    metadata.url ||
    metadata.download_url ||
    "";
  return v2MediaUrl(url);
}

function v2HistoryImageUrl(item, { thumbnail = true } = {}) {
  const metadata = item?.metadata || {};
  const url =
    (thumbnail && (item?.thumbnail_url || metadata.thumbnail_url)) ||
    item?.url ||
    metadata.url ||
    metadata.download_url ||
    "";
  return v2MediaUrl(url);
}

function v2ReviewLabel(decision) {
  if (decision === "pass") return "已通过";
  if (decision === "needs_review") return "待复核";
  if (decision === "retry_recommended") return "建议重试";
  if (decision === "failed") return "失败";
  return "未评估";
}

function v2OutputScore(score = {}) {
  if (typeof score.goal_match === "number") return score.goal_match;
  if (typeof score.prompt_adherence === "number") return score.prompt_adherence;
  if (typeof score.composition === "number") return score.composition;
  return 0;
}

function clearV2RunResult() {
  els.v2TraceId.textContent = "-";
  els.v2SelectedCases.innerHTML = "";
  els.v2SelectedCases.classList.add("empty-v2-list");
  renderV2Brain(null, v2State.orchestratorStatus);
  els.v2PromptPlan.textContent = "等待 V2.0 Agent 输出。";
  els.v2Outputs.innerHTML = "";
  els.v2Outputs.classList.add("empty-v2-list");
}

function toggleV2Loading(isLoading) {
  [els.v2RefreshBtn, els.v2SeedSyncBtn, els.v2RemoteSyncBtn, els.v2TemplateSearchBtn, els.v2RunBtn, els.v2RefreshHistoryBtn]
    .filter(Boolean)
    .forEach((button) => {
      button.disabled = isLoading;
    });
  if (els.v2RunBtn) els.v2RunBtn.textContent = isLoading ? "处理中..." : "生成图片";
}

function updateV2Notice(message, type = "info") {
  if (!els.v2NoticeBar) return;
  els.v2NoticeBar.textContent = message;
  els.v2NoticeBar.className = `notice-bar ${type === "info" ? "" : type}`.trim();
}

function getVeyraToken() {
  try {
    return localStorage.getItem(veyraTokenStorageKey) || "";
  } catch {
    return "";
  }
}

function setVeyraToken(token) {
  try {
    if (token) {
      localStorage.setItem(veyraTokenStorageKey, token);
    } else {
      localStorage.removeItem(veyraTokenStorageKey);
      localStorage.removeItem(veyraAccountStorageKey);
      veyraState.account = null;
      veyraState.history = [];
      veyraState.usage = [];
      updateAdminSettingsEntry();
    }
  } catch {
    // Ignore unavailable storage; the backend remains the source of truth.
  }
}

function hydrateCachedVeyraAccount() {
  if (!getVeyraToken()) {
    updateAdminSettingsEntry();
    return;
  }
  try {
    const cached = localStorage.getItem(veyraAccountStorageKey);
    if (!cached) {
      updateAdminSettingsEntry();
      return;
    }
    veyraState.account = JSON.parse(cached);
  } catch {
    veyraState.account = null;
  }
  updateAdminSettingsEntry();
}

function isVeyraAdmin(account = veyraState.account) {
  const user = veyraAccountUser(account);
  return String(user?.role || "").toLowerCase() === "admin";
}

function updateAdminSettingsEntry() {
  if (!els.headerAdminSettingsLink) return;
  els.headerAdminSettingsLink.hidden = !getVeyraToken() || !isVeyraAdmin();
}

function v2HistoryPath() {
  return getVeyraToken() ? "/veyra/history?limit=1000" : "/image/history?limit=1000";
}

async function loadV2HistoryResponse() {
  try {
    return await v2Request(v2HistoryPath());
  } catch (error) {
    if (error?.status === 401 && !getVeyraToken()) {
      return v2Request("/image/history?limit=1000", { skipVeyraAuth: true });
    }
    throw error;
  }
}

function cleanVeyraTicketFromUrl() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("ticket")) return;
  url.searchParams.delete("ticket");
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
}

async function handleVeyraTicketFromUrl() {
  const ticket = new URLSearchParams(window.location.search).get("ticket");
  if (!ticket) return;
  try {
    const session = await v2Request("/veyra/login", {
      method: "POST",
      body: { ticket },
      skipVeyraAuth: true,
    });
    setVeyraToken(session.access_token || "");
    cleanVeyraTicketFromUrl();
    await loadVeyraAccountPanel({ silent: true, force: true });
    updateV2Notice("Veyra 账户已接入。", "success");
  } catch (error) {
    setVeyraToken("");
    cleanVeyraTicketFromUrl();
    updateV2Notice(`Veyra 登录失败：${friendlyError(error)}`, "error");
  }
}

async function refreshVeyraAccount() {
  if (!getVeyraToken()) return null;
  try {
    const account = await v2Request("/veyra/me");
    veyraState.account = account;
    try {
      localStorage.setItem(veyraAccountStorageKey, JSON.stringify(account));
    } catch {
      // Ignore storage failures; this cache is only for browser display continuity.
    }
    updateAdminSettingsEntry();
    return account;
  } catch (error) {
    if (String(error?.message || error).includes("401")) setVeyraToken("");
    updateAdminSettingsEntry();
    return null;
  }
}

function veyraAccountUser(account = veyraState.account) {
  return account?.user || account || null;
}

function formatVeyraMoney(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "-";
  return amount.toFixed(4).replace(/\.?0+$/, "") || "0";
}

function veyraUsageTotal(items = []) {
  return items.reduce((sum, item) => {
    const amount = Number(item?.amount);
    return Number.isFinite(amount) ? sum + amount : sum;
  }, 0);
}

function setVeyraAccountLoading(isLoading) {
  veyraState.loading = isLoading;
  if (els.veyraRefreshAccountBtn) {
    els.veyraRefreshAccountBtn.disabled = isLoading;
    els.veyraRefreshAccountBtn.textContent = isLoading ? "刷新中..." : "刷新账户";
  }
}

function renderVeyraSignedOut() {
  updateAdminSettingsEntry();
  if (els.veyraAccountState) els.veyraAccountState.textContent = "未接入";
  if (els.veyraAccountEmail) els.veyraAccountEmail.textContent = "从 Veyra Agent 登录后显示";
  if (els.veyraAccountBalance) els.veyraAccountBalance.textContent = "-";
  if (els.veyraAccountStatus) els.veyraAccountStatus.textContent = "等待登录";
  if (els.veyraAccountUserId) els.veyraAccountUserId.textContent = "-";
  if (els.veyraAccountHistoryCount) els.veyraAccountHistoryCount.textContent = "0";
  if (els.veyraAccountHistoryScope) els.veyraAccountHistoryScope.textContent = "当前账户与旧公共记录";
  if (els.veyraAccountHistoryTitle) els.veyraAccountHistoryTitle.textContent = "我的生成记录";
  if (els.veyraAccountUsageTotal) els.veyraAccountUsageTotal.textContent = "-";
  renderVeyraAccountHistory([]);
  renderVeyraUsageList([]);
}

function renderVeyraAccountSummary() {
  const user = veyraAccountUser();
  if (!user) {
    renderVeyraSignedOut();
    return;
  }
  updateAdminSettingsEntry();
  const balance = Number(user.balance);
  if (els.veyraAccountState) els.veyraAccountState.textContent = "已接入";
  if (els.veyraAccountEmail) els.veyraAccountEmail.textContent = user.email || `用户 ${user.user_id || "-"}`;
  if (els.veyraAccountBalance) els.veyraAccountBalance.textContent = formatVeyraMoney(balance);
  if (els.veyraAccountStatus) {
    els.veyraAccountStatus.textContent = Number.isFinite(balance) && balance > 0 ? "可继续生成" : "余额不足会阻止生成";
  }
  if (els.veyraAccountUserId) {
    const role = user.role ? ` · ${user.role}` : "";
    els.veyraAccountUserId.textContent = `User #${user.user_id || "-"}${role}`;
  }
  if (els.veyraAccountHistoryCount) els.veyraAccountHistoryCount.textContent = String(veyraState.history.length);
  if (els.veyraAccountHistoryScope) {
    els.veyraAccountHistoryScope.textContent = isVeyraAdmin() ? "管理员可见全部账户" : "当前账户与旧公共记录";
  }
  if (els.veyraAccountHistoryTitle) {
    els.veyraAccountHistoryTitle.textContent = isVeyraAdmin() ? "全部生成记录" : "我的生成记录";
  }
  if (els.veyraAccountUsageTotal) els.veyraAccountUsageTotal.textContent = formatVeyraMoney(veyraUsageTotal(veyraState.usage));
}

function renderAccountEmpty(container, message, actionLabel = "", onAction = null) {
  if (!container) return;
  container.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "account-empty-state";
  const text = document.createElement("p");
  text.textContent = message;
  empty.appendChild(text);
  if (actionLabel && typeof onAction === "function") {
    const button = document.createElement("button");
    button.className = "button secondary";
    button.type = "button";
    button.textContent = actionLabel;
    button.addEventListener("click", onAction);
    empty.appendChild(button);
  }
  container.appendChild(empty);
}

function renderVeyraAccountHistory(items = []) {
  if (!els.veyraAccountHistoryGrid) return;
  els.veyraAccountHistoryGrid.innerHTML = "";
  if (!getVeyraToken()) {
    renderAccountEmpty(els.veyraAccountHistoryGrid, "登录后这里会按账户展示你自己的生图记录。");
    return;
  }
  const adminView = isVeyraAdmin();
  if (!items.length) {
    renderAccountEmpty(
      els.veyraAccountHistoryGrid,
      adminView ? "当前还没有任何账户生成记录。" : "当前账户还没有生成记录。",
      "去 V2.0 生图",
      () => switchTab("v2"),
    );
    return;
  }
  const sortedItems = [...items].sort(compareHistoryItems);
  sortedItems.slice(0, 24).forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "account-history-card";
    const cardPrompt = accountHistoryCardPrompt(item);
    const imageUrl = accountHistoryImageUrl(item);
    const mock = accountHistoryIsMock(item);
    const preview = document.createElement(mock || !imageUrl ? "div" : "button");
    preview.className = mock || !imageUrl ? "account-mock-preview" : "account-live-preview";
    if (mock || !imageUrl) {
      preview.textContent = `H${index + 1}`;
    } else {
      preview.type = "button";
      const image = document.createElement("img");
      image.src = imageUrl;
      image.alt = cardPrompt || `账户生成记录 ${index + 1}`;
      image.loading = "lazy";
      image.decoding = "async";
      preview.appendChild(image);
      preview.addEventListener("click", () => openAccountHistoryLightbox(item, index));
    }

    const meta = document.createElement("div");
    meta.className = "account-history-meta";
    const title = document.createElement("strong");
    title.textContent = cardPrompt || item.output_id || `生成记录 ${index + 1}`;
    const detail = document.createElement("span");
    detail.textContent = `${accountHistorySourceLabel(item)} · ${accountHistoryProviderText(item)} · ${formatDate(item.created_at || item.updated_at)}`;
    meta.append(title, detail);
    card.append(preview, meta);
    els.veyraAccountHistoryGrid.appendChild(card);
  });
}

function mergeAccountHistory(v1Items = [], v2Items = []) {
  const normalized = [
    ...v1Items.map((item) => ({ ...item, account_history_source: "v1" })),
    ...v2Items.map((item) => ({ ...item, account_history_source: "v2" })),
  ];
  return normalized.sort(compareHistoryItems);
}

function accountHistorySourceLabel(item) {
  return item?.account_history_source === "v1" ? "V1" : "V2";
}

function accountHistoryIsV1(item) {
  return item?.account_history_source === "v1" || Boolean(item?.id && !item?.output_id);
}

function accountHistoryIsMock(item) {
  if (accountHistoryIsV1(item)) return false;
  return Boolean(item?.metadata?.mock || item?.provider_id === "mock_image");
}

function accountHistoryCardPrompt(item) {
  return accountHistoryIsV1(item) ? promptTextFromHistoryItem(item).split("\n").find(Boolean) || item?.prompt || "" : v2HistoryCardPrompt(item);
}

function accountHistoryImageUrl(item, { thumbnail = true } = {}) {
  if (!accountHistoryIsV1(item)) return v2HistoryImageUrl(item, { thumbnail });
  return (thumbnail && item?.thumbnail_url) || item?.url || "";
}

function accountHistoryProviderText(item) {
  return accountHistoryIsV1(item) ? historyProviderResultText(item) : v2HistoryProviderResultText(item);
}

function openAccountHistoryLightbox(item, index = 0) {
  if (!accountHistoryIsV1(item)) {
    openV2HistoryLightbox(item, index);
    return;
  }
  const title = accountHistoryCardPrompt(item);
  openImageLightbox({
    id: item.id,
    title: title ? title.slice(0, 34) : `历史图片 ${index + 1}`,
    url: accountHistoryImageUrl(item, { thumbnail: false }),
    thumbnailUrl: accountHistoryImageUrl(item),
    format: item.format || "png",
    meta: historyMetaText(item),
    promptText: promptTextFromHistoryItem(item),
  });
}

function renderVeyraUsageList(items = []) {
  if (!els.veyraUsageList) return;
  els.veyraUsageList.innerHTML = "";
  if (!getVeyraToken()) {
    renderAccountEmpty(els.veyraUsageList, "登录后这里会展示 Alchemy 生图资金流水。");
    return;
  }
  if (!items.length) {
    renderAccountEmpty(els.veyraUsageList, "当前账户还没有资金消耗记录。");
    return;
  }
  items.slice(0, 40).forEach((item) => {
    const row = document.createElement("article");
    row.className = "account-usage-row";
    const main = document.createElement("div");
    const amount = document.createElement("strong");
    amount.textContent = `-${formatVeyraMoney(item.amount)}`;
    const meta = document.createElement("span");
    meta.textContent = `${item.source || "alchemy"} · ${formatDate(item.created_at)}${item.replayed ? " · 已重放" : ""}`;
    main.append(amount, meta);

    const side = document.createElement("div");
    const balance = document.createElement("strong");
    balance.textContent = formatVeyraMoney(item.balance_after);
    const reference = document.createElement("span");
    reference.textContent = item.reference_id || item.idempotency_key || "-";
    side.append(balance, reference);
    row.append(main, side);
    els.veyraUsageList.appendChild(row);
  });
}

async function loadVeyraAccountPanel({ silent = true, force = false } = {}) {
  if (!getVeyraToken()) {
    veyraState.account = null;
    veyraState.history = [];
    veyraState.usage = [];
    renderVeyraSignedOut();
    return null;
  }
  if (veyraState.loading && !force) return veyraState.account;
  setVeyraAccountLoading(true);
  try {
    const [account, v1HistoryResponse, v2HistoryResponse, usageResponse] = await Promise.all([
      refreshVeyraAccount(),
      request("/v1/image/history?limit=1000"),
      loadV2HistoryResponse(),
      v2Request("/veyra/usage?limit=100"),
    ]);
    veyraState.account = account;
    veyraState.history = mergeAccountHistory(v1HistoryResponse.items || [], v2HistoryResponse.items || []);
    veyraState.usage = usageResponse.items || [];
    renderVeyraAccountSummary();
    renderVeyraAccountHistory(veyraState.history);
    renderVeyraUsageList(veyraState.usage);
    if (!silent) showGlobalToast("账户信息已刷新。");
    return account;
  } catch (error) {
    if (error?.status === 401) {
      setVeyraToken("");
      renderVeyraSignedOut();
    }
    if (!silent) showGlobalToast(`账户刷新失败：${friendlyError(error)}`, "error");
    throw error;
  } finally {
    setVeyraAccountLoading(false);
  }
}

async function v2Request(path, options = {}) {
  const headers = {};
  if (options.body) headers["Content-Type"] = "application/json";
  if (options.headers) Object.assign(headers, options.headers);
  const token = getVeyraToken();
  if (token && !options.skipVeyraAuth && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${v2ApiBase}${path}`, {
    method: options.method || "GET",
    headers: Object.keys(headers).length ? headers : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const detail = await response.text();
    if (response.status === 401 && !options.skipVeyraAuth) setVeyraToken("");
    const buildError = (message) => {
      const error = new Error(message || `HTTP ${response.status}`);
      error.status = response.status;
      return error;
    };
    try {
      const payload = JSON.parse(detail);
      const payloadMessage =
        typeof payload.detail === "string"
          ? payload.detail
          : typeof payload.message === "string"
            ? payload.message
            : detail;
      throw buildError(payloadMessage);
    } catch (error) {
      if (error instanceof SyntaxError) throw buildError(detail);
      throw error;
    }
  }
  return response.json();
}

async function handleV2Asset() {
  const file = els.v2AssetInput?.files?.[0];
  if (!file) return;
  if (!isImageAssetFile(file)) {
    clearV2Asset({ keepNotice: true });
    if (els.v2AssetInput) els.v2AssetInput.value = "";
    updateV2Notice("V2 上传素材目前只支持图片，请选择 PNG、JPEG、WebP 等图片文件。", "warning");
    return;
  }
  const role = v2PrimaryAssetRole();
  const strength = v2SelectedAssetStrength();
  if (els.v2AssetName) els.v2AssetName.textContent = file.name;
  if (els.v2AssetState) els.v2AssetState.textContent = "上传中";
  renderV2AssetPreview(file);
  try {
    const upload = await v2Request("/uploads", {
      method: "POST",
      body: {
        filename: file.name,
        mime_type: file.type || imageMimeTypeFromName(file.name),
        size_bytes: file.size,
        role,
        constraint_strength: strength,
        intended_use: "v2_image_generation",
      },
    });
    if (!upload.upload_url) {
      throw new Error("素材未通过 V2 上传校验。");
    }
    await v2Request(`/uploads/${encodeURIComponent(upload.asset_id)}/content`, {
      method: "PUT",
      body: {
        content_base64: await fileToBase64(file),
        mime_type: file.type || imageMimeTypeFromName(file.name),
      },
    });
    const asset = await v2Request(`/uploads/${encodeURIComponent(upload.asset_id)}/complete`, { method: "POST" });
    if (asset.status !== "ready") {
      throw new Error(asset.error?.message || `素材状态：${asset.status}`);
    }
    v2State.uploadedAssets = [
      {
        asset_id: asset.asset_id,
        filename: asset.filename || file.name,
        status: asset.status,
        role,
        constraint_strength: strength,
        brief: asset.brief || null,
        source_url: asset.source_url || null,
      },
    ];
    renderV2AssetPanel();
    updateV2Notice("V2 素材已分析完成；生成时会交给 Claude 中枢按当前用途绑定。", "success");
  } catch (error) {
    v2State.uploadedAssets = [];
    if (els.v2AssetState) els.v2AssetState.textContent = "失败";
    renderV2AssetPanel();
    updateV2Notice(`V2 素材上传失败：${friendlyError(error)}`, "error");
  }
}

function v2SelectedAssetRoles() {
  return Array.from(document.querySelectorAll("[data-v2-asset-role]:checked"))
    .map((input) => input.dataset.v2AssetRole)
    .filter(Boolean);
}

function v2PrimaryAssetRole() {
  return v2SelectedAssetRoles()[0] || v2State.uploadedAssets[0]?.role || "style_reference";
}

function v2SelectedAssetStrength() {
  return els.v2AssetStrengthInput?.value || v2State.uploadedAssets[0]?.constraint_strength || "strong";
}

function v2AssetPayload() {
  if (!v2State.uploadedAssets.length) return [];
  const roles = v2SelectedAssetRoles();
  if (!roles.length) {
    throw new Error("请至少选择一个 V2 素材用途。");
  }
  const strength = v2SelectedAssetStrength();
  const notes = els.v2AssetNotesInput?.value.trim() || "";
  return v2State.uploadedAssets.flatMap((asset) =>
    roles.map((role) => ({
      asset_id: asset.asset_id,
      role,
      constraint_strength: strength,
      notes,
    }))
  );
}

function renderV2AssetPreview(file) {
  if (!els.v2AssetPreview || !els.v2AssetPreviewLabel) return;
  els.v2AssetPreview.classList.remove("empty-asset-preview");
  els.v2AssetPreview.style.backgroundImage = "";
  els.v2AssetPreviewLabel.textContent = file.name;
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    els.v2AssetPreview.style.backgroundImage = `url("${reader.result}")`;
    els.v2AssetPreviewLabel.textContent = "";
  });
  reader.readAsDataURL(file);
}

function resetV2AssetPreview() {
  if (!els.v2AssetPreview || !els.v2AssetPreviewLabel) return;
  els.v2AssetPreview.classList.add("empty-asset-preview");
  els.v2AssetPreview.style.backgroundImage = "";
  els.v2AssetPreviewLabel.textContent = "未选择素材";
}

function renderV2AssetPanel() {
  const hasAsset = v2State.uploadedAssets.length > 0;
  const roles = v2SelectedAssetRoles();
  const role = roles[0] || v2PrimaryAssetRole();
  const strength = v2SelectedAssetStrength();
  if (hasAsset) {
    v2State.uploadedAssets = v2State.uploadedAssets.map((asset) => ({ ...asset, role, roles, constraint_strength: strength }));
  }
  if (els.v2AssetState) els.v2AssetState.textContent = hasAsset ? "已就绪" : "可选";
  if (els.v2AssetList) {
    els.v2AssetList.innerHTML = "";
    els.v2AssetList.classList.toggle("empty-v2-list", !hasAsset);
    if (!hasAsset) {
      els.v2AssetList.textContent = "暂无上传素材";
    } else {
      v2State.uploadedAssets.forEach((asset) => {
        const row = document.createElement("div");
        row.className = "v2-asset-row";
        const title = document.createElement("strong");
        title.textContent = asset.filename || asset.asset_id;
        const detail = document.createElement("span");
        const summary = asset.brief?.visual_summary ? ` · ${asset.brief.visual_summary}` : "";
        const roleText = roles.length ? roles.map(assetRoleLabel).join(" + ") : "请选择用途";
        detail.textContent = `${roleText} · ${v2ConstraintStrengthLabel(strength)}${summary}`;
        row.append(title, detail);
        els.v2AssetList.appendChild(row);
      });
    }
  }
  if (els.v2AssetLockHint) {
    els.v2AssetLockHint.textContent = v2State.selectedTemplateId
      ? "已选案例优先锁定画面；上传素材只填入主体、Logo、人脸等可替换位置。"
      : "未选案例时，中枢会自由结合素材与案例库。";
  }
}

function clearV2Asset(options = {}) {
  v2State.uploadedAssets = [];
  if (els.v2AssetInput) els.v2AssetInput.value = "";
  if (els.v2AssetName) els.v2AssetName.textContent = "可与案例、提示词协作生效";
  resetV2AssetPreview();
  renderV2AssetPanel();
  if (!options.keepNotice) updateV2Notice("已清空 V2 上传素材。", "info");
}

function v2ConstraintStrengthLabel(value) {
  const labels = {
    required: "必须保留",
    strong: "强参考",
    soft: "弱参考",
  };
  return labels[value] || value || "强参考";
}

async function handleAsset() {
  const file = els.assetInput.files[0];
  if (!file) return;
  if (!isImageAssetFile(file)) {
    els.assetInput.value = "";
    els.assetName.textContent = "仅支持图片素材";
    els.assetState.textContent = "拒绝";
    resetAssetPreview();
    showNotice("高级版素材目前只支持图片，请选择 PNG、JPEG、WebP 等图片文件。", "warning");
    return;
  }
  state.assetMode = "advanced";
  els.assetName.textContent = file.name;
  els.assetState.textContent = "上传";
  renderAssetPreview(file);
  const consent = assetConsentPayload();
  const upload = await request("/v1/assets/upload-url", {
    method: "POST",
    body: {
      filename: file.name,
      mime_type: file.type || imageMimeTypeFromName(file.name),
      size_bytes: file.size,
      declared_role: primaryAssetRole(),
      intended_use: "image_generation",
      consent,
    },
  });
  if (!upload.upload_url) {
    els.assetState.textContent = "拒绝";
    showNotice("素材未通过校验，请更换素材后重试。", "warning");
    return;
  }
  await request(`/v1/assets/${upload.asset_id}/content`, {
    method: "PUT",
    body: {
      content_base64: await fileToBase64(file),
      mime_type: file.type || imageMimeTypeFromName(file.name),
    },
  });
  const asset = await request(`/v1/assets/${upload.asset_id}/complete`, { method: "POST" });
  if (asset.status === "ready") {
    state.assetIds = [asset.id];
    els.assetState.textContent = "高级";
    addEvent("asset.status", `${asset.id} · ${asset.material_brief.asset_type}`);
  } else {
    els.assetState.textContent = asset.status;
  }
}

function isImageAssetFile(file) {
  const mimeType = file.type || imageMimeTypeFromName(file.name);
  return mimeType.startsWith("image/");
}

function imageMimeTypeFromName(filename = "") {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".webp")) return "image/webp";
  if (lower.endsWith(".gif")) return "image/gif";
  if (lower.endsWith(".avif")) return "image/avif";
  if (lower.endsWith(".bmp")) return "image/bmp";
  return "application/octet-stream";
}

function assetConsentPayload() {
  return {
    rights_confirmed: true,
    user_confirmed_rights: true,
    logo_or_trademark_allowed: true,
    portrait_identity_allowed: true,
    commercial_use_allowed: true,
  };
}

async function fileToBase64(file) {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const chunks = [];
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    chunks.push(String.fromCharCode(...bytes.subarray(index, index + chunkSize)));
  }
  return window.btoa(chunks.join(""));
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

function imageAssetPayload() {
  if (!state.assetIds.length) {
    state.assetMode = "basic";
    return {
      asset_mode: "basic",
      asset_ids: [],
    };
  }
  state.assetMode = "advanced";
  const roles = selectedAssetRolesFromDom();
  state.selectedAssetRoles = roles;
  if (!roles.length) {
    throw new Error("请至少选择一个高级版素材用途。");
  }
  return {
    asset_mode: "advanced",
    asset_intents: roles.map((role) => advancedAssetIntentPayload(state.assetIds[0], role)),
  };
}

function advancedAssetIntentPayload(assetId, role) {
  const placementAnchor = els.assetPlacementInput?.value || "bottom_right";
  return {
    asset_id: assetId,
    role,
    priority: assetRolePriority(role),
    preservation: els.assetPreservationInput?.value || (role === "logo_overlay" ? "exact" : "medium"),
    strength: Number(els.assetStrengthInput?.value || 65) / 100,
    notes: els.assetIntentNotesInput?.value.trim() || "",
    placement:
      role === "logo_overlay"
        ? {
            anchor: placementAnchor,
            margin_ratio: 0.06,
            width_ratio: 0.18,
            opacity: 1,
            safe_area: true,
          }
        : null,
    consent: assetConsentPayload(),
  };
}

async function generateImage() {
  const prompt = els.promptInput.value.trim();
  if (!prompt) {
    showNotice("信息不全：请先填写提示词后再生成图片。", "warning");
    showGlobalToast("请先填写提示词。", "error");
    els.promptInput.focus();
    return;
  }
  await ensureSession();
  await flushProviderSettingsSync({ silent: true });
  if (!state.imageProviderReady || els.openaiApiKeyInput.value.trim() || els.geminiImageApiKeyInput.value.trim() || els.anthropicApiKeyInput.value.trim()) {
    await syncProviderSettings({ silent: true });
  }
  if (!state.imageProviderReady) {
    showNotice("生图模型未就绪。请先配置当前选择的 OpenAI 或 Gemini API。", "warning");
    (state.selectedProvider === "gemini_image" ? els.geminiImageApiKeyInput : els.openaiApiKeyInput).focus();
    return;
  }

  let assetPayload;
  try {
    assetPayload = imageAssetPayload();
  } catch (error) {
    showNotice(friendlyError(error), "warning");
    return;
  }

  toggleBusy(true);
  const count = Number(els.countInput.value);
  const providerName = providerLabel(state.selectedProvider);
  const modeText = assetPayload.asset_mode === "advanced" ? "V1.0 高级版" : "V1.0 基础版";
  showNotice(`${modeText}正在生成 ${count} 张图片；优先使用 ${providerName}，质量：${qualityMap[state.selectedQuality]}。`, "info");
  startImageProgress({ label: "生成中", count, providerName });
  renderSkeleton(count);
  try {
    const body = {
      session_id: state.sessionId,
      prompt,
      ...assetPayload,
      count,
      quality: state.selectedQuality,
      work_intensity: state.selectedIntensity,
      output_format: state.selectedFormat,
      provider_preference: state.selectedProvider,
    };
    if (state.selectedSize) {
      body.size = state.selectedSize;
    }
    const job = await request("/v1/image/jobs", {
      method: "POST",
      body,
    });
    stopImageProgress();
    state.currentJob = job;
    setStatus(job.status, job.outputs.length, job.trace_id);
    if (job.status !== "ready" || job.outputs.length === 0) {
      renderGallery([]);
      showNotice(`生成失败：${jobErrorMessage(job)}`, "error");
      await refreshEvents();
      return;
    }
    renderGallery(job.outputs);
    showNotice(`已生成 ${job.outputs.length} 张图片：${imageProviderResultText(job)}。`, "success");
    els.galleryWrap.scrollIntoView({ behavior: "smooth", block: "start" });
    await refreshHistory({ silent: true });
    await refreshEvents();
  } catch (error) {
    stopImageProgress();
    showNotice(`生成失败：${friendlyError(error)}`, "error");
    setStatus("失败", 0, "-");
    renderGallery([]);
  } finally {
    stopImageProgress();
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
  showNotice("V1.0 基础版正在生成修改版本。", "info");
  startImageProgress({ label: "修改中", count: 1, providerName: providerLabel(state.selectedProvider), traceId: state.currentJob.trace_id });
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
    stopImageProgress();
    state.currentJob = job;
    setStatus(job.status, job.outputs.length, job.trace_id);
    if (job.status !== "ready" || job.outputs.length === 0) {
      showNotice(`修改失败：${jobErrorMessage(job)}`, "error");
      await refreshEvents();
      return;
    }
    renderGallery(job.outputs);
    showNotice(`修改版本已生成：${imageProviderResultText(job)}。`, "success");
    els.galleryWrap.scrollIntoView({ behavior: "smooth", block: "start" });
    await refreshHistory({ silent: true });
    await refreshEvents();
  } catch (error) {
    stopImageProgress();
    showNotice(`修改失败：${friendlyError(error)}`, "error");
  } finally {
    stopImageProgress();
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
    const footer = node.querySelector(".output-meta");
    preview.dataset.label = `${output.format.toUpperCase()} · ${index + 1}`;
    preview.innerHTML = `<img class="output-image" alt="生成结果 ${index + 1}" src="${output.thumbnail_url || output.url}" loading="lazy" decoding="async" />`;
    id.textContent = output.id;
    const provider = document.createElement("span");
    provider.className = "output-provider";
    provider.textContent = outputProviderResultText(output, state.currentJob);
    footer.insertBefore(provider, link);
    bindDownloadLink(link, output.url, `${output.id}.${output.format === "jpeg" ? "jpg" : output.format}`);
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
        meta: `${outputProviderResultText(output, state.currentJob)} · ${output.format.toUpperCase()} · ${output.width || "-"}x${output.height || "-"}`,
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
    state.historyItems = history.items || [];
    state.historyRenderLimit = historyPageSize;
    renderHistory(state.historyItems);
    if (activePanelName() !== "v2") renderHeroHistory(history.items || [], { source: "v1" });
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
  const renderLimit = Math.min(state.historyRenderLimit, sortedItems.length);
  const renderedItems = sortedItems.slice(0, renderLimit);
  els.historyCount.textContent = renderLimit < sortedItems.length ? `${renderLimit}/${sortedItems.length}` : String(sortedItems.length);
  els.historyGallery.classList.toggle("empty-history", sortedItems.length === 0);
  renderedItems.forEach((item, index) => {
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
    prompt.textContent = item.original_prompt || item.prompt || "本地历史图片";

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
    bindDownloadLink(link, item.url, `${item.id}.${item.format === "jpeg" ? "jpg" : item.format}`);
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
  if (renderLimit < sortedItems.length) {
    const loadMore = document.createElement("article");
    loadMore.className = "history-load-more";
    const text = document.createElement("span");
    text.textContent = `已加载 ${renderLimit} / ${sortedItems.length}`;
    const button = document.createElement("button");
    button.className = "button secondary";
    button.type = "button";
    button.textContent = "加载更多历史";
    button.addEventListener("click", () => {
      state.historyRenderLimit = Math.min(state.historyRenderLimit + historyPageSize, sortedItems.length);
      renderHistory(state.historyItems);
    });
    loadMore.append(text, button);
    els.historyGallery.appendChild(loadMore);
  }
}

function renderHeroHistory(items, { source = "v1" } = {}) {
  if (!els.heroHistoryCarousel) return;
  clearHeroCarouselTimer();
  const heroItems = [...items]
    .filter((item) => (source === "v2" ? isRenderableV2HistoryImage(item) : item.url || item.thumbnail_url))
    .sort(compareHistoryItems)
    .slice(0, heroHistoryPageSize)
    .map((item, index) => normalizeHeroHistoryItem(item, source, index));
  state.heroHistorySource = source;
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
    image.src = item.thumbnailUrl || item.url;
    image.alt = item.title || `历史生成作品 ${index + 1}`;
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
    title: item.title ? item.title.slice(0, 34) : "历史图片",
    url: item.url,
    thumbnailUrl: item.thumbnailUrl || item.url,
    format: item.format,
    meta: item.meta,
    promptText: item.promptText,
  });
}

function normalizeHeroHistoryItem(item, source, index) {
  if (source === "v2") {
    const title = v2HistoryCardPrompt(item) || `2.0 历史图片 ${index + 1}`;
    return {
      id: item.output_id || item.id || `v2-history-${index}`,
      title,
      url: v2HistoryImageUrl(item, { thumbnail: false }),
      thumbnailUrl: v2HistoryImageUrl(item),
      format: v2HistoryFormat(item),
      meta: `${v2HistoryProviderResultText(item)} · ${formatDate(item.created_at || item.updated_at)}`,
      promptText: v2PromptTextFromHistory(item),
      source: "v2",
    };
  }
  return {
    id: item.id,
    title: item.original_prompt || item.prompt || `历史图片 ${index + 1}`,
    url: item.url,
    thumbnailUrl: item.thumbnail_url || item.url,
    format: item.format,
    meta: historyMetaText(item),
    promptText: promptTextFromHistoryItem(item),
    source: "v1",
  };
}

function activePanelName() {
  return document.querySelector("[data-panel].active")?.dataset.panel || "image";
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
    title: (item.original_prompt || item.prompt) ? (item.original_prompt || item.prompt).slice(0, 34) : "历史图片",
    url: item.url,
    thumbnailUrl: item.thumbnail_url || item.url,
    format: item.format,
    meta: historyMetaText(item),
    promptText: promptTextFromHistoryItem(item),
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

function openImageLightbox({ id, title, url, thumbnailUrl, format, meta, promptText, actions = [] }) {
  els.lightboxTitle.textContent = title || "图片预览";
  els.lightboxImage.src = url;
  els.lightboxImage.alt = title || "放大预览图";
  els.lightboxImage.dataset.fullUrl = url;
  els.lightboxImage.dataset.shareTitle = title || "Alchemy 生成图片";
  els.lightboxImage.dataset.shareImage = url || "";
  els.lightboxImage.dataset.shareThumb = thumbnailUrl || shareThumbFromImageUrl(url);
  els.lightboxImage.dataset.shareDesc = shareDescriptionFromPrompt(promptText);
  els.lightboxMeta.textContent = meta || id || "-";
  const fullPrompt = promptText || "";
  els.lightboxPromptText.textContent = fullPrompt || "这张图片没有记录到提示词。";
  els.lightboxPromptText.scrollTop = 0;
  els.lightboxPromptBtn.disabled = !fullPrompt;
  els.copyPromptBtn.disabled = !fullPrompt;
  setPromptCopyState("复制");
  els.lightboxPromptBtn.classList.toggle("available", Boolean(fullPrompt));
  closeLightboxPrompt();
  resetLightboxZoom();
  bindDownloadLink(els.lightboxDownload, url, `${id || "image"}.${format === "jpeg" ? "jpg" : format || "png"}`);
  renderLightboxActions([{ label: "分享", tone: "primary", run: shareCurrentLightboxImage }, ...actions]);
  els.imageLightbox.hidden = false;
  document.body.classList.add("modal-open");
  els.closeImageLightboxBtn.focus();
}

function closeImageLightbox() {
  els.imageLightbox.hidden = true;
  els.lightboxImage.removeAttribute("src");
  els.lightboxImage.removeAttribute("data-full-url");
  els.lightboxImage.removeAttribute("data-share-title");
  els.lightboxImage.removeAttribute("data-share-image");
  els.lightboxImage.removeAttribute("data-share-thumb");
  els.lightboxImage.removeAttribute("data-share-desc");
  resetLightboxZoom();
  closeLightboxPrompt();
  renderLightboxActions([]);
  document.body.classList.remove("modal-open");
}

function renderLightboxActions(actions = []) {
  activeLightboxActions = Array.isArray(actions) ? actions.filter((action) => action && action.label && typeof action.run === "function") : [];
  if (!els.lightboxActionBar) return;
  els.lightboxActionBar.innerHTML = "";
  els.lightboxActionBar.hidden = activeLightboxActions.length === 0;
  activeLightboxActions.forEach((action, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `button ${action.tone === "danger" ? "ghost lightbox-danger-action" : action.tone === "primary" ? "primary" : "secondary"}`;
    button.textContent = action.label;
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await activeLightboxActions[index]?.run();
      } finally {
        if (button.isConnected) button.disabled = false;
      }
    });
    els.lightboxActionBar.appendChild(button);
  });
}

async function shareCurrentLightboxImage() {
  const originalImageUrl = els.lightboxImage.dataset.shareImage || els.lightboxImage.dataset.fullUrl || els.lightboxImage.src;
  const title = els.lightboxImage.dataset.shareTitle || els.lightboxTitle.textContent || "Alchemy 生成图片";
  const desc = els.lightboxImage.dataset.shareDesc || "来自 Alchemy Media Agent 的 AI 影像作品。";
  const cardShareUrl = buildShareImageUrl({
    imageUrl: originalImageUrl,
    thumbUrl: els.lightboxImage.dataset.shareThumb || els.lightboxImage.dataset.shareImage,
    title,
    desc,
  });
  const posterUrl = buildSharePosterUrl({
    imageUrl: originalImageUrl,
    thumbUrl: els.lightboxImage.dataset.shareThumb || els.lightboxImage.dataset.shareImage,
    desc: "扫码查看原图",
    shareUrl: cardShareUrl,
  });
  showSharePosterPanel({
    posterUrl,
    shareUrl: cardShareUrl,
    title: "Alchemy Media Agent",
    desc: "下载分享图发送到微信，扫码打开。",
  });
}

function buildSharePosterUrl({ imageUrl, thumbUrl, desc, shareUrl }) {
  const params = new URLSearchParams();
  params.set("image", absoluteUrl(imageUrl));
  params.set("thumb", absoluteUrl(thumbUrl || imageUrl));
  params.set("title", "Alchemy Media Agent");
  params.set("desc", compactShareText(desc, "扫码查看原图", 18));
  params.set("url", shareUrl);
  return `${window.location.origin}/share/poster?${params.toString()}`;
}

function showSharePosterPanel({ posterUrl, shareUrl, title, desc }) {
  document.querySelector(".share-poster-sheet")?.remove();
  const sheet = document.createElement("section");
  sheet.className = "share-poster-sheet";
  sheet.setAttribute("role", "dialog");
  sheet.setAttribute("aria-modal", "true");
  sheet.innerHTML = `
    <button class="share-poster-backdrop" type="button" aria-label="关闭分享海报"></button>
    <article class="share-poster-card">
      <div class="share-poster-copy">
        <span>分享海报</span>
        <strong></strong>
        <p></p>
        <small class="share-poster-note"></small>
      </div>
      <div class="share-poster-preview">
        <img alt="分享海报预览" />
      </div>
      <div class="share-poster-actions">
        <a class="button primary share-poster-download" download="alchemy-share-poster.png">下载分享图</a>
        <button class="button secondary share-poster-copy-link" type="button">分享链接</button>
        <button class="button ghost share-poster-close" type="button">关闭</button>
      </div>
    </article>
  `;
  sheet.querySelector("strong").textContent = title || "Alchemy Media Agent";
  sheet.querySelector("p").textContent = desc || "下载图片发到微信，好友扫码即可打开。";
  sheet.querySelector(".share-poster-note").textContent = isWeChatBrowser() ? "微信内请用右上角分享" : "二维码进入分享页";
  const image = sheet.querySelector("img");
  image.src = posterUrl;
  const download = sheet.querySelector(".share-poster-download");
  download.href = posterUrl;
  sheet.querySelector(".share-poster-backdrop").addEventListener("click", () => sheet.remove());
  sheet.querySelector(".share-poster-close").addEventListener("click", () => sheet.remove());
  sheet.querySelector(".share-poster-copy-link").addEventListener("click", async () => {
    await shareOrCopyLink(shareUrl, "Alchemy Media Agent");
  });
  document.body.appendChild(sheet);
  if (!isWeChatBrowser()) {
    showGlobalToast("分享图已生成，可下载后发微信。");
  }
}

function shareThumbFromImageUrl(url = "") {
  if (!url) return "/static/showcase/city-poster.jpg";
  if (url.includes("/download")) return url.replace(/\/download(?:\?.*)?$/, "/thumbnail");
  return url;
}

function buildShareImageUrl({ imageUrl, thumbUrl, title, desc }) {
  const params = new URLSearchParams();
  params.set("image", absoluteUrl(imageUrl));
  params.set("thumb", absoluteUrl(thumbUrl || imageUrl));
  params.set("title", compactShareText(title, "Alchemy 生成图片", 48));
  params.set("desc", compactShareText(desc, "来自 Alchemy Media Agent 的 AI 影像作品。", 88));
  return `${window.location.origin}/share/image?${params.toString()}`;
}

function shareDescriptionFromPrompt(promptText = "") {
  const text = compactShareText(promptText, "来自 Alchemy Media Agent 的 AI 影像作品。", 88);
  return text.replace(/^(原始提示词|Agent 最终提示词|Claude 思考后的最终提示词)\s*/i, "") || "来自 Alchemy Media Agent 的 AI 影像作品。";
}

function absoluteUrl(url = "") {
  if (!url) return `${window.location.origin}/static/showcase/city-poster.jpg`;
  try {
    return new URL(url, window.location.origin).href;
  } catch {
    return `${window.location.origin}/static/showcase/city-poster.jpg`;
  }
}

function compactShareText(value, fallback, limit) {
  const compact = String(value || "").replace(/\s+/g, " ").trim();
  return (compact || fallback).slice(0, limit);
}

function isWeChatBrowser() {
  return /MicroMessenger/i.test(navigator.userAgent || "");
}

async function copyShareUrl(url) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(url);
    return;
  }
  copyTextFallback(url);
}

async function shareOrCopyLink(url, title = "Alchemy Media Agent") {
  if (isWeChatBrowser()) {
    try {
      await copyShareUrl(url);
      showGlobalToast("链接已复制。");
    } catch (error) {
      showGlobalToast("复制失败，请手动复制。", "error");
    }
    showWeChatShareGuide();
    return;
  }
  if (navigator.share && !isWeChatBrowser()) {
    try {
      await navigator.share({ title, url });
      showGlobalToast("分享面板已打开。");
      return;
    } catch (error) {
      if (error?.name === "AbortError") return;
    }
  }
  try {
    await copyShareUrl(url);
    showGlobalToast("分享链接已复制。");
  } catch (error) {
    showGlobalToast("复制失败，请手动复制。", "error");
  }
}

function showWeChatShareGuide(shareUrl) {
  const guide = document.createElement("button");
  guide.type = "button";
  guide.className = "wechat-share-guide";
  guide.innerHTML = `
    <span>微信分享</span>
    <strong>请用右上角分享</strong>
    <small>按钮会复制链接。</small>
  `;
  guide.addEventListener("click", () => guide.remove());
  document.body.appendChild(guide);
  window.setTimeout(() => {
    if (guide.isConnected) guide.remove();
  }, 5200);
}

function toggleLightboxZoom(event) {
  event.stopPropagation();
  if (!els.lightboxStage || !els.lightboxImage.src) return;
  const zoomed = els.lightboxStage.classList.toggle("zoomed");
  els.lightboxImage.classList.toggle("zoomed", zoomed);
}

function resetLightboxZoom() {
  els.lightboxStage?.classList.remove("zoomed");
  els.lightboxImage?.classList.remove("zoomed");
  if (els.lightboxStage) {
    els.lightboxStage.scrollTop = 0;
    els.lightboxStage.scrollLeft = 0;
  }
}

function bindDownloadLink(link, url, filename) {
  if (!link) return;
  link.href = url || "#";
  link.download = filename || "image.png";
  link.dataset.downloadUrl = url || "";
  link.dataset.downloadFilename = filename || "image.png";
  if (link.dataset.downloadBound !== "true") {
    link.addEventListener("click", handleDownloadLinkClick);
    link.dataset.downloadBound = "true";
  }
}

async function handleDownloadLinkClick(event) {
  event.preventDefault();
  event.stopPropagation();
  const link = event.currentTarget;
  const url = link?.dataset?.downloadUrl || link?.href;
  const filename = link?.dataset?.downloadFilename || link?.download || "image.png";
  if (!url || url === "#") return;
  await downloadImageFile(url, filename, link);
}

async function downloadImageFile(url, filename, link) {
  const originalText = link?.textContent;
  if (link?.dataset.downloading === "true") return;
  if (link) {
    link.dataset.downloading = "true";
    link.textContent = "下载中";
  }
  try {
    const response = await fetch(url, { credentials: "include" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename || "image.png";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1200);
    showGlobalToast("图片下载已开始。");
  } catch (error) {
    const fallbackUrl = url.startsWith("http") || url.startsWith("/") ? url : link?.href;
    if (fallbackUrl) window.open(fallbackUrl, "_blank", "noopener,noreferrer");
    showGlobalToast("下载受浏览器限制，已在新标签打开原图。");
  } finally {
    if (link) {
      link.dataset.downloading = "false";
      link.textContent = originalText || "下载";
    }
  }
}

function toggleLightboxPrompt() {
  if (els.lightboxPromptBtn.disabled) return;
  els.lightboxPromptPanel.hidden = !els.lightboxPromptPanel.hidden;
  if (!els.lightboxPromptPanel.hidden) {
    els.lightboxPromptText.focus({ preventScroll: true });
  }
}

function closeLightboxPrompt() {
  els.lightboxPromptPanel.hidden = true;
}

async function copyLightboxPrompt() {
  const prompt = els.lightboxPromptText.textContent || "";
  if (!prompt || els.copyPromptBtn.disabled) return;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(prompt);
    } else {
      copyTextFallback(prompt);
    }
    setPromptCopyState("已复制", true);
    showGlobalToast("完整提示词已复制。");
  } catch (error) {
    copyTextFallback(prompt);
    setPromptCopyState("已复制", true);
    showGlobalToast("完整提示词已复制。");
  }
}

function copyTextFallback(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("copy_failed");
}

function setPromptCopyState(label, copied = false) {
  els.copyPromptBtn.textContent = label;
  els.copyPromptBtn.classList.toggle("copied", copied);
  window.clearTimeout(setPromptCopyState.timer);
  if (copied) {
    setPromptCopyState.timer = window.setTimeout(() => setPromptCopyState("复制"), 1600);
  }
}

function promptTextFromJob(job) {
  const plan = job?.prompt_plan;
  if (!plan) return "";
  const advanced = plan.variables?.advanced_prompt_plan;
  if (advanced) {
    return advancedPromptDisplayText({
      originalPrompt: advanced.original_prompt || plan.variables?.original_prompt || plan.main_subject,
      finalPrompt: advanced.final_prompt || plan.variables?.generation_prompt,
      assetIntents: job.asset_plan?.assets || [],
      assetVisionProfiles: advanced.asset_vision_profiles || plan.variables?.asset_vision_profiles || [],
      providerInputPlan: advanced.provider_input_plan || plan.variables?.provider_input_plan || job.asset_plan?.provider_input_plan,
      visualReview: job.outputs?.[0]?.visual_review,
      negativePrompt: advanced.negative_prompt,
    });
  }
  const generationPrompt = plan.variables?.generation_prompt;
  if (generationPrompt) return generationPrompt;
  return [plan.main_subject, plan.scene, plan.style, plan.composition]
    .filter(Boolean)
    .join("\n");
}

function promptTextFromHistoryItem(item) {
  if (item?.asset_mode === "advanced" || item?.asset_plan || item?.original_prompt || item?.final_prompt) {
    return advancedPromptDisplayText({
      originalPrompt: item.original_prompt || item.prompt || "",
      finalPrompt: item.final_prompt || item.prompt || "",
      assetIntents: item.asset_intents || item.asset_plan?.assets || [],
      assetVisionProfiles: item.asset_vision_profiles || item.prompt_plan?.asset_vision_profiles || [],
      providerInputPlan: item.provider_input_plan || item.prompt_plan?.provider_input_plan || item.asset_plan?.provider_input_plan,
      visualReview: item.visual_review,
      negativePrompt: item.prompt_plan?.negative_prompt,
    });
  }
  return item?.prompt || "";
}

function advancedPromptDisplayText({ originalPrompt, finalPrompt, assetIntents, assetVisionProfiles, providerInputPlan, visualReview, negativePrompt }) {
  const roleLines = (assetIntents || []).map((item) => {
    const label = item.role_label || assetRoleLabel(item.role);
    const strength = item.strength !== undefined ? ` · 强度 ${Math.round(Number(item.strength) * 100)}%` : "";
    const preservation = item.preservation ? ` · ${assetPreservationLabel(item.preservation)}` : "";
    return `- ${label}${preservation}${strength}`;
  });
  const visionLines = (assetVisionProfiles || []).map((profile) => {
    const status = profile.status ? ` · ${assetVisionStatusLabel(profile.status)}` : "";
    const summary = profile.summary || profile.image?.filename || profile.asset_id || "图片素材";
    return `- ${summary}${status}`;
  });
  const inputLines = providerInputPlan
    ? [
        `- 操作：${providerInputOperationLabel(providerInputPlan.operation)}`,
        `- 参考图片：${providerInputPlan.reference_image_count || 0} 张`,
        providerInputPlan.postprocess_asset_ids?.length ? `- 后处理素材：${providerInputPlan.postprocess_asset_ids.length} 个` : "",
      ].filter(Boolean)
    : [];
  const reviewLines = visualReview
    ? [
        visualReview.overall_score !== undefined && visualReview.overall_score !== null
          ? `- 综合评分：${Math.round(Number(visualReview.overall_score) * 100)}%`
          : "",
        ...(visualReview.issues || []).map((issue) => `- ${issue.message || issue.code || "复检提醒"}`),
        visualReview.retry_recommendation ? `- ${visualReview.retry_recommendation}` : "",
      ].filter(Boolean)
    : [];
  return [
    "原始提示词",
    originalPrompt || "-",
    "",
    "高级素材用途",
    roleLines.length ? roleLines.join("\n") : "-",
    "",
    "素材视觉理解",
    visionLines.length ? visionLines.join("\n") : "-",
    "",
    "图片输入链路",
    inputLines.length ? inputLines.join("\n") : "-",
    "",
    "视觉复检",
    reviewLines.length ? reviewLines.join("\n") : "-",
    "",
    "最终提示词",
    finalPrompt || "-",
    negativePrompt ? `\n负向约束\n${negativePrompt}` : "",
  ]
    .filter((part) => part !== "")
    .join("\n");
}

function assetVisionStatusLabel(value) {
  const labels = {
    pending: "等待分析",
    ready: "已分析",
    failed: "分析失败",
    skipped: "已跳过",
  };
  return labels[value] || value;
}

function providerInputOperationLabel(value) {
  const labels = {
    generate: "文生图",
    image_edit_with_reference_images: "带参考图生成",
    image_edit_with_mask: "局部编辑",
    "images.edit": "图片编辑接口",
  };
  return labels[value] || value || "未声明";
}

function assetRoleLabel(role) {
  const labels = {
    style_reference: "风格参考",
    subject_reference: "主体参考",
    logo_reference: "Logo/标识",
    face_reference: "人物脸/身份",
    logo_overlay: "Logo/标识",
    portrait_identity: "人物脸/身份",
    background_reference: "背景参考",
    composition_reference: "构图参考",
    color_reference: "色彩参考",
    local_edit: "局部修改",
    negative_reference: "反向参考",
  };
  return labels[role] || role || "素材";
}

function assetFusionModeLabel(value) {
  const labels = {
    logo_product_surface: "Logo 融入物体表面",
    logo_canvas_brand_mark: "Logo 作为海报品牌标识",
    logo_template_slot: "Logo 填入模板品牌槽",
    logo_brand_mark: "Logo 品牌标识",
    typographic_brand_text: "品牌文字排版",
    subject_identity: "主体身份保留",
    face_identity: "人脸身份保留",
    background_identity: "背景身份保留",
    background_mood: "背景氛围参考",
    style_signal: "风格信号参考",
    composition_signal: "构图信号参考",
    color_signal: "色彩信号参考",
    negative_visual_exclusion: "反向视觉排除",
    reference: "参考素材",
  };
  return labels[value] || value || "参考素材";
}

function assetPreservationLabel(value) {
  const labels = {
    loose: "宽松参考",
    medium: "中等参考",
    strict: "强保真",
    exact: "精确保留",
  };
  return labels[value] || value;
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

function startImageProgress({ label, count, providerName, traceId = "pending" }) {
  stopImageProgress();
  state.imageProgressStartedAt = Date.now();
  state.imageProgressLabel = label || "生成中";
  const detail = `${providerName || "生图引擎"} · ${count || 1} 张`;
  const update = () => {
    const elapsed = imageProgressElapsedLabel();
    setStatus(`${state.imageProgressLabel} · ${elapsed}`, 0, traceId);
    if (els.outputCount) els.outputCount.title = detail;
  };
  update();
  state.imageProgressTimer = window.setInterval(update, 1000);
}

function stopImageProgress() {
  if (!state.imageProgressTimer) return;
  window.clearInterval(state.imageProgressTimer);
  state.imageProgressTimer = null;
}

function imageProgressElapsedLabel() {
  if (!state.imageProgressStartedAt) return "0s";
  const seconds = Math.max(0, Math.round((Date.now() - state.imageProgressStartedAt) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
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
  const headers = {};
  if (options.body) headers["Content-Type"] = "application/json";
  if (options.headers) Object.assign(headers, options.headers);
  const token = getVeyraToken();
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: Object.keys(headers).length ? headers : undefined,
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
  const detail = job.error.detail || {};
  if (detail.primary_provider) {
    const primary = providerLabel(detail.primary_provider);
    const fallback = providerLabel(detail.fallback_provider || job.error.provider);
    const primaryReason = detail.primary_error_message || detail.primary_error_code || "未知原因";
    const fallbackReason = detail.fallback_error_message || job.error.message || job.error.code || "未知原因";
    return `${primary} 失败：${primaryReason}；已尝试 ${fallback} 兜底，也失败：${fallbackReason}。`;
  }
  if (job.error.code === "rate_limit_error") {
    const retryAfter = job.error.detail?.retry_after_seconds;
    const waitHint = retryAfter ? `预计 ${retryAfter} 秒后再试。` : "请稍后再试。";
    return `上游图片额度或并发受限，系统已进入本地保护冷却。${waitHint}`;
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
  const providerText = historyProviderResultText(item);
  const parts = [providerText || model];
  const intensity = item.work_intensity_label || intensityMap[item.work_intensity]?.label;
  if (intensity) parts.push(`强度：${intensity}`);
  parts.push(formatDate(item.created_at || item.updated_at));
  return parts.filter(Boolean).join(" · ");
}
