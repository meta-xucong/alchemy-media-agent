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

const geminiImageGenerationTemporarilyDisabled = true;
const geminiImageUnavailableReason = "Gemini 生图暂不可用，恢复后会重新开放。";
const geminiImageUnavailableShortLabel = "暂不可用";
const heroCopyByTab = {
  image: "AI 自动优化创作表达，快速生成高质感视觉内容。",
  v2: "智能中枢统筹创意策略，案例体系赋能品牌视觉升级。",
  lab: "探索各种创意玩法",
  video: "coming soon",
  account: "账户资金、生成历史与消耗记录集中查看。",
};
const coffeeSamplePrompt = "生成 4 张日系清爽风格的咖啡产品海报，适配手机竖屏的";
const defaultImageCount = "1";
const coffeeSampleCount = "4";
const heroCarouselIntervalMs = 5000;
const historyPageSize = 24;
const heroHistoryPageSize = 8;
const v2TemplatePageSize = 16;
const v2TemplateEagerImageCount = 6;
const v2HistoryPageSize = 24;
const labStylePageSize = 80;
const labPollIntervalMs = 3000;
const labPollMaxAttempts = 360;
const labDefaultGenerationIntervalSeconds = 8;
const labReferenceMaxBytes = 12 * 1024 * 1024;
const labReferenceMimeTypes = ["image/png", "image/jpeg", "image/webp"];
const labReferenceRoleLabels = {
  subject_reference: "主体参考",
  product_reference: "产品参考",
  style_material_reference: "风格/材质参考",
  composition_reference: "构图参考",
  logo_reference: "Logo/标识",
};
const labReferenceStrengthLabels = {
  required: "必须保留",
  strong: "强约束",
  soft: "轻参考",
};
const v2RunLongWaitAttempt = 120;
const localPortalHomeUrl = "http://127.0.0.1:18080/";
const productionPortalHomeUrl = "https://aiself.vip/";
const v2ApiBase = window.ALCHEMY_V2_API_BASE || `${window.location.origin}/api/v2`;
const veyraTokenStorageKey = "alchemy_veyra_access_token";
const veyraAccountStorageKey = "alchemy_veyra_account";
const defaultVeyraLoginBaseUrl = "https://aiself.vip";

function isLocalAlchemyHost() {
  return ["127.0.0.1", "localhost", "::1", "[::1]"].includes(window.location.hostname);
}

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
const v2PromptTransformModes = {
  auto: { label: "自动", hint: "系统按 V2 场景自动选择：手选模板走原样保框架；智能增强、修图和批量走增强保约束；不会自动进入探索。" },
  stable: { label: "原样", hint: "弱介入：保留 Claude 输出的最终提示词，不额外包增强规则，适合做基准对比或看自然稳定效果。" },
  enhanced: { label: "增强", hint: "中介入：让 Claude 优化创意提示词，并在生成前加保真守护，适合文字、Logo、尺寸或素材用途必须稳住的任务。" },
  exploration: { label: "探索", hint: "强创意介入：让 Claude 主动换一种创意路径，例如角度、姿态、光影、背景层次或色彩氛围；适合找灵感和更大胆的备选方向。" },
};

const state = {
  sessionId: null,
  assetIds: [],
  assets: [],
  assetMode: "basic",
  selectedAssetRoles: ["style_reference"],
  currentJob: null,
  selectedOutputId: null,
  selectedRevisionSource: null,
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
  historyFavoritesOnly: false,
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
  templateIndex: null,
  templateTotal: 0,
  templateNextCursor: null,
  templateHasMore: false,
  templateLoadingMore: false,
  templatePrefetchKey: "",
  templatePrefetchPromise: null,
  templatePrefetchPage: null,
  templateDetailCache: {},
  templates: [],
  visibleTemplates: [],
  history: [],
  historyFavoritesOnly: false,
  selectedTemplateId: null,
  selectedTemplateDetail: null,
  favoriteReferenceItem: null,
  favoriteReferenceAsset: null,
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
  promptTransformMode: "auto",
};

const labState = {
  loaded: false,
  loading: false,
  styles: [],
  limits: { maxSelectedStyles: 8, maxImagesPerStyle: 2, maxTotalImages: 12, maxConcurrentGenerations: 1, defaultGenerationIntervalSeconds: 8 },
  selectedStyleIds: [],
  activeModule: "",
  targetCount: 4,
  imagesPerStyle: 1,
  generationIntervalSeconds: labDefaultGenerationIntervalSeconds,
  mode: "minimal",
  styleFamily: "",
  freshness: "high",
  intentDirector: "auto",
  qualityEnhancement: "auto",
  seed: "",
  search: "",
  semanticSearchQuery: "",
  semanticSearchResults: [],
  semanticSearchSource: "",
  semanticSearchLoading: false,
  styleRenderLimit: labStylePageSize,
  styleLibraryOpen: true,
  referenceOpen: true,
  referenceAssets: [],
  referenceRole: "subject_reference",
  referenceStrength: "strong",
  referenceNotes: "",
  referenceUploading: false,
  aspectRatio: "square",
  history: [],
  historyLoaded: false,
  historyLoading: false,
  currentSession: null,
  currentBoard: null,
  pollTimer: null,
  pollAttempt: 0,
  navOpen: false,
};

const veyraState = {
  account: null,
  history: [],
  usage: [],
  usedTemplates: [],
  loading: false,
  authPolicy: null,
};

function isGeminiImageTemporarilyDisabled(provider) {
  return geminiImageGenerationTemporarilyDisabled && provider === "gemini_image";
}

function safeImageProviderPreference(provider, fallback = "openai_gpt_image") {
  const allowed = ["auto", "openai_gpt_image", "doubao_image", "gemini_image", "mock_image"];
  if (!allowed.includes(provider)) return fallback;
  return isGeminiImageTemporarilyDisabled(provider) ? fallback : provider;
}

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
  labNavMenu: document.querySelector(".lab-nav-menu"),
  labNavTab: document.querySelector(".lab-nav-menu [data-tab='lab']"),
  labNavDropdown: document.querySelector(".lab-nav-dropdown"),
  heroLine: document.querySelector(".hero-line"),
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
  v2DoubaoImageState: document.querySelector("#v2DoubaoImageState"),
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
  v2PromptInput: document.querySelector("#v2PromptInput"),
  v2PromptTransformState: document.querySelector("#v2PromptTransformState"),
  v2PromptTransformHint: document.querySelector("#v2PromptTransformHint"),
  v2NoticeBar: document.querySelector("#v2NoticeBar"),
  v2ProgressPanel: document.querySelector("#v2ProgressPanel"),
  v2ProgressTitle: document.querySelector("#v2ProgressTitle"),
  v2ProgressElapsed: document.querySelector("#v2ProgressElapsed"),
  v2ProgressFill: document.querySelector("#v2ProgressFill"),
  v2ProgressSteps: document.querySelector("#v2ProgressSteps"),
  v2ProgressDetail: document.querySelector("#v2ProgressDetail"),
  v2RunBtn: document.querySelector("#v2RunBtn"),
  v2SelectedTemplateLabel: document.querySelector("#v2SelectedTemplateLabel"),
  v2PickFavoriteReferenceBtn: document.querySelector("#v2PickFavoriteReferenceBtn"),
  v2ClearFavoriteReferenceBtn: document.querySelector("#v2ClearFavoriteReferenceBtn"),
  v2FavoriteReferenceLabel: document.querySelector("#v2FavoriteReferenceLabel"),
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
  v2HistoryFavoritesOnly: document.querySelector("#v2HistoryFavoritesOnly"),
  v2RefreshHistoryBtn: document.querySelector("#v2RefreshHistoryBtn"),
  v2HistoryGrid: document.querySelector("#v2HistoryGrid"),
  labStyleCount: document.querySelector("#labStyleCount"),
  labLimitsLabel: document.querySelector("#labLimitsLabel"),
  labHomePanel: document.querySelector("#labHomePanel"),
  rareStyleExplorerPanel: document.querySelector("#rareStyleExplorerPanel"),
  labIdeaInput: document.querySelector("#labIdeaInput"),
  labNoticeBar: document.querySelector("#labNoticeBar"),
  labIntentSummary: document.querySelector("#labIntentSummary"),
  labIntentSummaryTitle: document.querySelector("#labIntentSummaryTitle"),
  labIntentSummaryText: document.querySelector("#labIntentSummaryText"),
  labTargetCountInput: document.querySelector("#labTargetCountInput"),
  labTargetCountValue: document.querySelector("#labTargetCountValue"),
  labImagesPerStyleInput: document.querySelector("#labImagesPerStyleInput"),
  labImagesPerStyleValue: document.querySelector("#labImagesPerStyleValue"),
  labIntervalInput: document.querySelector("#labIntervalInput"),
  labIntervalValue: document.querySelector("#labIntervalValue"),
  labModeInput: document.querySelector("#labModeInput"),
  labFamilyInput: document.querySelector("#labFamilyInput"),
  labFreshnessInput: document.querySelector("#labFreshnessInput"),
  labIntentDirectorInput: document.querySelector("#labIntentDirectorInput"),
  labQualityEnhancementInput: document.querySelector("#labQualityEnhancementInput"),
  labSeedInput: document.querySelector("#labSeedInput"),
  labStyleSearchInput: document.querySelector("#labStyleSearchInput"),
  labStyleSearchBtn: document.querySelector("#labStyleSearchBtn"),
  labStyleSearchThinking: document.querySelector("#labStyleSearchThinking"),
  labClearStylesBtn: document.querySelector("#labClearStylesBtn"),
  labStyleLibraryToggleBtn: document.querySelector("#labStyleLibraryToggleBtn"),
  labStyleLibraryPanel: document.querySelector("#labStyleLibraryPanel"),
  labReferenceToggleBtn: document.querySelector("#labReferenceToggleBtn"),
  labReferencePanel: document.querySelector("#labReferencePanel"),
  labReferenceCountLabel: document.querySelector("#labReferenceCountLabel"),
  labReferenceInput: document.querySelector("#labReferenceInput"),
  labReferenceRoleInput: document.querySelector("#labReferenceRoleInput"),
  labReferenceStrengthInput: document.querySelector("#labReferenceStrengthInput"),
  labReferenceNotesInput: document.querySelector("#labReferenceNotesInput"),
  labReferenceState: document.querySelector("#labReferenceState"),
  labReferenceList: document.querySelector("#labReferenceList"),
  labImageCountLabel: document.querySelector("#labImageCountLabel"),
  labGenerateBtn: document.querySelector("#labGenerateBtn"),
  labResetBtn: document.querySelector("#labResetBtn"),
  labStyleGrid: document.querySelector("#labStyleGrid"),
  labSessionState: document.querySelector("#labSessionState"),
  labProgress: document.querySelector("#labProgress"),
  labComparisonGrid: document.querySelector("#labComparisonGrid"),
  labHistoryCount: document.querySelector("#labHistoryCount"),
  labRefreshHistoryBtn: document.querySelector("#labRefreshHistoryBtn"),
  labHistoryGrid: document.querySelector("#labHistoryGrid"),
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
  veyraTemplateHistoryList: document.querySelector("#veyraTemplateHistoryList"),
  veyraUsageList: document.querySelector("#veyraUsageList"),
  providerState: document.querySelector("#providerState"),
  openaiApiKeyInput: document.querySelector("#openaiApiKeyInput"),
  openaiBaseUrlInput: document.querySelector("#openaiBaseUrlInput"),
  openaiImageModelInput: document.querySelector("#openaiImageModelInput"),
  doubaoImageModelInput: document.querySelector("#doubaoImageModelInput"),
  doubaoImageBaseUrlInput: document.querySelector("#doubaoImageBaseUrlInput"),
  doubaoImageApiKeyInput: document.querySelector("#doubaoImageApiKeyInput"),
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
  doubaoImageState: document.querySelector("#doubaoImageState"),
  geminiImageState: document.querySelector("#geminiImageState"),
  openaiThinkingState: document.querySelector("#openaiThinkingState"),
  agentThinkingState: document.querySelector("#agentThinkingState"),
  intensityValue: document.querySelector("#intensityValue"),
  assetInput: document.querySelector("#assetInput"),
  assetName: document.querySelector("#assetName"),
  assetPreview: document.querySelector("#assetPreview"),
  assetPreviewLabel: document.querySelector("#assetPreviewLabel"),
  assetState: document.querySelector("#assetState"),
  clearAssetBtn: document.querySelector("#clearAssetBtn"),
  assetList: document.querySelector("#assetList"),
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
  historyFavoritesOnly: document.querySelector("#historyFavoritesOnly"),
  refreshHistoryBtn: document.querySelector("#refreshHistoryBtn"),
  heroHistoryCarousel: document.querySelector("#heroHistoryCarousel"),
  caseReferenceCarousel: document.querySelector(".case-showcase .case-carousel"),
  outputTemplate: document.querySelector("#outputTemplate"),
  revisionInput: document.querySelector("#revisionInput"),
  reviseBtn: document.querySelector("#reviseBtn"),
  pickFavoriteRevisionBtn: document.querySelector("#pickFavoriteRevisionBtn"),
  clearRevisionSelectionBtn: document.querySelector("#clearRevisionSelectionBtn"),
  selectedOutputLabel: document.querySelector("#selectedOutputLabel"),
  revisionSelectedCard: document.querySelector("#revisionSelectedCard"),
  revisionSelectedTitle: document.querySelector("#revisionSelectedTitle"),
  revisionSelectedMeta: document.querySelector("#revisionSelectedMeta"),
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
  favoritePickerModal: document.querySelector("#favoritePickerModal"),
  favoritePickerGrid: document.querySelector("#favoritePickerGrid"),
  favoritePickerCount: document.querySelector("#favoritePickerCount"),
  closeFavoritePickerBtn: document.querySelector("#closeFavoritePickerBtn"),
  v2FavoriteReferenceModal: document.querySelector("#v2FavoriteReferenceModal"),
  v2FavoriteReferenceGrid: document.querySelector("#v2FavoriteReferenceGrid"),
  v2FavoriteReferenceCount: document.querySelector("#v2FavoriteReferenceCount"),
  closeV2FavoriteReferenceBtn: document.querySelector("#closeV2FavoriteReferenceBtn"),
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
  restoreInitialModuleRoute();
  const hadVeyraTicket = new URLSearchParams(window.location.search).has("ticket");
  try {
    const ticketAccepted = await handleVeyraTicketFromUrl();
    if (hadVeyraTicket && !ticketAccepted) return;
    if (await enforceVeyraUiAuth({ target: "alchemy" })) return;
    syncVeyraSessionCookie();
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
  if (els.headerAdminSettingsLink) {
    els.headerAdminSettingsLink.addEventListener("click", openBillingAdmin);
  }

  els.tabs.forEach((button) => {
    button.addEventListener("click", (event) => {
      const tabName = button.dataset.tab;
      if (tabName === "lab") {
        event.preventDefault();
        const shouldOpenLabMenu = !labState.navOpen;
        labState.activeModule = "";
        switchTab("lab");
        setLabNavOpen(canUseLabDropdown() && shouldOpenLabMenu);
        return;
      }
      switchTab(tabName);
      setLabNavOpen(false);
    });
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
  if (els.clearAssetBtn) els.clearAssetBtn.addEventListener("click", clearV1Asset);
  els.generateBtn.addEventListener("click", generateImage);
  els.reviseBtn.addEventListener("click", reviseSelectedOutput);
  if (els.pickFavoriteRevisionBtn) els.pickFavoriteRevisionBtn.addEventListener("click", openFavoritePicker);
  if (els.clearRevisionSelectionBtn) els.clearRevisionSelectionBtn.addEventListener("click", clearRevisionSelection);
  els.refreshHistoryBtn.addEventListener("click", () => refreshHistory({ silent: false }));
  if (els.historyFavoritesOnly) {
    els.historyFavoritesOnly.addEventListener("change", () => {
      state.historyFavoritesOnly = els.historyFavoritesOnly.checked;
      state.historyRenderLimit = historyPageSize;
      renderHistory(state.historyItems);
    });
  }
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
  document.querySelectorAll("[data-v2-prompt-transform]").forEach((button) => {
    button.addEventListener("click", () => setV2PromptTransformMode(button.dataset.v2PromptTransform || "auto"));
  });
  hydrateV2PromptTransformButtons();
  hydrateV2AspectButtons();
  setV2PromptTransformMode(v2State.promptTransformMode);
  if (els.v2ClearTemplateBtn) els.v2ClearTemplateBtn.addEventListener("click", clearV2Template);
  if (els.v2PickFavoriteReferenceBtn) els.v2PickFavoriteReferenceBtn.addEventListener("click", openV2FavoriteReferencePicker);
  if (els.v2ClearFavoriteReferenceBtn) els.v2ClearFavoriteReferenceBtn.addEventListener("click", () => clearV2FavoriteReference());
  if (els.v2RefreshHistoryBtn) els.v2RefreshHistoryBtn.addEventListener("click", () => loadV2History({ silent: false }));
  if (els.v2HistoryFavoritesOnly) {
    els.v2HistoryFavoritesOnly.addEventListener("change", () => {
      v2State.historyFavoritesOnly = els.v2HistoryFavoritesOnly.checked;
      v2State.historyRenderLimit = v2HistoryPageSize;
      renderV2History(v2State.history);
    });
  }
  if (els.veyraRefreshAccountBtn) els.veyraRefreshAccountBtn.addEventListener("click", () => loadVeyraAccountPanel({ silent: false, force: true }));
  if (els.v2RunBtn) els.v2RunBtn.addEventListener("click", runV2Creative);
  if (els.labImagesPerStyleInput) {
    els.labImagesPerStyleInput.addEventListener("input", () => {
      labState.imagesPerStyle = Number(els.labImagesPerStyleInput.value || 1);
      updateLabCountLabel();
    });
  }
  if (els.labIdeaInput) els.labIdeaInput.addEventListener("input", updateLabCountLabel);
  if (els.labTargetCountInput) {
    els.labTargetCountInput.addEventListener("input", () => {
      labState.targetCount = Number(els.labTargetCountInput.value || 4);
      updateLabCountLabel();
    });
  }
  if (els.labIntervalInput) {
    els.labIntervalInput.addEventListener("input", () => {
      labState.generationIntervalSeconds = Number(els.labIntervalInput.value || 0);
      updateLabCountLabel();
    });
  }
  if (els.labModeInput) els.labModeInput.addEventListener("change", () => { labState.mode = els.labModeInput.value || "minimal"; });
  if (els.labFamilyInput) {
    els.labFamilyInput.addEventListener("change", () => {
      labState.styleFamily = els.labFamilyInput.value || "";
      clearLabSemanticStyleSearch({ keepQuery: true });
      labState.styleRenderLimit = labStylePageSize;
      renderLabStyles();
      updateLabCountLabel();
    });
  }
  if (els.labFreshnessInput) els.labFreshnessInput.addEventListener("change", () => { labState.freshness = els.labFreshnessInput.value || "high"; });
  if (els.labIntentDirectorInput) {
    els.labIntentDirectorInput.addEventListener("change", () => {
      labState.intentDirector = els.labIntentDirectorInput.value || "auto";
      renderLabIntentSummary(null);
    });
  }
  if (els.labQualityEnhancementInput) {
    els.labQualityEnhancementInput.addEventListener("change", () => {
      labState.qualityEnhancement = els.labQualityEnhancementInput.value || "auto";
    });
  }
  if (els.labSeedInput) els.labSeedInput.addEventListener("input", () => { labState.seed = els.labSeedInput.value || ""; });
  if (els.labStyleSearchInput) {
    els.labStyleSearchInput.addEventListener("input", () => {
      labState.search = els.labStyleSearchInput.value || "";
      if (!labState.search.trim()) {
        clearLabSemanticStyleSearch();
      }
      labState.styleRenderLimit = labStylePageSize;
      renderLabStyles();
      renderLabSearchEmptyNotice();
    });
    els.labStyleSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") searchLabStyles();
    });
  }
  if (els.labStyleSearchBtn) els.labStyleSearchBtn.addEventListener("click", searchLabStyles);
  if (els.labClearStylesBtn) {
    els.labClearStylesBtn.addEventListener("click", () => {
      labState.selectedStyleIds = [];
      clearLabStyleSearchInput();
      renderLabStyles();
      updateLabCountLabel();
      updateLabNotice("已清空选择和搜索条件。", "success");
    });
  }
  if (els.labStyleLibraryToggleBtn) {
    els.labStyleLibraryToggleBtn.addEventListener("click", () => {
      setLabStyleLibraryOpen(!labState.styleLibraryOpen);
    });
  }
  if (els.labReferenceToggleBtn) {
    els.labReferenceToggleBtn.addEventListener("click", () => {
      setLabReferenceOpen(!labState.referenceOpen);
    });
  }
  if (els.labReferenceInput) els.labReferenceInput.addEventListener("change", handleLabReferenceFiles);
  if (els.labReferenceRoleInput) {
    els.labReferenceRoleInput.addEventListener("change", () => {
      labState.referenceRole = els.labReferenceRoleInput.value || "subject_reference";
    });
  }
  if (els.labReferenceStrengthInput) {
    els.labReferenceStrengthInput.addEventListener("change", () => {
      labState.referenceStrength = els.labReferenceStrengthInput.value || "strong";
    });
  }
  if (els.labReferenceNotesInput) {
    els.labReferenceNotesInput.addEventListener("input", () => {
      labState.referenceNotes = els.labReferenceNotesInput.value || "";
    });
  }
  if (els.labReferenceList) els.labReferenceList.addEventListener("click", handleLabReferenceListClick);
  document.querySelectorAll("[data-lab-module-open]").forEach((button) => {
    button.addEventListener("click", () => {
      openLabModule(button.dataset.labModuleOpen || "rare-style-explorer");
      setLabNavOpen(false);
    });
  });
  document.querySelectorAll("[data-lab-home-open]").forEach((button) => {
    button.addEventListener("click", openLabHome);
  });
  document.querySelectorAll("[data-lab-aspect]").forEach((button) => {
    button.addEventListener("click", () => {
      setActive(button, "[data-lab-aspect]");
      labState.aspectRatio = button.dataset.labAspect || "square";
    });
  });
  if (els.labStyleGrid) {
    els.labStyleGrid.addEventListener("click", handleLabStyleGridClick);
  }
  if (els.labComparisonGrid) {
    els.labComparisonGrid.addEventListener("click", handleLabComparisonClick);
  }
  if (els.labRefreshHistoryBtn) els.labRefreshHistoryBtn.addEventListener("click", () => loadLabHistory({ silent: false, force: true }));
  if (els.labHistoryGrid) els.labHistoryGrid.addEventListener("click", handleLabHistoryClick);
  if (els.labGenerateBtn) els.labGenerateBtn.addEventListener("click", runLabExploration);
  if (els.labResetBtn) els.labResetBtn.addEventListener("click", resetLabExplorer);
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
  if (els.closeFavoritePickerBtn) els.closeFavoritePickerBtn.addEventListener("click", closeFavoritePicker);
  if (els.closeV2FavoriteReferenceBtn) els.closeV2FavoriteReferenceBtn.addEventListener("click", closeV2FavoriteReferencePicker);
  if (els.favoritePickerModal) {
    els.favoritePickerModal.addEventListener("click", (event) => {
      if (event.target.hasAttribute("data-close-favorite-picker")) closeFavoritePicker();
    });
  }
  if (els.v2FavoriteReferenceModal) {
    els.v2FavoriteReferenceModal.addEventListener("click", (event) => {
      if (event.target.hasAttribute("data-close-v2-favorite-reference")) closeV2FavoriteReferencePicker();
    });
  }
  els.imageLightbox.addEventListener("click", (event) => {
    if (event.target.hasAttribute("data-close-lightbox")) closeImageLightbox();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setLabNavOpen(false);
    if (event.key === "Escape" && !els.sampleGuideModal.hidden) closeSampleGuide();
    if (event.key === "Escape" && els.favoritePickerModal && !els.favoritePickerModal.hidden) closeFavoritePicker();
    if (event.key === "Escape" && els.v2FavoriteReferenceModal && !els.v2FavoriteReferenceModal.hidden) closeV2FavoriteReferencePicker();
    if (event.key === "Escape" && !els.imageLightbox.hidden) closeImageLightbox();
  });
  document.addEventListener("click", (event) => {
    if (!labState.navOpen) return;
    if (els.labNavMenu?.contains(event.target)) return;
    setLabNavOpen(false);
  });
}

