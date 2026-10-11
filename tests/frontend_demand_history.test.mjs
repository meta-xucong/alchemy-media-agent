import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const shells = [
  { name: "desktop", path: "../src_skeleton/app/static/app.js" },
  { name: "mobile", path: "../src_skeleton/app/mobile_static/mobile.js" },
].map((shell) => ({
  ...shell,
  source: readFileSync(new URL(shell.path, import.meta.url), "utf8"),
}));

// Execute the shipped functions rather than reimplementing their control flow.
// Parser-check each closing-line candidate so multiline strings and nested
// declarations cannot silently truncate the function under test.
function extractFunction(source, name) {
  const start = new RegExp(`^([ \\t]*)(?:async )?function ${name}\\(`, "m").exec(source);
  assert.ok(start, `source function ${name} is present`);
  const tail = source.slice(start.index);
  const closes = new RegExp(`^${start[1]}\\};?\\s*$`, "gm");
  for (const close of tail.matchAll(closes)) {
    const candidate = tail.slice(0, close.index + close[0].trimEnd().length);
    try {
      new vm.Script(candidate);
      return candidate;
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
  }
  assert.fail(`complete source function ${name} is extractable`);
}

function extractBootstrap(source) {
  const start = source.indexOf('document.addEventListener("DOMContentLoaded", async () => {');
  assert.ok(start >= 0, "the real DOMContentLoaded entry point is present");
  const end = source.indexOf("\n});", start);
  assert.ok(end > start, "the real DOMContentLoaded entry point is complete");
  return source.slice(start, end + 4);
}

function node(dataset = {}, hidden = false) {
  const classes = new Set();
  return {
    dataset, hidden, disabled: false, textContent: "", children: [], events: new Map(),
    get innerHTML() { return this.html || ""; },
    set innerHTML(value) {
      this.html = value;
      this.children.forEach((child) => { child.parentElement = null; });
      this.children = [];
    },
    parentElement: null,
    style: { setProperty() {} },
    classList: {
      add: (...values) => values.forEach((value) => classes.add(value)),
      remove: (...values) => values.forEach((value) => classes.delete(value)),
      contains: (value) => classes.has(value),
      toggle(value, force = !classes.has(value)) {
        if (force) classes.add(value);
        else classes.delete(value);
        return force;
      },
    },
    setAttribute() {}, getAttribute() { return "tab"; }, removeAttribute() {}, remove() {},
    addEventListener(name, listener) { this.events.set(name, listener); }, scrollIntoView() {}, focus() {},
    appendChild(child) { child.parentElement = this; this.children.push(child); return child; },
    append(...children) { children.forEach((child) => this.appendChild(child)); },
    querySelector() { return null; },
    querySelectorAll(selector) {
      const descendants = this.children.flatMap((child) => [child, ...child.querySelectorAll("*")]);
      return selector === "*" ? descendants : descendants.filter((child) => child.tagName === selector.toUpperCase());
    },
    getBoundingClientRect() { return this.rect || { top: 10, bottom: 100, left: 0, right: 100, width: 100, height: 90 }; },
    closest(selector) {
      for (let current = this; current; current = current.parentElement) {
        if (selector === "[hidden]" && current.hidden) return current;
        if (selector.includes("data-account-view") && current.dataset.accountView) return current;
        if (selector.includes("data-panel") && current.dataset.panel) return current;
        if (selector === "section" && current.tagName === "SECTION") return current;
      }
      return null;
    },
  };
}

const historyFunctions = [
  "sharedProviderSettingsDemanded", "ensureSharedProviderSettings",
  "historyDemandState", "historyDemandVisible", "historyFavoritesDemanded",
  "historyPickerVisible", "renderHistoryDemand",
  "historyHeroVisible", "ensureHistoryHero",
  "clearHistoryMedia", "historyWindowLabel", "renderHistoryWindowNavigation",
  "loadPreviousHistoryWindow", "changeHistoryBrowseMode",
  "ensureHistoryDemand", "invalidateHistoryDemand", "readHistoryDemand",
  "clearHistoryDemandCaches", "refreshHistory", "loadV2History",
  "hasMoreV1History", "hasMoreV2History", "loadMoreV1History", "loadMoreV2History",
  "loadRemainingV1HistoryForFavorites", "loadRemainingV2HistoryForFavorites",
  "v2HistoryEndpoint", "v2HistoryPath", "loadV2RequestWithTimeout",
  "loadV2HistoryWithTimeout", "loadV2HistoryResponse", "v2HistoryLoadErrorMessage",
];

function installHistoryRenderers(h, module) {
  h.install(["historyMediaDemand"]);
  const liveBlobs = new Set();
  let imageId = 0;
  h.context.bindImageWithFallback = (image) => {
    const url = `blob:test-${++imageId}`;
    image.dataset.authenticatedObjectUrl = url;
    image.dataset.mediaLoadToken = url;
    liveBlobs.add(url);
  };
  h.context.releaseImageObjectUrl = (image) => {
    liveBlobs.delete(image.dataset.authenticatedObjectUrl);
    delete image.dataset.authenticatedObjectUrl;
  };
  for (const name of ["bindDownloadLink", "createFavoriteButton"]) h.context[name] = () => node();
  h.context.historyItemCanDelete = () => false;
  for (const name of ["historyMetaText", "v2HistoryCardPrompt", "v2HistoryProviderResultText", "historyDetailText", "historyRecordLabel", "formatDate", "favoriteRevisionDetail"]) h.context[name] = () => "test";
  h.context.v2HistoryImageCandidates = () => [];
  h.context.uniqueNonEmpty = (values) => [...new Set(values.filter(Boolean))];
  h.context.v1ExplicitDownloadUrl = h.context.v2ExplicitDownloadUrl = () => "/test.png";
  h.context.v2HistoryFormat = () => "png";
  h.install(module === "v1"
    ? ["renderHistory", "renderFavoritePicker", "editableFavoriteHistoryItems"]
    : ["renderV2History", "renderV2FavoriteReferencePicker", "v2FavoriteReferenceItems"]);
  return liveBlobs;
}

function createHarness(shell, { active = "image", ticket = false, respond } = {}) {
  const calls = [];
  const renders = [];
  const notices = [];
  const idleTasks = [];
  const listeners = new Map();
  const body = node({ activeModule: active, mobileActiveSurface: "" });
  const panels = ["image", "v2", "v3", "lab", "account"].map((name) => {
    const panel = node({ panel: name }, name !== active);
    panel.classList.toggle("active", name === active);
    return panel;
  });
  const overview = node({ accountView: "overview" });
  const access = node({ accountView: "access" }, true);
  const elements = {
    tabs: ["image", "v2", "account"].map((tab) => node({ tab })),
    panels,
    favoritePickerModal: node({}, true),
    v2FavoriteReferenceModal: node({}, true),
    imageLightbox: node({}, true),
    sampleGuideModal: node({}, true),
    mobileViewLayer: node({}, true), mobileSheetLayer: node({}, true),
  };
  const els = new Proxy(elements, {
    get(target, key) { return target[key] ??= node(); },
  });
  const surfaces = new Map(["account", "v1-history", "v2-history"].map((id) => [id, node({ mobileView: id }, true)]));
  const document = {
    body, title: "test", documentElement: { clientHeight: 800 },
    addEventListener(name, callback) { listeners.set(name, callback); },
    removeEventListener(name, callback) { if (listeners.get(name) === callback) listeners.delete(name); },
    createElement: (tag) => Object.assign(node(), { tagName: tag.toUpperCase() }),
    querySelector(selector) {
      if (selector === "[data-panel].active") return panels.find((panel) => panel.classList.contains("active"));
      if (/data-account-view.*overview/.test(selector)) return overview;
      if (/data-account-view.*access/.test(selector)) return access;
      if (/data-panel.*account/.test(selector)) return panels.find((panel) => panel.dataset.panel === "account");
      const surface = /data-mobile-view=["']([^"']+)/.exec(selector);
      if (surface) return surfaces.get(surface[1]) || null;
      if (selector.startsWith("#")) return els[selector.slice(1)];
      return null;
    },
    querySelectorAll(selector) {
      if (selector === ".mobile-view, .mobile-sheet") return [...surfaces.values()];
      if (selector === "[data-account-view]") return [overview, access];
      return [];
    },
  };
  const location = new URL(`https://example.test/?module=${active}${ticket ? "&ticket=opaque-ticket" : ""}`);
  let token = ticket ? "" : "session-token";
  const storage = new Map();
  storage.set("alchemy_veyra_access_token", token);
  const request = async (module, path, options = {}) => {
    calls.push({ module, path, options });
    if (respond) return await respond({ module, path, options, calls });
    if (path.includes("/history")) return { items: [], total: 0 };
    if (path === "/veyra/login") return { access_token: "session-token" };
    if (path === "/veyra/me") return { user: { user_id: "owner", balance: 10 } };
    return {};
  };
  const context = vm.createContext({
    console: { warn() {}, error() {} }, URL, URLSearchParams, AbortController,
    setTimeout, clearTimeout,
    document, els, activeTabName: active, accountReturnTabName: "image", mobileHistoryToken: 0,
    window: {
      location, innerHeight: 800, setTimeout, clearTimeout, addEventListener() {},
      requestAnimationFrame: (callback) => callback(),
      sessionStorage: { getItem: (key) => storage.get(key), removeItem: (key) => storage.delete(key) },
      history: { state: {}, replaceState() {}, pushState() {}, back() {} },
    },
    localStorage: {
      setItem: (key, value) => storage.set(key, value),
      getItem: (key) => storage.get(key) || null,
      removeItem: (key) => storage.delete(key),
    },
    state: { historyItems: [], historyTotal: 0, historyRenderLimit: 24, historyFavoritesOnly: false, historyLoadingMore: false },
    v2State: { history: [], historyTotal: 0, historyRenderLimit: 24, historyFavoritesOnly: false, historyLoadingMore: false, templateDetailCache: {}, loaded: false },
    veyraState: { account: { user: { user_id: "owner", balance: 10 } }, history: [], usage: [], usedTemplates: [] },
    labState: { history: [] }, v3State: {},
    pendingModuleRouteStorageKey: "pending-route", veyraAccountStorageKey: "account",
    veyraTokenStorageKey: "alchemy_veyra_access_token",
    request: (path, options) => request("v1", path, options),
    v2Request: (path, options) => request("v2", path, options),
    activePanelName: () => document.querySelector("[data-panel].active")?.dataset.panel || "image",
    getVeyraToken: () => token,
    setVeyraToken: (value) => { token = value; storage.set("alchemy_veyra_access_token", value); },
    hasVeyraClientSession: () => Boolean(token),
    isRenderableV2HistoryImage: (item) => item.renderable !== false,
    compareHistoryItems: (left, right) => Number(right.created_at || 0) - Number(left.created_at || 0),
    historyTime: (item) => Number(item.created_at || 0),
    friendlyError: (error) => error?.message || String(error),
    showNotice: (...args) => notices.push(args), updateV2Notice: (...args) => notices.push(args),
    renderHistory: (items) => renders.push({ kind: "v1", ids: items.map((item) => item.id) }),
    renderV2History: (items) => renders.push({ kind: "v2", ids: items.map((item) => item.output_id) }),
    renderHeroHistory: (items, options) => renders.push({ kind: "hero", source: options?.source, count: items.length }),
    renderFavoritePicker: () => renders.push({ kind: "v1-picker" }),
    renderV2FavoriteReferencePicker: () => renders.push({ kind: "v2-picker" }),
  });
  // Use the actual numeric constants: changing network limits in production
  // must change the requests observed by these tests.
  for (const declaration of shell.source.matchAll(/^const (\w+) = (\d+);$/gm)) {
    context[declaration[1]] = Number(declaration[2]);
  }
  for (const name of [
    "showGlobalToast", "setAppPageLoading", "setMobilePageLoading", "restartHeroCarousels", "scheduleMobileSummaryUpdate",
    "updateMobileSummaries", "updateMobileAccountSummary", "updateAdminSettingsEntry",
    "hydratePortalHomeLink", "hydrateCachedVeyraAccount", "bindControls", "setupH5AdvancedPanels",
    "setupMobileV3Adapter", "updateHeroCopy", "updateH5QuickGuide", "toggleV2Loading",
    "renderV2ProviderInheritance", "renderV2AssetPanel", "renderV2Health", "renderV2Providers",
    "renderV2CaseFacets", "renderV2Templates", "renderV2ModelSettings", "renderV2Brain",
    "applyV2TemplateIndex", "applyV2TemplatePage", "scheduleV2TemplatePrefetch",
    "renderLabModuleState", "renderV3HeroHistory", "renderVeyraSignedOut",
    "clearV3LocalCaches", "clearMobileV3Caches", "setAssetMode", "setAdvancedAssetRoles",
    "resetAssetPreview", "renderAssetPanel", "clearRevisionSelection", "setStatus", "toggleBusy", "renderEvents",
  ]) context[name] = () => {};
  context.scheduleIdleTask = (callback) => idleTasks.push(callback);
  context.enforceVeyraUiAuth = async () => false;
  context.hasValidVeyraSession = async () => true;
  context.setVeyraAccount = (account) => { context.veyraState.account = account; };
  context.v2TemplatePageEndpoint = () => "/templates/page";
  context.createSession = () => context.request("/v1/sessions", { method: "POST" });
  context.loadProviders = () => context.request("/v1/providers");
  context.v3CacheOwnerId = context.mobileV3CacheOwnerId = (account = context.veyraState.account) => account?.user?.user_id || "";

  function install(names, { optional = false, source = shell.source } = {}) {
    for (const name of names) {
      if (optional && !new RegExp(`^\\s*(?:async )?function ${name}\\(`, "m").test(source)) continue;
      vm.runInContext(extractFunction(source, name), context, { filename: `${shell.name}:${name}` });
    }
  }
  function activate(module, surface = "") {
    context.activeTabName = module;
    body.dataset.activeModule = module;
    body.dataset.mobileActiveSurface = surface;
    for (const panel of panels) {
      panel.hidden = panel.dataset.panel !== module;
      panel.classList.toggle("active", !panel.hidden);
    }
  }
  async function settle() {
    // Drain callbacks and promise chains, including fire-and-forget module
    // bootstraps. No wall-clock delay or real network is involved.
    for (let index = 0; index < 20; index += 1) {
      for (const callback of idleTasks.splice(0)) await callback();
      await new Promise((resolve) => setImmediate(resolve));
    }
  }
  return { context, calls, renders, notices, els, overview, access, surfaces, listeners, install, activate, settle };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((accept, decline) => { resolve = accept; reject = decline; });
  return { promise, resolve, reject };
}

function items(module, start, count, overrides = {}) {
  return Array.from({ length: count }, (_, index) => ({
    [module === "v1" ? "id" : "output_id"]: `${module}-${start + index}`,
    created_at: start + index, format: "png", favorite: false, ...overrides,
  }));
}

function historyCalls(harness, module) {
  return harness.calls.filter((call) => call.module === module && call.path.includes("/history")
    && (!call.options.method || call.options.method === "GET"));
}

function pageRequests(harness, module) {
  return historyCalls(harness, module).map(({ path }) => {
    const url = new URL(path, "https://example.test");
    return { path: url.pathname, limit: Number(url.searchParams.get("limit")), offset: Number(url.searchParams.get("offset")) };
  });
}

function historyHarness(shell, module, options = {}) {
  const harness = createHarness(shell, { active: module === "v1" ? "image" : "v2", ...options });
  harness.install(historyFunctions);
  // Keep legacy fallback code available if it is accidentally reintroduced:
  // the endpoint-count assertion must catch its execution, not a missing stub.
  harness.install(["loadV2ImageHistoryFallback", "v2HistoryItemCount"], { optional: true });
  harness.model = module === "v1" ? harness.context.state : harness.context.v2State;
  harness.key = module === "v1" ? "historyItems" : "history";
  harness.refresh = (options = {}) => harness.context[module === "v1" ? "refreshHistory" : "loadV2History"]({ silent: true, ...options });
  harness.more = () => harness.context[module === "v1" ? "loadMoreV1History" : "loadMoreV2History"]();
  harness.favorites = () => harness.context[module === "v1" ? "loadRemainingV1HistoryForFavorites" : "loadRemainingV2HistoryForFavorites"]();
  return harness;
}

const accountFunctions = [
  "accountOverviewDemanded", "accountSectionVisible", "observeAccountOverviewSections",
  "loadVeyraTemplateHistorySection", "loadVeyraAccountPanel", "refreshVeyraAccountPanelAfterHistoryChange",
  "setVeyraAccountLoading", "setVeyraAccountLoadNotice", "refreshVeyraAccount",
  "mergeAccountHistory", "mergeVeyraUsage", "buildVeyraTemplateHistory", "v2HistoryTemplateCaseId",
  "loadV2TemplateDetailForHistory", "findV2TemplateInCache",
  "renderVeyraAccountSummary", "veyraAccountUser", "isVeyraAdmin", "formatVeyraMoney", "veyraUsageTotal",
];

function accountHarness(shell, options = {}) {
  const h = createHarness(shell, { active: shell.name === "desktop" ? "account" : "v2", ...options });
  h.install(historyFunctions);
  h.install(accountFunctions);
  if (shell.name === "mobile") h.activate("v2", "account");
  h.context.v2HistoryCardPrompt = () => "sample prompt";
  h.context.renderVeyraAccountHistory = (rows) => h.renders.push({ kind: "account-history", count: rows.length });
  h.context.renderVeyraTemplateHistory = (rows) => h.renders.push({ kind: "account-cases", count: rows.length });
  h.context.renderVeyraUsageList = (rows) => h.renders.push({ kind: "account-usage", count: rows.length });
  h.context.IntersectionObserver = class {
    constructor(callback) { h.intersect = callback; }
    observe() {}
    disconnect() {}
  };
  for (const key of ["veyraAccountHistoryGrid", "veyraTemplateHistoryList", "veyraUsageList"]) {
    const section = node();
    section.tagName = "SECTION";
    section.rect = { top: 1200, bottom: 1500 };
    section.parentElement = h.overview;
    h.els[key].parentElement = section;
  }
  h.showSection = (key) => { h.els[key].parentElement.rect = { top: 50, bottom: 350 }; };
  return h;
}

function installBootstrap(h, shell) {
  h.install([
    "ensureV1Module", "normalizeModuleRouteToken", "initialModuleRoute", "panelExists",
    "restoreInitialModuleRoute", "switchTab", "scheduleInitialBackgroundLoads", "initV2",
    "loadV2OptionalResource", "loadV2TemplateBootstrap", "handleVeyraTicketFromUrl",
    "cleanVeyraTicketFromUrl", "syncVeyraSessionCookie", "refreshVeyraAccount",
  ]);
  vm.runInContext(extractBootstrap(shell.source), h.context, { filename: `${shell.name}:DOMContentLoaded` });
}

function installMobileHistory(h) {
  const navigation = [];
  h.install(["openMobileSurface", "closeMobileSurface"]);
  h.context.window.history.pushState = (state, title, url) => {
    navigation.push({ type: "push", state, title, url });
    h.context.window.history.state = state;
  };
  h.context.window.history.back = () => navigation.push({ type: "back" });
  return navigation;
}

function labHarness(shell, { defaultProvider = "doubao_image", providerGate = null } = {}) {
  const h = historyHarness(shell, "v1", {
    respond: async ({ path, options }) => {
      if (["/v1/providers", "/v1/runtime/provider-settings"].includes(path)) {
        if (providerGate) await providerGate.promise;
        if (path === "/v1/providers") return { image: [
          { provider: "openai_gpt_image", configured: false },
          { provider: "doubao_image", configured: true },
          { provider: "gemini_image", configured: true },
        ] };
        return { default_image_provider: defaultProvider, default_llm_provider: "openai", image_work_intensity: "balanced" };
      }
      if (path === "/api/lab/rare-style-explorer/sessions" && options.method === "POST") {
        return { session: { id: "lab-session" }, board: { status: "queued" } };
      }
      if (path === "/v1/sessions") return { id: "v1-session" };
      if (path.includes("/history")) return { items: [], total: 0 };
      return { user: { user_id: "owner", balance: 10 } };
    },
  });
  installBootstrap(h, shell);
  h.install([
    "loadProviders", "safeImageProviderPreference", "isGeminiImageTemporarilyDisabled",
    "normalizeThinkingProvider", "isImageProviderUsable", "firstUsableImageProvider",
    "openLabHome", "openLabModule", "loadLabHistory", "labProviderPreference", "runLabExploration",
    "isLabTerminalStatus", "getVeyraToken", "setVeyraToken",
  ]);
  h.context.window.location.search = "?module=lab";
  h.context.state.selectedProvider = "openai_gpt_image";
  Object.assign(h.context.labState, {
    loaded: true, loading: false, selectedStyleIds: [], limits: { maxTotalImages: 12 },
    referenceAssets: [], imagesPerStyle: 1, targetCount: 1, seed: "", aspectRatio: "square", mode: "minimal",
  });
  h.els.labIdeaInput.value = "A geometric still life";
  h.context.geminiImageGenerationTemporarilyDisabled = true;
  h.context.geminiImageUnavailableShortLabel = "unavailable";
  h.context.geminiImageUnavailableReason = "unavailable";
  h.context.intensityMap = { balanced: { label: "balanced" } };
  h.context.providerLabel = h.context.thinkingProviderLabel = (value) => value;
  h.context.updateLabNotice = (...args) => h.notices.push(args);
  h.context.labReferencePayload = () => [];
  for (const name of [
    "setActiveIntensity", "setImageProvider", "setThinkingProvider", "renderProviderLists",
    "setImageProviderAvailability", "setLabNavOpen", "renderLabHistory", "renderLabHistoryLoading",
    "renderLabHistoryError", "setLabBusy", "stopLabPolling", "updateLabSessionState",
    "renderLabIntentSummary", "renderLabBoard", "updateLabSessionFromPayload", "scheduleLabPolling",
  ]) h.context[name] = () => {};
  return h;
}

function assertLabIsolation(h) {
  assert.equal(h.calls.some(({ path }) => path === "/v1/sessions" || path.startsWith("/v1/image/history")), false);
  assert.equal(h.calls.some(({ module, path }) => module === "v2" && path.includes("/history")), false);
}

for (const shell of shells) {
  for (const module of ["v1", "v2"]) {
    const prefix = `${shell.name} ${module}`;
    const endpoint = module === "v1" ? "/v1/image/history" : "/veyra/history";
    const active = module === "v1" ? "image" : "v2";

    test(`${prefix}: first and next gestures each request exactly 24 rows`, async () => {
      const h = historyHarness(shell, module, {
        respond: ({ path }) => {
          const query = new URL(path, "https://example.test").searchParams;
          return { items: items(module, Number(query.get("offset")), 24), total: 96 };
        },
      });
      await h.refresh();
      assert.deepEqual(pageRequests(h, module), [{ path: endpoint, limit: 24, offset: 0 }]);
      assert.equal(h.model[h.key].length, 24);
      assert.equal(h.model.historyRenderLimit, 24);
      await h.more();
      assert.deepEqual(pageRequests(h, module), [
        { path: endpoint, limit: 24, offset: 0 },
        { path: endpoint, limit: 24, offset: 24 },
      ]);
      assert.equal(h.model[h.key].length, 48);
      assert.equal(h.model.historyRenderLimit, 48);
    });

    test(`${prefix}: hundreds of history pages retain one revisitable 72-row window and one Hero sample`, async () => {
      const h = historyHarness(shell, module, {
        respond: ({ path }) => {
          const offset = Number(new URL(path, "https://example.test").searchParams.get("offset"));
          return { items: items(module, offset, 24), total: 50000 };
        },
      });
      await h.refresh();
      for (let index = 0; index < 160; index += 1) {
        await h.more();
        assert.ok(h.model[h.key].length <= 72);
        assert.ok(h.model.historyRenderLimit <= 72);
        assert.ok(h.model.historyHeroItems.length <= 24);
        assert.deepEqual(Object.keys(h.model.historyDemand.positions).sort(), ["all", "favorites"]);
      }
      const start = h.model.historyDemand.start;
      assert.ok(start > 3000);
      assert.equal(h.model[h.key].some((item) => item.id === "v1-0" || item.output_id === "v2-0"), false);
      assert.equal(h.model.historyHeroItems[0][module === "v1" ? "id" : "output_id"], `${module}-0`);
      await h.context.loadPreviousHistoryWindow(module);
      assert.equal(h.model.historyDemand.start, start - 72);
      assert.equal(h.model[h.key][0][module === "v1" ? "id" : "output_id"], `${module}-${start - 72}`);
      assert.equal(pageRequests(h, module).at(-1).offset, start - 72);
      assert.ok(h.context.historyWindowLabel(module, 24).includes(`${start - 71}–${start - 48}`));
    });

    test(`${prefix}: actual history and picker DOM and authenticated Blob URLs stay bounded across windows`, async () => {
      const h = historyHarness(shell, module, {
        respond: ({ path }) => {
          const offset = Number(new URL(path, "https://example.test").searchParams.get("offset"));
          return { items: items(module, offset, 24, { favorite: true }), total: 50000 };
        },
      });
      const blobs = installHistoryRenderers(h, module);
      const grid = h.els[module === "v1" ? "historyGallery" : "v2HistoryGrid"];
      const picker = h.els[module === "v1" ? "favoritePickerGrid" : "v2FavoriteReferenceGrid"];
      await h.refresh();
      assert.equal(h.notices.length, 0, JSON.stringify(h.notices));
      const oldImage = grid.querySelectorAll("img")[0];
      for (let index = 0; index < 12; index += 1) await h.more();
      assert.equal(oldImage.dataset.mediaLoadToken, "");
      assert.equal(oldImage.dataset.authenticatedObjectUrl, undefined);
      assert.ok(grid.querySelectorAll("img").length <= 72);
      assert.ok(blobs.size <= 72);
      h.els[module === "v1" ? "favoritePickerModal" : "v2FavoriteReferenceModal"].hidden = false;
      await h.favorites();
      for (let index = 0; index < 13; index += 1) {
        await h.more();
        assert.ok(h.model[h.key].length <= 72);
        assert.ok(grid.querySelectorAll("img").length <= 72);
        assert.ok(picker.querySelectorAll("img").length <= 72);
        assert.ok(blobs.size <= 144);
      }
      assert.ok(picker.children.some((child) => child.children?.some((button) => button.textContent === "上一组历史")));
      h.install([module === "v1" ? "closeFavoritePicker" : "closeV2FavoriteReferencePicker"]);
      h.context[module === "v1" ? "closeFavoritePicker" : "closeV2FavoriteReferencePicker"]();
      await h.settle();
      assert.equal(picker.querySelectorAll("img").length, 0);
      assert.ok(blobs.size <= 72);
      assert.equal(h.model.historyDemand.mode, "all");
      // The all-history position survives only as a scalar, with a fresh read.
      assert.equal(h.model.historyDemand.start, 288);
    });

    test(`${prefix}: mode changes during a pending page discard that page and restore the previous ordinary window`, async () => {
      let pending = null;
      const h = historyHarness(shell, module, {
        respond: ({ path }) => {
          if (pending) return pending.promise;
          const params = new URL(path, "https://example.test").searchParams;
          return { items: items(module, Number(params.get("offset")), 24, { favorite: params.get("favorite") === "true" }), total: 240 };
        },
      });
      await h.refresh();
      for (let index = 0; index < 3; index += 1) await h.more();
      pending = deferred();
      h.model.historyFavoritesOnly = true;
      if (shell.name === "mobile") h.activate(active, `${module}-history`);
      const favoriteRead = h.context.changeHistoryBrowseMode(module);
      assert.equal(historyCalls(h, module).at(-1).path.includes("favorite=true"), true);
      h.model.historyFavoritesOnly = false;
      const ordinaryRead = h.context.changeHistoryBrowseMode(module);
      pending.resolve({ items: items(module, 999, 24, { favorite: true }), total: 240 });
      pending = null;
      await Promise.all([favoriteRead, ordinaryRead]);
      assert.equal(h.model.historyDemand.mode, "all");
      assert.equal(h.model.historyDemand.start, 72);
      assert.equal(h.model[h.key].some((item) => item.id === "v1-999" || item.output_id === "v2-999"), false);
    });

    test(`${prefix}: a favorite mutation invalidates filtered totals/windows and cannot cross an account boundary`, async () => {
      let pending = null;
      const h = historyHarness(shell, module, {
        respond: ({ path, options }) => {
          if (options.method === "PUT") return pending ? pending.promise : {};
          const offset = Number(new URL(path, "https://example.test").searchParams.get("offset"));
          return { items: items(module, offset, 24, { favorite: true }), total: 240 };
        },
      });
      h.install([`toggle${module.toUpperCase()}Favorite`]);
      h.install(["applyV1FavoriteState"], { optional: true });
      await h.refresh();
      await h.context[`toggle${module.toUpperCase()}Favorite`](h.model[h.key][0], true);
      assert.deepEqual(pageRequests(h, module).map((page) => page.offset), [0, 0]);
      assert.equal(h.model.historyDemand.dirty, false);
      pending = deferred();
      const mutation = h.context[`toggle${module.toUpperCase()}Favorite`](h.model[h.key][0], false);
      h.context.clearHistoryDemandCaches();
      h.context.setVeyraToken("next-owner");
      pending.resolve({});
      await mutation;
      assert.equal(h.model[h.key].length, 0);
      assert.equal(h.model.historyHeroItems.length, 0);
      assert.equal(historyCalls(h, module).length, 2);
    });

    test(`${prefix}: first favorites demand loads an independent ordinary Hero only while visible`, async () => {
      const h = historyHarness(shell, module, {
        respond: ({ path }) => {
          const params = new URL(path, "https://example.test").searchParams;
          return { items: items(module, params.get("favorite") === "true" ? 1000 : 0, 24, { favorite: true, url: "/image.png" }), total: 240 };
        },
      });
      installHistoryRenderers(h, module);
      h.context.clearHeroCarouselTimer = () => {};
      h.context.normalizeHeroHistoryItem = (item) => ({ id: item.id || item.output_id, url: item.url });
      h.install(["renderHeroHistory"]);
      h.model.historyFavoritesOnly = true;
      if (shell.name === "mobile") h.activate(active, `${module}-history`);
      await h.favorites();
      assert.equal(h.model[h.key][0][module === "v1" ? "id" : "output_id"], `${module}-1000`);
      assert.equal(historyCalls(h, module).length, shell.name === "desktop" ? 2 : 1);
      if (shell.name === "mobile") {
        assert.equal(h.model.historyHeroItems, undefined);
        h.activate(active);
        await h.context.ensureHistoryDemand(module);
      }
      assert.equal(h.model.historyHeroItems[0][module === "v1" ? "id" : "output_id"], `${module}-0`);
      assert.ok(h.context.state.heroHistoryItems.every((item) => Number(item.id.split("-").at(-1)) < 24));
      assert.equal(h.els.heroHistoryCarousel.querySelectorAll("img").length, 8);
      assert.ok(h.model.historyHeroItems.length <= 24);
    });

    test(`${prefix}: favorite-only mutations preserve the latest ordinary Hero without an extra ordinary read`, async () => {
      const h = historyHarness(shell, module, {
        respond: ({ path, options }) => {
          if (options.method === "PUT") return {};
          const params = new URL(path, "https://example.test").searchParams;
          return { items: items(module, params.get("favorite") === "true" ? 1000 : 0, 24, { favorite: true }), total: 240 };
        },
      });
      h.install([`toggle${module.toUpperCase()}Favorite`]);
      h.install(["applyV1FavoriteState"], { optional: true });
      await h.refresh();
      const heroItem = h.model.historyHeroItems[0];
      h.model.historyFavoritesOnly = true;
      if (shell.name === "mobile") h.activate(active, `${module}-history`);
      await h.favorites();
      const ordinaryReads = () => historyCalls(h, module).filter(({ path }) => !path.includes("favorite=true")).length;
      assert.equal(ordinaryReads(), 1);
      await h.context[`toggle${module.toUpperCase()}Favorite`](heroItem, false);
      assert.equal(ordinaryReads(), 1);
      assert.equal(h.model.historyHeroItems.length, 24);
      assert.equal(h.model.historyHeroItems[0][module === "v1" ? "id" : "output_id"], `${module}-0`);
      assert.equal(h.model.historyHeroItems[0].favorite, false);
      assert.equal(h.model.historyHeroDirty, false);
    });

    test(`${prefix}: a pending ordinary Hero read is single-flight and cannot restore a prior account`, async () => {
      const page = deferred();
      const h = historyHarness(shell, module, { respond: () => page.promise });
      const first = h.context.ensureHistoryHero(module);
      const second = h.context.ensureHistoryHero(module);
      assert.equal(historyCalls(h, module).length, 1);
      h.context.clearHistoryDemandCaches();
      h.context.setVeyraToken("next-owner");
      h.activate("lab");
      page.resolve({ items: items(module, 0, 24), total: 24 });
      await Promise.all([first, second]);
      assert.equal(historyCalls(h, module).length, 1);
      assert.equal(h.model.historyHeroItems.length, 0);
      assert.equal(h.model.historyHeroReady, false);
    });

    test(`${prefix}: valid empty history and request errors never call a second endpoint`, async () => {
      for (const error of [false, true]) {
        const h = historyHarness(shell, module, {
          respond: () => {
            if (error) throw new Error("history unavailable");
            return { items: [], total: 0 };
          },
        });
        await h.refresh();
        assert.deepEqual(pageRequests(h, module), [{ path: endpoint, limit: 24, offset: 0 }]);
        assert.equal(h.model[h.key].length, 0);
        assert.equal(h.model.historyLoadingMore, false);
        assert.equal(h.model.historyDemand.promise, null);
        assert.equal(h.model.historyDemand.loaded, !error);
      }
    });

    test(`${prefix}: a failed favorites entry preserves the error without automatically retrying completion`, async () => {
      const h = historyHarness(shell, module, {
        respond: () => { throw new Error("first history read unavailable"); },
      });
      h.model.historyFavoritesOnly = true;
      if (shell.name === "mobile") h.activate(active, `${module}-history`);
      await h.context.ensureHistoryDemand(module);
      assert.equal(historyCalls(h, module).length, 1);
      assert.equal(h.model.historyDemand.loaded, false);
      assert.equal(h.model.historyDemand.promise, null);
      assert.ok(h.notices.some(([message, type]) => type === "error" && message.includes("first history read unavailable")));
      assert.equal(h.notices.some(([, type]) => type === "success"), false);
    });

    test(`${prefix}: rapid duplicate entries and next-page gestures share one request`, async () => {
      let page = deferred();
      const h = historyHarness(shell, module, { respond: () => page.promise });
      const first = h.context.ensureHistoryDemand(module);
      const duplicate = h.context.ensureHistoryDemand(module);
      assert.equal(historyCalls(h, module).length, 1);
      page.resolve({ items: items(module, 0, 24), total: 96 });
      await Promise.all([first, duplicate]);
      page = deferred();
      const next = h.more();
      const nextDuplicate = h.more();
      assert.equal(historyCalls(h, module).length, 2);
      page.resolve({ items: items(module, 24, 24), total: 96 });
      await Promise.all([next, nextDuplicate]);
      assert.equal(h.model[h.key].length, 48);
    });

    test(`${prefix}: a response after navigation cannot render hidden history or hero media`, async () => {
      const page = deferred();
      const h = historyHarness(shell, module, { respond: () => page.promise });
      const loading = h.refresh();
      h.activate("lab");
      h.renders.length = 0;
      page.resolve({ items: items(module, 0, 24), total: 240 });
      await loading;
      assert.equal(historyCalls(h, module).length, 1);
      assert.deepEqual(h.renders, []);
      // Returning can use a valid cache without another network request.
      h.activate(active);
      await h.context.ensureHistoryDemand(module);
      assert.equal(historyCalls(h, module).length, 1);
      assert.ok(h.renders.some((render) => render.kind === module));
    });

    test(`${prefix}: a hidden mutation marks dirty and refreshes only on next demand`, async () => {
      const h = historyHarness(shell, module, {
        respond: () => ({ items: items(module, 0, 24), total: 24 }),
      });
      await h.refresh();
      h.activate("lab");
      h.renders.length = 0;
      await h.refresh({ invalidate: true });
      assert.equal(h.model.historyDemand.dirty, true);
      assert.equal(historyCalls(h, module).length, 1);
      assert.deepEqual(h.renders, []);
      h.activate(active);
      await h.context.ensureHistoryDemand(module);
      assert.deepEqual(pageRequests(h, module).map((page) => page.offset), [0, 0]);
      assert.equal(h.model.historyDemand.dirty, false);
    });

    test(`${prefix}: an invalidated in-flight response cannot overwrite newer owner state`, async () => {
      const oldPage = deferred();
      const h = historyHarness(shell, module, {
        respond: ({ calls }) => calls.length === 1 ? oldPage.promise : { items: items(module, 100, 24), total: 24 },
      });
      const old = h.refresh();
      h.context.clearHistoryDemandCaches();
      const fresh = h.context.ensureHistoryDemand(module);
      oldPage.resolve({ items: items(module, 0, 24), total: 24 });
      await Promise.all([old, fresh]);
      assert.equal(historyCalls(h, module).length, 2);
      assert.equal(h.model[h.key][0][module === "v1" ? "id" : "output_id"], `${module}-100`);
      assert.ok(h.renders.filter((render) => render.kind === module).every((render) => !render.ids.includes(`${module}-0`)));
    });

    test(`${prefix}: a cross-tab token change rejects late history before the storage event increments any epoch`, async () => {
      const page = deferred();
      const h = historyHarness(shell, module, { respond: () => page.promise });
      h.install(["getVeyraToken"]);
      const epoch = h.context.state.historyAuthEpoch || 0;
      const loading = h.refresh();
      h.context.localStorage.setItem(h.context.veyraTokenStorageKey, "other-tab-owner-token");
      assert.equal(h.context.state.historyAuthEpoch || 0, epoch);
      page.resolve({ items: items(module, 0, 24), total: 240 });
      await loading;
      assert.equal(historyCalls(h, module).length, 1);
      assert.equal(h.model[h.key].length, 0);
      assert.equal(h.model.historyDemand.loaded, false);
      assert.deepEqual(h.renders, []);
    });

    test(`${prefix}: favorites use an exact filtered page and continue only on explicit gestures`, async () => {
      const h = historyHarness(shell, module, {
        respond: ({ path }) => {
          const offset = Number(new URL(path, "https://example.test").searchParams.get("offset"));
          return { items: items(module, offset, 24, { favorite: true }), total: 120 };
        },
      });
      h.model.historyFavoritesOnly = true;
      if (shell.name === "mobile") h.activate(active, `${module}-history`);
      await h.favorites();
      const favoriteReads = () => historyCalls(h, module).filter(({ path }) => new URL(path, "https://example.test").searchParams.get("favorite") === "true");
      assert.equal(favoriteReads().length, 1);
      // Reopening an already loaded picker/filter is not another page gesture.
      await h.favorites();
      assert.equal(favoriteReads().length, 1);
      for (let page = 0; page < 4; page += 1) await h.more();
      assert.deepEqual(favoriteReads().map(({ path }) => Number(new URL(path, "https://example.test").searchParams.get("offset"))), [0, 24, 48, 72, 96]);
      assert.equal(h.model[h.key].length, 48);
      assert.equal(h.model.historyDemand.start, 72);
      assert.equal(h.model.historyDemand.exhausted, true);
      assert.ok(pageRequests(h, module).every((page) => page.limit === 24));
      assert.equal(historyCalls(h, module).length - favoriteReads().length, shell.name === "desktop" ? 1 : 0);
    });

    test(`${prefix}: closing favorites or navigating away stops the next page`, async () => {
      for (const cancel of ["filter", "picker", "navigate"]) {
        const secondPage = deferred();
        const h = historyHarness(shell, module, {
          respond: ({ calls }) => calls.length === 1
            ? { items: items(module, 0, 24), total: 240 }
            : secondPage.promise,
        });
        if (cancel === "picker") h.els[module === "v1" ? "favoritePickerModal" : "v2FavoriteReferenceModal"].hidden = false;
        else h.model.historyFavoritesOnly = true;
        if (shell.name === "mobile") h.activate(active, `${module}-history`);
        const loading = h.favorites();
        await h.settle();
        assert.equal(historyCalls(h, module).length, 2);
        if (cancel === "navigate") h.activate("lab");
        else if (cancel === "picker") h.els[module === "v1" ? "favoritePickerModal" : "v2FavoriteReferenceModal"].hidden = true;
        else h.model.historyFavoritesOnly = false;
        h.renders.length = 0;
        secondPage.resolve({ items: items(module, 24, 24), total: 240 });
        await loading;
        assert.equal(historyCalls(h, module).length, 2);
        assert.ok(h.renders.every((render) => !render.kind.endsWith("picker")));
        if (cancel === "navigate") assert.deepEqual(h.renders, []);
      }
    });

    test(`${prefix}: real deletion finishing offscreen invalidates history without GET or account fan-out`, async () => {
      const deletion = deferred();
      let deleted = false;
      const h = historyHarness(shell, module, {
        respond: ({ options }) => {
          if (options.method === "DELETE") { deleted = true; return deletion.promise; }
          return { items: items(module, deleted ? 100 : 0, 24), total: 24 };
        },
      });
      h.install(["deleteHistoryItem", "deleteV2HistoryItem", "historyItemCanDelete", "accountOverviewDemanded", "refreshVeyraAccountPanelAfterHistoryChange"]);
      h.context.window.confirm = () => true;
      await h.refresh();
      const entry = { ...h.model[h.key][0], can_delete: true };
      const card = node();
      const image = Object.assign(node({ mediaLoadToken: "pending", authenticatedObjectUrl: "blob:deleted" }), { tagName: "IMG" });
      card.appendChild(image);
      const released = [];
      h.context.releaseImageObjectUrl = (target) => {
        released.push(target.dataset.authenticatedObjectUrl);
        delete target.dataset.authenticatedObjectUrl;
      };
      const deleting = h.context[module === "v1" ? "deleteHistoryItem" : "deleteV2HistoryItem"](entry, card);
      h.activate("lab");
      h.renders.length = 0;
      deletion.resolve({ deleted: true });
      await deleting;
      assert.equal(h.notices.filter(([, type]) => type === "error").length, 0, JSON.stringify(h.notices));
      assert.equal(h.calls.filter((call) => call.options.method === "DELETE").length, 1);
      assert.equal(historyCalls(h, module).length, 1);
      assert.equal(h.calls.some((call) => /usage|prompt-cases|\/veyra\/me/.test(call.path)), false);
      assert.equal(h.model.historyDemand.dirty, true);
      assert.equal(h.model.historyHeroItems.some((item) => module === "v1" ? item.id === entry.id : item.output_id === entry.output_id), false);
      if (module === "v1") {
        assert.deepEqual(released, ["blob:deleted"]);
        assert.equal(image.dataset.mediaLoadToken, "");
        assert.equal(card.querySelectorAll("img").length, 0);
      }
      assert.equal(h.context.veyraState.overviewDirty, true);
      assert.deepEqual(h.renders, []);
      h.activate(active);
      await h.context.ensureHistoryDemand(module);
      assert.equal(historyCalls(h, module).length, 2);
      assert.equal(h.model[h.key][0][module === "v1" ? "id" : "output_id"], `${module}-100`);
    });
  }

  test(`${shell.name} v2: renderable fill is bounded to three pages and offsets count raw rows`, async () => {
    const h = historyHarness(shell, "v2", {
      respond: ({ path }) => {
        const offset = Number(new URL(path, "https://example.test").searchParams.get("offset"));
        // Duplicate IDs and non-renderable rows are retained in the server's
        // offset window even though they do not yield new visible cards.
        return { items: items("v2", offset === 24 ? 0 : offset, 24, { renderable: false }), total: 240 };
      },
    });
    await h.refresh();
    assert.deepEqual(pageRequests(h, "v2").map((page) => page.offset), [0, 24, 48]);
    assert.equal(h.model.historyDemand.offset, 72);
    assert.equal(h.model.history.length, 48);
    await h.more();
    assert.deepEqual(pageRequests(h, "v2").map((page) => page.offset), [0, 24, 48, 72, 96, 120]);
    assert.equal(h.model.historyDemand.offset, 144);
  });

  test(`${shell.name} v2: empty sparse windows expose working previous and next controls`, async () => {
    const h = historyHarness(shell, "v2", {
      respond: ({ path }) => {
        const offset = Number(new URL(path, "https://example.test").searchParams.get("offset"));
        return { items: items("v2", offset, 24, { renderable: offset >= 72 }), total: 144 };
      },
    });
    installHistoryRenderers(h, "v2");
    const grid = h.els.v2HistoryGrid;
    const findButton = (label) => grid.children.flatMap((child) => child.children || []).find((button) => button.textContent === label);
    await h.refresh();
    assert.equal(grid.querySelectorAll("img").length, 0);
    assert.equal(h.model.historyDemand.offset, 72);
    await findButton("下一组历史（可返回）").events.get("click")();
    assert.equal(h.model.historyDemand.start, 72);
    assert.equal(grid.querySelectorAll("img").length, 24);
    await findButton("上一组历史").events.get("click")();
    assert.equal(h.model.historyDemand.start, 0);
    assert.equal(grid.querySelectorAll("img").length, 0);
    assert.ok(findButton("下一组历史（可返回）"));
    await findButton("下一组历史（可返回）").events.get("click")();
    await h.more();
    await h.more();
    assert.equal(h.model.historyDemand.exhausted, true);
    assert.equal(grid.querySelectorAll("img").length, 72);
    assert.ok(findButton("上一组历史"));
    assert.equal(findButton("下一组历史（可返回）"), undefined);
  });

  for (const exhausted of [false, true]) {
    test(`${shell.name} v2: a 23-card remainder ${exhausted ? "is revealed without GET when exhausted" : "fetches to fill the next 24-card gesture"}`, async () => {
      const h = historyHarness(shell, "v2", {
        respond: ({ path }) => {
          const offset = Number(new URL(path, "https://example.test").searchParams.get("offset"));
          const page = items("v2", offset, 24);
          if (offset === 0) page[23].renderable = false;
          return { items: page, total: exhausted ? 48 : 96 };
        },
      });
      await h.refresh();
      assert.deepEqual(pageRequests(h, "v2").map((page) => page.offset), [0, 24]);
      assert.equal(h.model.history.filter((item) => item.renderable !== false).length, 47);
      assert.equal(h.model.historyRenderLimit, 24);
      await h.more();
      assert.deepEqual(pageRequests(h, "v2").map((page) => page.offset), exhausted ? [0, 24] : [0, 24, 48]);
      assert.equal(h.model.historyRenderLimit, exhausted ? 47 : 48);
      assert.equal(h.model.historyDemand.offset, exhausted ? 48 : 72);
      assert.ok(pageRequests(h, "v2").every((page) => page.limit === 24));
    });
  }

  for (const initiallyVisible of [0, 22]) {
    test(`${shell.name} v2: after the 72-row window shows ${initiallyVisible} cards, the next window starts with 24`, async () => {
      const h = historyHarness(shell, "v2", {
        respond: ({ path }) => {
          const offset = Number(new URL(path, "https://example.test").searchParams.get("offset"));
          return {
            items: items("v2", offset, 24).map((item, index) => ({
              ...item,
              renderable: offset >= 72 || offset + index < initiallyVisible,
            })),
            total: 240,
          };
        },
      });
      const visibleCount = () => Math.min(h.model.historyRenderLimit,
        h.model.history.filter((item) => item.renderable !== false).length);
      await h.refresh();
      assert.deepEqual(pageRequests(h, "v2").map((page) => page.offset), [0, 24, 48]);
      assert.equal(visibleCount(), initiallyVisible);
      assert.equal(h.model.historyDemand.offset, 72);
      await h.more();
      assert.deepEqual(pageRequests(h, "v2").map((page) => page.offset), [0, 24, 48, 72]);
      assert.equal(h.model.historyRenderLimit, 24);
      assert.equal(visibleCount(), 24);
      assert.equal(h.model.historyDemand.start, 72);
      assert.equal(h.model.historyDemand.offset, 96);
      assert.ok(pageRequests(h, "v2").every((page) => page.limit === 24));
    });
  }

  for (const module of ["v1", "v2"]) {
    test(`${shell.name}: real direct-${module} bootstrap does not initialize the other product`, async () => {
      const h = historyHarness(shell, module);
      installBootstrap(h, shell);
      await h.listeners.get("DOMContentLoaded")();
      await h.settle();
      assert.equal(h.notices.filter(([, type]) => type === "error").length, 0, JSON.stringify(h.notices));
      assert.equal(historyCalls(h, module).length, 1);
      assert.equal(historyCalls(h, module)[0].path.includes("limit=24"), true);
      if (module === "v2") {
        assert.deepEqual(h.calls.filter((call) => call.module === "v1"), []);
        assert.ok(h.calls.some((call) => call.path === "/resource-providers"));
        assert.equal(h.context.v2State.loaded, true);
      } else {
        assert.equal(h.calls.filter((call) => call.path === "/v1/sessions").length, 1);
        assert.equal(h.calls.filter((call) => call.path === "/v1/providers").length, 1);
        assert.deepEqual(h.calls.filter((call) => call.module === "v2" && !["/veyra/me", "/veyra/session-cookie"].includes(call.path)), []);
      }
    });
  }

  test(`${shell.name}: the real V3 entry and project bootstrap require no V1 session or provider configuration`, async () => {
    const h = historyHarness(shell, "v1", {
      respond: ({ path }) => path.startsWith("/api/v3/creative-agent/projects")
        ? { templates: [{ template_id: "general_creative" }], projects: [], total: 0 }
        : { user: { user_id: "owner", balance: 10 } },
    });
    installBootstrap(h, shell);
    const forbiddenReads = [];
    for (const key of ["sessionId", "selectedProvider", "providerSettings", "imageProviderCapabilities"]) {
      Object.defineProperty(h.context.state, key, {
        configurable: true,
        get() { forbiddenReads.push(key); throw new Error(`V3 must not read V1 ${key}`); },
      });
    }
    for (const name of [
      "renderV3ViewState", "renderV3ScenarioState", "renderV3HomeTemplateChooser", "renderV3Projects",
      "renderV3History", "renderV3ProjectDetail", "renderV3Job", "setV3PageLoading",
      "writeV3LocalProjects", "setV3WorkspaceMode", "openV3Home", "renderMobileV3ProjectCards",
      "renderMobileV3ProjectSkeletons", "setMobileV3LoadingLayer", "normalizeMobileV3HomeSurface",
      "persistMobileV3Caches",
    ]) h.context[name] = () => {};
    h.context.updateV3Notice = (...args) => h.notices.push(args);
    h.context.updateMobileV3Status = (message) => h.notices.push([message, "info"]);
    h.context.readV3LocalProjects = () => [];
    h.context.waitForV3Paint = h.context.waitForV3HomePreviewImages = h.context.waitForMobileV3HomePreviewImages = async () => {};
    if (shell.name === "desktop") {
      h.context.v3ApiBase = "/api/v3/creative-agent";
      h.context.v3ProjectFetchLimit = h.context.v3ProjectHomePageSize;
      h.context.v3State.projects = [];
      h.install(["initialV3ScenarioFromPath", "initialV3WorkspaceFromRoute", "initV3Shell", "mergeV3ProjectItems"]);
      h.context.window.location.search = "?module=v3";
      await h.listeners.get("DOMContentLoaded")();
    } else {
      // Mobile's existing entry is the V3 tab; its URL normalizer does not
      // support module=v3. Exercise that real entry without inventing a route.
      h.context.mobileV3State = { projects: [], templates: [], selectedTemplate: "" };
      h.context.mobileV3ProjectFetchLimit = h.context.mobileV3ProjectPageSize;
      h.context.mobileV3Request = (path) => h.context.request(`/api/v3/creative-agent${path}`);
      h.context.mobileV3VisibleProjects = () => h.context.mobileV3State.projects;
      h.install([
        "loadMobileV3Projects", "mergeMobileV3ProjectItems", "mobileV3TemplateCards",
        "mobileV3TemplateById", "mobileV3ProjectCountLabel", "loadMobileV3HomePreviews",
        "mobileV3ProjectDetailLoadingActive",
      ]);
      h.context.switchTab("v3");
    }
    await h.settle();
    const model = shell.name === "desktop" ? h.context.v3State : h.context.mobileV3State;
    assert.equal(model.loaded, true, JSON.stringify(h.notices));
    assert.equal(model.templates.length, 1, JSON.stringify(h.notices));
    assert.equal(model.projectsTotal, 0);
    assert.deepEqual(forbiddenReads, []);
    assert.equal(h.calls.filter((call) => call.path.startsWith("/api/v3/creative-agent/projects")).length, 1);
    assert.equal(h.calls.some((call) => call.path.startsWith("/v1/")), false);
    assert.equal(historyCalls(h, "v1").length, 0);
    assert.equal(historyCalls(h, "v2").length, 0);
  });

  for (const defaultProvider of ["doubao_image", "openai_gpt_image", "gemini_image"]) {
    test(`${shell.name}: direct Lab entry submits configured Doubao with runtime default ${defaultProvider}`, async () => {
      const h = labHarness(shell, { defaultProvider });
      await h.listeners.get("DOMContentLoaded")();
      await h.settle();
      assert.equal(h.context.document.body.dataset.activeModule, "lab");
      assert.equal(h.context.state.providerSettingsReady, true, JSON.stringify(h.notices));
      assert.equal(h.context.labProviderPreference(), "doubao_image", "unconfigured OpenAI and disabled Gemini fall back to the configured provider");
      await h.context.runLabExploration();
      const submissions = h.calls.filter(({ path, options }) => path === "/api/lab/rare-style-explorer/sessions" && options.method === "POST");
      assert.equal(submissions.length, 1, JSON.stringify(h.notices));
      assert.equal(submissions[0].options.body.provider_preference, "doubao_image");
      assert.deepEqual(h.calls.filter(({ path }) => path.startsWith("/v1/")).map(({ path }) => path), [
        "/v1/providers", "/v1/runtime/provider-settings",
      ]);
      assertLabIsolation(h);
    });
  }

  test(`${shell.name}: immediate Lab submission waits for the shared provider read without duplicating it`, async () => {
    const gate = deferred();
    const h = labHarness(shell, { providerGate: gate });
    await h.listeners.get("DOMContentLoaded")();
    const submission = h.context.runLabExploration();
    await h.settle();
    assert.equal(h.calls.some(({ options }) => options.method === "POST" && options.body?.provider_preference), false);
    assert.equal(h.calls.filter(({ path }) => path === "/v1/providers").length, 1);
    assert.equal(h.calls.filter(({ path }) => path === "/v1/runtime/provider-settings").length, 1);
    gate.resolve();
    await submission;
    await h.settle();
    const submissions = h.calls.filter(({ path }) => path === "/api/lab/rare-style-explorer/sessions");
    assert.equal(submissions.length, 1, JSON.stringify(h.notices));
    assert.equal(submissions[0].options.body.provider_preference, "doubao_image");
    assert.equal(h.calls.filter(({ path }) => path === "/v1/providers").length, 1);
    assertLabIsolation(h);
  });

  test(`${shell.name}: concurrent Lab and V1 entry share one provider-configuration request pair`, async () => {
    const gate = deferred();
    const h = labHarness(shell, { providerGate: gate });
    await h.listeners.get("DOMContentLoaded")();
    h.activate("image");
    const v1 = h.context.ensureV1Module();
    await h.settle();
    assert.equal(h.calls.filter(({ path }) => path === "/v1/providers").length, 1);
    assert.equal(h.calls.filter(({ path }) => path === "/v1/runtime/provider-settings").length, 1);
    gate.resolve();
    await v1;
    assert.equal(h.context.state.providerSettingsReady, true, JSON.stringify(h.notices));
    assert.equal(h.context.state.v1ModuleReady, true);
    assert.equal(h.context.labProviderPreference(), "doubao_image");
    assert.equal(h.calls.filter(({ path }) => path === "/v1/providers").length, 1);
    assert.equal(h.calls.filter(({ path }) => path === "/v1/runtime/provider-settings").length, 1);
    assert.equal(h.calls.filter(({ path }) => path === "/v1/sessions").length, 1);
    assert.equal(h.calls.filter(({ path }) => path.startsWith("/v1/image/history?")).length, 1);
    assert.equal(historyCalls(h, "v2").length, 0);
  });

  test(`${shell.name}: a Lab provider-configuration failure surfaces an error and never submits a guessed default`, async () => {
    const gate = deferred();
    const h = labHarness(shell, { providerGate: gate });
    await h.listeners.get("DOMContentLoaded")();
    const submission = h.context.runLabExploration();
    gate.reject(new Error("provider configuration unavailable"));
    await submission;
    await h.settle();
    assert.equal(h.calls.some(({ path }) => path === "/api/lab/rare-style-explorer/sessions"), false);
    assert.equal(Boolean(h.context.state.providerSettingsReady), false);
    assert.equal(h.context.labState.loading, false);
    assert.ok(h.notices.some(([message, type]) => type === "error" && message.includes("provider configuration unavailable")));
    assertLabIsolation(h);
  });

  test(`${shell.name}: an account change while Lab waits for provider settings prevents its queued submission`, async () => {
    for (const transition of ["token", "raw-storage"]) {
      const gate = deferred();
      const h = labHarness(shell, { providerGate: gate });
      await h.listeners.get("DOMContentLoaded")();
      const submission = h.context.runLabExploration();
      if (transition === "token") h.context.setVeyraToken("new-owner-token");
      else h.context.localStorage.setItem(h.context.veyraTokenStorageKey, "new-owner-token");
      gate.resolve();
      await submission;
      await h.settle();
      assert.equal(h.calls.some(({ path }) => path === "/api/lab/rare-style-explorer/sessions"), false);
      assert.equal(h.context.labState.loading, false);
      assert.ok(h.notices.some(([message, type]) => type === "error" && message.includes("Account changed")));
      assertLabIsolation(h);
    }
  });

  test(`${shell.name}: stale Lab provider reads do not restart after account reset and navigation to V2 or V3`, async () => {
    for (const nextModule of ["v2", "v3"]) {
      for (const explicitSubmission of [false, true]) {
        const gate = deferred();
        const h = labHarness(shell, { providerGate: gate });
        await h.listeners.get("DOMContentLoaded")();
        const submission = explicitSubmission ? h.context.runLabExploration() : null;
        h.context.setVeyraToken("new-owner-token");
        h.activate(nextModule);
        assert.equal(h.context.sharedProviderSettingsDemanded(), false);
        gate.resolve();
        if (submission) await submission;
        await h.settle();
        assert.equal(h.calls.filter(({ path }) => path === "/v1/providers").length, 1);
        assert.equal(h.calls.filter(({ path }) => path === "/v1/runtime/provider-settings").length, 1);
        assert.equal(h.context.state.providerSettingsReady, false);
        assert.equal(h.calls.some(({ path }) => path === "/api/lab/rare-style-explorer/sessions"), false);
        assertLabIsolation(h);
      }
    }
  });

  test(`${shell.name}: an explicit same-owner Lab submission may finish after navigation away`, async () => {
    for (const nextModule of ["v2", "v3"]) {
      const gate = deferred();
      const h = labHarness(shell, { providerGate: gate });
      await h.listeners.get("DOMContentLoaded")();
      const submission = h.context.runLabExploration();
      h.activate(nextModule);
      gate.resolve();
      await submission;
      await h.settle();
      const submissions = h.calls.filter(({ path }) => path === "/api/lab/rare-style-explorer/sessions");
      assert.equal(submissions.length, 1, JSON.stringify(h.notices));
      assert.equal(submissions[0].options.body.provider_preference, "doubao_image");
      assert.equal(h.calls.filter(({ path }) => path === "/v1/providers").length, 1);
      assert.equal(h.calls.filter(({ path }) => path === "/v1/runtime/provider-settings").length, 1);
      assertLabIsolation(h);
    }
  });

  test(`${shell.name}: automatic shared-provider demand excludes unrelated modules and mobile surfaces`, async () => {
    const h = labHarness(shell);
    for (const [module, surface] of [["v2", ""], ["v3", ""], ["lab", "account"], ["image", "v2-history"]]) {
      h.activate(module, surface);
      assert.equal(h.context.sharedProviderSettingsDemanded(), false);
      assert.equal(await h.context.ensureSharedProviderSettings(), false);
    }
    assert.deepEqual(h.calls, []);
    for (const [module, surface] of [["image", ""], ["lab", ""], ["image", "v1-parameters"], ["lab", "lab-references"]]) {
      h.activate(module, surface);
      assert.equal(h.context.sharedProviderSettingsDemanded(), true);
    }
  });

  test(`${shell.name}: ticket login authenticates without account overview or case/usage fan-out`, async () => {
    const h = historyHarness(shell, "v2", { ticket: true });
    installBootstrap(h, shell);
    let accountLoads = 0;
    h.context.loadVeyraAccountPanel = async () => { accountLoads += 1; };
    await h.listeners.get("DOMContentLoaded")();
    await h.settle();
    assert.equal(h.notices.filter(([, type]) => type === "error").length, 0, JSON.stringify(h.notices));
    assert.equal(h.calls.filter((call) => call.path === "/veyra/login").length, 1);
    assert.equal(accountLoads, 0);
    assert.equal(h.calls.some((call) => /usage|prompt-cases/.test(call.path)), false);
    assert.deepEqual(h.calls.filter((call) => call.module === "v1"), []);
    assert.equal(historyCalls(h, "v2").length, 1);
  });

  test(`${shell.name}: V2 catalog initialization completes while history is unresolved and survives its failure`, async () => {
    const history = deferred();
    const h = historyHarness(shell, "v2", {
      respond: ({ path }) => path.includes("/history") ? history.promise : {},
    });
    installBootstrap(h, shell);
    const catalogs = [];
    h.context.applyV2TemplateIndex = (index) => catalogs.push({ type: "index", index });
    h.context.applyV2TemplatePage = (page) => catalogs.push({ type: "page", page });
    let initialized = false;
    const loading = h.context.initV2().then(() => { initialized = true; });
    await h.settle();
    const readyBeforeHistory = initialized && h.context.v2State.loaded;
    const catalogsBeforeHistory = catalogs.length;
    history.reject(new Error("history unavailable"));
    await loading;
    await h.settle();
    assert.equal(readyBeforeHistory, true, "history must not block the independent V2 resource/template bootstrap");
    assert.equal(catalogsBeforeHistory, 2);
    assert.equal(h.context.v2State.loaded, true);
    assert.equal(h.context.v2State.loading, false);
    assert.equal(h.context.v2State.historyDemand.loaded, false);
    assert.equal(historyCalls(h, "v2").length, 1);
    assert.ok(h.notices.some(([, type]) => type === "error"), "history failure has independent feedback");
  });

  test(`${shell.name}: account overview retains 48/72 history and 100-per-product usage sample semantics`, async () => {
    const h = accountHarness(shell, {
      respond: ({ module, path }) => {
        if (path.includes("/history")) {
          const count = module === "v1" ? 48 : 72;
          return {
            items: items(module, 0, count).map((item, index) => ({ ...item, template_case_id: `case-${index % 4}` })),
            total: 10000,
          };
        }
        if (path.includes("/usage")) return {
          items: Array.from({ length: 100 }, (_, index) => ({
            idempotency_key: index === 0 ? "shared" : `${module}-${index}`,
            amount: module === "v1" ? 1 : 2,
          })),
        };
        if (path.startsWith("/prompt-cases/")) return { case_id: path.split("/").at(-1), title: "case" };
        return { user: { user_id: "owner", balance: 10 } };
      },
    });
    await Promise.all([h.context.loadVeyraAccountPanel(), h.context.loadVeyraAccountPanel()]);
    assert.deepEqual(pageRequests(h, "v1"), [{ path: "/v1/image/history", limit: 48, offset: 0 }]);
    assert.deepEqual(pageRequests(h, "v2"), [{ path: "/veyra/history", limit: 72, offset: 0 }]);
    assert.deepEqual(h.calls.filter((call) => call.path.includes("/usage")).map(({ module, path }) => ({ module, path })), [
      { module: "v1", path: "/v1/veyra/usage?limit=100" },
      { module: "v2", path: "/veyra/usage?limit=100" },
    ]);
    assert.equal(h.context.veyraState.history.length, 120);
    assert.equal(h.els.veyraAccountHistoryCount.textContent, "120", "count is the loaded sample, not backend totals or cards rendered");
    assert.equal(h.context.veyraState.usage.length, 199);
    assert.equal(h.els.veyraAccountUsageTotal.textContent, "298");
    assert.equal(h.context.veyraState.usedTemplates.length, 4);
    assert.ok(h.context.veyraState.usedTemplates.every((entry) => entry.usage_count === 18));
    assert.equal(h.calls.filter((call) => call.path.startsWith("/prompt-cases/")).length, 0);
    assert.deepEqual(h.renders, [], "offscreen account sections do not materialize media");
    h.showSection("veyraTemplateHistoryList");
    h.intersect();
    await h.settle();
    assert.equal(h.calls.filter((call) => call.path.startsWith("/prompt-cases/")).length, 4);
    assert.equal(h.context.veyraState.templateHistoryReady, true);
    assert.ok(h.context.veyraState.usedTemplates.every((entry) => entry.usage_count === 18));
    assert.equal(h.renders.filter((render) => render.kind === "account-cases").length, 1);
    const totalCalls = h.calls.length;
    await h.context.loadVeyraAccountPanel();
    assert.equal(h.calls.length, totalCalls, "reopening a clean overview reuses its sample");
  });

  test(`${shell.name}: access view does not start overview requests and notifies the shell of view changes`, async () => {
    const h = accountHarness(shell);
    const accessSource = readFileSync(new URL("../src_skeleton/app/static/account-access.js", import.meta.url), "utf8");
    const events = [];
    let refreshes = 0;
    h.context.accountShell = () => ({ querySelectorAll: (selector) => selector === "[data-account-view]" ? [h.overview, h.access] : [] });
    h.context.refresh = () => { refreshes += 1; };
    h.context.CustomEvent = class { constructor(type, detail) { this.type = type; Object.assign(this, detail); } };
    h.context.document.dispatchEvent = (event) => events.push(event);
    h.install(["setView"], { source: accessSource });
    h.context.setView("access");
    await h.context.loadVeyraAccountPanel();
    assert.equal(refreshes, 1);
    assert.equal(h.overview.hidden, true);
    assert.deepEqual(h.calls, []);
    assert.equal(events.at(-1).type, "alchemy:account-view");
    assert.equal(events.at(-1).detail.view, "access");
    h.context.setView("overview");
    assert.equal(h.overview.hidden, false);
    assert.equal(events.at(-1).detail.view, "overview");
  });

  test(`${shell.name}: hidden account mutation defers reads and a late response renders no sections`, async () => {
    const page = deferred();
    const h = accountHarness(shell, {
      respond: ({ path }) => path.includes("/history") ? page.promise : { user: { user_id: "owner", balance: 10 }, items: [] },
    });
    const loading = h.context.loadVeyraAccountPanel();
    h.activate("v2");
    h.renders.length = 0;
    page.resolve({ items: [], total: 0 });
    await loading;
    assert.deepEqual(h.renders, []);
    const count = h.calls.length;
    await h.context.refreshVeyraAccountPanelAfterHistoryChange();
    assert.equal(h.calls.length, count);
    assert.equal(h.context.veyraState.overviewDirty, true);
  });

  test(`${shell.name}: partial account failure keeps the valid sample without fallback or automatic duplicate reads`, async () => {
    const h = accountHarness(shell, {
      respond: ({ module, path }) => {
        if (module === "v2" && path.includes("/history")) throw new Error("temporarily unavailable");
        if (path.includes("/history")) return { items: items("v1", 0, 48), total: 1000 };
        return { user: { user_id: "owner", balance: 10 }, items: [] };
      },
    });
    await Promise.all([h.context.loadVeyraAccountPanel(), h.context.loadVeyraAccountPanel()]);
    assert.equal(historyCalls(h, "v1").length, 1);
    assert.equal(historyCalls(h, "v2").length, 1);
    assert.equal(h.context.veyraState.history.length, 48);
    assert.equal(h.els.veyraAccountHistoryCount.textContent, "48");
    assert.equal(h.context.veyraState.overviewDirty, true);
    assert.equal(h.els.veyraAccountLoadNotice.hidden, false);
  });

  test(`${shell.name}: account section visibility also responds to scrolling without IntersectionObserver`, async () => {
    const h = accountHarness(shell);
    delete h.context.IntersectionObserver;
    await h.context.loadVeyraAccountPanel();
    assert.deepEqual(h.renders, []);
    assert.equal(typeof h.listeners.get("scroll"), "function");
    h.showSection("veyraAccountHistoryGrid");
    h.listeners.get("scroll")();
    assert.equal(h.renders.filter((render) => render.kind === "account-history").length, 1);
    h.overview.hidden = true;
    h.renders.length = 0;
    h.listeners.get("scroll")();
    assert.deepEqual(h.renders, []);
  });

  test(`${shell.name}: case enrichment is capped at 30, batched four, and canceled when its section closes`, async () => {
    const pending = [];
    const h = accountHarness(shell, {
      respond: ({ path }) => {
        assert.ok(path.startsWith("/prompt-cases/"));
        const detail = deferred();
        pending.push(detail);
        return detail.promise;
      },
    });
    h.context.veyraState.templateHistoryItems = items("v2", 0, 72).map((item, index) => ({ ...item, template_case_id: `case-${index % 36}` }));
    h.showSection("veyraTemplateHistoryList");
    const first = h.context.loadVeyraTemplateHistorySection();
    assert.equal(h.calls.length, 4);
    h.overview.hidden = true;
    pending.splice(0).forEach((detail) => detail.resolve({ title: "case" }));
    await first;
    assert.equal(h.calls.length, 4);
    assert.equal(Boolean(h.context.veyraState.templateHistoryReady), false);
    assert.deepEqual(h.renders, []);

    // Retry after visibility returns. Four cached details need no new request.
    h.overview.hidden = false;
    const second = h.context.loadVeyraTemplateHistorySection();
    let maxConcurrent = 0;
    for (let batch = 0; batch < 10; batch += 1) {
      await h.settle();
      maxConcurrent = Math.max(maxConcurrent, pending.length);
      pending.splice(0).forEach((detail) => detail.resolve({ title: "case" }));
    }
    await second;
    assert.equal(h.calls.length, 30);
    assert.ok(maxConcurrent <= 4);
    assert.equal(h.context.veyraState.usedTemplates.length, 36);
    assert.ok(h.context.veyraState.usedTemplates.every((entry) => entry.usage_count === 2));
  });

  test(`${shell.name}: deferred real session creation cannot restore a previous token or account owner's session`, async () => {
    for (const transition of ["token", "owner", "logout"]) {
      const oldSession = deferred();
      let sessionCalls = 0;
      const h = historyHarness(shell, "v1", {
        respond: () => ++sessionCalls === 1 ? oldSession.promise : { id: "new-owner-session" },
      });
      h.install(["createSession", "getVeyraToken", "setVeyraToken", "setVeyraAccount"]);
      const loading = h.context.createSession({ announce: false });
      if (transition === "owner") h.context.setVeyraAccount({ user: { user_id: "new-owner" } });
      else h.context.setVeyraToken(transition === "logout" ? "" : "new-owner-token");
      oldSession.resolve({ id: "old-owner-session" });
      assert.equal(await loading, null);
      assert.equal(h.context.state.sessionId, null);
      assert.notEqual(h.els.sessionLabel.textContent, "old-owner-session");
      if (transition !== "logout") {
        await h.context.createSession({ announce: false });
        assert.equal(h.context.state.sessionId, "new-owner-session");
        assert.equal(h.els.sessionLabel.textContent, "new-owner-session");
      }
    }
  });

  test(`${shell.name}: deferred real provider and account reads cannot overwrite a new owner`, async () => {
    for (const kind of ["providers", "account"]) {
      const pending = deferred();
      const h = historyHarness(shell, "v1", { respond: () => pending.promise });
      h.install(["getVeyraToken", "setVeyraToken", "setVeyraAccount", "loadProviders", "refreshVeyraAccount"]);
      h.context.state.providerSettings = { owner: "new" };
      const loading = kind === "providers" ? h.context.loadProviders() : h.context.refreshVeyraAccount();
      h.context.setVeyraToken("new-owner-token");
      h.context.setVeyraAccount({ user: { user_id: "new-owner" } });
      pending.resolve({ user: { user_id: "old-owner" }, image: [], default_image_provider: "old-provider" });
      await loading;
      assert.equal(h.context.veyraState.account.user.user_id, "new-owner");
      assert.equal(h.context.state.providerSettings.owner, "new");
    }
  });

  test(`${shell.name}: raw cross-tab token changes fence session, provider, and account responses before the storage event`, async () => {
    for (const kind of ["session", "providers", "account"]) {
      const pending = deferred();
      const h = historyHarness(shell, "v1", { respond: () => pending.promise });
      h.install(["getVeyraToken", "createSession", "loadProviders", "refreshVeyraAccount"]);
      const providerSettings = { owner: "current" };
      const account = h.context.veyraState.account;
      h.context.state.sessionId = "current-session";
      h.context.state.providerSettings = providerSettings;
      const epoch = h.context.state.historyAuthEpoch || 0;
      const loading = kind === "session" ? h.context.createSession()
        : kind === "providers" ? h.context.loadProviders()
          : h.context.refreshVeyraAccount();
      h.context.localStorage.setItem(h.context.veyraTokenStorageKey, "other-tab-owner-token");
      assert.equal(h.context.state.historyAuthEpoch || 0, epoch);
      pending.resolve({ id: "stale-session", user: { user_id: "stale-owner" }, image: [], default_image_provider: "stale-provider" });
      await loading;
      assert.equal(h.context.state.sessionId, "current-session");
      assert.equal(h.context.state.providerSettings, providerSettings);
      assert.equal(h.context.veyraState.account, account);
    }
  });

  test(`${shell.name}: the real storage handler clears old caches and loads only current module demand`, async () => {
    const h = historyHarness(shell, "v2", {
      respond: ({ path }) => path.includes("/history")
        ? { items: items("v2", 100, 24), total: 24 }
        : { user: { user_id: "current-owner", balance: 10 } },
    });
    h.install(["getVeyraToken", "handleHistoryStorageChange", "refreshVeyraAccount", "accountOverviewDemanded"]);
    h.context.state.historyItems = items("v1", 0, 24);
    h.context.v2State.history = items("v2", 0, 24);
    h.context.localStorage.setItem(h.context.veyraTokenStorageKey, "other-tab-owner-token");
    h.context.handleHistoryStorageChange({ key: h.context.veyraTokenStorageKey, oldValue: "session-token", newValue: "other-tab-owner-token" });
    assert.equal(h.context.state.historyItems.length, 0);
    assert.equal(h.context.v2State.history.length, 0);
    await h.settle();
    assert.equal(h.context.state.historyAuthEpoch, 1);
    assert.equal(h.context.veyraState.account.user.user_id, "current-owner");
    assert.equal(h.context.v2State.history[0].output_id, "v2-100");
    assert.equal(h.calls.filter((call) => call.path === "/veyra/me").length, 1);
    assert.equal(historyCalls(h, "v2").length, 1);
    assert.equal(h.calls.some((call) => call.module === "v1"), false);
    assert.equal(h.calls.some((call) => /usage|prompt-cases/.test(call.path)), false);
  });

  test(`${shell.name}: irrelevant or unchanged storage events do no work, and cross-tab logout reads nothing`, async () => {
    const h = historyHarness(shell, "v2");
    h.install(["getVeyraToken", "handleHistoryStorageChange"]);
    const previous = items("v2", 0, 24);
    h.context.v2State.history = previous;
    h.context.handleHistoryStorageChange({ key: "unrelated-setting", oldValue: "old", newValue: "new" });
    h.context.handleHistoryStorageChange({ key: h.context.veyraTokenStorageKey, oldValue: "session-token", newValue: "session-token" });
    await h.settle();
    assert.equal(h.context.v2State.history, previous);
    assert.equal(h.context.state.historyAuthEpoch || 0, 0);
    assert.deepEqual(h.calls, []);
    let signedOut = 0;
    h.context.renderVeyraSignedOut = () => { signedOut += 1; };
    h.context.localStorage.removeItem(h.context.veyraTokenStorageKey);
    h.context.handleHistoryStorageChange({ key: h.context.veyraTokenStorageKey, oldValue: "session-token", newValue: null });
    await h.settle();
    assert.equal(h.context.v2State.history.length, 0);
    assert.equal(h.context.veyraState.account, null);
    assert.equal(signedOut, 1);
    assert.deepEqual(h.calls, []);
  });

  test(`${shell.name}: a cross-tab localStorage.clear event invalidates cached owners despite its null key and values`, async () => {
    const h = historyHarness(shell, "v2");
    h.install(["getVeyraToken", "handleHistoryStorageChange"]);
    h.context.state.historyItems = items("v1", 0, 24);
    h.context.v2State.history = items("v2", 0, 24);
    h.context.veyraState.history = items("v2", 0, 24);
    let signedOut = 0;
    h.context.renderVeyraSignedOut = () => { signedOut += 1; };
    h.context.localStorage.removeItem(h.context.veyraTokenStorageKey);
    h.context.handleHistoryStorageChange({ key: null, oldValue: null, newValue: null });
    await h.settle();
    assert.equal(h.context.state.historyAuthEpoch, 1);
    assert.equal(h.context.state.historyItems.length, 0);
    assert.equal(h.context.v2State.history.length, 0);
    assert.equal(h.context.veyraState.history.length, 0);
    assert.equal(h.context.veyraState.account, null);
    assert.equal(signedOut, 1);
    assert.deepEqual(h.calls, []);
  });

  test(`${shell.name}: module bootstrap joins a stale session then initializes the current owner exactly once`, async () => {
    const oldSession = deferred();
    let sessionCalls = 0;
    const h = historyHarness(shell, "v1", {
      respond: ({ path }) => {
        if (path === "/v1/sessions") return ++sessionCalls === 1 ? oldSession.promise : { id: "new-owner-session" };
        if (path.includes("/history")) return { items: items("v1", 100, 24), total: 24 };
        return {};
      },
    });
    h.install(["ensureV1Module", "createSession", "getVeyraToken", "setVeyraToken"]);
    const old = h.context.ensureV1Module();
    h.context.setVeyraToken("new-owner-token");
    const fresh = h.context.ensureV1Module();
    oldSession.resolve({ id: "old-owner-session" });
    await Promise.all([old, fresh]);
    assert.equal(h.context.state.sessionId, "new-owner-session");
    assert.equal(h.context.state.v1ModuleReady, true);
    assert.equal(sessionCalls, 2);
    assert.equal(historyCalls(h, "v1").length, 1);
  });

  test(`${shell.name}: real media binder neither fetches a fallback nor attaches a late image after demand ends`, async () => {
    for (const transition of ["navigate", "owner", "storage"]) {
      for (const outcome of ["reject", "resolve"]) {
        const media = deferred();
        const h = historyHarness(shell, "v2");
        h.install(["getVeyraToken", "historyMediaDemand", "bindImageWithFallback"]);
        const resolutions = [];
        const attached = [];
        const image = node();
        Object.defineProperty(image, "src", { set(value) { attached.push(value); } });
        h.context.cancelV3DeferredImageLoad = () => {};
        h.context.releaseImageObjectUrl = () => {};
        h.context.uniqueNonEmpty = (values) => [...new Set(values.filter(Boolean))];
        h.context.mediaUrlNeedsAuthenticatedFetch = () => true;
        h.context.resolveAuthenticatedMediaSource = (url) => { resolutions.push(url); return media.promise; };
        h.context.bindImageWithFallback(image, ["/protected/thumbnail", "/protected/full"], {
          shouldContinue: h.context.historyMediaDemand("v2", h.els.v2HistoryGrid),
        });
        assert.deepEqual(resolutions, ["/protected/thumbnail"]);
        if (transition === "navigate") h.activate("lab");
        else if (transition === "owner") h.context.clearHistoryDemandCaches();
        else {
          h.context.localStorage.setItem(h.context.veyraTokenStorageKey, "other-tab-owner-token");
          assert.equal(h.context.state.historyAuthEpoch || 0, 0);
        }
        if (outcome === "reject") media.reject(new Error("thumbnail failed"));
        else media.resolve({ url: "resolved-old-owner-url", objectUrl: false });
        await h.settle();
        image.onerror?.();
        await h.settle();
        assert.deepEqual(resolutions, ["/protected/thumbnail"]);
        assert.deepEqual(attached, []);
      }
    }
  });

  if (shell.name === "mobile") {
    test("mobile: opening surfaces pushes once and only normal user closes call history.back", async () => {
      const h = historyHarness(shell, "v2");
      const navigation = installMobileHistory(h);
      for (const options of [{}, { fromHistory: true }, { silent: true }]) {
        const before = navigation.filter((event) => event.type === "push").length;
        h.context.openMobileSurface("v2-history");
        assert.equal(navigation.filter((event) => event.type === "push").length, before + 1);
        assert.equal(h.context.window.history.state.mobileSurface, "v2-history");
        assert.equal(h.context.window.history.state.mobileToken, before + 1);
        assert.equal(h.surfaces.get("v2-history").hidden, false);
        h.context.closeMobileSurface(options);
        assert.equal(h.context.document.body.dataset.mobileActiveSurface, "");
        assert.equal(h.surfaces.get("v2-history").hidden, true);
        assert.equal(h.els.mobileViewLayer.hidden, true);
      }
      await h.settle();
      assert.equal(navigation.filter((event) => event.type === "push").length, 3);
      assert.equal(navigation.filter((event) => event.type === "back").length, 1);
    });

    test("mobile: the actual popstate callback closes mismatched surfaces without push/back recursion", async () => {
      const h = historyHarness(shell, "v2");
      const navigation = installMobileHistory(h);
      let popstate;
      h.context.window.addEventListener = (name, callback) => { if (name === "popstate") popstate = callback; };
      const start = shell.source.indexOf('  window.addEventListener("popstate", (event) => {');
      const end = shell.source.indexOf("\n  });", start);
      assert.ok(start >= 0 && end > start, "the unchanged mobile popstate listener is present");
      vm.runInContext(shell.source.slice(start, end + 6), h.context, { filename: "mobile:popstate" });
      h.context.openMobileSurface("v2-history");
      popstate({ state: { mobileSurface: "v2-history" } });
      assert.equal(h.context.document.body.dataset.mobileActiveSurface, "v2-history");
      popstate({ state: { mobileSurface: "v1-history" } });
      assert.equal(h.context.document.body.dataset.mobileActiveSurface, "");
      assert.equal(h.surfaces.get("v2-history").hidden, true);
      popstate({ state: null });
      await h.settle();
      assert.equal(navigation.filter((event) => event.type === "push").length, 1);
      assert.equal(navigation.filter((event) => event.type === "back").length, 0);
    });

    test("mobile: module changes silently close surfaces and opening one dismisses existing image/sample modals", async () => {
      const h = historyHarness(shell, "v2");
      const navigation = installMobileHistory(h);
      h.install(["switchTab"]);
      h.context.ensureV1Module = async () => {};
      const dismissed = [];
      h.els.imageLightbox.hidden = false;
      h.els.sampleGuideModal.hidden = false;
      h.context.closeImageLightbox = () => { dismissed.push("image"); h.els.imageLightbox.hidden = true; };
      h.context.closeSampleGuide = () => { dismissed.push("sample"); h.els.sampleGuideModal.hidden = true; };
      h.context.openMobileSurface("v2-history");
      assert.deepEqual(dismissed, ["image", "sample"]);
      h.context.switchTab("image");
      await h.settle();
      assert.equal(h.context.document.body.dataset.activeModule, "image");
      assert.equal(h.context.document.body.dataset.mobileActiveSurface, "");
      assert.equal(h.surfaces.get("v2-history").hidden, true);
      assert.equal(navigation.filter((event) => event.type === "push").length, 1);
      assert.equal(navigation.filter((event) => event.type === "back").length, 0);
    });

    test("mobile: shell and shared account-access click handlers initialize access once in either event order", async () => {
      const accessSource = readFileSync(new URL("../src_skeleton/app/static/account-access.js", import.meta.url), "utf8");
      for (const order of ["shell-first", "shared-first"]) {
        const h = accountHarness(shell);
        h.activate("v2");
        h.install(["openMobileSurface", "closeMobileSurface"]);
        const timers = [];
        const events = [];
        let accessRefreshes = 0;
        h.context.$ = () => null;
        h.context.accountShell = () => ({
          querySelectorAll: (selector) => selector === "[data-account-view]" ? [h.overview, h.access] : [],
          querySelector: (selector) => selector.includes('"access"') ? h.access : h.overview,
        });
        h.context.refresh = () => { accessRefreshes += 1; };
        h.context.CustomEvent = class { constructor(type, detail) { this.type = type; Object.assign(this, detail); } };
        h.context.document.dispatchEvent = (event) => events.push(event);
        h.context.window.setTimeout = (callback) => timers.push(callback);
        h.install(["setView", "bind"], { source: accessSource });
        h.context.window.AlchemyAccountAccess = { setView: h.context.setView };
        h.context.bind();
        const opener = node({ accountOpen: "access", mobileOpen: "account" });
        const click = { target: { closest: (selector) => selector === "[data-account-open]" ? opener : null }, preventDefault() {} };
        if (order === "shared-first") h.listeners.get("click")(click);
        h.context.openMobileSurface("account", opener);
        if (order === "shell-first") h.listeners.get("click")(click);
        for (const callback of timers.splice(0)) callback();
        await h.settle();
        assert.equal(accessRefreshes, 1, order);
        assert.equal(h.access.hidden, false);
        assert.equal(h.overview.hidden, true);
        assert.equal(events.filter((event) => event.type === "alchemy:account-view").length, 1);
        assert.deepEqual(h.calls, [], "opening access must not fetch account overview history/usage/cases");
      }
    });

    for (const module of ["v1", "v2"]) {
      test(`mobile ${module}: a remembered hidden favorites filter does not deep-page the module hero`, async () => {
        const h = historyHarness(shell, module, {
          respond: () => ({ items: items(module, 0, 24), total: 240 }),
        });
        h.model.historyFavoritesOnly = true;
        assert.equal(h.context.historyFavoritesDemanded(module), false);
        await h.context.ensureHistoryDemand(module);
        assert.equal(historyCalls(h, module).length, 1);
      });

      test(`mobile ${module}: closing the real history surface cancels favorite completion`, async () => {
        const secondPage = deferred();
        const h = historyHarness(shell, module, {
          respond: ({ calls }) => calls.length === 1
            ? { items: items(module, 0, 24), total: 240 }
            : secondPage.promise,
        });
        h.install(["openMobileSurface", "closeMobileSurface"]);
        h.model.historyFavoritesOnly = true;
        h.context.openMobileSurface(`${module}-history`);
        await h.settle();
        assert.equal(historyCalls(h, module).length, 2);
        h.context.closeMobileSurface({ silent: true, fromHistory: true });
        assert.equal(h.context.historyFavoritesDemanded(module), false);
        secondPage.resolve({ items: items(module, 24, 24), total: 240 });
        await h.settle();
        assert.equal(historyCalls(h, module).length, 2);
        assert.equal(h.context.document.body.dataset.mobileActiveSurface, "");
        assert.equal(h.surfaces.get(`${module}-history`).hidden, true);
      });
    }
  }
}