function switchTab(tabName) {
  activeTabName = tabName || "image";
  updateHeroCopy(activeTabName);
  document.body.dataset.activeModule = activeTabName;
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
  } else if (tabName === "lab") {
    renderLabModuleState();
    renderHeroHistory(labState.history, { source: "lab" });
    loadLabHistory({ silent: true }).catch((error) => updateLabNotice(`Lab 历史加载失败：${friendlyError(error)}`, "warning"));
  } else if (tabName === "account") {
    renderHeroHistory(v2State.history, { source: "v2" });
    loadVeyraAccountPanel({ silent: true }).catch((error) => {
      showGlobalToast(`账户加载失败：${friendlyError(error)}`, "error");
    });
  } else {
    renderHeroHistory(state.historyItems, { source: "v1" });
  }
}

function updateHeroCopy(tabName) {
  if (!els.heroLine) return;
  const moduleName = Object.prototype.hasOwnProperty.call(heroCopyByTab, tabName) ? tabName : "image";
  els.heroLine.textContent = heroCopyByTab[moduleName];
}

async function loadLabStyles({ force = false } = {}) {
  if (labState.loading || (labState.loaded && !force)) return;
  labState.loading = true;
  updateLabNotice("正在载入稀有风格预设。", "info");
  try {
    const payload = await request("/api/lab/rare-style-explorer/styles");
    labState.styles = Array.isArray(payload.styles) ? payload.styles : [];
    labState.limits = payload.limits || labState.limits;
    hydrateLabControlLimits();
    labState.loaded = true;
    renderLabStyles();
    updateLabCountLabel();
    updateLabNotice(`已载入 ${labState.styles.length} 个稀有风格预设。`, "success");
  } finally {
    labState.loading = false;
    updateLabCountLabel();
  }
}

async function loadLabHistory({ silent = true, force = false } = {}) {
  if (labState.historyLoading) {
    renderLabHistoryLoading();
    return;
  }
  if (labState.historyLoaded && !force) {
    renderLabHistory(labState.history);
    return;
  }
  labState.historyLoading = true;
  if (els.labRefreshHistoryBtn) els.labRefreshHistoryBtn.disabled = true;
  renderLabHistoryLoading();
  try {
    const payload = await request("/api/lab/history?limit=1000");
    labState.history = Array.isArray(payload.items) ? payload.items : [];
    labState.historyLoaded = true;
    renderLabHistory(labState.history);
    if (activePanelName() === "lab") renderHeroHistory(labState.history, { source: "lab" });
    if (!silent) {
      updateLabNotice(`已加载 ${labState.history.length} 条 Lab 历史。`, "success");
      showGlobalToast("Alchemy Lab 历史已刷新。");
    }
  } catch (error) {
    renderLabHistoryError(error);
    updateLabNotice("Alchemy Lab 历史加载失败，请刷新重试。", "error");
    if (!silent) showGlobalToast("Alchemy Lab 历史加载失败。", "error");
  } finally {
    labState.historyLoading = false;
    if (els.labRefreshHistoryBtn) els.labRefreshHistoryBtn.disabled = false;
  }
}

function renderLabHistoryLoading() {
  if (!els.labHistoryGrid || labState.historyLoaded || labState.history.length) return;
  els.labHistoryGrid.innerHTML = "正在加载 Alchemy Lab 历史。";
  els.labHistoryGrid.classList.add("empty-v2-list");
  if (els.labHistoryCount) els.labHistoryCount.textContent = "0";
}

function renderLabHistoryError(error) {
  if (!els.labHistoryGrid) return;
  console.warn("Failed to load Alchemy Lab history", error);
  els.labHistoryGrid.innerHTML = "Alchemy Lab 历史加载失败，请刷新重试。";
  els.labHistoryGrid.classList.add("empty-v2-list");
  if (els.labHistoryCount) els.labHistoryCount.textContent = "0";
}

function renderLabHistory(items) {
  if (!els.labHistoryGrid) return;
  const sortedItems = [...(items || [])].sort(compareHistoryItems);
  labState.history = sortedItems;
  els.labHistoryGrid.innerHTML = "";
  els.labHistoryGrid.classList.toggle("empty-v2-list", sortedItems.length === 0);
  if (els.labHistoryCount) els.labHistoryCount.textContent = String(sortedItems.length);
  if (!sortedItems.length) {
    els.labHistoryGrid.textContent = "暂无 Alchemy Lab 历史。";
    return;
  }
  sortedItems.slice(0, historyPageSize).forEach((item, index) => {
    const article = document.createElement("article");
    article.className = "v2-history-card lab-history-card";
    article.dataset.labHistoryCard = String(index);
    article.title = `点击展开 ${item.title || item.style_name || "Alchemy Lab 历史"}`;
    const metaText = labHistoryMetaText(item);
    const referenceText = labReferenceSummaryText(item.reference_summary ? { summary: item.reference_summary } : null);
    const title = item.title || item.style_name || "Rare Style Explorer";
    const detailText = historyDetailText(item.idea || "未记录画面方向", metaText);
    const footerText = historyDetailText(item.module_label || "Rare Style Explorer", item.style_family || item.style_category || "");
    article.innerHTML = `
      <button class="v2-live-preview lab-history-preview" type="button" data-lab-history-preview="${escapeHtml(item.url || "")}" data-lab-history-index="${index}" aria-label="展开图片">
        <img src="${escapeHtml(item.thumbnail_url || item.url || "")}" alt="${escapeHtml(title)}" loading="eager" decoding="async" />
      </button>
      <div class="v2-history-meta lab-history-meta">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(detailText)}</span>
        ${referenceText ? `<span>${escapeHtml(referenceText)}</span>` : ""}
      </div>
      <div class="output-meta v2-history-footer lab-history-footer">
        <span class="output-id">${escapeHtml(footerText || `#${index + 1}`)}</span>
        <div class="history-card-actions">
          <button class="download-link lab-text-link" data-lab-history-prompt="${index}" type="button">提示词</button>
          <a class="download-link" href="${escapeHtml(item.url || "#")}" data-lab-download="${escapeHtml(item.url || "")}" data-lab-filename="${escapeHtml(`alchemy-lab-${item.id || index}.png`)}">下载</a>
        </div>
      </div>
    `;
    els.labHistoryGrid.appendChild(article);
  });
}

function handleLabHistoryClick(event) {
  const preview = event.target.closest("[data-lab-history-preview]");
  if (preview) {
    const item = labState.history[Number(preview.dataset.labHistoryIndex || 0)];
    if (item) openLabHistoryPreview(item);
    return;
  }
  const promptButton = event.target.closest("[data-lab-history-prompt]");
  if (promptButton) {
    const item = labState.history[Number(promptButton.dataset.labHistoryPrompt || 0)];
    if (item) openLabHistoryPreview(item, { promptOnly: true });
    return;
  }
  const downloadLink = event.target.closest("[data-lab-download]");
  if (downloadLink) {
    event.preventDefault();
    downloadImageFile(downloadLink.dataset.labDownload || downloadLink.href, downloadLink.dataset.labFilename || "alchemy-lab.png", downloadLink);
    return;
  }
  const card = event.target.closest("[data-lab-history-card]");
  if (card) {
    const item = labState.history[Number(card.dataset.labHistoryCard || 0)];
    if (item) openLabHistoryPreview(item);
  }
}

function openLabHistoryPreview(item, { promptOnly = false } = {}) {
  if (!item?.url) return;
  openImageLightbox({
    id: item.id || "alchemy-lab-history",
    title: item.title || "Rare Style Explorer",
    url: item.url,
    thumbnailUrl: item.thumbnail_url || item.url,
    format: item.format || "png",
    meta: labHistoryMetaText(item),
    promptText: item.final_prompt || item.prompt || "",
  });
  if (promptOnly && els.lightboxPromptPanel?.hidden) toggleLightboxPrompt();
}

function labHistoryMetaText(item) {
  const parts = [
    item.mode_label || item.mode,
    item.style_category || item.style_family,
    item.aspect_ratio ? `画幅 ${item.aspect_ratio}` : "",
    item.target_count ? `${item.target_count} 张` : "",
    item.generation_interval_seconds ? `间隔 ${item.generation_interval_seconds}s` : "",
    item.provider || item.model,
  ].filter(Boolean);
  return parts.join(" · ") || "Alchemy Lab";
}

function labHistoryTags(item) {
  return [
    item.style_name,
    item.style_family,
    ...(Array.isArray(item.keywords) ? item.keywords : []),
  ].filter(Boolean).slice(0, 6);
}

function labHistoryQualityText(item) {
  if (!item) return "";
  const quality = {
    quality_enhancement_mode: item.quality_enhancement_mode,
    quality_enhancement_strategy: item.quality_enhancement_strategy,
    quality_enhancement_applied: item.quality_enhancement_applied,
    text_hierarchy_applied: item.text_hierarchy_applied,
    text_hierarchy_summary: item.text_hierarchy_summary,
    art_direction_summary: item.art_direction_summary,
  };
  return [labQualityMetaText(quality), labQualityDetailsText(quality)].filter(Boolean).join(" · ");
}

function openLabModule(moduleId = "rare-style-explorer") {
  if (moduleId !== "rare-style-explorer") return;
  labState.activeModule = moduleId;
  if (document.body.dataset.activeModule !== "lab") switchTab("lab");
  renderLabModuleState();
  if (!labState.loaded && !labState.loading) {
    loadLabStyles().catch((error) => updateLabNotice(`风格加载失败：${friendlyError(error)}`, "error"));
  }
  if (!labState.historyLoaded && !labState.historyLoading) {
    loadLabHistory({ silent: true }).catch((error) => updateLabNotice(`Lab 历史加载失败：${friendlyError(error)}`, "warning"));
  }
}

function openLabHome() {
  labState.activeModule = "";
  if (document.body.dataset.activeModule !== "lab") switchTab("lab");
  renderLabModuleState();
}

function renderLabModuleState() {
  const active = labState.activeModule === "rare-style-explorer";
  if (els.labHomePanel) els.labHomePanel.hidden = active;
  if (els.rareStyleExplorerPanel) els.rareStyleExplorerPanel.hidden = !active;
}

function canUseLabDropdown() {
  return Boolean(els.labNavMenu && els.labNavDropdown && window.matchMedia("(min-width: 761px)").matches);
}

function normalizeModuleRouteToken(value) {
  const token = decodeURIComponent(String(value || ""))
    .replace(/^#/, "")
    .replace(/^\/+/, "")
    .trim()
    .toLowerCase();
  if (["rare-style-explorer", "rare_style_explorer"].includes(token)) return "rare-style-explorer";
  if (["lab", "alchemy-lab", "alchemy_lab"].includes(token)) return "lab";
  if (["image", "v1", "v2", "video", "account"].includes(token)) return token === "v1" ? "image" : token;
  return "";
}

function initialModuleRoute() {
  const params = new URLSearchParams(window.location.search);
  return normalizeModuleRouteToken(params.get("module") || params.get("tab") || window.location.hash);
}

function panelExists(tabName) {
  return Array.from(els.panels).some((panel) => panel.dataset.panel === tabName);
}

function restoreInitialModuleRoute() {
  const route = initialModuleRoute();
  if (route === "rare-style-explorer") {
    openLabModule("rare-style-explorer");
    setLabNavOpen(false);
    return;
  }
  if (route === "lab") {
    openLabHome();
    setLabNavOpen(false);
    return;
  }
  if (route && panelExists(route)) {
    switchTab(route);
  }
}

function setLabStyleLibraryOpen(open) {
  labState.styleLibraryOpen = Boolean(open);
  renderLabStyleLibraryState();
}

function renderLabStyleLibraryState() {
  const open = els.labStyleLibraryToggleBtn ? Boolean(labState.styleLibraryOpen) : true;
  if (els.labStyleLibraryPanel) els.labStyleLibraryPanel.hidden = !open;
  if (els.labStyleLibraryToggleBtn) {
    els.labStyleLibraryToggleBtn.setAttribute("aria-expanded", String(open));
    els.labStyleLibraryToggleBtn.textContent = open ? "收起完整风格库" : "展开完整风格库";
  }
}

function setLabReferenceOpen(open) {
  labState.referenceOpen = Boolean(open);
  renderLabReferenceState();
}

function renderLabReferenceState(message = "") {
  const open = els.labReferenceToggleBtn ? Boolean(labState.referenceOpen) : true;
  const count = labState.referenceAssets.length;
  if (els.labReferencePanel) els.labReferencePanel.hidden = !open;
  if (els.labReferenceToggleBtn) els.labReferenceToggleBtn.setAttribute("aria-expanded", String(open));
  if (els.labReferenceCountLabel) {
    els.labReferenceCountLabel.textContent = count ? `${count} 张已添加` : "未添加";
  }
  if (els.labReferenceState) {
    els.labReferenceState.textContent = message || (count ? "参考图会作为约束输入，不会覆盖已选稀有风格。" : "支持 PNG / JPEG / WebP，单张不超过 12MB。");
  }
  if (!els.labReferenceList) return;
  els.labReferenceList.innerHTML = "";
  if (!count) return;
  labState.referenceAssets.forEach((asset) => {
    const row = document.createElement("div");
    row.className = "lab-reference-row";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(asset.display_name || asset.filename || "参考图")}</strong>
        <small>${escapeHtml(labReferenceAssetText(asset))}</small>
      </div>
      <button class="lab-reference-remove" type="button" data-lab-reference-remove="${escapeHtml(asset.asset_id)}">移除</button>
    `;
    els.labReferenceList.appendChild(row);
  });
}

async function handleLabReferenceFiles(event) {
  const files = Array.from(event.target?.files || []);
  if (event.target) event.target.value = "";
  if (!files.length) return;
  labState.referenceUploading = true;
  setLabBusy(labState.loading || true);
  setLabReferenceOpen(true);
  renderLabReferenceState(`正在上传 ${files.length} 张参考图...`);
  let successCount = 0;
  try {
    for (const file of files) {
      const uploaded = await uploadLabReferenceFile(file);
      labState.referenceAssets = [...labState.referenceAssets, uploaded];
      successCount += 1;
      renderLabReferenceState(`已上传 ${successCount}/${files.length} 张参考图。`);
    }
    updateLabNotice(`已添加 ${successCount} 张参考图，会在所选稀有风格上做约束增强。`, "success");
  } catch (error) {
    updateLabNotice(`参考图上传失败：${friendlyError(error)}`, "error");
    renderLabReferenceState(`上传失败：${friendlyError(error)}`);
  } finally {
    labState.referenceUploading = false;
    setLabBusy(labState.loading);
    renderLabReferenceState();
    updateLabCountLabel();
  }
}

async function uploadLabReferenceFile(file) {
  validateLabReferenceFile(file);
  const role = labState.referenceRole || "subject_reference";
  const strength = labState.referenceStrength || "strong";
  const notes = (labState.referenceNotes || "").trim();
  const created = await request("/api/lab/uploads", {
    method: "POST",
    body: {
      filename: file.name || "lab-reference-image",
      mime_type: file.type,
      size_bytes: file.size,
      role,
      constraint_strength: strength,
      intended_use: notes,
      consent: {
        user_confirmed_rights: true,
        generated_or_owned: true,
      },
    },
  });
  if (!created?.asset_id) throw new Error("上传初始化失败。");
  await request(`/api/lab/uploads/${encodeURIComponent(created.asset_id)}/content`, {
    method: "PUT",
    body: {
      content_base64: await fileToBase64(file),
      mime_type: file.type,
    },
  });
  const completed = await request(`/api/lab/uploads/${encodeURIComponent(created.asset_id)}/complete`, { method: "POST" });
  return {
    asset_id: completed.asset?.asset_id || created.asset_id,
    display_name: completed.asset?.display_name || file.name || "参考图",
    filename: file.name || "参考图",
    role,
    constraint_strength: strength,
    notes,
    visual_summary: completed.asset?.visual_summary || "",
  };
}

function validateLabReferenceFile(file) {
  if (!labReferenceMimeTypes.includes(file.type)) {
    throw new Error("仅支持 PNG、JPEG、WebP 图片。");
  }
  if (file.size > labReferenceMaxBytes) {
    throw new Error("单张参考图不能超过 12MB。");
  }
}

function handleLabReferenceListClick(event) {
  const button = event.target.closest("[data-lab-reference-remove]");
  if (!button) return;
  const assetId = button.dataset.labReferenceRemove;
  labState.referenceAssets = labState.referenceAssets.filter((asset) => asset.asset_id !== assetId);
  renderLabReferenceState();
  updateLabCountLabel();
}

function labReferencePayload() {
  return labState.referenceAssets.map((asset) => ({
    asset_id: asset.asset_id,
    role: asset.role || labState.referenceRole || "subject_reference",
    constraint_strength: asset.constraint_strength || labState.referenceStrength || "strong",
    notes: asset.notes || labState.referenceNotes || "",
  }));
}

function labReferenceAssetText(asset) {
  return [
    labReferenceRoleLabels[asset.role] || asset.role,
    labReferenceStrengthLabels[asset.constraint_strength] || asset.constraint_strength,
    asset.visual_summary,
  ].filter(Boolean).join(" · ");
}

function labReferenceSummaryText(reference) {
  if (!reference) return "";
  const roles = Array.isArray(reference.roles) ? reference.roles : [];
  if (reference.summary) return reference.summary;
  if (roles.length) return `参考图：${roles.map((item) => `${item.label || item.role || "参考"} ${item.count || 1}`).join("、")}`;
  return "";
}

function setLabNavOpen(open) {
  const nextOpen = Boolean(open && activePanelName() === "lab");
  labState.navOpen = nextOpen;
  if (els.labNavMenu) els.labNavMenu.classList.toggle("is-open", nextOpen);
  if (els.labNavTab) els.labNavTab.setAttribute("aria-expanded", String(nextOpen));
  if (els.labNavDropdown) {
    if (nextOpen && els.labNavTab) {
      const rect = els.labNavTab.getBoundingClientRect();
      els.labNavDropdown.style.setProperty("--lab-menu-left", `${rect.left + rect.width / 2}px`);
      els.labNavDropdown.style.setProperty("--lab-menu-top", `${rect.bottom + 8}px`);
    }
    els.labNavDropdown.hidden = !nextOpen;
  }
}

function hydrateLabControlLimits() {
  if (els.labTargetCountInput) els.labTargetCountInput.max = String(labState.limits.maxTotalImages || 12);
  if (els.labImagesPerStyleInput) els.labImagesPerStyleInput.max = String(labState.limits.maxImagesPerStyle || 4);
  if (els.labIntervalInput) els.labIntervalInput.max = String(labState.limits.maxGenerationIntervalSeconds || 60);
}

function renderLabStyles() {
  if (!els.labStyleGrid) return;
  const styles = filteredLabStyles();
  const renderLimit = Math.min(Number(labState.styleRenderLimit || labStylePageSize), styles.length);
  const renderedStyles = styles.slice(0, renderLimit);
  els.labStyleGrid.innerHTML = "";
  els.labStyleGrid.classList.toggle("empty-v2-list", styles.length === 0);
  if (els.labStyleCount) els.labStyleCount.textContent = `${labState.styles.length || 0}`;
  if (els.labLimitsLabel) els.labLimitsLabel.textContent = `${labState.selectedStyleIds.length}/${labState.limits.maxSelectedStyles || 8}`;
  if (!styles.length) {
    const query = String(labState.search || "").trim();
    els.labStyleGrid.textContent = query ? `没有匹配“${query}”的风格。` : "暂无可用风格。";
    return;
  }
  renderedStyles.forEach((style) => {
    const selected = labState.selectedStyleIds.includes(style.id);
    const button = document.createElement("button");
    button.className = `lab-style-card${selected ? " active" : ""}`;
    button.type = "button";
    button.dataset.labStyleId = style.id;
    button.setAttribute("aria-pressed", String(selected));
    button.innerHTML = `
      <span>${escapeHtml(style.category || style.family || "style")}</span>
      <strong>${escapeHtml(style.display_name || style.id)}</strong>
      <small>${escapeHtml(style.short_description || "")}</small>
      ${labState.semanticSearchQuery && typeof style.score === "number" ? `<small class="lab-style-score">相关度 ${Math.round(Number(style.score) * 100)}% · ${escapeHtml(style.why_selected || "语义匹配")}</small>` : ""}
      <em>${escapeHtml(style.id || "")}</em>
    `;
    els.labStyleGrid.appendChild(button);
  });
  if (renderLimit < styles.length) {
    const note = document.createElement("button");
    note.className = "lab-style-more-note";
    note.type = "button";
    note.dataset.labLoadMoreStyles = "true";
    note.textContent = `已显示 ${renderLimit} / ${styles.length} 个匹配风格，点击加载更多。`;
    els.labStyleGrid.appendChild(note);
  }
}

function filteredLabStyles() {
  const query = String(labState.search || "").trim().toLowerCase();
  const selected = new Set(labState.selectedStyleIds || []);
  const semanticActive = Boolean(labState.semanticSearchQuery && labState.semanticSearchResults.length);
  const baseStyles = semanticActive ? labState.semanticSearchResults : labState.styles || [];
  return baseStyles.filter((style) => {
    if (!selected.has(style.id) && labState.styleFamily && style.family !== labState.styleFamily) return false;
    if (semanticActive) return true;
    if (!query) return true;
    const blob = [style.id, style.display_name, style.short_description, style.category, style.family, ...(style.tags || [])].join(" ").toLowerCase();
    return selected.has(style.id) || blob.includes(query);
  }).sort((a, b) => {
    const selectedDelta = Number(selected.has(b.id)) - Number(selected.has(a.id));
    if (selectedDelta) return selectedDelta;
    if (semanticActive) {
      const scoreDelta = Number(b.score || 0) - Number(a.score || 0);
      if (scoreDelta) return scoreDelta;
    }
    const beginnerDelta = Number(Boolean(b.is_beginner_default)) - Number(Boolean(a.is_beginner_default));
    if (beginnerDelta) return beginnerDelta;
    return String(a.display_name || a.id).localeCompare(String(b.display_name || b.id), "zh-CN");
  });
}

async function searchLabStyles() {
  if (!els.labStyleSearchInput) return;
  const query = els.labStyleSearchInput.value.trim();
  labState.search = query;
  labState.styleRenderLimit = labStylePageSize;
  if (!query) {
    clearLabSemanticStyleSearch();
    renderLabStyles();
    updateLabNotice("已恢复完整风格库。", "success");
    return;
  }
  setLabStyleSearchThinking(true, query);
  try {
    const payload = await request("/api/lab/rare-style-explorer/styles/search", {
      method: "POST",
      body: {
        query_text: query,
        family_filter: labState.styleFamily || null,
        limit: 620,
        diversity_level: "medium",
      },
    });
    labState.semanticSearchQuery = query;
    labState.semanticSearchResults = Array.isArray(payload.styles) ? payload.styles : [];
    labState.semanticSearchSource = payload.source || "";
    renderLabStyles();
    const sourceLabel = labState.semanticSearchSource === "llm_rerank" ? "智能语义重排" : "本地语义评分";
    updateLabNotice(
      labState.semanticSearchResults.length
        ? `${sourceLabel}已找到 ${labState.semanticSearchResults.length} 个相关风格。`
        : `没有匹配“${query}”的风格，可以换成主体、用途、材质或情绪描述。`,
      labState.semanticSearchResults.length ? "success" : "warning",
    );
  } catch (error) {
    clearLabSemanticStyleSearch({ keepQuery: true });
    renderLabStyles();
    updateLabNotice(`智能匹配失败，已保留本地关键词过滤：${friendlyError(error)}`, "warning");
  } finally {
    setLabStyleSearchThinking(false);
  }
}

function clearLabSemanticStyleSearch({ keepQuery = false } = {}) {
  labState.semanticSearchQuery = "";
  labState.semanticSearchResults = [];
  labState.semanticSearchSource = "";
  labState.semanticSearchLoading = false;
  if (!keepQuery) labState.search = "";
}

function clearLabStyleSearchInput() {
  clearLabSemanticStyleSearch();
  if (els.labStyleSearchInput) els.labStyleSearchInput.value = "";
  labState.search = "";
  labState.styleRenderLimit = labStylePageSize;
}

function renderLabSearchEmptyNotice() {
  const query = String(labState.search || "").trim();
  if (!query || labState.semanticSearchLoading || labState.semanticSearchQuery) return;
  if (filteredLabStyles().length === 0) {
    updateLabNotice(`没有匹配“${query}”的本地风格，可点击智能匹配做语义搜索，或换主体、用途、材质描述。`, "warning");
  }
}

function setLabStyleSearchThinking(isLoading, query = "") {
  labState.semanticSearchLoading = Boolean(isLoading);
  if (els.labStyleSearchThinking) {
    els.labStyleSearchThinking.hidden = !isLoading;
    const label = els.labStyleSearchThinking.querySelector("small");
    if (label && isLoading) {
      label.textContent = query
        ? `正在理解“${query}”的主体、用途、风格和材质，再按相关度排序。`
        : "正在读取风格库画像并准备展示。";
    }
  }
  if (els.labStyleSearchBtn) {
    els.labStyleSearchBtn.disabled = Boolean(isLoading);
    els.labStyleSearchBtn.classList.toggle("is-thinking", Boolean(isLoading));
    els.labStyleSearchBtn.textContent = isLoading ? "匹配中..." : "智能匹配";
  }
}

function handleLabStyleGridClick(event) {
  const loadMore = event.target.closest("[data-lab-load-more-styles]");
  if (loadMore) {
    const total = filteredLabStyles().length;
    labState.styleRenderLimit = Math.min(Number(labState.styleRenderLimit || labStylePageSize) + labStylePageSize, total);
    renderLabStyles();
    return;
  }
  const button = event.target.closest("[data-lab-style-id]");
  if (!button) return;
  const styleId = button.dataset.labStyleId;
  if (labState.selectedStyleIds.includes(styleId)) {
    labState.selectedStyleIds = labState.selectedStyleIds.filter((id) => id !== styleId);
  } else if (labState.selectedStyleIds.length < (labState.limits.maxSelectedStyles || 8)) {
    labState.selectedStyleIds = [...labState.selectedStyleIds, styleId];
  } else {
    updateLabNotice(`一次最多选择 ${labState.limits.maxSelectedStyles || 8} 种风格。`, "warning");
  }
  renderLabStyles();
  updateLabCountLabel();
}

function updateLabCountLabel() {
  const imagesPerStyle = Math.max(1, Number(labState.imagesPerStyle || 1));
  const selectedCount = labState.selectedStyleIds.length;
  const targetTotal = Math.max(1, Number(labState.targetCount || 4));
  const total = targetTotal;
  const autoCount = Math.max(1, Math.min(labState.limits.maxSelectedStyles || 8, Math.ceil(total / imagesPerStyle)));
  const manualStyleCapacity = Math.max(1, selectedCount) * imagesPerStyle;
  const hasIdea = Boolean((els.labIdeaInput?.value || "").trim());
  if (els.labTargetCountValue) els.labTargetCountValue.textContent = String(Math.max(1, Number(labState.targetCount || 4)));
  if (els.labImagesPerStyleValue) els.labImagesPerStyleValue.textContent = String(imagesPerStyle);
  if (els.labIntervalValue) els.labIntervalValue.textContent = String(Math.max(0, Number(labState.generationIntervalSeconds || 0)));
  if (els.labImageCountLabel) {
    els.labImageCountLabel.textContent = selectedCount
      ? `预计 ${total} 张 · 已选 ${selectedCount} 个风格 · 最后一种承接余数`
      : `预计 ${total} 张 · 自动抽样约 ${autoCount} 个风格`;
  }
  if (els.labGenerateBtn) {
    els.labGenerateBtn.disabled =
      labState.loading ||
      labState.referenceUploading ||
      !hasIdea ||
      total <= 0 ||
      total > (labState.limits.maxTotalImages || 12) ||
      (selectedCount > 0 && total > manualStyleCapacity);
  }
}

async function runLabExploration() {
  if (labState.loading) return;
  if (!labState.loaded) await loadLabStyles();
  const idea = (els.labIdeaInput?.value || "").trim();
  if (!idea) {
    updateLabNotice("请先填写画面想法。", "warning");
    els.labIdeaInput?.focus();
    return;
  }
  if (labState.referenceUploading) {
    updateLabNotice("参考图还在上传，请稍等。", "warning");
    return;
  }
  const hasManualStyles = labState.selectedStyleIds.length > 0;
  const imagesPerStyle = Math.max(1, Number(labState.imagesPerStyle || 1));
  const total = Math.max(1, Number(labState.targetCount || 4));
  const manualStyleCapacity = Math.max(1, labState.selectedStyleIds.length) * imagesPerStyle;
  if (total > (labState.limits.maxTotalImages || 12)) {
    updateLabNotice(`本次共 ${total} 张，超过单次上限 ${labState.limits.maxTotalImages || 12} 张。`, "warning");
    return;
  }
  if (hasManualStyles && total > manualStyleCapacity) {
    updateLabNotice(`已选风格最多可生成 ${manualStyleCapacity} 张，请增加风格或降低总张数。`, "warning");
    return;
  }
  labState.loading = true;
  setLabBusy(true);
  stopLabPolling();
  updateLabNotice(`已提交 ${total} 张串行生成任务。`, "info");
  updateLabSessionState("排队中");
  if (els.labProgress) els.labProgress.textContent = "已提交任务，将逐张生成并刷新结果。";
  try {
    const payload = await request("/api/lab/rare-style-explorer/sessions", {
      method: "POST",
      body: {
        idea,
        selected_style_ids: labState.selectedStyleIds,
        target_count: Math.max(1, Number(labState.targetCount || 4)),
        mode: labState.mode || inferLabMode(idea),
        style_family: labState.styleFamily || null,
        freshness: labState.freshness || "high",
        quality_enhancement: labState.qualityEnhancement || "auto",
        images_per_style: imagesPerStyle,
        generation_interval_seconds: Math.max(0, Number(labState.generationIntervalSeconds || 0)),
        seed: labState.seed === "" ? null : Number(labState.seed),
        avoid_generic: true,
        aspect_ratio: labState.aspectRatio,
        provider_preference: labProviderPreference(),
        reference_assets: labReferencePayload(),
        reference_mode: labState.referenceAssets.length ? "guided" : "off",
        intent_director: labState.intentDirector || "auto",
      },
    });
    labState.currentSession = payload.session;
    labState.currentBoard = payload.board;
    renderLabIntentSummary(payload.session?.intent_plan);
    renderLabBoard(payload.board);
    updateLabSessionFromPayload(payload, { submittedTotal: total });
    if (isLabTerminalStatus(payload.board?.status)) {
      await finishLabPolling(payload.board);
    } else {
      scheduleLabPolling();
    }
  } catch (error) {
    updateLabNotice(`生成失败：${friendlyError(error)}`, "error");
    updateLabSessionState("失败");
    labState.loading = false;
    setLabBusy(false);
  }
}

function scheduleLabPolling() {
  stopLabPolling();
  labState.pollAttempt = 0;
  const tick = async () => {
    if (!labState.currentSession?.id) {
      stopLabPolling();
      labState.loading = false;
      setLabBusy(false);
      return;
    }
    labState.pollAttempt += 1;
    try {
      const payload = await request(`/api/lab/rare-style-explorer/sessions/${encodeURIComponent(labState.currentSession.id)}`);
      labState.currentSession = payload.session;
      labState.currentBoard = payload.board;
      renderLabIntentSummary(payload.session?.intent_plan);
      renderLabBoard(payload.board);
      updateLabSessionFromPayload(payload);
      if (isLabTerminalStatus(payload.board?.status)) {
        await finishLabPolling(payload.board);
        return;
      }
      if (labState.pollAttempt >= labPollMaxAttempts) {
        stopLabPolling();
        updateLabNotice("任务仍在后台串行生成，请稍后刷新历史查看结果。", "warning");
        labState.loading = false;
        setLabBusy(false);
        return;
      }
    } catch (error) {
      stopLabPolling();
      updateLabNotice(`状态刷新失败：${friendlyError(error)}。任务可能仍在后台继续。`, "warning");
      labState.loading = false;
      setLabBusy(false);
      return;
    }
    labState.pollTimer = window.setTimeout(tick, labPollIntervalMs);
  };
  labState.pollTimer = window.setTimeout(tick, labPollIntervalMs);
}

function stopLabPolling() {
  if (labState.pollTimer) {
    window.clearTimeout(labState.pollTimer);
    labState.pollTimer = null;
  }
}

async function finishLabPolling(board) {
  stopLabPolling();
  const okCount = countLabCards(board, "succeeded");
  const failedCount = countLabCards(board, "failed");
  updateLabSessionState(labStatusLabel(board?.status));
  const firstError = firstLabErrorMessage(board);
  updateLabNotice(
    firstError
      ? `已完成 ${okCount} 张，失败 ${failedCount} 张。${firstError}`
      : `已完成 ${okCount} 张，失败 ${failedCount} 张。`,
    failedCount ? "warning" : "success",
  );
  labState.loading = false;
  setLabBusy(false);
  await loadLabHistory({ silent: true, force: true }).catch(() => {});
}

function updateLabSessionFromPayload(payload, options = {}) {
  const board = payload?.board || {};
  const session = payload?.session || {};
  const progress = session.progress || {};
  const okCount = countLabCards(board, "succeeded");
  const failedCount = countLabCards(board, "failed");
  const total = Number(progress.total || options.submittedTotal || countLabCards(board) || labState.targetCount || 0);
  const pending = Math.max(0, total - okCount - failedCount);
  updateLabSessionState(labStatusLabel(board.status || progress.status));
  if (els.labProgress) {
    const wait = Number(progress.next_wait_seconds || 0);
    const waitText = wait > 0 ? ` · 冷却 ${Math.ceil(wait)} 秒后继续` : "";
    els.labProgress.textContent = `${okCount}/${total} 已生成 · ${failedCount} 失败 · ${pending} 等待${waitText}`;
  }
  if (!isLabTerminalStatus(board.status)) {
    const message = progress.message || `串行生成中，已完成 ${okCount}/${total} 张。`;
    updateLabNotice(message, "info");
  }
}

function isLabTerminalStatus(status) {
  return ["completed", "partial_success", "failed"].includes(status);
}

function inferLabMode(idea) {
  const text = idea.toLowerCase();
  if (/人像|肖像|portrait|角色|模特|美女|男士/.test(text)) return "character";
  if (/海报|poster|标题|封面|banner/.test(text)) return "poster";
  if (/产品|商品|包装|瓶|杯|鞋|包|香水|食物|甜品|咖啡/.test(text)) return "product";
  return "minimal";
}

function labProviderPreference() {
  const provider = safeImageProviderPreference(state.selectedProvider, "");
  return provider || null;
}

function renderLabBoard(board) {
  if (!els.labComparisonGrid) return;
  const groups = Array.isArray(board?.groups) ? board.groups : [];
  const cards = groups.flatMap((group) =>
    (Array.isArray(group.cards) ? group.cards : []).map((card) => ({ group, card })),
  );
  els.labComparisonGrid.innerHTML = "";
  els.labComparisonGrid.classList.toggle("empty-v2-list", cards.length === 0);
  if (!cards.length) {
    els.labComparisonGrid.textContent = "暂无对比结果。";
    if (els.labProgress) els.labProgress.textContent = "等待生成风格变化。";
    return;
  }
  if (els.labProgress) {
    els.labProgress.textContent = `${groups.length} 组风格 · ${countLabCards(board)} 张结果 · ${labStatusLabel(board.status)}`;
  }
  cards.forEach(({ group, card }) => {
    const article = document.createElement("article");
    article.className = `lab-result-card ${labResultCardClass(card.status)}`;
    const styleName = group.style_name || group.style_preset_id || "Rare Style";
    const imageHtml = card.image_url
      ? `<button class="lab-image-button" type="button" data-lab-preview="${escapeHtml(card.image_url)}" data-lab-title="${escapeHtml(styleName)}" data-lab-prompt="${escapeHtml(card.prompt || "")}"><img src="${escapeHtml(card.thumbnail_url || card.image_url)}" alt="${escapeHtml(styleName)}" loading="lazy" decoding="async" /></button>`
      : `<div class="lab-error-tile">${escapeHtml(labPlaceholderText(card))}</div>`;
    const imageActions = card.image_url
      ? `<a class="lab-card-action" href="${escapeHtml(card.image_url)}" data-lab-download="${escapeHtml(card.image_url)}" data-lab-filename="${escapeHtml(`alchemy-lab-${card.variant_id || "image"}.png`)}">下载</a>`
      : "";
    const qualityText = labQualityMetaText(card.quality);
    const qualityDetails = labQualityDetailsText(card.quality);
    const referenceText = labReferenceSummaryText(card.reference);
    const intentText = labIntentMetaText(card.intent);
    article.innerHTML = `
      ${imageHtml}
      <div class="lab-card-meta">
        <strong>${escapeHtml(styleName)}</strong>
        <span>${escapeHtml(labCardStatusLabel(card.status))}</span>
      </div>
      ${intentText ? `<p class="lab-card-intent">${escapeHtml(intentText)}</p>` : ""}
      ${referenceText ? `<p class="lab-card-reference">${escapeHtml(referenceText)}</p>` : ""}
      ${qualityText ? `<p class="lab-card-quality">${escapeHtml(qualityText)}</p>` : ""}
      ${qualityDetails ? `<small class="lab-card-quality-detail">${escapeHtml(qualityDetails)}</small>` : ""}
      <div class="lab-card-actions">
        <button class="lab-card-action" data-lab-copy-prompt="${escapeHtml(card.variant_id || "")}" data-lab-prompt="${escapeHtml(card.prompt || "")}" type="button">复制提示词</button>
        ${imageActions}
        <button class="lab-card-action lab-favorite-btn${card.is_favorite ? " active" : ""}" data-lab-favorite="${escapeHtml(card.variant_id)}" type="button" aria-pressed="${String(Boolean(card.is_favorite))}">收藏</button>
      </div>
      <details class="lab-prompt-detail">
        <summary>查看本图使用的提示词</summary>
        <pre>${escapeHtml(card.prompt || "")}</pre>
      </details>
    `;
    els.labComparisonGrid.appendChild(article);
  });
}

function firstLabErrorMessage(board) {
  for (const group of board?.groups || []) {
    for (const card of group.cards || []) {
      const message = card.error?.message || "";
      if (message) return message;
    }
  }
  return "";
}

async function handleLabComparisonClick(event) {
  const previewButton = event.target.closest("[data-lab-preview]");
  if (previewButton) {
    openLabPreview(previewButton.dataset.labPreview, previewButton.dataset.labTitle || "Alchemy Lab", previewButton.dataset.labPrompt || "");
    return;
  }
  const copyPromptButton = event.target.closest("[data-lab-copy-prompt]");
  if (copyPromptButton) {
    await copyLabPrompt(copyPromptButton.dataset.labPrompt || "");
    return;
  }
  const downloadLink = event.target.closest("[data-lab-download]");
  if (downloadLink) {
    event.preventDefault();
    await downloadImageFile(downloadLink.dataset.labDownload || downloadLink.href, downloadLink.dataset.labFilename || "alchemy-lab.png", downloadLink);
    return;
  }
  const favoriteButton = event.target.closest("[data-lab-favorite]");
  if (!favoriteButton || !labState.currentSession) return;
  const variantId = favoriteButton.dataset.labFavorite;
  const favorites = new Set(labState.currentBoard?.favorites || []);
  if (favorites.has(variantId)) favorites.delete(variantId);
  else favorites.add(variantId);
  try {
    const payload = await request(`/api/lab/rare-style-explorer/sessions/${labState.currentSession.id}/favorites`, {
      method: "POST",
      body: { variant_ids: Array.from(favorites) },
    });
    labState.currentSession = payload.session;
    labState.currentBoard = payload.board;
    renderLabBoard(payload.board);
    updateLabNotice(`已收藏 ${payload.board?.favorites?.length || 0} 张。`, "success");
  } catch (error) {
    updateLabNotice(`收藏失败：${friendlyError(error)}`, "error");
  }
}

async function copyLabPrompt(prompt) {
  if (!prompt) return;
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(prompt);
    else copyTextFallback(prompt);
  } catch (error) {
    copyTextFallback(prompt);
  }
  updateLabNotice("已复制这张图使用的提示词。", "success");
}

function openLabPreview(url, title, prompt) {
  if (!url || !els.imageLightbox) return;
  openImageLightbox({
    id: "alchemy-lab",
    title: title || "Alchemy Lab",
    url,
    thumbnailUrl: url,
    format: "png",
    meta: "Alchemy Lab",
    promptText: prompt || "",
  });
}

function resetLabExplorer() {
  stopLabPolling();
  if (els.labIdeaInput) els.labIdeaInput.value = "";
  labState.targetCount = 4;
  labState.imagesPerStyle = 1;
  labState.generationIntervalSeconds = labDefaultGenerationIntervalSeconds;
  labState.mode = "minimal";
  labState.styleFamily = "";
  labState.freshness = "high";
  labState.intentDirector = "auto";
  labState.qualityEnhancement = "auto";
  labState.seed = "";
  labState.search = "";
  labState.referenceOpen = true;
  labState.referenceAssets = [];
  labState.referenceRole = "subject_reference";
  labState.referenceStrength = "strong";
  labState.referenceNotes = "";
  labState.referenceUploading = false;
  if (els.labTargetCountInput) els.labTargetCountInput.value = "4";
  if (els.labImagesPerStyleInput) els.labImagesPerStyleInput.value = "1";
  if (els.labIntervalInput) els.labIntervalInput.value = String(labDefaultGenerationIntervalSeconds);
  if (els.labModeInput) els.labModeInput.value = "minimal";
  if (els.labFamilyInput) els.labFamilyInput.value = "";
  if (els.labFreshnessInput) els.labFreshnessInput.value = "high";
  if (els.labIntentDirectorInput) els.labIntentDirectorInput.value = "auto";
  if (els.labQualityEnhancementInput) els.labQualityEnhancementInput.value = "auto";
  if (els.labSeedInput) els.labSeedInput.value = "";
  if (els.labStyleSearchInput) els.labStyleSearchInput.value = "";
  if (els.labReferenceRoleInput) els.labReferenceRoleInput.value = "subject_reference";
  if (els.labReferenceStrengthInput) els.labReferenceStrengthInput.value = "strong";
  if (els.labReferenceNotesInput) els.labReferenceNotesInput.value = "";
  labState.selectedStyleIds = [];
  labState.currentSession = null;
  labState.currentBoard = null;
  labState.loading = false;
  setLabBusy(false);
  renderLabReferenceState();
  renderLabStyles();
  renderLabBoard(null);
  updateLabCountLabel();
  updateLabSessionState("待生成");
  updateLabNotice("输入想法后可自动抽样，也可手选风格生成对比图。", "info");
  renderLabIntentSummary(null);
}

function setLabBusy(isBusy) {
  if (els.labGenerateBtn) {
    els.labGenerateBtn.disabled = isBusy;
    els.labGenerateBtn.textContent = isBusy ? "生成中..." : "生成对比";
  }
  if (els.labResetBtn) els.labResetBtn.disabled = isBusy;
}

function updateLabNotice(message, type = "info") {
  if (!els.labNoticeBar) return;
  els.labNoticeBar.textContent = message;
  els.labNoticeBar.className = `notice-bar ${type === "info" ? "" : type}`.trim();
}

function renderLabIntentSummary(intentPlan) {
  if (!els.labIntentSummaryText) return;
  const mode = labState.intentDirector || "auto";
  if (els.labIntentSummaryTitle) els.labIntentSummaryTitle.textContent = mode === "off" ? "纯随机" : "智能判断";
  if (mode === "off" && !intentPlan) {
    els.labIntentSummaryText.textContent = "不调用智能判断收束风格族，按完整风格库随机探索；参考图仍可作为生成输入使用。";
    return;
  }
  const text = labIntentMetaText(publicLabIntentFromPlan(intentPlan));
  els.labIntentSummaryText.textContent = text || "调用智能判断理解文字和参考图用途，优先推荐更匹配的风格族与约束；不会覆盖手动选择的风格。";
}

function updateLabSessionState(label) {
  if (els.labSessionState) els.labSessionState.textContent = label || "待生成";
}

function countLabCards(board, status = "") {
  return (board?.groups || []).reduce((total, group) => {
    return total + (group.cards || []).filter((card) => !status || card.status === status).length;
  }, 0);
}

function labStatusLabel(status) {
  const labels = {
    queued: "排队中",
    running: "生成中",
    completed: "已完成",
    partial_success: "部分完成",
    failed: "失败",
  };
  return labels[status] || "待生成";
}

function labCardStatusLabel(status) {
  const labels = {
    succeeded: "已生成",
    failed: "失败",
    running: "生成中",
    queued: "排队中",
  };
  return labels[status] || status || "-";
}

function labResultCardClass(status) {
  if (status === "succeeded") return "is-ready";
  if (status === "failed") return "is-failed";
  if (status === "running") return "is-running";
  return "is-queued";
}

function labPlaceholderText(card) {
  if (card.status === "running") return "生成中";
  if (card.status === "queued") return "等待串行生成";
  return card.error?.message || "生成失败";
}

function labQualityModeLabel(mode) {
  const labels = {
    auto: "自动",
    off: "关闭",
    balanced: "精修",
    curated: "策展",
  };
  return labels[mode] || mode || "";
}

function labQualityStrategyLabel(strategy) {
  const labels = {
    off: "未增强",
    balanced: "平衡增强",
    curated: "策展增强",
  };
  return labels[strategy] || strategy || "";
}

function labQualityMetaText(quality) {
  if (!quality) return "";
  const mode = labQualityModeLabel(quality.quality_enhancement_mode);
  const strategy = labQualityStrategyLabel(quality.quality_enhancement_strategy);
  const applied = quality.quality_enhancement_applied ? "已精修" : "未改写";
  return [mode ? `质量增强 ${mode}` : "", strategy, applied].filter(Boolean).join(" · ");
}

function labQualityDetailsText(quality) {
  if (!quality) return "";
  const parts = [];
  if (quality.text_hierarchy_applied) parts.push("智能文案层级已规划");
  if (quality.text_hierarchy_summary) parts.push(quality.text_hierarchy_summary);
  if (quality.art_direction_summary) parts.push(quality.art_direction_summary);
  return parts.filter(Boolean).join(" · ");
}

function publicLabIntentFromPlan(plan) {
  if (!plan || typeof plan !== "object") return {};
  if (plan.source === "disabled" || plan.applied === false && plan.source === "disabled") return {};
  const constraints = plan.prompt_constraints && typeof plan.prompt_constraints === "object" ? plan.prompt_constraints : {};
  return {
    summary: plan.user_goal_summary || constraints.director_summary || plan.director_summary || "",
    target_use: plan.target_use || "",
    confidence: plan.confidence || "",
    must_keep: Array.isArray(constraints.must_keep) ? constraints.must_keep : [],
  };
}

function labIntentMetaText(intent) {
  if (!intent || typeof intent !== "object") return "";
  const summary = intent.summary || "";
  const target = labIntentTargetLabel(intent.target_use);
  const confidence = labIntentConfidenceLabel(intent.confidence);
  const mustKeep = Array.isArray(intent.must_keep) && intent.must_keep.length ? `保留 ${intent.must_keep.slice(0, 2).join("、")}` : "";
  return [target ? `智能判断 ${target}` : "智能判断", summary, mustKeep, confidence].filter(Boolean).join(" · ");
}

function labIntentTargetLabel(target) {
  const labels = {
    product: "产品",
    poster: "海报",
    portrait: "人像",
    food: "美食",
    packaging: "包装",
    logo: "标识",
    scene: "场景",
    material: "材质",
    abstract: "抽象",
    image_exploration: "创意探索",
  };
  return labels[target] || "";
}

function labIntentConfidenceLabel(confidence) {
  const labels = { high: "高置信", medium: "中置信", low: "保守判断" };
  return labels[confidence] || "";
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
  renderAssetPanel();
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
  const requested = ["openai_gpt_image", "doubao_image", "gemini_image"].includes(provider) ? provider : "openai_gpt_image";
  if (isGeminiImageTemporarilyDisabled(requested)) {
    showNotice(geminiImageUnavailableReason, "warning");
  } else if (["openai_gpt_image", "doubao_image", "gemini_image"].includes(requested) && !isImageProviderUsable(requested)) {
    showNotice(`${providerLabel(requested)} API 尚未配置；该通道需要独立 Key，不会复用其他模型 Key。`, "warning");
  } else {
    state.selectedProvider = requested;
  }
  document.querySelectorAll("[data-image-provider]").forEach((button) => {
    button.classList.toggle("active", button.dataset.imageProvider === state.selectedProvider);
  });
  els.imageActiveLabel.textContent = `${providerShortLabel(state.selectedProvider)} 已选`;
  if (persist) scheduleProviderSettingsSync({ immediate: true });
}

function firstUsableImageProvider(candidates = ["openai_gpt_image", "doubao_image", "gemini_image"]) {
  return candidates.find((provider) => isImageProviderUsable(provider)) || "";
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
    els.doubaoImageModelInput,
    els.doubaoImageBaseUrlInput,
    els.geminiImageModelInput,
    els.openaiLlmModelInput,
    els.agentLlmModelInput,
  ].forEach((input) => {
    input.addEventListener("input", () => scheduleProviderSettingsSync());
    input.addEventListener("change", () => scheduleProviderSettingsSync({ immediate: true }));
  });

  [els.openaiApiKeyInput, els.doubaoImageApiKeyInput, els.geminiImageApiKeyInput, els.anthropicApiKeyInput].forEach((input) => {
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
      title: "Verya Alchemy",
      orchestration_mode: "runtime_first",
    },
  });
  state.sessionId = session.id;
  state.assetIds = [];
  state.assets = [];
  state.currentJob = null;
  state.selectedOutputId = null;
  state.selectedRevisionSource = null;
  els.sessionLabel.textContent = session.id;
  els.gallery.innerHTML = "";
  els.gallery.classList.remove("loading");
  els.gallery.classList.add("empty-gallery");
  els.assetName.textContent = "支持多图，单次最多 6 张";
  els.assetState.textContent = "空";
  els.assetInput.value = "";
  setAssetMode("basic");
  setAdvancedAssetRoles(["style_reference"]);
  if (els.assetIntentNotesInput) els.assetIntentNotesInput.value = "";
  resetAssetPreview();
  renderAssetPanel();
  els.revisionInput.value = "";
  clearRevisionSelection({ keepNotice: true });
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
  clearV2FavoriteReference({ keepNotice: true });
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
  state.selectedProvider = safeImageProviderPreference(runtime.default_image_provider || "openai_gpt_image");
  state.selectedLlmProvider = runtime.default_llm_provider || "openai";
  state.selectedIntensity = runtime.image_work_intensity || "balanced";
  els.openaiImageModelInput.value = runtime.openai_image_model || "gpt-image-2";
  els.doubaoImageModelInput.value = runtime.doubao_image_model || "doubao-seedream-4-0-250828";
  els.geminiImageModelInput.value = runtime.gemini_image_model || "gemini-3-pro-image-preview";
  els.openaiLlmModelInput.value = runtime.openai_llm_model || "gpt-5.5";
  els.agentLlmModelInput.value = runtime.kimi_llm_model || "kimi-for-coding";
  els.doubaoImageBaseUrlInput.value = runtime.doubao_image_base_url || "";
  els.geminiImageBaseUrlInput.value = runtime.gemini_image_base_url || "";
  els.openaiBaseUrlInput.value = runtime.openai_base_url || "";
  els.anthropicBaseUrlInput.value = runtime.anthropic_base_url || "https://aiself.vip";
  els.intensityValue.textContent = intensityMap[state.selectedIntensity]?.label || "均衡";
  setActiveIntensity(state.selectedIntensity);
  if (!isImageProviderUsable(state.selectedProvider)) {
    state.selectedProvider = firstUsableImageProvider(["openai_gpt_image", "doubao_image", "gemini_image"]) || state.selectedProvider;
  }
  setImageProvider(state.selectedProvider);
  setThinkingProvider(state.selectedLlmProvider);

  renderProviderLists(providers, runtime);
  const openai = providers.image.find((provider) => provider.provider === "openai_gpt_image");
  const doubao = providers.image.find((provider) => provider.provider === "doubao_image");
  const gemini = providers.image.find((provider) => provider.provider === "gemini_image");
  const selectedImage = providers.image.find((provider) => provider.provider === state.selectedProvider);
  state.imageProviderReady = Boolean(selectedImage?.configured);
  els.openaiImageState.textContent = openai?.configured ? runtime.openai_image_model : "需 API";
  els.doubaoImageState.textContent = doubao?.configured ? runtime.doubao_image_model : "需 API";
  els.geminiImageState.textContent = isGeminiImageTemporarilyDisabled("gemini_image")
    ? geminiImageUnavailableShortLabel
    : gemini?.configured
      ? runtime.gemini_image_model
      : "需 API";
  els.openaiThinkingState.textContent = runtime.openai_api_key_configured ? runtime.openai_llm_model : "需 API";
  els.agentThinkingState.textContent = runtime.anthropic_api_key_configured ? runtime.kimi_llm_model || "已配置" : "需 Kimi API";
  els.providerState.textContent = state.imageProviderReady ? `${providerLabel(state.selectedProvider)} ready` : "需要 API";
  renderV2ModelSettings();
  renderV2ProviderInheritance();
  setImageProviderAvailability("openai_gpt_image", Boolean(openai?.configured), "");
  setImageProviderAvailability(
    "doubao_image",
    Boolean(doubao?.configured),
    doubao?.configured ? "" : "填写豆包 API Key 后即可选择。"
  );
  setImageProviderAvailability(
    "gemini_image",
    !isGeminiImageTemporarilyDisabled("gemini_image") && Boolean(gemini?.configured),
    isGeminiImageTemporarilyDisabled("gemini_image")
      ? geminiImageUnavailableReason
      : gemini?.configured
        ? ""
        : "填写 Gemini API Key 后即可选择。"
  );

  if (state.imageProviderReady) {
    showNotice(`模型已就绪：生图 ${providerLabel(state.selectedProvider)}；思考 ${thinkingProviderLabel(state.selectedLlmProvider)}。`, "success");
  } else {
    showNotice(`请在高级 API 配置里保存 ${providerLabel(state.selectedProvider)} 独立 API Key 后生成图片。`, "warning");
  }
}

function setActiveIntensity(value) {
  const button = document.querySelector(`[data-intensity="${value}"]`) || document.querySelector("[data-intensity='balanced']");
  if (button) setActive(button, "[data-intensity]");
}

function renderProviderLists(providers, runtime) {
  els.providerList.innerHTML = "";
  providers.image
    .filter((provider) => ["openai_gpt_image", "doubao_image", "gemini_image", "mock_image"].includes(provider.provider))
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
  const temporarilyDisabled = isGeminiImageTemporarilyDisabled(provider.provider);
  row.className = `provider-row ${provider.configured && !temporarilyDisabled ? "ready" : "muted-row"} ${temporarilyDisabled ? "temporarily-disabled" : ""}`.trim();

  const title = document.createElement("div");
  title.className = "provider-title";
  const name = document.createElement("strong");
  name.textContent = providerLabel(provider.provider);
  const badge = document.createElement("span");
  badge.className = "mini-pill";
  badge.textContent = temporarilyDisabled
    ? geminiImageUnavailableShortLabel
    : provider.configured
      ? "已接入"
      : ["openai_gpt_image", "doubao_image", "gemini_image"].includes(provider.provider)
        ? "需 API"
        : "未接入";
  title.append(name, badge);

  const models = document.createElement("span");
  models.className = "provider-models";
  models.textContent = provider.models.join(", ") || "-";

  const reason = document.createElement("p");
  reason.textContent = temporarilyDisabled ? geminiImageUnavailableReason : provider.reason || note || "";

  row.append(title, models, reason);
  return row;
}

function providerLabel(provider) {
  const labels = {
    openai_gpt_image: "GPT Image 2",
    doubao_image: "豆包 Seedream",
    gemini_image: "Gemini Image",
    mock_image: "Mock Image",
    seedance: "Seedance Video",
  };
  return labels[provider] || provider;
}

function providerShortLabel(provider) {
  const labels = {
    openai_gpt_image: "GPT",
    doubao_image: "豆包",
    gemini_image: "Gemini",
    mock_image: "Mock",
  };
  return labels[provider] || providerLabel(provider);
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
  if (isGeminiImageTemporarilyDisabled(provider)) return false;
  return Boolean(state.imageProviderCapabilities?.[provider]?.configured);
}

function setImageProviderAvailability(provider, enabled, title) {
  const button = document.querySelector(`[data-image-provider="${provider}"]`);
  if (!button) return;
  const temporarilyDisabled = isGeminiImageTemporarilyDisabled(provider);
  const available = enabled && !temporarilyDisabled;
  button.disabled = !available;
  button.title = temporarilyDisabled ? geminiImageUnavailableReason : title || "";
  button.classList.toggle("disabled", !available);
  button.classList.toggle("temporarily-disabled", temporarilyDisabled);
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
      default_image_provider: safeImageProviderPreference(state.selectedProvider),
      default_image_model: selectedImageModel(),
      openai_image_model: els.openaiImageModelInput.value.trim() || "gpt-image-2",
      doubao_image_model: els.doubaoImageModelInput.value.trim() || "doubao-seedream-4-0-250828",
      doubao_image_base_url: els.doubaoImageBaseUrlInput.value.trim(),
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
    const doubaoImageApiKey = els.doubaoImageApiKeyInput.value.trim();
    if (doubaoImageApiKey) payload.doubao_image_api_key = doubaoImageApiKey;
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
    els.doubaoImageApiKeyInput.value = "";
    els.geminiImageApiKeyInput.value = "";
    els.anthropicApiKeyInput.value = "";
    await loadProviders();
    if (!silent) {
      const message = modelEffectMessage(runtime);
      if (runtime.runtime_persistence_warning) {
        showNotice(`${message} ${runtime.runtime_persistence_warning}`, "warning");
        showGlobalToast("配置已临时生效，但未能持久化。", "error");
      } else {
        showNotice(message, "success");
        showGlobalToast(message);
      }
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
  if (state.selectedProvider === "gemini_image" && !isGeminiImageTemporarilyDisabled("gemini_image")) {
    return els.geminiImageModelInput.value.trim() || "gemini-3-pro-image-preview";
  }
  if (state.selectedProvider === "doubao_image") {
    return els.doubaoImageModelInput.value.trim() || "doubao-seedream-4-0-250828";
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

function otherThinkingProvider(provider) {
  return provider === "anthropic" ? "openai" : "anthropic";
}

function modelEffectMessage(runtime) {
  const imageProvider = safeImageProviderPreference(runtime.default_image_provider || state.selectedProvider);
  const thinkingProvider = runtime.default_llm_provider || state.selectedLlmProvider;
  const imageRoute = `生图通道 ${providerLabel(imageProvider)} 独立启用`;
  return `配置已生效：${imageRoute}；思考 ${thinkingProviderLabel(thinkingProvider)} 优先，${thinkingProviderLabel(otherThinkingProvider(thinkingProvider))} 兜底。`;
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
    const [health, providersResponse, imageProviderCapabilities, templateIndexResponse, templatesPageResponse, historyResponse, orchestratorStatus, modelSettings] = await Promise.all([
      v2Request("/health"),
      v2Request("/resource-providers"),
      v2Request("/provider-capabilities"),
      v2Request("/templates/index"),
      v2Request(v2TemplatePageEndpoint()),
      loadV2HistoryResponse(),
      v2Request("/orchestrator/status"),
      v2Request("/runtime/model-settings"),
    ]);
    v2State.health = health;
    v2State.providers = providersResponse.providers || [];
    v2State.imageProviderCapabilities = imageProviderCapabilities.providers || [];
    v2State.orchestratorStatus = orchestratorStatus;
    v2State.modelSettings = modelSettings;
    applyV2TemplateIndex(templateIndexResponse);
    applyV2TemplatePage(templatesPageResponse, { reset: true });
    scheduleV2TemplatePrefetch();
    v2State.historyRenderLimit = v2HistoryPageSize;
    v2State.history = historyResponse.items || [];
    v2State.loaded = true;
    renderV2Health(health);
    renderV2Providers(v2State.providers);
    renderV2CaseFacets();
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
  syncV2ImageProviderOptionState(provider);
  document.querySelectorAll("[data-v2-image-provider]").forEach((button) => {
    const isActive = button.dataset.v2ImageProvider === provider;
    const capability = v2ProviderCapability(button.dataset.v2ImageProvider);
    const isConfigured = v2ImageProviderConfigured(button.dataset.v2ImageProvider);
    button.classList.toggle("active", isActive);
    button.disabled = !isConfigured;
    button.classList.toggle("temporarily-disabled", isGeminiImageTemporarilyDisabled(button.dataset.v2ImageProvider));
    button.title = isGeminiImageTemporarilyDisabled(button.dataset.v2ImageProvider)
      ? geminiImageUnavailableReason
      : isConfigured
        ? ""
        : capability?.reason || "请先配置 V2 生图通道的 API Key。";
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
  if (els.v2DoubaoImageState) {
    const capability = v2ProviderCapability("doubao_image");
    els.v2DoubaoImageState.textContent = settings.doubao_image_api_key_configured
      ? capability?.configured === false
        ? "不可用"
        : settings.doubao_image_model || "doubao-seedream-4-0-250828"
      : "需 V2 API";
  }
  if (els.v2GeminiImageState) {
    const capability = v2ProviderCapability("gemini_image");
    els.v2GeminiImageState.textContent = isGeminiImageTemporarilyDisabled("gemini_image")
      ? geminiImageUnavailableShortLabel
      : settings.gemini_api_key_configured
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

function syncV2ImageProviderOptionState(fallbackProvider = "openai_gpt_image") {
  if (!els.v2ImageProviderInput) return;
  const option = els.v2ImageProviderInput.querySelector('option[value="gemini_image"]');
  if (option) {
    option.disabled = geminiImageGenerationTemporarilyDisabled;
    option.textContent = geminiImageGenerationTemporarilyDisabled ? "Gemini Image（暂不可用）" : "Gemini Image";
  }
  if (isGeminiImageTemporarilyDisabled(els.v2ImageProviderInput.value)) {
    els.v2ImageProviderInput.value = fallbackProvider || "auto";
  }
}

function v2EffectiveImageProvider(settings = v2State.modelSettings || {}) {
  const configured = safeImageProviderPreference(settings.image_generation_provider, "auto");
  if (["openai_gpt_image", "doubao_image", "gemini_image"].includes(configured) && v2ImageProviderConfigured(configured, settings)) {
    return configured;
  }
  if (configured === "mock_image" && settings.persisted) return "mock_image";
  const liveProvider = v2PreferredLiveImageProvider(settings);
  if (liveProvider) return liveProvider;
  return "mock_image";
}

function v2RequestedImageProvider(settings = v2State.modelSettings || {}) {
  const selected = safeImageProviderPreference(els.v2ImageProviderInput?.value || "", "auto");
  if (["openai_gpt_image", "doubao_image", "gemini_image", "mock_image"].includes(selected) && v2ImageProviderConfigured(selected, settings)) {
    return selected;
  }
  return v2EffectiveImageProvider(settings);
}

function v2PreferredLiveImageProvider(settings = v2State.modelSettings || {}) {
  if (v2ImageProviderConfigured("openai_gpt_image", settings)) return "openai_gpt_image";
  if (v2ImageProviderConfigured("doubao_image", settings)) return "doubao_image";
  if (v2ImageProviderConfigured("gemini_image", settings)) return "gemini_image";
  return "";
}

function v2ImageProviderConfigured(provider, settings = v2State.modelSettings || {}) {
  if (isGeminiImageTemporarilyDisabled(provider)) return false;
  if (provider === "mock_image") return true;
  const capability = v2ProviderCapability(provider);
  if (capability && capability.configured === false) return false;
  if (provider === "gemini_image") return Boolean(settings.gemini_api_key_configured);
  if (provider === "doubao_image") return Boolean(settings.doubao_image_api_key_configured);
  if (provider === "openai_gpt_image") return Boolean(settings.openai_api_key_configured);
  return false;
}

function v2ProviderCapability(provider) {
  return (v2State.imageProviderCapabilities || []).find((item) => item.provider === provider) || null;
}

function v2ImageModelName(provider, settings = v2State.modelSettings || {}) {
  if (provider === "gemini_image") return settings.gemini_image_model || "gemini-2.5-flash-image";
  if (provider === "doubao_image") return settings.doubao_image_model || "doubao-seedream-4-0-250828";
  if (provider === "mock_image") return "mock-image-v2-native";
  return settings.openai_image_model || "gpt-image-2";
}

async function setV2ImageProvider(provider, { persist = false } = {}) {
  const requested = ["openai_gpt_image", "doubao_image", "gemini_image", "mock_image"].includes(provider) ? provider : "openai_gpt_image";
  if (isGeminiImageTemporarilyDisabled(requested)) {
    updateV2Notice(geminiImageUnavailableReason, "warning");
    renderV2ModelCards();
    return;
  }
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
        image_generation_provider: safeImageProviderPreference(els.v2ImageProviderInput?.value || "auto", "auto"),
        openai_image_model: els.openaiImageModelInput?.value.trim() || "gpt-image-2",
        doubao_image_model: els.doubaoImageModelInput?.value.trim() || "doubao-seedream-4-0-250828",
        gemini_image_model: els.geminiImageModelInput?.value.trim() || "gemini-2.5-flash-image",
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
    doubao_image: "豆包",
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

function applyV2TemplateIndex(index) {
  v2State.templateIndex = index || null;
  v2State.templateTotal = Number(index?.total || 0);
  if (index?.index_version && els.v2IndexState) {
    els.v2IndexState.textContent = index.index_version;
  }
}

function applyV2TemplatePage(page, { reset = false } = {}) {
  const items = page?.items || [];
  const nextTemplates = reset ? [] : [...v2State.templates];
  const seen = new Set(nextTemplates.map((item) => item.case_id));
  items.forEach((item) => {
    if (!seen.has(item.case_id)) {
      nextTemplates.push(item);
      seen.add(item.case_id);
    }
  });
  v2State.templates = nextTemplates;
  v2State.visibleTemplates = nextTemplates;
  v2State.templateTotal = Number(page?.total ?? v2State.templateTotal ?? nextTemplates.length);
  v2State.templateNextCursor = page?.next_cursor || null;
  v2State.templateHasMore = Boolean(page?.has_more);
  v2State.templateRenderLimit = reset ? v2TemplatePageSize : nextTemplates.length;
}

function v2TemplatePageEndpoint({ cursor = null, facet = v2State.activeCaseFacet, limit = v2TemplatePageSize } = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  if (facet && facet !== "all") params.set("facet", facet);
  return `/templates/page?${params.toString()}`;
}

function v2TemplatePageKey({ cursor = null, facet = v2State.activeCaseFacet, limit = v2TemplatePageSize } = {}) {
  return v2TemplatePageEndpoint({ cursor, facet, limit });
}

async function loadV2TemplatePage({ reset = false, refreshIndex = false, silent = true } = {}) {
  if (v2State.templateLoadingMore) return;
  if (!reset && !v2State.templateHasMore) return;
  v2State.templateLoadingMore = true;
  if (!reset) renderV2Templates(v2State.visibleTemplates);
  let pageLoaded = false;
  try {
    if (refreshIndex) {
      applyV2TemplateIndex(await v2Request("/templates/index"));
    }
    const pageRequest = {
      cursor: reset ? null : v2State.templateNextCursor,
    };
    const page = await loadV2TemplatePageData(pageRequest, { allowPrefetchReuse: !reset });
    applyV2TemplatePage(page, { reset });
    pageLoaded = true;
    scheduleV2TemplatePrefetch();
    if (!silent) {
      updateV2Notice(`已加载 ${v2State.templates.length} / ${v2State.templateTotal || v2State.templates.length} 个案例。`, "success");
    }
  } catch (error) {
    updateV2Notice(`案例加载失败：${friendlyError(error)}`, "error");
  } finally {
    v2State.templateLoadingMore = false;
    if (pageLoaded || !reset) {
      renderV2CaseFacets();
      renderV2Templates(v2State.visibleTemplates);
    }
  }
}

async function loadV2TemplatePageData(request, { allowPrefetchReuse = true } = {}) {
  const key = v2TemplatePageKey(request);
  if (allowPrefetchReuse && v2State.templatePrefetchKey === key) {
    if (v2State.templatePrefetchPage) {
      const page = v2State.templatePrefetchPage;
      clearV2TemplatePrefetch();
      return page;
    }
    if (v2State.templatePrefetchPromise) {
      const page = await v2State.templatePrefetchPromise;
      clearV2TemplatePrefetch();
      if (page) return page;
    }
  }
  return v2Request(key);
}

function clearV2TemplatePrefetch() {
  v2State.templatePrefetchKey = "";
  v2State.templatePrefetchPromise = null;
  v2State.templatePrefetchPage = null;
}

function scheduleV2TemplatePrefetch() {
  if (v2State.caseSearchQuery || !v2State.templateHasMore || !v2State.templateNextCursor) {
    clearV2TemplatePrefetch();
    return;
  }
  const request = { cursor: v2State.templateNextCursor };
  const key = v2TemplatePageKey(request);
  if (v2State.templatePrefetchKey === key && (v2State.templatePrefetchPage || v2State.templatePrefetchPromise)) return;
  clearV2TemplatePrefetch();
  v2State.templatePrefetchKey = key;
  v2State.templatePrefetchPromise = v2IdleCallback(() => v2Request(key))
    .then((page) => {
      if (v2State.templatePrefetchKey === key) v2State.templatePrefetchPage = page;
      return page;
    })
    .catch((error) => {
      if (v2State.templatePrefetchKey === key) clearV2TemplatePrefetch();
      console.warn("V2 template prefetch failed", error);
      return null;
    });
}

function v2IdleCallback(callback) {
  return new Promise((resolve, reject) => {
    const run = () => {
      try {
        Promise.resolve(callback()).then(resolve, reject);
      } catch (error) {
        reject(error);
      }
    };
    if ("requestIdleCallback" in window) {
      window.requestIdleCallback(run, { timeout: 1600 });
    } else {
      window.setTimeout(run, 500);
    }
  });
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
    clearV2TemplatePrefetch();
    if (!query) {
      v2State.activeCaseFacet = "all";
      await loadV2TemplatePage({ reset: true, refreshIndex: true, silent: true });
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
      v2State.templateTotal = v2State.templates.length;
      v2State.templateNextCursor = null;
      v2State.templateHasMore = false;
      v2State.activeCaseFacet = "all";
      v2State.templateRenderLimit = v2TemplatePageSize;
      v2State.visibleTemplates = v2State.templates;
      renderV2CaseFacets();
      renderV2Templates(v2State.visibleTemplates);
    }
    if (query && v2State.visibleTemplates.length === 0) {
      updateV2Notice("没有匹配到相关案例。可以换一个更宽泛的描述，比如用途、主体、风格或关键材质。", "warning");
    } else {
      updateV2Notice(query ? `已按相关度找到 ${v2State.visibleTemplates.length} 个案例。` : `已展示 ${v2State.templates.length} / ${v2State.templateTotal || v2State.templates.length} 个案例。`, "success");
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

function renderV2CaseFacets() {
  if (!els.v2CaseFacetBar) return;
  const indexFacets = !v2State.caseSearchQuery && Array.isArray(v2State.templateIndex?.facets) ? v2State.templateIndex.facets : [];
  const facets = indexFacets.length
    ? indexFacets.map((item) => [item.value, item.count]).slice(0, 28)
    : v2LocalFacetCounts(v2State.templates).slice(0, 28);
  els.v2CaseFacetBar.innerHTML = "";
  const allCount = v2State.caseSearchQuery ? v2State.templates.length : Number(v2State.templateIndex?.total || v2State.templateTotal || v2State.templates.length);
  const allButton = v2FacetButton("全部", "all", allCount);
  els.v2CaseFacetBar.appendChild(allButton);
  facets.forEach(([tag, count]) => {
    els.v2CaseFacetBar.appendChild(v2FacetButton(v2DisplayLabel(tag), tag, count));
  });
}

function v2LocalFacetCounts(templates) {
  const counts = new Map();
  templates.forEach((template) => {
    const templateTags = new Set([template.category, ...(template.style_tags || []), ...(template.use_case_tags || [])].filter(Boolean));
    templateTags.forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
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

async function applyV2CaseFacet() {
  if (v2State.caseSearchQuery) {
    const facet = v2State.activeCaseFacet;
    v2State.visibleTemplates =
      facet === "all"
        ? v2State.templates
        : v2State.templates.filter((template) =>
            [template.category, ...(template.style_tags || []), ...(template.use_case_tags || [])].includes(facet)
          );
    v2State.templateRenderLimit = v2TemplatePageSize;
    renderV2CaseFacets();
    renderV2Templates(v2State.visibleTemplates);
    updateV2Notice(v2State.visibleTemplates.length ? `当前显示 ${v2State.visibleTemplates.length} 个案例。` : "这个分类下没有匹配案例。", v2State.visibleTemplates.length ? "success" : "warning");
    return;
  }
  toggleV2Loading(true);
  try {
    clearV2TemplatePrefetch();
    await loadV2TemplatePage({ reset: true, silent: true });
    updateV2Notice(v2State.visibleTemplates.length ? `当前显示 ${v2State.visibleTemplates.length} / ${v2State.templateTotal || v2State.visibleTemplates.length} 个案例。` : "这个分类下没有匹配案例。", v2State.visibleTemplates.length ? "success" : "warning");
  } finally {
    toggleV2Loading(false);
  }
}

function renderV2Templates(templates) {
  if (!els.v2TemplateGrid) return;
  els.v2TemplateGrid.innerHTML = "";
  const isSearchMode = Boolean(v2State.caseSearchQuery);
  const renderLimit = isSearchMode ? Math.min(v2State.templateRenderLimit, templates.length) : templates.length;
  const renderedTemplates = templates.slice(0, renderLimit);
  const total = isSearchMode ? templates.length : v2State.templateTotal || templates.length;
  els.v2TemplateCount.textContent = total ? `${renderLimit}/${total}` : "0";
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
  renderedTemplates.forEach((template, index) => {
    const card = document.createElement("article");
    card.className = `v2-template-card ${template.case_id === v2State.selectedTemplateId ? "selected" : ""}`;

    const preview = document.createElement(template.preview_url ? "button" : "div");
    preview.className = "v2-template-preview";
    if (template.preview_url) {
      preview.type = "button";
      const fullImageUrl = v2CasePreviewUrl(template.preview_url, template.index_version);
      const image = document.createElement("img");
      image.src = v2CaseThumbnailUrl(template.preview_url, "grid", template.index_version) || fullImageUrl;
      image.alt = template.title || "案例预览";
      image.width = 720;
      image.height = 900;
      image.loading = index < v2TemplateEagerImageCount ? "eager" : "lazy";
      image.decoding = "async";
      image.fetchPriority = index < v2TemplateEagerImageCount ? "high" : "low";
      image.addEventListener("error", () => fallbackV2CaseImageToPreview(image, fullImageUrl, preview));
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
  if ((isSearchMode && renderLimit < templates.length) || (!isSearchMode && v2State.templateHasMore)) {
    const loadMore = document.createElement("article");
    loadMore.className = "v2-template-load-more";
    const text = document.createElement("span");
    text.textContent = `已加载 ${renderLimit} / ${total}`;
    const button = document.createElement("button");
    button.className = "button secondary";
    button.type = "button";
    button.textContent = v2State.templateLoadingMore ? "加载中..." : "加载更多案例";
    button.disabled = v2State.templateLoadingMore;
    button.addEventListener("click", () => {
      if (isSearchMode) {
        v2State.templateRenderLimit = Math.min(v2State.templateRenderLimit + v2TemplatePageSize, templates.length);
        renderV2Templates(templates);
        return;
      }
      loadV2TemplatePage({ silent: false });
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
    url: previewUrl || v2CasePreviewUrl(template.preview_url, template.index_version),
    format: "jpg",
    meta: [...(template.style_tags || []), ...(template.use_case_tags || [])].slice(0, 8).map(v2DisplayLabel).join(" · ") || v2DisplayLabel(template.category),
    promptText: template.summary || template.why_selected || "",
  });
}

function findV2TemplateInCache(caseId) {
  if (!caseId) return null;
  const pools = [
    v2State.selectedTemplateDetail,
    ...(v2State.templates || []),
    ...(v2State.visibleTemplates || []),
    ...Object.values(v2State.templateDetailCache || {}),
  ].filter(Boolean);
  return pools.find((template) => template.case_id === caseId) || null;
}

async function loadV2TemplateDetailForHistory(caseId) {
  if (!caseId) return null;
  if (v2State.templateDetailCache?.[caseId]) return v2State.templateDetailCache[caseId];
  const cached = findV2TemplateInCache(caseId);
  if (cached?.preview_url && cached?.title) {
    v2State.templateDetailCache[caseId] = cached;
    return cached;
  }
  try {
    const detail = await v2Request(`/prompt-cases/${encodeURIComponent(caseId)}`);
    v2State.templateDetailCache[caseId] = detail;
    return detail;
  } catch (error) {
    if (cached) return cached;
    console.warn("Template history detail load failed", caseId, error);
    return null;
  }
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

function v2CasePreviewUrl(url, version = "") {
  if (!url) return "";
  const assetPath = v2CaseAssetPath(url);
  if (assetPath) return v2CaseThumbnailEndpoint(assetPath, "preview", version);
  if (url.startsWith("/api/v2/")) return v2MediaUrl(url);
  return url;
}

function v2CaseThumbnailUrl(url, variant = "grid", version = "") {
  const assetPath = v2CaseAssetPath(url);
  if (assetPath) return v2CaseThumbnailEndpoint(assetPath, variant, version);
  if (url?.startsWith("/api/v2/")) return v2MediaUrl(url);
  return url;
}

function v2CaseThumbnailEndpoint(assetPath, variant = "grid", version = "") {
  const endpoint = `${v2ApiBase}/case-thumbnails/${variant}/${encodeV2CaseAssetPath(assetPath)}`;
  return version ? `${endpoint}?v=${encodeURIComponent(version)}` : endpoint;
}

function v2CaseAssetPath(url) {
  if (!url) return "";
  const normalizedUrl = String(url);
  const thumbnailMarker = "/case-thumbnails/";
  if (normalizedUrl.includes(thumbnailMarker)) {
    const thumbnailPath = normalizedUrl.split(thumbnailMarker)[1].split("#", 1)[0].split("?", 1)[0].replace(/^\/+/, "");
    return thumbnailPath.replace(/^(grid|preview)\//, "");
  }
  const assetMarker = "/case-assets/";
  if (normalizedUrl.includes(assetMarker)) {
    return normalizedUrl.split(assetMarker)[1].split("#", 1)[0].split("?", 1)[0].replace(/^\/+/, "");
  }
  if (url.startsWith("../images/")) {
    return url.replace(/^(\.\.\/)+/, "");
  }
  const marker = "/awesome-gpt-image-2-API-and-Prompts/main/";
  if (url.includes("raw.githubusercontent.com") && url.includes(marker)) {
    return url.split(marker)[1];
  }
  const blobMarker = "/awesome-gpt-image-2-API-and-Prompts/blob/main/";
  if (url.includes("github.com") && url.includes(blobMarker)) {
    return url.split(blobMarker)[1];
  }
  const rawMarker = "/awesome-gpt-image-2-API-and-Prompts/raw/main/";
  if (url.includes("github.com") && url.includes(rawMarker)) {
    return url.split(rawMarker)[1];
  }
  return "";
}

function encodeV2CaseAssetPath(assetPath) {
  return assetPath
    .split("/")
    .map(encodeV2CaseAssetSegment)
    .join("/");
}

function encodeV2CaseAssetSegment(segment) {
  try {
    return encodeURIComponent(decodeURIComponent(segment));
  } catch {
    return encodeURIComponent(segment);
  }
}

function fallbackV2CaseImageToPreview(image, fullImageUrl, preview) {
  if (!image || image.dataset.caseFallbackApplied === "1") {
    if (preview) {
      preview.classList.add("missing-case-preview");
      preview.textContent = "Case";
    }
    return;
  }
  image.dataset.caseFallbackApplied = "1";
  if (fullImageUrl && image.src !== fullImageUrl) {
    image.src = fullImageUrl;
    return;
  }
  if (preview) {
    preview.classList.add("missing-case-preview");
    preview.textContent = "Case";
  }
}

async function selectV2Template(caseId) {
  clearV2FavoriteReference({ keepNotice: true });
  v2State.selectedTemplateId = caseId;
  const template = v2State.templates.find((item) => item.case_id === caseId);
  els.v2SelectedTemplateLabel.textContent = template ? `模板：${template.title}` : `模板：${caseId}`;
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

function clearV2Template(options = {}) {
  v2State.selectedTemplateId = null;
  v2State.selectedTemplateDetail = null;
  v2State.templateAutoFields = { subject: "", style: "", useCase: "" };
  if (!options.keepFavoriteReference) clearV2FavoriteReference({ keepNotice: true });
  els.v2SelectedTemplateLabel.textContent = "未选择模板";
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
  const waitingMessage = v2QueuedRetryMessage(run);
  if (run?.status === "failed") return run.next_actions?.[0] || "任务失败，已停止生成。";
  if (run?.status === "blocked_by_policy") return "安全策略要求停止本次生成。";
  if (run?.status === "waiting_for_user") return "需要用户确认后继续。";
  if (run?.status === "completed") return outputs.length ? `流程完成，共得到 ${outputs.length} 张输出。` : "流程结束。";
  if (waitingMessage) return waitingMessage;
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
  if (v2QueuedRetryMessage(run)) return "warning";
  if (run?.orchestrator_decision?.fallback_reason) return "warning";
  return "info";
}

function v2QueuedRetryMessage(run) {
  if (!run || run.status === "completed" || run.status === "failed") return "";
  const actions = Array.isArray(run.next_actions) ? run.next_actions : [];
  const message = String(actions[0] || "").trim();
  if (!message) return "";
  if (/上游|线路|额度|限流|队列|自动重试|稍后重试|暂时不可用|rate limit|retry/i.test(message)) {
    return message;
  }
  const job = (run.generation_jobs || [])[0];
  const error = job?.error || {};
  if (error.retryable || error.error_code === "provider_rate_limit") {
    return message || "上游暂时不可用，任务已保留在队列中，稍后自动重试。";
  }
  return "";
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
    const favoriteReferenceAsset = await ensureV2FavoriteReferenceAsset();
    const assetPayload = [...v2FavoriteReferencePayload(favoriteReferenceAsset), ...v2AssetPayload()];
    const templateCaseId = favoriteReferenceAsset ? null : v2State.selectedTemplateId;
    const output = {
      count: Number(els.v2CountInput.value),
      quality: "high",
      output_format: "png",
      provider_hint: imageProvider || "auto",
    };
    if (v2State.selectedRatio) {
      output.aspect_ratio = v2State.selectedRatio;
    }
    const promptTransformMode = v2PromptTransformMode();
    if (promptTransformMode !== "auto") {
      output.prompt_transform_mode = promptTransformMode;
    }
    const queuedRun = await v2Request("/creative/runs/async", {
      method: "POST",
      body: {
        user_prompt: prompt,
        mode_hint: templateCaseId ? "template_customize" : "smart_enhance",
        template_case_id: templateCaseId,
        assets: assetPayload,
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
    scrollV2HomeResultsIntoView(run);
    await loadV2History({ silent: true });
    await refreshVeyraAccountPanelAfterHistoryChange();
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
  return Boolean(String(prompt || "").trim() || v2State.selectedTemplateId || v2State.favoriteReferenceItem || v2State.uploadedAssets.length);
}

function setV2PromptTransformMode(mode) {
  const nextMode = Object.prototype.hasOwnProperty.call(v2PromptTransformModes, mode) ? mode : "auto";
  v2State.promptTransformMode = nextMode;
  document.querySelectorAll("[data-v2-prompt-transform]").forEach((button) => {
    const active = button.dataset.v2PromptTransform === nextMode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-checked", String(active));
  });
  if (els.v2PromptTransformState) {
    els.v2PromptTransformState.textContent = v2PromptTransformModes[nextMode].label;
  }
  updateV2PromptTransformHint();
}

function v2PromptTransformMode() {
  const mode = v2State.promptTransformMode || "auto";
  return Object.prototype.hasOwnProperty.call(v2PromptTransformModes, mode) ? mode : "auto";
}

function hydrateV2PromptTransformButtons() {
  document.querySelectorAll("[data-v2-prompt-transform]").forEach((button) => {
    const mode = button.dataset.v2PromptTransform || "auto";
    const profile = v2PromptTransformModes[mode];
    if (!profile) return;
    button.textContent = profile.label;
    button.dataset.tooltip = profile.hint;
    button.setAttribute("aria-label", `${profile.label}：${profile.hint}`);
    button.title = profile.hint;
  });
}

function v2SizeLabel(value) {
  const labels = {
    "": "自动画幅",
    "1024x1536": "竖版",
    "1024x1024": "方图",
    "1536x1024": "横版",
  };
  return labels[value || ""] || value || "自动画幅";
}

function hydrateV2AspectButtons() {
  document.querySelectorAll("[data-v2-ratio]").forEach((button) => {
    const value = button.dataset.v2Ratio || "";
    const hints = {
      "": "不锁定尺寸，可能随模板、生图引擎或探索模式变化。",
      "1024x1536": "锁定竖版输出：1024x1536。探索模式只改变创意路径，不改变画幅。",
      "1024x1024": "锁定方图输出：1024x1024。探索模式只改变创意路径，不改变画幅。",
      "1536x1024": "锁定横版输出：1536x1024。探索模式只改变创意路径，不改变画幅。",
    };
    button.textContent = v2SizeLabel(value).replace("画幅", "");
    button.title = hints[value] || value;
    button.setAttribute("aria-label", `${v2SizeLabel(value)}：${hints[value] || "手动画幅锁定。"}`);
  });
}

function updateV2PromptTransformHint() {
  if (!els.v2PromptTransformHint) return;
  const mode = v2PromptTransformMode();
  els.v2PromptTransformHint.textContent = v2PromptTransformModes[mode]?.hint || "";
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

function scrollV2HomeResultsIntoView(run) {
  const outputs = (run?.generation_jobs || []).flatMap((job) => job.outputs || []);
  if (!outputs.length) return;
  const resultSection = els.v2Outputs?.closest(".gallery-wrap");
  resultSection?.scrollIntoView({ behavior: "smooth", block: "start" });
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

function v2PlanVariables(plan) {
  return plan?.user_variables || plan?.variables || {};
}

function v2FirstGenerationJob(run) {
  const jobs = Array.isArray(run?.generation_jobs) ? run.generation_jobs : [];
  return jobs.find((job) => v2PlanVariables(job?.prompt_plan).prompt_transform) || jobs.find((job) => job?.prompt_plan) || null;
}

function v2PromptTransformMetadata(plan, run = v2State.currentRun) {
  const variables = v2PlanVariables(plan);
  const jobVariables = v2PlanVariables(v2FirstGenerationJob(run)?.prompt_plan);
  return variables.prompt_transform || jobVariables.prompt_transform || null;
}

function v2GenerationPromptFromPlan(plan, run = v2State.currentRun) {
  const variables = v2PlanVariables(plan);
  const jobVariables = v2PlanVariables(v2FirstGenerationJob(run)?.prompt_plan);
  return v2CleanPromptText(variables.generation_prompt || jobVariables.generation_prompt || "");
}

function v2PromptTransformLabel(mode, fidelity) {
  const normalized = String(mode || "").toLowerCase();
  if (normalized && v2PromptTransformModes[normalized]) return v2PromptTransformModes[normalized].label;
  if (fidelity === "strict") return v2PromptTransformModes.enhanced.label;
  if (fidelity === "original") return v2PromptTransformModes.stable.label;
  if (fidelity === "off") return v2PromptTransformModes.exploration.label;
  return v2PromptTransformModes.auto.label;
}

function v2PromptTransformStatus(transform) {
  if (!transform) return "等待生成";
  if (transform.fallback_used) return "已回退";
  return transform.applied ? "已应用" : "未改写";
}

function v2PromptPreviewText(text, limit = 900) {
  const value = v2CleanPromptText(text);
  if (!value || value.length <= limit) return value;
  return `${value.slice(0, limit).trimEnd()}\n...`;
}

function v2PromptTransformPlanLines(transform, plan, run) {
  const variables = v2PlanVariables(plan);
  const requested = variables.prompt_transform_mode || "auto";
  const lines = [];
  if (!transform) {
    lines.push(`Prompt Transform: ${v2PromptTransformLabel(requested, "")} · 待生成`);
    return lines;
  }
  const label = v2PromptTransformLabel(transform.transform_mode, transform.fidelity_mode);
  lines.push(`Prompt Transform: ${label} · ${v2PromptTransformStatus(transform)}`);
  if (Number(transform.constraint_count || 0) > 0) {
    lines.push(`Hard Constraints: ${transform.constraint_count}`);
    (transform.constraints || []).slice(0, 6).forEach((item) => lines.push(`- ${item}`));
  }
  const generationPrompt = v2GenerationPromptFromPlan(plan, run);
  const originalPrompt = v2CleanPromptText(plan?.prompt || "");
  if (generationPrompt && generationPrompt !== originalPrompt) {
    lines.push("最终提示词预览:");
    lines.push(v2PromptPreviewText(generationPrompt));
  }
  return lines;
}

function v2PromptTransformText(transform) {
  if (!transform) return "";
  const lines = [
    "提示词转换",
    `${v2PromptTransformLabel(transform.transform_mode, transform.fidelity_mode)} · ${v2PromptTransformStatus(transform)}`,
  ];
  if (Number(transform.constraint_count || 0) > 0) {
    lines.push(`硬约束 ${transform.constraint_count} 条`);
    (transform.constraints || []).slice(0, 8).forEach((item) => lines.push(`- ${item}`));
  }
  if (transform.fallback_used && transform.error) {
    lines.push(`回退原因：${transform.error}`);
  }
  return lines.join("\n");
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
  const transformLines = v2PromptTransformPlanLines(v2PromptTransformMetadata(plan, run), plan, run);
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
    assetLines.push(`生成输入: ${providerInputOperationLabel(providerPlan.operation)} · 参考图 ${providerPlan.reference_image_count} 张`);
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
    ...(transformLines.length ? ["", transformLines.join("\n")] : []),
    "",
    `Negative: ${plan.negative_prompt || "-"}`,
    "",
    `Mode: ${plan.mode}`,
    `Aspect: ${v2AspectDisplay(plan)}`,
    `Count: ${plan.provider_parameters?.count || "-"}`,
    ...(assetLines.length ? ["", assetLines.join("\n")] : []),
    "",
    plan.explanation || "",
  ].filter((line, index, list) => line || list[index - 1]);
  els.v2PromptPlan.textContent = lines.join("\n");
}

function v2AspectDisplay(plan) {
  const lock = plan?.user_variables?.aspect_lock || {};
  const provider = plan?.provider_parameters || {};
  if (lock.locked) {
    const value = lock.value || provider.size || provider.aspect_ratio || "-";
    const ratio = lock.aspect_ratio ? ` · ${lock.aspect_ratio}` : "";
    return `${value}${ratio} (locked)`;
  }
  return provider.aspect_ratio || provider.size || "auto";
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
  const renderableItems = items.filter((item) => isRenderableV2HistoryImage(item));
  const visibleItems = renderableItems.filter((item) => !v2State.historyFavoritesOnly || item.favorite);
  const hiddenMockCount = items.length - renderableItems.length;
  const renderLimit = Math.min(v2State.historyRenderLimit, visibleItems.length);
  const renderedItems = visibleItems.slice(0, renderLimit);
  els.v2HistoryCount.textContent = renderLimit < visibleItems.length ? `${renderLimit}/${visibleItems.length}` : String(visibleItems.length);
  els.v2HistoryGrid.classList.toggle("empty-v2-list", visibleItems.length === 0);
  renderedItems.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = `v2-history-card ${item.favorite ? "is-favorite" : ""}`.trim();
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
      preview.addEventListener("click", () => openV2HistoryLightbox(item, index, card));
    }
    const favoriteButton = createFavoriteButton({
      favorite: item.favorite,
      label: item.favorite ? "取消星标" : "星标收藏",
      onToggle: (next) => toggleV2Favorite(item, next),
    });

    const meta = document.createElement("div");
    meta.className = "v2-history-meta";
    const prompt = document.createElement("strong");
    prompt.textContent = cardPrompt || item.output_id;
    const details = document.createElement("span");
    details.textContent = historyDetailText(historyRecordLabel(item), v2HistoryProviderResultText(item), formatDate(item.created_at));
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
    actions.append(link);
    if (historyItemCanDelete(item)) {
      const deleteButton = document.createElement("button");
      deleteButton.className = "delete-link";
      deleteButton.type = "button";
      deleteButton.textContent = "删除";
      deleteButton.addEventListener("click", (event) => {
        event.stopPropagation();
        deleteV2HistoryItem(item, card);
      });
      actions.append(deleteButton);
    }
    footer.append(id, actions);

    card.append(preview, favoriteButton, meta, footer);
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

async function toggleV2Favorite(item, favorite) {
  await v2Request(`/image/history/${encodeURIComponent(item.output_id)}/favorite`, {
    method: "PUT",
    body: { favorite },
  });
  v2State.history = v2State.history.map((entry) => (entry.output_id === item.output_id ? { ...entry, favorite } : entry));
  if (!favorite && v2State.favoriteReferenceItem?.output_id === item.output_id) {
    clearV2FavoriteReference({ keepNotice: true });
  }
  renderV2History(v2State.history);
  if (els.v2FavoriteReferenceModal && !els.v2FavoriteReferenceModal.hidden) renderV2FavoriteReferencePicker();
  if (activePanelName() === "v2") renderHeroHistory(v2State.history, { source: "v2" });
  showGlobalToast(favorite ? "2.0 图片已加入星标。" : "2.0 图片已取消星标。");
}

function v2FavoriteReferenceItems() {
  return (v2State.history || []).filter((item) => item.favorite && isRenderableV2HistoryImage(item));
}

function openV2FavoriteReferencePicker() {
  if (!els.v2FavoriteReferenceModal) return;
  renderV2FavoriteReferencePicker();
  els.v2FavoriteReferenceModal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeV2FavoriteReferencePicker() {
  if (!els.v2FavoriteReferenceModal) return;
  els.v2FavoriteReferenceModal.hidden = true;
  document.body.classList.remove("modal-open");
}

function renderV2FavoriteReferencePicker() {
  if (!els.v2FavoriteReferenceGrid) return;
  const items = v2FavoriteReferenceItems();
  els.v2FavoriteReferenceGrid.innerHTML = "";
  els.v2FavoriteReferenceGrid.classList.toggle("empty-v2-list", items.length === 0);
  els.v2FavoriteReferenceGrid.classList.toggle("has-empty-message", items.length === 0);
  if (els.v2FavoriteReferenceCount) els.v2FavoriteReferenceCount.textContent = String(items.length);
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-v2-message";
    empty.textContent = "还没有可用于继续修改的 2.0 星标图片。请先在 2.0 历史缩略图上点亮星标。";
    els.v2FavoriteReferenceGrid.appendChild(empty);
    return;
  }
  items.forEach((item, index) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `favorite-picker-card ${v2State.favoriteReferenceItem?.output_id === item.output_id ? "selected" : ""}`.trim();
    const preview = document.createElement("span");
    preview.className = "favorite-picker-preview";
    const image = document.createElement("img");
    image.src = v2HistoryImageUrl(item);
    image.alt = v2HistoryCardPrompt(item) || `2.0 星标图片 ${index + 1}`;
    image.loading = "lazy";
    image.decoding = "async";
    preview.appendChild(image);
    const meta = document.createElement("span");
    meta.className = "favorite-picker-meta";
    const title = document.createElement("strong");
    title.textContent = v2HistoryCardPrompt(item) || item.output_id || `2.0 星标图片 ${index + 1}`;
    const detail = document.createElement("span");
    detail.textContent = historyDetailText(historyRecordLabel(item), v2HistoryProviderResultText(item), formatDate(item.created_at || item.updated_at));
    const action = document.createElement("em");
    action.className = "favorite-picker-action";
    action.textContent = v2State.favoriteReferenceItem?.output_id === item.output_id ? "已选择" : "选择此图继续修改";
    meta.append(title, detail, action);
    card.append(preview, meta);
    card.addEventListener("click", () => selectV2FavoriteReference(item));
    els.v2FavoriteReferenceGrid.appendChild(card);
  });
}

function selectV2FavoriteReference(item) {
  v2State.favoriteReferenceItem = item;
  v2State.favoriteReferenceAsset = null;
  clearV2Template({ keepFavoriteReference: true, keepNotice: true });
  updateV2FavoriteReferenceLabel();
  closeV2FavoriteReferencePicker();
  updateV2Notice("已选择星标图片作为继续修改参考；本次生成会放弃原模板，改用这张图作为画面参考。", "success");
  els.v2FavoriteReferenceLabel?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function clearV2FavoriteReference(options = {}) {
  v2State.favoriteReferenceItem = null;
  v2State.favoriteReferenceAsset = null;
  updateV2FavoriteReferenceLabel();
  if (!options.keepNotice) updateV2Notice("已清除 2.0 星标图继续修改参考。", "info");
}

function updateV2FavoriteReferenceLabel() {
  const item = v2State.favoriteReferenceItem;
  if (els.v2FavoriteReferenceLabel) {
    els.v2FavoriteReferenceLabel.textContent = item ? `已选择 ${shortOutputId(item.output_id)}` : "未选择";
    els.v2FavoriteReferenceLabel.title = item ? (v2HistoryCardPrompt(item) || item.output_id || "已选择") : "";
  }
  if (els.v2ClearFavoriteReferenceBtn) {
    els.v2ClearFavoriteReferenceBtn.hidden = !item;
  }
}

async function ensureV2FavoriteReferenceAsset() {
  const item = v2State.favoriteReferenceItem;
  if (!item?.output_id) return null;
  if (v2State.favoriteReferenceAsset?.source_output_id === item.output_id) {
    return v2State.favoriteReferenceAsset;
  }
  const asset = await v2Request(`/image/history/${encodeURIComponent(item.output_id)}/reference-asset`, {
    method: "POST",
    body: {
      role: "composition_reference",
      constraint_strength: "required",
      intended_use: "continue_modifying_selected_favorite_image",
      notes: "Use this starred V2 history image as the selected continuation frame reference. Current user changes take priority for local edits and replace conflicting visible details.",
    },
  });
  v2State.favoriteReferenceAsset = { ...asset, source_output_id: item.output_id };
  return v2State.favoriteReferenceAsset;
}

function isRenderableV2HistoryImage(item) {
  if (!item) return false;
  if (item.metadata?.mock || item.provider_id === "mock_image") return false;
  if (String(item.url || item.metadata?.url || "").includes("/mock-outputs/")) return false;
  return Boolean(v2HistoryImageUrl(item, { thumbnail: false }) || v2HistoryImageUrl(item));
}

function openV2HistoryLightbox(item, index = 0, card = null) {
  const cardPrompt = v2HistoryCardPrompt(item);
  const actions = historyItemCanDelete(item)
    ? [
        {
          label: "删除",
          tone: "danger",
          run: () => deleteV2HistoryItem(item, card),
        },
      ]
    : [];
  openImageLightbox({
    id: item.output_id,
    title: cardPrompt ? cardPrompt.slice(0, 34) : `2.0 历史图片 ${index + 1}`,
    url: v2HistoryImageUrl(item, { thumbnail: false }),
    thumbnailUrl: v2HistoryImageUrl(item),
    format: v2HistoryFormat(item),
    meta: historyDetailText(historyRecordLabel(item), v2HistoryProviderResultText(item), formatDate(item.created_at || item.updated_at)),
    promptText: v2PromptTextFromHistory(item),
    actions,
  });
}

async function deleteV2HistoryItem(item, card) {
  if (!historyItemCanDelete(item)) {
    updateV2Notice("这条历史记录不可删除。", "warning");
    return;
  }
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
    await refreshVeyraAccountPanelAfterHistoryChange();
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
  const variables = v2PlanVariables(plan);
  const original = v2CleanPromptText(variables.user_prompt || variables.original_prompt);
  const finalPrompt = v2CleanPromptText(variables.generation_prompt || plan.prompt);
  const finalLabel = plan.user_variables?.claude_final_prompt_used ? "Claude 思考后的最终提示词" : "Agent 最终提示词";
  const blocks = [`原始提示词\n${original || "未记录原始提示词。"}`];
  if (finalPrompt) blocks.push(`${finalLabel}\n${finalPrompt}`);
  const transformText = v2PromptTransformText(variables.prompt_transform);
  if (transformText) blocks.push(transformText);
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
  const transformText = v2PromptTransformText(metadata.prompt_transform);
  if (transformText) blocks.push(transformText);
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
      veyraState.usedTemplates = [];
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

async function openBillingAdmin(event) {
  event.preventDefault();
  try {
    await v2Request("/veyra/session-cookie", { method: "POST" });
    window.location.assign("/admin/billing");
  } catch (error) {
    showGlobalToast(`管理员设置打开失败：${friendlyError(error)}`, "error");
    if (error?.status === 401) {
      await handleVeyraUnauthorized();
    }
  }
}

function v2HistoryPath() {
  return "/veyra/history?limit=1000";
}

async function loadV2HistoryResponse() {
  return await v2Request(v2HistoryPath());
}

async function loadVeyraAuthPolicy() {
  if (veyraState.authPolicy) return veyraState.authPolicy;
  try {
    veyraState.authPolicy = await v2Request("/veyra/auth-policy", { skipVeyraAuth: true });
  } catch {
    veyraState.authPolicy = {
      enabled: false,
      require_ui_auth: false,
      login_base_url: defaultVeyraLoginBaseUrl,
    };
  }
  return veyraState.authPolicy;
}

function veyraLoginUrl(target = "alchemy") {
  const policy = veyraState.authPolicy || {};
  const base = String(policy.login_base_url || defaultVeyraLoginBaseUrl).replace(/\/+$/, "");
  return `${base}/_veyra/return?target=${encodeURIComponent(target)}`;
}

async function hasValidVeyraSession() {
  if (getVeyraToken()) return true;
  try {
    const account = await v2Request("/veyra/me", { skipVeyraAuth: true });
    veyraState.account = account;
    try {
      localStorage.setItem(veyraAccountStorageKey, JSON.stringify(account));
    } catch {
      // Ignore browser storage failures.
    }
    updateAdminSettingsEntry();
    return true;
  } catch {
    setVeyraToken("");
    return false;
  }
}

async function enforceVeyraUiAuth({ target = "alchemy" } = {}) {
  const policy = await loadVeyraAuthPolicy();
  if (!policy.enabled || !policy.require_ui_auth) return false;
  if (await hasValidVeyraSession()) return false;
  window.location.replace(veyraLoginUrl(target));
  return true;
}

function redirectToVeyraLogin(target = "alchemy") {
  window.location.replace(veyraLoginUrl(target));
}

async function handleVeyraUnauthorized() {
  setVeyraToken("");
  const policy = await loadVeyraAuthPolicy();
  if (policy.enabled && policy.require_ui_auth) {
    redirectToVeyraLogin("alchemy");
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
  if (!ticket) return true;
  try {
    const session = await v2Request("/veyra/login", {
      method: "POST",
      body: { ticket },
      skipVeyraAuth: true,
    });
    setVeyraToken(session.access_token || "");
    await syncVeyraSessionCookie();
    cleanVeyraTicketFromUrl();
    await loadVeyraAccountPanel({ silent: true, force: true });
    updateV2Notice("Veyra 账户已接入。", "success");
    return true;
  } catch (error) {
    setVeyraToken("");
    cleanVeyraTicketFromUrl();
    const message = `Veyra 登录失败：${friendlyError(error)}`;
    updateV2Notice(message, "error");
    showNotice(message, "error");
    return false;
  }
}

async function syncVeyraSessionCookie() {
  if (!getVeyraToken()) return;
  try {
    await v2Request("/veyra/session-cookie", { method: "POST" });
  } catch (error) {
    console.warn("Veyra session cookie sync failed", error);
  }
}

async function refreshVeyraAccount() {
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
  if (els.veyraAccountHistoryScope) els.veyraAccountHistoryScope.textContent = "当前账户与旧版生图记录";
  if (els.veyraAccountHistoryTitle) els.veyraAccountHistoryTitle.textContent = "我的生成记录";
  if (els.veyraAccountUsageTotal) els.veyraAccountUsageTotal.textContent = "-";
  renderVeyraAccountHistory([]);
  renderVeyraTemplateHistory([]);
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
    els.veyraAccountHistoryScope.textContent = isVeyraAdmin() ? "管理员可见全部账户" : "当前账户与旧版生图记录";
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
    detail.textContent = historyDetailText(
      accountHistorySourceLabel(item),
      historyRecordLabel(item),
      accountHistoryProviderText(item),
      formatDate(item.created_at || item.updated_at),
    );
    meta.append(title, detail);
    card.append(preview, meta);
    els.veyraAccountHistoryGrid.appendChild(card);
  });
}

function v2HistoryTemplateCaseId(item) {
  const contract = item?.metadata?.template_lock_contract || {};
  return String(
    item?.template_case_id ||
      item?.metadata?.template_case_id ||
      item?.metadata?.primary_case_id ||
      contract.locked_case_id ||
      contract.case_id ||
      ""
  ).trim();
}

async function buildVeyraTemplateHistory(v2Items = []) {
  const byCase = new Map();
  v2Items.forEach((item) => {
    const caseId = v2HistoryTemplateCaseId(item);
    if (!caseId) return;
    const time = historyTime(item);
    const existing = byCase.get(caseId);
    const next = existing || {
      case_id: caseId,
      usage_count: 0,
      latest_item: item,
      latest_time: time,
    };
    next.usage_count += 1;
    if (!existing || time > existing.latest_time) {
      next.latest_item = item;
      next.latest_time = time;
    }
    byCase.set(caseId, next);
  });

  const entries = [...byCase.values()].sort((a, b) => b.latest_time - a.latest_time);
  await Promise.all(
    entries.slice(0, 30).map(async (entry) => {
      const detail = await loadV2TemplateDetailForHistory(entry.case_id);
      entry.template = detail || null;
      entry.title = detail?.title || entry.case_id;
      entry.summary = detail?.summary || v2HistoryCardPrompt(entry.latest_item) || "";
      entry.preview_url = detail?.preview_url || "";
      entry.index_version = detail?.index_version || "";
      entry.category = detail?.category || "";
      entry.tags = [...(detail?.style_tags || []), ...(detail?.use_case_tags || [])].slice(0, 5);
    })
  );
  return entries;
}

function renderVeyraTemplateHistory(items = []) {
  if (!els.veyraTemplateHistoryList) return;
  els.veyraTemplateHistoryList.innerHTML = "";
  if (!getVeyraToken()) {
    renderAccountEmpty(els.veyraTemplateHistoryList, "登录后这里会展示 V2.0 曾经使用过的模板。");
    return;
  }
  if (!items.length) {
    renderAccountEmpty(els.veyraTemplateHistoryList, "还没有 V2.0 模板使用记录。", "去 V2.0 生图", () => switchTab("v2"));
    return;
  }
  items.slice(0, 30).forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "account-template-card";
    const previewUrl = item.preview_url ? v2CaseThumbnailUrl(item.preview_url, "grid", item.index_version) : "";
    const preview = document.createElement(previewUrl ? "button" : "div");
    preview.className = "account-template-preview";
    if (previewUrl) {
      preview.type = "button";
      const image = document.createElement("img");
      image.src = previewUrl;
      image.alt = item.title || `历史使用模板 ${index + 1}`;
      image.loading = "lazy";
      image.decoding = "async";
      preview.appendChild(image);
      preview.addEventListener("click", () => openV2CasePreview(item.template || item, v2CasePreviewUrl(item.preview_url, item.index_version)));
    } else {
      preview.textContent = "Case";
    }

    const meta = document.createElement("div");
    meta.className = "account-template-meta";
    const title = document.createElement("strong");
    title.textContent = item.title || item.case_id || `模板 ${index + 1}`;
    const summary = document.createElement("p");
    summary.textContent = item.summary || "V2.0 生成时使用过的视觉模板。";
    const detail = document.createElement("span");
    const tags = item.tags?.length
      ? ` · ${item.tags.map(v2DisplayLabel).filter(Boolean).slice(0, 3).join(" / ")}`
      : item.category
        ? ` · ${v2DisplayLabel(item.category)}`
        : "";
    detail.textContent = `${formatDate(item.latest_item?.created_at || item.latest_item?.updated_at)} · 使用 ${item.usage_count} 次${tags}`;
    meta.append(title, summary, detail);
    card.append(preview, meta);
    els.veyraTemplateHistoryList.appendChild(card);
  });
}

function mergeAccountHistory(v1Items = [], v2Items = []) {
  const normalized = [
    ...v1Items.map((item) => ({ ...item, account_history_source: "v1" })),
    ...v2Items.map((item) => ({ ...item, account_history_source: "v2" })),
  ];
  return normalized.sort(compareHistoryItems);
}

function mergeVeyraUsage(v1Items = [], v2Items = []) {
  const seen = new Set();
  return [...v1Items, ...v2Items]
    .filter((item) => {
      const key = item?.idempotency_key || item?.reference_id || JSON.stringify(item);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => historyTime(b) - historyTime(a));
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
    veyraState.usedTemplates = [];
    renderVeyraSignedOut();
    return null;
  }
  if (veyraState.loading && !force) return veyraState.account;
  setVeyraAccountLoading(true);
  try {
    const [account, v1HistoryResponse, v2HistoryResponse, v1UsageResponse, v2UsageResponse] = await Promise.all([
      refreshVeyraAccount(),
      request("/v1/image/history?limit=1000"),
      loadV2HistoryResponse(),
      request("/v1/veyra/usage?limit=100"),
      v2Request("/veyra/usage?limit=100"),
    ]);
    veyraState.account = account;
    veyraState.history = mergeAccountHistory(v1HistoryResponse.items || [], v2HistoryResponse.items || []);
    veyraState.usage = mergeVeyraUsage(v1UsageResponse.items || [], v2UsageResponse.items || []);
    veyraState.usedTemplates = await buildVeyraTemplateHistory(v2HistoryResponse.items || []);
    renderVeyraAccountSummary();
    renderVeyraAccountHistory(veyraState.history);
    renderVeyraTemplateHistory(veyraState.usedTemplates);
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

async function refreshVeyraAccountPanelAfterHistoryChange() {
  if (!getVeyraToken() || !els.veyraAccountHistoryGrid) return;
  try {
    await loadVeyraAccountPanel({ silent: true, force: true });
  } catch (error) {
    console.warn("Veyra account panel refresh failed", error);
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
    credentials: "include",
  });
  if (!response.ok) {
    const detail = await response.text();
    if (response.status === 401 && !options.skipVeyraAuth) {
      await handleVeyraUnauthorized();
    }
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
  const files = Array.from(els.v2AssetInput?.files || []);
  if (!files.length) return;
  const imageFiles = files.filter(isImageAssetFile);
  if (imageFiles.length !== files.length) {
    updateV2Notice("V2 上传素材目前只支持图片，已跳过非图片文件。", "warning");
  }
  if (!imageFiles.length) {
    clearV2Asset({ keepNotice: true });
    if (els.v2AssetInput) els.v2AssetInput.value = "";
    return;
  }
  const role = v2PrimaryAssetRole();
  const strength = v2SelectedAssetStrength();
  if (els.v2AssetName) els.v2AssetName.textContent = `${imageFiles.length} 张素材上传中`;
  if (els.v2AssetState) els.v2AssetState.textContent = "上传中";
  renderV2AssetPreview(imageFiles[0], imageFiles.length);
  try {
    const uploaded = [];
    for (const file of imageFiles) {
      uploaded.push(await uploadV2AssetFile(file, { role, strength }));
      if (els.v2AssetState) els.v2AssetState.textContent = `上传 ${uploaded.length}/${imageFiles.length}`;
    }
    v2State.uploadedAssets = [...v2State.uploadedAssets, ...uploaded];
    renderV2AssetPanel();
    updateV2Notice(`V2 已分析 ${uploaded.length} 张素材；生成时会交给 Claude 中枢按当前用途绑定。`, "success");
  } catch (error) {
    if (els.v2AssetState) els.v2AssetState.textContent = "失败";
    renderV2AssetPanel();
    updateV2Notice(`V2 素材上传失败：${friendlyError(error)}`, "error");
  } finally {
    if (els.v2AssetInput) els.v2AssetInput.value = "";
  }
}

async function uploadV2AssetFile(file, { role, strength }) {
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
  return {
    asset_id: asset.asset_id,
    filename: asset.filename || file.name,
    status: asset.status,
    role,
    constraint_strength: strength,
    brief: asset.brief || null,
    source_url: asset.source_url || null,
    preview_url: asset.thumbnail_url || asset.source_url || null,
  };
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
  const roles = v2RolesForCurrentPrompt();
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

function v2FavoriteReferencePayload(asset) {
  if (!asset?.asset_id) return [];
  return [
    {
      asset_id: asset.asset_id,
      role: "composition_reference",
      constraint_strength: "required",
      notes: "Use the selected starred V2 history image as the continuation frame: preserve its composition, lighting, palette, spatial hierarchy, and visual rhythm while applying the current user changes. If the current user change conflicts with an object, prop, text, or surface in the reference image, replace the conflicting reference detail instead of preserving it.",
    },
  ];
}

function v2RolesForCurrentPrompt() {
  const roles = v2SelectedAssetRoles();
  if (v2PromptRequestsUploadedContentSource() && !roles.includes("subject_reference")) {
    return [...roles, "subject_reference"];
  }
  return roles;
}

function v2PromptRequestsUploadedContentSource() {
  const text = `${els.v2PromptInput?.value || ""} ${els.v2AssetNotesInput?.value || ""}`.toLowerCase();
  if (!text.trim()) return false;
  const hasUploadedSource =
    /(上传(的)?(图片|图|素材|参考图)|参考图|上次(的)?图片|原图|图里|图中|图片里|图片中|uploaded\s+(image|asset|reference)|source\s+(image|poster|asset))/i.test(text);
  const hasContent =
    /(食物内容|食物部分|菜品|菜名|食品|美食|餐食|商品内容|产品内容|文案|文字|标题|价格|优惠|套餐|配送|加购|页脚|购买|规则|二维码|qr|copy|text|menu|food|dish|product|offer|price)/i.test(text);
  const hasTransfer =
    /(摘取|提取|抽取|取出|保留|完整保留|体现|放到|匹配到|迁移|转移|套到|套进|设计成|改成|替换|replace|extract|migrate|transfer|preserve|fit\s+into|adapt\s+into)/i.test(text);
  const hasTemplate = /(模板|案例|海报|poster|template|case|layout)/i.test(text);
  return hasUploadedSource && hasContent && (hasTransfer || hasTemplate);
}

function renderV2AssetPreview(file, count = 1) {
  if (!els.v2AssetPreview || !els.v2AssetPreviewLabel) return;
  els.v2AssetPreview.classList.remove("empty-asset-preview");
  els.v2AssetPreview.style.backgroundImage = "";
  els.v2AssetPreviewLabel.textContent = count > 1 ? `${file.name} 等 ${count} 张` : file.name;
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
  const files = Array.from(els.assetInput?.files || []);
  if (!files.length) return;
  const imageFiles = files.filter(isImageAssetFile);
  if (imageFiles.length !== files.length) {
    showNotice("高级版素材目前只支持图片，已跳过非图片文件。", "warning");
  }
  if (!imageFiles.length) {
    els.assetInput.value = "";
    els.assetName.textContent = "支持多图，单次最多 6 张";
    els.assetState.textContent = "拒绝";
    resetAssetPreview();
    renderAssetPanel();
    return;
  }
  state.assetMode = "advanced";
  els.assetState.textContent = "上传";
  renderAssetPreview(imageFiles[0], imageFiles.length);
  try {
    const uploaded = [];
    for (const file of imageFiles) {
      uploaded.push(await uploadV1AssetFile(file));
      els.assetState.textContent = `上传 ${uploaded.length}/${imageFiles.length}`;
    }
    state.assets = [...state.assets, ...uploaded];
    state.assetIds = state.assets.map((asset) => asset.asset_id);
    renderAssetPanel();
    els.assetState.textContent = "高级";
    showNotice(`已上传 ${uploaded.length} 张素材；生成时会作为多图参考传入。`, "success");
  } catch (error) {
    els.assetState.textContent = "失败";
    renderAssetPanel();
    showNotice(`高级素材上传失败：${friendlyError(error)}`, "error");
  } finally {
    els.assetInput.value = "";
  }
}

async function uploadV1AssetFile(file) {
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
    throw new Error("素材未通过校验，请更换素材后重试。");
  }
  await request(`/v1/assets/${upload.asset_id}/content`, {
    method: "PUT",
    body: {
      content_base64: await fileToBase64(file),
      mime_type: file.type || imageMimeTypeFromName(file.name),
    },
  });
  const asset = await request(`/v1/assets/${upload.asset_id}/complete`, { method: "POST" });
  if (asset.status !== "ready") {
    throw new Error(asset.error?.message || `素材状态：${asset.status}`);
  }
  addEvent("asset.status", `${asset.id} · ${asset.material_brief?.asset_type || "image"}`);
  return {
    asset_id: asset.id,
    filename: asset.filename || file.name,
    status: asset.status,
    material_brief: asset.material_brief || null,
    source_url: asset.source_url || `/v1/assets/${asset.id}/content`,
  };
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

function renderAssetPreview(file, count = 1) {
  els.assetPreview.classList.remove("empty-asset-preview");
  els.assetPreview.style.backgroundImage = "";
  els.assetPreviewLabel.textContent = count > 1 ? `${file.name} 等 ${count} 张` : file.name;
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

function clearV1Asset(options = {}) {
  state.assetIds = [];
  state.assets = [];
  state.assetMode = "basic";
  if (els.assetInput) els.assetInput.value = "";
  resetAssetPreview();
  renderAssetPanel();
  if (!options.keepNotice) {
    showNotice("已清除高级版参考素材。", "info");
    showGlobalToast("高级版素材已清除。");
  }
}

function renderAssetPanel() {
  const hasAssets = state.assets.length > 0;
  if (els.assetState) els.assetState.textContent = hasAssets ? "高级" : "空";
  if (els.clearAssetBtn) els.clearAssetBtn.hidden = !hasAssets;
  if (els.assetName) {
    els.assetName.textContent = hasAssets ? `${state.assets.length} 张素材已就绪` : "支持多图，单次最多 6 张";
  }
  if (!els.assetList) return;
  els.assetList.innerHTML = "";
  els.assetList.classList.toggle("empty-v2-list", !hasAssets);
  if (!hasAssets) {
    els.assetList.textContent = "暂无上传素材";
    return;
  }
  const roles = selectedAssetRolesFromDom();
  const strength = Number(els.assetStrengthInput?.value || 65);
  state.assets.forEach((asset, index) => {
    const row = document.createElement("div");
    row.className = "v2-asset-row";
    const title = document.createElement("strong");
    title.textContent = `${index + 1}. ${asset.filename || asset.asset_id}`;
    const detail = document.createElement("span");
    const summary = asset.material_brief?.summary || asset.material_brief?.asset_type || "";
    const roleText = roles.length ? roles.map(assetRoleLabel).join(" + ") : "请选择用途";
    detail.textContent = `${roleText} · 强度 ${strength}%${summary ? ` · ${summary}` : ""}`;
    row.append(title, detail);
    els.assetList.appendChild(row);
  });
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
    asset_intents: state.assetIds.flatMap((assetId) => roles.map((role) => advancedAssetIntentPayload(assetId, role))),
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

function v1ImageJobReady(job) {
  return job?.status === "ready" && Array.isArray(job.outputs) && job.outputs.length > 0;
}

function v1ImageJobTerminal(job) {
  return ["ready", "failed", "provider_not_configured", "rejected", "canceled"].includes(job?.status);
}

function v1ImageJobPollDelay(attempt) {
  if (attempt < 4) return 1200;
  if (attempt < 30) return 2500;
  return 5000;
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function waitForV1ImageJob(initialJob, { actionLabel = "生成", maxAttempts = 120 } = {}) {
  let job = initialJob;
  let transientErrors = 0;
  for (let attempt = 0; attempt <= maxAttempts; attempt += 1) {
    state.currentJob = job;
    setStatus(job?.status || "生成中", job?.outputs?.length || 0, job?.trace_id || "-");
    if (v1ImageJobReady(job) || v1ImageJobTerminal(job)) {
      return job;
    }
    if (!job?.id) {
      return job;
    }
    if (attempt === 0) {
      showNotice(`${actionLabel}任务已提交，后台正在生成。`, "info");
    }
    await delay(v1ImageJobPollDelay(attempt));
    try {
      job = await request(`/v1/image/jobs/${encodeURIComponent(job.id)}`);
      transientErrors = 0;
    } catch (error) {
      transientErrors += 1;
      if (transientErrors >= 3) {
        throw new Error(`${actionLabel}状态查询中断：${friendlyError(error)}。任务可能仍在后台继续，请稍后刷新历史。`);
      }
    }
  }
  throw new Error(`${actionLabel}仍在后台进行，请稍后刷新历史查看结果。`);
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
  if (
    !state.imageProviderReady ||
    els.openaiApiKeyInput.value.trim() ||
    els.doubaoImageApiKeyInput.value.trim() ||
    els.geminiImageApiKeyInput.value.trim() ||
    els.anthropicApiKeyInput.value.trim()
  ) {
    await syncProviderSettings({ silent: true });
  }
  if (!state.imageProviderReady) {
    showNotice(`生图模型未就绪。请先配置当前选择的 ${providerLabel(state.selectedProvider)} 独立 API。`, "warning");
    const keyInput = state.selectedProvider === "gemini_image"
      ? els.geminiImageApiKeyInput
      : state.selectedProvider === "doubao_image"
        ? els.doubaoImageApiKeyInput
        : els.openaiApiKeyInput;
    keyInput.focus();
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
  showNotice(`${modeText}正在生成 ${count} 张图片；使用 ${providerName} 独立通道，质量：${qualityMap[state.selectedQuality]}。`, "info");
  startImageProgress({ label: "生成中", count, providerName });
  renderSkeleton(count);
  let submittedJob = null;
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
    submittedJob = await request("/v1/image/jobs", {
      method: "POST",
      body,
    });
    const completedJob = await waitForV1ImageJob(submittedJob, { actionLabel: "生成" });
    stopImageProgress();
    state.currentJob = completedJob;
    setStatus(completedJob.status, completedJob.outputs.length, completedJob.trace_id);
    if (!v1ImageJobReady(completedJob)) {
      renderGallery([]);
      showNotice(`生成失败：${jobErrorMessage(completedJob)}`, "error");
      await refreshEvents();
      return;
    }
    renderGallery(completedJob.outputs);
    showNotice(`已生成 ${completedJob.outputs.length} 张图片：${imageProviderResultText(completedJob)}。`, "success");
    els.galleryWrap.scrollIntoView({ behavior: "smooth", block: "start" });
    await refreshHistory({ silent: true });
    await refreshVeyraAccountPanelAfterHistoryChange();
    await refreshEvents();
  } catch (error) {
    stopImageProgress();
    const submitted = Boolean(submittedJob?.id);
    showNotice(submitted ? friendlyError(error) : `生成失败：${friendlyError(error)}`, submitted ? "warning" : "error");
    setStatus(submitted ? "后台处理中" : "失败", 0, submittedJob?.trace_id || "-");
    if (!submitted) {
      renderGallery([]);
    }
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
  const sourceJobId = state.currentJob.id;
  const revisionProvider = state.currentJob.forceProviderPreference || state.selectedProvider;
  startImageProgress({ label: "修改中", count: 1, providerName: providerLabel(revisionProvider), traceId: state.currentJob.trace_id });
  let submittedJob = null;
  try {
    submittedJob = await request(`/v1/image/jobs/${sourceJobId}/revise`, {
      method: "POST",
      body: {
        output_id: state.selectedOutputId,
        feedback,
        preserve: ["composition", "main_subject"],
        provider_preference: revisionProvider,
      },
    });
    const completedJob = await waitForV1ImageJob(submittedJob, { actionLabel: "修改" });
    stopImageProgress();
    state.currentJob = completedJob;
    setStatus(completedJob.status, completedJob.outputs.length, completedJob.trace_id);
    if (!v1ImageJobReady(completedJob)) {
      showNotice(`修改失败：${jobErrorMessage(completedJob)}`, "error");
      await refreshEvents();
      return;
    }
    renderGallery(completedJob.outputs);
    showNotice(`修改版本已生成：${imageProviderResultText(completedJob)}。`, "success");
    els.galleryWrap.scrollIntoView({ behavior: "smooth", block: "start" });
    await refreshHistory({ silent: true });
    await refreshVeyraAccountPanelAfterHistoryChange();
    await refreshEvents();
  } catch (error) {
    stopImageProgress();
    const submitted = Boolean(submittedJob?.id);
    showNotice(submitted ? friendlyError(error) : `修改失败：${friendlyError(error)}`, submitted ? "warning" : "error");
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
  clearRevisionSelection({ keepNotice: true });

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
      setRevisionSelection({
        outputId: output.id,
        job: state.currentJob,
        imageUrl: output.thumbnail_url || output.url,
        title: `生成结果 ${index + 1}`,
        meta: `${shortOutputId(output.id)} · ${outputProviderResultText(output, state.currentJob)} · ${output.format.toUpperCase()}`,
        prompt: promptTextFromJob(state.currentJob),
      });
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
    if (activePanelName() === "image") renderHeroHistory(history.items || [], { source: "v1" });
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
  const sortedItems = [...items].filter((item) => !state.historyFavoritesOnly || item.favorite).sort(compareHistoryItems);
  const renderLimit = Math.min(state.historyRenderLimit, sortedItems.length);
  const renderedItems = sortedItems.slice(0, renderLimit);
  els.historyCount.textContent = renderLimit < sortedItems.length ? `${renderLimit}/${sortedItems.length}` : String(sortedItems.length);
  els.historyGallery.classList.toggle("empty-history", sortedItems.length === 0);
  renderedItems.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = `output-card history-card ${item.source === "repository" ? "" : "readonly"} ${item.favorite ? "is-favorite" : ""}`.trim();

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
    let deleteButton = null;
    if (historyItemCanDelete(item)) {
      deleteButton = document.createElement("button");
      deleteButton.className = "delete-link";
      deleteButton.type = "button";
      deleteButton.textContent = "删除";
      deleteButton.addEventListener("click", (event) => {
        event.stopPropagation();
        deleteHistoryItem(item, card);
      });
    }
    const favoriteButton = createFavoriteButton({
      favorite: item.favorite,
      label: item.favorite ? "取消星标" : "星标收藏",
      onToggle: (next) => toggleV1Favorite(item, next),
    });

    preview.addEventListener("click", () => selectHistoryItem(item, card));
    const actions = document.createElement("div");
    actions.className = "history-card-actions";
    actions.append(link);
    if (deleteButton) actions.append(deleteButton);
    footer.append(id, actions);
    meta.append(prompt, details);
    card.append(preview, favoriteButton, meta, footer);
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

function createFavoriteButton({ favorite = false, label = "星标收藏", onToggle }) {
  const button = document.createElement("button");
  button.className = `favorite-star-button ${favorite ? "active" : ""}`.trim();
  button.type = "button";
  button.setAttribute("aria-pressed", String(Boolean(favorite)));
  button.setAttribute("aria-label", label);
  button.title = label;
  button.textContent = "★";
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (button.disabled) return;
    button.disabled = true;
    const next = !button.classList.contains("active");
    try {
      await onToggle(next);
    } catch (error) {
      showGlobalToast(`星标更新失败：${friendlyError(error)}`, "error");
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

async function toggleV1Favorite(item, favorite) {
  await request(`/v1/image/history/${encodeURIComponent(item.id)}/favorite`, {
    method: "PUT",
    body: { favorite },
  });
  applyV1FavoriteState(item.id, favorite);
  renderHistory(state.historyItems);
  if (els.favoritePickerModal && !els.favoritePickerModal.hidden) renderFavoritePicker();
  if (activePanelName() === "image") renderHeroHistory(state.historyItems, { source: "v1" });
  showGlobalToast(favorite ? "已加入星标。" : "已取消星标。");
}

function applyV1FavoriteState(outputId, favorite) {
  state.historyItems = state.historyItems.map((entry) => (entry.id === outputId ? { ...entry, favorite } : entry));
}

function editableFavoriteHistoryItems() {
  return state.historyItems
    .filter((item) => item.favorite)
    .sort(compareHistoryItems);
}

function openFavoritePicker() {
  if (!els.favoritePickerModal) return;
  renderFavoritePicker();
  els.favoritePickerModal.hidden = false;
  document.body.classList.add("modal-open");
  els.closeFavoritePickerBtn?.focus();
}

function closeFavoritePicker() {
  if (!els.favoritePickerModal) return;
  els.favoritePickerModal.hidden = true;
  document.body.classList.remove("modal-open");
}

function renderFavoritePicker() {
  if (!els.favoritePickerGrid) return;
  const items = editableFavoriteHistoryItems();
  els.favoritePickerGrid.innerHTML = "";
  els.favoritePickerGrid.classList.toggle("empty-v2-list", items.length === 0);
  els.favoritePickerGrid.classList.toggle("has-empty-message", items.length === 0);
  if (els.favoritePickerCount) els.favoritePickerCount.textContent = String(items.length);
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-v2-message";
    empty.textContent = "还没有星标图片。先在历史图片上点亮星标，再回来选择。";
    els.favoritePickerGrid.appendChild(empty);
    return;
  }
  items.forEach((item, index) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "favorite-picker-card";
    card.addEventListener("click", () => chooseFavoriteForRevision(item));
    const preview = document.createElement("span");
    preview.className = "favorite-picker-preview";
    const image = document.createElement("img");
    image.src = item.thumbnail_url || item.url;
    image.alt = `星标图片 ${index + 1}`;
    image.loading = "lazy";
    image.decoding = "async";
    preview.appendChild(image);
    const meta = document.createElement("div");
    meta.className = "favorite-picker-meta";
    const title = document.createElement("strong");
    title.textContent = item.original_prompt || item.prompt || item.id;
    const detail = document.createElement("span");
    detail.textContent = favoriteRevisionDetail(item);
    const action = document.createElement("em");
    action.className = "favorite-picker-action";
    action.textContent = "选择此图继续修改";
    meta.append(title, detail, action);
    card.append(preview, meta);
    els.favoritePickerGrid.appendChild(card);
  });
}

function chooseFavoriteForRevision(item) {
  const job = {
    id: item.job_id,
    trace_id: item.trace_id || "",
    forceProviderPreference: "openai_gpt_image",
    revisionSource: item.source || "history",
  };
  setRevisionSelection({
    outputId: item.id,
    job,
    imageUrl: item.thumbnail_url || item.url,
    title: "星标图片",
    meta: `${shortOutputId(item.id)} · ${favoriteRevisionDetail(item)}`,
    prompt: promptTextFromHistoryItem(item),
  });
  closeFavoritePicker();
  showNotice("已选中星标图片，将以原图作为参考继续修改。", "success");
  els.revisionSelectedCard?.scrollIntoView({ behavior: "smooth", block: "center" });
  els.revisionInput?.focus();
}

function favoriteRevisionDetail(item) {
  const source = item.source === "repository" ? "当前任务" : "历史恢复";
  const provider = providerLabel(item.requested_provider || item.provider || "openai_gpt_image");
  return `${source} · 使用 GPT Image 2 参考原图继续修改 · ${provider}`;
}

function shortOutputId(value) {
  const text = String(value || "").trim();
  if (!text) return "星标图";
  return text.length > 14 ? `${text.slice(0, 14)}...` : text;
}

function setRevisionSelection({ outputId, job, imageUrl, title, meta, prompt }) {
  state.currentJob = job || null;
  state.selectedOutputId = outputId || null;
  state.selectedRevisionSource = {
    outputId,
    imageUrl,
    title,
    meta,
    prompt,
  };
  if (els.selectedOutputLabel) els.selectedOutputLabel.textContent = outputId ? "已选" : "未选";
  renderRevisionSelection();
  updateRevisionState();
}

function clearRevisionSelection(options = {}) {
  state.currentJob = null;
  state.selectedOutputId = null;
  state.selectedRevisionSource = null;
  if (els.selectedOutputLabel) els.selectedOutputLabel.textContent = options.label || "未选";
  renderRevisionSelection();
  updateRevisionState();
  if (!options.keepNotice) showNotice("已清除继续修改参考图。", "info");
}

function renderRevisionSelection() {
  const selected = state.selectedRevisionSource;
  if (els.revisionSelectedCard) els.revisionSelectedCard.classList.toggle("is-empty", !selected);
  const preview = els.revisionSelectedCard?.querySelector(".revision-selected-preview");
  if (preview) {
    preview.innerHTML = "";
    if (selected?.imageUrl) {
      const image = document.createElement("img");
      image.src = selected.imageUrl;
      image.alt = selected.title || "继续修改参考图";
      image.loading = "lazy";
      image.decoding = "async";
      preview.appendChild(image);
    } else {
      const empty = document.createElement("span");
      empty.textContent = "未选";
      preview.appendChild(empty);
    }
  }
  if (els.revisionSelectedTitle) {
    els.revisionSelectedTitle.textContent = selected?.title || "未选择图片";
    els.revisionSelectedTitle.title = selected?.prompt || selected?.title || "";
  }
  if (els.revisionSelectedMeta) {
    els.revisionSelectedMeta.textContent = selected?.meta || "从生成结果、历史图片或星标图片中选择一张继续修改。";
    els.revisionSelectedMeta.title = selected?.meta || "";
  }
  if (els.clearRevisionSelectionBtn) els.clearRevisionSelectionBtn.hidden = !selected;
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
  if (source === "lab") {
    return {
      id: item.id || `lab-history-${index}`,
      title: item.title || `Alchemy Lab 历史图片 ${index + 1}`,
      url: item.url,
      thumbnailUrl: item.thumbnail_url || item.url,
      format: item.format || "png",
      meta: labHistoryMetaText(item),
      promptText: item.final_prompt || item.prompt || "",
      source: "lab",
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
  if (!historyItemCanDelete(item)) {
    showNotice("这条历史记录不可删除。", "warning");
    return;
  }
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
      clearRevisionSelection({ keepNotice: true });
    }
    if (!els.imageLightbox.hidden && els.lightboxDownload.href.includes(encodeURIComponent(item.id))) {
      closeImageLightbox();
    }
    await refreshHistory({ silent: true });
    await refreshVeyraAccountPanelAfterHistoryChange();
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
  const actions = historyItemCanDelete(item)
    ? [
        {
          label: "删除",
          tone: "danger",
          run: () => deleteHistoryItem(item, card),
        },
      ]
    : [];
  openImageLightbox({
    id: item.id,
    title: (item.original_prompt || item.prompt) ? (item.original_prompt || item.prompt).slice(0, 34) : "历史图片",
    url: item.url,
    thumbnailUrl: item.thumbnail_url || item.url,
    format: item.format,
    meta: historyMetaText(item),
    promptText: promptTextFromHistoryItem(item),
    actions,
  });
  if (item.source !== "repository") {
    clearRevisionSelection({ label: "只读", keepNotice: true });
    updateRevisionState();
    showNotice("这张历史图来自本地历史清单，可查看和下载；当前会话缺少任务上下文，不能直接继续修改。", "warning");
    return;
  }
  setRevisionSelection({
    outputId: item.id,
    job: { id: item.job_id },
    imageUrl: item.thumbnail_url || item.url,
    title: "历史图片",
    meta: `${shortOutputId(item.id)} · ${historyMetaText(item)}`,
    prompt: promptTextFromHistoryItem(item),
  });
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
  const headers = {};
  const token = getVeyraToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/v1/sessions/${state.sessionId}/events`, {
    headers: Object.keys(headers).length ? headers : undefined,
    credentials: "include",
  });
  if (response.status === 401) {
    await handleVeyraUnauthorized();
    throw new Error("Veyra session is required.");
  }
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
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
    credentials: "include",
  });
  if (!response.ok) {
    const detail = await response.text();
    if (response.status === 401 && !options.skipVeyraAuth) {
      await handleVeyraUnauthorized();
    }
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
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
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

function historyRecordLabel(item) {
  if (item?.record_label) return item.record_label;
  if (item?.metadata?.record_label) return item.metadata.record_label;
  if (item?.veyra_legacy_public || item?.metadata?.veyra_legacy_public) return "旧版生图记录";
  return "";
}

function historyItemCanDelete(item) {
  return item?.can_delete === true || item?.metadata?.can_delete === true;
}

function historyDetailText(...parts) {
  return parts.filter(Boolean).join(" · ");
}

function historyMetaText(item, model = item.model || item.source) {
  const providerText = historyProviderResultText(item);
  const parts = [historyRecordLabel(item), providerText || model];
  const intensity = item.work_intensity_label || intensityMap[item.work_intensity]?.label;
  if (intensity) parts.push(`强度：${intensity}`);
  parts.push(formatDate(item.created_at || item.updated_at));
  return parts.filter(Boolean).join(" · ");
}
